# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the ACES Project.
"""Tests for version-scoped queries and the version resolver."""

import pytest

from aswf.aces.transforms import ACESTransformRegistry
from aswf.aces.transforms._version_resolver import resolve_version_key


@pytest.fixture
def registry():
    return ACESTransformRegistry()


class TestVersionResolver:
    """Tests for the version string resolution."""

    KEYS = [
        "v2.0.0+2025.04.04",
        "v1.3.1",
        "v1.3",
        "v1.2",
        "v1.1",
        "v1.0.3",
        "v1.0.2",
        "v1.0.1",
        "v1.0",
    ]

    def test_exact_pin_with_build(self):
        # Full key with build suffix pins to that exact release
        assert resolve_version_key("v2.0.0+2025.04.04", self.KEYS) == "v2.0.0+2025.04.04"

    def test_semver_resolves_to_latest_build(self):
        # "v2.0.0" resolves to latest build of v2.0.0
        assert resolve_version_key("v2.0.0", self.KEYS) == "v2.0.0+2025.04.04"

    def test_major_minor_resolves_to_latest_patch(self):
        # "v1.3" resolves to v1.3.1 (latest patch), not v1.3
        assert resolve_version_key("v1.3", self.KEYS) == "v1.3.1"

    def test_major_minor_resolves_to_latest_patch_v1_0(self):
        # "v1.0" resolves to v1.0.3 (latest patch)
        assert resolve_version_key("v1.0", self.KEYS) == "v1.0.3"

    def test_major_minor_single_match(self):
        # "v1.2" only has one match, resolves to it
        assert resolve_version_key("v1.2", self.KEYS) == "v1.2"

    def test_without_v_prefix(self):
        assert resolve_version_key("1.3", self.KEYS) == "v1.3.1"

    def test_no_match(self):
        assert resolve_version_key("v99.0", self.KEYS) is None

    def test_no_match_wrong_minor(self):
        assert resolve_version_key("v1.9", self.KEYS) is None

    def test_multiple_builds_picks_latest(self):
        # Simulate future scenario with multiple builds of same semver
        keys = ["v2.0.0+2025.04.04", "v2.0.0+2026.01.15"]
        assert resolve_version_key("v2.0.0", keys) == "v2.0.0+2026.01.15"

    def test_major_minor_with_builds(self):
        # "v2.0" should pick latest across patches and builds
        keys = ["v2.0.0+2025.04.04", "v2.0.0+2026.01.15", "v2.0.1+2026.06.01"]
        assert resolve_version_key("v2.0", keys) == "v2.0.1+2026.06.01"


class TestVersionScopedQueries:
    """Tests for version-scoped registry queries."""

    def test_list_versions(self, registry):
        versions = registry.list_versions()
        assert len(versions) == 9
        assert any("v2.0.0" in v for v in versions)
        assert "v1.3" in versions

    def test_list_transforms_for_v2(self, registry):
        transforms = registry.list_transforms(version="v2.0.0")
        assert len(transforms) == 164

    def test_list_transforms_for_v1_3_1(self, registry):
        transforms = registry.list_transforms(version="v1.3.1")
        assert len(transforms) == 993

    def test_list_transforms_for_v1_3(self, registry):
        # "v1.3" resolves to latest patch (v1.3.1), not v1.3.0
        transforms = registry.list_transforms(version="v1.3")
        assert len(transforms) == 993

    def test_list_transforms_unknown_version(self, registry):
        transforms = registry.list_transforms(version="v99.0")
        assert transforms == []

    def test_list_transforms_version_with_category(self, registry):
        csc = registry.list_transforms(category="CSC", version="v2.0.0")
        assert len(csc) > 0
        assert all(t["transform_type"] == "CSC" for t in csc)

    def test_is_valid_id_version_scoped(self, registry):
        v2_id = "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScc.a2.v1"
        # Valid in v2.0.0
        assert registry.is_valid_transform_id(v2_id, version="v2.0.0")
        # Not valid in v1.0.x (didn't exist yet) — "v1.0" resolves to v1.0.3
        assert not registry.is_valid_transform_id(v2_id, version="v1.0")

    def test_get_transform_info_version_scoped(self, registry):
        info = registry.get_transform_info(
            "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScc.a2.v1",
            version="v2.0.0",
        )
        assert info is not None
        assert "v2.0.0" in info["aces_version"]

    def test_get_transform_info_wrong_version(self, registry):
        info = registry.get_transform_info(
            "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScc.a2.v1",
            version="v1.0",
        )
        assert info is None

    def test_get_categories_version_scoped(self, registry):
        v2_cats = registry.get_transform_categories(version="v2.0.0")
        v1_cats = registry.get_transform_categories(version="v1.0")
        # v2 should have CSC, v1 should have IDT
        assert "CSC" in v2_cats
        assert "IDT" in v1_cats

    def test_fuzzy_version_match(self, registry):
        # "v2.0.0" should work even though key is "v2.0.0+2025.04.04"
        transforms = registry.list_transforms(version="v2.0.0")
        assert len(transforms) > 0

    def test_are_inverses_version_scoped(self, registry):
        assert registry.are_transforms_inverses(
            "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScc.a2.v1",
            "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACEScc_to_ACES.a2.v1",
            version="v2.0.0",
        )

    def test_previous_id_version_scoped(self, registry):
        # A v1.5 previous equivalent ID should be findable within the v2.0.0 version
        # since v2.0.0 transforms list their previous IDs
        info = registry.get_transform_info(
            "urn:ampas:aces:transformId:v1.5:ACEScsc.Academy.ACES_to_ACEScc.a1.0.3",
            version="v2.0.0",
        )
        assert info is not None

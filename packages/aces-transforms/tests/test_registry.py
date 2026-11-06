# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the ACES Project.
"""Tests for the ACES transform registry."""

import pytest

from aswf.aces.transforms import ACESTransformRegistry


@pytest.fixture
def registry():
    return ACESTransformRegistry()


class TestACESTransformRegistry:
    def test_loads_transforms(self, registry):
        assert registry.transform_count > 0

    def test_schema_version(self, registry):
        assert registry.schema_version == "1.0.0"

    def test_is_valid_transform_id_known(self, registry):
        assert registry.is_valid_transform_id(
            "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScc.a2.v1"
        )

    def test_is_valid_transform_id_v1(self, registry):
        assert registry.is_valid_transform_id(
            "urn:ampas:aces:transformId:v1.5:ACEScsc.Academy.ACES_to_ACEScc.a1.0.3"
        )

    def test_is_valid_transform_id_unknown(self, registry):
        assert not registry.is_valid_transform_id("urn:ampas:aces:transformId:v99.0:FAKE.Transform")

    def test_is_valid_transform_id_previous_equivalent(self, registry):
        assert registry.is_valid_transform_id("ACEScsc.ACES_to_ACEScc.a1.0.3")

    def test_get_transform_info(self, registry):
        info = registry.get_transform_info(
            "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScc.a2.v1"
        )
        assert info is not None
        assert isinstance(info, dict)
        assert info["user_name"] == "ACES2065-1 to ACEScc"
        assert info["transform_type"] == "CSC"
        assert info["inverse_transform_id"] is not None
        assert info["aces_version"] is not None

    def test_get_transform_info_not_found(self, registry):
        info = registry.get_transform_info("urn:ampas:aces:transformId:v99.0:FAKE")
        assert info is None

    def test_get_transform_info_via_previous_id(self, registry):
        info = registry.get_transform_info("ACEScsc.ACES_to_ACEScc.a1.0.3")
        assert info is not None
        assert "ACES" in info["user_name"]

    def test_list_transforms(self, registry):
        transforms = registry.list_transforms()
        assert len(transforms) > 0
        assert all(isinstance(t, dict) for t in transforms)
        assert all("transform_id" in t for t in transforms)

    def test_list_transforms_by_category(self, registry):
        csc_transforms = registry.list_transforms(category="CSC")
        assert len(csc_transforms) > 0
        assert all(t["transform_type"] == "CSC" for t in csc_transforms)

    def test_get_transform_categories(self, registry):
        categories = registry.get_transform_categories()
        assert len(categories) > 0
        assert "CSC" in categories

    def test_are_transforms_inverses(self, registry):
        assert registry.are_transforms_inverses(
            "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScc.a2.v1",
            "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACEScc_to_ACES.a2.v1",
        )

    def test_are_transforms_not_inverses(self, registry):
        assert not registry.are_transforms_inverses(
            "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScc.a2.v1",
            "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScct.a2.v1",
        )

    def test_get_equivalent_id(self, registry):
        # A legacy ID should resolve to its canonical equivalent
        equivalent = registry.get_equivalent_id("ACEScsc.ACES_to_ACEScc.a1.0.3")
        assert equivalent is not None
        assert equivalent == "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScc.a2.v1"

    def test_get_equivalent_id_already_canonical(self, registry):
        tid = "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScc.a2.v1"
        assert registry.get_equivalent_id(tid) == tid

    def test_get_equivalent_id_unknown(self, registry):
        assert registry.get_equivalent_id("totally.fake.id") is None

    def test_get_equivalent_ids(self, registry):
        ids = registry.get_equivalent_ids(
            "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScc.a2.v1"
        )
        assert isinstance(ids, list)
        assert len(ids) > 0

    def test_get_equivalent_ids_unknown(self, registry):
        ids = registry.get_equivalent_ids("totally.fake.id")
        assert ids == []

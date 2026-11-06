# SPDX-License-Identifier: Apache-2.0
"""Validate that all transform URNs in the registry match XSD regex patterns.

For each supported ACES version (v1.3+), every transform whose type has a
defined XSD pattern must have a transformId that matches that pattern.
This catches registry data issues (typos, format drift) early.
"""

import re

import pytest

from aswf.aces.common.constants import TRANSFORM_ID_PATTERNS, TRANSFORM_TYPES_WITHOUT_PATTERN
from aswf.aces.transforms import ACESTransformRegistry

# Only validate versions we support (v1.3+)
SUPPORTED_VERSIONS = ["v1.3", "v1.3.1", "v2.0.0+2025.04.04"]


@pytest.fixture(scope="module")
def registry():
    return ACESTransformRegistry()


def _compile_patterns():
    """Pre-compile all patterns with full-string anchoring."""
    compiled = {}
    for transform_type, patterns in TRANSFORM_ID_PATTERNS.items():
        compiled[transform_type] = [re.compile(f"^{p}$") for p in patterns]
    return compiled


_COMPILED = _compile_patterns()


@pytest.mark.parametrize("version", SUPPORTED_VERSIONS)
def test_all_transform_ids_match_xsd_patterns(registry, version):
    """Every transform in the registry (for supported versions) must match
    the XSD regex pattern for its transform type.

    Collects all failures and reports them together.
    """
    registry._ensure_loaded()
    idx = registry._version_index.get(version)
    assert idx is not None, f"Version {version} not found in registry"

    failures = []
    skipped_types = set()

    for transform_id, info in idx.items():
        transform_type = info.transform_type

        if transform_type in TRANSFORM_TYPES_WITHOUT_PATTERN:
            skipped_types.add(transform_type)
            continue

        patterns = _COMPILED.get(transform_type)
        if patterns is None:
            failures.append(
                f"  {version} | {transform_type} | {transform_id} "
                f"-- no XSD pattern defined for type '{transform_type}'"
            )
            continue

        if not any(p.match(transform_id) for p in patterns):
            failures.append(
                f"  {version} | {transform_type} | {transform_id}"
            )

    if failures:
        header = f"\n{len(failures)} transform ID(s) in {version} do not match XSD patterns:\n"
        pytest.fail(header + "\n".join(failures))

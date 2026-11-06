# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the ACES Project.
"""
aswf-aces-transforms — ACES transform URN registry.

Provides a bundled snapshot of the official ACES transforms registry
for lookup, validation, and version mapping of ACES transform IDs.

Usage:
    from aswf.aces.transforms import ACESTransformRegistry

    registry = ACESTransformRegistry()
    if registry.is_valid_transform_id("urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScc.a2.v1"):
        info = registry.get_transform_info("urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScc.a2.v1")
"""

from .registry import ACESTransformRegistry

__version__ = "0.1.0"

__all__ = [
    "ACESTransformRegistry",
]

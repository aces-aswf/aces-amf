# SPDX-License-Identifier: Apache-2.0
"""Shared helper to collect nested sub-transforms from input/output types."""

from __future__ import annotations

# (attr_name, human_label) for all nested sub-transform fields that carry
# uuid / file / transformId / hash.
_SUB_TRANSFORM_ATTRS = [
    ("inverse_output_transform", "inverseOutputTransform"),
    ("inverse_output_device_transform", "inverseOutputDeviceTransform"),
    ("inverse_reference_rendering_transform", "inverseReferenceRenderingTransform"),
    ("reference_rendering_transform", "referenceRenderingTransform"),
    ("output_device_transform", "outputDeviceTransform"),
]


def collect_sub_transforms(transform, prefix: str) -> list[tuple[str, object]]:
    """Collect nested sub-transforms that have uuid/file/transformId/hash.

    Works for both InputTransformType and OutputTransformType — attributes
    that don't exist on the given type are safely skipped via getattr.
    """
    subs: list[tuple[str, object]] = []
    for attr, label in _SUB_TRANSFORM_ATTRS:
        sub = getattr(transform, attr, None)
        if sub is not None:
            subs.append((f"{prefix} {label}", sub))
    return subs

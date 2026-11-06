# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the ACES Project.
"""Transform placement validation for authoring APIs."""

from __future__ import annotations

from aswf.aces.common.constants import (
    V2_CSC_TRANSFORM_PREFIXES,
    V2_INPUT_TRANSFORM_PREFIXES,
    V2_INVERSE_ODT_TRANSFORM_PREFIXES,
    V2_INVERSE_OUTPUT_TRANSFORM_PREFIXES,
    V2_INVERSE_RRT_TRANSFORM_PREFIXES,
    V2_LOOK_TRANSFORM_PREFIXES,
    V2_ODT_TRANSFORM_PREFIXES,
    V2_OUTPUT_TRANSFORM_PREFIXES,
    V2_RRT_TRANSFORM_PREFIXES,
)
from aswf.aces.common.types import TransformURN

INPUT_PLACEMENT = (V2_INPUT_TRANSFORM_PREFIXES, "InputTransform")
OUTPUT_PLACEMENT = (V2_OUTPUT_TRANSFORM_PREFIXES, "OutputTransform")
LOOK_PLACEMENT = (V2_LOOK_TRANSFORM_PREFIXES, "LookTransform")


def validate_transform_placement(
    transform_id: str | None,
    allowed: frozenset[str],
    label: str,
) -> None:
    """Validate that a transform_id URN prefix is allowed for the given container.

    Raises ValueError if the transform_id has a type prefix not in the allowed set.
    No-ops if transform_id is None or not a parseable ACES URN.
    """
    if transform_id is None:
        return
    parsed = TransformURN.parse(transform_id)
    if parsed and parsed.transform_type not in allowed:
        raise ValueError(
            f"Transform ID '{transform_id}' has type '{parsed.transform_type}' "
            f"which is not valid for {label}. "
            f"Allowed: {sorted(allowed)}"
        )


def validate_input_transform_placement(transform) -> None:
    """Validate placement for an input transform and its nested transforms."""
    validate_transform_placement(transform.transform_id, *INPUT_PLACEMENT)
    _validate_nested_transform(
        transform,
        "inverse_output_transform",
        V2_INVERSE_OUTPUT_TRANSFORM_PREFIXES,
        "Input inverseOutputTransform",
    )
    _validate_nested_transform(
        transform,
        "inverse_output_device_transform",
        V2_INVERSE_ODT_TRANSFORM_PREFIXES,
        "Input inverseOutputDeviceTransform",
    )
    _validate_nested_transform(
        transform,
        "inverse_reference_rendering_transform",
        V2_INVERSE_RRT_TRANSFORM_PREFIXES,
        "Input inverseReferenceRenderingTransform",
    )


def validate_output_transform_placement(transform) -> None:
    """Validate placement for an output transform and its nested transforms."""
    validate_transform_placement(transform.transform_id, *OUTPUT_PLACEMENT)
    _validate_nested_transform(
        transform,
        "reference_rendering_transform",
        V2_RRT_TRANSFORM_PREFIXES,
        "Output referenceRenderingTransform",
    )
    _validate_nested_transform(
        transform,
        "output_device_transform",
        V2_ODT_TRANSFORM_PREFIXES,
        "Output outputDeviceTransform",
    )


def validate_look_transform_placement(transform) -> None:
    """Validate placement for a look transform and its CDL working-space transforms."""
    validate_transform_placement(transform.transform_id, *LOOK_PLACEMENT)

    if transform.cdl_working_space is None:
        return

    working_space = transform.cdl_working_space
    if working_space.from_cdl_working_space is not None:
        validate_transform_placement(
            working_space.from_cdl_working_space.transform_id,
            V2_CSC_TRANSFORM_PREFIXES,
            "Look fromCdlWorkingSpace",
        )
    if working_space.to_cdl_working_space is not None:
        validate_transform_placement(
            working_space.to_cdl_working_space.transform_id,
            V2_CSC_TRANSFORM_PREFIXES,
            "Look toCdlWorkingSpace",
        )


def _validate_nested_transform(transform, attr: str, allowed: frozenset[str], label: str) -> None:
    """Validate placement for a named nested transform attribute if present."""
    nested = getattr(transform, attr, None)
    if nested is not None:
        validate_transform_placement(nested.transform_id, allowed, label)

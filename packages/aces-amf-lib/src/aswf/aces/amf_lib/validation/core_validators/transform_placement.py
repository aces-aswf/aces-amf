# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the ACES Project.
"""Transform type placement validation.

Checks that transform_id URN prefixes match their container type
(e.g., IDT URNs belong in InputTransformType, not OutputTransformType).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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

from aswf.aces.amf_lib.protocols import AMFValidator
from aswf.aces.amf_lib.validation.types import ValidationContext, ValidationLevel, ValidationMessage, ValidationType

if TYPE_CHECKING:
    from pathlib import Path

    from aswf.aces.amf_lib.amf import AcesMetadataFile

_SUB_TRANSFORM_PREFIXES: dict[str, frozenset[str]] = {
    "inverse_output_transform": V2_INVERSE_OUTPUT_TRANSFORM_PREFIXES,
    "inverse_output_device_transform": V2_INVERSE_ODT_TRANSFORM_PREFIXES,
    "inverse_reference_rendering_transform": V2_INVERSE_RRT_TRANSFORM_PREFIXES,
    "reference_rendering_transform": V2_RRT_TRANSFORM_PREFIXES,
    "output_device_transform": V2_ODT_TRANSFORM_PREFIXES,
}

_SUB_TRANSFORM_LABELS: dict[str, str] = {
    "inverse_output_transform": "inverseOutputTransform",
    "inverse_output_device_transform": "inverseOutputDeviceTransform",
    "inverse_reference_rendering_transform": "inverseReferenceRenderingTransform",
    "reference_rendering_transform": "referenceRenderingTransform",
    "output_device_transform": "outputDeviceTransform",
}


class TransformTypePlacementValidator(AMFValidator):
    name = "transform_placement"

    def validate(self, amf: AcesMetadataFile, context: ValidationContext) -> list[ValidationMessage]:
        messages: list[ValidationMessage] = []

        if amf.pipeline:
            messages.extend(_validate_pipeline_placement(amf.pipeline, "", context.amf_path))

        for idx, archived in enumerate(amf.archived_pipeline):
            messages.extend(_validate_pipeline_placement(archived, f"Archived pipeline #{idx + 1} ", context.amf_path))

        return messages


def _validate_pipeline_placement(pipeline, prefix: str, amf_path: Path | None) -> list[ValidationMessage]:
    """Collect placement errors for all transforms in a pipeline."""
    messages: list[ValidationMessage] = []

    if pipeline.input_transform:
        _check_placement(
            pipeline.input_transform.transform_id,
            V2_INPUT_TRANSFORM_PREFIXES,
            f"{prefix}InputTransform",
            ValidationLevel.ERROR,
            messages,
            amf_path,
        )
        _check_sub_transform_placements(pipeline.input_transform, f"{prefix}Input", messages, amf_path)

    for idx, lt in enumerate(pipeline.look_transforms):
        desc = lt.description or f"Look transform #{idx + 1}"
        _check_placement(
            lt.transform_id,
            V2_LOOK_TRANSFORM_PREFIXES,
            f"{prefix}{desc}",
            ValidationLevel.ERROR,
            messages,
            amf_path,
        )
        if lt.cdl_working_space:
            ws = lt.cdl_working_space
            if ws.from_cdl_working_space:
                _check_placement(
                    ws.from_cdl_working_space.transform_id,
                    V2_CSC_TRANSFORM_PREFIXES,
                    f"{prefix}{desc} fromCdlWorkingSpace",
                    ValidationLevel.ERROR,
                    messages,
                    amf_path,
                )
            if ws.to_cdl_working_space:
                _check_placement(
                    ws.to_cdl_working_space.transform_id,
                    V2_CSC_TRANSFORM_PREFIXES,
                    f"{prefix}{desc} toCdlWorkingSpace",
                    ValidationLevel.ERROR,
                    messages,
                    amf_path,
                )

    if pipeline.output_transform:
        _check_placement(
            pipeline.output_transform.transform_id,
            V2_OUTPUT_TRANSFORM_PREFIXES,
            f"{prefix}OutputTransform",
            ValidationLevel.ERROR,
            messages,
            amf_path,
        )
        _check_sub_transform_placements(pipeline.output_transform, f"{prefix}Output", messages, amf_path)

    return messages


def _check_sub_transform_placements(
    transform, prefix: str, messages: list[ValidationMessage], amf_path: Path | None
) -> None:
    """Check nested sub-transforms (RRT, ODT, inverse variants) for placement errors."""
    for attr, allowed in _SUB_TRANSFORM_PREFIXES.items():
        sub = getattr(transform, attr, None)
        if sub is not None:
            label = _SUB_TRANSFORM_LABELS[attr]
            _check_placement(
                sub.transform_id,
                allowed,
                f"{prefix} {label}",
                ValidationLevel.ERROR,
                messages,
                amf_path,
            )


def _check_placement(
    transform_id: str | None,
    allowed: frozenset[str],
    label: str,
    level: ValidationLevel,
    messages: list[ValidationMessage],
    amf_path: Path | None,
) -> None:
    """Append a placement error if transform_id's type prefix is not in allowed."""
    if transform_id is None:
        return
    parsed = TransformURN.parse(transform_id)
    if parsed and parsed.transform_type not in allowed:
        messages.append(
            ValidationMessage(
                level=level,
                validation_type=ValidationType.INVALID_TRANSFORM_ID,
                message=(
                    f"{label}: transform ID '{transform_id}' has type '{parsed.transform_type}' "
                    f"which is not valid for this container. Allowed: {sorted(allowed)}"
                ),
                file_path=amf_path,
            )
        )

# SPDX-License-Identifier: Apache-2.0
"""Transform ID URN format validation (no registry lookup)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from aswf.aces.amf_lib.protocols import AMFValidator
from aswf.aces.amf_lib.validation.types import ValidationContext, ValidationLevel, ValidationMessage, ValidationType
from aswf.aces.amf_lib.validation.core_validators._nested import collect_sub_transforms

if TYPE_CHECKING:
    from aswf.aces.amf_lib.amf import AcesMetadataFile

ACES_TRANSFORM_ID_PATTERN = re.compile(
    r"^urn:ampas:aces:transformId:v[12]\.\d+:"
    r"[A-Za-z][A-Za-z0-9]*"
    r"\.\S+"
    r"$"
)


class TransformIdFormatValidator(AMFValidator):
    name = "transform_ids"

    def validate(self, amf: AcesMetadataFile, context: ValidationContext) -> list[ValidationMessage]:
        messages: list[ValidationMessage] = []

        if amf.pipeline:
            messages.extend(_validate_pipeline_transform_ids(amf.pipeline, "", context.amf_path))

        for idx, archived in enumerate(amf.archived_pipeline):
            messages.extend(
                _validate_pipeline_transform_ids(archived, f"Archived pipeline #{idx + 1} ", context.amf_path)
            )

        return messages


def _validate_pipeline_transform_ids(pipeline, prefix: str, amf_path) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []

    if pipeline.input_transform:
        if pipeline.input_transform.transform_id:
            _check_id(pipeline.input_transform.transform_id, f"{prefix}Input transform", messages, amf_path)
        for sub_label, sub in collect_sub_transforms(pipeline.input_transform, f"{prefix}Input"):
            if sub.transform_id:
                _check_id(sub.transform_id, sub_label, messages, amf_path)

    for idx, lt in enumerate(pipeline.look_transforms):
        if lt.transform_id:
            desc = lt.description or f"Look transform #{idx + 1}"
            _check_id(lt.transform_id, f"{prefix}{desc}", messages, amf_path)

    if pipeline.output_transform:
        if pipeline.output_transform.transform_id:
            _check_id(pipeline.output_transform.transform_id, f"{prefix}Output transform", messages, amf_path)
        for sub_label, sub in collect_sub_transforms(pipeline.output_transform, f"{prefix}Output"):
            if sub.transform_id:
                _check_id(sub.transform_id, sub_label, messages, amf_path)

    # Working space transforms
    for idx, lt in enumerate(pipeline.look_transforms):
        if lt.cdl_working_space:
            ws = lt.cdl_working_space
            if ws.from_cdl_working_space and ws.from_cdl_working_space.transform_id:
                _check_id(
                    ws.from_cdl_working_space.transform_id,
                    f"{prefix}Look #{idx+1} fromCdlWorkingSpace",
                    messages,
                    amf_path,
                )
            if ws.to_cdl_working_space and ws.to_cdl_working_space.transform_id:
                _check_id(
                    ws.to_cdl_working_space.transform_id,
                    f"{prefix}Look #{idx+1} toCdlWorkingSpace",
                    messages,
                    amf_path,
                )

    return messages


def _check_id(transform_id: str, label: str, messages: list[ValidationMessage], amf_path) -> None:
    if not ACES_TRANSFORM_ID_PATTERN.match(transform_id):
        messages.append(
            ValidationMessage(
                level=ValidationLevel.WARNING,
                validation_type=ValidationType.INVALID_TRANSFORM_ID,
                message=f"{label} has malformed transform ID: {transform_id}",
                file_path=amf_path,
            )
        )

# SPDX-License-Identifier: Apache-2.0
"""Metadata completeness validation: descriptions, authors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aswf.aces.amf_lib.protocols import AMFValidator
from aswf.aces.amf_lib.validation.types import ValidationContext, ValidationLevel, ValidationMessage, ValidationType

if TYPE_CHECKING:
    from aswf.aces.amf_lib.amf import AcesMetadataFile


class MetadataValidator(AMFValidator):
    name = "metadata"

    def validate(self, amf: AcesMetadataFile, context: ValidationContext) -> list[ValidationMessage]:
        messages: list[ValidationMessage] = []

        # Check AMF description
        desc = amf.amf_info.description if amf.amf_info else None
        if not desc or not desc.strip():
            messages.append(
                ValidationMessage(
                    level=ValidationLevel.INFO,
                    validation_type=ValidationType.MISSING_DESCRIPTION,
                    message="AMF description is missing or empty",
                    file_path=context.amf_path,
                )
            )

        # Check for at least one author
        authors = amf.amf_info.author if amf.amf_info else []
        if not authors:
            messages.append(
                ValidationMessage(
                    level=ValidationLevel.INFO,
                    validation_type=ValidationType.MISSING_AUTHOR,
                    message="No authors specified",
                    file_path=context.amf_path,
                )
            )

        # Check pipeline description
        if amf.pipeline:
            messages.extend(_validate_pipeline_metadata(amf.pipeline, "", context.amf_path))

        for idx, archived in enumerate(amf.archived_pipeline):
            messages.extend(
                _validate_pipeline_metadata(archived, f"Archived pipeline #{idx + 1} ", context.amf_path)
            )

        return messages


def _validate_pipeline_metadata(pipeline, prefix: str, amf_path) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []

    pipeline_desc = pipeline.pipeline_info.description if pipeline.pipeline_info else None
    if not pipeline_desc or not pipeline_desc.strip():
        messages.append(
            ValidationMessage(
                level=ValidationLevel.INFO,
                validation_type=ValidationType.MISSING_DESCRIPTION,
                message=f"{prefix}Pipeline description is missing or empty",
                file_path=amf_path,
            )
        )

    for idx, lt in enumerate(pipeline.look_transforms):
        if not lt.description or not lt.description.strip():
            messages.append(
                ValidationMessage(
                    level=ValidationLevel.INFO,
                    validation_type=ValidationType.MISSING_TRANSFORM_DESCRIPTION,
                    message=f"{prefix}Look transform #{idx + 1} has no description",
                    file_path=amf_path,
                )
            )

    return messages

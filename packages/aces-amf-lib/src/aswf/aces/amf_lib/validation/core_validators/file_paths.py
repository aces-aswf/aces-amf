# SPDX-License-Identifier: Apache-2.0
"""File path security and portability validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aswf.aces.amf_lib.protocols import AMFValidator
from aswf.aces.amf_lib.validation.types import ValidationContext, ValidationLevel, ValidationMessage, ValidationType
from aswf.aces.amf_lib.validation.core_validators._nested import collect_sub_transforms

if TYPE_CHECKING:
    from aswf.aces.amf_lib.amf import AcesMetadataFile, PipelineType


class FilePathValidator(AMFValidator):
    name = "file_paths"

    def validate(self, amf: AcesMetadataFile, context: ValidationContext) -> list[ValidationMessage]:
        messages: list[ValidationMessage] = []

        if amf.pipeline:
            messages.extend(_validate_pipeline_file_paths(amf.pipeline, "", context.amf_path))

        for idx, archived in enumerate(amf.archived_pipeline):
            messages.extend(
                _validate_pipeline_file_paths(archived, f"Archived pipeline #{idx + 1} ", context.amf_path)
            )

        return messages


def _validate_pipeline_file_paths(pipeline: PipelineType, prefix: str, amf_path) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []

    if pipeline.input_transform:
        file_ref = getattr(pipeline.input_transform, "file", None)
        if file_ref:
            messages.extend(_check_path_security(file_ref, f"{prefix}Input transform", amf_path))
        for sub_label, sub in collect_sub_transforms(pipeline.input_transform, f"{prefix}Input"):
            sub_file = getattr(sub, "file", None)
            if sub_file:
                messages.extend(_check_path_security(sub_file, sub_label, amf_path))

    for idx, lt in enumerate(pipeline.look_transforms):
        desc = f"{prefix}{lt.description or f'Look transform #{idx + 1}'}"
        if lt.file:
            has_ccc_ref = getattr(lt, "color_correction_ref", None) is not None
            messages.extend(_check_path_security(lt.file, desc, amf_path, is_cdl_collection=has_ccc_ref))

    if pipeline.output_transform:
        file_ref = getattr(pipeline.output_transform, "file", None)
        if file_ref:
            messages.extend(_check_path_security(file_ref, f"{prefix}Output transform", amf_path))
        for sub_label, sub in collect_sub_transforms(pipeline.output_transform, f"{prefix}Output"):
            sub_file = getattr(sub, "file", None)
            if sub_file:
                messages.extend(_check_path_security(sub_file, sub_label, amf_path))

    return messages


ALLOWED_TRANSFORM_EXTENSIONS = {".clf"}
ALLOWED_CDL_COLLECTION_EXTENSIONS = {".cc", ".ccc", ".cdl"}


def _check_path_security(
    file_ref: str, label: str, amf_path, *, is_cdl_collection: bool = False
) -> list[ValidationMessage]:
    messages = []

    ext = f".{file_ref.rsplit('.', 1)[-1].lower()}" if "." in file_ref else ""
    if ext:
        allowed = ALLOWED_CDL_COLLECTION_EXTENSIONS if is_cdl_collection else ALLOWED_TRANSFORM_EXTENSIONS
        if ext not in allowed:
            if is_cdl_collection:
                fmt_desc = "CDL collection formats (.cc, .ccc, .cdl) are the supported formats for CDL collection files"
            else:
                fmt_desc = "CLF (.clf) is the supported format for ACES transform files"
            messages.append(
                ValidationMessage(
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.NON_CLF_TRANSFORM_FILE,
                    message=f"{label} uses unsupported format ({ext}): {file_ref}. {fmt_desc}.",
                    file_path=amf_path,
                )
            )

    if ".." in file_ref:
        messages.append(
            ValidationMessage(
                level=ValidationLevel.WARNING,
                validation_type=ValidationType.UNSAFE_FILE_PATH,
                message=f"{label} contains parent directory reference (..): {file_ref}",
                file_path=amf_path,
            )
        )

    if file_ref.startswith("/") or (len(file_ref) > 1 and file_ref[1] == ":"):
        messages.append(
            ValidationMessage(
                level=ValidationLevel.WARNING,
                validation_type=ValidationType.NON_PORTABLE_PATH,
                message=f"{label} uses absolute path (not portable): {file_ref}",
                file_path=amf_path,
            )
        )

    if "\\" in file_ref:
        messages.append(
            ValidationMessage(
                level=ValidationLevel.WARNING,
                validation_type=ValidationType.NON_PORTABLE_PATH,
                message=f"{label} uses backslashes (not portable): {file_ref}",
                file_path=amf_path,
            )
        )

    return messages

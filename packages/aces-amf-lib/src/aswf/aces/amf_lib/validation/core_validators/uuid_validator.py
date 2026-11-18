# SPDX-License-Identifier: Apache-2.0
"""UUID uniqueness validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aswf.aces.amf_lib.protocols import AMFValidator
from aswf.aces.amf_lib.validation.types import ValidationContext, ValidationLevel, ValidationMessage, ValidationType
from aswf.aces.amf_lib.validation.core_validators._nested import collect_sub_transforms

if TYPE_CHECKING:
    from aswf.aces.amf_lib.amf import AcesMetadataFile, PipelineType


class UUIDValidator(AMFValidator):
    name = "uuid"

    def validate(self, amf: AcesMetadataFile, context: ValidationContext) -> list[ValidationMessage]:
        messages: list[ValidationMessage] = []
        uuids: list[tuple[str, str]] = []  # (uuid, label) pairs

        # Collect UUIDs from amfInfo
        if amf.amf_info and amf.amf_info.uuid:
            uuids.append((amf.amf_info.uuid, "amfInfo"))

        # Collect from active pipeline
        if amf.pipeline:
            uuids.extend(_collect_pipeline_uuids(amf.pipeline, "Pipeline"))

        # Collect from archived pipelines
        for idx, archived in enumerate(amf.archived_pipeline):
            uuids.extend(_collect_pipeline_uuids(archived, f"Archived pipeline #{idx + 1}"))

        # Check for duplicates within this file
        seen: dict[str, str] = {}
        for uid, label in uuids:
            if uid in seen:
                messages.append(
                    ValidationMessage(
                        level=ValidationLevel.ERROR,
                        validation_type=ValidationType.DUPLICATE_UUID,
                        message=f"Duplicate UUID {uid} found in {label} and {seen[uid]}",
                        file_path=context.amf_path,
                    )
                )
            else:
                seen[uid] = label

        # Check against cross-file UUID pool
        if context.uuid_pool is not None:
            for uid, label in uuids:
                if uid in context.uuid_pool:
                    messages.append(
                        ValidationMessage(
                            level=ValidationLevel.ERROR,
                            validation_type=ValidationType.DUPLICATE_UUID,
                            message=f"UUID {uid} ({label}) appears in multiple AMF files",
                            file_path=context.amf_path,
                        )
                    )
                context.uuid_pool.add(uid)

        return messages


def _collect_pipeline_uuids(pipeline: PipelineType, prefix: str) -> list[tuple[str, str]]:
    """Collect all UUIDs from a pipeline (active or archived)."""
    uuids: list[tuple[str, str]] = []

    if pipeline.pipeline_info and pipeline.pipeline_info.uuid:
        uuids.append((pipeline.pipeline_info.uuid, f"{prefix} pipelineInfo"))

    if pipeline.input_transform:
        _collect_transform_uuids(pipeline.input_transform, f"{prefix} inputTransform", uuids)
        for sub_label, sub in collect_sub_transforms(pipeline.input_transform, f"{prefix} Input"):
            _collect_transform_uuids(sub, sub_label, uuids)

    for idx, lt in enumerate(pipeline.look_transforms):
        desc = lt.description or f"lookTransform #{idx + 1}"
        _collect_transform_uuids(lt, f"{prefix} {desc}", uuids)
        # Working space transforms
        if lt.cdl_working_space:
            ws = lt.cdl_working_space
            if ws.from_cdl_working_space:
                _collect_transform_uuids(ws.from_cdl_working_space, f"{prefix} {desc} fromCdlWorkingSpace", uuids)
            if ws.to_cdl_working_space:
                _collect_transform_uuids(ws.to_cdl_working_space, f"{prefix} {desc} toCdlWorkingSpace", uuids)

    if pipeline.output_transform:
        _collect_transform_uuids(pipeline.output_transform, f"{prefix} outputTransform", uuids)
        for sub_label, sub in collect_sub_transforms(pipeline.output_transform, f"{prefix} Output"):
            _collect_transform_uuids(sub, sub_label, uuids)

    return uuids


def _collect_transform_uuids(transform, label: str, uuids: list[tuple[str, str]]) -> None:
    """Collect UUID from a transform if present."""
    uid = getattr(transform, "uuid", None)
    if uid:
        uuids.append((uid, label))

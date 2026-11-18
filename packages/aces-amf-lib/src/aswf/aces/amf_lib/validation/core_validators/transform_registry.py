# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the ACES Project.
"""
Transform ID registry validation.

Validates transform IDs against a caller-provided TransformRegistry,
scoped to the ACES system version declared by the AMF pipeline.

The registry must be injected via ValidationContext.transform_registry.
If no registry is provided, RegistryNotConfiguredError is raised.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aswf.aces.common.types import TransformURN

from aswf.aces.amf_lib.protocols import AMFValidator
from aswf.aces.amf_lib.validation.types import (
    RegistryNotConfiguredError,
    ValidationContext,
    ValidationLevel,
    ValidationMessage,
    ValidationType,
)
from aswf.aces.amf_lib.validation.core_validators._nested import collect_sub_transforms

if TYPE_CHECKING:
    from aswf.aces.amf_lib.amf import AcesMetadataFile, PipelineType


class TransformRegistryValidator(AMFValidator):
    """Validates transform IDs against an injected TransformRegistry.

    For each transform ID in the AMF pipeline:

    a) Resolve the AMF system version to the correct registry version key
    b) Validate the URN string is parseable
    c) Check if the URN exists as a transformId in the version-scoped set
    d) If not, check previousEquivalentTransformIds in that set
    e) If found as previousEquivalent, recommend the canonical ID (WARNING)
    f) If not found anywhere, ERROR

    To skip this validator, pass exclude=["transform_id_registry"] to validate_semantic().
    """

    name = "transform_id_registry"

    def validate(self, amf: AcesMetadataFile, context: ValidationContext) -> list[ValidationMessage]:
        if context.transform_registry is None:
            raise RegistryNotConfiguredError(
                "TransformRegistryValidator requires a transform registry but none was provided. "
                "Pass a TransformRegistry to validate_semantic(transform_registry=...) or "
                "exclude this validator with exclude=['transform_id_registry']."
            )

        messages: list[ValidationMessage] = []

        if amf.pipeline:
            self._validate_pipeline(amf.pipeline, "", messages, context)

        for idx, archived in enumerate(amf.archived_pipeline):
            self._validate_pipeline(archived, f"Archived pipeline #{idx + 1} ", messages, context)

        return messages

    def _validate_pipeline(
        self, pipeline: PipelineType, prefix: str, messages: list[ValidationMessage], context: ValidationContext
    ) -> None:
        registry = context.transform_registry

        # (a) Resolve the AMF system version to a registry version string
        version_str = None
        sv = getattr(getattr(pipeline, "pipeline_info", None), "system_version", None)
        if sv is not None:
            version_str = f"v{sv.major_version}.{sv.minor_version}"

        def _check_id(transform_id: str, label: str) -> None:
            # Validation flow:
            #
            # (b) Parse URN → fails → ERROR: malformed
            # (c) Exists as transformId in version set? → VALID
            # (d) Exists as previousEquivalentTransformId? → no → ERROR: unknown
            # (e) Found as previousEquivalent → WARNING: recommend canonical ID

            # (b) Validate URN format
            parsed = TransformURN.parse(transform_id)
            if parsed is None:
                messages.append(
                    ValidationMessage(
                        level=ValidationLevel.ERROR,
                        validation_type=ValidationType.MALFORMED_TRANSFORM_ID,
                        message=f"{label} has malformed transform ID: {transform_id}",
                        file_path=context.amf_path,
                    )
                )
                return

            # (c) Check if transform ID exists directly in the version-scoped set
            info = registry.get_transform_info(transform_id, version=version_str)
            if info is not None and info["transform_id"] == transform_id:
                # Direct match — valid
                return

            # (d) If get_transform_info returned a result, it was found via
            #     previousEquivalentTransformIds (the canonical entry that
            #     lists this ID as a previous equivalent).
            if info is not None:
                # (e) Found as previousEquivalent — recommend the canonical ID
                messages.append(
                    ValidationMessage(
                        level=ValidationLevel.WARNING,
                        validation_type=ValidationType.VERSION_MISMATCH_TRANSFORM_ID,
                        message=(
                            f"{label} uses {transform_id} which is a previous equivalent of "
                            f"{info['transform_id']}. Consider updating to the canonical ID."
                        ),
                        file_path=context.amf_path,
                    )
                )
                return

            # (f/g) Not found in version-scoped set at all — ERROR
            scope = f" for ACES {version_str}" if version_str else ""
            messages.append(
                ValidationMessage(
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.INVALID_TRANSFORM_ID,
                    message=f"{label} uses unknown transform ID{scope}: {transform_id}",
                    file_path=context.amf_path,
                )
            )

        # Input transform + nested sub-transforms
        if pipeline.input_transform:
            if pipeline.input_transform.transform_id:
                _check_id(pipeline.input_transform.transform_id, f"{prefix}Input transform")
            for sub_label, sub in collect_sub_transforms(pipeline.input_transform, f"{prefix}Input"):
                if sub.transform_id:
                    _check_id(sub.transform_id, sub_label)

        # Look transforms + working space transforms
        for idx, lt in enumerate(pipeline.look_transforms):
            if lt.transform_id:
                desc = lt.description or f"Look transform #{idx + 1}"
                _check_id(lt.transform_id, f"{prefix}{desc}")

            if lt.cdl_working_space:
                ws = lt.cdl_working_space
                from_id = ws.from_cdl_working_space.transform_id if ws.from_cdl_working_space else None
                to_id = ws.to_cdl_working_space.transform_id if ws.to_cdl_working_space else None
                if from_id:
                    _check_id(from_id, f"{prefix}Look #{idx+1} fromCdlWorkingSpace")
                if to_id:
                    _check_id(to_id, f"{prefix}Look #{idx+1} toCdlWorkingSpace")
                from_info = registry.get_transform_info(from_id, version=version_str) if from_id else None
                to_info = registry.get_transform_info(to_id, version=version_str) if to_id else None
                if from_info and to_info and not (
                    from_info.get("inverse_transform_id") == to_info["transform_id"]
                    or to_info.get("inverse_transform_id") == from_info["transform_id"]
                ):
                    messages.append(
                        ValidationMessage(
                            level=ValidationLevel.ERROR,
                            validation_type=ValidationType.CDL_WORKING_SPACE_MISMATCH,
                            message=f"{prefix}Look #{idx+1} CDL working-space transforms are not inverses",
                            file_path=context.amf_path,
                        )
                    )

        # Output transform + nested sub-transforms
        if pipeline.output_transform:
            if pipeline.output_transform.transform_id:
                _check_id(pipeline.output_transform.transform_id, f"{prefix}Output transform")
            for sub_label, sub in collect_sub_transforms(pipeline.output_transform, f"{prefix}Output"):
                if sub.transform_id:
                    _check_id(sub.transform_id, sub_label)

# SPDX-License-Identifier: Apache-2.0
"""CDL working space validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aswf.aces.amf_lib.protocols import AMFValidator
from aswf.aces.amf_lib.validation.types import ValidationContext, ValidationLevel, ValidationMessage, ValidationType

from aswf.aces.amf_lib.amf import WorkingLocationType

if TYPE_CHECKING:
    from aswf.aces.amf_lib.amf import AcesMetadataFile


def _count_working_locations(pipeline) -> int:
    """Count workingLocation elements in the compound field."""
    return sum(
        1 for item in pipeline.working_location_or_look_transform
        if isinstance(item, WorkingLocationType)
    )


class WorkingSpaceValidator(AMFValidator):
    name = "working_space"

    def validate(self, amf: AcesMetadataFile, context: ValidationContext) -> list[ValidationMessage]:
        messages: list[ValidationMessage] = []

        if amf.pipeline:
            wl_count = _count_working_locations(amf.pipeline)
            if wl_count > 1:
                messages.append(
                    ValidationMessage(
                        level=ValidationLevel.ERROR,
                        validation_type=ValidationType.MULTIPLE_WORKING_LOCATIONS,
                        message=f"Pipeline has {wl_count} workingLocation elements (at most 1 allowed)",
                        file_path=context.amf_path,
                    )
                )
            messages.extend(_validate_pipeline_working_space(amf.pipeline.look_transforms, "", context.amf_path))

        for idx, archived in enumerate(amf.archived_pipeline):
            wl_count = _count_working_locations(archived)
            if wl_count > 1:
                messages.append(
                    ValidationMessage(
                        level=ValidationLevel.ERROR,
                        validation_type=ValidationType.MULTIPLE_WORKING_LOCATIONS,
                        message=f"Archived pipeline #{idx + 1} has {wl_count} workingLocation elements (at most 1 allowed)",
                        file_path=context.amf_path,
                    )
                )
            messages.extend(
                _validate_pipeline_working_space(
                    archived.look_transforms, f"Archived pipeline #{idx + 1} ", context.amf_path
                )
            )

        return messages


def _validate_pipeline_working_space(look_transforms, prefix: str, amf_path) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []

    for idx, lt in enumerate(look_transforms):
        # Resolve CDL element name alternates (ASC_SOP/SOPNode, ASC_SAT/SatNode)
        sop = lt.asc_sop or getattr(lt, "sopnode", None)
        sat = lt.asc_sat or getattr(lt, "sat_node", None)
        if not sop and not sat:
            continue

        desc = f"{prefix}{lt.description or f'Look transform #{idx + 1}'}"

        if not lt.cdl_working_space:
            messages.append(
                ValidationMessage(
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.MISSING_CDL_WORKING_SPACE,
                    message=f"{desc} has CDL but no working space specified",
                    file_path=amf_path,
                )
            )
            continue

        if not lt.cdl_working_space.from_cdl_working_space:
            messages.append(
                ValidationMessage(
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.CDL_WORKING_SPACE_MISMATCH,
                    message=f"{desc} missing required fromCdlWorkingSpace",
                    file_path=amf_path,
                )
            )

    return messages

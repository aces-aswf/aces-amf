# SPDX-License-Identifier: Apache-2.0
"""CDL value validation: range checks, identity detection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aswf.aces.amf_lib.protocols import AMFValidator
from aswf.aces.amf_lib.validation.types import ValidationContext, ValidationLevel, ValidationMessage, ValidationType

if TYPE_CHECKING:
    from aswf.aces.amf_lib.amf import AcesMetadataFile

# CDL validation constants
CDL_SLOPE_MAX = 5.0
CDL_OFFSET_MIN = -5.0
CDL_OFFSET_MAX = 5.0
CDL_POWER_MAX = 5.0
CDL_SATURATION_MIN = 0.0
CDL_SATURATION_MAX = 2.0
CDL_IDENTITY_TOLERANCE = 1e-6


class CDLValidator(AMFValidator):
    name = "cdl"

    def validate(self, amf: AcesMetadataFile, context: ValidationContext) -> list[ValidationMessage]:
        messages: list[ValidationMessage] = []

        if amf.pipeline:
            messages.extend(_validate_pipeline_cdl(amf.pipeline.look_transforms, "", context.amf_path))

        for idx, archived in enumerate(amf.archived_pipeline):
            messages.extend(
                _validate_pipeline_cdl(archived.look_transforms, f"Archived pipeline #{idx + 1} ", context.amf_path)
            )

        return messages


def _validate_pipeline_cdl(look_transforms, prefix: str, amf_path) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []

    for idx, lt in enumerate(look_transforms):
        desc = f"{prefix}{lt.description or f'Look transform #{idx + 1}'}"

        # ColorCorrectionRef requires an accompanying file in v2
        if lt.color_correction_ref is not None and lt.file is None:
            messages.append(
                ValidationMessage(
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.CDL_MISSING_CCR_FILE,
                    message=f"{desc} has ColorCorrectionRef without a file reference (required in AMF v2)",
                    file_path=amf_path,
                )
            )

        # Resolve CDL element name alternates (ASC_SOP/SOPNode, ASC_SAT/SatNode)
        sop = lt.asc_sop or getattr(lt, "sopnode", None)
        sat = lt.asc_sat or getattr(lt, "sat_node", None)

        if not sop and not sat:
            continue

        # Identity check
        if _is_cdl_identity_from(sop, sat):
            messages.append(
                ValidationMessage(
                    level=ValidationLevel.INFO,
                    validation_type=ValidationType.CDL_IDENTITY,
                    message=f"{desc} has identity CDL (no effect)",
                    file_path=amf_path,
                )
            )

        # Validate SOP values
        if sop:
            slope = sop.slope
            offset = sop.offset
            power = sop.power

            for label, values in [("slope", slope), ("offset", offset), ("power", power)]:
                if values and len(values) != 3:
                    messages.append(
                        ValidationMessage(
                            level=ValidationLevel.ERROR,
                            validation_type=ValidationType.CDL_INVALID_VALUES,
                            message=f"{desc} has invalid {label} format (expected 3 values, got {len(values)})",
                            file_path=amf_path,
                        )
                    )

            if slope:
                for i, s in enumerate(slope):
                    messages.extend(_check_sop_value(s, "slope", i, desc, amf_path))
            if offset:
                for i, o in enumerate(offset):
                    messages.extend(_check_sop_value(o, "offset", i, desc, amf_path))
            if power:
                for i, p in enumerate(power):
                    messages.extend(_check_sop_value(p, "power", i, desc, amf_path))

        # Validate saturation
        if sat and sat.saturation is not None:
            sat_val = sat.saturation
            if sat_val < CDL_SATURATION_MIN:
                messages.append(
                    ValidationMessage(
                        level=ValidationLevel.ERROR,
                        validation_type=ValidationType.CDL_INVALID_VALUES,
                        message=f"{desc} has invalid saturation = {sat_val} (must be >= {CDL_SATURATION_MIN})",
                        file_path=amf_path,
                    )
                )
            elif sat_val == CDL_SATURATION_MIN:
                messages.append(
                    ValidationMessage(
                        level=ValidationLevel.WARNING,
                        validation_type=ValidationType.CDL_EXTREME_VALUES,
                        message=f"{desc} has saturation = 0 (full desaturation)",
                        file_path=amf_path,
                    )
                )
            elif sat_val > CDL_SATURATION_MAX:
                messages.append(
                    ValidationMessage(
                        level=ValidationLevel.WARNING,
                        validation_type=ValidationType.CDL_EXTREME_VALUES,
                        message=f"{desc} has extreme saturation = {sat_val} (recommended: {CDL_SATURATION_MIN}-{CDL_SATURATION_MAX})",
                        file_path=amf_path,
                    )
                )

    return messages


def _is_cdl_identity_from(sop, sat) -> bool:
    if not sop or not sat:
        return False

    slope = sop.slope or [1.0, 1.0, 1.0]
    offset = sop.offset or [0.0, 0.0, 0.0]
    power = sop.power or [1.0, 1.0, 1.0]
    sat_val = sat.saturation if sat.saturation is not None else 1.0

    return (
        all(abs(s - 1.0) < CDL_IDENTITY_TOLERANCE for s in slope)
        and all(abs(o) < CDL_IDENTITY_TOLERANCE for o in offset)
        and all(abs(p - 1.0) < CDL_IDENTITY_TOLERANCE for p in power)
        and abs(sat_val - 1.0) < CDL_IDENTITY_TOLERANCE
    )


def _check_sop_value(value: float, value_type: str, index: int, desc: str, amf_path) -> list[ValidationMessage]:
    messages = []

    if value_type == "slope":
        if value < 0:
            messages.append(
                ValidationMessage(
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.CDL_INVALID_VALUES,
                    message=f"{desc} has invalid slope[{index}] = {value} (must be >= 0)",
                    file_path=amf_path,
                )
            )
        elif value == 0:
            messages.append(
                ValidationMessage(
                    level=ValidationLevel.WARNING,
                    validation_type=ValidationType.CDL_EXTREME_VALUES,
                    message=f"{desc} has slope[{index}] = 0 (fully black channel)",
                    file_path=amf_path,
                )
            )
        elif value > CDL_SLOPE_MAX:
            messages.append(
                ValidationMessage(
                    level=ValidationLevel.WARNING,
                    validation_type=ValidationType.CDL_EXTREME_VALUES,
                    message=f"{desc} has extreme slope[{index}] = {value} (recommended: 0-{CDL_SLOPE_MAX})",
                    file_path=amf_path,
                )
            )

    elif value_type == "offset":
        if value < CDL_OFFSET_MIN or value > CDL_OFFSET_MAX:
            messages.append(
                ValidationMessage(
                    level=ValidationLevel.WARNING,
                    validation_type=ValidationType.CDL_EXTREME_VALUES,
                    message=f"{desc} has extreme offset[{index}] = {value} (recommended: {CDL_OFFSET_MIN} to {CDL_OFFSET_MAX})",
                    file_path=amf_path,
                )
            )

    elif value_type == "power":
        if value <= 0:
            messages.append(
                ValidationMessage(
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.CDL_INVALID_VALUES,
                    message=f"{desc} has invalid power[{index}] = {value} (must be > 0)",
                    file_path=amf_path,
                )
            )
        elif value > CDL_POWER_MAX:
            messages.append(
                ValidationMessage(
                    level=ValidationLevel.WARNING,
                    validation_type=ValidationType.CDL_EXTREME_VALUES,
                    message=f"{desc} has extreme power[{index}] = {value} (recommended: 0-{CDL_POWER_MAX})",
                    file_path=amf_path,
                )
            )

    return messages

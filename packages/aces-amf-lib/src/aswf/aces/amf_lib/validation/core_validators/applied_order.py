# SPDX-License-Identifier: Apache-2.0
"""Transform applied order validation.

Once a look transform has applied=False, all subsequent transforms
must also be applied=False.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aswf.aces.amf_lib.protocols import AMFValidator
from aswf.aces.amf_lib.validation.types import ValidationContext, ValidationLevel, ValidationMessage, ValidationType

if TYPE_CHECKING:
    from aswf.aces.amf_lib.amf import AcesMetadataFile


class AppliedOrderValidator(AMFValidator):
    name = "applied_order"

    def validate(self, amf: AcesMetadataFile, context: ValidationContext) -> list[ValidationMessage]:
        messages: list[ValidationMessage] = []

        if amf.pipeline:
            messages.extend(_validate_pipeline_applied_order(amf.pipeline.look_transforms, "", context.amf_path))

        for idx, archived in enumerate(amf.archived_pipeline):
            messages.extend(
                _validate_pipeline_applied_order(
                    archived.look_transforms, f"Archived pipeline #{idx + 1} ", context.amf_path
                )
            )

        return messages


def _validate_pipeline_applied_order(look_transforms, prefix: str, amf_path) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []
    seen_non_applied = False

    for idx, lt in enumerate(look_transforms):
        desc = f"{prefix}{lt.description or f'Look transform #{idx + 1}'}"
        is_applied = lt.applied if lt.applied is not None else True

        if seen_non_applied and is_applied:
            messages.append(
                ValidationMessage(
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.INVALID_APPLIED_ORDER,
                    message=f"{desc} has applied=True but appears after a non-applied transform. "
                    f"Once applied=False, all subsequent transforms must be applied=False.",
                    file_path=amf_path,
                )
            )

        if not is_applied:
            seen_non_applied = True

    return messages

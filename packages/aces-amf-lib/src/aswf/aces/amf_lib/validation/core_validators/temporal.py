# SPDX-License-Identifier: Apache-2.0
"""Date/time validation: creation <= modification, no future timestamps."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from aswf.aces.amf_lib.protocols import AMFValidator
from aswf.aces.amf_lib.validation.types import ValidationContext, ValidationLevel, ValidationMessage, ValidationType

if TYPE_CHECKING:
    from aswf.aces.amf_lib.amf import AcesMetadataFile

logger = logging.getLogger(__name__)


class TemporalValidator(AMFValidator):
    name = "temporal"

    def validate(self, amf: AcesMetadataFile, context: ValidationContext) -> list[ValidationMessage]:
        messages: list[ValidationMessage] = []

        # AMF info dates
        if amf.amf_info and amf.amf_info.date_time:
            dt = amf.amf_info.date_time
            messages.extend(
                _validate_date_pair(dt.creation_date_time, dt.modification_date_time, "AMF", context.amf_path)
            )

        # Pipeline info dates
        if amf.pipeline and amf.pipeline.pipeline_info and amf.pipeline.pipeline_info.date_time:
            dt = amf.pipeline.pipeline_info.date_time
            messages.extend(
                _validate_date_pair(dt.creation_date_time, dt.modification_date_time, "Pipeline", context.amf_path)
            )

        # Archived pipeline dates
        for idx, archived in enumerate(amf.archived_pipeline):
            if archived.pipeline_info and archived.pipeline_info.date_time:
                dt = archived.pipeline_info.date_time
                label = f"Archived pipeline #{idx + 1}"
                messages.extend(
                    _validate_date_pair(dt.creation_date_time, dt.modification_date_time, label, context.amf_path)
                )

        return messages


def _validate_date_pair(creation_dt, modification_dt, label: str, amf_path) -> list[ValidationMessage]:
    messages = []
    now = datetime.now(timezone.utc)

    try:
        creation = creation_dt.to_datetime() if hasattr(creation_dt, "to_datetime") else creation_dt
        modification = modification_dt.to_datetime() if hasattr(modification_dt, "to_datetime") else modification_dt

        if creation and creation.tzinfo is None:
            creation = creation.replace(tzinfo=timezone.utc)
        if modification and modification.tzinfo is None:
            modification = modification.replace(tzinfo=timezone.utc)

        if creation and modification and creation > modification:
            messages.append(
                ValidationMessage(
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.INVALID_DATE_LOGIC,
                    message=f"{label} creation date ({creation}) is after modification date ({modification})",
                    file_path=amf_path,
                )
            )

        if modification and modification > now:
            messages.append(
                ValidationMessage(
                    level=ValidationLevel.WARNING,
                    validation_type=ValidationType.FUTURE_TIMESTAMP,
                    message=f"{label} modification date ({modification}) is in the future",
                    file_path=amf_path,
                )
            )
    except (ValueError, AttributeError) as e:
        logger.debug("Could not parse %s dates: %s", label, e)

    return messages

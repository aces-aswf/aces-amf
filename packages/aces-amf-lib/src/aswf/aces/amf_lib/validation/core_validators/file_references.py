# SPDX-License-Identifier: Apache-2.0
"""
Deep file reference validation: existence and CCC cross-refs.

Hash verification is handled separately by the file_hashes validator.

Requires base_path in ValidationContext to resolve relative file paths.
Skips silently when base_path is None (e.g., when loading from bytes).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import unquote

from aswf.aces.amf_lib.protocols import AMFValidator
from aswf.aces.amf_lib.validation.types import ValidationContext, ValidationLevel, ValidationMessage, ValidationType
from aswf.aces.amf_lib.validation.core_validators._nested import collect_sub_transforms

if TYPE_CHECKING:
    from aswf.aces.amf_lib.amf import AcesMetadataFile, PipelineType

CDL_COLLECTION_EXTENSIONS = {".ccc", ".cdl"}


class FileReferenceValidator(AMFValidator):
    """Validates file reference existence and CCC cross-references.

    Hash verification is handled by the file_hashes validator.
    Only runs when context.base_path is set (file-system access required).
    """

    name = "file_references"

    def validate(self, amf: AcesMetadataFile, context: ValidationContext) -> list[ValidationMessage]:
        if context.base_path is None:
            return []

        messages: list[ValidationMessage] = []

        if amf.pipeline:
            self._validate_pipeline(amf.pipeline, "", messages, context)

        for idx, archived in enumerate(amf.archived_pipeline):
            self._validate_pipeline(archived, f"Archived pipeline #{idx + 1} ", messages, context)

        return messages

    def _validate_pipeline(
        self, pipeline: PipelineType, prefix: str, messages: list[ValidationMessage], context: ValidationContext
    ) -> None:
        base_path = context.base_path

        def _check_file_ref(transform, label: str) -> None:
            file_ref = getattr(transform, "file", None)
            if not file_ref:
                return

            # Resolve relative to base_path, URL-decode
            file_path = base_path / unquote(file_ref)

            # 1. File existence
            if not file_path.exists():
                messages.append(
                    ValidationMessage(
                        level=ValidationLevel.ERROR,
                        validation_type=ValidationType.MISSING_REFERENCED_FILE,
                        message=f"{label} references missing file: {file_ref}",
                        file_path=context.amf_path,
                    )
                )
                return  # Can't check CCC if file doesn't exist

            # 2. CCC cross-reference
            # (Hash verification is handled by the file_hashes validator.)
            ccc_ref = getattr(transform, "color_correction_ref", None)
            if ccc_ref is not None and getattr(ccc_ref, "ref", None):
                if file_path.suffix.lower() in CDL_COLLECTION_EXTENSIONS:
                    _verify_ccc_ref(file_path, ccc_ref.ref, label, messages, context)

        # Input transform
        if pipeline.input_transform:
            _check_file_ref(pipeline.input_transform, f"{prefix}Input transform")
            for sub_label, sub in collect_sub_transforms(pipeline.input_transform, f"{prefix}Input"):
                _check_file_ref(sub, sub_label)

        # Look transforms
        for idx, lt in enumerate(pipeline.look_transforms):
            desc = f"{prefix}{lt.description or f'Look transform #{idx + 1}'}"
            _check_file_ref(lt, desc)

        # Output transform
        if pipeline.output_transform:
            _check_file_ref(pipeline.output_transform, f"{prefix}Output transform")
            for sub_label, sub in collect_sub_transforms(pipeline.output_transform, f"{prefix}Output"):
                _check_file_ref(sub, sub_label)


def _verify_ccc_ref(
    ccc_path: Path, ref_id: str, label: str, messages: list[ValidationMessage], context: ValidationContext
) -> None:
    """Verify that a ColorCorrectionRef ID exists in the referenced CCC/CDL file."""
    try:
        tree = ET.parse(ccc_path)
        root = tree.getroot()

        # Extract ColorCorrection IDs (with and without namespace)
        ns = {"cdl": "urn:ASC:CDL:v1.01"}
        ids = set()
        for cc in root.findall(".//cdl:ColorCorrection", ns):
            cc_id = cc.get("id")
            if cc_id:
                ids.add(cc_id)
        # Fallback for files without namespace
        if not ids:
            for cc in root.findall(".//ColorCorrection"):
                cc_id = cc.get("id")
                if cc_id:
                    ids.add(cc_id)

        if ref_id not in ids:
            available = ", ".join(sorted(ids)[:5])
            messages.append(
                ValidationMessage(
                    level=ValidationLevel.ERROR,
                    validation_type=ValidationType.CCC_MISSING_ID,
                    message=(
                        f"{label} references ColorCorrection ID '{ref_id}' "
                        f"not found in {ccc_path.name}. "
                        f"Available IDs: [{available}]"
                        if ids else
                        f"{label} references ColorCorrection ID '{ref_id}' "
                        f"but {ccc_path.name} contains no ColorCorrection elements"
                    ),
                    file_path=context.amf_path,
                )
            )
    except ET.ParseError as e:
        messages.append(
            ValidationMessage(
                level=ValidationLevel.ERROR,
                validation_type=ValidationType.CCC_PARSE_ERROR,
                message=f"{label} could not parse CCC file {ccc_path.name}: {e}",
                file_path=context.amf_path,
            )
        )

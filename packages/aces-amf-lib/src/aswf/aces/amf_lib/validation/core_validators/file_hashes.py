# SPDX-License-Identifier: Apache-2.0
"""File hash verification: compute and verify hashes for referenced files."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from aswf.aces.amf_lib.protocols import AMFValidator
from aswf.aces.amf_lib.validation.types import ValidationContext, ValidationLevel, ValidationMessage, ValidationType
from aswf.aces.amf_lib.validation.core_validators._nested import collect_sub_transforms

if TYPE_CHECKING:
    from aswf.aces.amf_lib.amf import AcesMetadataFile

logger = logging.getLogger(__name__)

DEFAULT_HASH_ALGORITHM = "http://www.w3.org/2001/04/xmlenc#sha256"

# Map AMF hash algorithm URIs to hashlib names
HASH_ALGO_MAP = {
    "http://www.w3.org/2001/04/xmlenc#sha256": "sha256",
    "http://www.w3.org/2000/09/xmldsig#sha1": "sha1",
    "http://www.w3.org/2001/04/xmldsig-more#md5": "md5",
}


class FileHashValidator(AMFValidator):
    name = "file_hashes"

    def validate(self, amf: AcesMetadataFile, context: ValidationContext) -> list[ValidationMessage]:
        messages: list[ValidationMessage] = []

        if context.base_path is None:
            # Can't verify file hashes without a base path to resolve files against
            return messages

        transforms = collect_transforms_with_hashes(amf)

        for label, transform in transforms:
            if transform.hash is None:
                continue

            # An undecodable hash value (neither base64 nor hex) is reported by the
            # hash_encoding validator; skip the mismatch check to avoid double-reporting.
            if getattr(transform.hash, "_source_encoding", None) == "unknown":
                continue

            file_ref = getattr(transform, "file", None)
            if not file_ref:
                continue

            resolved = context.base_path / file_ref
            if not resolved.is_file():
                messages.append(
                    ValidationMessage(
                        level=ValidationLevel.WARNING,
                        validation_type=ValidationType.HASH_FILE_NOT_FOUND,
                        message=f"{label} references file {file_ref!r} which was not found at {resolved}",
                        file_path=context.amf_path,
                    )
                )
                continue

            algo_uri = transform.hash.algorithm.value if hasattr(transform.hash.algorithm, "value") else str(transform.hash.algorithm)
            algo_name = HASH_ALGO_MAP.get(algo_uri)

            if algo_name is None:
                messages.append(
                    ValidationMessage(
                        level=ValidationLevel.WARNING,
                        validation_type=ValidationType.HASH_ALGORITHM_UNSUPPORTED,
                        message=f"{label} uses unsupported hash algorithm: {algo_uri}",
                        file_path=context.amf_path,
                    )
                )
                continue

            expected_hash = transform.hash.value
            actual_hash = compute_file_hash(resolved, algo_name)

            if actual_hash != expected_hash:
                messages.append(
                    ValidationMessage(
                        level=ValidationLevel.ERROR,
                        validation_type=ValidationType.HASH_MISMATCH,
                        message=f"{label} file {file_ref!r} hash mismatch: expected {expected_hash!r}, got {actual_hash!r}",
                        file_path=context.amf_path,
                    )
                )

        return messages


def collect_transforms_with_hashes(amf: AcesMetadataFile) -> list[tuple[str, object]]:
    """Collect all transforms that might have hash elements."""
    transforms = []

    if amf.pipeline:
        transforms.extend(_collect_pipeline_transforms(amf.pipeline, ""))

    for idx, archived in enumerate(amf.archived_pipeline):
        transforms.extend(_collect_pipeline_transforms(archived, f"Archived pipeline #{idx + 1} "))

    return transforms


def _collect_pipeline_transforms(pipeline, prefix: str) -> list[tuple[str, object]]:
    """Collect transforms from a single pipeline, including nested sub-transforms."""
    transforms = []

    if pipeline.input_transform:
        transforms.append((f"{prefix}Input transform", pipeline.input_transform))
        transforms.extend(collect_sub_transforms(pipeline.input_transform, f"{prefix}Input"))

    for idx, lt in enumerate(pipeline.look_transforms):
        desc = lt.description or f"Look transform #{idx + 1}"
        transforms.append((f"{prefix}{desc}", lt))

    if pipeline.output_transform:
        transforms.append((f"{prefix}Output transform", pipeline.output_transform))
        transforms.extend(collect_sub_transforms(pipeline.output_transform, f"{prefix}Output"))

    return transforms


def compute_file_hash(file_path: Path, algo_name: str) -> bytes:
    """Compute the hash of a file."""
    h = hashlib.new(algo_name)
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.digest()

# SPDX-License-Identifier: Apache-2.0
"""Hash encoding validation: warn on hex-encoded hashes, error on undecodable ones.

Reads ``HashType._source_encoding``, set during load by ``amf_helpers._normalize_hashes``.
Runs independently of ``base_path`` — encoding validity does not require the referenced
file to be present.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aswf.aces.amf_lib.protocols import AMFValidator
from aswf.aces.amf_lib.validation.types import ValidationContext, ValidationLevel, ValidationMessage, ValidationType
from aswf.aces.amf_lib.validation.core_validators.file_hashes import collect_transforms_with_hashes
from aswf.aces.amf_lib.validation.hash_encoding import ENCODING_HEX, ENCODING_UNKNOWN

if TYPE_CHECKING:
    from aswf.aces.amf_lib.amf import AcesMetadataFile


class HashEncodingValidator(AMFValidator):
    """Validates how transform hash values are encoded (base64 vs hex)."""

    name = "hash_encoding"

    def validate(self, amf: AcesMetadataFile, context: ValidationContext) -> list[ValidationMessage]:
        messages: list[ValidationMessage] = []

        for label, transform in collect_transforms_with_hashes(amf):
            hash_obj = transform.hash
            if hash_obj is None:
                continue

            encoding = getattr(hash_obj, "_source_encoding", None)
            if encoding == ENCODING_HEX:
                messages.append(
                    ValidationMessage(
                        level=ValidationLevel.WARNING,
                        validation_type=ValidationType.HASH_ENCODING_NON_STANDARD,
                        message=(
                            f"{label} hash is hex-encoded; hex is not officially supported "
                            "by the AMF spec — migrate to base64"
                        ),
                        file_path=context.amf_path,
                    )
                )
            elif encoding == ENCODING_UNKNOWN:
                messages.append(
                    ValidationMessage(
                        level=ValidationLevel.ERROR,
                        validation_type=ValidationType.HASH_ENCODING_INVALID,
                        message=f"{label} hash is neither valid base64 nor hex for its algorithm",
                        file_path=context.amf_path,
                    )
                )

        return messages

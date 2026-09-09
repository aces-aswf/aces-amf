# SPDX-License-Identifier: Apache-2.0
"""
Unified validation types for AMF validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aswf.aces.common.protocols import TransformRegistry


class ValidationLevel(Enum):
    """Validation message severity."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationType(Enum):
    """Types of validation issues."""

    # Schema
    SCHEMA_VIOLATION = auto()

    # Parse errors
    LOAD_ERROR = auto()

    # Temporal
    INVALID_DATE_LOGIC = auto()
    FUTURE_TIMESTAMP = auto()

    # Identity
    DUPLICATE_UUID = auto()

    # CDL
    CDL_IDENTITY = auto()
    CDL_INVALID_VALUES = auto()
    CDL_EXTREME_VALUES = auto()
    CDL_MISSING_CCR_FILE = auto()

    # Working Space
    MISSING_CDL_WORKING_SPACE = auto()
    CDL_WORKING_SPACE_MISMATCH = auto()
    MULTIPLE_WORKING_LOCATIONS = auto()

    # Transform IDs
    MALFORMED_TRANSFORM_ID = auto()
    INVALID_TRANSFORM_ID = auto()
    VERSION_MISMATCH_TRANSFORM_ID = auto()

    # Transform Application Order
    INVALID_APPLIED_ORDER = auto()

    # Metadata
    MISSING_DESCRIPTION = auto()
    MISSING_AUTHOR = auto()
    MISSING_TRANSFORM_DESCRIPTION = auto()

    # File Paths
    UNSAFE_FILE_PATH = auto()
    NON_PORTABLE_PATH = auto()
    NON_CLF_TRANSFORM_FILE = auto()

    # File References (deep validation — requires base_path)
    MISSING_REFERENCED_FILE = auto()
    CCC_MISSING_ID = auto()
    CCC_PARSE_ERROR = auto()

    # File Hashes
    HASH_MISMATCH = auto()
    HASH_FILE_NOT_FOUND = auto()
    HASH_ALGORITHM_UNSUPPORTED = auto()

    # Hash encoding (base64 vs hex)
    HASH_ENCODING_NON_STANDARD = auto()
    HASH_ENCODING_INVALID = auto()


@dataclass
class ValidationMessage:
    """A validation message with level, type, and details."""

    level: ValidationLevel
    validation_type: ValidationType
    message: str
    file_path: Path | None = None
    validator_name: str | None = None

    def __str__(self) -> str:
        parts = [f"[{self.level.value.upper()}]"]
        if self.file_path:
            parts.append(f"{self.file_path}:")
        parts.append(self.message)
        return " ".join(parts)


class AMFValidationError(Exception):
    """Raised when AMF validation fails with ERROR-level messages."""

    def __init__(self, messages: list[ValidationMessage]):
        self.messages = messages
        error_msgs = [m.message for m in messages if m.level == ValidationLevel.ERROR]
        super().__init__(f"AMF validation failed: {'; '.join(error_msgs)}")


class AMFSchemaError(Exception):
    """Raised when AMF data cannot be represented by the schema-derived model."""


class RegistryNotConfiguredError(Exception):
    """Raised when transform validation runs but no transform registry has been provided.

    To fix: pass a TransformRegistry implementation to validate_semantic() via the
    transform_registry parameter, or exclude the 'transform_id_registry' validator.
    """


@dataclass
class ValidationContext:
    """Shared context passed to validators."""

    amf_path: Path | None = None
    base_path: Path | None = None
    uuid_pool: set[str] | None = None
    transform_registry: TransformRegistry | None = field(default=None)

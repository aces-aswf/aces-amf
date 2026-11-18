# SPDX-License-Identifier: Apache-2.0
"""
AMF validation: schema validation and extensible semantic validation.

Usage:
    from aswf.aces.amf_lib.validation import validate_schema, validate_semantic

    # Schema-only validation
    messages = validate_schema("example.amf")

    # Semantic validation (all registered validators)
    messages = validate_semantic("example.amf")

    # Both combined
    messages = validate_all("example.amf")
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from aswf.aces.amf_lib.validation.types import (
    AMFSchemaError,
    AMFValidationError,
    RegistryNotConfiguredError,
    ValidationContext,
    ValidationLevel,
    ValidationMessage,
    ValidationType,
)
from aswf.aces.amf_lib.validation.schema import validate_schema
from aswf.aces.amf_lib.validation.registry import ValidatorRegistry, get_default_registry

# Import core validators to trigger auto-registration
from aswf.aces.amf_lib.validation import core_validators  # noqa: F401

if TYPE_CHECKING:
    from aswf.aces.common.protocols import TransformRegistry


def validate_semantic(
    amf_path: Path | str,
    *,
    base_path: Path | None = None,
    validators: list[str] | None = None,
    exclude: list[str] | None = None,
    uuid_pool: set[str] | None = None,
    registry: ValidatorRegistry | None = None,
    transform_registry: TransformRegistry | None = None,
) -> list[ValidationMessage]:
    """Run semantic validation on an AMF file.

    Args:
        amf_path: Path to the AMF file.
        base_path: Base directory for resolving relative file paths.
        validators: If provided, only run these validators (by name).
        exclude: If provided, skip these validators (by name).
        uuid_pool: Set of UUIDs for cross-file duplicate detection.
        registry: Validator registry (collection of AMFValidator instances) to use.
            Defaults to the global registry.
        transform_registry: TransformRegistry implementation for validating transform IDs.
            Required if the 'transform_id_registry' validator is active. Pass
            exclude=['transform_id_registry'] to skip transform ID registry validation.

    Returns:
        List of validation messages.

    Raises:
        RegistryNotConfiguredError: If the transform_id_registry validator runs and
            no transform_registry was provided.
    """
    from aswf.aces.amf_lib.amf_helpers import load_amf

    amf_path = Path(amf_path)

    # Load the AMF
    try:
        amf = load_amf(amf_path, validate=False)
    except Exception as e:
        return [
            ValidationMessage(
                level=ValidationLevel.ERROR,
                validation_type=ValidationType.LOAD_ERROR,
                message=f"Failed to load AMF: {e}",
                file_path=amf_path,
            )
        ]

    context = ValidationContext(
        amf_path=amf_path,
        base_path=base_path,
        uuid_pool=uuid_pool,
        transform_registry=transform_registry,
    )

    reg = registry or get_default_registry()
    return reg.validate(amf, context, validators=validators, exclude=exclude)


def validate_all(
    amf_path: Path | str,
    *,
    base_path: Path | None = None,
    validators: list[str] | None = None,
    exclude: list[str] | None = None,
    uuid_pool: set[str] | None = None,
    registry: ValidatorRegistry | None = None,
    transform_registry: TransformRegistry | None = None,
) -> list[ValidationMessage]:
    """Run both schema and semantic validation on an AMF file.

    Args:
        amf_path: Path to the AMF file.
        base_path: Base directory for resolving relative file paths.
        validators: If provided, only run these semantic validators (by name).
        exclude: If provided, skip these semantic validators (by name).
        uuid_pool: Set of UUIDs for cross-file duplicate detection.
        registry: Validator registry to use. Defaults to the global registry.
        transform_registry: TransformRegistry for transform ID validation.
            See validate_semantic() for details.

    Returns:
        Combined list of validation messages (schema first, then semantic).
    """
    messages = validate_schema(amf_path)

    # Only run semantic validation if no schema errors
    schema_errors = [m for m in messages if m.level == ValidationLevel.ERROR]
    if not schema_errors:
        messages.extend(
            validate_semantic(
                amf_path,
                base_path=base_path,
                validators=validators,
                exclude=exclude,
                uuid_pool=uuid_pool,
                registry=registry,
                transform_registry=transform_registry,
            )
        )

    return messages


from aswf.aces.amf_lib.validation.core_validators._nested import collect_sub_transforms  # noqa: E402
from aswf.aces.amf_lib.validation.core_validators.file_hashes import (  # noqa: E402
    HASH_ALGO_MAP,
    collect_transforms_with_hashes,
)


__all__ = [
    "validate_schema",
    "validate_semantic",
    "validate_all",
    "AMFSchemaError",
    "AMFValidationError",
    "RegistryNotConfiguredError",
    "ValidatorRegistry",
    "get_default_registry",
    "ValidationContext",
    "ValidationLevel",
    "ValidationMessage",
    "ValidationType",
    "collect_sub_transforms",
    "collect_transforms_with_hashes",
    "HASH_ALGO_MAP",
]

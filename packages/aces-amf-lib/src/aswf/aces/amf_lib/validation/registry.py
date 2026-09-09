# SPDX-License-Identifier: Apache-2.0
"""
Validator registry with entry point discovery and explicit registration.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aswf.aces.amf_lib.protocols import AMFValidator
from aswf.aces.amf_lib.validation.types import RegistryNotConfiguredError, ValidationContext, ValidationLevel, ValidationMessage, ValidationType

if TYPE_CHECKING:
    from aswf.aces.amf_lib.amf import AcesMetadataFile

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "aces_amf.validators"


class ValidatorRegistry:
    """Registry for AMF validators.

    Validators can be registered explicitly via ``register()`` or
    discovered automatically from Python entry points.
    """

    def __init__(self):
        self._validators: dict[str, AMFValidator] = {}

    @property
    def validator_names(self) -> list[str]:
        """Names of all registered validators."""
        return list(self._validators.keys())

    def register(self, validator: AMFValidator) -> None:
        """Register a validator instance."""
        self._validators[validator.name] = validator

    def unregister(self, name: str) -> None:
        """Remove a validator by name."""
        self._validators.pop(name, None)

    def get(self, name: str) -> AMFValidator | None:
        """Get a validator by name."""
        return self._validators.get(name)

    def discover(self) -> None:
        """Discover and register validators from entry points."""
        from importlib.metadata import entry_points

        for ep in entry_points(group=ENTRY_POINT_GROUP):
            try:
                validator_cls = ep.load()
                instance = validator_cls() if isinstance(validator_cls, type) else validator_cls
                self.register(instance)
                logger.debug("Discovered validator %r from entry point %s", instance.name, ep.name)
            except Exception:
                logger.warning("Failed to load validator entry point %s", ep.name, exc_info=True)

    def validate(
        self,
        amf: AcesMetadataFile,
        context: ValidationContext,
        *,
        validators: list[str] | None = None,
        exclude: list[str] | None = None,
    ) -> list[ValidationMessage]:
        """Run validators and collect messages.

        Args:
            amf: The parsed AMF object.
            context: Shared validation context.
            validators: If provided, only run these validators (by name).
            exclude: If provided, skip these validators (by name).

        Returns:
            Combined list of validation messages from all active validators.
        """
        active = dict(self._validators)

        if validators is not None:
            active = {k: v for k, v in active.items() if k in validators}

        if exclude:
            active = {k: v for k, v in active.items() if k not in exclude}

        messages: list[ValidationMessage] = []
        for validator in active.values():
            try:
                results = validator.validate(amf, context)
                for msg in results:
                    if msg.validator_name is None:
                        msg.validator_name = validator.name
                messages.extend(results)
            except RegistryNotConfiguredError:
                # Configuration error — propagate immediately, do not swallow
                raise
            except Exception:
                logger.warning("Validator %r raised an exception", validator.name, exc_info=True)
                messages.append(
                    ValidationMessage(
                        level=ValidationLevel.ERROR,
                        validation_type=ValidationType.LOAD_ERROR,
                        message=f"Validator {validator.name!r} raised an exception",
                        file_path=context.amf_path,
                        validator_name=validator.name,
                    )
                )

        return messages


# Global default registry
_default_registry: ValidatorRegistry | None = None


def get_default_registry() -> ValidatorRegistry:
    """Get the default global validator registry.

    The registry is created on first access and core validators
    are auto-registered.
    """
    global _default_registry
    if _default_registry is None:
        _default_registry = ValidatorRegistry()
    return _default_registry

# SPDX-License-Identifier: Apache-2.0
"""
Protocol definitions for plugin interfaces.

These protocols define the contracts that external packages can implement
to extend aswf-aces-amf-lib functionality.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from aswf.aces.common.protocols import TransformRegistry

if TYPE_CHECKING:
    from aswf.aces.amf_lib.amf import AcesMetadataFile
    from aswf.aces.amf_lib.validation.types import ValidationContext, ValidationMessage


@runtime_checkable
class AMFValidator(Protocol):
    """Protocol for AMF validation plugins.

    Validators are registered with the ValidatorRegistry and invoked
    during semantic validation. Each validator has a unique name and
    a validate method that checks a specific aspect of an AMF file.
    """

    name: str

    def validate(self, amf: AcesMetadataFile, context: ValidationContext) -> list[ValidationMessage]: ...


__all__ = ["AMFValidator", "TransformRegistry"]

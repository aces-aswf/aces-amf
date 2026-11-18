# SPDX-License-Identifier: Apache-2.0
"""
Core validators for AMF files.

Importing this module auto-registers all core validators with the default registry.
"""

from aswf.aces.amf_lib.validation.registry import get_default_registry
from aswf.aces.amf_lib.validation.core_validators.applied_order import AppliedOrderValidator
from aswf.aces.amf_lib.validation.core_validators.cdl import CDLValidator
from aswf.aces.amf_lib.validation.core_validators.file_hashes import FileHashValidator
from aswf.aces.amf_lib.validation.core_validators.file_paths import FilePathValidator
from aswf.aces.amf_lib.validation.core_validators.hash_encoding import HashEncodingValidator
from aswf.aces.amf_lib.validation.core_validators.file_references import FileReferenceValidator
from aswf.aces.amf_lib.validation.core_validators.metadata import MetadataValidator
from aswf.aces.amf_lib.validation.core_validators.temporal import TemporalValidator
from aswf.aces.amf_lib.validation.core_validators.transform_ids import TransformIdFormatValidator
from aswf.aces.amf_lib.validation.core_validators.transform_placement import TransformTypePlacementValidator
from aswf.aces.amf_lib.validation.core_validators.transform_registry import TransformRegistryValidator
from aswf.aces.amf_lib.validation.core_validators.uuid_validator import UUIDValidator
from .working_space import WorkingSpaceValidator


def _register_core_validators():
    registry = get_default_registry()
    for validator_cls in [
        TemporalValidator,
        UUIDValidator,
        CDLValidator,
        MetadataValidator,
        AppliedOrderValidator,
        FilePathValidator,
        FileReferenceValidator,
        HashEncodingValidator,
        WorkingSpaceValidator,
        TransformIdFormatValidator,
        TransformTypePlacementValidator,
        FileHashValidator,
        TransformRegistryValidator,
    ]:
        registry.register(validator_cls())


_register_core_validators()

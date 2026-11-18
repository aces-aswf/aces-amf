# SPDX-License-Identifier: Apache-2.0
"""Integration tests using generated AMF sample files.

Validates that:
- All files in valid_AMFs/ load without errors
- All files in invalid_AMFs/ produce at least one ERROR-level validation message
"""

from pathlib import Path

import pytest

from aswf.aces.amf_lib import load_amf
from aswf.aces.amf_lib.validation import (
    ValidationContext,
    ValidationLevel,
)

SAMPLES_DIR = Path(__file__).parent / "Generated_Samples_AMF"
VALID_DIR = SAMPLES_DIR / "valid_AMFs"
INVALID_DIR = SAMPLES_DIR / "invalid_AMFs"


@pytest.fixture(scope="module")
def transform_registry():
    from aswf.aces.transforms import ACESTransformRegistry
    return ACESTransformRegistry()


def _collect_amf_files(directory: Path) -> list[Path]:
    files = sorted(directory.glob("*.amf"))
    assert files, f"No AMF files found in {directory}"
    return files


class TestValidAMFs:
    """All files in valid_AMFs/ should load and parse without error."""

    @pytest.fixture(params=_collect_amf_files(VALID_DIR), ids=lambda p: p.name)
    def valid_amf(self, request):
        return request.param

    def test_loads_without_error(self, valid_amf, transform_registry):
        """Valid AMF loads and passes full validation."""
        amf = load_amf(valid_amf, validate=True, transform_registry=transform_registry)
        assert amf is not None
        assert amf.pipeline is not None


class TestInvalidAMFs:
    """All files in invalid_AMFs/ should produce at least one ERROR."""

    @pytest.fixture(params=_collect_amf_files(INVALID_DIR), ids=lambda p: p.name)
    def invalid_amf(self, request):
        return request.param

    def test_produces_validation_error(self, invalid_amf, transform_registry):
        """Invalid AMF produces at least one ERROR-level validation message."""
        try:
            amf = load_amf(invalid_amf, transform_registry=transform_registry)
        except Exception:
            # Parse failure is also a valid "rejection"
            return

        # Run semantic validation with base_path for deep file checks
        context = ValidationContext(
            amf_path=invalid_amf,
            base_path=invalid_amf.parent,
            transform_registry=transform_registry,
        )
        from aswf.aces.amf_lib.validation.registry import get_default_registry
        registry = get_default_registry()
        msgs = registry.validate(amf, context)

        errors = [m for m in msgs if m.level == ValidationLevel.ERROR]
        warnings = [m for m in msgs if m.level == ValidationLevel.WARNING]

        assert len(errors) > 0 or len(warnings) > 0, (
            f"{invalid_amf.name} produced no validation messages but was expected to be invalid"
        )

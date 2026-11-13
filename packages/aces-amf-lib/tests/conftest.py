# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import pytest

from aswf.aces.amf_lib.fixtures import get_amf_examples_path


# Test data directory (local test data, not package fixtures)
TEST_DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def test_data_path() -> Path:
    """Path to test data directory."""
    return TEST_DATA_DIR


@pytest.fixture
def aces_amf_examples_path() -> Path:
    """Path to ACES example AMF files (from package fixtures)."""
    return get_amf_examples_path()


@pytest.fixture
def transform_registry():
    """ACESTransformRegistry instance for tests that exercise transform ID validation."""
    from aswf.aces.transforms import ACESTransformRegistry
    return ACESTransformRegistry()

# SPDX-License-Identifier: Apache-2.0
"""Shared test fixtures for aces-amf-utils."""

import pytest
from pathlib import Path

from aswf.aces.amf_lib.fixtures import get_amf_examples_path


@pytest.fixture
def amf_examples_path():
    """Path to AMF example files."""
    return get_amf_examples_path()


@pytest.fixture
def sample_amf_path(amf_examples_path):
    """Path to a single sample AMF file."""
    examples = sorted(amf_examples_path.glob("*.amf"))
    assert examples, "No AMF example files found"
    return examples[0]


@pytest.fixture
def tmp_output(tmp_path):
    """Temporary output directory."""
    out = tmp_path / "output"
    out.mkdir()
    return out

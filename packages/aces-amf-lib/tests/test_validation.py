# SPDX-License-Identifier: Apache-2.0
"""Tests for XSD schema validation."""

from pathlib import Path

import pytest

from aswf.aces.amf_lib.validation import validate_schema, ValidationType


@pytest.mark.parametrize(
    "amf_name",
    ["example1.amf", "example6.amf", "exampleMinimum.amf"],
)
def test_amf_validation_pos(amf_name, aces_amf_examples_path):
    amf_path = aces_amf_examples_path / amf_name
    assert isinstance(validate_schema(amf_path), list)
    assert len(validate_schema(amf_path)) == 0


def test_amf_validation_neg_syntax(tmp_path):
    """Test validation rejects non-XML file."""
    bad_file = tmp_path / "bad.amf"
    bad_file.write_text("this is not xml")
    result = validate_schema(bad_file)
    assert len(result) == 1
    assert result[0].validation_type == ValidationType.SCHEMA_VIOLATION

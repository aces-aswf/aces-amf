# SPDX-License-Identifier: Apache-2.0
"""Tests for the public AMF API (load, save, render, minimal_amf)."""

from pathlib import Path
import time

import pytest
from pydantic import ValidationError

from aswf.aces.amf_lib import (
    AMFSchemaError,
    load_amf,
    load_amf_data,
    save_amf,
    render_amf,
)
from aswf.aces.amf_utils.factories import cdl_look_transform, minimal_amf, prepare_for_write
from aswf.aces.amf_lib import amf
from aswf.aces.amf_lib.amf import AcesMetadataFile, VersionType
from aswf.aces.amf_lib.validation import validate_schema


SCHEMA_INVALID_AMF_PATH = (
    Path(__file__).parent
    / "Generated_Samples_AMF"
    / "invalid_AMFs"
    / "invalid_15_missing_system_version.amf"
)


def test_load_amf(aces_amf_examples_path):
    """Test loading a v2 AMF file."""
    amf_path = aces_amf_examples_path / "example6.amf"
    amf_obj = load_amf(amf_path, validate=False)
    assert isinstance(amf_obj, AcesMetadataFile)
    assert amf_obj.amf_info.uuid == "urn:uuid:afe122be-59d3-4360-ad69-33c10108fa7a"


def test_load_amf_data(aces_amf_examples_path):
    """Test loading AMF from bytes."""
    amf_path = aces_amf_examples_path / "example6.amf"
    with amf_path.open("rb") as f:
        amf_obj = load_amf_data(f.read(), validate=False)
    assert amf_obj.amf_info.uuid == "urn:uuid:afe122be-59d3-4360-ad69-33c10108fa7a"


def test_render_amf(aces_amf_examples_path):
    amf_path = aces_amf_examples_path / "example6.amf"
    amf_obj = load_amf(amf_path, validate=False)
    dumped = render_amf(amf_obj, validate=False)

    assert isinstance(dumped, str)
    assert "<aces:amfInfo>" in dumped
    assert "<aces:uuid>" in dumped
    # Verify actual data survives the render (not just tags)
    assert amf_obj.pipeline is not None
    assert "urn:ampas:aces:amf:v2.0" in dumped


def test_save_amf(aces_amf_examples_path, tmp_path):
    amf_path = aces_amf_examples_path / "example6.amf"
    amf_obj = load_amf(amf_path, validate=False)

    out_path = tmp_path / "out.amf"
    save_amf(amf_obj, out_path, validate=False)

    out_data = out_path.read_text()
    assert "<aces:amfInfo>" in out_data
    assert "<aces:uuid>" in out_data


def test_create_minimal(tmp_path):
    amf_obj = minimal_amf()
    out_path = tmp_path / "out.amf"
    save_amf(amf_obj, out_path, validate=False)

    validation_messages = validate_schema(out_path)
    assert not validation_messages


def test_create_with_cdl(tmp_path):
    amf_obj = minimal_amf()
    amf_obj.pipeline.working_location_or_look_transform.append(
        cdl_look_transform(
            slope=(1.0, 1.0, 1.0),
            offset=(0.0, 0.0, 0.0),
            power=(1.0, 1.0, 1.0),
            saturation=1.0,
        )
    )

    out_path = tmp_path / "out.amf"
    save_amf(amf_obj, out_path, validate=False)

    validation_messages = validate_schema(out_path)
    assert not validation_messages


def test_housekeeping_updates(tmp_path):
    amf_obj = minimal_amf()
    out_path = tmp_path / "minimal.amf"
    save_amf(amf_obj, out_path, validate=False)

    time.sleep(1.00)

    amf_obj.pipeline.working_location_or_look_transform.append(
        cdl_look_transform(
            slope=(1.0, 1.0, 1.0),
            offset=(0.0, 0.0, 0.0),
            power=(1.0, 1.0, 1.0),
            saturation=1.0,
        )
    )

    out_path_updated = tmp_path / "updated_with_cdl.amf"
    save_amf(amf_obj, out_path_updated, validate=False)

    original = load_amf(out_path, validate=False)
    updated = load_amf(out_path_updated, validate=False)

    assert original.amf_info.uuid != updated.amf_info.uuid
    assert original.amf_info.date_time.creation_date_time == updated.amf_info.date_time.creation_date_time
    assert original.amf_info.date_time.modification_date_time != updated.amf_info.date_time.modification_date_time
    assert original.pipeline.pipeline_info.uuid != updated.pipeline.pipeline_info.uuid


def test_prepare_for_write():
    """Make sure prepare_for_write updates UUIDs and timestamps."""
    amf_obj = minimal_amf()
    original_uuid = amf_obj.amf_info.uuid
    original_pipeline_uuid = amf_obj.pipeline.pipeline_info.uuid

    prepare_for_write(amf_obj)

    # UUIDs should be regenerated
    assert amf_obj.amf_info.uuid != original_uuid
    assert amf_obj.pipeline.pipeline_info.uuid != original_pipeline_uuid
    # Modification timestamp should be set
    assert amf_obj.amf_info.date_time.modification_date_time is not None
    assert amf_obj.pipeline.pipeline_info.date_time.modification_date_time is not None


def test_roundtrip(aces_amf_examples_path, tmp_path):
    """Test round-trip: load -> write -> validate -> load."""
    amf_path = aces_amf_examples_path / "example6.amf"
    amf_obj = load_amf(amf_path, validate=False)

    out_path = tmp_path / "roundtrip.amf"
    save_amf(amf_obj, out_path, validate=False)

    # Validate the output
    validation_messages = validate_schema(out_path)
    assert not validation_messages

    # Load back and verify
    amf2 = load_amf(out_path, validate=False)
    assert amf2.pipeline is not None
    assert len(amf2.pipeline.look_transforms) == len(amf_obj.pipeline.look_transforms)


def test_set_aces_version():
    amf_obj = minimal_amf()
    amf_obj.pipeline.pipeline_info.system_version = VersionType(
        major_version=2, minor_version=0, patch_version=0
    )
    sv = amf_obj.pipeline.pipeline_info.system_version
    assert (sv.major_version, sv.minor_version, sv.patch_version) == (2, 0, 0)


# --- Auto-validation tests ---


def test_load_validates_by_default(aces_amf_examples_path, transform_registry):
    """Valid AMF files load without raising when registry provided."""
    amf_obj = load_amf(aces_amf_examples_path / "example6.amf", transform_registry=transform_registry)
    assert amf_obj is not None


def test_load_no_registry_raises(aces_amf_examples_path):
    """load_amf with validate=True and no registry raises RegistryNotConfiguredError."""
    from aswf.aces.amf_lib.validation.types import RegistryNotConfiguredError
    with pytest.raises(RegistryNotConfiguredError):
        load_amf(aces_amf_examples_path / "example6.amf")


def test_load_skip_validation(aces_amf_examples_path):
    """validate=False skips validation entirely."""
    amf_obj = load_amf(aces_amf_examples_path / "example6.amf", validate=False)
    assert amf_obj is not None


def test_load_schema_error_when_validation_disabled():
    """validate=False does not leak Pydantic errors from schema-derived models."""
    with pytest.raises(AMFSchemaError) as exc_info:
        load_amf(SCHEMA_INVALID_AMF_PATH, validate=False)

    assert isinstance(exc_info.value.__cause__, ValidationError)
    assert str(SCHEMA_INVALID_AMF_PATH) in str(exc_info.value)


def test_load_data_schema_error_when_validation_disabled():
    """Byte loading translates Pydantic model errors to the public AMF exception."""
    with pytest.raises(AMFSchemaError) as exc_info:
        load_amf_data(SCHEMA_INVALID_AMF_PATH.read_bytes(), validate=False)

    assert isinstance(exc_info.value.__cause__, ValidationError)


def test_save_validates_by_default(tmp_path, transform_registry):
    """Valid AMF saves without raising when registry provided."""
    amf_obj = minimal_amf()
    out = tmp_path / "valid.amf"
    save_amf(amf_obj, out, transform_registry=transform_registry)
    assert out.exists()


def test_save_raises_on_invalid(tmp_path, transform_registry):
    """save_amf with validate=True raises on ERROR-level issues."""
    from aswf.aces.amf_lib.validation.types import AMFValidationError

    amf_obj = minimal_amf()
    amf_obj.pipeline.working_location_or_look_transform.append(
        cdl_look_transform(slope=(-1.0, 1.0, 1.0))
    )
    out = tmp_path / "invalid.amf"
    with pytest.raises(AMFValidationError):
        save_amf(amf_obj, out, transform_registry=transform_registry)


def test_save_skip_validation(tmp_path):
    """validate=False allows saving invalid AMF without error."""
    amf_obj = minimal_amf()
    amf_obj.pipeline.working_location_or_look_transform.append(
        cdl_look_transform(slope=(-1.0, 1.0, 1.0))
    )
    out = tmp_path / "invalid.amf"
    save_amf(amf_obj, out, validate=False)
    assert out.exists()


def test_roundtrip_file_paths(aces_amf_examples_path):
    """Round-tripping a file with <file> elements produces no percent-encoding."""
    from aswf.aces.amf_lib.amf_helpers import dump_amf
    amf_path = aces_amf_examples_path / "example5.amf"
    amf_obj = load_amf(amf_path, validate=False)
    xml_out = dump_amf(amf_obj)
    # The file element value should be plain text, not percent-encoded
    assert "showLook.clf" in xml_out
    assert "%2F" not in xml_out
    assert "%25" not in xml_out


# --- URI encoding/decoding tests ---


_AMF_WITH_ENCODED_PATH = """\
<?xml version="1.0" encoding="UTF-8"?>
<acesMetadataFile xmlns="urn:ampas:aces:amf:v2.0" version="2.0"
  xmlns:cdl="urn:ASC:CDL:v1.01">
  <amfInfo>
    <dateTime>
      <creationDateTime>2024-01-01T00:00:00Z</creationDateTime>
      <modificationDateTime>2024-01-01T00:00:00Z</modificationDateTime>
    </dateTime>
    <uuid>urn:uuid:11111111-1111-1111-1111-111111111111</uuid>
  </amfInfo>
  <pipeline>
    <pipelineInfo>
      <dateTime>
        <creationDateTime>2024-01-01T00:00:00Z</creationDateTime>
        <modificationDateTime>2024-01-01T00:00:00Z</modificationDateTime>
      </dateTime>
      <uuid>urn:uuid:22222222-2222-2222-2222-222222222222</uuid>
      <systemVersion>
        <majorVersion>1</majorVersion>
        <minorVersion>3</minorVersion>
        <patchVersion>0</patchVersion>
      </systemVersion>
    </pipelineInfo>
    <inputTransform applied="false">
      <file>my%20show/Camera%20Files/A001.clf</file>
    </inputTransform>
  </pipeline>
</acesMetadataFile>"""


def test_load_decodes_percent_encoded_file_paths():
    """Percent-encoded file paths are decoded to human-readable form on load."""
    amf_obj = load_amf_data(_AMF_WITH_ENCODED_PATH.encode(), validate=False)
    assert amf_obj.pipeline.input_transform.file == "my show/Camera Files/A001.clf"


def test_save_encodes_file_paths_to_valid_uris(tmp_path):
    """File paths with spaces are percent-encoded in serialized XML."""
    from aswf.aces.amf_lib.amf_helpers import dump_amf
    amf_obj = load_amf_data(_AMF_WITH_ENCODED_PATH.encode(), validate=False)
    # In-memory should be decoded
    assert amf_obj.pipeline.input_transform.file == "my show/Camera Files/A001.clf"
    # Serialized should be re-encoded
    xml_out = dump_amf(amf_obj)
    assert "my%20show/Camera%20Files/A001.clf" in xml_out


def test_roundtrip_preserves_plain_paths(aces_amf_examples_path):
    """Plain paths with no special characters survive round-trip unchanged."""
    from aswf.aces.amf_lib.amf_helpers import dump_amf
    amf_obj = load_amf(aces_amf_examples_path / "example5.amf", validate=False)
    # Second look is file-based (first is CDL)
    assert amf_obj.pipeline.look_transforms[1].file == "showLook.clf"
    xml_out = dump_amf(amf_obj)
    assert "showLook.clf" in xml_out


def test_roundtrip_encoded_paths():
    """Encoded input -> decoded in memory -> re-encoded on save."""
    from aswf.aces.amf_lib.amf_helpers import dump_amf
    amf_obj = load_amf_data(_AMF_WITH_ENCODED_PATH.encode(), validate=False)
    xml_out = dump_amf(amf_obj)
    assert "my%20show/Camera%20Files/A001.clf" in xml_out
    # Forward slashes must NOT be encoded
    assert "%2F" not in xml_out


def test_decode_does_not_double_decode():
    """Already-decoded paths (no percent chars) pass through unchanged."""
    amf_obj = load_amf_data(_AMF_WITH_ENCODED_PATH.encode(), validate=False)
    # After decode, path should be clean
    assert amf_obj.pipeline.input_transform.file == "my show/Camera Files/A001.clf"
    # Loading again from XML that has no encoding should also work fine
    amf2 = minimal_amf()
    amf2.pipeline.input_transform = amf.InputTransformType(
        file="plain_file.clf", applied=False,
    )
    from aswf.aces.amf_lib.amf_helpers import dump_amf
    xml_out = dump_amf(amf2)
    assert "plain_file.clf" in xml_out


def test_encode_does_not_mutate_original():
    """dump_amf does not alter the in-memory model's file paths."""
    from aswf.aces.amf_lib.amf_helpers import dump_amf
    amf_obj = load_amf_data(_AMF_WITH_ENCODED_PATH.encode(), validate=False)
    original_path = amf_obj.pipeline.input_transform.file
    dump_amf(amf_obj)  # should deep-copy internally
    assert amf_obj.pipeline.input_transform.file == original_path
    assert amf_obj.pipeline.input_transform.file == "my show/Camera Files/A001.clf"


def test_clip_id_file_uri_roundtrip(tmp_path):
    """ClipIdType.file is decoded on load and encoded on save."""
    from aswf.aces.amf_lib.amf_helpers import dump_amf
    amf_obj = minimal_amf()
    amf_obj.clip_id = amf.ClipIdType(clip_name="A001", file="my show/A001.ari")
    xml_out = dump_amf(amf_obj)
    assert "my%20show/A001.ari" in xml_out
    # Round-trip: save then reload
    out = tmp_path / "clip_uri.amf"
    save_amf(amf_obj, out, validate=False)
    loaded = load_amf(out, validate=False)
    assert loaded.clip_id.file == "my show/A001.ari"


def test_nested_output_transform_file_uri():
    """File fields nested inside OutputTransformType are encoded/decoded."""
    from aswf.aces.amf_lib.amf_helpers import dump_amf
    amf_obj = minimal_amf()
    amf_obj.pipeline.output_transform = amf.OutputTransformType(
        applied=False,
        reference_rendering_transform=amf.ReferenceRenderingTransformType(
            file="path with spaces/rrt.clf",
        ),
        output_device_transform=amf.OutputDeviceTransformType(
            file="path with spaces/odt.clf",
        ),
    )
    xml_out = dump_amf(amf_obj)
    assert "path%20with%20spaces/rrt.clf" in xml_out
    assert "path%20with%20spaces/odt.clf" in xml_out


def test_render_amf_encodes_file_paths():
    """render_amf() encodes file paths just like dump_amf()."""
    amf_obj = load_amf_data(_AMF_WITH_ENCODED_PATH.encode(), validate=False)
    xml_out = render_amf(amf_obj, validate=False)
    assert "my%20show/Camera%20Files/A001.clf" in xml_out


# --- workingLocation interleaving tests ---


def test_working_location_ordering_preserved(test_data_path):
    """Loading an AMF with interleaved workingLocation/lookTransform preserves order."""
    from aswf.aces.amf_lib.amf import WorkingLocationType, LookTransformType

    amf_obj = load_amf(test_data_path / "interleaved_working_location.amf", validate=False)
    items = amf_obj.pipeline.working_location_or_look_transform

    # Should be: lookTransform, workingLocation, lookTransform
    assert len(items) == 3
    assert isinstance(items[0], LookTransformType)
    assert isinstance(items[1], WorkingLocationType)
    assert isinstance(items[2], LookTransformType)

    # First look is pre-working-location, second is post
    assert items[0].description == "Pre-working-location look"
    assert items[2].description == "Post-working-location look"


def test_working_location_roundtrip(test_data_path, tmp_path):
    """Round-trip preserves workingLocation/lookTransform ordering."""
    from aswf.aces.amf_lib.amf import WorkingLocationType, LookTransformType

    amf_obj = load_amf(test_data_path / "interleaved_working_location.amf", validate=False)
    out_path = tmp_path / "roundtrip.amf"
    save_amf(amf_obj, out_path, validate=False)

    amf2 = load_amf(out_path, validate=False)
    items = amf2.pipeline.working_location_or_look_transform

    assert len(items) == 3
    assert isinstance(items[0], LookTransformType)
    assert isinstance(items[1], WorkingLocationType)
    assert isinstance(items[2], LookTransformType)


def test_look_transforms_property_filters(test_data_path):
    """pipeline.look_transforms returns only LookTransformType items."""
    amf_obj = load_amf(test_data_path / "interleaved_working_location.amf", validate=False)

    # Full list has 3 items (2 looks + 1 working location)
    assert len(amf_obj.pipeline.working_location_or_look_transform) == 3
    # Property filters to just look transforms
    assert len(amf_obj.pipeline.look_transforms) == 2
    assert amf_obj.pipeline.look_transforms[0].description == "Pre-working-location look"
    assert amf_obj.pipeline.look_transforms[1].description == "Post-working-location look"


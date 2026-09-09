# SPDX-License-Identifier: Apache-2.0
"""Tests for AMF utility functions."""

from datetime import datetime, timezone
import uuid

from aswf.aces.amf_lib import amf_helpers
from aswf.aces.amf_utils import factories as amf_factories


def test_amf_timestamp_string():
    test_time = datetime(year=2020, month=11, day=10, hour=13, minute=20, second=0, tzinfo=timezone.utc)
    assert amf_helpers.amf_timestamp_string(test_time) == "2020-11-10T13:20:00Z"


def test_amf_date_time_now():
    date_time = amf_helpers.amf_date_time_now()
    assert date_time.creation_date_time is not None
    assert date_time.modification_date_time is not None
    assert date_time.creation_date_time == date_time.modification_date_time


def test_minimal_amf():
    amf = amf_factories.minimal_amf()

    amf_info = amf.amf_info
    assert amf_info.date_time.creation_date_time is not None
    assert amf_info.date_time.modification_date_time is not None
    assert amf_info.date_time.creation_date_time == amf_info.date_time.modification_date_time
    assert amf_info.uuid.startswith("urn:uuid:")
    amf_id = uuid.UUID(amf.amf_info.uuid)
    assert amf_id
    assert amf_id.version == 4

    pipeline_info = amf.pipeline.pipeline_info
    assert pipeline_info.date_time.creation_date_time is not None
    assert pipeline_info.date_time.modification_date_time is not None
    assert pipeline_info.date_time.creation_date_time == pipeline_info.date_time.modification_date_time
    assert pipeline_info.uuid.startswith("urn:uuid:")
    pipeline_id = uuid.UUID(pipeline_info.uuid)
    assert pipeline_id
    assert pipeline_id.version == 4
    assert pipeline_info.system_version.major_version == 1
    assert pipeline_info.system_version.minor_version == 3
    assert pipeline_info.system_version.patch_version == 0


def test_amf_roundtrip(aces_amf_examples_path):
    amf_path = aces_amf_examples_path / "example6.amf"
    amf, ns_map = amf_helpers.from_amf_file(amf_path)

    out_amf_lines = amf_helpers.dump_amf(amf, ns_map).split("\n")
    assert len(out_amf_lines) > 10


def test_cdl_look_transform_to_dict(aces_amf_examples_path):
    amf_path = aces_amf_examples_path / "example6.amf"
    amf, ns_map = amf_helpers.from_amf_file(amf_path)

    cdl_look_transform = amf.pipeline.look_transforms[0]
    cdl_dict = amf_factories.cdl_look_transform_to_dict(cdl_look_transform)

    assert cdl_dict == {"asc_sat": 1.0, "asc_sop": {"slope": [2.0, 2.0, 2.0], "offset": [0.1, 0.1, 0.1], "power": [1.0, 1.0, 1.0]}}


def test_cdl_look_transform(aces_amf_examples_path):
    amf_path = aces_amf_examples_path / "example6.amf"
    amf, ns_map = amf_helpers.from_amf_file(amf_path)
    ref_look_transform = amf.pipeline.look_transforms[0]

    look_transform = amf_factories.cdl_look_transform(slope=(2.0, 2.0, 2.0), offset=(0.1, 0.1, 0.1), power=(1.0, 1.0, 1.0), saturation=1.0)
    assert look_transform.description is None

    look_transform.description = "Technical Grade"
    assert look_transform == ref_look_transform

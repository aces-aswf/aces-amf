# SPDX-License-Identifier: Apache-2.0
"""Tests for the AMFBuilder fluent API."""

import pytest
from aswf.aces.amf_utils import AMFBuilder, cdl_look_transform
from aswf.aces.amf_lib import AcesMetadataFile, load_amf, save_amf
from aswf.aces.amf_lib.amf import (
    AuthorType,
    ClipIdType,
    InputTransformType,
    LookTransformType,
    OutputTransformType,
    VersionType,
    WorkingLocationType,
)


class TestAMFBuilder:
    def test_basic_build(self):
        amf = AMFBuilder().build()
        assert isinstance(amf, AcesMetadataFile)

    def test_with_description(self):
        amf = AMFBuilder().with_description("Test show").build()
        assert amf.amf_info.description == "Test show"

    def test_with_pipeline_description(self):
        amf = AMFBuilder().with_pipeline_description("Camera to Rec.709").build()
        assert amf.pipeline.pipeline_info.description == "Camera to Rec.709"

    def test_with_author(self):
        amf = AMFBuilder().with_author(AuthorType(name="Jane Doe", email_address="jane@example.com")).build()
        assert len(amf.amf_info.author) == 1
        assert amf.amf_info.author[0].name == "Jane Doe"
        assert amf.amf_info.author[0].email_address == "jane@example.com"

    def test_with_author_no_email(self, tmp_path):
        """Author without email is valid — emailAddress is optional in the schema."""
        amf = AMFBuilder().with_author(AuthorType(name="No Email")).build()
        assert amf.amf_info.author[0].email_address is None
        out = tmp_path / "no_email.amf"
        save_amf(amf, out, validate=False)
        loaded = load_amf(out, validate=False)
        assert loaded.amf_info.author[0].name == "No Email"
        assert loaded.amf_info.author[0].email_address is None

    def test_multiple_authors(self):
        amf = (
            AMFBuilder()
            .with_author(AuthorType(name="Alice", email_address="alice@example.com"))
            .with_author(AuthorType(name="Bob", email_address="bob@example.com"))
            .build()
        )
        assert len(amf.amf_info.author) == 2

    def test_input_transform(self):
        tid = "urn:ampas:aces:transformId:v1.5:IDT.ARRI.ARRI-LogC4.a1.v1"
        amf = AMFBuilder().with_input_transform(InputTransformType(transform_id=tid, applied=False)).build()
        it = amf.pipeline.input_transform
        assert it is not None
        assert it.transform_id == tid
        assert it.applied is False

    def test_output_transform(self):
        tid = "urn:ampas:aces:transformId:v1.5:RRTODT.Academy.Rec709_100nits_dim.a1.0.3"
        amf = AMFBuilder().with_output_transform(OutputTransformType(transform_id=tid, applied=True)).build()
        ot = amf.pipeline.output_transform
        assert ot is not None
        assert ot.transform_id == tid
        assert ot.applied is True

    def test_look_transform_with_file(self):
        amf = (
            AMFBuilder()
            .with_look_transform(LookTransformType(file="grade.clf", description="Primary grade", applied=False))
            .build()
        )
        lts = amf.pipeline.look_transforms
        assert len(lts) == 1
        assert lts[0].description == "Primary grade"

    def test_look_transform_with_cdl(self):
        lt = cdl_look_transform(slope=(1.2, 1.0, 0.8), offset=(0.01, 0.0, -0.01), saturation=0.9)
        lt.description = "CDL grade"
        amf = AMFBuilder().with_look_transform(lt).build()
        lts = amf.pipeline.look_transforms
        assert len(lts) == 1
        assert lts[0].asc_sop is not None

    def test_chaining(self):
        """Verify full builder chain returns a valid AMF."""
        lt = cdl_look_transform(slope=(1.1, 1.0, 0.9))
        amf = (
            AMFBuilder(aces_version=(2, 0, 0))
            .with_description("Full pipeline test")
            .with_pipeline_description("Camera to Display")
            .with_author(AuthorType(name="Test User", email_address=None))
            .with_input_transform(InputTransformType(
                transform_id="urn:ampas:aces:transformId:v1.5:IDT.ARRI.ARRI-LogC4.a1.v1",
                applied=False,
            ))
            .with_look_transform(lt)
            .with_output_transform(OutputTransformType(
                transform_id="urn:ampas:aces:transformId:v1.5:RRTODT.Academy.Rec709_100nits_dim.a1.0.3",
                applied=False,
            ))
            .build()
        )
        assert amf.amf_info.description == "Full pipeline test"
        sv = amf.pipeline.pipeline_info.system_version
        assert (int(sv.major_version), int(sv.minor_version), int(sv.patch_version)) == (2, 0, 0)
        assert amf.pipeline.input_transform is not None
        assert len(amf.pipeline.look_transforms) == 1
        assert amf.pipeline.output_transform is not None

    def test_with_aces_system_version(self):
        amf = AMFBuilder().with_aces_system_version(
            VersionType(major_version="2", minor_version="0", patch_version="0")
        ).build()
        sv = amf.pipeline.pipeline_info.system_version
        assert (int(sv.major_version), int(sv.minor_version), int(sv.patch_version)) == (2, 0, 0)

    def test_write_roundtrip(self, tmp_path):
        """Build, write, re-read, verify."""
        out = tmp_path / "test.amf"
        amf = (
            AMFBuilder()
            .with_description("Roundtrip test")
            .with_author(AuthorType(name="Tester", email_address=None))
            .build()
        )
        save_amf(amf, out, validate=False)

        loaded = load_amf(out, validate=False)
        assert loaded.amf_info.description == "Roundtrip test"
        assert len(loaded.amf_info.author) == 1
        assert loaded.amf_info.author[0].name == "Tester"

    def test_clip_id(self):
        amf = AMFBuilder().with_clip_id(ClipIdType(clip_name="A001C012", file="A001C012.ari")).build()
        assert amf.clip_id is not None
        assert amf.clip_id.clip_name == "A001C012"

    def test_working_location(self):
        """Builder inserts a working location delimiter."""
        amf = AMFBuilder().with_working_location().build()
        items = amf.pipeline.working_location_or_look_transform
        assert len(items) == 1
        assert isinstance(items[0], WorkingLocationType)

    def test_looks_around_working_location(self):
        """Looks added before/after working_location() are ordered correctly."""
        amf = (
            AMFBuilder()
            .with_look_transform(LookTransformType(file="pre_grade.clf", description="Pre", applied=False))
            .with_working_location()
            .with_look_transform(LookTransformType(file="post_grade.clf", description="Post", applied=False))
            .build()
        )
        items = amf.pipeline.working_location_or_look_transform
        assert len(items) == 3
        assert isinstance(items[0], LookTransformType)
        assert isinstance(items[1], WorkingLocationType)
        assert isinstance(items[2], LookTransformType)
        assert items[0].description == "Pre"
        assert items[2].description == "Post"

    def test_working_location_roundtrip(self, tmp_path):
        """Working location ordering survives save/reload."""
        amf = (
            AMFBuilder()
            .with_look_transform(LookTransformType(file="pre.clf", applied=False))
            .with_working_location()
            .with_look_transform(LookTransformType(file="post.clf", applied=False))
            .build()
        )
        out = tmp_path / "wl_test.amf"
        save_amf(amf, out, validate=False)

        loaded = load_amf(out, validate=False)
        items = loaded.pipeline.working_location_or_look_transform
        assert len(items) == 3
        assert isinstance(items[0], LookTransformType)
        assert isinstance(items[1], WorkingLocationType)
        assert isinstance(items[2], LookTransformType)

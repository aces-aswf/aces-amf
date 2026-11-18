# SPDX-License-Identifier: Apache-2.0
"""Tests for the AMF diff module."""

import pytest
from aswf.aces.amf_lib import load_amf, save_amf
from aswf.aces.amf_lib.amf import InputTransformType, LookTransformType
from aswf.aces.amf_utils import AMFBuilder, cdl_look_transform, diff_amf, DiffResult, FieldDiff


class TestDiffAmf:
    def test_identical_objects(self):
        amf1 = AMFBuilder().with_description("Same").build()
        amf2 = AMFBuilder().with_description("Same").build()
        result = diff_amf(amf1, amf2)
        assert not result.has_differences

    def test_different_description(self):
        amf1 = AMFBuilder().with_description("First").build()
        amf2 = AMFBuilder().with_description("Second").build()
        result = diff_amf(amf1, amf2)
        assert result.has_differences
        descs = [d for d in result.differences if d.field == "amf_description"]
        assert len(descs) == 1
        assert descs[0].old_value == "First"
        assert descs[0].new_value == "Second"

    def test_different_aces_version(self):
        amf1 = AMFBuilder(aces_version=(1, 3, 0)).build()
        amf2 = AMFBuilder(aces_version=(2, 0, 0)).build()
        result = diff_amf(amf1, amf2)
        assert result.has_differences
        versions = [d for d in result.differences if d.field == "aces_version"]
        assert len(versions) == 1

    def test_different_input_transform(self):
        amf1 = (
            AMFBuilder()
            .with_input_transform(InputTransformType(transform_id="urn:test:idt1", applied=False))
            .build()
        )
        amf2 = AMFBuilder().build()  # No input transform
        result = diff_amf(amf1, amf2)
        assert result.has_differences
        it_diffs = [d for d in result.differences if "input_transform" in d.field]
        assert len(it_diffs) >= 1

    def test_file_path_comparison(self, tmp_path):
        """Compare two files from disk."""
        f1 = tmp_path / "a.amf"
        f2 = tmp_path / "b.amf"

        amf1 = AMFBuilder().with_description("File A").build()
        amf2 = AMFBuilder().with_description("File B").build()
        save_amf(amf1, f1, validate=False)
        save_amf(amf2, f2, validate=False)

        result = diff_amf(f1, f2)
        assert result.has_differences
        assert result.amf1_path == f1
        assert result.amf2_path == f2

    def test_summary_no_diff(self):
        amf = AMFBuilder().build()
        result = diff_amf(amf, amf)
        assert "identical" in result.summary().lower()

    def test_summary_with_diffs(self):
        amf1 = AMFBuilder().with_description("A").build()
        amf2 = AMFBuilder().with_description("B").build()
        result = diff_amf(amf1, amf2)
        summary = result.summary()
        assert "1 difference" in summary
        assert "amf_description" in summary

    def test_look_transform_count_diff(self):
        amf1 = AMFBuilder().build()
        lt = cdl_look_transform()
        amf2 = AMFBuilder().with_look_transform(lt).build()
        result = diff_amf(amf1, amf2)
        lt_diffs = [d for d in result.differences if "look_transform" in d.field]
        assert len(lt_diffs) >= 1

    def test_verbose_transform_details(self):
        amf1 = AMFBuilder().with_input_transform(InputTransformType(transform_id="urn:a", applied=False)).build()
        amf2 = AMFBuilder().with_input_transform(InputTransformType(transform_id="urn:b", applied=False)).build()
        result = diff_amf(amf1, amf2, verbose=True)
        id_diffs = [d for d in result.differences if "transform_id" in d.field]
        assert len(id_diffs) >= 1

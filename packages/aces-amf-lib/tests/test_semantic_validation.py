# SPDX-License-Identifier: Apache-2.0
"""Tests for semantic validation module."""

import pytest
from pathlib import Path

from aswf.aces.amf_lib import save_amf, load_amf, write_amf
from aswf.aces.amf_utils.factories import minimal_amf, cdl_look_transform
from aswf.aces.amf_lib.validation import (
    validate_semantic,
    validate_schema,
    get_default_registry,
    ValidationContext,
    ValidationLevel,
    ValidationMessage,
    ValidationType,
)
from aswf.aces.amf_lib import amf


@pytest.fixture
def temp_amf_file(tmp_path):
    """Create a temporary AMF file for testing."""
    amf_obj = minimal_amf()
    amf_obj.amf_info.description = "Test AMF"
    amf_obj.pipeline.pipeline_info.description = "Test Pipeline"
    amf_obj.amf_info.author.append(amf.AuthorType(name="Test Author", email_address="test@example.com"))

    amf_path = tmp_path / "test.amf"
    save_amf(amf_obj, amf_path, validate=False)
    return amf_path


class TestValidatorRegistry:
    def test_default_registry_has_core_validators(self):
        registry = get_default_registry()
        names = registry.validator_names
        assert "temporal" in names
        assert "uuid" in names
        assert "cdl" in names
        assert "metadata" in names
        assert "applied_order" in names
        assert "file_paths" in names
        assert "working_space" in names
        assert "transform_ids" in names
        assert "transform_placement" in names
        assert "file_hashes" in names
        assert "transform_id_registry" in names

    def test_validate_minimal_amf(self, temp_amf_file):
        # Exclude transform_id_registry since no registry is provided
        messages = validate_semantic(temp_amf_file, exclude=["transform_id_registry"])
        errors = [m for m in messages if m.level == ValidationLevel.ERROR]
        assert len(errors) == 0

    def test_validate_with_registry(self, temp_amf_file):
        from aswf.aces.transforms import ACESTransformRegistry
        messages = validate_semantic(temp_amf_file, transform_registry=ACESTransformRegistry())
        errors = [m for m in messages if m.level == ValidationLevel.ERROR]
        assert len(errors) == 0

    def test_validate_no_registry_raises(self, temp_amf_file):
        from aswf.aces.amf_lib.validation.types import RegistryNotConfiguredError
        with pytest.raises(RegistryNotConfiguredError):
            validate_semantic(temp_amf_file)

    def test_validate_with_specific_validators(self, temp_amf_file):
        messages = validate_semantic(temp_amf_file, validators=["temporal", "uuid"])
        # Only temporal and uuid validators should have run
        for msg in messages:
            assert msg.validator_name in ("temporal", "uuid")

    def test_validate_with_exclude(self, temp_amf_file):
        messages = validate_semantic(temp_amf_file, exclude=["metadata", "transform_id_registry"])
        for msg in messages:
            assert msg.validator_name != "metadata"

    def test_validate_with_no_validators(self, temp_amf_file):
        messages = validate_semantic(temp_amf_file, validators=[])
        assert len(messages) == 0


class TestDateLogicValidation:
    def test_valid_dates(self, temp_amf_file):
        messages = validate_semantic(temp_amf_file, validators=["temporal"])
        date_errors = [m for m in messages if m.validation_type == ValidationType.INVALID_DATE_LOGIC]
        assert len(date_errors) == 0

    def test_creation_after_modification_error(self, tmp_path):
        """Creation date after modification date produces an ERROR."""
        from xsdata.models.datatype import XmlDateTime
        amf_obj = minimal_amf()
        amf_obj.amf_info.date_time.creation_date_time = XmlDateTime(2026, 6, 1, 0, 0, 0, 0, 0)
        amf_obj.amf_info.date_time.modification_date_time = XmlDateTime(2026, 1, 1, 0, 0, 0, 0, 0)
        amf_path = tmp_path / "test.amf"
        # Use write_amf directly to bypass _prepare_for_write(), which would
        # stamp modification_date_time with the current time and erase the invalid state.
        with open(amf_path, "w") as f:
            write_amf(f, amf_obj)

        msgs = validate_semantic(amf_path, validators=["temporal"])
        errors = [m for m in msgs if m.validation_type == ValidationType.INVALID_DATE_LOGIC]
        assert len(errors) >= 1
        assert "after modification" in errors[0].message

    def test_future_modification_warning(self, tmp_path):
        """Modification date in the future produces a WARNING."""
        from xsdata.models.datatype import XmlDateTime
        from aswf.aces.amf_lib.validation.core_validators.temporal import TemporalValidator

        amf_obj = minimal_amf()
        amf_obj.amf_info.date_time.creation_date_time = XmlDateTime(2026, 1, 1, 0, 0, 0, 0, 0)
        amf_obj.amf_info.date_time.modification_date_time = XmlDateTime(2099, 1, 1, 0, 0, 0, 0, 0)
        amf_obj.pipeline.pipeline_info.date_time.creation_date_time = XmlDateTime(2026, 1, 1, 0, 0, 0, 0, 0)
        amf_obj.pipeline.pipeline_info.date_time.modification_date_time = XmlDateTime(2026, 1, 1, 0, 0, 0, 0, 0)

        validator = TemporalValidator()
        context = ValidationContext()
        msgs = validator.validate(amf_obj, context)
        warnings = [m for m in msgs if m.validation_type == ValidationType.FUTURE_TIMESTAMP]
        assert len(warnings) >= 1
        assert "future" in warnings[0].message.lower()


class TestUUIDValidation:
    def test_unique_uuids(self, temp_amf_file):
        messages = validate_semantic(temp_amf_file, validators=["uuid"])
        uuid_errors = [m for m in messages if m.validation_type == ValidationType.DUPLICATE_UUID]
        assert len(uuid_errors) == 0

    def test_uuid_pool_tracking(self, tmp_path):
        amf1 = minimal_amf()
        amf1_path = tmp_path / "test1.amf"
        save_amf(amf1, amf1_path, validate=False)

        amf2 = minimal_amf()
        amf2_path = tmp_path / "test2.amf"
        save_amf(amf2, amf2_path, validate=False)

        uuid_pool = set()
        messages1 = validate_semantic(amf1_path, validators=["uuid"], uuid_pool=uuid_pool)
        messages2 = validate_semantic(amf2_path, validators=["uuid"], uuid_pool=uuid_pool)

        uuid_errors = [m for m in messages1 + messages2 if m.validation_type == ValidationType.DUPLICATE_UUID]
        assert len(uuid_errors) == 0


class TestCDLValidation:
    def test_valid_cdl(self, tmp_path):
        amf_obj = minimal_amf()
        amf_obj.pipeline.working_location_or_look_transform.append(cdl_look_transform(
            slope=(1.2, 1.0, 0.8), offset=(0.0, 0.0, 0.0), power=(1.0, 1.0, 1.0), saturation=1.05
        ))
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["cdl"])
        cdl_errors = [m for m in messages if m.validation_type == ValidationType.CDL_INVALID_VALUES]
        assert len(cdl_errors) == 0

    def test_identity_cdl_info(self, tmp_path):
        amf_obj = minimal_amf()
        amf_obj.pipeline.working_location_or_look_transform.append(cdl_look_transform(
            slope=(1.0, 1.0, 1.0), offset=(0.0, 0.0, 0.0), power=(1.0, 1.0, 1.0), saturation=1.0
        ))
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["cdl"])
        identity_info = [m for m in messages if m.validation_type == ValidationType.CDL_IDENTITY]
        assert len(identity_info) >= 1
        assert identity_info[0].level == ValidationLevel.INFO

    def test_negative_slope_error(self, tmp_path):
        amf_obj = minimal_amf()
        amf_obj.pipeline.working_location_or_look_transform.append(cdl_look_transform(
            slope=(-1.0, 1.0, 1.0), offset=(0.0, 0.0, 0.0), power=(1.0, 1.0, 1.0), saturation=1.0
        ))
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["cdl"])
        slope_errors = [m for m in messages if m.validation_type == ValidationType.CDL_INVALID_VALUES and "slope" in m.message]
        assert len(slope_errors) >= 1
        assert slope_errors[0].level == ValidationLevel.ERROR

    def test_extreme_slope_warning(self, tmp_path):
        amf_obj = minimal_amf()
        amf_obj.pipeline.working_location_or_look_transform.append(cdl_look_transform(
            slope=(10.0, 1.0, 1.0), offset=(0.0, 0.0, 0.0), power=(1.0, 1.0, 1.0), saturation=1.0
        ))
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["cdl"])
        extreme_warnings = [m for m in messages if m.validation_type == ValidationType.CDL_EXTREME_VALUES and "slope" in m.message]
        assert len(extreme_warnings) >= 1
        assert extreme_warnings[0].level == ValidationLevel.WARNING

    def test_negative_saturation_error(self, tmp_path):
        amf_obj = minimal_amf()
        amf_obj.pipeline.working_location_or_look_transform.append(cdl_look_transform(
            slope=(1.0, 1.0, 1.0), offset=(0.0, 0.0, 0.0), power=(1.0, 1.0, 1.0), saturation=-0.5
        ))
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["cdl"])
        sat_errors = [m for m in messages if m.validation_type == ValidationType.CDL_INVALID_VALUES and "saturation" in m.message]
        assert len(sat_errors) >= 1
        assert sat_errors[0].level == ValidationLevel.ERROR


class TestAppliedOrderValidation:
    def test_valid_all_applied(self, tmp_path):
        amf_obj = minimal_amf()
        for _ in range(3):
            amf_obj.pipeline.working_location_or_look_transform.append(cdl_look_transform(
                slope=(1.0, 1.0, 1.0), offset=(0.0, 0.0, 0.0), power=(1.0, 1.0, 1.0), saturation=1.0
            ))
            amf_obj.pipeline.working_location_or_look_transform[-1].applied = True

        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["applied_order"])
        order_errors = [m for m in messages if m.validation_type == ValidationType.INVALID_APPLIED_ORDER]
        assert len(order_errors) == 0

    def test_invalid_non_applied_then_applied(self, tmp_path):
        amf_obj = minimal_amf()
        amf_obj.pipeline.working_location_or_look_transform.append(cdl_look_transform(
            slope=(1.0, 1.0, 1.0), offset=(0.0, 0.0, 0.0), power=(1.0, 1.0, 1.0), saturation=1.0
        ))
        amf_obj.pipeline.working_location_or_look_transform[-1].applied = False
        amf_obj.pipeline.working_location_or_look_transform[-1].description = "Non-applied First"

        amf_obj.pipeline.working_location_or_look_transform.append(cdl_look_transform(
            slope=(1.2, 1.0, 0.8), offset=(0.0, 0.0, 0.0), power=(1.0, 1.0, 1.0), saturation=1.05
        ))
        amf_obj.pipeline.working_location_or_look_transform[-1].applied = True
        amf_obj.pipeline.working_location_or_look_transform[-1].description = "Applied Second"

        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["applied_order"])
        order_errors = [m for m in messages if m.validation_type == ValidationType.INVALID_APPLIED_ORDER]
        assert len(order_errors) == 1
        assert order_errors[0].level == ValidationLevel.ERROR
        assert "Applied Second" in order_errors[0].message


class TestMetadataValidation:
    def test_missing_description_info(self, tmp_path):
        amf_obj = minimal_amf()
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["metadata"])
        desc_msgs = [m for m in messages if m.validation_type == ValidationType.MISSING_DESCRIPTION]
        assert len(desc_msgs) >= 1
        assert desc_msgs[0].level == ValidationLevel.INFO

    def test_missing_author_info(self, tmp_path):
        amf_obj = minimal_amf()
        amf_obj.amf_info.description = "Test"
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["metadata"])
        author_msgs = [m for m in messages if m.validation_type == ValidationType.MISSING_AUTHOR]
        assert len(author_msgs) >= 1
        assert author_msgs[0].level == ValidationLevel.INFO

    def test_complete_metadata(self, temp_amf_file):
        messages = validate_semantic(temp_amf_file, validators=["metadata"])
        author_warnings = [m for m in messages if m.validation_type == ValidationType.MISSING_AUTHOR]
        assert len(author_warnings) == 0


class TestFilePathValidation:
    def test_absolute_path_warning(self, tmp_path):
        amf_obj = minimal_amf()
        amf_obj.pipeline.input_transform = amf.InputTransformType(applied=True, file="/absolute/path/to/file.clf")

        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["file_paths"])
        path_warnings = [m for m in messages if m.validation_type == ValidationType.NON_PORTABLE_PATH]
        assert len(path_warnings) >= 1
        assert "absolute path" in path_warnings[0].message.lower()

    def test_parent_directory_warning(self, tmp_path):
        amf_obj = minimal_amf()
        amf_obj.pipeline.input_transform = amf.InputTransformType(applied=True, file="../parent/file.clf")

        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["file_paths"])
        path_warnings = [m for m in messages if m.validation_type == ValidationType.UNSAFE_FILE_PATH]
        assert len(path_warnings) >= 1
        assert ".." in path_warnings[0].message

    def test_relative_path_valid(self, tmp_path):
        amf_obj = minimal_amf()
        amf_obj.pipeline.input_transform = amf.InputTransformType(applied=True, file="relative/path/to/file.clf")

        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["file_paths"])
        path_warnings = [m for m in messages if m.validation_type in [
            ValidationType.UNSAFE_FILE_PATH,
            ValidationType.NON_PORTABLE_PATH,
        ]]
        assert len(path_warnings) == 0


    def test_backslash_path_warning(self, tmp_path):
        """Backslash in file path produces a WARNING."""
        amf_obj = minimal_amf()
        amf_obj.pipeline.input_transform = amf.InputTransformType(applied=True, file="looks\\grade.clf")
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        msgs = validate_semantic(amf_path, validators=["file_paths"])
        warnings = [m for m in msgs if m.validation_type == ValidationType.NON_PORTABLE_PATH and "backslash" in m.message.lower()]
        assert len(warnings) == 1

    def test_non_clf_format_warning(self, tmp_path):
        """Non-CLF LUT format on a transform produces a WARNING."""
        amf_obj = minimal_amf()
        amf_obj.pipeline.input_transform = amf.InputTransformType(applied=True, file="look.cube")
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        msgs = validate_semantic(amf_path, validators=["file_paths"])
        warnings = [m for m in msgs if m.validation_type == ValidationType.NON_CLF_TRANSFORM_FILE]
        assert len(warnings) == 1
        assert ".cube" in warnings[0].message
        assert "CLF (.clf)" in warnings[0].message

    def test_clf_format_no_warning(self, tmp_path):
        """CLF format on a transform produces no warnings."""
        amf_obj = minimal_amf()
        amf_obj.pipeline.input_transform = amf.InputTransformType(applied=True, file="look.clf")
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        msgs = validate_semantic(amf_path, validators=["file_paths"])
        warnings = [m for m in msgs if m.validation_type == ValidationType.NON_CLF_TRANSFORM_FILE]
        assert len(warnings) == 0

    def test_cdl_collection_valid_extension(self, tmp_path):
        """CCC file on a CDL look transform produces no warnings."""
        amf_obj = minimal_amf()
        lt = amf.LookTransformType(
            file="grades.ccc",
            color_correction_ref=amf.ColorCorrectionRef(ref="shot_001"),
            applied=False,
        )
        amf_obj.pipeline.working_location_or_look_transform.append(lt)
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        msgs = validate_semantic(amf_path, validators=["file_paths"])
        warnings = [m for m in msgs if m.validation_type == ValidationType.NON_CLF_TRANSFORM_FILE]
        assert len(warnings) == 0

    def test_cdl_collection_wrong_extension(self, tmp_path):
        """Non-CDL file on a CDL look transform produces a WARNING."""
        amf_obj = minimal_amf()
        lt = amf.LookTransformType(
            file="grades.clf",
            color_correction_ref=amf.ColorCorrectionRef(ref="shot_001"),
            applied=False,
        )
        amf_obj.pipeline.working_location_or_look_transform.append(lt)
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        msgs = validate_semantic(amf_path, validators=["file_paths"])
        warnings = [m for m in msgs if m.validation_type == ValidationType.NON_CLF_TRANSFORM_FILE]
        assert len(warnings) == 1
        assert "CDL collection" in warnings[0].message


class TestCDLBoundaryFixes:
    """Tests for CDL boundary check fixes (slope=0 and sat=0 are valid per XSD)."""

    def test_cdl_slope_zero_valid(self, tmp_path):
        """Slope=0 is valid per XSD (nonNegativeFloatType) — should be WARNING, not ERROR."""
        amf_obj = minimal_amf()
        amf_obj.pipeline.working_location_or_look_transform.append(cdl_look_transform(
            slope=(0.0, 1.0, 1.0), offset=(0.0, 0.0, 0.0), power=(1.0, 1.0, 1.0), saturation=1.0
        ))
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["cdl"])
        slope_errors = [m for m in messages if m.validation_type == ValidationType.CDL_INVALID_VALUES and "slope" in m.message]
        assert len(slope_errors) == 0, "slope=0 should not be an ERROR (valid per XSD)"

        slope_warnings = [m for m in messages if m.validation_type == ValidationType.CDL_EXTREME_VALUES and "slope" in m.message]
        assert len(slope_warnings) >= 1, "slope=0 should produce a WARNING"
        assert slope_warnings[0].level == ValidationLevel.WARNING

    def test_cdl_saturation_zero_valid(self, tmp_path):
        """Saturation=0 is valid per XSD (nonNegativeFloatType) — should be WARNING, not ERROR."""
        amf_obj = minimal_amf()
        amf_obj.pipeline.working_location_or_look_transform.append(cdl_look_transform(
            slope=(1.0, 1.0, 1.0), offset=(0.0, 0.0, 0.0), power=(1.0, 1.0, 1.0), saturation=0.0
        ))
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["cdl"])
        sat_errors = [m for m in messages if m.validation_type == ValidationType.CDL_INVALID_VALUES and "saturation" in m.message]
        assert len(sat_errors) == 0, "saturation=0 should not be an ERROR (valid per XSD)"

        sat_warnings = [m for m in messages if m.validation_type == ValidationType.CDL_EXTREME_VALUES and "saturation" in m.message]
        assert len(sat_warnings) >= 1, "saturation=0 should produce a WARNING"
        assert sat_warnings[0].level == ValidationLevel.WARNING

    def test_cdl_power_zero_error(self, tmp_path):
        """Power=0 is invalid per XSD (positiveFloatType, minExclusive=0) — should be ERROR."""
        amf_obj = minimal_amf()
        amf_obj.pipeline.working_location_or_look_transform.append(cdl_look_transform(
            slope=(1.0, 1.0, 1.0), offset=(0.0, 0.0, 0.0), power=(0.0, 1.0, 1.0), saturation=1.0
        ))
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["cdl"])
        power_errors = [m for m in messages if m.validation_type == ValidationType.CDL_INVALID_VALUES and "power" in m.message]
        assert len(power_errors) >= 1, "power=0 should be an ERROR"
        assert power_errors[0].level == ValidationLevel.ERROR


class TestArchivedPipelineValidation:
    """Tests that all validators cover archived pipelines."""

    def _make_amf_with_archived(self, tmp_path, **overrides):
        """Create AMF with an archived pipeline containing a CDL look."""
        import uuid as uuid_mod
        amf_obj = minimal_amf()
        amf_obj.amf_info.description = "Test AMF"
        amf_obj.amf_info.author.append(amf.AuthorType(name="Test Author", email_address="test@example.com"))
        amf_obj.pipeline.pipeline_info.description = "Active pipeline"

        archived_info = amf.PipelineInfoType(
            date_time=amf_obj.pipeline.pipeline_info.date_time,
            uuid=uuid_mod.uuid4().urn,
            system_version=amf.VersionType(major_version=1, minor_version=3, patch_version=0),
            description="Archived pipeline",
        )
        archived = amf.PipelineType(pipeline_info=archived_info, **overrides)
        amf_obj.archived_pipeline.append(archived)

        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)
        return amf_path

    def test_archived_cdl_validation(self, tmp_path):
        """CDL validator should catch errors in archived pipelines."""
        look = cdl_look_transform(
            slope=(-1.0, 1.0, 1.0), offset=(0.0, 0.0, 0.0), power=(1.0, 1.0, 1.0), saturation=1.0
        )
        look.description = "Bad CDL"
        amf_path = self._make_amf_with_archived(tmp_path)
        # Load, add look to archived, save
        amf_obj = load_amf(amf_path, validate=False)
        amf_obj.archived_pipeline[0].working_location_or_look_transform.append(look)
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["cdl"])
        archived_errors = [m for m in messages if "Archived" in m.message and m.validation_type == ValidationType.CDL_INVALID_VALUES]
        assert len(archived_errors) >= 1

    def test_archived_applied_order_validation(self, tmp_path):
        """Applied order validator should catch errors in archived pipelines."""
        amf_path = self._make_amf_with_archived(tmp_path)
        amf_obj = load_amf(amf_path, validate=False)

        lt1 = cdl_look_transform()
        lt1.applied = False
        lt1.description = "Non-applied"
        lt2 = cdl_look_transform()
        lt2.applied = True
        lt2.description = "Applied after non-applied"
        amf_obj.archived_pipeline[0].working_location_or_look_transform.extend([lt1, lt2])
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["applied_order"])
        archived_errors = [m for m in messages if "Archived" in m.message and m.validation_type == ValidationType.INVALID_APPLIED_ORDER]
        assert len(archived_errors) >= 1

    def test_archived_file_path_validation(self, tmp_path):
        """File path validator should catch issues in archived pipelines."""
        amf_path = self._make_amf_with_archived(tmp_path)
        amf_obj = load_amf(amf_path, validate=False)

        amf_obj.archived_pipeline[0].input_transform = amf.InputTransformType(
            applied=True, file="/absolute/bad.clf"
        )
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["file_paths"])
        archived_warnings = [m for m in messages if "Archived" in m.message and m.validation_type == ValidationType.NON_PORTABLE_PATH]
        assert len(archived_warnings) >= 1

    def test_archived_metadata_validation(self, tmp_path):
        """Metadata validator should check archived pipeline descriptions."""
        import uuid as uuid_mod
        amf_obj = minimal_amf()
        amf_obj.amf_info.description = "Test AMF"
        amf_obj.amf_info.author.append(amf.AuthorType(name="Test Author", email_address="test@example.com"))
        amf_obj.pipeline.pipeline_info.description = "Active pipeline"

        # Archived pipeline with no description
        archived_info = amf.PipelineInfoType(
            date_time=amf_obj.pipeline.pipeline_info.date_time,
            uuid=uuid_mod.uuid4().urn,
            system_version=amf.VersionType(major_version=1, minor_version=3, patch_version=0),
        )
        archived = amf.PipelineType(pipeline_info=archived_info)
        amf_obj.archived_pipeline.append(archived)

        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["metadata"])
        archived_warnings = [m for m in messages if "Archived" in m.message and m.validation_type == ValidationType.MISSING_DESCRIPTION]
        assert len(archived_warnings) >= 1

    def test_archived_transform_ids_validation(self, tmp_path):
        """Transform ID validator should check archived pipeline transforms."""
        amf_path = self._make_amf_with_archived(tmp_path)
        amf_obj = load_amf(amf_path, validate=False)

        amf_obj.archived_pipeline[0].input_transform = amf.InputTransformType(
            applied=True, transform_id="bad-format-id"
        )
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["transform_ids"])
        archived_warnings = [m for m in messages if "Archived" in m.message and m.validation_type == ValidationType.INVALID_TRANSFORM_ID]
        assert len(archived_warnings) >= 1


class TestCDLAlternateFields:
    """Tests for CDL SOPNode/SatNode alternate element names."""

    def test_cdl_sopnode_alternate(self, tmp_path):
        """CDL validation should work with SOPNode/SatNode fields (not just ASC_SOP/ASC_SAT)."""
        amf_obj = minimal_amf()
        lt = amf.LookTransformType(
            sopnode=amf.Sopnode(slope=[-1.0, 1.0, 1.0], offset=[0.0, 0.0, 0.0], power=[1.0, 1.0, 1.0]),
            sat_node=amf.SatNode(saturation=1.0),
            cdl_working_space=amf.CdlWorkingSpaceType(
                from_cdl_working_space=amf.WorkingSpaceTransformType(
                    transform_id="urn:ampas:aces:transformId:v1.5:ACEScsc.Academy.ACEScct_to_ACES.a1.0.3"
                ),
            ),
            applied=False,
        )
        amf_obj.pipeline.working_location_or_look_transform.append(lt)
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["cdl"])
        slope_errors = [m for m in messages if m.validation_type == ValidationType.CDL_INVALID_VALUES and "slope" in m.message]
        assert len(slope_errors) >= 1, "CDL validator should catch invalid slope via SOPNode alternate"

    def test_cdl_identity_sopnode(self, tmp_path):
        """Identity detection should work with SOPNode/SatNode fields."""
        amf_obj = minimal_amf()
        lt = amf.LookTransformType(
            sopnode=amf.Sopnode(slope=[1.0, 1.0, 1.0], offset=[0.0, 0.0, 0.0], power=[1.0, 1.0, 1.0]),
            sat_node=amf.SatNode(saturation=1.0),
            cdl_working_space=amf.CdlWorkingSpaceType(
                from_cdl_working_space=amf.WorkingSpaceTransformType(
                    transform_id="urn:ampas:aces:transformId:v1.5:ACEScsc.Academy.ACEScct_to_ACES.a1.0.3"
                ),
            ),
            applied=False,
        )
        amf_obj.pipeline.working_location_or_look_transform.append(lt)
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["cdl"])
        identity_msgs = [m for m in messages if m.validation_type == ValidationType.CDL_IDENTITY]
        assert len(identity_msgs) >= 1, "Identity detection should work via SOPNode/SatNode alternate"

    def test_color_correction_ref_without_file_error(self, tmp_path):
        """ColorCorrectionRef without a file element should produce an ERROR.

        The XSD requires a file alongside ColorCorrectionRef in the CDL branch of
        lookTransformType (minOccurs=1), so its absence is schema-invalid.
        """
        amf_obj = minimal_amf()
        lt = amf.LookTransformType(
            color_correction_ref=amf.ColorCorrectionRef(ref="cc-001"),
            applied=False,
        )
        amf_obj.pipeline.working_location_or_look_transform.append(lt)
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["cdl"])
        ccr_msgs = [m for m in messages if m.validation_type == ValidationType.CDL_MISSING_CCR_FILE]
        assert len(ccr_msgs) == 1
        assert ccr_msgs[0].level == ValidationLevel.ERROR
        assert "ColorCorrectionRef" in ccr_msgs[0].message

    def test_color_correction_ref_with_file_no_error(self, tmp_path):
        """ColorCorrectionRef WITH a file element should not produce an error."""
        amf_obj = minimal_amf()
        lt = amf.LookTransformType(
            color_correction_ref=amf.ColorCorrectionRef(ref="cc-001"),
            file="grades.ccc",
            applied=False,
        )
        amf_obj.pipeline.working_location_or_look_transform.append(lt)
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["cdl"])
        ccr_msgs = [m for m in messages if m.validation_type == ValidationType.CDL_MISSING_CCR_FILE]
        assert len(ccr_msgs) == 0


class TestNestedSubTransforms:
    """Tests for validation of nested sub-transforms (RRT, ODT, inverse transforms)."""

    def test_nested_transform_id_validation(self, tmp_path):
        """Malformed transform ID in referenceRenderingTransform should be detected."""
        amf_obj = minimal_amf()
        amf_obj.pipeline.output_transform = amf.OutputTransformType(
            applied=True,
            reference_rendering_transform=amf.ReferenceRenderingTransformType(
                transform_id="bad-rrt-format"
            ),
            output_device_transform=amf.OutputDeviceTransformType(
                transform_id="urn:ampas:aces:transformId:v1.5:ODT.Academy.Rec709_100nits_dim.a1.0.3"
            ),
        )
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["transform_ids"])
        rrt_warnings = [m for m in messages if "referenceRenderingTransform" in m.message]
        assert len(rrt_warnings) >= 1, "Malformed RRT transform ID should be detected"

    def test_nested_file_path_validation(self, tmp_path):
        """Absolute path in nested outputDeviceTransform.file should be detected."""
        amf_obj = minimal_amf()
        amf_obj.pipeline.output_transform = amf.OutputTransformType(
            applied=True,
            output_device_transform=amf.OutputDeviceTransformType(
                file="/absolute/path/odt.clf"
            ),
        )
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["file_paths"])
        nested_warnings = [m for m in messages if "outputDeviceTransform" in m.message]
        assert len(nested_warnings) >= 1, "Absolute path in nested transform should be detected"

    def test_nested_uuid_duplicate(self, tmp_path):
        """Duplicate UUID in nested sub-transform should be detected."""
        shared_uuid = "urn:uuid:12345678-1234-1234-1234-123456789abc"
        amf_obj = minimal_amf()
        amf_obj.pipeline.output_transform = amf.OutputTransformType(
            applied=True,
            uuid=shared_uuid,
            reference_rendering_transform=amf.ReferenceRenderingTransformType(
                uuid=shared_uuid,  # duplicate!
            ),
        )
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["uuid"])
        dup_errors = [m for m in messages if m.validation_type == ValidationType.DUPLICATE_UUID]
        assert len(dup_errors) >= 1, "Duplicate UUID in nested sub-transform should be detected"

    def test_input_inverse_transform_id_validation(self, tmp_path):
        """Malformed transform ID in input's inverseOutputDeviceTransform should be detected."""
        amf_obj = minimal_amf()
        amf_obj.pipeline.input_transform = amf.InputTransformType(
            applied=True,
            inverse_output_device_transform=amf.InverseOutputDeviceTransformType(
                transform_id="bad-inv-odt-format"
            ),
        )
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["transform_ids"])
        inv_warnings = [m for m in messages if "inverseOutputDeviceTransform" in m.message]
        assert len(inv_warnings) >= 1, "Malformed inverse ODT transform ID should be detected"


class TestPrepareForWriteArchived:
    """Tests for prepare_for_write archived pipeline handling."""

    def test_archived_mod_timestamp_updated(self, tmp_path):
        """prepare_for_write should update archived pipeline modification timestamps."""
        import uuid as uuid_mod
        from aswf.aces.amf_lib.amf_helpers import amf_date_time_now

        amf_obj = minimal_amf()
        archived_info = amf.PipelineInfoType(
            date_time=amf_date_time_now(),
            uuid=uuid_mod.uuid4().urn,
            system_version=amf.VersionType(major_version=1, minor_version=3, patch_version=0),
        )
        original_uuid = archived_info.uuid
        amf_obj.archived_pipeline.append(amf.PipelineType(pipeline_info=archived_info))

        # Save triggers prepare_for_write
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        # UUID should be preserved (archived = historical identity)
        assert amf_obj.archived_pipeline[0].pipeline_info.uuid == original_uuid
        # Modification timestamp should have been updated (same as amf_info)
        assert (amf_obj.archived_pipeline[0].pipeline_info.date_time.modification_date_time
                == amf_obj.amf_info.date_time.modification_date_time)


class TestFilePathNoUnquote:
    """Regression: file paths with % should not be URL-decoded."""

    def test_file_path_percent_preserved(self, tmp_path):
        """A file path containing %20 should be validated as-is, not decoded."""
        amf_obj = minimal_amf()
        amf_obj.pipeline.input_transform = amf.InputTransformType(
            applied=True, file="path/with%20space/file.clf"
        )
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        messages = validate_semantic(amf_path, validators=["file_paths"])
        # Should not produce security warnings — %20 is just a literal character sequence
        security_warnings = [m for m in messages if m.validation_type in [
            ValidationType.UNSAFE_FILE_PATH,
            ValidationType.NON_PORTABLE_PATH,
        ]]
        assert len(security_warnings) == 0


class TestConvenienceFunction:
    def test_convenience_function(self, temp_amf_file):
        messages = validate_semantic(temp_amf_file, exclude=["transform_id_registry"])
        assert isinstance(messages, list)
        errors = [m for m in messages if m.level == ValidationLevel.ERROR]
        assert len(errors) == 0


class TestValidationMessage:
    def test_validation_message_string(self):
        msg = ValidationMessage(
            level=ValidationLevel.ERROR,
            validation_type=ValidationType.DUPLICATE_UUID,
            message="Test error message"
        )
        msg_str = str(msg)
        assert "ERROR" in msg_str
        assert "Test error message" in msg_str

    def test_validation_message_with_file_path(self):
        msg = ValidationMessage(
            level=ValidationLevel.WARNING,
            validation_type=ValidationType.MISSING_DESCRIPTION,
            message="Missing description",
            file_path=Path("/tmp/test.amf")
        )
        msg_str = str(msg)
        assert "WARNING" in msg_str
        assert "test.amf" in msg_str


class TestMultipleWorkingLocations:
    """Validate that at most one workingLocation is allowed per pipeline."""

    def test_zero_working_locations_valid(self, tmp_path):
        """A pipeline with no workingLocation is valid."""
        amf_obj = minimal_amf()
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)
        msgs = validate_semantic(amf_path, validators=["working_space"])
        wl_msgs = [m for m in msgs if m.validation_type == ValidationType.MULTIPLE_WORKING_LOCATIONS]
        assert len(wl_msgs) == 0

    def test_one_working_location_valid(self, tmp_path):
        """A pipeline with exactly one workingLocation is valid."""
        amf_obj = minimal_amf()
        amf_obj.pipeline.working_location_or_look_transform.append(amf.WorkingLocationType())
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)
        msgs = validate_semantic(amf_path, validators=["working_space"])
        wl_msgs = [m for m in msgs if m.validation_type == ValidationType.MULTIPLE_WORKING_LOCATIONS]
        assert len(wl_msgs) == 0

    def test_multiple_working_locations_error(self, tmp_path):
        """A pipeline with 2+ workingLocations produces an ERROR."""
        amf_obj = minimal_amf()
        amf_obj.pipeline.working_location_or_look_transform.append(amf.WorkingLocationType())
        amf_obj.pipeline.working_location_or_look_transform.append(amf.WorkingLocationType())
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)
        msgs = validate_semantic(amf_path, validators=["working_space"])
        wl_msgs = [m for m in msgs if m.validation_type == ValidationType.MULTIPLE_WORKING_LOCATIONS]
        assert len(wl_msgs) == 1
        assert wl_msgs[0].level == ValidationLevel.ERROR
        assert "2 workingLocation" in wl_msgs[0].message

    def test_archived_multiple_working_locations_error(self, tmp_path):
        """Archived pipelines with 2+ workingLocations also produce an ERROR."""
        from aswf.aces.amf_lib.amf_helpers import amf_xml_date_time

        amf_obj = minimal_amf()
        now = amf_xml_date_time()
        archived = amf.PipelineType(pipeline_info=amf.PipelineInfoType(
            uuid="urn:uuid:00000000-0000-0000-0000-000000000099",
            date_time=amf.DateTimeType(
                creation_date_time=now,
                modification_date_time=now,
            ),
            system_version=amf.VersionType(major_version=1, minor_version=3, patch_version=0),
        ))
        archived.working_location_or_look_transform.append(amf.WorkingLocationType())
        archived.working_location_or_look_transform.append(amf.WorkingLocationType())
        amf_obj.archived_pipeline.append(archived)
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)
        msgs = validate_semantic(amf_path, validators=["working_space"])
        wl_msgs = [m for m in msgs if m.validation_type == ValidationType.MULTIPLE_WORKING_LOCATIONS]
        assert len(wl_msgs) == 1
        assert "Archived pipeline #1" in wl_msgs[0].message

    def test_cdl_without_working_space_error(self, tmp_path):
        """CDL with no working space specified produces an ERROR."""
        amf_obj = minimal_amf()
        lt = amf.LookTransformType(
            asc_sop=amf.AscSop(slope=[1.0, 1.0, 1.0], offset=[0.0, 0.0, 0.0], power=[1.0, 1.0, 1.0]),
            asc_sat=amf.AscSat(saturation=1.0),
            applied=False,
        )
        amf_obj.pipeline.working_location_or_look_transform.append(lt)
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        msgs = validate_semantic(amf_path, validators=["working_space"])
        errors = [m for m in msgs if m.validation_type == ValidationType.MISSING_CDL_WORKING_SPACE]
        assert len(errors) == 1
        assert errors[0].level == ValidationLevel.ERROR
        assert "no working space" in errors[0].message.lower()

    def test_asc_sop_no_cdl_working_space_real_world(self, test_data_path):
        """Real-world DaVinci Resolve AMF: ASC_SOP look transforms without cdlWorkingSpace.

        Verifies three things:
        1. cdl:ASC_SOP is accepted at parse time — xsdata respects CDL substitution groups.
        2. Schema validation (lxml XSD) rejects the file — cdlWorkingSpace is mandatory
           in the CDL branch, so this is the primary gate in the full validate=True flow.
        3. Semantic validation flags MISSING_CDL_WORKING_SPACE at ERROR level for each
           CDL look transform that omits the required cdlWorkingSpace element.
        """
        amf_path = test_data_path / "test_ASC_SOP_no_cdlworkingSpace.amf"

        amf_obj = load_amf(amf_path, validate=False)
        assert amf_obj is not None

        schema_errors = [m for m in validate_schema(amf_path) if m.validation_type == ValidationType.SCHEMA_VIOLATION]
        assert len(schema_errors) >= 1
        assert all(m.level == ValidationLevel.ERROR for m in schema_errors)

        msgs = validate_semantic(amf_path, validators=["working_space"])

        errors = [m for m in msgs if m.validation_type == ValidationType.MISSING_CDL_WORKING_SPACE]
        assert len(errors) > 0
        assert all(m.level == ValidationLevel.ERROR for m in errors)

        other_errors = [
            m for m in msgs
            if m.level == ValidationLevel.ERROR
            and m.validation_type != ValidationType.MISSING_CDL_WORKING_SPACE
        ]
        assert len(other_errors) == 0

    def _cdl_working_space(self):
        return amf.CdlWorkingSpaceType(
            from_cdl_working_space=amf.WorkingSpaceTransformType(
                transform_id="urn:ampas:aces:transformId:v1.5:ACEScsc.Academy.ACEScct_to_ACES.a1.0.3"
            ),
        )

    def test_asc_sop_asc_sat_without_working_space(self, tmp_path):
        """ASC_SOP/ASC_SAT without cdlWorkingSpace.

        - Parse succeeds (substitution group respected).
        - Schema (lxml XSD) rejects it: cdlWorkingSpace is mandatory in the CDL
          branch of lookTransformType, so this is the primary gate via validate=True.
        - Semantic layer (run in isolation) also flags it as an ERROR.
        """
        amf_obj = minimal_amf()
        lt = amf.LookTransformType(
            asc_sop=amf.AscSop(slope=[1.0, 1.0, 1.0], offset=[0.0, 0.0, 0.0], power=[1.0, 1.0, 1.0]),
            asc_sat=amf.AscSat(saturation=1.0),
            applied=False,
        )
        amf_obj.pipeline.working_location_or_look_transform.append(lt)
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        loaded = load_amf(amf_path, validate=False)
        assert loaded is not None

        # Schema layer is the real gatekeeper in the full validate=True flow.
        schema_msgs = validate_schema(amf_path)
        schema_errors = [m for m in schema_msgs if m.validation_type == ValidationType.SCHEMA_VIOLATION]
        assert len(schema_errors) >= 1
        assert all(m.level == ValidationLevel.ERROR for m in schema_errors)

        # Semantic layer, run in isolation, also catches it with a clearer message.
        msgs = validate_semantic(amf_path, validators=["working_space"])
        errors = [m for m in msgs if m.validation_type == ValidationType.MISSING_CDL_WORKING_SPACE]
        assert len(errors) == 1
        assert errors[0].level == ValidationLevel.ERROR

    def test_asc_sop_asc_sat_with_working_space(self, tmp_path):
        """ASC_SOP/ASC_SAT with valid cdlWorkingSpace: parse + schema pass, no MISSING_CDL_WORKING_SPACE."""
        amf_obj = minimal_amf()
        lt = amf.LookTransformType(
            asc_sop=amf.AscSop(slope=[1.0, 1.0, 1.0], offset=[0.0, 0.0, 0.0], power=[1.0, 1.0, 1.0]),
            asc_sat=amf.AscSat(saturation=1.0),
            cdl_working_space=self._cdl_working_space(),
            applied=False,
        )
        amf_obj.pipeline.working_location_or_look_transform.append(lt)
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        loaded = load_amf(amf_path, validate=False)
        assert loaded is not None

        # With cdlWorkingSpace present, the schema accepts the CDL branch (ASC_SOP included).
        schema_errors = [m for m in validate_schema(amf_path) if m.validation_type == ValidationType.SCHEMA_VIOLATION]
        assert len(schema_errors) == 0

        msgs = validate_semantic(amf_path, validators=["working_space"])
        errors = [m for m in msgs if m.validation_type == ValidationType.MISSING_CDL_WORKING_SPACE]
        assert len(errors) == 0

    def test_sopnode_satnode_without_working_space(self, tmp_path):
        """SOPNode/SatNode without cdlWorkingSpace.

        - Parse succeeds (substitution group respected).
        - Schema (lxml XSD) rejects it: cdlWorkingSpace is mandatory in the CDL
          branch of lookTransformType, so this is the primary gate via validate=True.
        - Semantic layer (run in isolation) also flags it as an ERROR.
        """
        amf_obj = minimal_amf()
        lt = amf.LookTransformType(
            sopnode=amf.Sopnode(slope=[1.0, 1.0, 1.0], offset=[0.0, 0.0, 0.0], power=[1.0, 1.0, 1.0]),
            sat_node=amf.SatNode(saturation=1.0),
            applied=False,
        )
        amf_obj.pipeline.working_location_or_look_transform.append(lt)
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        loaded = load_amf(amf_path, validate=False)
        assert loaded is not None

        # Schema layer is the real gatekeeper in the full validate=True flow.
        schema_msgs = validate_schema(amf_path)
        schema_errors = [m for m in schema_msgs if m.validation_type == ValidationType.SCHEMA_VIOLATION]
        assert len(schema_errors) >= 1
        assert all(m.level == ValidationLevel.ERROR for m in schema_errors)

        # Semantic layer, run in isolation, also catches it with a clearer message.
        msgs = validate_semantic(amf_path, validators=["working_space"])
        errors = [m for m in msgs if m.validation_type == ValidationType.MISSING_CDL_WORKING_SPACE]
        assert len(errors) == 1
        assert errors[0].level == ValidationLevel.ERROR

    def test_sopnode_satnode_with_working_space(self, tmp_path):
        """SOPNode/SatNode with valid cdlWorkingSpace: parse + schema pass, no MISSING_CDL_WORKING_SPACE."""
        amf_obj = minimal_amf()
        lt = amf.LookTransformType(
            sopnode=amf.Sopnode(slope=[1.0, 1.0, 1.0], offset=[0.0, 0.0, 0.0], power=[1.0, 1.0, 1.0]),
            sat_node=amf.SatNode(saturation=1.0),
            cdl_working_space=self._cdl_working_space(),
            applied=False,
        )
        amf_obj.pipeline.working_location_or_look_transform.append(lt)
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        loaded = load_amf(amf_path, validate=False)
        assert loaded is not None

        # With cdlWorkingSpace present, the schema accepts the CDL branch (SOPNode included).
        schema_errors = [m for m in validate_schema(amf_path) if m.validation_type == ValidationType.SCHEMA_VIOLATION]
        assert len(schema_errors) == 0

        msgs = validate_semantic(amf_path, validators=["working_space"])
        errors = [m for m in msgs if m.validation_type == ValidationType.MISSING_CDL_WORKING_SPACE]
        assert len(errors) == 0

    def test_missing_from_cdl_working_space_error(self, tmp_path):
        """CDL with toCdlWorkingSpace but no fromCdlWorkingSpace produces an ERROR."""
        from aswf.aces.amf_lib.validation.core_validators.working_space import WorkingSpaceValidator

        amf_obj = minimal_amf()
        lt = amf.LookTransformType(
            asc_sop=amf.AscSop(slope=[1.0, 1.0, 1.0], offset=[0.0, 0.0, 0.0], power=[1.0, 1.0, 1.0]),
            asc_sat=amf.AscSat(saturation=1.0),
            cdl_working_space=amf.CdlWorkingSpaceType.model_construct(
                to_cdl_working_space=amf.WorkingSpaceTransformType(
                    transform_id="urn:ampas:aces:transformId:v1.5:ACEScsc.Academy.ACES_to_ACEScct.a1.0.3"
                ),
                from_cdl_working_space=None,
            ),
            applied=False,
        )
        amf_obj.pipeline.working_location_or_look_transform.append(lt)

        validator = WorkingSpaceValidator()
        context = ValidationContext()
        msgs = validator.validate(amf_obj, context)
        errors = [m for m in msgs if m.validation_type == ValidationType.CDL_WORKING_SPACE_MISMATCH]
        assert len(errors) == 1
        assert "fromCdlWorkingSpace" in errors[0].message


class TestVersionMismatchValidation:
    """Tests for URN version mismatch detection in TransformRegistryValidator."""

    def test_mismatched_cdl_working_space_error(self, transform_registry):
        """Registered CDL working-space transforms must form an inverse pair."""
        path = Path(__file__).parent / "Generated_Samples_AMF/invalid_AMFs/invalid_12_mismatched_working_space.amf"
        msgs = validate_semantic(path, validators=["transform_id_registry"], transform_registry=transform_registry)
        errors = [m for m in msgs if m.validation_type == ValidationType.CDL_WORKING_SPACE_MISMATCH]
        assert len(errors) == 1
        assert errors[0].level == ValidationLevel.ERROR

    def test_version_mismatch_with_equivalents_csc(self, test_data_path, transform_registry):
        """v1.5 CSC URNs in v2.0 AMF → WARNINGs recommending canonical IDs."""
        path = test_data_path / "mixed_urns_with_equivalent_csc.amf"
        msgs = validate_semantic(path, validators=["transform_id_registry"], transform_registry=transform_registry)
        mismatch_msgs = [m for m in msgs if m.validation_type == ValidationType.VERSION_MISMATCH_TRANSFORM_ID]
        assert len(mismatch_msgs) == 2  # toCdlWorkingSpace + fromCdlWorkingSpace
        for m in mismatch_msgs:
            assert m.level == ValidationLevel.WARNING
            assert "previous equivalent" in m.message

    def test_version_mismatch_rgc_all_resolvable(self, test_data_path, transform_registry):
        """v1.5 RGC + CSC URNs in v2.0 AMF → all WARNINGs (all found as previous equivalents)."""
        path = test_data_path / "mixed_urns_no_equivalent_rgc.amf"
        msgs = validate_semantic(path, validators=["transform_id_registry"], transform_registry=transform_registry)
        mismatch_msgs = [m for m in msgs if m.validation_type == ValidationType.VERSION_MISMATCH_TRANSFORM_ID]
        assert len(mismatch_msgs) == 3  # RGC + 2 CSCs
        for m in mismatch_msgs:
            assert m.level == ValidationLevel.WARNING

    def test_version_mismatch_no_equivalent_error(self, test_data_path, transform_registry):
        """v1.5 LogC URN with no v2.0 equivalent → ERROR (unknown for this version)."""
        path = test_data_path / "mixed_urns_no_equivalent_logc.amf"
        msgs = validate_semantic(path, validators=["transform_id_registry"], transform_registry=transform_registry)
        errors = [m for m in msgs if m.level == ValidationLevel.ERROR]
        assert len(errors) == 1
        assert "unknown transform ID" in errors[0].message
        assert "LogC_EI800_AWG" in errors[0].message

    def test_clean_v2_amf_no_mismatch(self, aces_amf_examples_path, transform_registry):
        """A pure v2.0 AMF should produce no version mismatch messages."""
        path = aces_amf_examples_path / "example1.amf"
        msgs = validate_semantic(path, validators=["transform_id_registry"], transform_registry=transform_registry)
        mismatch_msgs = [m for m in msgs if m.validation_type == ValidationType.VERSION_MISMATCH_TRANSFORM_ID]
        assert len(mismatch_msgs) == 0

    def test_unknown_ocio_urn_is_error(self, transform_registry):
        """An OCIO transform URN not in the ACES registry must produce an ERROR."""
        amf_obj = minimal_amf()
        amf_obj.pipeline.input_transform = amf.InputTransformType(
            transform_id="urn:aswf:ocio:transformId:1.0:ARRI:Input:ARRI_LogC3_EI800_to_ACES2065-1:1.0",
            applied=False,
        )
        context = ValidationContext(transform_registry=transform_registry)
        from aswf.aces.amf_lib.validation.registry import get_default_registry
        registry = get_default_registry()
        msgs = registry.validate(amf_obj, context)
        errors = [m for m in msgs if m.level == ValidationLevel.ERROR]
        assert len(errors) >= 1
        assert any("malformed transform ID" in e.message for e in errors)


class TestTransformIDFormatValidation:
    """Tests for URN format validation in TransformRegistryValidator."""

    def _validate_with_idt(self, transform_id, aces_version, transform_registry):
        """Helper: create a minimal AMF with given IDT and validate."""
        amf_obj = minimal_amf(aces_version=aces_version)
        amf_obj.pipeline.input_transform = amf.InputTransformType(
            transform_id=transform_id, applied=False,
        )
        context = ValidationContext(transform_registry=transform_registry)
        from aswf.aces.amf_lib.validation.registry import get_default_registry
        registry = get_default_registry()
        return registry.validate(amf_obj, context)

    def test_malformed_id_is_error(self, transform_registry):
        """A completely invalid string produces MALFORMED_TRANSFORM_ID ERROR."""
        msgs = self._validate_with_idt("not-a-valid-id", (1, 3, 0), transform_registry)
        errors = [m for m in msgs if m.level == ValidationLevel.ERROR]
        assert len(errors) == 1
        assert errors[0].validation_type == ValidationType.MALFORMED_TRANSFORM_ID

    def test_full_urn_in_v2_amf_ok(self, transform_registry):
        """A valid full URN in a v2.x AMF passes format validation."""
        msgs = self._validate_with_idt(
            "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScct.a2.v1",
            (2, 0, 0), transform_registry,
        )
        malformed = [m for m in msgs if m.validation_type == ValidationType.MALFORMED_TRANSFORM_ID]
        assert len(malformed) == 0

    def test_valid_v15_urn_in_v13_amf(self, transform_registry):
        """A valid v1.5 URN in a v1.3 AMF passes validation."""
        msgs = self._validate_with_idt(
            "urn:ampas:aces:transformId:v1.5:IDT.ARRI.ARRI-LogC4.a1.v1",
            (1, 3, 0), transform_registry,
        )
        errors = [m for m in msgs if m.level == ValidationLevel.ERROR]
        assert len(errors) == 0

    def test_unknown_urn_in_v2_amf_is_error(self, transform_registry):
        """A well-formed URN not in the v2.0 registry set is an ERROR."""
        msgs = self._validate_with_idt(
            "urn:ampas:aces:transformId:v2.0:Input.FakeVendor.FakeCamera.a2.v1",
            (2, 0, 0), transform_registry,
        )
        errors = [m for m in msgs if m.level == ValidationLevel.ERROR]
        assert len(errors) == 1
        assert errors[0].validation_type == ValidationType.INVALID_TRANSFORM_ID


# All transform locations that can carry a <file> + <hash> reference.
# Key -> substring expected in the validator message label (proves collection reached it).
_HASH_LOCATION_LABELS = {
    "input": "Input transform",
    "output": "Output transform",
    "look": "Look transform",
    "inverseOutputTransform": "inverseOutputTransform",
    "inverseOutputDeviceTransform": "inverseOutputDeviceTransform",
    "inverseReferenceRenderingTransform": "inverseReferenceRenderingTransform",
    "referenceRenderingTransform": "referenceRenderingTransform",
    "outputDeviceTransform": "outputDeviceTransform",
}
_HASH_LOCATIONS = list(_HASH_LOCATION_LABELS)


def _amf_with_hashed_file(location: str, file_name: str, hash_obj) -> amf.AcesMetadataFile:
    """Build a minimal AMF that references ``file_name`` with ``hash_obj`` at ``location``.

    Covers every file-bearing transform: the top-level input/output/look transforms
    and the nested sub-transforms reachable via collect_sub_transforms(). Parent
    input/output transforms in the nested cases carry no hash of their own, so the
    only hash to verify is the one on the sub-transform.
    """
    amf_obj = minimal_amf()
    pipeline = amf_obj.pipeline

    if location == "input":
        pipeline.input_transform = amf.InputTransformType(file=file_name, hash=hash_obj, applied=True)
    elif location == "output":
        pipeline.output_transform = amf.OutputTransformType(file=file_name, hash=hash_obj, applied=True)
    elif location == "look":
        pipeline.working_location_or_look_transform.append(
            amf.LookTransformType(file=file_name, hash=hash_obj, applied=False)
        )
    elif location == "inverseOutputTransform":
        pipeline.input_transform = amf.InputTransformType(
            applied=True,
            inverse_output_transform=amf.InverseOutputTransformType(file=file_name, hash=hash_obj),
        )
    elif location == "inverseOutputDeviceTransform":
        pipeline.input_transform = amf.InputTransformType(
            applied=True,
            inverse_output_device_transform=amf.InverseOutputDeviceTransformType(file=file_name, hash=hash_obj),
        )
    elif location == "inverseReferenceRenderingTransform":
        pipeline.input_transform = amf.InputTransformType(
            applied=True,
            inverse_reference_rendering_transform=amf.InverseReferenceRenderingTransformType(
                file=file_name, hash=hash_obj
            ),
        )
    elif location == "referenceRenderingTransform":
        pipeline.output_transform = amf.OutputTransformType(
            applied=True,
            reference_rendering_transform=amf.ReferenceRenderingTransformType(file=file_name, hash=hash_obj),
        )
    elif location == "outputDeviceTransform":
        pipeline.output_transform = amf.OutputTransformType(
            applied=True,
            output_device_transform=amf.OutputDeviceTransformType(file=file_name, hash=hash_obj),
        )
    else:
        raise ValueError(f"Unknown hash location: {location}")

    return amf_obj


class TestFileHashValidator:
    """Tests for file_hashes validator: compute and verify hashes for referenced files."""

    def _make_amf_with_hash(self, tmp_path, hash_value, algorithm=None):
        """Helper: create AMF with a look transform referencing a file with a hash."""
        import hashlib

        # Create a real file to reference
        clf_file = tmp_path / "test_look.clf"
        clf_file.write_bytes(b"<ProcessList/>")

        if algorithm is None:
            algorithm = amf.HashAlgoType.HTTP_WWW_W3_ORG_2001_04_XMLDSIG_MORE_MD5

        amf_obj = minimal_amf()
        lt = amf.LookTransformType(
            file="test_look.clf",
            hash=amf.HashType(value=hash_value, algorithm=algorithm),
            applied=False,
        )
        amf_obj.pipeline.working_location_or_look_transform.append(lt)

        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)
        return amf_path

    def test_valid_hash_passes(self, tmp_path):
        """Correct hash produces no errors."""
        import hashlib

        clf_content = b"<ProcessList/>"
        correct_hash = hashlib.md5(clf_content).digest()

        amf_path = self._make_amf_with_hash(tmp_path, correct_hash)
        msgs = validate_semantic(amf_path, base_path=tmp_path, validators=["file_hashes"])
        errors = [m for m in msgs if m.level == ValidationLevel.ERROR]
        assert len(errors) == 0

    def test_hash_mismatch_error(self, tmp_path):
        """Wrong hash produces an ERROR."""
        amf_path = self._make_amf_with_hash(tmp_path, b"\x00" * 16)
        msgs = validate_semantic(amf_path, base_path=tmp_path, validators=["file_hashes"])
        errors = [m for m in msgs if m.validation_type == ValidationType.HASH_MISMATCH]
        assert len(errors) == 1
        assert "mismatch" in errors[0].message.lower()

    def test_hash_file_not_found_warning(self, tmp_path):
        """Missing file produces a WARNING."""
        amf_obj = minimal_amf()
        lt = amf.LookTransformType(
            file="nonexistent.clf",
            hash=amf.HashType(
                value=b"\x00" * 16,
                algorithm=amf.HashAlgoType.HTTP_WWW_W3_ORG_2001_04_XMLDSIG_MORE_MD5,
            ),
            applied=False,
        )
        amf_obj.pipeline.working_location_or_look_transform.append(lt)
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        msgs = validate_semantic(amf_path, base_path=tmp_path, validators=["file_hashes"])
        warnings = [m for m in msgs if m.validation_type == ValidationType.HASH_FILE_NOT_FOUND]
        assert len(warnings) == 1

    def test_unsupported_hash_algorithm_warning(self, tmp_path):
        """Unknown hash algorithm produces a WARNING."""
        from aswf.aces.amf_lib.validation.core_validators.file_hashes import FileHashValidator

        clf_file = tmp_path / "test_look.clf"
        clf_file.write_bytes(b"<ProcessList/>")

        amf_obj = minimal_amf()
        lt = amf.LookTransformType(
            file="test_look.clf",
            hash=amf.HashType.model_construct(
                value=b"\x00" * 16,
                algorithm="http://example.com/unknown-algo",
            ),
            applied=False,
        )
        amf_obj.pipeline.working_location_or_look_transform.append(lt)

        validator = FileHashValidator()
        context = ValidationContext(base_path=tmp_path)
        msgs = validator.validate(amf_obj, context)
        warnings = [m for m in msgs if m.validation_type == ValidationType.HASH_ALGORITHM_UNSUPPORTED]
        assert len(warnings) == 1

    # --- Coverage across every file-bearing transform location -------------------

    @pytest.mark.parametrize("location", _HASH_LOCATIONS)
    def test_hash_mismatch_detected_at_all_locations(self, tmp_path, location):
        """A wrong hash is detected as a HASH_MISMATCH ERROR at every file-bearing location."""
        from aswf.aces.amf_lib.validation.core_validators.file_hashes import FileHashValidator

        file_name = "ref.clf"
        (tmp_path / file_name).write_bytes(b"<ProcessList/>")

        # Declared hash deliberately does not match the file content.
        hash_obj = amf.HashType(
            value=b"\x00" * 16,
            algorithm=amf.HashAlgoType.HTTP_WWW_W3_ORG_2001_04_XMLDSIG_MORE_MD5,
        )
        amf_obj = _amf_with_hashed_file(location, file_name, hash_obj)

        msgs = FileHashValidator().validate(amf_obj, ValidationContext(base_path=tmp_path))
        mismatches = [m for m in msgs if m.validation_type == ValidationType.HASH_MISMATCH]
        assert len(mismatches) == 1, f"expected one HASH_MISMATCH at {location}, got {msgs}"
        assert mismatches[0].level == ValidationLevel.ERROR
        assert _HASH_LOCATION_LABELS[location] in mismatches[0].message

    @pytest.mark.parametrize("location", _HASH_LOCATIONS)
    def test_valid_hash_passes_at_all_locations(self, tmp_path, location):
        """A correct hash produces no HASH_MISMATCH at every file-bearing location."""
        import hashlib

        from aswf.aces.amf_lib.validation.core_validators.file_hashes import FileHashValidator

        file_name = "ref.clf"
        content = b"<ProcessList/>"
        (tmp_path / file_name).write_bytes(content)

        hash_obj = amf.HashType(
            value=hashlib.md5(content).digest(),
            algorithm=amf.HashAlgoType.HTTP_WWW_W3_ORG_2001_04_XMLDSIG_MORE_MD5,
        )
        amf_obj = _amf_with_hashed_file(location, file_name, hash_obj)

        msgs = FileHashValidator().validate(amf_obj, ValidationContext(base_path=tmp_path))
        mismatches = [m for m in msgs if m.validation_type == ValidationType.HASH_MISMATCH]
        assert len(mismatches) == 0, f"unexpected HASH_MISMATCH at {location}: {msgs}"

    @pytest.mark.parametrize("location", _HASH_LOCATIONS)
    def test_unsupported_algorithm_detected_at_all_locations(self, tmp_path, location):
        """An unsupported hash algorithm is flagged at every file-bearing location."""
        from aswf.aces.amf_lib.validation.core_validators.file_hashes import FileHashValidator

        file_name = "ref.clf"
        (tmp_path / file_name).write_bytes(b"<ProcessList/>")

        # model_construct bypasses the HashAlgoType enum so we can inject an unsupported algo.
        hash_obj = amf.HashType.model_construct(
            value=b"\x00" * 16,
            algorithm="http://example.com/unknown-algo",
        )
        amf_obj = _amf_with_hashed_file(location, file_name, hash_obj)

        msgs = FileHashValidator().validate(amf_obj, ValidationContext(base_path=tmp_path))
        warnings = [m for m in msgs if m.validation_type == ValidationType.HASH_ALGORITHM_UNSUPPORTED]
        assert len(warnings) == 1, f"expected one HASH_ALGORITHM_UNSUPPORTED at {location}, got {msgs}"
        assert _HASH_LOCATION_LABELS[location] in warnings[0].message

    def test_invalid_hash_algorithm_rejected_at_parse_or_schema(self, tmp_path):
        """A hash algorithm outside the XSD enum is rejected at parse/schema, not silently accepted.

        HashAlgoType is a closed enum (sha256/sha1/md5), so a genuinely invalid algorithm in
        a real AMF cannot be parsed/validated as a supported value — it must be caught at the
        Pydantic parse layer or by XSD schema validation.
        """
        import hashlib
        import warnings

        file_name = "ref.clf"
        content = b"<ProcessList/>"
        (tmp_path / file_name).write_bytes(content)

        amf_obj = minimal_amf()
        amf_obj.pipeline.working_location_or_look_transform.append(
            amf.LookTransformType(
                file=file_name,
                hash=amf.HashType(
                    value=hashlib.md5(content).digest(),
                    algorithm=amf.HashAlgoType.HTTP_WWW_W3_ORG_2001_04_XMLDSIG_MORE_MD5,
                ),
                applied=False,
            )
        )
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        # Swap the valid algorithm URI for one that is not in the XSD enum.
        text = amf_path.read_text()
        assert "http://www.w3.org/2001/04/xmldsig-more#md5" in text
        amf_path.write_text(text.replace("http://www.w3.org/2001/04/xmldsig-more#md5", "http://example.com/bogus-algo"))

        parse_failed = False
        try:
            # The bogus algorithm trips an expected xsdata ConverterWarning before raising.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                load_amf(amf_path, validate=False)
        except Exception:
            parse_failed = True

        schema_errors = [m for m in validate_schema(amf_path) if m.validation_type == ValidationType.SCHEMA_VIOLATION]
        assert parse_failed or schema_errors, "invalid hash algorithm should be rejected at parse or schema layer"


_HASH_ALGOS = [
    ("md5", amf.HashAlgoType.HTTP_WWW_W3_ORG_2001_04_XMLDSIG_MORE_MD5),
    ("sha1", amf.HashAlgoType.HTTP_WWW_W3_ORG_2000_09_XMLDSIG_SHA1),
    ("sha256", amf.HashAlgoType.HTTP_WWW_W3_ORG_2001_04_XMLENC_SHA256),
]


def _save_amf_with_hash_text(tmp_path, *, algo_enum, digest_bytes, hash_text, location="look",
                             file_name="ref.clf", content=b"<ProcessList/>"):
    """Build+save an AMF referencing a real file with a hash, then rewrite the serialized
    <hash> text to ``hash_text`` (e.g. the hex form). Returns the AMF path.

    Because save_amf emits the hash as base64, we replace that base64 token with the
    desired on-disk text to simulate a producer that wrote hex (or something invalid).
    """
    import base64

    (tmp_path / file_name).write_bytes(content)
    hash_obj = amf.HashType(value=digest_bytes, algorithm=algo_enum)
    amf_obj = _amf_with_hashed_file(location, file_name, hash_obj)
    path = tmp_path / "test.amf"
    save_amf(amf_obj, path, validate=False)

    b64 = base64.b64encode(digest_bytes).decode("ascii")
    txt = path.read_text()
    assert b64 in txt, "expected base64 hash token in serialized AMF"
    path.write_text(txt.replace(b64, hash_text))
    return path


class TestHashEncoding:
    """Hex hash support: normalize on load, warn (non-standard), error if neither encoding."""

    @pytest.mark.parametrize("algo_name,algo_enum", _HASH_ALGOS)
    def test_hex_hash_normalizes_verifies_and_warns(self, tmp_path, algo_name, algo_enum):
        import hashlib
        content = b"<ProcessList/>"
        digest = hashlib.new(algo_name, content).digest()
        path = _save_amf_with_hash_text(
            tmp_path, algo_enum=algo_enum, digest_bytes=digest, hash_text=digest.hex()
        )

        # Normalized on load: value is the true digest bytes, tagged as hex.
        obj = load_amf(path, validate=False)
        h = obj.pipeline.look_transforms[0].hash
        assert h.value == digest
        assert h._source_encoding == "hex"

        # Verifies against the file (no mismatch) and warns that hex is non-standard.
        msgs = validate_semantic(path, base_path=tmp_path, validators=["file_hashes", "hash_encoding"])
        assert not [m for m in msgs if m.validation_type == ValidationType.HASH_MISMATCH]
        warns = [m for m in msgs if m.validation_type == ValidationType.HASH_ENCODING_NON_STANDARD]
        assert len(warns) == 1
        assert warns[0].level == ValidationLevel.WARNING

    @pytest.mark.parametrize("algo_name,algo_enum", _HASH_ALGOS)
    def test_wrong_hex_hash_is_mismatch(self, tmp_path, algo_name, algo_enum):
        import hashlib
        content = b"<ProcessList/>"
        wrong = hashlib.new(algo_name, b"a different payload").digest()
        path = _save_amf_with_hash_text(
            tmp_path, algo_enum=algo_enum, digest_bytes=wrong, hash_text=wrong.hex()
        )
        msgs = validate_semantic(path, base_path=tmp_path, validators=["file_hashes"])
        assert [m for m in msgs if m.validation_type == ValidationType.HASH_MISMATCH]

    def test_hex_hash_on_nested_transform_warns(self, tmp_path):
        import hashlib
        content = b"<ProcessList/>"
        digest = hashlib.md5(content).digest()
        path = _save_amf_with_hash_text(
            tmp_path,
            algo_enum=amf.HashAlgoType.HTTP_WWW_W3_ORG_2001_04_XMLDSIG_MORE_MD5,
            digest_bytes=digest,
            hash_text=digest.hex(),
            location="outputDeviceTransform",
        )
        msgs = validate_semantic(path, base_path=tmp_path, validators=["file_hashes", "hash_encoding"])
        assert not [m for m in msgs if m.validation_type == ValidationType.HASH_MISMATCH]
        warns = [m for m in msgs if m.validation_type == ValidationType.HASH_ENCODING_NON_STANDARD]
        assert len(warns) == 1
        assert "outputDeviceTransform" in warns[0].message

    def test_neither_base64_nor_hex_is_error(self, tmp_path):
        import base64
        # MD5 digest size is 16; a 15-byte value is neither 16 (base64) nor 24 (hex-as-base64).
        path = _save_amf_with_hash_text(
            tmp_path,
            algo_enum=amf.HashAlgoType.HTTP_WWW_W3_ORG_2001_04_XMLDSIG_MORE_MD5,
            digest_bytes=b"\x01" * 16,
            hash_text=base64.b64encode(b"\x02" * 15).decode("ascii"),
        )
        # No base_path needed — encoding validity is independent of the referenced file.
        msgs = validate_semantic(path, validators=["hash_encoding"])
        errs = [m for m in msgs if m.validation_type == ValidationType.HASH_ENCODING_INVALID]
        assert len(errs) == 1
        assert errs[0].level == ValidationLevel.ERROR

    @pytest.mark.parametrize("algo_name,algo_enum", _HASH_ALGOS)
    def test_base64_hash_no_warning(self, tmp_path, algo_name, algo_enum):
        import hashlib
        content = b"<ProcessList/>"
        digest = hashlib.new(algo_name, content).digest()
        (tmp_path / "ref.clf").write_bytes(content)
        amf_obj = _amf_with_hashed_file("look", "ref.clf", amf.HashType(value=digest, algorithm=algo_enum))
        path = tmp_path / "test.amf"
        save_amf(amf_obj, path, validate=False)

        obj = load_amf(path, validate=False)
        assert obj.pipeline.look_transforms[0].hash._source_encoding == "base64"

        msgs = validate_semantic(path, base_path=tmp_path, validators=["file_hashes", "hash_encoding"])
        assert not [
            m for m in msgs
            if m.validation_type in (
                ValidationType.HASH_ENCODING_NON_STANDARD,
                ValidationType.HASH_ENCODING_INVALID,
                ValidationType.HASH_MISMATCH,
            )
        ]

    def test_schema_accepts_hex_hash(self, tmp_path):
        import hashlib
        digest = hashlib.md5(b"<ProcessList/>").digest()
        path = _save_amf_with_hash_text(
            tmp_path,
            algo_enum=amf.HashAlgoType.HTTP_WWW_W3_ORG_2001_04_XMLDSIG_MORE_MD5,
            digest_bytes=digest,
            hash_text=digest.hex(),
        )
        schema_errors = [m for m in validate_schema(path) if m.validation_type == ValidationType.SCHEMA_VIOLATION]
        assert not schema_errors

    def test_hex_auto_migrates_to_base64_on_save(self, tmp_path):
        import hashlib, base64
        content = b"<ProcessList/>"
        digest = hashlib.md5(content).digest()
        path = _save_amf_with_hash_text(
            tmp_path,
            algo_enum=amf.HashAlgoType.HTTP_WWW_W3_ORG_2001_04_XMLDSIG_MORE_MD5,
            digest_bytes=digest,
            hash_text=digest.hex(),
        )

        obj = load_amf(path, validate=False)  # normalized to digest bytes
        out = tmp_path / "out.amf"
        save_amf(obj, out, validate=False)

        txt = out.read_text()
        assert base64.b64encode(digest).decode("ascii") in txt
        assert digest.hex() not in txt

        reloaded = load_amf(out, validate=False)
        rh = reloaded.pipeline.look_transforms[0].hash
        assert rh.value == digest
        assert rh._source_encoding == "base64"


class TestFileReferenceValidator:
    """Tests for file_references validator: existence, hashes, CCC cross-refs."""

    def test_valid_file_reference(self, tmp_path):
        """Existing file produces no errors."""
        clf_file = tmp_path / "look.clf"
        clf_file.write_bytes(b"<ProcessList/>")

        amf_obj = minimal_amf()
        lt = amf.LookTransformType(file="look.clf", applied=False)
        amf_obj.pipeline.working_location_or_look_transform.append(lt)
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        msgs = validate_semantic(amf_path, base_path=tmp_path, validators=["file_references"])
        errors = [m for m in msgs if m.level == ValidationLevel.ERROR]
        assert len(errors) == 0

    def test_missing_file_error(self, tmp_path):
        """Non-existent file produces an ERROR."""
        amf_obj = minimal_amf()
        lt = amf.LookTransformType(file="nonexistent.clf", applied=False)
        amf_obj.pipeline.working_location_or_look_transform.append(lt)
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        msgs = validate_semantic(amf_path, base_path=tmp_path, validators=["file_references"])
        errors = [m for m in msgs if m.validation_type == ValidationType.MISSING_REFERENCED_FILE]
        assert len(errors) == 1
        assert "nonexistent.clf" in errors[0].message

    def test_ccc_valid_ref(self, tmp_path):
        """Valid ColorCorrection ID in CCC file produces no errors."""
        ccc_file = tmp_path / "grades.ccc"
        ccc_file.write_text(
            '<?xml version="1.0"?>\n'
            '<ColorCorrectionCollection xmlns="urn:ASC:CDL:v1.01">\n'
            '  <ColorCorrection id="shot_001">\n'
            '    <SOPNode><Slope>1.0 1.0 1.0</Slope><Offset>0.0 0.0 0.0</Offset>'
            '<Power>1.0 1.0 1.0</Power></SOPNode>\n'
            '    <SatNode><Saturation>1.0</Saturation></SatNode>\n'
            '  </ColorCorrection>\n'
            '</ColorCorrectionCollection>\n'
        )

        amf_obj = minimal_amf()
        lt = amf.LookTransformType(
            file="grades.ccc",
            color_correction_ref=amf.ColorCorrectionRef(ref="shot_001"),
            applied=False,
        )
        amf_obj.pipeline.working_location_or_look_transform.append(lt)
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        msgs = validate_semantic(amf_path, base_path=tmp_path, validators=["file_references"])
        errors = [m for m in msgs if m.level == ValidationLevel.ERROR]
        assert len(errors) == 0

    def test_ccc_missing_id_error(self, tmp_path):
        """Wrong ColorCorrection ID produces an ERROR."""
        ccc_file = tmp_path / "grades.ccc"
        ccc_file.write_text(
            '<?xml version="1.0"?>\n'
            '<ColorCorrectionCollection xmlns="urn:ASC:CDL:v1.01">\n'
            '  <ColorCorrection id="shot_001">\n'
            '    <SOPNode><Slope>1.0 1.0 1.0</Slope><Offset>0.0 0.0 0.0</Offset>'
            '<Power>1.0 1.0 1.0</Power></SOPNode>\n'
            '    <SatNode><Saturation>1.0</Saturation></SatNode>\n'
            '  </ColorCorrection>\n'
            '</ColorCorrectionCollection>\n'
        )

        amf_obj = minimal_amf()
        lt = amf.LookTransformType(
            file="grades.ccc",
            color_correction_ref=amf.ColorCorrectionRef(ref="wrong_id"),
            applied=False,
        )
        amf_obj.pipeline.working_location_or_look_transform.append(lt)
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        msgs = validate_semantic(amf_path, base_path=tmp_path, validators=["file_references"])
        errors = [m for m in msgs if m.validation_type == ValidationType.CCC_MISSING_ID]
        assert len(errors) == 1
        assert "wrong_id" in errors[0].message

    def test_no_base_path_skips(self, tmp_path):
        """Without base_path, file_references validator produces no messages."""
        amf_obj = minimal_amf()
        lt = amf.LookTransformType(file="nonexistent.clf", applied=False)
        amf_obj.pipeline.working_location_or_look_transform.append(lt)
        amf_path = tmp_path / "test.amf"
        save_amf(amf_obj, amf_path, validate=False)

        # Run validation without base_path
        context = ValidationContext(amf_path=amf_path)
        from aswf.aces.amf_lib.validation.core_validators.file_references import FileReferenceValidator
        validator = FileReferenceValidator()
        amf_obj = load_amf(amf_path, validate=False)
        msgs = validator.validate(amf_obj, context)
        assert len(msgs) == 0


class TestAuthorEmailOptional:
    def test_author_without_email_is_valid(self, tmp_path):
        """AMF with an author that has no email passes full semantic validation."""
        amf_obj = minimal_amf()
        amf_obj.amf_info.author = [amf.AuthorType(name="No Email Author")]
        amf_path = tmp_path / "no_email.amf"
        save_amf(amf_obj, amf_path, validate=False)

        msgs = validate_semantic(amf_path, exclude=["transform_id_registry"])
        errors = [m for m in msgs if m.level.name == "ERROR"]
        assert len(errors) == 0

    def test_author_with_email_is_valid(self, tmp_path):
        """AMF with a valid author email passes full semantic validation."""
        amf_obj = minimal_amf()
        amf_obj.amf_info.author = [amf.AuthorType(name="With Email", email_address="author@example.com")]
        amf_path = tmp_path / "with_email.amf"
        save_amf(amf_obj, amf_path, validate=False)

        msgs = validate_semantic(amf_path, exclude=["transform_id_registry"])
        errors = [m for m in msgs if m.level.name == "ERROR"]
        assert len(errors) == 0

    def test_author_email_roundtrip(self, tmp_path):
        """email_address=None round-trips through save/load correctly."""
        amf_obj = minimal_amf()
        amf_obj.amf_info.author = [amf.AuthorType(name="Tester")]
        amf_path = tmp_path / "roundtrip.amf"
        save_amf(amf_obj, amf_path, validate=False)

        loaded = load_amf(amf_path, validate=False)
        assert loaded.amf_info.author[0].email_address is None

# SPDX-License-Identifier: Apache-2.0
"""Tests for CLI commands."""

import pytest
from click.testing import CliRunner
from pathlib import Path

from aswf.aces.amf_lib import load_amf, save_amf
from aswf.aces.amf_lib.amf import AuthorType, InputTransformType, OutputTransformType
from aswf.aces.amf_utils.cli import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def sample_amf(tmp_path):
    """Create a sample AMF file for testing."""
    from aswf.aces.amf_utils import AMFBuilder

    path = tmp_path / "sample.amf"
    amf = (
        AMFBuilder(aces_version=(1, 3, 0))
        .with_description("CLI Test")
        .with_author(AuthorType(name="Tester", email_address="test@example.com"))
        .with_input_transform(InputTransformType(
            transform_id="urn:ampas:aces:transformId:v1.5:IDT.ARRI.ARRI-LogC4.a1.v1",
            applied=False,
        ))
        .with_output_transform(OutputTransformType(
            transform_id="urn:ampas:aces:transformId:v1.5:RRTODT.Academy.P3D65_1000nits_15nits_ST2084.a1.1.0",
            applied=False,
        ))
        .build()
    )
    save_amf(amf, path, validate=False)
    return path


class TestMainGroup:
    def test_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "AMF" in result.output

    def test_version(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0


class TestInfoCommand:
    def test_info(self, runner, sample_amf):
        result = runner.invoke(main, ["info", str(sample_amf)])
        assert result.exit_code == 0
        assert "CLI Test" in result.output
        assert "Tester" in result.output

    def test_info_verbose(self, runner, sample_amf):
        result = runner.invoke(main, ["info", "-v", str(sample_amf)])
        assert result.exit_code == 0
        assert "CLI Test" in result.output
        assert "Input Transform" in result.output


class TestValidateCommand:
    def test_validate_valid_file(self, runner, sample_amf):
        result = runner.invoke(main, ["validate", str(sample_amf)])
        # Should either pass or only have warnings (not errors from schema)
        assert "sample.amf" in result.output

    def test_validate_schema_only(self, runner, sample_amf):
        result = runner.invoke(main, ["validate", "--schema-only", str(sample_amf)])
        assert "sample.amf" in result.output

    def test_validate_nonexistent(self, runner):
        result = runner.invoke(main, ["validate", "/nonexistent.amf"])
        assert result.exit_code != 0


class TestCreateCommand:
    def test_create_basic(self, runner, tmp_path):
        out = tmp_path / "new.amf"
        result = runner.invoke(main, [
            "create", str(out),
            "-d", "New AMF",
            "--author", "Creator",
        ])
        assert result.exit_code == 0
        assert out.exists()

        amf = load_amf(out, validate=False)
        assert amf.amf_info.description == "New AMF"

    def test_create_author_without_email(self, runner, tmp_path):
        """--author without --author-email produces a valid AMF (email is optional)."""
        out = tmp_path / "no_email.amf"
        result = runner.invoke(main, [
            "create", str(out),
            "--author", "Creator",
        ])
        assert result.exit_code == 0
        amf = load_amf(out, validate=False)
        assert amf.amf_info.author[0].name == "Creator"
        assert amf.amf_info.author[0].email_address is None

    def test_create_with_transforms(self, runner, tmp_path):
        out = tmp_path / "with_transforms.amf"
        result = runner.invoke(main, [
            "create", str(out),
            "--aces-version", "1.3.0",
            "--idt", "urn:ampas:aces:transformId:v1.5:IDT.ARRI.ARRI-LogC4.a1.v1",
            "--odt", "urn:ampas:aces:transformId:v1.5:RRTODT.Academy.P3D65_1000nits_15nits_ST2084.a1.1.0",
        ])
        assert result.exit_code == 0
        assert out.exists()
        assert load_amf(out, validate=False).pipeline.pipeline_info.system_version.major_version == 1

    def test_create_defaults_to_aces_2(self, runner, tmp_path):
        out = tmp_path / "default_version.amf"
        result = runner.invoke(main, [
            "create", str(out),
            "--idt", _PIPELINE_IDS[(2, 0, 0)][0],
            "--odt", _PIPELINE_IDS[(2, 0, 0)][1],
        ])
        assert result.exit_code == 0, result.output
        sv = load_amf(out, validate=False).pipeline.pipeline_info.system_version
        assert (sv.major_version, sv.minor_version, sv.patch_version) == (2, 0, 0)
        assert runner.invoke(main, ["validate", str(out)]).exit_code == 0

    def test_create_no_overwrite(self, runner, tmp_path):
        out = tmp_path / "existing.amf"
        out.write_text("placeholder")
        result = runner.invoke(main, ["create", str(out)])
        assert result.exit_code != 0
        assert "exists" in result.output.lower()

    def test_create_force_overwrite(self, runner, tmp_path):
        out = tmp_path / "existing.amf"
        out.write_text("placeholder")
        result = runner.invoke(main, ["create", str(out), "--force"])
        assert result.exit_code == 0


class TestDiffCommand:
    def test_diff_identical(self, runner, sample_amf, tmp_path):
        copy = tmp_path / "copy.amf"
        amf = load_amf(sample_amf, validate=False)
        save_amf(amf, copy, validate=False)
        result = runner.invoke(main, ["diff", str(sample_amf), str(copy)])
        assert result.exit_code == 0
        assert "identical" in result.output.lower()

    def test_diff_different(self, runner, tmp_path):
        from aswf.aces.amf_utils import AMFBuilder

        f1 = tmp_path / "a.amf"
        f2 = tmp_path / "b.amf"
        save_amf(AMFBuilder().with_description("A").build(), f1, validate=False)
        save_amf(AMFBuilder().with_description("B").build(), f2, validate=False)

        result = runner.invoke(main, ["diff", str(f1), str(f2)])
        assert result.exit_code == 1
        assert "difference" in result.output.lower()


class TestAddCdlCommand:
    def test_add_cdl(self, runner, sample_amf, tmp_path):
        out = tmp_path / "with_cdl.amf"
        result = runner.invoke(main, [
            "add-cdl", str(sample_amf),
            "--slope", "1.2", "1.0", "0.8",
            "--saturation", "0.95",
            "-d", "Primary grade",
            "-o", str(out),
        ])
        assert result.exit_code == 0
        assert out.exists()

        amf = load_amf(out, validate=False)
        assert len(amf.pipeline.look_transforms) >= 1


class TestComputeHashesCommand:
    def test_compute_hash(self, runner, sample_amf):
        result = runner.invoke(main, ["compute-hashes", str(sample_amf)])
        assert result.exit_code == 0
        assert "SHA256" in result.output

    def test_compute_hash_md5(self, runner, sample_amf):
        result = runner.invoke(main, ["compute-hashes", str(sample_amf), "--algorithm", "md5"])
        assert result.exit_code == 0
        assert "MD5" in result.output


class TestTransformsCommand:
    def test_transforms_list(self, runner):
        result = runner.invoke(main, ["transforms", "list", "-n", "5"])
        assert result.exit_code == 0
        assert "transform(s)" in result.output

    def test_transforms_categories(self, runner):
        result = runner.invoke(main, ["transforms", "categories"])
        assert result.exit_code == 0

    def test_transforms_info(self, runner):
        result = runner.invoke(main, [
            "transforms", "info",
            "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScc.a2.v1",
        ])
        assert result.exit_code == 0
        assert "ACES" in result.output


class TestTemplateCommand:
    def test_template_list_empty(self, runner):
        # Registry may be empty in test environment — should not crash
        result = runner.invoke(main, ["template", "list"])
        assert result.exit_code == 0

    def test_template_list_verbose(self, runner):
        result = runner.invoke(main, ["template", "list", "--verbose"])
        assert result.exit_code == 0

    def test_template_list_by_category(self, runner):
        result = runner.invoke(main, ["template", "list", "--category", "minimal"])
        assert result.exit_code == 0

    def test_template_search_no_results(self, runner):
        result = runner.invoke(main, ["template", "search", "xyzzy_nonexistent"])
        assert result.exit_code == 0
        assert "No templates" in result.output

    def test_template_show_not_found(self, runner):
        result = runner.invoke(main, ["template", "show", "nonexistent.template"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_template_validate_no_templates(self, runner):
        result = runner.invoke(main, ["template", "validate"])
        assert result.exit_code == 0

    def test_template_help(self, runner):
        result = runner.invoke(main, ["template", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "show" in result.output
        assert "search" in result.output
        assert "validate" in result.output


class TestResolveUrnsCommand:
    """Tests for the resolve-urns CLI command."""

    @pytest.fixture
    def test_data_path(self):
        return Path(__file__).parent / "../../aces-amf-lib/tests/data"

    def test_resolve_urns_auto(self, runner, test_data_path, tmp_path):
        """--auto resolves all v1.5 CSC URNs to v2.0 equivalents."""
        src = test_data_path / "mixed_urns_with_equivalent_csc.amf"
        out = tmp_path / "resolved.amf"
        result = runner.invoke(main, ["resolve-urns", str(src), "--auto", "--output", str(out)])
        assert result.exit_code == 0
        assert "Resolved 2 URN(s)" in result.output
        # Verify the output file has v2.0 URNs
        amf = load_amf(out, validate=False)
        for lt in amf.pipeline.look_transforms:
            if lt.cdl_working_space:
                ws = lt.cdl_working_space
                if ws.to_cdl_working_space:
                    assert "v2.0" in ws.to_cdl_working_space.transform_id
                if ws.from_cdl_working_space:
                    assert "v2.0" in ws.from_cdl_working_space.transform_id

    def test_resolve_urns_explicit(self, runner, test_data_path, tmp_path):
        """--urn flag applies specific replacement."""
        src = test_data_path / "mixed_urns_with_equivalent_csc.amf"
        out = tmp_path / "resolved.amf"
        old_urn = "urn:ampas:aces:transformId:v1.5:ACEScsc.Academy.ACES_to_ACEScct.a1.0.3"
        new_urn = "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScct.a2.v1"
        result = runner.invoke(main, [
            "resolve-urns", str(src),
            "--urn", f"{old_urn}={new_urn}",
            "--output", str(out),
        ])
        assert result.exit_code == 0
        assert "Resolved 1 URN(s)" in result.output

    def test_resolve_urns_unresolvable(self, runner, test_data_path, tmp_path):
        """--auto on file with no-equivalent URN reports it."""
        src = test_data_path / "mixed_urns_no_equivalent_logc.amf"
        out = tmp_path / "resolved.amf"
        result = runner.invoke(main, ["resolve-urns", str(src), "--auto", "--output", str(out)])
        assert result.exit_code == 0
        assert "1 unresolved" in result.output
        assert "LogC_EI800_AWG" in result.output

    def test_resolve_urns_help(self, runner):
        result = runner.invoke(main, ["resolve-urns", "--help"])
        assert result.exit_code == 0
        assert "resolve-urns" in result.output.lower() or "Resolve" in result.output


ACESCCT_URNS = {
    (1, 3, 0): (
        "urn:ampas:aces:transformId:v1.5:ACEScsc.Academy.ACEScct_to_ACES.a1.0.3",
        "urn:ampas:aces:transformId:v1.5:ACEScsc.Academy.ACES_to_ACEScct.a1.0.3",
    ),
    (2, 0, 0): (
        "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACEScct_to_ACES.a2.v1",
        "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScct.a2.v1",
    ),
}

_PIPELINE_IDS = {
    (1, 3, 0): (
        "urn:ampas:aces:transformId:v1.5:IDT.ARRI.ARRI-LogC4.a1.v1",
        "urn:ampas:aces:transformId:v1.5:RRTODT.Academy.P3D65_1000nits_15nits_ST2084.a1.1.0",
    ),
    (2, 0, 0): (
        "urn:ampas:aces:transformId:v2.0:CSC.Arri.LogC4_to_ACES.a2.v1",
        "urn:ampas:aces:transformId:v2.0:Output.Academy.P3-D60_1000nit_in_P3-D65_ST2084.a2.v1",
    ),
}


def _amf_for_version(tmp_path, version):
    """Write a minimal, valid AMF for the given ACES version."""
    from aswf.aces.amf_utils import AMFBuilder

    idt, odt = _PIPELINE_IDS[version]
    path = tmp_path / f"base_{'_'.join(map(str, version))}.amf"
    amf = (
        AMFBuilder(aces_version=version)
        .with_description("CDL working space test")
        .with_author(AuthorType(name="Tester", email_address="test@example.com"))
        .with_input_transform(InputTransformType(transform_id=idt, applied=False))
        .with_output_transform(OutputTransformType(transform_id=odt, applied=False))
        .build()
    )
    save_amf(amf, path, validate=False)
    return path


@pytest.mark.parametrize("version", list(ACESCCT_URNS))
class TestAddCdlWorkingSpaceVersion:
    """add-cdl must emit an ACEScct working space valid for the AMF's ACES version (issue #29)."""

    def _add_cdl(self, runner, tmp_path, version):
        src = _amf_for_version(tmp_path, version)
        out = tmp_path / "out.amf"
        result = runner.invoke(main, ["add-cdl", str(src), "--slope", "1.1", "1.0", "0.9", "-o", str(out)])
        assert result.exit_code == 0, result.output
        return out

    def test_default_working_space_validates_cleanly(self, runner, tmp_path, version):
        from aswf.aces.amf_lib import ValidationLevel, ValidationType, validate_semantic
        from aswf.aces.transforms import ACESTransformRegistry

        out = self._add_cdl(runner, tmp_path, version)
        msgs = validate_semantic(out, transform_registry=ACESTransformRegistry())
        errors = [m.message for m in msgs if m.level == ValidationLevel.ERROR]
        mismatches = [m.message for m in msgs if m.validation_type == ValidationType.VERSION_MISMATCH_TRANSFORM_ID]
        assert not errors, errors
        assert not mismatches, mismatches

    def test_from_is_canonical_acescct_for_version(self, runner, tmp_path, version):
        out = self._add_cdl(runner, tmp_path, version)
        ws = load_amf(out, validate=False).pipeline.look_transforms[0].cdl_working_space
        assert ws.from_cdl_working_space.transform_id == ACESCCT_URNS[version][0]

    def test_to_is_inverse_of_from(self, runner, tmp_path, version):
        out = self._add_cdl(runner, tmp_path, version)
        ws = load_amf(out, validate=False).pipeline.look_transforms[0].cdl_working_space
        assert ws.to_cdl_working_space is not None
        assert ws.to_cdl_working_space.transform_id == ACESCCT_URNS[version][1]

    def test_validate_command_has_no_working_space_warning(self, runner, tmp_path, version):
        out = self._add_cdl(runner, tmp_path, version)
        result = runner.invoke(main, ["validate", str(out)])
        assert "CdlWorkingSpace" not in result.output, result.output


class TestAddCdlWorkingSpaceOption:
    LOGC4_IN = "urn:ampas:aces:transformId:v2.0:CSC.Arri.LogC4_to_ACES.a2.v1"
    LOGC4_OUT = "urn:ampas:aces:transformId:v2.0:CSC.Arri.ACES_to_LogC4.a2.v1"
    LOGC3_NO_INVERSE = "urn:ampas:aces:transformId:v2.0:CSC.Arri.LogC3_to_ACES.a2.v1"
    OUTPUT_TRANSFORM = _PIPELINE_IDS[(2, 0, 0)][1]

    def _run(self, runner, tmp_path, working_space, version=(2, 0, 0)):
        src = _amf_for_version(tmp_path, version)
        out = tmp_path / "out.amf"
        result = runner.invoke(main, ["add-cdl", str(src), "--working-space", working_space, "-o", str(out)])
        return result, out

    def test_non_default_pair(self, runner, tmp_path):
        result, out = self._run(runner, tmp_path, self.LOGC4_IN)
        assert result.exit_code == 0, result.output
        ws = load_amf(out, validate=False).pipeline.look_transforms[0].cdl_working_space
        assert ws.from_cdl_working_space.transform_id == self.LOGC4_IN
        assert ws.to_cdl_working_space.transform_id == self.LOGC4_OUT
        assert runner.invoke(main, ["validate", str(out)]).exit_code == 0

    def test_inverse_direction_accepted(self, runner, tmp_path):
        result, out = self._run(runner, tmp_path, self.LOGC4_OUT)
        assert result.exit_code == 0, result.output
        ws = load_amf(out, validate=False).pipeline.look_transforms[0].cdl_working_space
        assert ws.from_cdl_working_space.transform_id == self.LOGC4_IN

    @pytest.mark.parametrize("bad", [LOGC3_NO_INVERSE, OUTPUT_TRANSFORM])
    def test_invalid_working_space_rejected(self, runner, tmp_path, bad):
        result, out = self._run(runner, tmp_path, bad)
        assert result.exit_code != 0
        assert "working space" in result.output.lower()
        assert not out.exists()

    def test_previous_equivalent_resolved(self, runner, tmp_path):
        result, out = self._run(runner, tmp_path, ACESCCT_URNS[(1, 3, 0)][0])
        assert result.exit_code == 0, result.output
        assert "Resolved working space" in result.output
        ws = load_amf(out, validate=False).pipeline.look_transforms[0].cdl_working_space
        assert (ws.from_cdl_working_space.transform_id, ws.to_cdl_working_space.transform_id) == ACESCCT_URNS[(2, 0, 0)]

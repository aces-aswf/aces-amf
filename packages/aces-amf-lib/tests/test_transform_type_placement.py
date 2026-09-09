# SPDX-License-Identifier: Apache-2.0
"""
Tests verifying that misplaced transform URNs are caught.

Enforcement layers:
1. Semantic validation — TransformTypePlacementValidator reports misplacement
   errors when validating an AMF that has already been loaded into memory.
2. XSD schema validation — pattern facets on transformId catch misplacement
   when saving/loading XML.
"""

from aswf.aces.amf_lib import amf
from aswf.aces.amf_lib.validation.types import ValidationContext, ValidationLevel, ValidationType
from aswf.aces.amf_lib.validation.core_validators.transform_placement import TransformTypePlacementValidator
from aswf.aces.amf_utils.factories import minimal_amf


# -- Valid URNs for each container type --
VALID_IDT_URN = "urn:ampas:aces:transformId:v1.5:IDT.ARRI.ARRI-LogC4.a1.v1"
VALID_ODT_URN = "urn:ampas:aces:transformId:v1.5:RRTODT.Academy.Rec709_100nits_dim.a1.0.3"
VALID_LMT_URN = "urn:ampas:aces:transformId:v1.5:LMT.Academy.ACES_1.3_Filmic_Tone_Map.a1.0.3"
VALID_INPUT_V2_URN = "urn:ampas:aces:transformId:v2.0:Input.ARRI.LogC4.a1.v1"
VALID_OUTPUT_V2_URN = "urn:ampas:aces:transformId:v2.0:Output.Rec709.a1.v1"
VALID_LOOK_V2_URN = "urn:ampas:aces:transformId:v2.0:Look.ACME.FilmGrade.a1.v1"
VALID_CSC_V1_URN = "urn:ampas:aces:transformId:v1.5:ACEScsc.Academy.ACES_to_ACEScct.a1.0.3"
VALID_CSC_V2_URN = "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScct.a2.v1"


class TestCorrectPlacements:
    """Correct URN placements should not raise and should produce no validation errors."""

    def test_idt_in_input(self):
        it = amf.InputTransformType(transform_id=VALID_IDT_URN, applied=False)
        assert it.transform_id == VALID_IDT_URN

    def test_acescsc_in_input(self):
        it = amf.InputTransformType(transform_id=VALID_CSC_V1_URN, applied=False)
        assert it.transform_id == VALID_CSC_V1_URN

    def test_v2_input_in_input(self):
        it = amf.InputTransformType(transform_id=VALID_INPUT_V2_URN, applied=False)
        assert it.transform_id == VALID_INPUT_V2_URN

    def test_v2_csc_in_input(self):
        it = amf.InputTransformType(
            transform_id="urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScct.a2.v1",
            applied=False,
        )
        assert it.transform_id is not None

    def test_rrtodt_in_output(self):
        ot = amf.OutputTransformType(transform_id=VALID_ODT_URN, applied=False)
        assert ot.transform_id == VALID_ODT_URN

    def test_v2_output_in_output(self):
        ot = amf.OutputTransformType(transform_id=VALID_OUTPUT_V2_URN, applied=False)
        assert ot.transform_id == VALID_OUTPUT_V2_URN

    def test_lmt_in_look(self):
        lt = amf.LookTransformType(transform_id=VALID_LMT_URN, applied=True)
        assert lt.transform_id == VALID_LMT_URN

    def test_v2_look_in_look(self):
        lt = amf.LookTransformType(transform_id=VALID_LOOK_V2_URN, applied=True)
        assert lt.transform_id == VALID_LOOK_V2_URN

    def test_csc_in_working_space(self):
        ws = amf.WorkingSpaceTransformType(transform_id=VALID_CSC_V1_URN)
        assert ws.transform_id == VALID_CSC_V1_URN

    def test_v2_csc_in_working_space(self):
        ws = amf.WorkingSpaceTransformType(transform_id=VALID_CSC_V2_URN)
        assert ws.transform_id == VALID_CSC_V2_URN

    def test_none_transform_id_accepted(self):
        it = amf.InputTransformType(transform_id=None, applied=False)
        assert it.transform_id is None


class TestConstructionPermissive:
    """Direct construction with wrong URN prefix succeeds — errors surface through validation."""

    def test_odt_in_input_constructs(self):
        it = amf.InputTransformType(transform_id=VALID_ODT_URN, applied=False)
        assert it.transform_id == VALID_ODT_URN

    def test_idt_in_output_constructs(self):
        ot = amf.OutputTransformType(transform_id=VALID_IDT_URN, applied=False)
        assert ot.transform_id == VALID_IDT_URN

    def test_idt_in_look_constructs(self):
        lt = amf.LookTransformType(transform_id=VALID_IDT_URN, applied=True)
        assert lt.transform_id == VALID_IDT_URN

    def test_idt_in_working_space_constructs(self):
        ws = amf.WorkingSpaceTransformType(transform_id=VALID_IDT_URN)
        assert ws.transform_id == VALID_IDT_URN


# -- Helpers --


def _validate_amf(amf_obj):
    """Run the placement validator and return messages."""
    validator = TransformTypePlacementValidator()
    return validator.validate(amf_obj, ValidationContext())


def _make_amf_with_input(transform_id):
    amf_obj = minimal_amf()
    amf_obj.pipeline.input_transform = amf.InputTransformType(transform_id=transform_id, applied=False)
    return amf_obj


def _make_amf_with_output(transform_id):
    amf_obj = minimal_amf()
    amf_obj.pipeline.output_transform = amf.OutputTransformType(transform_id=transform_id, applied=False)
    return amf_obj


def _make_amf_with_look(transform_id):
    amf_obj = minimal_amf()
    amf_obj.pipeline.working_location_or_look_transform.append(
        amf.LookTransformType(transform_id=transform_id, applied=True)
    )
    return amf_obj


def _errors(msgs):
    return [m for m in msgs if m.level == ValidationLevel.ERROR]


# -- Semantic validator tests --


class TestPlacementValidator:
    """TransformTypePlacementValidator detects misplaced URNs at ERROR level."""

    # -- Input transform misplacements --

    def test_odt_in_input_flagged(self):
        errors = _errors(_validate_amf(_make_amf_with_input(VALID_ODT_URN)))
        assert len(errors) == 1
        assert errors[0].validation_type == ValidationType.INVALID_TRANSFORM_ID
        assert "not valid for" in errors[0].message

    def test_lmt_in_input_flagged(self):
        errors = _errors(_validate_amf(_make_amf_with_input(VALID_LMT_URN)))
        assert len(errors) == 1

    def test_v2_output_in_input_flagged(self):
        errors = _errors(_validate_amf(_make_amf_with_input(VALID_OUTPUT_V2_URN)))
        assert len(errors) == 1

    def test_v2_look_in_input_flagged(self):
        errors = _errors(_validate_amf(_make_amf_with_input(VALID_LOOK_V2_URN)))
        assert len(errors) == 1

    # -- Output transform misplacements --

    def test_idt_in_output_flagged(self):
        errors = _errors(_validate_amf(_make_amf_with_output(VALID_IDT_URN)))
        assert len(errors) == 1

    def test_lmt_in_output_flagged(self):
        errors = _errors(_validate_amf(_make_amf_with_output(VALID_LMT_URN)))
        assert len(errors) == 1

    def test_v2_input_in_output_flagged(self):
        errors = _errors(_validate_amf(_make_amf_with_output(VALID_INPUT_V2_URN)))
        assert len(errors) == 1

    # -- Look transform misplacements --

    def test_idt_in_look_flagged(self):
        errors = _errors(_validate_amf(_make_amf_with_look(VALID_IDT_URN)))
        assert len(errors) == 1

    def test_odt_in_look_flagged(self):
        errors = _errors(_validate_amf(_make_amf_with_look(VALID_ODT_URN)))
        assert len(errors) == 1

    def test_v2_output_in_look_flagged(self):
        errors = _errors(_validate_amf(_make_amf_with_look(VALID_OUTPUT_V2_URN)))
        assert len(errors) == 1

    def test_v2_input_in_look_flagged(self):
        errors = _errors(_validate_amf(_make_amf_with_look(VALID_INPUT_V2_URN)))
        assert len(errors) == 1

    # -- Valid placements produce no errors --

    def test_valid_input_no_errors(self):
        assert len(_errors(_validate_amf(_make_amf_with_input(VALID_IDT_URN)))) == 0

    def test_valid_output_no_errors(self):
        assert len(_errors(_validate_amf(_make_amf_with_output(VALID_ODT_URN)))) == 0

    def test_valid_look_no_errors(self):
        assert len(_errors(_validate_amf(_make_amf_with_look(VALID_LMT_URN)))) == 0

    def test_none_transform_id_no_errors(self):
        assert len(_errors(_validate_amf(_make_amf_with_input(None)))) == 0


class TestSubTransformPlacement:
    """Sub-transform misplacements produce ERROR."""

    def test_odt_in_reference_rendering_flagged(self):
        amf_obj = minimal_amf()
        odt_urn = "urn:ampas:aces:transformId:v1.5:ODT.Academy.Rec709_100nits_dim.a1.0.3"
        amf_obj.pipeline.output_transform = amf.OutputTransformType(
            transform_id=VALID_ODT_URN,
            applied=False,
            reference_rendering_transform=amf.ReferenceRenderingTransformType(
                transform_id=odt_urn,
                applied=False,
            ),
        )
        errors = _errors(_validate_amf(amf_obj))
        assert len(errors) == 1
        assert "not valid for" in errors[0].message

    def test_valid_rrt_in_reference_rendering_no_error(self):
        amf_obj = minimal_amf()
        rrt_urn = "urn:ampas:aces:transformId:v1.5:RRT.a1.0.3"
        amf_obj.pipeline.output_transform = amf.OutputTransformType(
            transform_id=VALID_ODT_URN,
            applied=False,
            reference_rendering_transform=amf.ReferenceRenderingTransformType(
                transform_id=rrt_urn,
                applied=False,
            ),
        )
        assert len(_errors(_validate_amf(amf_obj))) == 0


class TestPlacementValidatorWorkingSpace:
    """Working space transform placement checks."""

    def _make_amf_with_working_space(self, transform_id):
        amf_obj = minimal_amf()
        lt = amf.LookTransformType(
            transform_id=VALID_LMT_URN,
            applied=True,
            cdl_working_space=amf.CdlWorkingSpaceType(
                from_cdl_working_space=amf.WorkingSpaceTransformType(transform_id=transform_id),
                to_cdl_working_space=amf.WorkingSpaceTransformType(transform_id=transform_id),
            ),
        )
        amf_obj.pipeline.working_location_or_look_transform.append(lt)
        return amf_obj

    def test_idt_in_working_space_flagged(self):
        errors = _errors(_validate_amf(self._make_amf_with_working_space(VALID_IDT_URN)))
        assert len(errors) == 2  # both from and to

    def test_valid_csc_no_errors(self):
        assert len(_errors(_validate_amf(self._make_amf_with_working_space(VALID_CSC_V1_URN)))) == 0

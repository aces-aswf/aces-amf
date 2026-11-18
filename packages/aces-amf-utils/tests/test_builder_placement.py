# SPDX-License-Identifier: Apache-2.0
"""Tests verifying that the builder API rejects misplaced transform URNs."""

import pytest

from aswf.aces.amf_utils import AMFBuilder
from aswf.aces.amf_lib.amf import (
    CdlWorkingSpaceType,
    InputTransformType,
    InverseOutputDeviceTransformType,
    InverseOutputTransformType,
    InverseReferenceRenderingTransformType,
    LookTransformType,
    OutputDeviceTransformType,
    OutputTransformType,
    ReferenceRenderingTransformType,
    WorkingSpaceTransformType,
)

VALID_IDT_URN = "urn:ampas:aces:transformId:v1.5:IDT.ARRI.ARRI-LogC4.a1.v1"
VALID_ODT_URN = "urn:ampas:aces:transformId:v1.5:RRTODT.Academy.Rec709_100nits_dim.a1.0.3"
VALID_LMT_URN = "urn:ampas:aces:transformId:v1.5:LMT.Academy.ACES_1.3_Filmic_Tone_Map.a1.0.3"
VALID_OUTPUT_V2_URN = "urn:ampas:aces:transformId:v2.0:Output.Rec709.a1.v1"
VALID_INPUT_V2_URN = "urn:ampas:aces:transformId:v2.0:Input.ARRI.LogC4.a1.v1"
VALID_RRT_URN = "urn:ampas:aces:transformId:v1.5:RRT.a1.0.3"
VALID_OUTPUT_DEVICE_URN = "urn:ampas:aces:transformId:v1.5:ODT.Academy.Rec709_100nits_dim.a1.0.3"
VALID_INV_RRTODT_URN = "urn:ampas:aces:transformId:v1.5:InvRRTODT.Academy.Rec709_100nits_dim.a1.0.3"
VALID_INV_OUTPUT_V2_URN = "urn:ampas:aces:transformId:v2.0:InvOutput.Rec709.a1.v1"
VALID_INV_ODT_URN = "urn:ampas:aces:transformId:v1.5:InvODT.Academy.Rec709_100nits_dim.a1.0.3"
VALID_INV_RRT_URN = "urn:ampas:aces:transformId:v1.5:InvRRT.a1.0.3"
VALID_CSC_URN = "urn:ampas:aces:transformId:v1.5:ACEScsc.Academy.ACES_to_ACEScct.a1.0.3"
VALID_CSC_V2_URN = "urn:ampas:aces:transformId:v2.0:CSC.Academy.ACES_to_ACEScct.a2.v1"


class TestBuilderRejectsInputMisplacement:
    def test_odt_in_input_raises(self):
        with pytest.raises(ValueError, match="not valid for InputTransform"):
            AMFBuilder().with_input_transform(InputTransformType(transform_id=VALID_ODT_URN, applied=False))

    def test_lmt_in_input_raises(self):
        with pytest.raises(ValueError, match="not valid for InputTransform"):
            AMFBuilder().with_input_transform(InputTransformType(transform_id=VALID_LMT_URN, applied=False))

    def test_v2_output_in_input_raises(self):
        with pytest.raises(ValueError, match="not valid for InputTransform"):
            AMFBuilder().with_input_transform(InputTransformType(transform_id=VALID_OUTPUT_V2_URN, applied=False))

    def test_valid_input_accepted(self):
        builder = AMFBuilder().with_input_transform(InputTransformType(transform_id=VALID_IDT_URN, applied=False))
        assert builder.input_transform.transform_id == VALID_IDT_URN


class TestBuilderRejectsOutputMisplacement:
    def test_idt_in_output_raises(self):
        with pytest.raises(ValueError, match="not valid for OutputTransform"):
            AMFBuilder().with_output_transform(OutputTransformType(transform_id=VALID_IDT_URN, applied=False))

    def test_lmt_in_output_raises(self):
        with pytest.raises(ValueError, match="not valid for OutputTransform"):
            AMFBuilder().with_output_transform(OutputTransformType(transform_id=VALID_LMT_URN, applied=False))

    def test_valid_output_accepted(self):
        builder = AMFBuilder().with_output_transform(OutputTransformType(transform_id=VALID_ODT_URN, applied=False))
        assert builder.output_transform.transform_id == VALID_ODT_URN


class TestBuilderRejectsLookMisplacement:
    def test_idt_in_look_raises(self):
        with pytest.raises(ValueError, match="not valid for LookTransform"):
            AMFBuilder().with_look_transform(LookTransformType(transform_id=VALID_IDT_URN, applied=True))

    def test_odt_in_look_raises(self):
        with pytest.raises(ValueError, match="not valid for LookTransform"):
            AMFBuilder().with_look_transform(LookTransformType(transform_id=VALID_ODT_URN, applied=True))

    def test_valid_look_accepted(self):
        builder = AMFBuilder().with_look_transform(LookTransformType(transform_id=VALID_LMT_URN, applied=True))
        assert len(builder.get_looks()) == 1


class TestBuilderInsertLookMisplacement:
    def test_insert_idt_in_look_raises(self):
        with pytest.raises(ValueError, match="not valid for LookTransform"):
            AMFBuilder().insert_look(0, LookTransformType(transform_id=VALID_IDT_URN, applied=True))

    def test_insert_valid_look_accepted(self):
        builder = AMFBuilder().insert_look(0, LookTransformType(transform_id=VALID_LMT_URN, applied=True))
        assert len(builder.get_looks()) == 1


class TestBuilderPropertySetterMisplacement:
    def test_input_setter_rejects_odt(self):
        builder = AMFBuilder()
        with pytest.raises(ValueError, match="not valid for InputTransform"):
            builder.input_transform = InputTransformType(transform_id=VALID_ODT_URN, applied=False)

    def test_output_setter_rejects_idt(self):
        builder = AMFBuilder()
        with pytest.raises(ValueError, match="not valid for OutputTransform"):
            builder.output_transform = OutputTransformType(transform_id=VALID_IDT_URN, applied=False)

    def test_input_setter_accepts_none(self):
        builder = AMFBuilder()
        builder.input_transform = None
        assert builder.input_transform is None

    def test_output_setter_accepts_none(self):
        builder = AMFBuilder()
        builder.output_transform = None
        assert builder.output_transform is None


class TestBuilderRejectsNestedInputMisplacement:
    def test_non_inverse_output_in_inverse_output_transform_raises(self):
        with pytest.raises(ValueError, match="inverseOutputTransform"):
            AMFBuilder().with_input_transform(
                InputTransformType(
                    transform_id=VALID_IDT_URN,
                    applied=False,
                    inverse_output_transform=InverseOutputTransformType(transform_id=VALID_ODT_URN, applied=False),
                )
            )

    def test_inverse_output_transform_accepts_inv_rrtodt(self):
        builder = AMFBuilder().with_input_transform(
            InputTransformType(
                transform_id=VALID_IDT_URN,
                applied=False,
                inverse_output_transform=InverseOutputTransformType(transform_id=VALID_INV_RRTODT_URN, applied=False),
            )
        )
        assert builder.input_transform.inverse_output_transform.transform_id == VALID_INV_RRTODT_URN

    def test_inverse_output_transform_accepts_v2_inv_output(self):
        builder = AMFBuilder().with_input_transform(
            InputTransformType(
                transform_id=VALID_IDT_URN,
                applied=False,
                inverse_output_transform=InverseOutputTransformType(transform_id=VALID_INV_OUTPUT_V2_URN, applied=False),
            )
        )
        assert builder.input_transform.inverse_output_transform.transform_id == VALID_INV_OUTPUT_V2_URN

    def test_odt_in_inverse_output_device_transform_raises(self):
        with pytest.raises(ValueError, match="inverseOutputDeviceTransform"):
            AMFBuilder().with_input_transform(
                InputTransformType(
                    transform_id=VALID_IDT_URN,
                    applied=False,
                    inverse_output_device_transform=InverseOutputDeviceTransformType(
                        transform_id=VALID_OUTPUT_DEVICE_URN,
                        applied=False,
                    ),
                )
            )

    def test_inverse_output_device_transform_accepts_inv_odt(self):
        builder = AMFBuilder().with_input_transform(
            InputTransformType(
                transform_id=VALID_IDT_URN,
                applied=False,
                inverse_output_device_transform=InverseOutputDeviceTransformType(
                    transform_id=VALID_INV_ODT_URN,
                    applied=False,
                ),
            )
        )
        assert builder.input_transform.inverse_output_device_transform.transform_id == VALID_INV_ODT_URN

    def test_rrt_in_inverse_reference_rendering_transform_raises(self):
        with pytest.raises(ValueError, match="inverseReferenceRenderingTransform"):
            AMFBuilder().with_input_transform(
                InputTransformType(
                    transform_id=VALID_IDT_URN,
                    applied=False,
                    inverse_reference_rendering_transform=InverseReferenceRenderingTransformType(
                        transform_id=VALID_RRT_URN,
                        applied=False,
                    ),
                )
            )

    def test_inverse_reference_rendering_transform_accepts_inv_rrt(self):
        builder = AMFBuilder().with_input_transform(
            InputTransformType(
                transform_id=VALID_IDT_URN,
                applied=False,
                inverse_reference_rendering_transform=InverseReferenceRenderingTransformType(
                    transform_id=VALID_INV_RRT_URN,
                    applied=False,
                ),
            )
        )
        assert builder.input_transform.inverse_reference_rendering_transform.transform_id == VALID_INV_RRT_URN


class TestBuilderRejectsNestedOutputMisplacement:
    def test_odt_in_reference_rendering_transform_raises(self):
        with pytest.raises(ValueError, match="referenceRenderingTransform"):
            AMFBuilder().with_output_transform(
                OutputTransformType(
                    transform_id=VALID_ODT_URN,
                    applied=False,
                    reference_rendering_transform=ReferenceRenderingTransformType(
                        transform_id=VALID_OUTPUT_DEVICE_URN,
                        applied=False,
                    ),
                )
            )

    def test_reference_rendering_transform_accepts_rrt(self):
        builder = AMFBuilder().with_output_transform(
            OutputTransformType(
                transform_id=VALID_ODT_URN,
                applied=False,
                reference_rendering_transform=ReferenceRenderingTransformType(transform_id=VALID_RRT_URN, applied=False),
            )
        )
        assert builder.output_transform.reference_rendering_transform.transform_id == VALID_RRT_URN

    def test_rrt_in_output_device_transform_raises(self):
        with pytest.raises(ValueError, match="outputDeviceTransform"):
            AMFBuilder().with_output_transform(
                OutputTransformType(
                    transform_id=VALID_ODT_URN,
                    applied=False,
                    output_device_transform=OutputDeviceTransformType(transform_id=VALID_RRT_URN, applied=False),
                )
            )

    def test_output_device_transform_accepts_odt(self):
        builder = AMFBuilder().with_output_transform(
            OutputTransformType(
                transform_id=VALID_ODT_URN,
                applied=False,
                output_device_transform=OutputDeviceTransformType(transform_id=VALID_OUTPUT_DEVICE_URN, applied=False),
            )
        )
        assert builder.output_transform.output_device_transform.transform_id == VALID_OUTPUT_DEVICE_URN


class TestBuilderRejectsNestedLookMisplacement:
    def test_idt_in_from_cdl_working_space_raises(self):
        with pytest.raises(ValueError, match="fromCdlWorkingSpace"):
            AMFBuilder().with_look_transform(
                LookTransformType(
                    transform_id=VALID_LMT_URN,
                    applied=True,
                    cdl_working_space=CdlWorkingSpaceType(
                        from_cdl_working_space=WorkingSpaceTransformType(transform_id=VALID_IDT_URN),
                    ),
                )
            )

    def test_idt_in_to_cdl_working_space_raises(self):
        with pytest.raises(ValueError, match="toCdlWorkingSpace"):
            AMFBuilder().with_look_transform(
                LookTransformType(
                    transform_id=VALID_LMT_URN,
                    applied=True,
                    cdl_working_space=CdlWorkingSpaceType(
                        from_cdl_working_space=WorkingSpaceTransformType(transform_id=VALID_CSC_URN),
                        to_cdl_working_space=WorkingSpaceTransformType(transform_id=VALID_IDT_URN),
                    ),
                )
            )

    def test_cdl_working_space_accepts_csc_transforms(self):
        builder = AMFBuilder().with_look_transform(
            LookTransformType(
                transform_id=VALID_LMT_URN,
                applied=True,
                cdl_working_space=CdlWorkingSpaceType(
                    from_cdl_working_space=WorkingSpaceTransformType(transform_id=VALID_CSC_URN),
                    to_cdl_working_space=WorkingSpaceTransformType(transform_id=VALID_CSC_V2_URN),
                ),
            )
        )
        look = builder.get_look(0)
        assert look.cdl_working_space.from_cdl_working_space.transform_id == VALID_CSC_URN
        assert look.cdl_working_space.to_cdl_working_space.transform_id == VALID_CSC_V2_URN

    def test_insert_look_rejects_bad_cdl_working_space(self):
        with pytest.raises(ValueError, match="fromCdlWorkingSpace"):
            AMFBuilder().insert_look(
                0,
                LookTransformType(
                    transform_id=VALID_LMT_URN,
                    applied=True,
                    cdl_working_space=CdlWorkingSpaceType(
                        from_cdl_working_space=WorkingSpaceTransformType(transform_id=VALID_IDT_URN),
                    ),
                ),
            )

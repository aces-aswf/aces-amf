# SPDX-License-Identifier: Apache-2.0
"""Tests for CDL working-space construction in factories."""

import pytest

from aswf.aces.amf_lib import ValidationLevel, ValidationType, save_amf, validate_semantic
from aswf.aces.amf_utils.factories import cdl_look_transform, cdl_working_space, minimal_amf
from aswf.aces.transforms import ACESTransformRegistry

V1 = "urn:ampas:aces:transformId:v1.5:ACEScsc.Academy"
V2 = "urn:ampas:aces:transformId:v2.0:CSC"

ACESCCT = {
    (1, 3, 0): (f"{V1}.ACEScct_to_ACES.a1.0.3", f"{V1}.ACES_to_ACEScct.a1.0.3"),
    (1, 3, 1): (f"{V1}.ACEScct_to_ACES.a1.0.3", f"{V1}.ACES_to_ACEScct.a1.0.3"),
    (2, 0, 0): (f"{V2}.Academy.ACEScct_to_ACES.a2.v1", f"{V2}.Academy.ACES_to_ACEScct.a2.v1"),
}
LOGC4_IN = f"{V2}.Arri.LogC4_to_ACES.a2.v1"
LOGC4_OUT = f"{V2}.Arri.ACES_to_LogC4.a2.v1"
BMD_OUT = f"{V2}.Academy.ACES_to_BMDFilm_WideGamut_Gen5.a2.v1"
BMD_IN = f"{V2}.Blackmagic.BMDFilm_WideGamut_Gen5_to_ACES.a2.v1"
LOGC3_NO_INVERSE = f"{V2}.Arri.LogC3_to_ACES.a2.v1"
OUTPUT_TRANSFORM = "urn:ampas:aces:transformId:v2.0:Output.Academy.P3-D60_1000nit_in_P3-D65_ST2084.a2.v1"


@pytest.fixture(scope="module")
def registry():
    return ACESTransformRegistry()


def _ids(ws):
    return ws.from_cdl_working_space.transform_id, ws.to_cdl_working_space.transform_id


class TestDefaultWorkingSpace:
    @pytest.mark.parametrize("version", list(ACESCCT))
    def test_acescct_for_version(self, registry, version):
        from_id, to_id = _ids(cdl_working_space(version, registry=registry))
        assert (from_id, to_id) == ACESCCT[version]
        assert registry.are_transforms_inverses(from_id, to_id, version=f"v{version[0]}.{version[1]}")

    def test_no_version_defaults_to_2_0(self, registry):
        assert _ids(cdl_working_space(registry=registry)) == ACESCCT[(2, 0, 0)]
        assert _ids(cdl_look_transform(registry=registry).cdl_working_space) == ACESCCT[(2, 0, 0)]

    def test_unsupported_version(self, registry):
        with pytest.raises(ValueError, match="No ACEScct"):
            cdl_working_space((9, 0, 0), registry=registry)


class TestExplicitWorkingSpace:
    def test_forward_direction(self, registry):
        assert _ids(cdl_working_space((2, 0, 0), LOGC4_IN, registry)) == (LOGC4_IN, LOGC4_OUT)

    def test_inverse_direction_gives_same_pair(self, registry):
        assert _ids(cdl_working_space((2, 0, 0), LOGC4_OUT, registry)) == (LOGC4_IN, LOGC4_OUT)

    def test_cross_namespace_pair(self, registry):
        assert _ids(cdl_working_space((2, 0, 0), BMD_OUT, registry)) == (BMD_IN, BMD_OUT)

    def test_previous_equivalent_resolves_to_canonical(self, registry):
        assert _ids(cdl_working_space((2, 0, 0), ACESCCT[(1, 3, 0)][0], registry)) == ACESCCT[(2, 0, 0)]

    def test_no_inverse_rejected(self, registry):
        with pytest.raises(ValueError, match="no inverse"):
            cdl_working_space((2, 0, 0), LOGC3_NO_INVERSE, registry)

    def test_non_csc_rejected(self, registry):
        with pytest.raises(ValueError, match="Not a CSC"):
            cdl_working_space((2, 0, 0), OUTPUT_TRANSFORM, registry)

    def test_unknown_rejected(self, registry):
        with pytest.raises(ValueError, match="Unknown transform"):
            cdl_working_space((2, 0, 0), f"{V2}.Academy.Nope_to_ACES.a2.v1", registry)


@pytest.mark.parametrize("version,working_space", [
    ((1, 3, 0), None),
    ((1, 3, 1), None),
    ((2, 0, 0), None),
    ((2, 0, 0), LOGC4_IN),
    ((2, 0, 0), BMD_OUT),
])
def test_result_validates_in_pipeline(registry, tmp_path, version, working_space):
    amf = minimal_amf(aces_version=version)
    amf.pipeline.working_location_or_look_transform.append(
        cdl_look_transform(aces_version=version, working_space=working_space, registry=registry)
    )
    path = tmp_path / "cdl.amf"
    save_amf(amf, path, validate=False)
    msgs = validate_semantic(path, transform_registry=registry)
    bad = [
        m.message for m in msgs
        if m.level == ValidationLevel.ERROR
        or m.validation_type in (ValidationType.VERSION_MISMATCH_TRANSFORM_ID, ValidationType.CDL_WORKING_SPACE_MISMATCH)
    ]
    assert not bad, bad

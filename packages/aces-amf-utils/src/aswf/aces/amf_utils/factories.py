# SPDX-License-Identifier: Apache-2.0
"""
Authoring factories for constructing AMF objects.

These functions create new AMF model instances and are intentionally
located in aswf-aces-amf-utils (not aswf-aces-amf-lib) because they are authoring
helpers, not core I/O operations.
"""

import uuid

from aswf.aces.amf_lib import amf
from aswf.aces.amf_lib.amf_helpers import amf_date_time_now, amf_xml_date_time

FloatVector = tuple[float, float, float]


def minimal_amf(aces_version: tuple[int, int, int] = (1, 3, 0)) -> amf.AcesMetadataFile:
    """Create a minimal AMF with required fields populated."""
    version_type = amf.VersionType(
        major_version=aces_version[0], minor_version=aces_version[1], patch_version=aces_version[2]
    )
    pipeline_info = amf.PipelineInfoType(
        date_time=amf_date_time_now(), uuid=uuid.uuid4().urn, system_version=version_type
    )
    return amf.AcesMetadataFile(
        amf_info=amf.InfoType(date_time=amf_date_time_now(), uuid=uuid.uuid4().urn),
        pipeline=amf.PipelineType(pipeline_info=pipeline_info),
    )


def cdl_look_transform(
    *, slope: FloatVector = None, offset: FloatVector = None, power: FloatVector = None, saturation: float = None
) -> amf.LookTransformType:
    """Create a CDL look transform from the provided parameters."""
    if slope is None:
        slope = (1.0, 1.0, 1.0)
    if offset is None:
        offset = (0.0, 0.0, 0.0)
    if power is None:
        power = (1.0, 1.0, 1.0)
    if saturation is None:
        saturation = 1.0

    if len(slope) != 3 or len(offset) != 3 or len(power) != 3:
        raise ValueError("Slope, offset, and power must be 3 element tuples")

    working_space = amf.CdlWorkingSpaceType(
        from_cdl_working_space=amf.WorkingSpaceTransformType(
            transform_id="urn:ampas:aces:transformId:v1.5:ACEScsc.Academy.ACEScct_to_ACES.a1.0.3"
        ),
    )
    sop_node = amf.AscSop(slope=list(slope), offset=list(offset), power=list(power))
    sat_node = amf.AscSat(saturation=saturation)
    return amf.LookTransformType(cdl_working_space=working_space, asc_sop=sop_node, asc_sat=sat_node, applied=False)


def cdl_look_transform_to_dict(look_transform: amf.LookTransformType) -> dict:
    """Extract CDL values from a look transform as a plain dict.

    Returns:
        Dict with ``asc_sop`` (slope/offset/power lists) and ``asc_sat`` (float).

    Raises:
        ValueError: If the look transform has no ASC SOP node.
    """
    if look_transform.asc_sop is None:
        raise ValueError("Missing ASC SOP node in CDL look transform")

    asc_cdl = {
        "asc_sop": {
            "slope": look_transform.asc_sop.slope or [1.0, 1.0, 1.0],
            "offset": look_transform.asc_sop.offset or [0.0, 0.0, 0.0],
            "power": look_transform.asc_sop.power or [1.0, 1.0, 1.0],
        },
        "asc_sat": 1.0,
    }
    if look_transform.asc_sat is not None and look_transform.asc_sat.saturation is not None:
        asc_cdl["asc_sat"] = look_transform.asc_sat.saturation

    return asc_cdl


def prepare_for_write(amf_obj: amf.AcesMetadataFile) -> None:
    """Update modification timestamps and regenerate UUIDs.

    Called automatically by ``save_amf`` and ``render_amf``.
    Can also be called manually before low-level ``dump_amf``/``write_amf``.
    """
    now = amf_xml_date_time()
    if amf_obj.amf_info:
        amf_obj.amf_info.date_time.modification_date_time = now
        amf_obj.amf_info.uuid = uuid.uuid4().urn
    if amf_obj.pipeline and amf_obj.pipeline.pipeline_info:
        amf_obj.pipeline.pipeline_info.date_time.modification_date_time = now
        amf_obj.pipeline.pipeline_info.uuid = uuid.uuid4().urn
    for archived in amf_obj.archived_pipeline:
        if archived.pipeline_info and archived.pipeline_info.date_time:
            archived.pipeline_info.date_time.modification_date_time = now

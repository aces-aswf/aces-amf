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
from aswf.aces.common.types import TransformURN

FloatVector = tuple[float, float, float]


def minimal_amf(aces_version: tuple[int, int, int] = (2, 0, 0)) -> amf.AcesMetadataFile:
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


_CSC_TYPES = {"CSC", "ACEScsc"}
_DEFAULT_WORKING_SPACE_NAME = "ACEScct_to_ACES"


def cdl_working_space(
    aces_version: tuple[int, int, int] = (2, 0, 0), working_space: str | None = None, registry=None
) -> amf.CdlWorkingSpaceType:
    """Build a CDL working space (from/to pair) valid for the given ACES version.

    Args:
        aces_version: ACES system version of the AMF. Selects the registry version scope.
        working_space: Any CSC transform URN, in either direction. The inverse is read from
            the registry so the pair is always forward/inverse. Defaults to ACEScct.
            A URN that is a previous equivalent in this version is resolved to its canonical ID.
        registry: Transform registry. Defaults to ACESTransformRegistry.

    Raises:
        ValueError: If the transform is unknown for this version, is not a CSC transform,
            or has no inverse.
    """
    if registry is None:
        from aswf.aces.transforms import ACESTransformRegistry

        registry = ACESTransformRegistry()

    version = f"v{aces_version[0]}.{aces_version[1]}"

    if working_space is None:
        seed = _default_acescct_id(registry, version)
        info = registry.get_transform_info(seed, version=version)
    else:
        info = registry.get_transform_info(working_space, version=version)
        if info is None:
            raise ValueError(f"Unknown transform for ACES {version}: {working_space}")

    seed = info["transform_id"]
    parsed = TransformURN.parse(seed)
    if parsed is None or parsed.transform_type not in _CSC_TYPES:
        raise ValueError(f"Not a CSC transform, cannot be used as a CDL working space: {seed}")

    inverse = info.get("inverse_transform_id")
    inverse_info = registry.get_transform_info(inverse, version=version) if inverse else None
    if not inverse_info or not (
        inverse == inverse_info["transform_id"]
        or inverse_info.get("inverse_transform_id") == seed
    ):
        raise ValueError(f"Transform has no inverse for ACES {version}, cannot be used as a CDL working space: {seed}")

    if parsed.name.endswith("_to_ACES"):
        from_id, to_id = seed, inverse
    elif parsed.name.startswith("ACES_to_"):
        from_id, to_id = inverse, seed
    else:
        raise ValueError(f"Cannot determine direction of CSC transform: {seed}")

    return amf.CdlWorkingSpaceType(
        from_cdl_working_space=amf.WorkingSpaceTransformType(transform_id=from_id),
        to_cdl_working_space=amf.WorkingSpaceTransformType(transform_id=to_id),
    )


def _default_acescct_id(registry, version: str) -> str:
    for info in registry.list_transforms(version=version):
        parsed = TransformURN.parse(info["transform_id"])
        if (
            parsed is not None
            and parsed.transform_type in _CSC_TYPES
            and parsed.namespace == "Academy"
            and parsed.name == _DEFAULT_WORKING_SPACE_NAME
        ):
            return info["transform_id"]
    raise ValueError(f"No ACEScct working-space transform in registry for ACES {version}")


def cdl_look_transform(
    *,
    slope: FloatVector = None,
    offset: FloatVector = None,
    power: FloatVector = None,
    saturation: float = None,
    aces_version: tuple[int, int, int] = (2, 0, 0),
    working_space: str | None = None,
    registry=None,
) -> amf.LookTransformType:
    """Create a CDL look transform from the provided parameters.

    The CDL working space defaults to ACEScct, using the transform IDs for ``aces_version``
    (default ACES 2.0). Pass ``working_space`` (a CSC URN, either direction) to use another
    CSC; see :func:`cdl_working_space`.
    """
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

    cdl_ws = cdl_working_space(aces_version, working_space, registry)
    sop_node = amf.AscSop(slope=list(slope), offset=list(offset), power=list(power))
    sat_node = amf.AscSat(saturation=saturation)
    return amf.LookTransformType(cdl_working_space=cdl_ws, asc_sop=sop_node, asc_sat=sat_node, applied=False)


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

# SPDX-License-Identifier: Apache-2.0
"""
AMF file comparison.

Provides programmatic comparison of two AMF files, returning structured
difference results that can be consumed by CLI or other tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aswf.aces.amf_lib import AcesMetadataFile, load_amf
from aswf.aces.amf_utils.factories import cdl_look_transform_to_dict


def _get_description(amf: AcesMetadataFile) -> str | None:
    return amf.amf_info.description if amf.amf_info else None


def _get_pipeline_description(amf: AcesMetadataFile) -> str | None:
    if amf.pipeline and amf.pipeline.pipeline_info:
        return amf.pipeline.pipeline_info.description
    return None


def _get_aces_version(amf: AcesMetadataFile) -> tuple[int, int, int] | None:
    if amf.pipeline and amf.pipeline.pipeline_info and amf.pipeline.pipeline_info.system_version:
        sv = amf.pipeline.pipeline_info.system_version
        try:
            return (int(sv.major_version), int(sv.minor_version), int(sv.patch_version))
        except (TypeError, ValueError):
            return None
    return None


def _get_authors(amf: AcesMetadataFile) -> list:
    return amf.amf_info.author if amf.amf_info else []


@dataclass
class FieldDiff:
    """A single field difference."""

    field: str
    old_value: Any
    new_value: Any


@dataclass
class DiffResult:
    """Result of comparing two AMF files."""

    amf1_path: Path | None = None
    amf2_path: Path | None = None
    differences: list[FieldDiff] = field(default_factory=list)

    @property
    def has_differences(self) -> bool:
        return len(self.differences) > 0

    def summary(self) -> str:
        if not self.has_differences:
            return "Files are identical"
        lines = [f"{len(self.differences)} difference(s) found:"]
        for d in self.differences:
            lines.append(f"  {d.field}:")
            lines.append(f"    - {d.old_value}")
            lines.append(f"    + {d.new_value}")
        return "\n".join(lines)


def diff_amf(
    amf1: AcesMetadataFile | Path | str,
    amf2: AcesMetadataFile | Path | str,
    *,
    verbose: bool = False,
) -> DiffResult:
    """Compare two AMF files or objects.

    Args:
        amf1: First AMF (path or object).
        amf2: Second AMF (path or object).
        verbose: Include detailed per-transform comparison.

    Returns:
        DiffResult with list of differences.
    """
    if isinstance(amf1, (str, Path)):
        path1 = Path(amf1)
        amf1 = load_amf(path1, validate=False)
    else:
        path1 = None

    if isinstance(amf2, (str, Path)):
        path2 = Path(amf2)
        amf2 = load_amf(path2, validate=False)
    else:
        path2 = None

    result = DiffResult(amf1_path=path1, amf2_path=path2)

    # Description
    desc1, desc2 = _get_description(amf1), _get_description(amf2)
    if desc1 != desc2:
        result.differences.append(FieldDiff("amf_description", desc1, desc2))

    # Pipeline description
    pdesc1, pdesc2 = _get_pipeline_description(amf1), _get_pipeline_description(amf2)
    if pdesc1 != pdesc2:
        result.differences.append(FieldDiff("pipeline_description", pdesc1, pdesc2))

    # ACES version
    ver1, ver2 = _get_aces_version(amf1), _get_aces_version(amf2)
    if ver1 != ver2:
        result.differences.append(FieldDiff("aces_version", ver1, ver2))

    # Authors
    authors1 = [(a.name, a.email_address) for a in _get_authors(amf1)]
    authors2 = [(a.name, a.email_address) for a in _get_authors(amf2)]
    if authors1 != authors2:
        result.differences.append(FieldDiff("authors", authors1, authors2))

    # Input transform
    it1 = amf1.pipeline.input_transform if amf1.pipeline else None
    it2 = amf2.pipeline.input_transform if amf2.pipeline else None
    _compare_transforms(result, "input_transform", it1, it2, verbose)

    # Look transforms
    lt1 = amf1.pipeline.look_transforms if amf1.pipeline else []
    lt2 = amf2.pipeline.look_transforms if amf2.pipeline else []
    if len(lt1) != len(lt2):
        result.differences.append(FieldDiff("look_transform_count", len(lt1), len(lt2)))

    if verbose:
        for i in range(min(len(lt1), len(lt2))):
            _compare_look_transforms(result, i, lt1[i], lt2[i])

    # Output transform
    ot1 = amf1.pipeline.output_transform if amf1.pipeline else None
    ot2 = amf2.pipeline.output_transform if amf2.pipeline else None
    _compare_transforms(result, "output_transform", ot1, ot2, verbose)

    return result


def _compare_transforms(result: DiffResult, name: str, t1, t2, verbose: bool):
    has1 = t1 is not None
    has2 = t2 is not None
    if has1 != has2:
        result.differences.append(
            FieldDiff(f"{name}.present", has1, has2)
        )
    elif verbose and has1 and has2:
        if getattr(t1, "transform_id", None) != getattr(t2, "transform_id", None):
            result.differences.append(
                FieldDiff(f"{name}.transform_id", t1.transform_id, t2.transform_id)
            )
        if getattr(t1, "description", None) != getattr(t2, "description", None):
            result.differences.append(
                FieldDiff(f"{name}.description", t1.description, t2.description)
            )


def _compare_look_transforms(result: DiffResult, idx: int, lt1, lt2):
    prefix = f"look_transform[{idx}]"

    if lt1.description != lt2.description:
        result.differences.append(
            FieldDiff(f"{prefix}.description", lt1.description, lt2.description)
        )
    if lt1.applied != lt2.applied:
        result.differences.append(
            FieldDiff(f"{prefix}.applied", lt1.applied, lt2.applied)
        )
    if getattr(lt1, "transform_id", None) != getattr(lt2, "transform_id", None):
        result.differences.append(
            FieldDiff(f"{prefix}.transform_id", lt1.transform_id, lt2.transform_id)
        )

    # Compare CDL values
    if lt1.asc_sop or lt2.asc_sop:
        try:
            cdl1 = cdl_look_transform_to_dict(lt1) if lt1.asc_sop else None
            cdl2 = cdl_look_transform_to_dict(lt2) if lt2.asc_sop else None
            if cdl1 != cdl2:
                result.differences.append(
                    FieldDiff(f"{prefix}.cdl", cdl1, cdl2)
                )
        except (ValueError, AttributeError):
            pass

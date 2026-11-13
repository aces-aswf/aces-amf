# SPDX-License-Identifier: Apache-2.0
"""
Bulk AMF file generation.

Generate IDT x ODT test matrices and template-based matrix generation.
"""

from __future__ import annotations

import itertools
import logging
import re
from pathlib import Path
from typing import Any

from aswf.aces.amf_lib import amf, save_amf
from aswf.aces.amf_utils.factories import minimal_amf
from aswf.aces.common.constants import INPUT_TRANSFORM_TYPES, OUTPUT_TRANSFORM_TYPES
from aswf.aces.transforms import ACESTransformRegistry

from aswf.aces.amf_utils.template_registry import REGISTRY

logger = logging.getLogger(__name__)



def generate_test_matrix(
    output_dir: Path,
    aces_version: tuple[int, int, int] = (2, 0, 0),
    *,
    idt_filter: str | None = None,
    odt_filter: str | None = None,
    max_combinations: int | None = None,
    author_name: str = "Test Matrix Generator",
    author_email: str = "test@example.com",
) -> list[Path]:
    """Generate a matrix of AMF files for all IDT x ODT combinations.

    Args:
        output_dir: Directory to write generated files.
        aces_version: ACES version to use.
        idt_filter: Filter IDTs by keyword in user_name.
        odt_filter: Filter ODTs by keyword in user_name.
        max_combinations: Maximum number of files to generate.
        author_name: Author name for generated files.
        author_email: Author email for generated files.

    Returns:
        List of paths to generated files.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    registry = ACESTransformRegistry()
    transforms = registry.list_transforms()

    # Split into IDTs and ODTs
    idts = [t for t in transforms if t["transform_type"] in INPUT_TRANSFORM_TYPES]
    odts = [t for t in transforms if t["transform_type"] in OUTPUT_TRANSFORM_TYPES]

    # Apply filters
    if idt_filter:
        filter_lower = idt_filter.lower()
        idts = [t for t in idts if filter_lower in t.get("user_name", "").lower()]

    if odt_filter:
        filter_lower = odt_filter.lower()
        odts = [t for t in odts if filter_lower in t.get("user_name", "").lower()]

    generated: list[Path] = []
    count = 0

    for idt, odt in itertools.product(idts, odts):
        if max_combinations and count >= max_combinations:
            break

        amf_obj = minimal_amf(aces_version=aces_version)
        amf_obj.amf_info.description = f"Test matrix: {idt['user_name']} -> {odt['user_name']}"
        amf_obj.amf_info.author.append(amf.AuthorType(name=author_name, email_address=author_email))

        amf_obj.pipeline.input_transform = amf.InputTransformType(
            applied=False,
            transform_id=idt["transform_id"],
            description=idt.get("user_name", ""),
        )

        amf_obj.pipeline.output_transform = amf.OutputTransformType(
            applied=False,
            transform_id=odt["transform_id"],
            description=odt.get("user_name", ""),
        )

        count += 1
        idt_safe = _safe_filename(idt["user_name"])
        odt_safe = _safe_filename(odt["user_name"])
        out_path = output_dir / f"matrix_{count:04d}_{idt_safe}_to_{odt_safe}.amf"

        save_amf(amf_obj, out_path)
        generated.append(out_path)
        logger.debug("Generated %s", out_path.name)

    logger.info("Generated %d AMF files in %s", len(generated), output_dir)
    return generated


def generate_from_template_matrix(
    output_dir: Path,
    template_id: str,
    parameter_grid: dict[str, list[Any]],
    *,
    max_combinations: int | None = None,
) -> list[Path]:
    """Generate AMF files from a template with all parameter combinations.

    Args:
        output_dir: Directory to write generated files.
        template_id: Template ID to use.
        parameter_grid: Dict mapping parameter names to lists of values.
        max_combinations: Maximum number of files to generate.

    Returns:
        List of paths to generated files.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    param_names = list(parameter_grid.keys())
    param_values = list(parameter_grid.values())

    generated: list[Path] = []
    count = 0

    for combo in itertools.product(*param_values):
        if max_combinations and count >= max_combinations:
            break

        params = dict(zip(param_names, combo))

        try:
            amf_obj = REGISTRY.generate(template_id, **params)
        except (KeyError, ValueError) as e:
            logger.warning("Failed to generate template %s with params %s: %s", template_id, params, e)
            continue

        count += 1
        out_path = output_dir / f"{template_id}_{count:04d}.amf"
        save_amf(amf_obj, out_path)
        generated.append(out_path)

    logger.info("Generated %d AMF files from template %s", len(generated), template_id)
    return generated


def _safe_filename(name: str, max_length: int = 50) -> str:
    """Convert a string to a safe filename component."""
    safe = re.sub(r"[^\w\-.]", "_", name)
    safe = re.sub(r"_+", "_", safe)
    safe = safe.strip("_.")
    return safe[:max_length]

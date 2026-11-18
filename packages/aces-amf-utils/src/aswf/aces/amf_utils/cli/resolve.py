# SPDX-License-Identifier: Apache-2.0
"""Resolve version-mismatched transform URNs in AMF files."""

from __future__ import annotations

from pathlib import Path

import click

from aswf.aces.common.types import TransformURN
from aswf.aces.amf_lib import load_amf, save_amf


def _collect_transform_refs(pipeline):
    """Yield (label, obj, attr_name) for every transform ID slot in a pipeline.

    Each yielded tuple lets the caller read and mutate the transform_id:
        label: human-readable description
        obj: the object holding the transform_id attribute
        attr_name: always "transform_id"
    """
    from aswf.aces.amf_lib.validation import collect_sub_transforms

    if pipeline.input_transform:
        if pipeline.input_transform.transform_id:
            yield "Input transform", pipeline.input_transform, "transform_id"
        for sub_label, sub in collect_sub_transforms(pipeline.input_transform, "Input"):
            if sub.transform_id:
                yield sub_label, sub, "transform_id"

    for idx, lt in enumerate(pipeline.look_transforms):
        if lt.transform_id:
            desc = lt.description or f"Look transform #{idx + 1}"
            yield desc, lt, "transform_id"
        if lt.cdl_working_space:
            ws = lt.cdl_working_space
            if ws.from_cdl_working_space and ws.from_cdl_working_space.transform_id:
                yield f"Look #{idx+1} fromCdlWorkingSpace", ws.from_cdl_working_space, "transform_id"
            if ws.to_cdl_working_space and ws.to_cdl_working_space.transform_id:
                yield f"Look #{idx+1} toCdlWorkingSpace", ws.to_cdl_working_space, "transform_id"

    if pipeline.output_transform:
        if pipeline.output_transform.transform_id:
            yield "Output transform", pipeline.output_transform, "transform_id"
        for sub_label, sub in collect_sub_transforms(pipeline.output_transform, "Output"):
            if sub.transform_id:
                yield sub_label, sub, "transform_id"


@click.command("resolve-urns")
@click.argument("file", type=click.Path(exists=True))
@click.option("--auto", "auto_resolve", is_flag=True, help="Automatically resolve all mismatched URNs that have equivalents.")
@click.option("--urn", "urn_mappings", multiple=True, metavar="OLD=NEW", help="Explicit URN replacement. Repeatable.")
@click.option("--output", "-o", "output_path", type=click.Path(), help="Write resolved AMF to this path.")
@click.option("--in-place", is_flag=True, help="Overwrite the input file.")
@click.pass_context
def resolve_urns(ctx, file, auto_resolve, urn_mappings, output_path, in_place):
    """Resolve version-mismatched transform URNs in an AMF file.

    Scans for transform IDs whose ACES version doesn't match the AMF's
    declared system version, and replaces them with their equivalents.

    In interactive mode (default), prompts for each mismatch.
    Use --auto to resolve all automatically, or --urn OLD=NEW for explicit mappings.
    """
    registry = ctx.obj.get("transform_registry") if ctx.obj else None
    if registry is None:
        raise click.ClickException("No transform registry available.")

    if in_place and output_path:
        raise click.ClickException("Cannot use both --in-place and --output.")

    # Parse explicit mappings
    explicit_map: dict[str, str] = {}
    for mapping in urn_mappings:
        if "=" not in mapping:
            raise click.ClickException(f"Invalid --urn format: {mapping!r}. Expected OLD=NEW.")
        old, new = mapping.split("=", 1)
        explicit_map[old] = new

    path = Path(file)
    amf = load_amf(path, validate=False)

    if not amf.pipeline:
        click.echo("No pipeline found in AMF.")
        return

    # Get system version
    sv = getattr(getattr(amf.pipeline, "pipeline_info", None), "system_version", None)
    if sv is None:
        click.echo("No system version found in AMF pipeline.")
        return
    sys_major = sv.major_version
    version_str = f"v{sv.major_version}.{sv.minor_version}"

    replaced = 0
    unresolved = 0

    for label, obj, attr in _collect_transform_refs(amf.pipeline):
        transform_id = getattr(obj, attr)
        parsed = TransformURN.parse(transform_id)
        if not parsed or parsed.spec_major_version == sys_major:
            continue

        # This URN has a version mismatch
        if explicit_map:
            # Explicit mode: only replace if in the map
            if transform_id in explicit_map:
                new_id = explicit_map[transform_id]
                click.echo(f"  {label}: {transform_id} -> {new_id}")
                setattr(obj, attr, new_id)
                replaced += 1
            continue

        # Look up equivalent
        current_id = registry.get_equivalent_id(transform_id)
        equivalent = current_id if current_id and current_id != transform_id else None

        if auto_resolve:
            if equivalent:
                click.echo(f"  {label}: {transform_id} -> {equivalent}")
                setattr(obj, attr, equivalent)
                replaced += 1
            else:
                click.echo(click.style(
                    f"  {label}: {transform_id} (ACES {parsed.spec_version}) — no equivalent for ACES {version_str}",
                    fg="red",
                ))
                unresolved += 1
        else:
            # Interactive mode
            click.echo(f"\n  {label}")
            click.echo(f"    Current: {transform_id} (ACES {parsed.spec_version})")
            if equivalent:
                click.echo(f"    Equivalent: {equivalent}")
                choice = click.prompt(
                    "    Replace with equivalent?",
                    type=click.Choice(["y", "n", "custom"]),
                    default="y",
                )
                if choice == "y":
                    setattr(obj, attr, equivalent)
                    replaced += 1
                elif choice == "custom":
                    custom = click.prompt("    Enter replacement URN")
                    setattr(obj, attr, custom)
                    replaced += 1
            else:
                click.echo(click.style(f"    No equivalent for ACES {version_str}", fg="red"))
                choice = click.prompt(
                    "    Enter replacement URN or skip?",
                    type=click.Choice(["skip", "custom"]),
                    default="skip",
                )
                if choice == "custom":
                    custom = click.prompt("    Enter replacement URN")
                    setattr(obj, attr, custom)
                    replaced += 1
                else:
                    unresolved += 1

    # Summary
    click.echo(f"\nResolved {replaced} URN(s).", nl=False)
    if unresolved:
        click.echo(click.style(f" {unresolved} unresolved.", fg="red"))
    else:
        click.echo()

    # Save
    if replaced > 0:
        if in_place:
            save_amf(amf, path, transform_registry=registry)
            click.echo(f"Saved: {path}")
        elif output_path:
            save_amf(amf, Path(output_path), transform_registry=registry)
            click.echo(f"Saved: {output_path}")
        elif not explicit_map and not auto_resolve:
            # Interactive mode without --output: ask
            if click.confirm("Save changes?", default=False):
                dest = click.prompt("Output path", default=str(path))
                save_amf(amf, Path(dest), transform_registry=registry)
                click.echo(f"Saved: {dest}")
        else:
            click.echo("Use --output or --in-place to save changes.")

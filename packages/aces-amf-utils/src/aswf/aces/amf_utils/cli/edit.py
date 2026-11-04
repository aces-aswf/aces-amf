# SPDX-License-Identifier: Apache-2.0
"""Edit commands: add-cdl, compute-hashes."""

import hashlib
from pathlib import Path

import click

from aswf.aces.amf_utils.aces_amf import ACESAMF
from aswf.aces.amf_utils.factories import cdl_look_transform


@click.command("add-cdl")
@click.argument("file", type=click.Path(exists=True))
@click.option("--slope", nargs=3, type=float, default=(1.0, 1.0, 1.0), help="CDL slope (R G B).")
@click.option("--offset", nargs=3, type=float, default=(0.0, 0.0, 0.0), help="CDL offset (R G B).")
@click.option("--power", nargs=3, type=float, default=(1.0, 1.0, 1.0), help="CDL power (R G B).")
@click.option("--saturation", type=float, default=1.0, help="CDL saturation.")
@click.option(
    "--working-space",
    help="CSC transform URN for the CDL working space (either direction; the inverse is derived). "
    "Default: ACEScct for the file's ACES version.",
)
@click.option("--description", "-d", help="Look description.")
@click.option("--output", "-o", type=click.Path(), help="Output path. Defaults to overwriting input.")
@click.pass_context
def add_cdl(ctx, file, slope, offset, power, saturation, working_space, description, output):
    """Add a CDL look transform to an AMF file."""
    registry = ctx.obj.get("transform_registry") if ctx.obj else None
    path = Path(file)
    amf = ACESAMF.from_file(path, registry=registry)

    aces_version = amf.aces_version or (2, 0, 0)
    try:
        lt = cdl_look_transform(
            slope=list(slope),
            offset=list(offset),
            power=list(power),
            saturation=saturation,
            aces_version=aces_version,
            working_space=working_space,
            registry=amf.registry,
        )
    except ValueError as e:
        raise click.ClickException(str(e)) from e
    if working_space:
        version = f"v{aces_version[0]}.{aces_version[1]}"
        canonical = amf.registry.get_transform_info(working_space, version=version)["transform_id"]
        if canonical != working_space:
            click.echo(f"Resolved working space {working_space} -> {canonical} for ACES {version}")
    if description:
        lt.description = description
    amf.with_look_transform(lt)

    out_path = Path(output) if output else path
    amf.write(out_path, registry=registry)
    click.echo(f"Added CDL look transform to {out_path.name}")


@click.command("compute-hashes")
@click.argument("file", type=click.Path(exists=True))
@click.option(
    "--algorithm",
    type=click.Choice(["md5", "sha1", "sha256"]),
    default="sha256",
    help="Hash algorithm.",
)
def compute_hashes(file, algorithm):
    """Compute and display file hash for an AMF file."""
    path = Path(file)
    data = path.read_bytes()

    h = hashlib.new(algorithm)
    h.update(data)
    digest = h.hexdigest()

    click.echo(f"{algorithm.upper()}: {digest}  {path.name}")

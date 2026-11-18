# SPDX-License-Identifier: Apache-2.0
"""Info command."""

from pathlib import Path

import click

from aswf.aces.amf_lib import load_amf
from aswf.aces.amf_utils.factories import cdl_look_transform_to_dict


@click.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--verbose", "-v", is_flag=True, help="Show detailed transform info.")
@click.pass_context
def info(ctx, file, verbose):
    """Display information about an AMF file."""
    path = Path(file)
    registry = ctx.obj.get("transform_registry") if ctx.obj else None
    amf = load_amf(path, transform_registry=registry)

    click.echo(f"File: {path.name}")

    # ACES version
    if amf.pipeline and amf.pipeline.pipeline_info and amf.pipeline.pipeline_info.system_version:
        sv = amf.pipeline.pipeline_info.system_version
        click.echo(f"ACES Version: {sv.major_version}.{sv.minor_version}.{sv.patch_version}")

    # Description
    if amf.amf_info and amf.amf_info.description:
        click.echo(f"Description: {amf.amf_info.description}")
    if amf.pipeline and amf.pipeline.pipeline_info and amf.pipeline.pipeline_info.description:
        click.echo(f"Pipeline: {amf.pipeline.pipeline_info.description}")

    # Authors
    if amf.amf_info and amf.amf_info.author:
        click.echo("Authors:")
        for author in amf.amf_info.author:
            email = f" <{author.email_address}>" if author.email_address else ""
            click.echo(f"  - {author.name}{email}")

    # Clip ID
    if amf.clip_id:
        clip = amf.clip_id
        click.echo(f"Clip: {clip.clip_name}")
        if clip.file:
            click.echo(f"  File: {clip.file}")
        if clip.uuid:
            click.echo(f"  UUID: {clip.uuid}")

    # Pipeline transforms
    pipeline = amf.pipeline
    if not pipeline:
        return

    if pipeline.input_transform:
        it = pipeline.input_transform
        click.echo(f"Input Transform:")
        if it.transform_id:
            click.echo(f"  ID: {it.transform_id}")
        if it.description:
            click.echo(f"  Description: {it.description}")
        click.echo(f"  Applied: {it.applied}")

    if pipeline.look_transforms:
        click.echo(f"Look Transforms ({len(pipeline.look_transforms)}):")
        for i, lt in enumerate(pipeline.look_transforms):
            click.echo(f"  [{i}] {lt.description or '(no description)'}")
            if lt.transform_id:
                click.echo(f"      ID: {lt.transform_id}")
            click.echo(f"      Applied: {lt.applied}")
            if verbose and lt.asc_sop:
                try:
                    cdl = cdl_look_transform_to_dict(lt)
                    click.echo(f"      CDL: {cdl}")
                except (ValueError, AttributeError):
                    pass

    if pipeline.output_transform:
        ot = pipeline.output_transform
        click.echo(f"Output Transform:")
        if ot.transform_id:
            click.echo(f"  ID: {ot.transform_id}")
        if ot.description:
            click.echo(f"  Description: {ot.description}")
        click.echo(f"  Applied: {ot.applied}")

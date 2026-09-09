# SPDX-License-Identifier: Apache-2.0
"""Create command."""

from pathlib import Path

import click

from aswf.aces.amf_lib import amf, save_amf

from aswf.aces.amf_utils.builder import AMFBuilder


@click.command()
@click.argument("output", type=click.Path())
@click.option("--description", "-d", help="AMF description.")
@click.option("--author", help="Author name.")
@click.option("--author-email", help="Author email.")
@click.option("--idt", "idt_id", help="Input transform ID (URN).")
@click.option("--odt", "odt_id", help="Output transform ID (URN).")
@click.option(
    "--aces-version",
    default="1.3.0",
    help="ACES version (major.minor.patch). Default: 1.3.0",
)
@click.option("--force", "-f", is_flag=True, help="Overwrite output if it exists.")
@click.pass_context
def create(ctx, output, description, author, author_email, idt_id, odt_id, aces_version, force):
    """Create a new AMF file."""
    registry = ctx.obj.get("transform_registry") if ctx.obj else None
    out_path = Path(output)

    if out_path.exists() and not force:
        raise click.ClickException(f"Output file exists: {out_path}. Use --force to overwrite.")

    parts = aces_version.split(".")
    if len(parts) != 3:
        raise click.ClickException("ACES version must be major.minor.patch (e.g. 1.3.0)")
    version = tuple(int(p) for p in parts)

    builder = AMFBuilder(aces_version=version)

    if description:
        builder.with_description(description)
    if author:
        builder.with_author(amf.AuthorType(name=author, email_address=author_email))
    if idt_id:
        builder.with_input_transform(amf.InputTransformType(transform_id=idt_id, applied=False))
    if odt_id:
        builder.with_output_transform(amf.OutputTransformType(transform_id=odt_id, applied=False))

    amf_obj = builder.build()
    save_amf(amf_obj, out_path, transform_registry=registry)
    click.echo(f"Created {out_path}")

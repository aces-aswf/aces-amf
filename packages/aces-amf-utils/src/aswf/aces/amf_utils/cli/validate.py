# SPDX-License-Identifier: Apache-2.0
"""Validate command."""

from pathlib import Path

import click

from aswf.aces.amf_lib import (
    ValidationLevel,
    validate_all,
    validate_schema,
    validate_semantic,
)

PROFILES = {
    "minimal": {"validators": ["temporal", "uuid"]},
    "standard": {"exclude": ["file_hashes"]},
    "strict": {},
}


@click.command()
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    "--profile",
    type=click.Choice(list(PROFILES.keys())),
    default="standard",
    help="Validation profile.",
)
@click.option("--schema-only", is_flag=True, help="Only run XSD schema validation.")
@click.option("--semantic-only", is_flag=True, help="Only run semantic validation.")
@click.option("--verbose", "-v", is_flag=True, help="Show all messages including INFO.")
@click.pass_context
def validate(ctx, files, profile, schema_only, semantic_only, verbose):
    """Validate one or more AMF files."""
    registry = ctx.obj.get("transform_registry") if ctx.obj else None
    profile_opts = PROFILES[profile]
    exit_code = 0
    uuid_pool: set[str] = set()

    for filepath in files:
        path = Path(filepath)
        click.echo(f"\n{path.name}")

        if schema_only:
            messages = validate_schema(path)
        elif semantic_only:
            messages = validate_semantic(
                path,
                uuid_pool=uuid_pool,
                transform_registry=registry,
                **profile_opts,
            )
        else:
            messages = validate_all(
                path,
                uuid_pool=uuid_pool,
                transform_registry=registry,
                **profile_opts,
            )

        errors = [m for m in messages if m.level == ValidationLevel.ERROR]
        warnings = [m for m in messages if m.level == ValidationLevel.WARNING]
        infos = [m for m in messages if m.level == ValidationLevel.INFO]

        if errors:
            exit_code = 1
            for m in errors:
                click.echo(click.style(f"  ERROR: {m.message}", fg="red"))
        for m in warnings:
            click.echo(click.style(f"  WARN:  {m.message}", fg="yellow"))
        if verbose:
            for m in infos:
                click.echo(f"  INFO:  {m.message}")

        if not errors and not warnings:
            click.echo(click.style("  PASS", fg="green"))

    raise SystemExit(exit_code)

# SPDX-License-Identifier: Apache-2.0
"""Diff command."""

from pathlib import Path

import click

from aswf.aces.amf_utils.diff import diff_amf


@click.command()
@click.argument("file1", type=click.Path(exists=True))
@click.argument("file2", type=click.Path(exists=True))
@click.option("--verbose", "-v", is_flag=True, help="Include detailed transform comparison.")
def diff(file1, file2, verbose):
    """Compare two AMF files and show differences."""
    result = diff_amf(Path(file1), Path(file2), verbose=verbose)

    if not result.has_differences:
        click.echo("Files are identical")
        return

    click.echo(f"{len(result.differences)} difference(s) found:")
    for d in result.differences:
        click.echo(f"  {d.field}:")
        click.echo(click.style(f"    - {d.old_value}", fg="red"))
        click.echo(click.style(f"    + {d.new_value}", fg="green"))

    raise SystemExit(1)

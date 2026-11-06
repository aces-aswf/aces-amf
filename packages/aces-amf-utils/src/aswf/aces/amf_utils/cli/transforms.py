# SPDX-License-Identifier: Apache-2.0
"""Transform info commands."""

import click

from aswf.aces.transforms import ACESTransformRegistry


@click.group()
def transforms():
    """Query the ACES transform registry."""


@transforms.command("list")
@click.option("--category", "-c", help="Filter by transform type (e.g. IDT, ODT, CSC).")
@click.option("--search", "-s", help="Filter by keyword in user name.")
@click.option("--limit", "-n", type=int, help="Maximum results to show.")
def list_transforms(category, search, limit):
    """List available ACES transforms."""
    registry = ACESTransformRegistry()
    results = registry.list_transforms(category=category)

    if search:
        search_lower = search.lower()
        results = [t for t in results if search_lower in t.get("user_name", "").lower()]

    if limit:
        results = results[:limit]

    if not results:
        click.echo("No transforms found.")
        return

    click.echo(f"{len(results)} transform(s):")
    for t in results:
        click.echo(f"  {t['transform_id']}")
        if t.get("user_name"):
            click.echo(f"    {t['user_name']}")


@transforms.command("info")
@click.argument("transform_id")
def transform_info(transform_id):
    """Show details about a specific transform."""
    registry = ACESTransformRegistry()
    info = registry.get_transform_info(transform_id)

    if not info:
        raise click.ClickException(f"Transform not found: {transform_id}")

    click.echo(f"Transform ID: {info['transform_id']}")
    click.echo(f"User Name: {info.get('user_name', '(none)')}")
    click.echo(f"Type: {info.get('transform_type', '(unknown)')}")
    if info.get("inverse_transform_id"):
        click.echo(f"Inverse: {info['inverse_transform_id']}")


@transforms.command("categories")
def list_categories():
    """List available transform categories."""
    registry = ACESTransformRegistry()
    categories = registry.get_transform_categories()

    for cat in sorted(categories):
        click.echo(f"  {cat}")

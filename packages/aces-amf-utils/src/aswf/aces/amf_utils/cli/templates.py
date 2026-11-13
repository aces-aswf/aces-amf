# SPDX-License-Identifier: Apache-2.0
"""Template management commands."""

import click

from aswf.aces.amf_utils.template_registry import REGISTRY, TemplateCategory


@click.group()
def template():
    """Manage and inspect AMF templates."""


@template.command("list")
@click.option(
    "--category", "-c",
    type=click.Choice([c.value for c in TemplateCategory], case_sensitive=False),
    help="Filter by category.",
)
@click.option("--verbose", "-v", is_flag=True, help="Show full template details.")
def list_templates(category, verbose):
    """List registered AMF templates."""
    cat = TemplateCategory(category) if category else None
    templates = REGISTRY.list_templates(category=cat)

    if not templates:
        click.echo("No templates registered.")
        return

    click.echo(f"{len(templates)} template(s):")
    for meta in templates:
        click.echo(f"  {meta.id}  [{meta.category.value}]")
        click.echo(f"    {meta.name}")
        if verbose:
            click.echo(f"    {meta.description}")
            if meta.tags:
                click.echo(f"    Tags: {', '.join(meta.tags)}")
            if meta.parameters:
                click.echo(f"    Parameters: {', '.join(meta.parameters.keys())}")


@template.command("show")
@click.argument("template_id")
def show_template(template_id):
    """Show details about a specific template."""
    entry = REGISTRY.get_template(template_id)
    if not entry:
        raise click.ClickException(f"Template not found: {template_id}")

    meta, _ = entry
    click.echo(f"ID:          {meta.id}")
    click.echo(f"Name:        {meta.name}")
    click.echo(f"Category:    {meta.category.value}")
    click.echo(f"Description: {meta.description}")
    if meta.tags:
        click.echo(f"Tags:        {', '.join(meta.tags)}")
    if meta.aces_versions:
        versions = [f"{v[0]}.{v[1]}.{v[2]}" for v in meta.aces_versions]
        click.echo(f"ACES:        {', '.join(versions)}")
    if meta.parameters:
        click.echo("Parameters:")
        for name, typ in meta.parameters.items():
            click.echo(f"  {name}: {typ.__name__}")
    if meta.example_usage:
        click.echo(f"Example:     {meta.example_usage}")


@template.command("search")
@click.argument("query")
def search_templates(query):
    """Search templates by name, description, or tags."""
    results = REGISTRY.search(query)
    if not results:
        click.echo(f"No templates matching {query!r}.")
        return

    click.echo(f"{len(results)} match(es) for {query!r}:")
    for meta in results:
        click.echo(f"  {meta.id}  [{meta.category.value}]  {meta.name}")


@template.command("validate")
@click.option("--verbose", "-v", is_flag=True, help="Show pass/fail for each template.")
def validate_templates(verbose):
    """Validate that all registered templates can generate without errors."""
    templates = REGISTRY.list_templates()
    if not templates:
        click.echo("No templates registered.")
        return

    passed = 0
    failed = 0
    for meta in templates:
        if not REGISTRY.can_generate_without_params(meta.id):
            if verbose:
                click.echo(f"  SKIP  {meta.id}  (requires parameters)")
            continue
        try:
            REGISTRY.generate(meta.id)
            passed += 1
            if verbose:
                click.echo(f"  PASS  {meta.id}")
        except Exception as e:
            failed += 1
            click.echo(f"  FAIL  {meta.id}: {e}")

    click.echo(f"\n{passed} passed, {failed} failed.")
    if failed:
        raise SystemExit(1)

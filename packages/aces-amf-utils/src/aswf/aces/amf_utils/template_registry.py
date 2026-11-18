# SPDX-License-Identifier: Apache-2.0
"""
Template registry for AMF file generation.

Provides a registration system for AMF templates that can generate
pre-configured AMF files with optional parameters.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from aswf.aces.amf_lib import AcesMetadataFile


class TemplateCategory(Enum):
    """Categories for AMF templates."""

    CAMERA_TO_DISPLAY = "camera_to_display"
    VFX_PULL = "vfx_pull"
    GRADING = "grading"
    HDR = "hdr"
    TESTING = "testing"
    ADVANCED = "advanced"
    MINIMAL = "minimal"


@dataclass
class TemplateMetadata:
    """Metadata for a registered template."""

    id: str
    name: str
    description: str
    category: TemplateCategory
    parameters: dict[str, type] = field(default_factory=dict)
    example_usage: str = ""
    aces_versions: list[tuple[int, int, int]] = field(default_factory=lambda: [(2, 0, 0)])
    tags: list[str] = field(default_factory=list)


class TemplateRegistry:
    """Registry for AMF file templates."""

    def __init__(self):
        self._templates: dict[str, tuple[TemplateMetadata, Callable]] = {}

    def register(self, metadata: TemplateMetadata, generator: Callable) -> None:
        """Register a template.

        Args:
            metadata: Template metadata.
            generator: Callable that returns an AcesMetadataFile instance.
        """
        self._templates[metadata.id] = (metadata, generator)

    def list_templates(self, category: TemplateCategory | None = None) -> list[TemplateMetadata]:
        """List registered templates, optionally filtered by category."""
        results = [meta for meta, _ in self._templates.values()]
        if category:
            results = [m for m in results if m.category == category]
        return sorted(results, key=lambda m: m.name)

    def get_template(self, template_id: str) -> tuple[TemplateMetadata, Callable] | None:
        """Get a template by ID."""
        return self._templates.get(template_id)

    def generate(self, template_id: str, **kwargs) -> AcesMetadataFile:
        """Generate an AMF from a template.

        Args:
            template_id: The template ID.
            **kwargs: Parameters for the template generator.

        Returns:
            Generated AcesMetadataFile instance.

        Raises:
            KeyError: If template not found.
            ValueError: If parameters are invalid.
        """
        entry = self._templates.get(template_id)
        if not entry:
            raise KeyError(f"Template {template_id!r} not found")

        _, generator = entry
        try:
            return generator(**kwargs)
        except TypeError as e:
            raise ValueError(f"Invalid parameters for template {template_id!r}: {e}") from e

    def can_generate_without_params(self, template_id: str) -> bool:
        """Check if a template can be generated without any parameters."""
        entry = self._templates.get(template_id)
        if not entry:
            return False

        _, generator = entry
        sig = inspect.signature(generator)
        return all(
            p.default is not inspect.Parameter.empty
            for p in sig.parameters.values()
        )

    def search(self, query: str) -> list[TemplateMetadata]:
        """Search templates by name, description, or tags."""
        query_lower = query.lower()
        results = []
        for meta, _ in self._templates.values():
            if (
                query_lower in meta.name.lower()
                or query_lower in meta.description.lower()
                or any(query_lower in tag.lower() for tag in meta.tags)
            ):
                results.append(meta)
        return sorted(results, key=lambda m: m.name)

    def get_categories(self) -> list[TemplateCategory]:
        """Get categories that have at least one template."""
        cats = {meta.category for meta, _ in self._templates.values()}
        return sorted(cats, key=lambda c: c.value)


# Global registry singleton
REGISTRY = TemplateRegistry()

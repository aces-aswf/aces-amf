# SPDX-License-Identifier: Apache-2.0
"""Tests for the template registry."""

import pytest
from aswf.aces.amf_lib import AcesMetadataFile
from aswf.aces.amf_utils import minimal_amf
from aswf.aces.amf_utils import (
    TemplateCategory,
    TemplateMetadata,
    TemplateRegistry,
)


def _simple_generator(description="Default"):
    amf = minimal_amf()
    amf.amf_info.description = description
    return amf


@pytest.fixture
def registry():
    reg = TemplateRegistry()
    reg.register(
        TemplateMetadata(
            id="test_basic",
            name="Basic Template",
            description="A basic test template",
            category=TemplateCategory.TESTING,
            tags=["test", "basic"],
        ),
        _simple_generator,
    )
    reg.register(
        TemplateMetadata(
            id="test_hdr",
            name="HDR Template",
            description="An HDR test template",
            category=TemplateCategory.HDR,
            tags=["hdr", "display"],
        ),
        _simple_generator,
    )
    return reg


class TestTemplateRegistry:
    def test_list_all(self, registry):
        templates = registry.list_templates()
        assert len(templates) == 2

    def test_list_by_category(self, registry):
        templates = registry.list_templates(category=TemplateCategory.TESTING)
        assert len(templates) == 1
        assert templates[0].id == "test_basic"

    def test_get_template(self, registry):
        result = registry.get_template("test_basic")
        assert result is not None
        meta, gen = result
        assert meta.name == "Basic Template"

    def test_get_template_not_found(self, registry):
        assert registry.get_template("nonexistent") is None

    def test_generate(self, registry):
        amf = registry.generate("test_basic", description="Custom")
        assert isinstance(amf, AcesMetadataFile)
        assert amf.amf_info.description == "Custom"

    def test_generate_not_found(self, registry):
        with pytest.raises(KeyError):
            registry.generate("nonexistent")

    def test_generate_invalid_params(self, registry):
        with pytest.raises(ValueError):
            registry.generate("test_basic", nonexistent_param=True)

    def test_search(self, registry):
        results = registry.search("hdr")
        assert len(results) == 1
        assert results[0].id == "test_hdr"

    def test_search_by_tag(self, registry):
        results = registry.search("display")
        assert len(results) == 1

    def test_search_no_results(self, registry):
        results = registry.search("nonexistent_query")
        assert len(results) == 0

    def test_can_generate_without_params(self, registry):
        # _simple_generator has description with default value
        assert registry.can_generate_without_params("test_basic")

    def test_get_categories(self, registry):
        cats = registry.get_categories()
        assert TemplateCategory.TESTING in cats
        assert TemplateCategory.HDR in cats
        assert len(cats) == 2

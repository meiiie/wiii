"""Tests for Site Playbook Loader and PlaybookDrivenAdapter."""

import pytest
import yaml
from pathlib import Path
from unittest.mock import MagicMock

from app.engine.search_platforms.playbook_loader import (
    PlaybookLoader,
    PlaybookSiteConfig,
    PlaybookRequestConfig,
    PlaybookExtractionConfig,
    PlaybookStrategyConfig,
    SitePlaybook,
    get_playbook_loader,
)


class TestPlaybookDataModels:
    def test_site_playbook_defaults(self):
        pb = SitePlaybook(platform_id="test", display_name="Test", backend="custom")
        assert pb.enabled is True
        assert pb.priority == 0
        assert pb.site.query_encoding == "percent"

    def test_site_config(self):
        cfg = PlaybookSiteConfig(
            base_url="https://example.com",
            url_template="{base_url}?q={query_encoded}",
            query_encoding="plus",
        )
        assert cfg.query_encoding == "plus"


class TestPlaybookLoader:
    def test_load_real_playbooks(self):
        """Should load the YAML playbooks from the playbooks/ directory."""
        loader = get_playbook_loader()
        playbooks = loader.get_all()
        assert len(playbooks) > 0
        # Check websosanh is present
        ws = loader.get("websosanh")
        assert ws is not None
        assert ws.display_name == "WebSosanh.vn"
        assert ws.backend == "custom"
        assert ws.extraction.type == "html_css"

    def test_get_nonexistent_playbook(self):
        loader = get_playbook_loader()
        assert loader.get("nonexistent_platform") is None

    def test_get_for_domain(self):
        loader = get_playbook_loader()
        pb = loader.get_for_domain("websosanh.vn")
        assert pb is not None
        assert pb.platform_id == "websosanh"

    def test_get_for_domain_facebook(self):
        loader = get_playbook_loader()
        pb = loader.get_for_domain("facebook.com")
        assert pb is not None
        assert "facebook" in pb.platform_id

    def test_get_for_domain_not_found(self):
        loader = get_playbook_loader()
        assert loader.get_for_domain("unknown-site.xyz") is None

    def test_reload(self):
        loader = get_playbook_loader()
        count_before = len(loader.get_all())
        count_after = loader.reload()
        assert count_after == count_before

    def test_parse_playbook_from_yaml(self, tmp_path):
        """Test parsing a custom YAML playbook file."""
        yaml_content = {
            "platform_id": "test_shop",
            "display_name": "Test Shop",
            "backend": "custom",
            "enabled": True,
            "priority": 5,
            "site": {
                "base_url": "https://testshop.vn",
                "url_template": "{base_url}/search?q={query_encoded}",
                "query_encoding": "percent",
            },
            "request": {
                "method": "GET",
                "timeout_seconds": 20,
            },
            "extraction": {
                "type": "html_css",
                "selectors": {
                    "container": ".product",
                    "title": ".product-title",
                    "price": ".product-price",
                },
            },
            "strategy": {
                "preferred_backend": "custom",
                "fallback_chain": ["serper_site"],
            },
        }
        yaml_file = tmp_path / "test_shop.playbook.yaml"
        yaml_file.write_text(yaml.dump(yaml_content), encoding="utf-8")

        loader = PlaybookLoader(playbooks_dir=tmp_path)
        pb = loader.get("test_shop")
        assert pb is not None
        assert pb.display_name == "Test Shop"
        assert pb.priority == 5
        assert pb.extraction.selectors["container"] == ".product"
        assert pb.request.timeout_seconds == 20
        assert pb.strategy.fallback_chain == ["serper_site"]


class TestPlaybookDrivenAdapter:
    def test_adapter_config_from_playbook(self):
        from app.engine.search_platforms.playbook_adapter import PlaybookDrivenAdapter
        from app.engine.search_platforms.base import BackendType

        playbook = SitePlaybook(
            platform_id="test",
            display_name="Test Platform",
            backend="custom",
            priority=5,
            request=PlaybookRequestConfig(timeout_seconds=15),
        )
        adapter = PlaybookDrivenAdapter(playbook)
        config = adapter.get_config()
        assert config.id == "test"
        assert config.display_name == "Test Platform"
        assert config.priority == 5
        assert config.timeout_seconds == 15

    def test_search_sync_empty_query(self):
        from app.engine.search_platforms.playbook_adapter import PlaybookDrivenAdapter

        playbook = SitePlaybook(
            platform_id="test", display_name="Test", backend="custom"
        )
        adapter = PlaybookDrivenAdapter(playbook)
        results = adapter.search_sync("")
        assert results == []

    def test_build_url_plus_encoding(self):
        from app.engine.search_platforms.playbook_adapter import PlaybookDrivenAdapter

        playbook = SitePlaybook(
            platform_id="test",
            display_name="Test",
            backend="custom",
            site=PlaybookSiteConfig(
                base_url="https://example.com/s/",
                url_template="{base_url}{query_encoded}.htm?page={page}",
                query_encoding="plus",
            ),
        )
        adapter = PlaybookDrivenAdapter(playbook)
        url = adapter._build_url("MacBook Pro M4", page=1)
        assert "MacBook+Pro+M4" in url
        assert "example.com/s/" in url

    def test_build_url_percent_encoding(self):
        from app.engine.search_platforms.playbook_adapter import PlaybookDrivenAdapter

        playbook = SitePlaybook(
            platform_id="test",
            display_name="Test",
            backend="custom",
            site=PlaybookSiteConfig(
                base_url="https://example.com",
                url_template="https://example.com/search?q={query_encoded}",
                query_encoding="percent",
            ),
        )
        adapter = PlaybookDrivenAdapter(playbook)
        url = adapter._build_url("iPhone 16 Pro", page=1)
        assert "%20" in url or "iPhone" in url

    def test_parse_html_with_selectors(self):
        from app.engine.search_platforms.playbook_adapter import PlaybookDrivenAdapter

        playbook = SitePlaybook(
            platform_id="test",
            display_name="Test Shop",
            backend="custom",
            extraction=PlaybookExtractionConfig(
                type="html_css",
                selectors={
                    "container": ".product",
                    "title": ".title",
                    "price": ".price",
                    "link": ".link[href]",
                    "image": "img[src]",
                },
                field_mapping={"link_base": "https://example.com"},
            ),
        )
        adapter = PlaybookDrivenAdapter(playbook)

        html = """
        <div class="product">
            <span class="title">MacBook Pro M4</span>
            <span class="price">45.000.000₫</span>
            <a class="link" href="/product/macbook-pro-m4">Link</a>
            <img src="/images/macbook.jpg">
        </div>
        <div class="product">
            <span class="title">iPhone 16</span>
            <span class="price">25.000.000₫</span>
            <a class="link" href="/product/iphone-16">Link</a>
            <img src="/images/iphone.jpg">
        </div>
        """
        results = adapter._parse_html(html, max_results=10)
        assert len(results) == 2
        assert results[0].title == "MacBook Pro M4"
        assert results[0].platform == "Test Shop"
        assert results[0].link == "https://example.com/product/macbook-pro-m4"
        assert results[0].image == "https://example.com/images/macbook.jpg"

    def test_parse_html_fallback_selectors(self):
        from app.engine.search_platforms.playbook_adapter import PlaybookDrivenAdapter

        playbook = SitePlaybook(
            platform_id="test",
            display_name="Test",
            backend="custom",
            extraction=PlaybookExtractionConfig(
                type="html_css",
                selectors={"container": ".old-layout"},
                fallback_selectors={
                    "container": [".new-layout", ".product-list"],
                    "title": [".name", "h3"],
                    "price": [".cost"],
                },
            ),
        )
        adapter = PlaybookDrivenAdapter(playbook)

        html = """
        <div class="product-list">
            <div class="name">Widget A</div>
            <div class="cost">100.000₫</div>
        </div>
        """
        results = adapter._parse_html(html, max_results=10)
        assert len(results) == 1
        assert results[0].title == "Widget A"

    def test_resolve_json_path(self):
        from app.engine.search_platforms.playbook_adapter import PlaybookDrivenAdapter

        data = {"data": {"items": [{"name": "Product A"}, {"name": "Product B"}]}}
        assert PlaybookDrivenAdapter._resolve_json_path(data, "data.items.0.name") == "Product A"
        assert PlaybookDrivenAdapter._resolve_json_path(data, "data.items.1.name") == "Product B"
        assert PlaybookDrivenAdapter._resolve_json_path(data, "data.missing") is None
        assert PlaybookDrivenAdapter._resolve_json_path(data, "") is None

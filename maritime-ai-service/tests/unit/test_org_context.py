"""
Tests for Organization ContextVar — Per-request org isolation.

Sprint 24: Multi-Organization Architecture.

Verifies:
- ContextVar set/get/reset
- Default None when unset
- Allowed domains tracking
- Async isolation (no cross-request leakage)
"""

import asyncio
import pytest

from app.core.org_context import (
    current_org_id,
    current_org_allowed_domains,
    get_current_org_id,
    get_current_org_allowed_domains,
)


class TestOrgContextVar:
    def test_default_is_none(self):
        assert get_current_org_id() is None

    def test_set_and_get(self):
        token = current_org_id.set("lms-hang-hai")
        try:
            assert get_current_org_id() == "lms-hang-hai"
        finally:
            current_org_id.reset(token)
        assert get_current_org_id() is None

    def test_reset_restores_none(self):
        token = current_org_id.set("org-1")
        current_org_id.reset(token)
        assert get_current_org_id() is None

    def test_allowed_domains_default_none(self):
        assert get_current_org_allowed_domains() is None

    def test_allowed_domains_set_and_get(self):
        token = current_org_allowed_domains.set(["maritime", "traffic_law"])
        try:
            assert get_current_org_allowed_domains() == ["maritime", "traffic_law"]
        finally:
            current_org_allowed_domains.reset(token)
        assert get_current_org_allowed_domains() is None

    def test_allowed_domains_empty_list(self):
        token = current_org_allowed_domains.set([])
        try:
            assert get_current_org_allowed_domains() == []
        finally:
            current_org_allowed_domains.reset(token)


class TestAsyncIsolation:
    @pytest.mark.asyncio
    async def test_no_cross_task_leakage(self):
        """Two concurrent tasks should not see each other's org_id."""
        results = {}

        async def task_a():
            token = current_org_id.set("org-a")
            await asyncio.sleep(0.01)
            results["a"] = get_current_org_id()
            current_org_id.reset(token)

        async def task_b():
            token = current_org_id.set("org-b")
            await asyncio.sleep(0.01)
            results["b"] = get_current_org_id()
            current_org_id.reset(token)

        await asyncio.gather(task_a(), task_b())
        assert results["a"] == "org-a"
        assert results["b"] == "org-b"

    @pytest.mark.asyncio
    async def test_unset_after_task(self):
        """After a task resets, the parent context should be unaffected."""
        assert get_current_org_id() is None

        async def inner():
            token = current_org_id.set("inner-org")
            current_org_id.reset(token)

        await inner()
        assert get_current_org_id() is None

    @pytest.mark.asyncio
    async def test_domains_isolation(self):
        """Allowed domains should also be isolated per-task."""
        results = {}

        async def task_a():
            token = current_org_allowed_domains.set(["maritime"])
            await asyncio.sleep(0.01)
            results["a"] = get_current_org_allowed_domains()
            current_org_allowed_domains.reset(token)

        async def task_b():
            # task_b doesn't set domains
            await asyncio.sleep(0.01)
            results["b"] = get_current_org_allowed_domains()

        await asyncio.gather(task_a(), task_b())
        assert results["a"] == ["maritime"]
        assert results["b"] is None

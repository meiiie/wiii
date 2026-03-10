"""Tests for manifest-driven sandbox workload catalog."""

from __future__ import annotations

from app.sandbox.catalog import (
    SandboxWorkloadCatalog,
    get_sandbox_workload_catalog,
    reset_sandbox_workload_catalog,
)
from app.sandbox.models import SandboxNetworkMode, SandboxWorkloadKind


class TestSandboxWorkloadCatalog:
    def teardown_method(self):
        reset_sandbox_workload_catalog()

    def test_builtin_profiles_are_loaded(self):
        catalog = get_sandbox_workload_catalog()

        profiles = {profile.profile_id: profile for profile in catalog.get_all()}

        assert "python_exec" in profiles
        assert "browser_playwright" in profiles
        assert profiles["python_exec"].workload_kind == SandboxWorkloadKind.PYTHON
        assert profiles["browser_playwright"].workload_kind == SandboxWorkloadKind.BROWSER
        assert profiles["python_exec"].network_mode == SandboxNetworkMode.EGRESS

    def test_find_by_tool_name_returns_bound_profile(self):
        catalog = get_sandbox_workload_catalog()

        profile = catalog.find_by_tool_name("tool_execute_python")

        assert profile is not None
        assert profile.profile_id == "python_exec"
        assert profile.approval_scope == "privileged_execution"

    def test_invalid_manifest_is_skipped(self, tmp_path):
        (tmp_path / "broken.yaml").write_text(
            "id: broken\nworkload_kind: not-real\n",
            encoding="utf-8",
        )

        catalog = SandboxWorkloadCatalog(tmp_path)

        assert catalog.get_all() == []

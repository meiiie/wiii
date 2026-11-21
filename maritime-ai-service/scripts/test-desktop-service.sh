#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

# Only the managed Service login, organization and Kết nối contracts used by
# the desktop app. Full backend tests remain available via pytest tests/unit/.
exec python -m pytest -x -p no:capture --tb=short -q \
  tests/unit/test_dev_login_router.py \
  tests/unit/test_magic_link_session_store.py \
  tests/unit/test_sprint224_magic_link.py \
  tests/unit/test_sprint157_google_oauth.py \
  tests/unit/test_sprint193_web_oauth.py \
  tests/unit/test_sprint192_auth_hardening.py \
  tests/unit/test_sprint194b_auth_hardening.py::TestAPIKeyUserIDTrustProduction \
  tests/unit/test_sprint194b_auth_hardening.py::TestAPIKeyRoleRestriction \
  tests/unit/test_org_context.py \
  tests/unit/test_org_middleware.py \
  tests/unit/test_organization_api.py \
  tests/unit/test_organization_models.py \
  tests/unit/test_organization_repository.py \
  tests/unit/api/test_wiii_connect_api.py \
  tests/unit/test_wiii_connect_action_catalog.py \
  tests/unit/test_wiii_connect_action_inventory.py \
  tests/unit/test_wiii_connect_action_policy.py \
  tests/unit/test_wiii_connect_adapter_v1.py \
  tests/unit/test_wiii_connect_callback_boundary.py \
  tests/unit/test_wiii_connect_callback_state.py \
  tests/unit/test_wiii_connect_connection_sessions.py \
  tests/unit/test_wiii_connect_persistent_storage.py \
  tests/unit/test_wiii_connect_provider_adapters.py \
  tests/unit/test_wiii_connect_provider_registry.py \
  tests/unit/test_wiii_connect_snapshot.py::test_wiii_connect_snapshot_fails_closed_without_host_or_provider \
  tests/unit/test_wiii_connect_snapshot.py::test_wiii_connect_snapshot_distinguishes_connected_account_from_agent_ready \
  tests/unit/test_wiii_connect_snapshot.py::test_wiii_connect_snapshot_projects_backend_provider_connection \
  tests/unit/test_wiii_connect_snapshot.py::test_wiii_connect_snapshot_connected_provider_without_scope_is_not_agent_ready \
  tests/unit/test_wiii_connect_vault_audit.py \
  "$@"

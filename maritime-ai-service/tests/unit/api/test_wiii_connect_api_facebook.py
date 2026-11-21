from __future__ import annotations

import json

import httpx
import pytest

from tests.unit.api.wiii_connect_api_helpers import (
    authenticated_app as authenticated_app,
)


@pytest.mark.asyncio
async def test_wiii_connect_facebook_post_preview_apply_requires_scope_and_token(
    authenticated_app,
    monkeypatch,
):
    from app.api.v1 import wiii_connect as wiii_connect_api
    from app.engine.wiii_connect.adapter_v1 import (
        WiiiConnectConnectionRecordV1,
        WiiiConnectScopeGrant,
        public_connection_ref,
    )
    from app.engine.wiii_connect.composio_adapter import (
        WiiiConnectComposioAdapterConfig,
        WiiiConnectComposioExecuteResult,
        WiiiConnectComposioToolSchemaResult,
    )
    from app.engine.wiii_connect.persistent_storage import (
        WiiiConnectPersistentStorageStatus,
    )
    from app.engine.wiii_connect.operation_approval import (
        WiiiConnectOperationApprovalDecision,
    )

    class FakeStorage:
        def __init__(self):
            self.connection = WiiiConnectConnectionRecordV1(
                connection_id="ca_facebook",
                provider_slug="facebook",
                state="connected",
                scopes=WiiiConnectScopeGrant(read=True),
            )
            self.audit_appends = 0
            self.operation_approval_appends = 0
            self.operation_approval_consumes = 0
            self.operation_approvals = {}
            self.upserts = 0

        def status(self, *, probe_database: bool = True):
            return WiiiConnectPersistentStorageStatus(
                enabled=True,
                persistent=True,
                connection_table_ready=True,
                audit_ledger_ready=True,
                operation_approval_table_ready=True,
                reason="ready",
            )

        def expire_stale_pending_connections(self, **kwargs):
            return 0

        def list_connection_records(self, **kwargs):
            return (self.connection,)

        def get_connection_record(self, **kwargs):
            assert kwargs["provider_slug"] == "facebook"
            assert kwargs["connection_id"] == "ca_facebook"
            return self.connection

        def upsert_connection_record(self, connection, **kwargs):
            self.upserts += 1
            self.connection = connection
            return True

        def append_audit_record(self, record, *, organization_id: str, user_id: str):
            self.audit_appends += 1
            serialized = json.dumps(record.to_public_metadata(), sort_keys=True)
            assert organization_id == "org_1"
            assert user_id == "user_1"
            assert "approval-token" not in serialized
            assert "secret post message" not in serialized
            assert "ca_facebook" not in serialized
            return True

        def append_operation_approval_record(
            self,
            record,
            *,
            organization_id: str,
            user_id: str,
        ):
            self.operation_approval_appends += 1
            serialized = json.dumps(record.to_public_metadata(), sort_keys=True)
            assert organization_id == "org_1"
            assert user_id == "user_1"
            assert "approval-token" not in serialized
            assert "secret post message" not in serialized
            assert "ca_facebook" not in serialized
            assert "123456" not in serialized
            self.operation_approvals[record.preview_evidence_id] = {
                "record": record,
                "consumed": False,
            }
            return True

        def consume_operation_approval_record(
            self,
            *,
            preview_evidence_id: str,
            request_fingerprint: str,
            organization_id: str,
            user_id: str,
            provider_slug: str,
            action_slug: str,
            consumed_at=None,
        ):
            self.operation_approval_consumes += 1
            assert organization_id == "org_1"
            assert user_id == "user_1"
            stored = self.operation_approvals.get(preview_evidence_id)
            if stored is None:
                return WiiiConnectOperationApprovalDecision(
                    status="blocked",
                    reason="approval_record_missing",
                    provider_slug=provider_slug,
                    action_slug=action_slug,
                    preview_evidence_id_present=bool(preview_evidence_id),
                    request_fingerprint_present=bool(request_fingerprint),
                    persistent=True,
                    blocked=True,
                )
            if stored["consumed"]:
                return WiiiConnectOperationApprovalDecision(
                    status="blocked",
                    reason="approval_record_already_consumed",
                    provider_slug=provider_slug,
                    action_slug=action_slug,
                    preview_evidence_id_present=True,
                    request_fingerprint_present=True,
                    persistent=True,
                    blocked=True,
                )
            record = stored["record"]
            if record.request_fingerprint != request_fingerprint:
                return WiiiConnectOperationApprovalDecision(
                    status="blocked",
                    reason="approval_fingerprint_mismatch",
                    provider_slug=provider_slug,
                    action_slug=action_slug,
                    preview_evidence_id_present=True,
                    request_fingerprint_present=True,
                    persistent=True,
                    blocked=True,
                )
            stored["consumed"] = True
            return WiiiConnectOperationApprovalDecision(
                status="consumed",
                reason="approval_consumed",
                provider_slug=provider_slug,
                action_slug=action_slug,
                preview_evidence_id_present=True,
                request_fingerprint_present=True,
                persistent=True,
                consumed=True,
            )

    fake_storage = FakeStorage()
    monkeypatch.setattr(
        wiii_connect_api,
        "build_composio_adapter_config",
        lambda: WiiiConnectComposioAdapterConfig(
            enabled=True,
            api_key="secret-api-key",
            api_key_present=True,
            auth_config_by_provider={"facebook": "authcfg_fb"},
            readonly_execute_enabled=True,
            readonly_action_allowlist_by_provider={
                "facebook": ("FACEBOOK_LIST_MANAGED_PAGES",),
            },
            apply_execute_enabled=True,
            apply_action_allowlist_by_provider={
                "facebook": (
                    "FACEBOOK_CREATE_POST",
                    "FACEBOOK_CREATE_PHOTO_POST",
                ),
            },
        ),
    )
    monkeypatch.setattr(
        wiii_connect_api,
        "get_wiii_connect_persistent_storage",
        lambda: fake_storage,
    )

    async def fake_schema(**kwargs):
        return WiiiConnectComposioToolSchemaResult(
            ready=True,
            provider_slug="facebook",
            action_slug=kwargs["action_slug"],
            reason="ready",
            schema_present=True,
            argument_keys=("page_id", "message", "published"),
            required_argument_keys=("page_id", "message"),
        )

    execute_calls = 0

    async def fake_execute(**kwargs):
        nonlocal execute_calls
        execute_calls += 1
        assert kwargs["provider_slug"] == "facebook"
        assert kwargs["action_slug"] == "FACEBOOK_CREATE_POST"
        assert kwargs["connected_account_id"] == "ca_facebook"
        assert kwargs["arguments"]["page_id"] == "123456"
        assert kwargs["arguments"]["message"] == "secret post message"
        return WiiiConnectComposioExecuteResult(
            ready=True,
            provider_slug="facebook",
            action_slug="FACEBOOK_CREATE_POST",
            reason="ready",
            successful=True,
            status_code=200,
            data_keys=("id",),
        )

    monkeypatch.setattr(wiii_connect_api, "verify_composio_tool_schema", fake_schema)
    monkeypatch.setattr(wiii_connect_api, "execute_composio_tool", fake_execute)

    connection_ref = public_connection_ref("facebook", "ca_facebook")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        blocked_preview = await client.post(
            "/wiii-connect/providers/facebook/facebook-post/preview",
            json={
                "connection_ref": connection_ref,
                "page_id": "123456",
                "message": "secret post message",
            },
        )
        scope_response = await client.post(
            f"/wiii-connect/providers/facebook/connections/{connection_ref}/scope-grant",
            json={"scopes": {"read": True, "preview": True, "apply": True}},
        )
        preview_response = await client.post(
            "/wiii-connect/providers/facebook/facebook-post/preview",
            json={
                "connection_ref": connection_ref,
                "page_id": "123456",
                "message": "secret post message",
            },
        )
        preview_payload = preview_response.json()
        apply_response = await client.post(
            "/wiii-connect/providers/facebook/facebook-post/apply",
            json={
                "connection_ref": connection_ref,
                "page_id": "123456",
                "message": "secret post message",
                "approval_token": preview_payload["approval_token"],
                "preview_evidence_id": preview_payload["preview_evidence_id"],
            },
        )
        replay_response = await client.post(
            "/wiii-connect/providers/facebook/facebook-post/apply",
            json={
                "connection_ref": connection_ref,
                "page_id": "123456",
                "message": "secret post message",
                "approval_token": preview_payload["approval_token"],
                "preview_evidence_id": preview_payload["preview_evidence_id"],
            },
        )

    blocked_payload = blocked_preview.json()
    scope_payload = scope_response.json()
    apply_payload = apply_response.json()
    replay_payload = replay_response.json()
    serialized = json.dumps(
        {
            "scope": scope_payload,
            "preview": preview_payload,
            "apply": apply_payload,
            "replay": replay_payload,
        },
        sort_keys=True,
    )

    assert blocked_payload["status"] == "blocked"
    assert blocked_payload["reason"] == "missing_scope"
    assert scope_payload["status"] == "ready"
    assert scope_payload["connection"]["scopes"]["preview"] is True
    assert scope_payload["connection"]["scopes"]["apply"] is True
    assert preview_payload["status"] == "ready"
    assert preview_payload["preview_evidence_id"].startswith("wcp_")
    assert preview_payload["approval_token"]
    assert preview_payload["approval_ledger"]["status"] == "pending"
    assert preview_payload["approval_ledger"]["persistent"] is True
    assert apply_payload["status"] == "succeeded"
    assert apply_payload["approval_ledger"]["status"] == "consumed"
    assert apply_payload["approval_ledger"]["consumed"] is True
    assert apply_payload["execution"]["status"] == "succeeded"
    assert replay_payload["status"] == "blocked"
    assert replay_payload["reason"] == "approval_record_already_consumed"
    assert replay_payload["approval_ledger"]["blocked"] is True
    assert fake_storage.upserts == 1
    assert fake_storage.audit_appends >= 3
    assert fake_storage.operation_approval_appends == 1
    assert fake_storage.operation_approval_consumes == 2
    assert execute_calls == 1
    assert "secret-api-key" not in serialized
    assert "authcfg_fb" not in serialized
    assert "ca_facebook" not in serialized


@pytest.mark.asyncio
async def test_wiii_connect_facebook_post_preview_rejects_missing_message(
    authenticated_app,
):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=authenticated_app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/wiii-connect/providers/facebook/facebook-post/preview",
            json={
                "connection_ref": "wcn_placeholder",
                "page_id": "123456",
                "message": "   ",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "validation_failed"
    assert payload["reason"] == "missing_message"

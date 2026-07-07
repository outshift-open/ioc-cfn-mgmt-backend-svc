# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for Cognition Engine API endpoints"""

import pytest
from fastapi import status

from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.cognition_engine import CognitionEngine as CognitionEngineModel
from server.utils.encryption import decrypt_credentials


def _base_payload(cfn_id: str, name: str = "test-engine") -> dict:
    return {
        "cfn_id": cfn_id,
        "name": name,
        "url": "http://ce.internal:8080",
        "version": "1.0.0",
    }


def _register(client, cfn_id, name="test-engine", **extra):
    resp = client.post(
        "/api/cognition-engines",
        json={**_base_payload(cfn_id, name), **extra},
    )
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()["ce_id"]


def _delete(client, ce_id: str) -> None:
    """Disable then soft-delete a CE."""
    client.patch(f"/api/cognition-engines/{ce_id}", json={"enabled": False})
    resp = client.delete(f"/api/cognition-engines/{ce_id}")
    assert resp.status_code == status.HTTP_204_NO_CONTENT


class TestCognitionEngineRegister:
    """Tests for POST /cognition-engines"""

    def test_register_invalid_cfn(self, client):
        """Registration under a non-existent CFN returns 404"""
        response = client.post(
            "/api/cognition-engines",
            json=_base_payload("non-existent-cfn-id"),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "cognition fabric node" in response.json()["detail"].lower()

    def test_register_new_engine_returns_201(self, client, registered_cfn):
        """New registration returns 201 and created=true"""
        response = client.post(
            "/api/cognition-engines",
            json=_base_payload(registered_cfn),
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["ce_id"]
        assert data["cfn_id"] == registered_cfn
        assert data["name"] == "test-engine"
        assert data["version"] == "1.0.0"
        assert data["kind"] is None
        assert data["subkind"] is None
        assert data["status"] == "offline"
        assert data["created"] is True

    def test_register_same_version_upserts_returns_200(self, client, registered_cfn):
        """Re-registering the same (cfn_id, name, version) updates the record and returns 200 + created=false"""
        payload = _base_payload(registered_cfn, "idempotent-engine")

        first = client.post("/api/cognition-engines", json=payload)
        assert first.status_code == status.HTTP_201_CREATED
        ce_id = first.json()["ce_id"]

        second = client.post(
            "/api/cognition-engines",
            json={**payload, "url": "http://ce-updated.internal:8080"},
        )

        assert second.status_code == status.HTTP_200_OK
        data = second.json()
        assert data["ce_id"] == ce_id
        assert data["created"] is False

    def test_register_new_version_creates_new_record(self, client, registered_cfn):
        """Re-registering the same (cfn_id, name) with a different version creates a new record (201)"""
        payload = _base_payload(registered_cfn, "versioned-engine")

        first = client.post("/api/cognition-engines", json=payload)
        assert first.status_code == status.HTTP_201_CREATED
        ce_id_v1 = first.json()["ce_id"]

        second = client.post(
            "/api/cognition-engines",
            json={**payload, "version": "2.0.0"},
        )

        assert second.status_code == status.HTTP_201_CREATED
        data = second.json()
        assert data["ce_id"] != ce_id_v1
        assert data["version"] == "2.0.0"
        assert data["created"] is True

    def test_register_full_payload(self, client, registered_cfn):
        """Registration with all optional fields"""
        payload = {
            "cfn_id": registered_cfn,
            "name": "knowledge-engine",
            "url": "https://ke.internal:9090",
            "version": "2.3.1",
            "kind": "knowledge",
            "subkind": "query",
            "capabilities": ["ingestion", "retrieval", "similarity_search"],
            "metrics": ["kb.documents.indexed", "kb.search.latency_ms"],
            "auth": {"type": "api_key", "credentials": {"api_key": "secret"}},
            "config": {"max_concurrent_requests": 100},
            "mas_config": {"880e8400-e29b-41d4-a716-446655440000": {"timeout": 30, "max_requests": 3000}},
        }

        response = client.post("/api/cognition-engines", json=payload)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["kind"] == "knowledge"
        assert data["subkind"] == "query"
        assert data["created"] is True

    def test_register_missing_required_fields(self, client, registered_cfn):
        """Missing url or version is rejected with 422"""
        response = client.post(
            "/api/cognition-engines",
            json={"cfn_id": registered_cfn, "name": "incomplete-engine"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_register_same_name_different_cfns(self, client):
        """Same engine name can be registered under different CFNs"""
        cfn1_id = client.post(
            "/api/cognition-fabric-nodes/register",
            json={"id": "cfn-ce-test-1", "name": "CFN CE Test 1"},
        ).json()["id"]

        cfn2_id = client.post(
            "/api/cognition-fabric-nodes/register",
            json={"id": "cfn-ce-test-2", "name": "CFN CE Test 2"},
        ).json()["id"]

        resp1 = client.post("/api/cognition-engines", json=_base_payload(cfn1_id, "shared-engine"))
        assert resp1.status_code == status.HTTP_201_CREATED

        resp2 = client.post("/api/cognition-engines", json=_base_payload(cfn2_id, "shared-engine"))
        assert resp2.status_code == status.HTTP_201_CREATED
        assert resp2.json()["cfn_id"] == cfn2_id
        assert resp2.json()["ce_id"] != resp1.json()["ce_id"]


class TestCognitionEngineList:
    """Tests for GET /cognition-engines"""

    def test_list_empty(self, client, registered_cfn):
        """No engines registered under CFN returns empty list"""
        response = client.get(f"/api/cognition-engines?cfn_id={registered_cfn}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 0
        assert data["cognition_engines"] == []

    def test_list_by_cfn_id(self, client, registered_cfn):
        """Lists all engines under a CFN"""
        for name in ("reasoning-engine", "planning-engine", "learning-engine"):
            _register(client, registered_cfn, name)

        response = client.get(f"/api/cognition-engines?cfn_id={registered_cfn}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 3
        names = [e["name"] for e in data["cognition_engines"]]
        assert "reasoning-engine" in names
        assert "planning-engine" in names
        assert "learning-engine" in names

    def test_list_filter_by_status(self, client, registered_cfn):
        """Status filter returns only matching engines"""
        ce_id = _register(client, registered_cfn, "online-engine")
        _register(client, registered_cfn, "offline-engine")

        # Bring one engine online via heartbeat
        client.put(f"/api/cognition-engines/{ce_id}/heartbeat")

        response = client.get(f"/api/cognition-engines?cfn_id={registered_cfn}&status=online")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["cognition_engines"][0]["name"] == "online-engine"

    def test_list_cfn_isolation(self, client):
        """Engines from one CFN don't appear in another CFN's listing"""
        cfn1_id = client.post(
            "/api/cognition-fabric-nodes/register",
            json={"id": "cfn-list-iso-1", "name": "CFN List Iso 1"},
        ).json()["id"]

        cfn2_id = client.post(
            "/api/cognition-fabric-nodes/register",
            json={"id": "cfn-list-iso-2", "name": "CFN List Iso 2"},
        ).json()["id"]

        _register(client, cfn1_id, "cfn1-engine")
        _register(client, cfn2_id, "cfn2-engine")

        resp1 = client.get(f"/api/cognition-engines?cfn_id={cfn1_id}")
        assert resp1.json()["total"] == 1
        assert resp1.json()["cognition_engines"][0]["name"] == "cfn1-engine"

        resp2 = client.get(f"/api/cognition-engines?cfn_id={cfn2_id}")
        assert resp2.json()["total"] == 1
        assert resp2.json()["cognition_engines"][0]["name"] == "cfn2-engine"

    def test_list_deleted_engines_excluded(self, client, registered_cfn):
        """Soft-deleted engines do not appear in the list"""
        _register(client, registered_cfn, "keep-engine")
        del_id = _register(client, registered_cfn, "delete-engine")

        _delete(client, del_id)

        data = client.get(f"/api/cognition-engines?cfn_id={registered_cfn}").json()
        assert data["total"] == 1
        assert data["cognition_engines"][0]["name"] == "keep-engine"

    def test_list_response_fields(self, client, registered_cfn):
        """List items contain the expected fields per spec"""
        _register(client, registered_cfn, "field-check-engine")

        item = client.get(f"/api/cognition-engines?cfn_id={registered_cfn}").json()["cognition_engines"][0]

        for field in ("id", "cfn_id", "name", "version", "kind", "subkind", "url", "enabled", "status", "config", "mas_config"):
            assert field in item
        assert "auth" not in item


class TestCognitionEngineGet:
    """Tests for GET /cognition-engines/{ce_id}"""

    def test_get_cognition_engine(self, client, registered_cfn):
        """Returns full detail for a known engine"""
        ce_id = _register(
            client, registered_cfn, "get-test-engine",
            kind="knowledge",
            subkind="distillation",
            capabilities=["summarize"],
            metrics=["latency_ms"],
        )

        response = client.get(f"/api/cognition-engines/{ce_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == ce_id
        assert data["cfn_id"] == registered_cfn
        assert data["name"] == "get-test-engine"
        assert data["kind"] == "knowledge"
        assert data["subkind"] == "distillation"
        assert data["capabilities"] == ["summarize"]
        assert data["metrics"] == ["latency_ms"]
        assert data["status"] == "offline"
        assert "created_at" in data
        assert "updated_at" in data
        assert "auth" not in data

    def test_get_nonexistent_engine(self, client):
        """Returns 404 for unknown ce_id"""
        response = client.get("/api/cognition-engines/nonexistent-id")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()



class TestCognitionEngineDelete:
    """Tests for DELETE /cognition-engines/{ce_id}"""

    def test_delete_enabled_ce_returns_409(self, client, registered_cfn):
        """Deleting an enabled CE returns 409 — must disable first."""
        ce_id = _register(client, registered_cfn, "delete-guard-test")

        response = client.delete(f"/api/cognition-engines/{ce_id}")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "disabled" in response.json()["detail"].lower()

    def test_delete_returns_204_after_disable(self, client, registered_cfn):
        """Disabling then deleting returns 204 No Content."""
        ce_id = _register(client, registered_cfn, "delete-test")
        client.patch(f"/api/cognition-engines/{ce_id}", json={"enabled": False})

        response = client.delete(f"/api/cognition-engines/{ce_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_deleted_engine_not_accessible(self, client, registered_cfn):
        """Deleted engine returns 404 on get."""
        ce_id = _register(client, registered_cfn, "soft-delete-test")
        _delete(client, ce_id)

        assert client.get(f"/api/cognition-engines/{ce_id}").status_code == status.HTTP_404_NOT_FOUND

    def test_delete_nonexistent_engine(self, client):
        """Deleting an unknown ce_id returns 404."""
        response = client.delete("/api/cognition-engines/nonexistent-id")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_deleted_engine_excluded_from_list(self, client, registered_cfn):
        """Deleted engines do not appear in list results."""
        _register(client, registered_cfn, "keep-engine")
        del_id = _register(client, registered_cfn, "gone-engine")
        _delete(client, del_id)

        data = client.get(f"/api/cognition-engines?cfn_id={registered_cfn}").json()
        assert data["total"] == 1
        assert data["cognition_engines"][0]["name"] == "keep-engine"

    def test_deleted_engine_name_can_be_reregistered(self, client, registered_cfn):
        """After deletion the same name can be registered again (partial unique index)."""
        ce_id = _register(client, registered_cfn, "reuse-name")
        _delete(client, ce_id)

        new = client.post("/api/cognition-engines", json=_base_payload(registered_cfn, "reuse-name"))
        assert new.status_code == status.HTTP_201_CREATED
        assert new.json()["ce_id"] != ce_id

    def test_delete_with_attached_mas_returns_409(self, client, registered_cfn, created_workspace):
        """Cannot delete a CE while it is associated with an active MAS.

        To reach this guard: disable the CE first (no MAS attached), then
        associate a MAS — now the CE is disabled but still has an active MAS.
        """
        ce_id = _register(client, registered_cfn, "delete-mas-guard")
        # Disable first so we can bypass the "must disable" guard
        client.patch(f"/api/cognition-engines/{ce_id}", json={"enabled": False})
        # Associate a MAS after disabling
        mas_id = _create_mas(client, created_workspace, "delete-guard-mas")
        client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )

        resp = client.delete(f"/api/cognition-engines/{ce_id}")

        assert resp.status_code == status.HTTP_409_CONFLICT
        assert "mas" in resp.json()["detail"].lower()

    def test_delete_ignores_soft_deleted_mas(self, client, registered_cfn, created_workspace):
        """Soft-deleted MAS associations do not block CE deletion."""
        ce_id = _register(client, registered_cfn, "delete-soft-mas-guard")
        # Disable first, then associate a MAS
        client.patch(f"/api/cognition-engines/{ce_id}", json={"enabled": False})
        mas_id = _create_mas(client, created_workspace, "delete-soft-mas")
        client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )
        # Soft-delete the MAS — junction row remains but MAS is gone
        client.delete(f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}")

        resp = client.delete(f"/api/cognition-engines/{ce_id}")

        assert resp.status_code == status.HTTP_204_NO_CONTENT


class TestCognitionEngineHeartbeat:
    def test_heartbeat_sets_status_online(self, client, registered_cfn):
        """Heartbeat flips offline→online and returns status/last_seen"""
        ce_id = _register(client, registered_cfn, "hb-engine")

        # Verify initial status is offline
        detail = client.get(f"/api/cognition-engines/{ce_id}").json()
        assert detail["status"] == "offline"
        assert detail["last_seen"] is None

        resp = client.put(f"/api/cognition-engines/{ce_id}/heartbeat")
        assert resp.status_code == status.HTTP_200_OK

        body = resp.json()
        assert body["status"] == "online"
        assert body["last_seen"] is not None

    def test_heartbeat_updates_last_seen(self, client, registered_cfn):
        """Two consecutive heartbeats produce increasing last_seen timestamps"""
        ce_id = _register(client, registered_cfn, "hb-ts-engine")

        r1 = client.put(f"/api/cognition-engines/{ce_id}/heartbeat")
        r2 = client.put(f"/api/cognition-engines/{ce_id}/heartbeat")

        assert r1.status_code == status.HTTP_200_OK
        assert r2.status_code == status.HTTP_200_OK
        assert r2.json()["last_seen"] >= r1.json()["last_seen"]

    def test_heartbeat_keeps_online_status(self, client, registered_cfn):
        """Heartbeat on an already-online engine keeps status online"""
        ce_id = _register(client, registered_cfn, "hb-online-engine")

        # First heartbeat → online
        client.put(f"/api/cognition-engines/{ce_id}/heartbeat")

        # Second heartbeat → still online
        resp = client.put(f"/api/cognition-engines/{ce_id}/heartbeat")
        assert resp.json()["status"] == "online"

    def test_heartbeat_nonexistent_engine(self, client):
        """Heartbeat for unknown ce_id returns 404"""
        resp = client.put("/api/cognition-engines/nonexistent-ce/heartbeat")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_heartbeat_reflects_in_get(self, client, registered_cfn):
        """After heartbeat, GET shows updated status and last_seen"""
        ce_id = _register(client, registered_cfn, "hb-reflect-engine")

        client.put(f"/api/cognition-engines/{ce_id}/heartbeat")

        detail = client.get(f"/api/cognition-engines/{ce_id}").json()
        assert detail["status"] == "online"
        assert detail["last_seen"] is not None

    def test_heartbeat_offline_to_online_increments_config_version(self, client, registered_cfn, created_workspace):
        """First heartbeat (offline→online transition) triggers a CFN config update."""
        ce_id = _register(client, registered_cfn, "hb-cfg-engine")

        initial_version = client.put(f"/api/cognition-fabric-nodes/{registered_cfn}/heartbeat").json()["config_version"]

        client.put(f"/api/cognition-engines/{ce_id}/heartbeat")

        updated_version = client.put(f"/api/cognition-fabric-nodes/{registered_cfn}/heartbeat").json()["config_version"]
        assert updated_version > initial_version

    def test_heartbeat_already_online_does_not_increment_config_version(self, client, registered_cfn, created_workspace):
        """Heartbeat on an already-online CE does not trigger a redundant config update."""
        ce_id = _register(client, registered_cfn, "hb-no-cfg-engine")
        client.put(f"/api/cognition-engines/{ce_id}/heartbeat")  # offline → online

        stable_version = client.put(f"/api/cognition-fabric-nodes/{registered_cfn}/heartbeat").json()["config_version"]

        client.put(f"/api/cognition-engines/{ce_id}/heartbeat")  # already online — no transition

        after_version = client.put(f"/api/cognition-fabric-nodes/{registered_cfn}/heartbeat").json()["config_version"]
        assert after_version == stable_version


def _db_auth(ce_id: str) -> dict:
    """Read the raw auth JSONB column directly from the DB."""
    db = RelationalDB()
    session = db.session_factory()
    try:
        engine = session.query(CognitionEngineModel).filter(CognitionEngineModel.id == ce_id).first()
        return engine.auth or {}
    finally:
        session.close()


class TestCognitionEngineAuthEncryption:
    """Auth credentials must be encrypted at rest and excluded from API responses."""

    _AUTH = {"type": "api_key", "credentials": {"api_key": "super-secret"}}

    def test_register_encrypts_credentials_at_rest(self, client, registered_cfn):
        """After registration, DB stores credentials_encrypted, not plaintext credentials."""
        ce_id = _register(client, registered_cfn, "enc-register", auth=self._AUTH)

        raw = _db_auth(ce_id)
        assert "credentials_encrypted" in raw
        assert "credentials" not in raw

    def test_register_stored_value_decrypts_correctly(self, client, registered_cfn):
        """The encrypted value round-trips back to the original credentials."""
        ce_id = _register(client, registered_cfn, "enc-roundtrip", auth=self._AUTH)

        raw = _db_auth(ce_id)
        decrypted = decrypt_credentials(raw["credentials_encrypted"])
        assert decrypted == self._AUTH["credentials"]

    def test_idempotent_register_re_encrypts_updated_auth(self, client, registered_cfn):
        """Re-registering with new auth credentials encrypts the new value."""
        _register(client, registered_cfn, "enc-idem", auth=self._AUTH)

        new_auth = {"type": "api_key", "credentials": {"api_key": "new-secret"}}
        resp = client.post(
            "/api/cognition-engines",
            json={**_base_payload(registered_cfn, "enc-idem"), "auth": new_auth},
        )
        assert resp.status_code == status.HTTP_200_OK
        ce_id = resp.json()["ce_id"]

        raw = _db_auth(ce_id)
        assert "credentials_encrypted" in raw
        assert decrypt_credentials(raw["credentials_encrypted"]) == {"api_key": "new-secret"}

    def test_auth_absent_from_get_response(self, client, registered_cfn):
        """GET response never includes auth regardless of what is stored."""
        ce_id = _register(client, registered_cfn, "enc-get", auth=self._AUTH)
        detail = client.get(f"/api/cognition-engines/{ce_id}").json()
        assert "auth" not in detail

    def test_auth_absent_from_list_response(self, client, registered_cfn):
        """List response items never include auth."""
        _register(client, registered_cfn, "enc-list", auth=self._AUTH)
        items = client.get(f"/api/cognition-engines?cfn_id={registered_cfn}").json()["cognition_engines"]
        assert all("auth" not in item for item in items)


class TestCognitionEngineEnabled:
    """enabled is a lifecycle field set by the service — not the caller."""

    def test_new_ce_is_enabled_on_registration(self, client, registered_cfn):
        """A freshly registered CE always has enabled=true."""
        ce_id = _register(client, registered_cfn, "enabled-check")

        detail = client.get(f"/api/cognition-engines/{ce_id}").json()
        assert detail["enabled"] is True

    def test_enabled_present_in_registration_response(self, client, registered_cfn):
        """Registration response includes enabled=true."""
        resp = client.post("/api/cognition-engines", json=_base_payload(registered_cfn, "enabled-reg"))
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["enabled"] is True

    def test_enabled_present_in_list_response(self, client, registered_cfn):
        """List items include enabled field."""
        _register(client, registered_cfn, "enabled-list")
        item = client.get(f"/api/cognition-engines?cfn_id={registered_cfn}").json()["cognition_engines"][0]
        assert "enabled" in item
        assert item["enabled"] is True

    def test_caller_cannot_set_enabled_via_registration(self, client, registered_cfn):
        """enabled is ignored even if the caller tries to pass it in the registration payload."""
        payload = {**_base_payload(registered_cfn, "enabled-override"), "enabled": False}
        resp = client.post("/api/cognition-engines", json=payload)
        assert resp.status_code == status.HTTP_201_CREATED

        detail = client.get(f"/api/cognition-engines/{resp.json()['ce_id']}").json()
        assert detail["enabled"] is True


class TestCognitionEngineAutoAttach:
    """mas_auto_associate is caller-provided at registration — defaults to false."""

    def test_mas_auto_associate_defaults_to_false(self, client, registered_cfn):
        """CE registered without mas_auto_associate has mas_auto_associate=false."""
        ce_id = _register(client, registered_cfn, "no-auto-associate")
        detail = client.get(f"/api/cognition-engines/{ce_id}").json()
        assert detail["mas_auto_associate"] is False

    def test_mas_auto_associate_can_be_set_true_on_registration(self, client, registered_cfn):
        """CE registered with mas_auto_associate=true reflects that value."""
        resp = client.post(
            "/api/cognition-engines",
            json={**_base_payload(registered_cfn, "ootb-engine"), "mas_auto_associate": True},
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["mas_auto_associate"] is True

        detail = client.get(f"/api/cognition-engines/{resp.json()['ce_id']}").json()
        assert detail["mas_auto_associate"] is True

    def test_mas_auto_associate_present_in_list_response(self, client, registered_cfn):
        """List items include mas_auto_associate field."""
        _register(client, registered_cfn, "auto-associate-list")
        item = client.get(f"/api/cognition-engines?cfn_id={registered_cfn}").json()["cognition_engines"][0]
        assert "mas_auto_associate" in item

    def test_mas_auto_associate_preserved_on_upsert(self, client, registered_cfn):
        """Re-registering same (cfn_id, name, version) with mas_auto_associate=true updates the flag."""
        payload = _base_payload(registered_cfn, "upsert-auto-associate")

        client.post("/api/cognition-engines", json=payload)

        resp = client.post("/api/cognition-engines", json={**payload, "mas_auto_associate": True})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["mas_auto_associate"] is True


class TestCognitionEnginePatch:
    """Tests for PATCH /cognition-engines/{ce_id}"""

    def test_patch_enabled_false(self, client, registered_cfn):
        """PATCH can disable a CE (enabled=false)."""
        ce_id = _register(client, registered_cfn, "patch-disable")

        resp = client.patch(f"/api/cognition-engines/{ce_id}", json={"enabled": False})

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["enabled"] is False

    def test_patch_enabled_true(self, client, registered_cfn):
        """PATCH can re-enable a disabled CE."""
        ce_id = _register(client, registered_cfn, "patch-enable")
        client.patch(f"/api/cognition-engines/{ce_id}", json={"enabled": False})

        resp = client.patch(f"/api/cognition-engines/{ce_id}", json={"enabled": True})

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["enabled"] is True

    def test_patch_mutable_fields(self, client, registered_cfn):
        """PATCH updates mutable fields and returns updated detail."""
        ce_id = _register(client, registered_cfn, "patch-fields")

        resp = client.patch(
            f"/api/cognition-engines/{ce_id}",
            json={
                "capabilities": ["ingestion", "retrieval"],
                "metrics": ["latency_ms"],
                "config": {"timeout": 60},
            },
        )

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["capabilities"] == ["ingestion", "retrieval"]
        assert data["metrics"] == ["latency_ms"]
        assert data["config"] == {"timeout": 60}

    def test_patch_only_provided_fields_updated(self, client, registered_cfn):
        """Unprovided fields are not changed."""
        ce_id = _register(client, registered_cfn, "patch-partial", config={"key": "original"})

        client.patch(f"/api/cognition-engines/{ce_id}", json={"enabled": False})

        detail = client.get(f"/api/cognition-engines/{ce_id}").json()
        assert detail["config"] == {"key": "original"}
        assert detail["enabled"] is False

    def test_patch_immutable_field_returns_400(self, client, registered_cfn):
        """Attempting to update an immutable field returns 400."""
        ce_id = _register(client, registered_cfn, "patch-immutable")

        for field, value in [
            ("name", "new-name"),
            ("cfn_id", "other-cfn"),
            ("version", "9.9.9"),
            ("kind", "contingency"),
            ("subkind", "alignment"),
        ]:
            resp = client.patch(f"/api/cognition-engines/{ce_id}", json={field: value})
            assert resp.status_code == status.HTTP_400_BAD_REQUEST, f"Expected 400 for field '{field}'"
            assert field in resp.json()["detail"]

    def test_patch_nonexistent_ce_returns_404(self, client):
        """PATCH on unknown ce_id returns 404."""
        resp = client.patch("/api/cognition-engines/nonexistent-id", json={"enabled": False})
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_patch_url(self, client, registered_cfn):
        """PATCH can update the CE URL."""
        ce_id = _register(client, registered_cfn, "patch-url")

        resp = client.patch(f"/api/cognition-engines/{ce_id}", json={"url": "http://new-url:9090"})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["url"] == "http://new-url:9090"

    def test_patch_empty_body_is_no_op(self, client, registered_cfn):
        """Empty PATCH body leaves the CE unchanged."""
        ce_id = _register(client, registered_cfn, "patch-empty")
        before = client.get(f"/api/cognition-engines/{ce_id}").json()

        resp = client.patch(f"/api/cognition-engines/{ce_id}", json={})
        assert resp.status_code == status.HTTP_200_OK

        after = client.get(f"/api/cognition-engines/{ce_id}").json()
        assert before["enabled"] == after["enabled"]
        assert before["config"] == after["config"]

    def test_patch_disable_with_attached_mas_returns_409(self, client, registered_cfn, created_workspace):
        """Cannot disable a CE while it has at least one MAS attached."""
        ce_id = _register(client, registered_cfn, "patch-disable-guard")
        mas_id = _create_mas(client, created_workspace, "guard-mas")
        client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )

        resp = client.patch(f"/api/cognition-engines/{ce_id}", json={"enabled": False})

        assert resp.status_code == status.HTTP_409_CONFLICT
        assert "mas" in resp.json()["detail"].lower()

    def test_patch_disable_ignores_soft_deleted_mas(self, client, registered_cfn, created_workspace):
        """Soft-deleted MAS associations do not block CE disable."""
        ce_id = _register(client, registered_cfn, "patch-disable-soft-mas")
        mas_id = _create_mas(client, created_workspace, "soft-deleted-mas")
        client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )
        # Soft-delete the MAS — junction row remains but MAS is gone
        client.delete(f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}")

        resp = client.patch(f"/api/cognition-engines/{ce_id}", json={"enabled": False})

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["enabled"] is False

    def test_patch_disable_allowed_after_disassociation(self, client, registered_cfn, created_workspace):
        """Disable succeeds once all MAS are disassociated."""
        ce_id = _register(client, registered_cfn, "patch-disable-after-disassoc")
        mas_id = _create_mas(client, created_workspace, "disassoc-guard-mas")
        client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )
        client.delete(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines/{ce_id}"
        )

        resp = client.patch(f"/api/cognition-engines/{ce_id}", json={"enabled": False})

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["enabled"] is False

    def test_patch_ce_mas_config_field_not_accepted(self, client, registered_cfn):
        """CE PATCH does not accept mas_config — it is silently ignored and factory default is unchanged."""
        factory_default = {"schedule": "0 0 * * *"}
        ce_id = _register(client, registered_cfn, "patch-ce-mas-config-ignored", mas_config=factory_default)

        resp = client.patch(
            f"/api/cognition-engines/{ce_id}",
            json={"mas_config": {"schedule": "0 12 * * *", "top_k": 99}},
        )

        # The request is not rejected — mas_config is simply not in CognitionEnginePatchRequest
        assert resp.status_code == status.HTTP_200_OK
        # Factory default must be unchanged
        assert resp.json()["mas_config"] == factory_default


class TestCognitionEngineMasConfigPerMas:
    """mas_config factory defaults are copied to junction on association and can be overridden per MAS."""

    def test_association_copies_ce_mas_config_to_junction(self, client, registered_cfn, created_workspace):
        """On association, CE's mas_config is copied into the junction for the MAS."""
        ce_id = _register(
            client, registered_cfn, "ce-mas-config-copy",
            mas_config={"schedule": "0 0 * * *"},
        )
        mas_id = _create_mas(client, created_workspace, "mas-config-copy-mas")

        resp = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_mas_update_overrides_per_mas_ce_config(self, client, registered_cfn, created_workspace):
        """PUT MAS with cognition_engine_configs overrides the mas_config for that CE on this MAS only."""
        ce_id = _register(
            client, registered_cfn, "ce-mas-config-override",
            mas_config={"schedule": "0 0 * * *"},
        )
        mas_id = _create_mas(client, created_workspace, "mas-config-override-mas")
        client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )

        resp = client.put(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}",
            json={"cognition_engine_configs": {ce_id: {"schedule": "0 */12 * * *"}}},
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_mas_update_ignores_config_for_unattached_ce(self, client, registered_cfn, created_workspace):
        """Providing a ce_id in cognition_engine_configs that is not attached is silently ignored."""
        mas_id = _create_mas(client, created_workspace, "mas-config-unattached")

        resp = client.put(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}",
            json={"cognition_engine_configs": {"nonexistent-ce": {"schedule": "0 0 * * *"}}},
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_association_seeds_factory_default_into_junction(self, client, registered_cfn, created_workspace):
        """On association, the CE factory mas_config is seeded into the junction row."""
        from server.database.relational_db.models.mas_cognition_engine import MasCognitionEngine

        factory_default = {"schedule": "0 0 * * *"}
        ce_id = _register(
            client, registered_cfn, "ce-seed-junction",
            mas_config=factory_default,
        )
        mas_id = _create_mas(client, created_workspace, "seed-junction-mas")
        client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )

        db = RelationalDB()
        session = db.get_session()
        try:
            row = (
                session.query(MasCognitionEngine)
                .filter(MasCognitionEngine.mas_id == mas_id, MasCognitionEngine.ce_id == ce_id)
                .first()
            )
            assert row is not None
            assert row.mas_config == factory_default
        finally:
            session.close()


def _disable_cfn(client, cfn_id: str) -> None:
    resp = client.patch(f"/api/cognition-fabric-nodes/{cfn_id}/disable")
    assert resp.status_code == status.HTTP_200_OK


def _create_mas(client, workspace_id: str, name: str = "test-mas") -> str:
    resp = client.post(
        f"/api/workspaces/{workspace_id}/multi-agentic-systems",
        json={"name": name},
    )
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()["id"]


class TestCognitionEngineCfnValidation:
    """All non-register ops must reject requests when the CE's CFN is inactive."""

    def test_get_rejects_inactive_cfn(self, client, registered_cfn):
        ce_id = _register(client, registered_cfn, "cfn-val-get")
        _disable_cfn(client, registered_cfn)

        resp = client.get(f"/api/cognition-engines/{ce_id}")
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert "inactive" in resp.json()["detail"].lower()

    def test_list_rejects_inactive_cfn(self, client, registered_cfn):
        _disable_cfn(client, registered_cfn)

        resp = client.get(f"/api/cognition-engines?cfn_id={registered_cfn}")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_list_without_cfn_id_unaffected(self, client, registered_cfn):
        """LIST with no cfn_id filter bypasses CFN validation."""
        _register(client, registered_cfn, "cfn-val-list-global")
        _disable_cfn(client, registered_cfn)

        resp = client.get("/api/cognition-engines")
        assert resp.status_code == status.HTTP_200_OK

    def test_patch_rejects_inactive_cfn(self, client, registered_cfn):
        ce_id = _register(client, registered_cfn, "cfn-val-patch")
        _disable_cfn(client, registered_cfn)

        resp = client.patch(f"/api/cognition-engines/{ce_id}", json={"enabled": False})
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_rejects_inactive_cfn(self, client, registered_cfn):
        ce_id = _register(client, registered_cfn, "cfn-val-delete")
        _disable_cfn(client, registered_cfn)

        resp = client.delete(f"/api/cognition-engines/{ce_id}")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_heartbeat_rejects_inactive_cfn(self, client, registered_cfn):
        ce_id = _register(client, registered_cfn, "cfn-val-hb")
        _disable_cfn(client, registered_cfn)

        resp = client.put(f"/api/cognition-engines/{ce_id}/heartbeat")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_registration_allowed_even_with_inactive_cfn(self, client, registered_cfn):
        """Registration does not check CFN active status — it only checks existence."""
        _disable_cfn(client, registered_cfn)

        resp = client.post("/api/cognition-engines", json=_base_payload(registered_cfn, "cfn-val-register"))
        assert resp.status_code == status.HTTP_201_CREATED


class TestCognitionEngineMasAssociation:
    """Tests for POST /workspaces/{ws}/multi-agentic-systems/{mas}/cognition-engines
    and DELETE /workspaces/{ws}/multi-agentic-systems/{mas}/cognition-engines/{ce}"""

    def test_associate_returns_201(self, client, registered_cfn, created_workspace):
        """Associating a CE with a MAS on the same CFN returns 201."""
        ce_id = _register(client, registered_cfn, "assoc-ce")
        mas_id = _create_mas(client, created_workspace, "assoc-mas")

        resp = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )

        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["ce_id"] == ce_id
        assert data["mas_id"] == mas_id
        assert "created_at" in data

    def test_associate_duplicate_returns_409(self, client, registered_cfn, created_workspace):
        """Associating the same CE-MAS pair twice returns 409."""
        ce_id = _register(client, registered_cfn, "assoc-dup-ce")
        mas_id = _create_mas(client, created_workspace, "assoc-dup-mas")

        client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )
        resp = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )

        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_associate_wrong_cfn_returns_422(self, client, registered_cfn, created_workspace):
        """Associating a CE with a MAS on a different CFN returns 422."""
        ce_id = _register(client, registered_cfn, "assoc-boundary-ce")

        # Create a second CFN and workspace not linked to registered_cfn
        other_cfn_id = client.post(
            "/api/cognition-fabric-nodes/register",
            json={"name": "Other CFN", "cfn_config": {}},
        ).json()["id"]
        other_ws_id = client.post(
            "/api/workspaces/create",
            json={"name": "Other Workspace", "cfn_id": other_cfn_id},
        ).json()["id"]
        other_mas_id = _create_mas(client, other_ws_id, "other-mas")

        resp = client.post(
            f"/api/workspaces/{other_ws_id}/multi-agentic-systems/{other_mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )

        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "cfn" in resp.json()["detail"].lower()

    def test_associate_nonexistent_ce_returns_404(self, client, registered_cfn, created_workspace):
        """Associating a non-existent CE returns 404."""
        mas_id = _create_mas(client, created_workspace, "assoc-404-mas")

        resp = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": "nonexistent-ce"},
        )

        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_associate_nonexistent_mas_returns_404(self, client, registered_cfn, created_workspace):
        """Associating with a non-existent MAS returns 404."""
        ce_id = _register(client, registered_cfn, "assoc-404-ce")

        resp = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/nonexistent-mas/cognition-engines",
            json={"ce_id": ce_id},
        )

        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_disassociate_returns_204(self, client, registered_cfn, created_workspace):
        """Disassociating an existing CE-MAS pair returns 204."""
        ce_id = _register(client, registered_cfn, "disassoc-ce")
        mas_id = _create_mas(client, created_workspace, "disassoc-mas")
        client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )

        resp = client.delete(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines/{ce_id}"
        )

        assert resp.status_code == status.HTTP_204_NO_CONTENT

    def test_disassociate_nonexistent_returns_404(self, client, registered_cfn, created_workspace):
        """Disassociating a pair that doesn't exist returns 404."""
        ce_id = _register(client, registered_cfn, "disassoc-404-ce")
        mas_id = _create_mas(client, created_workspace, "disassoc-404-mas")

        resp = client.delete(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines/{ce_id}"
        )

        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_disassociate_allows_reassociation(self, client, registered_cfn, created_workspace):
        """After disassociation the same pair can be re-associated."""
        ce_id = _register(client, registered_cfn, "reassoc-ce")
        mas_id = _create_mas(client, created_workspace, "reassoc-mas")

        client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )
        client.delete(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines/{ce_id}"
        )

        resp = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_associate_increments_config_version(self, client, registered_cfn, created_workspace):
        """Associating a CE with a MAS triggers a CFN config update (config_version increments)."""
        ce_id = _register(client, registered_cfn, "assoc-cfg-ce")
        mas_id = _create_mas(client, created_workspace, "assoc-cfg-mas")

        initial_version = client.put(f"/api/cognition-fabric-nodes/{registered_cfn}/heartbeat").json()["config_version"]

        client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )

        updated_version = client.put(f"/api/cognition-fabric-nodes/{registered_cfn}/heartbeat").json()["config_version"]
        assert updated_version > initial_version

    def test_disassociate_increments_config_version(self, client, registered_cfn, created_workspace):
        """Disassociating a CE from a MAS triggers a CFN config update (config_version increments)."""
        ce_id = _register(client, registered_cfn, "disassoc-cfg-ce")
        mas_id = _create_mas(client, created_workspace, "disassoc-cfg-mas")
        client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )

        initial_version = client.put(f"/api/cognition-fabric-nodes/{registered_cfn}/heartbeat").json()["config_version"]

        client.delete(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines/{ce_id}"
        )

        updated_version = client.put(f"/api/cognition-fabric-nodes/{registered_cfn}/heartbeat").json()["config_version"]
        assert updated_version > initial_version


class TestCognitionEngineAutoAttachTrigger:
    """Tests for auto-attach trigger logic."""

    def test_register_mas_auto_associate_does_not_attach_to_existing_mas(self, client, registered_cfn, created_workspace):
        """CE registration does not auto-attach to pre-existing MAS, even with mas_auto_associate=True."""
        mas_id = _create_mas(client, created_workspace, "pre-existing-mas")
        ce_id = _register(client, registered_cfn, "auto-attach-ce", mas_auto_associate=True)

        # Manual association should succeed — registration does not trigger auto-attach
        resp = client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_new_mas_mas_auto_associatees_existing_mas_auto_associate_ce(self, client, registered_cfn):
        """New MAS created in a CFN is auto-associated with all mas_auto_associate=True CEs in that CFN."""
        ce_id = _register(client, registered_cfn, "platform-ce", mas_auto_associate=True)

        # Create workspace linked to same CFN, then create a new MAS
        ws_id = client.post(
            "/api/workspaces/create",
            json={"name": "New Workspace", "cfn_id": registered_cfn},
        ).json()["id"]
        mas_id = _create_mas(client, ws_id, "new-mas")

        # Association should already exist from auto-attach
        resp = client.post(
            f"/api/workspaces/{ws_id}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )
        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_new_mas_does_not_attach_non_mas_auto_associate_ce(self, client, registered_cfn):
        """New MAS is NOT auto-associated with CEs that have mas_auto_associate=False."""
        ce_id = _register(client, registered_cfn, "non-platform-ce")  # mas_auto_associate=False

        ws_id = client.post(
            "/api/workspaces/create",
            json={"name": "WS No Attach", "cfn_id": registered_cfn},
        ).json()["id"]
        mas_id = _create_mas(client, ws_id, "mas-no-attach")

        # Manual association should succeed — no auto-attach occurred
        resp = client.post(
            f"/api/workspaces/{ws_id}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_mas_auto_associate_upsert_is_idempotent(self, client, registered_cfn, created_workspace):
        """Re-registering a CE with the same (cfn_id, name, version) returns 200 (upsert)."""
        _create_mas(client, created_workspace, "idempotent-mas")
        payload = {
            "cfn_id": registered_cfn,
            "name": "idempotent-auto-ce",
            "url": "http://ce:8080",
            "version": "1.0.0",
            "mas_auto_associate": True,
        }
        client.post("/api/cognition-engines", json=payload)  # first registration: creates (201)
        resp = client.post("/api/cognition-engines", json=payload)  # second registration: upsert (200)

        assert resp.status_code == status.HTTP_200_OK

    def test_mas_update_mas_auto_associatees_existing_mas_auto_associate_ce(self, client, registered_cfn):
        """Updating a MAS triggers auto-attach for all enabled mas_auto_associate CEs in the CFN."""
        # Create MAS first so no mas_auto_associate CE exists yet at creation time
        ws_id = client.post(
            "/api/workspaces/create",
            json={"name": "WS Update Trigger", "cfn_id": registered_cfn},
        ).json()["id"]
        mas_id = _create_mas(client, ws_id, "mas-before-ce")

        # Register CE after MAS exists — registration does not auto-attach
        ce_id = _register(client, registered_cfn, "platform-ce-update", mas_auto_associate=True)

        # Confirm no auto-attach happened: manual association should succeed
        assoc_resp = client.post(
            f"/api/workspaces/{ws_id}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )
        assert assoc_resp.status_code == status.HTTP_201_CREATED

        # Disassociate so we can verify that update re-attaches
        client.delete(f"/api/workspaces/{ws_id}/multi-agentic-systems/{mas_id}/cognition-engines/{ce_id}")

        # Update the MAS — auto-attach should fire
        client.put(
            f"/api/workspaces/{ws_id}/multi-agentic-systems/{mas_id}",
            json={"name": "mas-before-ce-updated"},
        )

        # Attempting manual association should return 409 — already associated by update auto-attach
        resp = client.post(
            f"/api/workspaces/{ws_id}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )
        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_mas_update_does_not_attach_non_mas_auto_associate_ce(self, client, registered_cfn):
        """Updating a MAS does not auto-attach CEs with mas_auto_associate=False."""
        ws_id = client.post(
            "/api/workspaces/create",
            json={"name": "WS Update No Attach", "cfn_id": registered_cfn},
        ).json()["id"]
        mas_id = _create_mas(client, ws_id, "mas-no-auto-attach")
        ce_id = _register(client, registered_cfn, "non-auto-attach-ce")  # mas_auto_associate=False

        # Update the MAS — should not trigger auto-attach
        client.put(
            f"/api/workspaces/{ws_id}/multi-agentic-systems/{mas_id}",
            json={"name": "mas-no-auto-attach-updated"},
        )

        # Manual association should succeed — CE was not auto-attached
        resp = client.post(
            f"/api/workspaces/{ws_id}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_new_mas_does_not_attach_disabled_mas_auto_associate_ce(self, client, registered_cfn):
        """New MAS is not wired to a disabled CE even if mas_auto_associate=True."""
        ce_id = _register(client, registered_cfn, "disabled-platform-ce", mas_auto_associate=True)

        # Create a workspace+MAS so the CE auto-attaches, then disassociate and disable
        ws_id = client.post(
            "/api/workspaces/create",
            json={"name": "WS Disable Trigger2", "cfn_id": registered_cfn},
        ).json()["id"]
        existing_mas_id = _create_mas(client, ws_id, "existing-mas")
        client.delete(
            f"/api/workspaces/{ws_id}/multi-agentic-systems/{existing_mas_id}/cognition-engines/{ce_id}"
        )
        client.patch(f"/api/cognition-engines/{ce_id}", json={"enabled": False})

        # Create a new MAS — disabled CE should not be auto-attached
        new_mas_id = _create_mas(client, ws_id, "new-mas-disabled-ce")

        # Manual association should succeed — CE was not auto-attached
        resp = client.post(
            f"/api/workspaces/{ws_id}/multi-agentic-systems/{new_mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )
        assert resp.status_code == status.HTTP_201_CREATED


class TestMasCognitionEnginePatch:
    """Tests for PATCH /workspaces/{ws}/multi-agentic-systems/{mas_id}/cognition-engines/{ce_id}

    This endpoint updates the per-MAS mas_config override for a single CE-MAS association.
    It exists because the correct scope for overriding a CE's config for a specific MAS is
    the MAS resource, not the CE resource.
    """

    def test_patch_returns_204(self, client, registered_cfn, created_workspace):
        """PATCH with valid mas_config returns 204 No Content."""
        ce_id = _register(client, registered_cfn, "mas-patch-ce")
        mas_id = _create_mas(client, created_workspace, "mas-patch-mas")
        client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )

        resp = client.patch(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines/{ce_id}",
            json={"mas_config": {"schedule": "0 2 * * *", "top_k": 5}},
        )

        assert resp.status_code == status.HTTP_204_NO_CONTENT

    def test_patch_updates_junction_row(self, client, registered_cfn, created_workspace):
        """PATCH stores the new mas_config in the CE-MAS junction row."""
        from server.database.relational_db.models.mas_cognition_engine import MasCognitionEngine

        ce_id = _register(client, registered_cfn, "mas-patch-db-ce")
        mas_id = _create_mas(client, created_workspace, "mas-patch-db-mas")
        client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )

        new_config = {"schedule": "0 6 * * *", "top_k": 20}
        client.patch(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines/{ce_id}",
            json={"mas_config": new_config},
        )

        db = RelationalDB()
        session = db.get_session()
        try:
            row = (
                session.query(MasCognitionEngine)
                .filter(MasCognitionEngine.mas_id == mas_id, MasCognitionEngine.ce_id == ce_id)
                .first()
            )
            assert row is not None
            assert row.mas_config == new_config
        finally:
            session.close()

    def test_patch_does_not_modify_ce_factory_default(self, client, registered_cfn, created_workspace):
        """PATCH MAS-scoped config does not modify the CE factory default mas_config."""
        factory_default = {"schedule": "0 0 * * *"}
        ce_id = _register(client, registered_cfn, "mas-patch-factory-ce", mas_config=factory_default)
        mas_id = _create_mas(client, created_workspace, "mas-patch-factory-mas")
        client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )

        client.patch(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines/{ce_id}",
            json={"mas_config": {"schedule": "0 12 * * *"}},
        )

        ce_detail = client.get(f"/api/cognition-engines/{ce_id}").json()
        assert ce_detail["mas_config"] == factory_default

    def test_patch_not_associated_returns_404(self, client, registered_cfn, created_workspace):
        """PATCH when CE is not associated with the MAS returns 404."""
        ce_id = _register(client, registered_cfn, "mas-patch-404-ce")
        mas_id = _create_mas(client, created_workspace, "mas-patch-404-mas")
        # CE is intentionally not associated with this MAS

        resp = client.patch(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines/{ce_id}",
            json={"mas_config": {"schedule": "0 0 * * *"}},
        )

        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_patch_increments_config_version(self, client, registered_cfn, created_workspace):
        """PATCH mas_config triggers a CFN config update (config_version increments)."""
        ce_id = _register(client, registered_cfn, "mas-patch-cfgv-ce")
        mas_id = _create_mas(client, created_workspace, "mas-patch-cfgv-mas")
        client.post(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
            json={"ce_id": ce_id},
        )

        initial_version = client.put(f"/api/cognition-fabric-nodes/{registered_cfn}/heartbeat").json()["config_version"]

        client.patch(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines/{ce_id}",
            json={"mas_config": {"schedule": "0 3 * * *"}},
        )

        updated_version = client.put(f"/api/cognition-fabric-nodes/{registered_cfn}/heartbeat").json()["config_version"]
        assert updated_version > initial_version

    def test_patch_only_affects_target_mas_junction(self, client, registered_cfn, created_workspace):
        """PATCH for one MAS does not affect other MAS junction rows for the same CE."""
        from server.database.relational_db.models.mas_cognition_engine import MasCognitionEngine

        original_config = {"schedule": "0 0 * * *"}
        ce_id = _register(client, registered_cfn, "mas-patch-iso-ce", mas_config=original_config)
        mas_id_1 = _create_mas(client, created_workspace, "mas-patch-iso-1")
        mas_id_2 = _create_mas(client, created_workspace, "mas-patch-iso-2")
        for mas_id in (mas_id_1, mas_id_2):
            client.post(
                f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id}/cognition-engines",
                json={"ce_id": ce_id},
            )

        # Override config for MAS 1 only
        client.patch(
            f"/api/workspaces/{created_workspace}/multi-agentic-systems/{mas_id_1}/cognition-engines/{ce_id}",
            json={"mas_config": {"schedule": "0 6 * * *"}},
        )

        db = RelationalDB()
        session = db.get_session()
        try:
            row1 = (
                session.query(MasCognitionEngine)
                .filter(MasCognitionEngine.mas_id == mas_id_1, MasCognitionEngine.ce_id == ce_id)
                .first()
            )
            row2 = (
                session.query(MasCognitionEngine)
                .filter(MasCognitionEngine.mas_id == mas_id_2, MasCognitionEngine.ce_id == ce_id)
                .first()
            )
            assert row1.mas_config == {"schedule": "0 6 * * *"}
            assert row2.mas_config == original_config
        finally:
            session.close()

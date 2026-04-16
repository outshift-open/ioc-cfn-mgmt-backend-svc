# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for /api/audit-events/* endpoints.

These endpoints proxy to ioc-cfn-svc's internal audit API.
All outbound HTTP calls are mocked via unittest.mock.patch.
"""

import uuid
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers — fake cfn-svc responses
# ---------------------------------------------------------------------------


def _make_audit_event(**overrides) -> dict:
    """Build a realistic audit event dict matching the Go Audit struct JSON."""
    event = {
        "id": str(uuid.uuid4()),
        "resource_type": "MAS",
        "resource_identifier": "mas-1",
        "audit_type": "RESOURCE_CREATED",
        "audit_resource_identifier": "mas-1",
        "audit_information": {"status": "SUCCESS"},
        "created_by": str(uuid.uuid4()),
        "created_on": "2026-04-15T09:00:00Z",
        "last_modified_by": str(uuid.uuid4()),
        "last_modified_on": "2026-04-15T09:00:00Z",
    }
    event.update(overrides)
    return event


def _make_list_response(events: list, page: int = 0, page_size: int = 20, total_elements: int = None) -> dict:
    """Build a paginated list response matching the upstream cfn-svc shape."""
    if total_elements is None:
        total_elements = len(events)
    return {
        "data": events,
        "pageInfo": {
            "page": page,
            "pageSize": page_size,
            "pageCount": len(events),
            "totalElements": total_elements,
        },
    }


def _mock_response(status_code: int = 200, json_data=None):
    """Create a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = "" if json_data is None else str(json_data)
    resp.raise_for_status.side_effect = None
    return resp


# ---------------------------------------------------------------------------
# List audit events — GET /api/audit-events/
# ---------------------------------------------------------------------------


class TestListAuditEvents:

    @patch("server.services.audit_cfn_event.requests.get")
    def test_list_returns_200_with_paginated_response(self, mock_get, client: TestClient):
        events = [_make_audit_event(), _make_audit_event()]
        mock_get.return_value = _mock_response(200, _make_list_response(events))

        response = client.get("/api/audit-events/")
        assert response.status_code == 200
        body = response.json()
        assert "data" in body
        assert "pageInfo" in body
        assert isinstance(body["data"], list)
        assert len(body["data"]) == 2

    @patch("server.services.audit_cfn_event.requests.get")
    def test_list_returns_empty_data(self, mock_get, client: TestClient):
        mock_get.return_value = _mock_response(200, _make_list_response([]))

        response = client.get("/api/audit-events/")
        assert response.status_code == 200
        body = response.json()
        assert body["data"] == []
        assert body["pageInfo"]["pageCount"] == 0
        assert body["pageInfo"]["totalElements"] == 0

    @patch("server.services.audit_cfn_event.requests.get")
    def test_list_default_pagination(self, mock_get, client: TestClient):
        mock_get.return_value = _mock_response(200, _make_list_response([]))

        client.get("/api/audit-events/")
        _, kwargs = mock_get.call_args
        params = kwargs.get("params") or mock_get.call_args[1].get("params", {})
        assert params["page"] == 0
        assert params["pageSize"] == 20

    @patch("server.services.audit_cfn_event.requests.get")
    def test_list_custom_pagination(self, mock_get, client: TestClient):
        mock_get.return_value = _mock_response(200, _make_list_response([], page=2, page_size=50))

        client.get("/api/audit-events/?page=2&pageSize=50")
        _, kwargs = mock_get.call_args
        params = kwargs.get("params", {})
        assert params["page"] == 2
        assert params["pageSize"] == 50

    @patch("server.services.audit_cfn_event.requests.get")
    def test_list_filter_resource_type(self, mock_get, client: TestClient):
        mock_get.return_value = _mock_response(200, _make_list_response([]))

        client.get("/api/audit-events/?resource_type=MAS")
        _, kwargs = mock_get.call_args
        params = kwargs.get("params", {})
        assert params["resource_type"] == "MAS"

    @patch("server.services.audit_cfn_event.requests.get")
    def test_list_filter_audit_type(self, mock_get, client: TestClient):
        mock_get.return_value = _mock_response(200, _make_list_response([]))

        client.get("/api/audit-events/?audit_type=SHARED_MEMORY_OPERATION")
        _, kwargs = mock_get.call_args
        params = kwargs.get("params", {})
        assert params["audit_type"] == "SHARED_MEMORY_OPERATION"

    @patch("server.services.audit_cfn_event.requests.get")
    def test_list_both_filters_and_pagination(self, mock_get, client: TestClient):
        mock_get.return_value = _mock_response(200, _make_list_response([], page=1, page_size=25))

        client.get("/api/audit-events/?resource_type=MAS&audit_type=RESOURCE_CREATED&page=1&pageSize=25")
        _, kwargs = mock_get.call_args
        params = kwargs.get("params", {})
        assert params["resource_type"] == "MAS"
        assert params["audit_type"] == "RESOURCE_CREATED"
        assert params["page"] == 1
        assert params["pageSize"] == 25

    def test_list_invalid_page_returns_422(self, client: TestClient):
        response = client.get("/api/audit-events/?page=-1")
        assert response.status_code == 422

    def test_list_invalid_pageSize_returns_422(self, client: TestClient):
        response = client.get("/api/audit-events/?pageSize=0")
        assert response.status_code == 422

    @patch("server.services.audit_cfn_event.requests.get")
    def test_list_pageSize_exceeds_max_clamped(self, mock_get, client: TestClient):
        mock_get.return_value = _mock_response(200, _make_list_response([], page=0, page_size=100, total_elements=0))

        response = client.get("/api/audit-events/?pageSize=9999")
        assert response.status_code == 200
        _, kwargs = mock_get.call_args
        params = kwargs.get("params", {})
        assert params["pageSize"] == 100  # clamped to MAX_PAGE_SIZE (env default 100)

    def test_list_non_integer_page_returns_422(self, client: TestClient):
        response = client.get("/api/audit-events/?page=abc")
        assert response.status_code == 422

    def test_list_non_integer_pageSize_returns_422(self, client: TestClient):
        response = client.get("/api/audit-events/?pageSize=abc")
        assert response.status_code == 422

    @patch("server.services.audit_cfn_event.requests.get")
    def test_list_invalid_resource_type_returns_400(self, mock_get, client: TestClient):
        error_body = {"error": "invalid resource_type: BOGUS. Valid values: COGNITION_ENGINE, POLICY_ENFORCER, MEMORY_PROVIDER, MAS, MAS-AGENT, WORKFLOW, TASK"}
        mock_get.return_value = _mock_response(400, error_body)

        response = client.get("/api/audit-events/?resource_type=BOGUS")
        assert response.status_code == 400
        body = response.json()
        assert "invalid resource_type" in body["error"]

    @patch("server.services.audit_cfn_event.requests.get")
    def test_list_invalid_audit_type_returns_400(self, mock_get, client: TestClient):
        error_body = {"error": "invalid audit_type: BOGUS. Valid values: RESOURCE_CREATED, RESOURCE_UPDATED, RESOURCE_DELETED"}
        mock_get.return_value = _mock_response(400, error_body)

        response = client.get("/api/audit-events/?audit_type=BOGUS")
        assert response.status_code == 400
        body = response.json()
        assert "invalid audit_type" in body["error"]

    @patch("server.services.audit_cfn_event.requests.get")
    def test_list_upstream_error_returns_500(self, mock_get, client: TestClient):
        import requests as req

        mock_get.side_effect = req.exceptions.ConnectionError("cfn-svc unreachable")

        response = client.get("/api/audit-events/")
        assert response.status_code == 500
        body = response.json()
        assert "error" in body

    @patch("server.services.audit_cfn_event.requests.get")
    def test_list_response_fields_match_go_struct(self, mock_get, client: TestClient):
        event = _make_audit_event(
            operation_id="op-123",
            audit_extra_information="some extra info",
        )
        mock_get.return_value = _mock_response(200, _make_list_response([event], total_elements=1))

        response = client.get("/api/audit-events/")
        body = response.json()
        assert len(body["data"]) == 1
        item = body["data"][0]
        assert item["id"] == event["id"]
        assert item["resource_type"] == "MAS"
        assert item["resource_identifier"] == "mas-1"
        assert item["audit_type"] == "RESOURCE_CREATED"
        assert item["audit_resource_identifier"] == "mas-1"
        assert item["audit_information"] == {"status": "SUCCESS"}
        assert item["operation_id"] == "op-123"
        assert item["audit_extra_information"] == "some extra info"
        assert item["created_by"] == event["created_by"]
        assert item["created_on"] == event["created_on"]
        assert item["last_modified_by"] == event["last_modified_by"]
        assert item["last_modified_on"] == event["last_modified_on"]

    @patch("server.services.audit_cfn_event.requests.get")
    def test_list_page_info_fields(self, mock_get, client: TestClient):
        events = [_make_audit_event() for _ in range(3)]
        mock_get.return_value = _mock_response(
            200, _make_list_response(events, page=0, page_size=20, total_elements=157)
        )

        response = client.get("/api/audit-events/")
        body = response.json()
        page_info = body["pageInfo"]
        assert page_info["page"] == 0
        assert page_info["pageSize"] == 20
        assert page_info["pageCount"] == 3
        assert page_info["totalElements"] == 157

    @patch("server.services.audit_cfn_event.requests.get")
    def test_list_omitempty_fields_absent(self, mock_get, client: TestClient):
        event = _make_audit_event()
        # Go omits these when nil
        event.pop("operation_id", None)
        event.pop("audit_information", None)
        event.pop("audit_extra_information", None)
        mock_get.return_value = _mock_response(200, _make_list_response([event]))

        response = client.get("/api/audit-events/")
        body = response.json()
        item = body["data"][0]
        assert "operation_id" not in item or item.get("operation_id") is None
        assert "audit_extra_information" not in item or item.get("audit_extra_information") is None


# ---------------------------------------------------------------------------
# Get audit event by ID — GET /api/audit-events/{eventId}
# ---------------------------------------------------------------------------


class TestGetAuditEvent:

    @patch("server.services.audit_cfn_event.requests.get")
    def test_get_returns_200(self, mock_get, client: TestClient):
        event = _make_audit_event()
        mock_get.return_value = _mock_response(200, event)

        response = client.get(f"/api/audit-events/{event['id']}")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == event["id"]
        assert body["resource_type"] == event["resource_type"]

    @patch("server.services.audit_cfn_event.requests.get")
    def test_get_not_found_returns_404(self, mock_get, client: TestClient):
        mock_get.return_value = _mock_response(404, {"error": "audit event not found"})

        response = client.get(f"/api/audit-events/{uuid.uuid4()}")
        assert response.status_code == 404
        body = response.json()
        assert body["error"] == "audit event not found"

    @patch("server.services.audit_cfn_event.requests.get")
    def test_get_invalid_uuid_returns_400(self, mock_get, client: TestClient):
        mock_get.return_value = _mock_response(400, {"error": "invalid event ID: must be a valid UUID"})

        response = client.get("/api/audit-events/not-a-uuid")
        assert response.status_code == 400
        body = response.json()
        assert body["error"] == "invalid event ID: must be a valid UUID"

    @patch("server.services.audit_cfn_event.requests.get")
    def test_get_response_single_object(self, mock_get, client: TestClient):
        event = _make_audit_event()
        mock_get.return_value = _mock_response(200, event)

        response = client.get(f"/api/audit-events/{event['id']}")
        body = response.json()
        assert isinstance(body, dict)
        assert "id" in body
        assert not isinstance(body, list)

    @patch("server.services.audit_cfn_event.requests.get")
    def test_get_upstream_error_returns_500(self, mock_get, client: TestClient):
        import requests as req

        mock_get.side_effect = req.exceptions.ConnectionError("cfn-svc unreachable")

        response = client.get(f"/api/audit-events/{uuid.uuid4()}")
        assert response.status_code == 500
        body = response.json()
        assert "error" in body

    @patch("server.services.audit_cfn_event.requests.get")
    def test_get_all_fields_present(self, mock_get, client: TestClient):
        event = _make_audit_event(
            operation_id="op-456",
            audit_extra_information="extra",
        )
        mock_get.return_value = _mock_response(200, event)

        response = client.get(f"/api/audit-events/{event['id']}")
        body = response.json()
        expected_keys = {
            "id",
            "resource_type",
            "resource_identifier",
            "audit_type",
            "audit_resource_identifier",
            "audit_information",
            "created_by",
            "created_on",
            "last_modified_by",
            "last_modified_on",
            "operation_id",
            "audit_extra_information",
        }
        assert expected_keys.issubset(set(body.keys()))

    @patch("server.services.audit_cfn_event.requests.get")
    def test_get_calls_correct_upstream_url(self, mock_get, client: TestClient, monkeypatch):
        monkeypatch.setenv("CFN_SVC_URL", "http://test-cfn-svc:9002")
        event_id = str(uuid.uuid4())
        mock_get.return_value = _mock_response(200, _make_audit_event(id=event_id))

        client.get(f"/api/audit-events/{event_id}")
        called_url = mock_get.call_args[0][0]
        assert called_url == f"http://test-cfn-svc:9002/api/internal/mgmt/audit/{event_id}"


# ---------------------------------------------------------------------------
# Pagination env configuration
# ---------------------------------------------------------------------------


class TestPaginationConfig:

    @patch("server.services.audit_cfn_event.requests.get")
    def test_custom_default_page_size_from_env(self, mock_get, client: TestClient, monkeypatch):
        monkeypatch.setenv("DEFAULT_PAGE_SIZE", "50")
        mock_get.return_value = _mock_response(200, _make_list_response([], page=0, page_size=50))

        client.get("/api/audit-events/")
        _, kwargs = mock_get.call_args
        params = kwargs.get("params", {})
        assert params["pageSize"] == 50

    @patch("server.services.audit_cfn_event.requests.get")
    def test_custom_max_page_size_from_env(self, mock_get, client: TestClient, monkeypatch):
        monkeypatch.setenv("MAX_PAGE_SIZE", "50")
        mock_get.return_value = _mock_response(200, _make_list_response([], page=0, page_size=50))

        client.get("/api/audit-events/?pageSize=200")
        _, kwargs = mock_get.call_args
        params = kwargs.get("params", {})
        assert params["pageSize"] == 50  # clamped to custom MAX_PAGE_SIZE

    @patch("server.services.audit_cfn_event.requests.get")
    def test_invalid_env_falls_back_to_defaults(self, mock_get, client: TestClient, monkeypatch):
        monkeypatch.setenv("DEFAULT_PAGE_SIZE", "invalid")
        monkeypatch.setenv("MAX_PAGE_SIZE", "invalid")
        mock_get.return_value = _mock_response(200, _make_list_response([]))

        client.get("/api/audit-events/")
        _, kwargs = mock_get.call_args
        params = kwargs.get("params", {})
        assert params["pageSize"] == 20  # fallback default


# ---------------------------------------------------------------------------
# Service layer retry logic
# ---------------------------------------------------------------------------


class TestServiceRetry:

    @patch("server.services.audit_cfn_event.time.sleep")
    @patch("server.services.audit_cfn_event.requests.get")
    def test_retries_on_connection_error(self, mock_get, mock_sleep, client: TestClient):
        import requests as req

        mock_get.side_effect = req.exceptions.ConnectionError("connection refused")

        response = client.get("/api/audit-events/")
        assert response.status_code == 500
        assert mock_get.call_count == 3  # CFN_SVC_MAX_RETRIES = 3

    @patch("server.services.audit_cfn_event.time.sleep")
    @patch("server.services.audit_cfn_event.requests.get")
    def test_returns_on_first_success(self, mock_get, mock_sleep, client: TestClient):
        mock_get.return_value = _mock_response(200, _make_list_response([]))

        response = client.get("/api/audit-events/")
        assert response.status_code == 200
        assert mock_get.call_count == 1
        mock_sleep.assert_not_called()

# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for /api/internal/diagnostics/* endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestDiagnosticsHealth:
    def test_health_returns_200(self, client: TestClient):
        response = client.get("/api/internal/diagnostics/health")
        assert response.status_code == 200

    def test_health_response_shape(self, client: TestClient):
        body = client.get("/api/internal/diagnostics/health").json()
        assert "status" in body
        assert "service_name" in body
        assert "service_state" in body
        assert "last_updated" in body

    def test_health_status_is_up_or_down(self, client: TestClient):
        body = client.get("/api/internal/diagnostics/health").json()
        assert body["status"] in ("UP", "DOWN")


class TestDiagnosticsInfo:
    def test_info_returns_200(self, client: TestClient):
        response = client.get("/api/internal/diagnostics/info")
        assert response.status_code == 200

    def test_info_response_shape(self, client: TestClient):
        body = client.get("/api/internal/diagnostics/info").json()
        assert "git" in body
        assert "commit" in body["git"]
        assert "branch" in body["git"]
        assert "time" in body["git"]["commit"]
        assert "id" in body["git"]["commit"]

    def test_info_defaults_when_env_not_set(self, client: TestClient, monkeypatch):
        monkeypatch.delenv("GIT_COMMIT_TIME", raising=False)
        monkeypatch.delenv("GIT_COMMIT_SHA", raising=False)
        monkeypatch.delenv("GIT_BRANCH", raising=False)
        body = client.get("/api/internal/diagnostics/info").json()
        assert body["git"]["commit"]["time"] == "unknown"
        assert body["git"]["commit"]["id"] == "unknown"
        assert body["git"]["branch"] == "main"

    def test_info_reads_env_vars(self, client: TestClient, monkeypatch):
        monkeypatch.setenv("GIT_COMMIT_TIME", "2026-01-01T00:00:00Z")
        monkeypatch.setenv("GIT_COMMIT_SHA", "abc1234")
        monkeypatch.setenv("GIT_BRANCH", "release/1.0")
        body = client.get("/api/internal/diagnostics/info").json()
        assert body["git"]["commit"]["time"] == "2026-01-01T00:00:00Z"
        assert body["git"]["commit"]["id"] == "abc1234"
        assert body["git"]["branch"] == "release/1.0"


class TestDiagnosticsMetrics:
    def test_list_metrics_returns_200(self, client: TestClient):
        response = client.get("/api/internal/diagnostics/metrics")
        assert response.status_code == 200

    def test_list_metrics_response_shape(self, client: TestClient):
        body = client.get("/api/internal/diagnostics/metrics").json()
        assert "metrics" in body
        assert isinstance(body["metrics"], list)
        assert len(body["metrics"]) > 0

    def test_list_metrics_entries_have_required_fields(self, client: TestClient):
        body = client.get("/api/internal/diagnostics/metrics").json()
        for entry in body["metrics"]:
            assert "name" in entry
            assert "type" in entry
            assert "help" in entry

    def test_get_metric_by_name_returns_200(self, client: TestClient):
        # python_info is always present in the Prometheus default registry
        response = client.get("/api/internal/diagnostics/metrics/python_info")
        assert response.status_code == 200

    def test_get_metric_by_name_response_shape(self, client: TestClient):
        body = client.get("/api/internal/diagnostics/metrics/python_info").json()
        assert "name" in body
        assert "type" in body
        assert "help" in body
        assert "samples" in body
        assert isinstance(body["samples"], list)

    def test_get_metric_by_name_unknown_returns_404(self, client: TestClient):
        response = client.get("/api/internal/diagnostics/metrics/does_not_exist_xyz")
        assert response.status_code == 404
        assert "error" in response.json()


class TestDiagnosticsLoggers:
    def test_get_loggers_returns_200(self, client: TestClient):
        response = client.get("/api/internal/diagnostics/loggers")
        assert response.status_code == 200

    def test_get_loggers_response_shape(self, client: TestClient):
        body = client.get("/api/internal/diagnostics/loggers").json()
        assert "log-level" in body
        assert "loggers" in body
        assert isinstance(body["loggers"], dict)

    def test_put_loggers_set_root_level(self, client: TestClient):
        response = client.put(
            "/api/internal/diagnostics/loggers",
            json={"module-name": "ROOT", "log-level": "DEBUG"},
        )
        assert response.status_code == 204

    def test_put_loggers_set_module_level(self, client: TestClient):
        response = client.put(
            "/api/internal/diagnostics/loggers",
            json={"module-name": "server.diagnostics", "log-level": "WARNING"},
        )
        assert response.status_code == 204

    def test_put_loggers_invalid_level_returns_400(self, client: TestClient):
        response = client.put(
            "/api/internal/diagnostics/loggers",
            json={"module-name": "ROOT", "log-level": "INVALID_LEVEL"},
        )
        assert response.status_code == 400
        assert "error" in response.json()

    def test_put_loggers_accepts_trace_alias(self, client: TestClient):
        response = client.put(
            "/api/internal/diagnostics/loggers",
            json={"module-name": "ROOT", "log-level": "TRACE"},
        )
        assert response.status_code == 204

    def test_put_loggers_accepts_warn_alias(self, client: TestClient):
        response = client.put(
            "/api/internal/diagnostics/loggers",
            json={"module-name": "ROOT", "log-level": "WARN"},
        )
        assert response.status_code == 204

    def test_put_loggers_level_reflected_in_get(self, client: TestClient):
        client.put(
            "/api/internal/diagnostics/loggers",
            json={"module-name": "ROOT", "log-level": "ERROR"},
        )
        body = client.get("/api/internal/diagnostics/loggers").json()
        assert body["log-level"] == "ERROR"

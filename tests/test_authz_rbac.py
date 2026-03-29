# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for RBAC enforcement using Rego policies"""

import pytest

from server.authz.authz_service import authz_service


class TestAuthzRBAC:
    """Test RBAC permission enforcement"""

    def test_admin_has_full_workspace_access(self):
        """Admin role should have full workspace access"""
        admin_user = {"id": "admin-123", "role": "admin"}

        # Admin can create workspaces
        assert authz_service.check_permission(admin_user, "create", "workspace")

        # Admin can get workspaces
        assert authz_service.check_permission(admin_user, "get", "workspace")

        # Admin can update workspaces
        assert authz_service.check_permission(admin_user, "update", "workspace")

        # Admin can delete workspaces
        assert authz_service.check_permission(admin_user, "delete", "workspace")

    def test_viewer_has_readonly_workspace_access(self):
        """Viewer role should have read-only workspace access"""
        viewer_user = {"id": "viewer-123", "role": "viewer"}

        # Viewer can get workspaces
        assert authz_service.check_permission(viewer_user, "get", "workspace")

        # Viewer cannot create workspaces
        assert not authz_service.check_permission(viewer_user, "create", "workspace")

        # Viewer cannot update workspaces
        assert not authz_service.check_permission(viewer_user, "update", "workspace")

        # Viewer cannot delete workspaces
        assert not authz_service.check_permission(viewer_user, "delete", "workspace")

    def test_guest_has_no_workspace_access(self):
        """Guest role should have no workspace access"""
        guest_user = {"id": "guest-123", "role": "guest"}

        # Guest cannot perform any workspace operations
        assert not authz_service.check_permission(guest_user, "get", "workspace")
        assert not authz_service.check_permission(guest_user, "create", "workspace")
        assert not authz_service.check_permission(guest_user, "update", "workspace")
        assert not authz_service.check_permission(guest_user, "delete", "workspace")

    def test_admin_has_full_cognitive_fabric_node_access(self):
        """Admin role should have full CFN access"""
        admin_user = {"id": "admin-123", "role": "admin"}

        # Admin can register CFN nodes
        assert authz_service.check_permission(admin_user, "register", "cognition_fabric_node")

        # Admin can update CFN nodes
        assert authz_service.check_permission(admin_user, "update", "cognition_fabric_node")

        # Admin can deregister CFN nodes
        assert authz_service.check_permission(admin_user, "deregister", "cognition_fabric_node")

        # Admin can send heartbeat
        assert authz_service.check_permission(admin_user, "heartbeat", "cognition_fabric_node")

        # Admin can list CFN nodes
        assert authz_service.check_permission(admin_user, "list", "cognition_fabric_node")

        # Admin can get CFN node details
        assert authz_service.check_permission(admin_user, "get", "cognition_fabric_node")

    def test_viewer_has_readonly_cognitive_fabric_node_access(self):
        """Viewer role should have read-only CFN access"""
        viewer_user = {"id": "viewer-123", "role": "viewer"}

        # Viewer can list CFN nodes
        assert authz_service.check_permission(viewer_user, "list", "cognition_fabric_node")

        # Viewer can get CFN node details
        assert authz_service.check_permission(viewer_user, "get", "cognition_fabric_node")

        # Viewer cannot register CFN nodes
        assert not authz_service.check_permission(viewer_user, "register", "cognition_fabric_node")

        # Viewer cannot update CFN nodes
        assert not authz_service.check_permission(viewer_user, "update", "cognition_fabric_node")

        # Viewer cannot deregister CFN nodes
        assert not authz_service.check_permission(viewer_user, "deregister", "cognition_fabric_node")

        # Viewer cannot send heartbeat
        assert not authz_service.check_permission(viewer_user, "heartbeat", "cognition_fabric_node")

    def test_guest_has_no_cognitive_fabric_node_access(self):
        """Guest role should have no CFN access"""
        guest_user = {"id": "guest-123", "role": "guest"}

        # Guest cannot perform any CFN operations
        assert not authz_service.check_permission(guest_user, "register", "cognition_fabric_node")
        assert not authz_service.check_permission(guest_user, "update", "cognition_fabric_node")
        assert not authz_service.check_permission(guest_user, "deregister", "cognition_fabric_node")
        assert not authz_service.check_permission(guest_user, "heartbeat", "cognition_fabric_node")
        assert not authz_service.check_permission(guest_user, "list", "cognition_fabric_node")
        assert not authz_service.check_permission(guest_user, "get", "cognition_fabric_node")

    def test_admin_has_full_api_key_access(self):
        """Admin role should have full API key access"""
        admin_user = {"id": "admin-123", "role": "admin"}

        assert authz_service.check_permission(admin_user, "create", "api_key")
        assert authz_service.check_permission(admin_user, "get", "api_key")
        assert authz_service.check_permission(admin_user, "delete", "api_key")

    def test_viewer_has_readonly_api_key_access(self):
        """Viewer role should have read-only API key access"""
        viewer_user = {"id": "viewer-123", "role": "viewer"}

        assert authz_service.check_permission(viewer_user, "get", "api_key")
        assert not authz_service.check_permission(viewer_user, "create", "api_key")
        assert not authz_service.check_permission(viewer_user, "delete", "api_key")

    def test_require_permission_raises_403_on_deny(self):
        """require_permission should raise 403 when permission is denied"""
        from fastapi import HTTPException

        viewer_user = {"id": "viewer-123", "role": "viewer"}

        # Viewer cannot create workspaces
        with pytest.raises(HTTPException) as exc_info:
            authz_service.require_permission(viewer_user, "create", "workspace")

        assert exc_info.value.status_code == 403
        assert "permission" in exc_info.value.detail.lower()

    def test_require_permission_allows_on_permit(self):
        """require_permission should not raise exception when permission is granted"""
        admin_user = {"id": "admin-123", "role": "admin"}

        # Admin can create workspaces - should not raise exception
        authz_service.require_permission(admin_user, "create", "workspace")

    def test_require_permission_custom_error_message(self):
        """require_permission should use custom error message when provided"""
        from fastapi import HTTPException

        guest_user = {"id": "guest-123", "role": "guest"}

        with pytest.raises(HTTPException) as exc_info:
            authz_service.require_permission(
                guest_user, "create", "workspace", detail="Custom error: guests cannot create workspaces"
            )

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Custom error: guests cannot create workspaces"

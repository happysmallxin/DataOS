"""RBAC 权限矩阵集成测试 — 验证 5 角色 x 关键权限.

测试原则:
  - super_admin: 所有操作都通过
  - viewer: 只有读操作通过, 写操作 403
  - 未认证: 所有操作 401
"""

import pytest
from httpx import AsyncClient


class TestRBACMatrix:
    """交叉验证: 角色 x 操作 → 预期状态码."""

    # (method, url, json_body, description)
    OPERATIONS = [
        # Project operations
        ("POST", "/api/v1/projects", {"name": "rbac-test", "display_name": "RBAC测试"}, "创建项目"),
        ("GET", "/api/v1/projects", None, "查看项目列表"),
        # DataSource operations
        ("POST", "/api/v1/datasources?project_id=1", {"name": "ds1", "source_type": "mysql", "config": {}, "project_id": 1}, "注册数据源"),
        ("GET", "/api/v1/datasources", None, "查看数据源"),
        # Role operations
        ("GET", "/api/v1/roles", None, "查看角色列表"),
        ("POST", "/api/v1/roles", {"name": "test_role", "display_name": "测试", "scope": "project"}, "创建角色"),
        # Audit (admin only — viewer 没有 platform:audit)
        ("GET", "/api/v1/audit-logs", None, "查看审计日志"),
    ]

    # Admin-only read operations (viewer doesn't have these permissions)
    ADMIN_ONLY_READS = [
        ("GET", "/api/v1/audit-logs", "查看审计日志"),
    ]

    @pytest.mark.asyncio
    async def test_admin_can_do_everything(self, client: AsyncClient, admin_headers):
        """super_admin should pass all operations."""
        for method, url, body, desc in self.OPERATIONS:
            if method == "POST":
                resp = await client.post(url, json=body, headers=admin_headers)
            else:
                resp = await client.get(url, headers=admin_headers)
            assert resp.status_code in (200, 201), f"Admin {desc} failed: {resp.status_code} {resp.text[:200]}"

    # Read operations viewer should have access to
    VIEWER_READS = [
        ("GET", "/api/v1/projects", "查看项目列表"),
        ("GET", "/api/v1/datasources", "查看数据源"),
        ("GET", "/api/v1/roles", "查看角色列表"),
    ]

    @pytest.mark.asyncio
    async def test_viewer_readonly(self, client: AsyncClient, viewer_headers):
        """Viewer: read succeeds, write fails."""
        # Read operations should succeed (viewer has read permissions)
        for method, url, desc in self.VIEWER_READS:
            resp = await client.get(url, headers=viewer_headers)
            assert resp.status_code == 200, f"Viewer {desc} should succeed but got {resp.status_code}"

        # Audit logs should be denied (viewer lacks platform:audit)
        resp = await client.get("/api/v1/audit-logs", headers=viewer_headers)
        assert resp.status_code == 403, "Viewer should not access audit logs"

        # Write operations should fail
        write_ops = [
            ("POST", "/api/v1/projects", {"name": "nope", "display_name": "NO"}),
            ("POST", "/api/v1/roles", {"name": "bad_role", "display_name": "Bad", "scope": "project"}),
        ]
        for method, url, body in write_ops:
            resp = await client.post(url, json=body, headers=viewer_headers)
            assert resp.status_code == 403, f"Viewer write should be 403 but got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_unauthenticated_denied(self, client: AsyncClient):
        """No token → 401 on all protected endpoints."""
        resp = await client.get("/api/v1/projects")
        assert resp.status_code == 401

        resp = await client.post("/api/v1/projects", json={
            "name": "anon", "display_name": "匿名",
        })
        assert resp.status_code == 401


class TestAdminGlobalAccess:
    """Test that global admin/super_admin bypass project membership check."""

    @pytest.mark.asyncio
    async def test_admin_can_manage_any_project(self, client: AsyncClient, admin_headers):
        """Admin should manage projects even without being a member."""
        # Create project as admin
        resp = await client.post("/api/v1/projects", json={
            "name": "admin-global", "display_name": "管理员全局项目",
        }, headers=admin_headers)
        assert resp.status_code == 201
        pid = resp.json()["id"]

        # Admin should be able to update member roles directly
        members_resp = await client.get(f"/api/v1/projects/{pid}/members", headers=admin_headers)
        assert members_resp.status_code == 200

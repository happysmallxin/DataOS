"""Test projects API — CRUD + members + RBAC."""

import pytest
from httpx import AsyncClient


class TestProjectCRUD:
    @pytest.mark.asyncio
    async def test_create_project_as_admin(self, client: AsyncClient, admin_headers):
        resp = await client.post("/api/v1/projects", json={
            "name": "test-project",
            "display_name": "测试项目",
            "description": "A test project",
        }, headers=admin_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "test-project"
        assert data["display_name"] == "测试项目"
        assert data["status"] == "active"
        assert data["member_count"] == 1

    @pytest.mark.asyncio
    async def test_create_project_duplicate_name(self, client: AsyncClient, admin_headers):
        await client.post("/api/v1/projects", json={
            "name": "dup-project", "display_name": "重复项目",
        }, headers=admin_headers)
        resp = await client.post("/api/v1/projects", json={
            "name": "dup-project", "display_name": "重复项目2",
        }, headers=admin_headers)
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_create_project_as_viewer_fails(self, client: AsyncClient, viewer_headers):
        """Viewer doesn't have project:create permission."""
        resp = await client.post("/api/v1/projects", json={
            "name": "viewer-project", "display_name": "Viewer项目",
        }, headers=viewer_headers)
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_list_projects(self, client: AsyncClient, admin_headers):
        # Create a project first
        await client.post("/api/v1/projects", json={
            "name": "p1", "display_name": "项目1",
        }, headers=admin_headers)

        resp = await client.get("/api/v1/projects", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_get_project_detail(self, client: AsyncClient, admin_headers):
        create_resp = await client.post("/api/v1/projects", json={
            "name": "detail-project", "display_name": "详情项目",
        }, headers=admin_headers)
        pid = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/projects/{pid}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "detail-project"

    @pytest.mark.asyncio
    async def test_freeze_project(self, client: AsyncClient, admin_headers):
        create_resp = await client.post("/api/v1/projects", json={
            "name": "freeze-me", "display_name": "冻结测试",
        }, headers=admin_headers)
        pid = create_resp.json()["id"]

        resp = await client.post(f"/api/v1/projects/{pid}/freeze", headers=admin_headers)
        assert resp.status_code == 200

        # Verify status changed
        get_resp = await client.get(f"/api/v1/projects/{pid}", headers=admin_headers)
        assert get_resp.json()["status"] == "frozen"

    @pytest.mark.asyncio
    async def test_delete_project(self, client: AsyncClient, admin_headers):
        create_resp = await client.post("/api/v1/projects", json={
            "name": "delete-me", "display_name": "删除测试",
        }, headers=admin_headers)
        pid = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/projects/{pid}", headers=admin_headers)
        assert resp.status_code == 200


class TestProjectMembers:
    @pytest.mark.asyncio
    async def test_list_members(self, client: AsyncClient, admin_headers):
        create_resp = await client.post("/api/v1/projects", json={
            "name": "member-test", "display_name": "成员测试",
        }, headers=admin_headers)
        pid = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/projects/{pid}/members", headers=admin_headers)
        assert resp.status_code == 200
        members = resp.json()
        assert len(members) == 1  # Creator is auto-added

    @pytest.mark.asyncio
    async def test_add_member(self, client: AsyncClient, admin_headers):
        create_resp = await client.post("/api/v1/projects", json={
            "name": "add-member-test", "display_name": "加人测试",
        }, headers=admin_headers)
        pid = create_resp.json()["id"]

        # Add viewer user (id=2) as editor
        resp = await client.post(f"/api/v1/projects/{pid}/members", json={
            "user_id": 2,
            "role_id": 4,  # editor role
        }, headers=admin_headers)
        assert resp.status_code == 201

        # Verify members increased
        members_resp = await client.get(f"/api/v1/projects/{pid}/members", headers=admin_headers)
        assert len(members_resp.json()) == 2

    @pytest.mark.asyncio
    async def test_remove_member(self, client: AsyncClient, admin_headers):
        create_resp = await client.post("/api/v1/projects", json={
            "name": "remove-test", "display_name": "移除测试",
        }, headers=admin_headers)
        pid = create_resp.json()["id"]

        # Add then remove viewer
        await client.post(f"/api/v1/projects/{pid}/members", json={
            "user_id": 2, "role_id": 4,
        }, headers=admin_headers)

        resp = await client.delete(f"/api/v1/projects/{pid}/members/2", headers=admin_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_cannot_remove_creator(self, client: AsyncClient, admin_headers):
        create_resp = await client.post("/api/v1/projects", json={
            "name": "no-remove-creator", "display_name": "不可移除创建者",
        }, headers=admin_headers)
        pid = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/projects/{pid}/members/1", headers=admin_headers)
        assert resp.status_code == 400


class TestProjectTransfer:
    @pytest.mark.asyncio
    async def test_transfer_project(self, client: AsyncClient, admin_headers):
        create_resp = await client.post("/api/v1/projects", json={
            "name": "transfer-me", "display_name": "转让测试",
        }, headers=admin_headers)
        pid = create_resp.json()["id"]

        # Add viewer as member first
        await client.post(f"/api/v1/projects/{pid}/members", json={
            "user_id": 2, "role_id": 5,  # viewer role id
        }, headers=admin_headers)

        # Transfer ownership
        resp = await client.post(f"/api/v1/projects/{pid}/transfer", json={
            "new_owner_id": 2,
        }, headers=admin_headers)
        assert resp.status_code == 200

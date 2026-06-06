"""Test auth API endpoints."""

import pytest
from httpx import AsyncClient


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "admin123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"] is not None
        assert "super_admin" in data["user"]["global_roles"]
        assert "project:create" in data["user"]["permissions"]

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "wrongpassword",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "username": "nobody", "password": "test123",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_returns_accessible_projects(self, client: AsyncClient):
        """Login should return accessible_projects array."""
        resp = await client.post("/api/v1/auth/login", json={
            "username": "admin", "password": "admin123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "accessible_projects" in data["user"]

    @pytest.mark.asyncio
    async def test_me_endpoint(self, client: AsyncClient, admin_headers):
        resp = await client.get("/api/v1/auth/me", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["username"] == "admin"

    @pytest.mark.asyncio
    async def test_me_without_token(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_register(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "username": "newuser", "password": "newpass123",
        })
        assert resp.status_code == 201
        assert resp.json()["username"] == "newuser"

    @pytest.mark.asyncio
    async def test_register_duplicate(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "username": "admin", "password": "test123",
        })
        assert resp.status_code == 409

"""Test RBAC permission dependency functions."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_user_permissions,
    get_user_global_roles,
    ROLE_LEVEL,
    GLOBAL_ADMIN_ROLES,
)


class TestPermissionQueries:
    @pytest.mark.asyncio
    async def test_admin_has_all_permissions(self, seeded_session: AsyncSession):
        """Admin (super_admin) should have all seeded permissions."""
        perms = await get_user_permissions(user_id=1, db=seeded_session)  # admin
        assert "project:create" in perms
        assert "project:delete" in perms
        assert "datasource:read" in perms
        assert "user:create" in perms

    @pytest.mark.asyncio
    async def test_viewer_has_readonly_permissions(self, seeded_session: AsyncSession):
        """Viewer should only have read permissions."""
        perms = await get_user_permissions(user_id=2, db=seeded_session)  # viewer
        assert "project:read" in perms
        assert "datasource:read" in perms
        assert "project:create" not in perms
        assert "project:delete" not in perms
        assert "datasource:delete" not in perms

    @pytest.mark.asyncio
    async def test_viewer_with_project_context(self, seeded_session: AsyncSession):
        """Viewer permissions with project_id (no project membership yet)."""
        perms = await get_user_permissions(user_id=2, db=seeded_session, project_id=1)
        # Should still have global read permissions even without project membership
        assert "project:read" in perms

    @pytest.mark.asyncio
    async def test_unknown_user_has_no_permissions(self, seeded_session: AsyncSession):
        """User with no roles should have empty permissions."""
        perms = await get_user_permissions(user_id=999, db=seeded_session)
        assert len(perms) == 0


class TestGlobalRoles:
    @pytest.mark.asyncio
    async def test_admin_global_roles(self, seeded_session: AsyncSession):
        roles = await get_user_global_roles(user_id=1, db=seeded_session)
        role_names = {r.name for r in roles}
        assert "super_admin" in role_names

    @pytest.mark.asyncio
    async def test_viewer_global_roles(self, seeded_session: AsyncSession):
        roles = await get_user_global_roles(user_id=2, db=seeded_session)
        role_names = {r.name for r in roles}
        assert "viewer" in role_names


class TestRoleLevels:
    def test_super_admin_is_highest(self):
        assert ROLE_LEVEL["super_admin"] > ROLE_LEVEL["admin"]
        assert ROLE_LEVEL["super_admin"] == 5

    def test_viewer_is_lowest(self):
        assert ROLE_LEVEL["viewer"] == 1

    def test_admin_roles_are_global(self):
        assert "super_admin" in GLOBAL_ADMIN_ROLES
        assert "admin" in GLOBAL_ADMIN_ROLES
        assert "viewer" not in GLOBAL_ADMIN_ROLES

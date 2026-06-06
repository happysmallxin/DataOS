"""Test fixtures — async SQLite in-memory DB + FastAPI TestClient."""

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Override settings before importing app
import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"  # won't be used in tests

from app.core.database import Base, get_db
from app.core.security import hash_password, create_access_token
from app.models.user import User
from app.models.role import Role, Permission, RolePermission
from app.models.project_member import UserRole

# Test DB engine
TEST_DB_URL = "sqlite+aiosqlite://"
test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


# ============================================================
# Seed data
# ============================================================
SEED_ROLES = [
    {"name": "super_admin", "display_name": "超级管理员", "scope": "global", "is_system": True},
    {"name": "admin", "display_name": "平台管理员", "scope": "global", "is_system": True},
    {"name": "project_owner", "display_name": "项目负责人", "scope": "project", "is_system": True},
    {"name": "editor", "display_name": "编辑者", "scope": "project", "is_system": True},
    {"name": "viewer", "display_name": "查看者", "scope": "project", "is_system": True},
]

SEED_PERMISSIONS = [
    ("user:create", "user", "create"),
    ("user:read", "user", "read"),
    ("project:create", "project", "create"),
    ("project:read", "project", "read"),
    ("project:update", "project", "update"),
    ("project:delete", "project", "delete"),
    ("project:manage_members", "project", "manage_members"),
    ("datasource:create", "datasource", "create"),
    ("datasource:read", "datasource", "read"),
    ("datasource:delete", "datasource", "delete"),
    ("role:read", "role", "read"),
    ("platform:audit", "platform", "audit"),
    ("platform:health", "platform", "health"),
]


async def seed_rbac(session: AsyncSession):
    """Create roles, permissions, and assign super_admin to admin user."""
    roles = {}
    for r in SEED_ROLES:
        role = Role(**r)
        session.add(role)
        roles[r["name"]] = role
    await session.flush()

    perms = {}
    for name, resource, action in SEED_PERMISSIONS:
        p = Permission(name=name, resource=resource, action=action)
        session.add(p)
        perms[name] = p
    await session.flush()

    # super_admin: all permissions
    for p in perms.values():
        session.add(RolePermission(role_id=roles["super_admin"].id, permission_id=p.id))

    # project_owner: project/* + datasource/*
    for perm_name in ["project:read", "project:update", "project:delete", "project:manage_members",
                       "datasource:create", "datasource:read", "datasource:delete",
                       "role:read", "platform:health"]:
        if perm_name in perms:
            session.add(RolePermission(
                role_id=roles["project_owner"].id, permission_id=perms[perm_name].id
            ))

    # editor: read + some write, no delete
    for perm_name in ["project:read", "datasource:create", "datasource:read", "platform:health"]:
        if perm_name in perms:
            session.add(RolePermission(
                role_id=roles["editor"].id, permission_id=perms[perm_name].id
            ))

    # viewer: read only
    for perm_name in ["project:read", "datasource:read", "platform:health"]:
        if perm_name in perms:
            session.add(RolePermission(
                role_id=roles["viewer"].id, permission_id=perms[perm_name].id
            ))

    await session.flush()
    return roles, perms


# ============================================================
# Fixtures
# ============================================================
@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh test DB session per test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def seeded_session(db_session: AsyncSession) -> AsyncSession:
    """DB session with RBAC seed data."""
    await seed_rbac(db_session)
    # Create admin user
    admin = User(
        username="admin", email="admin@test.local",
        hashed_password=hash_password("admin123"),
        display_name="管理员", is_active=True, is_superuser=True,
    )
    db_session.add(admin)
    await db_session.flush()

    # Assign super_admin role
    roles_result = await db_session.execute(
        __import__("sqlalchemy").select(Role).where(Role.name == "super_admin")
    )
    super_admin_role = roles_result.scalar_one()
    db_session.add(UserRole(user_id=admin.id, role_id=super_admin_role.id))

    # Create a regular viewer user
    viewer = User(
        username="viewer", email="viewer@test.local",
        hashed_password=hash_password("viewer123"),
        display_name="查看者", is_active=True,
    )
    db_session.add(viewer)
    await db_session.flush()

    roles_result2 = await db_session.execute(
        __import__("sqlalchemy").select(Role).where(Role.name == "viewer")
    )
    viewer_role = roles_result2.scalar_one()
    db_session.add(UserRole(user_id=viewer.id, role_id=viewer_role.id))

    await db_session.commit()
    return db_session


@pytest_asyncio.fixture(scope="function")
async def client(seeded_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client with overridden DB dependency."""
    from app.main import app

    async def override_get_db():
        yield seeded_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def admin_token(seeded_session):
    """JWT token for admin user."""
    return create_access_token(data={"sub": "1", "username": "admin"})


@pytest.fixture
def viewer_token(seeded_session):
    """JWT token for viewer user."""
    return create_access_token(data={"sub": "2", "username": "viewer"})


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def viewer_headers(viewer_token):
    return {"Authorization": f"Bearer {viewer_token}"}

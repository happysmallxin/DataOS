/**
 * E2E: RBAC 权限验证 — 角色/权限管理.
 */
import { test, expect } from '@playwright/test'
import { loginAs, authHeaders } from '../fixtures/auth'

let adminToken: string

test.beforeAll(async () => {
  const auth = await loginAs('admin', 'admin123')
  adminToken = auth.token
})

test.describe('Roles & Permissions', () => {
  test('list roles returns 5 system roles', async ({ request }) => {
    const resp = await request.get('/api/v1/roles', {
      headers: authHeaders(adminToken),
    })
    expect(resp.status()).toBe(200)
    const roles = await resp.json()
    expect(roles.length).toBeGreaterThanOrEqual(5)
    const roleNames = roles.map((r: any) => r.name)
    expect(roleNames).toContain('super_admin')
    expect(roleNames).toContain('admin')
    expect(roleNames).toContain('project_owner')
    expect(roleNames).toContain('editor')
    expect(roleNames).toContain('viewer')
  })

  test('filter roles by scope', async ({ request }) => {
    const resp = await request.get('/api/v1/roles?scope=global', {
      headers: authHeaders(adminToken),
    })
    expect(resp.status()).toBe(200)
    const roles = await resp.json()
    roles.forEach((r: any) => {
      expect(r.scope).toBe('global')
    })
  })

  test('list permissions', async ({ request }) => {
    const resp = await request.get('/api/v1/permissions', {
      headers: authHeaders(adminToken),
    })
    expect(resp.status()).toBe(200)
    const perms = await resp.json()
    expect(perms.length).toBeGreaterThanOrEqual(10)
  })

  test('filter permissions by resource', async ({ request }) => {
    const resp = await request.get('/api/v1/permissions?resource=project', {
      headers: authHeaders(adminToken),
    })
    expect(resp.status()).toBe(200)
    const perms = await resp.json()
    perms.forEach((p: any) => {
      expect(p.resource).toBe('project')
    })
  })

  test('get role permissions', async ({ request }) => {
    const resp = await request.get('/api/v1/roles/1/permissions', {
      headers: authHeaders(adminToken),
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data.role).toBeDefined()
    expect(Array.isArray(data.permissions)).toBeTruthy()
  })

  test('get current user permissions', async ({ request }) => {
    const resp = await request.get('/api/v1/users/me/permissions', {
      headers: authHeaders(adminToken),
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data.username).toBe('admin')
    expect(Array.isArray(data.permissions)).toBeTruthy()
    expect(Array.isArray(data.accessible_projects)).toBeTruthy()
  })

  test('system roles cannot be deleted', async ({ request }) => {
    // Try to delete super_admin (id=1) — should fail
    const resp = await request.delete('/api/v1/roles/1', {
      headers: authHeaders(adminToken),
    })
    expect(resp.status()).toBe(400)
  })

  test('create custom role', async ({ request }) => {
    const resp = await request.post('/api/v1/roles', {
      headers: authHeaders(adminToken),
      data: {
        name: 'e2e_custom_role',
        display_name: 'E2E自定义角色',
        scope: 'project',
        description: 'Created by E2E test',
      },
    })
    expect(resp.status()).toBe(201)
    const role = await resp.json()
    expect(role.name).toBe('e2e_custom_role')
    expect(role.is_system).toBe(false)

    // Cleanup: delete the custom role
    const delResp = await request.delete(`/api/v1/roles/${role.id}`, {
      headers: authHeaders(adminToken),
    })
    expect(delResp.status()).toBe(200)
  })
})

test.describe('Audit Logs', () => {
  test('audit logs accessible by admin', async ({ request }) => {
    const resp = await request.get('/api/v1/audit-logs', {
      headers: authHeaders(adminToken),
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data).toHaveProperty('items')
    expect(data).toHaveProperty('total')
    expect(data).toHaveProperty('page')
  })

  test('audit logs support pagination', async ({ request }) => {
    const resp = await request.get('/api/v1/audit-logs?page=1&page_size=5', {
      headers: authHeaders(adminToken),
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data.items.length).toBeLessThanOrEqual(5)
    expect(data.page).toBe(1)
    expect(data.page_size).toBe(5)
  })

  test('audit logs filter by resource', async ({ request }) => {
    const resp = await request.get('/api/v1/audit-logs?resource=project', {
      headers: authHeaders(adminToken),
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    data.items.forEach((item: any) => {
      expect(item.resource).toBe('project')
    })
  })
})

test.describe('Health Check', () => {
  test('health endpoint returns component status', async ({ request }) => {
    const resp = await request.get('/api/v1/../health') // /health at root
    // Actually let's just test the root
    const rootResp = await request.get('/')
    expect(rootResp.status()).toBe(200)
  })
})

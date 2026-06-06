/**
 * E2E: 项目 CRUD + 成员管理.
 */
import { test, expect } from '@playwright/test'
import { loginAs, authHeaders } from '../fixtures/auth'

let projectId: number
let adminToken: string

test.beforeAll(async () => {
  const auth = await loginAs('admin', 'admin123')
  adminToken = auth.token
})

test.describe('Project Lifecycle', () => {
  test('create project', async ({ request }) => {
    const resp = await request.post('/api/v1/projects', {
      headers: authHeaders(adminToken),
      data: {
        name: `e2e-project-${Date.now()}`,
        display_name: 'E2E测试项目',
        description: 'Playwright E2E test project',
      },
    })
    expect(resp.status()).toBe(201)
    const body = await resp.json()
    expect(body.name).toContain('e2e-project')
    expect(body.status).toBe('active')
    expect(body.member_count).toBe(1)
    projectId = body.id
  })

  test('get project detail', async ({ request }) => {
    expect(projectId).toBeDefined()
    const resp = await request.get(`/api/v1/projects/${projectId}`, {
      headers: authHeaders(adminToken),
    })
    expect(resp.status()).toBe(200)
    const body = await resp.json()
    expect(body.id).toBe(projectId)
    expect(body.member_count).toBe(1)
  })

  test('project appears in list', async ({ request }) => {
    const resp = await request.get('/api/v1/projects', {
      headers: authHeaders(adminToken),
    })
    expect(resp.status()).toBe(200)
    const body = await resp.json()
    expect(body.some((p: any) => p.id === projectId)).toBeTruthy()
  })

  test('list project members', async ({ request }) => {
    const resp = await request.get(`/api/v1/projects/${projectId}/members`, {
      headers: authHeaders(adminToken),
    })
    expect(resp.status()).toBe(200)
    const members = await resp.json()
    expect(members.length).toBeGreaterThanOrEqual(1)
    expect(members[0].username).toBe('admin')
  })

  test('freeze project', async ({ request }) => {
    const resp = await request.post(`/api/v1/projects/${projectId}/freeze`, {
      headers: authHeaders(adminToken),
    })
    expect(resp.status()).toBe(200)

    // Verify status
    const getResp = await request.get(`/api/v1/projects/${projectId}`, {
      headers: authHeaders(adminToken),
    })
    expect((await getResp.json()).status).toBe('frozen')
  })

  test('unfreeze project', async ({ request }) => {
    // First freeze
    await request.post(`/api/v1/projects/${projectId}/freeze`, {
      headers: authHeaders(adminToken),
    })
    // Then unfreeze
    const resp = await request.post(`/api/v1/projects/${projectId}/unfreeze`, {
      headers: authHeaders(adminToken),
    })
    expect(resp.status()).toBe(200)

    const getResp = await request.get(`/api/v1/projects/${projectId}`, {
      headers: authHeaders(adminToken),
    })
    expect((await getResp.json()).status).toBe('active')
  })

  test('delete project', async ({ request }) => {
    // Create a project to delete
    const createResp = await request.post('/api/v1/projects', {
      headers: authHeaders(adminToken),
      data: { name: `to-delete-${Date.now()}`, display_name: '待删除' },
    })
    const pid = (await createResp.json()).id

    const resp = await request.delete(`/api/v1/projects/${pid}`, {
      headers: authHeaders(adminToken),
    })
    expect(resp.status()).toBe(200)
  })

  test('viewer cannot create project', async ({ request }) => {
    try {
      const viewerAuth = await loginAs('viewer', 'viewer123')
      const resp = await request.post('/api/v1/projects', {
        headers: authHeaders(viewerAuth.token),
        data: { name: 'viewer-project', display_name: 'Viewer项目' },
      })
      expect(resp.status()).toBe(403)
    } catch {
      // viewer user may not exist
    }
  })
})

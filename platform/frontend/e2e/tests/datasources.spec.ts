/**
 * E2E: 数据源管理 — 注册/查看/删除.
 */
import { test, expect } from '@playwright/test'
import { loginAs, authHeaders } from '../fixtures/auth'

let adminToken: string

test.beforeAll(async () => {
  const auth = await loginAs('admin', 'admin123')
  adminToken = auth.token
})

test.describe('DataSource Management', () => {
  test('list datasource types', async ({ request }) => {
    const resp = await request.get('/api/v1/datasources/types', {
      headers: authHeaders(adminToken),
    })
    expect(resp.status()).toBe(200)
    const types = await resp.json()
    expect(types.length).toBeGreaterThanOrEqual(10)
    expect(types.some((t: any) => t.type === 'mysql')).toBeTruthy()
    expect(types.some((t: any) => t.type === 'postgresql')).toBeTruthy()
  })

  test('register and list datasource', async ({ request }) => {
    // Create
    const createResp = await request.post('/api/v1/datasources', {
      headers: authHeaders(adminToken),
      data: {
        project_id: 1,
        name: `e2e-mysql-${Date.now()}`,
        source_type: 'mysql',
        config: {
          host: '192.168.1.100',
          port: 3306,
          database: 'testdb',
          username: 'root',
          password: 'secret123',
        },
        description: 'E2E test datasource',
      },
    })
    expect(createResp.status()).toBe(201)
    const ds = await createResp.json()
    expect(ds.name).toContain('e2e-mysql')

    // Verify password is masked in response
    expect(ds.config.password).toBe('***')

    // List (without specifying project, gets all)
    const listResp = await request.get('/api/v1/datasources', {
      headers: authHeaders(adminToken),
    })
    expect(listResp.status()).toBe(200)
    const list = await listResp.json()
    expect(list.some((d: any) => d.id === ds.id)).toBeTruthy()

    // List with project filter
    const filteredResp = await request.get('/api/v1/datasources?project_id=1', {
      headers: authHeaders(adminToken),
    })
    expect(filteredResp.status()).toBe(200)
  })

  test('delete datasource', async ({ request }) => {
    // Create then delete
    const createResp = await request.post('/api/v1/datasources', {
      headers: authHeaders(adminToken),
      data: {
        project_id: 1,
        name: `to-delete-${Date.now()}`,
        source_type: 'mysql',
        config: { host: 'localhost' },
      },
    })
    const dsId = (await createResp.json()).id

    const deleteResp = await request.delete(`/api/v1/datasources/${dsId}`, {
      headers: authHeaders(adminToken),
    })
    expect(deleteResp.status()).toBe(200)
  })
})

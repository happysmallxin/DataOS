/**
 * Auth fixtures — 获取不同角色的 API token.
 */
import { APIRequestContext, request } from '@playwright/test'

const BASE_URL = 'http://localhost:8001'

export interface AuthContext {
  token: string
  userId: number
  username: string
  permissions: string[]
  roles: string[]
}

export async function loginAs(
  username: string,
  password: string,
): Promise<AuthContext> {
  const ctx = await request.newContext({ baseURL: BASE_URL })
  const resp = await ctx.post('/api/v1/auth/login', {
    data: { username, password },
  })
  const body = await resp.json()
  await ctx.dispose()

  return {
    token: body.access_token,
    userId: body.user?.id || 0,
    username: body.user?.username || username,
    permissions: body.user?.permissions || [],
    roles: body.user?.global_roles || [],
  }
}

export function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` }
}

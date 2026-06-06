/** API 客户端 — 封装后端 REST API 调用. */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截器 — 自动附加 JWT Token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// v1.5: 401 自动刷新 token (Token Rotation)
let isRefreshing = false
let refreshQueue: Array<{ resolve: (token: string) => void; reject: (err: unknown) => void }> = []

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const originalRequest = err.config

    if (err.response?.status === 401 && !originalRequest._retry) {
      const refreshToken = localStorage.getItem('refresh_token')

      if (refreshToken && !originalRequest.url?.includes('/auth/refresh')) {
        originalRequest._retry = true

        if (!isRefreshing) {
          isRefreshing = true
          try {
            const resp = await axios.post('/api/v1/auth/refresh', { refresh_token: refreshToken })
            const { access_token, refresh_token: newRefresh } = resp.data
            localStorage.setItem('access_token', access_token)
            if (newRefresh) localStorage.setItem('refresh_token', newRefresh)

            // 重放排队的请求
            refreshQueue.forEach(({ resolve }) => resolve(access_token))
            refreshQueue = []

            originalRequest.headers.Authorization = `Bearer ${access_token}`
            return api(originalRequest)
          } catch {
            refreshQueue.forEach(({ reject }) => reject(new Error('refresh failed')))
            refreshQueue = []
            localStorage.removeItem('access_token')
            localStorage.removeItem('refresh_token')
            if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
              window.location.href = '/login'
            }
            return Promise.reject(err)
          } finally {
            isRefreshing = false
          }
        } else {
          // 已有刷新进行中, 排队等待
          return new Promise((resolve, reject) => {
            refreshQueue.push({
              resolve: (token: string) => {
                originalRequest.headers.Authorization = `Bearer ${token}`
                resolve(api(originalRequest))
              },
              reject,
            })
          })
        }
      }

      // 无 refresh token, 直接跳转登录
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
        window.location.href = '/login'
      }
    }

    return Promise.reject(err)
  },
)

// ============================================================
// Auth
// ============================================================
export const authAPI = {
  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password }),
  me: () => api.get('/auth/me'),
  register: (username: string, password: string) =>
    api.post('/auth/register', { username, password }),
}

// ============================================================
// Projects
// ============================================================
export const projectsAPI = {
  list: (params?: Record<string, any>) => api.get('/projects', { params }),
  get: (id: number) => api.get(`/projects/${id}`),
  create: (data: { name: string; display_name: string; description?: string }) =>
    api.post('/projects', data),
  update: (id: number, data: Record<string, any>) => api.put(`/projects/${id}`, data),
  delete: (id: number) => api.delete(`/projects/${id}`),
  transfer: (id: number, newOwnerId: number) =>
    api.post(`/projects/${id}/transfer`, { new_owner_id: newOwnerId }),
  freeze: (id: number) => api.post(`/projects/${id}/freeze`),
  unfreeze: (id: number) => api.post(`/projects/${id}/unfreeze`),
  listMembers: (id: number) => api.get(`/projects/${id}/members`),
  addMember: (id: number, data: { user_id: number; role_id: number }) =>
    api.post(`/projects/${id}/members`, data),
  updateMember: (projectId: number, userId: number, data: { role_id: number }) =>
    api.put(`/projects/${projectId}/members/${userId}`, data),
  removeMember: (projectId: number, userId: number) =>
    api.delete(`/projects/${projectId}/members/${userId}`),
  auditLogs: (id: number, params?: Record<string, any>) =>
    api.get(`/projects/${id}/audit-logs`, { params }),
}

// ============================================================
// DataSources
// ============================================================
export const datasourcesAPI = {
  list: (projectId?: number) =>
    api.get('/datasources', { params: projectId ? { project_id: projectId } : {} }),
  create: (data: {
    project_id?: number; name: string; source_type: string
    config: Record<string, unknown>; description?: string
  }) => api.post('/datasources', data),
  delete: (id: number) => api.delete(`/datasources/${id}`),
  types: () => api.get('/datasources/types'),
}

// ============================================================
// Roles & Permissions
// ============================================================
export const rolesAPI = {
  list: () => api.get('/roles'),
  create: (data: { name: string; display_name: string; scope: string; description?: string }) =>
    api.post('/roles', data),
  update: (id: number, data: Record<string, any>) => api.put(`/roles/${id}`, data),
  delete: (id: number) => api.delete(`/roles/${id}`),
  getPermissions: (id: number) => api.get(`/roles/${id}/permissions`),
  listPermissions: () => api.get('/permissions'),
}

// ============================================================
// User Management
// ============================================================
export const usersAPI = {
  myPermissions: (projectId?: number) =>
    api.get('/users/me/permissions', { params: projectId ? { project_id: projectId } : {} }),
  assignRole: (userId: number, roleId: number) =>
    api.post(`/users/${userId}/roles`, { role_id: roleId }),
  revokeRole: (userId: number, roleId: number) =>
    api.delete(`/users/${userId}/roles/${roleId}`),
}

// ============================================================
// Audit Logs
// ============================================================
export const auditAPI = {
  list: (params?: Record<string, any>) => api.get('/audit-logs', { params }),
}

// ============================================================
// Crawlers (P2)
// ============================================================
export const crawlersAPI = {
  list: (projectId: number, status?: string) =>
    api.get('/crawlers', { params: { project_id: projectId, status } }),
  get: (id: number) => api.get(`/crawlers/${id}`),
  create: (data: { project_id: number; name: string; target_url?: string; framework?: string; config?: Record<string, unknown>; description?: string }) =>
    api.post('/crawlers', data),
  update: (id: number, data: Record<string, unknown>) =>
    api.put(`/crawlers/${id}`, data),
  delete: (id: number) => api.delete(`/crawlers/${id}`),
  start: (id: number) => api.post(`/crawlers/${id}/start`),
  stop: (id: number) => api.post(`/crawlers/${id}/stop`),
}

// ============================================================
// Health
// ============================================================
export const healthAPI = {
  check: () => api.get('/health'),
}

// ============================================================
// Quality
// ============================================================
export const qualityAPI = {
  check: (data: { data: Record<string, unknown>[]; rules: Record<string, unknown>[]; rule_ids?: number[] }) =>
    api.post('/quality/check', data),
  ruleTemplates: () => api.get('/quality/rule-templates'),
  // P1: 持久化规则 CRUD
  listRules: (projectId: number, ruleType?: string) =>
    api.get('/quality/rules', { params: { project_id: projectId, rule_type: ruleType } }),
  createRule: (data: { project_id: number; name: string; rule_type: string; target_column?: string; config?: Record<string, unknown>; description?: string }) =>
    api.post('/quality/rules', data),
  updateRule: (id: number, data: Record<string, unknown>) =>
    api.put(`/quality/rules/${id}`, data),
  deleteRule: (id: number) => api.delete(`/quality/rules/${id}`),
}

// ============================================================
// Cleaning
// ============================================================
export const cleaningAPI = {
  profile: (data: { data: Record<string, unknown>[]; sample_size?: number }) =>
    api.post('/cleaning/profile', data),
  runPipeline: (data: {
    data: Record<string, unknown>[]
    stages: Record<string, unknown>[]
    pipeline_name?: string
    pipeline_id?: number
  }) => api.post('/cleaning/pipelines/run', data),
  stages: () => api.get('/cleaning/stages'),
  // P1: 持久化 Pipeline CRUD
  listPipelines: (projectId: number, status?: string) =>
    api.get('/cleaning/pipelines', { params: { project_id: projectId, status } }),
  getPipeline: (id: number) => api.get(`/cleaning/pipelines/${id}`),
  createPipeline: (data: { project_id: number; name: string; description?: string; stages?: Record<string, unknown>[] }) =>
    api.post('/cleaning/pipelines', data),
  updatePipeline: (id: number, data: Record<string, unknown>) =>
    api.put(`/cleaning/pipelines/${id}`, data),
  deletePipeline: (id: number) => api.delete(`/cleaning/pipelines/${id}`),
}

export default api

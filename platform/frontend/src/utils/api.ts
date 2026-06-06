/** API 客户端 — 封装后端 REST API 调用. */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截器 — 自动附加 JWT Token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('dataos_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器 — 统一错误处理
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('dataos_token')
      // 暂不跳转登录，Phase 2 完善
    }
    return Promise.reject(err)
  }
)

// ============================================================
// Auth
// ============================================================
export const authAPI = {
  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password }),
  me: () => api.get('/auth/me'),
}

// ============================================================
// Projects
// ============================================================
export const projectsAPI = {
  list: () => api.get('/projects'),
  create: (data: { name: string; display_name: string; description?: string }) =>
    api.post('/projects', data),
}

// ============================================================
// DataSources
// ============================================================
export const datasourcesAPI = {
  list: (projectId?: number) =>
    api.get('/datasources', { params: projectId ? { project_id: projectId } : {} }),
  create: (data: { project_id?: number; name: string; source_type: string; config: Record<string, unknown>; description?: string }) =>
    api.post('/datasources', data),
  types: () => api.get('/datasources/types'),
}

// ============================================================
// Health
// ============================================================
export const healthAPI = {
  check: () => api.get('/health'),
}

export default api

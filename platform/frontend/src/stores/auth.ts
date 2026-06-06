/**
 * Zustand Auth Store — 用户认证状态 + 权限 + 可访问项目.
 */
import { create } from 'zustand'
import apiClient from '../utils/api'

interface UserInfo {
  id: number
  username: string
  email: string
  display_name: string | null
  is_superuser: boolean
}

interface AccessibleProject {
  id: number
  name: string
  display_name: string
  role: string
}

interface AuthState {
  // 状态
  token: string | null
  user: UserInfo | null
  permissions: string[]
  globalRoles: string[]
  accessibleProjects: AccessibleProject[]
  isAuthenticated: boolean
  loading: boolean

  // 操作
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  fetchPermissions: (projectId?: number) => Promise<void>
  hasPermission: (perm: string) => boolean
  hasAnyPermission: (...perms: string[]) => boolean
  hasAllPermissions: (...perms: string[]) => boolean
  isGlobalAdmin: () => boolean
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: localStorage.getItem('access_token'),
  user: null,
  permissions: [],
  globalRoles: [],
  accessibleProjects: [],
  isAuthenticated: !!localStorage.getItem('access_token'),
  loading: false,

  login: async (username: string, password: string) => {
    set({ loading: true })
    try {
      const resp = await apiClient.post('/auth/login', { username, password })
      const { access_token, user } = resp.data

      localStorage.setItem('access_token', access_token)
      set({
        token: access_token,
        user: user ? {
          id: user.id,
          username: user.username,
          email: user.email,
          display_name: user.display_name,
          is_superuser: user.is_superuser,
        } : null,
        permissions: user?.permissions || [],
        globalRoles: user?.global_roles || [],
        accessibleProjects: user?.accessible_projects || [],
        isAuthenticated: true,
        loading: false,
      })
    } catch (error) {
      set({ loading: false })
      throw error
    }
  },

  logout: () => {
    localStorage.removeItem('access_token')
    set({
      token: null,
      user: null,
      permissions: [],
      globalRoles: [],
      accessibleProjects: [],
      isAuthenticated: false,
    })
  },

  fetchPermissions: async (projectId?: number) => {
    try {
      const params = projectId ? { project_id: projectId } : {}
      const resp = await apiClient.get('/users/me/permissions', { params })
      set({
        permissions: resp.data.permissions || [],
        globalRoles: resp.data.global_roles || [],
        accessibleProjects: resp.data.accessible_projects || [],
      })
    } catch {
      // Silently fail — 权限获取失败不应阻塞页面渲染
    }
  },

  hasPermission: (perm: string) => {
    const { permissions, globalRoles } = get()
    if (globalRoles.some(r => ['super_admin', 'admin'].includes(r))) return true
    return permissions.includes(perm)
  },

  hasAnyPermission: (...perms: string[]) => {
    return perms.some(p => get().hasPermission(p))
  },

  hasAllPermissions: (...perms: string[]) => {
    return perms.every(p => get().hasPermission(p))
  },

  isGlobalAdmin: () => {
    return get().globalRoles.some(r => ['super_admin', 'admin'].includes(r))
  },
}))

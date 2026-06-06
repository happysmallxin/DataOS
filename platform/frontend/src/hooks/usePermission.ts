/**
 * usePermission Hook — 权限驱动的 UI 控制.
 *
 * 用法:
 *   const { can, canAny, canAll, projectRole, isGlobalAdmin } = usePermission(projectId?)
 *   {can('project:create') && <Button>新建项目</Button>}
 */
import { useAuthStore } from '../stores/auth'

interface PermissionHook {
  can: (perm: string) => boolean
  canAny: (...perms: string[]) => boolean
  canAll: (...perms: string[]) => boolean
  projectRole: string | null
  isGlobalAdmin: boolean
}

export function usePermission(projectId?: number): PermissionHook {
  const { hasPermission, hasAnyPermission, hasAllPermissions, isGlobalAdmin, accessibleProjects } =
    useAuthStore()

  const projectRole = projectId
    ? accessibleProjects.find((p) => p.id === projectId)?.role ?? null
    : null

  return {
    can: hasPermission,
    canAny: hasAnyPermission,
    canAll: hasAllPermissions,
    projectRole,
    isGlobalAdmin: isGlobalAdmin(),
  }
}

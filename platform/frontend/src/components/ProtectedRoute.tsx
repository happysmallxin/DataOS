/**
 * ProtectedRoute — 路由守卫.
 *
 * - 未登录 → 跳转 /login
 * - 无权限 → 显示 403 页面
 * - 有权限 → 渲染子组件
 */
import { Navigate, useLocation } from 'react-router-dom'
import { Result, Button } from 'antd'
import { useAuthStore } from '../stores/auth'

interface ProtectedRouteProps {
  children: React.ReactNode
  permission?: string // 可选: 需要的权限 (resource:action)
}

export default function ProtectedRoute({ children, permission }: ProtectedRouteProps) {
  const { isAuthenticated, hasPermission } = useAuthStore()
  const location = useLocation()

  // 未登录 → 登录页
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  // 需要特定权限但用户没有 → 403
  if (permission && !hasPermission(permission)) {
    return (
      <Result
        status="403"
        title="403"
        subTitle={`需要权限: ${permission}`}
        extra={
          <Button type="primary" onClick={() => window.history.back()}>
            返回上一页
          </Button>
        }
      />
    )
  }

  return <>{children}</>
}

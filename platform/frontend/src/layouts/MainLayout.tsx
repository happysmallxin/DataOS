import { useState, useEffect } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Button, Avatar, Dropdown, theme } from 'antd'
import {
  DashboardOutlined,
  DatabaseOutlined,
  BugOutlined,
  SafetyCertificateOutlined,
  ApiOutlined,
  SettingOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  LogoutOutlined,
  UserOutlined,
  ProjectOutlined,
  TeamOutlined,
  AuditOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '../stores/auth'

const { Header, Sider, Content } = Layout

interface MenuItem {
  key: string
  icon: React.ReactNode
  label: string
  permission?: string
}

const allMenuItems: MenuItem[] = [
  { key: '/', icon: <DashboardOutlined />, label: '工作台' },
  { key: '/projects', icon: <ProjectOutlined />, label: '项目管理', permission: 'project:read' },
  { key: '/datasources', icon: <DatabaseOutlined />, label: '数据源管理', permission: 'datasource:read' },
  { key: '/crawlers', icon: <BugOutlined />, label: '网页爬取', permission: 'crawler:read' },
  { key: '/quality', icon: <SafetyCertificateOutlined />, label: '数据质量', permission: 'quality:read' },
  { key: '/data-service', icon: <ApiOutlined />, label: '数据服务', permission: 'api:read' },
  { key: '/roles', icon: <TeamOutlined />, label: '角色权限', permission: 'role:read' },
  { key: '/audit-logs', icon: <AuditOutlined />, label: '审计日志', permission: 'platform:audit' },
  { key: '/settings', icon: <SettingOutlined />, label: '平台设置' },
]

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { token } = theme.useToken()
  // 直接订阅 globalRoles + permissions 以确保登录后重渲染
  const { user, logout, hasPermission, globalRoles, permissions, isAuthenticated } = useAuthStore()

  // 登录后如果权限为空，从 API 重新拉取 (安全网, 防止 Zustand 状态丢失)
  useEffect(() => {
    if (isAuthenticated && permissions.length === 0 && globalRoles.length === 0) {
      useAuthStore.getState().fetchPermissions()
    }
  }, [isAuthenticated, permissions.length, globalRoles.length])

  // 按权限过滤菜单 — 使用直接读取的 globalRoles 做超级管理员判定
  const isAdmin = globalRoles.some(r => ['super_admin', 'admin'].includes(r))
  const menuItems = allMenuItems
    .filter((item) => !item.permission || isAdmin || permissions.includes(item.permission))
    .map(({ key, icon, label }) => ({ key, icon, label }))

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {/* 侧边栏 */}
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        theme="light"
        width={220}
        style={{
          borderRight: `1px solid ${token.colorBorderSecondary}`,
          boxShadow: '1px 0 4px rgba(0,0,0,0.04)',
        }}
      >
        {/* Logo */}
        <div className="flex items-center h-16 px-5 border-b border-gray-100">
          <div className="w-8 h-8 bg-dataos-500 rounded-lg flex items-center justify-center flex-shrink-0">
            <span className="text-white font-bold text-sm">D</span>
          </div>
          {!collapsed && (
            <span className="ml-3 font-semibold text-lg text-gray-800 whitespace-nowrap">
              DataOS
            </span>
          )}
        </div>

        <Menu
          mode="inline"
          selectedKeys={[location.pathname === '/' ? '/' : `/${location.pathname.split('/')[1]}`]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ border: 'none', marginTop: 8 }}
        />
      </Sider>

      <Layout>
        {/* 顶部导航 */}
        <Header
          style={{
            padding: '0 24px',
            background: token.colorBgContainer,
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            height: 64,
          }}
        >
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
          />

          <Dropdown
            menu={{
              items: [
                { key: 'profile', icon: <UserOutlined />, label: user?.display_name || user?.username || '用户' },
                { type: 'divider' },
                { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', danger: true },
              ],
              onClick: ({ key }) => {
                if (key === 'logout') handleLogout()
              },
            }}
          >
            <div className="flex items-center gap-2 cursor-pointer">
              <Avatar size="small" icon={<UserOutlined />} />
              <span className="text-sm text-gray-600">
                {user?.display_name || user?.username || '管理员'}
              </span>
            </div>
          </Dropdown>
        </Header>

        {/* 内容区 */}
        <Content
          style={{
            margin: 24,
            padding: 24,
            background: token.colorBgContainer,
            borderRadius: token.borderRadiusLG,
            minHeight: 280,
            overflow: 'auto',
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}

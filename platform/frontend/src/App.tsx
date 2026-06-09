import { Routes, Route, Navigate } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import MainLayout from './layouts/MainLayout'
import ProtectedRoute from './components/ProtectedRoute'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import DataSources from './pages/DataSources'
import DataQuality from './pages/DataQuality'
import DataCleaning from './pages/DataCleaning'
import DataModeling from './pages/DataModeling'
import DatasetGeneration from './pages/DatasetGeneration'
import Settings from './pages/Settings'
import Projects from './pages/Projects'
import ProjectDetail from './pages/ProjectDetail'
import UserManagement from './pages/UserManagement'
import AuditLogs from './pages/AuditLogs'

export default function App() {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#2563eb',
          borderRadius: 6,
        },
      }}
    >
      <Routes>
        {/* 公开路由 */}
        <Route path="/login" element={<Login />} />

        {/* 受保护路由 */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route
            path="projects"
            element={
              <ProtectedRoute permission="project:read">
                <Projects />
              </ProtectedRoute>
            }
          />
          <Route
            path="projects/:id"
            element={
              <ProtectedRoute permission="project:read">
                <ProjectDetail />
              </ProtectedRoute>
            }
          />
          <Route
            path="datasources"
            element={
              <ProtectedRoute permission="datasource:read">
                <DataSources />
              </ProtectedRoute>
            }
          />
          <Route
            path="cleaning"
            element={
              <ProtectedRoute permission="project:read">
                <DataCleaning />
              </ProtectedRoute>
            }
          />
          <Route
            path="modeling"
            element={
              <ProtectedRoute permission="project:read">
                <DataModeling />
              </ProtectedRoute>
            }
          />
          <Route
            path="datasets"
            element={
              <ProtectedRoute permission="api:read">
                <DatasetGeneration />
              </ProtectedRoute>
            }
          />
          <Route
            path="quality"
            element={
              <ProtectedRoute permission="quality:read">
                <DataQuality />
              </ProtectedRoute>
            }
          />
          <Route
            path="users"
            element={
              <ProtectedRoute permission="user:read">
                <UserManagement />
              </ProtectedRoute>
            }
          />
          <Route
            path="audit-logs"
            element={
              <ProtectedRoute permission="platform:audit">
                <AuditLogs />
              </ProtectedRoute>
            }
          />
          <Route path="settings" element={<Settings />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ConfigProvider>
  )
}

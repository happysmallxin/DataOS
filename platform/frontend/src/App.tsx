import { Routes, Route, Navigate } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import MainLayout from './layouts/MainLayout'
import Dashboard from './pages/Dashboard'
import DataSources from './pages/DataSources'
import Crawlers from './pages/Crawlers'
import DataQuality from './pages/DataQuality'
import DataAPI from './pages/DataAPI'
import Settings from './pages/Settings'

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
        <Route path="/" element={<MainLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="datasources" element={<DataSources />} />
          <Route path="crawlers" element={<Crawlers />} />
          <Route path="quality" element={<DataQuality />} />
          <Route path="api" element={<DataAPI />} />
          <Route path="settings" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ConfigProvider>
  )
}

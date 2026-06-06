/**
 * 审计日志页 — admin only, 分页/筛选.
 */
import { useEffect, useState } from 'react'
import { Card, Table, Tag, Space, Typography, Select, Input, Button, message, Popover } from 'antd'
import { SearchOutlined, ReloadOutlined } from '@ant-design/icons'
import apiClient from '../api/client'

const { Title } = Typography

interface AuditEntry {
  id: number
  user_id: number
  username: string
  project_id: number | null
  resource: string
  action: string
  target_id: number | null
  target_name: string | null
  detail: any
  ip_address: string | null
  created_at: string
}

const resourceOptions = [
  { value: '', label: '全部资源' },
  { value: 'project', label: '项目' },
  { value: 'datasource', label: '数据源' },
  { value: 'member', label: '成员' },
  { value: 'role', label: '角色' },
  { value: 'permission', label: '权限' },
]

const actionColors: Record<string, string> = {
  create: 'green',
  update: 'blue',
  delete: 'red',
  grant: 'purple',
  revoke: 'orange',
  transfer: 'gold',
}

export default function AuditLogs() {
  const [data, setData] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)
  const [resource, setResource] = useState('')
  const [action, setAction] = useState('')

  const fetchData = async () => {
    setLoading(true)
    try {
      const params: any = { page, page_size: pageSize }
      if (resource) params.resource = resource
      if (action) params.action = action
      const resp = await apiClient.get('/audit-logs', { params })
      setData(resp.data.items || [])
      setTotal(resp.data.total || 0)
    } catch {
      message.error('获取审计日志失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [page, pageSize, resource, action])

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 70 },
    { title: '操作人', dataIndex: 'username', width: 100 },
    { title: '项目', dataIndex: 'project_id', width: 70, render: (v: number | null) => v || '-' },
    {
      title: '资源', dataIndex: 'resource', width: 90,
      render: (r: string) => <Tag>{r}</Tag>,
    },
    {
      title: '操作', dataIndex: 'action', width: 80,
      render: (a: string) => <Tag color={actionColors[a] || 'default'}>{a}</Tag>,
    },
    { title: '目标', dataIndex: 'target_name', ellipsis: true },
    {
      title: '详情', dataIndex: 'detail', width: 60,
      render: (d: any) => d ? (
        <Popover content={<pre style={{ fontSize: 11, maxHeight: 200, overflow: 'auto' }}>{JSON.stringify(d, null, 2)}</pre>} title="变更详情">
          <a>查看</a>
        </Popover>
      ) : '-',
    },
    { title: 'IP', dataIndex: 'ip_address', width: 120, render: (v: string | null) => v || '-' },
    { title: '时间', dataIndex: 'created_at', width: 170, render: (d: string) => new Date(d).toLocaleString() },
  ]

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <Title level={4} style={{ margin: 0 }}>审计日志</Title>
        <Space>
          <Select
            value={resource}
            onChange={(v) => { setResource(v); setPage(1) }}
            options={resourceOptions}
            style={{ width: 120 }}
          />
          <Select
            value={action}
            onChange={(v) => { setAction(v); setPage(1) }}
            options={[
              { value: '', label: '全部操作' },
              ...Object.entries(actionColors).map(([k, v]) => ({ value: k, label: k })),
            ]}
            style={{ width: 120 }}
          />
          <Button icon={<ReloadOutlined />} onClick={fetchData}>刷新</Button>
        </Space>
      </div>

      <Card>
        <Table
          dataSource={data}
          columns={columns}
          rowKey="id"
          size="small"
          loading={loading}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p, ps) => { setPage(p); setPageSize(ps) },
          }}
          scroll={{ x: 1000 }}
        />
      </Card>
    </div>
  )
}

import { Card, Table, Tag, Button, Space, Typography, Input } from 'antd'
import { PlusOutlined, SearchOutlined, CopyOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

const { Title, Text } = Typography

interface APIEndpoint {
  key: string
  name: string
  method: 'GET' | 'POST' | 'PUT' | 'DELETE'
  path: string
  source: string
  status: 'published' | 'draft'
  calls: number
}

const methodColors: Record<string, string> = {
  GET: 'green',
  POST: 'blue',
  PUT: 'orange',
  DELETE: 'red',
}

const columns: ColumnsType<APIEndpoint> = [
  { title: 'API 名称', dataIndex: 'name', key: 'name' },
  {
    title: '方法',
    dataIndex: 'method',
    key: 'method',
    render: (m: string) => <Tag color={methodColors[m]}>{m}</Tag>,
  },
  {
    title: '路径',
    dataIndex: 'path',
    key: 'path',
    render: (p: string) => (
      <Space>
        <Text code>{p}</Text>
        <Button size="small" type="text" icon={<CopyOutlined />} />
      </Space>
    ),
  },
  { title: '数据源', dataIndex: 'source', key: 'source' },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    render: (s: string) => <Tag color={s === 'published' ? 'green' : 'default'}>{s === 'published' ? '已发布' : '草稿'}</Tag>,
  },
  { title: '今日调用', dataIndex: 'calls', key: 'calls', render: (v: number) => v.toLocaleString() },
  {
    title: '操作',
    key: 'action',
    render: () => (
      <Space>
        <a>测试</a>
        <a>编辑</a>
        <a>文档</a>
      </Space>
    ),
  },
]

const mockData: APIEndpoint[] = [
  { key: '1', name: '设备列表', method: 'GET', path: '/api/v1/equipment', source: 'MySQL - 设备库', status: 'published', calls: 2340 },
  { key: '2', name: '告警记录查询', method: 'GET', path: '/api/v1/alarms', source: 'MongoDB - 日志库', status: 'published', calls: 1890 },
  { key: '3', name: '创建工单', method: 'POST', path: '/api/v1/workorders', source: 'MySQL - 工单库', status: 'published', calls: 456 },
  { key: '4', name: '行业数据查询', method: 'GET', path: '/api/v1/industry-data', source: '爬虫 - 行业新闻', status: 'draft', calls: 0 },
]

export default function DataAPI() {
  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <Title level={4} style={{ margin: 0 }}>数据服务 API</Title>
        <Space>
          <Input placeholder="搜索 API..." prefix={<SearchOutlined />} style={{ width: 240 }} />
          <Button type="primary" icon={<PlusOutlined />}>新建 API</Button>
        </Space>
      </div>
      <Card>
        <Table columns={columns} dataSource={mockData} />
      </Card>
    </div>
  )
}

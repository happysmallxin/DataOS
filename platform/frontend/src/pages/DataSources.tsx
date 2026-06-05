import { Card, Table, Tag, Button, Space, Typography } from 'antd'
import { PlusOutlined, ReloadOutlined, DatabaseOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

const { Title } = Typography

interface DataSourceRecord {
  key: string
  name: string
  type: string
  host: string
  status: 'connected' | 'disconnected' | 'pending'
  lastSync: string
}

const columns: ColumnsType<DataSourceRecord> = [
  { title: '名称', dataIndex: 'name', key: 'name' },
  {
    title: '类型',
    dataIndex: 'type',
    key: 'type',
    render: (type: string) => (
      <Tag icon={<DatabaseOutlined />} color="blue">{type}</Tag>
    ),
  },
  { title: '连接地址', dataIndex: 'host', key: 'host' },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    render: (status: string) => {
      const map: Record<string, { color: string; text: string }> = {
        connected: { color: 'green', text: '已连接' },
        disconnected: { color: 'red', text: '断开' },
        pending: { color: 'orange', text: '待配置' },
      }
      return <Tag color={map[status]?.color}>{map[status]?.text}</Tag>
    },
  },
  { title: '最后同步', dataIndex: 'lastSync', key: 'lastSync' },
  {
    title: '操作',
    key: 'action',
    render: () => (
      <Space>
        <a>测试连接</a>
        <a>同步</a>
        <a>配置</a>
      </Space>
    ),
  },
]

const mockData: DataSourceRecord[] = [
  { key: '1', name: '生产 MySQL', type: 'MySQL', host: '192.168.1.100:3306', status: 'connected', lastSync: '5 分钟前' },
  { key: '2', name: 'MongoDB 日志库', type: 'MongoDB', host: '192.168.1.101:27017', status: 'connected', lastSync: '1 小时前' },
  { key: '3', name: 'Kafka 设备消息', type: 'Kafka', host: 'kafka:9092', status: 'pending', lastSync: '-' },
]

export default function DataSources() {
  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <Title level={4} style={{ margin: 0 }}>数据源管理</Title>
        <Space>
          <Button icon={<ReloadOutlined />}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />}>新增数据源</Button>
        </Space>
      </div>
      <Card>
        <Table columns={columns} dataSource={mockData} />
      </Card>
    </div>
  )
}

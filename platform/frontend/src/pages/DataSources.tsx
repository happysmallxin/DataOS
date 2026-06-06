import { useEffect, useState } from 'react'
import { Card, Table, Tag, Button, Space, Typography, Modal, Form, Input, Select, message } from 'antd'
import { PlusOutlined, ReloadOutlined, DatabaseOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { datasourcesAPI } from '../utils/api'

const { Title } = Typography

interface DataSourceRecord {
  id: number
  name: string
  source_type: string
  config: Record<string, unknown>
  status: string
  last_sync_at: string | null
  created_at: string
}

const sourceTypeOptions = [
  { value: 'mysql', label: 'MySQL' },
  { value: 'postgresql', label: 'PostgreSQL' },
  { value: 'mongodb', label: 'MongoDB' },
  { value: 'redis', label: 'Redis' },
  { value: 'kafka', label: 'Kafka' },
  { value: 'api', label: 'REST API' },
  { value: 's3', label: 'S3/MinIO' },
  { value: 'crawler', label: '网页爬虫' },
  { value: 'file', label: '文件上传' },
]

export default function DataSources() {
  const [data, setData] = useState<DataSourceRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()

  const fetchData = async () => {
    setLoading(true)
    try {
      const res = await datasourcesAPI.list()
      setData(res.data)
    } catch {
      message.error('获取数据源列表失败，请检查后端是否启动')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  const handleCreate = async () => {
    try {
      const values = await form.validateFields()
      await datasourcesAPI.create({
        name: values.name,
        source_type: values.source_type,
        config: {
          host: values.host || 'localhost',
          port: values.port || 3306,
          database: values.database || '',
          username: values.username || '',
        },
        description: values.description,
      })
      message.success('数据源创建成功')
      setModalOpen(false)
      form.resetFields()
      fetchData()
    } catch (err: any) {
      if (err?.response) message.error(err.response.data?.detail || '创建失败')
    }
  }

  const statusMap: Record<string, { color: string; text: string }> = {
    active: { color: 'green', text: '已连接' },
    error: { color: 'red', text: '异常' },
    disabled: { color: 'default', text: '已禁用' },
  }

  const columns: ColumnsType<DataSourceRecord> = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    {
      title: '类型', dataIndex: 'source_type', key: 'source_type',
      render: (t: string) => <Tag icon={<DatabaseOutlined />} color="blue">{t}</Tag>,
    },
    {
      title: '连接地址',
      key: 'host',
      render: (_, r) => `${r.config?.host || '-'}:${r.config?.port || '-'}`,
    },
    {
      title: '状态', dataIndex: 'status', key: 'status',
      render: (s: string) => {
        const m = statusMap[s] || { color: 'default', text: s }
        return <Tag color={m.color}>{m.text}</Tag>
      },
    },
    {
      title: '最后同步', dataIndex: 'last_sync_at', key: 'last_sync_at',
      render: (v: string | null) => v || '从未同步',
    },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at' },
    {
      title: '操作', key: 'action',
      render: () => (
        <Space><a>测试连接</a><a>同步</a><a>编辑</a></Space>
      ),
    },
  ]

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <Title level={4} style={{ margin: 0 }}>数据源管理</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>新增数据源</Button>
        </Space>
      </div>

      <Card>
        <Table
          columns={columns}
          dataSource={data}
          rowKey="id"
          loading={loading}
          locale={{ emptyText: '暂无数据源，点击"新增数据源"添加' }}
        />
      </Card>

      <Modal
        title="新增数据源"
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => { setModalOpen(false); form.resetFields() }}
        okText="创建"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label="数据源名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="如: 生产MySQL" />
          </Form.Item>
          <Form.Item name="source_type" label="数据源类型" rules={[{ required: true, message: '请选择类型' }]}>
            <Select options={sourceTypeOptions} placeholder="选择数据源类型" />
          </Form.Item>
          <Form.Item name="host" label="主机地址">
            <Input placeholder="localhost 或 IP 地址" />
          </Form.Item>
          <Form.Item name="port" label="端口">
            <Input type="number" placeholder="3306" />
          </Form.Item>
          <Form.Item name="database" label="数据库名">
            <Input placeholder="数据库名称" />
          </Form.Item>
          <Form.Item name="username" label="用户名">
            <Input placeholder="数据库用户名" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="可选描述" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

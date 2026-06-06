/**
 * 爬虫任务管理页 — P2: 项目级爬虫 CRUD + 启停控制.
 */
import { useEffect, useState } from 'react'
import { Card, Table, Tag, Button, Space, Typography, Modal, Form, Input, Select, message, Popconfirm } from 'antd'
import { PlusOutlined, PlayCircleOutlined, PauseCircleOutlined, ReloadOutlined, DeleteOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import apiClient from '../utils/api'
import { usePermission } from '../hooks/usePermission'

const { Title } = Typography

interface CrawlerItem {
  id: number
  project_id: number
  name: string
  target_url: string | null
  framework: string
  config: Record<string, unknown>
  description: string | null
  status: string
  last_run_at: string | null
  total_runs: number
  total_rows_collected: number
  created_at: string
  updated_at: string
}

const statusMap: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '草稿' },
  active: { color: 'processing', text: '就绪' },
  running: { color: 'green', text: '运行中' },
  stopped: { color: 'warning', text: '已停止' },
  error: { color: 'red', text: '异常' },
}

export default function Crawlers() {
  const { can } = usePermission()
  const [data, setData] = useState<CrawlerItem[]>([])
  const [loading, setLoading] = useState(true)
  const [projectId, setProjectId] = useState<number>(1) // 默认项目 1
  const [createOpen, setCreateOpen] = useState(false)
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)

  const fetchData = async () => {
    setLoading(true)
    try {
      const resp = await apiClient.get('/crawlers', { params: { project_id: projectId } })
      setData(resp.data.items || resp.data)
    } catch {
      message.error('获取爬虫列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [projectId])

  const handleCreate = async (values: any) => {
    setSubmitting(true)
    try {
      await apiClient.post('/crawlers', { ...values, project_id: projectId })
      message.success('爬虫任务创建成功')
      setCreateOpen(false)
      form.resetFields()
      fetchData()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '创建失败')
    } finally {
      setSubmitting(false)
    }
  }

  const handleStart = async (id: number) => {
    try {
      await apiClient.post(`/crawlers/${id}/start`)
      message.success('任务已启动')
      fetchData()
    } catch { message.error('启动失败') }
  }

  const handleStop = async (id: number) => {
    try {
      await apiClient.post(`/crawlers/${id}/stop`)
      message.success('任务已停止')
      fetchData()
    } catch { message.error('停止失败') }
  }

  const handleDelete = async (id: number) => {
    try {
      await apiClient.delete(`/crawlers/${id}`)
      message.success('任务已删除')
      fetchData()
    } catch { message.error('删除失败') }
  }

  const columns: ColumnsType<CrawlerItem> = [
    { title: '任务名称', dataIndex: 'name', key: 'name', width: 160 },
    { title: '目标', dataIndex: 'target_url', key: 'target', ellipsis: true,
      render: (v: string | null) => v || <Typography.Text type="secondary">未设置</Typography.Text> },
    { title: '框架', dataIndex: 'framework', key: 'framework', width: 100,
      render: (fw: string) => <Tag>{fw}</Tag> },
    { title: '状态', dataIndex: 'status', key: 'status', width: 90,
      render: (s: string) => <Tag color={statusMap[s]?.color}>{statusMap[s]?.text || s}</Tag> },
    { title: '执行次数', dataIndex: 'total_runs', key: 'runs', width: 80 },
    { title: '采集量', dataIndex: 'total_rows_collected', key: 'rows', width: 100,
      render: (v: number) => `${v.toLocaleString()} 条` },
    { title: '上次执行', dataIndex: 'last_run_at', key: 'last_run', width: 150,
      render: (d: string | null) => d ? new Date(d).toLocaleString() : '-' },
    {
      title: '操作', key: 'action', width: 180,
      render: (_: any, record: CrawlerItem) => (
        <Space>
          {can('crawler:start') && record.status !== 'running' && (
            <Button size="small" icon={<PlayCircleOutlined />} type="primary" onClick={() => handleStart(record.id)}>启动</Button>
          )}
          {can('crawler:stop') && record.status === 'running' && (
            <Button size="small" icon={<PauseCircleOutlined />} onClick={() => handleStop(record.id)}>停止</Button>
          )}
          {can('crawler:delete') && (
            <Popconfirm title="确认删除?" onConfirm={() => handleDelete(record.id)}>
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <Title level={4} style={{ margin: 0 }}>网页爬取管理</Title>
        <Space>
          <Select
            value={projectId}
            onChange={setProjectId}
            style={{ width: 160 }}
            options={[{ value: 1, label: '默认项目' }]} // TODO: 从 accessibleProjects 加载
          />
          <Button icon={<ReloadOutlined />} onClick={fetchData}>刷新</Button>
          {can('crawler:create') && (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>新建爬虫任务</Button>
          )}
        </Space>
      </div>

      <Card>
        <Table
          columns={columns}
          dataSource={data}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 15, showTotal: (t) => `共 ${t} 个任务` }}
          locale={{ emptyText: '暂无爬虫任务' }}
        />
      </Card>

      <Modal
        title="新建爬虫任务"
        open={createOpen}
        onCancel={() => { setCreateOpen(false); form.resetFields() }}
        onOk={() => form.submit()}
        confirmLoading={submitting}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="name" label="任务名称" rules={[{ required: true }]}>
            <Input placeholder="例如: 行业新闻采集" />
          </Form.Item>
          <Form.Item name="target_url" label="目标 URL">
            <Input placeholder="https://example.com" />
          </Form.Item>
          <Form.Item name="framework" label="爬虫框架" initialValue="Scrapy">
            <Select options={[
              { value: 'Scrapy', label: 'Scrapy' },
              { value: 'Crawlee', label: 'Crawlee' },
              { value: 'Selenium', label: 'Selenium' },
              { value: 'Playwright', label: 'Playwright' },
              { value: 'Custom', label: '自定义' },
            ]} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

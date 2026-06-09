/**
 * 数据清洗 — Pipeline 列表与执行.
 */
import { useEffect, useState } from 'react'
import { Card, Table, Tag, Button, Space, Typography, Select, message, Popconfirm, Form, Modal, Input } from 'antd'
import { PlusOutlined, ReloadOutlined, PlayCircleOutlined, DeleteOutlined } from '@ant-design/icons'
import apiClient from '../utils/api'

const { Title, Text } = Typography

interface PipelineItem {
  id: number; project_id: number; name: string; source_table: string | null
  target_table: string | null; status: string; version: number
  last_run_at: string | null; last_output_rows: number; stages: any[]
}

export default function DataCleaning() {
  const [data, setData] = useState<PipelineItem[]>([])
  const [loading, setLoading] = useState(false)
  const [projectId, setProjectId] = useState(3)
  const [running, setRunning] = useState<number | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [form] = Form.useForm()

  const fetchData = async () => {
    setLoading(true)
    try {
      const resp = await apiClient.get('/cleaning/pipelines', { params: { project_id: projectId } })
      setData(resp.data.items || [])
    } catch { message.error('获取Pipeline列表失败') }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchData() }, [projectId])

  const handleCreate = async (values: any) => {
    try {
      await apiClient.post('/cleaning/pipelines', { project_id: projectId, ...values })
      message.success('Pipeline 已创建'); setCreateOpen(false); form.resetFields(); fetchData()
    } catch (err: any) { message.error(err.response?.data?.detail || '创建失败') }
  }

  const handleRun = async (id: number) => {
    setRunning(id)
    try {
      const resp = await apiClient.post('/cleaning/pipelines/run', { pipeline_id: id })
      const rows = resp.data.output_storage?.rows || 0
      message.success(`清洗完成: ${rows} 行 → MinIO Silver + PG Gold`)
      fetchData()
    } catch (err: any) { message.error(err.response?.data?.detail || '执行失败') }
    finally { setRunning(null) }
  }

  const handleDelete = async (id: number) => {
    try { await apiClient.delete(`/cleaning/pipelines/${id}`); message.success('已删除'); fetchData() }
    catch { message.error('删除失败') }
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <Title level={4} style={{ margin: 0 }}>数据清洗</Title>
        <Space>
          <Select value={projectId} onChange={setProjectId} style={{ width: 140 }}
            options={[{ value: 3, label: '演示项目' }]} />
          <Button icon={<ReloadOutlined />} onClick={fetchData}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); setCreateOpen(true) }}>新建 Pipeline</Button>
        </Space>
      </div>
      <Card>
        <Table dataSource={data} rowKey="id" loading={loading} size="middle"
          locale={{ emptyText: '暂无 Pipeline，点击"新建 Pipeline"创建' }}
          columns={[
            { title: '名称', dataIndex: 'name', width: 180 },
            { title: '源表', dataIndex: 'source_table', width: 120, render: (v: string|null) => v || '—' },
            { title: '目标表', dataIndex: 'target_table', width: 140, render: (v: string|null) => <Text code>{v || '—'}</Text> },
            { title: '状态', dataIndex: 'status', width: 70, render: (s: string) => <Tag color={s==='active'?'green':'default'}>{s}</Tag> },
            { title: '版本', dataIndex: 'version', width: 50, render: (v: number) => `v${v}` },
            { title: '上次输出', dataIndex: 'last_output_rows', width: 80, render: (v: number) => v ? `${v} 行` : '—' },
            { title: 'Stages', dataIndex: 'stages', ellipsis: true, render: (v: any[]) => (v||[]).map((s:any)=>s.type).join(' → ') || '—' },
            { title: '操作', width: 200, render: (_: any, r: PipelineItem) => (
              <Space size="small">
                <Button size="small" type="primary" icon={<PlayCircleOutlined />} loading={running===r.id} onClick={() => handleRun(r.id)}>执行</Button>
                <Popconfirm title="确认删除?" onConfirm={() => handleDelete(r.id)}>
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </Space>
            )},
          ]} />
      </Card>
      <Modal title="新建 Pipeline" open={createOpen} onOk={() => form.submit()} onCancel={() => setCreateOpen(false)}>
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}><Input placeholder="用户数据清洗" /></Form.Item>
          <Form.Item name="datasource_id" label="数据源 ID"><Input type="number" placeholder="3" /></Form.Item>
          <Form.Item name="source_table" label="源表名"><Input placeholder="users" /></Form.Item>
          <Form.Item name="target_table" label="目标表名"><Input placeholder="clean_users" /></Form.Item>
          <Form.Item name="description" label="描述"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

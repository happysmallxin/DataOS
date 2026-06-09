/**
 * 数据清洗 — 规则模板 + 选表绑定 (对齐 DataWorks).
 */
import { useEffect, useState } from 'react'
import { Card, Table, Tag, Button, Space, Typography, Select, message, Popconfirm, Form, Modal, Input, Checkbox, Divider } from 'antd'
import { PlusOutlined, ReloadOutlined, PlayCircleOutlined, DeleteOutlined, ThunderboltOutlined } from '@ant-design/icons'
import apiClient from '../utils/api'

const { Title, Text } = Typography

interface TemplateItem { id: number; name: string; display_name: string; stages: any[] }
interface PipelineItem { id: number; project_id: number; name: string; source_table: string | null; target_table: string | null; status: string; version: number; last_run_at: string | null; last_output_rows: number; stages: any[] }
interface TableInfo { name: string; columns: { name: string; type: string }[] }

export default function DataCleaning() {
  const [templates, setTemplates] = useState<TemplateItem[]>([])
  const [pipelines, setPipelines] = useState<PipelineItem[]>([])
  const [loading, setLoading] = useState(false)
  const [dsId, setDsId] = useState(3)
  const [tables, setTables] = useState<TableInfo[]>([])
  const [selectedTables, setSelectedTables] = useState<Set<string>>(new Set())
  const [selectedTemplate, setSelectedTemplate] = useState<number | null>(null)
  const [running, setRunning] = useState<number | null>(null)
  const [tplOpen, setTplOpen] = useState(false)
  const [tplForm] = Form.useForm()
  const [batchCreating, setBatchCreating] = useState(false)

  const fetchAll = async () => {
    setLoading(true)
    try {
      const [t, p] = await Promise.all([
        apiClient.get('/cleaning/templates'),
        apiClient.get('/cleaning/pipelines', { params: { project_id: 3 } }),
      ])
      setTemplates(t.data || []); setPipelines(p.data?.items || [])
    } catch { message.error('获取数据失败') }
    finally { setLoading(false) }
  }

  const fetchTables = async (id: number) => {
    try {
      const resp = await apiClient.post(`/datasources/${id}/tables`)
      setTables(resp.data || [])
    } catch { /* ignore */ }
  }

  useEffect(() => { fetchAll() }, [])
  useEffect(() => { if (dsId) { fetchTables(dsId); setSelectedTables(new Set()) } }, [dsId])

  // 批量创建 Pipeline
  const handleBatchCreate = async () => {
    if (selectedTables.size === 0) return
    setBatchCreating(true)
    try {
      const params: any = { datasource_id: dsId, tables: Array.from(selectedTables), target_prefix: 'clean_' }
      if (selectedTemplate) params.template_id = selectedTemplate
      const resp = await apiClient.post('/cleaning/batch-create-pipelines', null, { params })
      message.success(`已创建 ${resp.data.created} 条 Pipeline`)
      setSelectedTables(new Set()); fetchAll()
    } catch (err: any) { message.error(err.response?.data?.detail || '创建失败') }
    finally { setBatchCreating(false) }
  }

  const handleRun = async (id: number) => {
    setRunning(id)
    try {
      const resp = await apiClient.post('/cleaning/pipelines/run', { pipeline_id: id })
      message.success(`清洗完成: ${resp.data.output_storage?.rows || 0} 行`)
      fetchAll()
    } catch (err: any) { message.error(err.response?.data?.detail || '执行失败') }
    finally { setRunning(null) }
  }

  const handleDeletePl = async (id: number) => {
    try { await apiClient.delete(`/cleaning/pipelines/${id}`); message.success('已删除'); fetchAll() }
    catch { message.error('删除失败') }
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <Title level={4} style={{ margin: 0 }}>数据清洗</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchAll}>刷新</Button>
          <Button icon={<PlusOutlined />} onClick={() => { tplForm.resetFields(); setTplOpen(true) }}>新建规则模板</Button>
        </Space>
      </div>

      {/* 规则模板 */}
      <Card title="规则模板" size="small" style={{ marginBottom: 16 }}
        extra={<Text type="secondary">{templates.length} 个模板</Text>}>
        {templates.length === 0 ? (
          <Text type="secondary">暂无模板，点击"新建规则模板"创建</Text>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {templates.map(t => (
              <Tag key={t.id} color="blue" style={{ padding: '4px 12px', fontSize: 13, cursor: 'pointer' }}
                onClick={() => setSelectedTemplate(t.id === selectedTemplate ? null : t.id)}>
                📋 {t.display_name} ({t.stages?.length || 0} 规则)
                {selectedTemplate === t.id && ' ✓'}
              </Tag>
            ))}
          </div>
        )}
      </Card>

      {/* 选表绑定 */}
      <Card title="选择要清洗的表" size="small" style={{ marginBottom: 16 }}>
        <Space style={{ marginBottom: 12 }}>
          <Text>数据源:</Text>
          <Select value={dsId} onChange={setDsId} style={{ width: 180 }}
            options={[{ value: 3, label: '生产MySQL' }]} />
          <Text type="secondary">| 已选 {selectedTables.size} 张表</Text>
          <Button size="small" onClick={() => setSelectedTables(new Set(tables.map(t => t.name)))}>全选</Button>
          <Button size="small" onClick={() => setSelectedTables(new Set())}>取消</Button>
          {selectedTemplate && (
            <Tag color="green">模板: {templates.find(t => t.id === selectedTemplate)?.display_name}</Tag>
          )}
          <Button type="primary" icon={<ThunderboltOutlined />}
            loading={batchCreating} disabled={selectedTables.size === 0}
            onClick={handleBatchCreate}>
            批量创建 Pipeline
          </Button>
        </Space>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, maxHeight: 200, overflow: 'auto' }}>
          {tables.map(t => (
            <div key={t.name} style={{
              padding: '4px 10px', borderRadius: 4, cursor: 'pointer',
              background: selectedTables.has(t.name) ? '#e6f4ff' : '#fafafa',
              border: selectedTables.has(t.name) ? '1px solid #1677ff' : '1px solid #e8e8e8',
            }} onClick={() => {
              const next = new Set(selectedTables)
              selectedTables.has(t.name) ? next.delete(t.name) : next.add(t.name)
              setSelectedTables(next)
            }}>
              <Checkbox checked={selectedTables.has(t.name)} style={{ marginRight: 4 }} />
              <Text strong>{t.name}</Text>
              <Text type="secondary" style={{ fontSize: 11 }}> ({t.columns.length}列)</Text>
            </div>
          ))}
        </div>
      </Card>

      {/* Pipeline 列表 */}
      <Card title={`清洗 Pipeline (${pipelines.length})`} size="small">
        <Table dataSource={pipelines} rowKey="id" loading={loading} size="small" pagination={{ pageSize: 15 }}
          columns={[
            { title: '名称', dataIndex: 'name', width: 160, ellipsis: true },
            { title: '源表', dataIndex: 'source_table', width: 120 },
            { title: '目标表', dataIndex: 'target_table', width: 140, render: (v: string|null) => <Text code>{v||'—'}</Text> },
            { title: '规则', dataIndex: 'stages', ellipsis: true, render: (v: any[]) => (v||[]).map((s:any)=>s.type).join('→')||'—' },
            { title: '上次输出', dataIndex: 'last_output_rows', width: 80, render: (v: number) => v ? `${v}行` : '—' },
            { title: '操作', width: 140, render: (_: any, r: PipelineItem) => (
              <Space size="small">
                <Button size="small" type="primary" icon={<PlayCircleOutlined />} loading={running===r.id} onClick={() => handleRun(r.id)}>执行</Button>
                <Popconfirm title="确认删除?" onConfirm={() => handleDeletePl(r.id)}>
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </Space>
            )},
          ]} />
      </Card>

      {/* 新建模板弹窗 */}
      <Modal title="新建规则模板" open={tplOpen} onOk={() => tplForm.submit()} onCancel={() => setTplOpen(false)} width={560}>
        <Form form={tplForm} layout="vertical" onFinish={async (v) => {
          await apiClient.post('/cleaning/templates', v); message.success('模板已创建'); setTplOpen(false); fetchAll()
        }}>
          <Form.Item name="name" label="标识" rules={[{ required: true }]}><Input placeholder="mes_standard_clean" /></Form.Item>
          <Form.Item name="display_name" label="名称" rules={[{ required: true }]}><Input placeholder="MES标准清洗" /></Form.Item>
          <Form.Item name="stages" label="规则 JSON" initialValue="[]"
            extra='[{"type":"standardize","config":{"column":"id","operation":"trim"}},{"type":"standardize","config":{"column":"username","operation":"lowercase"}}]'>
            <Input.TextArea rows={6} placeholder='[{"type":"standardize","config":{"column":"id","operation":"trim"}}]' style={{ fontFamily: 'monospace' }} />
          </Form.Item>
          <Form.Item name="description" label="描述"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

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
  const [tplEditId, setTplEditId] = useState<number | null>(null)
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
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { tplForm.resetFields(); setTplEditId(null); setTplOpen(true) }}>新建模板</Button>
        </Space>
      </div>

      {/* 规则模板 — MES 风格表格 */}
      <Card title="清洗规则模板" size="small" style={{ marginBottom: 16 }}
>
        {templates.length === 0 ? (
          <Text type="secondary">暂无模板，点击"新建模板"创建</Text>
        ) : (
          templates.map(t => (
            <Card key={t.id} size="small" style={{ marginBottom: 8 }}
              title={
                <Space>
                  <Tag color={selectedTemplate === t.id ? 'green' : 'blue'}
                    style={{ cursor: 'pointer' }}
                    onClick={() => setSelectedTemplate(t.id === selectedTemplate ? null : t.id)}>
                    {selectedTemplate === t.id ? '✓ ' : ''}{t.display_name}
                  </Tag>
                  <Text type="secondary" style={{ fontSize: 12 }}>{t.description?.substring(0, 60)}...</Text>
                </Space>
              }
              extra={
                <Space size="small">
                  <Button size="small" onClick={() => { setTplEditId(t.id); tplForm.setFieldsValue({ name: t.name, display_name: t.display_name, stages: JSON.stringify(t.stages, null, 2), description: t.description || '' }); setTplOpen(true) }}>编辑</Button>
                  <Popconfirm title="确认删除?" onConfirm={async () => { await apiClient.delete(`/cleaning/templates/${t.id}`); fetchAll() }}>
                    <Button size="small" danger>删除</Button>
                  </Popconfirm>
                </Space>
              }>
              <Table dataSource={(t.stages || []).map((s: any, i: number) => ({ ...s, _key: i }))} rowKey="_key"
                size="small" pagination={false} showHeader={t.stages?.length > 0}
                columns={[
                  { title: '规则名称', dataIndex: 'rule_name', width: 160, render: (v: string) => v ? <Text strong>{v}</Text> : <Text type="secondary">—</Text> },
                  { title: '清洗类型', dataIndex: 'rule_type', width: 120, render: (v: string) => {
                    const m: Record<string, {c:string,l:string}> = {
                      structure_check:{c:'blue',l:'结构检查'}, primary_key:{c:'orange',l:'主键检查'},
                      code_mapping:{c:'purple',l:'编码映射'}, status_standardize:{c:'green',l:'状态标准化'},
                      time_logic:{c:'cyan',l:'时间逻辑'}, quantity_check:{c:'red',l:'数量合理性'},
                      field_standardize:{c:'geekblue',l:'字段标准化'},
                      standardize:{c:'default',l:'标准化'}, dedup:{c:'default',l:'去重'},
                    }
                    const info = m[v] || {c:'default',l:v}
                    return <Tag color={info.c}>{info.l}</Tag>
                  }},
                  { title: '目标', dataIndex: 'target', width: 140, render: (v: string) => <Text code style={{fontSize:11}}>{v||'*'}</Text> },
                  { title: '严重级别', dataIndex: 'severity', width: 80, render: (v: string) => {
                    const colors: Record<string,string> = {error:'red',warning:'orange',info:'blue'}
                    return <Tag color={colors[v]||'default'}>{v}</Tag>
                  }},
                  { title: '执行方式', dataIndex: 'action', width: 120, ellipsis: true },
                ]} />
            </Card>
          ))
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
      <Modal title={tplEditId ? '编辑规则模板' : '新建规则模板'} open={tplOpen}
        onOk={() => tplForm.submit()} onCancel={() => { setTplOpen(false); setTplEditId(null) }}
        footer={(_, { OkBtn }) => (
          <Space>
            {tplEditId && (
              <Popconfirm title="确认删除此模板?" onConfirm={async () => {
                await apiClient.delete(`/cleaning/templates/${tplEditId}`); message.success('模板已删除')
                setTplOpen(false); setTplEditId(null); fetchAll()
              }}>
                <Button danger>删除模板</Button>
              </Popconfirm>
            )}
            <Button onClick={() => { setTplOpen(false); setTplEditId(null) }}>取消</Button>
            <OkBtn />
          </Space>
        )} width={560}>
        <Form form={tplForm} layout="vertical" onFinish={async (v) => {
          const data = { ...v, stages: JSON.parse(v.stages || '[]') }
          if (tplEditId) {
            await apiClient.put(`/cleaning/templates/${tplEditId}`, data); message.success('模板已更新')
          } else {
            await apiClient.post('/cleaning/templates', data); message.success('模板已创建')
          }
          setTplOpen(false); setTplEditId(null); fetchAll()
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

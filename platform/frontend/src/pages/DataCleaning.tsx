/**
 * 数据清洗 — 规则模板 + 选表绑定 (对齐 DataWorks).
 */
import { useEffect, useState } from 'react'
import { Card, Table, Tag, Button, Space, Typography, Select, message, Popconfirm, Form, Modal, Input, Checkbox, Row, Col, Badge, Tooltip } from 'antd'
import {
  PlusOutlined, ReloadOutlined, PlayCircleOutlined, DeleteOutlined, ThunderboltOutlined,
  CheckCircleOutlined, CloseCircleOutlined, WarningOutlined, InfoCircleOutlined,
  DownOutlined, UpOutlined, EditOutlined,
} from '@ant-design/icons'
import apiClient from '../utils/api'

const { Title, Text } = Typography

interface TemplateItem { id: number; name: string; display_name: string; description?: string; stages: any[] }
interface PipelineItem { id: number; project_id: number; name: string; source_table: string | null; target_table: string | null; status: string; version: number; last_run_at: string | null; last_output_rows: number; stages: any[] }
interface TableInfo { name: string; columns: { name: string; type: string }[] }

const typeIcons: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  structure_check: { icon: <CheckCircleOutlined />, color: '#1677ff', label: '结构检查' },
  primary_key: { icon: <WarningOutlined />, color: '#fa8c16', label: '主键检查' },
  code_mapping: { icon: <ThunderboltOutlined />, color: '#722ed1', label: '编码映射' },
  status_standardize: { icon: <CheckCircleOutlined />, color: '#52c41a', label: '状态标准化' },
  time_logic: { icon: <InfoCircleOutlined />, color: '#13c2c2', label: '时间逻辑' },
  quantity_check: { icon: <CloseCircleOutlined />, color: '#f5222d', label: '数量合理性' },
  field_standardize: { icon: <EditOutlined />, color: '#2f54eb', label: '字段标准化' },
}

const sevColors: Record<string, string> = { error: '#f5222d', warning: '#fa8c16', info: '#1677ff' }

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
  const [expandedTpl, setExpandedTpl] = useState<Set<number>>(new Set())

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

  const handleBatchCreate = async () => {
    if (selectedTables.size === 0) return
    setBatchCreating(true)
    try {
      const resp = await apiClient.post('/cleaning/batch-create-pipelines', {
        datasource_id: dsId,
        table_names: Array.from(selectedTables),
        target_prefix: 'clean_',
        template_id: selectedTemplate || null,
      })
      message.success(`清洗任务已创建: ${resp.data.pipeline_name} (${resp.data.tables?.length || 0} 张表)`)
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

      {/* 规则模板 — 三列卡片网格 */}
      <Card title="清洗规则模板" size="small" style={{ marginBottom: 16 }}>
        {templates.length === 0 ? (
          <Text type="secondary">暂无模板，点击"新建模板"创建</Text>
        ) : (
          <Row gutter={[12, 12]}>
            {templates.map(t => {
              const isSelected = selectedTemplate === t.id
              const isExpanded = expandedTpl.has(t.id)
              const rules = t.stages || []
              const ruleCount = rules.length

              return (
                <Col xs={24} sm={12} lg={8} key={t.id}>
                  <Card
                    size="small"
                    hoverable
                    style={{
                      border: isSelected ? '2px solid #52c41a' : '1px solid #e8e8e8',
                      background: isSelected ? '#f6ffed' : '#fff',
                      transition: 'all 0.2s',
                      height: '100%',
                    }}
                    onClick={() => setSelectedTemplate(t.id === selectedTemplate ? null : t.id)}
                    styles={{ body: { padding: '12px 16px' } }}
                  >
                    {/* 标题行 */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                      <div>
                        <Space size={4}>
                          {isSelected && <Tag color="green" style={{ margin: 0, fontSize: 10 }}>已选</Tag>}
                          <Text strong style={{ fontSize: 14 }}>{t.display_name}</Text>
                        </Space>
                        {t.description && (
                          <div style={{ marginTop: 2 }}>
                            <Text type="secondary" style={{ fontSize: 11 }}>{t.description.substring(0, 45)}{t.description.length > 45 ? '...' : ''}</Text>
                          </div>
                        )}
                      </div>
                      <Space size={0}>
                        <Tooltip title="编辑"><Button type="text" size="small" icon={<EditOutlined style={{ fontSize: 13 }} />}
                          onClick={e => { e.stopPropagation(); setTplEditId(t.id); tplForm.setFieldsValue({ name: t.name, display_name: t.display_name, stages: JSON.stringify(rules, null, 2), description: t.description || '' }); setTplOpen(true) }} /></Tooltip>
                        <Popconfirm title="确认删除?" onConfirm={() => { apiClient.delete(`/cleaning/templates/${t.id}`); fetchAll() }}>
                          <Tooltip title="删除"><Button type="text" size="small" danger icon={<DeleteOutlined style={{ fontSize: 13 }} />} onClick={e => e.stopPropagation()} /></Tooltip>
                        </Popconfirm>
                      </Space>
                    </div>

                    {/* 规则类型标签 */}
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 10 }}>
                      {[...new Set(rules.map((s: any) => s.rule_type))].map((rt: any) => {
                        const info = typeIcons[rt] || { icon: null, color: '#999', label: rt }
                        return (
                          <Tag key={rt} color={info.color} style={{ fontSize: 11, margin: 0, opacity: 0.85 }}>
                            {info.label} x{rules.filter((s: any) => s.rule_type === rt).length}
                          </Tag>
                        )
                      })}
                    </div>

                    {/* 规则列表 — 折叠/展开 */}
                    <div style={{ padding: '8px 10px', background: '#fafafa', borderRadius: 6, fontSize: 12, lineHeight: '22px', minHeight: 36 }}>
                      {!isExpanded ? (
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Text style={{ fontSize: 12 }}>
                            {rules.slice(0, 2).map((s: any) => s.rule_name).join(', ')}
                            {ruleCount > 2 && <Text type="secondary" style={{ fontSize: 11 }}> +{ruleCount - 2}</Text>}
                          </Text>
                          <Button type="link" size="small" style={{ padding: 0, fontSize: 11, whiteSpace: 'nowrap' }}
                            onClick={e => { e.stopPropagation(); setExpandedTpl(new Set([...expandedTpl, t.id])) }}>
                            展开 <DownOutlined style={{ fontSize: 10 }} />
                          </Button>
                        </div>
                      ) : (
                        <div>
                          <div style={{ marginBottom: 6, maxHeight: 200, overflow: 'auto' }}>
                            {rules.map((s: any, i: number) => (
                              <div key={i} style={{
                                display: 'flex', alignItems: 'center', gap: 6, padding: '3px 0',
                                borderBottom: i < ruleCount - 1 ? '1px solid #f0f0f0' : 'none',
                              }}>
                                <span style={{ color: sevColors[s.severity] || '#999', fontSize: 12 }}>
                                  {s.severity === 'error' ? '●' : s.severity === 'warning' ? '◆' : '○'}
                                </span>
                                <Text style={{ fontSize: 12, flex: 1 }}>{s.rule_name}</Text>
                                <Text type="secondary" style={{ fontSize: 10 }}>{s.action}</Text>
                              </div>
                            ))}
                          </div>
                          <Button type="link" size="small" style={{ padding: 0, fontSize: 11 }}
                            onClick={e => { e.stopPropagation(); const n = new Set(expandedTpl); n.delete(t.id); setExpandedTpl(n) }}>
                            收起 <UpOutlined style={{ fontSize: 10 }} />
                          </Button>
                        </div>
                      )}
                    </div>

                    {/* 底部统计 */}
                    <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 12 }}>
                      <Badge count={ruleCount} size="small" color="#1677ff" overflowCount={99}>
                        <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>规则</Text>
                      </Badge>
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        严重 <Text style={{ color: '#f5222d', fontSize: 11 }}>{rules.filter((s: any) => s.severity === 'error').length}</Text>
                        {' '}警告 <Text style={{ color: '#fa8c16', fontSize: 11 }}>{rules.filter((s: any) => s.severity === 'warning').length}</Text>
                      </Text>
                    </div>
                  </Card>
                </Col>
              )
            })}
          </Row>
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
            创建清洗任务
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
            { title: '目标表', dataIndex: 'target_table', width: 140, render: (v: string|null) => <Text code>{v||'-'}</Text> },
            { title: '规则', dataIndex: 'stages', ellipsis: true, render: (v: any[]) => (v||[]).map((s:any)=>s.rule_type||s.type).join('→')||'-' },
            { title: '上次输出', dataIndex: 'last_output_rows', width: 80, render: (v: number) => v ? `${v}行` : '-' },
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

      {/* 新建/编辑模板弹窗 */}
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
            extra='[{"rule_type":"structure_check","rule_name":"字段检查","target":"all_columns","severity":"error","action":"check"}]'>
            <Input.TextArea rows={6} style={{ fontFamily: 'monospace' }} />
          </Form.Item>
          <Form.Item name="description" label="描述"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

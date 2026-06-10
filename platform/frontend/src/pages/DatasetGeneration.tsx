/**
 * 数据集生成 — 选模型→配字段→预览→生成→发布 (对齐 MES 文档 §3.4).
 */
import { useEffect, useState } from 'react'
import { Card, Table, Tag, Button, Space, Typography, Select, message, Popconfirm, Form, Modal, Input, Steps, Row, Col, Statistic, Descriptions } from 'antd'
import { PlusOutlined, ReloadOutlined, DeleteOutlined, PlayCircleOutlined, EyeOutlined, CheckCircleOutlined, DownloadOutlined } from '@ant-design/icons'
import apiClient from '../utils/api'

const { Title, Text } = Typography

interface DatasetItem { id: number; name: string; version: string; status: string; domain_id: number | null; model_table_ids: number[]; output_fields: any[]; total_rows: number; total_size_bytes: number; storage_path: string | null; update_cycle: string; export_format: string; created_at: string; published_at: string | null }
interface DomainItem { id: number; display_name: string }
interface ModelTableItem { id: number; code: string; name: string; table_type: string; domain_id: number }
interface VersionItem { id: number; version: string; status: string; total_rows: number; storage_path: string | null; created_at: string }

export default function DatasetGeneration() {
  const [datasets, setDatasets] = useState<DatasetItem[]>([])
  const [domains, setDomains] = useState<DomainItem[]>([])
  const [models, setModels] = useState<ModelTableItem[]>([])
  const [loading, setLoading] = useState(false)
  const [projectId, setProjectId] = useState(3)
  const [currentStep, setCurrentStep] = useState(0)

  // Create wizard
  const [createOpen, setCreateOpen] = useState(false)
  const [wizardName, setWizardName] = useState('')
  const [wizardDomain, setWizardDomain] = useState<number | undefined>()
  const [wizardModels, setWizardModels] = useState<number[]>([])
  const [wizardFields, setWizardFields] = useState<any[]>([])
  const [wizardCycle, setWizardCycle] = useState('once')
  const [wizardFormat, setWizardFormat] = useState('parquet')
  const [creating, setCreating] = useState(false)

  // Preview
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewData, setPreviewData] = useState<any>(null)

  // Versions
  const [versionsOpen, setVersionsOpen] = useState(false)
  const [versions, setVersions] = useState<VersionItem[]>([])

  const fetchAll = async () => {
    setLoading(true)
    try {
      const [d, m, ds] = await Promise.all([
        apiClient.get(`/projects/${projectId}/domains`),
        apiClient.get(`/projects/${projectId}/model-tables`),
        apiClient.get('/datasets', { params: { project_id: projectId } }),
      ])
      setDomains(d.data || []); setModels(m.data || []); setDatasets(ds.data || [])
    } catch { message.error('获取数据失败') }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchAll() }, [projectId])

  const filteredModels = wizardDomain ? models.filter(m => m.domain_id === wizardDomain) : models

  // ---- Dataset CRUD ----
  const handleCreate = async () => {
    setCreating(true)
    try {
      const r = await apiClient.post('/datasets', {
        name: wizardName, version: '1.0', domain_id: wizardDomain,
        model_table_ids: wizardModels, output_fields: wizardFields,
        update_cycle: wizardCycle, export_format: wizardFormat,
      }, { params: { project_id: projectId } })
      // 自动生成
      const dsId = r.data.id
      const genR = await apiClient.post(`/datasets/${dsId}/generate`)
      message.success(`数据集已生成: ${genR.data.total_rows || 0} 行`)
      setCreateOpen(false); resetWizard(); fetchAll()
    } catch (err: any) { message.error(err.response?.data?.detail || '创建失败') }
    finally { setCreating(false) }
  }

  const resetWizard = () => {
    setCurrentStep(0); setWizardName(''); setWizardDomain(undefined)
    setWizardModels([]); setWizardFields([]); setWizardCycle('once'); setWizardFormat('parquet')
  }

  const handleGenerate = async (id: number) => {
    try {
      const r = await apiClient.post(`/datasets/${id}/generate`)
      message.success(`数据集已生成: ${r.data.total_rows || 0} 行`)
      fetchAll()
    } catch (err: any) { message.error(err.response?.data?.detail || '生成失败') }
  }

  const handlePublish = async (id: number) => {
    try { await apiClient.post(`/datasets/${id}/publish`); message.success('已发布'); fetchAll() }
    catch { message.error('发布失败') }
  }

  const handlePreview = async (id: number) => {
    try { const r = await apiClient.post(`/datasets/${id}/preview`); setPreviewData(r.data); setPreviewOpen(true) }
    catch { message.error('预览失败') }
  }

  const handleVersions = async (id: number) => {
    try { const r = await apiClient.get(`/datasets/${id}/versions`); setVersions(r.data || []); setVersionsOpen(true) }
    catch { message.error('获取版本失败') }
  }

  const handleDelete = async (id: number) => {
    await apiClient.delete(`/datasets/${id}`); message.success('已删除'); fetchAll()
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <Title level={4} style={{ margin: 0 }}>数据集生成</Title>
        <Space>
          <Select value={projectId} onChange={setProjectId} style={{ width: 120 }} options={[{ value: 3, label: '演示' }]} />
          <Button icon={<ReloadOutlined />} onClick={fetchAll}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { resetWizard(); setCreateOpen(true) }}>新建数据集</Button>
        </Space>
      </div>

      {/* 数据集列表 */}
      <Card title={`数据集 (${datasets.length})`} size="small">
        <Table dataSource={datasets} rowKey="id" loading={loading} size="middle" pagination={false}
          locale={{ emptyText: '暂无数据集' }}
          columns={[
            { title: '名称', dataIndex: 'name', width: 160 },
            { title: '版本', dataIndex: 'version', width: 60 },
            { title: '状态', dataIndex: 'status', width: 80, render: (v: string) => {
              const m: Record<string, {c:string,t:string}> = {draft:{c:'default',t:'草稿'},generating:{c:'processing',t:'生成中'},published:{c:'green',t:'已发布'},rejected:{c:'red',t:'驳回'}}
              return <Tag color={m[v]?.c}>{m[v]?.t || v}</Tag>
            }},
            { title: '模型表', dataIndex: 'model_table_ids', width: 120, render: (v: number[]) => `${v?.length || 0} 张` },
            { title: '行数', dataIndex: 'total_rows', width: 80, render: (v: number) => v ? v.toLocaleString() : '—' },
            { title: '大小', dataIndex: 'total_size_bytes', width: 80, render: (v: number) => v ? `${(v/1024).toFixed(1)}KB` : '—' },
            { title: '更新', dataIndex: 'update_cycle', width: 60, render: (v: string) => <Tag>{v}</Tag> },
            { title: '格式', dataIndex: 'export_format', width: 70 },
            { title: '操作', width: 260, render: (_: any, r: DatasetItem) => (
              <Space size="small">
                {r.storage_path && (
                  <Button size="small" icon={<DownloadOutlined />}
                    onClick={async () => {
                      try {
                        const resp = await apiClient.get(`/datasets/${r.id}/export?format=csv`, { responseType: 'blob' })
                        const url = window.URL.createObjectURL(new Blob([resp.data]))
                        const a = document.createElement('a'); a.href = url
                        a.download = `${r.name}_v${r.version}.csv`; a.click()
                        window.URL.revokeObjectURL(url)
                      } catch { message.error('下载失败') }
                    }} />
                )}
                <Button size="small" icon={<EyeOutlined />} onClick={() => handlePreview(r.id)}>预览</Button>
                <Button size="small" icon={<PlayCircleOutlined />} onClick={() => handleGenerate(r.id)}>生成</Button>
                <Button size="small" onClick={() => handleVersions(r.id)}>版本</Button>
                {r.status === 'published' && (
                  <Button size="small" icon={<CheckCircleOutlined />} type="primary" onClick={() => handlePublish(r.id)}>发布</Button>
                )}
                <Popconfirm title="确认删除?" onConfirm={() => handleDelete(r.id)}>
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </Space>
            )},
          ]} />
      </Card>

      {/* 新建弹窗 - 向导式 */}
      <Modal title="新建数据集" open={createOpen} onCancel={() => setCreateOpen(false)} footer={null} width={640}>
        <Steps current={currentStep} size="small" style={{ marginBottom: 20 }}
          items={[{ title: '选择模型' }, { title: '配置' }, { title: '生成' }]} />

        {currentStep === 0 && (
          <div>
            <Form.Item label="数据集名称" required><Input value={wizardName} onChange={e => setWizardName(e.target.value)} placeholder="生产执行数据集" /></Form.Item>
            <Form.Item label="数据域"><Select value={wizardDomain} onChange={setWizardDomain} allowClear placeholder="全部" options={domains.map(d => ({ value: d.id, label: d.display_name }))} /></Form.Item>
            <Text strong>选择模型表</Text>
            <div style={{ maxHeight: 200, overflow: 'auto', margin: '8px 0' }}>
              {filteredModels.map(m => (
                <div key={m.id} style={{ padding: '4px 8px', cursor: 'pointer', background: wizardModels.includes(m.id) ? '#e6f4ff' : '#fafafa', borderRadius: 4, margin: '2px 0' }}
                  onClick={() => { const n = [...wizardModels]; wizardModels.includes(m.id) ? n.splice(n.indexOf(m.id),1) : n.push(m.id); setWizardModels(n) }}>
                  <Tag>{m.table_type}</Tag> {m.name} <Text type="secondary" style={{ fontSize: 11 }}>({m.code})</Text>
                  {wizardModels.includes(m.id) && ' ✓'}
                </div>
              ))}
            </div>
            <Button type="primary" disabled={!wizardName || wizardModels.length === 0} onClick={() => setCurrentStep(1)}>下一步</Button>
          </div>
        )}

        {currentStep === 1 && (
          <div>
            <Text>已选 {wizardModels.length} 张模型表</Text>
            <Row gutter={16} style={{ margin: '12px 0' }}>
              <Col span={12}><Form.Item label="更新周期"><Select value={wizardCycle} onChange={setWizardCycle} options={[{v:'once',l:'一次性'},{v:'daily',l:'每日'},{v:'weekly',l:'每周'},{v:'monthly',l:'每月'}].map(o=>({value:o.v,label:o.l}))} /></Form.Item></Col>
              <Col span={12}><Form.Item label="导出格式"><Select value={wizardFormat} onChange={setWizardFormat} options={[{v:'parquet',l:'Parquet'},{v:'csv',l:'CSV'},{v:'json',l:'JSON'}].map(o=>({value:o.v,label:o.l}))} /></Form.Item></Col>
            </Row>
            <Space>
              <Button onClick={() => setCurrentStep(0)}>上一步</Button>
              <Button type="primary" onClick={() => setCurrentStep(2)}>下一步</Button>
            </Space>
          </div>
        )}

        {currentStep === 2 && (
          <div>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="名称">{wizardName}</Descriptions.Item>
              <Descriptions.Item label="模型表">{wizardModels.length} 张</Descriptions.Item>
              <Descriptions.Item label="更新">{wizardCycle}</Descriptions.Item>
              <Descriptions.Item label="格式">{wizardFormat}</Descriptions.Item>
            </Descriptions>
            <Space style={{ marginTop: 16 }}>
              <Button onClick={() => setCurrentStep(1)}>上一步</Button>
              <Button type="primary" icon={<PlayCircleOutlined />} loading={creating} onClick={handleCreate}>创建并生成</Button>
            </Space>
          </div>
        )}
      </Modal>

      {/* 预览 */}
      <Modal title="数据集预览" open={previewOpen} onCancel={() => setPreviewOpen(false)} footer={null} width={600}>
        {previewData && (
          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label="数据集">{previewData.name}</Descriptions.Item>
            <Descriptions.Item label="版本">{previewData.version}</Descriptions.Item>
            <Descriptions.Item label="模型表">{previewData.total_models} 张</Descriptions.Item>
            <Descriptions.Item label="输出字段">{previewData.output_fields?.length || 0}</Descriptions.Item>
          </Descriptions>
        )}
        {previewData?.model_tables?.map((m: any) => (
          <Card key={m.code} size="small" style={{ marginTop: 8 }} title={`${m.model} (${m.field_count} 字段)`}>
            <Text code style={{ fontSize: 11 }}>{m.fields?.join(', ') || '—'}</Text>
          </Card>
        ))}
      </Modal>

      {/* 版本历史 */}
      <Modal title="版本历史" open={versionsOpen} onCancel={() => setVersionsOpen(false)} footer={null} width={500}>
        <Table dataSource={versions} rowKey="id" size="small" pagination={false}
          columns={[
            { title: '版本', dataIndex: 'version', width: 60 },
            { title: '状态', dataIndex: 'status', width: 70, render: (v: string) => <Tag color={v==='published'?'green':'default'}>{v}</Tag> },
            { title: '行数', dataIndex: 'total_rows', width: 80 },
            { title: '时间', dataIndex: 'created_at', render: (v: string) => v ? new Date(v).toLocaleString() : '—' },
          ]} />
      </Modal>
    </div>
  )
}

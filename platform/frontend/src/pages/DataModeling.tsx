/**
 * 数据建模 — 数据域 + 模型表(含字段定义) + DDL生成 (对齐 MES §3.3).
 */
import { useEffect, useState } from 'react'
import { Card, Table, Tag, Button, Space, Typography, Select, message, Popconfirm, Form, Modal, Input, Checkbox, Row, Col, Tooltip, Divider } from 'antd'
import { PlusOutlined, ReloadOutlined, DeleteOutlined, ThunderboltOutlined, ImportOutlined, EditOutlined, MinusCircleOutlined } from '@ant-design/icons'
import apiClient from '../utils/api'

const { Title, Text } = Typography

interface DomainItem { id: number; name: string; display_name: string }
interface ModelTableItem { id: number; code: string; name: string; table_type: string; domain_id: number; primary_key_field: string | null; source_gold_table: string | null; target_gold_table: string | null; status: string; version: string }
interface ModelFieldItem { id: number; code: string; name: string; data_type: string; is_primary_key: boolean; is_foreign_key: boolean; ref_table: string | null; source_field: string | null; quality_rule: string | null }

// 新建模型表时的临时字段
interface TempField { key: number; code: string; name: string; data_type: string; is_primary_key: boolean; source_field: string; quality_rule: string }

export default function DataModeling() {
  const [domains, setDomains] = useState<DomainItem[]>([])
  const [models, setModels] = useState<ModelTableItem[]>([])
  const [loading, setLoading] = useState(false)
  const [projectId, setProjectId] = useState(3)
  const [filterDomain, setFilterDomain] = useState<number | undefined>()
  const [filterType, setFilterType] = useState<string | undefined>()

  // Domain modal
  const [domainOpen, setDomainOpen] = useState(false)
  const [domainForm] = Form.useForm()
  // Model modal — 含字段定义
  const [modelOpen, setModelOpen] = useState(false)
  const [editModelId, setEditModelId] = useState<number | null>(null)
  const [modelForm] = Form.useForm()
  const [tempFields, setTempFields] = useState<TempField[]>([])
  const [fieldKeyCounter, setFieldKeyCounter] = useState(0)
  // Fields management (for existing models)
  const [fieldsOpen, setFieldsOpen] = useState(false)
  const [fieldsModel, setFieldsModel] = useState<ModelTableItem | null>(null)
  const [fields, setFields] = useState<ModelFieldItem[]>([])
  const [fieldForm] = Form.useForm()
  const [fieldOpen, setFieldOpen] = useState(false)

  const fetchAll = async () => {
    setLoading(true)
    try {
      const [d, m] = await Promise.all([
        apiClient.get(`/projects/${projectId}/domains`),
        apiClient.get(`/projects/${projectId}/model-tables`, { params: { domain_id: filterDomain, table_type: filterType } }),
      ])
      setDomains(d.data || []); setModels(m.data || [])
    } catch { message.error('获取数据失败') }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchAll() }, [projectId, filterDomain, filterType])

  const fetchFields = async (mid: number) => {
    try { const r = await apiClient.get(`/model-tables/${mid}/fields`); setFields(r.data || []) }
    catch { /* ignore */ }
  }

  // ---- Temp field management in model form ----
  const addTempField = () => {
    setTempFields([...tempFields, { key: fieldKeyCounter, code: '', name: '', data_type: 'VARCHAR', is_primary_key: false, source_field: '', quality_rule: '' }])
    setFieldKeyCounter(fieldKeyCounter + 1)
  }

  const removeTempField = (key: number) => {
    setTempFields(tempFields.filter(f => f.key !== key))
  }

  const updateTempField = (key: number, field: string, value: any) => {
    setTempFields(tempFields.map(f => f.key === key ? { ...f, [field]: value } : f))
  }

  // ---- Model CRUD ----
  const handleSaveModel = async (v: any) => {
    try {
      let mid: number
      if (editModelId) {
        await apiClient.put(`/projects/${projectId}/model-tables/${editModelId}`, v)
        mid = editModelId
      } else {
        const r = await apiClient.post(`/projects/${projectId}/model-tables`, v)
        mid = r.data.id
      }
      // 创建/更新字段
      if (tempFields.length > 0) {
        for (const f of tempFields) {
          if (!f.code) continue
          await apiClient.post(`/model-tables/${mid}/fields`, {
            code: f.code, name: f.name || f.code, data_type: f.data_type,
            is_primary_key: f.is_primary_key, source_field: f.source_field,
            quality_rule: f.quality_rule || null,
          })
        }
      }
      message.success(editModelId ? '已更新' : '已创建')
      setModelOpen(false); setTempFields([]); fetchAll()
    } catch (err: any) { message.error(err.response?.data?.detail || '保存失败') }
  }

  const handleDeleteModel = async (id: number) => {
    await apiClient.delete(`/projects/${projectId}/model-tables/${id}`); message.success('已删除'); fetchAll()
  }

  const handleDDL = async (mid: number) => {
    try {
      const r = await apiClient.post(`/projects/${projectId}/model-tables/${mid}/ddl`)
      if (r.data.executed) message.success(`DDL 已执行: ${r.data.table}`)
      else message.error(r.data.error || 'DDL 执行失败')
    } catch { message.error('操作失败') }
  }

  const handleImportFields = async (mid: number, sourceTable: string) => {
    if (!sourceTable) return
    try {
      const r = await apiClient.post(`/projects/${projectId}/model-tables/${mid}/import-fields?source_table=${sourceTable}`)
      message.success(`已导入 ${r.data.imported} 个字段`)
      fetchFields(mid)
    } catch (err: any) { message.error(err.response?.data?.detail || '导入失败') }
  }

  // ---- Field CRUD (for existing models) ----
  const handleSaveField = async (v: any) => {
    try {
      await apiClient.post(`/model-tables/${fieldsModel!.id}/fields`, v)
      message.success('字段已添加'); setFieldOpen(false); fetchFields(fieldsModel!.id)
    } catch (err: any) { message.error(err.response?.data?.detail || '保存失败') }
  }

  const handleDeleteField = async (fid: number) => {
    await apiClient.delete(`/model-tables/${fieldsModel!.id}/fields/${fid}`)
    message.success('已删除'); fetchFields(fieldsModel!.id)
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <Title level={4} style={{ margin: 0 }}>数据建模</Title>
        <Space>
          <Select value={projectId} onChange={setProjectId} style={{ width: 120 }} options={[{ value: 3, label: '演示' }]} />
          <Button icon={<ReloadOutlined />} onClick={fetchAll}>刷新</Button>
          <Button icon={<PlusOutlined />} onClick={() => { domainForm.resetFields(); setDomainOpen(true) }}>新增数据域</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { modelForm.resetFields(); setEditModelId(null); setTempFields([]); setModelOpen(true) }}>新建模型表</Button>
        </Space>
      </div>

      {/* 数据域 */}
      <Card title="数据域" size="small" style={{ marginBottom: 16 }}>
        {domains.length === 0 ? <Text type="secondary">暂无</Text> : (
          <Space wrap>{domains.map((d: any) => (
            <Tag key={d.id} color={filterDomain === d.id ? 'green' : 'blue'} style={{ cursor: 'pointer', padding: '4px 12px', fontSize: 13 }}
              onClick={() => setFilterDomain(filterDomain === d.id ? undefined : d.id)}>
              📁 {d.display_name} {filterDomain === d.id ? '✓' : ''}
            </Tag>
          ))}</Space>
        )}
      </Card>

      {/* 模型表列表 */}
      <Card title="模型表" size="small"
        extra={<Select value={filterType} onChange={setFilterType} allowClear placeholder="全部类型" style={{ width: 100 }}
          options={[{v:'DIM',l:'DIM'},{v:'FACT',l:'FACT'},{v:'DWD',l:'DWD'},{v:'DWS',l:'DWS'},{v:'ADS',l:'ADS'}].map(o=>({value:o.v,label:o.l}))} />}>
        <Table dataSource={models} rowKey="id" loading={loading} size="middle" pagination={false}
          locale={{ emptyText: '暂无模型表' }}
          columns={[
            { title: '编码', dataIndex: 'code', width: 150, render: (v: string) => <Text code>{v}</Text> },
            { title: '名称', dataIndex: 'name', width: 140 },
            { title: '类型', dataIndex: 'table_type', width: 60, render: (v: string) => <Tag>{v}</Tag> },
            { title: '数据域', dataIndex: 'domain_id', width: 80, render: (v: number) => domains.find(d => d.id === v)?.display_name || `#${v}` },
            { title: '主键', dataIndex: 'primary_key_field', width: 120, render: (v: string|null) => v ? <Text code style={{fontSize:11}}>{v}</Text> : '—' },
            { title: '来源', dataIndex: 'source_gold_table', width: 100, render: (v: string|null) => v || '—' },
            { title: '目标', dataIndex: 'target_gold_table', width: 100, render: (v: string|null) => <Text code style={{fontSize:11}}>{v||'—'}</Text> },
            { title: '版本', dataIndex: 'version', width: 50 },
            { title: '操作', width: 300,
              render: (_: any, r: ModelTableItem) => (
                <Space size="small">
                  <Button size="small" icon={<EditOutlined />} onClick={() => { setFieldsModel(r); fetchFields(r.id); setFieldsOpen(true) }}>字段</Button>
                  <Tooltip title="从 Gold 表导入字段"><Button size="small" icon={<ImportOutlined />}
                    onClick={() => handleImportFields(r.id, r.source_gold_table || '')} disabled={!r.source_gold_table}>导入</Button></Tooltip>
                  <Button size="small" icon={<ThunderboltOutlined />} onClick={() => handleDDL(r.id)}>DDL</Button>
                  <Button size="small" onClick={() => { setEditModelId(r.id); modelForm.setFieldsValue(r); setTempFields([]); setModelOpen(true) }}>编辑</Button>
                  <Popconfirm title="确认删除?" onConfirm={() => handleDeleteModel(r.id)}>
                    <Button size="small" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                </Space>
              ),
            },
          ]} />
      </Card>

      {/* ======== 弹窗 ======== */}
      <Modal title="新增数据域" open={domainOpen} onOk={() => domainForm.submit()} onCancel={() => setDomainOpen(false)}>
        <Form form={domainForm} layout="vertical" onFinish={async (v) => { await apiClient.post(`/projects/${projectId}/domains`, v); message.success('已创建'); setDomainOpen(false); fetchAll() }}>
          <Form.Item name="name" label="标识" rules={[{ required: true }]}><Input placeholder="production_domain" /></Form.Item>
          <Form.Item name="display_name" label="名称" rules={[{ required: true }]}><Input placeholder="生产调度" /></Form.Item>
          <Form.Item name="description" label="描述"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>

      {/* 新建/编辑模型表 - 含字段定义 */}
      <Modal title={editModelId ? '编辑模型表' : '新建模型表'} open={modelOpen}
        onOk={() => modelForm.submit()} onCancel={() => { setModelOpen(false); setTempFields([]) }} width={700}>
        <Form form={modelForm} layout="vertical" onFinish={handleSaveModel}>
          <Row gutter={16}>
            <Col span={10}><Form.Item name="code" label="编码" rules={[{ required: true }]}><Input placeholder="dim_employee" /></Form.Item></Col>
            <Col span={10}><Form.Item name="name" label="名称" rules={[{ required: true }]}><Input placeholder="人员维度表" /></Form.Item></Col>
            <Col span={4}><Form.Item name="version" label="版本" initialValue="1.0"><Input /></Form.Item></Col>
          </Row>
          <Row gutter={16}>
            <Col span={6}><Form.Item name="table_type" label="类型" initialValue="DIM"><Select options={['DIM','FACT','DWD','DWS','ADS'].map(v=>({value:v,label:v}))} /></Form.Item></Col>
            <Col span={6}><Form.Item name="domain_id" label="数据域" rules={[{ required: true }]}><Select options={domains.map(d => ({ value: d.id, label: d.display_name }))} /></Form.Item></Col>
            <Col span={6}><Form.Item name="source_gold_table" label="来源表"><Input placeholder="users" /></Form.Item></Col>
            <Col span={6}><Form.Item name="target_gold_table" label="目标表"><Input placeholder="dim_employee" /></Form.Item></Col>
          </Row>
          <Form.Item name="primary_key_field" label="主键字段"><Input placeholder="EMPLOYEE_CODE" /></Form.Item>

          {/* 字段定义 */}
          <Divider orientation="left" style={{ fontSize: 13, marginTop: 0 }}>模型字段</Divider>
          {tempFields.map((f) => (
            <Row key={f.key} gutter={8} style={{ marginBottom: 6 }} align="middle">
              <Col flex="auto">
                <Input size="small" placeholder="编码" value={f.code}
                  onChange={e => updateTempField(f.key, 'code', e.target.value)}
                  style={{ fontFamily: 'monospace', fontSize: 12 }} />
              </Col>
              <Col flex="auto">
                <Input size="small" placeholder="名称" value={f.name}
                  onChange={e => updateTempField(f.key, 'name', e.target.value)} />
              </Col>
              <Col flex="80px">
                <Select size="small" value={f.data_type} onChange={v => updateTempField(f.key, 'data_type', v)}
                  style={{ width: '100%' }}
                  options={['VARCHAR','INTEGER','BIGINT','DECIMAL','TIMESTAMP','DATE','TEXT','BOOLEAN'].map(v=>({value:v,label:v}))} />
              </Col>
              <Col flex="60px">
                <Select size="small" value={f.source_field || undefined} onChange={v => updateTempField(f.key, 'source_field', v || '')}
                  style={{ width: '100%' }} placeholder="来源"
                  options={[{value:'',label:'—'},...['id','username','email','display_name','is_active','created_at','updated_at'].map(v=>({value:v,label:v}))]} />
              </Col>
              <Col flex="40px">
                <Checkbox checked={f.is_primary_key} onChange={e => updateTempField(f.key, 'is_primary_key', e.target.checked)} />
              </Col>
              <Col flex="30px">
                <Button type="text" size="small" danger icon={<MinusCircleOutlined />} onClick={() => removeTempField(f.key)} />
              </Col>
            </Row>
          ))}
          <Button type="dashed" icon={<PlusOutlined />} onClick={addTempField} block style={{ marginBottom: 12 }}>
            添加字段
          </Button>

          <Form.Item name="description" label="描述"><Input.TextArea rows={1} /></Form.Item>
        </Form>
      </Modal>

      {/* 字段管理弹窗 (已有模型) */}
      <Modal title={`字段管理: ${fieldsModel?.name || ''}`} open={fieldsOpen} onCancel={() => setFieldsOpen(false)} footer={null} width={700}>
        <Space style={{ marginBottom: 12 }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { fieldForm.resetFields(); setFieldOpen(true) }}>添加字段</Button>
          <Button icon={<ImportOutlined />}
            onClick={() => handleImportFields(fieldsModel!.id, fieldsModel!.source_gold_table || '')}
            disabled={!fieldsModel?.source_gold_table}>从 Gold 表导入</Button>
        </Space>
        <Table dataSource={fields} rowKey="id" size="small" pagination={false}
          columns={[
            { title: '编码', dataIndex: 'code', width: 130, render: (v: string) => <Text code style={{fontSize:11}}>{v}</Text> },
            { title: '名称', dataIndex: 'name', width: 100 },
            { title: '类型', dataIndex: 'data_type', width: 80, render: (v: string) => <Text style={{fontSize:11}}>{v}</Text> },
            { title: '主键', dataIndex: 'is_primary_key', width: 50, render: (v: boolean) => v ? <Tag color="red">PK</Tag> : null },
            { title: '外键', dataIndex: 'is_foreign_key', width: 50, render: (v: boolean) => v ? <Tag color="orange">FK</Tag> : null },
            { title: '来源', dataIndex: 'source_field', width: 100, render: (v: string|null) => v || '—' },
            { title: '操作', width: 50, render: (_: any, r: ModelFieldItem) => (
              <Popconfirm title="确认删除?" onConfirm={() => handleDeleteField(r.id)}>
                <Button size="small" danger icon={<DeleteOutlined />} />
              </Popconfirm>
            )},
          ]} />
      </Modal>

      <Modal title="添加字段" open={fieldOpen} onOk={() => fieldForm.submit()} onCancel={() => setFieldOpen(false)}>
        <Form form={fieldForm} layout="vertical" onFinish={handleSaveField}>
          <Row gutter={16}>
            <Col span={12}><Form.Item name="code" label="编码" rules={[{ required: true }]}><Input placeholder="EMPLOYEE_CODE" /></Form.Item></Col>
            <Col span={12}><Form.Item name="name" label="名称" rules={[{ required: true }]}><Input placeholder="人员编码" /></Form.Item></Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}><Form.Item name="data_type" label="类型" initialValue="VARCHAR"><Input placeholder="VARCHAR(50)" /></Form.Item></Col>
            <Col span={12}><Form.Item name="source_field" label="来源字段"><Input placeholder="code" /></Form.Item></Col>
          </Row>
          <Space>
            <Form.Item name="is_primary_key" valuePropName="checked"><Checkbox>主键</Checkbox></Form.Item>
            <Form.Item name="is_foreign_key" valuePropName="checked"><Checkbox>外键</Checkbox></Form.Item>
          </Space>
          <Form.Item name="quality_rule" label="质量规则"><Input placeholder="not_null" /></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

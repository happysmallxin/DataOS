/**
 * 数据质量中心 — 持久化规则 CRUD + 执行检查.
 */
import { useEffect, useState } from 'react'
import {
  Card, Table, Tag, Button, Space, Typography, Statistic, Row, Col,
  Modal, Form, Input, Select, InputNumber, message, Spin, Popconfirm, Tooltip,
} from 'antd'
import {
  PlusOutlined, CheckCircleOutlined, CloseCircleOutlined,
  PlayCircleOutlined, DeleteOutlined, ReloadOutlined, EditOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import apiClient from '../utils/api'
import { usePermission } from '../hooks/usePermission'

const { Title, Text } = Typography

interface PersistedRule {
  id: number
  project_id: number
  name: string
  rule_type: string
  target_column: string | null
  config: Record<string, unknown>
  description: string | null
  is_enabled: boolean
  created_at: string
}

const ruleTypes = [
  { value: 'not_null', label: '非空校验', desc: '检查指定列是否包含空值' },
  { value: 'range', label: '范围校验', desc: '检查数值是否在指定范围内' },
  { value: 'regex', label: '格式校验', desc: '正则匹配检查字段格式' },
  { value: 'unique', label: '唯一性检查', desc: '检查指定列是否有重复值' },
  { value: 'custom_sql', label: '自定义规则', desc: 'DataFrame.eval 表达式条件' },
]

const typeColorMap: Record<string, string> = {
  not_null: 'blue', range: 'orange', regex: 'purple', unique: 'cyan', custom_sql: 'geekblue',
}

export default function DataQuality() {
  const { can } = usePermission()
  const [rules, setRules] = useState<PersistedRule[]>([])
  const [loading, setLoading] = useState(true)
  const [projectId, setProjectId] = useState(3) // 演示项目

  // Create/Edit
  const [formOpen, setFormOpen] = useState(false)
  const [editingRule, setEditingRule] = useState<PersistedRule | null>(null)
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)

  // Execute check
  const [checkOpen, setCheckOpen] = useState(false)
  const [checkForm] = Form.useForm()
  const [checking, setChecking] = useState(false)
  const [checkResult, setCheckResult] = useState<any>(null)

  // ---- data ----

  const fetchRules = async () => {
    setLoading(true)
    try {
      const resp = await apiClient.get('/quality/rules', { params: { project_id: projectId } })
      setRules(resp.data)
    } catch { message.error('获取规则列表失败') }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchRules() }, [projectId])

  // ---- CRUD ----

  const openCreate = () => {
    setEditingRule(null)
    form.resetFields()
    form.setFieldsValue({ rule_type: 'not_null' })
    setFormOpen(true)
  }

  const openEdit = (rule: PersistedRule) => {
    setEditingRule(rule)
    form.setFieldsValue({
      name: rule.name,
      rule_type: rule.rule_type,
      target_column: rule.target_column,
      description: rule.description,
      ...rule.config,
    })
    setFormOpen(true)
  }

  const handleSave = async () => {
    const values = await form.validateFields()
    const { name, rule_type, target_column, description, ...rest } = values
    const config: Record<string, unknown> = {}
    if (rule_type === 'range') { config.min = rest.min; config.max = rest.max }
    if (rule_type === 'regex') config.pattern = rest.pattern
    if (rule_type === 'custom_sql') config.condition = rest.condition

    setSubmitting(true)
    try {
      if (editingRule) {
        await apiClient.put(`/quality/rules/${editingRule.id}`, {
          name, rule_type, target_column: target_column || null, config, description,
        })
        message.success('规则已更新')
      } else {
        await apiClient.post('/quality/rules', {
          project_id: projectId, name, rule_type,
          target_column: target_column || null, config, description,
        })
        message.success('规则已创建')
      }
      setFormOpen(false)
      fetchRules()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '保存失败')
    } finally { setSubmitting(false) }
  }

  const handleDelete = async (id: number) => {
    try {
      await apiClient.delete(`/quality/rules/${id}`)
      message.success('规则已删除')
      fetchRules()
    } catch (err: any) { message.error(err.response?.data?.detail || '删除失败') }
  }

  // ---- execute check ----

  const handleRunCheck = async (values: any) => {
    if (!values.rule_ids || values.rule_ids.length === 0) {
      message.warning('请选择至少一条规则')
      return
    }
    setChecking(true)
    try {
      const sampleData = values.data
        ? JSON.parse(values.data)
        : [{ id: 1, name: '设备A', temp: 35.5 }, { id: 2, name: '设备B', temp: 42.0 }, { id: null, name: '设备C', temp: 28.0 }]

      const resp = await apiClient.post('/quality/check', {
        data: sampleData,
        rule_ids: values.rule_ids,
      })
      setCheckResult(resp.data)
    } catch (err: any) {
      message.error(err.response?.data?.detail || '检查失败')
    } finally { setChecking(false) }
  }

  // ---- columns ----

  const columns: ColumnsType<PersistedRule> = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 160 },
    {
      title: '类型', dataIndex: 'rule_type', key: 'type', width: 100,
      render: (t: string) => <Tag color={typeColorMap[t] || 'default'}>{ruleTypes.find(r => r.value === t)?.label || t}</Tag>,
    },
    {
      title: '目标列', dataIndex: 'target_column', key: 'col', width: 120,
      render: (c: string | null) => c ? <Text code>{c}</Text> : <Text type="secondary">不指定</Text>,
    },
    {
      title: '配置', dataIndex: 'config', key: 'config', ellipsis: true,
      render: (c: Record<string, unknown>) => {
        const entries = Object.entries(c || {})
        return entries.length > 0
          ? <Text style={{ fontSize: 12 }}>{entries.map(([k, v]) => `${k}=${v}`).join(', ')}</Text>
          : <Text type="secondary">—</Text>
      },
    },
    {
      title: '启用', dataIndex: 'is_enabled', key: 'enabled', width: 60,
      render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? '是' : '否'}</Tag>,
    },
    {
      title: '操作', key: 'action', width: 150,
      render: (_: unknown, record: PersistedRule) => (
        <Space size="small">
          <Tooltip title="编辑"><Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} /></Tooltip>
          <Popconfirm title="确认删除此规则?" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  // ---- render ----

  const ruleTypeExtra = (type: string) => {
    const fields = []
    if (type === 'not_null' || type === 'unique') {
      // no extra config
    } else if (type === 'range') {
      fields.push(<Form.Item key="min" name="min" label="最小值" style={{ display: 'inline-block', width: '48%' }}><InputNumber style={{ width: '100%' }} /></Form.Item>)
      fields.push(<Form.Item key="max" name="max" label="最大值" style={{ display: 'inline-block', width: '48%', marginLeft: '4%' }}><InputNumber style={{ width: '100%' }} /></Form.Item>)
    } else if (type === 'regex') {
      fields.push(<Form.Item key="pattern" name="pattern" label="正则表达式"><Input placeholder="^[A-Za-z]+$" /></Form.Item>)
    } else if (type === 'custom_sql') {
      fields.push(<Form.Item key="condition" name="condition" label="表达式 (DataFrame.eval)"><Input placeholder="column > 0" /></Form.Item>)
    }
    return <>{fields}</>
  }

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>数据质量中心</Title>

      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={6}>
          <Card><Statistic title="规则总数" value={rules.length} suffix="条" /></Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card><Statistic title="已启用" value={rules.filter(r => r.is_enabled).length} suffix="条" valueStyle={{ color: '#3f8600' }} /></Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic title="最近检查" value={checkResult ? `${checkResult.overall_pass_rate}%` : '—'}
              suffix={checkResult ? '通过率' : ''} valueStyle={{ color: '#3f8600' }} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic title="项目" value={`#${projectId}`} suffix={
              <Select size="small" value={projectId} onChange={setProjectId} style={{ width: 80 }} bordered={false}
                options={[{ value: 1, label: '#1' }, { value: 3, label: '演示' }]} />
            } />
          </Card>
        </Col>
      </Row>

      {/* 规则表格 */}
      <Card
        title="质量规则"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={fetchRules} loading={loading}>刷新</Button>
            <Button icon={<PlayCircleOutlined />} onClick={() => setCheckOpen(true)}>执行检查</Button>
            {can('quality:create') && (
              <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增规则</Button>
            )}
          </Space>
        }
      >
        {loading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : (
          <Table columns={columns} dataSource={rules} rowKey="id" size="middle"
            locale={{ emptyText: '暂无质量规则，点击"新增规则"创建' }}
            pagination={rules.length > 15 ? { pageSize: 15 } : false} />
        )}
      </Card>

      {/* 创建/编辑规则弹窗 */}
      <Modal
        title={editingRule ? '编辑规则' : '新增规则'}
        open={formOpen}
        onOk={handleSave}
        onCancel={() => { setFormOpen(false); form.resetFields() }}
        confirmLoading={submitting}
        width={520}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="规则名称" rules={[{ required: true }]}>
            <Input placeholder="如: 用户ID非空检查" />
          </Form.Item>
          <Form.Item name="rule_type" label="规则类型" rules={[{ required: true }]}>
            <Select options={ruleTypes.map(t => ({ value: t.value, label: `${t.label} — ${t.desc}` }))} />
          </Form.Item>
          <Form.Item name="target_column" label="目标列">
            <Input placeholder="可选, 如: username" />
          </Form.Item>
          <Form.Item noStyle shouldUpdate={(prev, cur) => prev.rule_type !== cur.rule_type}>
            {({ getFieldValue }) => ruleTypeExtra(getFieldValue('rule_type') || 'not_null')}
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="可选描述" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 执行检查弹窗 */}
      <Modal
        title="执行质量检查"
        open={checkOpen}
        onCancel={() => { setCheckOpen(false); setCheckResult(null) }}
        onOk={() => checkForm.submit()}
        confirmLoading={checking}
        width={600}
      >
        <Form form={checkForm} layout="vertical" onFinish={handleRunCheck}>
          <Form.Item name="rule_ids" label="选择规则" rules={[{ required: true }]}>
            <Select mode="multiple" placeholder="选择要执行的规则"
              options={rules.filter(r => r.is_enabled).map(r => ({ value: r.id, label: `${r.name} (${r.rule_type})` }))} />
          </Form.Item>
          <Form.Item name="data" label="测试数据 (JSON, 可选)">
            <Input.TextArea rows={6} placeholder='[{"id":1,"name":"A","temp":35.5},{"id":null,"name":"C","temp":28}]' />
          </Form.Item>
        </Form>
        {checkResult && (
          <Card size="small" style={{ marginTop: 12, background: '#f6f8fa' }}>
            <Row gutter={16} style={{ marginBottom: 8 }}>
              <Col span={8}><Statistic title="规则数" value={checkResult.total_rules} /></Col>
              <Col span={8}><Statistic title="通过" value={checkResult.passed_rules} valueStyle={{ color: '#3f8600' }} prefix={<CheckCircleOutlined />} /></Col>
              <Col span={8}><Statistic title="失败" value={checkResult.failed_rules} valueStyle={{ color: '#cf1322' }} prefix={<CloseCircleOutlined />} /></Col>
            </Row>
            <Table dataSource={checkResult.results || []} rowKey="rule_name" size="small" pagination={false}
              columns={[
                { title: '规则', dataIndex: 'rule_name', ellipsis: true },
                { title: '结果', dataIndex: 'passed', width: 70, render: (v: boolean) => v ? <Tag color="green">通过</Tag> : <Tag color="red">失败</Tag> },
                { title: '通过率', dataIndex: 'pass_rate', width: 80, render: (v: number) => `${v}%` },
                { title: '信息', dataIndex: 'message', ellipsis: true },
              ]} />
          </Card>
        )}
      </Modal>
    </div>
  )
}

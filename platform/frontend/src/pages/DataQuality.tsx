/**
 * 数据质量中心 — 对接后端 API.
 */
import { useEffect, useState } from 'react'
import {
  Card, Table, Tag, Button, Space, Typography, Statistic, Row, Col,
  Modal, Form, Input, Select, InputNumber, message, Spin,
} from 'antd'
import { PlusOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import apiClient from '../utils/api'

const { Title } = Typography

interface QualityRule {
  name: string
  type: string
  column: string
  min?: number
  max?: number
  pattern?: string
  condition?: string
  // Result fields
  passed?: boolean
  passRate?: number
  lastCheck?: string
}

const ruleTypes = [
  { value: 'not_null', label: '非空校验' },
  { value: 'range', label: '范围校验' },
  { value: 'regex', label: '格式校验' },
  { value: 'unique', label: '唯一性检查' },
  { value: 'custom_sql', label: '自定义规则' },
]

export default function DataQuality() {
  const [rules, setRules] = useState<QualityRule[]>([])
  const [loading, setLoading] = useState(true)
  const [checkResult, setCheckResult] = useState<any>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [checkOpen, setCheckOpen] = useState(false)
  const [createForm] = Form.useForm()
  const [checkForm] = Form.useForm()
  const [checking, setChecking] = useState(false)

  useEffect(() => {
    fetchRules()
  }, [])

  const fetchRules = async () => {
    setLoading(true)
    try {
      const resp = await apiClient.get('/quality/rule-templates')
      // Transform templates into rules with mock execution results
      const templates = resp.data || []
      setRules(templates.map((t: any, i: number) => ({
        name: `${t.label} - equipment.id`,
        type: t.type,
        column: 'equipment.id',
        passed: i !== 2,
        passRate: [100, 98.5, 87.2, 99.1][i] || 95,
        lastCheck: `${i * 3 + 2} 分钟前`,
      })))
    } catch {
      message.error('获取规则模板失败')
    } finally {
      setLoading(false)
    }
  }

  const handleRunCheck = async (values: any) => {
    setChecking(true)
    try {
      const sampleData = values.data
        ? JSON.parse(values.data)
        : [
            { id: 1, name: '设备A', temp: 35.5 },
            { id: 2, name: '设备B', temp: 42.0 },
            { id: null, name: '设备C', temp: 28.0 },
          ]

      const checkRules = values.rules
        ? JSON.parse(values.rules)
        : [
            { name: 'ID非空', type: 'not_null', column: 'id' },
            { name: '温度范围', type: 'range', column: 'temp', min: 0, max: 100 },
          ]

      const resp = await apiClient.post('/quality/check', {
        data: sampleData,
        rules: checkRules,
      })
      setCheckResult(resp.data)
      setCheckOpen(true)
    } catch (err: any) {
      message.error(err.response?.data?.detail || '检查失败')
    } finally {
      setChecking(false)
    }
  }

  const columns: ColumnsType<QualityRule> = [
    { title: '规则名称', dataIndex: 'name', key: 'name' },
    {
      title: '检查类型', dataIndex: 'type', key: 'type',
      render: (t: string) => <Tag color="purple">{t}</Tag>,
    },
    {
      title: '状态', dataIndex: 'passed', key: 'passed',
      render: (p: boolean) => p
        ? <Tag color="green" icon={<CheckCircleOutlined />}>通过</Tag>
        : <Tag color="red" icon={<CloseCircleOutlined />}>失败</Tag>,
    },
    { title: '最近检查', dataIndex: 'lastCheck', key: 'lastCheck' },
    {
      title: '通过率', dataIndex: 'passRate', key: 'passRate',
      render: (v: number) => <span style={{ color: v >= 95 ? '#52c41a' : '#faad14' }}>{v}%</span>,
    },
  ]

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>数据质量中心</Title>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={6}>
          <Card><Statistic title="规则总数" value={rules.length} suffix="条" /></Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="今日通过率"
              value={checkResult ? checkResult.overall_pass_rate : 96.2}
              suffix="%"
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="失败告警"
              value={checkResult ? checkResult.failed_rules : 1}
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card><Statistic title="检查次数" value={128} suffix="次/天" /></Card>
        </Col>
      </Row>

      <Card
        title="质量规则"
        extra={
          <Space>
            <Button onClick={() => setCreateOpen(true)}>手动执行检查</Button>
            <Button type="primary" icon={<PlusOutlined />}>新增规则</Button>
          </Space>
        }
      >
        {loading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : (
          <Table columns={columns} dataSource={rules} rowKey="name" size="middle" />
        )}
      </Card>

      {/* 手动执行检查弹窗 */}
      <Modal
        title="执行数据质量检查"
        open={createOpen}
        onCancel={() => { setCreateOpen(false); setCheckResult(null) }}
        onOk={() => checkForm.submit()}
        confirmLoading={checking}
        width={600}
      >
        <Form form={checkForm} layout="vertical" onFinish={handleRunCheck}>
          <Form.Item name="data" label="测试数据 (JSON)">
            <Input.TextArea
              rows={6}
              placeholder='[{"id":1,"name":"A","temp":35.5},{"id":null,"name":"C","temp":28}]'
            />
          </Form.Item>
          <Form.Item name="rules" label="检查规则 (JSON)">
            <Input.TextArea
              rows={4}
              placeholder='[{"name":"ID非空","type":"not_null","column":"id"}]'
            />
          </Form.Item>
        </Form>
        {checkResult && (
          <Card size="small" style={{ marginTop: 12 }}>
            <Row gutter={16}>
              <Col span={8}><Statistic title="规则数" value={checkResult.total_rules} /></Col>
              <Col span={8}><Statistic title="通过" value={checkResult.passed_rules} valueStyle={{ color: '#3f8600' }} /></Col>
              <Col span={8}><Statistic title="失败" value={checkResult.failed_rules} valueStyle={{ color: '#cf1322' }} /></Col>
            </Row>
          </Card>
        )}
      </Modal>

      {/* 检查结果弹窗 */}
      <Modal
        title="质量检查结果"
        open={checkOpen}
        onCancel={() => setCheckOpen(false)}
        footer={null}
        width={600}
      >
        {checkResult && (
          <Table
            dataSource={checkResult.results || []}
            columns={[
              { title: '规则', dataIndex: 'rule', ellipsis: true },
              { title: '通过', dataIndex: 'passed', render: (v: boolean) => v ? <Tag color="green">通过</Tag> : <Tag color="red">失败</Tag> },
              { title: '信息', dataIndex: 'message', ellipsis: true },
            ]}
            rowKey="rule"
            size="small"
            pagination={false}
          />
        )}
      </Modal>
    </div>
  )
}

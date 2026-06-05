import { Card, Table, Tag, Button, Space, Typography, Statistic, Row, Col } from 'antd'
import { PlusOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

const { Title } = Typography

interface QualityRule {
  key: string
  name: string
  target: string
  type: string
  status: 'pass' | 'fail' | 'disabled'
  lastCheck: string
  passRate: number
}

const columns: ColumnsType<QualityRule> = [
  { title: '规则名称', dataIndex: 'name', key: 'name' },
  { title: '目标表/字段', dataIndex: 'target', key: 'target' },
  {
    title: '检查类型',
    dataIndex: 'type',
    key: 'type',
    render: (t: string) => <Tag color="purple">{t}</Tag>,
  },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    render: (s: string) => {
      const map: Record<string, { color: string; icon: React.ReactNode; text: string }> = {
        pass: { color: 'green', icon: <CheckCircleOutlined />, text: '通过' },
        fail: { color: 'red', icon: <CloseCircleOutlined />, text: '失败' },
        disabled: { color: 'default', text: '已禁用' },
      }
      return <Tag color={map[s]?.color} icon={map[s]?.icon}>{map[s]?.text}</Tag>
    },
  },
  { title: '最近检查', dataIndex: 'lastCheck', key: 'lastCheck' },
  {
    title: '通过率',
    dataIndex: 'passRate',
    key: 'passRate',
    render: (v: number) => <span style={{ color: v >= 95 ? '#52c41a' : '#faad14' }}>{v}%</span>,
  },
  {
    title: '操作',
    key: 'action',
    render: () => (
      <Space>
        <a>执行</a>
        <a>编辑</a>
        <a>日志</a>
      </Space>
    ),
  },
]

const mockData: QualityRule[] = [
  { key: '1', name: '设备ID非空检查', target: 'equipment.id', type: '非空校验', status: 'pass', lastCheck: '2 分钟前', passRate: 100 },
  { key: '2', name: '温度范围校验', target: 'sensor.temp', type: '范围校验', status: 'pass', lastCheck: '2 分钟前', passRate: 98.5 },
  { key: '3', name: '时间戳格式校验', target: 'events.timestamp', type: '格式校验', status: 'fail', lastCheck: '5 分钟前', passRate: 87.2 },
  { key: '4', name: '重复数据检测', target: 'raw_data', type: '去重检查', status: 'pass', lastCheck: '10 分钟前', passRate: 99.1 },
]

export default function DataQuality() {
  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>数据质量中心</Title>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={6}>
          <Card><Statistic title="规则总数" value={4} suffix="条" /></Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card><Statistic title="今日通过率" value={96.2} suffix="%" valueStyle={{ color: '#3f8600' }} /></Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card><Statistic title="失败告警" value={1} valueStyle={{ color: '#cf1322' }} /></Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card><Statistic title="检查次数" value={128} suffix="次/天" /></Card>
        </Col>
      </Row>

      <Card
        title="质量规则"
        extra={<Button type="primary" icon={<PlusOutlined />}>新增规则</Button>}
      >
        <Table columns={columns} dataSource={mockData} />
      </Card>
    </div>
  )
}

import { Card, Col, Row, Statistic, Tag, List, Typography, Space } from 'antd'
import {
  DatabaseOutlined,
  BugOutlined,
  ApiOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  SyncOutlined,
} from '@ant-design/icons'

const { Title, Text } = Typography

// 组件状态模拟数据 — Phase 2 接入真实 API
const componentStatus = [
  { name: 'DolphinScheduler', url: 'http://localhost:12345', status: 'running' as const },
  { name: 'OpenMetadata', url: 'http://localhost:8585', status: 'running' as const },
  { name: 'SeaTunnel', url: 'http://localhost:8080', status: 'pending' as const },
  { name: 'Crawlab', url: 'http://localhost:8088', status: 'running' as const },
  { name: 'Datavines', url: 'http://localhost:5600', status: 'pending' as const },
  { name: 'Directus', url: 'http://localhost:8055', status: 'pending' as const },
]

const statusConfig = {
  running: { color: 'green', icon: <CheckCircleOutlined />, text: '运行中' },
  pending: { color: 'orange', icon: <SyncOutlined spin />, text: '待启动' },
  error: { color: 'red', icon: <ExclamationCircleOutlined />, text: '异常' },
}

export default function Dashboard() {
  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>工作台</Title>

      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <Statistic title="数据源" value={3} prefix={<DatabaseOutlined />} suffix="个" />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <Statistic title="爬虫任务" value={5} prefix={<BugOutlined />} suffix="个" />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <Statistic title="数据 API" value={12} prefix={<ApiOutlined />} suffix="个" />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <Statistic title="质量规则" value={8} prefix={<SafetyCertificateOutlined />} suffix="条" />
          </Card>
        </Col>
      </Row>

      {/* 组件状态 */}
      <Card title="平台组件状态">
        <List
          dataSource={componentStatus}
          renderItem={(item) => {
            const config = statusConfig[item.status]
            return (
              <List.Item
                extra={
                  <Space>
                    <Text type="secondary" style={{ fontSize: 12 }}>{item.url}</Text>
                    <Tag color={config.color} icon={config.icon}>{config.text}</Tag>
                  </Space>
                }
              >
                <List.Item.Meta
                  title={<Text strong>{item.name}</Text>}
                  description={
                    <Text type="secondary">
                      {item.status === 'running' ? '服务正常' : '尚未启动，请执行 docker compose up'}
                    </Text>
                  }
                />
              </List.Item>
            )
          }}
        />
      </Card>
    </div>
  )
}

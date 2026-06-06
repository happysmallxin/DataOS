/**
 * 工作台 Dashboard — 实时组件状态 + 统计.
 */
import { useEffect, useState } from 'react'
import { Card, Col, Row, Statistic, Tag, List, Typography, Space, Spin } from 'antd'
import {
  DatabaseOutlined,
  BugOutlined,
  ApiOutlined,
  SafetyCertificateOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons'
import apiClient from '../utils/api'

const { Title, Text } = Typography

interface ComponentItem {
  name: string
  url: string
  healthy: boolean
  message?: string
}

export default function Dashboard() {
  const [components, setComponents] = useState<ComponentItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const resp = await apiClient.get('/health')
        setComponents(resp.data.components || [])
      } catch {
        // Keep empty on error
      } finally {
        setLoading(false)
      }
    }
    fetchHealth()
  }, [])

  const healthyCount = components.filter(c => c.healthy).length
  const totalCount = components.length

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>工作台</Title>

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

      <Card
        title={
          <Space>
            <span>平台组件状态</span>
            {!loading && (
              <Tag color={healthyCount === totalCount ? 'green' : 'orange'}>
                {healthyCount}/{totalCount} 正常
              </Tag>
            )}
          </Space>
        }
      >
        {loading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : (
          <List
            dataSource={components}
            renderItem={(item) => {
              const icon = item.healthy
                ? <CheckCircleOutlined style={{ color: '#52c41a' }} />
                : <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
              return (
                <List.Item
                  extra={
                    <Space>
                      <Text type="secondary" style={{ fontSize: 12 }}>{item.url}</Text>
                      <Tag color={item.healthy ? 'green' : 'red'} icon={icon}>
                        {item.healthy ? '正常' : '异常'}
                      </Tag>
                    </Space>
                  }
                >
                  <List.Item.Meta
                    title={<Text strong>{item.name}</Text>}
                    description={
                      <Text type="secondary">
                        {item.healthy ? '服务正常' : item.message || '服务不可达'}
                      </Text>
                    }
                  />
                </List.Item>
              )
            }}
          />
        )}
      </Card>
    </div>
  )
}

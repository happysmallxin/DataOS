import { Card, Typography, Descriptions, Tag, Space, Divider } from 'antd'
import { CheckCircleOutlined, ExclamationCircleOutlined } from '@ant-design/icons'

const { Title, Text, Paragraph } = Typography

export default function Settings() {
  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>平台设置</Title>

      <Card title="组件连接配置" style={{ marginBottom: 24 }}>
        <Descriptions column={2} bordered size="small">
          <Descriptions.Item label="DolphinScheduler">
            <Tag icon={<CheckCircleOutlined />} color="green">连接正常</Tag>
            <Text type="secondary" style={{ marginLeft: 8 }}>localhost:12345</Text>
          </Descriptions.Item>
          <Descriptions.Item label="OpenMetadata">
            <Tag color="orange">待启动</Tag>
            <Text type="secondary" style={{ marginLeft: 8 }}>localhost:8585</Text>
          </Descriptions.Item>
          <Descriptions.Item label="SeaTunnel">
            <Tag color="orange">待启动</Tag>
            <Text type="secondary" style={{ marginLeft: 8 }}>localhost:8080</Text>
          </Descriptions.Item>
          <Descriptions.Item label="Crawlab">
            <Tag color="orange">待启动</Tag>
            <Text type="secondary" style={{ marginLeft: 8 }}>localhost:8088</Text>
          </Descriptions.Item>
          <Descriptions.Item label="Datavines">
            <Tag color="orange">待启动</Tag>
            <Text type="secondary" style={{ marginLeft: 8 }}>localhost:5600</Text>
          </Descriptions.Item>
          <Descriptions.Item label="Directus">
            <Tag color="orange">待启动</Tag>
            <Text type="secondary" style={{ marginLeft: 8 }}>localhost:8055</Text>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="关于 DataOS">
        <Paragraph>
          DataOS 是企业级数据治理平台，作为 RelOS（关系操作系统）的上游，
          负责多源数据采集、清洗、标准化和服务化，为 RelOS 提供高质量的关系数据输入。
        </Paragraph>
        <Divider />
        <Space direction="vertical">
          <Text>版本: <Text code>0.1.0-alpha</Text></Text>
          <Text>Phase 1 — 底座搭建</Text>
          <Text type="secondary">对标: Alibaba DataWorks + ByteDance DataLeap</Text>
        </Space>
      </Card>
    </div>
  )
}

/**
 * 数据集生成 — (待实现) 选模型→配置字段→预览→发布.
 */
import { Card, Typography } from 'antd'
const { Title, Text } = Typography

export default function DatasetGeneration() {
  return (
    <div>
      <Title level={4}>数据集生成</Title>
      <Card>
        <Text type="secondary">
          数据集生成模块待实现。流程: 选择已发布模型 → 配置输出字段 → 设置标签和版本 → 预览数据 → 执行生成 → 质量验收 → 发布。
        </Text>
      </Card>
    </div>
  )
}

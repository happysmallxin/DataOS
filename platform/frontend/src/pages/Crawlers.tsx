import { Card, Table, Tag, Button, Space, Typography, Progress } from 'antd'
import { PlusOutlined, PlayCircleOutlined, PauseCircleOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'

const { Title } = Typography

interface CrawlerRecord {
  key: string
  name: string
  target: string
  framework: string
  status: 'running' | 'stopped' | 'scheduled'
  lastRun: string
  dataCount: number
}

const columns: ColumnsType<CrawlerRecord> = [
  { title: '任务名称', dataIndex: 'name', key: 'name' },
  { title: '目标网站', dataIndex: 'target', key: 'target' },
  {
    title: '框架',
    dataIndex: 'framework',
    key: 'framework',
    render: (fw: string) => <Tag>{fw}</Tag>,
  },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    render: (s: string) => {
      const map: Record<string, { color: string; text: string }> = {
        running: { color: 'green', text: '运行中' },
        stopped: { color: 'default', text: '已停止' },
        scheduled: { color: 'blue', text: '定时' },
      }
      return <Tag color={map[s]?.color}>{map[s]?.text}</Tag>
    },
  },
  { title: '上次执行', dataIndex: 'lastRun', key: 'lastRun' },
  { title: '采集量', dataIndex: 'dataCount', key: 'dataCount', render: (v: number) => `${v.toLocaleString()} 条` },
  {
    title: '操作',
    key: 'action',
    render: () => (
      <Space>
        <Button size="small" icon={<PlayCircleOutlined />} type="primary">启动</Button>
        <Button size="small" icon={<PauseCircleOutlined />}>停止</Button>
        <a>日志</a>
      </Space>
    ),
  },
]

const mockData: CrawlerRecord[] = [
  { key: '1', name: '行业新闻采集', target: 'news.industry.com', framework: 'Scrapy', status: 'running', lastRun: '10 分钟前', dataCount: 12580 },
  { key: '2', name: '设备价格监控', target: 'b2b-platform.com', framework: 'Crawlee', status: 'scheduled', lastRun: '1 小时前', dataCount: 3420 },
  { key: '3', name: '竞品数据抓取', target: 'competitor.com', framework: 'Scrapy', status: 'stopped', lastRun: '3 天前', dataCount: 890 },
]

export default function Crawlers() {
  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <Title level={4} style={{ margin: 0 }}>网页爬取管理</Title>
        <Button type="primary" icon={<PlusOutlined />}>新建爬虫任务</Button>
      </div>
      <Card>
        <Table columns={columns} dataSource={mockData} />
      </Card>
    </div>
  )
}

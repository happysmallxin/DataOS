/**
 * 数据建模 — 数据域 + 业务过程管理.
 */
import { useEffect, useState } from 'react'
import { Card, Table, Tag, Button, Space, Typography, Select, message, Popconfirm, Form, Modal, Input } from 'antd'
import { PlusOutlined, ReloadOutlined, DeleteOutlined } from '@ant-design/icons'
import apiClient from '../utils/api'

const { Title, Text } = Typography

interface DomainItem { id: number; name: string; display_name: string; description: string | null }
interface ProcessItem { id: number; domain_id: number; name: string; display_name: string; table_type: string; source_tables: string[] | null; target_tables: string[] | null }

export default function DataModeling() {
  const [domains, setDomains] = useState<DomainItem[]>([])
  const [processes, setProcesses] = useState<ProcessItem[]>([])
  const [loading, setLoading] = useState(false)
  const [projectId, setProjectId] = useState(3)
  const [domainOpen, setDomainOpen] = useState(false)
  const [processOpen, setProcessOpen] = useState(false)
  const [form] = Form.useForm()
  const [pForm] = Form.useForm()

  const fetchData = async () => {
    setLoading(true)
    try {
      const [d, p] = await Promise.all([
        apiClient.get(`/projects/${projectId}/domains`),
        apiClient.get(`/projects/${projectId}/processes`),
      ])
      setDomains(d.data || []); setProcesses(p.data || [])
    } catch { message.error('获取数据失败') }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchData() }, [projectId])

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <Title level={4} style={{ margin: 0 }}>数据建模</Title>
        <Space>
          <Select value={projectId} onChange={setProjectId} style={{ width: 140 }}
            options={[{ value: 3, label: '演示项目' }]} />
          <Button icon={<ReloadOutlined />} onClick={fetchData}>刷新</Button>
          <Button icon={<PlusOutlined />} onClick={() => { form.resetFields(); setDomainOpen(true) }}>新增数据域</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { pForm.resetFields(); setProcessOpen(true) }}>新增业务过程</Button>
        </Space>
      </div>

      <Card title="数据域" size="small" style={{ marginBottom: 16 }}>
        {domains.length === 0 ? <Text type="secondary">暂无</Text> : (
          domains.map((d: any) => (
            <Tag key={d.id} color="blue" style={{ margin: 4, padding: '4px 12px', fontSize: 14 }}>
              📁 {d.display_name} <Text type="secondary" style={{ fontSize: 12 }}>({d.name})</Text>
            </Tag>
          ))
        )}
      </Card>

      <Card title="业务过程">
        <Table dataSource={processes} rowKey="id" loading={loading} size="middle" pagination={false}
          locale={{ emptyText: '暂无' }}
          columns={[
            { title: '名称', dataIndex: 'display_name', width: 120 },
            { title: '标识', dataIndex: 'name', width: 140, render: (v: string) => <Text code>{v}</Text> },
            { title: '数据域', dataIndex: 'domain_id', width: 80, render: (v: number) => domains.find(d => d.id === v)?.display_name || `#${v}` },
            { title: '类型', dataIndex: 'table_type', width: 70, render: (v: string) => <Tag>{v}</Tag> },
            { title: '源表', dataIndex: 'source_tables', ellipsis: true, render: (v: any) => v?.join(', ') || '—' },
            { title: '目标表', dataIndex: 'target_tables', ellipsis: true, render: (v: any) => v?.join(', ') || '—' },
            { title: '操作', width: 60, render: (_: any, r: ProcessItem) => (
              <Popconfirm title="确认删除?" onConfirm={async () => { await apiClient.delete(`/projects/${projectId}/processes/${r.id}`); fetchData() }}>
                <Button size="small" danger icon={<DeleteOutlined />} />
              </Popconfirm>
            )},
          ]} />
      </Card>

      <Modal title="新增数据域" open={domainOpen} onOk={() => form.submit()} onCancel={() => setDomainOpen(false)}>
        <Form form={form} layout="vertical" onFinish={async (v) => { await apiClient.post(`/projects/${projectId}/domains`, v); message.success('已创建'); setDomainOpen(false); fetchData() }}>
          <Form.Item name="name" label="标识" rules={[{ required: true }]}><Input placeholder="trade_domain" /></Form.Item>
          <Form.Item name="display_name" label="名称" rules={[{ required: true }]}><Input placeholder="交易域" /></Form.Item>
          <Form.Item name="description" label="描述"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>

      <Modal title="新增业务过程" open={processOpen} onOk={() => pForm.submit()} onCancel={() => setProcessOpen(false)}>
        <Form form={pForm} layout="vertical" onFinish={async (v) => { await apiClient.post(`/projects/${projectId}/domains/${v.domain_id}/processes`, v); message.success('已创建'); setProcessOpen(false); fetchData() }}>
          <Form.Item name="domain_id" label="数据域 ID" rules={[{ required: true }]}><Input type="number" placeholder="1" /></Form.Item>
          <Form.Item name="name" label="标识" rules={[{ required: true }]}><Input placeholder="order_create" /></Form.Item>
          <Form.Item name="display_name" label="名称" rules={[{ required: true }]}><Input placeholder="订单创建" /></Form.Item>
          <Form.Item name="table_type" label="表类型" initialValue="DWD">
            <Select options={[{value:'DIM',label:'DIM 维度表'},{value:'FACT',label:'FACT 事实表'},{value:'DWD',label:'DWD 明细表'},{value:'DWS',label:'DWS 汇总表'}]} />
          </Form.Item>
          <Form.Item name="description" label="描述"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

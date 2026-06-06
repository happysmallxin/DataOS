/**
 * 项目列表页 — 卡片 + 搜索 + 新建项目.
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Row, Col, Button, Input, Tag, Space, Typography, Modal, Form, message, Spin, Empty,
} from 'antd'
import { PlusOutlined, SearchOutlined, ProjectOutlined, DeleteOutlined, LockOutlined } from '@ant-design/icons'
import apiClient from '../api/client'
import { usePermission } from '../hooks/usePermission'

const { Title, Text } = Typography

interface Project {
  id: number
  name: string
  display_name: string
  description: string | null
  owner_id: number
  status: string
  member_count: number
  datasource_count: number
  created_at: string
  updated_at: string
}

const statusMap: Record<string, { color: string; text: string; icon: React.ReactNode }> = {
  active: { color: 'green', text: '活跃', icon: null },
  frozen: { color: 'blue', text: '已冻结', icon: <LockOutlined /> },
  archived: { color: 'default', text: '已归档', icon: null },
  deleted: { color: 'red', text: '已删除', icon: null },
}

export default function Projects() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string | undefined>('active')
  const [createOpen, setCreateOpen] = useState(false)
  const [createForm] = Form.useForm()
  const [creating, setCreating] = useState(false)
  const navigate = useNavigate()
  const { can } = usePermission()

  const fetchProjects = async () => {
    setLoading(true)
    try {
      const params: any = {}
      if (search) params.search = search
      if (statusFilter) params.status = statusFilter
      const resp = await apiClient.get('/projects', { params })
      setProjects(resp.data)
    } catch {
      message.error('获取项目列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchProjects()
  }, [statusFilter])

  const handleSearch = () => {
    fetchProjects()
  }

  const handleCreate = async (values: any) => {
    setCreating(true)
    try {
      await apiClient.post('/projects', values)
      message.success('项目创建成功')
      setCreateOpen(false)
      createForm.resetFields()
      fetchProjects()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '创建失败')
    } finally {
      setCreating(false)
    }
  }

  const handleFreeze = async (id: number) => {
    try {
      await apiClient.post(`/projects/${id}/freeze`)
      message.success('项目已冻结')
      fetchProjects()
    } catch {
      message.error('操作失败')
    }
  }

  const handleDelete = async (id: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '删除后项目将不可见，30天后自动清理。',
      onOk: async () => {
        await apiClient.delete(`/projects/${id}`)
        message.success('项目已删除')
        fetchProjects()
      },
    })
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <Title level={4} style={{ margin: 0 }}>项目管理</Title>
        <Space>
          <Input
            placeholder="搜索项目..."
            prefix={<SearchOutlined />}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 240 }}
          />
          <Button onClick={() => setStatusFilter(undefined)} type={!statusFilter ? 'primary' : 'default'}>
            全部
          </Button>
          <Button onClick={() => setStatusFilter('active')} type={statusFilter === 'active' ? 'primary' : 'default'}>
            活跃
          </Button>
          <Button onClick={() => setStatusFilter('frozen')} type={statusFilter === 'frozen' ? 'primary' : 'default'}>
            已冻结
          </Button>
          {can('project:create') && (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
              新建项目
            </Button>
          )}
        </Space>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>
      ) : projects.length === 0 ? (
        <Empty description="暂无项目" />
      ) : (
        <Row gutter={[16, 16]}>
          {projects.map((p) => {
            const st = statusMap[p.status] || statusMap.active
            return (
              <Col xs={24} sm={12} lg={8} key={p.id}>
                <Card
                  hoverable
                  onClick={() => navigate(`/projects/${p.id}`)}
                  actions={[
                    <Button type="link" onClick={(e) => { e.stopPropagation(); navigate(`/projects/${p.id}`) }}>
                      进入
                    </Button>,
                    can('project:update') && p.status === 'active' ? (
                      <Button type="link" onClick={(e) => { e.stopPropagation(); handleFreeze(p.id) }}>
                        冻结
                      </Button>
                    ) : null,
                    can('project:delete') ? (
                      <Button type="link" danger onClick={(e) => { e.stopPropagation(); handleDelete(p.id) }}>
                        <DeleteOutlined />
                      </Button>
                    ) : null,
                  ].filter(Boolean)}
                >
                  <Card.Meta
                    avatar={<ProjectOutlined style={{ fontSize: 28, color: '#2563eb' }} />}
                    title={
                      <Space>
                        {p.display_name}
                        <Tag color={st.color}>{st.icon}{st.text}</Tag>
                      </Space>
                    }
                    description={
                      <div>
                        <Text type="secondary" style={{ fontSize: 12 }}>{p.name}</Text>
                        {p.description && <div><Text type="secondary">{p.description}</Text></div>}
                        <div style={{ marginTop: 8 }}>
                          <Space size="middle">
                            <Text type="secondary">成员: {p.member_count}</Text>
                            <Text type="secondary">数据源: {p.datasource_count}</Text>
                          </Space>
                        </div>
                      </div>
                    }
                  />
                </Card>
              </Col>
            )
          })}
        </Row>
      )}

      {/* 新建项目弹窗 */}
      <Modal
        title="新建项目"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={() => createForm.submit()}
        confirmLoading={creating}
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="name" label="项目标识" rules={[{ required: true, pattern: /^[a-z0-9-]+$/, message: '小写字母、数字、连字符' }]}>
            <Input placeholder="my-project" />
          </Form.Item>
          <Form.Item name="display_name" label="显示名称" rules={[{ required: true }]}>
            <Input placeholder="我的项目" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

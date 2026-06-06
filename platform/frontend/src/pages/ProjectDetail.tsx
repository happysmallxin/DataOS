/**
 * 项目详情页 — Tab: 基本信息 / 成员管理 / 审计日志.
 */
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Tabs, Descriptions, Tag, Button, Table, Space, Typography, Modal, Select,
  Form, message, Spin, Popconfirm, Empty,
} from 'antd'
import { ArrowLeftOutlined, PlusOutlined, SwapOutlined } from '@ant-design/icons'
import apiClient from '../utils/api'
import { usePermission } from '../hooks/usePermission'

const { Title, Text } = Typography

interface ProjectInfo {
  id: number; name: string; display_name: string; description: string | null
  owner_id: number; status: string; member_count: number; datasource_count: number
  created_at: string; updated_at: string
}

interface Member {
  id: number; user_id: number; username: string; email: string
  role_id: number; role_name: string; role_display: string; joined_at: string
}

interface AuditEntry {
  id: number; user_id: number; username: string; resource: string; action: string
  target_name: string | null; detail: any; created_at: string
}

interface RoleOption {
  id: number; name: string; display_name: string
}

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const projectId = parseInt(id!)
  const navigate = useNavigate()
  const { can } = usePermission(projectId)

  const [project, setProject] = useState<ProjectInfo | null>(null)
  const [members, setMembers] = useState<Member[]>([])
  const [auditLogs, setAuditLogs] = useState<AuditEntry[]>([])
  const [roles, setRoles] = useState<RoleOption[]>([])
  const [loading, setLoading] = useState(true)
  const [addOpen, setAddOpen] = useState(false)
  const [addForm] = Form.useForm()
  const [transferOpen, setTransferOpen] = useState(false)
  const [transferUser, setTransferUser] = useState<number | null>(null)

  const fetchAll = async () => {
    setLoading(true)
    try {
      const [projResp, memberResp, auditResp, rolesResp] = await Promise.all([
        apiClient.get(`/projects/${projectId}`),
        apiClient.get(`/projects/${projectId}/members`),
        apiClient.get(`/projects/${projectId}/audit-logs`, { params: { page_size: 20 } }),
        apiClient.get('/roles', { params: { scope: 'project' } }),
      ])
      setProject(projResp.data)
      setMembers(memberResp.data)
      setAuditLogs(auditResp.data.items || [])
      setRoles(rolesResp.data)
    } catch {
      message.error('获取项目信息失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchAll() }, [projectId])

  const handleAddMember = async (values: any) => {
    try {
      await apiClient.post(`/projects/${projectId}/members`, {
        user_id: values.user_id,
        role_id: values.role_id,
      })
      message.success('成员添加成功')
      setAddOpen(false)
      addForm.resetFields()
      fetchAll()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '添加失败')
    }
  }

  const handleUpdateRole = async (userId: number, roleId: number) => {
    try {
      await apiClient.put(`/projects/${projectId}/members/${userId}`, { role_id: roleId })
      message.success('角色已更新')
      fetchAll()
    } catch {
      message.error('更新失败')
    }
  }

  const handleRemoveMember = async (userId: number) => {
    try {
      await apiClient.delete(`/projects/${projectId}/members/${userId}`)
      message.success('成员已移除')
      fetchAll()
    } catch {
      message.error('移除失败')
    }
  }

  const handleTransfer = async () => {
    if (!transferUser) return
    try {
      await apiClient.post(`/projects/${projectId}/transfer`, { new_owner_id: transferUser })
      message.success('项目转让成功')
      setTransferOpen(false)
      fetchAll()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '转让失败')
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>
  if (!project) return <Empty description="项目不存在" />

  const memberColumns = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '邮箱', dataIndex: 'email', key: 'email' },
    {
      title: '角色', dataIndex: 'role_display', key: 'role',
      render: (text: string, record: Member) => (
        can('project:manage_members') ? (
          <Select
            size="small"
            value={record.role_id}
            style={{ width: 140 }}
            onChange={(roleId) => handleUpdateRole(record.user_id, roleId)}
            options={roles.map(r => ({ value: r.id, label: r.display_name }))}
          />
        ) : (
          <Tag color="blue">{text}</Tag>
        )
      ),
    },
    { title: '加入时间', dataIndex: 'joined_at', key: 'joined_at', render: (d: string) => new Date(d).toLocaleDateString() },
    {
      title: '操作', key: 'action',
      render: (_: any, record: Member) => (
        can('project:manage_members') && record.role_name !== 'project_owner' ? (
          <Popconfirm title="确认移除该成员?" onConfirm={() => handleRemoveMember(record.user_id)}>
            <a>移除</a>
          </Popconfirm>
        ) : null
      ),
    },
  ]

  const auditColumns = [
    { title: '操作人', dataIndex: 'username', width: 100 },
    { title: '资源', dataIndex: 'resource', width: 80, render: (r: string) => <Tag>{r}</Tag> },
    { title: '操作', dataIndex: 'action', width: 80, render: (a: string) => <Tag color={a === 'delete' ? 'red' : 'blue'}>{a}</Tag> },
    { title: '目标', dataIndex: 'target_name', ellipsis: true },
    { title: '时间', dataIndex: 'created_at', width: 160, render: (d: string) => new Date(d).toLocaleString() },
  ]

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/projects')}>返回</Button>
        <Title level={4} style={{ margin: 0 }}>{project.display_name}</Title>
        <Tag color="blue">{project.status}</Tag>
      </div>

      <Tabs defaultActiveKey="info" items={[
        {
          key: 'info',
          label: '基本信息',
          children: (
            <Card>
              <Descriptions column={2} bordered size="small">
                <Descriptions.Item label="项目标识">{project.name}</Descriptions.Item>
                <Descriptions.Item label="显示名称">{project.display_name}</Descriptions.Item>
                <Descriptions.Item label="描述">{project.description || '-'}</Descriptions.Item>
                <Descriptions.Item label="状态"><Tag>{project.status}</Tag></Descriptions.Item>
                <Descriptions.Item label="成员数">{project.member_count}</Descriptions.Item>
                <Descriptions.Item label="数据源数">{project.datasource_count}</Descriptions.Item>
                <Descriptions.Item label="创建时间">{new Date(project.created_at).toLocaleString()}</Descriptions.Item>
                <Descriptions.Item label="更新时间">{new Date(project.updated_at).toLocaleString()}</Descriptions.Item>
              </Descriptions>
              {can('project:manage_members') && (
                <div style={{ marginTop: 16 }}>
                  <Button icon={<SwapOutlined />} onClick={() => setTransferOpen(true)}>转让项目</Button>
                </div>
              )}
            </Card>
          ),
        },
        {
          key: 'members',
          label: `成员 (${members.length})`,
          children: (
            <Card
              title="项目成员"
              extra={can('project:manage_members') && (
                <Button type="primary" icon={<PlusOutlined />} onClick={() => setAddOpen(true)}>
                  添加成员
                </Button>
              )}
            >
              <Table
                dataSource={members}
                columns={memberColumns}
                rowKey="id"
                pagination={false}
                size="middle"
              />
            </Card>
          ),
        },
        {
          key: 'audit',
          label: '审计日志',
          children: (
            <Card title="操作记录">
              {auditLogs.length === 0 ? (
                <Empty description="暂无审计日志" />
              ) : (
                <Table
                  dataSource={auditLogs}
                  columns={auditColumns}
                  rowKey="id"
                  size="middle"
                  pagination={{ pageSize: 15 }}
                />
              )}
            </Card>
          ),
        },
      ]} />

      {/* 添加成员弹窗 */}
      <Modal title="添加成员" open={addOpen} onCancel={() => setAddOpen(false)} onOk={() => addForm.submit()}>
        <Form form={addForm} layout="vertical" onFinish={handleAddMember}>
          <Form.Item name="user_id" label="用户 ID" rules={[{ required: true }]}>
            <Input type="number" placeholder="输入用户 ID" />
          </Form.Item>
          <Form.Item name="role_id" label="角色" rules={[{ required: true }]}>
            <Select options={roles.map(r => ({ value: r.id, label: `${r.display_name} (${r.name})` }))} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 转让弹窗 */}
      <Modal title="转让项目" open={transferOpen} onCancel={() => setTransferOpen(false)} onOk={handleTransfer}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text>选择新项目负责人 (必须是现有成员):</Text>
          <Select
            style={{ width: '100%' }}
            placeholder="选择成员"
            value={transferUser}
            onChange={setTransferUser}
            options={members.map(m => ({ value: m.user_id, label: `${m.username} (${m.role_display})` }))}
          />
        </Space>
      </Modal>
    </div>
  )
}

/**
 * 用户管理 — 用户CRUD + 角色分配 + 权限查看.
 */
import { useEffect, useState } from 'react'
import { Card, Table, Tag, Button, Space, Typography, Modal, Form, Input, Select, message, Popconfirm, Tabs } from 'antd'
import { PlusOutlined, ReloadOutlined, DeleteOutlined, TeamOutlined, SafetyCertificateOutlined } from '@ant-design/icons'
import apiClient from '../utils/api'

const { Title, Text } = Typography

interface UserItem {
  id: number; username: string; email: string; display_name: string | null
  is_active: boolean; is_superuser: boolean
  global_roles: { id: number; name: string; display_name: string }[]
  project_memberships: { project_id: number; role: string }[]
  created_at: string
}

interface RoleItem { id: number; name: string; display_name: string; scope: string }
interface PermItem { id: number; name: string; resource: string; action: string }

export default function UserManagement() {
  const [users, setUsers] = useState<UserItem[]>([])
  const [roles, setRoles] = useState<RoleItem[]>([])
  const [permissions, setPermissions] = useState<PermItem[]>([])
  const [loading, setLoading] = useState(true)
  const [createOpen, setCreateOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [roleOpen, setRoleOpen] = useState(false)
  const [selectedUser, setSelectedUser] = useState<UserItem | null>(null)
  const [form] = Form.useForm()
  const [roleForm] = Form.useForm()

  const fetchAll = async () => {
    setLoading(true)
    try {
      const [u, r, p] = await Promise.all([
        apiClient.get('/users'),
        apiClient.get('/roles'),
        apiClient.get('/permissions'),
      ])
      setUsers(u.data); setRoles(r.data); setPermissions(p.data)
    } catch { message.error('获取数据失败') }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchAll() }, [])

  // ---- 用户 CRUD ----
  const handleCreate = async (values: any) => {
    try {
      await apiClient.post('/users', values)
      message.success('用户创建成功')
      setCreateOpen(false); form.resetFields(); fetchAll()
    } catch (err: any) { message.error(err.response?.data?.detail || '创建失败') }
  }

  const handleUpdate = async (values: any) => {
    if (!selectedUser) return
    try {
      await apiClient.put(`/users/${selectedUser.id}`, values)
      message.success('用户已更新')
      setEditOpen(false); fetchAll()
    } catch (err: any) { message.error(err.response?.data?.detail || '更新失败') }
  }

  const handleDelete = async (id: number) => {
    try {
      await apiClient.delete(`/users/${id}`)
      message.success('用户已停用')
      fetchAll()
    } catch { message.error('操作失败') }
  }

  // ---- 角色分配 ----
  const openRoleAssign = (user: UserItem) => {
    setSelectedUser(user)
    roleForm.setFieldsValue({ role_id: user.global_roles[0]?.id || undefined })
    setRoleOpen(true)
  }

  const handleAssignRole = async () => {
    if (!selectedUser) return
    const values = await roleForm.validateFields()
    try {
      // 先撤销所有全局角色
      for (const r of selectedUser.global_roles) {
        await apiClient.delete(`/users/${selectedUser.id}/roles/${r.id}`).catch(() => {})
      }
      if (values.role_id) {
        await apiClient.post(`/users/${selectedUser.id}/roles`, { role_id: values.role_id })
      }
      message.success('角色已更新')
      setRoleOpen(false); fetchAll()
    } catch (err: any) { message.error(err.response?.data?.detail || '操作失败') }
  }

  const columns = [
    { title: '用户名', dataIndex: 'username', width: 100 },
    { title: '显示名', dataIndex: 'display_name', width: 100 },
    { title: '邮箱', dataIndex: 'email', ellipsis: true },
    { title: '状态', dataIndex: 'is_active', width: 70,
      render: (v: boolean) => <Tag color={v ? 'green' : 'red'}>{v ? '正常' : '停用'}</Tag> },
    { title: '超管', dataIndex: 'is_superuser', width: 60,
      render: (v: boolean) => v ? <Tag color="gold">是</Tag> : null },
    { title: '全局角色', dataIndex: 'global_roles', width: 150,
      render: (v: any[]) => v?.map(r => <Tag key={r.id} color="blue">{r.display_name}</Tag>) || <Text type="secondary">无</Text> },
    { title: '项目成员', dataIndex: 'project_memberships', width: 120,
      render: (v: any[]) => v?.length ? <Text>{v.length} 个项目</Text> : <Text type="secondary">无</Text> },
    { title: '操作', width: 180,
      render: (_: any, record: UserItem) => (
        <Space size="small">
          <Button size="small" icon={<TeamOutlined />} onClick={() => openRoleAssign(record)}>角色</Button>
          <Button size="small" onClick={() => { setSelectedUser(record); form.setFieldsValue(record); setEditOpen(true) }}>编辑</Button>
          {!record.is_superuser && (
            <Popconfirm title="确认停用?" onConfirm={() => handleDelete(record.id)}>
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  const permColumns = [
    { title: '权限', dataIndex: 'name', width: 200, render: (v: string) => <Text code>{v}</Text> },
    { title: '资源', dataIndex: 'resource', width: 120, render: (v: string) => <Tag>{v}</Tag> },
    { title: '操作', dataIndex: 'action', width: 100, render: (v: string) => <Tag color="blue">{v}</Tag> },
  ]

  const roleColumns = [
    { title: '角色', dataIndex: 'display_name', width: 120 },
    { title: '标识', dataIndex: 'name', width: 120, render: (v: string) => <Text code>{v}</Text> },
    { title: '范围', dataIndex: 'scope', width: 80, render: (v: string) => <Tag>{v === 'global' ? '全局' : '项目'}</Tag> },
  ]

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>用户管理</Title>

      <Tabs defaultActiveKey="users" items={[
        {
          key: 'users', label: <span><TeamOutlined /> 用户</span>,
          children: (
            <Card extra={<Space>
              <Button icon={<ReloadOutlined />} onClick={fetchAll}>刷新</Button>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); setCreateOpen(true) }}>新建用户</Button>
            </Space>}>
              <Table columns={columns} dataSource={users} rowKey="id" loading={loading} size="middle"
                pagination={users.length > 15 ? { pageSize: 15 } : false} />
            </Card>
          ),
        },
        {
          key: 'roles', label: <span><SafetyCertificateOutlined /> 角色 ({roles.length})</span>,
          children: (
            <Card><Table columns={roleColumns} dataSource={roles} rowKey="id" size="middle" pagination={false} /></Card>
          ),
        },
        {
          key: 'permissions', label: <span>权限 ({permissions.length})</span>,
          children: (
            <Card><Table columns={permColumns} dataSource={permissions} rowKey="id" size="middle"
              pagination={{ pageSize: 20 }} /></Card>
          ),
        },
      ]} />

      {/* 创建用户 */}
      <Modal title="新建用户" open={createOpen} onOk={() => form.submit()} onCancel={() => setCreateOpen(false)}>
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, min: 6 }]}><Input.Password /></Form.Item>
          <Form.Item name="display_name" label="显示名"><Input /></Form.Item>
          <Form.Item name="email" label="邮箱"><Input /></Form.Item>
        </Form>
      </Modal>

      {/* 编辑用户 */}
      <Modal title="编辑用户" open={editOpen} onOk={() => form.submit()} onCancel={() => setEditOpen(false)}>
        <Form form={form} layout="vertical" onFinish={handleUpdate}>
          <Form.Item name="display_name" label="显示名"><Input /></Form.Item>
          <Form.Item name="email" label="邮箱"><Input /></Form.Item>
          <Form.Item name="is_active" label="状态">
            <Select options={[{ value: true, label: '正常' }, { value: false, label: '停用' }]} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 分配角色 */}
      <Modal title={`分配角色 - ${selectedUser?.username}`} open={roleOpen} onOk={handleAssignRole} onCancel={() => setRoleOpen(false)}>
        <Form form={roleForm} layout="vertical">
          <Form.Item name="role_id" label="全局角色">
            <Select placeholder="选择角色 (留空=移除所有角色)" allowClear
              options={roles.filter(r => r.scope === 'global').map(r => ({ value: r.id, label: `${r.display_name} (${r.name})` }))} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

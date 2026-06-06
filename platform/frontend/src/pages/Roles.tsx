/**
 * 角色权限管理页 — admin only.
 */
import { useEffect, useState } from 'react'
import { Card, Table, Tag, Button, Space, Typography, Modal, Form, Input, Select, message, Spin, Checkbox, Row, Col } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import apiClient from '../utils/api'

const { Title, Text } = Typography

interface Role {
  id: number; name: string; display_name: string; description: string | null
  scope: string; is_system: boolean; created_at: string
}

interface Permission {
  id: number; name: string; resource: string; action: string; description: string | null
}

export default function Roles() {
  const [roles, setRoles] = useState<Role[]>([])
  const [permissions, setPermissions] = useState<Permission[]>([])
  const [rolePerms, setRolePerms] = useState<Record<number, string[]>>({})
  const [loading, setLoading] = useState(true)
  const [createOpen, setCreateOpen] = useState(false)
  const [permOpen, setPermOpen] = useState<{ roleId: number; roleName: string } | null>(null)
  const [createForm] = Form.useForm()
  const [selectedPerms, setSelectedPerms] = useState<string[]>([])

  const fetchAll = async () => {
    setLoading(true)
    try {
      const [rolesResp, permsResp] = await Promise.all([
        apiClient.get('/roles'),
        apiClient.get('/permissions'),
      ])
      setRoles(rolesResp.data)
      setPermissions(permsResp.data)

      // 获取每个角色的权限
      const rpMap: Record<number, string[]> = {}
      for (const r of rolesResp.data) {
        try {
          const rpResp = await apiClient.get(`/roles/${r.id}/permissions`)
          rpMap[r.id] = rpResp.data.permissions.map((p: Permission) => p.name)
        } catch { rpMap[r.id] = [] }
      }
      setRolePerms(rpMap)
    } catch {
      message.error('获取数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchAll() }, [])

  const handleCreate = async (values: any) => {
    try {
      await apiClient.post('/roles', values)
      message.success('角色创建成功')
      setCreateOpen(false)
      createForm.resetFields()
      fetchAll()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '创建失败')
    }
  }

  const handleDelete = async (id: number, name: string) => {
    Modal.confirm({
      title: `确认删除角色 "${name}"?`,
      onOk: async () => {
        await apiClient.delete(`/roles/${id}`)
        message.success('角色已删除')
        fetchAll()
      },
    })
  }

  const openPermEditor = (roleId: number, roleName: string) => {
    setSelectedPerms(rolePerms[roleId] || [])
    setPermOpen({ roleId, roleName })
  }

  // 按 resource 分组权限
  const permGroups: Record<string, Permission[]> = {}
  permissions.forEach(p => {
    if (!permGroups[p.resource]) permGroups[p.resource] = []
    permGroups[p.resource].push(p)
  })

  const columns = [
    { title: '角色名', dataIndex: 'display_name', key: 'display_name', render: (t: string) => <Text strong>{t}</Text> },
    { title: '标识', dataIndex: 'name', key: 'name', render: (t: string) => <Text code>{t}</Text> },
    { title: '作用域', dataIndex: 'scope', key: 'scope', render: (s: string) => <Tag color={s === 'global' ? 'gold' : 'blue'}>{s}</Tag> },
    { title: '系统预置', dataIndex: 'is_system', key: 'is_system', render: (v: boolean) => v ? <Tag color="green">是</Tag> : <Tag>否</Tag> },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '权限数', key: 'perm_count',
      render: (_: any, r: Role) => <Tag>{(rolePerms[r.id] || []).length}</Tag>,
    },
    {
      title: '操作', key: 'action',
      render: (_: any, r: Role) => (
        <Space>
          <a onClick={() => openPermEditor(r.id, r.display_name)}>权限</a>
          {!r.is_system && (
            <a style={{ color: 'red' }} onClick={() => handleDelete(r.id, r.display_name)}>
              <DeleteOutlined />
            </a>
          )}
        </Space>
      ),
    },
  ]

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <Title level={4} style={{ margin: 0 }}>角色权限管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          新建角色
        </Button>
      </div>

      <Card>
        <Table dataSource={roles} columns={columns} rowKey="id" size="middle" pagination={false} />
      </Card>

      {/* 创建角色弹窗 */}
      <Modal title="新建角色" open={createOpen} onCancel={() => setCreateOpen(false)} onOk={() => createForm.submit()}>
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="name" label="角色标识" rules={[{ required: true, pattern: /^[a-z_]+$/ }]}>
            <Input placeholder="custom_role" />
          </Form.Item>
          <Form.Item name="display_name" label="显示名称" rules={[{ required: true }]}>
            <Input placeholder="自定义角色" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input />
          </Form.Item>
          <Form.Item name="scope" label="作用域" initialValue="project">
            <Select options={[{ value: 'project', label: '项目级 (project)' }, { value: 'global', label: '平台级 (global)' }]} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 权限编辑弹窗 */}
      <Modal
        title={`编辑权限 — ${permOpen?.roleName || ''}`}
        open={!!permOpen}
        width={800}
        onCancel={() => setPermOpen(null)}
        footer={null}
      >
        {Object.entries(permGroups).map(([resource, perms]) => (
          <Card key={resource} title={<Tag color="blue">{resource}</Tag>} size="small" style={{ marginBottom: 12 }}>
            <Row gutter={[8, 8]}>
              {perms.map(p => (
                <Col span={12} key={p.id}>
                  <Checkbox
                    checked={selectedPerms.includes(p.name)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedPerms([...selectedPerms, p.name])
                      } else {
                        setSelectedPerms(selectedPerms.filter(x => x !== p.name))
                      }
                    }}
                  >
                    <Text code style={{ fontSize: 12 }}>{p.action}</Text>
                    <Text style={{ fontSize: 12, marginLeft: 4 }}>{p.description || p.name}</Text>
                  </Checkbox>
                </Col>
              ))}
            </Row>
          </Card>
        ))}
      </Modal>
    </div>
  )
}

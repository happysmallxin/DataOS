/**
 * 项目详情页 — 对标 DataWorks 工作空间详情.
 *
 * Tab: 概览 / 数据源 / 成员管理 / 审计日志
 */
import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Tabs, Descriptions, Tag, Button, Table, Space, Typography, Modal, Select,
  Form, Input, message, Spin, Popconfirm, Empty, Row, Col, Statistic, Tooltip,
} from 'antd'
import {
  ArrowLeftOutlined, PlusOutlined, SwapOutlined, DatabaseOutlined,
  SafetyCertificateOutlined, ApiOutlined, BugOutlined, DeleteOutlined,
  LinkOutlined, ReloadOutlined, CopyOutlined,
} from '@ant-design/icons'
import apiClient from '../utils/api'
import { usePermission } from '../hooks/usePermission'

const { Title, Text, Paragraph } = Typography

// ---- types ----

interface ProjectInfo {
  id: number; name: string; display_name: string; description: string | null
  owner_id: number; status: string; member_count: number; datasource_count: number
  created_at: string; updated_at: string
}

interface Member {
  id: number; user_id: number; username: string; email: string
  role_id: number; role_name: string; role_display: string; joined_at: string
}

interface DatasourceItem {
  id: number; project_id: number; name: string; source_type: string
  config: Record<string, unknown>; status: string; last_sync_at: string | null
  created_at: string
}

interface AuditEntry {
  id: number; user_id: number; username: string; resource: string; action: string
  target_name: string | null; detail: any; created_at: string
}

interface RoleOption {
  id: number; name: string; display_name: string
}

interface SourceTypeOption {
  type: string; label: string; category: string
}

const statusColorMap: Record<string, string> = {
  active: 'green', frozen: 'blue', archived: 'default', deleted: 'red',
  error: 'red', inactive: 'orange',
}

const datasourceIconMap: Record<string, React.ReactNode> = {
  mysql: '🐬', postgresql: '🐘', mongodb: '🍃', redis: '🔴',
  kafka: '📨', elasticsearch: '🔍', s3: '🪣', hdfs: '📂',
  hive: '🐝', clickhouse: '🏠', doris: '⭐',
  api: '🔗', crawler: '🕷️', file: '📄',
}

// ---- component ----

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const projectId = parseInt(id!)
  const navigate = useNavigate()
  const { can } = usePermission(projectId)

  // project info
  const [project, setProject] = useState<ProjectInfo | null>(null)
  const [loading, setLoading] = useState(true)

  // members
  const [members, setMembers] = useState<Member[]>([])
  const [roles, setRoles] = useState<RoleOption[]>([])
  const [addMemberOpen, setAddMemberOpen] = useState(false)
  const [addMemberForm] = Form.useForm()
  const [transferOpen, setTransferOpen] = useState(false)
  const [transferUser, setTransferUser] = useState<number | null>(null)

  // datasources
  const [datasources, setDatasources] = useState<DatasourceItem[]>([])
  const [sourceTypes, setSourceTypes] = useState<SourceTypeOption[]>([])
  const [dsCreateOpen, setDsCreateOpen] = useState(false)
  const [dsCreateForm] = Form.useForm()
  const [dsCreating, setDsCreating] = useState(false)

  // resource counts — P2: 从持久化 API 获取真实数据
  const [crawlerCount, setCrawlerCount] = useState(0)
  const [qualityRuleCount, setQualityRuleCount] = useState(0)
  const [pipelineCount, setPipelineCount] = useState(0)

  // audit
  const [auditLogs, setAuditLogs] = useState<AuditEntry[]>([])

  // ---- data fetching ----

  const fetchProject = useCallback(async () => {
    try {
      const resp = await apiClient.get(`/projects/${projectId}`)
      setProject(resp.data)
    } catch {
      message.error('获取项目信息失败')
    }
  }, [projectId])

  const fetchMembers = useCallback(async () => {
    try {
      const [memberResp, rolesResp] = await Promise.all([
        apiClient.get(`/projects/${projectId}/members`),
        apiClient.get('/roles', { params: { scope: 'project' } }),
      ])
      setMembers(memberResp.data)
      setRoles(rolesResp.data)
    } catch { /* ignore */ }
  }, [projectId])

  const fetchDatasources = useCallback(async () => {
    try {
      const resp = await apiClient.get('/datasources', { params: { project_id: projectId } })
      setDatasources(resp.data)
    } catch { /* ignore */ }
  }, [projectId])

  const fetchAuditLogs = useCallback(async () => {
    try {
      const resp = await apiClient.get(`/projects/${projectId}/audit-logs`, { params: { page_size: 30 } })
      setAuditLogs(resp.data.items || [])
    } catch { /* ignore */ }
  }, [projectId])

  const fetchSourceTypes = useCallback(async () => {
    try {
      const resp = await apiClient.get('/datasources/types')
      setSourceTypes(resp.data)
    } catch { /* ignore */ }
  }, [])

  // P2: 从持久化 API 获取项目资源计数
  const fetchCrawlerCount = useCallback(async () => {
    try {
      const resp = await apiClient.get('/crawlers', { params: { project_id: projectId, page_size: 1 } })
      setCrawlerCount(resp.data.total || resp.data.items?.length || 0)
    } catch { /* ignore */ }
  }, [projectId])

  const fetchQualityRuleCount = useCallback(async () => {
    try {
      const resp = await apiClient.get('/quality/rules', { params: { project_id: projectId } })
      setQualityRuleCount(resp.data.length || 0)
    } catch { /* ignore */ }
  }, [projectId])

  const fetchPipelineCount = useCallback(async () => {
    try {
      const resp = await apiClient.get('/cleaning/pipelines', { params: { project_id: projectId } })
      setPipelineCount(resp.data.total || resp.data.items?.length || 0)
    } catch { /* ignore */ }
  }, [projectId])

  const fetchAll = useCallback(async () => {
    setLoading(true)
    await Promise.all([
      fetchProject(), fetchMembers(), fetchDatasources(), fetchAuditLogs(),
      fetchSourceTypes(), fetchCrawlerCount(), fetchQualityRuleCount(), fetchPipelineCount(),
    ])
    setLoading(false)
  }, [fetchProject, fetchMembers, fetchDatasources, fetchAuditLogs, fetchSourceTypes,
      fetchCrawlerCount, fetchQualityRuleCount, fetchPipelineCount])

  useEffect(() => { fetchAll() }, [fetchAll])

  // ---- member actions ----

  const handleAddMember = async (values: { user_id: number; role_id: number }) => {
    try {
      await apiClient.post(`/projects/${projectId}/members`, values)
      message.success('成员添加成功')
      setAddMemberOpen(false)
      addMemberForm.resetFields()
      fetchMembers()
      fetchAuditLogs()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '添加失败')
    }
  }

  const handleUpdateRole = async (userId: number, roleId: number) => {
    try {
      await apiClient.put(`/projects/${projectId}/members/${userId}`, { role_id: roleId })
      message.success('角色已更新')
      fetchMembers()
      fetchAuditLogs()
    } catch { message.error('更新失败') }
  }

  const handleRemoveMember = async (userId: number) => {
    try {
      await apiClient.delete(`/projects/${projectId}/members/${userId}`)
      message.success('成员已移除')
      fetchMembers()
      fetchAuditLogs()
    } catch { message.error('移除失败') }
  }

  const handleTransfer = async () => {
    if (!transferUser) return
    try {
      await apiClient.post(`/projects/${projectId}/transfer`, { new_owner_id: transferUser })
      message.success('项目转让成功')
      setTransferOpen(false)
      setTransferUser(null)
      fetchAll()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '转让失败')
    }
  }

  // ---- datasource actions ----

  const handleCreateDatasource = async (values: any) => {
    setDsCreating(true)
    try {
      await apiClient.post('/datasources', {
        project_id: projectId,
        name: values.name,
        source_type: values.source_type,
        config: values.config ? JSON.parse(values.config) : {},
        description: values.description,
      })
      message.success('数据源创建成功')
      setDsCreateOpen(false)
      dsCreateForm.resetFields()
      fetchDatasources()
      fetchProject()
      fetchAuditLogs()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '创建失败')
    } finally {
      setDsCreating(false)
    }
  }

  const handleDeleteDatasource = async (dsId: number) => {
    try {
      await apiClient.delete(`/datasources/${dsId}`)
      message.success('数据源已删除')
      fetchDatasources()
      fetchProject()
      fetchAuditLogs()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '删除失败')
    }
  }

  const handleCopyDSName = (name: string) => {
    navigator.clipboard.writeText(name).then(() => message.success('已复制'))
  }

  // ---- loading / empty ----

  if (loading) {
    return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" tip="加载项目信息..." /></div>
  }
  if (!project) return <Empty description="项目不存在" />

  // ---- table columns ----

  const memberColumns = [
    { title: '用户名', dataIndex: 'username', key: 'username', width: 120 },
    { title: '邮箱', dataIndex: 'email', key: 'email', ellipsis: true },
    {
      title: '角色', dataIndex: 'role_display', key: 'role', width: 180,
      render: (text: string, record: Member) => (
        can('project:manage_members') && record.role_name !== 'project_owner' ? (
          <Select
            size="small"
            value={record.role_id}
            style={{ width: 140 }}
            onChange={(roleId) => handleUpdateRole(record.user_id, roleId)}
            options={roles.map(r => ({ value: r.id, label: r.display_name }))}
          />
        ) : (
          <Tag color={record.role_name === 'project_owner' ? 'gold' : 'blue'}>{text}</Tag>
        )
      ),
    },
    {
      title: '加入时间', dataIndex: 'joined_at', key: 'joined_at', width: 130,
      render: (d: string) => new Date(d).toLocaleDateString(),
    },
    {
      title: '操作', key: 'action', width: 80,
      render: (_: any, record: Member) => (
        can('project:manage_members') && record.role_name !== 'project_owner' ? (
          <Popconfirm title="确认移除该成员?" onConfirm={() => handleRemoveMember(record.user_id)}>
            <Button type="link" danger size="small">移除</Button>
          </Popconfirm>
        ) : null
      ),
    },
  ]

  const datasourceColumns = [
    {
      title: '名称', dataIndex: 'name', key: 'name', width: 180,
      render: (name: string, record: DatasourceItem) => (
        <Space>
          <span>{datasourceIconMap[record.source_type] || '📦'}</span>
          <a onClick={() => navigate(`/datasources`)}>{name}</a>
          <Tooltip title="复制名称"><CopyOutlined style={{ cursor: 'pointer', fontSize: 12, color: '#999' }} onClick={() => handleCopyDSName(name)} /></Tooltip>
        </Space>
      ),
    },
    {
      title: '类型', dataIndex: 'source_type', key: 'type', width: 120,
      render: (t: string) => {
        const info = sourceTypes.find(s => s.type === t)
        return <Tag>{info?.label || t}</Tag>
      },
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 90,
      render: (s: string) => <Tag color={statusColorMap[s] || 'default'}>{s}</Tag>,
    },
    {
      title: '最后同步', dataIndex: 'last_sync_at', key: 'sync', width: 150,
      render: (d: string | null) => d ? new Date(d).toLocaleString() : <Text type="secondary">从未</Text>,
    },
    {
      title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 150,
      render: (d: string) => new Date(d).toLocaleDateString(),
    },
    {
      title: '操作', key: 'action', width: 80,
      render: (_: any, record: DatasourceItem) => (
        can('datasource:delete') ? (
          <Popconfirm
            title="确认删除该数据源?"
            description="删除后关联的 Pipeline 和 API 将失效"
            onConfirm={() => handleDeleteDatasource(record.id)}
          >
            <Button type="link" danger size="small" icon={<DeleteOutlined />} />
          </Popconfirm>
        ) : null
      ),
    },
  ]

  const auditColumns = [
    { title: '操作人', dataIndex: 'username', width: 100 },
    { title: '资源', dataIndex: 'resource', width: 80, render: (r: string) => <Tag>{r}</Tag> },
    { title: '操作', dataIndex: 'action', width: 80, render: (a: string) => <Tag color={a === 'delete' || a === 'revoke' ? 'red' : a === 'create' || a === 'grant' ? 'green' : 'blue'}>{a}</Tag> },
    { title: '目标', dataIndex: 'target_name', ellipsis: true },
    { title: '时间', dataIndex: 'created_at', width: 160, render: (d: string) => new Date(d).toLocaleString() },
  ]

  // ---- render ----

  const resourceStats = [
    { title: '数据源', count: datasources.length, icon: <DatabaseOutlined />, color: '#1677ff', permission: 'datasource:read', path: '/datasources' },
    { title: '爬虫任务', count: crawlerCount, icon: <BugOutlined />, color: '#52c41a', permission: 'crawler:read', path: '/crawlers' },
    { title: '质量规则', count: qualityRuleCount, icon: <SafetyCertificateOutlined />, color: '#faad14', permission: 'quality:read', path: '/quality' },
    { title: 'Pipeline', count: pipelineCount, icon: <ApiOutlined />, color: '#eb2f96', permission: 'api:read', path: '/data-service' },
  ]

  const tabs = [
    // ---- Tab 1: 概览 ----
    {
      key: 'overview',
      label: '概览',
      children: (
        <div>
          {/* 项目基本信息 */}
          <Card title="基本信息" style={{ marginBottom: 16 }}>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="项目标识">
                <Space>
                  <code>{project.name}</code>
                  <Tooltip title="复制"><CopyOutlined style={{ cursor: 'pointer' }} onClick={() => handleCopyDSName(project.name)} /></Tooltip>
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="显示名称">{project.display_name}</Descriptions.Item>
              <Descriptions.Item label="描述" span={2}>{project.description || <Text type="secondary">未设置描述</Text>}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={statusColorMap[project.status]}>{project.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="成员数">{project.member_count}</Descriptions.Item>
              <Descriptions.Item label="创建时间">{new Date(project.created_at).toLocaleString()}</Descriptions.Item>
              <Descriptions.Item label="更新时间">{new Date(project.updated_at).toLocaleString()}</Descriptions.Item>
            </Descriptions>
            {can('project:manage_members') && (
              <div style={{ marginTop: 16 }}>
                <Space>
                  <Button icon={<SwapOutlined />} onClick={() => setTransferOpen(true)}>转让项目</Button>
                </Space>
              </div>
            )}
          </Card>

          {/* 资源概览卡片 */}
          <Card title="资源概览" style={{ marginBottom: 16 }}>
            <Row gutter={16}>
              {resourceStats.map((stat) => (
                <Col xs={12} sm={6} key={stat.title}>
                  <Card
                    size="small"
                    hoverable={can(stat.permission)}
                    onClick={() => can(stat.permission) && navigate(stat.path)}
                    style={{ textAlign: 'center', cursor: can(stat.permission) ? 'pointer' : 'default' }}
                  >
                    <Statistic
                      title={stat.title}
                      value={stat.count}
                      prefix={<span style={{ color: stat.color, fontSize: 24 }}>{stat.icon}</span>}
                    />
                  </Card>
                </Col>
              ))}
            </Row>
          </Card>

          {/* 快捷操作 */}
          <Card title="快捷操作">
            <Space wrap>
              {can('datasource:create') && (
                <Button type="primary" icon={<PlusOutlined />} onClick={() => setDsCreateOpen(true)}>注册数据源</Button>
              )}
              {can('project:manage_members') && (
                <Button icon={<PlusOutlined />} onClick={() => setAddMemberOpen(true)}>添加成员</Button>
              )}
              <Button icon={<LinkOutlined />} onClick={() => navigate('/datasources')}>数据源管理</Button>
              {can('project:read') && (
                <Button icon={<ReloadOutlined />} onClick={fetchAll}>刷新</Button>
              )}
            </Space>
          </Card>
        </div>
      ),
    },

    // ---- Tab 2: 数据源 ----
    {
      key: 'datasources',
      label: `数据源 (${datasources.length})`,
      children: (
        <Card
          title="项目数据源"
          extra={
            <Space>
              <Button icon={<ReloadOutlined />} onClick={fetchDatasources} size="small">刷新</Button>
              {can('datasource:create') && (
                <Button type="primary" icon={<PlusOutlined />} size="small" onClick={() => {
                  dsCreateForm.setFieldValue('source_type', 'mysql')
                  setDsCreateOpen(true)
                }}>
                  注册数据源
                </Button>
              )}
            </Space>
          }
        >
          {datasources.length === 0 ? (
            <Empty
              description="暂无数据源"
              children={
                can('datasource:create') ? (
                  <Button type="primary" icon={<PlusOutlined />} onClick={() => setDsCreateOpen(true)}>
                    注册第一个数据源
                  </Button>
                ) : null
              }
            />
          ) : (
            <Table
              dataSource={datasources}
              columns={datasourceColumns}
              rowKey="id"
              size="middle"
              pagination={datasources.length > 15 ? { pageSize: 15 } : false}
            />
          )}
        </Card>
      ),
    },

    // ---- Tab 3: 成员管理 ----
    {
      key: 'members',
      label: `成员 (${members.length})`,
      children: (
        <Card
          title="项目成员"
          extra={
            can('project:manage_members') && (
              <Button type="primary" icon={<PlusOutlined />} size="small" onClick={() => setAddMemberOpen(true)}>
                添加成员
              </Button>
            )
          }
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

    // ---- Tab 4: 审计日志 ----
    {
      key: 'audit',
      label: '审计日志',
      children: (
        <Card
          title="操作记录"
          extra={<Button icon={<ReloadOutlined />} size="small" onClick={fetchAuditLogs}>刷新</Button>}
        >
          {auditLogs.length === 0 ? (
            <Empty description="暂无审计日志" />
          ) : (
            <Table
              dataSource={auditLogs}
              columns={auditColumns}
              rowKey="id"
              size="middle"
              pagination={{ pageSize: 15, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
            />
          )}
        </Card>
      ),
    },
  ]

  return (
    <div>
      {/* header */}
      <div className="flex items-center gap-4 mb-4">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/projects')}>返回</Button>
        <Title level={4} style={{ margin: 0 }}>
          <span style={{ marginRight: 8 }}>{datasourceIconMap[project.name.charAt(0)] || '📁'}</span>
          {project.display_name}
        </Title>
        <Tag color={statusColorMap[project.status]}>{project.status}</Tag>
        <Text type="secondary" style={{ fontSize: 13 }}>{project.name}</Text>
      </div>

      <Tabs defaultActiveKey="overview" items={tabs} />

      {/* ======== 添加成员弹窗 ======== */}
      <Modal title="添加成员" open={addMemberOpen} onCancel={() => setAddMemberOpen(false)} onOk={() => addMemberForm.submit()}>
        <Form form={addMemberForm} layout="vertical" onFinish={handleAddMember}>
          <Form.Item name="user_id" label="用户 ID" rules={[{ required: true, message: '请输入用户 ID' }]}>
            <Input type="number" placeholder="输入用户 ID" />
          </Form.Item>
          <Form.Item name="role_id" label="角色" rules={[{ required: true, message: '请选择角色' }]}>
            <Select
              placeholder="选择角色"
              options={roles.map(r => ({ value: r.id, label: `${r.display_name} (${r.name})` }))}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* ======== 转让弹窗 ======== */}
      <Modal title="转让项目所有权" open={transferOpen} onCancel={() => { setTransferOpen(false); setTransferUser(null) }} onOk={handleTransfer} okText="确认转让">
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text>选择新项目负责人 (必须是现有成员):</Text>
          <Select
            style={{ width: '100%' }}
            placeholder="选择成员"
            value={transferUser}
            onChange={setTransferUser}
            options={members
              .filter(m => m.role_name !== 'project_owner')
              .map(m => ({ value: m.user_id, label: `${m.username} (${m.role_display})` }))}
          />
          {transferUser && (
            <Text type="secondary">转让后原负责人将降级为 editor，此操作不可撤销。</Text>
          )}
        </Space>
      </Modal>

      {/* ======== 创建数据源弹窗 ======== */}
      <Modal
        title="注册数据源"
        open={dsCreateOpen}
        onCancel={() => { setDsCreateOpen(false); dsCreateForm.resetFields() }}
        onOk={() => dsCreateForm.submit()}
        confirmLoading={dsCreating}
        width={560}
      >
        <Form form={dsCreateForm} layout="vertical" onFinish={handleCreateDatasource}>
          <Form.Item name="name" label="数据源名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如: mysql_prod" />
          </Form.Item>
          <Form.Item name="source_type" label="类型" rules={[{ required: true }]}>
            <Select
              showSearch
              placeholder="选择数据源类型"
              options={sourceTypes.map(s => ({
                value: s.type,
                label: `${datasourceIconMap[s.type] || '📦'} ${s.label}  — ${s.category}`,
              }))}
            />
          </Form.Item>
          <Form.Item name="config" label="连接配置 (JSON)"
            rules={[{ required: true, message: '请输入连接配置' }]}
            extra='JSON 格式，例如: {"host":"localhost","port":3306,"database":"mydb","username":"root","password":"xxx"}'
          >
            <Input.TextArea rows={5} placeholder='{"host":"...","port":3306,"database":"...","username":"...","password":"..."}' />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input placeholder="可选: 数据源用途说明" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

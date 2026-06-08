/**
 * 项目详情页 — 对标 DataWorks 工作空间详情.
 *
 * Tab: 概览 / 数据源 / 清洗Pipeline / 成员管理 / 审计日志
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
  LinkOutlined, ReloadOutlined, CopyOutlined, PlayCircleOutlined,
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
  const [pipelines, setPipelines] = useState<any[]>([])
  const [plCreateOpen, setPlCreateOpen] = useState(false)
  const [plCreateForm] = Form.useForm()
  const [plRunning, setPlRunning] = useState<number | null>(null)
  const [plResult, setPlResult] = useState<any>(null)

  // 数据建模
  const [domains, setDomains] = useState<any[]>([])
  const [processes, setProcesses] = useState<any[]>([])
  const [domainFormOpen, setDomainFormOpen] = useState(false)
  const [processFormOpen, setProcessFormOpen] = useState(false)
  const [domainForm] = Form.useForm()
  const [processForm] = Form.useForm()
  const [selectedDomain, setSelectedDomain] = useState<any>(null)

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

  const fetchPipelines = useCallback(async () => {
    try {
      const resp = await apiClient.get('/cleaning/pipelines', { params: { project_id: projectId } })
      const items = resp.data.items || resp.data || []
      setPipelines(items)
      setPipelineCount(resp.data.total || items.length || 0)
    } catch { /* ignore */ }
  }, [projectId])

  const fetchDomains = useCallback(async () => {
    try {
      const resp = await apiClient.get(`/projects/${projectId}/domains`)
      setDomains(resp.data || [])
    } catch { /* ignore */ }
  }, [projectId])

  const fetchProcesses = useCallback(async () => {
    try {
      const resp = await apiClient.get(`/projects/${projectId}/processes`)
      setProcesses(resp.data || [])
    } catch { /* ignore */ }
  }, [projectId])

  const fetchAll = useCallback(async () => {
    setLoading(true)
    await Promise.all([
      fetchProject(), fetchMembers(), fetchDatasources(), fetchAuditLogs(),
      fetchSourceTypes(), fetchCrawlerCount(), fetchQualityRuleCount(), fetchPipelines(),
      fetchDomains(), fetchProcesses(),
    ])
    setLoading(false)
  }, [fetchProject, fetchMembers, fetchDatasources, fetchAuditLogs, fetchSourceTypes,
      fetchCrawlerCount, fetchQualityRuleCount, fetchPipelines, fetchDomains, fetchProcesses])

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

  // ---- Pipeline handlers ----

  const handleCreatePipeline = async (values: any) => {
    try {
      await apiClient.post('/cleaning/pipelines', {
        project_id: projectId,
        datasource_id: values.datasource_id || null,
        source_table: values.source_table || null,
        name: values.name,
        target_table: values.target_table || null,
        stages: [
          { type: 'standardize', config: { column: values.column || 'id', operation: values.operation || 'trim' } },
        ],
        description: values.description,
      })
      message.success('Pipeline 创建成功')
      setPlCreateOpen(false)
      plCreateForm.resetFields()
      fetchPipelines()
      fetchAuditLogs()
    } catch (err: any) { message.error(err.response?.data?.detail || '创建失败') }
  }

  const handleRunPipeline = async (plId: number) => {
    setPlRunning(plId)
    setPlResult(null)
    try {
      const resp = await apiClient.post('/cleaning/pipelines/run', { pipeline_id: plId })
      const d = resp.data
      const s = d.output_storage || {}
      setPlResult({ ...d, id: plId })
      if (s.rows) message.success(`清洗完成: ${s.rows} 行 → MinIO Silver + PG Gold`)
      else message.info('清洗完成')
      fetchPipelines()
      fetchAuditLogs()
    } catch (err: any) { message.error(err.response?.data?.detail || '执行失败') }
    finally { setPlRunning(null) }
  }

  const handleDeletePipeline = async (plId: number) => {
    try {
      await apiClient.delete(`/cleaning/pipelines/${plId}`)
      message.success('Pipeline 已删除')
      fetchPipelines()
    } catch { message.error('删除失败') }
  }

  // ---- 数据建模 handlers ----
  const handleCreateDomain = async (values: any) => {
    try {
      await apiClient.post(`/projects/${projectId}/domains`, values)
      message.success('数据域已创建')
      setDomainFormOpen(false); domainForm.resetFields()
      fetchDomains()
    } catch (err: any) { message.error(err.response?.data?.detail || '创建失败') }
  }

  const handleDeleteDomain = async (id: number) => {
    try {
      await apiClient.delete(`/projects/${projectId}/domains/${id}`)
      message.success('数据域已删除')
      fetchDomains()
    } catch (err: any) { message.error(err.response?.data?.detail || '删除失败') }
  }

  const handleCreateProcess = async (values: any) => {
    try {
      await apiClient.post(`/projects/${projectId}/domains/${values.domain_id}/processes`, values)
      message.success('业务过程已创建')
      setProcessFormOpen(false); processForm.resetFields()
      fetchProcesses()
    } catch (err: any) { message.error(err.response?.data?.detail || '创建失败') }
  }

  const handleDeleteProcess = async (id: number) => {
    try {
      await apiClient.delete(`/projects/${projectId}/processes/${id}`)
      message.success('业务过程已删除')
      fetchProcesses()
    } catch { message.error('删除失败') }
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

          {/* 数据服务 — Directus API */}
          <Card title="数据服务 (Directus API)" size="small" style={{ marginTop: 16 }}>
            {pipelineCount > 0 ? (
              <div>
                <Text type="secondary" style={{ fontSize: 13 }}>
                  清洗后的数据已发布到 Directus，可通过 REST API 访问：
                </Text>
                <div style={{ marginTop: 8, padding: 12, background: '#f6f8fa', borderRadius: 6 }}>
                  <Text copyable code style={{ fontSize: 13 }}>
                    GET http://localhost:8055/items/clean_users
                  </Text>
                </div>
                <div style={{ marginTop: 6 }}>
                  <Button size="small" icon={<LinkOutlined />}
                    onClick={() => window.open('http://localhost:8055/admin', '_blank')}>
                    打开 Directus 管理后台
                  </Button>
                </div>
              </div>
            ) : (
              <Text type="secondary" style={{ fontSize: 13 }}>
                暂无清洗数据。创建并执行 Pipeline 后，清洗结果会自动发布到 Directus。
              </Text>
            )}
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

    // ---- Tab 3: 清洗 Pipeline ----
    {
      key: 'pipelines',
      label: `Pipeline (${pipelineCount})`,
      children: (
        <Card
          title="清洗 Pipeline"
          extra={
            <Space>
              <Button icon={<ReloadOutlined />} size="small" onClick={fetchPipelines}>刷新</Button>
              {can('project:read') && (
                <Button type="primary" icon={<PlusOutlined />} size="small" onClick={() => { plCreateForm.resetFields(); setPlCreateOpen(true) }}>
                  新建 Pipeline
                </Button>
              )}
            </Space>
          }
        >
          {pipelines.length === 0 ? (
            <Empty description="暂无 Pipeline" children={
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setPlCreateOpen(true)}>创建第一个 Pipeline</Button>
            } />
          ) : (
            <div>
              {pipelines.map((pl: any) => (
                <Card key={pl.id} size="small" style={{ marginBottom: 12 }}
                  title={<Space><Text strong>{pl.name}</Text><Tag color={pl.status === 'active' ? 'green' : 'default'}>{pl.status}</Tag></Space>}
                  extra={
                    <Space>
                      <Button size="small" type="primary" icon={<PlayCircleOutlined />}
                        loading={plRunning === pl.id} onClick={() => handleRunPipeline(pl.id)}>
                        执行
                      </Button>
                      <Popconfirm title="确认删除?" onConfirm={() => handleDeletePipeline(pl.id)}>
                        <Button size="small" danger icon={<DeleteOutlined />} />
                      </Popconfirm>
                    </Space>
                  }>
                  <Row gutter={16}>
                    <Col span={6}><Text type="secondary">数据源</Text><br /><Text>{pl.datasource_id ? (datasources.find(d => d.id === pl.datasource_id)?.name || `#${pl.datasource_id}`) : '未关联'}</Text></Col>
                    <Col span={6}><Text type="secondary">源表</Text><br /><Text>{pl.source_table || '—'}</Text></Col>
                    <Col span={6}><Text type="secondary">目标表</Text><br /><Text code>{pl.target_table || '—'}</Text></Col>
                    <Col span={6}><Text type="secondary">版本</Text><br /><Text>v{pl.version}</Text></Col>
                  </Row>
                  <Row gutter={16} style={{ marginTop: 8 }}>
                    <Col span={6}><Text type="secondary">上次执行</Text><br /><Text>{pl.last_run_at ? new Date(pl.last_run_at).toLocaleString() : '从未'}</Text></Col>
                    <Col span={6}><Text type="secondary">输出行数</Text><br /><Text>{pl.last_output_rows?.toLocaleString() || '—'}</Text></Col>
                    <Col span={12}><Text type="secondary">Stages</Text><br /><Text style={{ fontSize: 12 }}>{(pl.stages || []).map((s: any) => s.type).join(' → ') || '—'}</Text></Col>
                  </Row>
                  {/* 执行结果 */}
                  {plResult && plResult.id === pl.id && (
                    <div style={{ marginTop: 8, padding: 8, background: '#f6ffed', borderRadius: 6 }}>
                      <Text type="success" style={{ fontSize: 12 }}>
                        执行完成: {plResult.output_rows} 行 |
                        Silver: {plResult.output_storage?.minio_silver?.split('/').pop() || '—'} |
                        PG: {plResult.output_storage?.postgresql?.table || '—'}
                      </Text>
                    </div>
                  )}
                </Card>
              ))}
            </div>
          )}
        </Card>
      ),
    },

    // ---- Tab 4: 数据建模 ----
    {
      key: 'modeling',
      label: '数据建模',
      children: (
        <div>
          <Card title="数据域" size="small" style={{ marginBottom: 16 }}
            extra={<Button size="small" icon={<PlusOutlined />} onClick={() => { domainForm.resetFields(); setDomainFormOpen(true) }}>新增数据域</Button>}>
            {domains.length === 0 ? <Text type="secondary">暂无数据域，点击新增</Text> : (
              domains.map((d: any) => (
                <div key={d.id} style={{ padding: '8px 12px', margin: '4px 0', background: '#fafafa', borderRadius: 6,
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Space>
                    <Text strong>📁 {d.display_name}</Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>{d.name}</Text>
                    {d.description && <Text type="secondary" style={{ fontSize: 12 }}>— {d.description}</Text>}
                  </Space>
                  <Popconfirm title="确认删除?" onConfirm={() => handleDeleteDomain(d.id)}>
                    <Button size="small" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                </div>
              ))
            )}
          </Card>

          <Card title="业务过程" size="small"
            extra={<Button size="small" icon={<PlusOutlined />} onClick={() => { processForm.resetFields(); setProcessFormOpen(true) }}>新增业务过程</Button>}>
            {processes.length === 0 ? <Text type="secondary">暂无业务过程，点击新增</Text> : (
              <Table dataSource={processes} rowKey="id" size="small" pagination={false}
                columns={[
                  { title: '名称', dataIndex: 'display_name', width: 120, render: (v: string, r: any) => <Text strong>{v}</Text> },
                  { title: '标识', dataIndex: 'name', width: 100, render: (v: string) => <Text code>{v}</Text> },
                  { title: '数据域', dataIndex: 'domain_id', width: 80,
                    render: (v: number) => domains.find(d => d.id === v)?.display_name || `#${v}` },
                  { title: '类型', dataIndex: 'table_type', width: 70, render: (v: string) => {
                    const colors: Record<string, string> = { DIM: 'blue', FACT: 'orange', DWD: 'green', DWS: 'purple', ADS: 'red' }
                    return <Tag color={colors[v] || 'default'}>{v}</Tag>
                  }},
                  { title: '源表', dataIndex: 'source_tables', ellipsis: true, render: (v: any) => v ? (v as string[]).join(', ') : '—' },
                  { title: '目标表', dataIndex: 'target_tables', ellipsis: true, render: (v: any) => v ? (v as string[]).join(', ') : '—' },
                  { title: '操作', width: 60, render: (_: any, r: any) => (
                    <Popconfirm title="确认删除?" onConfirm={() => handleDeleteProcess(r.id)}>
                      <Button size="small" danger icon={<DeleteOutlined />} />
                    </Popconfirm>
                  )},
                ]} />
            )}
          </Card>
        </div>
      ),
    },

    // ---- Tab 5: 成员管理 ----
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

    // ---- Tab 6: 审计日志 ----
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

      {/* ======== 创建 Pipeline 弹窗 ======== */}
      <Modal title="新建 Pipeline" open={plCreateOpen}
        onCancel={() => { setPlCreateOpen(false); plCreateForm.resetFields() }}
        onOk={() => plCreateForm.submit()} width={520}>
        <Form form={plCreateForm} layout="vertical" onFinish={handleCreatePipeline}>
          <Form.Item name="name" label="Pipeline 名称" rules={[{ required: true }]}>
            <Input placeholder="如: 用户数据清洗" />
          </Form.Item>
          <Form.Item name="datasource_id" label="关联数据源 ID">
            <Input type="number" placeholder="如: 3" />
          </Form.Item>
          <Form.Item name="source_table" label="源表名">
            <Input placeholder="如: users (数据源中要清洗的表)" />
          </Form.Item>
          <Form.Item name="column" label="清洗列" initialValue="username">
            <Input placeholder="要标准化的列名" />
          </Form.Item>
          <Form.Item name="operation" label="操作" initialValue="trim">
            <Select options={[
              { value: 'trim', label: '去空格 (trim)' },
              { value: 'lowercase', label: '转小写 (lowercase)' },
              { value: 'uppercase', label: '转大写 (uppercase)' },
              { value: 'parse_date', label: '日期解析 (parse_date)' },
            ]} />
          </Form.Item>
          <Form.Item name="target_table" label="输出表名 (PG Gold)">
            <Input placeholder="如: clean_users" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* ======== 数据域弹窗 ======== */}
      <Modal title="新增数据域" open={domainFormOpen}
        onCancel={() => { setDomainFormOpen(false); domainForm.resetFields() }}
        onOk={() => domainForm.submit()}>
        <Form form={domainForm} layout="vertical" onFinish={handleCreateDomain}>
          <Form.Item name="name" label="标识" rules={[{ required: true }]}>
            <Input placeholder="trade_domain" />
          </Form.Item>
          <Form.Item name="display_name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="交易域" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* ======== 业务过程弹窗 ======== */}
      <Modal title="新增业务过程" open={processFormOpen}
        onCancel={() => { setProcessFormOpen(false); processForm.resetFields() }}
        onOk={() => processForm.submit()}>
        <Form form={processForm} layout="vertical" onFinish={handleCreateProcess}>
          <Form.Item name="domain_id" label="数据域" rules={[{ required: true }]}>
            <Select placeholder="选择数据域" options={domains.filter((d: any) => !d.children || d.children.length === 0).map((d: any) => ({ value: d.id, label: `${d.display_name} (${d.name})` }))} />
          </Form.Item>
          <Form.Item name="name" label="标识" rules={[{ required: true }]}>
            <Input placeholder="order_create" />
          </Form.Item>
          <Form.Item name="display_name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="订单创建" />
          </Form.Item>
          <Form.Item name="table_type" label="表类型" initialValue="DWD">
            <Select options={[
              { value: 'DIM', label: 'DIM 维度表' }, { value: 'FACT', label: 'FACT 事实表' },
              { value: 'DWD', label: 'DWD 明细表' }, { value: 'DWS', label: 'DWS 汇总表' },
              { value: 'ADS', label: 'ADS 应用表' },
            ]} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

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

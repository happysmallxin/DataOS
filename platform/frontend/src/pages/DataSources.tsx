import { useEffect, useState } from 'react'
import { Card, Table, Tag, Button, Space, Typography, Modal, Form, Input, Select, message, Popconfirm, Drawer, Checkbox } from 'antd'
import {
  PlusOutlined, ReloadOutlined, DatabaseOutlined, ApiOutlined,
  SyncOutlined, DeleteOutlined, EyeOutlined, TableOutlined, HistoryOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import apiClient from '../utils/api'
import { usePermission } from '../hooks/usePermission'

const { Title, Text } = Typography

interface DataSourceRecord {
  id: number; project_id: number; name: string; source_type: string
  config: Record<string, unknown>; status: string
  last_sync_at: string | null; created_at: string
}

interface TableInfo { name: string; columns: { name: string; type: string }[] }

const sourceTypeOptions = [
  { value: 'mysql', label: 'MySQL' }, { value: 'postgresql', label: 'PostgreSQL' },
  { value: 'mongodb', label: 'MongoDB' }, { value: 'redis', label: 'Redis' },
  { value: 'kafka', label: 'Kafka' }, { value: 'elasticsearch', label: 'Elasticsearch' },
  { value: 'api', label: 'REST API' }, { value: 's3', label: 'S3/MinIO' },
  { value: 'crawler', label: '网页爬虫' }, { value: 'file', label: '文件上传' },
  { value: 'clickhouse', label: 'ClickHouse' },
]

export default function DataSources() {
  const { can } = usePermission()
  const [data, setData] = useState<DataSourceRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [form] = Form.useForm()

  // 测试连接
  const [testing, setTesting] = useState<number | null>(null)

  // 同步
  const [syncing, setSyncing] = useState<number | null>(null)
  const [syncModalOpen, setSyncModalOpen] = useState(false)
  const [syncDsId, setSyncDsId] = useState<number | null>(null)
  const [tables, setTables] = useState<TableInfo[]>([])
  const [tablesLoading, setTablesLoading] = useState(false)
  const [syncTables, setSyncTables] = useState<Set<string>>(new Set())
  const [syncResults, setSyncResults] = useState<any>(null)

  // 预览
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewData, setPreviewData] = useState<Record<string, unknown>[]>([])
  const [previewCols, setPreviewCols] = useState<string[]>([])
  const [previewLoading, setPreviewLoading] = useState(false)

  // 同步历史
  const [historyOpen, setHistoryOpen] = useState(false)
  const [historyDsId, setHistoryDsId] = useState<number | null>(null)
  const [syncHistory, setSyncHistory] = useState<Record<string, unknown>[]>([])

  const fetchData = async () => {
    setLoading(true)
    try {
      const res = await apiClient.get('/datasources')
      setData(res.data)
    } catch { message.error('获取数据源列表失败') }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchData() }, [])

  // ---- 创建 ----
  const handleCreate = async () => {
    try {
      const values = await form.validateFields()
      await apiClient.post('/datasources', {
        project_id: values.project_id || 1,
        name: values.name,
        source_type: values.source_type,
        config: {
          host: values.host || 'localhost',
          port: values.port || 3306,
          database: values.database || '',
          username: values.username || '',
          password: values.password || '',
        },
        description: values.description,
      })
      message.success('数据源创建成功')
      setCreateOpen(false)
      form.resetFields()
      fetchData()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '创建失败')
    }
  }

  // ---- 测试连接 ----
  const handleTestConnection = async (id: number) => {
    setTesting(id)
    try {
      const res = await apiClient.post(`/datasources/${id}/test-connection`)
      if (res.data.status === 'ok') {
        message.success(`连接成功 ✓`)
      } else {
        message.error(`连接失败: ${res.data.message}`)
      }
    } catch (err: any) {
      message.error(err.response?.data?.detail || '测试失败')
    } finally { setTesting(null) }
  }

  // ---- 同步 ----
  const handleOpenSync = async (dsId: number) => {
    setSyncDsId(dsId)
    setSyncModalOpen(true)
    setTablesLoading(true)
    try {
      const res = await apiClient.post(`/datasources/${dsId}/tables`)
      setTables(res.data)
    } catch { message.error('获取表列表失败') }
    finally { setTablesLoading(false) }
  }

  const handleSync = async () => {
    if (!syncDsId || syncTables.size === 0) return
    setSyncing(syncDsId)
    setSyncResults(null)
    try {
      const res = await apiClient.post(`/datasources/${syncDsId}/sync-all`, {
        table_names: Array.from(syncTables),
      })
      const ok = res.data.tables.filter((t: any) => t.status === 'success').length
      const fail = res.data.tables.filter((t: any) => t.status === 'failed').length
      message.success(`同步完成: ${ok} 成功${fail > 0 ? `, ${fail} 失败` : ''}`)
      setSyncResults(res.data.tables)
      setSyncTables(new Set())
      fetchData()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '同步失败')
    } finally { setSyncing(null) }
  }

  // ---- 预览 ----
  const handlePreview = async (dsId: number, tableName: string) => {
    setPreviewOpen(true)
    setPreviewLoading(true)
    try {
      const res = await apiClient.post(`/datasources/${dsId}/tables/${tableName}/preview`)
      setPreviewCols(res.data.columns)
      setPreviewData(res.data.data)
    } catch { message.error('预览失败') }
    finally { setPreviewLoading(false) }
  }

  // ---- 同步历史 ----
  const handleOpenHistory = async (dsId: number) => {
    setHistoryDsId(dsId)
    setHistoryOpen(true)
    try {
      const res = await apiClient.get(`/datasources/${dsId}/sync-history`)
      setSyncHistory(res.data)
    } catch { message.error('获取同步历史失败') }
  }

  // ---- 删除 ----
  const handleDelete = async (id: number) => {
    try {
      await apiClient.delete(`/datasources/${id}`)
      message.success('数据源已删除')
      fetchData()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '删除失败')
    }
  }

  const statusMap: Record<string, { color: string; text: string }> = {
    active: { color: 'green', text: '已连接' },
    error: { color: 'red', text: '异常' },
    disabled: { color: 'default', text: '已禁用' },
  }

  const columns: ColumnsType<DataSourceRecord> = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 140 },
    { title: '类型', dataIndex: 'source_type', key: 'type', width: 100,
      render: (t: string) => <Tag icon={<DatabaseOutlined />}>{t}</Tag> },
    { title: '地址', key: 'host', width: 160,
      render: (_, r) => <Text code>{`${r.config?.host || '-'}:${r.config?.port || '-'}`}</Text> },
    { title: '状态', dataIndex: 'status', key: 'status', width: 80,
      render: (s: string) => <Tag color={statusMap[s]?.color}>{statusMap[s]?.text || s}</Tag> },
    { title: '最后同步', dataIndex: 'last_sync_at', key: 'sync', width: 100,
      render: (v: string | null) => v ? new Date(v).toLocaleDateString() : <Text type="secondary">从未</Text> },
    { title: '操作', key: 'action', width: 260,
      render: (_: unknown, record: DataSourceRecord) => (
        <Space size="small">
          <Button size="small" icon={<ApiOutlined />}
            loading={testing === record.id}
            onClick={() => handleTestConnection(record.id)}>
            测试
          </Button>
          <Button size="small" icon={<SyncOutlined />}
            onClick={() => handleOpenSync(record.id)}>
            同步
          </Button>
          <Button size="small" icon={<HistoryOutlined />}
            onClick={() => handleOpenHistory(record.id)}>
            历史
          </Button>
          {can('datasource:delete') && (
            <Popconfirm title="确认删除该数据源?" onConfirm={() => handleDelete(record.id)}>
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <Title level={4} style={{ margin: 0 }}>数据源管理</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>刷新</Button>
          {can('datasource:create') && (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>新增数据源</Button>
          )}
        </Space>
      </div>

      <Card>
        <Table columns={columns} dataSource={data} rowKey="id" loading={loading}
          locale={{ emptyText: '暂无数据源' }} size="middle"
          pagination={data.length > 15 ? { pageSize: 15 } : false} />
      </Card>

      {/* 创建弹窗 */}
      <Modal title="新增数据源" open={createOpen} onOk={handleCreate}
        onCancel={() => { setCreateOpen(false); form.resetFields() }} okText="创建">
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="project_id" label="项目 ID" initialValue={1}>
            <Input type="number" />
          </Form.Item>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="生产MySQL" />
          </Form.Item>
          <Form.Item name="source_type" label="类型" rules={[{ required: true }]}>
            <Select options={sourceTypeOptions} />
          </Form.Item>
          <Form.Item name="host" label="主机" initialValue="localhost">
            <Input />
          </Form.Item>
          <Form.Item name="port" label="端口" initialValue={3306}>
            <Input type="number" />
          </Form.Item>
          <Form.Item name="database" label="数据库名">
            <Input placeholder="dataos_platform" />
          </Form.Item>
          <Form.Item name="username" label="用户名">
            <Input placeholder="root" />
          </Form.Item>
          <Form.Item name="password" label="密码">
            <Input.Password placeholder="数据库密码" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 同步弹窗: 选表 + 预览 */}
      <Modal title={`选择要同步的表 (已选 ${syncTables.size} 张)`} open={syncModalOpen}
        onCancel={() => { setSyncModalOpen(false); setSyncTables(new Set()); setSyncResults(null) }}
        onOk={handleSync} okText={`同步 ${syncTables.size} 张表`} confirmLoading={syncing !== null}
        width={640}>
        {tablesLoading ? <Text type="secondary">加载表列表中...</Text> : (
          <div>
            <div style={{ marginBottom: 8 }}>
              <Button size="small" onClick={() => setSyncTables(new Set(tables.map(t => t.name)))}>全选</Button>
              <Button size="small" style={{ marginLeft: 8 }} onClick={() => setSyncTables(new Set())}>取消全选</Button>
            </div>
            {tables.map(t => (
              <div key={t.name} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '6px 12px', margin: '2px 0', background: '#fafafa', borderRadius: 6,
              }}>
                <Checkbox checked={syncTables.has(t.name)}
                  onChange={(e) => {
                    const next = new Set(syncTables)
                    e.target.checked ? next.add(t.name) : next.delete(t.name)
                    setSyncTables(next)
                  }}>
                  <Text strong>{t.name}</Text>
                  <Text type="secondary"> ({t.columns.length} 列)</Text>
                </Checkbox>
                <Button size="small" icon={<EyeOutlined />}
                  onClick={(e) => { e.stopPropagation(); handlePreview(syncDsId!, t.name) }}>
                  预览
                </Button>
              </div>
            ))}
            {tables.length === 0 && <Text type="secondary">无可用表</Text>}

            {/* 同步结果 */}
            {syncResults && (
              <div style={{ marginTop: 12, padding: 8, background: '#f6ffed', borderRadius: 6 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>同步结果:</Text>
                {syncResults.map((r: any) => (
                  <div key={r.table} style={{ fontSize: 12 }}>
                    <Tag color={r.status === 'success' ? 'green' : 'red'}>{r.status}</Tag>
                    {r.table}: {r.rows?.toLocaleString() || '—'} 行
                    {r.error && <Text type="danger"> — {r.error}</Text>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* 同步历史抽屉 */}
      <Drawer title="同步历史" open={historyOpen}
        onClose={() => setHistoryOpen(false)} width={600}>
        <Table columns={[
          { title: '表名', dataIndex: 'table_name', width: 100 },
          { title: '状态', dataIndex: 'status', width: 80,
            render: (s: string) => <Tag color={s === 'success' ? 'green' : 'red'}>{s}</Tag> },
          { title: '行数', dataIndex: 'total_rows', width: 60 },
          { title: '大小', dataIndex: 'total_bytes', width: 80,
            render: (v: number) => v ? `${(v / 1024).toFixed(1)} KB` : '-' },
          { title: '路径', dataIndex: 'storage_path', ellipsis: true,
            render: (v: string) => v ? <Text code style={{ fontSize: 11 }}>{v}</Text> : '-' },
          { title: '时间', dataIndex: 'created_at', width: 140,
            render: (v: string) => v ? new Date(v).toLocaleString() : '-' },
        ]}
        dataSource={syncHistory} rowKey="id" size="small"
        pagination={false}
        locale={{ emptyText: '暂无同步记录' }} />
      </Drawer>

      {/* 预览抽屉 */}
      <Drawer title="数据预览 (前 100 行)" open={previewOpen}
        onClose={() => setPreviewOpen(false)} width={700} loading={previewLoading}>
        <Table columns={previewCols.map(c => ({ title: c, dataIndex: c, key: c, ellipsis: true, width: 150 }))}
          dataSource={previewData.map((row, i) => ({ ...row, _key: i }))}
          rowKey="_key" size="small" scroll={{ x: previewCols.length * 150 }}
          pagination={false} />
      </Drawer>
    </div>
  )
}

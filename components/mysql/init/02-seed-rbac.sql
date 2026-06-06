-- DataOS RBAC 种子数据
-- 此文件供手动 SQL 导入参考, 应用启动时通过 seed_rbac() 自动初始化
-- 导入: docker exec -i dataos-mysql mysql -u root -pdataos_root_2025 < 02-seed-rbac.sql

USE dataos_platform;

-- ============================================================
-- 角色
-- ============================================================
INSERT IGNORE INTO roles (name, display_name, description, scope, is_system) VALUES
('super_admin',   '超级管理员', '平台最高权限，管理所有资源和用户',         'global',  TRUE),
('admin',         '平台管理员', '管理用户和全局配置',                     'global',  TRUE),
('project_owner', '项目负责人', '管理项目内所有资源和成员',               'project', TRUE),
('editor',        '编辑者',     '创建和修改数据源、爬虫、质量规则、API',  'project', TRUE),
('viewer',        '查看者',     '只读查看项目内所有资源',                 'project', TRUE);

-- ============================================================
-- 权限
-- ============================================================
INSERT IGNORE INTO permissions (name, resource, action, description) VALUES
('user:create',   'user', 'create', '创建用户'),
('user:read',     'user', 'read',   '查看用户'),
('user:update',   'user', 'update', '修改用户'),
('user:delete',   'user', 'delete', '删除用户'),
('role:create',   'role', 'create', '创建角色'),
('role:read',     'role', 'read',   '查看角色'),
('role:update',   'role', 'update', '修改角色'),
('role:delete',   'role', 'delete', '删除角色'),
('role:assign',   'role', 'assign', '分配角色给用户'),
('project:create',          'project', 'create',          '创建项目'),
('project:read',            'project', 'read',            '查看项目'),
('project:update',          'project', 'update',          '修改项目信息'),
('project:delete',          'project', 'delete',          '删除/归档项目'),
('project:manage_members',  'project', 'manage_members',  '管理项目成员'),
('datasource:create',          'datasource', 'create',           '注册数据源'),
('datasource:read',            'datasource', 'read',             '查看数据源'),
('datasource:update',          'datasource', 'update',           '修改数据源配置'),
('datasource:delete',          'datasource', 'delete',           '删除数据源'),
('datasource:test_connection', 'datasource', 'test_connection',  '测试数据源连接'),
('datasource:sync',            'datasource', 'sync',             '执行数据同步'),
('crawler:create',  'crawler', 'create', '创建爬虫任务'),
('crawler:read',    'crawler', 'read',   '查看爬虫任务'),
('crawler:update',  'crawler', 'update', '修改爬虫任务'),
('crawler:delete',  'crawler', 'delete', '删除爬虫任务'),
('crawler:start',   'crawler', 'start',  '启动爬虫'),
('crawler:stop',    'crawler', 'stop',   '停止爬虫'),
('quality:create',  'quality', 'create',  '创建质量规则'),
('quality:read',    'quality', 'read',    '查看质量规则'),
('quality:update',  'quality', 'update',  '修改质量规则'),
('quality:delete',  'quality', 'delete',  '删除质量规则'),
('quality:execute', 'quality', 'execute', '执行质量检查'),
('api:create',  'api', 'create',  '创建数据 API'),
('api:read',    'api', 'read',    '查看数据 API'),
('api:update',  'api', 'update',  '修改数据 API'),
('api:delete',  'api', 'delete',  '删除数据 API'),
('api:publish', 'api', 'publish', '发布/下线 API'),
('platform:health',   'platform', 'health',   '查看平台健康状态'),
('platform:settings', 'platform', 'settings', '修改平台配置'),
('platform:audit',    'platform', 'audit',    '查看审计日志');

-- ============================================================
-- 角色-权限绑定
-- ============================================================
-- super_admin → 所有权限
INSERT IGNORE INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'super_admin';

-- admin
INSERT IGNORE INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'admin'
  AND p.name IN (
    'user:create','user:read','user:update','user:delete',
    'role:create','role:read','role:update','role:delete','role:assign',
    'project:create','project:read','project:update','project:delete','project:manage_members',
    'datasource:read','datasource:delete',
    'crawler:read','crawler:delete',
    'quality:read','quality:delete',
    'api:read','api:delete',
    'platform:health','platform:settings','platform:audit'
  );

-- project_owner
INSERT IGNORE INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'project_owner'
  AND p.name IN (
    'project:read','project:update','project:delete','project:manage_members',
    'datasource:create','datasource:read','datasource:update','datasource:delete',
    'datasource:test_connection','datasource:sync',
    'crawler:create','crawler:read','crawler:update','crawler:delete',
    'crawler:start','crawler:stop',
    'quality:create','quality:read','quality:update','quality:delete','quality:execute',
    'api:create','api:read','api:update','api:delete','api:publish',
    'platform:health','role:assign'
  );

-- editor
INSERT IGNORE INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'editor'
  AND p.name IN (
    'project:read',
    'datasource:create','datasource:read','datasource:update',
    'datasource:test_connection','datasource:sync',
    'crawler:create','crawler:read','crawler:update',
    'crawler:start','crawler:stop',
    'quality:create','quality:read','quality:update','quality:execute',
    'api:create','api:read','api:update','api:publish',
    'platform:health'
  );

-- viewer
INSERT IGNORE INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'viewer'
  AND p.name IN (
    'project:read','datasource:read','crawler:read',
    'quality:read','api:read','platform:health'
  );

-- ============================================================
-- 初始 admin 用户 → super_admin 角色
-- ============================================================
INSERT IGNORE INTO user_roles (user_id, role_id)
SELECT 1, id FROM roles WHERE name = 'super_admin';

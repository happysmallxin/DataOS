-- DataOS v1.5 数据库迁移
-- 迁移 ID: 001
-- 描述: 添加 datasources (project_id, name) 唯一约束，防止项目内同名数据源
-- 执行: docker exec -i dataos-mysql mysql -u root -pdataos_root_2025 < 001-add-datasource-unique.sql

USE dataos_platform;

-- 检查并清理已存在的重复数据 (保留最早创建的记录)
-- SELECT project_id, name, COUNT(*) AS cnt
-- FROM datasources
-- GROUP BY project_id, name
-- HAVING cnt > 1;
-- 如果有重复，手动删除或重命名后再执行以下语句。

-- 添加唯一约束
ALTER TABLE datasources
  ADD CONSTRAINT uq_datasource_project_name UNIQUE (project_id, name);

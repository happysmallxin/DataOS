-- DataOS v1.5 数据库迁移
-- 迁移 ID: 004
-- 描述: Pipeline 关联数据源 + 同步历史表
-- 执行: docker exec -i dataos-mysql mysql -u root -pdataos_root_2025 < 004-pipeline-datasource-link.sql

USE dataos_platform;

-- Pipeline 新增字段
ALTER TABLE cleaning_pipelines
  ADD COLUMN datasource_id INTEGER NULL,
  ADD COLUMN source_table VARCHAR(128) NULL,
  ADD COLUMN target_table VARCHAR(128) NULL,
  ADD COLUMN last_output_rows INTEGER NOT NULL DEFAULT 0,
  ADD INDEX idx_pl_datasource (datasource_id),
  ADD FOREIGN KEY (datasource_id) REFERENCES datasources(id) ON DELETE SET NULL;

-- 同步历史表
CREATE TABLE IF NOT EXISTS sync_history (
    id              INTEGER PRIMARY KEY AUTO_INCREMENT,
    datasource_id   INTEGER NOT NULL,
    project_id      INTEGER NOT NULL,
    table_name      VARCHAR(128) NOT NULL,
    sync_mode       VARCHAR(32) NOT NULL DEFAULT 'full',  -- full / incremental
    status          VARCHAR(32) NOT NULL DEFAULT 'running', -- running / success / failed
    total_rows      INTEGER DEFAULT 0,
    total_bytes     INTEGER DEFAULT 0,
    storage_path    VARCHAR(512),
    error_message   TEXT,
    duration_seconds FLOAT,
    triggered_by    INTEGER NOT NULL,
    created_at      DATETIME NOT NULL DEFAULT (now()),

    INDEX idx_sync_ds (datasource_id),
    INDEX idx_sync_project (project_id),
    INDEX idx_sync_time (created_at),
    FOREIGN KEY (datasource_id) REFERENCES datasources(id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (triggered_by) REFERENCES users(id)
);

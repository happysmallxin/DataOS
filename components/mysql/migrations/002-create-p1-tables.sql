-- DataOS v1.5 数据库迁移
-- 迁移 ID: 002
-- 描述: 创建 quality_rules 和 cleaning_pipelines 表 (P1: 项目级持久化隔离)
-- 执行: docker exec -i dataos-mysql mysql -u root -pdataos_root_2025 < 002-create-p1-tables.sql

USE dataos_platform;

-- 质量规则表
CREATE TABLE IF NOT EXISTS quality_rules (
    id              INTEGER PRIMARY KEY AUTO_INCREMENT,
    project_id      INTEGER NOT NULL,
    name            VARCHAR(128) NOT NULL,
    rule_type       VARCHAR(32) NOT NULL,            -- not_null / range / regex / unique / custom_sql
    target_column   VARCHAR(128),
    config          JSON NOT NULL DEFAULT ('{}'),    -- {"min": 0, "max": 100} or {"pattern": "^[A-Z]"}
    description     TEXT,
    is_enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    created_by      INTEGER NOT NULL,
    created_at      DATETIME NOT NULL DEFAULT (now()),
    updated_at      DATETIME NOT NULL DEFAULT (now()),

    INDEX idx_qr_project (project_id),
    INDEX idx_qr_type (rule_type),
    UNIQUE KEY uq_quality_rule_project_name (project_id, name),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- 清洗 Pipeline 表
CREATE TABLE IF NOT EXISTS cleaning_pipelines (
    id              INTEGER PRIMARY KEY AUTO_INCREMENT,
    project_id      INTEGER NOT NULL,
    name            VARCHAR(128) NOT NULL,
    description     TEXT,
    stages          JSON NOT NULL DEFAULT ('[]'),    -- [{"type": "standardize", "config": {...}}, ...]
    status          VARCHAR(32) NOT NULL DEFAULT 'draft',  -- draft / active / archived
    version         INTEGER NOT NULL DEFAULT 1,
    last_run_at     DATETIME,
    created_by      INTEGER NOT NULL,
    created_at      DATETIME NOT NULL DEFAULT (now()),
    updated_at      DATETIME NOT NULL DEFAULT (now()),

    INDEX idx_pl_project (project_id),
    INDEX idx_pl_status (status),
    UNIQUE KEY uq_pipeline_project_name (project_id, name),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

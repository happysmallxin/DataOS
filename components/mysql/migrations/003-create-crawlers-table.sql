-- DataOS v1.5 数据库迁移
-- 迁移 ID: 003
-- 描述: 创建 crawlers 表 (P2: 爬虫任务项目归属映射)
-- Crawlab 侧的 spider/task 通过 crawlab_task_id 关联
-- 执行: docker exec -i dataos-mysql mysql -u root -pdataos_root_2025 < 003-create-crawlers-table.sql

USE dataos_platform;

CREATE TABLE IF NOT EXISTS crawlers (
    id                  INTEGER PRIMARY KEY AUTO_INCREMENT,
    project_id          INTEGER NOT NULL,
    name                VARCHAR(128) NOT NULL,
    target_url          VARCHAR(512),
    framework           VARCHAR(64) NOT NULL DEFAULT 'Scrapy',
    config              JSON NOT NULL DEFAULT ('{}'),
    description         TEXT,
    status              VARCHAR(32) NOT NULL DEFAULT 'draft',  -- draft/active/running/stopped/error
    crawlab_task_id     VARCHAR(128),                           -- Crawlab 侧任务 ID
    last_run_at         DATETIME,
    last_status         VARCHAR(32),
    total_runs          INTEGER NOT NULL DEFAULT 0,
    total_rows_collected INTEGER NOT NULL DEFAULT 0,
    created_by          INTEGER NOT NULL,
    created_at          DATETIME NOT NULL DEFAULT (now()),
    updated_at          DATETIME NOT NULL DEFAULT (now()),

    INDEX idx_crawler_project (project_id),
    INDEX idx_crawler_status (status),
    INDEX idx_crawler_crawlab (crawlab_task_id),
    UNIQUE KEY uq_crawler_project_name (project_id, name),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

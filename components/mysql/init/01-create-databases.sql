-- DataOS MySQL 初始化脚本
-- 为所有组件创建数据库和用户权限

CREATE USER IF NOT EXISTS 'dataos'@'%' IDENTIFIED BY 'dataos_2025';
GRANT ALL PRIVILEGES ON *.* TO 'dataos'@'%' WITH GRANT OPTION;

-- DolphinScheduler 数据库
CREATE DATABASE IF NOT EXISTS dolphinscheduler DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- OpenMetadata 数据库
CREATE DATABASE IF NOT EXISTS openmetadata DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- SeaTunnel 元数据库
CREATE DATABASE IF NOT EXISTS seatunnel DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Datavines 数据库
CREATE DATABASE IF NOT EXISTS datavines DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- DataOS 平台数据库
CREATE DATABASE IF NOT EXISTS dataos_platform DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

FLUSH PRIVILEGES;

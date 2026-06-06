"""爬虫任务模型 — P2: 项目级爬虫任务映射.

Crawlab 是实际的爬虫执行引擎，DataOS 通过此表建立项目归属映射。
Crawlab 侧的 spider/task 通过 crawlab_task_id 关联。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, func, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Crawler(Base):
    """项目级爬虫任务 — project_id 隔离, 映射到 Crawlab 任务."""

    __tablename__ = "crawlers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # 目标 URL / 网站
    target_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # 爬虫框架: Scrapy / Crawlee / Selenium / Playwright / Custom
    framework: Mapped[str] = mapped_column(String(64), default="Scrapy")
    # 爬取配置 JSON: {"spider": "...", "start_urls": [...], "rules": {...}}
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 状态: draft / active / running / stopped / error
    status: Mapped[str] = mapped_column(String(32), default="draft")
    # Crawlab 映射 (P2: 标记任务归属, Crawlab 侧通过 tag 传递 project_id)
    crawlab_task_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    # 统计数据
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    total_runs: Mapped[int] = mapped_column(default=0)
    total_rows_collected: Mapped[int] = mapped_column(default=0)
    # 创建者
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_crawler_project_name"),
    )

    def __repr__(self) -> str:
        return f"<Crawler(id={self.id}, name='{self.name}', project={self.project_id})>"

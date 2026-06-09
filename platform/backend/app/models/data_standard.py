"""数据标准模型 — 字段标准 + 字段映射 + 编码字典 (对齐MES数据集平台)."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, func, ForeignKey, JSON, UniqueConstraint, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DataStandard(Base):
    """标准字段定义 — 公司级统一的数据元素."""

    __tablename__ = "data_standards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    domain_id: Mapped[Optional[int]] = mapped_column(ForeignKey("data_domains.id", ondelete="SET NULL"), nullable=True)
    code: Mapped[str] = mapped_column(String(128), nullable=False)             # 标准字段编码: WORK_ORDER_CODE
    name: Mapped[str] = mapped_column(String(256), nullable=False)             # 字段名称: 工单号
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)    # 字段含义
    data_type: Mapped[str] = mapped_column(String(64), default="VARCHAR")      # 数据类型
    length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)       # 字段长度
    precision: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)    # 精度
    nullable: Mapped[bool] = mapped_column(Boolean, default=False)
    default_value: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    is_primary_key: Mapped[bool] = mapped_column(Boolean, default=False)
    is_foreign_key: Mapped[bool] = mapped_column(Boolean, default=False)
    ref_table: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # 关联表
    category: Mapped[str] = mapped_column(String(32), default="dimension")     # dimension/measure/status/time/relation
    quality_rule: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)  # 质量规则模板
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_standard_project_code"),)


class FieldMapping(Base):
    """字段映射 — 源字段到标准字段的映射关系."""

    __tablename__ = "field_mappings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    datasource_id: Mapped[Optional[int]] = mapped_column(ForeignKey("datasources.id", ondelete="CASCADE"), nullable=True)
    source_table: Mapped[str] = mapped_column(String(128), nullable=False)      # 源表名
    source_field: Mapped[str] = mapped_column(String(128), nullable=False)       # 源字段名
    standard_id: Mapped[int] = mapped_column(ForeignKey("data_standards.id", ondelete="CASCADE"), nullable=False)
    transform_rule: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)  # 转换规则: direct/code_map/expression
    transform_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)       # 转换配置
    confidence: Mapped[float] = mapped_column(default=1.0)                               # 映射置信度
    status: Mapped[str] = mapped_column(String(32), default="mapped")                   # mapped/unmapped/review
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("project_id", "source_table", "source_field", name="uq_mapping_source"),)


class CodeDictionary(Base):
    """编码字典 — 状态值/编码值的标准化映射."""

    __tablename__ = "code_dictionaries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)             # 字典名称: 工单状态
    code: Mapped[str] = mapped_column(String(128), nullable=False)             # 字典编码: order_status
    source_value: Mapped[str] = mapped_column(String(256), nullable=False)     # 原始值: 0/1/2/3
    standard_value: Mapped[str] = mapped_column(String(256), nullable=False)   # 标准值: 未发布/部分发布/已发布/完工
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("project_id", "code", "source_value", name="uq_dict_code_value"),)

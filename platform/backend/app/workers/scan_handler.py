"""表扫描任务 Worker 处理函数."""

import logging
logger = logging.getLogger(__name__)


def handle_scan_job(redis_client, job_id: str, **params) -> dict:
    """扫描数据源表列表 (在 Worker 线程中运行)."""
    from app.core.database import SessionLocal
    from app.models.datasource import DataSource
    from app.core.crypto import decrypt_config
    from sqlalchemy import create_engine, inspect

    ds_id = params.get("ds_id", 0)
    limit = params.get("limit", 0)

    db = SessionLocal()
    try:
        ds = db.get(DataSource, ds_id)
        if not ds:
            raise ValueError(f"数据源 {ds_id} 不存在")

        cfg = decrypt_config(ds.config)
        if ds.source_type == "mysql":
            url = f"mysql+pymysql://{cfg.get('username')}:{cfg.get('password')}@{cfg.get('host')}:{cfg.get('port', 3306)}/{cfg.get('database')}"
        elif ds.source_type == "postgresql":
            url = f"postgresql+psycopg2://{cfg.get('username')}:{cfg.get('password')}@{cfg.get('host')}:{cfg.get('port', 5432)}/{cfg.get('database')}"
        else:
            url = f"sqlite:///{cfg.get('path', '/tmp/data.db')}"

        engine = create_engine(url, connect_args={"connect_timeout": 30})
        inspector = inspect(engine)
        all_tables = inspector.get_table_names()
        total = len(all_tables)
        take = limit if limit > 0 else total

        redis_client.hset(f"job:{job_id}", "progress", 30)
        tables = []
        for i, name in enumerate(all_tables[:take]):
            try:
                cols = [{"name": c["name"], "type": str(c["type"])} for c in inspector.get_columns(name)]
                tables.append({"name": name, "columns": cols})
            except Exception:
                tables.append({"name": name, "columns": []})
            if i % 50 == 0:
                progress = 30 + int((i / max(take, 1)) * 60)
                redis_client.hset(f"job:{job_id}", "progress", progress)

        engine.dispose()
        return {"tables": tables, "total": total, "returned": len(tables)}

    finally:
        db.close()

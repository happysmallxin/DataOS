"""同步任务 Worker 处理函数 — 由 job_queue Worker 调用 (同步线程)."""

import time
import logging
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import create_engine, text, select as sa_select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def handle_sync_job(redis_client, job_id: str, **params) -> dict:
    """执行同步任务 (在 Worker 线程中同步运行).

    params: ds_id, table_name (单表) 或 table_names (批量), sync_mode, sync_column, user_id
    """
    from app.core.config import settings
    from app.core.crypto import decrypt_config
    from app.core.minio_client import write_dataframe, read_dataframe, get_bronze_path
    from app.models.datasource import DataSource
    from app.models.sync_history import SyncHistory
    from app.models.audit_log import AuditLog
    from app.core.database import SessionLocal

    ds_id = params["ds_id"]
    table_names = params.get("table_names", [])
    if not table_names:
        tn = params.get("table_name", "")
        table_names = [tn] if tn else []
    sync_mode = params.get("sync_mode", "full")
    sync_column = params.get("sync_column", "updated_at")
    user_id = params.get("user_id", 1)

    db = SessionLocal()
    try:
        ds = db.get(DataSource, ds_id)
        if not ds:
            raise ValueError(f"数据源 {ds_id} 不存在")

        results = {"tables_done": 0, "total_rows": 0, "skipped": 0}
        total_tables = len(table_names)

        for idx, table_name in enumerate(table_names):
            if not table_name.strip():
                continue

            progress = 10 + int((idx / max(total_tables, 1)) * 80)
            try:
                redis_client.hset(f"job:{job_id}", "progress", progress)
            except Exception:
                pass

            sync_record = SyncHistory(
                datasource_id=ds_id, project_id=ds.project_id or 0,
                table_name=table_name, sync_mode=sync_mode,
                status="running", triggered_by=user_id,
            )
            db.add(sync_record)
            db.commit()
            db.refresh(sync_record)

            start = time.time()
            try:
                cfg = decrypt_config(ds.config)
                if ds.source_type == "mysql":
                    url = f"mysql+pymysql://{cfg.get('username')}:{cfg.get('password')}@{cfg.get('host')}:{cfg.get('port', 3306)}/{cfg.get('database')}"
                elif ds.source_type == "postgresql":
                    url = f"postgresql+psycopg2://{cfg.get('username')}:{cfg.get('password')}@{cfg.get('host')}:{cfg.get('port', 5432)}/{cfg.get('database')}"
                else:
                    raise ValueError(f"不支持的数据源类型: {ds.source_type}")

                engine = create_engine(url, connect_args={"connect_timeout": 30} if "sqlite" not in url else {})

                if sync_mode == "incremental":
                    last_sync = db.query(SyncHistory).filter(
                        SyncHistory.datasource_id == ds_id,
                        SyncHistory.table_name == table_name,
                        SyncHistory.status == "success",
                    ).order_by(SyncHistory.created_at.desc()).first()
                    if last_sync and last_sync.last_sync_value:
                        sql = f"SELECT * FROM {table_name} WHERE {sync_column} > '{last_sync.last_sync_value}'"
                    else:
                        sql = f"SELECT * FROM {table_name}"
                else:
                    sql = f"SELECT * FROM {table_name}"

                df_new = pd.read_sql(sql, engine)

                if sync_mode == "incremental" and last_sync and last_sync.storage_path:
                    try:
                        ek = last_sync.storage_path.replace(f"{settings.MINIO_BUCKET_BRONZE}/", "")
                        df_existing = read_dataframe(settings.MINIO_BUCKET_BRONZE, ek)
                        df = pd.concat([df_existing, df_new], ignore_index=True).drop_duplicates(keep="last")
                    except Exception:
                        df = df_new
                else:
                    df = df_new

                if not df.empty and sync_column in df.columns:
                    sync_record.sync_column = sync_column
                    sync_record.last_sync_value = str(df[sync_column].max())

                engine.dispose()

                date_str = pd.Timestamp.now().strftime("%Y-%m-%d")
                prefix = get_bronze_path(ds.project_id, ds_id, table_name, date_str)
                key = f"{prefix}full_{pd.Timestamp.now().strftime('%H%M%S')}.parquet"
                result = write_dataframe(df, settings.MINIO_BUCKET_BRONZE, key)

                sync_record.status = "success"
                sync_record.total_rows = len(df)
                sync_record.total_bytes = result["size_bytes"]
                sync_record.storage_path = f"{settings.MINIO_BUCKET_BRONZE}/{key}"
                sync_record.duration_seconds = round(time.time() - start, 2)
                ds.last_sync_at = datetime.now(timezone.utc)

                db.add(AuditLog(user_id=user_id, project_id=ds.project_id,
                    resource="datasource", action="sync",
                    target_id=ds_id, target_name=ds.name,
                    detail={"table": table_name, "rows": len(df), "path": key}))

                db.commit()
                results["tables_done"] += 1
                results["total_rows"] += len(df)
            except Exception as e:
                sync_record.status = "failed"
                sync_record.error_message = str(e)
                sync_record.duration_seconds = round(time.time() - start, 2)
                db.commit()

        return results

    finally:
        db.close()

"""MinIO 对象存储客户端 — 数据暂存层 (Bronze/Silver).

使用 boto3 S3 API 兼容 MinIO:
  - Bronze: 原始数据 (数据源同步产物)
  - Silver: 清洗后数据 (Pipeline 输出)
"""

import io
import logging
from datetime import datetime

import boto3
import pandas as pd
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---- S3 client (lazy init) ----

_s3_client = None


def _get_s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=f"http{'s' if settings.MINIO_SECURE else ''}://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        # 确保 bucket 存在
        for bucket in [settings.MINIO_BUCKET_BRONZE, settings.MINIO_BUCKET_SILVER]:
            try:
                _s3_client.head_bucket(Bucket=bucket)
            except ClientError:
                _s3_client.create_bucket(Bucket=bucket)
                logger.info(f"MinIO bucket 已创建: {bucket}")
    return _s3_client


# ---- Public API ----

def write_dataframe(df: pd.DataFrame, bucket: str, key: str) -> dict:
    """将 DataFrame 以 Parquet 格式写入 MinIO.

    Args:
        df: pandas DataFrame
        bucket: bronze / silver
        key: 对象路径, 如 datasources/3/mysql_prod/orders/2026-06-06/batch_001.parquet

    Returns:
        {"bucket": ..., "key": ..., "size_bytes": ..., "rows": ...}
    """
    s3 = _get_s3()
    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow")
    buf.seek(0)
    size = buf.getbuffer().nbytes

    s3.put_object(Bucket=bucket, Key=key, Body=buf.getvalue())
    logger.info(f"MinIO 写入: {bucket}/{key} ({size} bytes, {len(df)} rows)")
    return {"bucket": bucket, "key": key, "size_bytes": size, "rows": len(df)}


def read_dataframe(bucket: str, key: str) -> pd.DataFrame:
    """从 MinIO 读取 Parquet 文件为 DataFrame."""
    s3 = _get_s3()
    resp = s3.get_object(Bucket=bucket, Key=key)
    df = pd.read_parquet(io.BytesIO(resp["Body"].read()), engine="pyarrow")
    logger.info(f"MinIO 读取: {bucket}/{key} ({len(df)} rows)")
    return df


def list_objects(bucket: str, prefix: str) -> list[dict]:
    """列出 MinIO 中的对象.

    Returns:
        [{"key": "...", "size": ..., "last_modified": ...}, ...]
    """
    s3 = _get_s3()
    try:
        resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        return [
            {"key": obj["Key"], "size": obj["Size"], "last_modified": obj["LastModified"]}
            for obj in resp.get("Contents", [])
        ]
    except ClientError:
        return []


def delete_objects(bucket: str, prefix: str) -> int:
    """删除 MinIO 中指定前缀的所有对象. 返回删除数量."""
    s3 = _get_s3()
    objects = list_objects(bucket, prefix)
    if not objects:
        return 0
    s3.delete_objects(
        Bucket=bucket,
        Delete={"Objects": [{"Key": o["key"]} for o in objects]},
    )
    logger.info(f"MinIO 删除: {bucket}/{prefix} ({len(objects)} 个对象)")
    return len(objects)


def get_bronze_path(datasource_id: int, table_name: str, date_str: str | None = None) -> str:
    """生成 Bronze 层存储路径."""
    date = date_str or datetime.now().strftime("%Y-%m-%d")
    return f"datasources/{datasource_id}/{table_name}/{date}/"


def get_silver_path(project_id: int, pipeline_name: str, date_str: str | None = None) -> str:
    """生成 Silver 层存储路径."""
    date = date_str or datetime.now().strftime("%Y-%m-%d")
    safe_name = pipeline_name.lower().replace(" ", "_")
    return f"projects/{project_id}/{safe_name}/{date}/"

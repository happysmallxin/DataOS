"""Worker 处理函数注册."""

from app.core.job_queue import register_handler
from app.workers.sync_handler import handle_sync_job
from app.workers.scan_handler import handle_scan_job


def init_handlers():
    register_handler("sync", handle_sync_job)
    register_handler("scan_tables", handle_scan_job)

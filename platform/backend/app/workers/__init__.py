"""Worker 处理函数注册."""

from app.core.job_queue import register_handler
from app.workers.sync_handler import handle_sync_job


def init_handlers():
    register_handler("sync", handle_sync_job)

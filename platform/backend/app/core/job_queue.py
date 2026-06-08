"""Redis 任务队列 — 异步执行同步/清洗等耗时操作.

设计:
  - 队列: Redis List (job:queue:{type})
  - 状态: Redis Hash (job:{id}) — status/progress/result/error
  - Worker: 后台线程, BRPOP 阻塞等待任务

用法:
  from app.core.job_queue import enqueue_job, get_job_status
  job_id = await enqueue_job("sync", ds_id=3, table="users")
  status = await get_job_status(job_id)  # → {status, progress, result, ...}
"""

import json
import uuid
import logging
import asyncio
import threading
from typing import Callable, Any

logger = logging.getLogger(__name__)

_redis = None

# 队列名
QUEUE_SYNC = "job:queue:sync"
QUEUE_CLEAN = "job:queue:clean"

# 注册的处理函数
_handlers: dict[str, Callable] = {}


def register_handler(job_type: str, handler: Callable):
    """注册任务类型的处理函数."""
    _handlers[job_type] = handler
    logger.info(f"Job handler 注册: {job_type}")


async def _get_redis():
    global _redis
    if _redis is not None:
        return _redis
    try:
        import redis.asyncio as aioredis
        from app.core.config import settings
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await _redis.ping()
    except Exception:
        _redis = None
    return _redis


async def enqueue_job(job_type: str, **params) -> str:
    """提交异步任务, 返回 job_id."""
    redis = await _get_redis()
    if not redis:
        raise RuntimeError("Redis 不可用, 无法提交异步任务")

    job_id = str(uuid.uuid4())[:8]
    job_data = {
        "id": job_id,
        "type": job_type,
        "status": "pending",
        "progress": 0,
        "created_at": str(asyncio.get_event_loop().time()),
        "params": json.dumps(params),
        "result": "",
        "error": "",
    }

    await redis.hset(f"job:{job_id}", mapping=job_data)
    await redis.expire(f"job:{job_id}", 86400)  # 24h TTL

    queue_key = {"sync": QUEUE_SYNC, "clean": QUEUE_CLEAN}.get(job_type, QUEUE_SYNC)
    await redis.lpush(queue_key, job_id)
    logger.info(f"Job 入队: {job_id} ({job_type}) — {params}")
    return job_id


async def update_job(job_id: str, **fields):
    """更新任务状态."""
    redis = await _get_redis()
    if not redis:
        return
    await redis.hset(f"job:{job_id}", mapping={k: str(v) if not isinstance(v, str) else v for k, v in fields.items()})


async def get_job_status(job_id: str) -> dict | None:
    """查询任务状态."""
    redis = await _get_redis()
    if not redis:
        return None
    data = await redis.hgetall(f"job:{job_id}")
    if not data:
        return None
    # 解析 JSON 字段
    for k in ("params", "result"):
        if data.get(k):
            try:
                data[k] = json.loads(data[k])
            except json.JSONDecodeError:
                pass
    data["progress"] = int(data.get("progress", 0))
    return data


# ---- Worker (后台线程) ----

_worker_running = False


def start_worker():
    """启动后台 Worker 线程."""
    global _worker_running
    if _worker_running:
        return
    _worker_running = True
    t = threading.Thread(target=_worker_loop, daemon=True, name="job-worker")
    t.start()
    logger.info("Job Worker 已启动")


def _worker_loop():
    """Worker 主循环 — BRPOP 阻塞等待任务."""
    import redis as sync_redis
    from app.core.config import settings

    try:
        r = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)
        r.ping()
    except Exception as e:
        logger.warning(f"Worker: Redis 不可用, 退出 — {e}")
        return

    logger.info("Worker: 开始监听队列...")
    while _worker_running:
        try:
            # BRPOP 阻塞等待, 超时 5s
            result = r.brpop([QUEUE_SYNC, QUEUE_CLEAN], timeout=5)
            if result is None:
                continue

            queue, job_id = result
            logger.info(f"Worker: 收到任务 {job_id} from {queue}")

            # 获取任务详情
            job_data = r.hgetall(f"job:{job_id}")
            if not job_data:
                continue

            job_type = job_data.get("type", "")
            params = json.loads(job_data.get("params", "{}"))

            # 更新状态为 running
            r.hset(f"job:{job_id}", mapping={"status": "running", "progress": 10})

            # 执行处理函数
            handler = _handlers.get(job_type)
            if handler:
                try:
                    result_data = handler(r, job_id, **params)
                    r.hset(f"job:{job_id}", mapping={
                        "status": "completed",
                        "progress": 100,
                        "result": json.dumps(result_data, default=str, ensure_ascii=False),
                    })
                except Exception as e:
                    logger.error(f"Worker: 任务 {job_id} 失败 — {e}")
                    r.hset(f"job:{job_id}", mapping={
                        "status": "failed",
                        "progress": 100,
                        "error": str(e),
                    })
            else:
                r.hset(f"job:{job_id}", mapping={
                    "status": "failed",
                    "error": f"未知任务类型: {job_type}",
                })

        except Exception as e:
            logger.error(f"Worker loop error: {e}")

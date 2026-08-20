"""Celery异步任务 - 应用初始化"""

from celery import Celery

from app.core.config import settings

# 创建Celery实例
celery_app = Celery(
    "recruitment",
    broker=settings.REDIS_URL.replace("/0", "/1"),  # 使用Redis DB 1作为broker
    backend=settings.REDIS_URL.replace("/0", "/2"),  # 使用Redis DB 2存结果
)

# Celery配置
celery_app.conf.update(
    # 序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,

    # 任务行为
    task_track_started=True,
    task_acks_late=True,                # 任务完成后才确认（防丢失）
    worker_prefetch_multiplier=1,       # 公平调度

    # 结果过期
    result_expires=3600,                # 结果保留1小时

    # 重试
    task_default_retry_delay=60,        # 默认重试间隔60秒
    task_max_retries=3,

    # 任务路由
    task_routes={
        "app.tasks.resume_tasks.*": {"queue": "resume"},
    },
)

# 自动发现任务
celery_app.autodiscover_tasks(["app.tasks"])

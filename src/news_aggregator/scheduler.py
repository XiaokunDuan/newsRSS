"""定时任务调度模块"""

import asyncio
import logging
from datetime import datetime
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import Config
from .fetcher import NewsFetcher
from .summarizer import QuickSummarizer
from .daily_report import DailyReportGenerator

logger = logging.getLogger(__name__)


class NewsScheduler:
    """新闻调度器"""

    def __init__(self, config: Config):
        self.config = config
        self.scheduler = AsyncIOScheduler()
        self.fetcher = NewsFetcher(config)
        self.quick_summarizer = QuickSummarizer(config)
        self._callback: Optional[Callable] = None

    def set_callback(self, callback: Callable):
        """设置任务完成回调"""
        self._callback = callback

    async def run_once(self) -> bool:
        """执行一次新闻聚合（逐篇分析模式）"""
        start_time = datetime.now()
        logger.info(f"开始新闻聚合任务: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            generator = DailyReportGenerator(self.config)
            success = await generator.run()

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.info(f"任务完成，耗时 {duration:.1f} 秒")

            # 触发回调
            if self._callback:
                try:
                    self._callback(success)
                except Exception as e:
                    logger.error(f"回调执行失败: {e}")

            return success

        except Exception as e:
            logger.error(f"任务执行失败: {e}")
            return False

    async def _scheduled_task(self):
        """定时任务包装器"""
        try:
            await self.run_once()
        except Exception as e:
            logger.error(f"定时任务执行失败: {e}")

    def start(self, cron_expression: Optional[str] = None):
        """启动定时任务"""
        if cron_expression is None:
            cron_expression = self.config.schedule_cron

        # 解析 cron 表达式
        parts = cron_expression.split()
        if len(parts) != 5:
            raise ValueError(f"无效的 cron 表达式: {cron_expression}")

        minute, hour, day, month, day_of_week = parts

        # 获取时区
        try:
            tz = ZoneInfo(self.config.timezone)
        except Exception:
            tz = ZoneInfo("Asia/Shanghai")

        trigger = CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            timezone=tz,
        )

        self.scheduler.add_job(
            self._scheduled_task,
            trigger=trigger,
            id="news_aggregation",
            name="新闻聚合任务",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info(f"定时任务已启动，cron: {cron_expression}，时区: {self.config.timezone}")

    def stop(self):
        """停止定时任务"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("定时任务已停止")

    def get_next_run_time(self) -> Optional[datetime]:
        """获取下次执行时间"""
        job = self.scheduler.get_job("news_aggregation")
        if job:
            return job.next_run_time
        return None


async def run_daily_report(config: Config, send_telegram: bool = False) -> bool:
    """运行每日报告"""
    generator = DailyReportGenerator(config)
    return await generator.run(
        send_telegram=send_telegram,
        telegram_bot_token=config.telegram_bot_token,
        telegram_chat_id=config.telegram_chat_id,
    )

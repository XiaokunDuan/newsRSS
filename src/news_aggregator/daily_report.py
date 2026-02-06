"""每日新闻报告生成器（逐篇分析模式）

功能：
1. 抓取所有新闻源
2. 使用 LLM 逐篇分析
3. 处理被审查的内容（单独保存）
4. 生成报告
5. 可选发送到Telegram
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

from .config import Config
from .sources import NEWS_SOURCES
from .fetcher import NewsFetcher, NewsItem
from .bypass import PaywallBypass
from .telegram_sender import TelegramSender
from .data_classes import ArticleResult, AnalysisConfig, DailyAnalysisSummary
from .article_analyzer import PerArticleAnalyzer
from .jsonl_writer import JSONLWriter
from .file_cleaner import FileCleaner

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """分析结果"""
    success: bool
    results: list[ArticleResult] = None
    censored_count: int = 0
    error_count: int = 0
    raw_news: Optional[list] = None
    stats: Optional[dict] = None


class DailyReportGenerator:
    """每日报告生成器（逐篇分析模式）"""

    def __init__(self, config: Config):
        self.config = config
        self.output_dir = config.output_dir

        # 逐篇分析模式配置
        self.analysis_config = AnalysisConfig(
            max_concurrent=config.per_article_max_concurrent,
            max_retries=config.per_article_max_retries,
            timeout_seconds=30,
            keep_days=config.per_article_keep_days,
            enable_auto_clean=config.per_article_enable_auto_clean,
            analysis_mode="per_article",
        )
        self.analyzer = PerArticleAnalyzer(config, self.analysis_config)
        self.writer = JSONLWriter(
            self.output_dir,
            subdir="articles",
            incremental_mode=True,
            deduplicate=True
        )
        self.cleaner = FileCleaner(
            self.output_dir,
            keep_days=config.per_article_keep_days,
            enable_auto_clean=config.per_article_enable_auto_clean,
        )

    async def fetch_all_news(self) -> list[NewsItem]:
        """抓取所有新闻"""
        logger.info("开始抓取新闻...")

        fetcher = NewsFetcher(self.config)

        bypass = PaywallBypass(
            proxy=self.config.http_proxy,
            timeout=35,
            bpc_extension_path=self.config.bpc_extension_path,
            use_browser_fallback=True,
        )

        try:
            # 抓取 RSS
            news_items = await fetcher.fetch_all_sources(NEWS_SOURCES)
            logger.info(f"抓取到 {len(news_items)} 条新闻")

            # 付费墙处理
            paywall_items = [n for n in news_items if n.has_paywall]
            if paywall_items:
                logger.info(f"处理 {len(paywall_items)} 条付费墙新闻...")
                urls = [n.link for n in paywall_items[:30]]  # 限制数量
                results = await bypass.batch_get_articles(urls, max_concurrent=3)

                for item in paywall_items:
                    if item.link in results and results[item.link].success:
                        result = results[item.link]
                        if result.content:
                            item.full_content = result.content

            return news_items

        finally:
            await bypass.close()

    async def analyze_news(self, news_items: list[NewsItem]) -> AnalysisResult:
        """逐篇分析新闻"""
        if not news_items:
            return AnalysisResult(success=False)

        logger.info(f"开始逐篇分析 {len(news_items)} 条新闻...")

        try:
            # 逐篇分析
            results = await self.analyzer.analyze_articles(news_items, detailed=True)

            # 写入结果
            stats = self.writer.batch_write_results(results, atomic=True)

            # 获取统计信息
            analysis_stats = self.analyzer.get_summary_statistics(results)

            # 创建每日摘要
            summary = DailyAnalysisSummary(
                date=datetime.now().strftime("%Y-%m-%d"),
                total_articles=len(news_items),
                analyzed_articles=analysis_stats['analyzed_articles'],
                censored_articles=analysis_stats['censored_articles'],
                average_importance=analysis_stats['average_importance'],
                top_categories=analysis_stats['category_distribution'],
                jsonl_file=self.writer.articles_file,
                censored_file=self.writer.censored_file,
            )

            # 写入摘要
            self.writer.write_summary(summary, incremental=True)

            # 清理旧文件
            if self.config.per_article_enable_auto_clean:
                cleanup_stats = self.cleaner.run_scheduled_cleanup(dry_run=False)
                logger.info(f"自动清理完成: {cleanup_stats['summary']}")

            return AnalysisResult(
                success=True,
                results=results,
                censored_count=analysis_stats['censored_articles'],
                error_count=analysis_stats['error_count'],
                raw_news=[asdict(n) for n in news_items[:50]],
                stats=analysis_stats
            )

        except Exception as e:
            logger.error(f"逐篇分析失败: {e}")
            return AnalysisResult(
                success=False,
                error_count=len(news_items),
                raw_news=[asdict(n) for n in news_items[:50]],
            )

    def save_report(self, summary: str, date_str: str) -> Path:
        """保存报告"""
        filepath = self.output_dir / f"daily-report-{date_str}.md"

        content = f"""# 每日新闻简报

**日期**: {date_str}
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

{summary}

---

*本报告由 AI 自动生成，仅供参考。*
"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"报告已保存: {filepath}")
        return filepath

    def _generate_summary_from_jsonl(self, articles: list[dict]) -> str:
        """从JSONL数据生成摘要"""
        # 提取最重要的文章
        important_articles = sorted(
            [a for a in articles if a.get('importance', 0) >= 7],
            key=lambda x: x.get('importance', 0),
            reverse=True
        )[:10]

        lines = ["# 今日重要新闻摘要\n"]
        for i, article in enumerate(important_articles, 1):
            lines.append(f"\n## {i}. {article.get('title', '未知标题')}")
            lines.append(f"**来源**: {article.get('source_name', '未知')}")
            lines.append(f"**重要性**: {article.get('importance', 5)}/10")
            if article.get('summary'):
                lines.append(f"**摘要**: {article.get('summary')}")
            if article.get('key_points'):
                lines.append(f"**关键点**:")
                for point in article.get('key_points', [])[:3]:
                    lines.append(f"  • {point}")

        return '\n'.join(lines)

    def _format_stats_for_telegram(self, stats: dict, date_str: str) -> str:
        """格式化统计信息用于Telegram发送"""
        return f"📊 每日新闻分析统计 - {date_str}\n\n" + \
               f"📰 总文章数: {stats.get('total_articles', 0)}\n" + \
               f"✅ 成功分析: {stats.get('analyzed_articles', 0)}\n" + \
               f"⚠️ 被审查: {stats.get('censored_articles', 0)}\n" + \
               f"⭐ 平均重要性: {stats.get('average_importance', 0):.1f}/10\n\n" + \
               f"📈 类别分布:\n" + \
               self._format_category_distribution(stats.get('category_distribution', {}))

    def _format_category_distribution(self, distribution: dict) -> str:
        """格式化类别分布"""
        if not distribution:
            return "   无类别数据"

        lines = []
        for category, count in sorted(distribution.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"    • {category}: {count} 篇")
        return '\n'.join(lines)

    async def run(
        self,
        send_telegram: bool = False,
        telegram_bot_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
    ) -> bool:
        """运行每日报告生成

        Args:
            send_telegram: 是否发送到Telegram
            telegram_bot_token: Telegram Bot Token
            telegram_chat_id: Telegram Chat ID

        Returns:
            是否成功
        """
        date_str = datetime.now().strftime("%Y-%m-%d")
        logger.info(f"开始生成 {date_str} 每日报告（逐篇分析模式）...")

        try:
            # 1. 抓取新闻
            news_items = await self.fetch_all_news()

            if not news_items:
                logger.error("没有抓取到任何新闻")
                return False

            # 2. 分析新闻
            result = await self.analyze_news(news_items)

            # 3. 处理结果
            if not result.success:
                # 逐篇模式下，即使部分失败，如果分析过一些文章也算成功
                if result.results and len(result.results) > 0:
                    logger.warning(f"逐篇分析部分失败: 成功 {len(result.results)} 篇，失败 {result.error_count} 篇")
                else:
                    logger.error(f"分析完全失败: {result.error_count} 篇全部失败")
                    return False

            # 4. 保存报告
            if result.results:
                # 从JSONL文件读取成功分析的文章
                articles = self.writer.read_articles()
                if articles:
                    summary_text = self._generate_summary_from_jsonl(articles)
                    self.save_report(summary_text, date_str)
                    logger.info(f"生成摘要报告，基于 {len(articles)} 篇成功分析的文章")
                else:
                    logger.warning("没有成功分析的文章，跳过报告生成")

                # 显示进度信息
                progress_info = self.writer.get_progress_info()
                logger.info(f"处理进度: {progress_info['processed_count']} 篇文章已处理")

            # 5. 发送到Telegram
            if send_telegram and telegram_bot_token and telegram_chat_id:
                try:
                    # 找到生成的报告文件
                    report_files = list(self.output_dir.glob(f"daily-report-{date_str}.*"))
                    if not report_files:
                        # 发送统计信息
                        if result.stats:
                            stats_text = self._format_stats_for_telegram(result.stats, date_str)
                            telegram_sender = TelegramSender(telegram_bot_token, telegram_chat_id)
                            telegram_success = await telegram_sender.send_document(
                                self.output_dir / f"daily-stats-{date_str}.txt",
                                caption=f"📊 每日新闻统计 - {date_str}"
                            )
                            if telegram_success:
                                logger.info(f"Telegram统计信息发送成功")
                            else:
                                logger.error("Telegram统计信息发送失败")
                        else:
                            logger.warning("未找到每日报告文件，跳过Telegram发送")
                    else:
                        # 发送报告文件内容
                        for report_file in report_files:
                            telegram_sender = TelegramSender(telegram_bot_token, telegram_chat_id)
                            telegram_success = await telegram_sender.send_document(
                                report_file,
                                caption=f"📰 每日新闻简报 - {date_str}"
                            )
                            if telegram_success:
                                logger.info(f"Telegram报告发送成功: {report_file.name}")
                            else:
                                logger.error(f"Telegram报告发送失败: {report_file.name}")

                except Exception as e:
                    logger.error(f"Telegram发送失败: {e}")

            logger.info("每日报告生成完成")
            return True

        except Exception as e:
            logger.error(f"生成报告失败: {e}")
            return False


async def run_daily_report(
    config: Config,
    send_telegram: bool = False,
) -> bool:
    """运行每日报告的便捷函数

    Args:
        config: 配置
        send_telegram: 是否发送到Telegram

    Returns:
        是否成功
    """
    generator = DailyReportGenerator(config)
    return await generator.run(
        send_telegram=send_telegram,
        telegram_bot_token=config.telegram_bot_token,
        telegram_chat_id=config.telegram_chat_id,
    )

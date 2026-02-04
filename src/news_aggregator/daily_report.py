"""每日新闻报告生成器

功能：
1. 抓取所有新闻源
2. 使用 DeepSeek 整理分析
3. 处理被审查的内容（单独保存）
4. 生成邮件报告
5. 生成Telegram报告
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

from openai import OpenAI

from .config import Config
from .sources import NEWS_SOURCES
from .fetcher import NewsFetcher, NewsItem
from .bypass import PaywallBypass
from .email_sender import EmailSender
from .telegram_sender import TelegramSender
from .data_classes import ArticleResult, AnalysisConfig, DailyAnalysisSummary
from .article_analyzer import PerArticleAnalyzer
from .jsonl_writer import JSONLWriter
from .file_cleaner import FileCleaner

logger = logging.getLogger(__name__)


@dataclass
class PerArticleAnalysisResult:
    """逐篇分析结果"""
    success: bool
    results: list[ArticleResult] = None
    summary: Optional[str] = None
    censored_count: int = 0
    error_count: int = 0
    raw_news: Optional[list] = None
    stats: Optional[dict] = None


class DailyReportGenerator:
    """每日报告生成器"""

    def __init__(self, config: Config, per_article_mode: bool = False):
        self.config = config
        self.per_article_mode = per_article_mode
        self.output_dir = config.output_dir

        if per_article_mode:
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
        else:
            # 传统批量模式配置
            self.client = OpenAI(
                api_key=config.openai_api_key,
                base_url=config.openai_base_url,
            )
            self.model = config.openai_model
            self.censored_dir = self.output_dir / "censored"
            self.censored_dir.mkdir(parents=True, exist_ok=True)

    def _is_censored_response(self, response: str) -> bool:
        """检测是否是审查拒绝的回复"""
        if not self.per_article_mode:
            CENSORSHIP_INDICATORS = [
                "作为一个人工智能语言模型，我还没学习如何回答这个问题，您可以向我问一些其它的问题，我会尽力帮您解决的。",
            ]
            response_lower = response.lower()
            for indicator in CENSORSHIP_INDICATORS:
                if indicator.lower() in response_lower:
                    return True
        return False

    def _call_llm(self, prompt: str, max_retries: int = 2) -> tuple[str, bool]:
        """调用 LLM，返回 (响应, 是否被审查)（仅用于批量模式）"""
        if self.per_article_mode:
            # 逐篇分析模式下不直接调用LLM
            return "逐篇分析模式", False

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "你是一个专业的新闻分析师，帮助用户整理和分析每日新闻。"
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=4000,
                )
                content = response.choices[0].message.content

                if self._is_censored_response(content):
                    return content, True

                return content, False

            except Exception as e:
                logger.warning(f"LLM 调用失败 (尝试 {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    return f"错误: {e}", False

        return "未知错误", False

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

    def _format_news_for_analysis(self, news_items: list[NewsItem]) -> str:
        """格式化新闻用于分析"""
        lines = []
        for i, item in enumerate(news_items[:50], 1):  # 限制数量
            content = item.full_content or item.summary or ""
            content = content[:500]  # 截断
            lines.append(f"""
{i}. 【{item.source_name}】{item.title}
   时间: {item.published or '未知'}
   摘要: {content}
""")
        return "\n".join(lines)

    def _generate_analysis_prompt(self, news_text: str) -> str:
        """生成分析提示词"""
        return f"""请分析以下今日新闻，并生成一份简洁的每日新闻简报。

要求：
1. 按重要性整理出 5-10 条最值得关注的新闻
2. 对每条新闻给出简短的中文总结（1-2句话）
3. 分析这些新闻背后的趋势和潜在影响
4. 最后给出一些基于这些新闻的思考和建议（可以涉及投资、工作、生活等任何方面）

格式要求：
- 使用简洁的中文
- 重点突出，不要冗余
- 建议部分要具体可行

今日新闻列表：
{news_text}

请生成新闻简报："""

    async def analyze_news(self, news_items: list[NewsItem]) -> PerArticleAnalysisResult:
        """分析新闻（支持逐篇和批量模式）"""
        if not news_items:
            return PerArticleAnalysisResult(success=False)

        if self.per_article_mode:
            # 逐篇分析模式
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

                return PerArticleAnalysisResult(
                    success=True,
                    results=results,
                    censored_count=analysis_stats['censored_articles'],
                    error_count=analysis_stats['error_count'],
                    raw_news=[asdict(n) for n in news_items[:50]],
                    stats=analysis_stats
                )

            except Exception as e:
                logger.error(f"逐篇分析失败: {e}")
                return PerArticleAnalysisResult(
                    success=False,
                    error_count=len(news_items),
                    raw_news=[asdict(n) for n in news_items[:50]],
                )
        else:
            # 传统批量模式
            logger.info(f"开始批量分析 {len(news_items)} 条新闻...")

            # 格式化新闻
            news_text = self._format_news_for_analysis(news_items)

            # 生成提示词
            prompt = self._generate_analysis_prompt(news_text)

            # 调用 LLM
            response, censored = self._call_llm(prompt)

            if censored:
                logger.warning("分析被审查，保存原始新闻...")
                return PerArticleAnalysisResult(
                    success=False,
                    censored_count=len(news_items),
                    error="内容被审查",
                    raw_news=[asdict(n) for n in news_items[:50]]
                )

            return PerArticleAnalysisResult(
                success=True,
                summary=response,
                raw_news=[asdict(n) for n in news_items[:50]]
            )

    def save_censored_content(self, result: PerArticleAnalysisResult, date_str: str):
        """保存被审查的内容"""
        if self.per_article_mode:
            # 逐篇分析模式下，被审查的内容已经在JSONL文件中
            logger.info(f"逐篇分析模式下，被审查内容已保存在JSONL文件中")
            return self.writer.censored_file
        else:
            # 传统批量模式
            filepath = self.censored_dir / f"censored-{date_str}.json"

            data = {
                "date": date_str,
                "reason": result.error if hasattr(result, 'error') else "内容被审查",
                "news_count": len(result.raw_news) if result.raw_news else 0,
                "news": result.raw_news,
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)

            logger.info(f"被审查内容已保存: {filepath}")
            return filepath

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

    def generate_email_html(self, summary: str, date_str: str) -> str:
        """生成邮件 HTML"""
        # 简单的 Markdown 转 HTML
        html_content = summary.replace("\n\n", "</p><p>").replace("\n", "<br>")
        html_content = f"<p>{html_content}</p>"

        # 处理标题
        import re
        html_content = re.sub(r'###\s*(.+?)(<br>|</p>)', r'<h3>\1</h3>', html_content)
        html_content = re.sub(r'##\s*(.+?)(<br>|</p>)', r'<h2>\1</h2>', html_content)
        html_content = re.sub(r'#\s*(.+?)(<br>|</p>)', r'<h1>\1</h1>', html_content)

        # 处理加粗
        html_content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_content)

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1, h2, h3 {{
            color: #1a1a1a;
            margin-top: 24px;
        }}
        h1 {{
            border-bottom: 2px solid #eee;
            padding-bottom: 10px;
        }}
        p {{
            margin: 12px 0;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <h1>📰 每日新闻简报 - {date_str}</h1>
    {html_content}
    <div class="footer">
        <p>本报告由 AI 自动生成，仅供参考。</p>
        <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
</body>
</html>
"""

    async def run(
        self,
        send_email: bool = True,
        send_telegram: bool = False,
        email_sender: Optional[str] = None,
        email_password: Optional[str] = None,
        email_recipient: Optional[str] = None,
        telegram_bot_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
    ) -> bool:
        """运行每日报告生成

        Args:
            send_email: 是否发送邮件
            send_telegram: 是否发送到Telegram
            email_sender: 发件人邮箱
            email_password: 邮箱密码
            email_recipient: 收件人邮箱
            telegram_bot_token: Telegram Bot Token
            telegram_chat_id: Telegram Chat ID

        Returns:
            是否成功
        """
        date_str = datetime.now().strftime("%Y-%m-%d")
        logger.info(f"开始生成 {date_str} 每日报告 (模式: {'逐篇分析' if self.per_article_mode else '批量分析'})...")

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
                if self.per_article_mode:
                    # 逐篇模式下，即使部分失败，如果分析过一些文章也算成功
                    if result.results and len(result.results) > 0:
                        logger.warning(f"逐篇分析部分失败: 成功 {len(result.results)} 篇，失败 {result.error_count} 篇")
                        # 继续处理成功的结果
                    else:
                        logger.error(f"分析完全失败: {result.error_count} 篇全部失败")
                        return False
                else:
                    # 批量模式下，失败则整体失败
                    logger.error(f"分析失败: {result.error}")
                    return False

            # 4. 保存报告
            if self.per_article_mode:
                # 逐篇模式下生成摘要报告
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
            else:
                # 传统批量模式
                self.save_report(result.summary, date_str)

            # 5. 发送邮件
            if send_email and email_sender and email_password and email_recipient:
                sender = EmailSender(email_sender, email_password)
                if self.per_article_mode:
                    # 逐篇分析邮件内容
                    if result.stats:
                        email_content = self._generate_per_article_email_content(result.stats, date_str)
                        email_subject = f"📰 逐篇新闻分析 - {date_str}"
                    else:
                        email_content = f"今日逐篇新闻分析完成，但没有生成统计信息。"
                        email_subject = f"[新闻分析] {date_str} - 完成"
                else:
                    # 传统批量模式邮件内容
                    email_content = self.generate_email_html(result.summary, date_str)
                    email_subject = f"📰 每日新闻简报 - {date_str}"

                success = sender.send(
                    email_recipient,
                    email_subject,
                    email_content,
                    is_html=True if not self.per_article_mode else False,
                )
                if not success:
                    logger.error("邮件发送失败")

            # 6. 发送到Telegram
            if send_telegram and telegram_bot_token and telegram_chat_id:
                try:
                    # 找到生成的报告文件
                    report_files = list(self.output_dir.glob(f"daily-report-{date_str}.*"))
                    if not report_files:
                        # 如果是逐篇分析模式，发送统计信息
                        if self.per_article_mode and result.stats:
                            stats_text = self._format_stats_for_telegram(result.stats, date_str)
                            telegram_sender = TelegramSender(telegram_bot_token, telegram_chat_id)
                            telegram_success = await telegram_sender.send_text(stats_text, lines_per_chunk=20)
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
                            telegram_success = await telegram_sender.send_file_chunks(
                                report_file,
                                lines_per_chunk=15
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

    def _generate_per_article_email_content(self, stats: dict, date_str: str) -> str:
        """生成逐篇分析邮件内容"""
        return f"""今日逐篇新闻分析报告 - {date_str}

统计分析:
• 总文章数: {stats.get('total_articles', 0)}
• 成功分析: {stats.get('analyzed_articles', 0)}
• 被审查: {stats.get('censored_articles', 0)}
• 平均重要性: {stats.get('average_importance', 0):.1f}

类别分布:
{self._format_category_distribution(stats.get('category_distribution', {}))}

详细结果已保存在 JSONL 文件中，可进行后续分析。
"""


async def run_daily_report(
    config: Config,
    per_article_mode: bool = False,
    send_telegram: bool = False,
) -> bool:
    """运行每日报告的便捷函数

    Args:
        config: 配置
        per_article_mode: 是否启用逐篇分析模式
        send_telegram: 是否发送到Telegram

    Returns:
        是否成功
    """
    generator = DailyReportGenerator(config, per_article_mode=per_article_mode)
    return await generator.run(
        send_email=True,
        send_telegram=send_telegram,
        email_sender=config.email_sender,
        email_password=config.email_password,
        email_recipient=config.email_recipient,
        telegram_bot_token=config.telegram_bot_token,
        telegram_chat_id=config.telegram_chat_id,
    )

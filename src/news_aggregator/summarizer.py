"""摘要生成模块"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .analyzer import Analysis, AnalyzedNews
from .sources import Category
from .config import Config

logger = logging.getLogger(__name__)


# 类别显示顺序
CATEGORY_ORDER = [
    Category.POLITICS,
    Category.CHINA,
    Category.ECONOMY,
    Category.TECHNOLOGY,
    Category.SOCIETY,
    Category.OPINION,
    Category.OTHER,
]

# 类别图标（可选）
CATEGORY_ICONS = {
    Category.POLITICS: "🌍",
    Category.CHINA: "🇨🇳",
    Category.ECONOMY: "💰",
    Category.TECHNOLOGY: "💻",
    Category.SOCIETY: "👥",
    Category.OPINION: "💭",
    Category.OTHER: "📰",
}


class NewsSummarizer:
    """摘要生成器"""

    def __init__(self, config: Config):
        self.config = config
        self.output_dir = config.output_dir

    def _format_news_item(
        self, analyzed: AnalyzedNews, index: int, show_details: bool = True
    ) -> str:
        """格式化单条新闻"""
        item = analyzed.item
        lines = [f"### {index}. {item.title}"]

        # 元信息
        meta_parts = [f"**来源**: {item.source_name}"]
        if item.published:
            meta_parts.append(f"**时间**: {item.published.strftime('%Y-%m-%d %H:%M')}")
        lines.append(" | ".join(meta_parts))

        # 摘要
        if analyzed.chinese_summary:
            lines.append(f"\n{analyzed.chinese_summary}")
        elif item.summary:
            lines.append(f"\n{item.summary[:200]}...")

        # 关键点
        if show_details and analyzed.key_points:
            lines.append("\n**关键点**:")
            for point in analyzed.key_points[:5]:
                lines.append(f"- {point}")

        # 原文链接
        lines.append(f"\n[阅读原文]({item.link})")

        return "\n".join(lines)

    def _format_top_stories(self, analysis: Analysis) -> str:
        """格式化头条新闻"""
        if not analysis.top_stories:
            return ""

        lines = ["## 📌 今日头条\n"]

        for i, analyzed in enumerate(analysis.top_stories[:5], 1):
            lines.append(self._format_news_item(analyzed, i, show_details=True))
            lines.append("\n---\n")

        return "\n".join(lines)

    def _format_category(
        self, category: Category, items: list[AnalyzedNews], max_items: int = 10
    ) -> str:
        """格式化分类新闻"""
        if not items:
            return ""

        # 按重要性排序
        sorted_items = sorted(items, key=lambda x: x.importance, reverse=True)

        icon = CATEGORY_ICONS.get(category, "📰")
        lines = [f"## {icon} {category.value}\n"]

        for i, analyzed in enumerate(sorted_items[:max_items], 1):
            lines.append(self._format_news_item(analyzed, i, show_details=False))
            lines.append("")

        return "\n".join(lines)

    def generate_daily_summary(
        self,
        analysis: Analysis,
        date: Optional[datetime] = None,
        include_top_stories: bool = True,
    ) -> str:
        """生成每日摘要"""
        if date is None:
            date = datetime.now()

        date_str = date.strftime("%Y-%m-%d")

        lines = [
            f"# 每日新闻摘要 - {date_str}",
            "",
            f"> 本报告自动生成于 {date.strftime('%Y-%m-%d %H:%M')}",
            f"> 共聚合 {analysis.total_count} 条新闻",
            "",
        ]

        # 头条新闻
        if include_top_stories and analysis.top_stories:
            lines.append(self._format_top_stories(analysis))
            lines.append("")

        # 按类别展示
        for category in CATEGORY_ORDER:
            if category in analysis.news_by_category:
                items = analysis.news_by_category[category]
                if items:
                    lines.append(self._format_category(category, items))
                    lines.append("")

        # 页脚
        lines.extend(
            [
                "---",
                "",
                "*由 AI 自动生成，仅供参考。新闻来源包括 BBC、CNN、NYTimes、Guardian 等主流媒体。*",
            ]
        )

        return "\n".join(lines)

    def save_markdown(
        self, summary: str, date: Optional[datetime] = None
    ) -> Path:
        """保存摘要到 Markdown 文件"""
        if date is None:
            date = datetime.now()

        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 文件名格式：news-summary-2026-02-04.md
        filename = f"news-summary-{date.strftime('%Y-%m-%d')}.md"
        filepath = self.output_dir / filename

        filepath.write_text(summary, encoding="utf-8")
        logger.info(f"摘要已保存至: {filepath}")

        return filepath

    def generate_and_save(
        self,
        analysis: Analysis,
        date: Optional[datetime] = None,
    ) -> Path:
        """生成并保存摘要"""
        summary = self.generate_daily_summary(analysis, date)
        return self.save_markdown(summary, date)


class QuickSummarizer:
    """快速摘要生成器（不使用 LLM）"""

    def __init__(self, config: Config):
        self.config = config
        self.output_dir = config.output_dir

    def generate_quick_summary(
        self,
        items: list,
        date: Optional[datetime] = None,
    ) -> str:
        """生成快速摘要（不经过 LLM 分析）"""
        if date is None:
            date = datetime.now()

        date_str = date.strftime("%Y-%m-%d")

        lines = [
            f"# 新闻聚合 - {date_str}",
            "",
            f"> 生成时间: {date.strftime('%Y-%m-%d %H:%M')}",
            f"> 共收集 {len(items)} 条新闻",
            "",
        ]

        # 按类别分组
        by_category: dict[Category, list] = {}
        for item in items:
            if item.category not in by_category:
                by_category[item.category] = []
            by_category[item.category].append(item)

        # 按类别输出
        for category in CATEGORY_ORDER:
            if category not in by_category:
                continue

            cat_items = by_category[category]
            icon = CATEGORY_ICONS.get(category, "📰")
            lines.append(f"## {icon} {category.value}")
            lines.append("")

            for i, item in enumerate(cat_items[:15], 1):
                lines.append(f"### {i}. {item.title}")
                lines.append(f"**来源**: {item.source_name}")
                if item.summary:
                    lines.append(f"\n{item.summary[:200]}...")
                lines.append(f"\n[阅读原文]({item.link})")
                lines.append("")

        lines.extend(
            [
                "---",
                "",
                "*自动聚合，未经 AI 分析*",
            ]
        )

        return "\n".join(lines)

    def save_markdown(
        self, summary: str, date: Optional[datetime] = None
    ) -> Path:
        """保存摘要"""
        if date is None:
            date = datetime.now()

        self.output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"news-quick-{date.strftime('%Y-%m-%d')}.md"
        filepath = self.output_dir / filename

        filepath.write_text(summary, encoding="utf-8")
        logger.info(f"快速摘要已保存至: {filepath}")

        return filepath

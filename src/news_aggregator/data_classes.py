"""数据类模块，包含新的数据类定义"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional
from pathlib import Path

from .fetcher import NewsItem


@dataclass
class ArticleResult:
    """单篇文章分析结果"""

    id: str
    title: str
    source_name: str
    summary: Optional[str] = None
    censored: bool = False
    censored_reason: Optional[str] = None
    importance: int = 5  # 1-10
    category: Optional[str] = None
    key_points: Optional[list[str]] = None
    sentiment: Optional[str] = None  # positive/negative/neutral
    analysis_time: Optional[str] = None
    original_item: Optional[NewsItem] = None

    def __post_init__(self):
        if self.analysis_time is None:
            self.analysis_time = datetime.now().isoformat()
        if self.key_points is None:
            self.key_points = []

    def to_dict(self) -> dict:
        """转换为字典格式，用于 JSON 序列化"""
        data = {
            "id": self.id,
            "title": self.title,
            "source_name": self.source_name,
            "summary": self.summary,
            "censored": self.censored,
        }
        # 添加发布时间（直接从original_item提取）
        if self.original_item and self.original_item.published:
            data["published"] = self.original_item.published.isoformat()
        else:
            data["published"] = None

        # 如果需要，保留审查原因
        if self.censored and self.censored_reason:
            data["censored_reason"] = self.censored_reason

        return data

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class DailyAnalysisSummary:
    """每日分析汇总"""

    date: str
    total_articles: int
    analyzed_articles: int
    censored_articles: int
    average_importance: float
    top_categories: dict[str, int]
    jsonl_file: Optional[Path] = None
    markdown_file: Optional[Path] = None
    censored_file: Optional[Path] = None

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "date": self.date,
            "total_articles": self.total_articles,
            "analyzed_articles": self.analyzed_articles,
            "censored_articles": self.censored_articles,
            "average_importance": self.average_importance,
            "top_categories": self.top_categories,
            "jsonl_file": str(self.jsonl_file) if self.jsonl_file else None,
            "markdown_file": str(self.markdown_file) if self.markdown_file else None,
            "censored_file": str(self.censored_file) if self.censored_file else None,
        }


@dataclass
class AnalysisConfig:
    """分析配置"""

    max_concurrent: int = 5
    max_retries: int = 2
    timeout_seconds: int = 30
    keep_days: int = 7
    enable_auto_clean: bool = True
    analysis_mode: str = "per_article"  # per_article 或 batch

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return asdict(self)
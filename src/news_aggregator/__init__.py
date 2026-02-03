"""News Aggregator - 新闻聚合与摘要系统"""

from .config import Config
from .sources import NEWS_SOURCES, NewsSource
from .fetcher import NewsFetcher, NewsItem
from .bypass import PaywallBypass
from .analyzer import NewsAnalyzer
from .summarizer import NewsSummarizer
from .scheduler import NewsScheduler

__version__ = "1.0.0"
__all__ = [
    "Config",
    "NEWS_SOURCES",
    "NewsSource",
    "NewsFetcher",
    "NewsItem",
    "PaywallBypass",
    "NewsAnalyzer",
    "NewsSummarizer",
    "NewsScheduler",
]

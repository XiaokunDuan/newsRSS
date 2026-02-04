"""RSS 新闻源定义"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Category(Enum):
    """新闻分类"""

    POLITICS = "国际政治"
    ECONOMY = "经济财经"
    TECHNOLOGY = "科技动态"
    SOCIETY = "社会民生"
    CHINA = "中国相关"
    OPINION = "观点评论"
    OTHER = "其他"


class Region(Enum):
    """媒体地区"""

    US = "美国"
    UK = "英国"
    EU = "欧洲"
    ASIA = "亚太"
    CHINA = "中文媒体"


@dataclass
class NewsSource:
    """新闻源定义"""

    name: str
    url: str
    region: Region
    category: Category
    language: str = "en"
    requires_proxy: bool = False
    has_paywall: bool = False
    description: Optional[str] = None


# 美国主流媒体
US_SOURCES = [
    NewsSource(
        name="CNN",
        url="https://rss.cnn.com/rss/edition.rss",
        region=Region.US,
        category=Category.OTHER,
        description="CNN 国际版",
    ),
    NewsSource(
        name="NYTimes 世界",
        url="https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        region=Region.US,
        category=Category.POLITICS,
        has_paywall=True,
    ),
    NewsSource(
        name="Washington Post",
        url="https://feeds.washingtonpost.com/rss/world",
        region=Region.US,
        category=Category.POLITICS,
        has_paywall=True,
    ),
    NewsSource(
        name="AP News",
        url="https://rsshub.app/apnews/topics/apf-topnews",
        region=Region.US,
        category=Category.OTHER,
    ),
    NewsSource(
        name="NPR News",
        url="https://feeds.npr.org/1001/rss.xml",
        region=Region.US,
        category=Category.OTHER,
    ),
    NewsSource(
        name="Wall Street Journal",
        url="https://feeds.a.dj.com/rss/RSSWorldNews.xml",
        region=Region.US,
        category=Category.ECONOMY,
        has_paywall=True,
    ),
    NewsSource(
        name="Bloomberg",
        url="https://feeds.bloomberg.com/politics/news.rss",
        region=Region.US,
        category=Category.ECONOMY,
        has_paywall=True,
    ),
    NewsSource(
        name="Politico",
        url="https://rss.politico.com/politics-news.xml",
        region=Region.US,
        category=Category.POLITICS,
    ),
    NewsSource(
        name="The Atlantic",
        url="https://www.theatlantic.com/feed/all/",
        region=Region.US,
        category=Category.OPINION,
        has_paywall=True,
    ),
]

# 英国媒体
UK_SOURCES = [
    NewsSource(
        name="BBC World",
        url="https://feeds.bbci.co.uk/news/world/rss.xml",
        region=Region.UK,
        category=Category.OTHER,
    ),
    NewsSource(
        name="The Guardian World",
        url="https://www.theguardian.com/world/rss",
        region=Region.UK,
        category=Category.OTHER,
    ),
    NewsSource(
        name="Financial Times",
        url="https://www.ft.com/rss/home",
        region=Region.UK,
        category=Category.ECONOMY,
        has_paywall=True,
    ),
]

# 欧洲媒体
EU_SOURCES = [
    NewsSource(
        name="德国之声 英文",
        url="https://rss.dw.com/rdf/rss-en-all",
        region=Region.EU,
        category=Category.OTHER,
    ),
    NewsSource(
        name="France 24",
        url="https://www.france24.com/en/rss",
        region=Region.EU,
        category=Category.OTHER,
    ),
    NewsSource(
        name="Euronews",
        url="https://www.euronews.com/rss",
        region=Region.EU,
        category=Category.OTHER,
    ),
    NewsSource(
        name="POLITICO Europe",
        url="https://www.politico.eu/feed/",
        region=Region.EU,
        category=Category.POLITICS,
    ),
    NewsSource(
        name="Der Spiegel",
        url="https://www.spiegel.de/international/index.rss",
        region=Region.EU,
        category=Category.OTHER,
    ),
]

# 亚太媒体
ASIA_SOURCES = [
    NewsSource(
        name="NHK World",
        url="https://www3.nhk.or.jp/rss/news/cat0.xml",
        region=Region.ASIA,
        category=Category.OTHER,
        language="ja",
    ),
    NewsSource(
        name="日经亚洲",
        url="https://asia.nikkei.com/rss/feed/nar",
        region=Region.ASIA,
        category=Category.ECONOMY,
        has_paywall=True,
    ),
    NewsSource(
        name="南华早报",
        url="https://www.scmp.com/rss/91/feed",
        region=Region.ASIA,
        category=Category.CHINA,
        has_paywall=True,
    ),
    NewsSource(
        name="联合早报",
        url="https://rsshub.app/zaobao/realtime/china",
        region=Region.ASIA,
        category=Category.CHINA,
        language="zh",
    ),
    NewsSource(
        name="ABC Australia",
        url="https://www.abc.net.au/news/feed/1948/rss.xml",
        region=Region.ASIA,
        category=Category.OTHER,
    ),
    NewsSource(
        name="Channel NewsAsia",
        url="https://www.channelnewsasia.com/rssfeeds/8395986",
        region=Region.ASIA,
        category=Category.OTHER,
    ),
]

# 中文独立媒体 (被墙)
CHINA_SOURCES = [
    NewsSource(
        name="RFI 法广中文",
        url="https://www.rfi.fr/cn/rss",
        region=Region.CHINA,
        category=Category.CHINA,
        language="zh",
        requires_proxy=True,
    ),
    NewsSource(
        name="VOA 美国之音",
        url="https://www.voachinese.com/api/zrqiteuuqu",
        region=Region.CHINA,
        category=Category.CHINA,
        language="zh",
        requires_proxy=True,
    ),
    NewsSource(
        name="RFA 自由亚洲",
        url="https://www.rfa.org/mandarin/RSS",
        region=Region.CHINA,
        category=Category.CHINA,
        language="zh",
        requires_proxy=True,
    ),
]

# 科技媒体
TECH_SOURCES = [
    NewsSource(
        name="TechCrunch",
        url="https://techcrunch.com/feed/",
        region=Region.US,
        category=Category.TECHNOLOGY,
    ),
    NewsSource(
        name="Wired",
        url="https://www.wired.com/feed/rss",
        region=Region.US,
        category=Category.TECHNOLOGY,
        has_paywall=True,
    ),
    NewsSource(
        name="Ars Technica",
        url="https://feeds.arstechnica.com/arstechnica/index",
        region=Region.US,
        category=Category.TECHNOLOGY,
    ),
    NewsSource(
        name="The Verge",
        url="https://www.theverge.com/rss/index.xml",
        region=Region.US,
        category=Category.TECHNOLOGY,
    ),
    NewsSource(
        name="MIT Technology Review",
        url="https://www.technologyreview.com/feed/",
        region=Region.US,
        category=Category.TECHNOLOGY,
        has_paywall=True,
    ),
]

# 财经媒体
FINANCE_SOURCES = [
    NewsSource(
        name="CNBC",
        url="https://www.cnbc.com/id/100003114/device/rss/rss.html",
        region=Region.US,
        category=Category.ECONOMY,
    ),
    NewsSource(
        name="MarketWatch",
        url="https://feeds.marketwatch.com/marketwatch/topstories/",
        region=Region.US,
        category=Category.ECONOMY,
    ),
    NewsSource(
        name="Yahoo Finance",
        url="https://finance.yahoo.com/news/rss",
        region=Region.US,
        category=Category.ECONOMY,
    ),
]

# 所有新闻源
NEWS_SOURCES: list[NewsSource] = (
    US_SOURCES
    + UK_SOURCES
    + EU_SOURCES
    + ASIA_SOURCES
    + CHINA_SOURCES
    + TECH_SOURCES
    + FINANCE_SOURCES
)


def get_sources_by_category(category: Category) -> list[NewsSource]:
    """按分类获取新闻源"""
    return [s for s in NEWS_SOURCES if s.category == category]


def get_sources_by_region(region: Region) -> list[NewsSource]:
    """按地区获取新闻源"""
    return [s for s in NEWS_SOURCES if s.region == region]


def get_sources_requiring_proxy() -> list[NewsSource]:
    """获取需要代理的新闻源"""
    return [s for s in NEWS_SOURCES if s.requires_proxy]


def get_sources_with_paywall() -> list[NewsSource]:
    """获取有付费墙的新闻源"""
    return [s for s in NEWS_SOURCES if s.has_paywall]

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
        url="http://rss.cnn.com/rss/edition.rss",  # 使用 HTTP 避免 SSL 问题
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
        url="https://news.google.com/rss/search?q=site:apnews.com&hl=en-US&gl=US&ceid=US:en",  # Google News AP
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
    # 已删除：The Atlantic - 过于知识分子化，实用性不强
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
        url="http://www.theguardian.com/world/rss",  # HTTP 避免 SSL 问题
        region=Region.UK,
        category=Category.OTHER,
    ),
    NewsSource(
        name="Financial Times",
        url="https://www.ft.com/news-feed?format=rss",  # FT 官方 RSS Feed
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
    # 联合早报 - RSS 已失效，暂时移除
    # NewsSource(
    #     name="联合早报",
    #     url="...",
    #     region=Region.ASIA,
    #     category=Category.CHINA,
    #     language="zh",
    # ),
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

# 中文独立媒体 (被墙) - 已删除：政治倾向太明显，不适合趋吉避害
# CHINA_SOURCES = []
CHINA_SOURCES = []

# 科技媒体 (精简，只保留最重要的)
TECH_SOURCES = [
    NewsSource(
        name="The Verge",
        url="https://www.theverge.com/rss/index.xml",
        region=Region.US,
        category=Category.TECHNOLOGY,
        description="消费科技视角，关注科技对社会的影响",
    ),
    NewsSource(
        name="MIT Technology Review",
        url="https://www.technologyreview.com/feed/",
        region=Region.US,
        category=Category.TECHNOLOGY,
        has_paywall=True,
        description="前沿科技研究，关注技术突破趋势",
    ),
]

# 新增媒体 (平衡视角，趋吉避害)
ADDITIONAL_SOURCES = [
    # 右派平衡媒体
    NewsSource(
        name="Fox News",
        url="http://feeds.foxnews.com/foxnews/latest",  # HTTP 避免 SSL 问题
        region=Region.US,
        category=Category.POLITICS,
        description="美国最大保守派媒体，提供右派视角平衡",
    ),
    # 经济深度分析
    NewsSource(
        name="The Economist",
        url="http://www.economist.com/the-world-this-week/rss.xml",  # HTTP 避免 SSL 问题
        region=Region.UK,
        category=Category.ECONOMY,
        has_paywall=True,
        description="全球经济政治深度分析，权威经济杂志",
    ),
    # 国际关系权威
    NewsSource(
        name="Foreign Affairs",
        url="https://www.foreignaffairs.com/rss.xml",  # 正确的 RSS 地址
        region=Region.US,
        category=Category.POLITICS,
        has_paywall=True,
        description="国际关系权威期刊，外交政策深度分析",
    ),
    # 财新网 - 无可用公开 RSS，已移除
    # NewsSource(
    #     name="财新网",
    #     url="...",
    #     region=Region.CHINA,
    #     category=Category.ECONOMY,
    #     language="zh",
    #     description="中国财经政策权威报道，关注经济改革",
    # ),
    # 中国官方视角
    NewsSource(
        name="CCTV News",
        url="https://www.cgtn.com/subscribe/rss/section/world.xml",  # CGTN RSS (CCTV 国际频道)
        region=Region.CHINA,
        category=Category.CHINA,
        description="中国官方英文新闻，了解政府立场和宣传重点",
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
    + TECH_SOURCES
    + FINANCE_SOURCES
    + ADDITIONAL_SOURCES
    # 注：已删除 CHINA_SOURCES（政治倾向太明显）
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

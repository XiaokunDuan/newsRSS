"""新闻获取模块"""

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import aiohttp
import feedparser

from .sources import NewsSource, NEWS_SOURCES, Category
from .bypass import PaywallBypass
from .config import Config

logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    """新闻条目"""

    id: str
    title: str
    link: str
    summary: str
    source_name: str
    source_url: str
    category: Category
    language: str
    published: Optional[datetime] = None
    full_content: Optional[str] = None
    has_paywall: bool = False

    @classmethod
    def from_feed_entry(
        cls, entry: dict, source: NewsSource
    ) -> Optional["NewsItem"]:
        """从 feed entry 创建 NewsItem"""
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()

        if not title or not link:
            return None

        # 生成唯一 ID
        item_id = hashlib.md5(f"{link}{title}".encode()).hexdigest()[:16]

        # 获取摘要
        summary = ""
        if "summary" in entry:
            summary = entry["summary"]
        elif "description" in entry:
            summary = entry["description"]

        # 清理 HTML 标签
        if summary:
            import re

            summary = re.sub(r"<[^>]+>", "", summary)
            summary = summary.strip()[:500]

        # 解析发布时间
        published = None
        if "published_parsed" in entry and entry["published_parsed"]:
            try:
                published = datetime(*entry["published_parsed"][:6])
            except Exception:
                pass

        return cls(
            id=item_id,
            title=title,
            link=link,
            summary=summary,
            source_name=source.name,
            source_url=source.url,
            category=source.category,
            language=source.language,
            published=published,
            has_paywall=source.has_paywall,
        )


@dataclass
class FetchResult:
    """获取结果"""

    source: NewsSource
    items: list[NewsItem] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


class NewsFetcher:
    """新闻获取器"""

    def __init__(self, config: Config):
        self.config = config
        self.timeout = aiohttp.ClientTimeout(total=config.fetch_timeout)
        self.bypass = PaywallBypass(
            proxy=config.https_proxy or config.http_proxy,
            timeout=config.fetch_timeout,
        )
        self._seen_ids: set[str] = set()

    def _get_proxy(self, source: NewsSource) -> Optional[str]:
        """获取代理配置"""
        if source.requires_proxy:
            return self.config.https_proxy or self.config.http_proxy
        return None

    async def fetch_source(self, source: NewsSource) -> FetchResult:
        """获取单个源的新闻"""
        try:
            proxy = self._get_proxy(source)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(
                connector=connector, timeout=self.timeout
            ) as session:
                async with session.get(
                    source.url, headers=headers, proxy=proxy
                ) as response:
                    if response.status != 200:
                        return FetchResult(
                            source=source,
                            success=False,
                            error=f"HTTP {response.status}",
                        )

                    content = await response.text()

            # 解析 RSS
            feed = feedparser.parse(content)
            if feed.bozo and not feed.entries:
                return FetchResult(
                    source=source,
                    success=False,
                    error="RSS 解析失败",
                )

            items = []
            for entry in feed.entries:
                item = NewsItem.from_feed_entry(entry, source)
                if item:
                    items.append(item)

            logger.info(f"获取 {source.name}: {len(items)} 条新闻")
            return FetchResult(source=source, items=items)

        except asyncio.TimeoutError:
            return FetchResult(
                source=source,
                success=False,
                error="请求超时",
            )
        except Exception as e:
            return FetchResult(
                source=source,
                success=False,
                error=str(e),
            )

    async def fetch_all_sources(
        self,
        sources: Optional[list[NewsSource]] = None,
        max_concurrent: Optional[int] = None,
    ) -> list[NewsItem]:
        """获取所有源的新闻"""
        if sources is None:
            sources = NEWS_SOURCES

        if max_concurrent is None:
            max_concurrent = self.config.fetch_max_concurrent

        semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_with_semaphore(source: NewsSource) -> FetchResult:
            async with semaphore:
                result = await self.fetch_source(source)
                # 添加重试逻辑
                if not result.success:
                    for retry in range(self.config.fetch_retry_times):
                        logger.warning(
                            f"重试 {source.name} ({retry + 1}/{self.config.fetch_retry_times})"
                        )
                        await asyncio.sleep(1)
                        result = await self.fetch_source(source)
                        if result.success:
                            break
                return result

        # 并发获取
        tasks = [fetch_with_semaphore(source) for source in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 收集结果并去重
        all_items = []
        self._seen_ids.clear()

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"获取失败: {result}")
                continue

            if result.success:
                for item in result.items:
                    if item.id not in self._seen_ids:
                        self._seen_ids.add(item.id)
                        all_items.append(item)
            else:
                logger.warning(f"获取 {result.source.name} 失败: {result.error}")

        # 按时间排序（最新的在前）
        all_items.sort(key=lambda x: x.published or datetime.min, reverse=True)

        logger.info(f"总共获取 {len(all_items)} 条新闻")
        return all_items

    async def fetch_full_content(
        self, items: list[NewsItem], max_items: int = 50
    ) -> list[NewsItem]:
        """获取有付费墙的新闻全文"""
        paywall_items = [item for item in items if item.has_paywall][:max_items]

        if not paywall_items:
            return items

        logger.info(f"尝试获取 {len(paywall_items)} 篇付费文章全文")

        urls = [item.link for item in paywall_items]
        results = await self.bypass.batch_get_articles(urls, max_concurrent=5)

        # 更新新闻条目
        url_to_item = {item.link: item for item in paywall_items}
        for url, bypass_result in results.items():
            if bypass_result.success and url in url_to_item:
                url_to_item[url].full_content = bypass_result.content
                logger.info(f"成功获取全文: {url_to_item[url].title[:30]}...")

        return items

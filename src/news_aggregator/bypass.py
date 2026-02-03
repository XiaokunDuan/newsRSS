"""付费墙绕过模块"""

import asyncio
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, quote

import aiohttp
from bs4 import BeautifulSoup
from readability import Document


@dataclass
class BypassResult:
    """绕过结果"""

    success: bool
    content: Optional[str] = None
    title: Optional[str] = None
    method: Optional[str] = None
    error: Optional[str] = None


# 搜索引擎伪装 Headers
GOOGLEBOT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Referer": "https://www.google.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

BINGBOT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "Referer": "https://www.bing.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# 常规浏览器 Headers (配合 Google Referer)
BROWSER_FROM_GOOGLE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.google.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


@dataclass
class SiteRule:
    """站点特定规则"""

    method: str  # googlebot, bingbot, browser_google, archive, amp
    clear_cookies: bool = True
    use_amp: bool = False
    fallback: Optional[str] = None  # 备用方法


# 站点特定规则
SITE_RULES: dict[str, SiteRule] = {
    # 美国媒体
    "nytimes.com": SiteRule(method="googlebot", fallback="archive"),
    "wsj.com": SiteRule(method="archive", fallback="google_cache"),
    "washingtonpost.com": SiteRule(method="browser_google", use_amp=True),
    "bloomberg.com": SiteRule(method="archive", fallback="google_cache"),
    "theatlantic.com": SiteRule(method="googlebot"),
    "foreignpolicy.com": SiteRule(method="googlebot"),
    "foreignaffairs.com": SiteRule(method="archive"),
    # 英国媒体
    "economist.com": SiteRule(method="googlebot", fallback="archive"),
    "ft.com": SiteRule(method="archive", fallback="google_cache"),
    "telegraph.co.uk": SiteRule(method="googlebot"),
    # 亚太媒体
    "scmp.com": SiteRule(method="googlebot"),
    "asia.nikkei.com": SiteRule(method="googlebot"),
    "theinitium.com": SiteRule(method="archive"),
    # 科技媒体
    "wired.com": SiteRule(method="googlebot"),
    "technologyreview.com": SiteRule(method="googlebot"),
}


class PaywallBypass:
    """付费墙绕过类"""

    def __init__(self, proxy: Optional[str] = None, timeout: int = 30):
        self.proxy = proxy
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    def _get_domain(self, url: str) -> str:
        """提取域名"""
        parsed = urlparse(url)
        domain = parsed.netloc
        # 移除 www. 前缀
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    def _get_site_rule(self, url: str) -> Optional[SiteRule]:
        """获取站点规则"""
        domain = self._get_domain(url)
        # 精确匹配
        if domain in SITE_RULES:
            return SITE_RULES[domain]
        # 子域名匹配
        for rule_domain, rule in SITE_RULES.items():
            if domain.endswith("." + rule_domain) or domain == rule_domain:
                return rule
        return None

    def _get_headers(self, method: str) -> dict:
        """根据方法获取 Headers"""
        if method == "googlebot":
            return GOOGLEBOT_HEADERS.copy()
        elif method == "bingbot":
            return BINGBOT_HEADERS.copy()
        elif method == "browser_google":
            return BROWSER_FROM_GOOGLE_HEADERS.copy()
        return BROWSER_FROM_GOOGLE_HEADERS.copy()

    def _get_amp_url(self, url: str) -> str:
        """获取 AMP 版本 URL"""
        parsed = urlparse(url)
        # 尝试添加 /amp/ 路径
        if "/amp/" not in parsed.path and not parsed.path.endswith("/amp"):
            path = parsed.path.rstrip("/") + "/amp/"
            return f"{parsed.scheme}://{parsed.netloc}{path}"
        return url

    async def _fetch_with_headers(
        self, url: str, headers: dict
    ) -> Optional[tuple[str, str]]:
        """使用指定 headers 获取页面"""
        connector = aiohttp.TCPConnector(ssl=False)
        try:
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=self.timeout,
                cookie_jar=aiohttp.DummyCookieJar(),  # 不保存 cookies
            ) as session:
                async with session.get(
                    url, headers=headers, proxy=self.proxy, allow_redirects=True
                ) as response:
                    if response.status == 200:
                        html = await response.text()
                        return self._extract_content(html)
        except Exception:
            pass
        return None

    def _extract_content(self, html: str) -> Optional[tuple[str, str]]:
        """从 HTML 提取正文内容"""
        try:
            doc = Document(html)
            title = doc.title()
            content = doc.summary()
            # 清理 HTML 标签，保留文本
            soup = BeautifulSoup(content, "lxml")
            text = soup.get_text(separator="\n", strip=True)
            # 清理多余空行
            text = re.sub(r"\n{3,}", "\n\n", text)
            if len(text) > 200:  # 确保有足够内容
                return title, text
        except Exception:
            pass
        return None

    async def _try_archive_today(self, url: str) -> Optional[tuple[str, str]]:
        """尝试从 archive.today 获取"""
        archive_url = f"https://archive.today/newest/{quote(url, safe='')}"
        headers = BROWSER_FROM_GOOGLE_HEADERS.copy()
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(
                connector=connector, timeout=self.timeout
            ) as session:
                async with session.get(
                    archive_url,
                    headers=headers,
                    proxy=self.proxy,
                    allow_redirects=True,
                ) as response:
                    if response.status == 200:
                        html = await response.text()
                        return self._extract_content(html)
        except Exception:
            pass
        return None

    async def _try_archive_org(self, url: str) -> Optional[tuple[str, str]]:
        """尝试从 archive.org 获取"""
        archive_url = f"https://web.archive.org/web/{quote(url, safe='')}"
        headers = BROWSER_FROM_GOOGLE_HEADERS.copy()
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(
                connector=connector, timeout=self.timeout
            ) as session:
                async with session.get(
                    archive_url,
                    headers=headers,
                    proxy=self.proxy,
                    allow_redirects=True,
                ) as response:
                    if response.status == 200:
                        html = await response.text()
                        return self._extract_content(html)
        except Exception:
            pass
        return None

    async def _try_google_cache(self, url: str) -> Optional[tuple[str, str]]:
        """尝试从 Google Cache 获取"""
        cache_url = (
            f"https://webcache.googleusercontent.com/search?q=cache:{quote(url, safe='')}"
        )
        headers = BROWSER_FROM_GOOGLE_HEADERS.copy()
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(
                connector=connector, timeout=self.timeout
            ) as session:
                async with session.get(
                    cache_url, headers=headers, proxy=self.proxy, allow_redirects=True
                ) as response:
                    if response.status == 200:
                        html = await response.text()
                        return self._extract_content(html)
        except Exception:
            pass
        return None

    async def get_full_article(self, url: str) -> BypassResult:
        """获取完整文章内容"""
        rule = self._get_site_rule(url)

        # 如果没有特定规则，使用默认方法
        if not rule:
            rule = SiteRule(method="browser_google")

        methods_to_try = []

        # 如果使用 AMP，先尝试 AMP 版本
        if rule.use_amp:
            methods_to_try.append(("amp", self._get_amp_url(url)))

        # 主要方法
        if rule.method == "archive":
            methods_to_try.append(("archive_today", url))
            methods_to_try.append(("archive_org", url))
        else:
            methods_to_try.append((rule.method, url))

        # 备用方法
        if rule.fallback:
            if rule.fallback == "archive":
                methods_to_try.append(("archive_today", url))
                methods_to_try.append(("archive_org", url))
            elif rule.fallback == "google_cache":
                methods_to_try.append(("google_cache", url))

        # 依次尝试各种方法
        for method, target_url in methods_to_try:
            result = None

            if method in ("googlebot", "bingbot", "browser_google", "amp"):
                headers = self._get_headers(method)
                result = await self._fetch_with_headers(target_url, headers)
            elif method == "archive_today":
                result = await self._try_archive_today(target_url)
            elif method == "archive_org":
                result = await self._try_archive_org(target_url)
            elif method == "google_cache":
                result = await self._try_google_cache(target_url)

            if result:
                title, content = result
                return BypassResult(
                    success=True, content=content, title=title, method=method
                )

        return BypassResult(success=False, error="所有绕过方法均失败")

    async def batch_get_articles(
        self, urls: list[str], max_concurrent: int = 5
    ) -> dict[str, BypassResult]:
        """批量获取文章"""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_with_semaphore(url: str) -> tuple[str, BypassResult]:
            async with semaphore:
                result = await self.get_full_article(url)
                return url, result

        tasks = [fetch_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = {}
        for result in results:
            if isinstance(result, Exception):
                continue
            url, bypass_result = result
            output[url] = bypass_result

        return output

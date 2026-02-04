"""付费墙绕过模块

基于 Bypass Paywalls Clean 扩展的技术，支持多种绕过方法：
1. 真实浏览器 Headers（最有效）
2. JSON-LD 结构化数据提取（SEO 数据）
3. Googlebot User-Agent 伪装
4. 搜索引擎 Referer（Google/Facebook/Twitter）
5. Archive 服务（archive.today/archive.org）
6. Playwright 浏览器 + BPC 扩展（备用方案，用于顽固付费墙）
"""

import asyncio
import json
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


# =============================================================================
# Headers 配置
# =============================================================================

# 真实 Chrome 浏览器 Headers（最有效）
CHROME_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Ch-Ua": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

# 从 Google 搜索来的浏览器
CHROME_FROM_GOOGLE = {
    **CHROME_HEADERS,
    "Referer": "https://www.google.com/",
    "Sec-Fetch-Site": "cross-site",
}

# 从 Facebook 来的浏览器（部分网站对社交媒体流量更宽松）
CHROME_FROM_FACEBOOK = {
    **CHROME_HEADERS,
    "Referer": "https://www.facebook.com/",
    "Sec-Fetch-Site": "cross-site",
}

# 从 Twitter 来的浏览器
CHROME_FROM_TWITTER = {
    **CHROME_HEADERS,
    "Referer": "https://t.co/",
    "Sec-Fetch-Site": "cross-site",
}

# Googlebot（基于 BPC 扩展配置）
GOOGLEBOT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Googlebot Mobile
GOOGLEBOT_MOBILE_HEADERS = {
    "User-Agent": "Chrome/121.0.0.0 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Bingbot
BINGBOT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Facebook Bot（用于预览）
FACEBOOKBOT_HEADERS = {
    "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# =============================================================================
# 站点规则配置（基于 BPC 扩展）
# =============================================================================

@dataclass
class SiteRule:
    """站点特定规则"""
    # 主要方法: chrome, googlebot, bingbot, facebookbot
    method: str = "chrome"
    # 备用方法列表
    fallbacks: tuple = ()
    # 是否优先尝试 JSON-LD 提取
    try_json_ld: bool = True
    # 最小内容长度（用于验证）
    min_content_length: int = 500


# 站点规则（基于 BPC 扩展的实际配置）
SITE_RULES: dict[str, SiteRule] = {
    # === 美国媒体 ===
    "nytimes.com": SiteRule(
        method="chrome",
        fallbacks=("googlebot", "archive"),
        try_json_ld=True,
    ),
    "washingtonpost.com": SiteRule(
        method="googlebot",  # BPC 使用 googlebot
        fallbacks=("chrome_google", "archive"),
        try_json_ld=True,
    ),
    "wsj.com": SiteRule(
        method="chrome",
        fallbacks=("googlebot", "archive"),
        try_json_ld=True,
        min_content_length=300,  # WSJ 返回的内容较短
    ),
    "bloomberg.com": SiteRule(
        method="chrome",  # BPC 不用 googlebot，靠阻止 JS
        fallbacks=("chrome_facebook", "archive"),
        try_json_ld=True,
        min_content_length=300,
    ),
    "theatlantic.com": SiteRule(
        method="chrome",
        fallbacks=("chrome_google",),  # Googlebot 返回 403
        try_json_ld=True,
        min_content_length=500,
    ),
    "foreignaffairs.com": SiteRule(
        method="chrome",
        fallbacks=("archive",),
        try_json_ld=True,
    ),

    # === 英国媒体 ===
    "ft.com": SiteRule(
        method="chrome",
        fallbacks=("archive",),
        try_json_ld=True,
    ),

    # === 亚太媒体 ===
    "scmp.com": SiteRule(
        method="chrome",  # SCMP 有 JSON-LD
        fallbacks=("googlebot",),
        try_json_ld=True,
    ),
    "asia.nikkei.com": SiteRule(
        method="googlebot",
        fallbacks=("chrome",),
        try_json_ld=True,
    ),
    "theinitium.com": SiteRule(
        method="chrome",
        fallbacks=("archive",),
        try_json_ld=True,
    ),

    # === 科技媒体 ===
    "wired.com": SiteRule(
        method="chrome",  # Wired 有 JSON-LD
        fallbacks=("googlebot",),
        try_json_ld=True,
    ),
    "technologyreview.com": SiteRule(
        method="chrome",
        fallbacks=("googlebot",),
        try_json_ld=True,
    ),
}


# =============================================================================
# 内容提取器
# =============================================================================

class ContentExtractor:
    """内容提取器"""

    # 付费墙检测关键词（必须是明确的付费墙提示）
    PAYWALL_INDICATORS = [
        "subscribe now to continue",
        "subscription required",
        "sign in to read the full",
        "create a free account to continue",
        "already a subscriber? sign in",
        "to continue reading, please",
        "unlock this article",
        "this article is for members only",
        "premium content - subscribe",
        "you've reached your limit",
        "free articles remaining",
        "register to continue reading",
    ]

    @staticmethod
    def extract_json_ld(html: str) -> Optional[tuple[str, str]]:
        """从 JSON-LD 结构化数据中提取文章内容

        很多网站为 SEO 目的在页面中嵌入完整文章内容
        """
        soup = BeautifulSoup(html, "lxml")
        scripts = soup.find_all("script", type="application/ld+json")

        for script in scripts:
            if not script.string:
                continue
            try:
                data = json.loads(script.string)

                # 处理数组形式
                items = [data] if isinstance(data, dict) else data

                # 处理 @graph 数组
                if isinstance(data, dict) and "@graph" in data:
                    items = data["@graph"]

                for item in items:
                    if not isinstance(item, dict):
                        continue

                    # 提取 articleBody 或 text
                    body = item.get("articleBody") or item.get("text")
                    headline = item.get("headline", "")

                    if body and len(body) > 300:
                        # 清理内容
                        body = re.sub(r"\s+", " ", body).strip()
                        return headline, body

            except (json.JSONDecodeError, TypeError):
                continue

        return None

    @staticmethod
    def extract_next_data(html: str) -> Optional[tuple[str, str]]:
        """从 Next.js __NEXT_DATA__ 中提取内容"""
        soup = BeautifulSoup(html, "lxml")
        script = soup.find("script", id="__NEXT_DATA__")

        if not script or not script.string:
            return None

        try:
            data = json.loads(script.string)

            # 递归搜索 articleBody 或 content
            def find_content(obj, depth=0):
                if depth > 10:
                    return None
                if isinstance(obj, dict):
                    for key in ["articleBody", "content", "body", "text"]:
                        if key in obj and isinstance(obj[key], str) and len(obj[key]) > 300:
                            title = obj.get("headline", obj.get("title", ""))
                            return title, obj[key]
                    for value in obj.values():
                        result = find_content(value, depth + 1)
                        if result:
                            return result
                elif isinstance(obj, list):
                    for item in obj:
                        result = find_content(item, depth + 1)
                        if result:
                            return result
                return None

            return find_content(data)
        except (json.JSONDecodeError, TypeError):
            return None

    @staticmethod
    def extract_readability(html: str) -> Optional[tuple[str, str]]:
        """使用 Readability 提取内容"""
        try:
            doc = Document(html)
            title = doc.title()
            content = doc.summary()

            soup = BeautifulSoup(content, "lxml")
            text = soup.get_text(separator="\n", strip=True)
            text = re.sub(r"\n{3,}", "\n\n", text)

            if len(text) > 300:
                return title, text
        except Exception:
            pass
        return None

    @classmethod
    def is_paywall_content(cls, text: str) -> bool:
        """检测内容是否是付费墙页面

        如果内容较长（>2000字符），即使有一些付费墙关键词也可能是真实内容
        """
        if not text:
            return True

        text_lower = text.lower()
        # 统计付费墙指标出现次数
        count = sum(1 for ind in cls.PAYWALL_INDICATORS if ind in text_lower)

        # 内容长度阈值：长内容更可能是真实文章
        if len(text) > 2000:
            # 长内容需要更多指标才判定为付费墙
            return count >= 3
        elif len(text) > 1000:
            return count >= 2
        else:
            # 短内容更可能是付费墙提示页
            return count >= 1

    @classmethod
    def extract(cls, html: str, try_json_ld: bool = True) -> Optional[tuple[str, str]]:
        """提取内容，返回 (title, content)"""

        # 方法1: JSON-LD（最可靠，因为是结构化数据）
        if try_json_ld:
            result = cls.extract_json_ld(html)
            if result and not cls.is_paywall_content(result[1]):
                return result

        # 方法2: Next.js 数据
        result = cls.extract_next_data(html)
        if result and not cls.is_paywall_content(result[1]):
            return result

        # 方法3: Readability
        result = cls.extract_readability(html)
        if result and not cls.is_paywall_content(result[1]):
            return result

        return None


# =============================================================================
# 主类
# =============================================================================

class PaywallBypass:
    """付费墙绕过类"""

    def __init__(
        self,
        proxy: Optional[str] = None,
        timeout: int = 30,
        bpc_extension_path: Optional[str] = None,
        use_browser_fallback: bool = True,
    ):
        """
        Args:
            proxy: HTTP 代理
            timeout: 请求超时（秒）
            bpc_extension_path: BPC 扩展路径（用于浏览器备用方案）
            use_browser_fallback: 是否启用浏览器备用方案
        """
        self.proxy = proxy
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.extractor = ContentExtractor()
        self.bpc_extension_path = bpc_extension_path
        self.use_browser_fallback = use_browser_fallback
        self._browser_bypass = None

    def _get_domain(self, url: str) -> str:
        """提取域名"""
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    def _get_site_rule(self, url: str) -> SiteRule:
        """获取站点规则"""
        domain = self._get_domain(url)

        # 精确匹配
        if domain in SITE_RULES:
            return SITE_RULES[domain]

        # 子域名匹配
        for rule_domain, rule in SITE_RULES.items():
            if domain.endswith("." + rule_domain):
                return rule

        # 默认规则
        return SiteRule(method="chrome", fallbacks=("chrome_google",))

    def _get_headers(self, method: str) -> dict:
        """根据方法获取 Headers"""
        headers_map = {
            "chrome": CHROME_HEADERS,
            "chrome_google": CHROME_FROM_GOOGLE,
            "chrome_facebook": CHROME_FROM_FACEBOOK,
            "chrome_twitter": CHROME_FROM_TWITTER,
            "googlebot": GOOGLEBOT_HEADERS,
            "googlebot_mobile": GOOGLEBOT_MOBILE_HEADERS,
            "bingbot": BINGBOT_HEADERS,
            "facebookbot": FACEBOOKBOT_HEADERS,
        }
        return headers_map.get(method, CHROME_HEADERS).copy()

    async def _fetch(self, url: str, headers: dict) -> Optional[str]:
        """获取页面 HTML"""
        try:
            connector = aiohttp.TCPConnector(ssl=False, force_close=True)
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=self.timeout,
                cookie_jar=aiohttp.DummyCookieJar(),
            ) as session:
                async with session.get(
                    url, headers=headers, proxy=self.proxy, allow_redirects=True
                ) as response:
                    if response.status == 200:
                        return await response.text()
        except Exception:
            pass
        return None

    async def _try_archive_today(self, url: str) -> Optional[str]:
        """尝试从 archive.today 获取"""
        archive_url = f"https://archive.today/newest/{quote(url, safe='')}"
        html = await self._fetch(archive_url, CHROME_HEADERS)

        # 验证不是 nginx 默认页面
        if html and "Welcome to nginx" not in html:
            return html
        return None

    async def _try_archive_org(self, url: str) -> Optional[str]:
        """尝试从 archive.org 获取"""
        archive_url = f"https://web.archive.org/web/2/{url}"
        return await self._fetch(archive_url, CHROME_HEADERS)

    async def get_full_article(self, url: str) -> BypassResult:
        """获取完整文章内容"""
        rule = self._get_site_rule(url)

        # 构建方法列表
        methods = [rule.method] + list(rule.fallbacks)

        for method in methods:
            # Archive 服务特殊处理
            if method == "archive":
                # 尝试 archive.today
                html = await self._try_archive_today(url)
                if html:
                    result = self.extractor.extract(html, rule.try_json_ld)
                    if result and len(result[1]) >= rule.min_content_length:
                        return BypassResult(
                            success=True,
                            title=result[0],
                            content=result[1],
                            method="archive.today"
                        )

                # 尝试 archive.org
                html = await self._try_archive_org(url)
                if html:
                    result = self.extractor.extract(html, rule.try_json_ld)
                    if result and len(result[1]) >= rule.min_content_length:
                        return BypassResult(
                            success=True,
                            title=result[0],
                            content=result[1],
                            method="archive.org"
                        )
                continue

            # 常规方法
            headers = self._get_headers(method)
            html = await self._fetch(url, headers)

            if not html:
                continue

            # 提取内容
            result = self.extractor.extract(html, rule.try_json_ld)

            if result:
                title, content = result
                if len(content) >= rule.min_content_length:
                    return BypassResult(
                        success=True,
                        title=title,
                        content=content,
                        method=method
                    )

        # 如果常规方法失败，尝试浏览器备用方案
        if self.use_browser_fallback and self._needs_browser_fallback(url):
            browser_result = await self._try_browser_bypass(url)
            if browser_result and browser_result.success:
                return browser_result

        return BypassResult(success=False, error="所有绕过方法均失败")

    def _needs_browser_fallback(self, url: str) -> bool:
        """检查是否需要浏览器备用方案"""
        browser_sites = ["bloomberg.com", "ft.com", "washingtonpost.com", "economist.com"]
        return any(site in url for site in browser_sites)

    async def _try_browser_bypass(self, url: str) -> Optional[BypassResult]:
        """尝试使用浏览器绕过"""
        try:
            from .bypass_browser import BrowserBypass

            if self._browser_bypass is None:
                self._browser_bypass = BrowserBypass(
                    extension_path=self.bpc_extension_path,
                    timeout=30000,
                )

            result = await self._browser_bypass.get_article(url)

            if result.success:
                return BypassResult(
                    success=True,
                    title=result.title,
                    content=result.content,
                    method="browser+bpc"
                )
        except ImportError:
            pass  # Playwright 未安装
        except Exception:
            pass

        return None

    async def close(self):
        """关闭资源"""
        if self._browser_bypass:
            await self._browser_bypass.close()
            self._browser_bypass = None

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

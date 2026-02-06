"""使用 Playwright 无头浏览器绕过付费墙

当常规 HTTP 方法失败时，使用 Playwright + BPC 扩展作为备用方案。

依赖：
    pip install playwright
    playwright install chromium

BPC 扩展：
    需要下载 Bypass Paywalls Clean 扩展到本地
    https://gitflic.ru/project/magnolia1234/bypass-paywalls-chrome-clean
"""

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from playwright.async_api import async_playwright, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@dataclass
class BrowserBypassResult:
    """浏览器绕过结果"""
    success: bool
    content: Optional[str] = None
    title: Optional[str] = None
    error: Optional[str] = None


# 需要浏览器绕过的站点
BROWSER_BYPASS_SITES = [
    "bloomberg.com",
    "ft.com",
    "washingtonpost.com",
    "economist.com",
    "telegraph.co.uk",
    "zaobao.com.sg",  # 联合早报需要浏览器绕过
    "wsj.com",  # Wall Street Journal
    "nytimes.com",  # New York Times
    "scmp.com",  # 南华早报
    "asia.nikkei.com",  # 日经亚洲
    "technologyreview.com",  # MIT Technology Review
    "foreignaffairs.com",  # Foreign Affairs
]


class BrowserBypass:
    """使用 Playwright + BPC 扩展绕过付费墙"""

    def __init__(
        self,
        extension_path: Optional[str] = None,
        timeout: int = 30000,
        headless: bool = False,  # 扩展需要非无头模式
    ):
        """
        Args:
            extension_path: BPC 扩展路径
            timeout: 页面加载超时（毫秒）
            headless: 是否无头模式（加载扩展时必须为 False）
        """
        self.extension_path = extension_path
        self.timeout = timeout
        self.headless = headless
        self._context: Optional[BrowserContext] = None
        self._playwright = None

    @staticmethod
    def is_available() -> bool:
        """检查 Playwright 是否可用"""
        return PLAYWRIGHT_AVAILABLE

    @staticmethod
    def needs_browser(url: str) -> bool:
        """检查 URL 是否需要浏览器绕过"""
        return any(site in url for site in BROWSER_BYPASS_SITES)

    async def _ensure_context(self):
        """确保浏览器上下文已启动"""
        if self._context is not None:
            return

        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright 未安装，请运行: pip install playwright && playwright install chromium")

        self._playwright = await async_playwright().start()

        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-site-isolation-trials",
        ]

        # 如果有扩展路径，加载扩展（扩展需要非无头模式）
        use_extension = self.extension_path and Path(self.extension_path).exists()
        if use_extension:
            args.extend([
                f"--disable-extensions-except={self.extension_path}",
                f"--load-extension={self.extension_path}",
            ])
            # 扩展需要非无头模式
            actual_headless = False
        else:
            actual_headless = self.headless

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir="/tmp/newsrss_playwright_profile",
            headless=actual_headless,
            args=args,
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            ignore_https_errors=True,
        )

        # 等待扩展加载
        if use_extension:
            await asyncio.sleep(3)

    async def close(self):
        """关闭浏览器"""
        if self._context:
            await self._context.close()
            self._context = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def _extract_content(self, page) -> tuple[str, str]:
        """从页面提取内容"""
        # 提取标题
        title = ""
        try:
            title = await page.title()
        except:
            pass

        # 文章选择器
        selectors = [
            "article",
            "[role='article']",
            ".article-body",
            ".article__body",
            ".article-content",
            ".story-body",
            ".body-content",
            "[data-component='body-content']",
            ".article__content-body",
            "main",
        ]

        for selector in selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    text = await element.inner_text()
                    if text and len(text) > 500:
                        text = re.sub(r'\s+', ' ', text).strip()
                        return title, text
            except:
                continue

        # 备用：清理后获取 body 内容
        try:
            await page.evaluate("""
                document.querySelectorAll('script, style, nav, header, footer, aside, [class*="paywall"], [class*="subscribe"]').forEach(el => el.remove());
            """)
            text = await page.inner_text("body")
            if text:
                text = re.sub(r'\s+', ' ', text).strip()
                return title, text[:10000]
        except:
            pass

        return title, ""

    @staticmethod
    def _is_valid_content(text: str) -> bool:
        """检查内容是否有效（不是付费墙页面）"""
        if not text or len(text) < 300:
            return False

        indicators = [
            "subscribe to unlock",
            "subscription required",
            "sign in to read",
            "unusual activity",
            "robot",
            "captcha",
            "verify you are human",
        ]

        text_lower = text.lower()
        count = sum(1 for ind in indicators if ind in text_lower)
        return count < 2

    async def get_article(self, url: str) -> BrowserBypassResult:
        """获取文章内容"""
        try:
            await self._ensure_context()
        except Exception as e:
            return BrowserBypassResult(success=False, error=str(e))

        page = await self._context.new_page()

        try:
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.timeout
            )

            if not response or response.status >= 400:
                return BrowserBypassResult(
                    success=False,
                    error=f"HTTP {response.status if response else 'N/A'}"
                )

            # 等待页面和扩展处理
            await page.wait_for_timeout(4000)

            title, content = await self._extract_content(page)

            if self._is_valid_content(content):
                return BrowserBypassResult(
                    success=True,
                    title=title,
                    content=content
                )
            else:
                return BrowserBypassResult(
                    success=False,
                    error="内容无效或被付费墙阻止"
                )

        except asyncio.TimeoutError:
            return BrowserBypassResult(success=False, error="页面加载超时")
        except Exception as e:
            return BrowserBypassResult(success=False, error=str(e))
        finally:
            await page.close()

    async def batch_get_articles(
        self,
        urls: list[str],
        max_concurrent: int = 3
    ) -> dict[str, BrowserBypassResult]:
        """批量获取文章"""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_with_semaphore(url: str):
            async with semaphore:
                result = await self.get_article(url)
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


# 便捷函数
async def bypass_with_browser(
    url: str,
    extension_path: Optional[str] = None
) -> BrowserBypassResult:
    """使用浏览器绕过付费墙的便捷函数"""
    bypass = BrowserBypass(extension_path=extension_path)
    try:
        return await bypass.get_article(url)
    finally:
        await bypass.close()

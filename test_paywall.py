#!/usr/bin/env python3
"""完整付费墙绕过测试 - 包含浏览器备用方案"""

import asyncio
import feedparser
import aiohttp
from src.news_aggregator.bypass import PaywallBypass
from src.news_aggregator.sources import NEWS_SOURCES

# BPC 扩展路径
BPC_PATH = "/Users/dxk/Downloads/bypass-paywalls-chrome-clean-master 2"

# 付费墙媒体
PAYWALL_SOURCES = [s for s in NEWS_SOURCES if s.has_paywall and not s.requires_proxy]


async def fetch_rss(url: str) -> str | None:
    """获取 RSS 第一篇文章"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    feed = feedparser.parse(await resp.text())
                    if feed.entries:
                        return feed.entries[0].link
    except:
        pass
    return None


async def test_source(bypass: PaywallBypass, source):
    """测试单个源"""
    print(f"\n{'='*70}")
    print(f"📰 {source.name}")

    article_url = await fetch_rss(source.url)
    if not article_url:
        print("   ❌ RSS 获取失败")
        return source.name, False, "RSS失败", 0

    print(f"   URL: {article_url[:65]}...")

    result = await bypass.get_full_article(article_url)

    if result.success:
        length = len(result.content) if result.content else 0
        print(f"   ✅ 成功 [{result.method}] ({length} 字符)")
        preview = result.content[:100] if result.content else ""
        print(f"   预览: {preview}...")
        return source.name, True, result.method, length
    else:
        print(f"   ❌ 失败: {result.error}")
        return source.name, False, result.error, 0


async def main():
    print("完整付费墙绕过测试")
    print("="*70)
    print(f"测试媒体: {len(PAYWALL_SOURCES)} 个")
    print(f"BPC 扩展: {BPC_PATH}")

    # 初始化（启用浏览器备用方案）
    bypass = PaywallBypass(
        timeout=35,
        bpc_extension_path=BPC_PATH,
        use_browser_fallback=True,
    )

    results = []

    try:
        for source in PAYWALL_SOURCES:
            result = await test_source(bypass, source)
            results.append(result)
            await asyncio.sleep(2)
    finally:
        await bypass.close()

    # 汇总
    print("\n" + "="*70)
    print("测试结果汇总")
    print("="*70)

    success = [(n, m, c) for n, s, m, c in results if s]
    failed = [(n, e) for n, s, e, c in results if not s]

    print(f"\n✅ 成功: {len(success)}/{len(results)}")
    for name, method, chars in success:
        print(f"   - {name}: {method} ({chars} 字符)")

    if failed:
        print(f"\n❌ 失败: {len(failed)}/{len(results)}")
        for name, error in failed:
            print(f"   - {name}: {error}")

    rate = len(success) / len(results) * 100 if results else 0
    print(f"\n📊 成功率: {rate:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())

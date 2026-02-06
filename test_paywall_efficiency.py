#!/usr/bin/env python3
"""付费墙绕过效率对比测试脚本

测试两种方案：
1. 分层策略（HTTP方法优先，失败后回退BPC）
2. 纯BPC方案（直接使用浏览器+BPC扩展）
"""

import asyncio
import time
import statistics
import psutil
import tracemalloc
from dataclasses import dataclass
from typing import List, Dict, Tuple
from datetime import datetime
import json

from src.news_aggregator.bypass import PaywallBypass
from src.news_aggregator.bypass_browser import BrowserBypass


test_urls = [
    "https://www.bloomberg.com/news/articles/2024-01-01/example-article-1",
    "https://www.nytimes.com/2024/01/01/world/example-article-1.html",
    "https://www.ft.com/content/example-article-1",
    "https://www.wsj.com/articles/example-article-1",
    "https://www.economist.com/example-article-1",
]


@dataclass
class TestResult:
    """单个测试结果"""
    url: str
    success: bool
    method_used: str
    response_time_ms: float
    content_length: int = 0
    error: str = ""


@dataclass
class TestSummary:
    """测试结果摘要"""
    test_name: str
    total_tests: int
    success_count: int
    success_rate: float
    avg_response_time_ms: float
    median_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    memory_usage_mb: float
    cpu_usage_percent: float
    results: List[TestResult]


def get_memory_usage() -> float:
    """获取当前进程内存使用量（MB）"""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024


def get_cpu_usage() -> float:
    """获取CPU使用率"""
    return psutil.cpu_percent(interval=0.1)


class TestHarness:
    """测试框架"""

    def __init__(self):
        self.memory_before = 0.0
        self.cpu_before = 0.0

    async def test_layered_strategy(self, urls: List[str]) -> TestSummary:
        """测试分层策略"""
        print("\n=== 测试分层策略（HTTP优先，失败回退BPC） ===")

        self.memory_before = get_memory_usage()
        self.cpu_before = get_cpu_usage()

        bypass = PaywallBypass(
            use_browser_fallback=True,
            bpc_extension_path=None  # 使用默认路径
        )

        results = []
        for url in urls:
            print(f"\n测试: {url}")
            start_time = time.time()

            try:
                result = await bypass.get_full_article(url)
                response_time = (time.time() - start_time) * 1000

                test_result = TestResult(
                    url=url,
                    success=result.success,
                    method_used=result.method or "unknown",
                    response_time_ms=response_time,
                    content_length=len(result.content) if result.content else 0,
                    error=result.error or ""
                )

                print(f"  结果: {'成功' if result.success else '失败'}")
                print(f"  方法: {result.method}")
                print(f"  耗时: {response_time:.1f}ms")
                print(f"  内容长度: {test_result.content_length} 字符")

            except Exception as e:
                response_time = (time.time() - start_time) * 1000
                test_result = TestResult(
                    url=url,
                    success=False,
                    method_used="error",
                    response_time_ms=response_time,
                    error=str(e)
                )
                print(f"  异常: {e}")

            results.append(test_result)

        await bypass.close()

        return self._create_summary("分层策略", results)

    async def test_pure_bpc_strategy(self, urls: List[str]) -> TestSummary:
        """测试纯BPC方案"""
        print("\n=== 测试纯BPC方案（直接浏览器+BPC） ===")

        self.memory_before = get_memory_usage()
        self.cpu_before = get_cpu_usage()

        if not BrowserBypass.is_available():
            print("警告: Playwright 未安装，跳过纯BPC测试")
            results = []
            for url in urls:
                results.append(TestResult(
                    url=url,
                    success=False,
                    method_used="unavailable",
                    response_time_ms=0,
                    error="Playwright not installed"
                ))
            return self._create_summary("纯BPC方案", results)

        bypass = BrowserBypass(
            extension_path=None,  # 使用默认路径
            headless=False  # 扩展需要非无头模式
        )

        results = []
        for url in urls:
            print(f"\n测试: {url}")
            start_time = time.time()

            try:
                result = await bypass.get_article(url)
                response_time = (time.time() - start_time) * 1000

                test_result = TestResult(
                    url=url,
                    success=result.success,
                    method_used="browser+bpc",
                    response_time_ms=response_time,
                    content_length=len(result.content) if result.content else 0,
                    error=result.error or ""
                )

                print(f"  结果: {'成功' if result.success else '失败'}")
                print(f"  方法: 浏览器+BPC")
                print(f"  耗时: {response_time:.1f}ms")
                print(f"  内容长度: {test_result.content_length} 字符")

            except Exception as e:
                response_time = (time.time() - start_time) * 1000
                test_result = TestResult(
                    url=url,
                    success=False,
                    method_used="error",
                    response_time_ms=response_time,
                    error=str(e)
                )
                print(f"  异常: {e}")

            results.append(test_result)

        await bypass.close()

        return self._create_summary("纯BPC方案", results)

    async def test_modified_bypass(self, urls: List[str]) -> TestSummary:
        """测试修改后的分层策略（直接使用浏览器绕过）"""
        print("\n=== 测试修改后的分层策略（直接浏览器绕过） ===")

        self.memory_before = get_memory_usage()
        self.cpu_before = get_cpu_usage()

        # 创建自定义的 PaywallBypass，修改 _needs_browser_fallback 方法
        # 使其始终返回 True，强制使用浏览器绕过
        from src.news_aggregator.bypass import PaywallBypass

        class ModifiedPaywallBypass(PaywallBypass):
            def _needs_browser_fallback(self, url: str) -> bool:
                # 修改为始终返回 True，强制使用浏览器回退
                return True

            async def get_full_article(self, url: str):
                # 修改方法，跳过所有 HTTP 尝试，直接使用浏览器
                if not self.use_browser_fallback:
                    return await super().get_full_article(url)

                # 直接调用浏览器绕过
                browser_result = await self._try_browser_bypass(url)
                if browser_result and browser_result.success:
                    return browser_result

                # 如果浏览器绕过失败，再尝试 HTTP 方法
                rule = self._get_site_rule(url)
                methods = [rule.method] + list(rule.fallbacks)

                for method in methods:
                    if method == "archive":
                        continue

                    headers = self._get_headers(method)
                    html = await self._fetch(url, headers)

                    if not html:
                        continue

                    result = self.extractor.extract(html, rule.try_json_ld)
                    if result:
                        title, content = result
                        if len(content) >= rule.min_content_length:
                            return super()._create_result(
                                success=True,
                                title=title,
                                content=content,
                                method=method
                            )

                return super()._create_result(
                    success=False,
                    error="所有绕过方法均失败"
                )

        bypass = ModifiedPaywallBypass(
            use_browser_fallback=True,
            bpc_extension_path=None
        )

        results = []
        for url in urls:
            print(f"\n测试: {url}")
            start_time = time.time()

            try:
                result = await bypass.get_full_article(url)
                response_time = (time.time() - start_time) * 1000

                test_result = TestResult(
                    url=url,
                    success=result.success,
                    method_used=result.method or "unknown",
                    response_time_ms=response_time,
                    content_length=len(result.content) if result.content else 0,
                    error=result.error or ""
                )

                print(f"  结果: {'成功' if result.success else '失败'}")
                print(f"  方法: {result.method}")
                print(f"  耗时: {response_time:.1f}ms")
                print(f"  内容长度: {test_result.content_length} 字符")

            except Exception as e:
                response_time = (time.time() - start_time) * 1000
                test_result = TestResult(
                    url=url,
                    success=False,
                    method_used="error",
                    response_time_ms=response_time,
                    error=str(e)
                )
                print(f"  异常: {e}")

            results.append(test_result)

        await bypass.close()

        return self._create_summary("修改后的分层策略", results)

    def _create_summary(self, test_name: str, results: List[TestResult]) -> TestSummary:
        """创建测试摘要"""
        success_results = [r for r in results if r.success]
        response_times = [r.response_time_ms for r in success_results]

        memory_after = get_memory_usage()
        cpu_after = get_cpu_usage()

        summary = TestSummary(
            test_name=test_name,
            total_tests=len(results),
            success_count=len(success_results),
            success_rate=len(success_results) / len(results) if results else 0,
            avg_response_time_ms=statistics.mean(response_times) if response_times else 0,
            median_response_time_ms=statistics.median(response_times) if response_times else 0,
            min_response_time_ms=min(response_times) if response_times else 0,
            max_response_time_ms=max(response_times) if response_times else 0,
            memory_usage_mb=memory_after - self.memory_before,
            cpu_usage_percent=cpu_after - self.cpu_before,
            results=results
        )

        return summary

    def print_summary(self, summary: TestSummary):
        """打印测试摘要"""
        print(f"\n{'='*60}")
        print(f"测试名称: {summary.test_name}")
        print(f"测试总数: {summary.total_tests}")
        print(f"成功数量: {summary.success_count}")
        print(f"成功率: {summary.success_rate:.1%}")
        print(f"平均响应时间: {summary.avg_response_time_ms:.1f}ms")
        print(f"中位响应时间: {summary.median_response_time_ms:.1f}ms")
        print(f"最小响应时间: {summary.min_response_time_ms:.1f}ms")
        print(f"最大响应时间: {summary.max_response_time_ms:.1f}ms")
        print(f"内存使用增量: {summary.memory_usage_mb:.1f} MB")
        print(f"CPU使用增量: {summary.cpu_usage_percent:.1f}%")
        print(f"{'='*60}")

        # 详细结果
        print("\n详细结果:")
        for result in summary.results:
            status = "✓" if result.success else "✗"
            print(f"  {status} {result.url}")
            print(f"    方法: {result.method_used}")
            print(f"    耗时: {result.response_time_ms:.1f}ms")
            print(f"    内容长度: {result.content_length} 字符")
            if result.error:
                print(f"    错误: {result.error}")


def compare_strategies(summary1: TestSummary, summary2: TestSummary):
    """比较两种策略"""
    print(f"\n{'='*60}")
    print("策略对比:")
    print(f"{'='*60}")

    print(f"\n成功率对比:")
    print(f"  {summary1.test_name}: {summary1.success_rate:.1%}")
    print(f"  {summary2.test_name}: {summary2.success_rate:.1%}")

    improvement = (summary2.success_rate - summary1.success_rate) / summary1.success_rate if summary1.success_rate > 0 else 0
    print(f"  改进: {improvement:+.1%}")

    print(f"\n响应时间对比:")
    print(f"  {summary1.test_name}: {summary1.avg_response_time_ms:.1f}ms (中位: {summary1.median_response_time_ms:.1f}ms)")
    print(f"  {summary2.test_name}: {summary2.avg_response_time_ms:.1f}ms (中位: {summary2.median_response_time_ms:.1f}ms)")

    time_diff = summary2.avg_response_time_ms - summary1.avg_response_time_ms
    time_pct = time_diff / summary1.avg_response_time_ms if summary1.avg_response_time_ms > 0 else 0
    print(f"  差异: {time_diff:+.1f}ms ({time_pct:+.1%})")

    print(f"\n资源消耗对比:")
    print(f"  {summary1.test_name}: 内存 {summary1.memory_usage_mb:.1f} MB, CPU {summary1.cpu_usage_percent:.1f}%")
    print(f"  {summary2.test_name}: 内存 {summary2.memory_usage_mb:.1f} MB, CPU {summary2.cpu_usage_percent:.1f}%")

    mem_diff = summary2.memory_usage_mb - summary1.memory_usage_mb
    cpu_diff = summary2.cpu_usage_percent - summary1.cpu_usage_percent
    print(f"  内存差异: {mem_diff:+.1f} MB")
    print(f"  CPU差异: {cpu_diff:+.1f}%")

    print(f"\n建议:")
    if summary2.success_rate > summary1.success_rate:
        print(f"  • {summary2.test_name} 成功率更高")
    else:
        print(f"  • {summary1.test_name} 成功率更高")

    if summary2.avg_response_time_ms < summary1.avg_response_time_ms:
        print(f"  • {summary2.test_name} 响应时间更短")
    else:
        print(f"  • {summary1.test_name} 响应时间更短")

    if summary2.memory_usage_mb < summary1.memory_usage_mb:
        print(f"  • {summary2.test_name} 内存使用更少")
    else:
        print(f"  • {summary1.test_name} 内存使用更少")

    print(f"{'='*60}")


async def main():
    """主测试函数"""
    print("付费墙绕过效率对比测试")
    print("=" * 60)

    harness = TestHarness()

    # 测试分层策略
    summary1 = await harness.test_layered_strategy(test_urls)
    harness.print_summary(summary1)

    # 等待一段时间，让系统恢复
    print("\n等待10秒让系统恢复...")
    await asyncio.sleep(10)

    # 测试纯BPC方案
    summary2 = await harness.test_pure_bpc_strategy(test_urls)
    harness.print_summary(summary2)

    # 等待一段时间，让系统恢复
    print("\n等待10秒让系统恢复...")
    await asyncio.sleep(10)

    # 测试修改后的策略
    summary3 = await harness.test_modified_bypass(test_urls)
    harness.print_summary(summary3)

    # 对比分析
    print("\n对比分析:")
    compare_strategies(summary1, summary2)  # 原始分层 vs 纯BPC
    compare_strategies(summary1, summary3)  # 原始分层 vs 修改后分层

    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"paywall_efficiency_results_{timestamp}.json"

    results = {
        "test_urls": test_urls,
        "timestamp": timestamp,
        "summaries": {
            "layered_strategy": summary1.__dict__,
            "pure_bpc_strategy": summary2.__dict__,
            "modified_strategy": summary3.__dict__,
        }
    }

    # 移除 results 列表中的对象，只保留字典
    for key in results["summaries"]:
        summary_dict = results["summaries"][key]
        summary_dict["results"] = [r.__dict__ for r in summary_dict["results"]]

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n测试结果已保存到: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
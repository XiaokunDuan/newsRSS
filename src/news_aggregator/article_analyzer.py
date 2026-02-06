"""逐篇新闻分析器

实现每篇新闻单独调用 API 进行分析，避免触发 DeepSeek 风控。
支持并发控制、错误处理和实时进度追踪。
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Union
from dataclasses import asdict

from openai import OpenAI

from .config import Config
from .fetcher import NewsItem
from .data_classes import ArticleResult, AnalysisConfig

logger = logging.getLogger(__name__)


class PerArticleAnalyzer:
    """逐篇新闻分析器"""

    # DeepSeek 审查拒绝的关键词
    CENSORSHIP_INDICATORS = [
        "作为一个人工智能语言模型，我还没学习如何回答这个问题，您可以向我问一些其它的问题，我会尽力帮您解决的。",
    ]

    def __init__(self, config: Config, analysis_config: Optional[AnalysisConfig] = None):
        self.config = config
        self.analysis_config = analysis_config or AnalysisConfig()

        # OpenAI client (for DeepSeek)
        self.client = OpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
        )
        self.model = config.openai_model

        # 进度追踪
        self.processed_count = 0
        self.censored_count = 0
        self.error_count = 0

    def _is_censored_response(self, response: str) -> bool:
        """检测是否是审查拒绝的回复"""
        response_lower = response.lower()
        for indicator in self.CENSORSHIP_INDICATORS:
            if indicator.lower() in response_lower:
                return True
        return False

    def _generate_single_prompt(self, item: NewsItem) -> str:
        """生成单篇文章分析提示词"""
        content = item.full_content or item.summary or ""
        # 截断内容以避免过长提示
        if len(content) > 3000:
            content = content[:3000] + "..."

        return f"""请分析以下新闻并给出简洁的中文摘要（1-2句话）：

标题：{item.title}
来源：{item.source_name}
发布时间：{item.published or '未知'}

内容：{content}

请给出中文摘要："""

    def _generate_detailed_prompt(self, item: NewsItem) -> str:
        """生成详细分析提示词"""
        content = item.full_content or item.summary or ""
        if len(content) > 2000:
            content = content[:2000] + "..."

        return f"""你是一个专业的新闻分析师。请分析以下新闻：

标题：{item.title}
来源：{item.source_name}
发布时间：{item.published or '未知'}

内容：{content}

请以 JSON 格式返回以下分析结果：
1. 中文摘要 (summary): 1-2句话总结核心内容
2. 重要性评分 (importance): 1-10分，10分最重要
3. 类别 (category): 国际政治/经济财经/科技动态/社会民生/中国相关/观点评论/其他
4. 关键点 (key_points): 3-5个关键点
5. 情感倾向 (sentiment): positive/negative/neutral

格式示例：
{{"summary": "摘要内容", "importance": 7, "category": "国际政治", "key_points": ["关键点1", "关键点2"], "sentiment": "neutral"}}

请只返回 JSON，不要有其他内容。"""

    async def _call_llm_with_retry(self, prompt: str) -> tuple[str, bool]:
        """调用 LLM 并带有重试机制，返回 (响应, 是否被审查)"""
        max_retries = self.analysis_config.max_retries

        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "你是一个专业的新闻分析师，帮助用户分析和总结新闻内容。"
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=2000,
                    timeout=self.analysis_config.timeout_seconds,
                )
                content = response.choices[0].message.content

                if self._is_censored_response(content):
                    return content, True

                return content, False

            except Exception as e:
                logger.warning(f"LLM 调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    return f"错误: {e}", False
                # 指数退避重试
                await asyncio.sleep(2 ** attempt)

        return "未知错误", False

    def _parse_json_response(self, response: str) -> Optional[dict]:
        """解析 JSON 响应"""
        if not response:
            return None

        try:
            # 尝试提取 JSON 块
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            return json.loads(response.strip())
        except (json.JSONDecodeError, IndexError) as e:
            logger.warning(f"JSON 解析失败: {e}")
            # 尝试直接解析
            try:
                return json.loads(response.strip())
            except json.JSONDecodeError:
                return None

    async def analyze_article(self, item: NewsItem, detailed: bool = True) -> ArticleResult:
        """分析单篇文章"""
        # 生成提示词
        prompt = self._generate_detailed_prompt(item) if detailed else self._generate_single_prompt(item)

        # 调用 LLM
        response, censored = await self._call_llm_with_retry(prompt)

        # 创建分析结果
        result = ArticleResult(
            id=item.id,
            title=item.title,
            source_name=item.source_name,
            original_item=item,
            censored=censored,
            censored_reason=response if censored else None,
        )

        # 如果不是被审查的，尝试解析详细结果
        if not censored and detailed:
            parsed = self._parse_json_response(response)
            if parsed:
                result.summary = parsed.get("summary")
                result.importance = parsed.get("importance", 5)
                result.category = parsed.get("category")
                result.key_points = parsed.get("key_points", [])
                result.sentiment = parsed.get("sentiment")
            else:
                # 如果解析失败，使用原始响应作为摘要
                result.summary = response[:500]  # 截断
        elif not censored and not detailed:
            # 简单模式下直接使用响应作为摘要
            result.summary = response[:500]  # 截断

        return result

    async def analyze_articles(self, news_items: list[NewsItem], detailed: bool = True) -> list[ArticleResult]:
        """逐篇分析新闻列表"""
        if not news_items:
            logger.warning("没有新闻可分析")
            return []

        logger.info(f"开始逐篇分析 {len(news_items)} 条新闻，并发数: {self.analysis_config.max_concurrent}")

        # 重置进度计数器
        self.processed_count = 0
        self.censored_count = 0
        self.error_count = 0

        # 信号量控制并发数
        semaphore = asyncio.Semaphore(self.analysis_config.max_concurrent)

        async def analyze_with_semaphore(item: NewsItem) -> Union[ArticleResult, Exception]:
            """带信号量的分析函数"""
            async with semaphore:
                try:
                    result = await self.analyze_article(item, detailed)

                    # 更新统计
                    self.processed_count += 1
                    if result.censored:
                        self.censored_count += 1

                    # 进度日志
                    if self.processed_count % 10 == 0 or self.processed_count == len(news_items):
                        logger.info(
                            f"分析进度: {self.processed_count}/{len(news_items)} "
                            f"(审查: {self.censored_count}, 错误: {self.error_count})"
                        )

                    return result

                except Exception as e:
                    self.error_count += 1
                    logger.error(f"分析新闻失败 {item.title[:30]}...: {e}")

                    # 创建失败结果
                    return ArticleResult(
                        id=item.id,
                        title=item.title,
                        source_name=item.source_name,
                        censored=False,
                        summary=None,
                        censored_reason=f"分析错误: {str(e)}",
                    )

        # 创建所有任务
        tasks = [analyze_with_semaphore(item) for item in news_items]

        # 并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.error_count += 1
                logger.error(f"任务异常: {result}")
                # 为异常创建占位结果
                if i < len(news_items):
                    item = news_items[i]
                    processed_results.append(ArticleResult(
                        id=item.id,
                        title=item.title,
                        source_name=item.source_name,
                        censored=False,
                        summary=None,
                        censored_reason=f"任务异常: {str(result)}",
                    ))
            else:
                processed_results.append(result)

        # 最终统计
        total_censored = sum(1 for r in processed_results if r.censored)
        total_analyzed = sum(1 for r in processed_results if r.summary)

        logger.info(
            f"分析完成: 总数 {len(processed_results)}, "
            f"成功分析 {total_analyzed}, "
            f"被审查 {total_censored}, "
            f"错误 {self.error_count}"
        )

        return processed_results

    def get_summary_statistics(self, results: list[ArticleResult]) -> dict:
        """获取分析统计信息"""
        total = len(results)
        censored = sum(1 for r in results if r.censored)
        analyzed = sum(1 for r in results if r.summary)

        # 计算平均重要性
        importance_scores = [r.importance for r in results if r.importance]
        avg_importance = sum(importance_scores) / len(importance_scores) if importance_scores else 0

        # 统计类别分布
        category_counts = {}
        for r in results:
            if r.category:
                category_counts[r.category] = category_counts.get(r.category, 0) + 1

        return {
            "total_articles": total,
            "analyzed_articles": analyzed,
            "censored_articles": censored,
            "error_count": self.error_count,
            "average_importance": round(avg_importance, 2),
            "category_distribution": category_counts,
        }
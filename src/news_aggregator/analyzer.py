"""LLM 分析模块"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from openai import OpenAI

from .config import Config
from .fetcher import NewsItem
from .sources import Category

logger = logging.getLogger(__name__)


@dataclass
class AnalyzedNews:
    """分析后的新闻"""

    item: NewsItem
    key_points: list[str] = field(default_factory=list)
    sentiment: Optional[str] = None  # positive, negative, neutral
    importance: int = 5  # 1-10
    chinese_summary: str = ""


@dataclass
class Analysis:
    """分析结果"""

    news_by_category: dict[Category, list[AnalyzedNews]] = field(default_factory=dict)
    top_stories: list[AnalyzedNews] = field(default_factory=list)
    total_count: int = 0


CATEGORIZE_PROMPT = """你是一个新闻分类专家。请分析以下新闻标题和摘要，将其归类到最合适的类别，并提取关键信息。

新闻列表：
{news_list}

请以 JSON 格式返回结果，格式如下：
{{
    "results": [
        {{
            "id": "新闻ID",
            "category": "类别（国际政治/经济财经/科技动态/社会民生/中国相关/观点评论/其他）",
            "importance": 重要性评分(1-10),
            "key_points": ["关键点1", "关键点2"],
            "chinese_summary": "中文摘要（50字以内）"
        }}
    ]
}}

分类标准：
- 国际政治：国际关系、外交、政治事件、选举、政策
- 经济财经：股市、金融、贸易、经济政策、企业新闻
- 科技动态：科技公司、新技术、AI、互联网
- 社会民生：社会事件、文化、教育、医疗
- 中国相关：涉及中国的新闻
- 观点评论：评论、分析文章
- 其他：不属于以上类别

重要性评分标准：
- 9-10：重大国际事件、影响深远
- 7-8：重要新闻、值得关注
- 5-6：一般新闻
- 3-4：次要新闻
- 1-2：不太重要

请只返回 JSON，不要有其他内容。"""


SUMMARIZE_PROMPT = """你是一个专业的新闻编辑。请为以下新闻生成详细的中文摘要和关键点分析。

新闻信息：
标题：{title}
来源：{source}
原文摘要：{summary}
{full_content_section}

请以 JSON 格式返回：
{{
    "chinese_summary": "详细中文摘要（100-200字）",
    "key_points": ["关键点1", "关键点2", "关键点3"],
    "sentiment": "positive/negative/neutral"
}}

要求：
1. 摘要要准确概括新闻核心内容
2. 关键点要提炼出最重要的信息
3. 如果有全文内容，要充分利用
4. 请只返回 JSON，不要有其他内容"""


class NewsAnalyzer:
    """新闻分析器"""

    def __init__(self, config: Config):
        self.config = config
        self.client = OpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
        )
        self.model = config.openai_model

    def _call_llm(self, prompt: str, max_tokens: int = 4000) -> Optional[str]:
        """调用 LLM"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的新闻分析助手。"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.3,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return None

    def _parse_json(self, text: str) -> Optional[dict]:
        """解析 JSON 响应"""
        if not text:
            return None
        try:
            # 尝试提取 JSON 块
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text.strip())
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            return None

    def categorize_news(
        self, items: list[NewsItem], batch_size: int = 20
    ) -> dict[str, dict]:
        """批量分类新闻"""
        results = {}

        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]

            # 构建新闻列表
            news_list = []
            for item in batch:
                news_list.append(
                    f"ID: {item.id}\n"
                    f"标题: {item.title}\n"
                    f"来源: {item.source_name}\n"
                    f"摘要: {item.summary[:200] if item.summary else '无'}\n"
                )

            prompt = CATEGORIZE_PROMPT.format(news_list="\n---\n".join(news_list))
            response = self._call_llm(prompt)
            parsed = self._parse_json(response)

            if parsed and "results" in parsed:
                for result in parsed["results"]:
                    results[result["id"]] = result

            logger.info(f"分类进度: {min(i + batch_size, len(items))}/{len(items)}")

        return results

    def analyze_single(self, item: NewsItem) -> AnalyzedNews:
        """分析单条新闻"""
        full_content_section = ""
        if item.full_content:
            # 截取前2000字
            content = item.full_content[:2000]
            full_content_section = f"全文内容：\n{content}"

        prompt = SUMMARIZE_PROMPT.format(
            title=item.title,
            source=item.source_name,
            summary=item.summary,
            full_content_section=full_content_section,
        )

        response = self._call_llm(prompt, max_tokens=1000)
        parsed = self._parse_json(response)

        analyzed = AnalyzedNews(item=item)

        if parsed:
            analyzed.chinese_summary = parsed.get("chinese_summary", item.summary)
            analyzed.key_points = parsed.get("key_points", [])
            analyzed.sentiment = parsed.get("sentiment", "neutral")

        return analyzed

    async def analyze_news(
        self, items: list[NewsItem], max_items: int = 100, max_concurrent: int = 10
    ) -> Analysis:
        """分析新闻列表 - 异步并发分析"""
        import asyncio
        from typing import List

        # 限制数量
        items = items[:max_items]

        logger.info(f"开始并发分析 {len(items)} 条新闻，并发数: {max_concurrent}...")

        # 异步分析单个文章
        async def analyze_single_async(item: NewsItem) -> AnalyzedNews:
            analyzed = self.analyze_single(item)  # 每条新闻都深度分析

            # 更新JSONL中的摘要
            try:
                from .jsonl_writer import JSONLWriter
                from pathlib import Path
                jsonl_writer = JSONLWriter(Path("output"), incremental_mode=True)
                jsonl_writer.open()
                jsonl_writer.update_summary(item.id, analyzed.chinese_summary)
                jsonl_writer.close()
            except Exception as e:
                logger.warning(f"更新JSONL摘要失败 {item.id}: {e}")

            # 从单条分析结果中提取重要性评分
            # 基于摘要长度和内容质量估算重要性
            importance = 5  # 默认中等重要性
            summary_length = len(analyzed.chinese_summary) if analyzed.chinese_summary else 0
            key_points_count = len(analyzed.key_points) if analyzed.key_points else 0

            # 重要性评分逻辑
            if summary_length > 150 and key_points_count >= 3:
                importance = 8  # 高质量新闻
            elif summary_length > 100 and key_points_count >= 2:
                importance = 6  # 中等质量
            elif summary_length > 50:
                importance = 4  # 一般新闻
            else:
                importance = 2  # 简短新闻

            analyzed.importance = importance
            return analyzed

        # 并发分析所有新闻
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_with_semaphore(item: NewsItem, index: int) -> AnalyzedNews:
            async with semaphore:
                result = await analyze_single_async(item)
                if (index + 1) % 10 == 0:
                    logger.info(f"分析进度: {index + 1}/{len(items)}")
                return result

        # 创建并发任务
        tasks = [
            analyze_with_semaphore(item, i)
            for i, item in enumerate(items)
        ]

        # 并发执行
        all_analyzed: List[AnalyzedNews] = await asyncio.gather(*tasks)

        # 构建分析结果
        analysis = Analysis(total_count=len(items))

        # 按原始类别组织
        for analyzed in all_analyzed:
            category = analyzed.item.category
            if category not in analysis.news_by_category:
                analysis.news_by_category[category] = []
            analysis.news_by_category[category].append(analyzed)

        # 提取重要新闻（importance >= 7）
        analysis.top_stories = sorted(
            [a for a in all_analyzed if a.importance >= 7],
            key=lambda x: x.importance,
            reverse=True,
        )[:15]  # 增加到15条重要新闻

        logger.info(
            f"分析完成: {len(analysis.news_by_category)} 个类别, "
            f"{len(analysis.top_stories)} 条重要新闻 (并发分析完成)"
        )

        return analysis

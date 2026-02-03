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

    def analyze_news(
        self, items: list[NewsItem], max_items: int = 100
    ) -> Analysis:
        """分析新闻列表"""
        # 限制数量
        items = items[:max_items]

        # 第一步：批量分类
        logger.info(f"开始分类 {len(items)} 条新闻...")
        categorized = self.categorize_news(items)

        # 构建分析结果
        analysis = Analysis(total_count=len(items))

        # 按类别组织
        category_map = {
            "国际政治": Category.POLITICS,
            "经济财经": Category.ECONOMY,
            "科技动态": Category.TECHNOLOGY,
            "社会民生": Category.SOCIETY,
            "中国相关": Category.CHINA,
            "观点评论": Category.OPINION,
            "其他": Category.OTHER,
        }

        for item in items:
            cat_info = categorized.get(item.id, {})

            analyzed = AnalyzedNews(
                item=item,
                key_points=cat_info.get("key_points", []),
                importance=cat_info.get("importance", 5),
                chinese_summary=cat_info.get("chinese_summary", item.summary[:100]),
            )

            # 确定类别
            cat_name = cat_info.get("category", item.category.value)
            category = category_map.get(cat_name, item.category)

            if category not in analysis.news_by_category:
                analysis.news_by_category[category] = []
            analysis.news_by_category[category].append(analyzed)

        # 提取重要新闻（importance >= 8）
        all_analyzed = []
        for cat_items in analysis.news_by_category.values():
            all_analyzed.extend(cat_items)

        analysis.top_stories = sorted(
            [a for a in all_analyzed if a.importance >= 8],
            key=lambda x: x.importance,
            reverse=True,
        )[:10]

        logger.info(
            f"分析完成: {len(analysis.news_by_category)} 个类别, "
            f"{len(analysis.top_stories)} 条重要新闻"
        )

        return analysis

    def enhance_top_stories(self, analysis: Analysis) -> Analysis:
        """增强重要新闻的分析"""
        logger.info(f"增强分析 {len(analysis.top_stories)} 条重要新闻...")

        for i, analyzed in enumerate(analysis.top_stories):
            enhanced = self.analyze_single(analyzed.item)
            # 更新分析结果
            analyzed.chinese_summary = enhanced.chinese_summary
            analyzed.key_points = enhanced.key_points
            analyzed.sentiment = enhanced.sentiment
            logger.info(f"增强进度: {i + 1}/{len(analysis.top_stories)}")

        return analysis

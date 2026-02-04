"""JSONL 写入器模块

实现 JSONL 格式的输出，支持实时写入和批量写入。
每个分析结果保存为单独的一行 JSON 对象。
"""

import json
import logging
import time
import fcntl
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Union, Optional, List, TextIO, Set

from .data_classes import ArticleResult, DailyAnalysisSummary

logger = logging.getLogger(__name__)


class JSONLWriter:
    """JSONL 格式写入器"""

    def __init__(self, output_dir: Union[str, Path], subdir: str = "articles",
                 incremental_mode: bool = True, deduplicate: bool = True):
        """初始化 JSONL 写入器

        Args:
            output_dir: 输出目录
            subdir: 子目录名称，默认 'articles'
            incremental_mode: 是否启用增量模式，失败不会丢失之前的数据
            deduplicate: 是否去重，避免重复写入相同的文章
        """
        self.output_dir = Path(output_dir) / subdir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 今日日期
        self.date_str = datetime.now().strftime("%Y-%m-%d")

        # 文件路径
        self.articles_file = self.output_dir / f"articles-{self.date_str}.jsonl"
        self.censored_file = self.output_dir / f"censored-{self.date_str}.jsonl"
        self.progress_file = self.output_dir / f"progress-{self.date_str}.json"

        # 配置
        self.incremental_mode = incremental_mode
        self.deduplicate = deduplicate

        # 文件句柄缓存
        self._articles_fh: Optional[TextIO] = None
        self._censored_fh: Optional[TextIO] = None
        self._summary_fh: Optional[TextIO] = None
        self._progress_fh: Optional[TextIO] = None

        # 已处理文章缓存（用于去重）
        self._processed_ids: Set[str] = set()
        self._processed_hashes: Set[str] = set()

        # 加载进度（如果是增量模式）
        if incremental_mode:
            self._load_progress()
            self._load_existing_hashes()

    def open(self) -> "JSONLWriter":
        """打开文件句柄（用于实时写入）"""
        # 文章文件
        self._articles_fh = open(self.articles_file, 'a', encoding='utf-8')
        logger.info(f"打开文章文件: {self.articles_file}")

        # 审查文件
        self._censored_fh = open(self.censored_file, 'a', encoding='utf-8')
        logger.info(f"打开审查文件: {self.censored_file}")

        return self

    def _load_progress(self):
        """加载进度信息"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress = json.load(f)
                    self._processed_ids = set(progress.get('processed_ids', []))
                    logger.info(f"加载进度: {len(self._processed_ids)} 个已处理ID")
            except Exception as e:
                logger.warning(f"加载进度文件失败: {e}")
                self._processed_ids = set()

    def _load_existing_hashes(self):
        """加载已存在文章的哈希值（用于去重）"""
        if self.deduplicate:
            # 加载已存在的文章哈希
            existing_articles = self.read_articles()
            for article in existing_articles:
                content_hash = self._generate_content_hash(article)
                self._processed_hashes.add(content_hash)
            logger.info(f"加载 {len(self._processed_hashes)} 个已存在文章哈希")

    def _generate_content_hash(self, data: dict) -> str:
        """生成内容哈希，用于去重"""
        # 基于标题、摘要和内容生成哈希
        key_parts = [
            data.get('title', ''),
            data.get('summary', ''),
            data.get('original_item', {}).get('link', '')
        ]
        content = ''.join(str(part) for part in key_parts)
        return hashlib.md5(content.encode()).hexdigest()

    def _save_progress(self):
        """保存进度信息"""
        if self.incremental_mode:
            try:
                progress_data = {
                    'processed_ids': list(self._processed_ids),
                    'last_updated': datetime.now().isoformat(),
                    'total_processed': len(self._processed_ids)
                }
                with open(self.progress_file, 'w', encoding='utf-8') as f:
                    json.dump(progress_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning(f"保存进度文件失败: {e}")

    def close(self):
        """关闭所有文件句柄"""
        for fh_name in ['_articles_fh', '_censored_fh', '_summary_fh', '_progress_fh']:
            fh = getattr(self, fh_name, None)
            if fh:
                try:
                    fh.close()
                except Exception as e:
                    logger.warning(f"关闭文件句柄 {fh_name} 失败: {e}")
                setattr(self, fh_name, None)

        # 保存进度
        self._save_progress()

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _write_line_with_lock(self, fh: TextIO, data: dict, operation_id: str = ""):
        """安全写入一行 JSONL（带文件锁和重试）"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 获取文件锁（非阻塞）
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    logger.warning(f"文件被占用，等待重试 (操作: {operation_id}, 尝试 {attempt + 1})")
                    time.sleep(0.1 * (attempt + 1))
                    continue

                try:
                    # 写入数据
                    json_line = json.dumps(data, ensure_ascii=False)
                    fh.write(json_line + '\n')
                    fh.flush()  # 实时写入
                    logger.debug(f"成功写入 {operation_id}")
                    return True
                finally:
                    # 释放文件锁
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

            except Exception as e:
                logger.error(f"写入 JSONL 行失败 (尝试 {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    logger.error(f"写入失败: {operation_id}")
                    return False
                time.sleep(0.1 * (attempt + 1))

        return False

    def _write_line(self, fh: TextIO, data: dict, operation_id: str = ""):
        """写入一行 JSONL"""
        return self._write_line_with_lock(fh, data, operation_id)

    def write_article_result(self, result: ArticleResult, check_duplicate: bool = True) -> bool:
        """实时写入单篇文章分析结果，返回是否成功写入

        Args:
            result: 文章分析结果
            check_duplicate: 是否检查重复

        Returns:
            是否成功写入
        """
        if not self._articles_fh:
            self.open()

        try:
            data = result.to_dict()
            article_id = result.id

            # 增量模式：检查是否已处理
            if self.incremental_mode and article_id in self._processed_ids:
                logger.debug(f"文章 {article_id} 已处理，跳过")
                return True  # 已经处理过，视为成功

            # 去重检查
            if check_duplicate and self.deduplicate:
                content_hash = self._generate_content_hash(data)
                if content_hash in self._processed_hashes:
                    logger.debug(f"文章 {article_id} 内容重复，跳过")
                    return True  # 重复内容，视为成功

            operation_id = f"article_{article_id}"

            if result.censored:
                # 被审查的文章写入审查文件
                if self._censored_fh:
                    success = self._write_line(self._censored_fh, data, operation_id + "_censored")
                else:
                    success = False
            else:
                # 正常文章写入文章文件
                success = self._write_line(self._articles_fh, data, operation_id)

            if success:
                # 更新进度
                if self.incremental_mode:
                    self._processed_ids.add(article_id)
                if self.deduplicate:
                    content_hash = self._generate_content_hash(data)
                    self._processed_hashes.add(content_hash)
                logger.debug(f"成功写入文章 {article_id}")
            else:
                logger.warning(f"写入文章 {article_id} 失败")

            return success

        except Exception as e:
            logger.error(f"写入文章结果失败 {result.id}: {e}")
            return False

    def batch_write_results(self, results: List[ArticleResult], atomic: bool = True) -> dict:
        """批量写入分析结果，返回写入统计

        Args:
            results: 文章结果列表
            atomic: 是否原子操作（失败时不会部分写入）

        Returns:
            写入统计
        """
        stats = {
            'total': len(results),
            'articles_written': 0,
            'censored_written': 0,
            'duplicates': 0,
            'already_processed': 0,
            'errors': 0
        }

        if atomic:
            # 原子操作：先收集所有数据，然后一次性写入
            articles_data = []
            censored_data = []
            articles_to_write = []
            censored_to_write = []

            for result in results:
                try:
                    data = result.to_dict()
                    article_id = result.id

                    # 增量模式检查
                    if self.incremental_mode and article_id in self._processed_ids:
                        stats['already_processed'] += 1
                        continue

                    # 去重检查
                    if self.deduplicate:
                        content_hash = self._generate_content_hash(data)
                        if content_hash in self._processed_hashes:
                            stats['duplicates'] += 1
                            continue

                    if result.censored:
                        censored_data.append(data)
                        censored_to_write.append((result, data))
                    else:
                        articles_data.append(data)
                        articles_to_write.append((result, data))

                except Exception as e:
                    logger.error(f"处理文章结果失败 {result.id}: {e}")
                    stats['errors'] += 1

            # 一次性写入（原子操作）
            try:
                # 写入文章文件
                if articles_to_write:
                    with open(self.articles_file, 'a', encoding='utf-8') as f:
                        for result, data in articles_to_write:
                            json_line = json.dumps(data, ensure_ascii=False)
                            f.write(json_line + '\n')
                            # 更新进度
                            if self.incremental_mode:
                                self._processed_ids.add(result.id)
                            if self.deduplicate:
                                content_hash = self._generate_content_hash(data)
                                self._processed_hashes.add(content_hash)
                    stats['articles_written'] = len(articles_to_write)
                    logger.info(f"原子写入 {len(articles_to_write)} 篇正常文章到 {self.articles_file}")

                # 写入审查文件
                if censored_to_write:
                    with open(self.censored_file, 'a', encoding='utf-8') as f:
                        for result, data in censored_to_write:
                            json_line = json.dumps(data, ensure_ascii=False)
                            f.write(json_line + '\n')
                            # 更新进度
                            if self.incremental_mode:
                                self._processed_ids.add(result.id)
                            if self.deduplicate:
                                content_hash = self._generate_content_hash(data)
                                self._processed_hashes.add(content_hash)
                    stats['censored_written'] = len(censored_to_write)
                    logger.info(f"原子写入 {len(censored_to_write)} 篇被审查文章到 {self.censored_file}")

            except Exception as e:
                logger.error(f"原子批量写入失败: {e}")
                stats['errors'] = len(results) - (stats['articles_written'] + stats['censored_written'] +
                                                  stats['duplicates'] + stats['already_processed'])

        else:
            # 非原子操作：逐篇写入
            for result in results:
                try:
                    success = self.write_article_result(result)
                    if success:
                        if result.censored:
                            stats['censored_written'] += 1
                        else:
                            stats['articles_written'] += 1
                except Exception as e:
                    logger.error(f"写入文章 {result.id} 失败: {e}")
                    stats['errors'] += 1

        return stats

    def write_summary(self, summary: DailyAnalysisSummary, incremental: bool = True) -> bool:
        """写入每日分析摘要（单独文件），支持增量更新

        Args:
            summary: 每日分析摘要
            incremental: 是否增量模式（合并现有统计）

        Returns:
            是否成功写入
        """
        summary_file = self.output_dir / f"summary-{self.date_str}.json"

        try:
            summary_data = summary.to_dict()

            if incremental and summary_file.exists():
                # 读取现有摘要
                try:
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)

                    # 合并统计：保留更大的值
                    merged_data = self._merge_summary_stats(existing_data, summary_data)
                    summary_data = merged_data
                    logger.info(f"合并现有摘要统计")
                except Exception as e:
                    logger.warning(f"读取现有摘要失败，将创建新文件: {e}")

            # 写入摘要文件
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, ensure_ascii=False, indent=2)

            logger.info(f"写入摘要文件: {summary_file}")
            return True

        except Exception as e:
            logger.error(f"写入摘要文件失败: {e}")
            return False

    def _merge_summary_stats(self, existing: dict, new: dict) -> dict:
        """合并摘要统计，保留较大的值"""
        merged = existing.copy()

        # 更新数值字段（取最大值）
        numeric_fields = [
            'total_articles', 'analyzed_articles', 'censored_articles',
            'average_importance'
        ]
        for field in numeric_fields:
            if field in new and field in existing:
                if isinstance(new[field], (int, float)):
                    merged[field] = max(existing[field], new[field])

        # 合并类别统计
        if 'top_categories' in new and 'top_categories' in existing:
            merged_categories = existing['top_categories'].copy()
            for category, count in new['top_categories'].items():
                merged_categories[category] = max(
                    merged_categories.get(category, 0),
                    count
                )
            merged['top_categories'] = merged_categories

        # 更新文件路径
        file_fields = ['jsonl_file', 'markdown_file', 'censored_file']
        for field in file_fields:
            if field in new and new[field]:
                merged[field] = new[field]

        # 更新时间戳
        merged['last_updated'] = datetime.now().isoformat()

        return merged

    def get_file_paths(self) -> dict:
        """获取文件路径"""
        return {
            'articles_file': str(self.articles_file),
            'censored_file': str(self.censored_file),
            'summary_file': str(self.output_dir / f"summary-{self.date_str}.json"),
            'progress_file': str(self.progress_file),
        }

    def get_progress_info(self) -> dict:
        """获取进度信息"""
        return {
            'processed_count': len(self._processed_ids),
            'processed_ids': list(self._processed_ids),
            'unique_hashes': len(self._processed_hashes),
            'incremental_mode': self.incremental_mode,
            'deduplicate': self.deduplicate,
            'date': self.date_str
        }

    def read_articles(self, limit: Optional[int] = None) -> List[dict]:
        """读取文章文件内容"""
        articles = []
        try:
            if self.articles_file.exists():
                with open(self.articles_file, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f):
                        if limit and i >= limit:
                            break
                        try:
                            data = json.loads(line.strip())
                            articles.append(data)
                        except json.JSONDecodeError as e:
                            logger.warning(f"JSONL 行解析失败 (行 {i+1}): {e}")
        except Exception as e:
            logger.error(f"读取文章文件失败: {e}")

        return articles

    def read_summary(self) -> Optional[dict]:
        """读取摘要文件内容"""
        summary_file = self.output_dir / f"summary-{self.date_str}.json"
        if summary_file.exists():
            try:
                with open(summary_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"读取摘要文件失败: {e}")
        return None

    def consolidate_files(self) -> dict:
        """合并增量文件，确保数据一致性

        用于在增量运行后合并所有写入的数据
        """
        stats = {
            'total_articles': 0,
            'total_censored': 0,
            'duplicates_removed': 0
        }

        try:
            # 读取所有文章
            all_articles = self.read_articles()
            all_censored = self.read_censored()

            # 去重（基于哈希）
            unique_articles = []
            unique_censored = []
            seen_hashes = set()

            for article in all_articles:
                content_hash = self._generate_content_hash(article)
                if content_hash not in seen_hashes:
                    seen_hashes.add(content_hash)
                    unique_articles.append(article)
                else:
                    stats['duplicates_removed'] += 1

            for censored in all_censored:
                content_hash = self._generate_content_hash(censored)
                if content_hash not in seen_hashes:
                    seen_hashes.add(content_hash)
                    unique_censored.append(censored)
                else:
                    stats['duplicates_removed'] += 1

            # 重新写入去重后的数据
            if unique_articles:
                with open(self.articles_file, 'w', encoding='utf-8') as f:
                    for article in unique_articles:
                        json_line = json.dumps(article, ensure_ascii=False)
                        f.write(json_line + '\n')
                logger.info(f"合并后文章文件: {len(unique_articles)} 篇（移除 {len(all_articles) - len(unique_articles)} 篇重复）")

            if unique_censored:
                with open(self.censored_file, 'w', encoding='utf-8') as f:
                    for censored in unique_censored:
                        json_line = json.dumps(censored, ensure_ascii=False)
                        f.write(json_line + '\n')
                logger.info(f"合并后审查文件: {len(unique_censored)} 篇（移除 {len(all_censored) - len(unique_censored)} 篇重复）")

            stats['total_articles'] = len(unique_articles)
            stats['total_censored'] = len(unique_censored)

            # 更新进度
            if self.incremental_mode:
                # 基于去重后的数据更新ID集合
                self._processed_ids = set()
                self._processed_hashes = set()
                for article in unique_articles + unique_censored:
                    if 'id' in article:
                        self._processed_ids.add(article['id'])
                    content_hash = self._generate_content_hash(article)
                    self._processed_hashes.add(content_hash)
                self._save_progress()

        except Exception as e:
            logger.error(f"合并文件失败: {e}")

        return stats

    def read_censored(self, limit: Optional[int] = None) -> List[dict]:
        """读取审查文件内容"""
        censored = []
        try:
            if self.censored_file.exists():
                with open(self.censored_file, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f):
                        if limit and i >= limit:
                            break
                        try:
                            data = json.loads(line.strip())
                            censored.append(data)
                        except json.JSONDecodeError as e:
                            logger.warning(f"JSONL 行解析失败 (行 {i+1}): {e}")
        except Exception as e:
            logger.error(f"读取审查文件失败: {e}")

        return censored

    def get_file_stats(self) -> dict:
        """获取文件统计信息"""
        stats = {}
        for file_name, file_path in [
            ('articles', self.articles_file),
            ('censored', self.censored_file)
        ]:
            if file_path.exists():
                try:
                    lines = 0
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = sum(1 for _ in f)
                    stats[f'{file_name}_lines'] = lines
                    stats[f'{file_name}_size'] = file_path.stat().st_size
                except Exception as e:
                    logger.warning(f"获取文件 {file_name} 统计失败: {e}")
            else:
                stats[f'{file_name}_lines'] = 0
                stats[f'{file_name}_size'] = 0

        return stats
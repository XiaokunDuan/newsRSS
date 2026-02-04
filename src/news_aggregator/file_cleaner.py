"""文件清理器模块

实现自动清理旧文件，避免磁盘空间耗尽。
支持按文件类型和保留天数进行清理。
"""

import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Union

logger = logging.getLogger(__name__)


class FileCleaner:
    """文件清理器"""

    def __init__(self,
                 output_dir: Union[str, Path],
                 keep_days: int = 7,
                 enable_auto_clean: bool = True):
        """初始化文件清理器

        Args:
            output_dir: 输出目录
            keep_days: 保留天数
            enable_auto_clean: 是否启用自动清理
        """
        self.output_dir = Path(output_dir)
        self.keep_days = keep_days
        self.enable_auto_clean = enable_auto_clean

        # 确保目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_files_by_type(self, pattern: str = "*.*") -> List[Path]:
        """获取指定模式的文件列表"""
        try:
            return list(self.output_dir.rglob(pattern))
        except Exception as e:
            logger.error(f"获取文件列表失败: {e}")
            return []

    def should_clean_file(self, file_path: Path) -> bool:
        """判断是否应该清理文件"""
        if not file_path.exists():
            return False

        try:
            # 获取文件修改时间
            file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            cutoff_date = datetime.now() - timedelta(days=self.keep_days)

            # 检查是否是旧文件
            if file_mtime < cutoff_date:
                return True

            # 如果是空文件，也考虑清理
            if file_path.stat().st_size == 0:
                logger.debug(f"空文件: {file_path}")
                return True

            return False

        except Exception as e:
            logger.warning(f"检查文件 {file_path} 失败: {e}")
            return False

    def clean_file(self, file_path: Path, dry_run: bool = False) -> bool:
        """清理单个文件"""
        try:
            if dry_run:
                logger.info(f"[DRY RUN] 将清理文件: {file_path}")
                return True

            if file_path.is_file():
                # 获取文件大小用于日志
                file_size = file_path.stat().st_size
                file_path.unlink()
                logger.info(f"已清理文件: {file_path} ({file_size} bytes)")
                return True
            elif file_path.is_dir():
                # 如果是空目录，也清理
                if not any(file_path.iterdir()):
                    file_path.rmdir()
                    logger.info(f"已清理空目录: {file_path}")
                    return True
                else:
                    logger.debug(f"非空目录，跳过: {file_path}")
                    return False

        except PermissionError:
            logger.warning(f"权限不足，无法清理文件: {file_path}")
            return False
        except Exception as e:
            logger.error(f"清理文件 {file_path} 失败: {e}")
            return False

    def clean_old_files(self,
                        patterns: Optional[List[str]] = None,
                        dry_run: bool = False) -> dict:
        """清理旧文件"""
        if not self.enable_auto_clean:
            logger.info("自动清理已禁用")
            return {'total': 0, 'cleaned': 0, 'skipped': 0}

        # 默认清理所有文件
        if patterns is None:
            patterns = ["*.*"]

        stats = {'total': 0, 'cleaned': 0, 'skipped': 0}

        logger.info(
            f"开始清理 {self.output_dir} 中超过 {self.keep_days} 天的旧文件"
        )

        for pattern in patterns:
            try:
                files = self.get_files_by_type(pattern)
                logger.debug(f"模式 {pattern} 匹配到 {len(files)} 个文件")

                for file_path in files:
                    stats['total'] += 1

                    if self.should_clean_file(file_path):
                        if self.clean_file(file_path, dry_run=dry_run):
                            stats['cleaned'] += 1
                        else:
                            stats['skipped'] += 1
                    else:
                        stats['skipped'] += 1

            except Exception as e:
                logger.error(f"清理模式 {pattern} 失败: {e}")

        if stats['cleaned'] > 0:
            logger.info(
                f"清理完成: 总数 {stats['total']}, "
                f"已清理 {stats['cleaned']}, "
                f"跳过 {stats['skipped']}"
            )

        return stats

    def clean_output_directory(self, keep_subdirs: bool = True, dry_run: bool = False) -> dict:
        """清理输出目录

        Args:
            keep_subdirs: 是否保留子目录结构
            dry_run: 试运行模式
        """
        stats = {'total': 0, 'cleaned': 0, 'skipped': 0}

        logger.info(f"开始清理输出目录: {self.output_dir}")

        try:
            # 遍历所有文件和目录
            for item in self.output_dir.iterdir():
                stats['total'] += 1

                if item.is_file():
                    if self.should_clean_file(item):
                        if self.clean_file(item, dry_run=dry_run):
                            stats['cleaned'] += 1
                        else:
                            stats['skipped'] += 1
                    else:
                        stats['skipped'] += 1

                elif item.is_dir() and not keep_subdirs:
                    # 如果需要清理子目录
                    if self.should_clean_file(item):
                        try:
                            if dry_run:
                                logger.info(f"[DRY RUN] 将清理目录: {item}")
                                stats['cleaned'] += 1
                            else:
                                shutil.rmtree(item)
                                logger.info(f"已清理目录: {item}")
                                stats['cleaned'] += 1
                        except Exception as e:
                            logger.error(f"清理目录 {item} 失败: {e}")
                            stats['skipped'] += 1
                    else:
                        stats['skipped'] += 1

        except Exception as e:
            logger.error(f"清理输出目录失败: {e}")

        logger.info(
            f"目录清理完成: 总数 {stats['total']}, "
            f"已清理 {stats['cleaned']}, "
            f"跳过 {stats['skipped']}"
        )

        return stats

    def cleanup_temp_files(self,
                           temp_dir: Optional[Union[str, Path]] = None,
                           dry_run: bool = False) -> dict:
        """清理临时文件"""
        if temp_dir is None:
            # 默认清理 output 目录中的 temp 子目录
            temp_dir = self.output_dir / "temp"

        temp_path = Path(temp_dir)
        if not temp_path.exists():
            logger.info(f"临时目录不存在: {temp_path}")
            return {'total': 0, 'cleaned': 0, 'skipped': 0}

        stats = {'total': 0, 'cleaned': 0, 'skipped': 0}
        logger.info(f"开始清理临时目录: {temp_path}")

        try:
            for item in temp_path.rglob("*"):
                stats['total'] += 1

                # 临时文件直接清理，不需要检查时间
                if item.is_file():
                    try:
                        if dry_run:
                            logger.info(f"[DRY RUN] 将清理临时文件: {item}")
                            stats['cleaned'] += 1
                        else:
                            file_size = item.stat().st_size
                            item.unlink()
                            logger.debug(f"已清理临时文件: {item} ({file_size} bytes)")
                            stats['cleaned'] += 1
                    except Exception as e:
                        logger.warning(f"清理临时文件 {item} 失败: {e}")
                        stats['skipped'] += 1

                elif item.is_dir():
                    # 检查是否是空目录
                    try:
                        if not any(item.iterdir()):
                            if dry_run:
                                logger.info(f"[DRY RUN] 将清理空目录: {item}")
                                stats['cleaned'] += 1
                            else:
                                item.rmdir()
                                logger.debug(f"已清理空目录: {item}")
                                stats['cleaned'] += 1
                        else:
                            stats['skipped'] += 1
                    except Exception as e:
                        logger.warning(f"检查目录 {item} 失败: {e}")
                        stats['skipped'] += 1

        except Exception as e:
            logger.error(f"清理临时目录失败: {e}")

        # 清理完成后检查主临时目录
        try:
            if temp_path.exists() and not any(temp_path.iterdir()):
                if not dry_run:
                    temp_path.rmdir()
                    logger.info(f"已清理空临时目录: {temp_path}")
        except Exception as e:
            logger.warning(f"清理临时目录失败: {e}")

        logger.info(
            f"临时目录清理完成: 总数 {stats['total']}, "
            f"已清理 {stats['cleaned']}, "
            f"跳过 {stats['skipped']}"
        )

        return stats

    def get_disk_usage(self) -> dict:
        """获取磁盘使用情况"""
        try:
            total_size = 0
            total_files = 0

            for item in self.output_dir.rglob("*"):
                if item.is_file():
                    total_files += 1
                    total_size += item.stat().st_size

            # 转换为更友好的格式
            size_kb = total_size / 1024
            size_mb = size_kb / 1024
            size_gb = size_mb / 1024

            return {
                'total_files': total_files,
                'total_bytes': total_size,
                'total_kb': round(size_kb, 2),
                'total_mb': round(size_mb, 2),
                'total_gb': round(size_gb, 4),
                'output_dir': str(self.output_dir)
            }

        except Exception as e:
            logger.error(f"获取磁盘使用情况失败: {e}")
            return {
                'total_files': 0,
                'total_bytes': 0,
                'total_kb': 0,
                'total_mb': 0,
                'total_gb': 0,
                'output_dir': str(self.output_dir),
                'error': str(e)
            }

    def run_scheduled_cleanup(self, dry_run: bool = False) -> dict:
        """运行计划的清理任务"""
        logger.info("运行计划的文件清理任务")

        stats = {
            'old_files': self.clean_old_files(dry_run=dry_run),
            'temp_files': self.cleanup_temp_files(dry_run=dry_run),
            'disk_usage': self.get_disk_usage()
        }

        # 汇总统计
        total_cleaned = (
            stats['old_files'].get('cleaned', 0) +
            stats['temp_files'].get('cleaned', 0)
        )
        total_skipped = (
            stats['old_files'].get('skipped', 0) +
            stats['temp_files'].get('skipped', 0)
        )
        total_files = (
            stats['old_files'].get('total', 0) +
            stats['temp_files'].get('total', 0)
        )

        stats['summary'] = {
            'total_files': total_files,
            'total_cleaned': total_cleaned,
            'total_skipped': total_skipped,
            'disk_usage_mb': stats['disk_usage'].get('total_mb', 0)
        }

        logger.info(
            f"计划清理完成: 总数 {total_files}, "
            f"已清理 {total_cleaned}, "
            f"跳过 {total_skipped}, "
            f"磁盘使用: {stats['disk_usage'].get('total_mb', 0):.2f} MB"
        )

        return stats
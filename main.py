#!/usr/bin/env python3
"""新闻聚合系统主入口"""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from src.news_aggregator import (
    Config,
    NewsScheduler,
    NEWS_SOURCES,
)
from src.news_aggregator.scheduler import run_aggregation


def setup_logging(verbose: bool = False):
    """配置日志"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # 减少第三方库日志
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)


def list_sources():
    """列出所有新闻源"""
    print("\n📰 新闻源列表\n")
    print(f"总计: {len(NEWS_SOURCES)} 个源\n")

    by_region = {}
    for source in NEWS_SOURCES:
        region = source.region.value
        if region not in by_region:
            by_region[region] = []
        by_region[region].append(source)

    for region, sources in by_region.items():
        print(f"## {region} ({len(sources)} 个)")
        for s in sources:
            flags = []
            if s.requires_proxy:
                flags.append("需代理")
            if s.has_paywall:
                flags.append("付费墙")
            flag_str = f" [{', '.join(flags)}]" if flags else ""
            print(f"  - {s.name}: {s.url}{flag_str}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="新闻聚合与摘要系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py --once              # 运行一次
  python main.py --once --no-llm     # 运行一次（不使用 LLM）
  python main.py --daemon            # 以守护进程运行
  python main.py --list-sources      # 列出所有新闻源
        """,
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="运行一次后退出",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="以守护进程模式运行定时任务",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="不使用 LLM 分析（仅聚合）",
    )
    parser.add_argument(
        "--no-paywall",
        action="store_true",
        help="不尝试绕过付费墙",
    )
    parser.add_argument(
        "--max-news",
        type=int,
        default=100,
        help="最大分析新闻数量（默认 100）",
    )
    parser.add_argument(
        "--cron",
        type=str,
        help="自定义 cron 表达式（默认使用 .env 配置）",
    )
    parser.add_argument(
        "--env",
        type=str,
        default=".env",
        help="环境变量文件路径（默认 .env）",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="输出目录（覆盖 .env 配置）",
    )
    parser.add_argument(
        "--list-sources",
        action="store_true",
        help="列出所有新闻源",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="详细日志输出",
    )

    args = parser.parse_args()

    # 配置日志
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # 列出源
    if args.list_sources:
        list_sources()
        return 0

    # 加载配置
    env_file = args.env if Path(args.env).exists() else None
    config = Config.from_env(env_file)

    # 覆盖输出目录
    if args.output:
        config.output_dir = Path(args.output)

    # 验证配置
    if not args.no_llm:
        errors = config.validate()
        if errors:
            for error in errors:
                logger.error(error)
            logger.error("请检查 .env 配置文件")
            return 1

    # 运行模式
    if args.once:
        # 单次运行
        logger.info("开始单次运行...")
        filepath = asyncio.run(
            run_aggregation(
                config,
                use_llm=not args.no_llm,
            )
        )
        if filepath:
            print(f"\n✅ 摘要已生成: {filepath}")
        return 0

    elif args.daemon:
        # 守护进程模式
        logger.info("启动守护进程模式...")
        scheduler = NewsScheduler(config)

        # 信号处理
        def signal_handler(signum, frame):
            logger.info("收到停止信号，正在关闭...")
            scheduler.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # 启动调度器
        cron = args.cron or config.schedule_cron
        scheduler.start(cron)

        next_run = scheduler.get_next_run_time()
        if next_run:
            logger.info(f"下次运行时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")

        # 保持运行
        try:
            asyncio.get_event_loop().run_forever()
        except (KeyboardInterrupt, SystemExit):
            scheduler.stop()

        return 0

    else:
        # 默认显示帮助
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Python 新闻聚合系统，从 34 个全球新闻源获取 RSS 内容，使用 LLM 进行分析，生成每日中文 Markdown 摘要，支持邮件和Telegram发送。

## 核心命令

```bash
# 安装依赖
pip install -r requirements.txt
playwright install chromium  # 可选，用于顽固付费墙

# 运行一次（使用 LLM）
python main.py --once

# 运行一次（快速模式，不使用 LLM）
python main.py --once --no-llm

# 守护进程模式
python main.py --daemon

# 查看新闻源
python main.py --list-sources

# 测试付费墙绕过
python test_paywall.py

# 生成每日报告（含邮件）
python main.py --daily-report

# 生成每日报告并发送到Telegram
python main.py --daily-report --telegram
```

### 命令行选项
- `--no-paywall`: 不绕过付费墙
- `--max-news N`: 限制分析数量（默认 100）
- `--output DIR`: 输出目录
- `--cron "0 8 * * *"`: 自定义定时
- `--telegram`: 发送报告到Telegram
- `-v`: 详细日志

## 架构

```
新闻源 → RSS抓取 → 付费墙绕过 → LLM分析 → 生成摘要 → 输出 → 邮件/Telegram
```

### 核心模块 (src/news_aggregator/)

| 模块 | 功能 |
|------|------|
| `config.py` | 配置管理，加载 `.env` |
| `sources.py` | 34 个新闻源定义 |
| `fetcher.py` | 异步 RSS 抓取，`NewsItem` 数据类 |
| `bypass.py` | HTTP 付费墙绕过（Chrome headers、JSON-LD、Googlebot） |
| `bypass_browser.py` | Playwright + BPC 扩展绕过（用于顽固付费墙） |
| `analyzer.py` | LLM 批量分析，重要性评分 1-10 |
| `summarizer.py` | Markdown 摘要生成 |
| `scheduler.py` | APScheduler 定时任务 |
| `email_sender.py` | Gmail 邮件发送 |
| `telegram_sender.py` | Telegram 消息发送（支持分块发送大文件） |
| `daily_report.py` | 每日报告生成（支持邮件和Telegram） |

### Telegram 功能
- **文本发送**: 自动分割长消息以适应Telegram限制
- **文件分块**: 大文件按行分割发送
- **文档发送**: 完整文件作为附件发送
- **进度显示**: 显示发送进度（第X/Y部分）

### 付费墙绕过策略

**HTTP 方法**（大多数网站）：
- Chrome 浏览器 Headers + 安全头
- JSON-LD 结构化数据提取
- Googlebot User-Agent
- 搜索引擎 Referer

**浏览器方法**（顽固付费墙）：
- Playwright + Bypass Paywalls Clean 扩展
- 适用于：Bloomberg、Financial Times、Washington Post

### 新闻源（34 个）

- **美国**: CNN, NYTimes, Washington Post, WSJ, Bloomberg, Politico, The Atlantic
- **英国**: BBC, Guardian, Financial Times
- **欧洲**: 德国之声, France 24, Euronews, POLITICO Europe, Der Spiegel
- **亚太**: NHK, 日经亚洲, 南华早报, 联合早报, ABC Australia, Channel NewsAsia
- **中文独立**: RFI, VOA, RFA（需代理）
- **科技**: TechCrunch, Wired, Ars Technica, The Verge, MIT Tech Review
- **财经**: CNBC, MarketWatch, Yahoo Finance

**付费墙媒体**: 10 个，全部可绕过

## 配置

```env
# .env
# LLM 配置
LLM_PROVIDER=openai
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://qianfan.baidubce.com/v2
OPENAI_MODEL=deepseek-v3.2

# 代理配置 (可选)
HTTP_PROXY=
HTTPS_PROXY=

# 定时任务 (北京时间)
SCHEDULE_CRON=0 8 * * *
TIMEZONE=Asia/Shanghai

# 输出配置
OUTPUT_DIR=./output

# 邮件配置
EMAIL_SENDER=your-email@gmail.com
EMAIL_PASSWORD=xxxx xxxx xxxx xxxx
EMAIL_RECIPIENT=your-email@gmail.com

# Telegram 配置
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_ID=your-telegram-chat-id

# 逐篇分析配置 (per-article mode)
PER_ARTICLE_MAX_CONCURRENT=20
PER_ARTICLE_MAX_RETRIES=3
PER_ARTICLE_KEEP_DAYS=7
PER_ARTICLE_ENABLE_AUTO_CLEAN=true

# BPC 扩展路径 (用于顽固付费墙)
BPC_EXTENSION_PATH=/path/to/bypass-paywalls-chrome-clean
```

### Telegram 配置说明
1. **创建机器人**: 通过 @BotFather 创建机器人获取 Token
2. **获取 Chat ID**: 给机器人发送消息后，可通过 `get_telegram_id.py` 获取数字ID
3. **配置**: 将 Token 和 Chat ID 填入 `.env` 文件

## 输出

- **完整摘要**: `output/news-summary-YYYY-MM-DD.md`
- **快速聚合**: `output/news-quick-YYYY-MM-DD.md`
- **详细分析**: `output/news-analysis-*.md`
- **每日报告**: `output/daily-report-YYYY-MM-DD.md`

## 使用示例

### 1. 简单运行
```bash
# 单次运行，生成摘要
python main.py --once

# 单次运行（不使用LLM，仅聚合）
python main.py --once --no-llm
```

### 2. 每日报告
```bash
# 生成报告并发送邮件
python main.py --daily-report

# 生成报告并发送到Telegram
python main.py --daily-report --telegram
```

### 3. 定时任务
```bash
# 启动守护进程，每天8点自动运行
python main.py --daemon
```

### 4. 逐篇分析模式
```bash
# 启用逐篇分析并发送到Telegram
python main.py --once --per-article --telegram
```

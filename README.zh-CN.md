# newsRSS

面向日常新闻监控的 LLM 辅助 RSS 情报流水线。

newsRSS 会从全球 RSS 源抓取文章，抽取正文，用大模型做重要性判断和摘要生成，再把最终结果输出为 Markdown、邮件或 Telegram 每日报告。

## 它解决什么问题

这个项目适合那些不想每天手动刷几十个站点，而是希望得到一份更紧凑、更有筛选逻辑的新闻工作流的人。

核心流程是：

1. 从一组筛选好的 RSS 源抓取内容
2. 提取文章正文
3. 按需处理部分付费墙网站
4. 用 LLM 做重要性评分、分类和摘要
5. 输出日报，或自动发送给自己

## 核心特性

- 覆盖国际主流媒体、科技媒体、财经媒体和亚太区域媒体
- 基于 LLM 做排序、分类和摘要生成
- 支持 Markdown 每日报告
- 支持 SMTP 邮件发送
- 支持 Telegram 发送，包含长消息拆分与文件发送
- 支持 cron 风格定时运行
- 支持代理配置与可选付费墙绕过

## 快速开始

### 环境要求

- Python 3.10+
- 一个可用的 OpenAI 风格接口模型服务
- 可选：Playwright，用于浏览器版付费墙处理

### 安装

```bash
git clone https://github.com/XiaokunDuan/newsRSS.git
cd newsRSS
pip install -r requirements.txt
```

如需启用浏览器版付费墙流程：

```bash
playwright install chromium
```

### 配置

```bash
cp .env.example .env
```

然后在 `.env` 中填写模型、发送渠道和定时任务配置。

### 常用命令

```bash
# 查看所有新闻源
python main.py --list-sources

# 生成一次每日报告
python main.py --daily-report

# 同时发送到 Telegram
python main.py --daily-report --telegram

# 守护进程模式定时运行
python main.py --daemon
```

## 输出方式

- 本地 Markdown 报告，便于归档和复查
- SMTP 邮件发送
- Telegram 日报推送与大段内容拆分发送

## 配置概览

`.env.example` 覆盖了这些配置项：

- LLM 服务地址与模型
- HTTP / HTTPS 代理
- 时区与定时表达式
- 输出目录
- 邮件账号
- Telegram Bot 配置
- 付费墙扩展路径

## 项目结构

```text
newsRSS/
├── main.py
├── .env.example
├── requirements.txt
├── check_daemon.py
├── run_overnight.sh
├── test_paywall_efficiency.py
└── src/news_aggregator/
```

## 说明

- 这个项目更偏个人或小团队的信息监控流程，不是托管型新闻 SaaS。
- 付费墙绕过能力是可选增强，不启用也可以正常使用项目主体功能。
- 敏感密钥必须保存在 `.env`，不要提交到仓库。

## 文档

- English README: [README.md](./README.md)

## License

当前仓库还没有独立的 license 文件；如果后续计划更广泛公开传播，建议补上。

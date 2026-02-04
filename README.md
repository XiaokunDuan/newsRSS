# 📰 News RSS Aggregator

智能新闻聚合系统，从全球34个新闻源获取RSS内容，使用LLM进行分析，生成每日中文Markdown摘要，支持邮件和Telegram自动发送。

## ✨ 特性

### 🗞️ 新闻源覆盖
- **全球34个优质新闻源**：涵盖美国、英国、欧洲、亚太等地区
- **多种媒体类型**：主流媒体、财经媒体、科技媒体、独立媒体
- **付费墙支持**：自动绕过10个主流付费墙网站

### 🤖 AI智能分析
- **LLM深度分析**：使用DeepSeek等模型分析新闻重要性（1-10分）
- **多模式分析**：支持批量分析和逐篇分析模式
- **智能分类**：自动识别新闻类别和趋势

### 📬 多渠道输出
- **Markdown报告**：生成格式化的每日新闻摘要
- **邮件发送**：支持Gmail自动发送HTML格式报告
- **Telegram集成**：支持消息分割和大文件发送
- **多种格式**：完整摘要、快速聚合、详细分析

### ⚙️ 灵活配置
- **定时任务**：支持cron表达式自定义运行时间
- **代理支持**：支持HTTP/HTTPS代理配置
- **扩展性强**：模块化设计，易于扩展新功能

## 🚀 快速开始

### 1. 环境准备
```bash
# 克隆项目
git clone https://github.com/yourusername/newsRSS.git
cd newsRSS

# 安装依赖
pip install -r requirements.txt

# 安装Playwright（如需付费墙绕过）
playwright install chromium
```

### 2. 配置设置
复制配置文件并修改：
```bash
cp .env.example .env
```

编辑 `.env` 文件配置以下信息：
```env
# LLM配置
OPENAI_API_KEY=your-deepseek-api-key
OPENAI_BASE_URL=https://qianfan.baidubce.com/v2
OPENAI_MODEL=deepseek-v3.2

# 邮件配置（可选）
EMAIL_SENDER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
EMAIL_RECIPIENT=recipient-email@gmail.com

# Telegram配置（可选）
TELEGRAM_BOT_TOKEN=your-bot-token-here
TELEGRAM_CHAT_ID=your-chat-id-here

# 定时任务（北京时间早上8点）
SCHEDULE_CRON=0 8 * * *
TIMEZONE=Asia/Shanghai
```

**⚠️ 安全提示**：请勿将包含个人API密钥和Token的 `.env` 文件提交到Git仓库！

### 3. 获取Telegram配置
```bash
# 创建Telegram机器人
# 1. 在Telegram中搜索 @BotFather
# 2. 发送 /newbot 创建新机器人
# 3. 获取Bot Token
# 4. 给机器人发送消息后，使用以下命令获取Chat ID（临时工具）
python -c "
import asyncio
from telegram import Bot
from dotenv import load_dotenv
import os

load_dotenv()
token = os.getenv('TELEGRAM_BOT_TOKEN')
bot = Bot(token=token)
updates = asyncio.run(bot.get_updates())
if updates:
    print(f'Chat ID: {updates[-1].message.chat.id}')
"
```

## 📖 使用方法

### 基础命令
```bash
# 查看所有新闻源
python main.py --list-sources

# 单次运行（使用LLM分析）
python main.py --once

# 单次运行（仅聚合，不使用LLM）
python main.py --once --no-llm

# 生成每日报告并发送邮件
python main.py --daily-report

# 生成每日报告并发送到Telegram
python main.py --daily-report --telegram

# 守护进程模式（定时运行）
python main.py --daemon

# 逐篇分析模式（每篇文章单独分析）
python main.py --once --per-article
```

### 高级选项
```bash
# 自定义定时表达式
python main.py --daemon --cron "0 12 * * *"  # 每天中午12点

# 限制分析新闻数量
python main.py --once --max-news 50

# 详细日志输出
python main.py --once -v

# 不绕过付费墙
python main.py --once --no-paywall

# 自定义输出目录
python main.py --once --output ./my-output

# 使用自定义环境文件
python main.py --once --env .env.production
```

### Telegram功能示例
```bash
# 发送每日报告到Telegram
python main.py --daily-report --telegram

# 逐篇分析并发送统计信息到Telegram
python main.py --once --per-article --telegram
```

## 📁 项目结构

```
newsRSS/
├── main.py                    # 主程序入口
├── requirements.txt           # Python依赖
├── .env.example              # 环境变量示例
├── CLAUDE.md                 # 项目开发文档
├── README.md                 # 项目说明文档
├── src/news_aggregator/      # 核心模块
│   ├── config.py            # 配置管理
│   ├── sources.py           # 新闻源定义
│   ├── fetcher.py           # RSS抓取
│   ├── bypass.py            # 付费墙绕过
│   ├── analyzer.py          # LLM分析
│   ├── summarizer.py        # 摘要生成
│   ├── scheduler.py         # 定时任务
│   ├── email_sender.py      # 邮件发送
│   ├── telegram_sender.py   # Telegram发送
│   ├── daily_report.py      # 每日报告
│   └── ...                  # 其他工具模块
└── output/                  # 输出目录
    ├── daily-report-*.md    # 每日报告
    ├── news-analysis-*.md   # 详细分析
    └── news-quick-*.md      # 快速聚合
```

## 🛡️ 新闻源列表（34个）

### 🌎 美国媒体
- CNN, New York Times, Washington Post, Wall Street Journal
- Bloomberg, Politico, The Atlantic

### 🇬🇧 英国媒体
- BBC, The Guardian, Financial Times

### 🇪🇺 欧洲媒体
- 德国之声 (DW), France 24, Euronews
- POLITICO Europe, Der Spiegel

### 🌏 亚太媒体
- NHK Japan, Nikkei Asia, South China Morning Post
- Straits Times, ABC Australia, Channel NewsAsia

### 🇨🇳 中文独立媒体
- Radio France Internationale (RFI)
- Voice of America (VOA)
- Radio Free Asia (RFA) - 需代理

### 💻 科技媒体
- TechCrunch, Wired, Ars Technica
- The Verge, MIT Technology Review

### 💰 财经媒体
- CNBC, MarketWatch, Yahoo Finance

**📰 付费墙媒体（10个）**：全部支持自动绕过

## 🔧 付费墙绕过技术

### HTTP方法（大多数网站）
- Chrome浏览器Headers + 安全头
- JSON-LD结构化数据提取
- Googlebot User-Agent
- 搜索引擎Referer

### 浏览器方法（顽固付费墙）
- Playwright + Bypass Paywalls Clean扩展
- 支持：Bloomberg、Financial Times、Washington Post等

## 📧 邮件和Telegram功能

### 邮件发送
- 支持Gmail SMTP
- HTML格式美观排版
- 支持中文内容

### Telegram发送
- **智能消息分割**：自动分割长消息（>4000字符）
- **文件分块发送**：大文件按行分割发送
- **文档附件**：完整文件作为附件发送
- **进度显示**：实时显示发送进度
- **多格式支持**：文本、Markdown、文件

## ⚠️ 安全注意事项

1. **保护API密钥**：
   - 永远不要将 `.env` 文件提交到Git
   - 使用 `.env.example` 作为模板
   - 将 `.env` 添加到 `.gitignore`

2. **Telegram安全**：
   - Bot Token 应保密
   - 定期轮换Token（如怀疑泄露）
   - 使用环境变量存储敏感信息

3. **邮件安全**：
   - 使用Gmail应用专用密码
   - 不要使用主账户密码

## 🐛 故障排除

### 常见问题

**Q: Telegram发送失败 "Chat not found"**
A:
1. 确认Chat ID是否正确
2. 确保用户已给机器人发送 /start 命令
3. 检查机器人是否被用户屏蔽

**Q: 邮件发送失败**
A:
1. 确认使用Gmail应用专用密码
2. 检查是否开启了两步验证
3. 确认SMTP设置正确

**Q: LLM分析失败**
A:
1. 检查API密钥是否正确
2. 确认API服务可访问
3. 检查网络连接和代理设置

**Q: 付费墙绕过失败**
A:
1. 尝试使用浏览器模式 `--use-browser`
2. 检查网络代理设置
3. 确认Playwright已正确安装

### 日志查看
```bash
# 启用详细日志
python main.py --once -v

# 查看特定模块日志
import logging
logging.getLogger('src.news_aggregator').setLevel(logging.DEBUG)
```

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 开发规范
- 遵循PEP 8代码风格
- 添加适当的类型注解
- 编写单元测试
- 更新相关文档

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🙏 致谢

- 感谢所有新闻源提供内容
- 感谢DeepSeek等LLM服务提供商
- 感谢开源社区的工具支持

## 📞 联系方式

如有问题或建议，请通过GitHub Issues提交。

---

**🚀 开始使用**：配置好环境变量后，运行 `python main.py --once` 即可体验智能新闻聚合！

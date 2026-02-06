#!/bin/bash
# 夜间自动运行新闻聚合脚本
# 使用Claude Code的headless模式无需人工确认

cd /Users/dxk/newsRSS

# 设置环境变量
# 空闲300秒（5分钟）后自动退出
export CLAUDE_CODE_EXIT_AFTER_STOP_DELAY=300000
# API请求超时3分钟
export API_TIMEOUT_MS=180000
# 禁用成本警告
export DISABLE_COST_WARNINGS=true
# 禁用遥测
export DISABLE_TELEMETRY=true
# 命令默认超时2分钟
export BASH_DEFAULT_TIMEOUT_MS=120000
# 命令最大超时5分钟
export BASH_MAX_TIMEOUT_MS=300000

# 创建日志目录
mkdir -p logs

# 开始运行日志
echo "=== 开始夜间新闻聚合运行 ($(date)) ===" >> logs/overnight.log
echo "工作目录: $(pwd)" >> logs/overnight.log
echo "环境变量设置完成" >> logs/overnight.log

# 使用Claude Code headless模式运行新闻聚合
# -p: 任务描述
# --allowedTools: 允许的工具（自动批准这些工具的使用）
# --output-format: 输出格式为JSON便于解析

echo "启动Claude Code headless模式..." >> logs/overnight.log

claude -p "执行夜间新闻聚合任务：
1. 运行 python main.py --once 获取和分析今日新闻
2. 运行 python main.py --list-sources 列出新闻源状态
3. 如果遇到付费墙问题，运行 python test_paywall.py 测试
4. 生成分析报告到output目录
5. 返回处理结果摘要，包括成功处理的新闻源数量和遇到的错误" \
  --allowedTools "Bash(python main.py --once),Bash(python main.py --list-sources),Bash(python test_paywall.py),Bash(playwright install chromium),Bash(pip install -r requirements.txt),Read(./output/*),Edit(./output/*.md),Write(./output/*.md),Bash(ls -la ./output/),Bash(mkdir -p ./output/),Bash(mkdir -p logs),Bash(echo *),Bash(grep *),Bash(wc -l *)" \
  --output-format json \
  >> logs/overnight-$(date +%Y-%m-%d).json 2>> logs/overnight-error.log

# 检查运行状态
EXIT_CODE=$?

echo "=== 运行结束 ($(date)) ===" >> logs/overnight.log
echo "退出代码: $EXIT_CODE" >> logs/overnight.log

if [ $EXIT_CODE -eq 0 ]; then
    echo "状态: 成功完成" >> logs/overnight.log
    # 检查输出文件是否存在
    if ls output/news-summary-*.md 1> /dev/null 2>&1; then
        LATEST_FILE=$(ls -t output/news-summary-*.md | head -1)
        echo "最新生成文件: $LATEST_FILE" >> logs/overnight.log
        echo "文件大小: $(wc -l < "$LATEST_FILE") 行" >> logs/overnight.log
    else
        echo "警告: 未找到输出文件" >> logs/overnight.log
    fi
else
    echo "状态: 运行失败" >> logs/overnight.log
    echo "错误日志内容:" >> logs/overnight.log
    tail -20 logs/overnight-error.log >> logs/overnight.log 2>/dev/null
fi

echo "" >> logs/overnight.log
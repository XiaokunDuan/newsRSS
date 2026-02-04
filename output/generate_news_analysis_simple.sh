#!/bin/bash

# 生成极简版新闻分析报告
# 格式：标题（来源+题目）、发布时间、关键点
# 移除：##前缀、重要性、情感、分析时间字段

INPUT_FILE="/Users/dxk/newsRSS/output/articles/articles-2026-02-04.jsonl"
OUTPUT_FILE="/Users/dxk/newsRSS/output/news-analysis-simple-2026-02-04.md"

# 检查输入文件是否存在
if [ ! -f "$INPUT_FILE" ]; then
    echo "错误: 输入文件不存在: $INPUT_FILE"
    exit 1
fi

# 生成报告
cat "$INPUT_FILE" | jq -r '
. | "\(.source_name) \(.title)\n发布时间: \(.original_item.published)\n" +
(if (.key_points | length) > 0 then
  .key_points | map("• " + .) | join("\n")
else
  "• 无关键点"
end) + "\n"
' > "$OUTPUT_FILE"

# 检查输出文件
if [ -f "$OUTPUT_FILE" ]; then
    echo "已生成极简版报告: $OUTPUT_FILE"
    echo "文件大小: $(wc -c < "$OUTPUT_FILE") 字节"
    echo "文章数量: $(jq -c '.' < "$INPUT_FILE" | wc -l) 篇"
else
    echo "错误: 生成报告失败"
    exit 1
fi
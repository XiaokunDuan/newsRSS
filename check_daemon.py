#!/usr/bin/env python3
"""检查守护进程状态"""

import subprocess
import os
from datetime import datetime, timedelta

print("=== 守护进程状态检查 ===\n")

# 1. 检查进程
print("1. 正在运行的守护进程:")
result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
demon_processes = []
for line in result.stdout.split('\n'):
    if "python" in line and "main.py" in line and "--daemon" in line and "grep" not in line:
        demon_processes.append(line)

if demon_processes:
    print(f"   ✅ 找到 {len(demon_processes)} 个守护进程:")
    for proc in demon_processes:
        print(f"   - {proc.strip()[:80]}...")
    print("\n2. 守护进程日志:")
    if os.path.exists("daemon.log"):
        with open("daemon.log", "r") as f:
            lines = f.readlines()
            print(f"   日志文件大小: {len(lines)} 行")
            if lines:
                print("   最后5行日志:")
                for line in lines[-5:]:
                    print(f"    - {line.strip()}")
    else:
        print("   ℹ️ 没有日志文件 (可能尚未生成)")

    print("\n3. 下次运行时间:")
    # 根据.env文件中的CRON表达式计算
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if line.startswith("SCHEDULE_CRON="):
                    cron = line.split("=")[1].strip()
                    hour = int(cron.split()[1])  # 第二个是小时
                    now = datetime.now()
                    next_run = now.replace(hour=hour, minute=0, second=0, microsecond=0)
                    if next_run <= now:
                        next_run += timedelta(days=1)
                    print(f"   配置: {cron} (每天{hour:02d}:00)")
                    print(f"   下次运行: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"   距离现在: {(next_run - now).seconds // 3600}小时{(next_run - now).seconds % 3600 // 60}分钟")
                    break
else:
    print("   ❌ 没有找到运行中的守护进程")
    print("\n尝试启动守护进程...")
    result = subprocess.run(["python", "main.py", "--daemon", "&"], shell=True)
    if result.returncode == 0:
        print("   ✅ 守护进程已启动")
    else:
        print("   ❌ 启动失败")

print("\n4. 输出目录状态:")
if os.path.exists("output"):
    import glob
    jsonl_files = glob.glob("output/articles/*.jsonl")
    md_files = glob.glob("output/*.md")
    print(f"   JSONL文件: {len(jsonl_files)} 个")
    if jsonl_files:
        print("   最新JSONL文件:")
        sorted_files = sorted(jsonl_files, key=os.path.getmtime, reverse=True)
        for f in sorted_files[:2]:
            mtime = datetime.fromtimestamp(os.path.getmtime(f))
            print(f"    - {os.path.basename(f)} ({mtime.strftime('%Y-%m-%d %H:%M')})")

    print(f"   Markdown摘要: {len(md_files)} 个")
    if md_files:
        print("   最新摘要文件:")
        sorted_files = sorted(md_files, key=os.path.getmtime, reverse=True)
        for f in sorted_files[:2]:
            mtime = datetime.fromtimestamp(os.path.getmtime(f))
            print(f"    - {os.path.basename(f)} ({mtime.strftime('%Y-%m-%d %H:%M')})")
else:
    print("   ℹ️ 输出目录不存在")

print("\n5. 增量JSONL状态:")
if os.path.exists("output/articles"):
    today = datetime.now().strftime("%Y-%m-%d")
    today_jsonl = f"output/articles/articles-{today}.jsonl"
    if os.path.exists(today_jsonl):
        import json
        with open(today_jsonl, "r") as f:
            lines = f.readlines()
            print(f"   今日JSONL文件: {os.path.basename(today_jsonl)}")
            print(f"   文章数量: {len(lines)} 篇")
            if lines:
                # 分析第一篇文章的字段
                try:
                    data = json.loads(lines[0].strip())
                    print("   示例文章字段:")
                    for key, value in data.items():
                        if value is not None:
                            if key == 'full_content' and value:
                                print(f"    - {key}: [已填充] ({len(value)} 字符)")
                            elif key == 'summary' and value:
                                print(f"    - {key}: [已填充] ({len(value)} 字符)")
                            else:
                                print(f"    - {key}: {str(value)[:50]}")
                except json.JSONDecodeError as e:
                    print(f"   解析错误: {e}")
    else:
        print(f"   今日JSONL文件不存在: {today_jsonl}")
else:
    print("   ℹ️ articles目录不存在")

print("\n=== 检查完成 ===")

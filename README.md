# newsRSS

LLM-assisted RSS intelligence pipeline for daily news monitoring.

newsRSS fetches articles from global RSS sources, scores and summarizes them with language models, and delivers daily digests through Markdown, email, and Telegram.

## What it does

This project is designed for people who want a compact, opinionated news workflow instead of opening dozens of sites every day.

Core workflow:

1. collect RSS items from a curated source list
2. extract article content
3. optionally bypass selected paywalls
4. analyze importance and themes with an LLM
5. export a daily report or send it automatically

## Features

- Global RSS source set spanning major international, tech, finance, and Asia-focused media
- LLM-based ranking, classification, and summary generation
- Daily report generation in Markdown
- Email delivery for formatted reports
- Telegram delivery for daily digests and large report chunks
- Scheduled execution with cron-style configuration
- Proxy support and optional paywall bypass flow

## Quick start

### Requirements

- Python 3.10+
- A model endpoint compatible with the configured OpenAI-style interface
- Optional: Playwright for the paywall workflow

### Install

```bash
git clone https://github.com/XiaokunDuan/newsRSS.git
cd newsRSS
pip install -r requirements.txt
```

If you want the browser-based paywall flow:

```bash
playwright install chromium
```

### Configure

```bash
cp .env.example .env
```

Fill in your API, delivery, and scheduling settings in `.env`.

### Common commands

```bash
# List all configured sources
python main.py --list-sources

# Generate one daily report
python main.py --daily-report

# Send the report to Telegram as well
python main.py --daily-report --telegram

# Run as a scheduled daemon
python main.py --daemon
```

## Delivery modes

- Local Markdown output for archive or manual review
- Email delivery through SMTP
- Telegram delivery with long-message splitting and file sending

## Configuration overview

The `.env.example` file covers:

- LLM provider endpoint and model
- HTTP / HTTPS proxy
- timezone and schedule
- output directory
- email credentials
- Telegram bot credentials
- paywall extension path

## Project layout

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

## Notes

- The repository is tuned for a personal or small-team monitoring workflow, not a hosted multi-tenant service.
- The paywall workflow is optional; the project remains usable without it.
- Sensitive credentials must stay in `.env` and should never be committed.

## Documentation

- Chinese README: [README.zh-CN.md](./README.zh-CN.md)

## License

This repository currently does not include a standalone license file. Add one before wider redistribution if needed.

"""配置管理模块"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv


@dataclass
class Config:
    """应用配置类"""

    # LLM 配置
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_base_url: str = "https://qianfan.baidubce.com/v2"
    openai_model: str = "deepseek-v3.2"

    # 代理配置
    http_proxy: Optional[str] = None
    https_proxy: Optional[str] = None

    # 定时任务配置
    schedule_cron: str = "0 8 * * *"
    timezone: str = "Asia/Shanghai"

    # 输出配置
    output_dir: Path = field(default_factory=lambda: Path("./output"))


    # Telegram 配置
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    # BPC 扩展路径
    bpc_extension_path: Optional[str] = None

    # 抓取设置
    fetch_timeout: int = 30
    fetch_max_concurrent: int = 10
    fetch_retry_times: int = 3

    # 逐篇分析配置
    per_article_max_concurrent: int = 5
    per_article_max_retries: int = 2
    per_article_keep_days: int = 7
    per_article_enable_auto_clean: bool = True

    @classmethod
    def from_env(cls, env_file: Optional[str] = None) -> "Config":
        """从环境变量加载配置"""
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        http_proxy = None
        https_proxy = None


        # Telegram 配置
        telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or None
        telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip() or None

        # BPC 扩展路径
        bpc_path = os.getenv("BPC_EXTENSION_PATH", "").strip() or None

        # 逐篇分析配置
        per_article_max_concurrent = int(os.getenv("PER_ARTICLE_MAX_CONCURRENT", "5"))
        per_article_max_retries = int(os.getenv("PER_ARTICLE_MAX_RETRIES", "2"))
        per_article_keep_days = int(os.getenv("PER_ARTICLE_KEEP_DAYS", "7"))
        per_article_enable_auto_clean = os.getenv("PER_ARTICLE_ENABLE_AUTO_CLEAN", "true").lower() == "true"

        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", "openai"),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_base_url=os.getenv(
                "OPENAI_BASE_URL", "https://qianfan.baidubce.com/v2"
            ),
            openai_model=os.getenv("OPENAI_MODEL", "deepseek-v3.2"),
            http_proxy=http_proxy,
            https_proxy=https_proxy,
            schedule_cron=os.getenv("SCHEDULE_CRON", "0 8 * * *"),
            timezone=os.getenv("TIMEZONE", "Asia/Shanghai"),
            output_dir=Path(os.getenv("OUTPUT_DIR", "./output")),
            telegram_bot_token=telegram_bot_token,
            telegram_chat_id=telegram_chat_id,
            bpc_extension_path=bpc_path,
            per_article_max_concurrent=per_article_max_concurrent,
            per_article_max_retries=per_article_max_retries,
            per_article_keep_days=per_article_keep_days,
            per_article_enable_auto_clean=per_article_enable_auto_clean,
        )

    def get_proxy_dict(self) -> Optional[dict]:
        """获取代理配置字典"""
        if not self.http_proxy and not self.https_proxy:
            return None
        return {
            "http": self.http_proxy,
            "https": self.https_proxy or self.http_proxy,
        }

    def validate(self) -> list[str]:
        """验证配置，返回错误列表"""
        errors = []
        if not self.openai_api_key:
            errors.append("OPENAI_API_KEY 未配置")
        return errors

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

    # 输出配置
    output_dir: Path = field(default_factory=lambda: Path("./output"))

    # 获取设置
    fetch_timeout: int = 30
    fetch_max_concurrent: int = 10
    fetch_retry_times: int = 3

    @classmethod
    def from_env(cls, env_file: Optional[str] = None) -> "Config":
        """从环境变量加载配置"""
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        http_proxy = os.getenv("HTTP_PROXY", "").strip() or None
        https_proxy = os.getenv("HTTPS_PROXY", "").strip() or None

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
            output_dir=Path(os.getenv("OUTPUT_DIR", "./output")),
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

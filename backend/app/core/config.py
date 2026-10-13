"""全局配置：从 .env 读取（pydantic-settings），密钥一律不进 Git。"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend\ 目录（.env 与相对路径的基准）
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """环境配置项。所有字段均可被 .env / 环境变量覆盖。"""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ---- LLM 在线通道 ----
    dashscope_api_key: str = ""
    qwen_model: str = "qwen-plus"
    qwen_url: str = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

    # ---- LLM 本地通道 ----
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3.5:4b"
    llm_channel: str = "auto"  # auto | local | online
    llm_local_timeout: int = 60

    # ---- 和风天气 ----
    weather_api_key: str = ""
    weather_host: str = ""
    weather_city_id: str = "101210701"

    # ---- 数据 ----
    data_dir: str = "./data"

    # ---- 语音 ----
    tts_voice: str = "zh-CN-XiaoxiaoNeural"  # 晓晓：edge-tts 最自然的中文女声
    vosk_model_path: str = "./models/vosk-model-cn-0.22"
    ffmpeg_path: str = "ffmpeg"

    # ---- 用户资料 ----
    user_name: str = "小叶"
    user_birthday: str = "04-06"

    # ---- 服务 ----
    api_host: str = "127.0.0.1"
    api_port: int = 8900
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def data_path(self) -> Path:
        """数据目录绝对路径（不存在则创建）。"""
        p = Path(self.data_dir)
        if not p.is_absolute():
            p = BACKEND_DIR / p
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()

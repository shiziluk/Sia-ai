"""全局配置：从 .env 读取（pydantic-settings），密钥一律不进 Git。"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend\ 目录（.env 与相对路径的基准）
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


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
    tts_voice: str = "zh-CN-XiaoxiaoNeural"  # 晓晓：edge-tts 最自然的中文女声（降级兜底）
    vosk_model_path: str = "./models/vosk-model-cn-0.22"
    ffmpeg_path: str = "ffmpeg"

    # ---- 语音：双后端架构（V14，见 docs/23）----
    # 后端选择：gpt_sovits（本地摩耶音色）| edge（仅云端兜底）。
    # 本地后端合成失败会自动降级 edge，应用不中断。
    tts_backend: str = "gpt_sovits"
    # GPT-SoVITS api_v2 本地 HTTP 服务地址（启动命令见 docs/20 §api_v2 用法）。
    gpt_sovits_api_url: str = "http://127.0.0.1:9880"
    gpt_sovits_timeout_seconds: float = 180.0
    voice_ref_manifest: str = "./config/voice_refs.json"
    # 权重路径相对仓库根目录解析；需要在 .env 中换模型时也可使用绝对路径。
    sovits_weight: str = (
        "GPT-SoVITS/GPT-SoVITS-v2pro-20261006/"
        "SoVITS_weights_v2ProPlus/maya_e3.pth"
    )
    gpt_zh_weight: str = (
        "GPT-SoVITS/GPT-SoVITS-v2pro-20261006/"
        "GPT_SoVITS/pretrained_models/s1v3.ckpt"
    )
    gpt_ja_weight: str = (
        "GPT-SoVITS/GPT-SoVITS-v2pro-20261006/"
        "GPT_weights_v2ProPlus/maya-e20.ckpt"
    )
    # SVC 变声路线（RVC）：音色 sim 裁决未出（训练已暂停），默认关闭。
    svc_enabled: bool = False

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

"""统一日志：控制台 + 滚动文件（data/logs/xia.log），替代 V13 的 print 调试。"""
import logging
from logging.handlers import RotatingFileHandler

from app.core.config import settings

_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging() -> logging.Logger:
    """初始化根日志器，返回 'xia' 业务日志器。"""
    logger = logging.getLogger("xia")
    if logger.handlers:  # 防止重复初始化
        return logger

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(_FMT)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    log_dir = settings.data_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_dir / "xia.log", maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


logger = setup_logging()

"""GraphRAG Copilot - 集中式日志服务

基于 loguru，统一格式 + 文件轮转。所有模块通过
`from app.core.logger import logger` 引用，替代 print() 与 traceback.print_exc()。
"""
import os
import sys
from pathlib import Path
from typing import Optional

from loguru import logger as _logger

_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_default_log_dir = Path(__file__).parent.parent.parent / "data" / "logs"
_LOG_DIR: Optional[Path] = Path(os.getenv("LOG_DIR") or str(_default_log_dir))
try:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    # 即便日志目录创建失败，也不要阻断应用启动
    _LOG_DIR = None

_logger.remove()

_logger.add(
    sys.stderr,
    level=_LOG_LEVEL,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True,
    backtrace=False,
    diagnose=False,
)

if _LOG_DIR is not None:
    _logger.add(
        str(_LOG_DIR / "app.log"),
        level=_LOG_LEVEL,
        rotation="10 MB",
        retention="14 days",
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
        diagnose=False,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    )

logger = _logger

__all__ = ["logger"]

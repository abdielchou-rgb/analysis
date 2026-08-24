"""2hao-analyst 统一日志配置

所有模块应通过 get_logger() 获取 logger，不要手动 logging.getLogger()。
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

_LOG_CONFIGURED = False

def configure_logging(level=logging.INFO, log_dir: str = "logs"):
    """全局配置日志（线程安全，只配置一次）"""
    global _LOG_CONFIGURED
    if _LOG_CONFIGURED:
        return
    
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # File handler — 所有级别
    file_handler = logging.FileHandler(
        log_path / f"pipeline_{datetime.now().strftime('%Y%m%d')}.log",
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    
    # Console handler — INFO+
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)
    root.addHandler(console_handler)
    
    _LOG_CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """获取统一配置的 logger"""
    if not _LOG_CONFIGURED:
        configure_logging()
    return logging.getLogger(name)

import logging
import os
import sys
from pathlib import Path

from config import WORKSPACE_ROOT

LOG_DIR = Path(os.getenv("LOG_DIR", str(WORKSPACE_ROOT / "logs")))

def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(LOG_DIR / "server.log", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        pass
    return logger

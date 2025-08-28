# -*- coding: utf-8 -*-
import logging, os
from logging.handlers import RotatingFileHandler

def get_logger(name: str, log_dir: str, log_file: str) -> logging.Logger:
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        path = os.path.join(log_dir, log_file)
        fh = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        fh.setFormatter(fmt); logger.addHandler(fh)
        ch = logging.StreamHandler(); ch.setFormatter(fmt); logger.addHandler(ch)
    return logger

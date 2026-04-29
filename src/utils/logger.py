import logging
import os

# Resolve the project root (2 levels up from this file: src/utils/logger.py -> src/ -> root)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LOG_DIR = os.path.join(_PROJECT_ROOT, "logs")


def setup_logger(name: str) -> logging.Logger:
    """
    Return a named logger with console + rotating file handlers.
    Log files are always written to <project_root>/logs/app.log,
    regardless of the process's current working directory.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # Already configured — avoid duplicate handlers

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File handler (project-root-relative so it works from any cwd)
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        fh = logging.FileHandler(os.path.join(_LOG_DIR, "app.log"), encoding="utf-8")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception as e:
        logger.warning(f"Could not create log file handler: {e}")

    return logger

"""app package init — bootstraps logging on import."""
from app.core.logging_setup import setup_logging
from app.core.settings import get_settings
from pathlib import Path

_s = get_settings()
setup_logging(
    level=_s.logging_config.level,
    logs_dir=Path(_s.storage.logs_dir),
    max_bytes=_s.logging_config.max_bytes,
    backup_count=_s.logging_config.backup_count,
    log_format=_s.logging_config.format,
)

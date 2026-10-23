"""Persistent application logs. No transcript contents are written to logs."""
import logging
from pathlib import Path

def configure_logging(project_root: Path) -> None:
    log_dir = project_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(getattr(h, "_audiototext_file", False) for h in root.handlers):
        errors = logging.FileHandler(log_dir / "errors.log", encoding="utf-8")
        errors.setLevel(logging.ERROR); errors.setFormatter(fmt); errors._audiototext_file = True
        root.addHandler(errors)
        app = logging.FileHandler(log_dir / "application.log", encoding="utf-8")
        app.setLevel(logging.INFO); app.setFormatter(fmt); app._audiototext_file = True
        root.addHandler(app)
        processing = logging.FileHandler(log_dir / "processing.log", encoding="utf-8")
        processing.setLevel(logging.INFO); processing.setFormatter(fmt); processing._audiototext_file = True
        logging.getLogger("processing").addHandler(processing)
        logging.getLogger("processing").setLevel(logging.INFO)
        logging.getLogger("processing").propagate = False
    logging.getLogger(__name__).info("Logging initialized")

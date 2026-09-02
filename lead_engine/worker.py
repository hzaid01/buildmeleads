from __future__ import annotations

import os
import signal
import time
from pathlib import Path

from .config import ROOT_DIR
from .database import init_db
from .outreach import dispatch_due


def main() -> None:
    init_db()
    pid_path = ROOT_DIR / "data" / "outreach_worker.pid"
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()), encoding="ascii")
    running = True

    def stop(*_: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        while running:
            result = dispatch_due()
            time.sleep(2 if result.get("sent") else 15)
    finally:
        try:
            if pid_path.exists() and pid_path.read_text(encoding="ascii").strip() == str(os.getpid()):
                pid_path.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()

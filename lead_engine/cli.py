from __future__ import annotations

import argparse
import json

from .config import ROOT_DIR
from .database import analytics, init_db
from .enrichment import enrich_batch
from .importer import import_csv_directory
from .outreach import dispatch_due, plan_outreach


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Lead Scout engine commands")
    parser.add_argument("command", choices=("init", "import", "enrich", "plan", "dispatch", "tick", "analytics"))
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()
    init_db()

    if args.command == "init":
        result = {"success": True, "message": "Database initialized"}
    elif args.command == "import":
        result = import_csv_directory(ROOT_DIR / "data" / "out")
    elif args.command == "enrich":
        result = enrich_batch(args.limit)
    elif args.command == "plan":
        result = plan_outreach()
    elif args.command == "dispatch":
        result = dispatch_due()
    elif args.command == "tick":
        plan = plan_outreach()
        dispatch = dispatch_due()
        result = {"plan": plan, "dispatch": dispatch}
    else:
        result = analytics()
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()

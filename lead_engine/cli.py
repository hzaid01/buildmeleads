from __future__ import annotations

import argparse
import json

from .config import ROOT_DIR
from .database import analytics, init_db
from .enrichment import enrich_batch
from .importer import import_csv_directory
from .outreach import dispatch_due, generate_batch


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Lead Scout engine commands")
    parser.add_argument("command", choices=("init", "import", "enrich", "generate", "dispatch", "analytics"))
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--user-id", default="")
    args = parser.parse_args()
    init_db()

    if args.command == "init":
        result = {"success": True, "message": "Database initialized"}
    elif args.command == "import":
        result = import_csv_directory(args.user_id, ROOT_DIR / "data" / "out")
    elif args.command == "enrich":
        result = enrich_batch(args.user_id, args.limit)
    elif args.command == "generate":
        result = generate_batch(args.user_id, args.limit)
    elif args.command == "dispatch":
        result = dispatch_due()
    else:
        result = analytics(args.user_id)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()

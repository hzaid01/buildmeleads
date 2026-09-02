from __future__ import annotations

import json

from lead_engine.database import LEGACY_OWNER_ID, connect, init_db


def main() -> None:
    init_db()
    with connect() as connection:
        legacy = connection.execute("SELECT COUNT(*) FROM leads WHERE user_id=?", (LEGACY_OWNER_ID,)).fetchone()[0]
        active_users = connection.execute("SELECT COUNT(*) FROM app_users WHERE status='active'").fetchone()[0]
        foreign_key_errors = [tuple(row) for row in connection.execute("PRAGMA foreign_key_check")]
        isolated = {}
        for table in ("leads","suppressions","campaigns","outreach_queue","send_logs","analytics_results","gmail_oauth_accounts","scrape_runs"):
            isolated[table] = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(json.dumps({"success":not foreign_key_errors,"legacyLeadsAwaitingFirstAdmin":legacy,
                      "activeUsers":active_users,"foreignKeyErrors":foreign_key_errors,"rows":isolated},indent=2))


if __name__ == "__main__":
    main()

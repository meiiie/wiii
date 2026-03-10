"""Enable Row-Level Security on org-scoped tables.

Run this script MANUALLY when ready for production RLS.
Prerequisites:
  1. Migration 023 applied (policies created but dormant)
  2. enable_rls=True in .env
  3. enable_multi_tenant=True in .env

Usage:
    python scripts/enable_rls.py              # Enable RLS
    python scripts/enable_rls.py --disable    # Disable RLS
"""
import argparse
import sys

from sqlalchemy import create_engine, text, inspect

ORG_SCOPED_TABLES = [
    "semantic_memories",
    "chat_history",
    "learning_profile",
    "scheduled_tasks",
    "wiii_emotional_snapshots",
    "wiii_skills",
    "wiii_journal",
    "wiii_browsing_log",
    "wiii_heartbeat_audit",
    "wiii_pending_actions",
    "thread_views",
    "user_preferences",
]


def main():
    parser = argparse.ArgumentParser(description="Enable/disable PostgreSQL RLS")
    parser.add_argument("--disable", action="store_true", help="Disable RLS instead of enabling")
    parser.add_argument("--database-url", default=None, help="Database URL (reads from .env if not set)")
    args = parser.parse_args()

    # Get database URL
    db_url = args.database_url
    if not db_url:
        try:
            from app.core.config import settings
            db_url = settings.postgres_url_sync
        except Exception:
            print("ERROR: Cannot load settings. Pass --database-url explicitly.")
            sys.exit(1)

    if "+psycopg" not in db_url and db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

    engine = create_engine(db_url)
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    action = "DISABLE" if args.disable else "ENABLE"

    with engine.begin() as conn:
        for table in ORG_SCOPED_TABLES:
            if table not in existing_tables:
                print(f"  SKIP {table} (not found)")
                continue

            conn.execute(text(f"ALTER TABLE {table} {action} ROW LEVEL SECURITY"))
            print(f"  {action} RLS on {table}")

    print(f"\nDone. RLS {action}D on {len(ORG_SCOPED_TABLES)} tables.")
    if not args.disable:
        print("Remember to set enable_rls=True in your .env file.")


if __name__ == "__main__":
    main()

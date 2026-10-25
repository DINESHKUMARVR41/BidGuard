import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load configuration here too: this module may be imported before main.py calls load_dotenv().
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
_raw_db_path = Path(os.getenv("BIDGUARD_DATABASE", "bidguard.db")).expanduser()
DB_PATH = str(_raw_db_path if _raw_db_path.is_absolute() else BASE_DIR / _raw_db_path)


@contextmanager
def db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db() as c:
        # Fail with a clear message instead of a confusing SQL error if an old database
        # has incompatible tables. Back it up and point BIDGUARD_DATABASE to a fresh file.
        expected = {
            "users": {"id", "email", "full_name", "password_hash", "created_at"},
            "company_profiles": {"user_id", "data", "updated_at"},
            "tenders": {"id", "user_id", "tender_key", "title", "source_url", "source_name", "retrieved_at"},
            "documents": {"id", "tender_id", "filename", "stored_path", "uploaded_at"},
        }
        existing = {r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        for table, required in expected.items():
            if table in existing:
                present = {r["name"] for r in c.execute(f'PRAGMA table_info("{table}")').fetchall()}
                missing = required - present
                if missing:
                    raise RuntimeError(
                        f"Database schema mismatch in '{table}' (missing: {', '.join(sorted(missing))}). "
                        f"Back up the old database and set BIDGUARD_DATABASE to a new SQLite filename in .env."
                    )

        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, full_name TEXT NOT NULL,
          password_hash TEXT NOT NULL, created_at TEXT NOT NULL, firebase_uid TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS sessions(
          token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires_at REAL NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS company_profiles(
          user_id INTEGER PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL,
          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS tenders(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, tender_key TEXT NOT NULL, title TEXT NOT NULL,
          tender_reference TEXT, authority TEXT, location TEXT, closing_date TEXT, estimated_value TEXT,
          source_url TEXT NOT NULL, source_name TEXT NOT NULL, retrieved_at TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'discovered', raw_text TEXT NOT NULL DEFAULT '',
          analysis_json TEXT NOT NULL DEFAULT '{}', UNIQUE(user_id,tender_key),
          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS documents(
          id INTEGER PRIMARY KEY AUTOINCREMENT, tender_id INTEGER NOT NULL, filename TEXT NOT NULL,
          stored_path TEXT NOT NULL, page_count INTEGER, uploaded_at TEXT NOT NULL,
          FOREIGN KEY(tender_id) REFERENCES tenders(id) ON DELETE CASCADE
        );
        """)

        # Safe additive migration for databases created before Firebase UID support.
        columns = {row["name"] for row in c.execute("PRAGMA table_info(users)").fetchall()}
        if "firebase_uid" not in columns:
            c.execute("ALTER TABLE users ADD COLUMN firebase_uid TEXT")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_firebase_uid ON users(firebase_uid)")

import os, sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("BIDGUARD_DATABASE", "bidguard.db")

@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS company(id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tenders(
          id INTEGER PRIMARY KEY AUTOINCREMENT, tender_key TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
          tender_reference TEXT, authority TEXT, location TEXT, closing_date TEXT, estimated_value TEXT,
          source_url TEXT NOT NULL, source_name TEXT NOT NULL, retrieved_at TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'discovered', raw_text TEXT NOT NULL DEFAULT '', analysis_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS documents(
          id INTEGER PRIMARY KEY AUTOINCREMENT, tender_id INTEGER NOT NULL, filename TEXT NOT NULL,
          stored_path TEXT NOT NULL, page_count INTEGER, uploaded_at TEXT NOT NULL,
          FOREIGN KEY(tender_id) REFERENCES tenders(id) ON DELETE CASCADE
        );
        """)

import os, sqlite3
from contextlib import contextmanager
DB_PATH=os.getenv("BIDGUARD_DATABASE","bidguard.db")
@contextmanager
def db():
    conn=sqlite3.connect(DB_PATH);conn.row_factory=sqlite3.Row
    try:
        yield conn;conn.commit()
    finally:conn.close()
def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT UNIQUE NOT NULL,full_name TEXT NOT NULL,password_hash TEXT NOT NULL,created_at TEXT NOT NULL,firebase_uid TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL,expires_at REAL NOT NULL,created_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS company_profiles(user_id INTEGER PRIMARY KEY,data TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS tenders(
          id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,tender_key TEXT NOT NULL,title TEXT NOT NULL,
          tender_reference TEXT,authority TEXT,location TEXT,closing_date TEXT,estimated_value TEXT,
          source_url TEXT NOT NULL,source_name TEXT NOT NULL,retrieved_at TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'discovered',
          raw_text TEXT NOT NULL DEFAULT '',analysis_json TEXT NOT NULL DEFAULT '{}',UNIQUE(user_id,tender_key),
          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY AUTOINCREMENT,tender_id INTEGER NOT NULL,filename TEXT NOT NULL,stored_path TEXT NOT NULL,page_count INTEGER,uploaded_at TEXT NOT NULL,FOREIGN KEY(tender_id) REFERENCES tenders(id) ON DELETE CASCADE);
        """)
        # Upgrade existing local databases without deleting existing company/tender data.
        columns = {row["name"] for row in c.execute("PRAGMA table_info(users)").fetchall()}
        if "firebase_uid" not in columns:
            c.execute("ALTER TABLE users ADD COLUMN firebase_uid TEXT")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_firebase_uid ON users(firebase_uid)")

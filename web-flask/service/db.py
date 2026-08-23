# SQLite 数据库
import os
import sqlite3
from contextlib import contextmanager
from config import DATABASE_PATH, WEB_FLASK_DIR


def _ensure_dir():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)


@contextmanager
def get_conn():
    _ensure_dir()
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    _ensure_dir()
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            real_name TEXT,
            phone TEXT UNIQUE,
            email TEXT,
            avatar TEXT,
            theme TEXT DEFAULT 'default',
            bio TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS sms_codes (
            phone TEXT NOT NULL,
            code TEXT NOT NULL,
            purpose TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS user_settings (
            username TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            PRIMARY KEY (username, key)
        );
        CREATE TABLE IF NOT EXISTS detection_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            model_name TEXT,
            total INTEGER DEFAULT 0,
            summary TEXT,
            detections_json TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS email_codes (
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            purpose TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_email_codes ON email_codes(email, purpose);
        """)
        _migrate_user_columns(conn)
        _migrate_sms_columns(conn)
        _migrate_user_role(conn)


def _migrate_user_role(conn):
    existing = {r[1] for r in conn.execute('PRAGMA table_info(users)').fetchall()}
    if 'role' not in existing:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
        conn.execute("UPDATE users SET role='admin' WHERE username='admin'")


def _migrate_sms_columns(conn):
    existing = {r[1] for r in conn.execute('PRAGMA table_info(sms_codes)').fetchall()}
    if 'out_id' not in existing:
        conn.execute('ALTER TABLE sms_codes ADD COLUMN out_id TEXT')


def _migrate_user_columns(conn):
    cols = {
        'gender': 'TEXT',
        'work_unit': 'TEXT',
        'department': 'TEXT',
        'address': 'TEXT',
        'postal_code': 'TEXT',
        'region': 'TEXT',
    }
    existing = {r[1] for r in conn.execute('PRAGMA table_info(users)').fetchall()}
    for name, typ in cols.items():
        if name not in existing:
            conn.execute(f'ALTER TABLE users ADD COLUMN {name} {typ}')


def row_to_user(row):
    if not row:
        return None
    role = row['role'] if 'role' in row.keys() and row['role'] else ('admin' if row['username'] == 'admin' else 'user')
    if role == 'admin':
        role_label = '管理员'
    elif role == 'member':
        role_label = '会员用户'
    else:
        role_label = '普通用户'
    return {
        'username': row['username'],
        'realName': row['real_name'] or row['username'],
        'role': role,
        'roleLabel': role_label,
        'isAdmin': role == 'admin',
        'isMember': role == 'member',
        'phone': row['phone'] or '',
        'email': row['email'] or '',
        'avatar': row['avatar'] or '',
        'theme': row['theme'] or 'default',
        'bio': row['bio'] or '',
        'gender': row['gender'] or '',
        'workUnit': row['work_unit'] or '',
        'department': row['department'] or '',
        'address': row['address'] or '',
        'postalCode': row['postal_code'] or '',
        'region': row['region'] or '',
        'phoneBound': bool(row['phone']),
        'emailBound': bool(row['email']),
        'createdAt': row['created_at'] or '',
    }


def public_user(row):
    u = row_to_user(row)
    if not u:
        return None
    u['id'] = u['username']
    return u

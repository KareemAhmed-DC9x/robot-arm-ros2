"""
database.py
===========
SQLite database layer for the ARM Control RBAC system.
Self-contained — no ORM dependencies.

Tables: users · permissions · sessions · logs
"""

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

# ── Storage paths ─────────────────────────────────────────────────
BASE_DIR     = Path.home() / 'arm_ws' / 'system'
DB_PATH      = BASE_DIR / 'data' / 'database.db'
AVATARS_DIR  = BASE_DIR / 'uploads' / 'profiles'
LOGS_DIR     = BASE_DIR / 'data' / 'logs'

for _d in [DB_PATH.parent, AVATARS_DIR, LOGS_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ── Role defaults ─────────────────────────────────────────────────
ALL_PAGES = ['control', 'monitor', 'admin', 'account', 'logs', 'sensor', 'robot_programmer']

ROLE_PAGES = {
    'admin':    ['control', 'monitor', 'admin', 'account', 'logs', 'sensor', 'robot_programmer'],
    'operator': ['control', 'monitor', 'account', 'sensor', 'robot_programmer'],
    'viewer':   ['monitor', 'account'],
}

PROTECTED_PAGES = {'admin'}   # non-admins can never get these via permissions


# ═══════════════════════════════════════════════════════════════════
#  CONNECTION
# ═══════════════════════════════════════════════════════════════════
@contextmanager
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA journal_mode = WAL')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════
#  SCHEMA
# ═══════════════════════════════════════════════════════════════════
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    username     TEXT    UNIQUE NOT NULL COLLATE NOCASE,
    password_hash TEXT   NOT NULL,
    display_name TEXT    DEFAULT '',
    email        TEXT    DEFAULT '',
    role         TEXT    DEFAULT 'viewer'   CHECK(role IN ('admin','operator','viewer')),
    status       TEXT    DEFAULT 'active'   CHECK(status IN ('active','inactive','suspended')),
    avatar       TEXT    DEFAULT NULL,
    created_at   REAL    DEFAULT (unixepoch()),
    last_login   REAL    DEFAULT NULL,
    last_ip      TEXT    DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS permissions (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL,
    page     TEXT    NOT NULL,
    granted  INTEGER DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, page)
);

CREATE TABLE IF NOT EXISTS sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    token      TEXT    UNIQUE NOT NULL,
    ip         TEXT,
    ua         TEXT,
    created_at REAL    DEFAULT (unixepoch()),
    last_seen  REAL    DEFAULT (unixepoch()),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS logs (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER,
    username TEXT,
    action   TEXT NOT NULL,
    details  TEXT DEFAULT '',
    ip       TEXT DEFAULT '',
    ts       REAL DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_sessions_token   ON sessions(token);
CREATE INDEX IF NOT EXISTS idx_sessions_user    ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_logs_user        ON logs(user_id);
CREATE INDEX IF NOT EXISTS idx_logs_ts          ON logs(ts);
CREATE INDEX IF NOT EXISTS idx_permissions_user ON permissions(user_id);
"""


def init_db():
    """Initialize schema and create default admin account."""
    with get_db() as db:
        db.executescript(SCHEMA)

    # Create default admin if no users exist
    if not get_all_users():
        from auth_rbac import hash_password
        create_user(
            username='admin',
            password_hash=hash_password('admin1234'),
            role='admin',
            display_name='Administrator',
        )
        log_action(None, 'system', 'INIT', 'Default admin account created', '')
        print('[DB] Default admin created  →  admin / admin1234')
        print('[DB] ⚠ Change the password immediately after first login!')


# ═══════════════════════════════════════════════════════════════════
#  USER QUERIES
# ═══════════════════════════════════════════════════════════════════
def create_user(username: str, password_hash: str, role: str = 'viewer',
                display_name: str = '', email: str = '') -> int:
    with get_db() as db:
        cur = db.execute(
            'INSERT INTO users (username, password_hash, role, display_name, email) '
            'VALUES (?,?,?,?,?)',
            (username, password_hash, role, display_name, email)
        )
        uid = cur.lastrowid
    _set_default_permissions(uid, role)
    return uid


def get_user_by_id(uid: int) -> sqlite3.Row | None:
    with get_db() as db:
        return db.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()


def get_user_by_username(username: str) -> sqlite3.Row | None:
    with get_db() as db:
        return db.execute('SELECT * FROM users WHERE username=? COLLATE NOCASE',
                          (username,)).fetchone()


def get_all_users() -> list:
    with get_db() as db:
        return db.execute(
            'SELECT id,username,display_name,email,role,status,avatar,created_at,last_login,last_ip '
            'FROM users ORDER BY created_at DESC'
        ).fetchall()


def update_user_profile(uid: int, display_name: str = None, email: str = None,
                        avatar: str = None):
    fields, vals = [], []
    if display_name is not None:
        fields.append('display_name=?'); vals.append(display_name[:80])
    if email is not None:
        fields.append('email=?'); vals.append(email[:120])
    if avatar is not None:
        fields.append('avatar=?'); vals.append(avatar)
    if not fields:
        return
    vals.append(uid)
    with get_db() as db:
        db.execute(f'UPDATE users SET {", ".join(fields)} WHERE id=?', vals)


def update_user_password(uid: int, password_hash: str):
    with get_db() as db:
        db.execute('UPDATE users SET password_hash=? WHERE id=?', (password_hash, uid))


def update_user_role(uid: int, role: str):
    with get_db() as db:
        db.execute('UPDATE users SET role=? WHERE id=?', (role, uid))
    _set_default_permissions(uid, role)


def update_user_status(uid: int, status: str):
    with get_db() as db:
        db.execute('UPDATE users SET status=? WHERE id=?', (status, uid))


def update_last_login(uid: int, ip: str):
    with get_db() as db:
        db.execute('UPDATE users SET last_login=?, last_ip=? WHERE id=?',
                   (time.time(), ip, uid))


def delete_user(uid: int):
    with get_db() as db:
        db.execute('DELETE FROM users WHERE id=?', (uid,))


def admin_update_user(uid: int, data: dict):
    """Bulk update by admin — role, status, display_name, email."""
    allowed = {'role', 'status', 'display_name', 'email'}
    fields, vals = [], []
    for k, v in data.items():
        if k in allowed:
            fields.append(f'{k}=?')
            vals.append(v)
    if not fields:
        return
    vals.append(uid)
    with get_db() as db:
        db.execute(f'UPDATE users SET {", ".join(fields)} WHERE id=?', vals)
    if 'role' in data:
        _set_default_permissions(uid, data['role'])


# ═══════════════════════════════════════════════════════════════════
#  PERMISSIONS
# ═══════════════════════════════════════════════════════════════════
def _set_default_permissions(uid: int, role: str):
    pages = ROLE_PAGES.get(role, [])
    with get_db() as db:
        db.execute('DELETE FROM permissions WHERE user_id=?', (uid,))
        for page in ALL_PAGES:
            granted = 1 if page in pages else 0
            db.execute(
                'INSERT INTO permissions (user_id, page, granted) VALUES (?,?,?)',
                (uid, page, granted)
            )


def get_user_permissions(uid: int) -> dict:
    """Returns {page: bool}."""
    with get_db() as db:
        rows = db.execute(
            'SELECT page, granted FROM permissions WHERE user_id=?', (uid,)
        ).fetchall()
    return {r['page']: bool(r['granted']) for r in rows}


def set_user_permission(uid: int, page: str, granted: bool, actor_role: str):
    """Admin sets a single permission. Admins cannot lose admin/logs pages."""
    if page in PROTECTED_PAGES and actor_role != 'admin':
        return   # non-admins can't touch protected pages
    with get_db() as db:
        db.execute(
            'INSERT INTO permissions (user_id, page, granted) VALUES (?,?,?) '
            'ON CONFLICT(user_id, page) DO UPDATE SET granted=excluded.granted',
            (uid, page, 1 if granted else 0)
        )


def set_all_permissions(uid: int, pages: list, actor_role: str):
    """Admin sets the full permission list for a user."""
    user = get_user_by_id(uid)
    if not user:
        return
    with get_db() as db:
        db.execute('DELETE FROM permissions WHERE user_id=?', (uid,))
        for page in ALL_PAGES:
            g = page in pages
            # Protect admin/logs pages — only admins can have them
            if page in PROTECTED_PAGES and user['role'] != 'admin':
                g = False
            db.execute(
                'INSERT INTO permissions (user_id, page, granted) VALUES (?,?,?)',
                (uid, page, 1 if g else 0)
            )


def user_can(uid: int, page: str, role: str) -> bool:
    """Fast permission check. Admins always get admin pages."""
    if role == 'admin':
        return True
    if page in PROTECTED_PAGES:
        return False
    perms = get_user_permissions(uid)
    return perms.get(page, False)


# ═══════════════════════════════════════════════════════════════════
#  SESSIONS
# ═══════════════════════════════════════════════════════════════════
def create_session(uid: int, token: str, ip: str, ua: str):
    with get_db() as db:
        db.execute(
            'INSERT INTO sessions (user_id, token, ip, ua) VALUES (?,?,?,?)',
            (uid, token, ip, ua[:200])
        )


def get_session(token: str) -> sqlite3.Row | None:
    with get_db() as db:
        sess = db.execute(
            'SELECT s.*, u.username, u.role, u.status '
            'FROM sessions s JOIN users u ON s.user_id=u.id '
            'WHERE s.token=?', (token,)
        ).fetchone()
    if sess:
        # Touch last_seen
        with get_db() as db:
            db.execute('UPDATE sessions SET last_seen=? WHERE token=?',
                       (time.time(), token))
    return sess


def delete_session(token: str):
    with get_db() as db:
        db.execute('DELETE FROM sessions WHERE token=?', (token,))


def delete_all_user_sessions(uid: int):
    with get_db() as db:
        db.execute('DELETE FROM sessions WHERE user_id=?', (uid,))


def delete_session_by_id(sess_id: int, uid: int):
    with get_db() as db:
        db.execute('DELETE FROM sessions WHERE id=? AND user_id=?', (sess_id, uid))


def get_user_sessions(uid: int) -> list:
    with get_db() as db:
        return db.execute(
            'SELECT id, ip, ua, created_at, last_seen FROM sessions '
            'WHERE user_id=? ORDER BY last_seen DESC', (uid,)
        ).fetchall()


# ═══════════════════════════════════════════════════════════════════
#  LOGS
# ═══════════════════════════════════════════════════════════════════
def log_action(uid, username: str, action: str, details: str = '', ip: str = ''):
    with get_db() as db:
        db.execute(
            'INSERT INTO logs (user_id, username, action, details, ip) VALUES (?,?,?,?,?)',
            (uid, username, action, details, ip)
        )


def get_logs(limit: int = 200, username: str = None, action: str = None) -> list:
    sql  = 'SELECT * FROM logs WHERE 1=1'
    args = []
    if username:
        sql  += ' AND username LIKE ?'; args.append(f'%{username}%')
    if action:
        sql  += ' AND action=?';        args.append(action)
    sql += ' ORDER BY ts DESC LIMIT ?'; args.append(limit)
    with get_db() as db:
        return db.execute(sql, args).fetchall()


def get_user_logs(uid: int, limit: int = 50) -> list:
    with get_db() as db:
        return db.execute(
            'SELECT * FROM logs WHERE user_id=? ORDER BY ts DESC LIMIT ?',
            (uid, limit)
        ).fetchall()


# ── Init on import ────────────────────────────────────────────────
init_db()

# ═══════════════════════════════════════════════════════════════════
#  PROGRAMS
# ═══════════════════════════════════════════════════════════════════
_PROG_SCHEMA = """
CREATE TABLE IF NOT EXISTS programs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    blocks      TEXT    NOT NULL,
    created_by  INTEGER,
    username    TEXT    NOT NULL DEFAULT 'unknown',
    created_at  REAL    DEFAULT (unixepoch()),
    updated_at  REAL    DEFAULT (unixepoch()),
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_programs_user ON programs(created_by);
"""

def _init_programs():
    with get_db() as db:
        db.executescript(_PROG_SCHEMA)

_init_programs()

def save_program(name: str, blocks_json: str, user_id: int, username: str) -> int:
    with get_db() as db:
        cur = db.execute(
            'INSERT INTO programs (name, blocks, created_by, username) VALUES (?,?,?,?)',
            (name, blocks_json, user_id, username)
        )
        return cur.lastrowid

def get_all_programs() -> list:
    with get_db() as db:
        return db.execute(
            'SELECT id, name, username, created_by, created_at, updated_at, '
            'length(blocks) as size FROM programs ORDER BY updated_at DESC'
        ).fetchall()

def get_program(program_id: int) -> sqlite3.Row | None:
    with get_db() as db:
        return db.execute('SELECT * FROM programs WHERE id=?', (program_id,)).fetchone()

def update_program(program_id: int, name: str, blocks_json: str, user_id: int) -> bool:
    with get_db() as db:
        cur = db.execute(
            'UPDATE programs SET name=?, blocks=?, updated_at=unixepoch() '
            'WHERE id=? AND created_by=?',
            (name, blocks_json, program_id, user_id)
        )
        return cur.rowcount > 0

def delete_program(program_id: int, user_id: int, role: str) -> bool:
    with get_db() as db:
        if role == 'admin':
            cur = db.execute('DELETE FROM programs WHERE id=?', (program_id,))
        else:
            cur = db.execute('DELETE FROM programs WHERE id=? AND created_by=?',
                             (program_id, user_id))
        return cur.rowcount > 0

"""
auth_rbac.py
============
Authentication helpers + RBAC decorators for Flask routes.
"""

import hashlib
import hmac
import os
import secrets
import time
from functools import wraps

from flask import jsonify, redirect, request, session

import database as db


# ═══════════════════════════════════════════════════════════════════
#  PASSWORD HASHING  (PBKDF2-SHA256, 260k iterations)
# ═══════════════════════════════════════════════════════════════════
_ITERATIONS = 260_000
_ALGO       = 'sha256'


def hash_password(password: str) -> str:
    salt  = secrets.token_hex(16)
    dk    = hashlib.pbkdf2_hmac(_ALGO, password.encode(), salt.encode(), _ITERATIONS)
    return f'pbkdf2:{_ALGO}:{_ITERATIONS}${salt}${dk.hex()}'


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        _meta, salt, dk_hex = stored_hash.split('$')
        _, algo, iters      = _meta.split(':')
        dk = hashlib.pbkdf2_hmac(
            algo, password.encode(), salt.encode(), int(iters)
        )
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════
#  SESSION
# ═══════════════════════════════════════════════════════════════════
SESSION_COOKIE = 'arm_token'
SESSION_TTL    = 8 * 3600   # 8 hours


def _client_ip() -> str:
    return request.headers.get('X-Forwarded-For', request.remote_addr) or ''


def _client_ua() -> str:
    return (request.headers.get('User-Agent') or '')[:200]


def login_user(uid: int) -> str:
    """Create a new DB session token, store in Flask session cookie."""
    token = secrets.token_hex(32)
    db.create_session(uid, token, _client_ip(), _client_ua())
    session.clear()
    session[SESSION_COOKIE] = token
    return token


def logout_user():
    token = session.get(SESSION_COOKIE)
    if token:
        db.delete_session(token)
    session.clear()


def get_current_user() -> dict | None:
    """Return full user+session dict or None."""
    token = session.get(SESSION_COOKIE)
    if not token:
        return None
    sess = db.get_session(token)
    if not sess:
        return None
    # Session TTL check
    if time.time() - sess['created_at'] > SESSION_TTL:
        db.delete_session(token)
        session.clear()
        return None
    # Account must be active
    if sess['status'] != 'active':
        return None
    return dict(sess)


# ═══════════════════════════════════════════════════════════════════
#  BRUTE-FORCE PROTECTION  (in-memory, resets on restart)
# ═══════════════════════════════════════════════════════════════════
_FAIL_STORE: dict = {}   # {ip: {'count': int, 'locked_until': float}}
MAX_ATTEMPTS  = 6
LOCKOUT_SEC   = 120


def is_ip_locked(ip: str) -> tuple[bool, int]:
    """(locked, seconds_remaining)"""
    entry = _FAIL_STORE.get(ip)
    if not entry:
        return False, 0
    remaining = entry.get('locked_until', 0) - time.time()
    return remaining > 0, int(remaining)


def record_fail(ip: str) -> tuple[int, bool]:
    """Returns (attempts_remaining, just_locked)."""
    e = _FAIL_STORE.setdefault(ip, {'count': 0, 'locked_until': 0})
    e['count'] += 1
    if e['count'] >= MAX_ATTEMPTS:
        e['locked_until'] = time.time() + LOCKOUT_SEC
        e['count'] = 0
        return 0, True
    return MAX_ATTEMPTS - e['count'], False


def clear_fails(ip: str):
    _FAIL_STORE.pop(ip, None)


# ═══════════════════════════════════════════════════════════════════
#  DECORATORS
# ═══════════════════════════════════════════════════════════════════
def require_login(f):
    """Require authenticated session. Redirects to /login or 401 JSON."""
    @wraps(f)
    def wrapper(*a, **kw):
        user = get_current_user()
        if not user:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'ok': False, 'message': 'Unauthorized'}), 401
            return redirect('/login')
        return f(*a, **kw)
    return wrapper


def require_page(page: str):
    """Require login AND permission to a specific page."""
    def decorator(f):
        @wraps(f)
        def wrapper(*a, **kw):
            user = get_current_user()
            if not user:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'ok': False, 'message': 'Unauthorized'}), 401
                return redirect('/login')
            if not db.user_can(user['user_id'], page, user['role']):
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'ok': False, 'message': 'Access denied'}), 403
                return redirect('/denied')
            return f(*a, **kw)
        return wrapper
    return decorator


def require_role(*roles):
    """Require login AND specific role(s)."""
    def decorator(f):
        @wraps(f)
        def wrapper(*a, **kw):
            user = get_current_user()
            if not user:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'ok': False, 'message': 'Unauthorized'}), 401
                return redirect('/login')
            if user['role'] not in roles:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'ok': False, 'message': 'Forbidden — insufficient role'}), 403
                return redirect('/denied')
            return f(*a, **kw)
        return wrapper
    return decorator

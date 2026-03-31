import json
import hashlib
import secrets
import os
from flask import Blueprint, request, jsonify
from backend.db import use_db

auth_bp = Blueprint('auth', __name__)


def _hash_password(password, salt=None):
    """Hash password with PBKDF2-SHA256."""
    if salt is None:
        salt = os.urandom(32)
    elif isinstance(salt, str):
        salt = bytes.fromhex(salt)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return salt.hex() + ':' + dk.hex()


def _verify_password(password, stored_hash):
    """Verify password against stored hash."""
    salt_hex, _ = stored_hash.split(':', 1)
    return _hash_password(password, salt_hex) == stored_hash


def _get_user_from_token(req):
    """Extract and validate user from auth token."""
    token = req.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return None
    with use_db() as db:
        row = db.execute("""
            SELECT u.id, u.email, u.name, u.profile_data, u.user_data, u.created_at
            FROM user_sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ? AND s.created_at > datetime('now', '-30 days')
        """, (token,)).fetchone()
        return dict(row) if row else None


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password', '')
    name = (data.get('name') or '').strip()

    if not email or '@' not in email or '.' not in email.split('@')[-1]:
        return jsonify({'error': 'Please enter a valid email address'}), 400
    if len(email) > 254:
        return jsonify({'error': 'Email address is too long'}), 400
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    if len(name) > 100:
        return jsonify({'error': 'Name is too long (max 100 characters)'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    if len(password) > 128:
        return jsonify({'error': 'Password is too long (max 128 characters)'}), 400

    password_hash = _hash_password(password)

    with use_db() as db:
        # Check if email already exists
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            return jsonify({'error': 'Email already registered'}), 409

        cur = db.execute(
            "INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)",
            (email, password_hash, name)
        )
        user_id = cur.lastrowid

        # Create session token
        token = secrets.token_hex(32)
        db.execute(
            "INSERT INTO user_sessions (token, user_id) VALUES (?, ?)",
            (token, user_id)
        )
        db.commit()

    return jsonify({
        'token': token,
        'user': {
            'id': user_id,
            'email': email,
            'name': name,
            'profile': {},
            'data': {}
        }
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    with use_db() as db:
        row = db.execute(
            "SELECT id, email, name, password_hash, profile_data, user_data FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if not row or not _verify_password(password, row['password_hash']):
            return jsonify({'error': 'Invalid email or password'}), 401

        # Create session token
        token = secrets.token_hex(32)
        db.execute(
            "INSERT INTO user_sessions (token, user_id) VALUES (?, ?)",
            (token, row['id'])
        )
        db.commit()

    profile = json.loads(row['profile_data'] or '{}')
    user_data = json.loads(row['user_data'] or '{}')

    return jsonify({
        'token': token,
        'user': {
            'id': row['id'],
            'email': row['email'],
            'name': row['name'],
            'profile': profile,
            'data': user_data
        }
    })


@auth_bp.route('/me', methods=['GET'])
def get_me():
    user = _get_user_from_token(request)
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401

    profile = json.loads(user['profile_data'] or '{}')
    user_data = json.loads(user['user_data'] or '{}')

    return jsonify({
        'user': {
            'id': user['id'],
            'email': user['email'],
            'name': user['name'],
            'profile': profile,
            'data': user_data
        }
    })


@auth_bp.route('/profile', methods=['PUT'])
def update_profile():
    """Save the user's fitness profile (weight, height, macros, etc.)."""
    user = _get_user_from_token(request)
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json() or {}
    profile = data.get('profile', {})

    with use_db() as db:
        db.execute(
            "UPDATE users SET profile_data = ?, name = COALESCE(?, name), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (json.dumps(profile), data.get('name'), user['id'])
        )
        db.commit()

    return jsonify({'message': 'Profile saved'})


@auth_bp.route('/sync', methods=['PUT'])
def sync_data():
    """Sync all user data (logs, workouts, body, preferences, etc.) to the server."""
    user = _get_user_from_token(request)
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401

    from config import MAX_SYNC_SIZE_BYTES
    content_length = request.content_length or 0
    if content_length > MAX_SYNC_SIZE_BYTES:
        return jsonify({'error': 'Sync payload too large'}), 413

    data = request.get_json() or {}
    user_data = data.get('data', {})

    with use_db() as db:
        db.execute(
            "UPDATE users SET user_data = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (json.dumps(user_data), user['id'])
        )
        db.commit()

    return jsonify({'message': 'Data synced'})


@auth_bp.route('/logout', methods=['POST'])
def logout():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token:
        with use_db() as db:
            db.execute("DELETE FROM user_sessions WHERE token = ?", (token,))
            db.commit()
    return jsonify({'message': 'Logged out'})

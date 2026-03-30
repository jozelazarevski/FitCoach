"""
FitCoach Backend Server
Serves the frontend app + REST API for recipes, coaching, and admin.

Usage:
    python app.py [--port 5000] [--debug]
"""

import logging
import time
from collections import defaultdict
from flask import Flask, send_from_directory, jsonify, request
from backend.db import init_db
from backend.api.recipes import recipes_bp
from backend.api.admin import admin_bp
from backend.api.auth import auth_bp
from config import SECRET_KEY, CORS_ORIGINS

logging.basicConfig(level=logging.INFO)

# Allowed static directories - never serve project root directly
STATIC_DIRS = {'js', 'css', 'admin'}

app = Flask(__name__)

app.config['SECRET_KEY'] = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max request size

# Register API blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(recipes_bp, url_prefix='/api/recipes')
app.register_blueprint(admin_bp, url_prefix='/api/admin')


# ---------------------------------------------------------------------------
#  Simple in-memory rate limiter
# ---------------------------------------------------------------------------
_rate_limit_store = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMITS = {
    '/api/auth/login': 10,
    '/api/auth/register': 5,
    '/api/admin/login': 5,
    '/api/recipes/suggest-llm': 10,
    '/api/recipes/generate-llm': 10,
    '/api/recipes/meal-plan-llm': 5,
}


def _check_rate_limit(key, limit):
    """Return True if request should be rate-limited."""
    now = time.time()
    timestamps = _rate_limit_store[key]
    # Prune old entries
    _rate_limit_store[key] = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]
    if len(_rate_limit_store[key]) >= limit:
        return True
    _rate_limit_store[key].append(now)
    return False


@app.before_request
def rate_limit():
    path = request.path
    if path in RATE_LIMITS and request.method in ('POST', 'PUT'):
        client_ip = request.remote_addr or 'unknown'
        key = f"{client_ip}:{path}"
        if _check_rate_limit(key, RATE_LIMITS[path]):
            return jsonify({'error': 'Too many requests. Please try again later.'}), 429


# ---------------------------------------------------------------------------
#  CORS + security headers
# ---------------------------------------------------------------------------
def _get_cors_origin():
    """Return the appropriate CORS origin header value."""
    if CORS_ORIGINS == '*':
        return '*'
    allowed = [o.strip() for o in CORS_ORIGINS.split(',')]
    origin = request.headers.get('Origin', '')
    if origin in allowed:
        return origin
    return None


@app.after_request
def add_security_headers(response):
    # Security headers on all responses
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

    # CORS headers on API routes
    if request.path.startswith('/api/'):
        cors_origin = _get_cors_origin()
        if cors_origin:
            response.headers['Access-Control-Allow-Origin'] = cors_origin
            if cors_origin != '*':
                response.headers['Vary'] = 'Origin'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Admin-Token, Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    return response


# Handle CORS preflight
@app.route('/api/<path:path>', methods=['OPTIONS'])
def cors_preflight(path):
    response = jsonify({'ok': True})
    return response


# Serve frontend
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/admin')
@app.route('/admin/')
def admin_panel():
    return send_from_directory('admin', 'index.html')


@app.route('/manifest.json')
def manifest():
    return send_from_directory('.', 'manifest.json')


@app.route('/sw.js')
def service_worker():
    return send_from_directory('.', 'sw.js')


@app.route('/icons/<path:filename>')
def serve_icons(filename):
    return send_from_directory('icons', filename)


# Serve only whitelisted static directories
@app.route('/js/<path:filename>')
def serve_js(filename):
    return send_from_directory('js', filename)


@app.route('/css/<path:filename>')
def serve_css(filename):
    return send_from_directory('css', filename)


@app.route('/admin/<path:filename>')
def serve_admin(filename):
    return send_from_directory('admin', filename)


# Health check
@app.route('/api/health')
def health():
    from backend.db import use_db
    try:
        with use_db() as db:
            count = db.execute("SELECT COUNT(*) FROM recipes WHERE status = 'active'").fetchone()[0]
        return jsonify({'status': 'ok', 'recipes_count': count})
    except Exception as e:
        logging.error("Health check failed: %s", e)
        return jsonify({'status': 'error', 'error': str(e)}), 500


# Error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()

    init_db()
    print(f"FitCoach server starting on http://localhost:{args.port}")
    print(f"Admin panel: http://localhost:{args.port}/admin")
    app.run(host='0.0.0.0', port=args.port, debug=args.debug)

"""
FitCoach Backend Server
Serves the frontend app + REST API for recipes, coaching, and admin.

Usage:
    python app.py [--port 5000] [--debug]
"""

import logging
import secrets
import time
import uuid
from collections import defaultdict
from flask import Flask, send_from_directory, jsonify, request, g
from backend.db import init_db
from backend.api.recipes import recipes_bp
from backend.api.admin import admin_bp
from backend.api.auth import auth_bp
from backend.logging_config import setup_logging
from config import SECRET_KEY, CORS_ORIGINS, ENVIRONMENT

setup_logging(env=ENVIRONMENT)

# Allowed static directories - never serve project root directly
STATIC_DIRS = {'js', 'css', 'admin'}

app = Flask(__name__)

app.config['SECRET_KEY'] = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max request size

# Register API blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(recipes_bp, url_prefix='/api/recipes')
app.register_blueprint(admin_bp, url_prefix='/api/admin')

logger = logging.getLogger(__name__)


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
def attach_request_metadata():
    """Attach request ID and start time for structured logging."""
    g.request_id = request.headers.get('X-Request-ID', str(uuid.uuid4())[:8])
    g.request_start = time.time()


@app.before_request
def rate_limit():
    path = request.path
    if path in RATE_LIMITS and request.method in ('POST', 'PUT'):
        client_ip = request.remote_addr or 'unknown'
        key = f"{client_ip}:{path}"
        if _check_rate_limit(key, RATE_LIMITS[path]):
            logger.warning("Rate limit exceeded", extra={
                'client_ip': client_ip, 'endpoint': path, 'request_id': getattr(g, 'request_id', '')
            })
            return jsonify({'error': 'Too many requests. Please try again later.'}), 429


@app.before_request
def csrf_protection():
    """Validate CSRF token on state-changing requests from browser sessions."""
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return
    if not request.path.startswith('/api/'):
        return
    # API requests with Authorization or X-Admin-Token headers are exempt (non-browser clients)
    if request.headers.get('Authorization') or request.headers.get('X-Admin-Token'):
        return
    # Validate Origin header to prevent cross-site request forgery
    origin = request.headers.get('Origin')
    if origin and CORS_ORIGINS != '*':
        allowed = [o.strip() for o in CORS_ORIGINS.split(',')]
        if origin not in allowed:
            return jsonify({'error': 'CSRF validation failed: origin not allowed'}), 403


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
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    if ENVIRONMENT == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

    # CORS headers on API routes
    if request.path.startswith('/api/'):
        cors_origin = _get_cors_origin()
        if cors_origin:
            response.headers['Access-Control-Allow-Origin'] = cors_origin
            if cors_origin != '*':
                response.headers['Vary'] = 'Origin'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Admin-Token, Authorization, X-Request-ID'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'

    return response


@app.after_request
def log_request(response):
    """Log each request with timing and status for observability."""
    if request.path in ('/api/health', '/favicon.ico'):
        return response
    duration_ms = round((time.time() - getattr(g, 'request_start', time.time())) * 1000, 1)
    logger.info(
        "%s %s %s %.1fms",
        request.method, request.path, response.status_code, duration_ms,
        extra={
            'request_id': getattr(g, 'request_id', ''),
            'method': request.method,
            'endpoint': request.path,
            'status_code': response.status_code,
            'duration_ms': duration_ms,
            'client_ip': request.remote_addr,
        }
    )
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
    checks = {}
    overall = 'ok'

    # Database check
    try:
        with use_db() as db:
            count = db.execute("SELECT COUNT(*) FROM recipes WHERE status = 'active'").fetchone()[0]
            user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        checks['database'] = {'status': 'ok', 'recipes': count, 'users': user_count}
    except Exception as e:
        checks['database'] = {'status': 'error', 'error': str(e)}
        overall = 'degraded'

    # LLM provider check
    try:
        from backend.llm_client import _get_provider_config
        config = _get_provider_config()
        if config:
            checks['llm'] = {'status': 'ok', 'provider': config['provider'], 'model': config.get('model', 'unknown')}
        else:
            checks['llm'] = {'status': 'unavailable', 'message': 'No LLM provider configured'}
    except Exception as e:
        checks['llm'] = {'status': 'error', 'error': str(e)}

    status_code = 200 if overall == 'ok' else 503
    return jsonify({'status': overall, 'environment': ENVIRONMENT, 'checks': checks}), status_code


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

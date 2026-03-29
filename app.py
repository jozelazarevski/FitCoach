"""
FitCoach Backend Server
Serves the frontend app + REST API for recipes, coaching, and admin.

Usage:
    python app.py [--port 5000] [--debug]
"""

from flask import Flask, send_from_directory, jsonify, request
from backend.db import init_db
from backend.api.recipes import recipes_bp
from backend.api.admin import admin_bp
import os

# Allowed static directories - never serve project root directly
STATIC_DIRS = {'js', 'css', 'admin'}

app = Flask(__name__)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fitcoach-dev-key')

# Register API blueprints
app.register_blueprint(recipes_bp, url_prefix='/api/recipes')
app.register_blueprint(admin_bp, url_prefix='/api/admin')


# CORS support for API routes
@app.after_request
def add_cors_headers(response):
    if request.path.startswith('/api/'):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Admin-Token'
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

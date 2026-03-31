import os
import secrets

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
#  Environment (development | staging | production)
# ---------------------------------------------------------------------------
ENVIRONMENT = os.getenv('FITCOACH_ENV', 'development')

# ---------------------------------------------------------------------------
#  Core settings
# ---------------------------------------------------------------------------
DB_PATH = os.getenv('FITCOACH_DB', os.path.join(_PROJECT_DIR, 'fitcoach.db'))
def _get_or_create_secret_key():
    """Get SECRET_KEY from env, or generate and persist one to .secret_key file."""
    env_key = os.getenv('SECRET_KEY')
    if env_key:
        return env_key
    key_file = os.path.join(_PROJECT_DIR, '.secret_key')
    try:
        with open(key_file, 'r') as f:
            key = f.read().strip()
            if key:
                return key
    except FileNotFoundError:
        pass
    key = secrets.token_hex(32)
    try:
        with open(key_file, 'w') as f:
            f.write(key)
    except OSError:
        pass
    return key


SECRET_KEY = _get_or_create_secret_key()
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'fitcoach-admin')
CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*' if ENVIRONMENT == 'development' else '')
MAX_SYNC_SIZE_BYTES = int(os.getenv('MAX_SYNC_SIZE_BYTES', 5 * 1024 * 1024))  # 5MB default

# ---------------------------------------------------------------------------
#  LLM provider settings (model versions pinned in config, not source code)
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
ANTHROPIC_MODEL = os.getenv('ANTHROPIC_MODEL', 'claude-haiku-4-5-20251001')
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.1')

# ---------------------------------------------------------------------------
#  Tuning
# ---------------------------------------------------------------------------
RECIPES_PER_API_CALL = 5
MAX_RETRIES = 3

# ---------------------------------------------------------------------------
#  Admin password safety check
# ---------------------------------------------------------------------------
if ENVIRONMENT == 'production' and ADMIN_PASSWORD == 'fitcoach-admin':
    import warnings
    warnings.warn(
        "SECURITY: Default admin password in production! Set ADMIN_PASSWORD env var.",
        stacklevel=1,
    )

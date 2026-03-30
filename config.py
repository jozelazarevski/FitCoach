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
SECRET_KEY = os.getenv('SECRET_KEY') or secrets.token_hex(32)
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'fitcoach-admin')
CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*' if ENVIRONMENT == 'development' else '')
MAX_SYNC_SIZE_BYTES = int(os.getenv('MAX_SYNC_SIZE_BYTES', 5 * 1024 * 1024))  # 5MB default

# ---------------------------------------------------------------------------
#  LLM provider settings (model versions pinned in config, not source code)
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
ANTHROPIC_MODEL = os.getenv('ANTHROPIC_MODEL', 'claude-3-5-haiku-20241022')
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

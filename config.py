import os
import secrets

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv('FITCOACH_DB', os.path.join(_PROJECT_DIR, 'fitcoach.db'))
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.1')
SECRET_KEY = os.getenv('SECRET_KEY') or secrets.token_hex(32)
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'fitcoach-admin')
CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*')  # comma-separated origins, or '*' for dev
MAX_SYNC_SIZE_BYTES = int(os.getenv('MAX_SYNC_SIZE_BYTES', 5 * 1024 * 1024))  # 5MB default
RECIPES_PER_API_CALL = 5
MAX_RETRIES = 3

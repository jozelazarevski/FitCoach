import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv('FITCOACH_DB', os.path.join(_PROJECT_DIR, 'fitcoach.db'))
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
SECRET_KEY = os.getenv('SECRET_KEY', 'fitcoach-dev-key-change-in-production')
RECIPES_PER_API_CALL = 10
MAX_RETRIES = 3

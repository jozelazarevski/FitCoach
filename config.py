import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DB_PATH = os.getenv('FITCOACH_DB', 'fitcoach.db')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
SECRET_KEY = os.getenv('SECRET_KEY', 'fitcoach-dev-key-change-in-production')
RECIPES_PER_API_CALL = 10
MAX_RETRIES = 3

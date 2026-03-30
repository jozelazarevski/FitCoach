# CLAUDE.md

## Project Overview

FitCoach is an AI-powered fitness macro tracking PWA. It provides personalized recipe recommendations, AI-driven meal planning, multi-method food logging (text, photo, barcode, voice), and nutritional tracking. Full-stack Python + vanilla JS with offline-first architecture.

## Tech Stack

- **Backend**: Flask 3.0+, SQLite with WAL mode, parameterized queries (no ORM for core DB)
- **Frontend**: Vanilla HTML/CSS/JavaScript (no framework), client-side SQLite via sql.js
- **AI**: Anthropic Claude API (primary) + Ollama (local fallback) via unified `backend/llm_client.py`
- **Validation**: Pydantic 2.0+ for LLM response validation (`backend/validation.py`)
- **PWA**: Service worker (`sw.js`, cache v15) + `manifest.json`, offline-first
- **Deployment**: Docker (multi-stage, Python 3.12-slim), Fly.io, Render, Heroku, Gunicorn

## Commands

- **Dev server**: `python app.py --port 5000 --debug`
- **Production**: `python start.py && gunicorn app:app --bind 0.0.0.0:5000 --workers 2 --timeout 120`
- **Docker**: `docker build -t fitcoach . && docker run -p 5000:5000 fitcoach`
- **Import recipes**: `python import_recipes.py recipes.json` (add `--dry-run` to validate only)
- **Seed DB**: `python -m backend.seed_recipes` (30 hand-crafted starter recipes)
- **Batch generate**: `python -m backend.recipe_generator --batch-size 10 --max-items 100`
- **Lint**: `ruff check .` and `ruff format --check .`
- **Lint (fix)**: `ruff check --fix . && ruff format .`
- **Pre-commit setup**: `pre-commit install`

## Project Structure

```
app.py                  # Flask app: routes, middleware, rate limiting, CSRF, security headers
config.py               # Environment-aware config (dev/staging/prod), LLM model versions
start.py                # Initialization script (seeds DB if empty, starts gunicorn)
index.html              # Main SPA HTML shell
backend/
  db.py                 # SQLite schema, connection management, WAL mode
  models.py             # Recipe queries, suggestion engine (multi-factor scoring)
  tag_engine.py         # Deterministic + LLM-based recipe tagging (10 dimensions)
  llm_client.py         # Unified LLM interface (Anthropic Claude + Ollama fallback)
  validation.py         # Pydantic models for LLM response validation
  logging_config.py     # Structured JSON logging (production) / dev formatter
  recipe_generator.py   # Batch recipe generation (3000+ via Claude, resumable)
  seed_recipes.py       # 30 starter recipes for initial DB population
  api/
    recipes.py          # Recipe CRUD, suggestions, LLM generation endpoints
    admin.py            # Admin management, batch generation control
    auth.py             # User auth, profile sync, session management
admin/
  index.html            # Admin dashboard (stats, recipe CRUD, API keys, batch gen)
  admin.js              # Admin panel JS
js/
  app.js                # Main app controller, screen navigation
  auth.js               # Login/registration, token management
  tracker.js            # Food logging (text, photo, barcode, voice)
  coach.js              # AI coaching screen, meal suggestions
  recipes.js            # Recipe browsing and details
  profile.js            # User profile, goal setting, preferences
  body.js               # Body metrics, weight tracking, workouts
  llm.js                # LLM API calls (local or cloud)
  db.js                 # Client-side SQLite (sql.js) operations
  storage.js            # IndexedDB storage layer
  ui.js                 # UI utilities
  config.js             # API_URL config
css/
  style.css             # Full stylesheet (~40KB), CSS variables, responsive, dark mode
data/
  recipes.json          # Recipe data store
tools/scraper/
  recipe_scraper.py     # AllRecipes.com scraper (requests + BeautifulSoup)
```

## Key API Routes

**Auth** (`/api/auth/`):
- `POST /register`, `POST /login` (rate limited), `GET /me`, `PUT /profile`, `PUT /sync`, `POST /logout`

**Recipes** (`/api/recipes/`):
- `GET /` — list with filters (meal_type, cuisine, max_calories, etc.)
- `GET /<id>` — single recipe, `GET /<id>/similar` — similar recipes
- `POST /suggest` — DB-based suggestions (free)
- `POST /suggest-llm` — LLM-powered suggestions (paid, cached, Pydantic-validated)
- `POST /generate-llm` — full recipe generation via LLM (Pydantic-validated)
- `POST /meal-plan` — 7-day plan from DB
- `POST /meal-plan-llm` — 7-day plan via LLM (Pydantic-validated)

**Admin** (`/api/admin/`):
- `POST /login`, `GET /stats`, `GET /llm-savings`, `GET /tags`
- Recipe CRUD, API key management, batch generation start/status

**Health** (`/api/health`):
- Returns DB status (recipe/user count), LLM provider status (provider, model), environment

## Environment Variables

- `FITCOACH_ENV` — `development` | `staging` | `production` (default: development)
- `FITCOACH_DB` — SQLite path (default: fitcoach.db)
- `SECRET_KEY` — Flask session key (auto-generated if not set)
- `ADMIN_PASSWORD` — Admin login (default: fitcoach-admin; warns in production if default)
- `CORS_ORIGINS` — Allowed origins or `*` (auto `*` in dev, empty in prod)
- `ANTHROPIC_API_KEY` — Claude API key (optional, settable via admin)
- `ANTHROPIC_MODEL` — Claude model version (default: claude-3-5-haiku-20241022)
- `OLLAMA_BASE_URL` — Local Ollama URL (default: http://localhost:11434)
- `OLLAMA_MODEL` — Ollama model (default: llama3.1)
- `PORT` — Server port (default: 5000)

See `.env.example` for a template.

## Code Quality

- **Linting**: `ruff` — config in `ruff.toml` (PEP 8, pyflakes, isort, bugbear, bandit)
- **Formatting**: `ruff format` (single quotes)
- **Pre-commit**: `.pre-commit-config.yaml` (ruff lint+format, trailing whitespace, large file check)
- **CI/CD**: GitHub Actions (`.github/workflows/ci.yml`) — lint + test on push/PR to main
- **Dev deps**: `requirements-dev.txt` (pytest, ruff, pre-commit, pydantic)

## Code Conventions

- Python: PEP 8, 4-space indent, snake_case functions, CamelCase classes
- JavaScript: ES6+ modules, const/let, async/await, template literals
- CSS: kebab-case class names, CSS custom properties for theming
- Parameterized SQL queries throughout (no raw string interpolation)
- Structured JSON logging in production, human-readable in dev
- Error handling with try/except, user-friendly JSON error responses

## Security

- PBKDF2-SHA256 password hashing (100k iterations)
- Token-based sessions (secrets.token_hex(32), 30-day user / 7-day admin expiry)
- In-memory rate limiting per IP (login: 10/60s, register: 5/60s, LLM endpoints: 10/60s)
- CSRF protection via Origin header validation on state-changing requests
- Security headers: X-Content-Type-Options, X-Frame-Options, Referrer-Policy, X-XSS-Protection, Permissions-Policy, HSTS (production)
- SQLite foreign keys enabled, WAL mode for concurrent access
- Max request size: 10MB, sync limit: 5MB
- Production admin password safety warning

## Architecture Notes

- **Offline-first**: Service worker + client-side SQLite (sql.js) for local data
- **Dual LLM**: Anthropic Claude (cloud, preferred) with Ollama (local) fallback; model versions pinned in config
- **LLM validation**: All LLM responses validated via Pydantic models before use
- **Cost-aware caching**: LLM responses cached to DB, savings tracked in `llm_cost_log`
- **Recipe suggestion engine**: Multi-factor scoring (time of day, macros, goals, preferences, diversity, seasonality)
- **Tag engine**: 10 dimensions (goal, cooking_style, lifestyle, micronutrients, health, dietary, satiety, texture, protein_source, seasonal) — hybrid LLM + deterministic
- **Batch generation**: Background thread, resumable, 3 retries with exponential backoff, macro validation (±10%)
- **Structured logging**: JSON-formatted logs in production with request ID, timing, and status codes
- **Multi-stage Docker**: Separate builder/runtime stages for smaller images; includes HEALTHCHECK
- **Large data files in repo**: `fuel_5000_recipes.csv` (~11MB), `recipes_1000.json` (~3MB) — tracked via .gitattributes

# CLAUDE.md

## Project Overview

FitCoach is a Progressive Web App (PWA) for fitness coaching — personalized recipe recommendations, AI-powered meal planning (via Anthropic Claude API), workout suggestions, and health profile management. Full-stack Python + vanilla JS.

## Tech Stack

- **Backend**: Flask, Flask-SQLAlchemy, Flask-CORS, SQLite (`fitcoach.db`)
- **Frontend**: Vanilla HTML/CSS/JavaScript (no framework), single-page app
- **AI**: Anthropic Claude API (`claude-sonnet-4-20250514`) via `backend/ai/claude_service.py`
- **PWA**: Service worker (`sw.js`) + `manifest.json`
- **Deployment**: Docker, Fly.io, Render, Gunicorn

## Commands

- **Dev server**: `python start.py` (Flask on 0.0.0.0:5001, debug mode)
- **Production**: `gunicorn app:app --bind 0.0.0.0:$PORT`
- **Docker**: `docker build -t fitcoach . && docker run -p 8080:8080 fitcoach`
- **Import recipes**: `python import_recipes.py` (loads CSV into SQLite)
- **No test suite exists**
- **No linter/formatter configured**

## Project Structure

```
app.py              # Flask app: all routes and API endpoints
config.py           # FlaskConfig (env vars: SECRET_KEY, ANTHROPIC_API_KEY, etc.)
start.py            # Dev entry point
index.html          # Main SPA HTML
backend/
  models.py         # SQLAlchemy models: User, Recipe, MealPlan, MealPlanItem, UserFavorite
  ai/
    claude_service.py  # ClaudeService: recipe recommendations + meal plan generation
admin/
  admin_panel.html  # Admin dashboard
  admin.js          # Admin panel JS
js/
  app.js            # FitCoachApp class (~2900 lines), all frontend logic
  config.js         # API_URL config
css/
  style.css         # Full stylesheet (~2500 lines), CSS variables, responsive, dark mode
data/
  recipes.json      # Recipe data (currently empty)
tools/scraper/
  recipe_scraper.py # AllRecipes.com scraper (requests + BeautifulSoup)
```

## Key API Routes (app.py)

- `GET /` — serves index.html
- `GET/POST /api/user/profile` — user profile CRUD
- `GET /api/recipes` — paginated recipes with search/filter
- `GET /api/recipes/<id>` — single recipe
- `GET /api/recommendations` — AI-powered recipe recommendations
- `GET /api/meal-plan` — AI-generated meal plan

## Code Conventions

- Python: PEP 8 style, 4-space indent
- JavaScript: ES6+ classes, const/let, async/await, template literals
- CSS: kebab-case class names, CSS custom properties for theming
- No tests, no linting config, no type checking
- Database uses `db.create_all()` — no migration system
- Environment variables for secrets (no .env file committed; .env is gitignored)

## Dependencies

Python (`requirements.txt`): flask, flask-cors, flask-sqlalchemy, anthropic, gunicorn

## Important Notes

- Large data files in repo: `fuel_5000_recipes.csv` (~11MB), `recipes_1000.json` (~3MB)
- SQLite is the only supported database — not horizontally scalable
- No authentication system; admin panel has hardcoded stats
- Workout data is hardcoded in `js/app.js`, not database-driven
- Service worker caches static assets with cache-first strategy (cache name: `fitcoach-v1`)

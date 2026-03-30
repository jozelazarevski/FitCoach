# FitCoach Code Analysis

## Architecture Overview

FitCoach is a full-stack fitness nutrition coaching app with:
- **Backend**: Python/Flask REST API with SQLite (WAL mode)
- **Frontend**: Vanilla JS single-page app (no framework) served as static files
- **LLM Integration**: Dual-provider support (Anthropic Claude + Ollama) for food parsing, recipe generation, and coaching
- **PWA**: Service worker + manifest for installable mobile experience

### Tech Stack
| Layer | Technology |
|-------|-----------|
| Backend | Flask (Python), SQLite3 |
| Frontend | Vanilla JS, CSS (custom dark theme) |
| LLM | Anthropic Claude API, Ollama (local) |
| Auth | Session tokens (PBKDF2-SHA256 passwords) |
| Barcode | QuaggaJS (in-browser scanner) |
| SQL (client) | sql.js (WASM SQLite in browser) |

## Key Features
1. Food tracking - text input or camera-based food image analysis via LLM
2. AI Coach - meal suggestions based on remaining macros, goal, preferences, workout history
3. Recipe database - searchable/filterable with tagging engine
4. 7-day meal planning - DB-powered with ingredient overlap optimization
5. Body tracking - weight, body fat trends with plateau detection
6. Workout logging - calorie tracking, recovery day detection
7. Admin panel - recipe management, LLM cost tracking, API key management, bulk recipe generation

## Security Issues

### Critical

1. **Hardcoded admin password** (backend/api/admin.py:33)
   The admin password is `fitcoach-admin` - hardcoded and using weak SHA-256 (no salt, no key stretching).

2. **Hardcoded SECRET_KEY** (app.py:21, config.py:14)
   The fallback secret key is predictable (`fitcoach-dev-key`), which could allow session forgery.

3. **Wildcard CORS** (app.py:33)
   All API routes accept requests from any origin (`Access-Control-Allow-Origin: *`).

4. **API keys stored in plaintext** (backend/db.py:118)
   The `api_keys` table stores LLM API keys as plain text in SQLite.

5. **User data synced unvalidated** (backend/api/auth.py:177)
   The `/api/auth/sync` endpoint stores arbitrary JSON without validation or size limits.

### Moderate

6. **No rate limiting** on login, registration, or LLM endpoints.

7. **Session tokens never expire** server-side beyond a 30-day window check.

8. **Duplicate model property** (js/llm.js:237-238, 285-286)
   The `model` key is declared twice in object literals. First value is silently overwritten.

## Code Quality Issues

### Backend

9. **Silent exception swallowing** (backend/api/recipes.py:86,159)
   `_save_suggestion_to_db` and `_save_full_recipe_to_db` catch all exceptions and return `None`.

10. **No input validation on recipe endpoints** (recipes.py:369)
    `int()` casts without `ValueError` handling will cause 500 errors.

11. **N+1 query problem in meal planning** (recipes.py:475-498)
    `meal-plan` endpoint calls `suggest_recipes()` 28 times (7 days x 4 slots).

12. **Thread-safety concern** (admin.py:345-349)
    Background recipe generation uses threads with SQLite, risking lock contention.

13. **`get_active_api_key` has side effects** (admin.py:321-326)
    This read function updates `usage_count` even when the subsequent LLM call may fail.

### Frontend

14. **API key stored in localStorage** (js/storage.js:25)
    Accessible to any JavaScript on the page including XSS payloads.

15. **No offline data persistence strategy** despite service worker.

16. **`Store.load()` called excessively** with fragile caching pattern.

## Architectural Observations

17. **Dual data path** - Both client-side and server-side LLM calls create confusing UX and duplicated logic.

18. **No tests** - Zero test files exist.

19. **No CI/CD** - No GitHub Actions or linting configuration.

20. **No database migrations** - Schema changes require manual editing of SCHEMA string.

21. **Smart caching strategy** - LLM-generated recipes cached to DB for free subsequent retrieval. `llm_cost_log` tracks savings.

22. **Good suggest algorithm** - 20+ contextual signals for personalized recommendations.

## Recommendations (Priority Order)

1. Fix the duplicate `model` key bug in js/llm.js (immediate)
2. Add environment-based admin authentication (critical security)
3. Restrict CORS to specific origins (critical security)
4. Add rate limiting on auth and LLM endpoints
5. Add input validation and size limits on sync endpoint
6. Add error logging instead of silent exception swallowing
7. Add basic test suite (at least for auth and recipe APIs)
8. Set up CI/CD pipeline with linting

import sqlite3
import os
from contextlib import contextmanager
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT DEFAULT 'general',
    cuisine TEXT DEFAULT 'International',
    country_of_origin TEXT DEFAULT 'International',
    region TEXT DEFAULT 'International',
    meal_type TEXT DEFAULT 'any',
    difficulty TEXT DEFAULT 'medium',
    prep_time_min INTEGER DEFAULT 0,
    cook_time_min INTEGER DEFAULT 0,
    total_time_min INTEGER DEFAULT 0,
    servings INTEGER DEFAULT 1,
    calories INTEGER NOT NULL,
    protein INTEGER NOT NULL,
    carbs INTEGER NOT NULL,
    fat INTEGER NOT NULL,
    fiber INTEGER DEFAULT 0,
    sugar INTEGER DEFAULT 0,
    ingredients TEXT NOT NULL,
    steps TEXT NOT NULL,
    tips TEXT,
    equipment TEXT DEFAULT '[]',
    allergens TEXT DEFAULT '[]',
    diet TEXT DEFAULT '[]',
    meal_prep_friendly INTEGER DEFAULT 0,
    source TEXT DEFAULT 'generated',
    generation_batch TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recipe_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    dimension TEXT NOT NULL,
    tag TEXT NOT NULL,
    UNIQUE(recipe_id, dimension, tag)
);

CREATE INDEX IF NOT EXISTS idx_tags_dim_tag ON recipe_tags(dimension, tag);
CREATE INDEX IF NOT EXISTS idx_tags_recipe ON recipe_tags(recipe_id);
CREATE INDEX IF NOT EXISTS idx_tags_recipe_dim ON recipe_tags(recipe_id, dimension, tag);
CREATE INDEX IF NOT EXISTS idx_recipes_meal ON recipes(meal_type);
CREATE INDEX IF NOT EXISTS idx_recipes_cuisine ON recipes(cuisine);
CREATE INDEX IF NOT EXISTS idx_recipes_category ON recipes(category);
CREATE INDEX IF NOT EXISTS idx_recipes_status ON recipes(status);
CREATE INDEX IF NOT EXISTS idx_recipes_calories ON recipes(calories);
CREATE INDEX IF NOT EXISTS idx_recipes_protein ON recipes(protein);
CREATE INDEX IF NOT EXISTS idx_recipes_status_meal ON recipes(status, meal_type);
CREATE INDEX IF NOT EXISTS idx_recipes_status_cal ON recipes(status, calories);
CREATE INDEX IF NOT EXISTS idx_recipes_difficulty ON recipes(difficulty);
CREATE INDEX IF NOT EXISTS idx_recipes_name ON recipes(name);

CREATE TABLE IF NOT EXISTS generation_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL UNIQUE,
    total_planned INTEGER NOT NULL,
    completed INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running',
    parameters TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS generation_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL,
    prompt_key TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    recipe_ids TEXT,
    error_message TEXT,
    attempts INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(batch_id, prompt_key)
);

CREATE INDEX IF NOT EXISTS idx_queue_batch_status ON generation_queue(batch_id, status);

CREATE TABLE IF NOT EXISTS admin_sessions (
    token TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    key_name TEXT NOT NULL DEFAULT 'default',
    api_key TEXT NOT NULL,
    model TEXT,
    is_active INTEGER DEFAULT 1,
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider, key_name)
);
"""


def get_db():
    """Open a raw connection. Caller must close it. Prefer use_db() instead."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def use_db():
    """Context manager that guarantees connection cleanup.

    Usage:
        with use_db() as db:
            db.execute(...)
            db.commit()
    """
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with use_db() as conn:
        conn.executescript(SCHEMA)
        conn.commit()
    # Run one-time maintenance
    _run_maintenance()


def _run_maintenance():
    """Run periodic maintenance: purge old sessions, optimize, checkpoint WAL."""
    with use_db() as conn:
        # Purge admin sessions older than 7 days
        conn.execute("DELETE FROM admin_sessions WHERE created_at < datetime('now', '-7 days')")
        conn.commit()
        # Optimize query planner statistics
        conn.execute("PRAGMA optimize")
        # Checkpoint WAL to keep file size reasonable
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

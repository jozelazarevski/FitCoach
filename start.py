"""Production startup: initialize DB and seed recipes if empty."""
from backend.db import init_db, use_db

init_db()

with use_db() as db:
    count = db.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]

if count == 0:
    print("Empty database — seeding starter recipes...")
    from backend.seed_recipes import seed_database
    seed_database()
    print("Seed complete.")
else:
    print(f"Database has {count} recipes, skipping seed.")

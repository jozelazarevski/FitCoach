# FitCoach Feature Roadmap

## 1. Smart Grocery List from Meal Plans
Auto-generate a consolidated grocery list from the 7-day meal plan.
- Deduplicate ingredients, combine quantities (e.g., "2 chicken breasts Mon + 3 Wed = 5 total")
- Organize by category (produce, protein, dairy, pantry staples)
- "Pantry" feature: users check off what they already have, list shows only what to buy
- Shareable list (copy to clipboard or export)

**API**: `POST /api/recipes/grocery-list` (accepts meal plan or list of recipe IDs)
**Frontend**: New tab/modal on meal plan screen with checkable items

---

## 2. Adaptive Macro Targets
Dynamically adjust daily macro targets based on context.
- Workout intensity: more carbs on heavy lifting days, maintenance on rest days
- Weekly trend correction: behind on weekly protein avg? shift tomorrow's targets up
- Weight trajectory: if weight stall detected over 2+ weeks, suggest deficit adjustment
- Activity level multiplier from logged workouts

**API**: `GET /api/coach/adaptive-targets` (returns adjusted macros for today)
**Frontend**: Dashboard shows "adjusted targets" vs base targets with explanation

---

## 3. Progress Insights Dashboard
Visual weekly/monthly analytics.
- Macro adherence chart (% of target hit per day, 7-day rolling avg)
- Weight trend line with moving average
- Top 10 most-eaten foods
- Cuisine variety score
- Protein source distribution (poultry vs fish vs plant vs red meat)
- Calorie consistency heatmap (calendar view)

**API**: `GET /api/coach/insights?period=7d|30d`
**Frontend**: New "Insights" screen with charts (lightweight canvas-based, no chart lib)

---

## 4. Recipe Scaling
Adjust servings on any recipe and auto-recalculate everything.
- Scale ingredient amounts proportionally
- Recalculate macros per serving
- Show both original and scaled values
- Persist user's preferred serving size

**API**: `GET /api/recipes/<id>?servings=4` (returns scaled recipe)
**Frontend**: Serving adjuster (+/-) on recipe detail screen

---

## 5. Restaurant Mode
Help users make macro-friendly choices when eating out.
- Search by restaurant name or snap a menu photo
- AI estimates macros for menu items
- Suggests best option given remaining daily macros
- Save favorite restaurant meals for quick re-logging

**API**: `POST /api/tracker/restaurant` (name or photo → macro estimates)
**Frontend**: "Eating Out" button in tracker with search/photo input

---

## 6. Streak & Habit Tracking
Gamification to drive retention.
- Daily logging streak counter
- Water intake goal tracking
- Weekly macro adherence badges (hit protein target 5/7 days)
- Milestone celebrations (7-day streak, 30-day streak, 100 recipes tried)

**API**: `GET /api/coach/streaks` (returns current streaks and badges)
**Frontend**: Streak counter on dashboard, badge collection in profile

---

## Implementation Order
1. Smart Grocery List ← most actionable, completes the meal plan flow
2. Recipe Scaling ← quick win, high polish
3. Adaptive Macro Targets ← core differentiator
4. Progress Insights Dashboard ← retention driver
5. Streak & Habit Tracking ← gamification layer
6. Restaurant Mode ← hardest, most novel

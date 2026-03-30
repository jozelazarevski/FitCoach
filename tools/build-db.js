const fs = require('fs');
const path = require('path');
const { parse } = require('csv-parse/sync');
const Database = require('better-sqlite3');

const CSV_PATH = path.join(__dirname, '..', 'fuel_5000_recipes.csv');
const DB_PATH = path.join(__dirname, '..', 'data', 'recipes.db');

// Ensure data directory exists
const dataDir = path.dirname(DB_PATH);
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}

// Remove old DB if exists
if (fs.existsSync(DB_PATH)) {
  fs.unlinkSync(DB_PATH);
}

console.log('Reading CSV...');
const csvData = fs.readFileSync(CSV_PATH, 'utf-8');

console.log('Parsing CSV...');
const records = parse(csvData, {
  columns: true,
  skip_empty_lines: true,
  trim: true
});

console.log(`Parsed ${records.length} recipes.`);

const db = new Database(DB_PATH);
db.pragma('journal_mode = WAL');

console.log('Creating table...');
db.exec(`
  CREATE TABLE recipes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    cuisine TEXT,
    category TEXT,
    meal_type TEXT,
    difficulty TEXT,
    prep_time_min INTEGER,
    cook_time_min INTEGER,
    total_time_min INTEGER,
    servings INTEGER,
    calories INTEGER,
    protein_g REAL,
    carbs_g REAL,
    fat_g REAL,
    fiber_g REAL,
    sugar_g REAL,
    description TEXT,
    tips TEXT,
    meal_prep_friendly INTEGER,
    allergens TEXT,
    diet TEXT,
    equipment TEXT,
    ingredients_items TEXT,
    ingredients_amounts TEXT,
    ingredients_grams TEXT,
    step_1 TEXT,
    step_2 TEXT,
    step_3 TEXT,
    step_4 TEXT,
    step_5 TEXT,
    step_6 TEXT,
    step_7 TEXT,
    tag_goal TEXT,
    tag_cooking_style TEXT,
    tag_lifestyle TEXT,
    tag_micronutrients TEXT,
    tag_health TEXT,
    tag_dietary TEXT,
    tag_satiety TEXT,
    tag_texture TEXT,
    tag_protein_source TEXT,
    tag_seasonal TEXT,
    tag_coaching TEXT
  );

  CREATE INDEX idx_meal_type ON recipes(meal_type);
  CREATE INDEX idx_calories ON recipes(calories);
  CREATE INDEX idx_protein ON recipes(protein_g);
  CREATE INDEX idx_difficulty ON recipes(difficulty);
  CREATE INDEX idx_cuisine ON recipes(cuisine);
  CREATE INDEX idx_total_time ON recipes(total_time_min);
`);

const insert = db.prepare(`
  INSERT INTO recipes VALUES (
    @id, @name, @cuisine, @category, @meal_type, @difficulty,
    @prep_time_min, @cook_time_min, @total_time_min, @servings,
    @calories, @protein_g, @carbs_g, @fat_g, @fiber_g, @sugar_g,
    @description, @tips, @meal_prep_friendly,
    @allergens, @diet, @equipment,
    @ingredients_items, @ingredients_amounts, @ingredients_grams,
    @step_1, @step_2, @step_3, @step_4, @step_5, @step_6, @step_7,
    @tag_goal, @tag_cooking_style, @tag_lifestyle, @tag_micronutrients,
    @tag_health, @tag_dietary, @tag_satiety, @tag_texture,
    @tag_protein_source, @tag_seasonal, @tag_coaching
  )
`);

console.log('Inserting recipes...');

const insertAll = db.transaction((rows) => {
  for (const row of rows) {
    insert.run({
      id: parseInt(row.id) || 0,
      name: row.name || '',
      cuisine: row.cuisine || '',
      category: row.category || '',
      meal_type: row.meal_type || '',
      difficulty: row.difficulty || '',
      prep_time_min: parseInt(row.prep_time_min) || 0,
      cook_time_min: parseInt(row.cook_time_min) || 0,
      total_time_min: parseInt(row.total_time_min) || 0,
      servings: parseInt(row.servings) || 1,
      calories: parseInt(row.calories) || 0,
      protein_g: parseFloat(row.protein_g) || 0,
      carbs_g: parseFloat(row.carbs_g) || 0,
      fat_g: parseFloat(row.fat_g) || 0,
      fiber_g: parseFloat(row.fiber_g) || 0,
      sugar_g: parseFloat(row.sugar_g) || 0,
      description: row.description || '',
      tips: row.tips || '',
      meal_prep_friendly: row.meal_prep_friendly === 'True' ? 1 : 0,
      allergens: row.allergens || '',
      diet: row.diet || '',
      equipment: row.equipment || '',
      ingredients_items: row.ingredients_items || '',
      ingredients_amounts: row.ingredients_amounts || '',
      ingredients_grams: row.ingredients_grams || '',
      step_1: row.step_1 || '',
      step_2: row.step_2 || '',
      step_3: row.step_3 || '',
      step_4: row.step_4 || '',
      step_5: row.step_5 || '',
      step_6: row.step_6 || '',
      step_7: row.step_7 || '',
      tag_goal: row.tag_goal || '',
      tag_cooking_style: row.tag_cooking_style || '',
      tag_lifestyle: row.tag_lifestyle || '',
      tag_micronutrients: row.tag_micronutrients || '',
      tag_health: row.tag_health || '',
      tag_dietary: row.tag_dietary || '',
      tag_satiety: row.tag_satiety || '',
      tag_texture: row.tag_texture || '',
      tag_protein_source: row.tag_protein_source || '',
      tag_seasonal: row.tag_seasonal || '',
      tag_coaching: row.tag_coaching || ''
    });
  }
});

insertAll(records);

const count = db.prepare('SELECT COUNT(*) as n FROM recipes').get();
console.log(`Done! ${count.n} recipes inserted into ${DB_PATH}`);

const stats = fs.statSync(DB_PATH);
console.log(`Database size: ${(stats.size / 1024 / 1024).toFixed(2)} MB`);

db.close();

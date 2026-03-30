const Profile = {
  healthOptions: [
    ['diabetes_t2', 'Type 2 Diabetes'],
    ['diabetes_t1', 'Type 1 Diabetes'],
    ['prediabetes', 'Prediabetes'],
    ['insulin_resistance', 'Insulin Resistance'],
    ['high_cholesterol', 'High Cholesterol'],
    ['high_triglycerides', 'High Triglycerides'],
    ['high_blood_pressure', 'High Blood Pressure'],
    ['heart_disease', 'Heart Disease'],
    ['pcos', 'PCOS'],
    ['hypothyroid', 'Hypothyroidism'],
    ['hyperthyroid', 'Hyperthyroidism'],
    ['hashimoto', "Hashimoto's"],
    ['ibs', 'IBS'],
    ['ibd_crohn', "Crohn's Disease"],
    ['ibd_colitis', 'Ulcerative Colitis'],
    ['celiac', 'Celiac Disease'],
    ['kidney_disease', 'Kidney Disease'],
    ['gout', 'Gout'],
    ['anemia', 'Iron Deficiency'],
    ['b12_deficiency', 'B12 Deficiency'],
    ['osteoporosis', 'Osteoporosis'],
    ['lactose_intolerant', 'Lactose Intolerant'],
    ['fatty_liver', 'Fatty Liver'],
    ['acid_reflux', 'Acid Reflux / GERD'],
    ['gallbladder', 'Gallbladder Issues'],
    ['food_allergies', 'Food Allergies'],
    ['nut_allergy', 'Nut Allergy'],
    ['shellfish_allergy', 'Shellfish Allergy'],
    ['egg_allergy', 'Egg Allergy'],
    ['soy_allergy', 'Soy Allergy'],
    ['arthritis', 'Arthritis'],
    ['fibromyalgia', 'Fibromyalgia'],
    ['endometriosis', 'Endometriosis'],
    ['sleep_apnea', 'Sleep Apnea'],
    ['anxiety_depression', 'Anxiety / Depression'],
    ['migraine', 'Migraines'],
    ['autoimmune', 'Autoimmune Disorder'],
  ],

  activityMultipliers: {
    sedentary: 1.2,
    light: 1.375,
    moderate: 1.55,
    active: 1.725,
    very_active: 1.9
  },

  goalMultipliers: {
    fat_loss: -500,
    aggressive_fat_loss: -750,
    muscle_gain: 300,
    lean_bulk: 200,
    maintain: 0,
    recomp: -100
  },

  goalLabels: {
    fat_loss: 'Fat Loss',
    aggressive_fat_loss: 'Aggressive Cut',
    muscle_gain: 'Muscle Gain',
    lean_bulk: 'Lean Bulk',
    maintain: 'Maintain',
    recomp: 'Recomposition'
  },

  activityLabels: {
    sedentary: 'Sedentary (desk job)',
    light: 'Lightly Active (1-2x/week)',
    moderate: 'Moderate (3-5x/week)',
    active: 'Very Active (6-7x/week)',
    very_active: 'Athlete (2x/day)'
  },

  calculateBMR(weight, height, age, gender) {
    if (gender === 'female') {
      return 10 * weight + 6.25 * height - 5 * age - 161;
    }
    return 10 * weight + 6.25 * height - 5 * age + 5;
  },

  calculateTDEE(profile) {
    const bmr = this.calculateBMR(profile.weight, profile.height, profile.age, profile.gender);
    const multiplier = this.activityMultipliers[profile.activityLevel] || 1.55;
    return Math.round(bmr * multiplier);
  },

  calculateMacros(profile) {
    if (profile.customMacros) return profile.macros;

    const tdee = this.calculateTDEE(profile);
    const adjustment = this.goalMultipliers[profile.goal] || 0;
    const targetCals = Math.round(tdee + adjustment);

    let proteinPerKg, fatPercent;

    switch (profile.goal) {
      case 'fat_loss':
      case 'aggressive_fat_loss':
        proteinPerKg = 2.2;
        fatPercent = 0.25;
        break;
      case 'muscle_gain':
      case 'lean_bulk':
        proteinPerKg = 1.8;
        fatPercent = 0.25;
        break;
      case 'recomp':
        proteinPerKg = 2.0;
        fatPercent = 0.25;
        break;
      default:
        proteinPerKg = 1.6;
        fatPercent = 0.3;
    }

    const protein = Math.round(profile.weight * proteinPerKg);
    const fat = Math.round((targetCals * fatPercent) / 9);
    const carbCals = targetCals - (protein * 4) - (fat * 9);
    const carbs = Math.round(Math.max(0, carbCals / 4));

    return {
      calories: targetCals,
      protein,
      carbs,
      fat
    };
  },

  renderProfileForm() {
    const profile = Store.getProfile();
    const screen = UI.$('#screen-profile');

    screen.innerHTML = `
      <div class="form-section">
        <div class="form-section-title">Body Stats</div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Weight (${profile.unit === 'metric' ? 'kg' : 'lbs'})</label>
            <input type="number" class="form-input" id="inp-weight" value="${profile.weight || ''}" placeholder="80" step="0.1">
          </div>
          <div class="form-group">
            <label class="form-label">Height (${profile.unit === 'metric' ? 'cm' : 'in'})</label>
            <input type="number" class="form-input" id="inp-height" value="${profile.height || ''}" placeholder="180">
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">Age</label>
            <input type="number" class="form-input" id="inp-age" value="${profile.age || ''}" placeholder="30">
          </div>
          <div class="form-group">
            <label class="form-label">Gender</label>
            <select class="form-select" id="inp-gender">
              <option value="male" ${profile.gender === 'male' ? 'selected' : ''}>Male</option>
              <option value="female" ${profile.gender === 'female' ? 'selected' : ''}>Female</option>
            </select>
          </div>
        </div>
        <div class="form-group">
          <label class="form-label">Unit System</label>
          <select class="form-select" id="inp-unit">
            <option value="metric" ${profile.unit === 'metric' ? 'selected' : ''}>Metric (kg/cm)</option>
            <option value="imperial" ${profile.unit === 'imperial' ? 'selected' : ''}>Imperial (lbs/in)</option>
          </select>
        </div>
      </div>

      <div class="form-section">
        <div class="form-section-title">Activity Level</div>
        <div class="goal-pills" id="activity-pills">
          ${Object.entries(this.activityLabels).map(([k, v]) =>
            `<button class="goal-pill ${profile.activityLevel === k ? 'active' : ''}" data-val="${k}">${v}</button>`
          ).join('')}
        </div>
      </div>

      <div class="form-section">
        <div class="form-section-title">Goal</div>
        <div class="goal-pills" id="goal-pills">
          ${Object.entries(this.goalLabels).map(([k, v]) =>
            `<button class="goal-pill ${profile.goal === k ? 'active' : ''}" data-val="${k}">${v}</button>`
          ).join('')}
        </div>
      </div>

      <div class="form-section">
        <div class="form-section-title">Health Conditions (optional)</div>
        <div class="form-label" style="margin-bottom:10px">Select any that apply - meals will be tailored accordingly</div>
        <div class="goal-pills" id="health-pills">
          ${Profile.healthOptions.map(([k, v]) =>
            `<button class="goal-pill health-pill ${(profile.healthConditions || []).includes(k) ? 'active' : ''}" data-val="${k}">${v}</button>`
          ).join('')}
          ${(profile.healthConditions || []).filter(c => !Profile.healthOptions.some(([k]) => k === c)).map(c =>
            `<button class="goal-pill health-pill active custom-health" data-val="${c}">${c} <span class="health-remove">&times;</span></button>`
          ).join('')}
        </div>
        <div class="form-group" style="margin-top:10px">
          <div class="food-input-wrap">
            <input type="text" class="food-input" id="inp-custom-health" placeholder="Add other condition...">
            <button class="btn" id="btn-add-health" style="padding:10px 16px">Add</button>
          </div>
        </div>
      </div>

      <div class="form-section" id="tdee-section">
      </div>

      <div class="form-section">
        <div class="form-section-title">AI Provider</div>
        <div class="form-group">
          <label class="form-label">Provider</label>
          <select class="form-select" id="inp-provider">
            <option value="openai" ${profile.apiProvider === 'openai' ? 'selected' : ''}>OpenAI</option>
            <option value="anthropic" ${profile.apiProvider === 'anthropic' ? 'selected' : ''}>Claude (Anthropic)</option>
          </select>
        </div>
        <div class="form-group" id="claude-model-group" style="${profile.apiProvider === 'anthropic' ? '' : 'display:none'}">
          <label class="form-label">Claude Model</label>
          <select class="form-select" id="inp-claude-model">
            <option value="claude-haiku-4-5-20251001" ${profile.claudeModel === 'claude-haiku-4-5-20251001' ? 'selected' : ''}>Claude Haiku 4.5 (fast, cheap)</option>
            <option value="claude-sonnet-4-6" ${profile.claudeModel === 'claude-sonnet-4-6' ? 'selected' : ''}>Claude Sonnet 4.6 (balanced)</option>
            <option value="claude-opus-4-6" ${profile.claudeModel === 'claude-opus-4-6' ? 'selected' : ''}>Claude Opus 4.6 (most capable)</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">API Key</label>
          <div class="api-key-wrap">
            <input type="password" class="form-input" id="inp-apikey" value="${profile.apiKey || ''}" placeholder="Enter your API key">
            <button class="api-key-toggle" id="toggle-key">&#128065;</button>
          </div>
        </div>
      </div>

      <div class="form-section">
        <div class="form-section-title">Data</div>
        <div class="data-actions">
          <button class="btn btn-outline" id="btn-export">Export Backup</button>
          <button class="btn btn-outline" id="btn-import">Import Backup</button>
        </div>
        <input type="file" id="file-import" accept=".json" style="display:none">
      </div>

      <button class="btn btn-full" id="btn-save-profile" style="margin-top:8px">Save Profile</button>

      ${Auth.isLoggedIn() ? `
        <div class="form-section" style="margin-top:16px">
          <div class="form-section-title">Account</div>
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
            <span style="color:var(--text-dim);font-size:13px">${Auth.getUser()?.email || ''}</span>
            <button class="btn btn-outline" id="btn-logout" style="font-size:12px;padding:6px 14px">Sign Out</button>
          </div>
        </div>
      ` : ''}
    `;

    this._bindProfileEvents();
    this._updateTDEE();
  },

  _bindProfileEvents() {
    const pills = (container, callback) => {
      UI.$(container).addEventListener('click', e => {
        const pill = e.target.closest('.goal-pill');
        if (!pill) return;
        UI.$$(container + ' .goal-pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        callback(pill.dataset.val);
      });
    };

    pills('#goal-pills', () => this._updateTDEE());
    pills('#activity-pills', () => this._updateTDEE());

    // Health conditions: multi-select toggle
    UI.$('#health-pills')?.addEventListener('click', e => {
      // Handle remove button on custom pills
      const removeBtn = e.target.closest('.health-remove');
      if (removeBtn) {
        const pill = removeBtn.closest('.health-pill');
        if (pill) pill.remove();
        return;
      }
      const pill = e.target.closest('.health-pill');
      if (!pill) return;
      pill.classList.toggle('active');
    });

    UI.$('#btn-add-health')?.addEventListener('click', () => this._addCustomHealth());
    UI.$('#inp-custom-health')?.addEventListener('keydown', e => {
      if (e.key === 'Enter') this._addCustomHealth();
    });

    ['inp-weight', 'inp-height', 'inp-age', 'inp-gender'].forEach(id => {
      UI.$('#' + id)?.addEventListener('input', () => this._updateTDEE());
    });

    UI.$('#inp-unit')?.addEventListener('change', e => {
      const profile = this._readForm();
      const unit = e.target.value;
      const wLabel = unit === 'metric' ? 'kg' : 'lbs';
      const hLabel = unit === 'metric' ? 'cm' : 'in';
      UI.$('#inp-weight').previousElementSibling.textContent = `Weight (${wLabel})`;
      UI.$('#inp-height').previousElementSibling.textContent = `Height (${hLabel})`;
    });

    UI.$('#inp-provider')?.addEventListener('change', e => {
      const group = UI.$('#claude-model-group');
      if (group) group.style.display = e.target.value === 'anthropic' ? '' : 'none';
    });

    UI.$('#toggle-key')?.addEventListener('click', () => {
      const inp = UI.$('#inp-apikey');
      inp.type = inp.type === 'password' ? 'text' : 'password';
    });

    UI.$('#btn-save-profile')?.addEventListener('click', () => {
      const profile = this._readForm();
      if (!profile.weight || !profile.height || !profile.age) {
        UI.toast('Please fill in all body stats', 'error');
        return;
      }
      const tdee = this.calculateTDEE(this._toMetric(profile));
      const macros = this.calculateMacros(this._toMetric(profile));
      Store.saveProfile({ ...profile, tdee, macros });
      UI.toast('Profile saved!', 'success');
      App.refreshDashboard();
      // Sync to server
      Auth.syncProfile();
      Auth.syncData();
    });

    UI.$('#btn-logout')?.addEventListener('click', async () => {
      if (!confirm('Sign out of your account?')) return;
      await Auth.logout();
      location.reload();
    });

    UI.$('#btn-export')?.addEventListener('click', () => Store.exportData());

    UI.$('#btn-import')?.addEventListener('click', () => UI.$('#file-import').click());

    UI.$('#file-import')?.addEventListener('change', async e => {
      const file = e.target.files[0];
      if (!file) return;
      try {
        await Store.importData(file);
        UI.toast('Data imported!', 'success');
        this.renderProfileForm();
        App.refreshDashboard();
      } catch (err) {
        UI.toast(err.message, 'error');
      }
    });
  },

  _readForm() {
    return {
      weight: parseFloat(UI.$('#inp-weight')?.value) || 0,
      height: parseFloat(UI.$('#inp-height')?.value) || 0,
      age: parseInt(UI.$('#inp-age')?.value) || 0,
      gender: UI.$('#inp-gender')?.value || 'male',
      unit: UI.$('#inp-unit')?.value || 'metric',
      activityLevel: UI.$('#activity-pills .goal-pill.active')?.dataset.val || 'moderate',
      goal: UI.$('#goal-pills .goal-pill.active')?.dataset.val || 'fat_loss',
      healthConditions: Array.from(UI.$$('#health-pills .health-pill.active')).map(p => p.dataset.val),
      apiProvider: UI.$('#inp-provider')?.value || 'openai',
      apiKey: UI.$('#inp-apikey')?.value || '',
      claudeModel: UI.$('#inp-claude-model')?.value || 'claude-haiku-4-5-20251001'
    };
  },

  _addCustomHealth() {
    const input = UI.$('#inp-custom-health');
    const text = input.value.trim();
    if (!text) return;

    // Check if already exists
    const existing = Array.from(UI.$$('#health-pills .health-pill')).map(p => p.dataset.val.toLowerCase());
    if (existing.includes(text.toLowerCase())) {
      UI.toast('Already added', 'error');
      return;
    }

    const pill = document.createElement('button');
    pill.className = 'goal-pill health-pill active custom-health';
    pill.dataset.val = text;
    pill.innerHTML = `${text} <span class="health-remove">&times;</span>`;
    UI.$('#health-pills').appendChild(pill);
    input.value = '';
    UI.toast(`Added "${text}"`, 'success');
  },

  _toMetric(profile) {
    if (profile.unit === 'imperial') {
      return { ...profile, weight: profile.weight * 0.4536, height: profile.height * 2.54 };
    }
    return profile;
  },

  _updateTDEE() {
    const profile = this._readForm();
    const metricProfile = this._toMetric(profile);
    if (!metricProfile.weight || !metricProfile.height || !metricProfile.age) return;

    const tdee = this.calculateTDEE(metricProfile);
    const macros = this.calculateMacros(metricProfile);

    const section = UI.$('#tdee-section');
    section.innerHTML = `
      <div class="form-section-title">Your Targets</div>
      <div class="tdee-display">
        <div class="tdee-number">${macros.calories}</div>
        <div class="tdee-label">Daily Calories (TDEE: ${tdee})</div>
      </div>
      <div class="macro-targets">
        <div class="macro-target-item">
          <div class="macro-target-value" style="color:var(--protein-color)">${macros.protein}g</div>
          <div class="macro-target-label">Protein</div>
        </div>
        <div class="macro-target-item">
          <div class="macro-target-value" style="color:var(--carb-color)">${macros.carbs}g</div>
          <div class="macro-target-label">Carbs</div>
        </div>
        <div class="macro-target-item">
          <div class="macro-target-value" style="color:var(--fat-color)">${macros.fat}g</div>
          <div class="macro-target-label">Fat</div>
        </div>
      </div>
    `;
  },

  // --- Onboarding wizard state ---
  _obStep: 1,
  _obData: {},
  _obLiked: [],
  _obDisliked: [],
  _obCustomHealth: [],
  _totalSteps: 5,

  renderOnboarding() {
    this._obStep = 1;
    this._obData = {};
    this._obLiked = [];
    this._obDisliked = [];
    this._obCustomHealth = [];
    this._renderOnboardStep();
  },

  _renderOnboardStep() {
    const overlay = UI.$('.onboarding');
    const step = this._obStep;
    const pct = Math.round((step / this._totalSteps) * 100);

    const stepTitles = ['', 'About You', 'Your Fitness Goal', 'Health & Conditions', 'Food Preferences', 'Ready to Go'];

    overlay.innerHTML = `
      <div style="max-width:440px;margin:0 auto;padding:20px 16px">
        <div class="onboarding-title">FitCoach</div>
        <div class="onboarding-subtitle">${stepTitles[step]}</div>
        <div class="ob-progress">
          <div class="ob-step-label">Step ${step} of ${this._totalSteps}</div>
          <div class="progress-bar" style="margin:8px auto 24px;max-width:300px">
            <div class="progress-fill" style="width:${pct}%;background:var(--primary)"></div>
          </div>
        </div>
        <div id="ob-step-content">
          ${this._obStepHTML(step)}
        </div>
        <div class="ob-nav">
          ${step > 1 ? '<button class="btn btn-outline" id="ob-back">Back</button>' : ''}
          <button class="btn btn-full btn-coach" id="ob-next">${step === this._totalSteps ? 'Start Tracking' : 'Continue'}</button>
        </div>
      </div>
    `;

    UI.show(overlay);
    this._bindObStep(step);

    UI.$('#ob-back')?.addEventListener('click', () => {
      this._saveObStep(step);
      this._obStep--;
      this._renderOnboardStep();
    });

    UI.$('#ob-next')?.addEventListener('click', () => {
      if (!this._validateObStep(step)) return;
      this._saveObStep(step);
      if (step === this._totalSteps) {
        this._finalizeOnboarding();
      } else {
        this._obStep++;
        this._renderOnboardStep();
      }
    });
  },

  _obStepHTML(step) {
    const d = this._obData;
    const unit = d.unit || 'metric';
    const wLabel = unit === 'metric' ? 'kg' : 'lbs';
    const hLabel = unit === 'metric' ? 'cm' : 'in';

    switch (step) {
      case 1: return `
        <div class="form-section">
          <div class="form-group">
            <label class="form-label">What's your name? (optional)</label>
            <input type="text" class="form-input" id="ob-name" value="${UI.esc(d.name || '')}" placeholder="Your name" autocomplete="name">
          </div>
          <div class="form-group">
            <label class="form-label">Unit System</label>
            <select class="form-select" id="ob-unit">
              <option value="metric" ${unit === 'metric' ? 'selected' : ''}>Metric (kg / cm)</option>
              <option value="imperial" ${unit === 'imperial' ? 'selected' : ''}>Imperial (lbs / in)</option>
            </select>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label" id="ob-weight-label">Weight (${wLabel})</label>
              <input type="number" class="form-input" id="ob-weight" value="${d.weight || ''}" placeholder="80" step="0.1">
            </div>
            <div class="form-group">
              <label class="form-label" id="ob-height-label">Height (${hLabel})</label>
              <input type="number" class="form-input" id="ob-height" value="${d.height || ''}" placeholder="180">
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Age</label>
              <input type="number" class="form-input" id="ob-age" value="${d.age || ''}" placeholder="30">
            </div>
            <div class="form-group">
              <label class="form-label">Gender</label>
              <select class="form-select" id="ob-gender">
                <option value="male" ${(d.gender || 'male') === 'male' ? 'selected' : ''}>Male</option>
                <option value="female" ${d.gender === 'female' ? 'selected' : ''}>Female</option>
              </select>
            </div>
          </div>
        </div>`;

      case 2: return `
        <div class="form-section">
          <div class="form-section-title">How active are you?</div>
          <div class="goal-pills" id="ob-activity">
            ${Object.entries(this.activityLabels).map(([k, v]) =>
              `<button class="goal-pill ${(d.activityLevel || 'moderate') === k ? 'active' : ''}" data-val="${k}">${v}</button>`
            ).join('')}
          </div>
        </div>
        <div class="form-section">
          <div class="form-section-title">What's your goal?</div>
          <div class="goal-pills" id="ob-goal">
            ${Object.entries(this.goalLabels).map(([k, v]) =>
              `<button class="goal-pill ${(d.goal || 'fat_loss') === k ? 'active' : ''}" data-val="${k}">${v}</button>`
            ).join('')}
          </div>
        </div>
        <div id="ob-tdee-section"></div>`;

      case 3: return `
        <div class="form-section">
          <div class="form-label" style="margin-bottom:14px;line-height:1.5">
            Select any conditions that apply. We'll filter out allergens and prioritize foods that support your health. This is optional.
          </div>
          <div class="goal-pills" id="ob-health-pills">
            ${Profile.healthOptions.map(([k, v]) =>
              `<button class="goal-pill health-pill ${(d.healthConditions || []).includes(k) ? 'active' : ''}" data-val="${k}">${v}</button>`
            ).join('')}
            ${this._obCustomHealth.map(c =>
              `<button class="goal-pill health-pill active custom-health" data-val="${UI.esc(c)}">${UI.esc(c)} <span class="health-remove">&times;</span></button>`
            ).join('')}
          </div>
          <div class="form-group" style="margin-top:12px">
            <div class="food-input-wrap">
              <input type="text" class="food-input" id="ob-custom-health" placeholder="Add other condition...">
              <button class="btn" id="ob-btn-add-health" style="padding:10px 16px">Add</button>
            </div>
          </div>
        </div>`;

      case 4: return `
        <div class="form-section">
          <div class="form-section-title">Do you follow a dietary style?</div>
          <div class="meal-type-pills" id="ob-diet-pills">
            ${['vegan','vegetarian','keto','low_carb','high_protein','paleo','gluten_free','dairy_free','mediterranean','whole30'].map(f => {
              const labels = {vegan:'Vegan',vegetarian:'Vegetarian',keto:'Keto',low_carb:'Low Carb',high_protein:'High Protein',paleo:'Paleo',gluten_free:'Gluten Free',dairy_free:'Dairy Free',mediterranean:'Mediterranean',whole30:'Whole30'};
              return `<button class="meal-type-pill diet-pill ${(d.dietaryStyle || []).includes(f) ? 'active' : ''}" data-filter="${f}">${labels[f]}</button>`;
            }).join('')}
          </div>
        </div>
        <div class="form-section">
          <div class="form-section-title">Foods you enjoy</div>
          <div class="food-input-wrap">
            <input type="text" class="food-input" id="ob-liked-input" placeholder="e.g. chicken, pasta, avocado...">
            <button class="btn" id="ob-btn-add-liked" style="padding:10px 16px;background:var(--accent-green)">Add</button>
          </div>
          <div class="prefs-tags" id="ob-liked-tags" style="margin-top:8px">
            ${this._obLiked.map(f => `<span class="pref-tag pref-liked">${UI.esc(f)} <button class="pref-remove" data-type="liked" data-food="${UI.esc(f)}">&times;</button></span>`).join('')}
          </div>
        </div>
        <div class="form-section">
          <div class="form-section-title">Foods you want to avoid</div>
          <div class="food-input-wrap">
            <input type="text" class="food-input" id="ob-disliked-input" placeholder="e.g. liver, tofu, mushrooms...">
            <button class="btn" id="ob-btn-add-disliked" style="padding:10px 16px;background:var(--accent-red)">Add</button>
          </div>
          <div class="prefs-tags" id="ob-disliked-tags" style="margin-top:8px">
            ${this._obDisliked.map(f => `<span class="pref-tag pref-disliked">${UI.esc(f)} <button class="pref-remove" data-type="disliked" data-food="${UI.esc(f)}">&times;</button></span>`).join('')}
          </div>
        </div>`;

      case 5: {
        const metricProfile = this._toMetric({
          weight: d.weight || 0, height: d.height || 0, age: d.age || 0,
          gender: d.gender || 'male', unit: d.unit || 'metric',
          activityLevel: d.activityLevel || 'moderate', goal: d.goal || 'fat_loss'
        });
        const macros = this.calculateMacros(metricProfile);
        const tdee = this.calculateTDEE(metricProfile);
        const healthList = (d.healthConditions || []);
        const dietList = (d.dietaryStyle || []);
        const dietLabels = {vegan:'Vegan',vegetarian:'Vegetarian',keto:'Keto',low_carb:'Low Carb',high_protein:'High Protein',paleo:'Paleo',gluten_free:'Gluten Free',dairy_free:'Dairy Free',mediterranean:'Mediterranean',whole30:'Whole30'};

        return `
        <div class="card">
          <div class="card-title">Your Targets</div>
          <div class="tdee-display">
            <div class="tdee-number">${macros.calories}</div>
            <div class="tdee-label">Daily Calories (TDEE: ${tdee})</div>
          </div>
          <div class="macro-targets">
            <div class="macro-target-item">
              <div class="macro-target-value" style="color:var(--protein-color)">${macros.protein}g</div>
              <div class="macro-target-label">Protein</div>
            </div>
            <div class="macro-target-item">
              <div class="macro-target-value" style="color:var(--carb-color)">${macros.carbs}g</div>
              <div class="macro-target-label">Carbs</div>
            </div>
            <div class="macro-target-item">
              <div class="macro-target-value" style="color:var(--fat-color)">${macros.fat}g</div>
              <div class="macro-target-label">Fat</div>
            </div>
          </div>
        </div>
        <div class="card">
          <div class="card-title">Profile</div>
          <div style="font-size:14px;color:var(--text-dim);line-height:1.8">
            ${d.name ? `<div><strong>Name:</strong> ${UI.esc(d.name)}</div>` : ''}
            <div><strong>Stats:</strong> ${d.weight}${d.unit === 'metric' ? 'kg' : 'lbs'}, ${d.height}${d.unit === 'metric' ? 'cm' : 'in'}, ${d.age}yo, ${d.gender}</div>
            <div><strong>Activity:</strong> ${this.activityLabels[d.activityLevel] || d.activityLevel}</div>
            <div><strong>Goal:</strong> ${this.goalLabels[d.goal] || d.goal}</div>
          </div>
        </div>
        ${healthList.length > 0 ? `
        <div class="card">
          <div class="card-title">Health Conditions</div>
          <div class="goal-pills">
            ${healthList.map(c => {
              const label = Profile.healthOptions.find(([k]) => k === c)?.[1] || c;
              return `<span class="goal-pill active" style="cursor:default;font-size:12px">${UI.esc(label)}</span>`;
            }).join('')}
          </div>
        </div>` : ''}
        ${dietList.length > 0 || this._obLiked.length > 0 || this._obDisliked.length > 0 ? `
        <div class="card">
          <div class="card-title">Food Preferences</div>
          ${dietList.length > 0 ? `<div class="goal-pills" style="margin-bottom:8px">${dietList.map(f => `<span class="goal-pill active" style="cursor:default;font-size:12px">${dietLabels[f] || f}</span>`).join('')}</div>` : ''}
          ${this._obLiked.length > 0 ? `<div style="margin-bottom:4px"><span style="color:var(--accent-green);font-size:12px">Enjoy:</span> <span style="font-size:13px;color:var(--text-dim)">${this._obLiked.map(f => UI.esc(f)).join(', ')}</span></div>` : ''}
          ${this._obDisliked.length > 0 ? `<div><span style="color:var(--accent-red);font-size:12px">Avoid:</span> <span style="font-size:13px;color:var(--text-dim)">${this._obDisliked.map(f => UI.esc(f)).join(', ')}</span></div>` : ''}
        </div>` : ''}
        `;
      }
      default: return '';
    }
  },

  _bindObStep(step) {
    if (step === 1) {
      UI.$('#ob-unit')?.addEventListener('change', e => {
        const u = e.target.value;
        const wl = u === 'metric' ? 'kg' : 'lbs';
        const hl = u === 'metric' ? 'cm' : 'in';
        UI.$('#ob-weight-label').textContent = `Weight (${wl})`;
        UI.$('#ob-height-label').textContent = `Height (${hl})`;
      });
    }

    if (step === 2) {
      ['#ob-activity', '#ob-goal'].forEach(sel => {
        UI.$(sel)?.addEventListener('click', e => {
          const pill = e.target.closest('.goal-pill');
          if (!pill) return;
          UI.$$(sel + ' .goal-pill').forEach(p => p.classList.remove('active'));
          pill.classList.add('active');
          this._updateObTDEE();
        });
      });
      this._updateObTDEE();
    }

    if (step === 3) {
      UI.$('#ob-health-pills')?.addEventListener('click', e => {
        const removeBtn = e.target.closest('.health-remove');
        if (removeBtn) {
          const pill = removeBtn.closest('.health-pill');
          if (pill) {
            this._obCustomHealth = this._obCustomHealth.filter(c => c !== pill.dataset.val);
            pill.remove();
          }
          return;
        }
        const pill = e.target.closest('.health-pill');
        if (pill) pill.classList.toggle('active');
      });

      const addHealth = () => {
        const input = UI.$('#ob-custom-health');
        const text = input?.value.trim();
        if (!text) return;
        if (this._obCustomHealth.includes(text)) { UI.toast('Already added', 'error'); return; }
        this._obCustomHealth.push(text);
        const pill = document.createElement('button');
        pill.className = 'goal-pill health-pill active custom-health';
        pill.dataset.val = text;
        pill.innerHTML = `${UI.esc(text)} <span class="health-remove">&times;</span>`;
        UI.$('#ob-health-pills').appendChild(pill);
        input.value = '';
      };
      UI.$('#ob-btn-add-health')?.addEventListener('click', addHealth);
      UI.$('#ob-custom-health')?.addEventListener('keydown', e => { if (e.key === 'Enter') addHealth(); });
    }

    if (step === 4) {
      // Diet style multi-select
      UI.$('#ob-diet-pills')?.addEventListener('click', e => {
        const pill = e.target.closest('.diet-pill');
        if (pill) pill.classList.toggle('active');
      });

      // Liked foods
      const addLiked = () => {
        const input = UI.$('#ob-liked-input');
        const text = input?.value.trim();
        if (!text) return;
        if (!this._obLiked.some(f => f.toLowerCase() === text.toLowerCase())) {
          this._obLiked.push(text);
          this._obDisliked = this._obDisliked.filter(f => f.toLowerCase() !== text.toLowerCase());
        }
        this._saveObStep(4);
        this._renderOnboardStep();
      };
      UI.$('#ob-btn-add-liked')?.addEventListener('click', addLiked);
      UI.$('#ob-liked-input')?.addEventListener('keydown', e => { if (e.key === 'Enter') addLiked(); });

      // Disliked foods
      const addDisliked = () => {
        const input = UI.$('#ob-disliked-input');
        const text = input?.value.trim();
        if (!text) return;
        if (!this._obDisliked.some(f => f.toLowerCase() === text.toLowerCase())) {
          this._obDisliked.push(text);
          this._obLiked = this._obLiked.filter(f => f.toLowerCase() !== text.toLowerCase());
        }
        this._saveObStep(4);
        this._renderOnboardStep();
      };
      UI.$('#ob-btn-add-disliked')?.addEventListener('click', addDisliked);
      UI.$('#ob-disliked-input')?.addEventListener('keydown', e => { if (e.key === 'Enter') addDisliked(); });

      // Remove tags
      UI.$$('.pref-remove').forEach(btn => {
        btn.addEventListener('click', () => {
          const type = btn.dataset.type;
          const food = btn.dataset.food;
          if (type === 'liked') this._obLiked = this._obLiked.filter(f => f !== food);
          else this._obDisliked = this._obDisliked.filter(f => f !== food);
          this._saveObStep(4);
          this._renderOnboardStep();
        });
      });
    }
  },

  _validateObStep(step) {
    if (step === 1) {
      const w = parseFloat(UI.$('#ob-weight')?.value);
      const h = parseFloat(UI.$('#ob-height')?.value);
      const a = parseInt(UI.$('#ob-age')?.value);
      if (!w || !h || !a) { UI.toast('Please fill in weight, height & age', 'error'); return false; }
    }
    return true;
  },

  _saveObStep(step) {
    if (step === 1) {
      this._obData.name = UI.$('#ob-name')?.value.trim() || '';
      this._obData.unit = UI.$('#ob-unit')?.value || 'metric';
      this._obData.weight = parseFloat(UI.$('#ob-weight')?.value) || 0;
      this._obData.height = parseFloat(UI.$('#ob-height')?.value) || 0;
      this._obData.age = parseInt(UI.$('#ob-age')?.value) || 0;
      this._obData.gender = UI.$('#ob-gender')?.value || 'male';
    }
    if (step === 2) {
      this._obData.activityLevel = UI.$('#ob-activity .goal-pill.active')?.dataset.val || 'moderate';
      this._obData.goal = UI.$('#ob-goal .goal-pill.active')?.dataset.val || 'fat_loss';
    }
    if (step === 3) {
      const selected = Array.from(UI.$$('#ob-health-pills .health-pill.active')).map(p => p.dataset.val);
      this._obData.healthConditions = selected;
    }
    if (step === 4) {
      this._obData.dietaryStyle = Array.from(UI.$$('#ob-diet-pills .diet-pill.active')).map(p => p.dataset.filter);
    }
  },

  _updateObTDEE() {
    const section = UI.$('#ob-tdee-section');
    if (!section) return;
    const d = this._obData;
    if (!d.weight || !d.height || !d.age) return;

    const metricProfile = this._toMetric({
      weight: d.weight, height: d.height, age: d.age,
      gender: d.gender || 'male', unit: d.unit || 'metric',
      activityLevel: UI.$('#ob-activity .goal-pill.active')?.dataset.val || 'moderate',
      goal: UI.$('#ob-goal .goal-pill.active')?.dataset.val || 'fat_loss'
    });

    const tdee = this.calculateTDEE(metricProfile);
    const macros = this.calculateMacros(metricProfile);

    section.innerHTML = `
      <div class="form-section">
        <div class="tdee-display">
          <div class="tdee-number">${macros.calories}</div>
          <div class="tdee-label">Daily Calories (TDEE: ${tdee})</div>
        </div>
        <div class="macro-targets">
          <div class="macro-target-item">
            <div class="macro-target-value" style="color:var(--protein-color)">${macros.protein}g</div>
            <div class="macro-target-label">Protein</div>
          </div>
          <div class="macro-target-item">
            <div class="macro-target-value" style="color:var(--carb-color)">${macros.carbs}g</div>
            <div class="macro-target-label">Carbs</div>
          </div>
          <div class="macro-target-item">
            <div class="macro-target-value" style="color:var(--fat-color)">${macros.fat}g</div>
            <div class="macro-target-label">Fat</div>
          </div>
        </div>
      </div>
    `;
  },

  _finalizeOnboarding() {
    const d = this._obData;

    const profile = {
      name: d.name || '',
      weight: d.weight,
      height: d.height,
      age: d.age,
      gender: d.gender || 'male',
      unit: d.unit || 'metric',
      activityLevel: d.activityLevel || 'moderate',
      goal: d.goal || 'fat_loss',
      healthConditions: d.healthConditions || [],
      dietaryPreferences: {
        dietaryStyle: d.dietaryStyle || [],
        liked: [...this._obLiked],
        disliked: [...this._obDisliked]
      }
    };

    const metricProfile = this._toMetric(profile);
    profile.tdee = this.calculateTDEE(metricProfile);
    profile.macros = this.calculateMacros(metricProfile);
    Store.saveProfile(profile);

    // Sync liked/disliked into top-level preferences
    this._obLiked.forEach(f => Store.addPreference('liked', f));
    this._obDisliked.forEach(f => Store.addPreference('disliked', f));

    // Sync to server
    Auth.syncProfile();
    Auth.syncData();

    // Show post-onboarding assessment instead of going straight to dashboard
    this._showAssessment(profile);
  },

  _showAssessment(profile) {
    const overlay = UI.$('.onboarding');
    const macros = profile.macros;
    const tdee = profile.tdee;
    const bmr = this.calculateBMR(
      profile.unit === 'imperial' ? profile.weight * 0.4536 : profile.weight,
      profile.unit === 'imperial' ? profile.height * 2.54 : profile.height,
      profile.age, profile.gender
    );
    const weightKg = profile.unit === 'imperial' ? profile.weight * 0.4536 : profile.weight;
    const heightCm = profile.unit === 'imperial' ? profile.height * 2.54 : profile.height;
    const wLabel = profile.unit === 'metric' ? 'kg' : 'lbs';

    // BMI calculation
    const heightM = heightCm / 100;
    const bmi = (weightKg / (heightM * heightM)).toFixed(1);
    let bmiCategory = 'Normal';
    let bmiColor = 'var(--accent-green)';
    if (bmi < 18.5) { bmiCategory = 'Underweight'; bmiColor = 'var(--cal-color)'; }
    else if (bmi >= 25 && bmi < 30) { bmiCategory = 'Overweight'; bmiColor = 'var(--cal-color)'; }
    else if (bmi >= 30) { bmiCategory = 'Obese'; bmiColor = 'var(--accent-red)'; }

    // Water target
    const waterMl = Math.round(weightKg * 33);
    const waterL = (waterMl / 1000).toFixed(1);

    // Goal-specific advice
    const goalAdvice = {
      fat_loss: {
        title: 'Fat Loss Plan',
        desc: `Your daily target of <strong>${macros.calories} cal</strong> is set at a 500 cal deficit from your TDEE. This puts you on track to lose about <strong>0.45 ${wLabel}/week</strong> in a healthy, sustainable way.`,
        tips: [
          `Hit your <strong>${macros.protein}g protein</strong> target daily to preserve muscle mass during your cut`,
          'Prioritize whole foods, lean proteins, and vegetables to stay full on fewer calories',
          'Log every meal — even small snacks. Consistency in tracking is what drives results',
          'Drink plenty of water (often mistaken for hunger) and get 7-9 hours of sleep'
        ]
      },
      aggressive_fat_loss: {
        title: 'Aggressive Cut Plan',
        desc: `Your daily target of <strong>${macros.calories} cal</strong> is set at a 750 cal deficit. You can expect to lose about <strong>0.7 ${wLabel}/week</strong>. This is aggressive — monitor energy levels closely.`,
        tips: [
          `<strong>${macros.protein}g protein</strong> is non-negotiable — muscle loss risk is higher on aggressive cuts`,
          'Schedule 1-2 refeed days per week at maintenance calories to prevent metabolic adaptation',
          'Reduce training volume slightly and focus on maintaining strength, not pushing PRs',
          'If energy drops significantly after 2-3 weeks, consider switching to standard fat loss'
        ]
      },
      muscle_gain: {
        title: 'Muscle Gain Plan',
        desc: `Your daily target of <strong>${macros.calories} cal</strong> includes a 300 cal surplus for muscle building. Combined with resistance training, this supports <strong>0.2-0.5 ${wLabel}/month</strong> of lean mass gain.`,
        tips: [
          `Spread your <strong>${macros.protein}g protein</strong> across 4+ meals for optimal muscle protein synthesis`,
          'Focus on progressive overload in your training — this is what drives muscle growth',
          'Time carbs around your workouts for better performance and recovery',
          'Weigh yourself weekly — if gaining faster than 0.5% bodyweight/week, reduce surplus slightly'
        ]
      },
      lean_bulk: {
        title: 'Lean Bulk Plan',
        desc: `Your daily target of <strong>${macros.calories} cal</strong> has a modest 200 cal surplus. This minimizes fat gain while still supporting muscle growth — ideal for staying lean year-round.`,
        tips: [
          `Your <strong>${macros.protein}g protein</strong> and <strong>${macros.carbs}g carbs</strong> fuel training and recovery`,
          'Train with intensity 4-5x/week with compound lifts as your foundation',
          'Be patient — lean bulking is slower but you stay leaner with less cutting needed later',
          'Track body measurements alongside weight to monitor composition changes'
        ]
      },
      maintain: {
        title: 'Maintenance Plan',
        desc: `Your daily target of <strong>${macros.calories} cal</strong> matches your estimated energy expenditure. This will keep your weight stable while supporting your current activity level.`,
        tips: [
          'Maintenance is the best phase for improving body composition through training quality',
          'Use this phase to build healthy habits and meal timing routines',
          `Keep protein at <strong>${macros.protein}g</strong> to support recovery and maintain muscle mass`,
          'Weigh weekly — if weight drifts more than 1-2 ${wLabel}, adjust slightly'
        ]
      },
      recomp: {
        title: 'Recomposition Plan',
        desc: `Your daily target of <strong>${macros.calories} cal</strong> is at a slight 100 cal deficit. Combined with resistance training and high protein, this supports losing fat while building muscle simultaneously.`,
        tips: [
          `<strong>${macros.protein}g protein</strong> is critical — recomp demands high protein intake`,
          'Prioritize heavy compound lifts 3-4x/week with progressive overload',
          'Be patient — recomp is slower than a bulk/cut cycle but the results are sustainable',
          'Track body measurements and progress photos, not just scale weight'
        ]
      }
    };

    const advice = goalAdvice[profile.goal] || goalAdvice.maintain;
    const conditions = profile.healthConditions || [];
    const dietStyles = profile.dietaryPreferences?.dietaryStyle || [];

    // Health condition implications
    let healthHTML = '';
    if (conditions.length > 0) {
      const conditionAdvice = {
        diabetes_t2: 'Focus on low-glycemic carbs, fiber-rich foods, and consistent meal timing',
        diabetes_t1: 'Coordinate carb intake with insulin dosing. Consistent carb tracking is essential',
        prediabetes: 'Prioritize fiber, whole grains, and regular physical activity to improve insulin sensitivity',
        insulin_resistance: 'Reduce refined carbs and sugar. Focus on protein and healthy fats at each meal',
        high_cholesterol: 'Limit saturated fat, increase fiber and omega-3 fatty acids',
        high_blood_pressure: 'Watch sodium intake (aim under 2300mg/day), increase potassium-rich foods',
        pcos: 'Low-glycemic eating pattern, anti-inflammatory foods, and consistent exercise help manage symptoms',
        hypothyroid: 'Ensure adequate iodine, selenium, and zinc. Avoid excessive soy and cruciferous vegetables raw',
        celiac: 'All meal suggestions will be strictly gluten-free. Read labels carefully for hidden gluten',
        lactose_intolerant: 'Dairy-free alternatives will be prioritized. Consider calcium-fortified options',
        ibs: 'Consider a low-FODMAP approach. We\'ll suggest gentle, easy-to-digest recipes',
        gout: 'Limit high-purine foods (organ meats, shellfish). Stay well hydrated',
        fatty_liver: 'Minimize added sugars and refined carbs. Focus on Mediterranean-style eating',
        acid_reflux: 'Avoid large meals, spicy/acidic foods, and eating close to bedtime'
      };

      const relevantAdvice = conditions
        .map(c => conditionAdvice[c])
        .filter(Boolean)
        .slice(0, 4);

      if (relevantAdvice.length > 0) {
        healthHTML = `
        <div class="card">
          <div class="card-title">Health Considerations</div>
          <div class="assessment-list">
            ${relevantAdvice.map(a => `<div class="assessment-item"><span class="assessment-bullet">&#9679;</span> ${a}</div>`).join('')}
          </div>
          <div style="margin-top:8px;font-size:12px;color:var(--text-dim)">Your meal suggestions will automatically account for ${conditions.length === 1 ? 'this condition' : 'these conditions'}.</div>
        </div>`;
      }
    }

    // Macro breakdown explanation
    const proteinPct = Math.round((macros.protein * 4 / macros.calories) * 100);
    const carbPct = Math.round((macros.carbs * 4 / macros.calories) * 100);
    const fatPct = Math.round((macros.fat * 9 / macros.calories) * 100);

    overlay.innerHTML = `
      <div style="max-width:440px;margin:0 auto;padding:20px 16px">
        <div class="onboarding-title">Your Assessment</div>
        <div class="onboarding-subtitle">Here's your personalized plan</div>

        <div class="card">
          <div class="card-title">Body Analysis</div>
          <div class="assessment-stats">
            <div class="assessment-stat">
              <div class="assessment-stat-value">${bmi}</div>
              <div class="assessment-stat-label">BMI</div>
              <div class="assessment-stat-note" style="color:${bmiColor}">${bmiCategory}</div>
            </div>
            <div class="assessment-stat">
              <div class="assessment-stat-value">${Math.round(bmr)}</div>
              <div class="assessment-stat-label">BMR</div>
              <div class="assessment-stat-note">cal/day at rest</div>
            </div>
            <div class="assessment-stat">
              <div class="assessment-stat-value">${tdee}</div>
              <div class="assessment-stat-label">TDEE</div>
              <div class="assessment-stat-note">cal/day active</div>
            </div>
          </div>
          <div style="font-size:12px;color:var(--text-dim);margin-top:12px;line-height:1.6">
            Your body burns <strong>${Math.round(bmr)} cal/day</strong> at rest (BMR). With your ${this.activityLabels[profile.activityLevel]?.toLowerCase() || 'moderate'} activity level, your total daily expenditure is <strong>${tdee} cal</strong>.
          </div>
        </div>

        <div class="card">
          <div class="card-title">${advice.title}</div>
          <div style="font-size:13px;color:var(--text-dim);line-height:1.6;margin-bottom:12px">${advice.desc}</div>
          <div class="macro-targets" style="margin-bottom:12px">
            <div class="macro-target-item">
              <div class="macro-target-value" style="color:var(--protein-color)">${macros.protein}g</div>
              <div class="macro-target-label">Protein (${proteinPct}%)</div>
            </div>
            <div class="macro-target-item">
              <div class="macro-target-value" style="color:var(--carb-color)">${macros.carbs}g</div>
              <div class="macro-target-label">Carbs (${carbPct}%)</div>
            </div>
            <div class="macro-target-item">
              <div class="macro-target-value" style="color:var(--fat-color)">${macros.fat}g</div>
              <div class="macro-target-label">Fat (${fatPct}%)</div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-title">Your Next Steps</div>
          <div class="assessment-list">
            ${advice.tips.map((t, i) => `<div class="assessment-item"><span class="assessment-step">${i + 1}</span> ${t}</div>`).join('')}
          </div>
        </div>

        ${healthHTML}

        <div class="card">
          <div class="card-title">Daily Targets</div>
          <div class="assessment-list">
            <div class="assessment-item"><span class="assessment-bullet">&#9679;</span> <strong>${waterL}L water</strong> per day (${waterMl}ml based on your weight)</div>
            <div class="assessment-item"><span class="assessment-bullet">&#9679;</span> <strong>25-30g fiber</strong> daily for digestive health</div>
            <div class="assessment-item"><span class="assessment-bullet">&#9679;</span> <strong>7-9 hours sleep</strong> for recovery and hormone regulation</div>
            ${dietStyles.length > 0 ? `<div class="assessment-item"><span class="assessment-bullet">&#9679;</span> Meal suggestions tailored to your <strong>${dietStyles.map(d => d.replace(/_/g, ' ')).join(', ')}</strong> diet</div>` : ''}
          </div>
        </div>

        <div class="ob-nav">
          <button class="btn btn-full btn-coach" id="assessment-start">Let's Get Started</button>
        </div>
      </div>
    `;

    UI.$('#assessment-start')?.addEventListener('click', () => {
      UI.hide(overlay);
      App.navigate('dashboard');
    });
  }
};

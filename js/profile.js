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

  renderOnboarding() {
    const overlay = UI.$('.onboarding');
    overlay.innerHTML = `
      <div class="onboarding-title">FitCoach</div>
      <div class="onboarding-subtitle">Your AI-powered macro coach</div>
      <div style="max-width:400px;margin:0 auto">
        <div class="form-section">
          <div class="form-section-title">Let's set up your profile</div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Weight (kg)</label>
              <input type="number" class="form-input" id="ob-weight" placeholder="80" step="0.1">
            </div>
            <div class="form-group">
              <label class="form-label">Height (cm)</label>
              <input type="number" class="form-input" id="ob-height" placeholder="180">
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Age</label>
              <input type="number" class="form-input" id="ob-age" placeholder="30">
            </div>
            <div class="form-group">
              <label class="form-label">Gender</label>
              <select class="form-select" id="ob-gender">
                <option value="male">Male</option>
                <option value="female">Female</option>
              </select>
            </div>
          </div>
        </div>

        <div class="form-section">
          <div class="form-section-title">Activity Level</div>
          <div class="goal-pills" id="ob-activity">
            <button class="goal-pill" data-val="sedentary">Sedentary</button>
            <button class="goal-pill" data-val="light">Light</button>
            <button class="goal-pill active" data-val="moderate">Moderate</button>
            <button class="goal-pill" data-val="active">Active</button>
            <button class="goal-pill" data-val="very_active">Athlete</button>
          </div>
        </div>

        <div class="form-section">
          <div class="form-section-title">Your Goal</div>
          <div class="goal-pills" id="ob-goal">
            <button class="goal-pill active" data-val="fat_loss">Fat Loss</button>
            <button class="goal-pill" data-val="muscle_gain">Muscle Gain</button>
            <button class="goal-pill" data-val="lean_bulk">Lean Bulk</button>
            <button class="goal-pill" data-val="maintain">Maintain</button>
            <button class="goal-pill" data-val="recomp">Recomp</button>
          </div>
        </div>

        <div class="form-section">
          <div class="form-section-title">AI Provider</div>
          <div class="form-group">
            <select class="form-select" id="ob-provider">
              <option value="openai">OpenAI</option>
              <option value="anthropic">Claude (Anthropic)</option>
            </select>
          </div>
          <div class="form-group" id="ob-claude-model-group" style="display:none">
            <label class="form-label">Claude Model</label>
            <select class="form-select" id="ob-claude-model">
              <option value="claude-haiku-4-5-20251001">Claude Haiku 4.5 (fast, cheap)</option>
              <option value="claude-sonnet-4-6">Claude Sonnet 4.6 (balanced)</option>
              <option value="claude-opus-4-6">Claude Opus 4.6 (most capable)</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">API Key</label>
            <input type="password" class="form-input" id="ob-apikey" placeholder="Your API key">
          </div>
        </div>

        <button class="btn btn-full btn-coach" id="btn-onboard" style="margin-bottom:40px">
          Start Tracking
        </button>
      </div>
    `;

    UI.show(overlay);

    // pill toggles
    ['#ob-activity', '#ob-goal'].forEach(sel => {
      UI.$(sel).addEventListener('click', e => {
        const pill = e.target.closest('.goal-pill');
        if (!pill) return;
        UI.$$(sel + ' .goal-pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
      });
    });

    UI.$('#ob-provider')?.addEventListener('change', e => {
      const group = UI.$('#ob-claude-model-group');
      if (group) group.style.display = e.target.value === 'anthropic' ? '' : 'none';
    });

    UI.$('#btn-onboard').addEventListener('click', () => {
      const w = parseFloat(UI.$('#ob-weight').value);
      const h = parseFloat(UI.$('#ob-height').value);
      const a = parseInt(UI.$('#ob-age').value);

      if (!w || !h || !a) { UI.toast('Fill in weight, height & age', 'error'); return; }

      const profile = {
        weight: w, height: h, age: a,
        gender: UI.$('#ob-gender').value,
        activityLevel: UI.$('#ob-activity .goal-pill.active')?.dataset.val || 'moderate',
        goal: UI.$('#ob-goal .goal-pill.active')?.dataset.val || 'fat_loss',
        apiProvider: UI.$('#ob-provider').value,
        apiKey: key,
        claudeModel: UI.$('#ob-claude-model')?.value || 'claude-haiku-4-5-20251001',
        unit: 'metric'
      };

      profile.tdee = Profile.calculateTDEE(profile);
      profile.macros = Profile.calculateMacros(profile);
      Store.saveProfile(profile);

      // Sync to server
      Auth.syncProfile();

      UI.hide(overlay);
      App.navigate('dashboard');
    });
  }
};

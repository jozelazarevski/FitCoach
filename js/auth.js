const Auth = {
  TOKEN_KEY: 'fitcoach_token',
  USER_KEY: 'fitcoach_user',
  _syncing: false,

  getToken() {
    return localStorage.getItem(this.TOKEN_KEY);
  },

  getUser() {
    try {
      return JSON.parse(localStorage.getItem(this.USER_KEY) || 'null');
    } catch { return null; }
  },

  isLoggedIn() {
    return !!this.getToken();
  },

  async _api(path, opts = {}) {
    const token = this.getToken();
    const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(`/api/auth${path}`, { ...opts, headers });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Request failed');
    return data;
  },

  async register(email, password, name) {
    const data = await this._api('/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, name })
    });
    this._saveSession(data.token, data.user);
    return data.user;
  },

  async login(email, password) {
    const data = await this._api('/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    });
    this._saveSession(data.token, data.user);

    // Restore profile and data from server
    if (data.user.profile && Object.keys(data.user.profile).length > 0) {
      Store.saveProfile(data.user.profile);
    }
    if (data.user.data && Object.keys(data.user.data).length > 0) {
      const current = Store.load();
      const serverData = data.user.data;
      // Merge server data with local defaults
      const merged = { ...Store._defaults(), ...serverData };
      merged.profile = current.profile; // profile handled separately above
      Store.save(merged);
    }

    return data.user;
  },

  async logout() {
    try { await this._api('/logout', { method: 'POST' }); } catch {}
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.USER_KEY);
  },

  _saveSession(token, user) {
    localStorage.setItem(this.TOKEN_KEY, token);
    localStorage.setItem(this.USER_KEY, JSON.stringify(user));
  },

  // Sync profile to server
  async syncProfile() {
    if (!this.isLoggedIn() || this._syncing) return;
    this._syncing = true;
    try {
      const profile = Store.getProfile();
      const user = this.getUser();
      await this._api('/profile', {
        method: 'PUT',
        body: JSON.stringify({ profile, name: user?.name || profile.name || '' })
      });
    } catch {} finally { this._syncing = false; }
  },

  // Sync all data to server
  async syncData() {
    if (!this.isLoggedIn() || this._syncing) return;
    this._syncing = true;
    try {
      const data = Store.load();
      // Don't sync API keys to server
      const toSync = { ...data };
      if (toSync.profile) {
        toSync.profile = { ...toSync.profile };
        delete toSync.profile.apiKey;
      }
      await this._api('/sync', {
        method: 'PUT',
        body: JSON.stringify({ data: toSync })
      });
    } catch {} finally { this._syncing = false; }
  },

  // Render login/register screen
  renderAuthScreen() {
    const overlay = UI.$('.onboarding');
    overlay.innerHTML = `
      <div class="auth-container">
        <div class="auth-logo">FitCoach</div>
        <div class="auth-subtitle">Your AI-powered macro coach</div>

        <div class="auth-tabs">
          <button class="auth-tab active" data-tab="login">Sign In</button>
          <button class="auth-tab" data-tab="register">Create Account</button>
        </div>

        <div class="auth-error" id="auth-error" style="display:none"></div>

        <form class="auth-form" id="auth-form-login">
          <div class="form-group">
            <label class="form-label">Email</label>
            <input type="email" class="form-input" id="auth-email-login" placeholder="you@example.com" autocomplete="email" required>
            <div class="field-error" id="err-email-login"></div>
          </div>
          <div class="form-group">
            <label class="form-label">Password</label>
            <div class="pass-toggle-wrap">
              <input type="password" class="form-input" id="auth-pass-login" placeholder="Enter password" autocomplete="current-password" required>
              <button type="button" class="pass-toggle" tabindex="-1" data-target="auth-pass-login">Show</button>
            </div>
          </div>
          <button type="submit" class="btn btn-full btn-coach" id="btn-login">Sign In</button>
        </form>

        <form class="auth-form" id="auth-form-register" style="display:none">
          <div class="form-group">
            <label class="form-label">Name</label>
            <input type="text" class="form-input" id="auth-name" placeholder="Your name" autocomplete="name" required>
            <div class="field-error" id="err-name"></div>
          </div>
          <div class="form-group">
            <label class="form-label">Email</label>
            <input type="email" class="form-input" id="auth-email-register" placeholder="you@example.com" autocomplete="email" required>
            <div class="field-error" id="err-email-register"></div>
          </div>
          <div class="form-group">
            <label class="form-label">Password</label>
            <div class="pass-toggle-wrap">
              <input type="password" class="form-input" id="auth-pass-register" placeholder="Min 6 characters" autocomplete="new-password" required>
              <button type="button" class="pass-toggle" tabindex="-1" data-target="auth-pass-register">Show</button>
            </div>
            <div class="pass-strength" id="pass-strength"></div>
            <div class="field-error" id="err-pass-register"></div>
          </div>
          <div class="form-group">
            <label class="form-label">Confirm Password</label>
            <div class="pass-toggle-wrap">
              <input type="password" class="form-input" id="auth-pass-confirm" placeholder="Repeat password" autocomplete="new-password" required>
              <button type="button" class="pass-toggle" tabindex="-1" data-target="auth-pass-confirm">Show</button>
            </div>
            <div class="field-error" id="err-pass-confirm"></div>
          </div>
          <button type="submit" class="btn btn-full btn-coach" id="btn-register" disabled>Create Account</button>
        </form>

        <div class="auth-divider"><span>or</span></div>
        <button class="btn btn-outline btn-full" id="btn-guest">Continue as Guest</button>
      </div>
    `;

    UI.show(overlay);

    // Tab switching
    overlay.querySelectorAll('.auth-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        overlay.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const isLogin = tab.dataset.tab === 'login';
        document.getElementById('auth-form-login').style.display = isLogin ? 'block' : 'none';
        document.getElementById('auth-form-register').style.display = isLogin ? 'none' : 'block';
        this._hideError();
        this._clearFieldErrors();
        if (!isLogin) {
          setTimeout(() => document.getElementById('auth-name')?.focus(), 100);
        } else {
          setTimeout(() => document.getElementById('auth-email-login')?.focus(), 100);
        }
      });
    });

    // Password visibility toggles
    overlay.querySelectorAll('.pass-toggle').forEach(btn => {
      btn.addEventListener('click', () => {
        const input = document.getElementById(btn.dataset.target);
        if (!input) return;
        const isHidden = input.type === 'password';
        input.type = isHidden ? 'text' : 'password';
        btn.textContent = isHidden ? 'Hide' : 'Show';
      });
    });

    // Real-time password strength
    const passInput = document.getElementById('auth-pass-register');
    const confirmInput = document.getElementById('auth-pass-confirm');
    passInput?.addEventListener('input', () => {
      this._updatePasswordStrength(passInput.value);
      this._validateRegisterForm();
      if (confirmInput.value) {
        this._checkConfirmMatch(passInput.value, confirmInput.value);
      }
    });

    // Real-time confirm match
    confirmInput?.addEventListener('input', () => {
      this._checkConfirmMatch(passInput.value, confirmInput.value);
      this._validateRegisterForm();
    });

    // Real-time email validation for register
    const regEmail = document.getElementById('auth-email-register');
    regEmail?.addEventListener('input', () => {
      const val = regEmail.value.trim();
      if (val && !this._isValidEmail(val)) {
        this._setFieldError('err-email-register', 'Enter a valid email address');
      } else {
        this._setFieldError('err-email-register', '');
      }
      this._validateRegisterForm();
    });

    // Real-time name validation
    const nameInput = document.getElementById('auth-name');
    nameInput?.addEventListener('input', () => {
      this._validateRegisterForm();
    });

    // Login
    document.getElementById('auth-form-login').addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = document.getElementById('auth-email-login').value.trim();
      const password = document.getElementById('auth-pass-login').value;
      if (!email || !password) {
        if (!email) this._setFieldError('err-email-login', 'Email is required');
        return;
      }
      if (!this._isValidEmail(email)) {
        this._setFieldError('err-email-login', 'Enter a valid email address');
        return;
      }

      const btn = document.getElementById('btn-login');
      btn.disabled = true;
      btn.textContent = 'Signing in...';
      this._hideError();
      this._clearFieldErrors();

      try {
        await this.login(email, password);
        UI.hide(overlay);

        if (!Store.isProfileComplete()) {
          Profile.renderOnboarding();
        } else {
          App.navigate('dashboard');
        }
      } catch (err) {
        this._showError(err.message);
      } finally {
        btn.disabled = false;
        btn.textContent = 'Sign In';
      }
    });

    // Register
    document.getElementById('auth-form-register').addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = document.getElementById('auth-name').value.trim();
      const email = document.getElementById('auth-email-register').value.trim();
      const password = document.getElementById('auth-pass-register').value;
      const confirm = document.getElementById('auth-pass-confirm').value;

      // Field-level validation
      let valid = true;
      this._clearFieldErrors();

      if (!name) {
        this._setFieldError('err-name', 'Name is required');
        valid = false;
      }
      if (!email) {
        this._setFieldError('err-email-register', 'Email is required');
        valid = false;
      } else if (!this._isValidEmail(email)) {
        this._setFieldError('err-email-register', 'Enter a valid email address');
        valid = false;
      }
      if (!password || password.length < 6) {
        this._setFieldError('err-pass-register', 'Password must be at least 6 characters');
        valid = false;
      }
      if (password !== confirm) {
        this._setFieldError('err-pass-confirm', 'Passwords do not match');
        valid = false;
      }
      if (!valid) return;

      const btn = document.getElementById('btn-register');
      btn.disabled = true;
      btn.textContent = 'Creating account...';
      this._hideError();

      try {
        await this.register(email, password, name);
        UI.hide(overlay);
        Profile.renderOnboarding();
      } catch (err) {
        if (err.message.toLowerCase().includes('already registered')) {
          this._showError('This email is already registered. Try signing in instead.');
          // Switch to login tab with email pre-filled
          overlay.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
          overlay.querySelector('[data-tab="login"]')?.classList.add('active');
          document.getElementById('auth-form-login').style.display = 'block';
          document.getElementById('auth-form-register').style.display = 'none';
          document.getElementById('auth-email-login').value = email;
          document.getElementById('auth-pass-login')?.focus();
        } else {
          this._showError(err.message);
        }
      } finally {
        btn.disabled = false;
        btn.textContent = 'Create Account';
      }
    });

    // Guest mode — skip auth, go straight to onboarding or dashboard
    document.getElementById('btn-guest')?.addEventListener('click', () => {
      UI.hide(overlay);
      if (!Store.isProfileComplete()) {
        Profile.renderOnboarding();
      } else {
        App.navigate('dashboard');
      }
    });

    // Auto-focus email on login form
    setTimeout(() => document.getElementById('auth-email-login')?.focus(), 150);
  },

  _isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  },

  _updatePasswordStrength(password) {
    const el = document.getElementById('pass-strength');
    if (!el) return;
    if (!password) { el.innerHTML = ''; return; }

    let score = 0;
    if (password.length >= 6) score++;
    if (password.length >= 10) score++;
    if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score++;
    if (/\d/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;

    const levels = [
      { label: 'Too short', cls: 'str-weak' },
      { label: 'Weak', cls: 'str-weak' },
      { label: 'Fair', cls: 'str-fair' },
      { label: 'Good', cls: 'str-good' },
      { label: 'Strong', cls: 'str-strong' },
      { label: 'Very strong', cls: 'str-strong' },
    ];
    const level = levels[score];
    el.innerHTML = `<div class="str-bar ${level.cls}"><div class="str-fill" style="width:${score * 20}%"></div></div><span class="str-label ${level.cls}">${level.label}</span>`;
  },

  _checkConfirmMatch(password, confirm) {
    if (!confirm) {
      this._setFieldError('err-pass-confirm', '');
    } else if (password !== confirm) {
      this._setFieldError('err-pass-confirm', 'Passwords do not match');
    } else {
      this._setFieldError('err-pass-confirm', '');
    }
  },

  _validateRegisterForm() {
    const name = document.getElementById('auth-name')?.value.trim();
    const email = document.getElementById('auth-email-register')?.value.trim();
    const password = document.getElementById('auth-pass-register')?.value || '';
    const confirm = document.getElementById('auth-pass-confirm')?.value || '';
    const btn = document.getElementById('btn-register');
    if (!btn) return;

    const valid = name && email && this._isValidEmail(email) &&
      password.length >= 6 && password === confirm;
    btn.disabled = !valid;
  },

  _showError(msg) {
    const el = document.getElementById('auth-error');
    if (el) {
      el.textContent = msg;
      el.style.display = 'block';
      el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  },

  _hideError() {
    const el = document.getElementById('auth-error');
    if (el) el.style.display = 'none';
  },

  _setFieldError(id, msg) {
    const el = document.getElementById(id);
    if (el) {
      el.textContent = msg;
      el.style.display = msg ? 'block' : 'none';
    }
  },

  _clearFieldErrors() {
    document.querySelectorAll('.field-error').forEach(el => {
      el.textContent = '';
      el.style.display = 'none';
    });
  }
};

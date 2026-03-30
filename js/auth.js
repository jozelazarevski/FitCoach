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

        <form class="auth-form" id="auth-form-login">
          <div class="form-group">
            <label class="form-label">Email</label>
            <input type="email" class="form-input" id="auth-email-login" placeholder="you@example.com" autocomplete="email" required>
          </div>
          <div class="form-group">
            <label class="form-label">Password</label>
            <input type="password" class="form-input" id="auth-pass-login" placeholder="Enter password" autocomplete="current-password" required>
          </div>
          <button type="submit" class="btn btn-full btn-coach" id="btn-login">Sign In</button>
        </form>

        <form class="auth-form" id="auth-form-register" style="display:none">
          <div class="form-group">
            <label class="form-label">Name</label>
            <input type="text" class="form-input" id="auth-name" placeholder="Your name" autocomplete="name">
          </div>
          <div class="form-group">
            <label class="form-label">Email</label>
            <input type="email" class="form-input" id="auth-email-register" placeholder="you@example.com" autocomplete="email" required>
          </div>
          <div class="form-group">
            <label class="form-label">Password</label>
            <input type="password" class="form-input" id="auth-pass-register" placeholder="Min 6 characters" autocomplete="new-password" required>
          </div>
          <div class="form-group">
            <label class="form-label">Confirm Password</label>
            <input type="password" class="form-input" id="auth-pass-confirm" placeholder="Repeat password" autocomplete="new-password" required>
          </div>
          <button type="submit" class="btn btn-full btn-coach" id="btn-register">Create Account</button>
        </form>

        <div class="auth-error" id="auth-error" style="display:none"></div>
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
        document.getElementById('auth-error').style.display = 'none';
      });
    });

    // Login
    document.getElementById('auth-form-login').addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = document.getElementById('auth-email-login').value.trim();
      const password = document.getElementById('auth-pass-login').value;
      if (!email || !password) return;

      const btn = document.getElementById('btn-login');
      btn.disabled = true;
      btn.textContent = 'Signing in...';
      this._hideError();

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

      if (!email || !password) return;
      if (password !== confirm) {
        this._showError('Passwords do not match');
        return;
      }
      if (password.length < 6) {
        this._showError('Password must be at least 6 characters');
        return;
      }

      const btn = document.getElementById('btn-register');
      btn.disabled = true;
      btn.textContent = 'Creating account...';
      this._hideError();

      try {
        await this.register(email, password, name);
        UI.hide(overlay);
        Profile.renderOnboarding();
      } catch (err) {
        this._showError(err.message);
      } finally {
        btn.disabled = false;
        btn.textContent = 'Create Account';
      }
    });
  },

  _showError(msg) {
    const el = document.getElementById('auth-error');
    if (el) {
      el.textContent = msg;
      el.style.display = 'block';
    }
  },

  _hideError() {
    const el = document.getElementById('auth-error');
    if (el) el.style.display = 'none';
  }
};

const Tracker = {
  pendingParse: null,
  isListening: false,
  recognition: null,
  selectedDate: null,

  renderFoodInput() {
    const hasSpeech = 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;
    const todayKey = Store.getTodayKey();
    return `
      <div class="food-date-row">
        <input type="date" class="food-date-picker" id="food-date" value="${todayKey}" max="${todayKey}">
        <span class="food-date-label" id="food-date-label">Today</span>
      </div>
      <div class="food-input-wrap">
        <input type="text" class="food-input" id="food-text" placeholder="What did you eat?">
        <button class="btn" id="btn-parse">Log</button>
      </div>
      <div class="input-actions">
        <button class="input-action-btn" id="btn-camera" title="Take photo of food">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z"/><circle cx="12" cy="13" r="4"/></svg>
          <span>Photo</span>
        </button>
        <button class="input-action-btn" id="btn-barcode" title="Scan barcode">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="4" width="2" height="16"/><rect x="6" y="4" width="1" height="16"/><rect x="9" y="4" width="2" height="16"/><rect x="13" y="4" width="1" height="16"/><rect x="16" y="4" width="2" height="16"/><rect x="20" y="4" width="2" height="16"/></svg>
          <span>Barcode</span>
        </button>
        ${hasSpeech ? `
        <button class="input-action-btn" id="btn-voice" title="Voice input">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/><path d="M19 10v2a7 7 0 01-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
          <span>Voice</span>
        </button>` : ''}
        <button class="input-action-btn" id="btn-restaurant" title="Eating out">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 002-2V2"/><path d="M7 2v20"/><path d="M21 15V2v0a5 5 0 00-5 5v6c0 1.1.9 2 2 2h3zm0 0v7"/></svg>
          <span>Eating Out</span>
        </button>
      </div>
      <input type="file" id="camera-input" accept="image/*" capture="environment" style="display:none">
      <input type="file" id="gallery-input" accept="image/*" style="display:none">
      <div class="parse-result" id="parse-result"></div>
      <div class="camera-preview" id="camera-preview"></div>
      <div class="barcode-scanner" id="barcode-scanner"></div>
    `;
  },

  bindFoodInput() {
    // Date picker
    this.selectedDate = null;
    UI.$('#food-date')?.addEventListener('change', () => {
      const val = UI.$('#food-date')?.value;
      const todayKey = Store.getTodayKey();
      const label = UI.$('#food-date-label');
      if (val && val !== todayKey) {
        this.selectedDate = val;
        const d = new Date(val + 'T12:00:00');
        label.textContent = d.toLocaleDateString('en', { weekday: 'short', month: 'short', day: 'numeric' });
        label.classList.add('past-date');
      } else {
        this.selectedDate = null;
        label.textContent = 'Today';
        label.classList.remove('past-date');
      }
    });

    UI.$('#btn-parse')?.addEventListener('click', () => this.handleParse());
    UI.$('#food-text')?.addEventListener('keydown', e => {
      if (e.key === 'Enter') this.handleParse();
    });
    UI.$('#btn-camera')?.addEventListener('click', () => this.showCameraOptions());
    UI.$('#btn-barcode')?.addEventListener('click', () => this.startBarcodeScanner());
    UI.$('#btn-voice')?.addEventListener('click', () => this.toggleVoice());
    UI.$('#btn-restaurant')?.addEventListener('click', () => this.showRestaurantMode());

    UI.$('#camera-input')?.addEventListener('change', e => this.handleImageCapture(e));
    UI.$('#gallery-input')?.addEventListener('change', e => this.handleImageCapture(e));
  },

  // === TEXT PARSE ===
  async handleParse() {
    const input = UI.$('#food-text');
    const text = input.value.trim();
    if (!text) return;

    const profile = Store.getProfile();
    if (!profile.apiKey) {
      UI.toast('Set your API key in Profile first', 'error');
      App.navigate('profile');
      return;
    }

    UI.showLoading('Analyzing your meal...');

    try {
      const result = await LLM.parseFood(text);
      this.pendingParse = { description: text, ...result };
      this.showParseResult(result);
    } catch (err) {
      UI.toast(err.message, 'error');
    } finally {
      UI.hideLoading();
    }
  },

  // === CAMERA / PHOTO ===
  showCameraOptions() {
    const preview = UI.$('#camera-preview');
    preview.innerHTML = `
      <div class="camera-options card">
        <div class="card-title">Add food photo</div>
        <div class="camera-btns">
          <button class="btn btn-full" id="btn-take-photo">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z"/><circle cx="12" cy="13" r="4"/></svg>
            Take Photo
          </button>
          <button class="btn btn-outline btn-full" id="btn-pick-gallery">Choose from Gallery</button>
          <button class="btn btn-outline btn-full" id="btn-cancel-camera" style="color:var(--text-dim);border-color:var(--border)">Cancel</button>
        </div>
      </div>
    `;
    UI.show(preview);

    UI.$('#btn-take-photo').addEventListener('click', () => {
      UI.hide(preview);
      UI.$('#camera-input').click();
    });
    UI.$('#btn-pick-gallery').addEventListener('click', () => {
      UI.hide(preview);
      UI.$('#gallery-input').click();
    });
    UI.$('#btn-cancel-camera').addEventListener('click', () => UI.hide(preview));
  },

  async handleImageCapture(e) {
    const file = e.target.files[0];
    if (!file) return;
    e.target.value = '';

    const profile = Store.getProfile();
    if (!profile.apiKey) {
      UI.toast('Set your API key in Profile first', 'error');
      App.navigate('profile');
      return;
    }

    // Show image preview
    const preview = UI.$('#camera-preview');
    const imgUrl = URL.createObjectURL(file);
    preview.innerHTML = `
      <div class="card">
        <div class="card-title">Analyzing photo...</div>
        <img src="${imgUrl}" class="food-photo-preview" alt="Food photo">
      </div>
    `;
    UI.show(preview);

    UI.showLoading('Analyzing your food photo...');

    try {
      const base64 = await this._fileToBase64(file);
      const result = await LLM.parseFoodImage(base64);
      this.pendingParse = { description: 'Photo: ' + result.items.map(i => i.name).join(', '), ...result };
      UI.hide(preview);
      URL.revokeObjectURL(imgUrl);
      this.showParseResult(result);
    } catch (err) {
      UI.toast(err.message, 'error');
      UI.hide(preview);
    } finally {
      UI.hideLoading();
    }
  },

  _fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      const objUrl = URL.createObjectURL(file);
      img.onload = () => {
        URL.revokeObjectURL(objUrl);
        const canvas = document.createElement('canvas');
        const maxSize = 1024;
        let w = img.width, h = img.height;
        if (w > maxSize || h > maxSize) {
          if (w > h) { h = Math.round(h * maxSize / w); w = maxSize; }
          else { w = Math.round(w * maxSize / h); h = maxSize; }
        }
        canvas.width = w;
        canvas.height = h;
        canvas.getContext('2d').drawImage(img, 0, 0, w, h);
        const dataUrl = canvas.toDataURL('image/jpeg', 0.8);
        resolve(dataUrl.split(',')[1]);
      };
      img.onerror = () => { URL.revokeObjectURL(objUrl); reject(new Error('Failed to load image')); };
      img.src = objUrl;
    });
  },

  // === BARCODE SCANNER ===
  async startBarcodeScanner() {
    const container = UI.$('#barcode-scanner');
    container.innerHTML = `
      <div class="card">
        <div class="card-title">Scan Barcode</div>
        <div class="barcode-video-wrap" id="barcode-viewport"></div>
        <div class="barcode-status" id="barcode-status">Point camera at barcode...</div>
        <button class="btn btn-outline btn-full" id="btn-cancel-barcode" style="margin-top:8px">Cancel</button>
        <button class="btn btn-outline btn-full" id="btn-manual-barcode" style="margin-top:4px;color:var(--text-dim);border-color:var(--border)">Enter code manually</button>
      </div>
    `;
    UI.show(container);

    UI.$('#btn-cancel-barcode').addEventListener('click', () => this._stopBarcodeScanner());
    UI.$('#btn-manual-barcode').addEventListener('click', () => {
      this._stopBarcodeScanner();
      this._showManualBarcode();
    });

    // Try QuaggaJS first, then native BarcodeDetector, then manual
    if (typeof Quagga !== 'undefined') {
      this._startQuaggaScanner();
    } else if ('BarcodeDetector' in window) {
      this._startNativeBarcode();
    } else {
      UI.hide(container);
      this._showManualBarcode();
      UI.toast('Camera barcode scanning not available. Enter manually.', 'error');
    }
  },

  _startQuaggaScanner() {
    Quagga.init({
      inputStream: {
        name: 'Live',
        type: 'LiveStream',
        target: document.querySelector('#barcode-viewport'),
        constraints: {
          facingMode: 'environment',
          width: { ideal: 1280 },
          height: { ideal: 720 }
        }
      },
      decoder: {
        readers: ['ean_reader', 'ean_8_reader', 'upc_reader', 'upc_e_reader', 'code_128_reader']
      },
      locate: true,
      frequency: 10
    }, (err) => {
      if (err) {
        this._stopBarcodeScanner();
        this._showManualBarcode();
        UI.toast('Camera access failed. Enter barcode manually.', 'error');
        return;
      }
      Quagga.start();
      this._quaggaRunning = true;
    });

    Quagga.onDetected((result) => {
      if (result?.codeResult?.code) {
        const code = result.codeResult.code;
        UI.$('#barcode-status').textContent = `Found: ${code}`;
        this._stopBarcodeScanner();
        this._lookupBarcode(code);
      }
    });
  },

  async _startNativeBarcode() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } }
      });
      const viewport = UI.$('#barcode-viewport');
      const video = document.createElement('video');
      video.autoplay = true;
      video.playsInline = true;
      video.srcObject = stream;
      viewport.appendChild(video);
      this._barcodeStream = stream;

      const detector = new BarcodeDetector({ formats: ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128'] });

      const scan = async () => {
        if (!this._barcodeStream) return;
        try {
          const barcodes = await detector.detect(video);
          if (barcodes.length > 0) {
            this._stopBarcodeScanner();
            this._lookupBarcode(barcodes[0].rawValue);
            return;
          }
        } catch {}
        requestAnimationFrame(scan);
      };
      video.addEventListener('loadeddata', scan);
    } catch {
      this._stopBarcodeScanner();
      this._showManualBarcode();
      UI.toast('Camera access denied. Enter barcode manually.', 'error');
    }
  },

  _stopBarcodeScanner() {
    if (this._quaggaRunning) {
      try { Quagga.stop(); } catch {}
      this._quaggaRunning = false;
    }
    if (this._barcodeStream) {
      this._barcodeStream.getTracks().forEach(t => t.stop());
      this._barcodeStream = null;
    }
    UI.hide('#barcode-scanner');
  },

  _showManualBarcode() {
    const container = UI.$('#barcode-scanner');
    container.innerHTML = `
      <div class="card">
        <div class="card-title">Enter Barcode</div>
        <div class="food-input-wrap">
          <input type="text" class="food-input" id="barcode-input" placeholder="Enter barcode number..." inputmode="numeric">
          <button class="btn" id="btn-lookup-barcode">Look up</button>
        </div>
        <button class="btn btn-outline btn-full" id="btn-cancel-manual-barcode" style="margin-top:8px;color:var(--text-dim);border-color:var(--border)">Cancel</button>
      </div>
    `;
    UI.show(container);

    UI.$('#btn-lookup-barcode').addEventListener('click', () => {
      const code = UI.$('#barcode-input').value.trim();
      if (code) {
        UI.hide(container);
        this._lookupBarcode(code);
      }
    });
    UI.$('#barcode-input').addEventListener('keydown', e => {
      if (e.key === 'Enter') {
        const code = UI.$('#barcode-input').value.trim();
        if (code) {
          UI.hide(container);
          this._lookupBarcode(code);
        }
      }
    });
    UI.$('#btn-cancel-manual-barcode').addEventListener('click', () => UI.hide(container));
  },

  async _lookupBarcode(code) {
    UI.showLoading('Looking up product...');

    try {
      const res = await fetch(`https://world.openfoodfacts.org/api/v2/product/${code}.json`);
      if (!res.ok) throw new Error('Product not found');

      const data = await res.json();
      if (data.status !== 1 || !data.product) throw new Error('Product not found');

      const p = data.product;
      const n = p.nutriments || {};
      const servingSize = p.serving_size || '100g';
      const name = p.product_name || 'Unknown product';

      // Prefer per-serving, fallback to per 100g
      const cal = Math.round(n['energy-kcal_serving'] || n['energy-kcal_100g'] || 0);
      const protein = Math.round(n.proteins_serving || n.proteins_100g || 0);
      const carbs = Math.round(n.carbohydrates_serving || n.carbohydrates_100g || 0);
      const fat = Math.round(n.fat_serving || n.fat_100g || 0);
      const sugar = Math.round(n.sugars_serving || n.sugars_100g || 0);

      // Packaged foods = processed sugar by default
      const item = { name: `${name} (${servingSize})`, calories: cal, protein, carbs, fat, sugar_natural: 0, sugar_processed: sugar };

      const result = {
        items: [item],
        total: { calories: cal, protein, carbs, fat, sugar_natural: 0, sugar_processed: sugar }
      };

      this.pendingParse = { description: `Barcode: ${name}`, ...result };
      this.showParseResult(result);
    } catch (err) {
      UI.toast('Product not found. Try entering the food manually.', 'error');
    } finally {
      UI.hideLoading();
    }
  },

  // === VOICE INPUT ===
  toggleVoice() {
    if (this.isListening) {
      this.stopVoice();
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      UI.toast('Voice input not supported in this browser', 'error');
      return;
    }

    this.recognition = new SpeechRecognition();
    this.recognition.continuous = false;
    this.recognition.interimResults = true;
    this.recognition.lang = navigator.language || 'en-US';

    const btn = UI.$('#btn-voice');
    const input = UI.$('#food-text');

    this.recognition.onstart = () => {
      this.isListening = true;
      btn.classList.add('listening');
      input.placeholder = 'Listening...';
    };

    this.recognition.onresult = (e) => {
      let transcript = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        transcript += e.results[i][0].transcript;
      }
      input.value = transcript;
    };

    this.recognition.onend = () => {
      this.isListening = false;
      btn.classList.remove('listening');
      input.placeholder = 'What did you eat?';
      // Auto-parse if we got text
      if (input.value.trim()) {
        this.handleParse();
      }
    };

    this.recognition.onerror = (e) => {
      this.isListening = false;
      btn.classList.remove('listening');
      input.placeholder = 'What did you eat?';
      if (e.error === 'not-allowed') {
        UI.toast('Microphone access denied', 'error');
      } else if (e.error !== 'aborted') {
        UI.toast('Voice input error. Try again.', 'error');
      }
    };

    this.recognition.start();
  },

  stopVoice() {
    if (this.recognition) {
      this.recognition.stop();
      this.recognition = null;
    }
    this.isListening = false;
    UI.$('#btn-voice')?.classList.remove('listening');
  },

  // === SHARED UI ===
  showParseResult(result) {
    const container = UI.$('#parse-result');
    container.innerHTML = `
      <div class="card">
        <div class="card-title">Parsed Items</div>
        ${result.items.map((item, i) => `
          <div class="parse-item">
            <span class="parse-item-name">${UI.esc(item.name)}</span>
            <div class="parse-item-macros">
              <span>${item.calories} cal</span>
              <span>${item.protein}g P</span>
              <span>${item.carbs}g C</span>
              <span>${item.fat}g F</span>
              ${(item.sugar_natural || item.sugar_processed) ? `<span>${(item.sugar_natural||0)+(item.sugar_processed||0)}g S</span>` : ''}
            </div>
          </div>
        `).join('')}
        <div class="parse-item" style="font-weight:600;border-top:2px solid var(--border)">
          <span class="parse-item-name">Total</span>
          <div class="parse-item-macros">
            <span>${result.total.calories} cal</span>
            <span>${result.total.protein}g P</span>
            <span>${result.total.carbs}g C</span>
            <span>${result.total.fat}g F</span>
          </div>
        </div>
        <div class="parse-actions">
          <button class="btn btn-outline" id="btn-cancel-parse">Cancel</button>
          <button class="btn" id="btn-confirm-parse">Confirm & Save</button>
        </div>
      </div>
    `;
    UI.show(container);

    UI.$('#btn-confirm-parse').addEventListener('click', () => this.confirmMeal());
    UI.$('#btn-cancel-parse').addEventListener('click', () => {
      UI.hide(container);
      this.pendingParse = null;
    });
  },

  confirmMeal() {
    if (!this.pendingParse) return;

    const dateKey = this.selectedDate || null;
    const timeStr = dateKey
      ? new Date(dateKey + 'T12:00:00').toISOString()
      : new Date().toISOString();

    const meal = {
      time: timeStr,
      description: this.pendingParse.description,
      items: this.pendingParse.items,
      total: this.pendingParse.total
    };

    Store.addMeal(meal, dateKey);
    UI.hide('#parse-result');
    UI.$('#food-text').value = '';
    this.pendingParse = null;

    const label = dateKey
      ? new Date(dateKey + 'T12:00:00').toLocaleDateString('en', { month: 'short', day: 'numeric' })
      : 'today';
    UI.toast(`Meal logged for ${label}!`, 'success');
    App.refreshDashboard();

    // Show feeling prompt only for today's meals
    if (!dateKey) {
      const todayMeals = Store.getTodayMeals();
      const mealIndex = todayMeals.length - 1;
      setTimeout(() => this.showFeelingPrompt(Store.getTodayKey(), mealIndex, meal.description), 500);
    }
  },

  // === POST-MEAL FEELING TRACKER ===
  feelingEmojis: {
    energy: { high: ['&#9889;', 'Energized'], normal: ['&#128578;', 'Normal'], low: ['&#128564;', 'Tired'] },
    digestion: { good: ['&#128077;', 'Good'], normal: ['&#128528;', 'Okay'], bad: ['&#128556;', 'Upset'] },
    mood: { good: ['&#128522;', 'Great'], normal: ['&#128528;', 'Neutral'], bad: ['&#128542;', 'Low'] }
  },

  showFeelingPrompt(dateKey, mealIndex, mealDesc) {
    // Don't show if already rated
    if (Store.getMealFeeling(dateKey, mealIndex)) return;

    const container = UI.$('#parse-result');
    if (!container) return;

    const shortDesc = (mealDesc || 'this meal').substring(0, 40) + (mealDesc?.length > 40 ? '...' : '');

    container.innerHTML = `
      <div class="card feeling-prompt">
        <div class="feeling-prompt-header">
          <div class="card-title">How do you feel?</div>
          <div class="feeling-prompt-desc">After eating ${UI.esc(shortDesc)}</div>
        </div>

        <div class="feeling-category">
          <div class="feeling-label">Energy</div>
          <div class="feeling-options" id="feeling-energy">
            <button class="feeling-btn" data-val="high"><span class="feeling-emoji">&#9889;</span><span class="feeling-text">Energized</span></button>
            <button class="feeling-btn" data-val="normal"><span class="feeling-emoji">&#128578;</span><span class="feeling-text">Normal</span></button>
            <button class="feeling-btn" data-val="low"><span class="feeling-emoji">&#128564;</span><span class="feeling-text">Tired</span></button>
          </div>
        </div>

        <div class="feeling-category">
          <div class="feeling-label">Digestion</div>
          <div class="feeling-options" id="feeling-digestion">
            <button class="feeling-btn" data-val="good"><span class="feeling-emoji">&#128077;</span><span class="feeling-text">Good</span></button>
            <button class="feeling-btn" data-val="normal"><span class="feeling-emoji">&#128528;</span><span class="feeling-text">Okay</span></button>
            <button class="feeling-btn" data-val="bad"><span class="feeling-emoji">&#128556;</span><span class="feeling-text">Upset</span></button>
          </div>
        </div>

        <div class="feeling-category">
          <div class="feeling-label">Mood</div>
          <div class="feeling-options" id="feeling-mood">
            <button class="feeling-btn" data-val="good"><span class="feeling-emoji">&#128522;</span><span class="feeling-text">Great</span></button>
            <button class="feeling-btn" data-val="normal"><span class="feeling-emoji">&#128528;</span><span class="feeling-text">Neutral</span></button>
            <button class="feeling-btn" data-val="bad"><span class="feeling-emoji">&#128542;</span><span class="feeling-text">Low</span></button>
          </div>
        </div>

        <div class="feeling-category">
          <label class="feeling-check-label">
            <input type="checkbox" id="feeling-bloating">
            <span>Feeling bloated</span>
          </label>
        </div>

        <div class="feeling-category">
          <input type="text" class="food-input" id="feeling-note" placeholder="Any notes? (optional)" style="font-size:13px">
        </div>

        <div class="parse-actions">
          <button class="btn btn-outline" id="btn-skip-feeling">Skip</button>
          <button class="btn" id="btn-save-feeling">Save</button>
        </div>
      </div>
    `;
    UI.show(container);

    // Bind selection toggles
    ['feeling-energy', 'feeling-digestion', 'feeling-mood'].forEach(id => {
      UI.$('#' + id)?.addEventListener('click', e => {
        const btn = e.target.closest('.feeling-btn');
        if (!btn) return;
        UI.$$('#' + id + ' .feeling-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
      });
    });

    UI.$('#btn-skip-feeling')?.addEventListener('click', () => {
      UI.hide(container);
    });

    UI.$('#btn-save-feeling')?.addEventListener('click', () => {
      const energy = UI.$('#feeling-energy .feeling-btn.active')?.dataset.val || null;
      const digestion = UI.$('#feeling-digestion .feeling-btn.active')?.dataset.val || null;
      const mood = UI.$('#feeling-mood .feeling-btn.active')?.dataset.val || null;
      const bloating = UI.$('#feeling-bloating')?.checked || false;
      const note = UI.$('#feeling-note')?.value.trim() || '';

      if (!energy && !digestion && !mood && !bloating) {
        UI.toast('Select at least one feeling', 'error');
        return;
      }

      Store.addMealFeeling(dateKey, mealIndex, {
        energy, digestion, mood, bloating, note
      });

      UI.hide(container);
      UI.toast('Feeling logged! This helps personalize your coaching.', 'success');
      App.refreshDashboard();
    });
  },

  renderMealsList(meals) {
    if (!meals.length) {
      return `<div class="empty-state">
        <div class="empty-state-icon">&#127869;</div>
        <div class="empty-state-text">No meals logged today<br>Start by entering what you ate above</div>
      </div>`;
    }

    const todayKey = Store.getTodayKey();
    const dayFeelings = Store.getDayFeelings(todayKey);
    const emojiMap = {
      energy: { high: '&#9889;', normal: '&#128578;', low: '&#128564;' },
      digestion: { good: '&#128077;', normal: '&#128528;', bad: '&#128556;' },
      mood: { good: '&#128522;', normal: '&#128528;', bad: '&#128542;' }
    };

    return meals.map((meal, i) => {
      const feeling = dayFeelings[i];
      let feelingHTML = '';

      if (feeling) {
        const badges = [];
        if (feeling.energy) badges.push(`<span class="feeling-badge feeling-${feeling.energy === 'low' || feeling.energy === 'bad' ? 'neg' : feeling.energy === 'normal' ? 'neutral' : 'pos'}">${emojiMap.energy[feeling.energy]} ${feeling.energy}</span>`);
        if (feeling.digestion) badges.push(`<span class="feeling-badge feeling-${feeling.digestion === 'bad' ? 'neg' : feeling.digestion === 'normal' ? 'neutral' : 'pos'}">${emojiMap.digestion[feeling.digestion]} ${feeling.digestion}</span>`);
        if (feeling.mood) badges.push(`<span class="feeling-badge feeling-${feeling.mood === 'bad' ? 'neg' : feeling.mood === 'normal' ? 'neutral' : 'pos'}">${emojiMap.mood[feeling.mood]} ${feeling.mood}</span>`);
        if (feeling.bloating) badges.push('<span class="feeling-badge feeling-neg">bloated</span>');
        feelingHTML = `<div class="meal-feelings">${badges.join('')}</div>`;
      } else {
        feelingHTML = `<button class="feeling-add-btn" data-date="${todayKey}" data-index="${i}" data-desc="${UI.esc(meal.description || '')}">+ How did you feel?</button>`;
      }

      return `
        <div class="meal-card">
          <div class="meal-card-header">
            <span class="meal-time">${UI.formatTime(meal.time)}</span>
            <button class="meal-delete" data-index="${i}" title="Delete">&times;</button>
          </div>
          <div class="meal-name">${UI.esc(meal.description || meal.items?.map(it => it.name).join(', '))}</div>
          <div class="meal-macros">
            <span>${UI.macroDot('cal')} ${meal.total.calories} cal</span>
            <span>${UI.macroDot('protein')} ${meal.total.protein}g P</span>
            <span>${UI.macroDot('carb')} ${meal.total.carbs}g C</span>
            <span>${UI.macroDot('fat')} ${meal.total.fat}g F</span>
          </div>
          ${feelingHTML}
        </div>
      `;
    }).join('');
  },

  bindDeleteButtons() {
    UI.$$('.meal-delete').forEach(btn => {
      btn.addEventListener('click', e => {
        const index = parseInt(e.target.dataset.index);
        Store.deleteMeal(index);
        UI.toast('Meal deleted', '');
        App.refreshDashboard();
      });
    });

    // Bind "How did you feel?" buttons on past meals
    UI.$$('.feeling-add-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const dateKey = btn.dataset.date;
        const mealIndex = parseInt(btn.dataset.index);
        const desc = btn.dataset.desc;
        this.showFeelingPrompt(dateKey, mealIndex, desc);
      });
    });
  },

  // === RESTAURANT MODE ===
  showRestaurantMode() {
    const html = `
      <div class="modal-overlay show" id="restaurant-modal">
        <div class="recipe-detail-sheet" style="max-height:85vh;overflow-y:auto">
          <div class="rd-header">
            <button class="rd-close" id="restaurant-close">&times;</button>
            <div class="rd-name">Eating Out</div>
            <div class="rd-desc">Get macro estimates for restaurant meals</div>
          </div>
          <div style="padding:0 16px">
            <input type="text" class="food-input" id="restaurant-name" placeholder="Restaurant name (optional)" style="margin-bottom:8px">
            <textarea class="food-input" id="restaurant-items" rows="4" placeholder="Enter dish names (one per line)&#10;e.g. Chicken Caesar Salad&#10;Grilled Salmon&#10;Pasta Bolognese" style="resize:vertical;min-height:80px"></textarea>
            <div class="restaurant-btn-row">
              <button class="btn" id="restaurant-quick-btn" style="flex:1">Quick Estimate</button>
              <button class="btn btn-outline" id="restaurant-ai-btn" style="flex:1">AI Estimate</button>
            </div>
          </div>
          <div id="restaurant-results" style="padding:0 16px 16px"></div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML('beforeend', html);

    UI.$('#restaurant-close')?.addEventListener('click', () => UI.$('#restaurant-modal')?.remove());
    UI.$('#restaurant-modal')?.addEventListener('click', e => {
      if (e.target.id === 'restaurant-modal') UI.$('#restaurant-modal')?.remove();
    });

    UI.$('#restaurant-quick-btn')?.addEventListener('click', () => this._restaurantEstimate(false));
    UI.$('#restaurant-ai-btn')?.addEventListener('click', () => this._restaurantEstimate(true));
  },

  async _restaurantEstimate(useAI) {
    const itemsText = UI.$('#restaurant-items')?.value?.trim();
    const restaurant = UI.$('#restaurant-name')?.value?.trim() || '';
    if (!itemsText && !restaurant) {
      UI.toast('Enter dish names or a restaurant name', 'error');
      return;
    }

    const items = itemsText ? itemsText.split('\n').map(l => l.trim()).filter(Boolean) : [];
    const totals = Store.getTodayTotals();
    const profile = Store.getProfile();
    const remaining = {
      calories: Math.max(0, profile.macros.calories - totals.calories),
      protein: Math.max(0, profile.macros.protein - totals.protein),
      carbs: Math.max(0, profile.macros.carbs - totals.carbs),
      fat: Math.max(0, profile.macros.fat - totals.fat),
    };

    const resultsEl = UI.$('#restaurant-results');
    resultsEl.innerHTML = '<div class="recipe-loading">Estimating...</div>';

    try {
      const endpoint = useAI ? '/api/tracker/restaurant' : '/api/tracker/restaurant-quick';
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          restaurant,
          items: items.length > 0 ? items : undefined,
          remaining_macros: remaining,
          goal: profile.goal || 'maintenance',
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || 'Estimation failed');
      }
      const data = await res.json();
      this._renderRestaurantResults(data, remaining);
    } catch (err) {
      resultsEl.innerHTML = `<div class="recipe-empty">${err.message}</div>`;
    }
  },

  _renderRestaurantResults(data, remaining) {
    const resultsEl = UI.$('#restaurant-results');
    if (!resultsEl) return;

    const estimates = data.estimates || [];
    const bestPick = data.best_pick;

    resultsEl.innerHTML = `
      ${bestPick ? `
        <div class="restaurant-best-pick">
          <div class="restaurant-best-label">Best Pick</div>
          <div class="restaurant-best-name">${bestPick.name}</div>
          <div class="restaurant-best-reason">${bestPick.reason}</div>
        </div>
      ` : ''}
      <div class="restaurant-estimates">
        ${estimates.map((e, idx) => `
          <div class="restaurant-item ${bestPick && e.name === bestPick.name ? 'is-best' : ''}">
            <div class="restaurant-item-header">
              <span class="restaurant-item-name">${e.name}</span>
              ${e.macro_fit_score ? `<span class="restaurant-fit-score" style="--fit:${e.macro_fit_score}">${e.macro_fit_score}/10</span>` : ''}
            </div>
            <div class="suggestion-macros" style="margin:4px 0">
              <span style="color:var(--cal-color)">${e.calories} cal</span>
              <span style="color:var(--protein-color)">${e.protein}g P</span>
              <span style="color:var(--carb-color)">${e.carbs}g C</span>
              <span style="color:var(--fat-color)">${e.fat}g F</span>
            </div>
            ${e.portion_note ? `<div class="restaurant-note">${e.portion_note}</div>` : ''}
            ${e.tip ? `<div class="restaurant-tip">${e.tip}</div>` : ''}
            ${e.source ? `<div class="restaurant-source">${e.source === 'database' ? 'From database' : e.source === 'estimate' ? 'Estimated' : 'Approximate'}</div>` : ''}
            <button class="btn btn-outline restaurant-log-btn" data-idx="${idx}" style="margin-top:6px;padding:6px 12px;font-size:12px">Log This</button>
          </div>
        `).join('')}
      </div>
      ${data.general_tips ? `
        <div class="restaurant-tips">
          ${data.general_tips.map(t => `<div class="restaurant-general-tip">${t}</div>`).join('')}
        </div>
      ` : ''}
    `;

    // Bind log buttons
    resultsEl.querySelectorAll('.restaurant-log-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.dataset.idx);
        const e = estimates[idx];
        if (!e) return;
        Store.addMeal({
          time: new Date().toISOString(),
          description: `${e.name} (restaurant)`,
          items: [{ name: e.name, calories: e.calories, protein: e.protein, carbs: e.carbs, fat: e.fat, sugar_natural: 0, sugar_processed: 0, fiber: e.fiber || 0 }],
          total: { calories: e.calories, protein: e.protein, carbs: e.carbs, fat: e.fat, sugar_natural: 0, sugar_processed: 0, fiber: e.fiber || 0 },
        });
        btn.textContent = 'Logged!';
        btn.disabled = true;
        UI.toast(`${e.name} logged!`, 'success');
        App.refreshDashboard();
      });
    });
  },
};

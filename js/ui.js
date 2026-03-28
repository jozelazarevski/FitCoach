const UI = {
  $(sel) { return document.querySelector(sel); },
  $$(sel) { return document.querySelectorAll(sel); },

  show(el) { if (typeof el === 'string') el = this.$(el); el?.classList.add('show'); },
  hide(el) { if (typeof el === 'string') el = this.$(el); el?.classList.remove('show'); },

  toast(msg, type = '') {
    const t = this.$('.toast');
    t.textContent = msg;
    t.className = 'toast' + (type ? ' ' + type : '');
    this.show(t);
    setTimeout(() => this.hide(t), 2500);
  },

  showLoading(msg = 'Analyzing...') {
    this.$('.loading-text').textContent = msg;
    this.show('.loading-overlay');
  },

  hideLoading() {
    this.hide('.loading-overlay');
  },

  formatNum(n) {
    return Math.round(n).toLocaleString();
  },

  formatTime(date) {
    if (typeof date === 'string') date = new Date(date);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  },

  formatDate(dateStr) {
    const d = new Date(dateStr + 'T12:00:00');
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    if (dateStr === today.toISOString().split('T')[0]) return 'Today';
    if (dateStr === yesterday.toISOString().split('T')[0]) return 'Yesterday';

    return d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
  },

  progressPercent(current, target) {
    if (!target) return 0;
    return Math.min(100, Math.round((current / target) * 100));
  },

  macroDot(type) {
    const colors = { cal: 'var(--cal-color)', protein: 'var(--protein-color)', carb: 'var(--carb-color)', fat: 'var(--fat-color)' };
    return `<span class="dot" style="background:${colors[type]}"></span>`;
  }
};

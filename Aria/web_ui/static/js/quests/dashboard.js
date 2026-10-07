/**
 * Aria Quest Dashboard - Interactive Logic
 * Modern 2026 Dashboard Implementation
 */

class QuestDashboard {
  constructor() {
    this.currentPage = 'overview';
    this.quests = {
      active: [],
      available: [],
      completed: [],
      claimable: []
    };
    this.autoComplete = false;
    this.questLoadPromise = null;
    this.questRefreshTimer = null;
    this.questDataLoaded = false;
    this.lastQuestDataSuccess = 0;
    this.init();
  }

  init() {
    this.setupEventListeners();
    this.loadQuestData().finally(() => this.hideLoader());
    this.questRefreshTimer = window.setInterval(() => {
      const refreshDue = !this.questDataLoaded || Date.now() - this.lastQuestDataSuccess >= 5 * 60 * 1000;
      if (!document.hidden && refreshDue) this.loadQuestData();
    }, 30 * 1000);
  }

  setupEventListeners() {
    // Settings
    document.getElementById('darkMode')?.addEventListener('change', (e) => this.toggleDarkMode(e.target.checked));
    document.getElementById('compactView')?.addEventListener('change', (e) => this.toggleCompactView(e.target.checked));
  }

  navigateTo(section) {
    if (typeof window.navigateTo === 'function') window.navigateTo(section);
    this.currentPage = section;
  }

  async api(path, options) {
    const init = { ...(options || {}) };
    if (init.method && init.method !== 'GET') {
      init.headers = {
        ...(init.headers || {}),
        'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]')?.content || ''
      };
    }
    const response = await fetch(path, init);
    let body = null;
    try { body = await response.json(); } catch (e) { /* non-JSON error page */ }
    if (!response.ok || (body && body.ok === false)) {
      const error = new Error((body && body.error) || `HTTP ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return body || {};
  }

  esc(value) {
    return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  async loadQuestData(force = false) {
    if (this.questLoadPromise) return this.questLoadPromise;
    this.questLoadPromise = this.fetchQuestData(force);
    try {
      return await this.questLoadPromise;
    } finally {
      this.questLoadPromise = null;
    }
  }

  async fetchQuestData(force = false) {
    const maxAttempts = 5;
    let lastError = null;
    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      try {
        const data = await this.api('/api/quests/@me' + (force ? '?refresh=1' : ''));
        if (!Array.isArray(data.quests)) {
          throw new Error('Quest API returned an invalid quest list.');
        }
        const quests = data.quests;
        const now = Date.now();
        const live = quests.filter(q => !this.isQuestExpired(q, now) || q.user_status?.completed_at);
        this.quests.active = live.filter(q => q.user_status?.enrolled_at && !q.user_status?.completed_at);
        this.quests.available = live.filter(q => !q.user_status?.enrolled_at && !q.user_status?.completed_at);
        this.quests.completed = live.filter(q => q.user_status?.completed_at);
        this.quests.claimable = live.filter(q => q.user_status?.completed_at && !q.user_status?.claimed_at);
        this.autoComplete = !!data.auto_complete;
        this.questDataLoaded = true;
        this.lastQuestDataSuccess = Date.now();
        this.syncAutoButton();
        this.renderQuests();
        this.updateStats();
        return true;
      } catch (error) {
        lastError = error;
        const retryable = !error.status || error.status >= 500;
        if (!retryable || attempt === maxAttempts) break;
        await new Promise(resolve => window.setTimeout(resolve, attempt * 1000));
      }
    }

    console.error('Failed to load quests:', lastError);
    if (!this.questDataLoaded) this.setQuestStatsUnavailable();
    this.showToast('Quests: ' + (lastError?.message || 'Unable to load quests.'), 'error');
    return false;
  }

  isQuestExpired(quest, now) {
    const expiresAt = quest?.config?.expires_at;
    if (expiresAt === null || expiresAt === undefined || expiresAt === '') return false;

    let timestamp;
    if (typeof expiresAt === 'number' || /^\d+(?:\.\d+)?$/.test(String(expiresAt).trim())) {
      timestamp = Number(expiresAt);
      if (timestamp > 0 && timestamp < 1e12) timestamp *= 1000;
    } else {
      timestamp = Date.parse(expiresAt);
    }
    return Number.isFinite(timestamp) && timestamp <= now;
  }

  syncAutoButton() {
    const btn = document.getElementById('autoCompleteToggle');
    if (!btn) return;
    btn.classList.toggle('active', this.autoComplete);
    const title = btn.querySelector('.action-title');
    if (title) title.textContent = this.autoComplete ? 'Stop Auto-Complete' : 'Start Auto-Complete';
  }

  renderQuests() {
    // Render active quests
    const activeContainer = document.querySelector('[data-section-content="quests-overview"] .active-quests');
    if (activeContainer) {
      activeContainer.innerHTML = this.quests.active.length > 0
        ? this.quests.active.map(q => this.createQuestCard(q)).join('')
        : this.getEmptyState('No active quests', '⏳');
    }

    const activeList = document.querySelector('[data-section-content="quests-active"] .quests-list');
    if (activeList) {
      activeList.innerHTML = this.quests.active.length > 0
        ? this.quests.active.map(q => this.createQuestCard(q)).join('')
        : this.getEmptyState('No active quests', '⏳');
    }

    // Render available quests
    const availableContainer = document.querySelector('[data-section-content="quests-available"] .quests-list');
    if (availableContainer) {
      availableContainer.innerHTML = this.quests.available.length > 0 
        ? this.quests.available.map(q => this.createQuestCard(q)).join('')
        : this.getEmptyState('No available quests', '🔍');
    }

    // Render completed quests
    const completedContainer = document.querySelector('[data-section-content="quests-completed"] .quests-list');
    if (completedContainer) {
      completedContainer.innerHTML = this.quests.completed.length > 0 
        ? this.quests.completed.map(q => this.createQuestCard(q, 'completed')).join('')
        : this.getEmptyState('No completed quests', '✨');
    }

    // Render claimable quests
    const claimContainer = document.querySelector('[data-section-content="quests-claim"] .quests-list');
    if (claimContainer) {
      claimContainer.innerHTML = this.quests.claimable.length > 0 
        ? this.quests.claimable.map(q => this.createQuestCard(q, 'claimable')).join('')
        : this.getEmptyState('No rewards to claim', '🎁');
    }
  }

  createQuestCard(quest, state = 'active') {
    const config = quest.config || {};
    const userStatus = quest.user_status;
    const progress = this.getQuestProgress(quest);
    const progressPercent = progress.total ? (progress.done / progress.total) * 100 : 0;

    const badge = state === 'completed' ? 'completed' 
                : state === 'claimable' ? 'claimable'
                : userStatus?.enrolled_at ? 'active' 
                : 'available';

    const reward = config.rewards_config?.rewards?.[0];
    const rewardTier = reward?.reward_type?.includes('gold') ? 'gold'
                     : reward?.reward_type?.includes('silver') ? 'silver'
                     : 'bronze';

    return `
      <div class="quest-card reward-tier-${rewardTier}">
        <div class="quest-header">
          <div>
            <h3 class="quest-title">${this.esc(config.messages?.quest_name || 'Untitled Quest')}</h3>
            <p class="quest-game">${this.esc(config.application?.name || 'Unknown')}</p>
          </div>
          <span class="quest-badge ${badge}">${this.formatBadge(badge)}</span>
        </div>

        <p class="quest-description">${this.esc(config.messages?.quest_description || '')}</p>

        ${state !== 'completed' && state !== 'claimable' ? `
          <div class="quest-progress">
            <div class="progress-info">
              <span class="progress-label">${this.esc(progress.event)}</span>
              <span class="progress-value">${progress.done}/${progress.total}</span>
            </div>
            <div class="progress-bar">
              <div class="progress-fill" style="width: ${progressPercent}%"></div>
            </div>
          </div>
        ` : ''}

        <div class="quest-footer">
          <span class="quest-time">${this.getTimeRemaining(config.expires_at)}</span>
          <div class="quest-actions">
            ${state === 'active' ? `
              <button class="quest-action" onclick="dashboard.pauseQuest('${this.esc(quest.id)}')">Pause</button>
            ` : state === 'available' ? `
              <button class="quest-action" onclick="dashboard.enrollQuest('${this.esc(quest.id)}')">Enroll</button>
            ` : state === 'claimable' ? `
              <button class="quest-action" onclick="dashboard.claimReward('${this.esc(quest.id)}')">Claim</button>
            ` : ''}
          </div>
        </div>
      </div>
    `;
  }

  getQuestProgress(quest) {
    const userStatus = quest.user_status;
    const config = quest.config || {};
    const tasks = config.task_config_v2?.tasks || {};

    if (!userStatus?.progress) {
      return { event: 'No progress', done: 0, total: 100 };
    }

    let maxProgress = 0;
    let targetEvent = 'Unknown';
    let targetTotal = 100;

    for (const [eventName, progressData] of Object.entries(userStatus.progress)) {
      if ((progressData?.value || 0) > maxProgress) {
        maxProgress = progressData.value;
        targetEvent = eventName;
      }
    }

    // Get target from task config
    for (const task of Object.values(tasks)) {
      if (task.event_name === targetEvent) {
        targetTotal = task.target || 100;
        break;
      }
    }

    return {
      event: targetEvent,
      done: Math.min(maxProgress, targetTotal),
      total: targetTotal
    };
  }

  getTimeRemaining(expiresAt) {
    if (!expiresAt) return 'No expiry';
    
    const expires = new Date(expiresAt);
    const now = new Date();
    const diff = expires - now;
    
    if (diff < 0) return 'Expired';
    
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    if (days > 0) return `${days}d remaining`;
    
    const hours = Math.floor(diff / (1000 * 60 * 60));
    if (hours > 0) return `${hours}h remaining`;
    
    const minutes = Math.floor(diff / (1000 * 60));
    return `${minutes}m remaining`;
  }

  formatBadge(badge) {
    const badgeMap = {
      'active': '⏳ Active',
      'available': '🆕 Available',
      'completed': '✅ Completed',
      'claimable': '🎁 Claimable',
      'expired': '⏰ Expired'
    };
    return badgeMap[badge] || badge;
  }

  setText(selector, value) {
    document.querySelectorAll(selector).forEach(el => { el.textContent = value; });
  }

  updateStats() {
    this.setText('[data-stat="active"]' , this.quests.active.length);
    this.setText('[data-stat="available"]' , this.quests.available.length);
    this.setText('[data-stat="completed"]' , this.quests.completed.length);
    this.setText('[data-stat="claimable"]' , this.quests.claimable.length);

    // Update badges
    this.setText('[data-badge="active"]' , this.quests.active.length);
    this.setText('[data-badge="available"]' , this.quests.available.length);
    this.setText('[data-badge="completed"]' , this.quests.completed.length);
    this.setText('[data-badge="claimable"]' , this.quests.claimable.length);
  }

  setQuestStatsUnavailable() {
    ['active', 'available', 'completed', 'claimable'].forEach(stat => {
      this.setText(`[data-stat="${stat}"]`, '—');
      this.setText(`[data-badge="${stat}"]`, '—');
    });
  }

  async enrollQuest(questId, quiet = false) {
    try {
      await this.api(`/api/quests/${encodeURIComponent(questId)}/enroll`, { method: 'POST' });
      if (!quiet) { this.showToast('Enrolled in quest!', 'success'); await this.loadQuestData(); }
      return true;
    } catch (error) {
      this.showToast('Enroll failed: ' + error.message, 'error');
      return false;
    }
  }

  async claimReward(questId, quiet = false) {
    try {
      await this.api(`/api/quests/${encodeURIComponent(questId)}/claim-reward`, { method: 'POST' });
      if (!quiet) { this.showToast('Reward claimed! 🎉', 'success'); await this.loadQuestData(); }
      return true;
    } catch (error) {
      this.showToast('Claim failed: ' + error.message, 'error');
      return false;
    }
  }

  async enrollAll() {
    const targets = [...this.quests.available];
    if (!targets.length) { this.showToast('No quests to enroll in', 'info'); return; }
    let ok = 0;
    for (const quest of targets) {
      if (await this.enrollQuest(quest.id, true)) ok += 1;
      await new Promise(resolve => setTimeout(resolve, 800));
    }
    await this.loadQuestData(true);
    this.showToast(`Enrolled in ${ok}/${targets.length} quests`, ok ? 'success' : 'error');
  }

  async claimAll() {
    const targets = [...this.quests.claimable];
    if (!targets.length) { this.showToast('No rewards to claim', 'info'); return; }
    let ok = 0;
    for (const quest of targets) {
      if (await this.claimReward(quest.id, true)) ok += 1;
      await new Promise(resolve => setTimeout(resolve, 800));
    }
    await this.loadQuestData(true);
    this.showToast(`Claimed ${ok}/${targets.length} rewards`, ok ? 'success' : 'error');
  }

  async refreshData() {
    this.showToast('Refreshing quest data...', 'info');
    if (await this.loadQuestData(true)) this.showToast('Quest data refreshed!', 'success');
  }

  async toggleAutoComplete() {
    try {
      const data = await this.api('/api/quests/auto', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !this.autoComplete })
      });
      this.autoComplete = !!data.auto_complete;
      this.syncAutoButton();
      this.showToast(this.autoComplete ? 'Auto-complete enabled ▶' : 'Auto-complete disabled', 'info');
    } catch (error) {
      this.showToast('Auto-complete: ' + error.message, 'error');
    }
  }

  toggleDarkMode(enabled) {
    document.body.classList.toggle('light-mode', !enabled);
    localStorage.setItem('darkMode', enabled);
  }

  toggleCompactView(enabled) {
    document.body.classList.toggle('compact-view', enabled);
    localStorage.setItem('compactView', enabled);
  }

  hideLoader() {
    const loader = document.getElementById('globalLoader');
    if (loader) {
      loader.style.opacity = '0';
      loader.style.pointerEvents = 'none';
      setTimeout(() => loader.style.display = 'none', 300);
    }
  }

  showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    const host = document.getElementById('ariaToastHost');
    host?.appendChild(toast);
    
    setTimeout(() => {
      toast.classList.add('show');
    }, 10);

    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  getEmptyState(message, icon) {
    return `
      <div class="empty-state">
        <div class="empty-state-icon">${icon}</div>
        <h3>${message}</h3>
      </div>
    `;
  }

  pauseQuest(questId) {
    this.showToast('Quest paused', 'info');
    // Implement pause logic
  }
}

// Initialize dashboard
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
  dashboard = new QuestDashboard();
});

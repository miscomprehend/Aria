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
    this.init();
  }

  init() {
    this.setupEventListeners();
    this.loadQuestData();
    this.updateStats();
    this.hideLoader();
  }

  setupEventListeners() {
    // Navigation
    document.querySelectorAll('[data-section]').forEach(item => {
      item.addEventListener('click', (e) => {
        this.navigateTo(item.dataset.section);
      });
    });

    // Action buttons
    document.getElementById('autoCompleteToggle')?.addEventListener('click', () => this.toggleAutoComplete());
    document.getElementById('enrollAllBtn')?.addEventListener('click', () => this.enrollAll());
    document.getElementById('claimAllBtn')?.addEventListener('click', () => this.claimAll());
    document.getElementById('refreshAllBtn')?.addEventListener('click', () => this.refreshData());

    // Settings
    document.getElementById('darkMode')?.addEventListener('change', (e) => this.toggleDarkMode(e.target.checked));
    document.getElementById('compactView')?.addEventListener('change', (e) => this.toggleCompactView(e.target.checked));
  }

  navigateTo(section) {
    // Update active nav
    document.querySelectorAll('[data-section]').forEach(item => {
      item.classList.toggle('active', item.dataset.section === section);
    });

    // Update content
    document.querySelectorAll('.section-content').forEach(content => {
      content.classList.add('hidden');
    });

    const targetContent = document.querySelector(`[data-section-content="${section}"]`);
    if (targetContent) {
      targetContent.classList.remove('hidden');
    }

    this.currentPage = section;
  }

  async loadQuestData() {
    try {
      const response = await fetch('/api/quests/@me');
      const data = await response.json();
      
      // Categorize quests
      this.quests.active = data.quests.filter(q => q.user_status?.enrolled_at && !q.user_status?.completed_at);
      this.quests.available = data.quests.filter(q => !q.user_status?.enrolled_at);
      this.quests.completed = data.quests.filter(q => q.user_status?.completed_at);
      this.quests.claimable = data.quests.filter(q => q.user_status?.completed_at && !q.user_status?.claimed_at);
      
      this.renderQuests();
      this.updateStats();
    } catch (error) {
      console.error('Failed to load quests:', error);
      this.showToast('Failed to load quests', 'error');
    }
  }

  renderQuests() {
    // Render active quests
    const activeContainer = document.querySelector('[data-section-content="overview"] .active-quests');
    if (activeContainer) {
      activeContainer.innerHTML = this.quests.active.map(q => this.createQuestCard(q)).join('');
    }

    // Render available quests
    const availableContainer = document.querySelector('[data-section-content="available"] .quests-list');
    if (availableContainer) {
      availableContainer.innerHTML = this.quests.available.length > 0 
        ? this.quests.available.map(q => this.createQuestCard(q)).join('')
        : this.getEmptyState('No available quests', '🔍');
    }

    // Render completed quests
    const completedContainer = document.querySelector('[data-section-content="completed"] .quests-list');
    if (completedContainer) {
      completedContainer.innerHTML = this.quests.completed.length > 0 
        ? this.quests.completed.map(q => this.createQuestCard(q, 'completed')).join('')
        : this.getEmptyState('No completed quests', '✨');
    }

    // Render claimable quests
    const claimContainer = document.querySelector('[data-section-content="claim"] .quests-list');
    if (claimContainer) {
      claimContainer.innerHTML = this.quests.claimable.length > 0 
        ? this.quests.claimable.map(q => this.createQuestCard(q, 'claimable')).join('')
        : this.getEmptyState('No rewards to claim', '🎁');
    }
  }

  createQuestCard(quest, state = 'active') {
    const config = quest.config;
    const userStatus = quest.user_status;
    const progress = this.getQuestProgress(quest);
    const progressPercent = (progress.done / progress.total) * 100;

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
            <h3 class="quest-title">${config.messages?.quest_name || 'Untitled Quest'}</h3>
            <p class="quest-game">${config.application?.name || 'Unknown'}</p>
          </div>
          <span class="quest-badge ${badge}">${this.formatBadge(badge)}</span>
        </div>

        <p class="quest-description">${config.messages?.quest_description || ''}</p>

        ${state !== 'completed' && state !== 'claimable' ? `
          <div class="quest-progress">
            <div class="progress-info">
              <span class="progress-label">${progress.event}</span>
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
              <button class="quest-action" onclick="dashboard.pauseQuest('${quest.id}')">Pause</button>
            ` : state === 'available' ? `
              <button class="quest-action" onclick="dashboard.enrollQuest('${quest.id}')">Enroll</button>
            ` : state === 'claimable' ? `
              <button class="quest-action" onclick="dashboard.claimReward('${quest.id}')">Claim</button>
            ` : ''}
          </div>
        </div>
      </div>
    `;
  }

  getQuestProgress(quest) {
    const userStatus = quest.user_status;
    const config = quest.config;
    const tasks = config.task_config_v2?.tasks || {};

    if (!userStatus?.progress) {
      return { event: 'No progress', done: 0, total: 100 };
    }

    let maxProgress = 0;
    let targetEvent = 'Unknown';
    let targetTotal = 100;

    for (const [eventName, progressData] of Object.entries(userStatus.progress)) {
      if (progressData.value > maxProgress) {
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

  updateStats() {
    document.querySelector('[data-stat="active"]')!.textContent = this.quests.active.length;
    document.querySelector('[data-stat="available"]')!.textContent = this.quests.available.length;
    document.querySelector('[data-stat="completed"]')!.textContent = this.quests.completed.length;
    document.querySelector('[data-stat="claimable"]')!.textContent = this.quests.claimable.length;

    // Update badges
    document.querySelector('[data-badge="active"]')!.textContent = this.quests.active.length;
    document.querySelector('[data-badge="available"]')!.textContent = this.quests.available.length;
    document.querySelector('[data-badge="completed"]')!.textContent = this.quests.completed.length;
    document.querySelector('[data-badge="claimable"]')!.textContent = this.quests.claimable.length;
  }

  async enrollQuest(questId) {
    try {
      const response = await fetch(`/api/quests/${questId}/enroll`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (response.ok) {
        this.showToast(`Enrolled in quest!`, 'success');
        await this.loadQuestData();
      } else {
        this.showToast('Failed to enroll', 'error');
      }
    } catch (error) {
      console.error('Enroll failed:', error);
      this.showToast('Enrollment error', 'error');
    }
  }

  async claimReward(questId) {
    try {
      const response = await fetch(`/api/quests/${questId}/claim-reward`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (response.ok) {
        this.showToast('Reward claimed! 🎉', 'success');
        await this.loadQuestData();
      } else {
        this.showToast('Failed to claim reward', 'error');
      }
    } catch (error) {
      console.error('Claim failed:', error);
      this.showToast('Claim error', 'error');
    }
  }

  async enrollAll() {
    if (this.quests.available.length === 0) {
      this.showToast('No quests to enroll in', 'info');
      return;
    }

    for (const quest of this.quests.available) {
      await this.enrollQuest(quest.id);
      await new Promise(resolve => setTimeout(resolve, 300)); // Throttle requests
    }

    this.showToast(`Enrolled in ${this.quests.available.length} quests!`, 'success');
  }

  async claimAll() {
    if (this.quests.claimable.length === 0) {
      this.showToast('No rewards to claim', 'info');
      return;
    }

    for (const quest of this.quests.claimable) {
      await this.claimReward(quest.id);
      await new Promise(resolve => setTimeout(resolve, 300));
    }

    this.showToast(`Claimed ${this.quests.claimable.length} rewards! 🎉`, 'success');
  }

  async refreshData() {
    this.showToast('Refreshing quest data...', 'info');
    await this.loadQuestData();
    this.showToast('Quest data refreshed!', 'success');
  }

  toggleAutoComplete() {
    this.autoComplete = !this.autoComplete;
    const btn = document.getElementById('autoCompleteToggle');
    btn.classList.toggle('active');
    
    if (this.autoComplete) {
      this.showToast('Auto-complete enabled ▶', 'success');
      btn.innerHTML = '⏹ Stop Auto-Complete';
    } else {
      this.showToast('Auto-complete disabled', 'info');
      btn.innerHTML = '▶ Start Auto-Complete';
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

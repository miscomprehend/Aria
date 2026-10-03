// ===== ARIA DISCORD DASHBOARD - INTERACTIVE CONTROLS =====

class AriaDashboard {
    constructor() {
        this.currentSection = 'overview';
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadUserInfo();
        this.loadGuilds();
        this.loadStats();
    }

    setupEventListeners() {
        // Sidebar navigation
        document.querySelectorAll('.sidebar-item').forEach(item => {
            item.addEventListener('click', (e) => this.navigateToSection(e.currentTarget));
        });

        // Dropdown menus
        document.querySelectorAll('.dropdown-toggle').forEach(toggle => {
            toggle.addEventListener('click', (e) => this.toggleDropdown(e.currentTarget));
        });

        // Dropdown items
        document.querySelectorAll('.dropdown-item').forEach(item => {
            item.addEventListener('click', (e) => this.handleDropdownItem(e));
        });

        // Close dropdowns when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.dropdown')) {
                document.querySelectorAll('.dropdown.open').forEach(dd => {
                    dd.classList.remove('open');
                });
            }
        });

        // User profile click
        document.getElementById('userProfile').addEventListener('click', () => {
            this.showUserMenu();
        });
    }

    navigateToSection(item) {
        // Remove active class from all items
        document.querySelectorAll('.sidebar-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');

        // Get section id
        const sectionId = item.getAttribute('data-section');
        this.currentSection = sectionId;

        // Hide all sections
        document.querySelectorAll('.content-section').forEach(section => {
            section.classList.remove('active');
        });

        // Show selected section
        document.getElementById(sectionId).classList.add('active');

        // Load section-specific data
        this.loadSectionData(sectionId);
    }

    toggleDropdown(toggle) {
        const dropdown = toggle.closest('.dropdown');
        dropdown.classList.toggle('open');
    }

    handleDropdownItem(e) {
        const item = e.currentTarget;
        const label = item.querySelector('.dropdown-item-label').textContent;
        const dropdown = item.closest('.dropdown');
        const toggle = dropdown.querySelector('.dropdown-toggle');
        
        // Update toggle text (get first part before any icon/arrow)
        const icon = toggle.querySelector('.dropdown-arrow');
        toggle.textContent = label;
        toggle.appendChild(icon);

        // Close dropdown
        dropdown.classList.remove('open');

        // Trigger action
        this.handleFilterChange(label);
    }

    handleFilterChange(filter) {
        console.log('Filter changed to:', filter);
        // Implement filtering logic here
        this.refreshCurrentSection();
    }

    loadUserInfo() {
        // Simulate loading user info
        const userData = {
            name: 'SelfBot User',
            status: 'Online',
            avatar: 'U'
        };

        document.getElementById('userName').textContent = userData.name;
        document.getElementById('userStatus').textContent = userData.status;
        document.getElementById('userAvatar').textContent = userData.avatar;
    }

    loadGuilds() {
        if (this.currentSection !== 'guilds') return;

        // This would normally fetch from API
        const guilds = [
            { name: 'Gaming Central', members: 2400, icon: '🎮', owner: true, configured: true },
            { name: 'Community Hub', members: 1800, icon: '💬', verified: true },
            { name: 'Creative Space', members: 956, icon: '🎨', botAdmin: true },
        ];

        this.renderGuilds(guilds);
    }

    renderGuilds(guilds) {
        const grid = document.getElementById('guildGrid');
        if (!grid) return;

        // Grid is already pre-populated with example cards
        // In a real scenario, this would dynamically create cards
        console.log('Guilds loaded:', guilds);
    }

    loadStats() {
        if (this.currentSection !== 'overview') return;

        // Simulate API call
        document.getElementById('statServers').textContent = Math.floor(Math.random() * 50 + 100);
        document.getElementById('statUsers').textContent = Math.floor(Math.random() * 10000 + 50000);
        document.getElementById('statCommands').textContent = Math.floor(Math.random() * 5000 + 10000);
        document.getElementById('statUptime').textContent = (99 + Math.random()).toFixed(1) + '%';

        const updates = ['just now', '2 min ago', '5 min ago'];
        document.getElementById('statLastUpdate').textContent = updates[Math.floor(Math.random() * updates.length)];
    }

    loadSectionData(sectionId) {
        switch(sectionId) {
            case 'overview':
                this.loadStats();
                break;
            case 'guilds':
                this.loadGuilds();
                break;
            case 'commands':
                this.loadCommands();
                break;
            case 'users':
                this.loadUsers();
                break;
            case 'stats':
                this.loadDetailedStats();
                break;
        }
    }

    loadCommands() {
        console.log('Loading commands...');
        // Fetch commands from API
    }

    loadUsers() {
        console.log('Loading users...');
        // Fetch users from API
    }

    loadDetailedStats() {
        console.log('Loading detailed stats...');
        // Fetch stats from API
    }

    refreshCurrentSection() {
        this.loadSectionData(this.currentSection);
    }

    showUserMenu() {
        // Create simple user menu
        const menu = document.createElement('div');
        menu.className = 'dropdown-menu';
        menu.style.position = 'absolute';
        menu.style.top = '60px';
        menu.style.right = '20px';
        menu.innerHTML = `
            <button class="dropdown-item">
                <div class="dropdown-item-icon">👤</div>
                <div>
                    <div class="dropdown-item-label">Profile</div>
                    <div class="dropdown-item-desc">View your profile</div>
                </div>
            </button>
            <button class="dropdown-item">
                <div class="dropdown-item-icon">⚙️</div>
                <div>
                    <div class="dropdown-item-label">Settings</div>
                    <div class="dropdown-item-desc">Account settings</div>
                </div>
            </button>
            <div class="dropdown-divider"></div>
            <button class="dropdown-item">
                <div class="dropdown-item-icon">🚪</div>
                <div>
                    <div class="dropdown-item-label">Logout</div>
                    <div class="dropdown-item-desc">Sign out from dashboard</div>
                </div>
            </button>
        `;

        // Remove existing menu if any
        document.querySelectorAll('.user-menu').forEach(m => m.remove());

        menu.className = 'dropdown-menu user-menu';
        document.body.appendChild(menu);

        // Position menu
        const profile = document.getElementById('userProfile');
        const rect = profile.getBoundingClientRect();
        menu.style.top = (rect.bottom + 8) + 'px';
        menu.style.right = (window.innerWidth - rect.right) + 'px';
        menu.style.display = 'block';
        menu.style.zIndex = '1001';

        // Close on click outside
        setTimeout(() => {
            document.addEventListener('click', (e) => {
                if (!e.target.closest('.user-profile') && !e.target.closest('.user-menu')) {
                    menu.remove();
                }
            });
        }, 100);
    }
}

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new AriaDashboard();
    
    // Simulate real-time updates
    setInterval(() => {
        // Update status indicator
        if (window.dashboard.currentSection === 'overview') {
            window.dashboard.loadStats();
        }
    }, 30000); // Update every 30 seconds
});

// ===== UTILITY FUNCTIONS =====

/**
 * Fetch data from API endpoint
 * @param {string} url - API endpoint
 * @param {object} options - Fetch options
 * @returns {Promise}
 */
async function apiCall(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
        },
        credentials: 'same-origin',
    };

    try {
        const response = await fetch(url, { ...defaultOptions, ...options });
        
        if (!response.ok) {
            throw new Error(`API Error: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

/**
 * Format numbers for display
 * @param {number} num - Number to format
 * @returns {string} Formatted number
 */
function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    }
    if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

/**
 * Format time ago
 * @param {Date} date - Date to format
 * @returns {string} Time ago string
 */
function formatTimeAgo(date) {
    const now = new Date();
    const diff = now - date;
    
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    return `${days}d ago`;
}

/**
 * Show notification toast
 * @param {string} message - Notification message
 * @param {string} type - Notification type (success, error, warning, info)
 */
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-icon">
            ${type === 'success' ? '✓' : type === 'error' ? '✕' : type === 'warning' ? '!' : 'ℹ'}
        </div>
        <div class="notification-content">
            <div class="notification-message">${message}</div>
        </div>
    `;

    document.body.appendChild(notification);

    // Auto remove after 5 seconds
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

/**
 * Debounce function
 * @param {function} func - Function to debounce
 * @param {number} wait - Wait time in ms
 * @returns {function} Debounced function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Export for use in other modules
window.utils = {
    apiCall,
    formatNumber,
    formatTimeAgo,
    showNotification,
    debounce,
};

/**
 * ===== ACCOUNT PROFILE MANAGEMENT =====
 */

// Load account profile data
function loadAccountProfile() {
    const accountData = {
        username: 'YourUsername',
        displayName: 'Your Display Name',
        bio: 'Welcome to my profile!',
        avatar: 'https://cdn.discordapp.com/embed/avatars/0.png',
        bannerColor: '#69B7FF',
        status: 'online',
        statusMessage: 'Building with Aria 🚀',
        privateProfile: false,
        allowDMS: true,
        onlineStatus: true
    };

    // Populate form fields
    document.getElementById('discordUsername').value = accountData.username;
    document.getElementById('discordDisplayName').value = accountData.displayName;
    document.getElementById('discordBio').value = accountData.bio;
    document.getElementById('bannerColor').value = accountData.bannerColor;
    document.getElementById('userStatus').value = accountData.status;
    document.getElementById('statusMessage').value = accountData.statusMessage;
    document.getElementById('privateProfile').checked = accountData.privateProfile;
    document.getElementById('allowDMS').checked = accountData.allowDMS;
    document.getElementById('onlineStatus').checked = accountData.onlineStatus;
    
    // Set avatar
    const avatarImg = document.getElementById('avatarImg');
    if (avatarImg) {
        avatarImg.src = accountData.avatar;
    }
}

// Avatar upload handler
const avatarUpload = document.getElementById('avatarUpload');
if (avatarUpload) {
    avatarUpload.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function(event) {
                const avatarImg = document.getElementById('avatarImg');
                if (avatarImg) {
                    avatarImg.src = event.target.result;
                }
                showNotification('Avatar preview updated', 'success');
            };
            reader.readAsDataURL(file);
        }
    });
}

// Profile avatar click to upload
const profileAvatarPreview = document.getElementById('profileAvatarPreview');
if (profileAvatarPreview) {
    profileAvatarPreview.addEventListener('click', function() {
        document.getElementById('avatarUpload').click();
    });
}

// Save profile button handler
const saveProfileBtn = document.getElementById('saveProfileBtn');
if (saveProfileBtn) {
    saveProfileBtn.addEventListener('click', function() {
        const profileData = {
            username: document.getElementById('discordUsername').value,
            displayName: document.getElementById('discordDisplayName').value,
            bio: document.getElementById('discordBio').value,
            bannerColor: document.getElementById('bannerColor').value,
            status: document.getElementById('userStatus').value,
            statusMessage: document.getElementById('statusMessage').value,
            privateProfile: document.getElementById('privateProfile').checked,
            allowDMS: document.getElementById('allowDMS').checked,
            onlineStatus: document.getElementById('onlineStatus').checked,
            avatar: document.getElementById('avatarImg').src
        };

        // Validate profile data
        if (!profileData.username.trim()) {
            showNotification('Username is required', 'error');
            return;
        }

        if (profileData.bio.length > 190) {
            showNotification('Bio must be 190 characters or less', 'error');
            return;
        }

        // Save to backend
        saveProfileToBackend(profileData);
    });
}

// Save profile to backend
async function saveProfileToBackend(profileData) {
    try {
        const response = await fetch('/api/profile/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(profileData)
        });

        if (response.ok) {
            showNotification('✓ Profile saved successfully!', 'success');
        } else {
            showNotification('✕ Failed to save profile', 'error');
        }
    } catch (error) {
        console.error('Error saving profile:', error);
        showNotification('✕ Error: ' + error.message, 'error');
    }
}

// Account action buttons
const changePasswordBtn = document.getElementById('changePasswordBtn');
if (changePasswordBtn) {
    changePasswordBtn.addEventListener('click', function() {
        showNotification('Password change functionality coming soon', 'info');
        // TODO: Implement password change modal
    });
}

const logoutAllBtn = document.getElementById('logoutAllBtn');
if (logoutAllBtn) {
    logoutAllBtn.addEventListener('click', function() {
        if (confirm('Are you sure you want to logout all devices?')) {
            showNotification('Logging out all devices...', 'warning');
            // TODO: Call logout all endpoint
        }
    });
}

const deleteAccountBtn = document.getElementById('deleteAccountBtn');
if (deleteAccountBtn) {
    deleteAccountBtn.addEventListener('click', function() {
        if (confirm('WARNING: This action cannot be undone! Are you absolutely sure you want to delete your account?')) {
            if (confirm('This is your final warning. Your account and all data will be permanently deleted.')) {
                showNotification('Account deletion in progress...', 'warning');
                // TODO: Call account deletion endpoint
            }
        }
    });
}

// Initialize account profile when page loads
document.addEventListener('DOMContentLoaded', function() {
    const accountSection = document.getElementById('account');
    if (accountSection && accountSection.classList.contains('active')) {
        loadAccountProfile();
    }
});

// Load profile when account section becomes active
const originalNavigateToSection = AriaDashboard.prototype.navigateToSection;
if (originalNavigateToSection) {
    AriaDashboard.prototype.navigateToSection = function(item) {
        originalNavigateToSection.call(this, item);
        
        const sectionId = item.getAttribute('data-section');
        if (sectionId === 'account') {
            loadAccountProfile();
        }
    };
}

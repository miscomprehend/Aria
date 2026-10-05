// ═══════════════════════════════════════════════════════════════
//  ARIA PARTICLE BACKGROUND
// ═══════════════════════════════════════════════════════════════
(function initParticles() {
    const canvas = document.getElementById('particleCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let W, H, particles = [];
    const COLORS = ['rgba(139,92,246,', 'rgba(236,72,153,', 'rgba(6,182,212,'];

    function resize() {
        W = canvas.width = window.innerWidth;
        H = canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    function mkParticle() {
        const c = COLORS[Math.floor(Math.random() * COLORS.length)];
        return {
            x: Math.random() * W, y: Math.random() * H,
            r: Math.random() * 1.4 + 0.3,
            vx: (Math.random() - .5) * 0.22,
            vy: (Math.random() - .5) * 0.18,
            a: Math.random() * 0.55 + 0.15,
            da: (Math.random() - .5) * 0.003,
            color: c,
        };
    }
    for (let i = 0; i < 100; i++) particles.push(mkParticle());

    // Draw connecting lines
    function drawLines() {
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 110) {
                    const alpha = (1 - dist / 110) * 0.06;
                    ctx.beginPath();
                    ctx.strokeStyle = `rgba(139,92,246,${alpha})`;
                    ctx.lineWidth = 0.5;
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.stroke();
                }
            }
        }
    }

    function loop() {
        ctx.clearRect(0, 0, W, H);
        drawLines();
        particles.forEach(p => {
            p.a += p.da;
            if (p.a > 0.7 || p.a < 0.1) p.da *= -1;
            p.x += p.vx; p.y += p.vy;
            if (p.x < 0) p.x = W; if (p.x > W) p.x = 0;
            if (p.y < 0) p.y = H; if (p.y > H) p.y = 0;
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx.fillStyle = p.color + p.a + ')';
            ctx.fill();
        });
        requestAnimationFrame(loop);
    }
    loop();
})();

// ═══════════════════════════════════════════════════════════════
//  GLOBAL LOADER DISMISS
// ═══════════════════════════════════════════════════════════════
function dismissLoader() {
    const loader = document.getElementById('globalLoader');
    if (loader) {
        loader.classList.add('hidden');
        setTimeout(() => { if (loader.parentNode) loader.parentNode.removeChild(loader); }, 500);
    }
}
// ═══════════════════════════════════════════════════════════════
//  ARIA TOAST NOTIFICATION SYSTEM
// ═══════════════════════════════════════════════════════════════
const _TOAST_ICONS = { ok: '✅', warn: '⚠️', err: '❌', info: '💠' };
function showToast(title, msg = '', type = 'info', duration = 3800) {
    const host = document.getElementById('ariaToastHost');
    if (!host) return;
    const t = document.createElement('div');
    t.className = `p-toast ${type}`;
    const icon = document.createElement('span');
    icon.className = 'p-toast-icon';
    icon.textContent = _TOAST_ICONS[type] || '💠';
    const body = document.createElement('div');
    body.className = 'p-toast-body';
    const heading = document.createElement('div');
    heading.className = 'p-toast-title';
    heading.textContent = String(title);
    body.appendChild(heading);
    if (msg) {
        const message = document.createElement('div');
        message.className = 'p-toast-msg';
        message.textContent = String(msg);
        body.appendChild(message);
    }
    const close = document.createElement('button');
    close.className = 'p-toast-close';
    close.type = 'button';
    close.textContent = '×';
    close.setAttribute('aria-label', 'Dismiss notification');
    close.addEventListener('click', () => removeToast(t));
    t.append(icon, body, close);
    host.appendChild(t);
    if (duration > 0) setTimeout(() => removeToast(t), duration);
}
function removeToast(el) {
    if (!el || !el.parentNode) return;
    el.classList.add('p-toast-exit');
    setTimeout(() => { if (el.parentNode) el.parentNode.removeChild(el); }, 380);
}

const _dashboardErrorTimes = new Map();

function reportDashboardError(source, error) {
    const message = error instanceof Error ? error.message : String(error || 'Unknown error');
    console.error(`[Aria dashboard] ${source}:`, error);
    dismissLoader();
    const now = Date.now();
    if (now - (_dashboardErrorTimes.get(source) || 0) < 10000) return;
    _dashboardErrorTimes.set(source, now);
    showToast('Dashboard recovered', `${source} failed: ${message}`, 'err', 6500);
}

window.addEventListener('error', event => {
    reportDashboardError('Interface', event.error || event.message);
});

window.addEventListener('unhandledrejection', event => {
    reportDashboardError('Background operation', event.reason);
});

// ═══════════════════════════════════════════════════════════════
//  TYPEWRITER EFFECT
// ═══════════════════════════════════════════════════════════════
function typewrite(el, text, speed = 28) {
    if (!el) return;
    el.textContent = '';
    const cursor = document.createElement('span');
    cursor.className = 'typewriter-cursor';
    el.appendChild(cursor);
    let i = 0;
    const iv = setInterval(() => {
        if (i >= text.length) { clearInterval(iv); return; }
        cursor.insertAdjacentText('beforebegin', text[i++]);
    }, speed);
}

// ═══════════════════════════════════════════════════════════════
//  ANIMATED NUMBER COUNTER
// ═══════════════════════════════════════════════════════════════
function countUp(id, target, duration = 700, decimals = 0) {
    const el = document.getElementById(id);
    if (!el) return;
    const start = parseFloat(el.textContent) || 0;
    const end = parseFloat(target) || 0;
    if (start === end) return;
    const t0 = performance.now();
    function tick(now) {
        const p = Math.min(1, (now - t0) / duration);
        const ease = 1 - Math.pow(1 - p, 3);
        const cur = start + (end - start) * ease;
        el.textContent = decimals ? cur.toFixed(decimals) : Math.round(cur);
        if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
}

// ═══════════════════════════════════════════════════════════════
//  KEYBOARD SHORTCUTS
// ═══════════════════════════════════════════════════════════════
document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
    if (e.key === '/') {
        e.preventDefault();
        const srch = document.getElementById('cmdSearch');
        if (srch) { navigateTo('commands'); srch.focus(); }
    }
    if (e.key === 'r' && !e.ctrlKey && !e.metaKey) {
        const active = document.querySelector('.nav-item.active');
        if (active) { const s = active.dataset.section; if (s) loadSection(s); }
    }
    if (e.key === 'Escape') {
        const srch = document.getElementById('cmdSearch');
        if (srch && document.activeElement === srch) srch.blur();
    }
});

// ═══════════════════════════════════════════════════════════════
//  NAVIGATE TO SECTION HELPER
// ═══════════════════════════════════════════════════════════════
function navigateTo(sectionId) {
    const item = document.querySelector(`.nav-item[data-section="${sectionId}"]`);
    if (item) item.click();
}

function togglePasswordField(inputId, btn) {
    const el = document.getElementById(inputId);
    if (!el) return;
    const next = el.type === 'password' ? 'text' : 'password';
    el.type = next;
    if (btn) {
        const showing = next === 'text';
        btn.classList.toggle('is-visible', showing);
        btn.setAttribute('aria-label', showing ? 'Hide password' : 'Show password');
        btn.setAttribute('title', showing ? 'Hide password' : 'Show password');
    }
}

// ── User Profile Loader (topbar sync only) ──
async function loadUserProfile() {
    let data = await fetchJSON('/api/max/user-profile');
    if (!data || !data.ok) {
        const me = await fetchJSON('/api/dash/me');
        if (me && me.ok && me.profile) {
            data = {
                ok: true,
                username: me.profile.username || me.profile.user_id || '—',
                user_id: me.profile.user_id || '',
                avatar_url: me.profile.avatar_url || '',
            };
        }
    }
    if (!data || !data.ok) return;

    // Sync topbar chip
    const tbUser = document.getElementById('topbarUsername');
    if (tbUser) tbUser.textContent = data.username || '—';

    const sidebarUser = document.getElementById('sidebarUsername');
    if (sidebarUser) sidebarUser.textContent = data.username || 'Aria account';
    
    const tbAvatar = document.getElementById('topbarAvatar');
    setAvatarImage(tbAvatar, data.avatar_url, data.user_id, { allowFallback: true });
    setAvatarImage(document.getElementById('sidebarAvatar'), data.avatar_url, data.user_id, { allowFallback: true });
    
    // Sync hero avatar
    const heroAvatar = document.getElementById('heroAvatar');
    setAvatarImage(heroAvatar, data.avatar_url, data.user_id, { allowFallback: true });
}

window.addEventListener('DOMContentLoaded', () => {
    loadUserProfile();
    setInterval(loadUserProfile, 10000);
});
// ── Sidebar Toggle (Mobile) ──
const sidebarToggle = document.getElementById('sidebarToggle');
const sidebar = document.querySelector('.sidebar');
const mainContent = document.querySelector('.main-content');
if (sidebarToggle && sidebar && mainContent) {
    sidebarToggle.addEventListener('change', () => {
        sidebar.classList.toggle('is-open', sidebarToggle.checked);
    });
    document.querySelector('.sidebar-toggle-btn')?.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            sidebarToggle.checked = !sidebarToggle.checked;
            sidebarToggle.dispatchEvent(new Event('change', { bubbles: true }));
        }
    });
}

// ── Overview Quick / Hero Env Loader ──
async function loadOverviewQuick() {
    // Version info → hero env grid
    fetchJSON('/api/max/version-info').then(data => {
        setText('heroVersion', data?.version || '—');
    });
    // MOTD → hero banner
    fetchJSON('/api/max/motd').then(data => {
        const motd = data?.motd || '';
        const el = document.getElementById('heroMotd');
        if (el && motd) typewrite(el, motd, 22);
    });
}

window.addEventListener('DOMContentLoaded', () => {
    loadOverviewQuick();
});
// ── Navigation ────────────────────────────────────────────────────────────────
const navItems = document.querySelectorAll('.nav-item');
const sections = document.querySelectorAll('.section');
const pageTitle = document.getElementById('pageTitle');
let _meProfile = null;
const _liveOverviewState = { lastCount: null, lastTs: null };
const _notificationState = {
    open: false,
    seenTs: 0,
    events: [],
};

navItems.forEach(item => {
    const navLabel = item.textContent.trim();
    item.setAttribute('role', 'button');
    item.setAttribute('aria-label', navLabel);
    item.setAttribute('title', navLabel);
    item.tabIndex = 0;
    if (item.classList.contains('active')) item.setAttribute('aria-current', 'page');
    item.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            item.click();
        }
    });
    item.addEventListener('click', () => {
        const target = item.dataset.section;
        const targetSection = document.getElementById('section-' + target);
        if (item.hidden || item.dataset.hiddenByRole === 'true' || !targetSection || targetSection.hidden) return;
        const navGroup = item.dataset.navGroup;
        if (navGroup) setSidebarGroupExpanded(navGroup, true);
        navItems.forEach(navItem => {
            navItem.classList.remove('active');
            navItem.removeAttribute('aria-current');
        });
        sections.forEach(s => s.classList.remove('active'));
        item.classList.add('active');
        item.setAttribute('aria-current', 'page');
        targetSection.classList.add('active');
        document.title = 'Aria';
        // strip emoji from title — take last text node
        const rawText = item.childNodes[item.childNodes.length - 1].textContent.trim();
        pageTitle.textContent = rawText;
        // Update breadcrumb
        const bc = document.getElementById('topbarBreadcrumb');
        if (bc) bc.textContent = target;
        loadSection(target);
        if (sidebarToggle && window.matchMedia('(max-width: 900px)').matches) {
            sidebarToggle.checked = false;
            sidebar.classList.remove('is-open');
        }
        trackDashboardAction('navigate', `Opened ${target}`);
    });
});

// ── API helpers ───────────────────────────────────────────────────────────────
async function fetchJSON(url) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
        const r = await fetch(url, {
            cache: 'no-store',
            credentials: 'same-origin',
            signal: controller.signal,
        });
        if (!r.ok) throw new Error(r.status);
        return await r.json();
    } catch (e) {
        console.warn('Fetch failed:', url, e);
        return null;
    } finally {
        clearTimeout(timeout);
    }
}

async function mutateJSON(url, method, body) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    const headers = {
        'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]')?.content || '',
    };
    const init = {
        method,
        headers,
        cache: 'no-store',
        credentials: 'same-origin',
        signal: controller.signal,
    };
    if (body !== undefined) {
        headers['Content-Type'] = 'application/json';
        init.body = JSON.stringify(body);
    }
    try {
        const r = await fetch(url, init);
        const result = await r.json();
        if (!r.ok && (!result || typeof result !== 'object')) {
            throw new Error(`HTTP ${r.status}`);
        }
        return result;
    } catch (e) {
        console.warn('Post failed:', url, e);
        return null;
    } finally {
        clearTimeout(timeout);
    }
}

function postJSON(url, body) {
    return mutateJSON(url, 'POST', body);
}

function deleteJSON(url) {
    return mutateJSON(url, 'DELETE');
}

function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val != null ? val : '—';
}

function relativeTime(ts) {
    const n = Number(ts || 0);
    if (!n) return 'just now';
    const nowSec = Date.now() / 1000;
    const diff = Math.max(0, Math.floor(nowSec - n));
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
}

function esc(s) {
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function defaultAvatarUrl(userId) {
    const id = String(userId || '').trim();
    if (!id || id === '—') return '/static/images/aria-favicon.png';
    const n = Number(id);
    const slot = Number.isFinite(n) ? Math.abs(n) % 5 : 0;
    return `https://cdn.discordapp.com/embed/avatars/${slot}.png`;
}

function isDefaultishAvatarSrc(src) {
    const s = String(src || '');
    if (!s) return true;
    return s.includes('/static/images/aria-favicon') || s.includes('/embed/avatars/');
}

function setAvatarImage(el, avatarUrl, userId, opts = {}) {
    if (!el) return;
    const allowFallback = opts.allowFallback !== false;
    const next = String(avatarUrl || '').trim();
    const fallback = defaultAvatarUrl(userId);

    // Do not overwrite a valid custom avatar with fallback during async races.
    if (next) {
        if (el.src !== next) el.src = next;
    } else if (allowFallback && isDefaultishAvatarSrc(el.src)) {
        el.src = fallback;
    }

    el.onerror = () => {
        if (el.src !== fallback) el.src = fallback;
    };
}

function fmtTs(ts) {
    const n = Number(ts || 0);
    if (!n) return '—';
    const d = new Date(n * 1000);
    if (Number.isNaN(d.getTime())) return '—';
    return d.toLocaleString();
}

// ── Status dot ───────────────────────────────────────────────────────────────
function setGlobalStatus(connected) {
    const dot = document.getElementById('globalStatus');
    const lbl = document.getElementById('globalStatusLabel');
    if (dot && lbl) {
        dot.className = 'status-dot ' + (connected ? 'online' : 'offline');
        lbl.textContent = connected ? 'Connected' : 'Disconnected';
    }
}

// ── Overview ──────────────────────────────────────────────────────────────────
async function loadOverview() {
    const res = await fetchJSON('/api/bot');
    if (!res || !res.data) { setGlobalStatus(false); return; }
    const d = res.data;
    // Cache bot data for use by loadRpc Discord card
    window._botDataCache = d;
    setGlobalStatus(d.connected);
    setText('prefix', d.prefix || '$');
    setText('uptime', d.uptime);
    updateUptimeRing(d.uptime);
    countUp('commandCount', d.command_count, 900);
    countUp('commandsRegistered', d.commands_registered, 800);
    setText('connectionStatus', d.connected ? 'Online' : 'Offline');
    const gatewayParts = [];
    if (d.gateway_latency_ms != null) gatewayParts.push(`${Math.round(Number(d.gateway_latency_ms))} ms`);
    gatewayParts.push(`${Number(d.reconnect_attempts || 0)} retries`);
    if (d.connection_quality != null) gatewayParts.push(`quality ${Math.round(Number(d.connection_quality))}%`);
    setText('gatewayDiagnostics', d.identified ? gatewayParts.join(' · ') : 'Waiting for gateway READY');
    setText('botStatus', d.status || 'online');
    setText('clientType', d.client_type || 'mobile');
    updateLiveOverviewMetrics(d);

   // Show welcome modal on first overview load if not dismissed this session
   if (!window._welcomeModalShown) {
        window._welcomeModalShown = true;
        setTimeout(() => {
            openWelcomeModal();
            loadWelcomeUpdates();
            updateWelcomeVersion(d.ui_version || '—');
        }, 500);
   }
    // ── Hero Banner ──────────────────────────────────────────────────────────
    const heroBadgeConn = document.getElementById('heroBadgeConn');
    if (heroBadgeConn) {
        heroBadgeConn.textContent = d.connected ? '● Connected' : '● Offline';
        heroBadgeConn.classList.toggle('offline', !d.connected);
    }
    const heroBadgeClient = document.getElementById('heroBadgeClient');
    if (heroBadgeClient) heroBadgeClient.textContent = d.client_type || 'mobile';
    const heroBadgePrefix = document.getElementById('heroBadgePrefix');
    if (heroBadgePrefix) heroBadgePrefix.textContent = `prefix: ${d.prefix || '$'}`;
    const heroStatusDot = document.getElementById('heroStatusDot');
    if (heroStatusDot) heroStatusDot.classList.toggle('offline', !d.connected);
    const heroUserId = document.getElementById('heroUserId');
    if (heroUserId) heroUserId.textContent = d.user_id || '—';
    const heroRuntimeState = document.getElementById('heroRuntimeState');
    if (heroRuntimeState) heroRuntimeState.textContent = d.connected ? 'live' : 'offline';
    const heroCommandEcho = document.getElementById('heroCommandEcho');
    if (heroCommandEcho) heroCommandEcho.textContent = String(d.command_count || 0);

    // ── Hero Banner title with username ─────────────────────────────────────
    const dashboardTitle = document.getElementById('heroDashboardTitle');
    if (dashboardTitle && d.username) {
        dashboardTitle.textContent = `${d.username}`;
    }

    // ── Topbar avatar/username sync ──────────────────────────────────────────
    const tbAvatar = document.getElementById('topbarAvatar');
    setAvatarImage(tbAvatar, d.avatar_url, d.user_id, { allowFallback: false });
    const tbUser = document.getElementById('topbarUsername');
    if (tbUser) {
        tbUser.textContent = d.username || '—';
    }

    // ── Hero avatar ──────────────────────────────────────────────────────────
    const heroAvatar = document.getElementById('heroAvatar');
    setAvatarImage(heroAvatar, d.avatar_url, d.user_id, { allowFallback: false });

    await loadClientSwitcher(d);
    updateSparkline();
    updateToastFeed();
    loadAriaOverviewWidgets();
    loadUserProfile();
}

// ── Welcome Modal Functions ─────────────────────────────────────────────
function openWelcomeModal() {
    const modal = document.getElementById('welcomeModal');
    if (modal) {
        modal.hidden = false;
        document.body.style.overflow = 'hidden';
    }
}

function closeWelcomeModal() {
    const modal = document.getElementById('welcomeModal');
    if (modal) {
        modal.hidden = true;
        document.body.style.overflow = '';
    }
}

function switchWelcomeTab(tabName, btn) {
    // Hide all tab contents
    document.querySelectorAll('.welcome-tab-content').forEach(el => {
        el.classList.remove('active');
    });
    
    // Remove active from all buttons
    document.querySelectorAll('.welcome-tab-btn').forEach(el => {
        el.classList.remove('active');
    });
    
    // Show selected tab
    const tab = document.getElementById(`welcome-tab-${tabName}`);
    if (tab) tab.classList.add('active');
    
    // Mark button as active
    if (btn) btn.classList.add('active');
}

async function loadWelcomeUpdates() {
    const updatesList = document.getElementById('welcomeUpdatesList');
    const status = document.getElementById('welcomeUpdateStatus');
    if (!updatesList) return;

    updatesList.replaceChildren();
    if (status) {
        status.dataset.state = 'checking';
        status.textContent = 'Checking the latest Aria changes...';
    }

    const data = await fetchJSON('/api/max/updates');
    if (!data || !data.ok) {
        if (status) {
            status.dataset.state = 'unavailable';
            status.textContent = 'Update check is temporarily unavailable.';
        }
        return;
    }

    if (data.version) updateWelcomeVersion(data.version);
    if (status) {
        const stateMessages = {
            update_available: `Update available · latest commit ${data.latest_commit || ''}`,
            up_to_date: `You are up to date · ${data.local_commit || ''}`,
            local_changes: 'Local changes detected; commit comparison is unavailable.',
            revision_unknown: 'Recent changes loaded; this revision could not be matched.',
        };
        status.dataset.state = data.status || 'unknown';
        status.textContent = stateMessages[data.status] || 'Recent changes loaded.';
    }

    const commits = Array.isArray(data.commits) ? data.commits : [];
    if (!commits.length) {
        const empty = document.createElement('div');
        empty.className = 'update-desc';
        empty.textContent = 'No recent commits were returned.';
        updatesList.appendChild(empty);
        return;
    }

    commits.forEach((commit, index) => {
        const row = document.createElement('div');
        row.className = 'update-item';
        const badge = document.createElement('div');
        badge.className = 'update-badge';
        badge.textContent = String(index + 1);
        const info = document.createElement('div');
        info.className = 'update-info';
        const title = document.createElement('div');
        title.className = 'update-version';
        title.textContent = commit.title || 'Aria update';
        const description = document.createElement('div');
        description.className = 'update-desc';
        const date = commit.date ? new Date(commit.date) : null;
        const dateText = date && !Number.isNaN(date.valueOf()) ? date.toLocaleDateString() : '';
        description.textContent = [commit.sha, dateText].filter(Boolean).join(' · ');
        info.append(title, description);
        row.append(badge, info);

        try {
            const commitUrl = new URL(commit.url);
            if (commitUrl.protocol === 'https:' && commitUrl.hostname === 'github.com') {
                const link = document.createElement('a');
                link.className = 'update-commit-link';
                link.href = commitUrl.toString();
                link.textContent = 'View';
                link.target = '_blank';
                link.rel = 'noopener noreferrer';
                row.appendChild(link);
            }
        } catch (_) {}
        updatesList.appendChild(row);
    });
}

function updateWelcomeVersion(version) {
    const verEl = document.getElementById('welcomeVersion');
    if (verEl && version) {
        verEl.textContent = version;
    }
}

async function loadAriaOverviewWidgets() {
    const [summaryRes, sysRes] = await Promise.all([
        fetchJSON('/api/max/system-summary'),
        fetchJSON('/api/max/system-stats'),
    ]);

    // Update fleet snapshot timestamp
    const timeEl = document.getElementById('fleetSnapshotTime');
    if (timeEl) {
        const now = new Date();
        timeEl.textContent = `Updated ${now.toLocaleTimeString('en-US', {hour: '2-digit', minute: '2-digit', second: '2-digit'})}`;
    }

    if (summaryRes && summaryRes.ok && summaryRes.summary) {
        const s = summaryRes.summary;
        setText('ariaHostedTotal', s.hosted_total ?? 0);
        setText('ariaHostedActive', s.hosted_active ?? 0);
        setText('ariaRegisteredUsers', s.users_registered ?? 0);
        setText('ariaSuccessRate', `${Number(s.success_rate || 0).toFixed(1)}%`);
        setText('ariaLatency', `${Math.round(Number(s.avg_response_ms || 0))}ms`);
        setText('ariaCommands', s.total_commands ?? 0);
    }

    if (sysRes && sysRes.ok) {
        const cpu = Number(sysRes.cpu || 0);
        const ram = Number(sysRes.ram || 0);
        const disk = Number(sysRes.disk || 0);
        const sentKb = Math.round(Number((sysRes.net || {}).sent || 0) / 1024);
        const recvKb = Math.round(Number((sysRes.net || {}).recv || 0) / 1024);

        setText('ariaCpu', `${cpu.toFixed(1)}%`);
        setText('ariaRam', `${ram.toFixed(1)}%`);
        setText('ariaDisk', `${disk.toFixed(1)}%`);
        setText('ariaNet', `up ${sentKb}kb | down ${recvKb}kb`);

        const badge = document.getElementById('infraHealthBadge');
        if (badge) {
            const maxUse = Math.max(cpu, ram, disk);
            if (maxUse >= 90) {
                badge.textContent = 'critical';
            } else if (maxUse >= 75) {
                badge.textContent = 'elevated';
            } else {
                badge.textContent = 'healthy';
            }
        }
    }
}

// ── Uptime Ring ────────────────────────────────────────────────────────────
function updateUptimeRing(uptimeStr) {
    // Parse uptime string like "1h 23m 45s"
    let total = 0;
    if (typeof uptimeStr === 'string') {
        const m = uptimeStr.match(/(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+)s)?/);
        if (m) {
            total += (parseInt(m[1]||'0',10)||0) * 3600;
            total += (parseInt(m[2]||'0',10)||0) * 60;
            total += (parseInt(m[3]||'0',10)||0);
        }
    }
    // Animate ring: 24h = full circle
    const max = 24*3600;
    const pct = Math.min(1, total / max);
    const offset = 151 - Math.round(151 * pct);
    const fg = document.querySelector('.uptime-fg');
    if (fg) fg.setAttribute('stroke-dashoffset', offset);
}

// ── Sparkline Chart ─────────────────────────────────────────────────────---
async function updateSparkline() {
    const canvas = document.getElementById('sparkline');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0,0,canvas.width,canvas.height);
    // Fetch history
    const res = await fetchJSON('/api/history');
    let entries = (res && res.data && res.data.entries) || [];
    // Group by minute
    const now = Date.now();
    const buckets = Array(20).fill(0);
    entries.forEach(e => {
        let ts = Number(e.timestamp || 0);
        if (!ts || ts > 1e12) ts = Math.floor(ts/1000); // handle ms
        const minAgo = Math.floor((now/1000 - ts)/60);
        if (minAgo >= 0 && minAgo < 20) buckets[19-minAgo]++;
    });
    // Draw sparkline
    const maxVal = Math.max(1, ...buckets);
    ctx.beginPath();
    for (let i=0; i<buckets.length; ++i) {
        const x = 7 + i*6.5;
        const y = 32 - (buckets[i]/maxVal)*28;
        if (i===0) ctx.moveTo(x,y);
        else ctx.lineTo(x,y);
    }
    ctx.strokeStyle = '#accbee';
    ctx.lineWidth = 2.2;
    ctx.shadowColor = '#7fafd6';
    ctx.shadowBlur = 4;
    ctx.stroke();
    ctx.shadowBlur = 0;
    // Fill area
    ctx.lineTo(7+19*6.5,32);
    ctx.lineTo(7,32);
    ctx.closePath();
    ctx.globalAlpha = 0.18;
    ctx.fillStyle = '#accbee';
    ctx.fill();
    ctx.globalAlpha = 1;
}

// ── Toast Feed ─────────────────────────────────────────────────────────---
function toastWhen(ev) {
    if (ev && ev.time) return ev.time;
    return fmtTs(ev && ev.ts);
}

async function updateToastFeed() {
    const feed = document.getElementById('toastFeed');
    if (!feed) return;
    const res = await fetchJSON('/api/dash/activity');
    let timeline = (res && res.runtime_events) || [];
    if (!timeline.length) timeline = (res && res.timeline) || [];
    if (!timeline.length) {
        const pub = await fetchJSON('/api/public/activity');
        timeline = ((pub && pub.events) || []).map(ev => ({
            action: ev.kind || 'runtime',
            details: ev.label || '',
            time: ev.time || '',
        }));
    }
    feed.replaceChildren();
    if (!timeline.length) {
        const empty = document.createElement('div');
        empty.className = 'toast';
        empty.textContent = 'No session events yet. Commands and gateway changes show up here.';
        feed.appendChild(empty);
        return;
    }
    timeline.slice(0, 8).forEach(ev => {
        const t = document.createElement('div');
        t.className = 'toast';
        t.textContent = `[${toastWhen(ev)}] ${ev.action || 'event'}${ev.details ? ': ' + ev.details : ''}`;
        feed.appendChild(t);
    });
}

let quickTogglesReady = false;
let lastRpcActivity = null;

function setQuickToggle(id, checked) {
    const input = document.getElementById(id);
    if (!input) return;
    input.dataset.syncing = '1';
    input.checked = Boolean(checked);
    delete input.dataset.syncing;
}

function setQuickToggleMsg(text) {
    const msg = document.getElementById('quickToggleMsg');
    if (msg) msg.textContent = text;
}

async function loadQuickToggles() {
    const [afk, logger, rpc, tools] = await Promise.all([
        fetchJSON('/api/afk'),
        fetchJSON('/api/message-logger'),
        fetchJSON('/api/rpc'),
        fetchJSON('/api/command-tools'),
    ]);
    setQuickToggle('toggleAfk', afk && afk.active);
    setQuickToggle('toggleLogger', logger && logger.config && logger.config.enabled);
    setQuickToggle('toggleRpc', rpc && rpc.active);
    setQuickToggle('toggleAntiGc', tools && tools.anti_gc && tools.anti_gc.enabled);
    if (rpc && rpc.activity) lastRpcActivity = rpc.activity;
}

async function onQuickToggle(event) {
    const input = event.target;
    if (!input || input.dataset.syncing) return;
    const wanted = input.checked;
    let result = null;
    if (input.id === 'toggleAfk') {
        result = await postJSON('/api/afk', { action: wanted ? 'enable' : 'disable', message: 'AFK' });
    } else if (input.id === 'toggleLogger') {
        result = await postJSON('/api/message-logger', { action: 'config', config: { enabled: wanted } });
    } else if (input.id === 'toggleAntiGc') {
        result = await postJSON('/api/command-tools', { action: 'antigc_enabled', value: wanted });
    } else if (input.id === 'toggleRpc') {
        if (!wanted) {
            if (lastRpcActivity) {
                result = await postJSON('/api/rpc', { action: 'stop' });
            } else {
                result = await postJSON('/api/rpc', { action: 'stop' });
            }
        } else if (lastRpcActivity) {
            result = await postJSON('/api/rpc', { action: 'set', activity: lastRpcActivity });
        } else {
            input.checked = false;
            setQuickToggleMsg('Open Presence to set one first');
            if (typeof navigateTo === 'function') navigateTo('rpc');
            return;
        }
    }
    if (!result || result.ok === false) {
        input.checked = !wanted;
        setQuickToggleMsg((result && result.error) || 'Could not update');
        return;
    }
    setQuickToggleMsg('Updated');
}

function bindQuickToggles() {
    if (quickTogglesReady) return;
    const grid = document.querySelector('.quick-toggle-grid');
    if (!grid) return;
    quickTogglesReady = true;
    grid.addEventListener('change', onQuickToggle);
    loadQuickToggles();
}

function startLiveExampleDemo() {
    const eventList = document.getElementById('demoEventList');
    const elapsedLabel = document.getElementById('demoTrackElapsed');
    const progressBar = document.getElementById('demoTrackProgress');
    if (!eventList || !elapsedLabel || !progressBar) return;

    const events = [
        'Identify flow simulated',
        'READY handshake pending',
        'Safe presence preview refreshed',
        'Heartbeat response staged',
        'RPC payload preview synchronized',
    ];
    let eventIndex = 0;
    const durationSeconds = 238;
    const startedAt = Date.now() - 102000;
    const formatTime = seconds => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;

    const pushEvent = () => {
        if (!document.getElementById('section-overview')?.classList.contains('active')) return;
        const now = new Date();
        const time = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const row = document.createElement('li');
        const timestamp = document.createElement('time');
        timestamp.textContent = time;
        const message = document.createElement('span');
        message.textContent = events[eventIndex++ % events.length];
        const safe = document.createElement('b');
        safe.textContent = 'SAFE';
        row.append(timestamp, message, safe);
        eventList.prepend(row);
        while (eventList.children.length > 3) eventList.lastElementChild.remove();
    };

    const updateTrack = () => {
        const elapsed = Math.floor((Date.now() - startedAt) / 1000) % durationSeconds;
        elapsedLabel.textContent = formatTime(elapsed);
        progressBar.style.width = `${(elapsed / durationSeconds) * 100}%`;
    };

    eventList.replaceChildren();
    pushEvent();
    updateTrack();
    window.setInterval(pushEvent, 2600);
    window.setInterval(updateTrack, 1000);
}

document.addEventListener('DOMContentLoaded', () => {
    startLiveExampleDemo();
    bindQuickToggles();
}, { once: true });

// ── Live Metrics Refresh ─────────────────────────────────────────────────-
setInterval(() => {
    if (document.getElementById('section-overview')?.classList.contains('active')) {
        updateSparkline();
        updateToastFeed();
        loadQuickToggles();
        // Optionally, update uptime ring
        const uptime = document.getElementById('uptime');
        if (uptime) updateUptimeRing(uptime.textContent);
    }
}, 7000);

function animateMetricValue(id, newVal, decimals = 0) {
    const el = document.getElementById(id);
    if (!el) return;
    const prev = Number(el.dataset.value || 0);
    const next = Number(newVal || 0);
    const duration = 420;
    const start = performance.now();
    const isInt = decimals === 0;

    function tick(now) {
        const p = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - p, 3);
        const cur = prev + (next - prev) * eased;
        el.textContent = isInt ? String(Math.round(cur)) : cur.toFixed(decimals);
        if (p < 1) requestAnimationFrame(tick);
        else el.dataset.value = String(next);
    }
    requestAnimationFrame(tick);
}

function updateLiveOverviewMetrics(botData) {
    const cmdCount = Number(botData.command_count || 0);
    const now = Date.now();

    let delta = 0;
    let perMin = 0;
    if (_liveOverviewState.lastCount != null && _liveOverviewState.lastTs != null) {
        delta = Math.max(0, cmdCount - _liveOverviewState.lastCount);
        const mins = Math.max((now - _liveOverviewState.lastTs) / 60000, 0.001);
        perMin = delta / mins;
    }

    _liveOverviewState.lastCount = cmdCount;
    _liveOverviewState.lastTs = now;

    animateMetricValue('liveCmdRate', perMin, 1);
    animateMetricValue('liveCmdDelta', delta, 0);

    const rateBar = document.getElementById('liveCmdRateBar');
    const deltaBar = document.getElementById('liveCmdDeltaBar');
    if (rateBar) rateBar.style.width = Math.min(100, Math.round(perMin * 8)) + '%';
    if (deltaBar) deltaBar.style.width = Math.min(100, Math.round(delta * 12)) + '%';

    const pulse = document.getElementById('livePulse');
    const pulseLabel = document.getElementById('livePulseLabel');
    if (pulse) pulse.classList.toggle('live', !!botData.connected);
    if (pulseLabel) pulseLabel.textContent = botData.connected ? 'live stream' : 'offline';

    const clock = document.getElementById('liveClock');
    if (clock) {
        const d = new Date();
        const hh = String(d.getHours()).padStart(2, '0');
        const mm = String(d.getMinutes()).padStart(2, '0');
        const ss = String(d.getSeconds()).padStart(2, '0');
        clock.textContent = `${hh}:${mm}:${ss}`;
    }
}

async function loadClientSwitcher(overviewData = null) {
    const select = document.getElementById('clientTypeSelect');
    if (!select) return;

    let data = overviewData;
    if (!data) {
        const res = await fetchJSON('/api/client');
        if (!res || !res.ok) return;
        data = res;
    }

    const current = String(data.client_type || 'mobile');
    const available = Array.isArray(data.available_clients) && data.available_clients.length
        ? data.available_clients
        : ['web', 'desktop', 'mobile', 'vr'];

    select.innerHTML = available.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join('');
    select.value = available.includes(current) ? current : available[0];
}

function showClientMsg(msg, ok) {
    const el = document.getElementById('clientMsg');
    if (!el) return;
    el.textContent = msg;
    el.className = 'settings-msg ' + (ok ? 'ok' : 'err');
    setTimeout(() => { el.textContent = ''; el.className = 'settings-msg'; }, 2800);
}

async function applyClientType() {
    const select = document.getElementById('clientTypeSelect');
    if (!select) return;
    const clientType = String(select.value || '').trim();
    if (!clientType) return;

    const res = await postJSON('/api/client', { client_type: clientType });
    if (res && res.ok) {
        showClientMsg(`Client switched to ${res.client_type}`, true);
        trackDashboardAction('client_switch', `Switched client to ${res.client_type}`);
        loadOverview();
    } else {
        showClientMsg((res && res.error) || 'Failed to switch client', false);
    }
}

// ── Commands ─────────────────────────────────────────────────────────────────
let _allCommands = [];
let _commandRegistryRetryTimer = null;
let _commandRegistryRetryCount = 0;

async function loadCommands() {
    if (_commandRegistryRetryTimer) clearTimeout(_commandRegistryRetryTimer);
    const res = await fetchJSON('/api/commands');
    if (!res || !res.data) return;
    if (res.data.loading && _commandRegistryRetryCount < 15) {
        _commandRegistryRetryCount += 1;
        setText('cmdCountLabel', 'Loading this client\'s commands...');
        _commandRegistryRetryTimer = setTimeout(loadCommands, 1000);
        return;
    }
    _commandRegistryRetryCount = 0;
    _allCommands = Array.isArray(res.data.commands) ? res.data.commands : [];
    setText('cmdCountLabel', _allCommands.length + ' commands');
    renderCommands(_allCommands);
    if (!_allCommands.length && res.data.error) {
        const grid = document.getElementById('commandsBody');
        if (grid) grid.innerHTML = `<div class="empty-row cmd-empty">${esc(res.data.error)}</div>`;
    }
}

let _cmdFilter = 'all';

function _cmdMatches(c, q) {
    if (_cmdFilter === 'used' && !Number(c.recent_usage || 0)) return false;
    if (_cmdFilter === 'unused' && Number(c.recent_usage || 0)) return false;
    if (_cmdFilter === 'aliased' && !(c.aliases && c.aliases.length)) return false;
    if (!q) return true;
    return c.name.toLowerCase().includes(q) ||
        (c.aliases || []).some(a => a.toLowerCase().includes(q)) ||
        (c.description || '').toLowerCase().includes(q);
}

function applyCommandFilters() {
    const searchEl = document.getElementById('cmdSearch');
    const q = searchEl ? searchEl.value.toLowerCase().trim() : '';
    renderCommands(_allCommands.filter(c => _cmdMatches(c, q)));
}

function renderCommands(list) {
    const grid = document.getElementById('commandsBody');
    const badge = document.getElementById('cmdBadge');
    if (badge) badge.textContent = list.length + (list.length === 1 ? ' command' : ' commands');
    if (!grid) return;
    if (!list || list.length === 0) {
        grid.innerHTML = '<div class="empty-row cmd-empty">No commands found</div>';
        return;
    }
    grid.innerHTML = list.map(c => {
        const uses = Number(c.recent_usage || 0);
        const aliases = c.aliases && c.aliases.length
            ? c.aliases.map(a => `<span class="cmd-alias">${esc(a)}</span>`).join('') : '';
        return `<article class="cmd-card">
            <header><span class="cmd-name">${esc(c.name)}</span>
            <span class="cmd-uses${uses ? ' is-used' : ''}">${uses} ${uses === 1 ? 'use' : 'uses'}</span></header>
            <p>${esc(c.description || 'No description provided.')}</p>
            ${aliases ? `<footer>${aliases}</footer>` : ''}
        </article>`;
    }).join('');
}

async function loadFriends() {
    const res = await fetchJSON('/api/friends');
    const tbody = document.getElementById('friendsBody');
    if (!tbody || !res) return;
    if (!res.ok) {
        tbody.innerHTML = `<tr><td colspan="3" class="empty-row">${esc(res.error || 'Friend data unavailable')}</td></tr>`;
        setText('friendsTotal', '—');
        setText('friendsBadge', 'Unavailable');
        return;
    }
    const friends = Array.isArray(res.friends) ? res.friends : [];
    setText('friendsTotal', res.total ?? friends.length);
    setText('friendsBadge', friends.length + (friends.length === 1 ? ' friend' : ' friends'));
    tbody.innerHTML = friends.length ? friends.map(friend => `<tr>
        <td style="font-weight:600">${esc(friend.username || 'Unknown')}</td>
        <td class="cmd-aliases">${esc(friend.user_id || '—')}</td>
        <td>${friend.bot ? 'Bot' : 'User'}</td>
    </tr>`).join('') : '<tr><td colspan="3" class="empty-row">No friends found</td></tr>';
}

// live search
document.addEventListener('DOMContentLoaded', () => {
    const desktopApi = window.ariaDesktop;
    if (!desktopApi) return;

    document.getElementById('desktopTitlebar')?.removeAttribute('hidden');
    document.querySelectorAll('[data-electron-only]').forEach(el => el.removeAttribute('hidden'));
    document.querySelectorAll('[data-desktop-action]').forEach(button => {
        button.addEventListener('click', async () => {
            const message = document.getElementById('desktopControlsMessage');
            if (message) {
                message.textContent = '';
                message.dataset.state = '';
            }
            try {
                const result = await desktopApi.perform(button.dataset.desktopAction);
                if (!result?.ok && message) {
                    message.dataset.state = 'error';
                    message.textContent = result?.error || 'The desktop action could not be completed.';
                }
            } catch (error) {
                if (message) {
                    message.dataset.state = 'error';
                    message.textContent = error.message || 'The desktop action could not be completed.';
                }
            }
        });
    });
});

document.addEventListener('DOMContentLoaded', () => {
    const chips = document.getElementById('cmdChips');
    if (chips) chips.addEventListener('click', e => {
        const btn = e.target.closest('.cmd-chip');
        if (!btn) return;
        _cmdFilter = btn.dataset.filter || 'all';
        chips.querySelectorAll('.cmd-chip').forEach(x => x.classList.toggle('is-active', x === btn));
        applyCommandFilters();
    });
    const searchEl = document.getElementById('cmdSearch');
    if (searchEl) {
        searchEl.addEventListener('input', applyCommandFilters);
    }
});

// ── Analytics ─────────────────────────────────────────────────────────────────
let _telemetryEntries = [];
let _telemetryChartBound = false;
let _telemetryResizeTimer = null;

function renderTelemetryChart() {
    const canvas = document.getElementById('telemetryChart');
    const metric = document.getElementById('telemetryMetricSelect')?.value || 'latency';
    const summary = document.getElementById('telemetryChartSummary');
    if (!canvas || !summary) return;

    const bounds = canvas.getBoundingClientRect();
    if (!bounds.width) return;
    const width = bounds.width;
    const height = 220;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    canvas.style.height = `${height}px`;
    const chartContext = canvas.getContext('2d');
    if (!chartContext) return;
    chartContext.scale(ratio, ratio);
    chartContext.clearRect(0, 0, width, height);

    const entries = _telemetryEntries.slice(-40);
    const plotLeft = 38;
    const plotRight = width - 10;
    const plotTop = 14;
    const plotBottom = height - 21;
    const plotHeight = plotBottom - plotTop;
    const accent = getComputedStyle(document.documentElement).getPropertyValue('--a2').trim() || '#69b7ff';
    chartContext.font = '9px "DM Mono", monospace';
    chartContext.lineWidth = 1;
    chartContext.strokeStyle = 'rgba(177,197,219,0.1)';
    chartContext.fillStyle = '#748394';

    for (let lineIndex = 0; lineIndex <= 3; lineIndex += 1) {
        const y = plotTop + plotHeight * lineIndex / 3;
        chartContext.beginPath();
        chartContext.moveTo(plotLeft, y);
        chartContext.lineTo(plotRight, y);
        chartContext.stroke();
    }

    if (!entries.length) {
        chartContext.fillStyle = '#748394';
        chartContext.textAlign = 'center';
        chartContext.fillText('No runtime history yet', width / 2, height / 2);
        summary.textContent = 'No runtime command history is available yet.';
        return;
    }

    if (metric === 'outcomes') {
        const bucketCount = Math.min(8, entries.length);
        const bucketWidth = (plotRight - plotLeft) / bucketCount;
        const maxBucketSize = Math.max(1, ...Array.from({ length: bucketCount }, (_, bucketIndex) =>
            Math.floor((bucketIndex + 1) * entries.length / bucketCount) - Math.floor(bucketIndex * entries.length / bucketCount)
        ));
        let successes = 0;
        let failures = 0;
        for (let bucketIndex = 0; bucketIndex < bucketCount; bucketIndex += 1) {
            const start = Math.floor(bucketIndex * entries.length / bucketCount);
            const end = Math.floor((bucketIndex + 1) * entries.length / bucketCount);
            const bucket = entries.slice(start, end);
            const failed = bucket.filter(entry => String(entry.status || 'success').toLowerCase() !== 'success').length;
            const succeeded = bucket.length - failed;
            successes += succeeded;
            failures += failed;
            const barHeight = Math.max(4, plotHeight * bucket.length / maxBucketSize);
            const groupWidth = Math.min(24, bucketWidth * 0.62);
            const barWidth = Math.max(3, (groupWidth - 3) / 2);
            const groupX = plotLeft + bucketIndex * bucketWidth + (bucketWidth - groupWidth) / 2;
            chartContext.fillStyle = accent;
            chartContext.fillRect(groupX, plotBottom - barHeight * (succeeded / Math.max(bucket.length, 1)), barWidth, barHeight * (succeeded / Math.max(bucket.length, 1)));
            chartContext.fillStyle = '#e87980';
            chartContext.fillRect(groupX + barWidth + 3, plotBottom - barHeight * (failed / Math.max(bucket.length, 1)), barWidth, barHeight * (failed / Math.max(bucket.length, 1)));
        }
        chartContext.textAlign = 'left';
        chartContext.fillStyle = accent;
        chartContext.fillText('OK', plotLeft, height - 4);
        chartContext.fillStyle = '#e87980';
        chartContext.fillText('FAILED', plotLeft + 27, height - 4);
        canvas.setAttribute('aria-label', `Recent command outcomes: ${successes} successful, ${failures} failed`);
        summary.textContent = `${entries.length} recent executions · ${successes} successful · ${failures} failed`;
        return;
    }

    const samples = entries.map(entry => Number(entry.duration_ms)).filter(value => Number.isFinite(value) && value >= 0);
    if (!samples.length) {
        chartContext.fillStyle = '#748394';
        chartContext.textAlign = 'center';
        chartContext.fillText('No response-time samples available', width / 2, height / 2);
        canvas.setAttribute('aria-label', 'No recent command response-time data available');
        summary.textContent = `${entries.length} recent executions · response-time data unavailable`;
        return;
    }

    const maximum = Math.max(1, ...samples);
    const points = samples.map((value, pointIndex) => ({
        x: plotLeft + (samples.length === 1 ? 0 : pointIndex * (plotRight - plotLeft) / (samples.length - 1)),
        y: plotBottom - value / maximum * plotHeight,
        value,
    }));
    chartContext.beginPath();
    chartContext.moveTo(points[0].x, plotBottom);
    points.forEach(point => chartContext.lineTo(point.x, point.y));
    chartContext.lineTo(points[points.length - 1].x, plotBottom);
    chartContext.closePath();
    chartContext.fillStyle = 'rgba(105,183,255,0.08)';
    chartContext.fill();
    chartContext.beginPath();
    points.forEach((point, pointIndex) => {
        if (pointIndex === 0) chartContext.moveTo(point.x, point.y);
        else chartContext.lineTo(point.x, point.y);
    });
    chartContext.strokeStyle = accent;
    chartContext.lineWidth = 2;
    chartContext.stroke();
    chartContext.fillStyle = '#90a0b0';
    chartContext.textAlign = 'left';
    chartContext.fillText(`${Math.round(maximum)} ms`, 2, plotTop + 3);
    chartContext.textAlign = 'right';
    chartContext.fillText(`${Math.round(Math.min(...samples))} ms`, plotRight, height - 4);
    const average = Math.round(samples.reduce((total, value) => total + value, 0) / samples.length);
    const failures = entries.filter(entry => String(entry.status || 'success').toLowerCase() !== 'success').length;
    canvas.setAttribute('aria-label', `Recent command response times, average ${average} milliseconds`);
    summary.textContent = `${samples.length} response samples · ${average} ms average · ${failures} failed events`;
}

function bindTelemetryChart() {
    if (_telemetryChartBound) return;
    _telemetryChartBound = true;
    document.getElementById('telemetryMetricSelect')?.addEventListener('change', renderTelemetryChart);
    window.addEventListener('resize', () => {
        clearTimeout(_telemetryResizeTimer);
        _telemetryResizeTimer = setTimeout(renderTelemetryChart, 100);
    });
}

async function loadAnalytics() {
    bindTelemetryChart();
    const [res, historyResponse] = await Promise.all([
        fetchJSON('/api/analytics'),
        fetchJSON('/api/history'),
    ]);
    _telemetryEntries = Array.isArray(historyResponse?.data?.entries) ? historyResponse.data.entries : [];
    renderTelemetryChart();
    if (!res || !res.data) return;
    const d = res.data;
    loadAdvancedAnalytics();
    setText('totalCommands', d.total_commands ?? 0);
    countUp('totalCommands', d.total_commands ?? 0, 800);
    setText('successRate', (d.success_rate ?? 100) + '%');
    setText('avgResponseMs', (d.avg_response_ms ?? 0) + ' ms');

    const wrap = document.getElementById('topCommandsBody');
    if (!wrap) return;
    if (!d.top_commands || d.top_commands.length === 0) {
        wrap.innerHTML = '<div class="empty-row" style="padding:32px 20px">No command data yet</div>';
        return;
    }
    const maxCount = d.top_commands[0].count || 1;
    wrap.innerHTML = d.top_commands.map((c, i) => {
        const pct = Math.round((c.count / maxCount) * 100);
        const rankClass = i === 0 ? 'top-cmd-rank gold' : 'top-cmd-rank';
        return `<div class="top-cmd-row">
            <div class="${rankClass}">${i + 1}</div>
            <div class="top-cmd-name">${esc(c.name)}</div>
            <div class="top-cmd-bar-wrap"><div class="top-cmd-bar" style="width:${pct}%"></div></div>
            <div class="top-cmd-count">${c.count}</div>
        </div>`;
    }).join('');
}

// ── History ───────────────────────────────────────────────────────────────────
async function loadHistory() {
    const res = await fetchJSON('/api/history');
    if (!res || !res.data) return;
    const d = res.data;
    const badge = document.getElementById('historyBadge');
    if (badge) badge.textContent = (d.total ?? 0) + ' entries';

    const feed = document.getElementById('historyFeed');
    if (!feed) return;
    if (!d.entries || d.entries.length === 0) {
        feed.innerHTML = '<div class="log-loading">No history entries yet — Run some commands!</div>';
        return;
    }
    feed.innerHTML = d.entries.slice().reverse().map(e => {
        if (typeof e === 'object' && e !== null) {
            // Improved command name resolution with multiple fallback paths
            const cmd = String(e.command || e.cmd || e.name || e.op || '').trim() || '(unknown)';
            const user = e.user || e.author || e.author_id || e.username || '';
            const guild = e.guild_id || e.guild || e.server || '';
            const chan  = e.channel_id || e.channel || '';
            let ts    = e.timestamp || e.time || '';
            
            // Format timestamp if it's a unix number
            if (ts && !isNaN(ts)) {
                try {
                    ts = new Date(Number(ts) * 1000).toLocaleTimeString('en-US', {hour: '2-digit', minute: '2-digit', second: '2-digit'});
                } catch (ex) {
                    ts = String(ts);
                }
            } else {
                ts = String(ts || '');
            }
            
            const status = e.status || e.result || '';
            const dur = e.duration_ms != null ? `${Math.round(Number(e.duration_ms) || 0)}ms` : '';
            const statusBadge = status === 'success' || status === 'ok'
                ? '<span class="badge badge-ok">ok</span>'
                : status ? `<span class="badge badge-warn">${esc(status)}</span>` : '';
            return `<div class="history-item">
                <div class="history-dot"></div>
                <div class="history-content">
                    <span class="history-cmd">${esc(cmd)}</span>
                    ${statusBadge}
                    <div class="history-meta">${[
                        user  ? '👤 ' + esc(String(user)) : '',
                        guild ? '🏠 ' + esc(String(guild)) : '',
                        chan  ? '# ' + esc(String(chan))   : '',
                        ts   ? '🕐 ' + esc(ts)    : '',
                        dur  ? '⚡ ' + dur   : ''
                    ].filter(Boolean).join(' &nbsp;·&nbsp; ')}</div>
                </div>
            </div>`;
        }
        return `<div class="history-item"><div class="history-dot"></div><div class="history-content"><div class="history-raw">${esc(String(e))}</div></div></div>`;
    }).join('');
}

// ── Boost ─────────────────────────────────────────────────────────────────────

async function loadBoost() {
    const res = await fetchJSON('/api/boost');
    if (!res || !res.data) return;
    const data = res.data;
    const live = data.live || {};
    const total = Number(live.total_slots) || 0;
    const used  = Number(live.slots_used)  || 0;
    const cd    = Number(live.slots_cooldown) || 0;
    const avail = Number(live.slots_available) || 0;

    setText('boostTotalSlots',     total  || '—');
    setText('boostSlotsAvail',     avail  || '—');
    setText('boostSlotsUsed',      used   || '—');
    setText('boostSlotsCd',        cd     || '—');
    setText('boostTracked',        live.tracked_servers   ?? '—');
    setText('boostBoostedServers', live.boosted_servers   ?? '—');
    setText('boostTotalOut',       live.total_boosts      ?? '—');
    setText('boostStatusText',     live.status            || '—');

    // Visual slot bar
    const pct   = total ? Math.round((used / total) * 100) : 0;
    const cdPct = total ? Math.round((cd   / total) * 100) : 0;
    setText('boostSlotPct', pct + '%');
    const fill   = document.getElementById('boostSlotFill');
    const cdFill = document.getElementById('boostSlotCdFill');
    if (fill)   fill.style.width   = pct + '%';
    if (cdFill) { cdFill.style.width = cdPct + '%'; cdFill.style.left = pct + '%'; }

}

// ── Help / Token Guide ───────────────────────────────────────────────────────
function loadHelp() {
    // Just make sure the content is visible
    const section = document.getElementById('section-help');
    if (section) {
        // Reset tabs to show desktop by default
        const tabs = section.querySelectorAll('.help-tab-content');
        tabs.forEach(tab => tab.classList.remove('active'));
        const desktopTab = document.getElementById('help-tab-desktop');
        if (desktopTab) desktopTab.classList.add('active');
        
        const tabBtns = section.querySelectorAll('.help-tab-btn');
        tabBtns.forEach(btn => btn.classList.remove('active'));
        if (tabBtns[0]) tabBtns[0].classList.add('active');
    }
    trackDashboardAction('view_help', 'Opened help guide');
}

function switchHelpTab(tabName, btn) {
    // Hide all tabs
    const tabContents = document.querySelectorAll('.help-tab-content');
    tabContents.forEach(tab => tab.classList.remove('active'));
    
    // Deactivate all buttons
    const tabBtns = document.querySelectorAll('.help-tab-btn');
    tabBtns.forEach(b => b.classList.remove('active'));
    
    // Show selected tab
    const selectedTab = document.getElementById(`help-tab-${tabName}`);
    if (selectedTab) selectedTab.classList.add('active');
    
    // Activate button
    if (btn) btn.classList.add('active');
    
    trackDashboardAction('help_tab_switch', `Switched help tab to ${tabName}`);
}

function copyToClipboard(elementRef) {
    const codeElement = typeof elementRef === 'string'
        ? document.getElementById(elementRef)
        : elementRef;
    if (!codeElement) return;
    
    const code = codeElement.textContent;
    navigator.clipboard.writeText(code).then(() => {
        showToast('Copied', 'Code copied to clipboard!', 'ok');
    }).catch(() => {
        // Fallback for older browsers
        const textarea = document.createElement('textarea');
        textarea.value = code;
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand('copy');
            showToast('Copied', 'Code copied to clipboard!', 'ok');
        } catch (err) {
            showToast('Copy Failed', 'Could not copy to clipboard', 'err');
        }
        document.body.removeChild(textarea);
    });
}

// ── Settings ─────────────────────────────────────────────────────────────────
async function loadSettings() {
    const res = await fetchJSON('/api/config');
    if (!res || !res.data) return;
    const d = res.data;
    setText('cfgPrefix', d.prefix);
    setText('cfgAutoDelete', d.auto_delete_enabled ? 'Enabled' : 'Disabled');
    setText('cfgDelay', d.auto_delete_delay + 's');
    setText('cfgStatus', d.status || 'online');

    const tog = document.getElementById('newAutoDeleteToggle');
    if (tog) tog.value = d.auto_delete_enabled ? 'true' : 'false';
}

function showSettingsMsg(msg, ok) {
    const el = document.getElementById('settingsMsg');
    if (!el) return;
    el.textContent = msg;
    el.className = 'settings-msg ' + (ok ? 'ok' : 'err');
    setTimeout(() => { el.textContent = ''; el.className = 'settings-msg'; }, 3000);
}

async function applyPrefix() {
    const val = document.getElementById('newPrefixInput').value.trim();
    if (!val) { showSettingsMsg('Enter a prefix first.', false); return; }
    const res = await postJSON('/api/config', { prefix: val });
    if (res && res.ok) {
        showSettingsMsg('Prefix updated to: ' + res.data.prefix, true);
        showToast('Prefix Updated', `New prefix: ${res.data.prefix}`, 'ok');
        trackDashboardAction('config_prefix', `Updated prefix to ${res.data.prefix}`);
        loadSettings();
        loadOverview();
    } else {
        showSettingsMsg('Failed to update prefix.', false);
        showToast('Update Failed', 'Could not update prefix', 'err');
    }
}

async function applyDelay() {
    const val = parseInt(document.getElementById('newDelayInput').value);
    if (isNaN(val) || val < 1) { showSettingsMsg('Enter a valid delay (1–600).', false); return; }
    const res = await postJSON('/api/config', { auto_delete_delay: val });
    if (res && res.ok) {
        showSettingsMsg('Delay updated to: ' + res.data.auto_delete_delay + 's', true);
        showToast('Delay Updated', `Auto-delete: ${res.data.auto_delete_delay}s`, 'ok');
        trackDashboardAction('config_delay', `Updated auto-delete delay to ${res.data.auto_delete_delay}s`);
        loadSettings();
    } else {
        showSettingsMsg('Failed to update delay.', false);
        showToast('Update Failed', 'Could not update delay', 'err');
    }
}

async function applyAutoDelete() {
    const val = document.getElementById('newAutoDeleteToggle').value === 'true';
    const res = await postJSON('/api/config', { auto_delete_enabled: val });
    if (res && res.ok) {
        showSettingsMsg('Auto-delete ' + (val ? 'enabled' : 'disabled'), true);
        trackDashboardAction('config_autodelete', `Set auto-delete ${val ? 'enabled' : 'disabled'}`);
        loadSettings();
    } else {
        showSettingsMsg('Failed to update.', false);
    }
}

// ── Help Modal Functions ──────────────────────────────────────────────────
function openHelpModal() {
    const modal = document.getElementById('helpModal');
    if (modal) {
        modal.removeAttribute('hidden');
        document.body.style.overflow = 'hidden';
    }
}

function closeHelpModal() {
    const modal = document.getElementById('helpModal');
    if (modal) {
        modal.setAttribute('hidden', '');
        document.body.style.overflow = '';
    }
}

function switchHelpTab(tabName, btn) {
    const tabContents = document.querySelectorAll('.help-tab-content');
    tabContents.forEach(tab => tab.classList.remove('active'));
    const tabBtns = document.querySelectorAll('.help-tab-btn');
    tabBtns.forEach(b => b.classList.remove('active'));
    const selectedTab = document.getElementById(`help-tab-${tabName}`);
    if (selectedTab) selectedTab.classList.add('active');
    if (btn) btn.classList.add('active');
}

function copyToClipboard(elementRef) {
    const codeElement = typeof elementRef === 'string'
        ? document.getElementById(elementRef)
        : elementRef;
    if (!codeElement) return;
    const code = codeElement.textContent;
    navigator.clipboard.writeText(code).then(() => {
        showToast('Copied', 'Code copied!', 'ok');
    }).catch(() => {
        const textarea = document.createElement('textarea');
        textarea.value = code;
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand('copy');
            showToast('Copied', 'Code copied!', 'ok');
        } catch (err) {
            showToast('Error', 'Copy failed', 'err');
        }
        document.body.removeChild(textarea);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const menuBtn = document.getElementById('topbarMenuBtn');
    const menuDropdown = document.getElementById('topbarMenuDropdown');
    if (menuBtn && menuDropdown) {
        menuBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const open = menuDropdown.hasAttribute('hidden');
            menuDropdown.toggleAttribute('hidden', !open);
            menuBtn.setAttribute('aria-expanded', String(open));
        });
        document.addEventListener('click', () => {
            menuDropdown.setAttribute('hidden', '');
            menuBtn.setAttribute('aria-expanded', 'false');
        });
    }
});

// ── Section router ────────────────────────────────────────────────────────────
const _sectionLoadPromises = new Map();

function loadSection(name) {
    const inProgress = _sectionLoadPromises.get(name);
    if (inProgress) return inProgress;

    let tasks;
    if (name === 'overview') tasks = [loadOverview];
    else if (name === 'account') tasks = [loadAccount];
    else if (name === 'friends') tasks = [loadFriends];
    else if (name === 'administration') tasks = [loadAdministration];
    else if (name === 'owner') tasks = [loadOwnerPanel];
    else if (name === 'commands') tasks = [loadCommands];
    else if (name === 'analytics') tasks = [loadAnalytics];
    else if (name === 'history') tasks = [loadHistory];
    else if (name === 'logger') tasks = [loadMessageLogger];
    else if (name === 'automation') tasks = [loadCommandTools];
    else if (name === 'boost') tasks = [loadBoost];
    else if (name === 'rpc') {
        let savedTab = 'editor';
        try { savedTab = localStorage.getItem('aria.rpcDashboardTab') || savedTab; } catch (_) {}
        setRpcTab(savedTab);
        tasks = [loadRpc, loadRpcStack, loadSpotifyLyrics];
    }
    else if (name === 'presence') tasks = [loadPresence];
    else if (name === 'hosted') tasks = [loadHosted];
    else if (name === 'logs') tasks = [loadLogs];
    else if (name === 'users') tasks = [loadDashUsers];
    else if (name === 'settings') tasks = [loadSettings];
    else if (name === 'chat') tasks = [loadChat];
    else if (name === 'system') tasks = [loadSystemStats];
    else if (name === 'cmdbreakdown') tasks = [loadCommandBreakdown];
    else if (name === 'errors') tasks = [loadErrorLogs];
    else if (name === 'leaderboard') tasks = [loadLeaderboard];
    else if (name === 'serverinfo') tasks = [loadServerInfo];
    else if (name === 'activitymap') tasks = [loadActivityMap];
    else if (name === 'notifications') tasks = [loadNotifications];
    else if (name === 'advanced-analytics') tasks = [loadAdvancedAnalytics];
    else if (name === 'widgets') tasks = [loadWidgets];
    else return Promise.resolve();

    const pending = Promise.allSettled(tasks.map(task => Promise.resolve().then(task)))
        .then(results => {
            const failure = results.find(result => result.status === 'rejected');
            if (failure) reportDashboardError(`Loading ${name}`, failure.reason);
        })
        .finally(() => {
            if (_sectionLoadPromises.get(name) === pending) _sectionLoadPromises.delete(name);
        });
    _sectionLoadPromises.set(name, pending);
    return pending;
}

async function loadAccount() {
    const [profileData, identityData] = await Promise.all([
        fetchJSON('/api/dash/me'),
        fetchJSON('/api/max/user-profile'),
    ]);
    const profile = profileData && profileData.ok ? profileData.profile : null;
    const identity = identityData && identityData.ok ? identityData : {};
    if (!profile) {
        setText('accountUsername', 'Account unavailable');
        setText('accountConnection', 'Unavailable');
        return;
    }

    setText('accountUsername', profile.username || 'Aria user');
    setText('accountUserId', profile.user_id || '—');
    setText('accountRole', profile.is_owner ? 'Owner' : profile.is_admin ? 'Admin' : profile.role || 'User');
    setText('accountRoleBadge', profile.is_owner ? 'owner' : profile.is_admin ? 'admin' : 'member');
    setText('accountInstance', profile.instance_id || '—');
    setText('accountCreatedAt', fmtTs(profile.created_at));
    setText('accountLastLogin', fmtTs(profile.last_login_at));
    setText('accountLastSeen', fmtTs(profile.last_seen_at));

    const botResponse = await fetchJSON('/api/bot');
    const bot = botResponse && botResponse.data ? botResponse.data : {};
    setText('accountInstance', bot.instance_id || profile.instance_id || '—');
    const connected = !!bot.connected;
    setText('accountConnection', connected ? 'Runtime connected' : 'Runtime offline');
    setText('accountPrefix', bot.prefix || '$');
    setText('accountClientType', bot.client_type || '—');
    setText('accountLatency', bot.gateway_latency_ms == null ? '—' : `${Math.round(Number(bot.gateway_latency_ms))} ms`);
    setText('accountUptime', bot.uptime || '—');
    const connectionDot = document.getElementById('accountConnectionDot');
    if (connectionDot) connectionDot.classList.toggle('is-online', connected);
    setAvatarImage(document.getElementById('accountAvatar'), identity.avatar_url, profile.user_id, { allowFallback: true });
}

async function loadAdministration() {
    const response = await fetchJSON('/api/bot');
    const bot = response && response.data ? response.data : null;
    if (!bot) {
        setText('adminGatewayState', 'Unavailable');
        setText('adminCommandCount', '—');
        setText('adminPrefix', '$');
        setText('adminUptime', '—');
        return;
    }
    setText('adminGatewayState', bot.connected ? 'Connected' : 'Offline');
    setText('adminCommandCount', bot.commands_registered ?? 0);
    setText('adminPrefix', bot.prefix || '$');
    setText('adminUptime', bot.uptime || '—');
}

// ── Maximalist Dashboard Panel Loaders ─────────────────────────────────────
async function loadSystemStats() {
    const res = await fetchJSON('/api/max/system-stats');
    setText('cpuUsage', res && res.cpu != null ? res.cpu + '%' : '—');
    setText('ramUsage', res && res.ram != null ? res.ram + '%' : '—');
    setText('diskUsage', res && res.disk != null ? res.disk + '%' : '—');
    setText('netUsage', res && res.net ? `↑${Math.round(res.net.sent/1024)}KB ↓${Math.round(res.net.recv/1024)}KB` : '—');
    // Timeline chart (placeholder: random walk)
    const canvas = document.getElementById('resourceTimeline');
    if (canvas) {
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0,0,canvas.width,canvas.height);
        ctx.beginPath();
        for (let i=0; i<56; ++i) {
            const y = 50 + 8*Math.sin(i/3 + Date.now()/4000);
            ctx.lineTo(10+i*10, y);
        }
        ctx.strokeStyle = '#06b6d4';
        ctx.lineWidth = 2.2;
        ctx.stroke();
    }
}

async function loadCommandBreakdown() {
    const res = await fetchJSON('/api/max/command-breakdown');
    // Pie chart
    const pie = document.getElementById('cmdPie');
    if (pie && res && res.pie) {
        const ctx = pie.getContext('2d');
        ctx.clearRect(0,0,pie.width,pie.height);
        const data = res.pie;
        const total = data.reduce((a,b)=>a+b.count,0)||1;
        let start = 0;
        data.forEach((c,i) => {
            const val = c.count/total;
            ctx.beginPath();
            ctx.moveTo(130,90);
            ctx.arc(130,90,80,start,start+val*2*Math.PI);
            ctx.closePath();
            ctx.fillStyle = ['#8b5cf6','#ec4899','#06b6d4','#10b981','#f59e0b','#ef4444'][i%6];
            ctx.fill();
            start += val*2*Math.PI;
        });
    }
    // Bar chart
    const bar = document.getElementById('cmdBar');
    if (bar && res && res.bar) {
        const ctx = bar.getContext('2d');
        ctx.clearRect(0,0,bar.width,bar.height);
        const cats = Object.entries(res.bar);
        const max = Math.max(1, ...cats.map(c=>c[1]));
        cats.forEach((c,i) => {
            ctx.fillStyle = ['#8b5cf6','#ec4899','#06b6d4','#10b981','#f59e0b','#ef4444'][i%6];
            ctx.fillRect(30+i*50, 170-(c[1]/max)*140, 36, (c[1]/max)*140);
            ctx.fillStyle = '#fff';
            ctx.font = '13px sans-serif';
            ctx.fillText(c[0], 30+i*50, 175);
        });
    }
}

async function loadErrorLogs() {
    const res = await fetchJSON('/api/max/errors');
    const feed = document.getElementById('errorFeed');
    if (!feed) return;
    if (!res || !res.errors || res.errors.length === 0) {
        feed.innerHTML = '<div class="log-loading">No errors found.</div>';
        return;
    }
    feed.innerHTML = res.errors.slice().reverse().map(e => `<div class="history-item"><div class="history-dot"></div><div class="history-content"><div class="history-raw">${esc(e)}</div></div></div>`).join('');
}

async function loadLeaderboard() {
    const res = await fetchJSON('/api/max/leaderboard');
    const tbody = document.getElementById('leaderboardBody');
    if (!tbody) return;
    if (!res || !res.leaderboard || res.leaderboard.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3">No data</td></tr>';
        return;
    }
    tbody.innerHTML = res.leaderboard.map(u => `<tr><td>${esc(u.username)}</td><td>${u.count}</td><td>${fmtTs(u.last_seen_at)}</td></tr>`).join('');
}

async function loadServerInfo() {
    const res = await fetchJSON('/api/max/server-info');
    const g = res && res.guild || {};
    setText('guildName', g.name || '—');
    setText('guildId', g.id || '—');
    setText('guildMembers', g.members || '—');
    setText('guildRegion', g.region || '—');
}

async function loadActivityMap() {
    const res = await fetchJSON('/api/max/activity-map');
    // Timeline
    const timeline = res && res.timeline || [];
    const tcanvas = document.getElementById('activityTimeline');
    if (tcanvas) {
        const ctx = tcanvas.getContext('2d');
        ctx.clearRect(0,0,tcanvas.width,tcanvas.height);
        ctx.beginPath();
        timeline.forEach((v,i) => {
            const x = 20+i*24;
            const y = 50-(v/Math.max(1,...timeline))*40;
            if (i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
        });
        ctx.strokeStyle = '#f59e0b';
        ctx.lineWidth = 2.2;
        ctx.stroke();
    }
    // Heatmap
    const heatmap = res && res.heatmap || [];
    const hcanvas = document.getElementById('activityHeatmap');
    if (hcanvas) {
        const ctx = hcanvas.getContext('2d');
        ctx.clearRect(0,0,hcanvas.width,hcanvas.height);
        for (let h=0; h<24; ++h) for (let d=0; d<7; ++d) {
            const v = heatmap[h] && heatmap[h][d] || 0;
            ctx.fillStyle = `rgba(139,92,246,${0.08+0.7*(v/Math.max(1,...heatmap.flat()))})`;
            ctx.fillRect(20+d*80, 5+h*5, 70, 4);
        }
    }
}

// ── Discord notification center ───────────────────────────────────────────────

const NOTIF_ICONS = {
    dm:             '✉️',
    mention:        '🔔',
    friend_request: '👋',
    friend_accept:  '✅',
    friend_remove:  '👤',
    guild_join:     '🏠',
    guild_remove:   '🚪',
    ban:            '🔨',
    unban:          '🔓',
    pin:            '📌',
    reaction:       '❤️',
    call:           '📞',
    system:         '⚙️',
};

const NOTIF_COLORS = {
    dm:             '#accbee',
    mention:        '#f59e0b',
    friend_request: '#67e8f9',
    friend_accept:  '#86efac',
    friend_remove:  '#94a3b8',
    guild_join:     '#86efac',
    guild_remove:   '#ef4444',
    ban:            '#ef4444',
    unban:          '#86efac',
    pin:            '#accbee',
    reaction:       '#ec4899',
    call:           '#67e8f9',
    system:         '#94a3b8',
};

async function loadNotifications() {
    // Legacy feed on Notifications section page
    const feed = document.getElementById('notificationFeed');
    if (!feed) return;
    let res = await fetchJSON('/api/discord/notifications');
    if (!res || !res.ok) {
        const fallback = await fetchJSON('/api/max/notifications');
        const events = (fallback && fallback.ok && Array.isArray(fallback.events))
            ? fallback.events.map(e => ({
                title: e.action || 'Activity',
                body: e.details || '',
                author: e.user || '',
                ts: Number(e.ts || 0),
                kind: 'system',
                icon: '⚙️',
            }))
            : [];
        res = { ok: true, notifications: events };
    }
    if (!res || !res.notifications || !res.notifications.length) {
        feed.innerHTML = '<div class="log-loading">No Discord notifications yet.</div>';
        return;
    }
    feed.innerHTML = res.notifications.map(n => {
        const icon = n.icon || NOTIF_ICONS[n.kind] || '🔔';
        const color = NOTIF_COLORS[n.kind] || 'var(--a2)';
        const sub = [n.author, n.guild_id ? `Server ${n.guild_id}` : ''].filter(Boolean).join(' · ');
        return `<div class="history-item">
            <div class="history-dot" style="background:${color}"></div>
            <div class="history-content">
                <span class="history-cmd">${icon} ${esc(n.title)}</span>
                <div class="history-meta">${esc(sub)} · ${relativeTime(n.ts)}</div>
                ${n.body ? `<div class="history-raw">${esc(n.body)}</div>` : ''}
            </div>
        </div>`;
    }).join('');
}

async function refreshNotificationCenter() {
    const bellBadge = document.getElementById('bellBadge');
    const bell      = document.getElementById('topbarBell');
    const list      = document.getElementById('notificationCenterList');
    if (!bellBadge || !bell || !list) return;

    let res = await fetchJSON('/api/discord/notifications');
    if (!res || !res.ok) {
        const fallback = await fetchJSON('/api/max/notifications');
        const events = (fallback && fallback.ok && Array.isArray(fallback.events))
            ? fallback.events.map(e => ({
                title: e.action || 'Activity',
                body: e.details || '',
                author: e.user || '',
                ts: Number(e.ts || 0),
                kind: 'system',
                icon: '⚙️',
                read: false,
            }))
            : [];
        res = { ok: true, notifications: events };
    }
    const notifs = (res && res.ok && Array.isArray(res.notifications)) ? res.notifications : [];
    _notificationState.events = notifs;

    const unread = notifs.filter(n => !n.read && n.ts > Number(_notificationState.seenTs || 0));
    bellBadge.textContent   = String(unread.length || '');
    bellBadge.style.display = unread.length ? 'inline-flex' : 'none';
    bell.classList.toggle('has-unread', unread.length > 0);

    if (!notifs.length) {
        list.innerHTML = '<div class="notification-empty">No Discord notifications yet.</div>';
        return;
    }

    list.innerHTML = notifs.map(n => {
        const isUnread = !n.read && n.ts > Number(_notificationState.seenTs || 0);
        const icon  = n.icon || NOTIF_ICONS[n.kind] || '🔔';
        const color = NOTIF_COLORS[n.kind] || 'var(--a2)';
        const meta  = [n.author, n.guild_id ? 'Server' : (n.channel_id ? 'DM' : '')].filter(Boolean).join(' · ');
        return `<div class="notification-item ${isUnread ? 'unread' : ''}" style="${isUnread ? `border-left:2px solid ${color}` : ''}">
            <div class="notification-item-head">
                <span class="notification-action">${icon} ${esc(n.title)}</span>
                <span class="notification-time">${relativeTime(n.ts)}</span>
            </div>
            ${meta ? `<div class="notification-meta">${esc(meta)}</div>` : ''}
            ${n.body ? `<div class="notification-details">${esc(n.body)}</div>` : ''}
        </div>`;
    }).join('');
}

function markNotificationsSeen() {
    const maxTs = _notificationState.events.reduce(
        (m, n) => Math.max(m, Number(n.ts || 0)),
        Number(_notificationState.seenTs || 0)
    );
    _notificationState.seenTs = maxTs;
    // Mark read on server too
    postJSON('/api/discord/notifications/mark_read', {});
    refreshNotificationCenter();
}

function toggleNotificationCenter(forceState = null) {
    const panel = document.getElementById('notificationCenter');
    if (!panel) return;
    const next = forceState == null ? !_notificationState.open : !!forceState;
    _notificationState.open = next;
    panel.hidden = !next;
    document.getElementById('topbarBell')?.setAttribute('aria-expanded', String(next));
    if (next) {
        markNotificationsSeen();
    }
}

async function loadAdvancedAnalytics() {
    const res = await fetchJSON('/api/max/advanced-analytics');
    setText('advSuccessRate', res && res.success_rate != null ? res.success_rate+'%' : '—');
    setText('advAvgLatency', res && res.avg_latency != null ? res.avg_latency+'ms' : '—');
    setText('advFailures', res && res.failures != null ? res.failures : '—');
    setText('advLongestCmd', res && res.longest_cmd != null ? res.longest_cmd+'ms' : '—');
}

async function loadWidgets() {
    const grid = document.getElementById('widgetGrid');
    if (!grid) return;
    const res = await fetchJSON('/api/max/widgets');
    if (!res || !res.widgets) {
        grid.innerHTML = '<div class="log-loading">No widgets found.</div>';
        return;
    }
    grid.innerHTML = res.widgets.map(w => `<div class="widget-card">${esc(w.name)}</div>`).join('');
}

// ── RPC ───────────────────────────────────────────────────────────────────────
const RPC_TYPE_LABELS = ['Playing', 'Streaming', 'Listening to', 'Watching', '', 'Competing in'];
const DEFAULT_RPC_APPLICATION_ID = '367827983903490050';
const RPC_DRAFT_STORAGE_KEY = 'aria_rpc_draft_v1';
let _rpcDraftRestored = false;
let _rpcActiveActivities = [];

const RPC_TYPE_CONFIG = {
    0: { activityType: 0, label: 'Playing a game', applicationId: '367827983903490050' },
    1: { activityType: 1, label: 'Streaming', applicationId: '111299001912' },
    2: { activityType: 2, label: 'Listening to', applicationId: '534203414247112723' },
    3: { activityType: 3, label: 'Watching', applicationId: '367827983903490050' },
    5: { activityType: 5, label: 'Competing in', applicationId: '367827983903490050' },
    spotify: { activityType: 2, label: 'Listening to', applicationId: '3201606009684', name: 'Spotify' },
    youtube: { activityType: 3, label: 'Watching', applicationId: '111299001912', name: 'YouTube' },
    crunchyroll: { activityType: 3, label: 'Watching', applicationId: '981509069309354054', name: 'Crunchyroll' },
    xbox: { activityType: 0, label: 'Playing a game', applicationId: '622174530214821906', name: 'Game', platform: 'xbox' },
    playstation: { activityType: 0, label: 'Playing a game', applicationId: '1470539864909943067', name: 'Game', platform: 'ps5' },
    ps4: { activityType: 0, label: 'Playing a game', applicationId: '1470539864909943067', name: 'Game', platform: 'ps4' },
    vrchat: { activityType: 0, label: 'Playing VRChat', applicationId: '1498387526501535835', name: 'VRChat', platform: 'meta_quest' },
    quest: { activityType: 0, label: 'Playing a game', applicationId: '367827983903490050', name: 'Game', platform: 'meta_quest' },
    android: { activityType: 0, label: 'Playing a game', applicationId: '367827983903490050', name: 'Game', platform: 'android' },
    ios: { activityType: 0, label: 'Playing a game', applicationId: '367827983903490050', name: 'Game', platform: 'ios' },
    samsung: { activityType: 0, label: 'Playing a game', applicationId: '367827983903490050', name: 'Game', platform: 'samsung' },
    desktop: { activityType: 0, label: 'Playing a game', applicationId: '367827983903490050', name: 'Game', platform: 'desktop' },
    custom_status: { activityType: 4, label: 'Custom Status', applicationId: '367827983903490050', name: 'Custom Status', customStatus: true },
};

const RPC_APP_ID_BY_NAME = [
    { keys: ['spotify'], appId: '3201606009684' },
    { keys: ['crunchyroll', 'crunchy roll'], appId: '981509069309354054' },
    { keys: ['youtube'], appId: '111299001912' },
    { keys: ['xbox'], appId: '622174530214821906' },
    { keys: ['playstation', 'ps4', 'ps5'], appId: '1470539864909943067' },
    { keys: ['vrchat'], appId: '1498387526501535835' },
];

function normalizeRpcActivityName(name) {
    return String(name || '').toLowerCase().replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim();
}

function inferRpcAppIdFromName(name) {
    const normalized = normalizeRpcActivityName(name);
    if (!normalized) return DEFAULT_RPC_APPLICATION_ID;
    for (const entry of RPC_APP_ID_BY_NAME) {
        if (entry.keys.some(k => normalized.includes(k))) return entry.appId;
    }
    return DEFAULT_RPC_APPLICATION_ID;
}

function inferRpcAppIdFromActivity(name, details = '', state = '') {
    const blob = `${name || ''} ${details || ''} ${state || ''}`.trim();
    return inferRpcAppIdFromName(blob);
}

function resolveRpcPreviewImage(rawValue, applicationId = '') {
    const value = String(rawValue || '').trim();
    if (!value) return '';

    if (value.startsWith('http://') || value.startsWith('https://')) return value;

    const appId = String(applicationId || '').trim();

    // Common Discord RPC image key format (e.g. "large", "cover_art")
    // requires app id to resolve to app-assets CDN URL.
    if (!value.includes('/') && appId) {
        return `https://cdn.discordapp.com/app-assets/${appId}/${encodeURIComponent(value)}.png?size=256`;
    }

    const toCdnPath = (path) => {
        const clean = String(path || '').replace(/^\/+/, '');
        if (!clean) return '';
        if (clean.startsWith('attachments/')) return `https://media.discordapp.net/${clean}`;
        if (clean.startsWith('external/')) return `https://media.discordapp.net/${clean}`;
        if (clean.startsWith('app-assets/')) return `https://cdn.discordapp.com/${clean}`;
        return '';
    };

    if (value.startsWith('mp:')) {
        return toCdnPath(value.slice(3));
    }
    return toCdnPath(value);
}

function getRpcTypeConfig(type = document.getElementById('rpcType')?.value) {
    return RPC_TYPE_CONFIG[String(type)] || RPC_TYPE_CONFIG['0'];
}

function syncRpcTypePicker() {
    const picker = document.getElementById('rpcTypePicker');
    const value = String(document.getElementById('rpcType')?.value || '0');
    if (!picker) return;
    const options = [...picker.querySelectorAll('[data-rpc-type]')];
    const selected = options.find(option => option.dataset.rpcType === value) || options[0];
    if (!selected) return;
    const label = selected.querySelector('strong')?.textContent || 'Playing';
    const description = selected.querySelector('small')?.textContent || '';
    setText('rpcTypeLabel', label);
    setText('rpcTypeDescription', description);
    options.forEach(option => {
        const isSelected = option === selected;
        option.classList.toggle('is-selected', isSelected);
        option.setAttribute('aria-selected', String(isSelected));
    });
}

function setRpcTypeMenuOpen(open, focusSelection = false) {
    const menu = document.getElementById('rpcTypeMenu');
    const trigger = document.getElementById('rpcTypeTrigger');
    if (!menu || !trigger) return;
    menu.hidden = !open;
    trigger.setAttribute('aria-expanded', String(open));
    if (open && focusSelection) {
        const selected = menu.querySelector('[aria-selected="true"]');
        (selected || menu.querySelector('[role="option"]'))?.focus();
    }
}

function toggleRpcTypeMenu() {
    const menu = document.getElementById('rpcTypeMenu');
    setRpcTypeMenuOpen(Boolean(menu?.hidden), Boolean(menu?.hidden));
}

function selectRpcType(value) {
    setRpcTypeMenuOpen(false);
    if (value === 'custom_status') {
        setRpcTab('status');
        document.getElementById('rpcTabStatus')?.focus();
        return;
    }
    const input = document.getElementById('rpcType');
    if (input) input.value = value;
    syncRpcTypePicker();
    syncRpcStreamingControls();
    updateRpcPreview();
    document.getElementById('rpcTypeTrigger')?.focus();
}

document.getElementById('rpcTypeTrigger')?.addEventListener('keydown', event => {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
    event.preventDefault();
    setRpcTypeMenuOpen(true, true);
});

document.getElementById('rpcTypeMenu')?.addEventListener('keydown', event => {
    const options = [...event.currentTarget.querySelectorAll('[role="option"]')];
    const currentIndex = options.indexOf(document.activeElement);
    let nextIndex = currentIndex;
    if (event.key === 'ArrowDown') nextIndex = Math.min(options.length - 1, currentIndex + 1);
    else if (event.key === 'ArrowUp') nextIndex = Math.max(0, currentIndex - 1);
    else if (event.key === 'Home') nextIndex = 0;
    else if (event.key === 'End') nextIndex = options.length - 1;
    else if (event.key === 'Escape') {
        event.preventDefault();
        setRpcTypeMenuOpen(false);
        document.getElementById('rpcTypeTrigger')?.focus();
        return;
    } else return;
    event.preventDefault();
    options[nextIndex]?.focus();
});

document.addEventListener('click', event => {
    const picker = document.getElementById('rpcTypePicker');
    if (picker && !picker.contains(event.target)) setRpcTypeMenuOpen(false);
});

function getRpcTypeForActivity(activity) {
    if (Number(activity?.type) === 4) return 'custom_status';
    const appId = String(activity?.application_id || '');
    const provider = Object.entries(RPC_TYPE_CONFIG).find(([key, config]) =>
        config.name && config.applicationId === appId && String(key) === key
    );
    return provider ? provider[0] : String(activity?.type ?? '0');
}

function getEffectiveRpcAppId() {
    const name = (document.getElementById('rpcNameInput')?.value || '').trim();
    const details = (document.getElementById('rpcDetailsInput')?.value || '').trim();
    const state = (document.getElementById('rpcStateInput')?.value || '').trim();
    const config = getRpcTypeConfig();
    if (config.customStatus) return '';
    return config.name ? config.applicationId : inferRpcAppIdFromActivity(name, details, state);
}

function syncRpcStreamingControls() {
    const typeVal = String(document.getElementById('rpcType')?.value || '0');
    const row = document.getElementById('rpcStreamUrlRow');
    const typeConfig = getRpcTypeConfig(typeVal);
    const spoofType = document.getElementById('rpcSpoofType')?.value || 'none';
    const spoofRequested = spoofType === 'streaming' && !typeConfig.customStatus && typeVal !== '1';
    const spoofSelect = document.getElementById('rpcSpoofType');
    if (spoofSelect) spoofSelect.disabled = typeConfig.customStatus || typeVal === '1';
    if (row) row.style.display = typeVal === '1' || spoofRequested ? '' : 'none';
}

function getRpcTimestamps(now = Date.now()) {
    const elapsedRaw = document.getElementById('rpcElapsedMinutes')?.value || '0';
    const totalRaw = document.getElementById('rpcTotalMinutes')?.value || '';
    const elapsed = Number(elapsedRaw);
    const total = totalRaw === '' ? null : Number(totalRaw);
    if (!Number.isFinite(elapsed) || elapsed < 0 || (total !== null && (!Number.isFinite(total) || total <= 0))) return null;
    const start = now - elapsed * 60000;
    return { start, ...(total === null ? {} : { end: start + total * 60000 }) };
}

function renderRpcTimeline(timestamps) {
    const progressWrap = document.getElementById('rpcDiscordProgressWrap');
    const progressBar = document.getElementById('rpcPreviewProgress');
    const start = Number(timestamps?.start);
    const end = Number(timestamps?.end);
    if (!Number.isFinite(start)) {
        if (progressWrap) progressWrap.style.display = 'none';
        if (progressBar) progressBar.style.width = '0%';
        setText('rpcDiscordTime', '');
        return;
    }

    const now = Date.now();
    const elapsedSeconds = Math.max(0, (now - start) / 1000);
    const formatTime = seconds => {
        const minutes = Math.floor(seconds / 60);
        return `${minutes}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
    };
    if (Number.isFinite(end) && end > start) {
        const totalSeconds = (end - start) / 1000;
        const percent = Math.max(0, Math.min(100, (elapsedSeconds / totalSeconds) * 100));
        if (progressWrap) progressWrap.style.display = '';
        if (progressBar) progressBar.style.width = `${percent}%`;
        setText('rpcDiscordProgressStart', formatTime(elapsedSeconds));
        setText('rpcDiscordProgressEnd', formatTime(totalSeconds));
        setText('rpcDiscordTime', '');
    } else {
        if (progressWrap) progressWrap.style.display = 'none';
        if (progressBar) progressBar.style.width = '0%';
        setText('rpcDiscordTime', `${formatTime(elapsedSeconds)} elapsed`);
    }
}

function readRpcDraftFromInputs() {
    const val = id => (document.getElementById(id)?.value || '').trim();
    return {
        type: String(document.getElementById('rpcType')?.value || '0'),
        name: val('rpcNameInput'),
        details: val('rpcDetailsInput'),
        state: val('rpcStateInput'),
        elapsedMinutes: val('rpcElapsedMinutes'),
        totalMinutes: val('rpcTotalMinutes'),
        streamUrl: val('rpcStreamUrlInput'),
        largeImage: val('rpcLargeImageInput'),
        largeImageText: val('rpcLargeImageTextInput'),
        smallImage: val('rpcSmallImageInput'),
        smallImageText: val('rpcSmallImageTextInput'),
        button1Label: val('rpcButton1Label'),
        button1Url: val('rpcButton1Url'),
        button2Label: val('rpcButton2Label'),
        button2Url: val('rpcButton2Url'),
        spoofType: val('rpcSpoofType') || 'none',
    };
}

function saveRpcDraft() {
    try {
        localStorage.setItem(RPC_DRAFT_STORAGE_KEY, JSON.stringify(readRpcDraftFromInputs()));
    } catch (_) {}
}

function applyRpcDraftToInputs(draft) {
    if (!draft || typeof draft !== 'object') return false;
    const setVal = (id, v) => {
        const el = document.getElementById(id);
        if (el) el.value = v != null ? String(v) : '';
    };
    setVal('rpcType', draft.type || '0');
    setVal('rpcNameInput', draft.name || '');
    setVal('rpcDetailsInput', draft.details || '');
    setVal('rpcStateInput', draft.state || '');
    setVal('rpcElapsedMinutes', draft.elapsedMinutes ?? '0');
    setVal('rpcTotalMinutes', draft.totalMinutes || '');
    setVal('rpcStreamUrlInput', draft.streamUrl || '');
    setVal('rpcLargeImageInput', draft.largeImage || '');
    setVal('rpcLargeImageTextInput', draft.largeImageText || '');
    setVal('rpcSmallImageInput', draft.smallImage || '');
    setVal('rpcSmallImageTextInput', draft.smallImageText || '');
    setVal('rpcButton1Label', draft.button1Label || '');
    setVal('rpcButton1Url', draft.button1Url || '');
    setVal('rpcButton2Label', draft.button2Label || '');
    setVal('rpcButton2Url', draft.button2Url || '');
    setVal('rpcSpoofType', draft.spoofType || (draft.spoof ? 'streaming' : 'none'));
    syncRpcTypePicker();
    syncRpcStreamingControls();
    syncRpcButtonControls();
    return true;
}

function restoreRpcDraft() {
    try {
        const raw = localStorage.getItem(RPC_DRAFT_STORAGE_KEY);
        if (!raw) return false;
        const draft = JSON.parse(raw);
        return applyRpcDraftToInputs(draft);
    } catch (_) {
        return false;
    }
}

async function loadRpc() {
    loadRpcProfiles();
    const res = await fetchJSON('/api/rpc');
    if (!res) return;
    const activities = Array.isArray(res.activities)
        ? res.activities.filter(activity => activity && typeof activity === 'object')
        : (res.activity && typeof res.activity === 'object' ? [res.activity] : []);
    _rpcActiveActivities = activities;
    const act = activities.find(activity => Number(activity.type) !== 4) || {};
    const customStatus = activities.find(activity => Number(activity.type) === 4) || null;
    const active = activities.length > 0;
    const assets = act.assets || {};

    // Active badge
    const badge = document.getElementById('rpcActiveBadge');
    if (badge) {
        badge.textContent = active ? 'Active' : 'Inactive';
        badge.className   = 'badge ' + (active ? 'badge-ok' : 'badge-off');
    }

    // Populate bot identity in card from cached bot data (if overview was loaded)
    const botUsername  = document.getElementById('rpcDiscordUsername');
    const botAvatarEl  = document.getElementById('rpcDiscordAvatar');
    const botStatusDot = document.getElementById('rpcDiscordStatusDot');
    let cachedBot = window._botDataCache || {};
    if (!cachedBot.user_id) {
        const botResponse = await fetchJSON('/api/bot');
        cachedBot = botResponse && botResponse.data ? botResponse.data : cachedBot;
        window._botDataCache = cachedBot;
    }
    if (botUsername)  botUsername.textContent          = cachedBot.username  || 'Loading…';
    setText('rpcClientName', cachedBot.username || '—');
    setText('rpcClientId', cachedBot.user_id || '—');
    setText('rpcClientState', cachedBot.connected ? 'Client online' : 'Client offline');
    const rpcClientStateDot = document.getElementById('rpcClientStateDot');
    if (rpcClientStateDot) rpcClientStateDot.classList.toggle('is-online', !!cachedBot.connected);
    if (botAvatarEl) {
        const topbarSrc = document.getElementById('topbarAvatar')?.src || '';
        const rpcAvatar = String(cachedBot.avatar_url || topbarSrc || '').trim();
        setAvatarImage(botAvatarEl, rpcAvatar, cachedBot.user_id, { allowFallback: true });
    }
    if (botStatusDot) {
        botStatusDot.className = 'discord-user-dot';
        const s = cachedBot.status || 'online';
        if (s !== 'online') botStatusDot.classList.add(s);
    }

    // Custom Status stays independent from the activity editor.
    const customStatusText = customStatus?.state || '';
    const customStatusEmoji = customStatus?.emoji?.name || '';
    const setStatusInput = (id, value) => {
        const input = document.getElementById(id);
        if (input) input.value = value;
    };
    setStatusInput('rpcCustomStatusTextInput', customStatusText);
    setStatusInput('rpcCustomStatusEmojiInput', customStatusEmoji);
    setText('rpcDiscordCustomStatus', [customStatusEmoji, customStatusText].filter(Boolean).join(' '));
    const statusBadge = document.getElementById('rpcCustomStatusBadge');
    if (statusBadge) {
        statusBadge.textContent = customStatus ? 'Active' : 'Off';
        statusBadge.className = `badge ${customStatus ? 'badge-ok' : 'badge-off'}`;
    }

    // Activity type header
    const headerEl = document.querySelector('.discord-activity-header');
    if (headerEl) headerEl.textContent = RPC_ACTIVITY_HEADERS[act.type ?? 0] || 'Playing a game';
    const activityPreview = document.getElementById('rpcDiscordActivity');
    if (activityPreview) activityPreview.style.display = act.name ? '' : 'none';

    // Activity text
    setText('rpcPreviewName',    active ? (act.name || '') : '');
    setText('rpcPreviewDetails', active ? (act.details || '') : '');
    setText('rpcPreviewState',   active ? (act.state   || '') : '');

    // Large art
    const artEl = document.getElementById('rpcDiscordArt');
    if (artEl) {
        const li = resolveRpcPreviewImage(assets.large_image || '', act.application_id || getEffectiveRpcAppId());
        if (active && li) {
            artEl.style.backgroundImage  = `url("${String(li).replace(/"/g, '%22')}")`;
            artEl.style.backgroundSize   = 'cover';
            artEl.style.backgroundColor = 'transparent';
        } else {
            artEl.style.backgroundImage  = 'none';
            artEl.style.backgroundColor = 'var(--a1)';
        }
    }

    // Small art
    const smallArtEl = document.getElementById('rpcDiscordSmallArt');
    if (smallArtEl) {
        const si = resolveRpcPreviewImage(assets.small_image || '', act.application_id || getEffectiveRpcAppId());
        if (active && si) {
            smallArtEl.classList.add('visible');
            smallArtEl.style.backgroundImage = `url("${String(si).replace(/"/g, '%22')}")`;
            smallArtEl.style.backgroundSize  = 'cover';
            smallArtEl.style.backgroundColor = 'transparent';
        } else {
            smallArtEl.classList.remove('visible');
            smallArtEl.style.backgroundImage = 'none';
            smallArtEl.style.backgroundColor = 'var(--a1)';
        }
    }

    // Buttons
    const btnsEl = document.getElementById('rpcDiscordButtons');
    if (btnsEl) {
        const labels = Array.isArray(act.buttons) ? act.buttons.filter(Boolean) : [];
        btnsEl.innerHTML    = labels.map(l => `<div class="discord-btn">${esc(l)}</div>`).join('');
        btnsEl.style.display = labels.length ? '' : 'none';
    }

    renderRpcTimeline(act.timestamps);

    // No-activity overlay
    const noAct = document.getElementById('rpcNoActivity');
    if (noAct) {
        if (active && (act.name || customStatus)) noAct.classList.remove('visible');
        else                    noAct.classList.add('visible');
    }

    // Meta strip
    setText('rpcPreviewMode',    res.mode   || 'none');
    setText('rpcPreviewTypeId',  act.type != null ? act.type : '—');
    setText('rpcPreviewAppId',   act.application_id || '—');
    setText('rpcPreviewButtons', Array.isArray(act.buttons) ? act.buttons.length : 0);

    if (!_rpcDraftRestored) {
        _rpcDraftRestored = true;
        const restored = restoreRpcDraft();
        if (!restored) {
            const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.value = v || ''; };
            setVal('rpcType',            getRpcTypeForActivity(act));
            setVal('rpcNameInput',       act.name    || '');
            setVal('rpcDetailsInput',    act.details || '');
            setVal('rpcStateInput',      act.state   || '');
            const timestamps = act.timestamps || {};
            const timestampStart = Number(timestamps.start);
            const timestampEnd = Number(timestamps.end);
            if (Number.isFinite(timestampStart)) {
                setVal('rpcElapsedMinutes', Math.floor(Math.max(0, Date.now() - timestampStart) / 60000));
                setVal('rpcTotalMinutes', Number.isFinite(timestampEnd) && timestampEnd > timestampStart
                    ? Math.round((timestampEnd - timestampStart) / 60000)
                    : '');
            }
            setVal('rpcStreamUrlInput',  act.url     || '');
            setVal('rpcLargeImageInput', assets.large_image || '');
            setVal('rpcLargeImageTextInput', assets.large_text || '');
            setVal('rpcSmallImageInput', assets.small_image || '');
            setVal('rpcSmallImageTextInput', assets.small_text || '');
            const btns    = Array.isArray(act.buttons) ? act.buttons : [];
            const btnUrls = act.metadata && Array.isArray(act.metadata.button_urls) ? act.metadata.button_urls : [];
            setVal('rpcButton1Label', btns[0]    || '');
            setVal('rpcButton1Url',   btnUrls[0] || '');
            setVal('rpcButton2Label', btns[1]    || '');
            setVal('rpcButton2Url',   btnUrls[1] || '');

            setVal('rpcSpoofType', 'none');
            syncRpcStreamingControls();
            syncRpcButtonControls();
            saveRpcDraft();
        }
    }
    updateRpcPreview();
}

// ── RPC live Discord-card preview ────────────────────────────────────────────
const RPC_ACTIVITY_HEADERS = {
    0: 'Playing a game',
    1: 'Streaming',
    2: 'Listening to',
    3: 'Watching',
    4: 'Custom Status',
    5: 'Competing in',
};

function updateRpcPreview() {
    syncRpcTypePicker();
    syncRpcStreamingControls();

    const typeKey = String(document.getElementById('rpcType')?.value || '0');
    const typeConfig = getRpcTypeConfig(typeKey);
    const typeVal = typeConfig.activityType;
    const spoof = (document.getElementById('rpcSpoofType')?.value || 'none') === 'streaming'
        && !typeConfig.customStatus && typeVal !== 1;
    const previewType = spoof ? 1 : typeVal;
    const name      = (document.getElementById('rpcNameInput')?.value    || '').trim();
    const details   = (document.getElementById('rpcDetailsInput')?.value || '').trim();
    const state     = (document.getElementById('rpcStateInput')?.value   || '').trim();
    const streamUrl = (document.getElementById('rpcStreamUrlInput')?.value || '').trim();
    const largeImg  = (document.getElementById('rpcLargeImageInput')?.value  || '').trim();
    const smallImg  = (document.getElementById('rpcSmallImageInput')?.value  || '').trim();
    const btn1Label = (document.getElementById('rpcButton1Label')?.value || '').trim();
    const btn2Label = (document.getElementById('rpcButton2Label')?.value || '').trim();
    const timestamps = getRpcTimestamps();

    // Activity header text
    const headerEl = document.querySelector('.discord-activity-header');
    if (headerEl) headerEl.textContent = spoof ? 'Streaming' : typeConfig.label || RPC_ACTIVITY_HEADERS[typeVal] || 'Playing a game';

    // Text fields in card
    // Use spoofed display name if provided, else real name
    setText('rpcPreviewName', typeConfig.customStatus ? 'Custom Status' : name || typeConfig.name || '—');
    setText('rpcPreviewDetails', details || '');
    setText('rpcPreviewState',   typeVal === 1 ? (streamUrl || state || '') : (state || ''));
    const customStatusText = (document.getElementById('rpcCustomStatusTextInput')?.value || '').trim();
    const customStatusEmoji = (document.getElementById('rpcCustomStatusEmojiInput')?.value || '').trim();
    setText('rpcDiscordCustomStatus', [customStatusEmoji, customStatusText].filter(Boolean).join(' '));
    renderRpcTimeline(typeConfig.customStatus ? null : timestamps);
    const activityEl = document.getElementById('rpcDiscordActivity');
    if (activityEl) activityEl.style.display = typeConfig.customStatus ? 'none' : '';
    const nameLabel = document.getElementById('rpcNameLabel');
    if (nameLabel) nameLabel.textContent = typeConfig.customStatus ? 'Status text' : 'Name';
    const nameSub = document.getElementById('rpcNameSub');
    if (nameSub) nameSub.firstChild.textContent = typeConfig.customStatus ? 'Custom status text ' : 'Activity name ';
    const nameInput = document.getElementById('rpcNameInput');
    if (nameInput) nameInput.placeholder = typeConfig.customStatus ? 'e.g. Away for lunch' : 'e.g. Spotify, Valorant';
    const spoofBadge = document.getElementById('rpcPreviewSpoofBadge');
    if (spoofBadge) spoofBadge.hidden = !spoof;

    // Mini app id display
    const miniAppId = document.getElementById('miniAppId');
    if (miniAppId) {
        const appId = getEffectiveRpcAppId();
        miniAppId.textContent = !typeConfig.customStatus && appId && appId !== DEFAULT_RPC_APPLICATION_ID ? `App ID: ${appId}` : '';
    }

    // Large image
    const artEl = document.getElementById('rpcDiscordArt');
    if (artEl) {
        const appIdForImage = getEffectiveRpcAppId();
        const largePreview = resolveRpcPreviewImage(largeImg, appIdForImage);
        artEl.title = (document.getElementById('rpcLargeImageTextInput')?.value || '').trim() || 'Edit large image';
        if (largePreview) {
            artEl.style.backgroundImage = `url("${String(largePreview).replace(/"/g, '%22')}")`;
            artEl.style.backgroundSize  = 'cover';
            artEl.style.backgroundColor = 'transparent';
        } else {
            artEl.style.backgroundImage = 'none';
            artEl.style.backgroundColor = 'var(--a1)';
        }
    }

    // Small art visibility
    const smallArtEl = document.getElementById('rpcDiscordSmallArt');
    if (smallArtEl) {
        const appIdForImage = getEffectiveRpcAppId();
        const smallPreview = resolveRpcPreviewImage(smallImg, appIdForImage);
        smallArtEl.title = (document.getElementById('rpcSmallImageTextInput')?.value || '').trim() || 'Edit small image';
        if (smallPreview) {
            smallArtEl.classList.add('visible');
            smallArtEl.style.backgroundImage = `url("${String(smallPreview).replace(/"/g, '%22')}")`;
            smallArtEl.style.backgroundSize  = 'cover';
            smallArtEl.style.backgroundColor = 'transparent';
        } else {
            smallArtEl.classList.remove('visible');
            smallArtEl.style.backgroundImage = 'none';
            smallArtEl.style.backgroundColor = 'var(--a1)';
        }
    }

    // Buttons
    const btnsEl = document.getElementById('rpcDiscordButtons');
    if (btnsEl) {
        const entries = [
            { label: btn1Label, url: (document.getElementById('rpcButton1Url')?.value || '').trim() },
            { label: btn2Label, url: (document.getElementById('rpcButton2Url')?.value || '').trim() },
        ].filter(entry => entry.label);
        btnsEl.replaceChildren();
        entries.forEach(entry => {
            const button = document.createElement('div');
            button.className = 'discord-btn';
            button.textContent = entry.label;
            if (entry.url) button.title = entry.url;
            btnsEl.append(button);
        });
        btnsEl.style.display = entries.length ? '' : 'none';
    }
    syncRpcButtonControls();

    // Toggle no-activity overlay
    const noAct = document.getElementById('rpcNoActivity');
    if (noAct) {
        if (name || typeConfig.customStatus || customStatusText) noAct.classList.remove('visible');
        else      noAct.classList.add('visible');
    }

    // Update meta strip
    setText('rpcPreviewTypeId', previewType);
    setText('rpcPreviewAppId', typeConfig.customStatus ? '—' : getEffectiveRpcAppId());
    setText('rpcPreviewButtons', [btn1Label, btn2Label].filter(Boolean).length);
    saveRpcDraft();
}

document.getElementById('rpcPreview')?.addEventListener('click', event => {
    const target = event.target.closest('[data-rpc-focus]');
    if (!target) return;
    document.getElementById(target.dataset.rpcFocus)?.focus();
});

document.getElementById('rpcPreview')?.addEventListener('keydown', event => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    const target = event.target.closest('[data-rpc-focus]');
    if (!target) return;
    event.preventDefault();
    document.getElementById(target.dataset.rpcFocus)?.focus();
});

function showRpcMsg(msg, ok) {
    const el = document.getElementById('rpcMsg');
    if (!el) return;
    el.textContent = msg;
    el.className = 'settings-msg ' + (ok ? 'ok' : 'err');
    setTimeout(() => { el.textContent = ''; el.className = 'settings-msg'; }, 3000);
}

function setCustomStatusMessage(message, ok) {
    const element = document.getElementById('rpcCustomStatusMsg');
    if (!element) return;
    element.textContent = message;
    element.className = `rpc-profile-feedback ${ok ? 'success' : 'error'}`;
}

async function applyCustomStatus() {
    const text = (document.getElementById('rpcCustomStatusTextInput')?.value || '').trim();
    const emoji = (document.getElementById('rpcCustomStatusEmojiInput')?.value || '').trim();
    if (!text) {
        setCustomStatusMessage('Status text is required.', false);
        return;
    }
    const otherActivities = _rpcActiveActivities.filter(activity => Number(activity.type) !== 4);
    if (otherActivities.length >= 5) {
        setCustomStatusMessage('Presence already has the maximum of five activities.', false);
        return;
    }
    const status = { type: 4, name: 'Custom Status', state: text };
    if (emoji) status.emoji = { name: emoji, id: null, animated: false };
    const response = await postJSON('/api/rpc', { action: 'set', activity: [...otherActivities, status] });
    if (response?.ok) {
        setCustomStatusMessage('Custom Status applied.', true);
        trackDashboardAction('rpc_status_set', 'Set Custom Status');
        loadRpc();
    } else {
        setCustomStatusMessage(response?.error || 'Custom Status could not be applied.', false);
    }
}

async function stopCustomStatus() {
    const remainingActivities = _rpcActiveActivities.filter(activity => Number(activity.type) !== 4);
    const response = remainingActivities.length
        ? await postJSON('/api/rpc', { action: 'set', activity: remainingActivities })
        : await postJSON('/api/rpc', { action: 'stop' });
    if (response?.ok) {
        document.getElementById('rpcCustomStatusTextInput').value = '';
        document.getElementById('rpcCustomStatusEmojiInput').value = '';
        setCustomStatusMessage('Custom Status stopped.', true);
        trackDashboardAction('rpc_status_clear', 'Stopped Custom Status');
        loadRpc();
    } else {
        setCustomStatusMessage(response?.error || 'Custom Status could not be stopped.', false);
    }
}

let _rpcSecondButtonOpen = false;

function syncRpcButtonControls() {
    const row = document.getElementById('rpcButton2Row');
    const addButton = document.getElementById('rpcAddButton');
    if (!row || !addButton) return;
    const hasSecondButton = Boolean(
        document.getElementById('rpcButton2Label')?.value
        || document.getElementById('rpcButton2Url')?.value
    );
    row.hidden = !_rpcSecondButtonOpen && !hasSecondButton;
    addButton.hidden = !row.hidden;
}

function addRpcButton() {
    _rpcSecondButtonOpen = true;
    syncRpcButtonControls();
    document.getElementById('rpcButton2Label')?.focus();
}

async function applyRpc() {
    const typeKey = String(document.getElementById('rpcType')?.value || '0');
    const typeConfig = getRpcTypeConfig(typeKey);
    const type = typeConfig.activityType;
    const name = document.getElementById('rpcNameInput').value.trim() || typeConfig.name || '';
    const details = document.getElementById('rpcDetailsInput').value.trim();
    const state = document.getElementById('rpcStateInput').value.trim();
    const streamUrl = (document.getElementById('rpcStreamUrlInput')?.value || '').trim();
    const largeImage = (document.getElementById('rpcLargeImageInput')?.value || '').trim();
    const smallImage = (document.getElementById('rpcSmallImageInput')?.value || '').trim();
    const button1Label = (document.getElementById('rpcButton1Label')?.value || '').trim();
    const button1Url = (document.getElementById('rpcButton1Url')?.value || '').trim();
    const button2Label = (document.getElementById('rpcButton2Label')?.value || '').trim();
    const button2Url = (document.getElementById('rpcButton2Url')?.value || '').trim();
    const appId = getEffectiveRpcAppId();
    const spoof = (document.getElementById('rpcSpoofType')?.value || 'none') === 'streaming'
        && !typeConfig.customStatus && type !== 1;
    const timestamps = getRpcTimestamps();
    if (!name) { showRpcMsg('Name is required.', false); return; }
    if (!timestamps) { showRpcMsg('Elapsed must be zero or more minutes and total must be greater than zero.', false); return; }

    if (type === 1 || spoof) {
        const streamHostOk = /^https?:\/\/(www\.)?(twitch\.(tv|com)|youtube\.com|youtu\.be)\//i.test(streamUrl);
        if (!streamHostOk) {
            showRpcMsg('Streaming type requires a valid Twitch or YouTube URL.', false);
            return;
        }
    }

    const activity = { type, name, application_id: appId, timestamps };
    if (details) activity.details = details;
    if (state) activity.state = state;
    if (type === 1 && streamUrl) activity.url = streamUrl;
    
    // Build assets object properly for Discord API
    const assets = {};
    if (largeImage) assets.large_image = largeImage;
    const largeImageText = (document.getElementById('rpcLargeImageTextInput')?.value || '').trim();
    if (largeImageText) assets.large_text = largeImageText;
    if (smallImage) assets.small_image = smallImage;
    const smallImageText = (document.getElementById('rpcSmallImageTextInput')?.value || '').trim();
    if (smallImageText) assets.small_text = smallImageText;
    if (Object.keys(assets).length > 0) activity.assets = assets;
    
    // Build buttons properly - Discord API expects buttons array of labels and metadata.button_urls array
    const buttonLabels = [];
    const buttonUrls = [];
    if (button1Label && button1Url) {
        buttonLabels.push(button1Label);
        buttonUrls.push(button1Url);
    }
    if (button2Label && button2Url) {
        buttonLabels.push(button2Label);
        buttonUrls.push(button2Url);
    }
    if (buttonLabels.length > 0) {
        activity.buttons = buttonLabels;
        activity.metadata = { button_urls: buttonUrls };
    }

    saveRpcDraft();
    
    const retainedStatus = _rpcActiveActivities.filter(item => Number(item.type) === 4);
    const activities = [activity, ...retainedStatus].slice(0, 5);
    const res = await postJSON('/api/rpc', { action: 'set', activity: activities, spoof, stream_url: streamUrl });
    if (res && res.ok) {
        showRpcMsg('RPC set.', true);
        trackDashboardAction('rpc_set', `Set RPC ${name}`);
        loadRpc();
    } else {
        showRpcMsg((res && res.error) || 'Failed to set RPC.', false);
    }
}

async function clearRpc() {
    const customStatus = _rpcActiveActivities.find(activity => Number(activity.type) === 4);
    const res = customStatus
        ? await postJSON('/api/rpc', { action: 'set', activity: [customStatus] })
        : await postJSON('/api/rpc', { action: 'stop' });
    if (res && res.ok) {
        showRpcMsg('RPC cleared.', true);
        trackDashboardAction('rpc_clear', 'Stopped RPC activity');
        loadRpc();
    } else {
        showRpcMsg('Failed to stop RPC.', false);
    }
}

async function loadSpotifyLyrics() {
    const res = await fetchJSON('/api/spotify-lyrics');
    if (!res || !res.ok) return;
    const enabled = Boolean(res.enabled || res.running);
    const badge = document.getElementById('spotifyLyricsBadge');
    if (badge) {
        badge.textContent = enabled ? (res.phase === 'syncing' ? 'Syncing' : 'On') : 'Off';
        badge.className = 'badge ' + (enabled ? 'badge-ok' : 'badge-off');
    }
    const track = [res.title, res.artist].filter(Boolean).join(' - ');
    setText('spotifyLyricsTrack', track || (res.available === false ? 'Unavailable for this client' : 'No active track'));
    setText('spotifyLyricsLine', res.current_line || res.error || (res.available === false
        ? 'Spotify lyrics controls are unavailable'
        : 'Waiting for Spotify playback'));
}

async function setSpotifyLyrics(action) {
    const res = await postJSON('/api/spotify-lyrics', { action });
    const message = document.getElementById('spotifyLyricsMsg');
    if (message) {
        message.textContent = res && res.ok
            ? (action === 'start' ? 'Spotify lyrics sync started.' : 'Spotify lyrics sync stopping.')
            : ((res && res.error) || 'Spotify lyrics action failed.');
        message.className = `rpc-profile-feedback ${res && res.ok ? 'success' : 'error'}`;
    }
    if (res && res.ok) {
        trackDashboardAction('spotify_lyrics', `${action === 'start' ? 'Started' : 'Stopped'} Spotify lyrics sync`);
    }
    await loadSpotifyLyrics();
}

function showRpcProfileMsg(message, state = '') {
    for (const id of ['rpcProfileMsg', 'rpcRotationMsg']) {
        const el = document.getElementById(id);
        if (!el) continue;
        el.textContent = message;
        el.className = `rpc-profile-feedback${state ? ` ${state}` : ''}`;
    }
}

const RPC_DASHBOARD_TABS = ['editor', 'status', 'presets', 'stack', 'rotation', 'lyrics'];
const RPC_STATIC_PREVIEW = document.querySelector('meta[name="csrf-token"]')?.content === '__CSRF_TOKEN__';
const RPC_PREVIEW_PRESETS_KEY = 'aria.rpcPreviewPresets';
const RPC_PREVIEW_STACK_KEY = 'aria.rpcPreviewStack';
const RPC_PREVIEW_ROTATION_KEY = 'aria.rpcPreviewRotation';
const RPC_PAGE_COPY = {
    editor: ['Rich Presence', 'Build an activity, preview it as it will appear, then apply it to your connected account.'],
    status: ['Custom Status', 'Set a status text independently from your activity.'],
    presets: ['RPC Presets', 'Switch between saved activity configurations instantly.'],
    stack: ['RPC Stack', 'Queue activities to play one after another, each for a set duration.'],
    rotation: ['RPC Rotation', 'Cycle through saved activities automatically in your chosen order.'],
    lyrics: ['Spotify Lyrics', 'Sync your presence with the currently playing Spotify track.'],
};

function setRpcTab(tabName, moveFocus = false) {
    if (!RPC_DASHBOARD_TABS.includes(tabName)) return;
    for (const name of RPC_DASHBOARD_TABS) {
        const suffix = name[0].toUpperCase() + name.slice(1);
        const tab = document.getElementById(`rpcTab${suffix}`);
        const panel = document.getElementById(`rpcPanel${suffix}`);
        const selected = name === tabName;
        if (tab) {
            tab.classList.toggle('is-active', selected);
            tab.setAttribute('aria-selected', String(selected));
            tab.tabIndex = selected ? 0 : -1;
        }
        if (panel) panel.hidden = !selected;
    }
    setText('rpcPageTitle', RPC_PAGE_COPY[tabName][0]);
    setText('rpcPageSubtitle', RPC_PAGE_COPY[tabName][1]);
    document.querySelectorAll('[data-rpc-page-action]').forEach(button => {
        button.hidden = button.dataset.rpcPageAction !== tabName;
    });
    try { localStorage.setItem('aria.rpcDashboardTab', tabName); } catch (_) {}
    if (moveFocus) {
        const suffix = tabName[0].toUpperCase() + tabName.slice(1);
        document.getElementById(`rpcTab${suffix}`)?.focus();
    }
}

function readRpcPreviewStore(key, fallback) {
    try {
        const value = JSON.parse(localStorage.getItem(key) || 'null');
        return value == null ? fallback : value;
    } catch (_) {
        return fallback;
    }
}

function writeRpcPreviewStore(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); return true; }
    catch (_) { return false; }
}

function buildRpcPresetActivity() {
    const value = id => (document.getElementById(id)?.value || '').trim();
    const typeKey = value('rpcPresetType') || 'custom';
    const typeConfig = getRpcTypeConfig(typeKey);
    const name = value('rpcPresetActivityName') || typeConfig.name || '';
    const statusEmoji = value('rpcPresetEmoji');
    const elapsed = Number(value('rpcPresetElapsed') || 0);
    const totalRaw = value('rpcPresetTotal');
    const total = totalRaw ? Number(totalRaw) : null;
    if (!name) return { error: typeConfig.customStatus ? 'Status text is required.' : 'Activity name is required.' };
    if (!typeConfig.customStatus && (!Number.isFinite(elapsed) || elapsed < 0 || (total !== null && (!Number.isFinite(total) || total <= 0)))) {
        return { error: 'Elapsed must be zero or more and total must be greater than zero.' };
    }
    const activity = typeConfig.customStatus
        ? { type: 4, name: 'Custom Status', state: name }
        : {
            type: typeConfig.activityType,
            name,
            application_id: typeConfig.name
                ? typeConfig.applicationId
                : inferRpcAppIdFromActivity(name, value('rpcPresetDetails'), value('rpcPresetState')),
            timestamps: { start: Date.now() - elapsed * 60000 },
        };
    if (typeConfig.customStatus && statusEmoji) activity.emoji = { name: statusEmoji, id: null, animated: false };
    if (!typeConfig.customStatus && total !== null) activity.timestamps.end = activity.timestamps.start + total * 60000;
    if (value('rpcPresetDetails')) activity.details = value('rpcPresetDetails');
    if (!typeConfig.customStatus && value('rpcPresetState')) activity.state = value('rpcPresetState');
    if (typeConfig.activityType === 1 && value('rpcPresetStreamUrl')) activity.url = value('rpcPresetStreamUrl');
    const assets = {};
    if (value('rpcPresetLargeImage')) assets.large_image = value('rpcPresetLargeImage');
    if (value('rpcPresetLargeText')) assets.large_text = value('rpcPresetLargeText');
    if (value('rpcPresetSmallImage')) assets.small_image = value('rpcPresetSmallImage');
    if (value('rpcPresetSmallText')) assets.small_text = value('rpcPresetSmallText');
    if (Object.keys(assets).length) activity.assets = assets;
    return { activity };
}

function fillRpcPresetComposer(name, activity) {
    const setVal = (id, nextValue) => {
        const input = document.getElementById(id);
        if (input) input.value = nextValue == null ? '' : String(nextValue);
    };
    const assets = activity.assets || {};
    const timestamps = activity.timestamps || {};
    const status = Number(activity.type) === 4;
    setVal('rpcPresetName', name);
    setVal('rpcPresetActivityName', status ? activity.state : activity.name);
    setVal('rpcPresetType', getRpcTypeForActivity(activity));
    setVal('rpcPresetEmoji', activity.emoji?.name || '');
    setVal('rpcPresetDetails', activity.details);
    setVal('rpcPresetState', activity.state);
    setVal('rpcPresetStreamUrl', activity.url);
    setVal('rpcPresetLargeImage', assets.large_image);
    setVal('rpcPresetLargeText', assets.large_text);
    setVal('rpcPresetSmallImage', assets.small_image);
    setVal('rpcPresetSmallText', assets.small_text);
    setVal('rpcPresetElapsed', Number.isFinite(Number(timestamps.start))
        ? Math.floor(Math.max(0, Date.now() - Number(timestamps.start)) / 60000)
        : 0);
    setVal('rpcPresetTotal', Number.isFinite(Number(timestamps.end)) && Number(timestamps.end) > Number(timestamps.start)
        ? Math.round((Number(timestamps.end) - Number(timestamps.start)) / 60000)
        : '');
}

function previewRpcPresetOnEditor(activity) {
    const assets = activity.assets || {};
    const timestamps = activity.timestamps || {};
    applyRpcDraftToInputs({
        type: getRpcTypeForActivity(activity),
        name: Number(activity.type) === 4 ? activity.state || '' : activity.name || '',
        display_name: activity.display_name || '',
        details: activity.details || '',
        state: activity.state || '',
        statusEmoji: activity.emoji?.name || '',
        elapsedMinutes: Number.isFinite(Number(timestamps.start))
            ? Math.floor(Math.max(0, Date.now() - Number(timestamps.start)) / 60000)
            : '0',
        totalMinutes: Number.isFinite(Number(timestamps.end)) && Number(timestamps.end) > Number(timestamps.start)
            ? Math.round((Number(timestamps.end) - Number(timestamps.start)) / 60000)
            : '',
        largeImage: assets.large_image || '',
        smallImage: assets.small_image || '',
        streamUrl: activity.url || '',
    });
    setRpcTab('editor');
    updateRpcPreview();
}

document.querySelector('.rpc-tabs')?.addEventListener('keydown', event => {
    const current = RPC_DASHBOARD_TABS.find(name => {
        const suffix = name[0].toUpperCase() + name.slice(1);
        return document.getElementById(`rpcTab${suffix}`) === event.target;
    });
    if (!current) return;
    const currentIndex = RPC_DASHBOARD_TABS.indexOf(current);
    let nextIndex = currentIndex;
    if (event.key === 'ArrowRight') nextIndex = (currentIndex + 1) % RPC_DASHBOARD_TABS.length;
    else if (event.key === 'ArrowLeft') nextIndex = (currentIndex + RPC_DASHBOARD_TABS.length - 1) % RPC_DASHBOARD_TABS.length;
    else if (event.key === 'Home') nextIndex = 0;
    else if (event.key === 'End') nextIndex = RPC_DASHBOARD_TABS.length - 1;
    else return;
    event.preventDefault();
    setRpcTab(RPC_DASHBOARD_TABS[nextIndex], true);
});

function renderRpcStack(stack) {
    const list = document.getElementById('rpcStackList');
    if (!list) return;
    list.replaceChildren();
    const activities = Array.isArray(stack) ? stack : [];
    setText('rpcStackCount', `${activities.length} / 5`);
    if (!activities.length) {
        const empty = document.createElement('div');
        empty.className = 'rpc-empty-state';
        empty.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 9 4.5-9 4.5-9-4.5L12 3Z"/><path d="m3 12 9 4.5 9-4.5M3 16.5 12 21l9-4.5"/></svg><strong>No entries</strong><span>Click “Add entry” to start building your stack.</span>';
        list.append(empty);
        return;
    }
    activities.forEach((activity, index) => {
        const row = document.createElement('div');
        row.className = 'rpc-stack-item';
        const number = document.createElement('span');
        number.className = 'rpc-stack-index';
        number.textContent = String(index + 1).padStart(2, '0');
        const copy = document.createElement('div');
        copy.className = 'rpc-stack-item-copy';
        const title = document.createElement('strong');
        title.textContent = activity.name || 'Activity';
        const detail = document.createElement('span');
        detail.textContent = [activity.details, activity.state].filter(Boolean).join(' · ') || 'No details';
        copy.append(title, detail);
        const remove = document.createElement('button');
        remove.className = 'rpc-stack-remove';
        remove.type = 'button';
        remove.textContent = 'Remove';
        remove.setAttribute('aria-label', `Remove ${activity.name || 'activity'} from stack`);
        remove.addEventListener('click', () => updateRpcStack('remove', index));
        row.append(number, copy, remove);
        list.append(row);
    });
}

async function loadRpcStack() {
    let data = await fetchJSON('/api/rpc/stack');
    if ((!data || !data.ok) && RPC_STATIC_PREVIEW) {
        data = { ok: true, stack: readRpcPreviewStore(RPC_PREVIEW_STACK_KEY, []) };
    }
    if (data?.ok) renderRpcStack(data.stack);
}

async function updateRpcStack(action, index, activity) {
    const payload = { action };
    if (index !== undefined) payload.index = index;
    if (activity) payload.activity = activity;
    let response = await postJSON('/api/rpc/stack', payload);
    if ((!response || !response.ok) && RPC_STATIC_PREVIEW) {
        const stack = readRpcPreviewStore(RPC_PREVIEW_STACK_KEY, []);
        if (action === 'add') {
            if (stack.length >= 5) response = { ok: false, error: 'A stack can contain up to five activities.' };
            else if (!activity) response = { ok: false, error: 'Build an activity in Editor before adding it.' };
            else { stack.push(activity); writeRpcPreviewStore(RPC_PREVIEW_STACK_KEY, stack); response = { ok: true, stack }; }
        } else if (action === 'remove') {
            stack.splice(index, 1);
            writeRpcPreviewStore(RPC_PREVIEW_STACK_KEY, stack);
            response = { ok: true, stack };
        } else if (action === 'clear') {
            writeRpcPreviewStore(RPC_PREVIEW_STACK_KEY, []);
            response = { ok: true, stack: [] };
        } else {
            response = { ok: false, error: 'Applying activities requires a connected client.' };
        }
    }
    const message = document.getElementById('rpcStackMsg');
    if (message) {
        message.textContent = response?.ok
            ? ({ add: 'Activity added to the stack.', add_current: 'Added the live activity to the stack.', apply: 'Activity stack applied.', clear: 'Activity stack cleared.', remove: 'Activity removed from the stack.' }[action] || 'Stack updated.')
            : (response?.error || 'Stack action failed.');
        message.className = `rpc-profile-feedback ${response?.ok ? 'success' : 'error'}`;
    }
    if (response?.ok) {
        renderRpcStack(response.stack);
        if (action === 'apply') loadRpc();
    }
}

function buildRpcEditorActivity() {
    const draft = readRpcDraftFromInputs();
    const typeConfig = getRpcTypeConfig(draft.type);
    const name = draft.name || typeConfig.name || '';
    if (!name) return null;
    const timestamps = typeConfig.customStatus ? null : getRpcTimestamps();
    if (!typeConfig.customStatus && !timestamps) return null;
    const spoof = draft.spoofType === 'streaming' && !typeConfig.customStatus && typeConfig.activityType !== 1;
    const activity = typeConfig.customStatus
        ? { type: 4, name: 'Custom Status', state: name }
        : { type: spoof ? 1 : typeConfig.activityType, name, application_id: getEffectiveRpcAppId(), timestamps };
    if (typeConfig.customStatus && draft.statusEmoji) activity.emoji = { name: draft.statusEmoji, id: null, animated: false };
    if (draft.display_name) activity.display_name = draft.display_name;
    if (typeConfig.platform) activity.platform = typeConfig.platform;
    if (!typeConfig.customStatus && draft.details) activity.details = draft.details;
    if (!typeConfig.customStatus && draft.state) activity.state = draft.state;
    if ((typeConfig.activityType === 1 || spoof) && draft.streamUrl) activity.url = draft.streamUrl;
    const assets = {};
    if (draft.largeImage) assets.large_image = draft.largeImage;
    if (draft.largeImageText) assets.large_text = draft.largeImageText;
    if (draft.smallImage) assets.small_image = draft.smallImage;
    if (draft.smallImageText) assets.small_text = draft.smallImageText;
    if (Object.keys(assets).length) activity.assets = assets;
    const labels = [draft.button1Label, draft.button2Label].filter(Boolean);
    const urls = [draft.button1Label ? draft.button1Url : '', draft.button2Label ? draft.button2Url : ''].filter(Boolean);
    if (labels.length) {
        activity.buttons = labels;
        activity.metadata = { button_urls: urls };
    }
    return activity;
}

function addCurrentRpcToStack() {
    const activity = buildRpcEditorActivity();
    if (!activity) {
        const message = document.getElementById('rpcStackMsg');
        if (message) {
            message.textContent = 'Build an activity in Editor first, then add it here.';
            message.className = 'rpc-profile-feedback error';
        }
        return;
    }
    updateRpcStack('add', undefined, activity);
}
function applyRpcStack() { updateRpcStack('apply'); }
function clearRpcStack() { updateRpcStack('clear'); }

let _rpcRotationOrder = [];
let _rpcRotationDirty = false;

function renderRpcRotationOrder() {
    const list = document.getElementById('rpcRotationList');
    const empty = document.getElementById('rpcRotationEmpty');
    if (!list) return;
    list.replaceChildren();
    if (empty) empty.hidden = _rpcRotationOrder.length > 0;
    _rpcRotationOrder.forEach((name, index) => {
        const row = document.createElement('div');
        row.className = 'rpc-rotation-item';
        const position = document.createElement('span');
        position.className = 'rpc-stack-index';
        position.textContent = String(index + 1).padStart(2, '0');
        const label = document.createElement('strong');
        label.textContent = name;
        const remove = document.createElement('button');
        remove.className = 'rpc-stack-remove';
        remove.type = 'button';
        remove.textContent = 'Remove';
        remove.setAttribute('aria-label', `Remove ${name} from rotation`);
        remove.addEventListener('click', () => {
            _rpcRotationOrder.splice(index, 1);
            _rpcRotationDirty = true;
            renderRpcRotationOrder();
            showRpcProfileMsg('Rotation order changed. Set order to save it.');
        });
        row.append(position, label, remove);
        list.append(row);
    });
    const startButton = document.querySelector('[data-rpc-page-action="rotation"][onclick*="controlRpcRotation"]');
    if (startButton) startButton.disabled = _rpcRotationDirty || _rpcRotationOrder.length < 2;
}

function addRpcRotationPreset() {
    const select = document.getElementById('rpcRotationPresets');
    const name = select?.value || '';
    if (!name) { showRpcProfileMsg('Choose a saved preset to add.', 'error'); select?.focus(); return; }
    if (_rpcRotationOrder.includes(name)) { showRpcProfileMsg(`${name} is already in the rotation.`, 'error'); return; }
    _rpcRotationOrder.push(name);
    _rpcRotationDirty = true;
    renderRpcRotationOrder();
    showRpcProfileMsg('Rotation entry added. Set order to save it.');
}

async function loadRpcProfiles() {
    let data = await fetchJSON('/api/rpc/profiles');
    if ((!data || !data.ok) && RPC_STATIC_PREVIEW) {
        const rotation = readRpcPreviewStore(RPC_PREVIEW_ROTATION_KEY, null);
        data = {
            ok: true,
            presets: Object.keys(readRpcPreviewStore(RPC_PREVIEW_PRESETS_KEY, {})).sort((left, right) => left.localeCompare(right)),
            rotation,
            rotation_running: false,
        };
    }
    if (!data || !data.ok) return;

    const presets = Array.isArray(data.presets) ? data.presets : [];
    const rotationNames = data.rotation?.presets || [];
    const presetSelect = document.getElementById('rpcPresetSelect');
    const rotationSelect = document.getElementById('rpcRotationPresets');
    const intervalInput = document.getElementById('rpcRotationInterval');
    const selectedPreset = presetSelect?.value || '';

    if (presetSelect) {
        presetSelect.replaceChildren();
        if (!presets.length) presetSelect.add(new Option('No presets saved', ''));
        for (const name of presets) presetSelect.add(new Option(name, name));
    }
    if (rotationSelect) {
        rotationSelect.replaceChildren(new Option('Choose saved preset', ''));
        for (const name of presets) rotationSelect.add(new Option(name, name));
    }
    _rpcRotationOrder = rotationNames.filter(name => presets.includes(name));
    _rpcRotationDirty = false;
    renderRpcRotationOrder();
    if (presetSelect && presets.includes(selectedPreset)) presetSelect.value = selectedPreset;
    if (intervalInput && data.rotation?.interval) intervalInput.value = data.rotation.interval;
    if (data.rotation_running) {
        showRpcProfileMsg(`Rotation active · ${rotationNames.join(' → ')} · ${data.rotation.interval}s`, 'success');
    } else if (data.rotation) {
        showRpcProfileMsg(`Rotation ready · ${rotationNames.join(' → ')} · ${data.rotation.interval}s`);
    } else {
        showRpcProfileMsg(presets.length ? `${presets.length} preset${presets.length === 1 ? '' : 's'} saved` : 'Save an activity to create your first preset.');
    }
}

async function saveRpcPreset() {
    const name = (document.getElementById('rpcPresetName')?.value || '').trim();
    if (!name) { showRpcProfileMsg('Enter a preset name first.', 'error'); return; }
    const built = buildRpcPresetActivity();
    if (built.error) { showRpcProfileMsg(built.error, 'error'); return; }
    let res = await postJSON('/api/rpc/profiles/preset', { action: 'save', name, activity: built.activity });
    if ((!res || !res.ok) && RPC_STATIC_PREVIEW) {
        const presets = readRpcPreviewStore(RPC_PREVIEW_PRESETS_KEY, {});
        presets[name] = built.activity;
        if (writeRpcPreviewStore(RPC_PREVIEW_PRESETS_KEY, presets)) res = { ok: true };
    }
    if (!res?.ok) { showRpcProfileMsg(res?.error || 'Preset could not be saved.', 'error'); return; }
    document.getElementById('rpcPresetName').value = '';
    showRpcProfileMsg(`Saved “${name}”.`, 'success');
    await loadRpcProfiles();
}

async function applyRpcPresetDraft() {
    const built = buildRpcPresetActivity();
    if (built.error) { showRpcProfileMsg(built.error, 'error'); return; }
    const response = await postJSON('/api/rpc', { action: 'set', activity: built.activity });
    if (response?.ok) {
        showRpcProfileMsg('RPC applied.', 'success');
        loadRpc();
        return;
    }
    if (RPC_STATIC_PREVIEW) {
        previewRpcPresetOnEditor(built.activity);
        showRpcMsg('Preview updated. Applying requires a connected client.', true);
        return;
    }
    showRpcProfileMsg(response?.error || 'RPC could not be applied.', 'error');
}

async function loadRpcPreset() {
    const name = document.getElementById('rpcPresetSelect')?.value || '';
    if (!name) { showRpcProfileMsg('Choose a saved preset first.', 'error'); return; }
    if (RPC_STATIC_PREVIEW) {
        const activity = readRpcPreviewStore(RPC_PREVIEW_PRESETS_KEY, {})[name];
        if (!activity) { showRpcProfileMsg('Preset could not be found in this preview.', 'error'); return; }
        fillRpcPresetComposer(name, activity);
        previewRpcPresetOnEditor(activity);
        showRpcMsg(`Loaded “${name}” into the live preview.`, true);
        return;
    }
    const res = await postJSON('/api/rpc/profiles/preset', { action: 'load', name });
    if (!res?.ok) { showRpcProfileMsg(res?.error || 'Preset could not be loaded.', 'error'); return; }
    showRpcProfileMsg(`Loaded “${name}”.`, 'success');
    loadRpc();
}

async function deleteRpcPreset() {
    const name = document.getElementById('rpcPresetSelect')?.value || '';
    if (!name) { showRpcProfileMsg('Choose a saved preset first.', 'error'); return; }
    let res;
    if (RPC_STATIC_PREVIEW) {
        const presets = readRpcPreviewStore(RPC_PREVIEW_PRESETS_KEY, {});
        if (!Object.hasOwn(presets, name)) { showRpcProfileMsg('Preset could not be found in this preview.', 'error'); return; }
        delete presets[name];
        writeRpcPreviewStore(RPC_PREVIEW_PRESETS_KEY, presets);
        res = { ok: true };
    } else {
        if (!window.confirm(`Delete the RPC preset “${name}”?`)) return;
        res = await postJSON('/api/rpc/profiles/preset', { action: 'delete', name });
    }
    if (!res?.ok) { showRpcProfileMsg(res?.error || 'Preset could not be deleted.', 'error'); return; }
    showRpcProfileMsg(`Deleted “${name}”.`, 'success');
    await loadRpcProfiles();
}

async function setRpcRotation() {
    const presets = [..._rpcRotationOrder];
    const interval = Number.parseInt(document.getElementById('rpcRotationInterval')?.value, 10);
    if (presets.length < 2) { showRpcProfileMsg('Add at least two presets to the rotation order.', 'error'); return; }
    let res = await postJSON('/api/rpc/profiles/rotation', { action: 'set', presets, interval });
    if ((!res || !res.ok) && RPC_STATIC_PREVIEW) {
        if (writeRpcPreviewStore(RPC_PREVIEW_ROTATION_KEY, { presets, interval })) res = { ok: true };
    }
    if (!res?.ok) { showRpcProfileMsg(res?.error || 'Rotation could not be saved.', 'error'); return; }
    _rpcRotationDirty = false;
    showRpcProfileMsg(`Rotation saved · ${presets.join(' → ')} · ${interval}s`, 'success');
    await loadRpcProfiles();
}

async function controlRpcRotation(action) {
    if (action === 'start' && (_rpcRotationDirty || _rpcRotationOrder.length < 2)) {
        showRpcProfileMsg('Save a rotation order with at least two presets first.', 'error');
        return;
    }
    if (RPC_STATIC_PREVIEW) {
        if (action === 'clear') {
            localStorage.removeItem(RPC_PREVIEW_ROTATION_KEY);
            _rpcRotationOrder = [];
            _rpcRotationDirty = false;
            renderRpcRotationOrder();
            showRpcProfileMsg('Rotation configuration cleared.', 'success');
            await loadRpcProfiles();
        } else {
            showRpcProfileMsg('Starting rotation requires a connected dashboard.', 'error');
        }
        return;
    }
    const res = await postJSON('/api/rpc/profiles/rotation', { action });
    if (!res?.ok) { showRpcProfileMsg(res?.error || `Rotation ${action} failed.`, 'error'); return; }
    const messages = { start: 'Rotation started.', stop: 'Rotation stopped.', clear: 'Rotation configuration cleared.' };
    showRpcProfileMsg(messages[action] || 'Rotation updated.', 'success');
    await loadRpcProfiles();
}

// ── Presence ───────────────────────────────────────────────────────────────────
const PRESENCE_BADGES = {
    online:    'badge-ok',
    idle:      'badge-warn',
    dnd:       'badge-pink',
    invisible: 'badge-off',
};

async function loadPresence() {
    const [presRes, afkRes] = await Promise.all([
        fetchJSON('/api/presence'),
        fetchJSON('/api/afk'),
    ]);
    if (presRes) {
        const status = presRes.status || 'unknown';
        const badge = document.getElementById('presenceBadge');
        const currentLabel = document.getElementById('presenceCurrentLabel');
        if (badge) {
            badge.textContent = status.charAt(0).toUpperCase() + status.slice(1);
            badge.className = 'badge ' + (PRESENCE_BADGES[status] || 'badge-off');
        }
        if (currentLabel) currentLabel.textContent = status === 'dnd' ? 'Do Not Disturb' : status.charAt(0).toUpperCase() + status.slice(1);
        document.querySelectorAll('[data-presence-status]').forEach(button => {
            button.setAttribute('aria-pressed', String(button.dataset.presenceStatus === status));
        });
    }
    if (afkRes) {
        const afkBadge = document.getElementById('afkBadge');
        const afkPanel = document.getElementById('afkPanel');
        const afkSummary = document.getElementById('afkStateSummary');
        const afkEnableButton = document.getElementById('afkEnableButton');
        const afkDisableButton = document.getElementById('afkDisableButton');
        if (afkBadge) {
            afkBadge.textContent = afkRes.active ? 'AFK' : 'Off';
            afkBadge.className = 'badge ' + (afkRes.active ? 'badge-warn' : 'badge-off');
        }
        if (afkPanel) afkPanel.classList.toggle('is-active', Boolean(afkRes.active));
        if (afkSummary) afkSummary.textContent = afkRes.active ? 'Automatic reply is on' : 'Automatic reply is off';
        if (afkEnableButton) afkEnableButton.setAttribute('aria-pressed', String(Boolean(afkRes.active)));
        if (afkDisableButton) afkDisableButton.setAttribute('aria-pressed', String(!afkRes.active));
        const afkInput = document.getElementById('afkMessageInput');
        if (afkInput && afkRes.message && !afkInput.value && document.activeElement !== afkInput) afkInput.value = afkRes.message;
        const count = document.getElementById('afkMessageCount');
        if (count && afkInput) count.textContent = `${afkInput.value.length} / 180`;
    }
}

function showPresenceMsg(id, msg, ok) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = msg;
    el.className = 'settings-msg ' + (ok ? 'ok' : 'err');
    setTimeout(() => { el.textContent = ''; el.className = 'settings-msg'; }, 3000);
}

async function setPresence(status) {
    const res = await postJSON('/api/presence', { status });
    if (res && res.ok) {
        showPresenceMsg('presenceMsg', 'Status set to: ' + status, true);
        trackDashboardAction('presence_set', `Set status to ${status}`);
        loadPresence();
        loadOverview();
    } else {
        showPresenceMsg('presenceMsg', (res && res.error) || 'Failed to set status.', false);
    }
}

document.addEventListener('input', event => {
    if (event.target && event.target.id === 'afkMessageInput') {
        const count = document.getElementById('afkMessageCount');
        if (count) count.textContent = `${event.target.value.length} / 180`;
    }
});

async function toggleAfk(action) {
    const message = document.getElementById('afkMessageInput').value.trim() || 'AFK';
    const res = await postJSON('/api/afk', { action, message });
    if (res && res.ok) {
        showPresenceMsg('afkMsg', res.active ? ('AFK enabled: ' + (res.message || '')) : 'AFK cleared.', true);
        trackDashboardAction('afk_toggle', res.active ? 'Enabled AFK' : 'Disabled AFK');
        loadPresence();
    } else {
        showPresenceMsg('afkMsg', (res && res.error) || 'AFK system unavailable.', false);
    }
}

// ── Hosted ────────────────────────────────────────────────────────────────────
async function loadHosted() {
    const res = await fetchJSON('/api/hosted');
    if (!res) return;
    setText('hostedTotal', res.total ?? 0);
    setText('hostedActive', res.active_count ?? 0);
    const badge = document.getElementById('hostedBadge');
    if (badge) badge.textContent = res.total ?? 0;
    const tbody = document.getElementById('hostedBody');
    if (!tbody) return;
    if (!res.hosted || res.hosted.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="empty-row">No hosted users found</td></tr>';
        return;
    }

    tbody.innerHTML = res.hosted.map(u => {
        const connected = !!u.connected;
        const processRunning = !!u.process_running;
        const statusLabel = connected ? '● Connected' : processRunning ? '◌ Starting' : '○ Inactive';
        const statusClass = connected ? 'badge-ok' : processRunning ? 'badge-warn' : 'badge-off';
        let statusBadge = `<span class="badge ${statusClass}">${statusLabel}</span>`;
        let warn = '';
        if (!connected) {
            const detail = u.connection_error || (processRunning ? 'Waiting for gateway READY' : 'Process stopped. Restart to retry.');
            warn = `<div style="color:#e74c3c;font-size:12px;margin-top:2px">${esc(detail)}</div>`;
        }
        return `<tr>
            <td class="cmd-name" style="font-size:11px">${esc(u.token_id || '—')}</td>
            <td>${esc(u.username || '—')}</td>
            <td class="cmd-aliases">${esc(u.user_id || '—')}</td>
            <td class="cmd-aliases">${esc(u.prefix || '—')}</td>
            <td class="cmd-aliases">${esc(u.client_type || 'unknown')}</td>
            <td>${statusBadge}${warn}</td>
            <td class="cmd-aliases">${esc(fmtTs(u.connected_at) || '—')}</td>
            <td>
                <button class="btn btn-ghost" style="padding:4px 10px;font-size:11px" onclick="restartHostedInstance('${encodeURIComponent(u.token_ref || '')}')" ${connected ? 'disabled' : ''}>Restart</button>
                <button class="btn btn-danger-soft" style="padding:4px 10px;font-size:11px" onclick="disconnectHostedInstance('${encodeURIComponent(u.token_ref || '')}')">Remove</button>
            </td>
        </tr>`;
    }).join('');
}

async function connectHostedToken() {
    const tokenInput = document.getElementById('hostTokenInput');
    const prefixInput = document.getElementById('hostPrefixInput');
    const token = tokenInput ? tokenInput.value.trim() : '';
    const prefix = prefixInput ? prefixInput.value.trim() : '$';
    if (!token) {
        showPresenceMsg('hostedActionMsg', 'Token is required.', false);
        return;
    }
    const res = await postJSON('/api/hosted/connect', { token, prefix });
    if (res && res.ok) {
        showPresenceMsg('hostedActionMsg', res.message || 'Instance connected.', true);
        trackDashboardAction('host_connect', 'Connected a hosted instance');
        if (tokenInput) tokenInput.value = '';
        await loadHosted();
        await loadOverview();
        return;
    }
    showPresenceMsg('hostedActionMsg', (res && res.error) || 'Failed to connect instance.', false);
}

async function disconnectHostedInstance(encodedTokenId) {
    const token_id = decodeURIComponent(encodedTokenId || '');
    if (!token_id) return;
    if (!confirm('Disconnect this hosted instance?')) return;
    const res = await postJSON('/api/hosted/disconnect', { token_id });
    if (res && res.ok) {
        showPresenceMsg('hostedActionMsg', 'Hosted instance disconnected.', true);
        trackDashboardAction('host_disconnect', `Disconnected ${token_id.slice(0, 8)}...`);
        await loadHosted();
        await loadOverview();
        return;
    }
    showPresenceMsg('hostedActionMsg', (res && res.error) || 'Failed to disconnect instance.', false);
}

async function restartHostedInstance(encodedTokenId) {
    const token_id = decodeURIComponent(encodedTokenId || '');
    if (!token_id) return;
    const res = await postJSON('/api/hosted/restart', { token_id });
    if (res && res.ok) {
        showPresenceMsg('hostedActionMsg', res.message || 'Instance restart requested.', true);
        trackDashboardAction('host_restart', `Restarted ${token_id.slice(0, 8)}...`);
        await loadHosted();
        return;
    }
    showPresenceMsg('hostedActionMsg', (res && res.error) || 'Failed to restart instance.', false);
}

// ── Dashboard Users (login management) ───────────────────────────────────────
async function loadDashUsers() {
    await loadDashProfile();
    await loadMyActivityTimeline();
    const res = await fetchJSON('/api/dash/users');
    if (!res) {
        const tbody = document.getElementById('dashUsersBody');
        if (tbody) tbody.innerHTML = '<tr><td colspan="4" class="empty-row">Admin only</td></tr>';
        return;
    }
    const count = res.total ?? 0;
    const el = document.getElementById('dashUsersTotal');
    if (el) el.textContent = count + (count === 1 ? ' account' : ' accounts');
    const tbody = document.getElementById('dashUsersBody');
    if (!tbody) return;
    if (!res.users || res.users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-row">No dashboard accounts yet</td></tr>';
        return;
    }
    tbody.innerHTML = res.users.map(u =>
        `<tr>
            <td class="cmd-aliases">${esc(u.user_id)}</td>
            <td style="font-weight:600">${esc(u.username)}</td>
            <td class="cmd-aliases">${esc(u.instance_id || '—')}</td>
            <td><button class="btn btn-danger-soft" onclick="removeDashUser('${esc(u.user_id)}')" style="padding:4px 12px;font-size:11px">Remove</button></td>
        </tr>`
    ).join('');

    await loadAccessRequests();
}

function showDashAccountMsg(msg, ok) {
    const el = document.getElementById('dashAccountMsg');
    if (!el) return;
    el.textContent = msg;
    el.className = 'settings-msg ' + (ok ? 'ok' : 'err');
    setTimeout(() => { el.textContent = ''; el.className = 'settings-msg'; }, 4000);
}

function showAccessReqBulkMsg(msg, ok) {
    const el = document.getElementById('accessReqBulkMsg');
    if (!el) return;
    el.textContent = msg;
    el.className = 'settings-msg ' + (ok ? 'ok' : 'err');
    setTimeout(() => { el.textContent = ''; el.className = 'settings-msg'; }, 5000);
}

const WORKSPACE_PREFS_VERSION = 'aria-workspace-v1';
const DEFAULT_WORKSPACE_PREFS = { accent: '#69b7ff', density: 'comfortable', visibleTabs: null };
let _workspacePrefs = { ...DEFAULT_WORKSPACE_PREFS };
let _workspaceCustomizerBound = false;
let _sidebarGroupsBound = false;

function workspacePrefsKey(profile = _meProfile) {
    const identity = String(profile?.user_id || profile?.username || 'default');
    return `${WORKSPACE_PREFS_VERSION}:${encodeURIComponent(identity)}`;
}

function saveWorkspacePrefs() {
    try { localStorage.setItem(workspacePrefsKey(), JSON.stringify(_workspacePrefs)); } catch (_) {}
}

function applyWorkspaceAppearance() {
    const root = document.documentElement;
    const hex = /^#[0-9a-f]{6}$/i.test(_workspacePrefs.accent) ? _workspacePrefs.accent : DEFAULT_WORKSPACE_PREFS.accent;
    const channels = [1, 3, 5].map(index => parseInt(hex.slice(index, index + 2), 16));
    const lighter = channels.map(channel => Math.round(channel + (255 - channel) * 0.24));
    root.style.setProperty('--workspace-accent-rgb', channels.join(', '));
    root.style.setProperty('--a2', hex);
    root.style.setProperty('--a3', `#${lighter.map(channel => channel.toString(16).padStart(2, '0')).join('')}`);
    document.body.classList.toggle('density-compact', _workspacePrefs.density === 'compact');
    document.querySelectorAll('[data-accent]').forEach(button => {
        button.classList.toggle('is-selected', button.dataset.accent.toLowerCase() === hex.toLowerCase());
    });
    const picker = document.getElementById('workspaceAccentPicker');
    if (picker) picker.value = hex;
    document.querySelectorAll('[data-density-choice]').forEach(button => {
        button.classList.toggle('is-selected', button.dataset.densityChoice === _workspacePrefs.density);
    });
}

function userCanSeeNavItem(item, profile = _meProfile) {
    if (item.dataset.ownerOnly === 'true') return !!profile?.is_owner;
    if (item.dataset.adminOnly === 'true') return !!profile?.is_admin || !!profile?.is_owner;
    return true;
}

function applyWorkspaceTabs() {
    const configured = Array.isArray(_workspacePrefs.visibleTabs) ? new Set(_workspacePrefs.visibleTabs) : null;
    navItems.forEach(item => {
        const permitted = userCanSeeNavItem(item);
        const visible = item.dataset.pinned === 'true' || !configured || configured.has(item.dataset.section);
        item.hidden = !permitted || !visible;
        item.dataset.hiddenByRole = String(!permitted);
    });
    document.querySelectorAll('.nav-group-label').forEach(label => {
        const rolePermitted = label.dataset.ownerOnly === 'true' ? !!_meProfile?.is_owner :
            label.dataset.adminOnly === 'true' ? !!_meProfile?.is_admin || !!_meProfile?.is_owner : true;
        let next = label.nextElementSibling;
        let hasVisibleItem = false;
        while (next && !next.classList.contains('nav-group-label')) {
            if (next.classList.contains('nav-item') && !next.hidden) hasVisibleItem = true;
            next = next.nextElementSibling;
        }
        label.hidden = !rolePermitted || !hasVisibleItem;
    });
    const active = document.querySelector('.nav-item.active');
    if (active && active.hidden) document.querySelector('.nav-item[data-section="overview"]')?.click();
}

function renderWorkspaceTabChoices(profile) {
    const grid = document.getElementById('workspaceTabsGrid');
    if (!grid) return;
    const configured = Array.isArray(_workspacePrefs.visibleTabs) ? new Set(_workspacePrefs.visibleTabs) : null;
    grid.innerHTML = Array.from(navItems).filter(item => userCanSeeNavItem(item, profile)).map(item => {
        const section = item.dataset.section;
        const label = item.textContent.trim();
        const checked = item.dataset.pinned === 'true' || !configured || configured.has(section);
        const disabled = item.dataset.pinned === 'true' ? ' disabled' : '';
        return `<label class="appearance-tab-option"><input type="checkbox" data-workspace-tab="${esc(section)}"${checked ? ' checked' : ''}${disabled}><span>${esc(label)}</span></label>`;
    }).join('');
    grid.querySelectorAll('[data-workspace-tab]').forEach(input => {
        input.addEventListener('change', () => {
            const selected = Array.from(grid.querySelectorAll('[data-workspace-tab]:checked')).map(control => control.dataset.workspaceTab);
            _workspacePrefs.visibleTabs = selected;
            saveWorkspacePrefs();
            applyWorkspaceTabs();
        });
    });
}

function initializeWorkspaceCustomizer(profile) {
    try {
        const stored = JSON.parse(localStorage.getItem(workspacePrefsKey(profile)) || 'null');
        _workspacePrefs = {
            ...DEFAULT_WORKSPACE_PREFS,
            ...(stored && typeof stored === 'object' ? stored : {}),
        };
    } catch (_) {
        _workspacePrefs = { ...DEFAULT_WORKSPACE_PREFS };
    }
    applyWorkspaceAppearance();
    applyWorkspaceTabs();
    renderWorkspaceTabChoices(profile);
    if (_workspaceCustomizerBound) return;
    const overlay = document.getElementById('workspaceCustomizer');
    if (!overlay) return;
    _workspaceCustomizerBound = true;
    const close = () => { overlay.hidden = true; };
    document.getElementById('openWorkspaceCustomizer')?.addEventListener('click', () => {
        overlay.hidden = false;
        document.getElementById('closeWorkspaceCustomizer')?.focus();
    });
    ['closeWorkspaceCustomizer', 'doneWorkspaceCustomizer'].forEach(id => document.getElementById(id)?.addEventListener('click', close));
    overlay.querySelector('[data-close-workspace-customizer]')?.addEventListener('click', close);
    overlay.addEventListener('keydown', event => { if (event.key === 'Escape') close(); });
    document.querySelectorAll('[data-accent]').forEach(button => button.addEventListener('click', () => {
        _workspacePrefs.accent = button.dataset.accent;
        applyWorkspaceAppearance();
        saveWorkspacePrefs();
    }));
    document.getElementById('workspaceAccentPicker')?.addEventListener('input', event => {
        _workspacePrefs.accent = event.currentTarget.value;
        applyWorkspaceAppearance();
        saveWorkspacePrefs();
    });
    document.querySelectorAll('[data-density-choice]').forEach(button => button.addEventListener('click', () => {
        _workspacePrefs.density = button.dataset.densityChoice;
        applyWorkspaceAppearance();
        saveWorkspacePrefs();
    }));
    document.getElementById('resetWorkspaceAppearance')?.addEventListener('click', () => {
        _workspacePrefs = { ...DEFAULT_WORKSPACE_PREFS };
        try { localStorage.removeItem(workspacePrefsKey(profile)); } catch (_) {}
        applyWorkspaceAppearance();
        applyWorkspaceTabs();
        renderWorkspaceTabChoices(profile);
    });
}

function applyRoleVisibility(profile) {
    const isOwner = !!(profile && profile.is_owner);
    const isAdmin = !!(profile && profile.is_admin) || isOwner;
    document.querySelectorAll('[data-owner-only="true"]').forEach(el => {
        el.hidden = !isOwner;
        if (el.classList.contains('nav-item')) el.dataset.hiddenByRole = String(!isOwner);
    });
    const adminOnly = document.querySelectorAll('[data-admin-only="true"], .admin-only');
    adminOnly.forEach(el => {
        el.hidden = !isAdmin;
        el.style.removeProperty('display');
        if (el.classList.contains('nav-item')) el.dataset.hiddenByRole = String(!isAdmin);
    });

    const usersTitle = document.getElementById('dashUsersTotal');
    if (usersTitle && !isAdmin) usersTitle.textContent = 'My account';

    const active = document.querySelector('.nav-item.active');
    if (active && (active.hidden || active.dataset.hiddenByRole === 'true')) {
        const fallback = document.querySelector('.nav-item[data-section="overview"]');
        if (fallback) fallback.click();
    }
    initializeWorkspaceCustomizer(profile);
    initializeSidebarGroups(profile);
}

function sidebarGroupStorageKey(profile = _meProfile) {
    return `${workspacePrefsKey(profile)}:sidebar-groups`;
}

function setSidebarGroupExpanded(groupName, expanded, persist = true) {
    const toggle = document.querySelector(`[data-group-toggle="${groupName}"]`);
    if (!toggle) return;
    toggle.setAttribute('aria-expanded', String(expanded));
    document.querySelectorAll(`.nav-item[data-nav-group="${groupName}"]`).forEach(item => {
        item.classList.toggle('is-collapsed', !expanded);
    });
    if (!persist) return;
    try {
        const key = sidebarGroupStorageKey();
        const stored = JSON.parse(localStorage.getItem(key) || '{}');
        stored[groupName] = expanded;
        localStorage.setItem(key, JSON.stringify(stored));
    } catch (_) {}
}

function initializeSidebarGroups(profile) {
    let stored = {};
    try { stored = JSON.parse(localStorage.getItem(sidebarGroupStorageKey(profile)) || '{}'); } catch (_) {}
    const defaults = { workspace: true, presence: true, account: false, tools: false, administration: false, owner: false };
    document.querySelectorAll('[data-group-toggle]').forEach(toggle => {
        const groupName = toggle.dataset.groupToggle;
        const expanded = typeof stored[groupName] === 'boolean' ? stored[groupName] : !!defaults[groupName];
        setSidebarGroupExpanded(groupName, expanded, false);
    });
    if (_sidebarGroupsBound) return;
    _sidebarGroupsBound = true;
    document.querySelectorAll('[data-group-toggle]').forEach(toggle => {
        const activate = () => {
            const groupName = toggle.dataset.groupToggle;
            setSidebarGroupExpanded(groupName, toggle.getAttribute('aria-expanded') !== 'true');
        };
        toggle.addEventListener('click', activate);
        toggle.addEventListener('keydown', event => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                activate();
            }
        });
    });
}

async function loadOwnerPanel() {
    const res = await fetchJSON('/api/owner/summary');
    if (!res || !res.ok) {
        setText('ownerGatewayState', 'Unavailable');
        setText('ownerIdentityState', 'Unavailable');
        return;
    }

    const data = res.data || {};
    setText('ownerAccountTotal', data.total_accounts ?? 0);
    setText('ownerAdminTotal', data.admin_accounts ?? 0);
    setText('ownerPendingTotal', data.pending_requests ?? 0);
    setText('ownerGatewayState', data.connected ? 'Connected' : 'Offline');
    setText('ownerGatewayLatency', `Latency ${data.gateway_latency_ms == null ? '—' : `${data.gateway_latency_ms} ms`}`);
    setText('ownerIdentityState', data.connected ? 'ready' : 'offline');
    setText('ownerIdentityName', data.username || '—');
    setText('ownerIdentityId', data.user_id || '—');

    const accounts = Array.isArray(data.accounts) ? data.accounts : [];
    setText('ownerAccountBadge', `${accounts.length} accounts`);
    const accountBody = document.getElementById('ownerAccountBody');
    if (accountBody) {
        accountBody.innerHTML = accounts.length ? accounts.map(account => {
            const username = String(account.username || 'Unnamed account');
            return `<tr data-username="${esc(username.toLowerCase())}">
                <td class="owner-account-name">${esc(username)}</td>
                <td>${esc(account.role || 'user')}</td>
                <td>${fmtTs(account.created_at)}</td>
                <td>${fmtTs(account.last_login_at)}</td>
            </tr>`;
        }).join('') : '<tr><td colspan="4" class="empty-row">No accounts yet.</td></tr>';
    }

    const resetRequests = Array.isArray(data.password_reset_requests) ? data.password_reset_requests : [];
    setText('ownerResetBadge', `${resetRequests.length} pending`);
    const resetList = document.getElementById('ownerResetRequestsList');
    if (resetList) {
        resetList.innerHTML = resetRequests.length ? resetRequests.map(item => {
            const requestId = esc(item.id || '');
            const username = esc(item.username || 'Account');
            return `<article class="owner-reset-request">
                <div class="owner-reset-request-main"><strong>${username}</strong><span>${esc(item.reason || 'Password reset requested')}</span><small>${relativeTime(item.timestamp)}</small></div>
                <div class="owner-reset-request-actions">
                    <button class="btn btn-primary" type="button" onclick="approveAccessRequest('${requestId}', 'password_reset')">Approve reset</button>
                    <button class="btn btn-ghost" type="button" onclick="denyAccessRequest('${requestId}')" aria-label="Deny reset request for ${username}">Deny</button>
                </div>
            </article>`;
        }).join('') : '<div class="log-loading">No pending password reset requests.</div>';
    }
}

function filterOwnerAccounts() {
    const query = String(document.getElementById('ownerAccountSearch')?.value || '').trim().toLowerCase();
    document.querySelectorAll('#ownerAccountBody tr[data-username]').forEach(row => {
        row.hidden = !row.dataset.username.includes(query);
    });
}

function showOwnerResetCredential(username, password) {
    const overlay = document.getElementById('ownerResetCredential');
    if (!overlay) return;
    setText('ownerResetCredentialUser', username || 'Account');
    setText('ownerResetCredentialValue', password || '');
    overlay.hidden = false;
    document.getElementById('ownerResetDialogTitle')?.focus();
}

async function copyOwnerResetCredential() {
    const password = document.getElementById('ownerResetCredentialValue')?.textContent || '';
    if (!password) return;
    try {
        await navigator.clipboard.writeText(password);
        showOwnerResetMessage('Temporary password copied. This view will not be available again.', true);
    } catch {
        showOwnerResetMessage('Clipboard unavailable. Select the temporary password to copy it.', false);
    }
}

function dismissOwnerResetCredential() {
    const overlay = document.getElementById('ownerResetCredential');
    if (overlay) overlay.hidden = true;
    setText('ownerResetCredentialValue', '');
    setText('ownerResetCredentialUser', 'Account');
}

function showOwnerResetMessage(message, ok) {
    const el = document.getElementById('ownerResetMessage');
    if (!el) return;
    el.textContent = message;
    el.className = 'owner-reset-message settings-msg ' + (ok ? 'ok' : 'err');
}

async function loadDashProfile() {
    const res = await fetchJSON('/api/dash/me');
    if (!res || !res.ok) {
        setText('meUsername', '—');
        setText('meUserId', '—');
        setText('meRole', '—');
        setText('meInstance', '—');
        setText('pendingRequests', 0);
        setText('meLastLogin', '—');
        setText('meLastSeen', '—');
        return;
    }

    const p = res.profile || {};
    _meProfile = p;
    const s = res.summary || {};
    setText('meUsername', p.username || '—');
    setText('meUserId', p.user_id || '—');
    setText('meRole', p.role || 'user');
    setText('sidebarRoleLabel', p.is_owner ? 'Owner workspace' : p.is_admin ? 'Admin workspace' : 'Aria workspace');
    setText('meInstance', p.instance_id || '—');
    setText('pendingRequests', s.pending_requests ?? 0);
    setText('meLastLogin', fmtTs(p.last_login_at));
    setText('meLastSeen', fmtTs(p.last_seen_at));

    const card = document.getElementById('accessRequestsCard');
    if (card) card.style.display = p.is_admin ? 'block' : 'none';
    applyRoleVisibility(p);
}

async function loadMyActivityTimeline() {
    const feed = document.getElementById('activityTimelineFeed');
    const badge = document.getElementById('activityTimelineBadge');
    if (!feed || !badge) return;

    const res = await fetchJSON('/api/dash/activity');
    if (!res || !res.ok) {
        badge.textContent = '0';
        feed.innerHTML = '<div class="log-loading">Unable to load timeline.</div>';
        return;
    }

    const timeline = Array.isArray(res.timeline) ? res.timeline : [];
    badge.textContent = String(timeline.length);
    if (!timeline.length) {
        feed.innerHTML = '<div class="log-loading">No recent account actions yet.</div>';
        return;
    }

    feed.innerHTML = timeline.slice().reverse().map(t => {
        const action = esc(t.action || 'activity');
        const details = esc(t.details || '');
        const ts = fmtTs(t.ts);
        return `<div class="history-item">
            <div class="history-dot"></div>
            <div class="history-content">
                <span class="history-cmd">${action}</span>
                <div class="history-meta">🕐 ${esc(ts)}</div>
                ${details ? `<div class="history-raw">${details}</div>` : ''}
            </div>
        </div>`;
    }).join('');
}

async function changeMyPassword() {
    const oldPassword = document.getElementById('oldPasswordInput').value;
    const newPassword = document.getElementById('newPasswordInput').value;
    if (!oldPassword || !newPassword) {
        showDashAccountMsg('Enter both current and new password.', false);
        return;
    }
    const res = await postJSON('/api/dash/change-password', {
        old_password: oldPassword,
        new_password: newPassword,
    });
    if (res && res.ok) {
        showDashAccountMsg('Password updated.', true);
        trackDashboardAction('password_change', 'Updated dashboard password');
        document.getElementById('oldPasswordInput').value = '';
        document.getElementById('newPasswordInput').value = '';
        loadMyActivityTimeline();
    } else {
        showDashAccountMsg((res && res.error) || 'Failed to update password.', false);
    }
}

async function loadAccessRequests() {
    const card = document.getElementById('accessRequestsCard');
    const body = document.getElementById('accessReqBody');
    const badge = document.getElementById('accessReqBadge');
    if (!card || !body || !badge) return;

    const res = await fetchJSON('/api/dash/requests');
    if (!res || !res.ok) {
        body.innerHTML = '<tr><td colspan="5" class="empty-row">Admin only</td></tr>';
        return;
    }

    const reqs = res.requests || [];
    badge.textContent = String(reqs.length);
    if (!reqs.length) {
        body.innerHTML = '<tr><td colspan="5" class="empty-row">No account requests</td></tr>';
        return;
    }

    body.innerHTML = reqs.slice().reverse().map(r => {
        const id = esc(r.id || '');
        const reqType = String(r.type || 'access').toLowerCase();
        const reqLabel = reqType === 'password_reset' ? 'Password Reset' : 'Access';
        const targetUser = reqType === 'password_reset'
            ? (r.user_id || r.approved_uid || '—')
            : (r.username || r.user_id || '—');
        const details = reqType === 'password_reset'
            ? (r.reason || 'Password reset requested')
            : (r.reason || '—');
        const status = String(r.status || 'pending').toLowerCase();
        const statusClass = status === 'approved' ? 'badge-ok' : status === 'denied' ? 'badge-pink' : 'badge-warn';
        const actions = status === 'pending'
            ? `<button class="btn btn-primary" style="padding:4px 10px;font-size:11px" onclick="approveAccessRequest('${id}', '${esc(reqType)}')">Approve</button>
               <button class="btn btn-danger-soft" style="padding:4px 10px;font-size:11px" onclick="denyAccessRequest('${id}')">Deny</button>`
            : '<span style="color:var(--muted);font-size:12px">Complete</span>';

        return `<tr>
            <td style="font-weight:600">${esc(reqLabel)}</td>
            <td>${esc(targetUser)}</td>
            <td style="color:var(--muted)">${esc(details)}</td>
            <td><span class="badge ${statusClass}">${esc(status)}</span></td>
            <td>${actions}</td>
        </tr>`;
    }).join('');
}

async function approveAccessRequest(reqId, reqType = 'access') {
    const isPasswordReset = String(reqType || '').toLowerCase() === 'password_reset';
    if (isPasswordReset && !confirm('Rotate this account password and show the generated temporary password once?')) return;
    const customUserId = isPasswordReset ? '' : (prompt('Optional: set custom user_id (leave empty for auto)') || '');
    const customPassword = isPasswordReset ? '' : (prompt('Optional: set custom password (leave empty for auto)') || '');
    const body = {};
    if (customUserId.trim()) body.user_id = customUserId.trim();
    if (customPassword.trim()) body.password = customPassword.trim();

    try {
        const res = await postJSON(`/api/dash/requests/${encodeURIComponent(reqId)}/approve`, body);
        if (res && res.ok) {
            if (isPasswordReset) {
                showOwnerResetCredential(res.username, res.password);
                showOwnerResetMessage('Reset approved. Copy the generated password now; it will not be stored in this panel.', true);
            } else {
                showDashUsersMsg(`Approved account ${res.user_id}.`, true);
            }
            trackDashboardAction('request_approve', `Approved request ${reqId}`);
            loadAccessRequests();
            loadDashUsers();
            loadOwnerPanel();
        } else {
            showDashUsersMsg((res && res.error) || 'Approve failed.', false);
        }
    } catch {
        showDashUsersMsg('Approve request failed.', false);
    }
}

async function denyAccessRequest(reqId) {
    try {
        const res = await postJSON(`/api/dash/requests/${encodeURIComponent(reqId)}/deny`, {});
        if (res && res.ok) {
            showDashUsersMsg('Request denied.', true);
            trackDashboardAction('request_deny', `Denied request ${reqId}`);
            loadAccessRequests();
            loadDashUsers();
            loadOwnerPanel();
        } else {
            showDashUsersMsg((res && res.error) || 'Deny failed.', false);
        }
    } catch {
        showDashUsersMsg('Deny request failed.', false);
    }
}

function showDashUsersMsg(msg, ok) {
    const el = document.getElementById('dashUsersMsg') || document.getElementById('ownerResetMessage');
    if (!el) return;
    el.textContent = msg;
    el.className = 'settings-msg ' + (ok ? 'ok' : 'err');
    setTimeout(() => { el.textContent = ''; el.className = 'settings-msg'; }, 4000);
}

async function addDashUser() {
    const uid = document.getElementById('newDashUserId').value.trim();
    const uname = document.getElementById('newDashUsername').value.trim();
    const pw = document.getElementById('newDashPassword').value;
    if (!uid || !pw) { showDashUsersMsg('User ID and password required.', false); return; }
    const res = await postJSON('/api/dash/register', { user_id: uid, username: uname || uid, password: pw });
    if (res && res.ok) {
        showDashUsersMsg(`Login created for ${uid}`, true);
        trackDashboardAction('account_create', `Created account ${uid}`);
        document.getElementById('newDashPassword').value = '';
        loadDashUsers();
    } else {
        showDashUsersMsg((res && res.error) || 'Failed.', false);
    }
}

async function removeDashUser(uid) {
    try {
        const res = await deleteJSON(`/api/dash/register/${encodeURIComponent(uid)}`);
        if (res && res.ok) { showDashUsersMsg(`Removed ${uid}`, true); trackDashboardAction('account_remove', `Removed account ${uid}`); loadDashUsers(); }
        else showDashUsersMsg((res && res.error) || 'Failed.', false);
    } catch(e) { showDashUsersMsg('Request failed.', false); }
}

async function approveAllPendingRequests() {
    const res = await postJSON('/api/dash/requests/approve-all-pending', {});
    if (res && res.ok) {
        const count = Number(res.approved_count || 0);
        const sample = Array.isArray(res.approved) && res.approved.length
            ? ` First: ${res.approved[0].user_id}/${res.approved[0].password}`
            : '';
        showAccessReqBulkMsg(`Approved ${count} pending request(s).${sample}`, true);
        trackDashboardAction('request_bulk_approve', `Bulk approved ${count} requests`);
        loadAccessRequests();
        loadDashUsers();
    } else {
        showAccessReqBulkMsg((res && res.error) || 'Bulk approve failed.', false);
    }
}

async function denyAllPendingRequests() {
    const res = await postJSON('/api/dash/requests/deny-all-pending', {});
    if (res && res.ok) {
        const count = Number(res.denied_count || 0);
        showAccessReqBulkMsg(`Denied ${count} pending request(s).`, true);
        trackDashboardAction('request_bulk_deny', `Bulk denied ${count} requests`);
        loadAccessRequests();
        loadDashUsers();
    } else {
        showAccessReqBulkMsg((res && res.error) || 'Bulk deny failed.', false);
    }
}

async function trackDashboardAction(action, details = '') {
    if (!_meProfile) return;
    if (!action) return;
    await postJSON('/api/dash/activity', { action, details });
}

// ── Logs ──────────────────────────────────────────────────────────────────────
async function loadLogs() {
    const container = document.getElementById('logContainer');
    const countEl   = document.getElementById('logLineCount');
    const cmdFeed   = document.getElementById('commandExecFeed');
    const sniperFeed = document.getElementById('sniperFeed');
    const gatewayFeed = document.getElementById('gatewayFeed');
    if (!container) return;
    container.innerHTML = '<div class="log-loading">Fetching logs…</div>';
    const res = await fetchJSON('/api/logs?lines=100');
    if (!res || !res.lines) {
        container.innerHTML = '<div class="log-loading">Failed to load logs.</div>';
        return;
    }

    const summary = res.summary || {};
    const connectedUser = summary.connected_user || {};
    setText('logsConnectedUser', connectedUser.username || '—');
    setText('logsConnectedUserId', connectedUser.user_id || '—');
    setText('logsCommandTotal', summary.command_total ?? 0);
    setText('logsCommandEvents', summary.command_events ?? 0);
    setText('logsSniperEvents', summary.sniper_events ?? 0);
    setText('logsGatewayEvents', summary.gateway_events ?? 0);
    setText('logsErrorEvents', summary.error_events ?? 0);

    const events = res.events || {};
    const commandEvents = events.commands || [];
    const sniperEvents = events.snipers || [];
    const gatewayEvents = events.gateway || [];
    const errorEvents = events.errors || [];

    if (cmdFeed) {
        if (!commandEvents.length) {
            cmdFeed.innerHTML = '<div class="log-loading">No command execution logs yet.</div>';
        } else {
            cmdFeed.innerHTML = commandEvents.slice().reverse().map(e => {
                const duration = e.duration_ms != null ? `${Math.round(e.duration_ms)}ms` : '—';
                const status = String(e.status || 'success').toLowerCase();
                const statusBadge = status === 'failed'
                    ? '<span class="badge badge-pink">failed</span>'
                    : '<span class="badge badge-ok">ok</span>';
                return `<div class="history-item">
                    <div class="history-dot"></div>
                    <div class="history-content">
                        <span class="history-cmd">${esc(e.command || '(unknown)')}</span>
                        <span class="badge badge-warn">#${esc(String(e.number || '0'))}</span>
                        ${statusBadge}
                        <div class="history-meta">${[
                            e.user ? '👤 ' + esc(e.user) : '',
                            e.guild ? '🏠 ' + esc(e.guild) : '',
                            e.time ? '🕐 ' + esc(e.time) : '',
                            '⚡ ' + esc(duration),
                        ].filter(Boolean).join(' &nbsp;·&nbsp; ')}</div>
                    </div>
                </div>`;
            }).join('');
        }
    }

    if (sniperFeed) {
        if (!sniperEvents.length) {
            sniperFeed.innerHTML = '<div class="log-loading">No sniper logs yet.</div>';
        } else {
            sniperFeed.innerHTML = sniperEvents.slice().reverse().map(e => `
                <div class="history-item">
                    <div class="history-dot"></div>
                    <div class="history-content">
                        ${e.time ? `<div class="history-meta">🕐 ${esc(e.time)}</div>` : ''}
                        <div class="history-raw">${esc(e.raw || '')}</div>
                    </div>
                </div>
            `).join('');
        }
    }

    if (gatewayFeed) {
        const merged = gatewayEvents.concat(errorEvents).slice(-100);
        if (!merged.length) {
            gatewayFeed.innerHTML = '<div class="log-loading">No gateway/error logs yet.</div>';
        } else {
            gatewayFeed.innerHTML = merged.slice().reverse().map(e => {
                const lo = String(e.raw || '').toLowerCase();
                const badge = (lo.includes('error') || lo.includes('exception') || lo.includes('failed'))
                    ? '<span class="badge badge-pink">error</span>'
                    : '<span class="badge badge-warn">gateway</span>';
                return `<div class="history-item">
                    <div class="history-dot"></div>
                    <div class="history-content">
                        ${badge}
                        ${e.time ? `<div class="history-meta">🕐 ${esc(e.time)}</div>` : ''}
                        <div class="history-raw">${esc(e.raw || '')}</div>
                    </div>
                </div>`;
            }).join('');
        }
    }

    if (res.lines.length === 0) {
        container.innerHTML = '<div class="log-loading">No log output yet.</div>';
        return;
    }
    if (countEl) countEl.textContent = res.lines.length + ' lines';
    container.innerHTML = res.lines.map(l => {
        const lo = l.toLowerCase();
        const cls = (lo.includes('[error]') || lo.includes('[auth-error]') || lo.includes('traceback') || lo.includes('exception'))
                  ? 'log-error'
                  : (lo.includes('[warning]') || lo.includes('[warn]'))
                  ? 'log-warn'
                  : lo.includes('[rpc]')
                  ? 'log-rpc'
                  : lo.includes('[gateway]')
                  ? 'log-gateway'
                  : (lo.includes('success') || lo.includes('connected') || lo.includes('ready'))
                  ? 'log-success'
                  : '';
        return `<div class="log-line ${cls}">${esc(l)}</div>`;
    }).join('');
    container.scrollTop = container.scrollHeight;
}

// ── Refresh button ────────────────────────────────────────────────────────────
document.getElementById('refreshBtn')?.addEventListener('click', () => {
    const active = document.querySelector('.nav-item.active');
    if (active) {
        loadSection(active.dataset.section);
        showToast('Refreshed', `Section "${active.dataset.section}" reloaded`, 'ok', 2200);
    }
});

// ── Auto-refresh every 30s ────────────────────────────────────────────────────
setInterval(() => {
    const active = document.querySelector('.nav-item.active');
    if (active) loadSection(active.dataset.section);
}, 30000);

// Faster overview heartbeat for more "live" feeling metrics.
setInterval(() => {
    const active = document.querySelector('.nav-item.active');
    if (active && active.dataset.section === 'overview') loadOverview();
}, 7000);

setInterval(() => {
    const active = document.querySelector('.nav-item.active');
    if (active && active.dataset.section === 'rpc') loadSpotifyLyrics();
}, 5000);

// ── Initial load ──────────────────────────────────────────────────────────────
async function bootDashboard() {
    let timeoutId;
    try {
        const initialRequests = Promise.allSettled([
            loadSection('overview'),
            loadDashProfile(),
            refreshNotificationCenter(),
        ]).then(results => {
            const failure = results.find(result => result.status === 'rejected');
            if (failure) reportDashboardError('Initial dashboard data', failure.reason);
            return true;
        });
        const timeout = new Promise(resolve => {
            timeoutId = setTimeout(() => resolve(false), 8000);
        });
        const isSynced = await Promise.race([initialRequests.then(() => true), timeout]);
        setText('loaderStatus', isSynced
            ? 'RUNTIME / INITIAL SYNC COMPLETE'
            : 'RUNTIME / CONTINUING CONNECTION');
    } catch (error) {
        reportDashboardError('Initial load', error);
    } finally {
        clearTimeout(timeoutId);
        setTimeout(dismissLoader, 300);
    }
}
bootDashboard();
// Welcome toast
setTimeout(() => showToast('Welcome back 👋', 'Aria dashboard loaded successfully', 'ok', 4000), 1200);

document.addEventListener('DOMContentLoaded', () => {
    const bell = document.getElementById('topbarBell');
    const panel = document.getElementById('notificationCenter');
    const clearBtn = document.getElementById('notificationClearBtn');

    if (bell) {
        bell.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleNotificationCenter();
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            deleteJSON('/api/discord/notifications');
            _notificationState.events = [];
            _notificationState.seenTs = Date.now() / 1000;
            refreshNotificationCenter();
        });
    }

    document.addEventListener('click', (e) => {
        if (!_notificationState.open) return;
        if (!panel) return;
        if (panel.contains(e.target) || (bell && bell.contains(e.target))) return;
        toggleNotificationCenter(false);
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && _notificationState.open) {
            toggleNotificationCenter(false);
        }
    });
});

const _dashboardSelectStates = new WeakMap();
let _dashboardSelectSequence = 0;

function updateDashboardSelectPosition(state) {
    const rect = state.trigger.getBoundingClientRect();
    const maxHeight = Math.min(360, Math.max(160, window.innerHeight - 24));
    state.menu.style.width = `${rect.width}px`;
    state.menu.style.maxHeight = `${maxHeight}px`;
    const menuHeight = Math.min(state.menu.scrollHeight, maxHeight);
    const top = rect.bottom + menuHeight + 8 <= window.innerHeight || rect.top < menuHeight + 8
        ? rect.bottom + 4
        : rect.top - menuHeight - 4;
    state.menu.style.top = `${Math.max(8, Math.min(top, window.innerHeight - menuHeight - 8))}px`;
    state.menu.style.left = `${Math.max(8, Math.min(rect.left, window.innerWidth - rect.width - 8))}px`;
}

function closeDashboardSelect(state, restoreFocus = false) {
    state.menu.hidden = true;
    state.trigger.setAttribute('aria-expanded', 'false');
    if (restoreFocus) state.trigger.focus();
}

function renderDashboardSelect(state) {
    const { select, trigger, menu } = state;
    const options = [...select.options];
    const selected = options.find(option => option.selected) || options[0];
    const selectedText = selected?.textContent.trim() || 'Choose';
    const copy = document.createElement('span');
    copy.className = 'aria-select-trigger-copy';
    copy.textContent = selectedText;
    trigger.replaceChildren(copy);
    trigger.disabled = select.disabled;
    trigger.setAttribute('aria-label', state.label);

    const fragment = document.createDocumentFragment();
    let lastGroup = null;
    for (const option of options) {
        const group = option.parentElement instanceof HTMLOptGroupElement
            ? option.parentElement.label
            : '';
        if (group && group !== lastGroup) {
            const heading = document.createElement('div');
            heading.className = 'aria-select-group-label';
            heading.setAttribute('role', 'presentation');
            heading.textContent = group;
            fragment.append(heading);
        }
        lastGroup = group;

        const row = document.createElement('button');
        row.className = 'aria-select-option';
        row.type = 'button';
        row.setAttribute('role', 'option');
        row.setAttribute('aria-selected', String(option.value === select.value));
        row.dataset.value = option.value;
        row.disabled = option.disabled || select.disabled;
        const label = document.createElement('span');
        label.className = 'aria-select-option-copy';
        const title = document.createElement('strong');
        title.textContent = option.textContent.trim();
        label.append(title);
        const description = option.dataset.description || '';
        if (description) {
            const detail = document.createElement('small');
            detail.textContent = description;
            label.append(detail);
        }
        const check = document.createElement('i');
        check.setAttribute('aria-hidden', 'true');
        check.textContent = '\u2713';
        row.append(label, check);
        fragment.append(row);
    }
    menu.replaceChildren(fragment);
}

function openDashboardSelect(state) {
    for (const other of document.querySelectorAll('.aria-select-menu:not([hidden])')) {
        if (other !== state.menu) other.hidden = true;
    }
    renderDashboardSelect(state);
    state.menu.hidden = false;
    state.trigger.setAttribute('aria-expanded', 'true');
    updateDashboardSelectPosition(state);
    state.menu.querySelector('[aria-selected="true"]')?.focus();
}

function enhanceDashboardSelect(select) {
    if (select.dataset.ariaSelectEnhanced) return;
    select.dataset.ariaSelectEnhanced = 'true';
    const label = select.closest('.setting-row')?.querySelector('.setting-label')?.textContent.trim()
        || [...(select.labels || [])].map(item => {
            const namedSpan = item.querySelector('.setting-label, span');
            if (namedSpan) return namedSpan.textContent.trim();
            return [...item.childNodes].filter(node => node.nodeType === Node.TEXT_NODE).map(node => node.textContent.trim()).filter(Boolean).join(' ');
        }).filter(Boolean).join(' ')
        || select.getAttribute('aria-label')
        || select.id;
    const state = { select, label, trigger: null, menu: null };
    const root = document.createElement('span');
    root.className = `aria-select-root${select.classList.contains('small') ? ' is-small' : ''}`;
    const trigger = document.createElement('button');
    trigger.className = 'aria-select-trigger';
    trigger.type = 'button';
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.id = `${select.id || 'dashboardSelect'}Trigger`;
    const menu = document.createElement('div');
    menu.className = 'aria-select-menu';
    menu.id = `${select.id || 'dashboardSelect'}Menu${++_dashboardSelectSequence}`;
    menu.setAttribute('role', 'listbox');
    menu.setAttribute('aria-label', label);
    menu.hidden = true;
    trigger.setAttribute('aria-controls', menu.id);
    state.trigger = trigger;
    state.menu = menu;
    select.insertAdjacentElement('afterend', root);
    root.append(trigger);
    document.body.append(menu);
    select.classList.add('aria-select-native');
    select.tabIndex = -1;
    select.setAttribute('aria-hidden', 'true');
    for (const associatedLabel of [...(select.labels || [])]) associatedLabel.htmlFor = trigger.id;
    _dashboardSelectStates.set(select, state);

    trigger.addEventListener('click', () => {
        if (menu.hidden) openDashboardSelect(state);
        else closeDashboardSelect(state);
    });
    trigger.addEventListener('keydown', event => {
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault();
            openDashboardSelect(state);
        }
    });
    menu.addEventListener('click', event => {
        const option = event.target.closest('[role="option"]');
        if (!option || option.disabled) return;
        select.value = option.dataset.value;
        select.dispatchEvent(new Event('change', { bubbles: true }));
        renderDashboardSelect(state);
        closeDashboardSelect(state, true);
    });
    menu.addEventListener('keydown', event => {
        const options = [...menu.querySelectorAll('[role="option"]:not(:disabled)')];
        const index = options.indexOf(document.activeElement);
        let next = index;
        if (event.key === 'ArrowDown') next = Math.min(options.length - 1, index + 1);
        else if (event.key === 'ArrowUp') next = Math.max(0, index - 1);
        else if (event.key === 'Home') next = 0;
        else if (event.key === 'End') next = options.length - 1;
        else if (event.key === 'Escape') {
            event.preventDefault();
            closeDashboardSelect(state, true);
            return;
        } else return;
        event.preventDefault();
        options[next]?.focus();
    });
    select.addEventListener('change', () => renderDashboardSelect(state));
    const observer = new MutationObserver(() => renderDashboardSelect(state));
    observer.observe(select, { childList: true, subtree: true, attributes: true, attributeFilter: ['disabled', 'label', 'value'] });
    state.observer = observer;
    renderDashboardSelect(state);
}

function refreshDashboardSelects() {
    document.querySelectorAll('select').forEach(enhanceDashboardSelect);
    for (const select of document.querySelectorAll('select.aria-select-native')) {
        const state = _dashboardSelectStates.get(select);
        if (state) renderDashboardSelect(state);
    }
}

function watchDashboardSelects() {
    const observer = new MutationObserver(records => {
        for (const record of records) {
            for (const node of record.addedNodes) {
                if (!(node instanceof Element)) continue;
                if (node.matches('select')) enhanceDashboardSelect(node);
                node.querySelectorAll('select').forEach(enhanceDashboardSelect);
            }
        }
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
}

document.addEventListener('pointerdown', event => {
    for (const select of document.querySelectorAll('select.aria-select-native')) {
        const state = _dashboardSelectStates.get(select);
        if (state && !state.menu.hidden && !state.menu.contains(event.target) && !state.trigger.contains(event.target)) {
            closeDashboardSelect(state);
        }
    }
});
window.addEventListener('resize', () => {
    for (const select of document.querySelectorAll('select.aria-select-native')) {
        const state = _dashboardSelectStates.get(select);
        if (state && !state.menu.hidden) updateDashboardSelectPosition(state);
    }
});
window.addEventListener('scroll', () => {
    for (const select of document.querySelectorAll('select.aria-select-native')) {
        const state = _dashboardSelectStates.get(select);
        if (state && !state.menu.hidden) updateDashboardSelectPosition(state);
    }
}, true);

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        refreshDashboardSelects();
        watchDashboardSelects();
    }, { once: true });
} else {
    refreshDashboardSelects();
    watchDashboardSelects();
}

// ── Live Chat Support System ─────────────────────────────────────────────────
let _chatState = {
    sessions: [],
    currentSessionId: null,
    autoRefreshInterval: null
};

async function loadChat() {
    try {
        const chatLayout = document.getElementById('chat-layout') || document.querySelector('.chat-layout');
        if (!chatLayout) return;

        loadChatSessions();
        
        // Set up auto-refresh
        if (_chatState.autoRefreshInterval) clearInterval(_chatState.autoRefreshInterval);
        _chatState.autoRefreshInterval = setInterval(loadChatSessions, 3000);
    } catch (e) {
        console.error('[Chat] Load error:', e);
    }
}

async function loadChatSessions() {
    try {
        const sessionsList = document.getElementById('chatSessionsList');
        if (!sessionsList) return;
        
        const res = await fetchJSON('/api/chat/sessions');
        if (!res || res.error) return;
        
        _chatState.sessions = res.sessions || [];
        
        // Clear and rebuild list
        sessionsList.innerHTML = '';
        
        if (_chatState.sessions.length === 0) {
            sessionsList.innerHTML = '<div style="padding:12px;text-align:center;color:var(--muted);font-size:0.9em">No active chats</div>';
            return;
        }
        
        _chatState.sessions.forEach(session => {
            const item = document.createElement('div');
            item.className = 'chat-session-item' + (session.session_id === _chatState.currentSessionId ? ' active' : '');
            item.dataset.sessionId = session.session_id;
            item.onclick = () => openChatSession(session.session_id, item);
            
            const unreadCount = (session.unread_count || 0);
            const unreadBadge = unreadCount > 0 ? `<span class="unread-badge">${unreadCount}</span>` : '';
            
            item.innerHTML = `
                <div class="session-user">
                    <strong>${escapeHtml(session.username)}</strong>
                    ${unreadBadge}
                </div>
                <div class="session-meta" style="font-size:0.8em;color:var(--muted)">
                    ${session.resolved ? '<span style="color:#ff4757">Resolved</span>' : '<span style="color:#2ed573">Active</span>'}
                    • ${formatTime(session.last_updated)}
                </div>
            `;
            
            sessionsList.appendChild(item);
        });

        if (_chatState.currentSessionId) {
            const activeItem = Array.from(sessionsList.children).find(
                item => item.dataset.sessionId === _chatState.currentSessionId
            );
            if (activeItem) {
                await openChatSession(_chatState.currentSessionId, activeItem);
            }
        }
    } catch (e) {
        console.error('[Chat] Load sessions error:', e);
    }
}

async function openChatSession(sessionId, clickedItem = null) {
    try {
        _chatState.currentSessionId = sessionId;
        
        const chatViewer = document.getElementById('chatViewer');
        const emptyState = document.getElementById('chatEmptyState');
        const messagesContainer = document.getElementById('chatMessages');
        
        if (!chatViewer || !messagesContainer) return;
        
        // Show viewer, hide empty state
        chatViewer.style.display = 'flex';
        emptyState.style.display = 'none';
        
        // Update active highlight
        document.querySelectorAll('.chat-session-item').forEach(item => {
            item.classList.remove('active');
        });
        if (clickedItem) clickedItem.classList.add('active');
        
        // Find session data
        const session = _chatState.sessions.find(s => s.session_id === sessionId);
        if (!session) return;
        
        // Update header
        const header = document.querySelector('.chat-viewer-header');
        if (header) {
            const username = document.querySelector('.chat-viewer-username');
            const userId = document.querySelector('.chat-viewer-userid');
            
            if (username) username.textContent = session.username;
            if (userId) userId.textContent = `ID: ${session.user_id}`;
        }
        
        // Load messages
        const msgRes = await fetchJSON(`/api/chat/messages/${sessionId}`);
        if (!msgRes || msgRes.error) {
            messagesContainer.innerHTML = '<div style="padding:12px;color:var(--muted)">Failed to load messages</div>';
            return;
        }
        
        const messages = msgRes.messages || [];
        messagesContainer.innerHTML = '';
        
        if (messages.length === 0) {
            messagesContainer.innerHTML = '<div style="padding:12px;color:var(--muted);text-align:center">No messages yet</div>';
        } else {
            messages.forEach(msg => {
                const msgEl = document.createElement('div');
                msgEl.className = `chat-message ${msg.from === 'admin' ? 'admin' : 'user'}`;
                msgEl.innerHTML = `
                    <div class="msg-content">${escapeHtml(msg.text)}</div>
                    <div class="msg-time">${new Date(msg.ts * 1000).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</div>
                `;
                messagesContainer.appendChild(msgEl);
            });
        }
        
        // Auto-scroll to bottom
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
        // Update input field data
        const input = document.getElementById('chatInput');
        if (input) input.dataset.sessionId = sessionId;
        
    } catch (e) {
        console.error('[Chat] Open session error:', e);
    }
}

function closeChatViewer() {
    const chatViewer = document.getElementById('chatViewer');
    const emptyState = document.getElementById('chatEmptyState');
    
    if (chatViewer) chatViewer.style.display = 'none';
    if (emptyState) emptyState.style.display = 'flex';
    
    _chatState.currentSessionId = null;
    
    document.querySelectorAll('.chat-session-item').forEach(item => {
        item.classList.remove('active');
    });
}

async function sendChatMessage() {
    try {
        const input = document.getElementById('chatInput');
        if (!input || !input.value.trim()) return;
        
        const sessionId = input.dataset.sessionId;
        if (!sessionId) {
            showToast('Error', 'No session selected', 'err');
            return;
        }
        
        const message = input.value.trim();
        input.value = '';
        
        const res = await postJSON('/api/chat/send', {
            session_id: sessionId,
            message: message
        });
        
        if (res && res.ok) {
            // Reload messages
            const msgRes = await fetchJSON(`/api/chat/messages/${sessionId}`);
            if (msgRes && msgRes.messages) {
                const messagesContainer = document.getElementById('chatMessages');
                messagesContainer.innerHTML = '';
                
                msgRes.messages.forEach(msg => {
                    const msgEl = document.createElement('div');
                    msgEl.className = `chat-message ${msg.from === 'admin' ? 'admin' : 'user'}`;
                    msgEl.innerHTML = `
                        <div class="msg-content">${escapeHtml(msg.text)}</div>
                        <div class="msg-time">${new Date(msg.ts * 1000).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</div>
                    `;
                    messagesContainer.appendChild(msgEl);
                });
                
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }
        } else {
            showToast('Error', res?.message || 'Failed to send message', 'err');
        }
    } catch (e) {
        console.error('[Chat] Send message error:', e);
        showToast('Error', 'Failed to send message', 'err');
    }
}

async function resolveChat() {
    try {
        if (!_chatState.currentSessionId) return;
        
        if (!confirm('Mark this chat as resolved?')) return;
        
        const res = await postJSON('/api/chat/resolve', {
            session_id: _chatState.currentSessionId
        });
        
        if (res && res.ok) {
            showToast('Success', 'Chat marked as resolved', 'ok');
            closeChatViewer();
            loadChatSessions();
        } else {
            showToast('Error', res?.message || 'Failed to resolve chat', 'err');
        }
    } catch (e) {
        console.error('[Chat] Resolve error:', e);
        showToast('Error', 'Failed to resolve chat', 'err');
    }
}

// Chat input send button
document.addEventListener('DOMContentLoaded', () => {
    const sendBtn = document.getElementById('chatSendBtn');
    const input = document.getElementById('chatInput');
    const closeBtn = document.getElementById('chatCloseBtn');
    const resolveBtn = document.getElementById('chatResolveBtn');
    
    if (sendBtn) sendBtn.addEventListener('click', sendChatMessage);
    if (input) input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage();
        }
    });
    if (closeBtn) closeBtn.addEventListener('click', closeChatViewer);
    if (resolveBtn) resolveBtn.addEventListener('click', resolveChat);
});

setInterval(() => {
    refreshNotificationCenter();
}, 7000);

function renderMessageLoggerState(data) {
    const config = data.config || {};
    const toggles = {
        loggerEnabled: 'enabled',
        loggerMentions: 'mentions',
        loggerEdits: 'edits',
        loggerDeletes: 'deletes',
        loggerIgnoreSelf: 'ignore_self',
    };
    for (const [id, key] of Object.entries(toggles)) {
        const input = document.getElementById(id);
        if (input) input.checked = Boolean(config[key]);
    }

    const badge = document.getElementById('loggerStateBadge');
    if (badge) {
        badge.textContent = config.enabled ? 'Enabled' : 'Disabled';
        badge.className = `badge ${config.enabled ? 'badge-ok' : 'badge-off'}`;
    }
    const scopeMode = document.getElementById('loggerScopeMode');
    const scopeId = document.getElementById('loggerScopeId');
    if (scopeMode) scopeMode.value = config.scope?.mode || 'all';
    if (scopeId) {
        scopeId.value = config.scope?.id || '';
        scopeId.hidden = !['guild', 'channel'].includes(scopeMode?.value);
    }

    const keywordList = document.getElementById('loggerKeywordList');
    if (keywordList) {
        keywordList.replaceChildren();
        for (const keyword of config.keywords || []) {
            const chip = document.createElement('span');
            chip.className = 'logger-keyword-chip';
            const label = document.createElement('span');
            label.textContent = keyword;
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.textContent = '×';
            remove.setAttribute('aria-label', `Remove keyword ${keyword}`);
            remove.addEventListener('click', () => removeLoggerKeyword(keyword));
            chip.append(label, remove);
            keywordList.appendChild(chip);
        }
    }

    const feed = Array.isArray(data.feed) ? data.feed : [];
    const feedBody = document.getElementById('loggerFeedBody');
    const count = document.getElementById('loggerFeedCount');
    if (count) count.textContent = `${feed.length} event${feed.length === 1 ? '' : 's'}`;
    if (!feedBody) return;
    feedBody.replaceChildren();
    if (!feed.length) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.className = 'empty-row';
        cell.colSpan = 5;
        cell.textContent = config.enabled ? 'No matching events yet.' : 'Logger is disabled.';
        row.appendChild(cell);
        feedBody.appendChild(row);
        return;
    }

    const labels = { mention: 'Mention', keyword: 'Keyword', edit: 'Edited', delete: 'Deleted' };
    for (const item of feed) {
        const row = document.createElement('tr');
        const values = [
            labels[item.kind] || item.kind || 'Event',
            item.author || 'Unknown',
            item.content || (item.kind === 'edit' ? item.after : '') || '(no text)',
            item.guild_id ? `Server ${item.guild_id} · Channel ${item.channel_id}` : `DM · ${item.channel_id}`,
            item.ts ? new Date(Number(item.ts) * 1000).toLocaleString() : '—',
        ];
        for (const value of values) {
            const cell = document.createElement('td');
            cell.textContent = value;
            row.appendChild(cell);
        }
        if (item.before) row.title = `Before edit: ${item.before}`;
        feedBody.appendChild(row);
    }
}

async function loadMessageLogger() {
    const data = await fetchJSON('/api/message-logger');
    if (data?.ok) renderMessageLoggerState(data);
}

async function saveMessageLoggerConfig(config) {
    const data = await postJSON('/api/message-logger', { action: 'config', config });
    if (!data?.ok) {
        showToast('Logger', data?.error || 'Settings could not be saved.', 'err');
        return;
    }
    renderMessageLoggerState(data);
}

async function addLoggerKeyword() {
    const input = document.getElementById('loggerKeywordInput');
    const keyword = (input?.value || '').trim();
    if (!keyword) return;
    const data = await postJSON('/api/message-logger', { action: 'keyword_add', keyword });
    if (!data?.ok) {
        showToast('Logger', data?.error || 'Keyword could not be added.', 'err');
        return;
    }
    input.value = '';
    renderMessageLoggerState(data);
}

async function removeLoggerKeyword(keyword) {
    const data = await postJSON('/api/message-logger', { action: 'keyword_remove', keyword });
    if (data?.ok) renderMessageLoggerState(data);
    else showToast('Logger', data?.error || 'Keyword could not be removed.', 'err');
}

async function clearMessageLoggerFeed() {
    if (!window.confirm('Clear the current message logger feed?')) return;
    const data = await postJSON('/api/message-logger', { action: 'clear' });
    if (data?.ok) renderMessageLoggerState(data);
    else showToast('Logger', data?.error || 'Feed could not be cleared.', 'err');
}

async function refreshMessageLogger() {
    await loadMessageLogger();
}

function renderCommandTools(data) {
    if (data?.anti_gc) {
        const enabled = document.getElementById('commandAgctEnabled');
        const blockCreators = document.getElementById('commandAgctBlockCreators');
        if (enabled) enabled.checked = Boolean(data.anti_gc.enabled);
        if (blockCreators) blockCreators.checked = Boolean(data.anti_gc.block_creators);
    }

    if (Array.isArray(data?.auto_replies)) {
        const body = document.getElementById('autoReplyBody');
        const count = document.getElementById('autoReplyCount');
        if (!body) return;
        body.replaceChildren();
        if (count) count.textContent = `${data.auto_replies.length} target${data.auto_replies.length === 1 ? '' : 's'}`;
        if (!data.auto_replies.length) {
            const row = document.createElement('tr');
            const cell = document.createElement('td');
            cell.colSpan = 3;
            cell.className = 'empty-row';
            cell.textContent = 'No auto-replies configured.';
            row.appendChild(cell);
            body.appendChild(row);
            return;
        }
        for (const reply of data.auto_replies) {
            const row = document.createElement('tr');
            for (const value of [reply.user_id, reply.message]) {
                const cell = document.createElement('td');
                cell.textContent = String(value ?? '');
                row.appendChild(cell);
            }
            const actionCell = document.createElement('td');
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'btn btn-danger-soft';
            remove.textContent = 'Remove';
            remove.dataset.autoReplyUserId = String(reply.user_id ?? '');
            actionCell.appendChild(remove);
            row.appendChild(actionCell);
            body.appendChild(row);
        }
    }
}

async function loadCommandTools() {
    const data = await fetchJSON('/api/command-tools');
    if (data?.ok) {
        renderCommandTools(data);
        return;
    }
    const message = document.getElementById('commandToolsMsg');
    if (message) message.textContent = data?.error || 'Command controls could not be loaded.';
}

async function saveCommandTool(action, value) {
    const result = await postJSON('/api/command-tools', { action, value });
    if (!result?.ok) {
        showToast('Command Controls', result?.error || 'The change could not be saved.', 'err');
        await loadCommandTools();
        return false;
    }
    renderCommandTools(result);
    const message = document.getElementById('commandToolsMsg');
    if (message) message.textContent = 'Protection setting updated for this session.';
    return true;
}

async function addCommandAutoReply() {
    const userInput = document.getElementById('autoReplyUserId');
    const messageInput = document.getElementById('autoReplyMessage');
    const userId = (userInput?.value || '').trim();
    const reply = (messageInput?.value || '').trim();
    if (!/^\d{1,20}$/.test(userId) || !reply) {
        showToast('Auto-reply', 'Enter a numeric user ID and a reply message.', 'err');
        return;
    }
    const data = await postJSON('/api/command-tools', {
        action: 'auto_reply_add',
        user_id: userId,
        message: reply,
    });
    if (!data?.ok) {
        showToast('Auto-reply', data?.error || 'The auto-reply could not be saved.', 'err');
        return;
    }
    if (messageInput) messageInput.value = '';
    renderCommandTools(data);
    showToast('Auto-reply', data.message || 'Auto-reply saved.', 'ok');
}

async function removeCommandAutoReply(userId) {
    const data = await postJSON('/api/command-tools', {
        action: 'auto_reply_remove',
        user_id: userId,
    });
    if (!data?.ok) {
        showToast('Auto-reply', data?.error || 'The auto-reply could not be removed.', 'err');
        return;
    }
    renderCommandTools(data);
    showToast('Auto-reply', data.message || 'Auto-reply removed.', 'ok');
}

setInterval(() => {
    if (document.querySelector('.nav-item.active')?.dataset.section === 'logger') {
        loadMessageLogger();
    }
}, 5000);

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('commandAgctEnabled')?.addEventListener('change', event => {
        saveCommandTool('antigc_enabled', event.currentTarget.checked);
    });
    document.getElementById('commandAgctBlockCreators')?.addEventListener('change', event => {
        saveCommandTool('antigc_block_creators', event.currentTarget.checked);
    });
    document.getElementById('addAutoReplyButton')?.addEventListener('click', addCommandAutoReply);
    document.getElementById('autoReplyBody')?.addEventListener('click', event => {
        const button = event.target.closest('[data-auto-reply-user-id]');
        if (button) removeCommandAutoReply(button.dataset.autoReplyUserId);
    });

    const toggleMap = {
        loggerEnabled: 'enabled',
        loggerMentions: 'mentions',
        loggerEdits: 'edits',
        loggerDeletes: 'deletes',
        loggerIgnoreSelf: 'ignore_self',
    };
    for (const [id, key] of Object.entries(toggleMap)) {
        document.getElementById(id)?.addEventListener('change', event => {
            saveMessageLoggerConfig({ [key]: event.currentTarget.checked });
        });
    }

    const scopeMode = document.getElementById('loggerScopeMode');
    const scopeId = document.getElementById('loggerScopeId');
    const saveScope = () => {
        const mode = scopeMode?.value || 'all';
        if (scopeId) scopeId.hidden = !['guild', 'channel'].includes(mode);
        saveMessageLoggerConfig({ scope: { mode, id: scopeId?.value || '' } });
    };
    scopeMode?.addEventListener('change', saveScope);
    scopeId?.addEventListener('change', saveScope);
    document.getElementById('loggerKeywordInput')?.addEventListener('keydown', event => {
        if (event.key === 'Enter') {
            event.preventDefault();
            addLoggerKeyword();
        }
    });
});

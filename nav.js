(function () {
    // لا تعمل إذا كنا على صفحة login
    if (window.location.pathname === '/login') return;

    const ALL_LINKS = [
        { href: '/', page: 'control', icon: 'tune', label: 'Control', sub: 'Motor Commands', adminOnly: false },
        { href: '/monitor', page: 'monitor', icon: 'monitor', label: 'Monitor', sub: '3D Visualization', adminOnly: false },
        { href: '/admin', page: 'admin', icon: 'admin_panel_settings', label: 'Admin', sub: 'User Management', adminOnly: true },
        { href: '/logs', page: 'logs', icon: 'receipt_long', label: 'Logs', sub: 'Activity Log', adminOnly: true },
        { href: '/sensor.html', page: 'sensor', icon: 'sensors', label: 'Sensors', sub: 'Encoder & Limits', adminOnly: false },
        { href: '/torque_dashboard.html', page: 'torque_dashboard', icon: 'speed', label: 'Torque', sub: 'Load Analysis', adminOnly: false },
        { href: '/robot_programmer.html', page: 'robot_programmer', icon: 'code', label: 'Robot Programmer', sub: 'Programming Interface', adminOnly: false },
        { href: '/torque_ai_dashboard.html', page: 'torque_ai_dashboard', icon: 'psychology', label: 'AI Torque', sub: 'Smart Load Analysis', adminOnly: false },
        { href: '/data_explorer.html', page: 'data_explorer', icon: 'data_exploration', label: 'Dataset', sub: 'View Training Data', adminOnly: false },
        { href: '/current_sensor.html', page: 'current_sensor', icon: 'bolt', label: 'Current', sub: 'Motor Current Monitor', adminOnly: false },

    ];

    const CUR = window.location.pathname.replace(/\/$/, '') || '/';

    ['https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600&display=swap',
        'https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap']
        .forEach(h => {
            if (!document.querySelector(`link[href="${h}"]`)) {
                const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = h;
                document.head.appendChild(l);
            }
        });

    const css = document.createElement('style');
    css.textContent = `
:root{--nw:220px;--nwc:64px}
.msym{font-family:'Material Symbols Outlined';font-variation-settings:'FILL' 0,'wght' 200,'GRAD' 0,'opsz' 24;font-style:normal;line-height:1;user-select:none}
#arm-nav{position:fixed;top:0;left:0;bottom:0;width:var(--nw);background:rgba(9,11,15,.98);border-right:1px solid rgba(59,73,76,.25);display:flex;flex-direction:column;z-index:1000;transition:width .25s cubic-bezier(.4,0,.2,1);backdrop-filter:blur(16px);overflow:hidden}
#arm-nav.col{width:var(--nwc)}
body{padding-left:var(--nw)!important;transition:padding-left .25s cubic-bezier(.4,0,.2,1)}
body.nav-col{padding-left:var(--nwc)!important}

/* Logo */
.nv-logo{padding:18px 16px;border-bottom:1px solid rgba(59,73,76,.2);display:flex;align-items:center;gap:12px;flex-shrink:0}
.nv-logo-ico{font-size:20px;color:#00e5ff;flex-shrink:0}
.nv-logo-txt{font-family:'Space Grotesk',sans-serif;font-size:.72rem;font-weight:700;letter-spacing:.14em;color:#c3f5ff;text-transform:uppercase;white-space:nowrap;transition:opacity .2s}
.nv-logo-txt em{color:#b9f61d;font-style:normal}
#arm-nav.col .nv-logo-txt{opacity:0;pointer-events:none}

/* Toggle button */
.nv-tog{position:absolute;top:16px;right:-11px;width:22px;height:22px;background:#0d0f14;border:1px solid rgba(59,73,76,.5);border-radius:50%;display:flex;align-items:center;justify-content:center;cursor:pointer;z-index:10;transition:border-color .15s}
.nv-tog:hover{border-color:#00e5ff}
.nv-tog-ico{font-size:14px;color:#849396;transition:transform .25s,color .15s}
.nv-tog:hover .nv-tog-ico{color:#00e5ff}
#arm-nav.col .nv-tog-ico{transform:rotate(180deg)}

/* Nav links */
.nv-links{flex:1;padding:10px 0;overflow-y:auto;overflow-x:hidden}
.nv-link{display:flex;align-items:center;gap:12px;padding:10px 16px;text-decoration:none;position:relative;transition:background .1s;white-space:nowrap;overflow:hidden}
.nv-link:hover{background:rgba(0,229,255,.04)}
.nv-link.active{background:rgba(0,229,255,.07)}
.nv-link.active::before{content:'';position:absolute;left:0;top:0;bottom:0;width:2px;background:#00e5ff}
.nv-link-ico{font-size:18px;flex-shrink:0;color:#3d4f55;transition:color .15s}
.nv-link:hover .nv-link-ico{color:#849396}
.nv-link.active .nv-link-ico{color:#00e5ff}
.nv-link-txt{display:flex;flex-direction:column;gap:1px;transition:opacity .18s}
#arm-nav.col .nv-link-txt{opacity:0;pointer-events:none}
.nv-link-lbl{font-family:'Space Grotesk',sans-serif;font-size:.65rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#5a6e74;transition:color .15s}
.nv-link:hover .nv-link-lbl,.nv-link.active .nv-link-lbl{color:#c3f5ff}
.nv-link-sub{font-family:'Inter',sans-serif;font-size:.55rem;color:#2a3840}
.nv-link.active .nv-link-sub{color:rgba(0,229,255,.3)}
#arm-nav.col .nv-link::after{content:attr(data-label);position:absolute;left:calc(var(--nwc) + 8px);top:50%;transform:translateY(-50%);background:#0d0f14;border:1px solid rgba(59,73,76,.5);color:#c3f5ff;font-family:'Space Grotesk',sans-serif;font-size:.62rem;letter-spacing:.1em;text-transform:uppercase;padding:5px 10px;white-space:nowrap;opacity:0;pointer-events:none;transition:opacity .15s;z-index:2000}
#arm-nav.col .nv-link:hover::after{opacity:1}

/* Status dots */
.nv-status{padding:8px 16px;border-top:1px solid rgba(59,73,76,.15);flex-shrink:0;display:flex;flex-direction:column;gap:4px}
.nv-st-row{display:flex;align-items:center;gap:8px}
.nv-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0;background:#2a3840;transition:all .3s}
.nv-dot.ok{background:#b9f61d;box-shadow:0 0 6px #b9f61d}
.nv-dot.err{background:#ff3366;box-shadow:0 0 6px #ff3366}
.nv-st-lbl{font-family:'Space Grotesk',sans-serif;font-size:.55rem;letter-spacing:.1em;text-transform:uppercase;color:#2a3840;white-space:nowrap;transition:opacity .18s}
#arm-nav.col .nv-st-lbl{opacity:0}

/* Profile section */
.nv-profile{padding:10px 12px;border-top:1px solid rgba(59,73,76,.15);flex-shrink:0;position:relative}
.nv-prof-btn{display:flex;align-items:center;gap:10px;cursor:pointer;padding:6px 4px;border:1px solid transparent;transition:border-color .15s;user-select:none}
.nv-prof-btn:hover{border-color:rgba(0,229,255,.15)}

/* Avatar circle */
.nv-av{
  width:36px;height:36px;border-radius:50%;
  border:2px solid rgba(0,229,255,.25);
  background:#0d1420;flex-shrink:0;overflow:hidden;
  display:flex;align-items:center;justify-content:center;
  transition:border-color .2s;position:relative;
}
.nv-prof-btn:hover .nv-av{border-color:rgba(0,229,255,.6)}
.nv-av img{width:100%;height:100%;object-fit:cover;border-radius:50%;display:block}
.nv-av-ini{
  font-family:'Space Grotesk',sans-serif;font-size:.7rem;font-weight:700;
  color:#00e5ff;text-transform:uppercase;letter-spacing:.04em;
}
.nv-av-ico{font-size:18px;color:#2a3840}

.nv-prof-info{flex:1;overflow:hidden;transition:opacity .18s;min-width:0}
#arm-nav.col .nv-prof-info{opacity:0;pointer-events:none}
.nv-prof-name{font-family:'Space Grotesk',sans-serif;font-size:.68rem;font-weight:600;color:#bac9cc;text-transform:uppercase;letter-spacing:.06em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.nv-prof-role{font-family:'Space Grotesk',sans-serif;font-size:.56rem;letter-spacing:.08em;text-transform:uppercase;margin-top:2px}
.nv-prof-role.admin{color:#b9f61d}
.nv-prof-role.operator{color:#00e5ff}
.nv-prof-role.viewer{color:#849396}
.nv-caret{font-size:14px;color:#3d4f55;transition:opacity .18s,transform .2s}
#arm-nav.col .nv-caret{opacity:0}
.nv-dd.open ~ .nv-prof-btn .nv-caret{transform:rotate(180deg)}

/* Dropdown */
.nv-dd{position:absolute;bottom:calc(100% + 4px);left:8px;right:8px;background:#0d1015;border:1px solid rgba(59,73,76,.4);padding:6px;display:none;flex-direction:column;gap:2px;z-index:2000;box-shadow:0 -8px 24px rgba(0,0,0,.5)}
.nv-dd.open{display:flex}
.nv-dd-user{padding:10px 10px 8px;display:flex;align-items:center;gap:10px;border-bottom:1px solid rgba(59,73,76,.2);margin-bottom:4px}
.nv-dd-av{width:38px;height:38px;border-radius:50%;border:2px solid rgba(0,229,255,.3);background:#0d1420;overflow:hidden;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.nv-dd-av img{width:100%;height:100%;object-fit:cover;border-radius:50%;display:block}
.nv-dd-av-ini{font-family:'Space Grotesk',sans-serif;font-size:.72rem;font-weight:700;color:#00e5ff;text-transform:uppercase}
.nv-dd-uname{font-family:'Space Grotesk',sans-serif;font-size:.68rem;font-weight:600;color:#c3f5ff;letter-spacing:.06em;text-transform:uppercase}
.nv-dd-urole{font-size:.56rem;font-family:'Space Grotesk',sans-serif;letter-spacing:.08em;text-transform:uppercase;margin-top:2px}
.nv-dd-urole.admin{color:#b9f61d}
.nv-dd-urole.operator{color:#00e5ff}
.nv-dd-urole.viewer{color:#849396}
.nv-dd-item{display:flex;align-items:center;gap:8px;padding:8px 10px;cursor:pointer;text-decoration:none;transition:background .1s}
.nv-dd-item:hover{background:rgba(0,229,255,.05)}
.nv-dd-item .msym{font-size:16px;color:#3d4f55}
.nv-dd-item:hover .msym{color:#00e5ff}
.nv-dd-lbl{font-family:'Space Grotesk',sans-serif;font-size:.62rem;letter-spacing:.1em;text-transform:uppercase;color:#5a6e74}
.nv-dd-item:hover .nv-dd-lbl{color:#c3f5ff}
.nv-dd-sep{height:1px;background:rgba(59,73,76,.3);margin:3px 0}
.nv-dd-item.danger .msym{color:rgba(255,51,102,.4)}
.nv-dd-item.danger:hover .msym{color:#ff3366}
.nv-dd-item.danger .nv-dd-lbl{color:rgba(255,51,102,.4)}
.nv-dd-item.danger:hover .nv-dd-lbl{color:#ff3366}
.nv-links::-webkit-scrollbar{width:2px}
.nv-links::-webkit-scrollbar-thumb{background:#1a2530}
`;
    document.head.appendChild(css);

    // ── Build nav HTML ───────────────────────────────────────────────
    const nav = document.createElement('nav');
    nav.id = 'arm-nav';
    const collapsed = localStorage.getItem('nav_col') === '1';
    if (collapsed) { nav.classList.add('col'); document.body.classList.add('nav-col'); }

    nav.innerHTML = `
<div class="nv-logo">
  <span class="msym nv-logo-ico">precision_manufacturing</span>
  <div class="nv-logo-txt">ARM<em>.</em>CTRL</div>
</div>
<button class="nv-tog" id="nv-tog"><span class="msym nv-tog-ico">chevron_left</span></button>
<div class="nv-links" id="nv-links"></div>
<div class="nv-status">
  <div class="nv-st-row"><div class="nv-dot" id="nv-uart"></div><span class="nv-st-lbl">UART</span></div>
  <div class="nv-st-row"><div class="nv-dot" id="nv-ros"></div><span class="nv-st-lbl">ROS2</span></div>
</div>
<div class="nv-profile">
  <div class="nv-dd" id="nv-dd">
    <div class="nv-dd-user">
      <div class="nv-dd-av" id="nv-dd-av"><span class="msym" style="font-size:18px;color:#2a3840">person</span></div>
      <div>
        <div class="nv-dd-uname" id="nv-dd-un">—</div>
        <div class="nv-dd-urole" id="nv-dd-rl">—</div>
      </div>
    </div>
    <a class="nv-dd-item" href="/account">
      <span class="msym">manage_accounts</span>
      <span class="nv-dd-lbl">Account Settings</span>
    </a>
    <div class="nv-dd-sep"></div>
    <div class="nv-dd-item danger" id="nv-logout">
      <span class="msym">logout</span>
      <span class="nv-dd-lbl">Logout</span>
    </div>
  </div>
  <div class="nv-prof-btn" id="nv-pb">
    <div class="nv-av" id="nv-av">
      <span class="msym nv-av-ico">person</span>
    </div>
    <div class="nv-prof-info">
      <div class="nv-prof-name" id="nv-un">—</div>
      <div class="nv-prof-role" id="nv-rl">—</div>
    </div>
    <span class="msym nv-caret">expand_less</span>
  </div>
</div>`;

    document.body.insertBefore(nav, document.body.firstChild);

    // ── Toggle collapse ──────────────────────────────────────────────
    document.getElementById('nv-tog').addEventListener('click', () => {
        const c = nav.classList.toggle('col');
        document.body.classList.toggle('nav-col', c);
        localStorage.setItem('nav_col', c ? '1' : '0');
    });

    // ── Dropdown ─────────────────────────────────────────────────────
    const dd = document.getElementById('nv-dd');
    document.getElementById('nv-pb').addEventListener('click', e => {
        e.stopPropagation();
        dd.classList.toggle('open');
    });
    document.addEventListener('click', () => dd.classList.remove('open'));

    // ── Logout ───────────────────────────────────────────────────────
    document.getElementById('nv-logout').addEventListener('click', async () => {
        await fetch('/api/auth/logout', { method: 'POST' }).catch(() => { });
        location.replace('/login');
    });

    // ── Avatar helper ────────────────────────────────────────────────
    function setAvatar(avatarUrl, username) {
        const ini = (username || '?').slice(0, 2).toUpperCase();

        // sidebar avatar
        const avEl = document.getElementById('nv-av');
        if (avatarUrl) {
            avEl.innerHTML = `<img src="${avatarUrl}" alt="avatar" onerror="this.parentElement.innerHTML='<span class=nv-av-ini>${ini}</span>'"/>`;
        } else {
            avEl.innerHTML = `<span class="nv-av-ini">${ini}</span>`;
        }

        // dropdown avatar
        const ddAv = document.getElementById('nv-dd-av');
        if (avatarUrl) {
            ddAv.innerHTML = `<img src="${avatarUrl}" alt="avatar" onerror="this.parentElement.innerHTML='<span class=nv-dd-av-ini>${ini}</span>'"/>`;
        } else {
            ddAv.innerHTML = `<span class="nv-dd-av-ini">${ini}</span>`;
        }
    }

    // ── Load user info ───────────────────────────────────────────────
    async function loadUser() {
        try {
            const r = await fetch('/api/me');
            if (r.status === 401) { location.replace('/login'); return; }
            const d = await r.json();
            if (!d.ok) { location.replace('/login'); return; }

            const name = d.display_name || d.username || '—';
            const role = d.role || 'viewer';

            // sidebar text
            document.getElementById('nv-un').textContent = name.toUpperCase();
            const rl = document.getElementById('nv-rl');
            rl.textContent = role.toUpperCase();
            rl.className = 'nv-prof-role ' + role;

            // dropdown text
            document.getElementById('nv-dd-un').textContent = name;
            const ddRl = document.getElementById('nv-dd-rl');
            ddRl.textContent = role.toUpperCase();
            ddRl.className = 'nv-dd-urole ' + role;

            // avatar (with cache-busting timestamp already in avatar_url from server)
            setAvatar(d.avatar_url || null, d.username);

            // build nav links based on permissions
            const perms = d.permissions || {};
            const linksEl = document.getElementById('nv-links');
            linksEl.innerHTML = '';
            ALL_LINKS.forEach(lk => {
                const allowed = role === 'admin' || (!lk.adminOnly && perms[lk.page]);
                if (!allowed) return;
                const active = lk.href === '/'
                    ? (CUR === '' || CUR === '/')
                    : CUR.startsWith(lk.href);
                const a = document.createElement('a');
                a.href = lk.href;
                a.className = 'nv-link' + (active ? ' active' : '');
                a.dataset.label = lk.label;
                a.innerHTML = `
          <span class="msym nv-link-ico">${lk.icon}</span>
          <div class="nv-link-txt">
            <div class="nv-link-lbl">${lk.label}</div>
            <div class="nv-link-sub">${lk.sub}</div>
          </div>`;
                linksEl.appendChild(a);
            });

            window._armUser = d;
            window.dispatchEvent(new CustomEvent('arm:user', { detail: d }));
        } catch (e) {
            console.error('nav:', e);
        }
    }
    loadUser();

    // ── Health ping ──────────────────────────────────────────────────
    async function ping() {
        try {
            const d = await fetch('/api/health', { cache: 'no-store' }).then(r => r.json());
            document.getElementById('nv-uart').className = 'nv-dot ' + (d.uart ? 'ok' : 'err');
            document.getElementById('nv-ros').className = 'nv-dot ' + (d.ros ? 'ok' : 'err');
        } catch {
            ['nv-uart', 'nv-ros'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.className = 'nv-dot err';
            });
        }
    }
    ping();
    setInterval(ping, 5000);
})();
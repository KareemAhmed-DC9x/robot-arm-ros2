/**
 * auth_guard.js
 * Include this script in control.html and monitor.html.
 * Checks auth on load → redirects to /login if session expired.
 * Also adds a logout button to the header.
 */
(function () {
  // ── Check auth on page load ──────────────────────────────────
  fetch('/api/arm/status', { method: 'GET' })
    .then(r => {
      if (r.status === 401 || r.redirected) {
        window.location.replace('/login');
      }
    })
    .catch(() => {
      // server unreachable — stay, let socket handle it
    });

  // ── Add logout button after DOM ready ────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    const header = document.querySelector('header');
    if (!header) return;

    const btn = document.createElement('button');
    btn.innerHTML = `
      <span class="material-symbols-outlined" style="font-size:16px;vertical-align:middle;
            font-variation-settings:'FILL' 0,'wght' 200,'GRAD' 0,'opsz' 20">
        logout
      </span>
      <span style="font-size:9px;letter-spacing:.15em;vertical-align:middle;margin-left:5px;">
        LOGOUT
      </span>`;
    btn.title = 'Logout';
    btn.style.cssText = `
      display:flex; align-items:center; gap:4px;
      background:transparent; border:1px solid rgba(186,201,204,0.15);
      color:rgba(186,201,204,0.4); font-family:'Space Grotesk',sans-serif;
      padding:5px 12px; cursor:pointer; transition:all .15s;
      text-transform:uppercase;
    `;
    btn.addEventListener('mouseenter', () => {
      btn.style.borderColor = '#ff3366';
      btn.style.color = '#ff3366';
    });
    btn.addEventListener('mouseleave', () => {
      btn.style.borderColor = 'rgba(186,201,204,0.15)';
      btn.style.color = 'rgba(186,201,204,0.4)';
    });
    btn.addEventListener('click', async () => {
      await fetch('/api/logout', { method: 'POST' });
      window.location.replace('/login');
    });

    header.appendChild(btn);
  });
})();

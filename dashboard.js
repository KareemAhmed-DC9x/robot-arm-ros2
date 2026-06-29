// ════════════════════════════════════════════════════════════════
//  AI TORQUE DASHBOARD — main logic
//  Physics model: identical port of torque_dashboard.html's math.
//  AI model: calls the Flask inference_api.py /predict endpoint.
// ════════════════════════════════════════════════════════════════

// ---- Arm config (mirrors physics_model.py DEFAULT_CONFIG) ----
const ARM_CFG = {
  d1: 0.12, a2: 0.25, d4: 0.20, d6: 0.12,
  mass: [0.40, 0.30, 0.25, 0.15, 0.10, 0.05],
  gear: { J1: 4, J2: 4, J3: 1, J4: 3, J56: 2 },
  invertPitch: false,
  invertYaw: false,
  rated: [0.45, 1.90, 0.45, 1.90, 0.45, 0.45],
  // Joint limits (deg) — same placeholders as physics_model.py;
  // edit here AND there if you update them.
  jointLimitsDeg: [
    [-180, 180], [-90, 90], [-150, 150], [-180, 180], [-90, 90], [-180, 180],
  ],
  // ── Motor safety limits for AI speed/accel derivation ──
  maxSpeed: [1200, 800, 1200, 600, 1500, 1500], // steps/s per motor M1..M6
  maxAccel: [5000, 3000, 5000, 2000, 6000, 6000], // steps/s² per motor M1..M6
  safetyMargin: 0.85,   // do not exceed 85% of rated torque
  loadDerate: { light: 0.5, heavy: 3.0 },          // kg thresholds for load-based derating
};

const MOTOR_META = [
  { id: 'M1', joint: 'J4', jointName: 'Wrist Roll' },
  { id: 'M2', joint: 'J2', jointName: 'Shoulder' },
  { id: 'M3', joint: 'J3', jointName: 'Elbow' },
  { id: 'M4', joint: 'J1', jointName: 'Base' },
  { id: 'M5', joint: 'J5/J6', jointName: 'Wrist Diff Σ(+)' },
  { id: 'M6', joint: 'J5/J6', jointName: 'Wrist Diff Δ(−)' },
];
const JOINT_NAMES = ['J1 Base', 'J2 Shoulder', 'J3 Elbow', 'J4 Wrist Roll', 'J5 Wrist Pitch', 'J6 Wrist Yaw'];

// ════════════════════════════════════════════════════════════════
//  PHYSICS MODEL (ported 1:1 from torque_dashboard.html)
// ════════════════════════════════════════════════════════════════
function dhMatrix(t, d, a, al) {
  const ct = Math.cos(t), st = Math.sin(t), ca = Math.cos(al), sa = Math.sin(al);
  return [
    [ct, -st * ca, st * sa, a * ct],
    [st, ct * ca, -ct * sa, a * st],
    [0, sa, ca, d],
    [0, 0, 0, 1],
  ];
}
function matMul(A, B) {
  const out = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]];
  for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) { let s = 0; for (let k = 0; k < 4; k++) s += A[i][k] * B[k][j]; out[i][j] = s; }
  return out;
}
function cross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
function sub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
const I4 = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]];

function FK(q, dh) {
  const T01 = dhMatrix(q[0], dh.d1, 0, Math.PI / 2);
  const T02 = matMul(T01, dhMatrix(q[1], 0, dh.a2, 0));
  const T03 = matMul(T02, dhMatrix(q[2], 0, 0, Math.PI / 2));
  const T04 = matMul(T03, dhMatrix(q[3], dh.d4, 0, -Math.PI / 2));
  const T05 = matMul(T04, dhMatrix(q[4], 0, 0, Math.PI / 2));
  const T06 = matMul(T05, dhMatrix(q[5], dh.d6, 0, 0));
  const T = [I4, T01, T02, T03, T04, T05, T06];
  const Pe = [T06[0][3], T06[1][3], T06[2][3]];
  return { T, Pe };
}
function JAC(T, Pe) {
  const J = [[0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0]];
  for (let i = 0; i < 6; i++) {
    const z = [T[i][0][2], T[i][1][2], T[i][2][2]];
    const p = [T[i][0][3], T[i][1][3], T[i][2][3]];
    const lin = cross(z, sub(Pe, p));
    J[0][i] = lin[0]; J[1][i] = lin[1]; J[2][i] = lin[2];
    J[3][i] = z[0]; J[4][i] = z[1]; J[5][i] = z[2];
  }
  return J;
}
function GRAV(T, mL) {
  const G = [0, 0, 0, 0, 0, 0];
  const g = [0, 0, -9.81];
  for (let i = 0; i < 6; i++) {
    const Pcom = [
      (T[i][0][3] + T[i + 1][0][3]) / 2,
      (T[i][1][3] + T[i + 1][1][3]) / 2,
      (T[i][2][3] + T[i + 1][2][3]) / 2,
    ];
    for (let j = 0; j <= i; j++) {
      const z = [T[j][0][2], T[j][1][2], T[j][2][2]];
      const p = [T[j][0][3], T[j][1][3], T[j][2][3]];
      const col = cross(z, sub(Pcom, p));
      G[j] += mL[i] * (col[0] * g[0] + col[1] * g[1] + col[2] * g[2]);
    }
  }
  return G;
}
function jacTransposeForce(J, F) {
  const out = [0, 0, 0, 0, 0, 0];
  for (let k = 0; k < 6; k++) { let s = 0; for (let r = 0; r < 6; r++) s += J[r][k] * F[r]; out[k] = s; }
  return out;
}
function codeAnglesToJoints(pos, cfg) {
  const toRad = d => d * Math.PI / 180;
  const [m1, m2, m3, m4, m5, m6] = pos;
  const th1 = toRad(m4) / cfg.gear.J1;
  const th2 = toRad(m2) / cfg.gear.J2;
  const th3 = toRad(m3) / cfg.gear.J3;
  const th4 = toRad(m1) / cfg.gear.J4;
  const sP = cfg.invertPitch ? -1 : 1;
  const sY = cfg.invertYaw ? -1 : 1;
  const th5 = sP * (toRad(m5) + toRad(m6)) / (2 * cfg.gear.J56);
  const th6 = sY * (toRad(m5) - toRad(m6)) / (2 * cfg.gear.J56);
  return [th1, th2, th3, th4, th5, th6];
}
function jointTorqueToMotorTorque(tauJ, cfg) {
  const tauM = [0, 0, 0, 0, 0, 0];
  tauM[3] = tauJ[0] / cfg.gear.J1;
  tauM[1] = tauJ[1] / cfg.gear.J2;
  tauM[2] = tauJ[2] / cfg.gear.J3;
  tauM[0] = tauJ[3] / cfg.gear.J4;
  tauM[4] = (tauJ[4] + tauJ[5]) / (2 * cfg.gear.J56);
  tauM[5] = (tauJ[4] - tauJ[5]) / (2 * cfg.gear.J56);
  return tauM;
}
function physicsFromJointAngles(jointDeg, loadKg, cfg) {
  const toRad = d => d * Math.PI / 180;
  const q = jointDeg.map(toRad);
  const { T, Pe } = FK(q, cfg);
  const J = JAC(T, Pe);
  const G = GRAV(T, cfg.mass);
  const F = [0, 0, -loadKg * 9.81, 0, 0, 0];
  const JtF = jacTransposeForce(J, F);
  const tauJoint = G.map((g, i) => g + JtF[i]);
  return jointTorqueToMotorTorque(tauJoint, cfg);
}
function physicsFromMotorAngles(motorDeg, loadKg, cfg) {
  const q = codeAnglesToJoints(motorDeg, cfg);
  const { T, Pe } = FK(q, cfg);
  const J = JAC(T, Pe);
  const G = GRAV(T, cfg.mass);
  const F = [0, 0, -loadKg * 9.81, 0, 0, 0];
  const JtF = jacTransposeForce(J, F);
  const tauJoint = G.map((g, i) => g + JtF[i]);
  return { tauMotor: jointTorqueToMotorTorque(tauJoint, cfg), jointDeg: q.map(r => r * 180 / Math.PI) };
}

// ════════════════════════════════════════════════════════════════
//  AI → SAFE SPEED & ACCEL (anti-break / anti-stall logic)
// ════════════════════════════════════════════════════════════════
function calculateSafeSpeedAccel(motorIndex, aiTorqueNm, loadKg) {
  const rated = ARM_CFG.rated[motorIndex];
  const maxSpd = ARM_CFG.maxSpeed[motorIndex];
  const maxAcc = ARM_CFG.maxAccel[motorIndex];
  const absT = Math.abs(aiTorqueNm);
  const safeLimit = rated * ARM_CFG.safetyMargin;

  let u = absT / safeLimit;

  // ═══════════════════════════════════════════════
  // CONTINUOUS LOAD FACTOR — starts at 0 kg
  // ═══════════════════════════════════════════════
  // Heavier load = lower speed/accel (inverse-square-root curve)
  //   0g   → 1.00  (no reduction)
  //   19g  → 0.91  (light reduction)
  //   100g → 0.82
  //   500g → 0.60
  //   1kg  → 0.45
  //   3kg  → 0.25
  //   5kg  → 0.18
  //  10kg  → 0.12
  // ═══════════════════════════════════════════════
  const loadFactor = Math.max(0.05, 1.0 / (1 + Math.sqrt(loadKg * 5)));

  let speedFactor, accelFactor;
  if (u <= 0.30) {
    speedFactor = 1.00; accelFactor = 1.00;
  } else if (u <= 0.55) {
    speedFactor = 0.90; accelFactor = 0.95;
  } else if (u <= 0.75) {
    speedFactor = 0.70; accelFactor = 0.80;
  } else if (u <= 0.90) {
    speedFactor = 0.50; accelFactor = 0.60;
  } else if (u <= 1.00) {
    speedFactor = 0.30; accelFactor = 0.40;
  } else {
    speedFactor = 0.15; accelFactor = 0.20;
    u = Math.min(u, 2.0);
  }

  return {
    speed: Math.max(50, Math.round(maxSpd * speedFactor * loadFactor)),
    accel: Math.max(100, Math.round(maxAcc * accelFactor * loadFactor)),
    utilization: u,
    safe: u <= 1.0,
    factors: { speed: speedFactor, accel: accelFactor, load: loadFactor }
  };
}

// ════════════════════════════════════════════════════════════════
//  STATE
// ════════════════════════════════════════════════════════════════
const state = {
  motorPositions: [0, 0, 0, 0, 0, 0],
  jointAnglesDeg: [0, 0, 0, 0, 0, 0],
  manualMode: false,
  loadKg: 0.5,
  physicsTorque: [0, 0, 0, 0, 0, 0],
  aiTorque: null,
  aiSpeedAccel: [],
  aiControlParams: null,
  errorPct: [0, 0, 0, 0, 0, 0],
  apiConnected: false,
  apiModelName: null,
  history: { t: [], physics: [[], [], [], [], [], []], ai: [[], [], [], [], [], []] },
  maxHistoryPoints: 60,
};

// ════════════════════════════════════════════════════════════════
//  ROS2 SOCKET
// ════════════════════════════════════════════════════════════════
let socket;
try {
  socket = io({ transports: ['websocket'], withCredentials: true });
  socket.on('connect', () => setRosStatus(true));
  socket.on('disconnect', () => setRosStatus(false));
  socket.on('arm_status', (d) => {
    if (d && d.positions && !state.manualMode) {
      state.motorPositions = d.positions;
      document.getElementById('last-update').textContent =
        'Last update: ' + new Date().toTimeString().slice(0, 8);
      recompute();
    }
  });
} catch (e) {
  setRosStatus(false);
  console.warn('Socket.IO unavailable:', e);
}

function setRosStatus(ok) {
  const dot = document.getElementById('ros-dot');
  const label = document.getElementById('ros-label');
  dot.className = 'conn-dot ' + (ok ? 'ok' : 'err');
  label.textContent = 'ROS2: ' + (ok ? 'CONNECTED' : 'DISCONNECTED');
}

// ════════════════════════════════════════════════════════════════
//  AI INFERENCE API CALLS
// ════════════════════════════════════════════════════════════════
let apiPollTimer = null;

function setApiStatus(ok, modelName) {
  state.apiConnected = ok;
  const dot = document.getElementById('api-dot');
  const label = document.getElementById('api-label');
  dot.className = 'conn-dot ' + (ok ? 'ok' : 'err');
  label.textContent = 'AI API: ' + (ok ? 'CONNECTED (' + modelName + ')' : 'DISCONNECTED');
  document.getElementById('api-warn-banner').classList.toggle('hidden', ok);
  document.getElementById('active-model-pill').textContent = 'AI: ' + (ok ? modelName : '—');
}

async function checkApiHealth() {
  const base = document.getElementById('api-url').value.trim().replace(/\/$/, '');
  try {
    const res = await fetch(base + '/health', { method: 'GET' });
    if (!res.ok) throw new Error('bad status ' + res.status);
    const data = await res.json();
    state.apiModelName = data.model;
    setApiStatus(true, data.model);
  } catch (e) {
    setApiStatus(false, null);
  }
}

async function fetchAiPrediction(jointAnglesDeg, loadKg) {
  const base = document.getElementById('api-url').value.trim().replace(/\/$/, '');
  try {
    const res = await fetch(base + '/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ joint_angles_deg: jointAnglesDeg, load_kg: loadKg }),
    });
    if (!res.ok) throw new Error('bad status ' + res.status);
    const data = await res.json();
    return data;
  } catch (e) {
    if (state.apiConnected) setApiStatus(false, null);
    return null;
  }
}

function reconnectApi() {
  document.getElementById('footer-api-url').textContent = document.getElementById('api-url').value.trim();
  checkApiHealth();
}

// ════════════════════════════════════════════════════════════════
//  UI BUILD — comparison cards
// ════════════════════════════════════════════════════════════════
function buildCards() {
  const grid = document.getElementById('motor-grid');
  grid.innerHTML = MOTOR_META.map(m => `
    <div class="motor-card" id="card-${m.id}">
      <div class="card-head">
        <span class="motor-tag">${m.id}</span>
        <span class="joint-tag">${m.jointName} · ${m.joint}</span>
      </div>
      <div class="compare-row">
        <span class="compare-label"><span class="dot-phys"></span>Physics</span>
        <span class="compare-val phys" id="phys-${m.id}">0.000 N·m</span>
      </div>
      <div class="compare-row">
        <span class="compare-label"><span class="dot-ai"></span>AI Predicted</span>
        <span class="compare-val ai" id="ai-${m.id}">—</span>
      </div>
      <div class="err-row">
        <span class="err-label">Δ Torque</span>
        <span class="err-val ok" id="err-${m.id}">—</span>
      </div>
      <div class="bar-track"><div class="bar-fill" id="bar-${m.id}" style="width:0%;background:var(--green);"></div></div>
    </div>`).join('');
}

function errClass(pct) {
  if (pct === null || isNaN(pct)) return 'ok';
  if (pct >= 80) return 'bad';
  if (pct >= 40) return 'warn';
  return 'ok';
}
function errColor(cls) {
  return cls === 'bad' ? 'var(--red)' : cls === 'warn' ? 'var(--yellow)' : 'var(--green)';
}
function updateCards() {
  MOTOR_META.forEach((m, i) => {
    const physVal = state.physicsTorque[i];
    document.getElementById(`phys-${m.id}`).textContent = physVal.toFixed(3) + ' N·m';

    const card = document.getElementById(`card-${m.id}`);
    if (state.aiTorque) {
      const aiVal = state.aiTorque[i];
      const absError = Math.abs(aiVal - physVal);

      document.getElementById(`ai-${m.id}`).textContent = aiVal.toFixed(3) + ' N·m';

      const errEl = document.getElementById(`err-${m.id}`);
      errEl.textContent = absError.toFixed(4) + ' N·m';

      const maxTorque = Math.max(Math.abs(physVal), Math.abs(aiVal), 0.01);
      const normalizedError = Math.min(absError / maxTorque, 1.0);

      const barEl = document.getElementById(`bar-${m.id}`);
      barEl.style.width = (normalizedError * 100) + '%';

      const cls = errClass(normalizedError * 100);
      barEl.style.background = errColor(cls);
      errEl.className = 'err-val ' + cls;

      card.classList.toggle('overload', cls === 'bad');
    } else {
      document.getElementById(`ai-${m.id}`).textContent = '—';
      document.getElementById(`err-${m.id}`).textContent = '—';
      document.getElementById(`bar-${m.id}`).style.width = '0%';
      card.classList.remove('overload');
    }
  });
}

// ════════════════════════════════════════════════════════════════
//  AI CONTROL PANEL UI
// ════════════════════════════════════════════════════════════════
function buildAiControlGrid() {
  const grid = document.getElementById('ai-control-grid');
  if (!grid) return;
  grid.innerHTML = MOTOR_META.map(m => `
    <div class="motor-card" id="aicard-${m.id}">
      <div class="card-head">
        <span class="motor-tag">${m.id}</span>
        <span class="joint-tag">AI Safe Params</span>
      </div>
      <div class="compare-row">
        <span class="compare-label"><span class="dot-phys" style="background:var(--ai);"></span>Speed</span>
        <span class="compare-val ai" id="aispeed-${m.id}">—</span>
      </div>
      <div class="compare-row">
        <span class="compare-label"><span class="dot-ai" style="background:var(--accent2);"></span>Accel</span>
        <span class="compare-val phys" id="aiaccel-${m.id}" style="color:var(--accent2);">—</span>
      </div>
      <div class="err-row">
        <span class="err-label">Utilization</span>
        <span class="err-val ok" id="aiutil-${m.id}">—</span>
      </div>
      <div class="bar-track"><div class="bar-fill" id="aibar-${m.id}" style="width:0%;background:var(--green);"></div></div>
    </div>`).join('');
}

function updateAiControlCards() {
  const grid = document.getElementById('ai-control-grid');
  if (!grid) return;
  MOTOR_META.forEach((m, i) => {
    if (!state.aiSpeedAccel[i]) {
      document.getElementById(`aispeed-${m.id}`).textContent = '—';
      document.getElementById(`aiaccel-${m.id}`).textContent = '—';
      document.getElementById(`aiutil-${m.id}`).textContent = '—';
      document.getElementById(`aibar-${m.id}`).style.width = '0%';
      return;
    }
    const sa = state.aiSpeedAccel[i];
    document.getElementById(`aispeed-${m.id}`).textContent = sa.speed + ' steps/s';
    document.getElementById(`aiaccel-${m.id}`).textContent = sa.accel + ' steps/s²';

    const utilEl = document.getElementById(`aiutil-${m.id}`);
    utilEl.textContent = (sa.utilization * 100).toFixed(1) + '%';
    const cls = errClass(sa.utilization * 100);
    utilEl.className = 'err-val ' + cls;

    const bar = document.getElementById(`aibar-${m.id}`);
    bar.style.width = Math.min(sa.utilization * 100, 100) + '%';
    bar.style.background = errColor(cls);

    const card = document.getElementById(`aicard-${m.id}`);
    card.classList.toggle('overload', !sa.safe);
  });
}

function sendToControl() {
  if (!state.aiSpeedAccel || state.aiSpeedAccel.length === 0) {
    alert('No AI predictions yet. Connect API and wait for inference first.');
    return;
  }
  const payload = {
    timestamp: Date.now(),
    load_kg: state.loadKg,
    motors: state.aiSpeedAccel.map((sa, idx) => ({
      name: MOTOR_META[idx].id,
      torque_ai: state.aiTorque ? state.aiTorque[idx] : null,
      torque_physics: state.physicsTorque[idx],
      speed: sa.speed,
      accel: sa.accel,
      utilization: sa.utilization,
      safe: sa.safe
    }))
  };
  state.aiControlParams = payload;

  if (socket && socket.connected) {
    socket.emit('ai_control_params', payload);
  }

  fetch('/api/arm/ai_params', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).catch(() => { });

  const btn = document.getElementById('send-to-control-btn');
  if (btn) {
    const orig = btn.textContent;
    btn.textContent = '✓ SENT TO CONTROL';
    btn.style.borderColor = 'var(--green)';
    btn.style.color = 'var(--green)';
    setTimeout(() => {
      btn.textContent = orig;
      btn.style.borderColor = '';
      btn.style.color = '';
    }, 1800);
  }
}

// ════════════════════════════════════════════════════════════════
//  MANUAL POSE SLIDERS
// ════════════════════════════════════════════════════════════════
function buildManualSliders() {
  const grid = document.getElementById('manual-sliders');
  grid.innerHTML = JOINT_NAMES.map((name, i) => {
    const [lo, hi] = ARM_CFG.jointLimitsDeg[i];
    return `
      <div class="cfg-field">
        <label>${name} (${lo}° to ${hi}°)</label>
        <input type="number" id="manual-j${i}" value="0" min="${lo}" max="${hi}" step="1"
               oninput="onManualSliderChange()">
      </div>`;
  }).join('');
}
function onManualSliderChange() {
  state.manualMode = true;
  state.jointAnglesDeg = JOINT_NAMES.map((_, i) =>
    parseFloat(document.getElementById(`manual-j${i}`).value) || 0);
  recompute();
}

// ════════════════════════════════════════════════════════════════
//  CHARTS (Chart.js)
// ════════════════════════════════════════════════════════════════
const trendCharts = {};
let errorBarChart = null;

function buildTrendCharts() {
  const grid = document.getElementById('trend-chart-grid');
  grid.innerHTML = MOTOR_META.map(m => `
    <div class="chart-box">
      <canvas id="trend-${m.id}"></canvas>
    </div>`).join('');

  MOTOR_META.forEach(m => {
    const ctx = document.getElementById(`trend-${m.id}`).getContext('2d');
    trendCharts[m.id] = new Chart(ctx, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          { label: `${m.id} Physics`, data: [], borderColor: '#00e5ff', backgroundColor: 'transparent', tension: 0.25, pointRadius: 0, borderWidth: 2 },
          { label: `${m.id} AI`, data: [], borderColor: '#b9f61d', backgroundColor: 'transparent', tension: 0.25, pointRadius: 0, borderWidth: 2, borderDash: [4, 2] },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        plugins: { legend: { labels: { color: '#c8d6e5', font: { size: 9 } } }, title: { display: true, text: `${m.id} Torque (N·m)`, color: '#3d4f55', font: { size: 10 } } },
        scales: {
          x: { ticks: { color: '#3d4f55', font: { size: 8 }, maxTicksLimit: 6 }, grid: { color: '#1a2028' } },
          y: { ticks: { color: '#3d4f55', font: { size: 8 } }, grid: { color: '#1a2028' } },
        },
      },
    });
  });
}

function buildErrorBarChart() {
  const ctx = document.getElementById('error-bar-chart').getContext('2d');
  errorBarChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: MOTOR_META.map(m => m.id),
      datasets: [{ label: 'Error %', data: [0, 0, 0, 0, 0, 0], backgroundColor: '#b9f61d' }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#c8d6e5' }, grid: { color: '#1a2028' } },
        y: { ticks: { color: '#3d4f55' }, grid: { color: '#1a2028' }, beginAtZero: true },
      },
    },
  });
}

function pushHistory(tLabel) {
  state.history.t.push(tLabel);
  for (let i = 0; i < 6; i++) {
    state.history.physics[i].push(state.physicsTorque[i]);
    state.history.ai[i].push(state.aiTorque ? state.aiTorque[i] : null);
  }
  if (state.history.t.length > state.maxHistoryPoints) {
    state.history.t.shift();
    for (let i = 0; i < 6; i++) { state.history.physics[i].shift(); state.history.ai[i].shift(); }
  }
}

function updateCharts() {
  MOTOR_META.forEach((m, i) => {
    const c = trendCharts[m.id];
    if (!c) return;
    c.data.labels = state.history.t;
    c.data.datasets[0].data = state.history.physics[i];
    c.data.datasets[1].data = state.history.ai[i];
    c.update('none');
  });
  if (errorBarChart) {
    errorBarChart.data.datasets[0].data = state.aiTorque ? state.errorPct.map(p => Math.min(p, 100)) : [0, 0, 0, 0, 0, 0];
    errorBarChart.data.datasets[0].backgroundColor = state.errorPct.map(p => errColor(errClass(p)));
    errorBarChart.update('none');
  }
}

// ════════════════════════════════════════════════════════════════
//  MAIN RECOMPUTE
// ════════════════════════════════════════════════════════════════
let lastAiFetchTime = 0;
const AI_FETCH_THROTTLE_MS = 400;

function recompute() {
  state.loadKg = parseFloat(document.getElementById('load-kg').value) || 0;
  document.getElementById('load-n').textContent = (state.loadKg * 9.81).toFixed(2);

  if (state.manualMode) {
    state.physicsTorque = physicsFromJointAngles(state.jointAnglesDeg, state.loadKg, ARM_CFG);
  } else {
    const { tauMotor, jointDeg } = physicsFromMotorAngles(state.motorPositions, state.loadKg, ARM_CFG);
    state.physicsTorque = tauMotor;
    state.jointAnglesDeg = jointDeg;
  }

  updateCards();

  const now = Date.now();
  if (state.apiConnected && now - lastAiFetchTime > AI_FETCH_THROTTLE_MS) {
    lastAiFetchTime = now;
    fetchAiPrediction(state.jointAnglesDeg, state.loadKg).then(data => {
      if (data) {
        state.aiTorque = data.ai_torque;
        state.errorPct = data.error_pct;
        state.aiSpeedAccel = state.aiTorque.map((t, i) =>
          calculateSafeSpeedAccel(i, t, state.loadKg)
        );
      } else {
        state.aiTorque = null;
        state.aiSpeedAccel = [];
      }
      updateCards();
      updateAiControlCards();
      pushHistory(new Date().toTimeString().slice(0, 8));
      updateCharts();
    });
  } else if (!state.apiConnected) {
    state.aiSpeedAccel = [];
    pushHistory(new Date().toTimeString().slice(0, 8));
    updateCharts();
  }
}

function onInputChange() { recompute(); }

// ════════════════════════════════════════════════════════════════
//  TABS
// ════════════════════════════════════════════════════════════════
function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
}

// ════════════════════════════════════════════════════════════════
//  MODEL COMPARISON TAB
// ════════════════════════════════════════════════════════════════
async function loadModelComparison() {
  const statusEl = document.getElementById('models-status');
  try {
    const res = await fetch('../models/comparison_report.json');
    if (!res.ok) throw new Error('not found');
    const report = await res.json();
    renderModelComparison(report);
  } catch (e) {
    statusEl.textContent = '⚠ Could not load ../models/comparison_report.json — run train_models.py first, ' +
      'then serve this dashboard from a path where that relative path resolves (or copy the file next to the dashboard).';
  }
}

function renderModelComparison(report) {
  document.getElementById('models-status').style.display = 'none';
  const table = document.getElementById('models-table');
  table.style.display = '';
  const tbody = document.getElementById('models-table-body');

  const best = report.reduce((a, b) => (b.avg_R2_excl_degenerate > a.avg_R2_excl_degenerate ? b : a));

  tbody.innerHTML = report.map(r => `
    <tr class="${r.label === best.label ? 'best-row' : ''}">
      <td>${r.label}${r.label === best.label ? ' 🏆' : ''}</td>
      <td class="${r.label === best.label ? 'best' : ''}">${r.avg_MAE.toFixed(5)}</td>
      <td class="${r.label === best.label ? 'best' : ''}">${r.avg_RMSE.toFixed(5)}</td>
      <td class="${r.label === best.label ? 'best' : ''}">${r.avg_R2_excl_degenerate.toFixed(4)}</td>
      <td>${r.train_time_sec ? r.train_time_sec.toFixed(1) + 's' : '—'}</td>
    </tr>`).join('');

  const panel = document.getElementById('per-target-panel');
  panel.style.display = '';
  const targets = Object.keys(best.per_target);
  const r2vals = targets.map(t => best.per_target[t].R2 === null || isNaN(best.per_target[t].R2) ? 0 : best.per_target[t].R2);

  const ctx = document.getElementById('r2-bar-chart').getContext('2d');
  new Chart(ctx, {
    type: 'bar',
    data: { labels: targets, datasets: [{ label: `${best.label} R² per target`, data: r2vals, backgroundColor: '#00e5ff' }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { color: '#c8d6e5' } } },
      scales: {
        x: { ticks: { color: '#c8d6e5' }, grid: { color: '#1a2028' } },
        y: { ticks: { color: '#3d4f55' }, grid: { color: '#1a2028' }, suggestedMin: 0, suggestedMax: 1 },
      },
    },
  });
}

// ════════════════════════════════════════════════════════════════
//  WARNING DISMISS HANDLERS
// ════════════════════════════════════════════════════════════════
document.getElementById('api-warn-dismiss').addEventListener('click', () => {
  document.getElementById('api-warn-banner').classList.add('hidden');
});
document.getElementById('data-warn-dismiss').addEventListener('click', () => {
  document.getElementById('data-warn-banner').classList.add('hidden');
});

// ════════════════════════════════════════════════════════════════
//  INIT
// ════════════════════════════════════════════════════════════════
buildCards();
buildAiControlGrid();
buildManualSliders();
buildTrendCharts();
buildErrorBarChart();
loadModelComparison();
checkApiHealth();
recompute();

setInterval(() => { checkApiHealth(); }, 5000);
setInterval(() => { recompute(); }, 2000);

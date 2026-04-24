// ============================================================
// ASSETS/APP.JS — RoboTrack Monitor frontend
// Vanilla JS, geen externe dependencies.
// ============================================================

(() => {
  'use strict';

  // --- Config vanuit DOM ---
  const cfg         = document.getElementById('js-config');
  const POLL_MS     = parseInt(cfg.dataset.poll, 10) || 500;
  const API_URL     = cfg.dataset.api;
  const LOW_BAT     = parseInt(cfg.dataset.lowBattery, 10) || 20;
  const IS_ADMIN    = cfg.dataset.role === 'admin';

  // --- DOM refs ---
  const canvas        = document.getElementById('robot-canvas');
  const ctx           = canvas.getContext('2d');
  const trackImg      = document.getElementById('track-bg');
  const robotList     = document.getElementById('robot-list');
  const batteryPanel  = document.getElementById('battery-panel');
  const tooltip       = document.getElementById('robot-tooltip');
  const liveLabel     = document.getElementById('live-label');
  const liveDot       = document.getElementById('live-indicator');
  const lastUpdate    = document.getElementById('last-update');
  const robotCount    = document.getElementById('robot-count');
  const activeCount   = document.getElementById('active-count');
  const offlineCount  = document.getElementById('offline-count');
  const pollStatus    = document.getElementById('poll-status');
  const batBanner     = document.getElementById('battery-warning-banner');
  const batBannerText = document.getElementById('battery-warning-text');

  // --- State ---
  let robots          = [];
  let selectedRobotId = null;
  let errorCount      = 0;
  const frozenPos     = {};   // id → {x, y, heading} van het laatste actieve moment

  // --- Status kleuren ---
  const STATUS_COLORS = {
    active : '#22c55e',
    idle   : '#f59e0b',
    error  : '#ef4444',
    offline: '#64748b',
    unknown: '#94a3b8',
  };

  // ============================================================
  // CANVAS RESIZE
  // ============================================================
  function syncCanvasSize() {
    const rect = trackImg.getBoundingClientRect();
    if (canvas.width !== rect.width || canvas.height !== rect.height) {
      canvas.width  = rect.width;
      canvas.height = rect.height;
    }
    canvas._naturalW = trackImg.naturalWidth  || rect.width;
    canvas._naturalH = trackImg.naturalHeight || rect.height;
    canvas._dispW    = rect.width;
    canvas._dispH    = rect.height;
  }

  function toDisplay(x, y) {
    const scaleX = canvas._dispW  / canvas._naturalW;
    const scaleY = canvas._dispH  / canvas._naturalH;
    return { dx: x * scaleX, dy: y * scaleY };
  }

  // ============================================================
  // DRAW ROBOT
  // ============================================================
  const ROBOT_RADIUS   = 12;
  const ARROW_LENGTH   = 22;
  const ARROW_HEAD     = 6;
  const LABEL_OFFSET_Y = 20;

  function drawRobot(r, isSelected) {
    const { dx, dy } = toDisplay(r.x, r.y);
    const color      = STATUS_COLORS[r.status] || STATUS_COLORS.unknown;
    const headRad    = (r.heading - 90) * (Math.PI / 180);

    ctx.save();
    ctx.translate(dx, dy);

    // Halo bij selectie
    if (isSelected) {
      ctx.beginPath();
      ctx.arc(0, 0, ROBOT_RADIUS + 6, 0, Math.PI * 2);
      ctx.strokeStyle = color;
      ctx.lineWidth   = 1.5;
      ctx.globalAlpha = 0.4;
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    // Lage batterij puls
    if (r.battery >= 0 && r.battery <= LOW_BAT) {
      ctx.beginPath();
      ctx.arc(0, 0, ROBOT_RADIUS + 4, 0, Math.PI * 2);
      ctx.strokeStyle = '#ef4444';
      ctx.lineWidth   = 2;
      ctx.globalAlpha = 0.5 + 0.5 * Math.sin(Date.now() / 250);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    // Robot cirkel
    ctx.beginPath();
    ctx.arc(0, 0, ROBOT_RADIUS, 0, Math.PI * 2);
    ctx.fillStyle   = '#0f172a';
    ctx.strokeStyle = color;
    ctx.lineWidth   = 2;
    ctx.fill();
    ctx.stroke();

    // Heading pijl
    const arrowTipX = Math.cos(headRad) * ARROW_LENGTH;
    const arrowTipY = Math.sin(headRad) * ARROW_LENGTH;

    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(arrowTipX, arrowTipY);
    ctx.strokeStyle = color;
    ctx.lineWidth   = 2;
    ctx.lineCap     = 'round';
    ctx.stroke();

    const backAngle = headRad + Math.PI;
    ctx.beginPath();
    ctx.moveTo(arrowTipX, arrowTipY);
    ctx.lineTo(arrowTipX + Math.cos(backAngle - 0.45) * ARROW_HEAD,
               arrowTipY + Math.sin(backAngle - 0.45) * ARROW_HEAD);
    ctx.lineTo(arrowTipX + Math.cos(backAngle + 0.45) * ARROW_HEAD,
               arrowTipY + Math.sin(backAngle + 0.45) * ARROW_HEAD);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();

    // Label
    ctx.font         = 'bold 9px "JetBrains Mono", "Courier New", monospace';
    ctx.textAlign    = 'center';
    ctx.textBaseline = 'top';
    const lw = ctx.measureText(r.label).width + 6;
    ctx.fillStyle = 'rgba(0,0,0,0.75)';
    ctx.fillRect(-lw / 2, LABEL_OFFSET_Y - 1, lw, 12);
    ctx.fillStyle = color;
    ctx.fillText(r.label, 0, LABEL_OFFSET_Y);

    ctx.restore();
  }

  // ============================================================
  // RENDER
  // ============================================================
  function render() {
    syncCanvasSize();
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    robots.forEach(r => drawRobot(r, r.id === selectedRobotId));

    // Herrender voor lage-batterij animatie
    if (robots.some(r => r.battery >= 0 && r.battery <= LOW_BAT)) {
      requestAnimationFrame(render);
    }
  }

  // ============================================================
  // BATTERY WARNING BANNER
  // ============================================================
  function updateBatteryBanner() {
    const deadBots = robots.filter(r => r.battery === 0);
    const lowBots  = robots.filter(r => r.battery > 0 && r.battery <= LOW_BAT);

    if (deadBots.length > 0 || lowBots.length > 0) {
      const parts = [];
      if (deadBots.length > 0)
        parts.push('BATTERIJ LEEG (offline): ' + deadBots.map(r => esc(r.label)).join(', '));
      if (lowBots.length > 0)
        parts.push('LAAG: ' + lowBots.map(r => `${esc(r.label)} (${r.battery}%)`).join(', '));
      batBannerText.textContent = parts.join(' | ');
      batBanner.classList.remove('hidden');
    } else {
      batBanner.classList.add('hidden');
    }
  }

  // ============================================================
  // BATTERY OVERVIEW PANEL
  // ============================================================
  function updateBatteryPanel() {
    if (!batteryPanel) return;
    if (!IS_ADMIN) { batteryPanel.innerHTML = '<div class="robot-list-loading">Enkel zichtbaar voor admin</div>'; return; }
    const withBat = robots.filter(r => r.battery >= 0);
    if (!withBat.length) {
      batteryPanel.innerHTML = '<div class="robot-list-loading">Geen batterijdata</div>';
      return;
    }
    batteryPanel.innerHTML = withBat
      .sort((a, b) => a.battery - b.battery)
      .map(r => {
        const color = batteryColor(r.battery);
        const warn  = r.battery <= LOW_BAT ? ' bat-warn' : '';
        return `
          <div class="bat-overview-row${warn}">
            <span class="bat-ov-label">${esc(r.label)}</span>
            <div class="bat-bar">
              <div class="bat-fill" style="width:${r.battery}%; background:${color}"></div>
            </div>
            <span class="bat-ov-pct">${r.battery}%</span>
          </div>`;
      }).join('');
  }

  // ============================================================
  // SIDEBAR ROBOT LIJST
  // ============================================================
  function updateSidebar() {
    robotList.innerHTML = '';
    if (!robots.length) {
      robotList.innerHTML = '<div class="robot-list-loading">Geen robots gedetecteerd</div>';
      return;
    }

    robots.forEach(r => {
      const color   = STATUS_COLORS[r.status] || STATUS_COLORS.unknown;
      const batHtml = IS_ADMIN && r.battery >= 0
        ? `<div class="robot-bat">
             <div class="bat-bar">
               <div class="bat-fill" style="width:${r.battery}%; background:${batteryColor(r.battery)}"></div>
             </div>
             <span>${r.battery}%</span>
           </div>`
        : '';

      const isOverride = r.override;
      const toggleHtml = IS_ADMIN
        ? `<button class="robot-toggle${r.status === 'offline' ? ' is-offline' : ''}"
              title="${r.status === 'offline' ? 'Zet online' : 'Zet offline'}"
              data-robot-id="${esc(r.id)}"
              data-current="${esc(r.status)}">⏻</button>`
        : '';

      const item = document.createElement('div');
      item.className = 'robot-item' + (r.id === selectedRobotId ? ' selected' : '');
      item.dataset.id = r.id;
      item.innerHTML = `
        <div class="robot-item-header">
          <span class="robot-dot" style="background:${color}"></span>
          <span class="robot-label">${esc(r.label)}</span>
          <span class="robot-status">${esc(r.status)}${isOverride ? ' ✎' : ''}</span>
          ${toggleHtml}
        </div>
        <div class="robot-coords">
          X:${Math.round(r.x)} Y:${Math.round(r.y)} HDG:${Math.round(r.heading)}°
        </div>
        ${batHtml}
      `;
      item.addEventListener('click', (e) => {
        if (e.target.closest('.robot-toggle')) return;
        selectedRobotId = (selectedRobotId === r.id) ? null : r.id;
        updateSidebar();
        render();
      });
      robotList.appendChild(item);
    });

    const activeN  = robots.filter(r => r.status === 'active').length;
    const offlineN = robots.filter(r => r.status === 'offline').length;

    robotCount.textContent  = `${robots.length} robots`;
    activeCount.textContent = `${activeN} active`;
    offlineCount.textContent = offlineN > 0 ? `${offlineN} offline` : '';
    offlineCount.style.color = offlineN > 0 ? '#ef4444' : '';
  }

  function batteryColor(pct) {
    if (pct > 50) return '#22c55e';
    if (pct > 20) return '#f59e0b';
    return '#ef4444';
  }

  // ============================================================
  // FETCH — polling
  // ============================================================
  async function fetchRobots() {
    try {
      const res = await fetch(API_URL, { credentials: 'same-origin' });
      if (res.status === 401) { window.location.href = 'login.php'; return; }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      const raw  = data.robots || [];

      // Bevrieg positie van offline robots op hun laatste bekende locatie
      raw.forEach(r => {
        if (r.status !== 'offline') {
          frozenPos[r.id] = { x: r.x, y: r.y, heading: r.heading };
        } else if (frozenPos[r.id]) {
          r.x       = frozenPos[r.id].x;
          r.y       = frozenPos[r.id].y;
          r.heading = frozenPos[r.id].heading;
        }
      });

      robots     = raw;
      errorCount = 0;

      setLiveStatus('live');
      lastUpdate.textContent = new Date(data.ts * 1000).toLocaleTimeString();
      pollStatus.textContent = '';

      updateSidebar();
      if (IS_ADMIN) { updateBatteryPanel(); updateBatteryBanner(); }

    } catch (err) {
      errorCount++;
      setLiveStatus('error');
      pollStatus.textContent = `ERR×${errorCount}`;
      console.warn('[RoboTrack] fetch error:', err);
    }
    render();
  }

  function setLiveStatus(state) {
    liveDot.className     = 'live-dot ' + state;
    liveLabel.textContent = state === 'live'  ? 'LIVE'
                          : state === 'error' ? 'RECONNECTING…'
                          : 'CONNECTING…';
  }

  // ============================================================
  // TOOLTIP & CANVAS EVENTS
  // ============================================================
  canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    const mx   = e.clientX - rect.left;
    const my   = e.clientY - rect.top;

    let found = null;
    for (const r of robots) {
      const { dx, dy } = toDisplay(r.x, r.y);
      if (Math.hypot(mx - dx, my - dy) < ROBOT_RADIUS + 8) { found = r; break; }
    }

    if (found) {
      const batLine = IS_ADMIN && found.battery >= 0
        ? `<span${found.battery <= LOW_BAT ? ' class="bat-low-tip"' : ''}>Battery: ${found.battery}%</span>`
        : '';
      tooltip.innerHTML = `
        <strong>${esc(found.label)}</strong>
        <span>Status: ${esc(found.status)}</span>
        <span>X: ${found.x}  Y: ${found.y}</span>
        <span>Heading: ${found.heading}°</span>
        ${batLine}
      `;
      tooltip.classList.remove('hidden');
      tooltip.style.left = (e.clientX - rect.left + 16) + 'px';
      tooltip.style.top  = (e.clientY - rect.top  - 10) + 'px';
      canvas.style.cursor = 'pointer';
    } else {
      tooltip.classList.add('hidden');
      canvas.style.cursor = 'crosshair';
    }
  });

  // ============================================================
  // ROBOT TOGGLE (admin only)
  // ============================================================
  robotList.addEventListener('click', async (e) => {
    const btn = e.target.closest('.robot-toggle');
    if (!btn || !IS_ADMIN) return;

    const id      = btn.dataset.robotId;
    const current = btn.dataset.current;
    const next    = current === 'offline' ? 'active' : 'offline';

    btn.disabled = true;
    try {
      const res = await fetch('api/robot_control.php', {
        method     : 'POST',
        credentials: 'same-origin',
        headers    : { 'Content-Type': 'application/json' },
        body       : JSON.stringify({ id, status: next }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        console.error('[RoboTrack] toggle error:', err);
      } else {
        // Als robot terug active wordt, bevroren positie wissen
        if (next === 'active') delete frozenPos[id];
        await fetchRobots();
      }
    } catch (err) {
      console.error('[RoboTrack] toggle fetch error:', err);
    }
    btn.disabled = false;
  });

  canvas.addEventListener('mouseleave', () => tooltip.classList.add('hidden'));

  canvas.addEventListener('click', (e) => {
    const rect = canvas.getBoundingClientRect();
    const mx   = e.clientX - rect.left;
    const my   = e.clientY - rect.top;
    let found  = null;
    for (const r of robots) {
      const { dx, dy } = toDisplay(r.x, r.y);
      if (Math.hypot(mx - dx, my - dy) < ROBOT_RADIUS + 8) { found = r; break; }
    }
    selectedRobotId = found ? (selectedRobotId === found.id ? null : found.id) : null;
    updateSidebar();
    render();
  });

  // ============================================================
  // INIT
  // ============================================================
  function esc(str) {
    const d = document.createElement('div');
    d.appendChild(document.createTextNode(String(str)));
    return d.innerHTML;
  }

  if (trackImg.complete) {
    syncCanvasSize();
    fetchRobots();
  } else {
    trackImg.addEventListener('load', () => { syncCanvasSize(); fetchRobots(); });
  }

  window.addEventListener('resize', () => { syncCanvasSize(); render(); });

  setInterval(fetchRobots, POLL_MS);

})();

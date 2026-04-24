<?php
// ============================================================
// DASHBOARD.PHP — Hoofdpagina robot monitoring
// ============================================================
require_once __DIR__ . '/includes/auth.php';
require_once __DIR__ . '/config/config.php';
require_login();

$user      = current_user();
$role      = current_role();
$isAdmin   = is_admin();
$cameraUrl = CAMERA_STREAM_URL;
?>
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard — <?= APP_NAME ?></title>
<link rel="stylesheet" href="assets/style.css">
</head>
<body class="dash-body">

<!-- ========== TOPBAR ========== -->
<header class="topbar">
  <div class="topbar-left">
    <svg class="topbar-icon" width="28" height="28" viewBox="0 0 48 48" fill="none">
      <rect x="4" y="14" width="40" height="26" rx="3" stroke="#f59e0b" stroke-width="2"/>
      <rect x="14" y="4" width="20" height="10" rx="2" stroke="#f59e0b" stroke-width="2"/>
      <circle cx="16" cy="27" r="4" fill="#f59e0b"/>
      <circle cx="32" cy="27" r="4" fill="#f59e0b"/>
      <line x1="20" y1="27" x2="28" y2="27" stroke="#f59e0b" stroke-width="2"/>
    </svg>
    <span class="topbar-title">ROBOTRACK</span>
    <span class="topbar-version">v<?= APP_VERSION ?></span>
  </div>

  <div class="topbar-center">
    <span id="live-indicator" class="live-dot"></span>
    <span id="live-label">CONNECTING…</span>
    <span id="last-update" class="topbar-ts"></span>
  </div>

  <div class="topbar-right">
    <span class="role-badge role-<?= $role ?>"><?= strtoupper($role) ?></span>
    <span class="topbar-user">
      <svg width="12" height="12" viewBox="0 0 12 12" fill="#94a3b8">
        <circle cx="6" cy="4" r="2.5"/>
        <path d="M1 11c0-2.76 2.24-5 5-5s5 2.24 5 5" stroke="#94a3b8" fill="none" stroke-width="1.2"/>
      </svg>
      <?= $user ?>
    </span>
    <a href="logout.php" class="btn-logout">LOGOUT</a>
  </div>
</header>

<!-- ========== BATTERY WARNING BANNER ========== -->
<div id="battery-warning-banner" class="battery-banner hidden">
  <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
    <path d="M7 1L13 12H1L7 1Z" stroke="currentColor" stroke-width="1.2" fill="none"/>
    <line x1="7" y1="5" x2="7" y2="8" stroke="currentColor" stroke-width="1.5"/>
    <circle cx="7" cy="10" r="0.7" fill="currentColor"/>
  </svg>
  <span id="battery-warning-text">LOW BATTERY WARNING</span>
</div>

<!-- ========== MAIN LAYOUT ========== -->
<div class="dash-layout">

  <!-- ---- SIDEBAR ---- -->
  <aside class="sidebar">
    <div class="sidebar-header">FLEET STATUS</div>
    <div id="robot-list" class="robot-list">
      <div class="robot-list-loading">Initializing…</div>
    </div>

    <!-- Batterij overzicht — enkel voor admin -->
    <?php if (is_admin()): ?>
    <div class="sidebar-section">
      <div class="sidebar-header">BATTERY OVERVIEW</div>
      <div id="battery-panel" class="battery-overview-panel">
        <div class="robot-list-loading">Waiting for data…</div>
      </div>
    </div>
    <?php endif; ?>

    <!-- Camera stream -->
    <div class="sidebar-section">
      <div class="sidebar-header">
        TOP-VIEW CAMERA
        <?php if ($cameraUrl): ?>
          <span class="cam-live-dot"></span>
        <?php endif; ?>
      </div>
      <div class="camera-panel">
        <?php if ($cameraUrl): ?>
          <img
            id="camera-stream"
            src="<?= htmlspecialchars($cameraUrl, ENT_QUOTES, 'UTF-8') ?>"
            alt="Top-view camera"
            class="camera-img"
            onclick="openCamModal()"
            onerror="this.style.display='none'; document.getElementById('cam-error').style.display='block';"
          >
          <p id="cam-error" class="placeholder-text" style="display:none">
            Stream onbereikbaar — controleer verbinding
          </p>
        <?php else: ?>
          <p class="placeholder-text">
            Stream URL nog niet geconfigureerd.<br>
            Stel <code>CAMERA_STREAM_URL</code> in via <code>config.php</code>.
          </p>
        <?php endif; ?>
      </div>
    </div>
  </aside>

  <!-- ---- MAP AREA ---- -->
  <main class="map-area">
    <div class="map-wrapper">
      <img
        id="track-bg"
        src="<?= htmlspecialchars(TRACK_IMAGE, ENT_QUOTES, 'UTF-8') ?>"
        alt="Track layout"
        class="track-image"
        draggable="false"
      >
      <canvas id="robot-canvas" class="robot-canvas"></canvas>
      <div id="robot-tooltip" class="robot-tooltip hidden"></div>
    </div>

    <div class="map-statusbar">
      <span id="robot-count">-- robots</span>
      <span id="active-count">-- active</span>
      <span id="offline-count"></span>
      <span class="map-source">SOURCE: <?= strtoupper(DATA_SOURCE) ?></span>
      <span id="poll-status"></span>
    </div>
  </main>

</div>

<!-- Config doorgeven aan JS (geen secrets) -->
<div
  id="js-config"
  data-poll="<?= POLL_INTERVAL_MS ?>"
  data-api="api/robots.php"
  data-low-battery="<?= LOW_BATTERY_THRESHOLD ?>"
  data-role="<?= $role ?>"
  hidden
></div>

<!-- ========== CAMERA MODAL ========== -->
<?php if ($cameraUrl): ?>
<div id="cam-modal" class="cam-modal" onclick="closeCamModal()">
  <div class="cam-modal-inner" onclick="event.stopPropagation()">
    <div class="cam-modal-header">
      <span>TOP-VIEW CAMERA &nbsp;<span class="cam-live-dot"></span></span>
      <button class="cam-modal-close" onclick="closeCamModal()">✕</button>
    </div>
    <img
      src="<?= htmlspecialchars($cameraUrl, ENT_QUOTES, 'UTF-8') ?>"
      alt="Top-view camera fullscreen"
    >
  </div>
</div>
<script>
function openCamModal()  { document.getElementById('cam-modal').classList.add('open'); }
function closeCamModal() { document.getElementById('cam-modal').classList.remove('open'); }
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeCamModal(); });
</script>
<?php endif; ?>

<script src="assets/app.js"></script>
</body>
</html>

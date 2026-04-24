<?php
// ============================================================
// LOGIN.PHP
// ============================================================
require_once __DIR__ . '/includes/auth.php';

// Déjà connecté → redirect
if (is_logged_in()) {
    header('Location: dashboard.php');
    exit;
}

$error = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // CSRF basique : token en session
    if (!isset($_POST['csrf_token']) || $_POST['csrf_token'] !== ($_SESSION['csrf_token'] ?? '')) {
        $error = 'Invalid request. Please try again.';
    } else {
        $username = trim($_POST['username'] ?? '');
        $password = $_POST['password'] ?? '';

        if ($username === '' || $password === '') {
            $error = 'Please fill in all fields.';
        } elseif (!attempt_login($username, $password)) {
            // Délai anti-bruteforce minimal (côté scolaire c'est suffisant)
            sleep(1);
            $error = 'Invalid credentials.';
        } else {
            header('Location: dashboard.php');
            exit;
        }
    }
}

// Générer token CSRF
session_start_secure();
if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
}
$csrf = $_SESSION['csrf_token'];
?>
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Login — RoboTrack Monitor</title>
<link rel="stylesheet" href="assets/style.css">
</head>
<body class="login-body">

<div class="login-wrapper">
  <div class="login-card">

    <div class="login-logo">
      <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="4" y="14" width="40" height="26" rx="3" stroke="#f59e0b" stroke-width="2"/>
        <rect x="14" y="4" width="20" height="10" rx="2" stroke="#f59e0b" stroke-width="2"/>
        <circle cx="16" cy="27" r="4" fill="#f59e0b"/>
        <circle cx="32" cy="27" r="4" fill="#f59e0b"/>
        <line x1="20" y1="27" x2="28" y2="27" stroke="#f59e0b" stroke-width="2"/>
        <line x1="8" y1="27" x2="4" y2="32" stroke="#f59e0b" stroke-width="2"/>
        <line x1="40" y1="27" x2="44" y2="32" stroke="#f59e0b" stroke-width="2"/>
      </svg>
      <span class="login-title">ROBOTRACK</span>
    </div>

    <p class="login-subtitle">FLEET MONITORING SYSTEM</p>

    <?php if ($error): ?>
      <div class="alert alert-error"><?= htmlspecialchars($error, ENT_QUOTES, 'UTF-8') ?></div>
    <?php endif; ?>

    <form method="POST" action="login.php" autocomplete="off">
      <input type="hidden" name="csrf_token" value="<?= $csrf ?>">

      <div class="form-group">
        <label for="username">OPERATOR ID</label>
        <input
          type="text"
          id="username"
          name="username"
          placeholder="admin"
          autocomplete="username"
          value="<?= htmlspecialchars($_POST['username'] ?? '', ENT_QUOTES, 'UTF-8') ?>"
          required
        >
      </div>

      <div class="form-group">
        <label for="password">ACCESS CODE</label>
        <input
          type="password"
          id="password"
          name="password"
          placeholder="••••••••"
          autocomplete="current-password"
          required
        >
      </div>

      <button type="submit" class="btn-login">
        AUTHENTICATE
        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
          <path d="M8 1l7 7-7 7M1 8h14" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/>
        </svg>
      </button>
    </form>

    <div class="login-footer">
      <span class="status-dot active"></span> SYSTEM ONLINE
    </div>
  </div>
</div>

</body>
</html>

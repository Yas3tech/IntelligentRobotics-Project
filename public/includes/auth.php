<?php
// ============================================================
// INCLUDES/AUTH.PHP — Sessie, login & toegangscontrole
// ============================================================

require_once __DIR__ . '/../config/config.php';

function session_start_secure(): void {
    if (session_status() === PHP_SESSION_NONE) {
        ini_set('session.cookie_httponly', 1);
        ini_set('session.cookie_samesite', 'Strict');
        ini_set('session.gc_maxlifetime', SESSION_LIFETIME);
        session_name(SESSION_NAME);
        session_start();
    }
}

function is_logged_in(): bool {
    session_start_secure();
    return isset($_SESSION['user'])
        && isset($_SESSION['expires'])
        && $_SESSION['expires'] > time();
}

function require_login(): void {
    if (!is_logged_in()) {
        header('Location: login.php');
        exit;
    }
    $_SESSION['expires'] = time() + SESSION_LIFETIME;
}

function require_role(string $role): void {
    require_login();
    if (($_SESSION['role'] ?? '') !== $role) {
        http_response_code(403);
        echo json_encode(['error' => 'Forbidden']);
        exit;
    }
}

function attempt_login(string $username, string $password): bool {
    session_start_secure();
    $users = USERS;
    if (
        isset($users[$username])
        && password_verify($password, $users[$username]['hash'])
    ) {
        session_regenerate_id(true);
        $_SESSION['user']    = $username;
        $_SESSION['role']    = $users[$username]['role'];
        $_SESSION['expires'] = time() + SESSION_LIFETIME;
        return true;
    }
    return false;
}

function logout(): void {
    session_start_secure();
    $_SESSION = [];
    session_destroy();
}

function current_user(): string {
    return htmlspecialchars($_SESSION['user'] ?? 'Unknown', ENT_QUOTES, 'UTF-8');
}

function current_role(): string {
    return htmlspecialchars($_SESSION['role'] ?? 'viewer', ENT_QUOTES, 'UTF-8');
}

function is_admin(): bool {
    return ($_SESSION['role'] ?? '') === 'admin';
}

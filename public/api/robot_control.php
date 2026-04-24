<?php
// ============================================================
// API/ROBOT_CONTROL.PHP — Admin: robot status overschrijven
// POST  body: {"id": "tag10", "status": "offline" | "active"}
// ============================================================
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../config/config.php';

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

require_login();

// Enkel admins mogen robots beheren
if (!is_admin()) {
    http_response_code(403);
    echo json_encode(['error' => 'Forbidden — admin only']);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'POST required']);
    exit;
}

$body = json_decode(file_get_contents('php://input'), true);
if (!$body) {
    http_response_code(400);
    echo json_encode(['error' => 'Invalid JSON body']);
    exit;
}

$id     = preg_replace('/[^a-zA-Z0-9_\-]/', '', $body['id']     ?? '');
$status = in_array($body['status'] ?? '', ['offline', 'active']) ? $body['status'] : null;

if (!$id || !$status) {
    http_response_code(400);
    echo json_encode(['error' => 'id en status (active|offline) zijn verplicht']);
    exit;
}

$overridesFile = __DIR__ . '/../data/robot_overrides.json';

// Lees huidige overrides
$overrides = [];
if (file_exists($overridesFile)) {
    $overrides = json_decode(file_get_contents($overridesFile), true) ?? [];
}

// Pas aan
if ($status === 'active') {
    unset($overrides[$id]);  // override verwijderen = robot volgt MQTT weer
} else {
    $overrides[$id] = $status;
}

// Schrijf atomisch
$tmp = $overridesFile . '.tmp';
file_put_contents($tmp, json_encode($overrides));
rename($tmp, $overridesFile);

echo json_encode([
    'ok'       => true,
    'id'       => $id,
    'status'   => $status,
    'overrides'=> $overrides,
]);

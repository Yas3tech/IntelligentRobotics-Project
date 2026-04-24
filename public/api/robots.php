<?php
// ============================================================
// API/ROBOTS.PHP — Endpoint JSON robots
// ============================================================
// Retourne la liste des robots avec positions et états.
// Appel : GET api/robots.php
// Réponse : application/json
// ============================================================

require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../config/config.php';

// Protection : seuls les clients connectés peuvent interroger l'API
require_login();

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

// ------------------------------------------------------------------
// SOURCE DE DONNÉES
// ------------------------------------------------------------------
// Changer DATA_SOURCE dans config/config.php pour switcher de source.

switch (DATA_SOURCE) {

    // ---- MODE MOCK : lit un fichier JSON statique ----
    case 'mock':
        $file = __DIR__ . '/../data/robots_mock.json';
        if (!file_exists($file)) {
            http_response_code(500);
            echo json_encode(['error' => 'Mock data file not found']);
            exit;
        }
        $raw = file_get_contents($file);
        // Validation JSON minimale
        $robots = json_decode($raw, true);
        if (json_last_error() !== JSON_ERROR_NONE) {
            http_response_code(500);
            echo json_encode(['error' => 'Invalid mock JSON']);
            exit;
        }
        break;

    // ---- MODE FILE : fichier écrit par un script externe ----
    // Le signaling server / bridge MQTT écrit dans data/robots_live.json
    // Format identique au mock.
    // TODO MQTT → FILE : brancher ici le consumer MQTT qui écrit le fichier
    case 'file':
        $file = __DIR__ . '/../data/robots_live.json';
        if (!file_exists($file)) {
            // Fallback sur mock si le fichier live n'existe pas encore
            $file = __DIR__ . '/../data/robots_mock.json';
        }
        $raw    = file_get_contents($file);
        $robots = json_decode($raw, true) ?? [];
        break;

    // ---- MODE API : proxy vers un endpoint externe ----
    // Utile si vous avez un signaling server Node/Python séparé.
    // TODO API EXTERNE : remplacer DATA_SOURCE_URL dans config.php
    case 'api':
        $ctx = stream_context_create([
            'http' => [
                'timeout'       => 2,
                'ignore_errors' => true,
            ]
        ]);
        $raw = @file_get_contents(DATA_SOURCE_URL, false, $ctx);
        if ($raw === false) {
            http_response_code(502);
            echo json_encode(['error' => 'Cannot reach data source']);
            exit;
        }
        $robots = json_decode($raw, true) ?? [];
        break;

    default:
        http_response_code(500);
        echo json_encode(['error' => 'Unknown DATA_SOURCE']);
        exit;
}

// ------------------------------------------------------------------
// OVERRIDES — admin kan robots handmatig op offline zetten
// ------------------------------------------------------------------
$overridesFile = __DIR__ . '/../data/robot_overrides.json';
$overrides = [];
if (file_exists($overridesFile)) {
    $overrides = json_decode(file_get_contents($overridesFile), true) ?? [];
}

// ------------------------------------------------------------------
// VALIDATION & SANITIZE
// ------------------------------------------------------------------
$output = [];
foreach ($robots as $r) {
    $id     = htmlspecialchars((string)($r['id'] ?? ''), ENT_QUOTES, 'UTF-8');
    $status = in_array($r['status'] ?? '', ['active','idle','error','offline'])
                ? $r['status'] : 'unknown';

    // Admin override wint van live status
    if (isset($overrides[$id])) {
        $status = $overrides[$id];
    }

    $battery = (int)($r['battery'] ?? -1);
    $battery = $battery < 0 ? -1 : max(0, min(100, $battery));

    // Batterij leeg → automatisch offline
    if ($battery === 0) {
        $status = 'offline';
    }

    $output[] = [
        'id'       => $id,
        'label'    => htmlspecialchars((string)($r['label'] ?? $r['id'] ?? '?'), ENT_QUOTES, 'UTF-8'),
        'x'        => (float)($r['x']       ?? 0),
        'y'        => (float)($r['y']       ?? 0),
        'heading'  => (float)($r['heading'] ?? 0),
        'status'   => $status,
        'battery'  => $battery,
        'override' => isset($overrides[$id]) || $battery === 0,
    ];
}

echo json_encode([
    'ts'     => time(),                  // timestamp serveur
    'source' => DATA_SOURCE,
    'robots' => $output,
]);

<?php
// ============================================================
// CONFIG — RoboTrack Monitor
// ============================================================

define('APP_NAME', 'RoboTrack Monitor');
define('APP_VERSION', '1.0.0');

// --- Auth: gebruikers met rollen (admin / viewer) ---
// Hash genereren: php -r "echo password_hash('jouw_wachtwoord', PASSWORD_BCRYPT);"
define('USERS', [
    'admin'  => [
        'hash' => '$2y$12$pRB.PhPoM06WdfiwA2ZK7et0Rp4HOkWyWJXYSIysqo1XUW7DiNf5m', // "password"
        'role' => 'admin',
    ],
    'viewer' => [
        'hash' => '$2y$12$hhXwoDifcgIIyB05QMtmzePTA9Pxd0P1LRi0X2/ZIDkMoe3X4FSRS', // "viewer123"
        'role' => 'viewer',
    ],
]);

// --- Session ---
define('SESSION_NAME', 'robotrack_sess');
define('SESSION_LIFETIME', 3600);

// --- Data source ---
// 'mock' => data/robots_mock.json (statisch, voor testen)
// 'file' => data/robots_live.json (geschreven door mqtt_bridge.py)
// 'api'  => externe URL (zie DATA_SOURCE_URL)
define('DATA_SOURCE', 'file');
define('DATA_SOURCE_URL', 'http://localhost:9000/robots');

// --- MQTT bridge coördinaten (meters → pixels) ---
// Pas aan na kalibratie met Team 1 op locatie
define('WORLD_W_M', 6.0);   // breedte robot city in meter
define('WORLD_H_M', 3.0);   // hoogte robot city in meter

// --- Polling interval frontend (ms) ---
define('POLL_INTERVAL_MS', 500);

// --- Track afbeelding ---
// Sla de echte track foto op als public/assets/track.jpg
// Gebruik track.jpg als die bestaat, anders de SVG placeholder
define('TRACK_IMAGE', file_exists(__DIR__ . '/../assets/track1.jpg') ? 'assets/track1.jpg' : 'assets/track.svg');

// --- Camera stream ---
// URL naar de MJPEG of WebRTC stream van Team 1 (Jetson top-view camera)
// Laat leeg ('') om de placeholder te tonen
define('CAMERA_STREAM_URL', '');

// --- Batterij waarschuwingsdrempel (%) ---
define('LOW_BATTERY_THRESHOLD', 20);

// --- Timezone ---
date_default_timezone_set('Europe/Brussels');

# RoboTrack Monitor — Volledige Technische Documentatie

**Project:** Intelligent Robotics — Project 6 (EHB)  
**Auteurs:** Bilal / Yassine  
**Repo:** https://github.com/Yas3tech/IntelligentRobotics-Project  
**Datum:** April 2026

---

## Inhoudsopgave

1. [Overzicht van het project](#1-overzicht)
2. [Bestandsstructuur](#2-bestandsstructuur)
3. [Bestand per bestand uitgelegd](#3-bestanden-uitgelegd)
4. [Hoe de data stroomt](#4-dataflow)
5. [Rollen en rechten](#5-rollen-en-rechten)
6. [Robot offline zetten](#6-robot-offline-zetten)
7. [Batterij bewaking](#7-batterij-bewaking)
8. [Coördinaten en kaart](#8-coordinaten-en-kaart)
9. [Camera stream](#9-camera-stream)
10. [Opstarten en gebruik](#10-opstarten-en-gebruik)
11. [Wachtwoorden wijzigen](#11-wachtwoorden-wijzigen)

---

## 1. Overzicht

RoboTrack Monitor is een webdashboard in PHP dat meerdere autonome robots in real-time volgt op een parcours. Het systeem bestaat uit drie lagen:

```
MQTT Broker (Jetson van Team 1 OF Mosquitto lokaal)
       ↓
mqtt_bridge.py  (Python — converteert MQTT → JSON, met 180° coördinaatspiegeling)
       ↓
robots_live.json  (gedeeld bestand op de server)
       ↓
api/robots.php  (PHP API — beveiligd, past overrides toe)
       ↓
dashboard.php + app.js  (browser — pollt elke 500ms, tekent op canvas)
```

Tijdens ontwikkeling vervangt `simulate_robots.py` de Jetson volledig: het publiceert dezelfde MQTT-topics EN schrijft rechtstreeks naar het JSON-bestand als er geen broker beschikbaar is.

---

## 2. Bestandsstructuur

```
IntelligentRobotics-Project/
├── .gitignore
├── README.md
├── DOCUMENTATION.md
├── mqtt_bridge.py              ← Python MQTT bridge (productie + lokale test)
├── simulate_robots.py          ← Python simulator (publiceert MQTT of schrijft JSON)
└── public/                     ← Webroot
    ├── .htaccess
    ├── login.php
    ├── logout.php
    ├── dashboard.php           ← Hoofdpagina met kaart, sidebar, camera popup
    ├── api/
    │   ├── robots.php          ← GET: robotdata ophalen
    │   └── robot_control.php   ← POST: robot offline/online zetten (admin)
    ├── assets/
    │   ├── app.js              ← Frontend: polling, canvas, tooltip, camera modal
    │   ├── style.css           ← Dark theme + responsive (tablet/mobile)
    │   └── track1.jpg          ← Parcoursfoto (2508×1696 px)
    ├── config/
    │   └── config.php          ← Centrale configuratie
    ├── data/
    │   ├── robots_mock.json        ← Statische testdata (8 robots)
    │   ├── robots_live.json        ← Live data (geschreven door simulator/bridge)
    │   └── robot_overrides.json    ← Admin overrides (auto-aangemaakt)
    └── includes/
        ├── .htaccess
        └── auth.php            ← Authenticatie & sessies
```

---

## 3. Bestanden Uitgelegd

### 3.1 `config.php`

**Locatie:** `public/config/config.php`  
**Doel:** Één centraal bestand voor alle instellingen.

```php
define('DATA_SOURCE', 'file');
// 'file'  → leest data/robots_live.json (simulator of MQTT bridge schrijft dit)
// 'mock'  → leest data/robots_mock.json (statisch, voor testen zonder Python)
// 'api'   → proxy naar externe URL

define('CAMERA_STREAM_URL', 'http://jetson-dang.local:8080');
// URL van de MJPEG stream van de Jetson camera (Team 1)

define('LOW_BATTERY_THRESHOLD', 20);
// Batterij onder deze % → waarschuwing
```

Wachtwoorden zijn nooit in plaintext — enkel bcrypt hashes:
```php
define('USERS', [
    'admin'  => ['hash' => '$2y$12$pRB...', 'role' => 'admin'],
    'viewer' => ['hash' => '$2y$12$hhX...', 'role' => 'viewer'],
]);
```

---

### 3.2 `auth.php`

**Locatie:** `public/includes/auth.php`  
**Doel:** Volledige sessie-authenticatie op één plek.

```php
function attempt_login(string $username, string $password): bool
// Controleert via password_verify() (bcrypt)
// session_regenerate_id(true) na login → beschermt tegen session fixation

function require_login(): void
// Elke pagina en API-endpoint roept dit aan → redirect als niet ingelogd

function is_admin(): bool
// true als ingelogde gebruiker rol 'admin' heeft
```

Sessiecookie instellingen: `httponly`, `SameSite=Strict` → beschermd tegen XSS en CSRF.

---

### 3.3 `dashboard.php`

**Locatie:** `public/dashboard.php`  
**Doel:** Hoofdpagina — geeft HTML-structuur terug, alle live data laadt via JavaScript.

PHP-waarden worden via een verborgen `<div>` aan JavaScript doorgegeven — geen secrets:
```html
<div id="js-config"
  data-poll="500"
  data-api="api/robots.php"
  data-low-battery="20"
  data-role="<?= $role ?>"
  hidden>
</div>
```

Battery Overview wordt server-side weggelaten voor viewers (niet enkel CSS hidden):
```php
<?php if (is_admin()): ?>
  <div class="sidebar-section">BATTERY OVERVIEW</div>
<?php endif; ?>
```

Camera popup: klikken op de thumbnail opent een modal overlay met de volledige stream:
```php
<img id="camera-stream" onclick="openCamModal()" ...>
// Escape of klik buiten → sluit popup
```

---

### 3.4 `api/robots.php`

**Methode:** GET | **Respons:** JSON

```json
{
  "ts": 1714000000,
  "source": "file",
  "robots": [
    {
      "id": "tag10", "label": "R-10",
      "x": 1200.5, "y": 315.0, "heading": 270.0,
      "status": "active", "battery": 87, "override": false
    }
  ]
}
```

**Override prioriteit (hoog → laag):**
```
1. Batterij = 0%       →  altijd offline
2. Admin override      →  status uit robot_overrides.json
3. Live MQTT status    →  status uit robots_live.json
```

---

### 3.5 `api/robot_control.php`

**Methode:** POST | **Admin only**  
**Body:** `{"id": "tag10", "status": "offline"}`

- Schrijft naar `data/robot_overrides.json`
- Status `"active"` → verwijdert de override (robot volgt MQTT weer)
- Atomisch schrijven via tijdelijk bestand + rename

---

### 3.6 `assets/app.js`

**Doel:** Volledige frontend in Vanilla JS — geen externe libraries.

**Polling:**
```javascript
setInterval(fetchRobots, 500);  // elke 500ms
```

**Canvas coördinaten schalen:**
```javascript
function toDisplay(x, y) {
    const scaleX = canvas._dispW / canvas._naturalW;  // display / 2508
    const scaleY = canvas._dispH / canvas._naturalH;  // display / 1696
    return { dx: x * scaleX, dy: y * scaleY };
}
// Robots schalen automatisch mee bij elke schermgrootte
```

**Kalibratie-hoekpunten (rode vierkantjes):**
```javascript
// 4 rode markers op de kaart = de 4 ArUco kalibratieposities van Team 1
// (0,0), (6,0), (0,3), (6,3) in meters → omgezet naar pixels
// Gebruik deze om te verifiëren dat de coördinaten correct zijn
```

**Offline robots bevriezen:**
```javascript
const frozenPos = {};
// Bij offline: robot stopt op zijn laatste bekende positie op de kaart
```

**Camera popup:**
```javascript
function openCamModal()  { document.getElementById('cam-modal').classList.add('open'); }
function closeCamModal() { document.getElementById('cam-modal').classList.remove('open'); }
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeCamModal(); });
```

---

### 3.7 `assets/style.css`

Volledig dark industrial theme. Geen Bootstrap — puur CSS met variabelen.

**Responsive breakpoints:**
```css
@media (max-width: 1024px) { --sidebar-w: 180px; }  /* tablet */
@media (max-width: 768px)  { flex-direction: column-reverse; }  /* mobile */
```

Op mobiel: map boven, sidebar eronder. Canvas schaalt automatisch mee.

---

### 3.8 `mqtt_bridge.py`

**Doel:** Productiecomponent — luistert op MQTT, converteert naar pixels, schrijft JSON.

**MQTT topics:**

| Topic | Inhoud |
|-------|--------|
| `city/robots/tag{id}` | `{"x": 2.5, "y": 1.2, "theta": 1.57}` (meters, radialen) |
| `city/robots/+/battery` | Batterijpercentage |
| `city/camera/topview` | URL van de camera stream |

**180° coördinaatspiegeling:**

De trackfoto is 180° gedraaid t.o.v. het coördinatenstelsel van Team 1 (hun camera heeft de start/finish onderaan, onze foto heeft het bovenaan). Daarom worden beide assen gespiegeld:

```python
def world_to_px(x_m, y_m):
    px = TRACK_OFFSET_X + (1.0 - x_m / WORLD_W) * TRACK_PX_W
    py = TRACK_OFFSET_Y + (1.0 - y_m / WORLD_H) * TRACK_PX_H
    return round(px, 1), round(py, 1)
```

**Huidige kalibratiewaarden** (gemeten op track1.jpg 2508×1696 px):
```python
TRACK_OFFSET_X = 455   # pixels trackrand links
TRACK_OFFSET_Y = 238   # pixels trackrand boven
TRACK_PX_W     = 1620  # breedte rijgedeelte in pixels
TRACK_PX_H     = 1185  # hoogte rijgedeelte in pixels
WORLD_W        = 6.0   # breedte robot city (meter)
WORLD_H        = 3.0   # hoogte robot city (meter)
```

**Offline detectie:** robot zonder update gedurende 5 seconden → status `"offline"`.

**Broker configuratie:**
```python
BROKER_HOST = "jetson-dang.local"  # voor echte robots
# BROKER_HOST = "localhost"        # voor lokale test met Mosquitto
```

---

### 3.9 `simulate_robots.py`

**Doel:** Vervangt de Jetson volledig tijdens ontwikkeling.

**Twee modi:**
- **MQTT beschikbaar** → publiceert op `city/robots/tag<id>` (meters, zelfde formaat als Jetson), schrijft NIET naar bestand (mqtt_bridge.py doet dat)
- **Geen MQTT** → schrijft pixel-coördinaten rechtstreeks naar `robots_live.json`

**MQTT publicatie:**
```python
def mqtt_publish(client, robot_id, x_px, y_px, heading, battery, status):
    x_m, y_m = px_to_world(x_px, y_px)  # pixels → meters
    theta = heading_to_theta(heading)     # graden → radialen
    client.publish(f"city/robots/{robot_id}",
                   json.dumps({"x": x_m, "y": y_m, "theta": theta}))
```

**8 gesimuleerde robots:**

| ID | Label | Snelheid |
|----|-------|----------|
| tag10 | R-10 | 1.00× |
| tag11 | R-11 | 0.90× |
| tag12 | R-12 | 1.10× |
| tag13 | R-13 | 0.80× |
| tag14 | R-14 | 1.20× |
| tag15 | R-15 | 0.95× |
| tag16 | R-16 | 1.05× |
| tag17 | R-17 | 0.85× (gaat periodiek offline als demo) |

---

## 4. Dataflow

```
┌──────────────────────────────────────────────────────────┐
│                   BROWSER (elke 500ms)                   │
│  app.js → fetch("api/robots.php")                        │
│         ← JSON {ts, source, robots:[...]}                │
│  Canvas hertekenen + sidebar updaten + banner checken    │
└──────────────────────┬───────────────────────────────────┘
                       │ HTTP GET (authenticated)
┌──────────────────────▼───────────────────────────────────┐
│                   api/robots.php                         │
│  1. require_login()                                      │
│  2. Lees robots_live.json                                │
│  3. Lees robot_overrides.json                            │
│  4. Prioriteit: batterij=0 > override > live             │
│  5. Saniteer & return JSON                               │
└──────────────────────┬───────────────────────────────────┘
                       │ file read
┌──────────────────────▼───────────────────────────────────┐
│             public/data/robots_live.json                 │
└──────┬───────────────────────────────────────┬───────────┘
       │                                       │
┌──────▼──────────────┐             ┌──────────▼──────────────────┐
│  simulate_robots.py │             │  mqtt_bridge.py             │
│  (testen/demo)      │             │  (productie / lokale test)  │
│                     │             │                             │
│  Modus A: geen MQTT │             │  MQTT ontvangen van:        │
│  → schrijft JSON    │             │  - Jetson (echte robots)    │
│    met pixels       │             │  - simulate_robots (test)   │
│                     │             │                             │
│  Modus B: met MQTT  │             │  world_to_px() + 180° flip  │
│  → publiceert MQTT  │             │  → schrijft JSON            │
│    (meters)         │             │                             │
└─────────────────────┘             └─────────────────────────────┘
         │                                      ▲
         └──────────── MQTT ────────────────────┘
                  via Mosquitto (localhost:1883)
                  of direct naar Jetson
```

---

## 5. Rollen en Rechten

| Functie | Viewer | Admin |
|---------|--------|-------|
| Inloggen | ✅ | ✅ |
| Kaart bekijken | ✅ | ✅ |
| Robot namen & status | ✅ | ✅ |
| Camera stream (thumbnail + popup) | ✅ | ✅ |
| Batterijpercentage per robot | ❌ | ✅ |
| Battery Overview panel | ❌ | ✅ |
| Battery Warning banner | ❌ | ✅ |
| Robot offline/online zetten | ❌ | ✅ |
| Toegang tot `robot_control.php` | ❌ (403) | ✅ |

---

## 6. Robot Offline Zetten

**Als admin:**
1. Klik op de **⏻ knop** naast de robot in de sidebar
2. Robot krijgt status `"offline"` → grijs op de kaart, bevroren positie
3. Klik opnieuw → terug `"active"`

**Wat er technisch gebeurt:**
1. Browser POSTt naar `api/robot_control.php`
2. PHP schrijft `{"tag10": "offline"}` naar `robot_overrides.json`
3. Bij volgende poll overschrijft `api/robots.php` de live status met de override
4. De bridge en simulator respecteren de override ook

---

## 7. Batterij Bewaking

| Niveau | Drempel | Visueel |
|--------|---------|---------|
| Normaal | > 20% | Groene balk |
| Laag | ≤ 20% | Oranje/rode balk + knipperende ring op canvas + banner |
| Leeg | 0% | Robot gaat automatisch offline |

```php
// public/config/config.php
define('LOW_BATTERY_THRESHOLD', 20);
```

---

## 8. Coördinaten en Kaart

### Trackfoto
- **Bestand:** `public/assets/track1.jpg`
- **Afmetingen:** 2508 × 1696 pixels

### Coördinaten Team 1 vs. onze foto

Team 1's camera heeft de **start/finish onderaan** (checkered). Onze foto heeft de **start/finish bovenaan**. Dit is een 180° rotatie — beide assen worden gespiegeld in `world_to_px()`.

```
Team 1 (0,0) = hun linksboven = onze rechtsonder
Team 1 (6,3) = hun rechtsonder = onze linksboven
```

### Kalibratie

De 4 rode vierkantjes op het dashboard tonen de 4 ArUco-kalibratiepunten van Team 1. Vergelijk met hun live camera om de kalibratie te verifiëren.

Aanpassen: open `track1.jpg` in Paint → meet de pixel-coördinaten van de 4 hoeken van het rijgedeelte → vul in:

```python
# mqtt_bridge.py EN public/assets/app.js (zelfde waarden!)
TRACK_OFFSET_X = 455   # pixel x van linkerbovenhoek rijgedeelte
TRACK_OFFSET_Y = 238   # pixel y van linkerbovenhoek rijgedeelte
TRACK_PX_W     = 1620  # breedte rijgedeelte in pixels
TRACK_PX_H     = 1185  # hoogte rijgedeelte in pixels
```

> **Belangrijk:** deze waarden staan op **twee plaatsen**: `mqtt_bridge.py` (voor de conversie) én `app.js` (voor de kalibratiehoekpunten op de kaart). Beide aanpassen bij kalibratie.

---

## 9. Camera Stream

**Huidige URL:** `http://jetson-dang.local:8080`

Instellen in `public/config/config.php`:
```php
define('CAMERA_STREAM_URL', 'http://jetson-dang.local:8080');
```

- De thumbnail verschijnt in de sidebar (groen bolletje = stream actief)
- Klik op de thumbnail → volledig popup-venster
- Escape of klik buiten het venster → sluit popup

---

## 10. Opstarten en Gebruik

### Vereisten
- PHP 8.x
- Python 3.10+ met `paho-mqtt` (`pip install paho-mqtt`)
- Mosquitto MQTT broker (Windows service op `localhost:1883`)

### Modus 1 — Simpel (geen MQTT)
```bash
php -S localhost:8080 -t public   # Terminal 1
python simulate_robots.py          # Terminal 2
```

### Modus 2 — Lokale MQTT test
```bash
python mqtt_bridge.py              # Terminal 1 (verbindt met localhost)
python simulate_robots.py          # Terminal 2 (publiceert MQTT)
php -S localhost:8080 -t public   # Terminal 3
```

### Modus 3 — Echte robots (Jetson)
```bash
# Pas BROKER_HOST = "jetson-dang.local" aan in mqtt_bridge.py
python mqtt_bridge.py              # Terminal 1
php -S localhost:8080 -t public   # Terminal 2
```

### Inloggen

| Gebruikersnaam | Wachtwoord | Rol |
|----------------|-----------|-----|
| `admin` | `password` | Admin |
| `viewer` | `viewer123` | Viewer |

---

## 11. Wachtwoorden Wijzigen

```bash
php -r "echo password_hash('NIEUW_WACHTWOORD', PASSWORD_BCRYPT);"
```

Kopieer de output naar `public/config/config.php`:

```php
define('USERS', [
    'admin' => [
        'hash' => '$2y$12$NIEUWE_HASH_HIER',
        'role' => 'admin',
    ],
]);
```

---

*Documentatie — april 2026*

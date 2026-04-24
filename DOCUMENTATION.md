# RoboTrack Monitor — Volledige Technische Documentatie

**Project:** Intelligent Robotics — Project 6 (EHB)  
**Auteur:** Bouchta Bilal  
**Repo:** https://github.com/Yas3tech/IntelligentRobotics-Project  
**Datum:** April 2026

---

## Inhoudsopgave

1. [Overzicht van het project](#1-overzicht)
2. [Wat de teammate al had vs. wat wij toegevoegd hebben](#2-verschil-teammate-vs-wij)
3. [Bestandsstructuur](#3-bestandsstructuur)
4. [Bestand per bestand uitgelegd](#4-bestanden-uitgelegd)
5. [Hoe de data stroomt](#5-dataflow)
6. [Rollen en rechten](#6-rollen-en-rechten)
7. [Robot offline zetten](#7-robot-offline-zetten)
8. [Batterij bewaking](#8-batterij-bewaking)
9. [Coördinaten en kaart](#9-coordinaten-en-kaart)
10. [Opstarten en gebruik](#10-opstarten-en-gebruik)
11. [Overschakelen van simulator naar echte MQTT](#11-overschakelen-naar-mqtt)
12. [Wachtwoorden wijzigen](#12-wachtwoorden-wijzigen)

---

## 1. Overzicht

RoboTrack Monitor is een webdashboard in PHP dat meerdere autonome robots in real-time volgt op een parcours. Het systeem bestaat uit drie lagen:

```
MQTT Broker (Jetson)
       ↓
mqtt_bridge.py  (Python — converteert MQTT → JSON)
       ↓
robots_live.json  (gedeeld bestand op de server)
       ↓
api/robots.php  (PHP API — beveiligd, past overrides toe)
       ↓
dashboard.php + app.js  (browser — pollt elke 500ms)
```

Tijdens ontwikkeling en testen vervangt `simulate_robots.py` de MQTT bridge — het schrijft hetzelfde JSON-formaat naar `robots_live.json`.

---

## 2. Verschil: Teammate vs. Wij

### Wat de teammate (Yas3tech) al had

| Aanwezig | Beschrijving |
|----------|-------------|
| `public/` map | Basisstructuur van de webserver |
| `README.md` | Minimale beschrijving van het project |
| Initiële commit | Lege of placeholder bestanden |

De repo had **geen werkend dashboard**, geen authenticatie, geen API en geen robot-visualisatie.

---

### Wat wij volledig toegevoegd hebben

| Bestand / Map | Wat het doet |
|---------------|-------------|
| `public/config/config.php` | Centrale configuratie: gebruikers, rollen, databron, camera URL, batterijdrempel |
| `public/includes/auth.php` | Volledige sessie-authenticatie met bcrypt en rolbeheer |
| `public/login.php` | Beveiligde inlogpagina |
| `public/logout.php` | Sessie beëindigen |
| `public/dashboard.php` | Hoofdpagina met kaart, sidebar, camera panel |
| `public/api/robots.php` | JSON API: leest robotdata, past overrides toe, enforceert batterijregel |
| `public/api/robot_control.php` | Admin-only API: robot handmatig offline/online zetten |
| `public/assets/app.js` | Volledige frontend: canvas rendering, polling, tooltips, toggle-knop |
| `public/assets/style.css` | Volledig dark-theme UI |
| `public/assets/track1.jpg` | Foto van het echte parcours (landscape geroteerd) |
| `public/data/robots_mock.json` | Testdata met 8 robots |
| `public/includes/.htaccess` | Blokkeert directe toegang tot PHP-includes |
| `public/.htaccess` | Apache regels: geen directory listing, geen directe JSON toegang |
| `mqtt_bridge.py` | Python bridge: MQTT → robots_live.json (voor echte robots) |
| `simulate_robots.py` | Python simulator: 8 robots op waypoint-pad (voor testen) |
| `DOCUMENTATION.md` | Dit document |
| `.gitignore` | Sluit `.claude/`, live JSON-bestanden uit van git |

---

## 3. Bestandsstructuur

```
IntelligentRobotics-Project/
├── .gitignore
├── README.md
├── DOCUMENTATION.md
├── mqtt_bridge.py              ← Python MQTT bridge (productie)
├── simulate_robots.py          ← Python simulator (testen)
└── public/                     ← Webroot
    ├── .htaccess
    ├── login.php
    ├── logout.php
    ├── dashboard.php
    ├── api/
    │   ├── robots.php          ← GET: robotdata ophalen
    │   └── robot_control.php   ← POST: robot offline/online zetten (admin)
    ├── assets/
    │   ├── app.js              ← Frontend JavaScript
    │   ├── style.css           ← Volledige CSS styling
    │   └── track1.jpg          ← Parcoursfoto
    ├── config/
    │   └── config.php          ← Centrale configuratie
    ├── data/
    │   ├── robots_mock.json    ← Statische testdata
    │   ├── robots_live.json    ← Live data (geschreven door simulator/bridge)
    │   └── robot_overrides.json← Admin overrides (auto-aangemaakt)
    └── includes/
        ├── .htaccess
        └── auth.php            ← Authenticatie & sessies
```

---

## 4. Bestanden Uitgelegd

### 4.1 `config.php`

**Locatie:** `public/config/config.php`  
**Doel:** Één centraal bestand voor alle instellingen. Niets anders in het project heeft hardcoded waarden.

```php
define('USERS', [
    'admin'  => ['hash' => '$2y$12$pRB...', 'role' => 'admin'],
    'viewer' => ['hash' => '$2y$12$hhX...', 'role' => 'viewer'],
]);
```

Gebruikers zijn hardcoded in dit bestand — geen database nodig. De wachtwoorden worden **nooit in plaintext opgeslagen**, alleen als bcrypt hash.

```php
define('DATA_SOURCE', 'file');
```

Bepaalt waar de robotdata vandaan komt:
- `'file'` → leest `data/robots_live.json` (simulator of MQTT bridge schrijft dit)
- `'mock'` → leest `data/robots_mock.json` (statisch, voor testen zonder Python)
- `'api'`  → proxy naar externe URL

```php
define('CAMERA_STREAM_URL', '');
```

URL van de MJPEG stream van de Jetson camera (Team 1). Laat leeg totdat Team 1 de stream actief heeft.

---

### 4.2 `auth.php`

**Locatie:** `public/includes/auth.php`  
**Doel:** Alle authenticatielogica op één plek.

**Belangrijkste functies:**

```php
function session_start_secure(): void
```
Start de PHP sessie met beveiligde instellingen:
- `httponly` cookie → JavaScript kan de sessiecookie **niet** lezen (beschermt tegen XSS)
- `SameSite=Strict` → cookie wordt **niet** meegestuurd bij cross-site requests (beschermt tegen CSRF)

```php
function attempt_login(string $username, string $password): bool
```
Controleert gebruikersnaam + wachtwoord via `password_verify()` (bcrypt). Bij succes:
- `session_regenerate_id(true)` → nieuw sessie-ID na login (beschermt tegen session fixation aanvallen)
- Slaat `user`, `role` en `expires` op in de sessie

```php
function require_login(): void
```
Elke pagina en API-endpoint roept dit aan. Als er geen geldige sessie is → redirect naar `login.php`.

```php
function is_admin(): bool
```
Geeft `true` als de ingelogde gebruiker de rol `'admin'` heeft.

---

### 4.3 `login.php` / `logout.php`

**login.php:** Toont het inlogformulier en verwerkt de POST. Na succesvolle login → redirect naar `dashboard.php`.

**logout.php:** Wist de sessie volledig (`session_destroy()`) en redirect naar `login.php`.

---

### 4.4 `dashboard.php`

**Locatie:** `public/dashboard.php`  
**Doel:** De hoofdpagina. Geeft de HTML-structuur terug; alle live data laadt via JavaScript.

```php
require_login();  // ← Onmogelijk om de pagina te zien zonder in te loggen
```

```html
<div id="js-config"
  data-poll="500"
  data-api="api/robots.php"
  data-low-battery="20"
  data-role="<?= $role ?>"
  hidden>
</div>
```

Dit verborgen `<div>` geeft PHP-waarden door aan JavaScript **zonder secrets bloot te stellen**. JavaScript leest `dataset.role` om te weten of de gebruiker admin of viewer is.

```php
<?php if (is_admin()): ?>
  <div class="sidebar-section"> <!-- Battery Overview --> </div>
<?php endif; ?>
```

De Battery Overview sectie wordt **server-side** weggelaten voor viewers — niet alleen verborgen via CSS, maar echt niet aanwezig in de HTML.

---

### 4.5 `api/robots.php`

**Locatie:** `public/api/robots.php`  
**Methode:** GET  
**Respons:** JSON

Dit is het hart van de API. Het antwoord heeft altijd dit formaat:

```json
{
  "ts": 1714000000,
  "source": "file",
  "robots": [
    {
      "id": "tag10",
      "label": "R-10",
      "x": 1200.5,
      "y": 315.0,
      "heading": 270.0,
      "status": "active",
      "battery": 87,
      "override": false
    }
  ]
}
```

**Override logica — prioriteit van hoog naar laag:**

```
1. Batterij = 0%       →  altijd offline  (hoogste prioriteit)
2. Admin override      →  status uit robot_overrides.json
3. Live status         →  status uit robots_live.json
```

```php
// Admin override wint van live status
if (isset($overrides[$id])) {
    $status = $overrides[$id];
}

// Batterij leeg → automatisch offline
if ($battery === 0) {
    $status = 'offline';
}
```

Alle output wordt gesaniteerd met `htmlspecialchars()` en numerieke waarden worden gecast — nooit ruwe data rechtstreeks aan de browser gegeven.

---

### 4.6 `api/robot_control.php`

**Locatie:** `public/api/robot_control.php`  
**Methode:** POST (admin only)  
**Body:** `{"id": "tag10", "status": "offline"}` of `{"id": "tag10", "status": "active"}`

```php
if (!is_admin()) {
    http_response_code(403);
    echo json_encode(['error' => 'Forbidden — admin only']);
    exit;
}
```

Schrijft naar `data/robot_overrides.json`:
- Status `"offline"` → robot-ID wordt toegevoegd
- Status `"active"` → robot-ID wordt **verwijderd** (robot volgt MQTT/simulator weer)

**Atomisch schrijven** (zodat de PHP API nooit een half-geschreven bestand leest):

```php
$tmp = $overridesFile . '.tmp';
file_put_contents($tmp, json_encode($overrides));
rename($tmp, $overridesFile);  // ← atomische operatie
```

---

### 4.7 `assets/app.js`

**Locatie:** `public/assets/app.js`  
**Doel:** Volledige frontend-logica in Vanilla JavaScript — geen externe libraries.

**Polling:**
```javascript
setInterval(fetchRobots, POLL_MS);  // elke 500ms
```

**Positie bevriezen van offline robots:**
```javascript
const frozenPos = {};

raw.forEach(r => {
    if (r.status !== 'offline') {
        frozenPos[r.id] = { x: r.x, y: r.y, heading: r.heading };
    } else if (frozenPos[r.id]) {
        r.x       = frozenPos[r.id].x;
        r.y       = frozenPos[r.id].y;
        r.heading = frozenPos[r.id].heading;
    }
});
```

Zodra een robot offline gaat, onthoudt de browser zijn laatste positie. Bij elke volgende poll wordt die bevroren positie gebruikt — de robot blijft stilstaan op de kaart.

**Canvas rendering:**

De track-foto is een gewone `<img>`. De `<canvas>` ligt er bovenop (CSS `position: absolute`). Coördinaten worden geschaald van afbeeldingspixels naar schermgrootte:

```javascript
function toDisplay(x, y) {
    const scaleX = canvas._dispW / canvas._naturalW;
    const scaleY = canvas._dispH / canvas._naturalH;
    return { dx: x * scaleX, dy: y * scaleY };
}
```

**Admin toggle-knop:**
```javascript
const toggleHtml = IS_ADMIN
    ? `<button class="robot-toggle${r.status === 'offline' ? ' is-offline' : ''}"
          data-robot-id="${esc(r.id)}"
          data-current="${esc(r.status)}">⏻</button>`
    : '';
```

Enkel zichtbaar voor admins. Bij klik: POST naar `api/robot_control.php` → pagina ververst direct.

**Batterij banner — twee niveaus:**
```javascript
const deadBots = robots.filter(r => r.battery === 0);
const lowBots  = robots.filter(r => r.battery > 0 && r.battery <= LOW_BAT);
```
- 0% → "BATTERIJ LEEG (offline): R-17"
- ≤ 20% → "LAAG: R-14 (18%), R-17 (8%)"

---

### 4.8 `assets/style.css`

Volledig dark industrial theme. Geen Bootstrap — puur CSS met variabelen.

```css
:root {
    --bg-base : #060a10;
    --amber   : #f59e0b;
    --green   : #22c55e;
    --red     : #ef4444;
}
```

Rol badges:
```css
.role-admin  { background: rgba(245,158,11,0.15); color: var(--amber); }
.role-viewer { background: rgba(100,116,139,0.15); color: var(--text-sec); }
```

Robot toggle-knop:
```css
.robot-toggle            { color: var(--text-sec); }
.robot-toggle:hover      { color: var(--green); }   /* → online zetten */
.robot-toggle.is-offline { color: var(--red); }     /* robot is offline */
```

---

### 4.9 `mqtt_bridge.py`

**Doel:** Productiecomponent. Luistert op de MQTT broker van Team 1 en schrijft elke 500ms de robotposities naar `robots_live.json`.

**MQTT topics:**

| Topic | Inhoud |
|-------|--------|
| `city/robots/tag{id}` | `{"x": 2.5, "y": 1.2, "theta": 1.57}` (meters, radialen) |
| `city/robots/+/battery` | Batterijpercentage als getal |
| `city/camera/topview` | URL van de camera stream |

**Coördinatentransformatie (meters → pixels):**
```python
def world_to_px(x_m, y_m):
    px = TRACK_OFFSET_X + (x_m / WORLD_W) * TRACK_PX_W
    py = TRACK_OFFSET_Y + (y_m / WORLD_H) * TRACK_PX_H
    return round(px, 1), round(py, 1)
```

**Heading transformatie:**
```python
def theta_to_heading(theta_rad):
    # MQTT: 0=oost, CCW positief
    # Dashboard: 0=noord, CW positief (kompasrichting)
    return round((90.0 - math.degrees(theta_rad)) % 360.0, 1)
```

Offline detectie: een robot zonder update gedurende 5 seconden krijgt status `"offline"`.

---

### 4.10 `simulate_robots.py`

**Doel:** Vervangt de MQTT bridge tijdens ontwikkeling. Simuleert 8 robots op het parcours.

**8 robots met verschillende snelheden en startposities:**

| ID | Label | Snelheid |
|----|-------|----------|
| tag10 | R-10 | 1.00× |
| tag11 | R-11 | 0.90× |
| tag12 | R-12 | 1.10× |
| tag13 | R-13 | 0.80× |
| tag14 | R-14 | 1.20× |
| tag15 | R-15 | 0.95× |
| tag16 | R-16 | 1.05× |
| tag17 | R-17 | 0.85× |

**Admin overrides lezen:**
```python
def read_overrides():
    if os.path.exists(OVERRIDES_FILE):
        with open(OVERRIDES_FILE, "r") as f:
            return json.load(f)
    return {}
```

Offline robots bevriezen in de simulator:
```python
if status == "offline":
    if r["id"] in frozen:
        x, y, heading = frozen[r["id"]]["x"], ...
else:
    frozen[r["id"]] = {"x": x, "y": y, "heading": heading}
```

**Batterij daalt automatisch bij 0% → status offline:**
```python
elif battery == 0:
    status = "offline"
```

---

## 5. Dataflow

```
┌──────────────────────────────────────────────────────────┐
│                   BROWSER (elke 500ms)                   │
│  app.js → fetch("api/robots.php")                        │
│         ← JSON {ts, source, robots:[...]}                │
│  Canvas hertekenen, sidebar updaten                      │
└──────────────────────┬───────────────────────────────────┘
                       │ HTTP GET (authenticated)
┌──────────────────────▼───────────────────────────────────┐
│                   api/robots.php                         │
│  1. require_login()  → sessie checken                    │
│  2. Lees robots_live.json                                │
│  3. Lees robot_overrides.json                            │
│  4. Prioriteitsregel: batterij=0 > override > live       │
│  5. Saniteer & return JSON                               │
└──────────────────────┬───────────────────────────────────┘
                       │ file read
┌──────────────────────▼───────────────────────────────────┐
│             public/data/robots_live.json                 │
│  Geschreven door: simulate_robots.py OF mqtt_bridge.py   │
└──────────────────────┬───────────────────────────────────┘
           ┌───────────┴───────────┐
           │                       │
┌──────────▼─────────┐   ┌────────▼────────────────────────┐
│  simulate_robots.py │   │  mqtt_bridge.py                 │
│  (testen/demo)      │   │  (productie — echte robots)     │
│  Waypoint animatie  │   │  MQTT → world_to_px() → JSON    │
└─────────────────────┘   └─────────────────────────────────┘
```

---

## 6. Rollen en Rechten

| Functie | Viewer | Admin |
|---------|--------|-------|
| Inloggen | ✅ | ✅ |
| Kaart bekijken | ✅ | ✅ |
| Robot namen & status | ✅ | ✅ |
| Coördinaten & heading | ✅ | ✅ |
| Batterijpercentage per robot | ❌ | ✅ |
| Battery Overview panel | ❌ | ✅ |
| Battery Warning banner | ❌ | ✅ |
| Robot offline/online zetten | ❌ | ✅ |
| Toegang tot `robot_control.php` | ❌ (403) | ✅ |

---

## 7. Robot Offline Zetten

**Als admin:**
1. Klik op de **⏻ knop** naast de robot in de sidebar
2. De robot krijgt status `"offline"` (rode kleur)
3. De robot bevriest op zijn huidige positie op de kaart
4. Klik opnieuw om terug `"active"` te zetten

**Wat er technisch gebeurt:**
1. Browser POSTt naar `api/robot_control.php`
2. PHP schrijft `{"tag10": "offline"}` naar `robot_overrides.json`
3. Bij volgende poll overschrijft `api/robots.php` de live status
4. Simulator leest ook de override en stopt met de positie te berekenen

---

## 8. Batterij Bewaking

| Niveau | Drempel | Visueel effect |
|--------|---------|----------------|
| Normaal | > 20% | Groene balk |
| Laag | ≤ 20% | Oranje/rode balk + knipperende ring op canvas + banner |
| Leeg | 0% | Robot gaat **automatisch offline** |

De drempel is instelbaar:
```php
// public/config/config.php
define('LOW_BATTERY_THRESHOLD', 20);
```

In de simulator daalt de batterij elke 2 minuten met 1%:
```python
battery = max(0, robot["battery"] - int(t / 120))
```

---

## 9. Coördinaten en Kaart

### Afbeelding
- **Bestand:** `public/assets/track1.jpg`
- **Afmetingen:** 2508 × 1696 pixels (landscape)

### Coördinatenstelsel — let op!
Door de 90° rotatie van de foto is de **X-as gespiegeld**:
- Klein X (≈ 361 px) = **RECHTS** op het scherm
- Groot X (≈ 2246 px) = **LINKS** op het scherm

Dit is correct verwerkt in de waypoints van de simulator en in `world_to_px()` van de bridge.

### Track kalibratie
```python
# mqtt_bridge.py
TRACK_OFFSET_X = 267   # grijze rand links (pixels)
TRACK_OFFSET_Y = 204   # grijze rand boven (pixels)
TRACK_PX_W     = 2124  # breedte van het zwarte wegdek (pixels)
TRACK_PX_H     = 1257  # hoogte van het zwarte wegdek (pixels)
WORLD_W        = 6.0   # breedte robot city (meter)
WORLD_H        = 3.0   # hoogte robot city (meter)
```

Formule: `pixel_x = OFFSET_X + (meter_x / WORLD_W) * TRACK_PX_W`

---

## 10. Opstarten en Gebruik

### Vereisten
- PHP 8.x (XAMPP of ingebouwde server)
- Python 3.9+ met `paho-mqtt` (`pip install paho-mqtt`)

### Stap 1 — PHP server starten
```bash
cd IntelligentRobotics-Project/public
php -S localhost:8080
```

### Stap 2 — Simulator starten (voor testen)
```bash
cd IntelligentRobotics-Project
python simulate_robots.py
```

### Stap 3 — Dashboard openen
Ga naar `http://localhost:8080/login.php`

| Gebruikersnaam | Wachtwoord | Rol |
|----------------|-----------|-----|
| `admin` | `password` | Admin |
| `viewer` | `viewer123` | Viewer |

---

## 11. Overschakelen naar MQTT

1. Stop de simulator (`Ctrl+C`)
2. Controleer `mqtt_bridge.py`:
   ```python
   BROKER_HOST = "jetson-dang.local"  # of IP-adres van de Jetson
   BROKER_PORT = 1883
   ```
3. Start de bridge:
   ```bash
   python mqtt_bridge.py
   ```

Het dashboard werkt zonder aanpassingen — `DATA_SOURCE = 'file'` blijft hetzelfde.

**Verschil simulator vs. MQTT:**

| | Simulator | MQTT |
|---|-----------|------|
| Positie bevriezen | In Python (`simulate_robots.py`) | In de browser (`app.js` `frozenPos`) |
| Batterij | Gesimuleerd (daalt per 2 min) | Via `city/robots/+/battery` topic |
| Camera URL | Niet beschikbaar | Via `city/camera/topview` topic |

---

## 12. Wachtwoorden Wijzigen

Wachtwoorden worden **nooit** als plaintext opgeslagen. Om een nieuw wachtwoord in te stellen:

```bash
php -r "echo password_hash('NIEUW_WACHTWOORD', PASSWORD_BCRYPT);"
```

Kopieer de output en plak in `public/config/config.php`:

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

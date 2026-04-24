# RoboTrack Monitor

**Project 6 · EHB Intelligent Robotics**  
Web-dashboard voor live monitoring van autonome robots op een parcours.

---

## Wat doet dit project?

RoboTrack Monitor is een webapplicatie die de positie, richting en batterijstatus van meerdere robots in real-time weergeeft op een kaart van het parcours.

De robots worden gevolgd via ArUco-markers (door Team 1 – Project 1). Hun positie wordt via MQTT doorgestuurd naar dit dashboard. Gebruikers kunnen inloggen en de volledige vloot bewaken vanuit een browser.

---

## Architectuur

```
[ Jetson (Team 1) ]
       │ MQTT (city/robots/#)
       ▼
[ Mosquitto broker ]  ←── localhost:1883 OF jetson-dang.local:1883
       │
       ▼
[ mqtt_bridge.py ]  ←── converteert meters → pixels, schrijft JSON
       │ schrijft elke 500 ms
       ▼
[ public/data/robots_live.json ]
       │ leest via API
       ▼
[ api/robots.php ]  ←── PHP JSON endpoint (beveiligd)
       │ pollt elke 500 ms
       ▼
[ app.js + dashboard.php ]  ←── Browser, tekent robots op canvas
```

Voor testen zonder echte robots: `simulate_robots.py` publiceert op MQTT (zelfde topics als de Jetson) en vervangt Team 1 volledig.

---

## Projectstructuur

```
IntelligentRobotics-Project/
├── mqtt_bridge.py          ← MQTT → JSON bridge (productie + lokale test)
├── simulate_robots.py      ← Simulator: publiceert MQTT + schrijft JSON
├── README.md
├── DOCUMENTATION.md
└── public/                 ← PHP webroot
    ├── login.php
    ├── dashboard.php       ← Hoofdpagina (kaart, sidebar, camera popup)
    ├── logout.php
    ├── api/
    │   ├── robots.php          ← JSON API endpoint
    │   └── robot_control.php   ← Admin: robot offline/online zetten
    ├── assets/
    │   ├── app.js              ← Polling, canvas rendering, camera modal
    │   ├── style.css           ← Dark theme + responsive
    │   └── track1.jpg          ← Top-view foto van het parcours
    ├── config/
    │   └── config.php          ← Centrale configuratie
    ├── data/
    │   ├── robots_mock.json        ← Statische testdata (8 robots)
    │   ├── robots_live.json        ← Geschreven door bridge of simulator
    │   └── robot_overrides.json    ← Admin-overrides (optioneel)
    └── includes/
        └── auth.php            ← Sessie- en authenticatielogica
```

---

## Installatie

**Vereisten**

| Software | Versie | Installatie |
|----------|--------|-------------|
| PHP | 8.0+ | [php.net](https://php.net) |
| Python | 3.10+ | [python.org](https://python.org) |
| paho-mqtt | latest | `pip install paho-mqtt` |
| Mosquitto | latest | [mosquitto.org/download](https://mosquitto.org/download/) |

---

## Opstarten

Er zijn 3 manieren om het project te draaien:

---

### Modus 1 — Simpel (geen MQTT)

Snelste manier om het dashboard te testen. De simulator schrijft rechtstreeks naar het JSON-bestand.

**Terminal 1:**
```bash
php -S localhost:8080 -t public
```

**Terminal 2:**
```bash
python simulate_robots.py
```

---

### Modus 2 — Lokale MQTT simulatie (volledig pipeline testen)

Test het volledige MQTT-traject lokaal. De simulator publiceert dezelfde topics als de echte Jetson.

```
simulate_robots.py  →  MQTT  →  Mosquitto  →  mqtt_bridge.py  →  robots_live.json  →  dashboard
```

> Op Windows installeert Mosquitto zichzelf als Windows-service — het draait automatisch op `localhost:1883`.

**Terminal 1 — MQTT bridge:**
```bash
python mqtt_bridge.py
```

**Terminal 2 — Simulator (publiceert op MQTT):**
```bash
python simulate_robots.py
```

**Terminal 3 — Webserver:**
```bash
php -S localhost:8080 -t public
```

---

### Modus 3 — Met echte robots (Jetson van Team 1)

Zorg dat de Jetson bereikbaar is op het netwerk (`jetson-dang.local`).

**Terminal 1 — MQTT bridge:**
```bash
python mqtt_bridge.py
```

**Terminal 2 — Webserver:**
```bash
php -S localhost:8080 -t public
```

---

Dashboard altijd bereikbaar op: **http://localhost:8080/login.php**

---

## Inloggen

| Gebruiker | Wachtwoord | Rol |
|-----------|------------|-----|
| admin | password | admin |
| viewer | viewer123 | viewer |

Het **admin**-account ziet ook het batterij-overzichtspaneel en kan robots handmatig op offline zetten.

---

## Configuratie

### `public/config/config.php`

| Constante | Beschrijving |
|-----------|--------------|
| `DATA_SOURCE` | `'mock'` (statisch), `'file'` (bridge/simulator), `'api'` (extern) |
| `CAMERA_STREAM_URL` | URL naar MJPEG top-view camera van Team 1 |
| `LOW_BATTERY_THRESHOLD` | Drempel voor batterijwaarschuwing (standaard 20%) |
| `POLL_INTERVAL_MS` | Hoe vaak de browser de API opvraagt (standaard 500 ms) |

### `mqtt_bridge.py`

| Constante | Beschrijving |
|-----------|--------------|
| `BROKER_HOST` | `"localhost"` (lokaal) of `"jetson-dang.local"` (Jetson) |
| `BROKER_PORT` | 1883 (standaard) |
| `WORLD_W` / `WORLD_H` | Wereld-afmetingen in meters (6.0 × 3.0) |
| `TRACK_OFFSET_X/Y` | Pixel-offset van de trackrand in track1.jpg |
| `TRACK_PX_W` / `TRACK_PX_H` | Afmetingen van het rijgedeelte in pixels |
| `OFFLINE_TIMEOUT` | Seconden zonder update voor robot → offline (standaard 5s) |

---

## MQTT Topics (Team 1 – Project 1)

| Topic | Payload | Beschrijving |
|-------|---------|--------------|
| `city/robots/tag<id>` | `{"x": 2.14, "y": 1.39, "theta": 1.57}` | Positie in meters + hoek in radialen |
| `city/robots/<id>/battery` | `{"battery": 72}` | Batterijpercentage (0–100) |
| `city/camera/topview` | `"http://..."` | URL naar top-view camera stream |

---

## Coördinaten kalibratie

Team 1 publiceert in meters (0–6m breed, 0–3m hoog). De bridge converteert naar pixels op `track1.jpg`.

**Belangrijk:** de trackfoto is **180° gedraaid** t.o.v. het coördinatenstelsel van Team 1. De bridge past een spiegeling toe op beide assen:

```python
px = TRACK_OFFSET_X + (1.0 - x_m / WORLD_W) * TRACK_PX_W
py = TRACK_OFFSET_Y + (1.0 - y_m / WORLD_H) * TRACK_PX_H
```

Huidige kalibratiewaarden (gemeten op `track1.jpg` 2508×1696 px):

```python
TRACK_OFFSET_X = 455
TRACK_OFFSET_Y = 238
TRACK_PX_W     = 1620
TRACK_PX_H     = 1185
```

Het dashboard toont **4 rode kalibratiehoekpunten** op de kaart die overeenkomen met de ArUco-kalibratiemarkers van Team 1.

---

## Data flow in detail

1. Team 1 detecteert robots via ArUco-markers en publiceert posities via MQTT op de Jetson broker.
2. `mqtt_bridge.py` ontvangt de berichten, converteert meters → pixels (met 180° spiegeling) en schrijft elke 500 ms atomisch naar `robots_live.json`.
3. `api/robots.php` leest het bestand, valideert de data en past admin-overrides toe.
4. `app.js` pollt de API elke 500 ms en tekent robots als gekleurde cirkels met richtingspijlen op een HTML canvas boven de trackfoto.
5. Bij lage batterij verschijnt een waarschuwingsbanner. Offline robots bevriezen op hun laatste positie.
6. Klik op de top-view camera in de sidebar → opent een volledig popup-venster van de stream.

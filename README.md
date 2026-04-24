# RoboTrack Monitor — Deployment & Security Guide

**Project 6 · Front-end Robot Monitor Dashboard**  
EHB Intelligent Robotics — Bilal / Yassine

---

## Overzicht

Web-dashboard voor live monitoring van meerdere robots:
- Beveiligde login (admin + viewer)
- Live kaart met robotposities via MQTT (Team 1 – ArUco localisation)
- Batterijstatus per robot met waarschuwingen
- Top-view camerastream
- HTTPS op poort 9010

---

## Vereisten

| Software | Versie |
|----------|--------|
| PHP | 8.0+ |
| Python | 3.10+ |
| paho-mqtt | `pip install paho-mqtt` |

---

## Installatie & Opstarten

### Stap 1 — Track afbeelding instellen

Kopieer de top-view foto van het parcours naar:
```
public/assets/track.jpg
```

### Stap 2 — PHP webserver starten

```bash
php -S localhost:8080 -t public
```

Dashboard beschikbaar op: http://localhost:8080/login.php

### Stap 3 — MQTT Bridge starten

Zorg dat de MQTT broker (Jetson van Team 1) bereikbaar is op het netwerk.

```bash
pip install paho-mqtt
python mqtt_bridge.py
```

De bridge subscribeert op `city/robots/#` en schrijft posities naar `public/data/robots_live.json`.

### Stap 4 — HTTPS op poort 9010 (productie)

EHB IT regelt de externe forwarding. Voor lokale HTTPS:

```bash
# Zelfgesigneerd certificaat aanmaken (development)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# PHP met HTTPS draaien via een reverse proxy (bv. Caddy)
# Caddyfile:
# :9010 {
#     tls cert.pem key.pem
#     reverse_proxy localhost:8080
# }
caddy run
```

---

## Gebruikers

| Gebruikersnaam | Wachtwoord | Rol |
|----------------|------------|-----|
| admin | password | admin |
| viewer | viewer123 | viewer |

> **Productie:** verander de wachtwoorden via `config/config.php`:
> ```bash
> php -r "echo password_hash('nieuw_wachtwoord', PASSWORD_BCRYPT);"
> ```
> Plak de output in de `hash` van de gewenste gebruiker.

---

## Configuratie (`public/config/config.php`)

| Constante | Beschrijving |
|-----------|-------------|
| `DATA_SOURCE` | `'mock'` (test) of `'file'` (MQTT bridge) |
| `CAMERA_STREAM_URL` | URL naar MJPEG camera stream van Team 1 |
| `LOW_BATTERY_THRESHOLD` | Batterijdrempel voor waarschuwingen (standaard 20%) |
| `WORLD_W_M` / `WORLD_H_M` | Afmetingen robot city in meters (voor coördinaten-mapping) |
| `POLL_INTERVAL_MS` | Hoe vaak de frontend data ophaalt (ms) |

---

## MQTT Bridge configuratie (`mqtt_bridge.py`)

| Constante | Beschrijving |
|-----------|-------------|
| `BROKER_HOST` | Hostname/IP van de Jetson MQTT broker |
| `BROKER_PORT` | 1883 (standaard) |
| `WORLD_W` / `WORLD_H` | Wereld-afmetingen in meters |
| `IMG_W` / `IMG_H` | Pixel-afmetingen van track.jpg (voor coördinaten-mapping) |
| `OFFLINE_TIMEOUT` | Seconden zonder update voor robot → offline |

### MQTT Topics (Team 1 – Project 1)

| Topic | Payload | Beschrijving |
|-------|---------|-------------|
| `city/robots/tag<id>` | `{"x": 2.14, "y": 1.39, "theta": 1.57}` | Robotpositie (meters, radialen) |
| `city/robots/<id>/battery` | `{"battery": 72}` | Batterijpercentage |
| `city/camera/topview` | `"http://..."` | Camera stream URL |

---

## Coördinaten kalibratie

Team 1 publiceert coördinaten in meters op een `WORLD_W × WORLD_H` meter raster.
De bridge converteert die naar pixels op basis van `IMG_W × IMG_H`.

Na installatie op locatie: meet 2 referentiepunten (bv. hoeken van de track) en
pas `IMG_W`, `IMG_H`, `WORLD_W`, `WORLD_H` aan in `mqtt_bridge.py`.

---

## Security hardening

- Alle routes vereisen sessie-authenticatie
- CSRF tokens op login formulier
- Session fixation preventie (`session_regenerate_id`)
- `HttpOnly` cookies
- Outputs gesanitiseerd met `htmlspecialchars`
- API endpoint (`api/robots.php`) enkel bereikbaar voor ingelogde gebruikers
- `.htaccess` blokkeert directe toegang tot `includes/`

### Productie checklist

- [ ] Wachtwoorden wijzigen in `config.php`
- [ ] HTTPS certificaat installeren
- [ ] `DATA_SOURCE` op `'file'` zetten
- [ ] `CAMERA_STREAM_URL` instellen
- [ ] PHP error display uitschakelen (`display_errors = Off`)
- [ ] `config.php` buiten webroot of via environment variabelen beheren

---

## Projectstructuur

```
IntelligentRobotics-Project/
├── mqtt_bridge.py          ← Python MQTT bridge (apart starten)
├── README.md
└── public/                 ← PHP webroot
    ├── login.php
    ├── dashboard.php
    ├── logout.php
    ├── api/
    │   └── robots.php      ← JSON API endpoint
    ├── assets/
    │   ├── app.js
    │   ├── style.css
    │   └── track.jpg       ← Zelf toevoegen!
    ├── config/
    │   └── config.php
    ├── data/
    │   ├── robots_mock.json
    │   └── robots_live.json ← Geschreven door mqtt_bridge.py
    └── includes/
        └── auth.php
```

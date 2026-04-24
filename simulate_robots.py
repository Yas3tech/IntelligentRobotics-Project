"""
simulate_robots.py — Test simulator voor RoboTrack Dashboard
=============================================================
Simuleert 8 robots die het parcours volgen langs de rode randen.
Schrijft elke 500ms naar public/data/robots_live.json
EN publiceert dezelfde data via MQTT (zelfde topics als echte robots).

Start: python simulate_robots.py
Stop:  Ctrl+C

MQTT topics gepubliceerd:
  city/robots/tag<id>          {"x": ..., "y": ..., "theta": ...}  (meters)
  city/robots/<id>/battery     {"battery": ...}
"""

import json
import math
import os
import time

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False

# ── MQTT configuratie ──────────────────────────────────────────────────
MQTT_ENABLED  = True          # zet op False om MQTT uit te schakelen
BROKER_HOST   = "localhost"   # pas aan naar Jetson IP/hostname indien nodig
BROKER_PORT   = 1883

# Wereld-afmetingen (pixels → meters, omgekeerde van mqtt_bridge.py)
WORLD_W = 6.0
WORLD_H = 3.0
IMG_W   = 2508
IMG_H   = 1696
TRACK_OFFSET_X = 267
TRACK_OFFSET_Y = 204
TRACK_PX_W     = 2124
TRACK_PX_H     = 1257

OUTPUT_FILE    = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "public", "data", "robots_live.json"
)
OVERRIDES_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "public", "data", "robot_overrides.json"
)

# ── RIJPAD — waypoints langs de buitenbaan van het parcours ──────────
# Gedefinieerd in volledige afbeeldingspixels (2508x1696).
# De waypoints volgen de rode/witte randen (binnenste rijlijn).
# Volgorde: met de klok mee.
#
#   361 ──────────────────────────── 2246
#   301  ┌──────────────────────────┐
#        │  ┌────────┐              │
#        │  │ INNER  │              │
#        │  └────────┘              │
#   1360  └──────────────────────────┘
#

# OPGELET: door de -90° rotatie van track1.jpg is de X-as omgekeerd:
#   Klein X (≈361)  = RECHTS op het scherm
#   Groot X (≈2246) = LINKS op het scherm
#   Klein Y (≈310)  = BOVEN op het scherm
#   Groot Y (≈1370) = ONDER op het scherm
#
# Waypoints gaan MET DE KLOK MEE zoals zichtbaar op het scherm:
#   Linksboven → rechtsboven → rechtsonder → linksonder → terug
#
WAYPOINTS = [
    # Linksboven op scherm → rechtsboven (bovenste rechte, x daalt)
    (2180,  320),
    (1700,  315),
    (1200,  312),
    ( 700,  315),
    ( 460,  320),
    # Bocht rechtsboven (op scherm)
    ( 390,  400),
    ( 370,  530),
    # Rechter rechte omlaag (op scherm, x klein)
    ( 361,  700),
    ( 361,  900),
    ( 361, 1100),
    # Bocht rechtsonder (op scherm)
    ( 390, 1280),
    ( 480, 1365),
    # Onderste rechte, rechts → links op scherm (x stijgt)
    ( 700, 1375),
    (1200, 1375),
    (1700, 1375),
    (2100, 1365),
    # Bocht linksonder (op scherm)
    (2220, 1280),
    (2246, 1100),
    # Linker rechte omhoog (op scherm, x groot)
    (2246,  900),
    (2246,  700),
    # Bocht linksboven (op scherm)
    (2220,  400),
    (2180,  320),  # gesloten lus
]

# 8 robots met verschillende startposities en snelheden
ROBOTS = [
    {"id": "tag10", "label": "R-10", "battery": 87, "speed": 1.00, "offset": 0.00},
    {"id": "tag11", "label": "R-11", "battery": 72, "speed": 0.90, "offset": 0.13},
    {"id": "tag12", "label": "R-12", "battery": 55, "speed": 1.10, "offset": 0.25},
    {"id": "tag13", "label": "R-13", "battery": 91, "speed": 0.80, "offset": 0.38},
    {"id": "tag14", "label": "R-14", "battery": 18, "speed": 1.20, "offset": 0.50},
    {"id": "tag15", "label": "R-15", "battery": 68, "speed": 0.95, "offset": 0.63},
    {"id": "tag16", "label": "R-16", "battery": 79, "speed": 1.05, "offset": 0.75},
    {"id": "tag17", "label": "R-17", "battery": 8,  "speed": 0.85, "offset": 0.88},
]


# ── WAYPOINT INTERPOLATIE ─────────────────────────────────────────────

def build_path(waypoints):
    """
    Bouwt een genormaliseerd pad van waypoints.
    Geeft (cumulative_distances, total_length) terug.
    """
    dists = [0.0]
    for i in range(1, len(waypoints)):
        x0, y0 = waypoints[i - 1]
        x1, y1 = waypoints[i]
        dists.append(dists[-1] + math.hypot(x1 - x0, y1 - y0))
    return dists, dists[-1]


WAYPOINTS.reverse()
PATH_DISTS, PATH_TOTAL = build_path(WAYPOINTS)


def position_on_path(progress):
    """
    Geeft (x, y, heading) op het pad op basis van progress [0.0 – 1.0].
    """
    target = (progress % 1.0) * PATH_TOTAL

    # Zoek het segment
    for i in range(1, len(WAYPOINTS)):
        if PATH_DISTS[i] >= target:
            seg_start = PATH_DISTS[i - 1]
            seg_end   = PATH_DISTS[i]
            seg_len   = seg_end - seg_start
            t = (target - seg_start) / seg_len if seg_len > 0 else 0

            x0, y0 = WAYPOINTS[i - 1]
            x1, y1 = WAYPOINTS[i]

            x = x0 + t * (x1 - x0)
            y = y0 + t * (y1 - y0)

            # Heading = richting van dit segment (0=Noord, 90=Oost)
            heading = (math.degrees(math.atan2(x1 - x0, -(y1 - y0)))) % 360

            return round(x, 1), round(y, 1), round(heading, 1)

    # Fallback: laatste waypoint
    x, y = WAYPOINTS[-1]
    return round(x, 1), round(y, 1), 0.0


def robot_state(robot, t):
    """Berekent positie, heading en batterij voor een robot op tijdstip t."""
    # Progress op het pad (snelheid * tijd + startoffset)
    progress = (robot["speed"] * t * 0.004 + robot["offset"]) % 1.0
    x, y, heading = position_on_path(progress)

    # Batterij daalt langzaam
    battery = max(0, robot["battery"] - int(t / 120))

    # R-17 gaat periodiek offline (demo)
    status = "offline" if (robot["id"] == "tag17" and int(t) % 30 < 5) else "active"

    return x, y, heading, battery, status


# ── MAIN ──────────────────────────────────────────────────────────────

def read_overrides():
    """Lees admin-overrides uit robot_overrides.json ({"tag10": "offline", ...})."""
    try:
        if os.path.exists(OVERRIDES_FILE):
            with open(OVERRIDES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def px_to_world(px: float, py: float) -> tuple[float, float]:
    """Converteert pixel-coördinaten terug naar wereld-coördinaten (meters)."""
    x_m = (px - TRACK_OFFSET_X) / TRACK_PX_W * WORLD_W
    y_m = (py - TRACK_OFFSET_Y) / TRACK_PX_H * WORLD_H
    return round(max(0.0, x_m), 3), round(max(0.0, y_m), 3)


def heading_to_theta(heading_deg: float) -> float:
    """Converteert dashboard heading (graden, 0=Noord CW) naar theta (radialen, 0=oost CCW)."""
    return round(math.radians((90.0 - heading_deg) % 360.0), 4)


def mqtt_connect() -> "mqtt.Client | None":
    if not MQTT_ENABLED or not MQTT_AVAILABLE:
        return None
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    try:
        client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
        client.loop_start()
        print(f"[MQTT] Verbonden met {BROKER_HOST}:{BROKER_PORT}")
    except Exception as e:
        print(f"[MQTT] Kan niet verbinden met broker: {e} — MQTT uitgeschakeld")
        return None
    return client


def mqtt_publish(client, robot_id: str, x_px: float, y_px: float,
                 heading: float, battery: int, status: str):
    if client is None:
        return
    x_m, y_m = px_to_world(x_px, y_px)
    theta     = heading_to_theta(heading)

    # Positie topic (zelfde formaat als echte ArUco robots)
    if status == "active":
        client.publish(
            f"city/robots/{robot_id}",
            json.dumps({"x": x_m, "y": y_m, "theta": theta}),
            qos=0,
        )

    # Batterij topic
    if battery >= 0:
        client.publish(
            f"city/robots/{robot_id}/battery",
            json.dumps({"battery": battery}),
            qos=0,
        )


def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    mqtt_client = mqtt_connect()
    if not MQTT_AVAILABLE:
        print("[Simulator] paho-mqtt niet geïnstalleerd — MQTT uitgeschakeld (pip install paho-mqtt)")
    elif not MQTT_ENABLED:
        print("[Simulator] MQTT uitgeschakeld (MQTT_ENABLED = False)")

    # Als MQTT actief is, schrijft mqtt_bridge.py het bestand — niet de simulator zelf
    write_file = mqtt_client is None
    if write_file:
        print(f"[Simulator] Schrijft naar: {OUTPUT_FILE} (geen MQTT — directe modus)")
    else:
        print(f"[Simulator] MQTT modus — mqtt_bridge.py schrijft {OUTPUT_FILE}")
    print(f"[Simulator] {len(WAYPOINTS)} waypoints — robots volgen het parcours")
    print("[Simulator] Open http://localhost:8080/login.php")
    print("[Simulator] Druk Ctrl+C om te stoppen\n")

    t = 0.0
    frozen = {}   # id → {"x": ..., "y": ..., "heading": ...}

    try:
        while True:
            overrides = read_overrides()
            output = []

            for r in ROBOTS:
                x, y, heading, battery, auto_status = robot_state(r, t)

                # Admin override heeft voorrang; daarna batterij-check
                if r["id"] in overrides:
                    status = overrides[r["id"]]
                elif battery == 0:
                    status = "offline"
                else:
                    status = auto_status

                # Bevroren positie: offline robots bewegen niet
                if status == "offline":
                    if r["id"] in frozen:
                        x, y, heading = frozen[r["id"]]["x"], frozen[r["id"]]["y"], frozen[r["id"]]["heading"]
                else:
                    frozen[r["id"]] = {"x": x, "y": y, "heading": heading}

                output.append({
                    "id"     : r["id"],
                    "label"  : r["label"],
                    "x"      : x,
                    "y"      : y,
                    "heading": heading,
                    "status" : status,
                    "battery": battery,
                })

                # Publiceer op MQTT (zelfde topics als echte robots)
                mqtt_publish(mqtt_client, r["id"], x, y, heading, battery, status)

            # Alleen direct naar bestand schrijven als MQTT niet beschikbaar is
            if write_file:
                tmp = OUTPUT_FILE + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(output, f)
                os.replace(tmp, OUTPUT_FILE)

            active = sum(1 for r in output if r["status"] == "active")
            low    = [r["label"] for r in output if 0 <= r["battery"] <= 20]
            mqtt_info = f"| MQTT: {'aan' if mqtt_client else 'uit'}" if MQTT_ENABLED else ""
            print(f"\r[t={t:6.1f}s] {active}/8 actief | Lage batterij: {low if low else 'geen'} {mqtt_info}   ", end="")

            time.sleep(0.5)
            t += 0.5

    except KeyboardInterrupt:
        print("\n[Simulator] Gestopt.")
    finally:
        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()


if __name__ == "__main__":
    main()

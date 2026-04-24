"""
mqtt_bridge.py — RoboTrack MQTT Bridge
=======================================
Subscribeert op MQTT topics van Team 1 (Project 1 – ArUco localisation),
converteert wereld-coördinaten (meters) naar pixel-coördinaten en schrijft
het resultaat elke 500 ms naar public/data/robots_live.json.

Start:  python mqtt_bridge.py
Stop:   Ctrl+C

Vereisten:
    pip install paho-mqtt
"""

import json
import math
import os
import time

import paho.mqtt.client as mqtt

# ============================================================
# CONFIGURATIE — pas aan indien nodig
# ============================================================

BROKER_HOST = "jetson-dang.local"   # hostname of IP van de Jetson MQTT broker
BROKER_PORT = 1883
KEEPALIVE   = 60

# MQTT topics
TOPIC_ROBOTS   = "city/robots/#"        # positie: city/robots/tag<id>
TOPIC_BATTERY  = "city/robots/+/battery"  # batterij (indien beschikbaar)
TOPIC_CAMERA   = "city/camera/topview"    # camera stream URL (indien beschikbaar)

# Wereld-afmetingen robot city (meters) — kalibreer samen met Team 1
WORLD_W = 6.0   # x-as breedte in meter
WORLD_H = 3.0   # y-as hoogte in meter

# Natuurlijke afmetingen van de track-afbeelding (pixels) — landscape na rotatie
IMG_W = 2508
IMG_H = 1696

# ── KALIBRATIE (aanpassen op locatie) ────────────────────────
# Meet in de foto hoeveel pixels de grijze rand breed is.
# Gebruik bv. Paint of GIMP: open track1.jpg en zoek de pixel-
# coördinaten van de linkerbovenhoek en rechteronderhoek
# van het zwarte wegdek (niet de foto-rand).
#
# Stap 1: open public/assets/track1.jpg in een beeldbewerker
# Stap 2: zoek pixel (x,y) van linkerbovenhoek track  → TRACK_OFFSET_X, TRACK_OFFSET_Y
# Stap 3: zoek pixel (x,y) van rechteronderhoek track → bereken TRACK_PX_W en TRACK_PX_H
#
# Zolang je dit niet weet: zet alles op 0 / volledige afbeelding (huidige standaard)
TRACK_OFFSET_X = 455    # pixels zwarte rand links
TRACK_OFFSET_Y = 238    # pixels zwarte rand boven
TRACK_PX_W     = 1620   # breedte van de track in pixels
TRACK_PX_H     = 1185   # hoogte van de track in pixels
# ─────────────────────────────────────────────────────────────

# Robot offline na N seconden zonder update
OFFLINE_TIMEOUT = 5.0

# Schrijf-interval (seconden)
WRITE_INTERVAL = 0.5

# Uitvoerbestand (relatief aan dit script)
OUTPUT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "public", "data", "robots_live.json"
)

# ============================================================
# STATUS kleuren → vertaling van ArUco tracking events
# ============================================================
# Team 1 publiceert alleen positie-updates, geen expliciete status.
# We leiden de status af uit activiteit:
#   - recent update  → active
#   - geen update >5s → offline


# ============================================================
# STATE
# ============================================================
robots: dict = {}
camera_url: str = ""


# ============================================================
# HULPFUNCTIES
# ============================================================

def world_to_px(x_m: float, y_m: float) -> tuple[float, float]:
    """
    Converteert wereld-coördinaten (meters) naar pixel-coördinaten.
    De track-foto is 180° gedraaid t.o.v. Team 1's coördinatenstelsel,
    dus X en Y worden gespiegeld.
    """
    px = TRACK_OFFSET_X + (1.0 - x_m / WORLD_W) * TRACK_PX_W
    py = TRACK_OFFSET_Y + (1.0 - y_m / WORLD_H) * TRACK_PX_H
    return round(px, 1), round(py, 1)


def theta_to_heading(theta_rad: float) -> float:
    """
    Converteert Team 1 theta (radialen, 0=oost, CCW positief)
    naar dashboard heading (graden, 0=noord, CW positief).
    """
    return round((90.0 - math.degrees(theta_rad)) % 360.0, 1)


def robot_label(raw_id: str) -> str:
    """tag10 → R-10"""
    return "R-" + raw_id.replace("tag", "").replace("TAG", "")


# ============================================================
# MQTT CALLBACKS
# ============================================================

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print(f"[MQTT] Verbonden met {BROKER_HOST}:{BROKER_PORT}")
        client.subscribe(TOPIC_ROBOTS)
        client.subscribe(TOPIC_BATTERY)
        client.subscribe(TOPIC_CAMERA)
        print(f"[MQTT] Gesubscribeerd op: {TOPIC_ROBOTS}, {TOPIC_BATTERY}, {TOPIC_CAMERA}")
    else:
        print(f"[MQTT] Verbinding mislukt, code: {reason_code}")


def on_disconnect(client, userdata, reason_code, properties=None):
    print(f"[MQTT] Verbroken (code={reason_code}), herverbinden...")


def on_message(client, userdata, msg):
    global camera_url
    topic   = msg.topic
    payload = msg.payload.decode(errors="replace").strip()

    # ---- Camera URL ----
    if topic == TOPIC_CAMERA:
        camera_url = payload
        print(f"[MQTT] Camera URL ontvangen: {camera_url}")
        return

    # ---- Payload moet JSON zijn ----
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return

    parts = topic.split("/")  # ['city', 'robots', 'tag10'] of ['city','robots','tag10','battery']

    if len(parts) < 3:
        return

    # ---- Batterij: city/robots/<id>/battery ----
    if len(parts) == 4 and parts[3] == "battery":
        robot_id = parts[2]
        battery  = int(data) if isinstance(data, (int, float)) else int(data.get("battery", -1))
        battery  = max(0, min(100, battery))
        if robot_id in robots:
            robots[robot_id]["battery"] = battery
        return

    # ---- Positie: city/robots/tag<id> ----
    if len(parts) == 3:
        robot_id = parts[2]  # bv. "tag10"

        # Valideer payload
        if not isinstance(data, dict):
            return
        if "x" not in data or "y" not in data:
            return

        x_m   = float(data["x"])
        y_m   = float(data["y"])
        theta = float(data.get("theta", 0.0))

        # Klem binnen wereld-grenzen
        x_m = max(0.0, min(WORLD_W, x_m))
        y_m = max(0.0, min(WORLD_H, y_m))

        px, py    = world_to_px(x_m, y_m)
        heading   = theta_to_heading(theta)

        if robot_id not in robots:
            robots[robot_id] = {
                "id"      : robot_id,
                "label"   : robot_label(robot_id),
                "x"       : px,
                "y"       : py,
                "heading" : heading,
                "status"  : "active",
                "battery" : -1,
                "last_seen": time.time(),
            }
            print(f"[Bridge] Nieuwe robot: {robot_id} ({robot_label(robot_id)})")
        else:
            robots[robot_id].update({
                "x"        : px,
                "y"        : py,
                "heading"  : heading,
                "status"   : "active",
                "last_seen": time.time(),
            })


# ============================================================
# OFFLINE DETECTIE & JSON SCHRIJVEN
# ============================================================

def update_statuses():
    now = time.time()
    for r in robots.values():
        if now - r.get("last_seen", now) > OFFLINE_TIMEOUT:
            r["status"] = "offline"


def write_json():
    update_statuses()
    output = [
        {k: v for k, v in r.items() if k != "last_seen"}
        for r in robots.values()
    ]
    tmp = OUTPUT_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(output, f)
        os.replace(tmp, OUTPUT_FILE)  # atomische schrijfoperatie
    except OSError as e:
        print(f"[Bridge] Schrijffout: {e}")


# ============================================================
# MAIN
# ============================================================

def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect    = on_connect
    client.on_message    = on_message
    client.on_disconnect = on_disconnect
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    print(f"[Bridge] Verbinden met {BROKER_HOST}:{BROKER_PORT} ...")
    try:
        client.connect(BROKER_HOST, BROKER_PORT, keepalive=KEEPALIVE)
    except Exception as e:
        print(f"[Bridge] Eerste verbinding mislukt: {e} — herprobeert automatisch")

    client.loop_start()

    print(f"[Bridge] Schrijft naar: {OUTPUT_FILE}")
    print("[Bridge] Druk Ctrl+C om te stoppen\n")

    try:
        while True:
            write_json()
            time.sleep(WRITE_INTERVAL)
    except KeyboardInterrupt:
        print("\n[Bridge] Gestopt.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()

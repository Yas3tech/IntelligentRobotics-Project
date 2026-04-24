"""
simulate_robots.py — Test simulator voor RoboTrack Dashboard
=============================================================
Simuleert 8 robots die het parcours volgen langs de rode randen.
Schrijft elke 500ms naar public/data/robots_live.json.

Start: python simulate_robots.py
Stop:  Ctrl+C
"""

import json
import math
import os
import time

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


def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    print(f"[Simulator] Schrijft naar: {OUTPUT_FILE}")
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
                    # anders laatste berekende positie (eerste keer offline)
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

            tmp = OUTPUT_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(output, f)
            os.replace(tmp, OUTPUT_FILE)

            active = sum(1 for r in output if r["status"] == "active")
            low    = [r["label"] for r in output if 0 <= r["battery"] <= 20]
            print(f"\r[t={t:6.1f}s] {active}/8 actief | Lage batterij: {low if low else 'geen'}   ", end="")

            time.sleep(0.5)
            t += 0.5

    except KeyboardInterrupt:
        print("\n[Simulator] Gestopt.")


if __name__ == "__main__":
    main()

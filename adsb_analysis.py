import os
import requests
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime
from airport_config import AIRPORTS
from threshold_config import THRESHOLDS

# ===== Constants =====
MAX_RADIUS_METERS = 48280  # ~30 mi
AEROAPI_KEY = os.getenv("AEROAPI_KEY", "eGaJ8okficMsluf0vlW5d7t8u1XlpmFJ")
AEROAPI_URL = "https://aeroapi.flightaware.com/aeroapi/flights/search"

# ===== Distance / geometry =====
def haversine(lat1, lon1, alt1, lat2, lon2, alt2):
    # 3D ECEF (WGS-84)
    A = 6378137.0
    F = 1.0 / 298.257223563
    E2 = F * (2.0 - F)

    def to_ecef(lat, lon, alt):
        alt = 0.0 if alt is None else float(alt)
        phi, lam = radians(lat), radians(lon)
        sphi, cphi = sin(phi), cos(phi)
        slam, clam = sin(lam), cos(lam)
        N = A / sqrt(1.0 - E2 * sphi * sphi)
        x = (N + alt) * cphi * clam
        y = (N + alt) * cphi * slam
        z = (N * (1.0 - E2) + alt) * sphi
        return x, y, z

    x1, y1, z1 = to_ecef(lat1, lon1, alt1)
    x2, y2, z2 = to_ecef(lat2, lon2, alt2)
    dx, dy, dz = x1 - x2, y1 - y2, z1 - z2
    return sqrt(dx*dx + dy*dy + dz*dz)

def ground_distance(lat1, lon1, lat2, lon2):
    R = 6_371_000.0
    p1, p2 = radians(lat1), radians(lat2)
    dphi = p2 - p1
    dl = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(p1)*cos(p2)*sin(dl/2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))

def is_ground(plane):
    alt = float(plane.get("Altitude") or 0.0)      # meters
    vel = float(plane.get("Velocity") or 0.0)      # m/s
    vr  = float(plane.get("VerticalRate") or 0.0)  # m/s

    MPS_TO_KT, MPS_TO_FPS = 1.9438444924, 3.28084
    vel_kt, vr_fps = vel * MPS_TO_KT, vr * MPS_TO_FPS

    if alt < 15.0: 
        return True
    if alt < 60.0 and not (vel_kt >= 40.0 or abs(vr_fps) >= 2.0):
        return True
    if alt < 120.0 and vel_kt < 25.0 and abs(vr_fps) < 1.5:
        return True
    return False

def is_airborne(plane):
    return not is_ground(plane)

def fetch_planes_near_airport(airport_code):
    airport = AIRPORTS[airport_code]
    lat, lon = float(airport["lat"]), float(airport["lon"])

    params_bbox = {"lamin": lat - 0.5, "lamax": lat + 0.5, "lomin": lon - 0.5, "lomax": lon + 0.5}

    query = f'-latlong "{params_bbox["lamin"]} {params_bbox["lomin"]} {params_bbox["lamax"]} {params_bbox["lomax"]}"'
    headers = {"x-apikey": AEROAPI_KEY, "Accept": "application/json; charset=UTF-8"}
    params = {"query": query}

    FT_TO_M = 0.3048
    KTS_TO_MPS = 0.514444

    aircraft = []
    try:
        next_url, next_params = AEROAPI_URL, params
        while True:
            resp = requests.get(next_url, headers=headers, params=next_params, timeout=15)
            resp.raise_for_status()
            data = resp.json() or {}

            for f in (data.get("flights") or []):
                lp = f.get("last_position") or {}
                ac_lat = lp.get("latitude")
                ac_lon = lp.get("longitude")
                if ac_lat is None or ac_lon is None:
                    continue

                alt_hund_ft = lp.get("altitude") or 0
                alt_m = max(0.0, float(alt_hund_ft) * 100.0 * FT_TO_M)

                vel_mps = float(lp.get("groundspeed") or 0.0) * KTS_TO_MPS

                dist_h = ground_distance(lat, lon, ac_lat, ac_lon)
                if dist_h > MAX_RADIUS_METERS:
                    continue

                ts = lp.get("timestamp")
                last_contact = ts if isinstance(ts, str) else datetime.utcnow().isoformat()

                p = {
                    "ICAO24": f.get("aircraft") or f.get("fa_flight_id") or "N/A",
                    "Callsign": (f.get("ident") or "N/A").strip(),
                    "Origin Country": None,
                    "Last Contact": last_contact,
                    "Longitude": ac_lon,
                    "Latitude": ac_lat,
                    "Altitude": round(alt_m),
                    "DistanceFromAirport": round(dist_h),
                    "Velocity": vel_mps,
                    "Heading": lp.get("heading"),
                    "VerticalRate": 0.0,
                    "AlertLevel": "NONE",
                    "Conflicts": []
                }
                p["Status"] = "In Air" if is_airborne(p) else "On Ground"
                aircraft.append(p)

            # Paging
            links = data.get("links") or {}
            next_link = (links.get("next") or {}).get("href")
            if not next_link:
                break
            next_url, next_params = next_link, None

        return aircraft

    except requests.RequestException as e:
        print(f"[ERROR] AeroAPI fetch failed: {e}")
        return []

def check_proximity_alerts(planes):
    def sev(lvl): return {"NONE": 0, "WARNING": 1, "ALERT": 2, "ALARM": 3}[lvl]

    for p in planes:
        p["Status"] = "In Air" if is_airborne(p) else "On Ground"

    for i in range(len(planes)):
        for j in range(i + 1, len(planes)):
            p1, p2 = planes[i], planes[j]
            if None in (p1["Latitude"], p1["Longitude"], p2["Latitude"], p2["Longitude"]):
                continue
            if p1.get("ICAO24") == p2.get("ICAO24"):
                continue

            d = haversine(p1["Latitude"], p1["Longitude"], p1["Altitude"],
                          p2["Latitude"], p2["Longitude"], p2["Altitude"])

            g1, g2 = is_ground(p1), is_ground(p2)
            if g1 and g2:
                cat = "Ground-Ground"
            elif not g1 and not g2:
                cat = "Air-Air"
            else:
                cat = "Air-Ground"

            thr = THRESHOLDS[cat]
            if d <= thr["high"]:
                alert = "ALARM"
            elif d <= thr["medium"]:
                alert = "ALERT"
            elif d <= thr["low"]:
                alert = "WARNING"
            else:
                continue

            if sev(alert) > sev(p1["AlertLevel"]):
                p1["AlertLevel"] = alert
            if sev(alert) > sev(p2["AlertLevel"]):
                p2["AlertLevel"] = alert

            p1["Conflicts"].append({"Callsign": p2["Callsign"], "Distance": round(d), "Alert": alert, "Category": cat})
            p2["Conflicts"].append({"Callsign": p1["Callsign"], "Distance": round(d), "Alert": alert, "Category": cat})
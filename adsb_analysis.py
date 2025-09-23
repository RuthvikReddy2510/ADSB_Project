import requests
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime
from airport_config import AIRPORTS
from threshold_config import THRESHOLDS

# constants
MAX_RADIUS_METERS = 48280  # ~30 mi

# geometry
def haversine(lat1, lon1, alt1, lat2, lon2, alt2):
    # 3D ECEF (WGS-84)
    A = 6378137.0
    F = 1.0 / 298.257223563
    E2 = F * (2.0 - F)

    def to_ecef(lat, lon, alt):
        alt = 0.0 if alt is None else alt
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
    # surface GC distance
    R = 6_371_000.0
    p1, p2 = radians(lat1), radians(lat2)
    dphi = p2 - p1
    dl = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(p1)*cos(p2)*sin(dl/2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))

# airborne classifier (robust)
def is_airborne(plane):
    alt = plane.get("Altitude") or 0.0
    vel = plane.get("Velocity") or 0.0
    vr  = plane.get("VerticalRate") or 0.0
    og  = plane.get("OnGround")

    # clamp spikes when flagged ground
    if og is True:
        if vel > 120: vel = 0.0
        if abs(vr) > 2.0: vr = 0.0
        if alt < 5: alt = 0.0

    # strong cues
    if alt > 300 or vel > 80 or abs(vr) > 3.0:
        return True
    if alt < 60 and vel < 10 and abs(vr) < 0.5:
        return False

    # hint from flag (tie-breaker only)
    if og is True and vel < 30 and abs(vr) < 1.5 and alt < 200:
        return False
    if og is False and (alt > 150 or vel > 40 or abs(vr) > 1.0):
        return True

    return False

# data fetch
def fetch_planes_near_airport(airport_code):
    airport = AIRPORTS[airport_code]
    lat, lon = airport["lat"], airport["lon"]

    params = {"lamin": lat - 0.5, "lamax": lat + 0.5, "lomin": lon - 0.5, "lomax": lon + 0.5}

    try:
        resp = requests.get("https://opensky-network.org/api/states/all", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        aircraft = []

        for ac in data.get("states", []):
            ac_lat, ac_lon = ac[6], ac[5]
            if ac_lat is None or ac_lon is None:
                continue

            # prefer baro (7), fallback geo (13)
            alt = (ac[7] if len(ac) > 7 and ac[7] is not None else
                   (ac[13] if len(ac) > 13 and ac[13] is not None else 0.0))
            if not alt or alt < 0:
                alt = 0.0

            # 30-mi horizontal filter
            dist_h = ground_distance(lat, lon, ac_lat, ac_lon)
            if dist_h > MAX_RADIUS_METERS:
                continue

            aircraft.append({
                "ICAO24": ac[0],
                "Callsign": ac[1].strip() if ac[1] else "N/A",
                "Origin Country": ac[2],
                "Last Contact": datetime.fromtimestamp(ac[4]).isoformat() if ac[4] else None,
                "Longitude": ac_lon,
                "Latitude": ac_lat,
                "Altitude": round(alt),
                "DistanceFromAirport": round(dist_h),
                "OnGround": ac[8],
                "Velocity": ac[9] or 0.0,
                "Heading": ac[10],
                "VerticalRate": ac[11] or 0.0,
                "AlertLevel": "NONE",
                "Conflicts": []
            })

        return aircraft

    except requests.RequestException as e:
        print(f"[ERROR] Fetch failed: {e}")
        return []

# conflict detection
def check_proximity_alerts(planes):
    def sev(lvl): return {"NONE": 0, "WARNING": 1, "ALERT": 2, "ALARM": 3}[lvl]

    for i in range(len(planes)):
        for j in range(i + 1, len(planes)):
            p1, p2 = planes[i], planes[j]
            if None in (p1["Latitude"], p1["Longitude"], p2["Latitude"], p2["Longitude"]):
                continue
            if p1.get("ICAO24") == p2.get("ICAO24"):
                continue

            # 3D separation
            d = haversine(p1["Latitude"], p1["Longitude"], p1["Altitude"],
                          p2["Latitude"], p2["Longitude"], p2["Altitude"])

            # category with ground-ground override
            if p1.get("OnGround") is True and p2.get("OnGround") is True:
                cat = "Ground-Ground"
            else:
                a1, a2 = is_airborne(p1), is_airborne(p2)
                if a1 and a2:
                    cat = "Air-Air"
                elif not a1 and not a2:
                    cat = "Ground-Ground"
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

            for p in (p1, p2):
                if sev(alert) > sev(p["AlertLevel"]):
                    p["AlertLevel"] = alert

            p1["Conflicts"].append({"Callsign": p2["Callsign"], "Distance": round(d), "Alert": alert, "Category": cat})
            p2["Conflicts"].append({"Callsign": p1["Callsign"], "Distance": round(d), "Alert": alert, "Category": cat})

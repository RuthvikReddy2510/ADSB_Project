import requests
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime
from airport_config import AIRPORTS
from threshold_config import THRESHOLDS

# Constants
MAX_RADIUS_METERS = 48280  # 30 miles ≈ 48.28 km

def haversine(lat1, lon1, alt1, lat2, lon2, alt2):
    R = 6371000  # Earth radius in meters
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = radians(lat2 - lat1)
    d_lambda = radians(lon2 - lon1)
    a = sin(d_phi / 2)**2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    horizontal_distance = R * c
    vertical_distance = abs((alt1 or 0) - (alt2 or 0))
    return sqrt(horizontal_distance**2 + vertical_distance**2)

def is_airborne(plane):
    """Improved classification of airborne state."""
    alt = plane["Altitude"] or 0
    vel = plane["Velocity"] or 0
    vrate = plane["VerticalRate"] or 0
    return (alt > 150 or vrate > 1 or vel > 30)

def fetch_planes_near_airport(airport_code):
    airport = AIRPORTS[airport_code]
    lat, lon = airport["lat"], airport["lon"]
    
    params = {
        "lamin": lat - 0.5,
        "lamax": lat + 0.5,
        "lomin": lon - 0.5,
        "lomax": lon + 0.5
    }

    try:
        response = requests.get("https://opensky-network.org/api/states/all", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        aircraft_list = []

        for ac in data.get("states", []):
            ac_lat, ac_lon = ac[6], ac[5]
            if ac_lat is None or ac_lon is None:
                continue
            alt = ac[7] if ac[7] and ac[7] > 0 else 0
            distance = haversine(lat, lon, 0, ac_lat, ac_lon, alt)
            if distance > MAX_RADIUS_METERS:
                continue

            aircraft_list.append({
                "ICAO24": ac[0],
                "Callsign": ac[1].strip() if ac[1] else "N/A",
                "Origin Country": ac[2],
                "Last Contact": datetime.fromtimestamp(ac[4]).isoformat(),
                "Longitude": ac_lon,
                "Latitude": ac_lat,
                "Altitude": round(alt),
                "DistanceFromAirport": round(distance),
                "OnGround": ac[8],
                "Velocity": ac[9],
                "Heading": ac[10],
                "VerticalRate": ac[11],
                "AlertLevel": "NONE",
                "Conflicts": []
            })

        return aircraft_list

    except requests.RequestException as e:
        print(f"[ERROR] Fetch failed: {e}")
        return []

def check_proximity_alerts(planes):
    def severity(lvl): return {"NONE": 0, "WARNING": 1, "ALERT": 2, "ALARM": 3}[lvl]

    for i in range(len(planes)):
        for j in range(i + 1, len(planes)):
            p1, p2 = planes[i], planes[j]
            if None in (p1["Latitude"], p1["Longitude"], p2["Latitude"], p2["Longitude"]):
                continue
            distance = haversine(p1["Latitude"], p1["Longitude"], p1["Altitude"],
                                 p2["Latitude"], p2["Longitude"], p2["Altitude"])

            p1_air = is_airborne(p1)
            p2_air = is_airborne(p2)

            if p1_air and p2_air:
                category = "Air-Air"
            elif not p1_air and not p2_air:
                category = "Ground-Ground"
            else:
                category = "Air-Ground"

            thresholds = THRESHOLDS[category]
            if distance <= thresholds["high"]:
                alert = "ALARM"
            elif distance <= thresholds["medium"]:
                alert = "ALERT"
            elif distance <= thresholds["low"]:
                alert = "WARNING"
            else:
                continue

            for p in (p1, p2):
                if severity(alert) > severity(p["AlertLevel"]):
                    p["AlertLevel"] = alert

            p1["Conflicts"].append({
                "Callsign": p2["Callsign"],
                "Distance": round(distance),
                "Alert": alert,
                "Category": category
            })
            p2["Conflicts"].append({
                "Callsign": p1["Callsign"],
                "Distance": round(distance),
                "Alert": alert,
                "Category": category
            })

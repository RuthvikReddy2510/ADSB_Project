import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import requests
import time
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime
from plotter import plot_aircraft_3d
from map_plotter import plot_aircraft_map


# Constants
SEATAC_LAT = 47.4502
SEATAC_LON = -122.3088
SEATAC_ALT = 0
MAX_RADIUS_METERS = 48280  # 30 miles ≈ 48.28 km
PROXIMITY_ALERT_THRESHOLD = 305  # meters
FETCH_INTERVAL_SECONDS = 15

def haversine(lat1, lon1, alt1, lat2, lon2, alt2):
    R = 6371000  # Earth radius in meters
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = radians(lat2 - lat1)
    d_lambda = radians(lon2 - lon1)

    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    horizontal_distance = R * c
    vertical_distance = abs((alt1 or 0) - (alt2 or 0))
    return sqrt(horizontal_distance**2 + vertical_distance**2)

def fetch_planes_near_seatac():
    url = "https://opensky-network.org/api/states/all"
    params = {
        "lamin": SEATAC_LAT - 0.5,
        "lamax": SEATAC_LAT + 0.5,
        "lomin": SEATAC_LON - 0.5,
        "lomax": SEATAC_LON + 0.5
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        aircraft_list = []

        for aircraft in data.get("states", []):
            lon, lat = aircraft[5], aircraft[6]
            if lat is None or lon is None:
                continue

            alt = aircraft[7] if aircraft[7] is not None and aircraft[7] >= 0 else 0
            distance = haversine(SEATAC_LAT, SEATAC_LON, SEATAC_ALT, lat, lon, alt)

            if distance <= MAX_RADIUS_METERS:
                aircraft_list.append({
                    "ICAO24": aircraft[0],
                    "Callsign": aircraft[1].strip() if aircraft[1] else "N/A",
                    "Origin Country": aircraft[2],
                    "Last Contact": datetime.fromtimestamp(aircraft[4]),
                    "Longitude": lon,
                    "Latitude": lat,
                    "Distance from SeaTac (m)": round(distance),
                    "Altitude": round(alt),
                    "On Ground": aircraft[8],
                    "Velocity": aircraft[9],
                    "Heading": aircraft[10],
                    "Vertical Rate": aircraft[11],
                })

        return aircraft_list

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to fetch aircraft data: {e}")
        return []

def check_proximity_alerts(planes):
    # Initialize all planes with AlertLevel = NONE
    for p in planes:
        p['AlertLevel'] = 'NONE'

    def severity_level(level):
        return {'NONE': 0, 'WARNING': 1, 'ALERT': 2, 'ALARM': 3}[level]

    for i in range(len(planes)):
        for j in range(i + 1, len(planes)):
            p1, p2 = planes[i], planes[j]
            distance = haversine(p1["Latitude"], p1["Longitude"], p1["Altitude"],
                                 p2["Latitude"], p2["Longitude"], p2["Altitude"])

            if distance <= 200:
                level = 'ALARM'
            elif distance <= 500:
                level = 'ALERT'
            elif distance <= 1000:
                level = 'WARNING'
            else:
                level = 'NONE'

            if level != 'NONE':
                print(f"""{level}: Aircraft proximity within {int(distance)} meters
  {p1['Callsign']} ({'On Ground' if p1['On Ground'] else 'In Air'}) | Altitude: {p1['Altitude']} m | Velocity: {p1['Velocity']} m/s | Heading Angle: {p1['Heading']}° | Last Contact: {p1['Last Contact']}
  {p2['Callsign']} ({'On Ground' if p2['On Ground'] else 'In Air'}) | Altitude: {p2['Altitude']} m | Velocity: {p2['Velocity']} m/s | Heading Angle: {p2['Heading']}° | Last Contact: {p2['Last Contact']}\n""")

                # Upgrade both aircraft with most severe level seen
                for p in (p1, p2):
                    if severity_level(level) > severity_level(p['AlertLevel']):
                        p['AlertLevel'] = level

# Main loop
if __name__ == "__main__":
    while True:
        print(f"\n Checking aircraft near Sea-Tac ({SEATAC_LAT}, {SEATAC_LON})...")
        planes = fetch_planes_near_seatac()
        planes.sort(key=lambda x: x["Distance from SeaTac (m)"])

        if planes:
            print(f"Found {len(planes)} aircraft within 30 miles:\n")
            for plane in planes:
                print(f"""
   Callsign: {plane['Callsign']}
   Position: ({plane['Latitude']:.4f}, {plane['Longitude']:.4f})
   Distance: {plane['Distance from SeaTac (m)']} m
   Altitude: {plane['Altitude']} m | Velocity: {plane['Velocity']} m/s
   Heading: {plane['Heading']}° | On Ground: {'Yes' if plane['On Ground'] else 'No'}
""")
            print("\n" + "+" * 120 + "\n")
            check_proximity_alerts(planes)
        else:
            print("No aircraft found in the area.")
        plot_aircraft_3d(planes)
        plot_aircraft_map(planes)
        print(f"\n Waiting {FETCH_INTERVAL_SECONDS} seconds before next update...\n" + "*" * 120 + "\n")
        time.sleep(FETCH_INTERVAL_SECONDS)
from flask import Flask, jsonify, render_template, request
from adsb_analysis import fetch_planes_near_airport, check_proximity_alerts
from airport_config import AIRPORTS
from threshold_config import THRESHOLDS

app = Flask(__name__)

@app.route("/")
def home():
    # Extract only lat/lon for JSON serialization
    airport_coords = {
        code: {"lat": data["lat"], "lon": data["lon"]}
        for code, data in AIRPORTS.items()
    }
    return render_template(
        "index.html",
        airports=AIRPORTS,
        thresholds=THRESHOLDS,
        airport_coords=airport_coords  # ✅ this fixes the error
    )

@app.route("/api/planes")
def get_planes():
    airport_code = request.args.get("airport", "SEA").upper()
    threshold_level = request.args.get("threshold", "none").lower()

    # Fetch all aircraft near the selected airport
    planes = fetch_planes_near_airport(airport_code)

    # Check for proximity conflicts (updates each plane's AlertLevel and Conflicts)
    check_proximity_alerts(planes)

    # Return all planes (including those with AlertLevel: NONE)
    return jsonify(planes)

if __name__ == "__main__":
    app.run(debug=True)

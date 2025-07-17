from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from adsb_analysis import fetch_planes_near_airport, check_proximity_alerts
from airport_config import AIRPORTS
from threshold_config import THRESHOLDS

app = Flask(__name__)
app.secret_key = "anicca-demo-key"  # For session handling

# Login Routes

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "admin" and password == "Anicca":
            session["user"] = username
            return redirect(url_for("home"))
        else:
            return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# Main Dashboard

@app.route("/home")
def home():
    if "user" not in session:
        return redirect(url_for("login"))
    
    airport_coords = {
        code: {"lat": data["lat"], "lon": data["lon"]}
        for code, data in AIRPORTS.items()
    }
    return render_template(
        "index.html",
        airports=AIRPORTS,
        thresholds=THRESHOLDS,
        airport_coords=airport_coords
    )

@app.route("/api/planes")
def get_planes():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    airport_code = request.args.get("airport", "SEA").upper()
    threshold_level = request.args.get("threshold", "none").lower()

    planes = fetch_planes_near_airport(airport_code)
    check_proximity_alerts(planes)

    return jsonify(planes)


if __name__ == "__main__":
    app.run(debug=True)

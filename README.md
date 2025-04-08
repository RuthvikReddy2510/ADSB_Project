SeaTac Aircraft Tracker

This is a simple real-time aircraft tracking tool that:
- Fetches aircraft data near SeaTac airport using the OpenSky API
- Detects aircraft proximity alerts (ALARM / ALERT / WARNING)
- Shows aircraft in a 3D view and a live map view

Requirements:
- Python 3.9 or higher

Install the required libraries:
pip install requests plotly pandas flask

How to run:
python adsb_seatac_addon.py

Files:
- adsb_seatac_addon.py : Main logic (fetching, alerts, visualization)
- plotter.py            : 3D aircraft plotting
- map_plotter.py        : Map-based aircraft plotting

import plotly.express as px

def plot_aircraft_map(planes):
    alert_colors = {
        'ALARM': 'red',
        'ALERT': 'orange',
        'WARNING': 'yellow',
        'NONE': 'blue'
    }

    # Prepare data
    df = [{
        'Callsign': p['Callsign'],
        'Latitude': p['Latitude'],
        'Longitude': p['Longitude'],
        'Altitude': p['Altitude'],
        'Status': 'On Ground' if p['On Ground'] else 'In Air',
        'Velocity': p['Velocity'],
        'Heading': p['Heading'],
        'Vertical Rate': p['Vertical Rate'],
        'AlertLevel': p.get('AlertLevel', 'NONE'),
    } for p in planes]

    # Plot using scatter_mapbox
    fig = px.scatter_mapbox(
        df,
        lat='Latitude',
        lon='Longitude',
        color='AlertLevel',
        color_discrete_map=alert_colors,
        hover_data={
            'Callsign': True,
            'Altitude': True,
            'Velocity': True,
            'Heading': True,
            'Vertical Rate': True,
            'Status': True,
            'AlertLevel': False,
            'Latitude': False,
            'Longitude': False
        },
        zoom=9,
        height=700
    )

    # Add SeaTac marker manually
    fig.add_scattermapbox(
        lat=[47.4502],
        lon=[-122.3088],
        mode='markers+text',
        marker=dict(size=14, color='green'),
        text=["SeaTac"],
        textposition="top right",
        name="SeaTac"
    )

    fig.update_layout(
        mapbox_style="carto-positron",
        mapbox_center={"lat": 47.4502, "lon": -122.3088},
        title="Live Aircraft Map View - SeaTac Region",
        margin={"r": 0, "t": 40, "l": 0, "b": 0},
        legend_title="Alert Level"
    )

    fig.show(config={"scrollZoom": True})
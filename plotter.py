import plotly.graph_objects as go

def format_hover(p):
    status = "On Ground" if p["On Ground"] else "In Air"
    return (
        f"Callsign: {p['Callsign']} | "
        f"Status: {status} | "
        f"Altitude: {p['Altitude']} m | "
        f"Velocity: {p['Velocity']} m/s | "
        f"Heading: {p['Heading']}° | "
        f"Vertical Rate: {p['Vertical Rate']} m/s |"
        f"Alert Level: {p['AlertLevel']}"
    )

def plot_aircraft_3d(planes):
    fig = go.Figure()

    alert_levels = {
        'ALARM': 'red',
        'ALERT': 'orange',
        'WARNING': 'yellow',
        'NONE': 'blue'
    }

    # Plot each alert level in a separate trace
    for level, color in alert_levels.items():
        filtered = [p for p in planes if p.get('AlertLevel', 'NONE') == level]
        if not filtered:
            continue  # Skip if no planes in that level

        fig.add_trace(go.Scatter3d(
            x=[p['Latitude'] for p in filtered],
            y=[p['Longitude'] for p in filtered],
            z=[p['Altitude'] for p in filtered],
            mode='markers+text',
            name=level,
            marker=dict(size=6, color=color, opacity=0.9, line=dict(width=1, color='black')),
            text=[p['Callsign'] for p in filtered],
            hovertext=[format_hover(p) for p in filtered],
            hoverinfo='text'
        ))

    # SeaTac reference marker
    fig.add_trace(go.Scatter3d(
        x=[47.4502], y=[-122.3088], z=[0],
        mode='markers+text',
        marker=dict(size=10, color='green'),
        name='SeaTac',
        text=['SeaTac'],
        textposition="bottom center"
    ))

    # Final layout and camera settings
    fig.update_layout(
        scene_camera=dict(
            eye=dict(x=1.5, y=1.5, z=0.5),  # Simulates a low-altitude view from SeaTac outward
            center=dict(x=0, y=0, z=0)
        ),
        scene=dict(
            xaxis_title="Longitude",
            yaxis_title="Latitude",
            zaxis_title="Altitude (m)"
        ),
    title="3D Aircraft View - From SeaTac",
    margin=dict(r=0, l=0, b=0, t=40)
    )


    fig.show()
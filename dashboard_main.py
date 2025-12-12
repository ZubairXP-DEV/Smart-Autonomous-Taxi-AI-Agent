"""
Main entry point for Professional Dashboard using Plotly Dash
"""

from dashboard.app import app

if __name__ == '__main__':
    print("=" * 60)
    print("Smart Autonomous Taxi and Traffic System")
    print("Professional Dashboard - Plotly Dash")
    print("=" * 60)
    print(f"Starting dashboard server...")
    print(f"Open your browser to: http://127.0.0.1:8050")
    print("=" * 60)
    app.run(debug=False, port=8050, host='127.0.0.1')


"""
app.py — Entry point shim.

The real application logic now lives in app_pkg/.
This file exists so Gunicorn/Procfile commands stay the same:
    gunicorn app:app
    python app.py
"""

import os

from app_pkg import create_app

app = create_app()

if __name__ == "__main__":
    from app_pkg.blueprints.api.routes import AVAILABLE_TOOLS

    port = int(os.environ.get("PORT", 5000))
    is_prod = os.environ.get("FLASK_ENV", "development") == "production"

    print("\nServer Starting:")
    print(f"   Environment : {'production' if is_prod else 'development'}")
    print(f"   Port        : {port}")
    print("   Auth        : JWT (access=15m, refresh=30d)")
    print(f"   Tools       : {AVAILABLE_TOOLS}")
    print(
        f"   AI Mentor   : {'enabled' if os.environ.get('GEMINI_API_KEY') else 'disabled (no GEMINI_API_KEY)'}"
    )
    print(f"\n   http://0.0.0.0:{port}\n")

    app.run(host="0.0.0.0", port=port, debug=not is_prod)  # nosec B104

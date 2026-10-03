"""
Root entrypoint for Vercel Python runtime and local executions.
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.db import init_db
from backend.api_server import BusinessPilotAPIHandler, DualHandler

# Initialize database schema on cold start
init_db()

# Expose handler and app for Vercel runtime (supports both BaseHTTPRequestHandler and WSGI)
handler = DualHandler
app = handler

if __name__ == "__main__":
    from http.server import HTTPServer
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), handler)
    print(f"🚀 BusinessPilot running on http://0.0.0.0:{port}/")
    server.serve_forever()

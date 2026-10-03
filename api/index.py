"""
Vercel Serverless Function Entrypoint for BusinessPilot API.
"""
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.db import init_db
from backend.api_server import BusinessPilotAPIHandler, DualHandler

# Initialize database schema on serverless cold start
init_db()

# Expose handler and app for Vercel runtime (supports both BaseHTTPRequestHandler and WSGI)
handler = DualHandler
app = handler

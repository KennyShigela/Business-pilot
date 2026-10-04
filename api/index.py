"""
Vercel Serverless Function Entrypoint for BusinessPilot API.
"""
import os
import sys

# This piece of code below deals with resolving project root paths for Vercel serverless execution
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# This piece of code below deals with exposing WSGI and ASGI entrypoint handlers for serverless requests
from index import handler, app, application, asgi_app

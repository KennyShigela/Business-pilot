"""
Vercel application entrypoint alias for BusinessPilot.
"""
from index import handler, app, application, asgi_app

if __name__ == "__main__":
    from http.server import HTTPServer
    import os
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), handler)
    print(f"🚀 BusinessPilot running on http://0.0.0.0:{port}/")
    server.serve_forever()

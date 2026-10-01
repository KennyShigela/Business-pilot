"""
Unit tests for BusinessPilot API Handler.
Tests all endpoints directly via HTTP request handler simulation.
"""
import unittest
import json
import io
from http.server import HTTPServer
from database.db import init_db
from backend.api_server import BusinessPilotAPIHandler


class MockSocket:
    def __init__(self, data: bytes):
        self.rfile = io.BytesIO(data)
        self.wfile = io.BytesIO()

    def makefile(self, mode: str, bufsize: int = -1):
        if "r" in mode:
            return self.rfile
        return self.wfile

    def sendall(self, data: bytes):
        self.wfile.write(data)

    def send(self, data: bytes):
        self.wfile.write(data)
        return len(data)


def simulate_request(method: str, path: str, body: bytes = b"") -> tuple[int, dict, bytes]:
    """Simulates an HTTP request to BusinessPilotAPIHandler and parses response."""
    req_header = f"{method} {path} HTTP/1.1\r\nHost: localhost\r\nContent-Length: {len(body)}\r\n\r\n".encode("utf-8")
    sock = MockSocket(req_header + body)

    class DummyServer:
        pass

    try:
        handler = BusinessPilotAPIHandler(sock, ("127.0.0.1", 8080), DummyServer())
    except Exception:
        pass

    response_bytes = sock.wfile.getvalue()
    parts = response_bytes.split(b"\r\n\r\n", 1)
    header_part = parts[0].decode("utf-8", errors="ignore")
    body_part = parts[1] if len(parts) > 1 else b""

    # Parse status code
    status_line = header_part.splitlines()[0]
    status_code = int(status_line.split()[1])

    # Parse headers
    headers = {}
    for line in header_part.splitlines()[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()

    return status_code, headers, body_part


class TestAPIServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_health_endpoint(self):
        status, headers, body = simulate_request("GET", "/api/health")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["status"], "ok")

    def test_dashboard_endpoint(self):
        status, headers, body = simulate_request("GET", "/api/dashboard?company_id=company-abc-supermarket-001")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("briefing", data)
        self.assertIn("kpi_cards", data)
        self.assertIn("revenue", data["kpi_cards"])

    def test_sales_endpoint(self):
        status, headers, body = simulate_request("GET", "/api/sales?company_id=company-abc-supermarket-001&limit=5")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("sales", data)

    def test_inventory_endpoint(self):
        status, headers, body = simulate_request("GET", "/api/inventory?company_id=company-abc-supermarket-001")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("summary", data)
        self.assertIn("products", data)

    def test_static_html_serving(self):
        status, headers, body = simulate_request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("content-type", ""))
        self.assertIn(b"Business Pilot", body)


if __name__ == "__main__":
    unittest.main()

"""
Tests for Workspace Registration, Multi-Tenant Session, System Reset, and Empty States.
"""
import unittest
import json
import os
import sys
from io import BytesIO

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.db import init_db, query_all, query_one
from backend.api_server import BusinessPilotAPIHandler


class MockSocket:
    def __init__(self, data=b""):
        self.data = data
        self.output = BytesIO()

    def makefile(self, mode, *args, **kwargs):
        if "r" in mode:
            return BytesIO(self.data)
        elif "w" in mode:
            return self.output
        raise ValueError("Unknown mode: " + mode)

    def sendall(self, data):
        self.output.write(data)


def simulate_request(method, path, body_data=None, headers=None):
    if headers is None:
        headers = {}
    
    body_bytes = b""
    if body_data is not None:
        if isinstance(body_data, dict):
            body_bytes = json.dumps(body_data).encode("utf-8")
        elif isinstance(body_data, str):
            body_bytes = body_data.encode("utf-8")
        headers["Content-Length"] = str(len(body_bytes))
        headers["Content-Type"] = "application/json"

    raw_req = f"{method} {path} HTTP/1.1\r\nHost: localhost\r\n"
    for k, v in headers.items():
        raw_req += f"{k}: {v}\r\n"
    raw_req += "\r\n"
    raw_bytes = raw_req.encode("utf-8") + body_bytes

    sock = MockSocket(raw_bytes)
    try:
        handler = BusinessPilotAPIHandler(sock, ("127.0.0.1", 8080), None)
    except Exception:
        pass

    out_bytes = sock.output.getvalue()
    parts = out_bytes.split(b"\r\n\r\n", 1)
    header_part = parts[0].decode("utf-8", errors="replace")
    body_part = parts[1] if len(parts) > 1 else b""
    
    status_line = header_part.split("\r\n")[0]
    status_code = int(status_line.split(" ")[1])

    return status_code, body_part


class TestAuthAndRegistration(unittest.TestCase):
    def setUp(self):
        init_db()

    def test_session_on_clean_db(self):
        code, body = simulate_request("GET", "/api/auth/session")
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("authenticated", data)
        # For a new visitor with no company_id provided, authenticated must be False
        self.assertFalse(data["authenticated"])
        self.assertIsNone(data["company"])

    def test_register_company_and_user(self):
        payload = {
            "company_name": "Apex Electronics Ltd",
            "user_name": "Kennedy M",
            "email": "kennedy@apexelectronics.com",
            "currency": "USD",
            "business_type": "Retail & Wholesale",
            "country": "Kenya"
        }
        code, body = simulate_request("POST", "/api/auth/register", body_data=payload)
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertEqual(data["company"]["name"], "Apex Electronics Ltd")
        self.assertEqual(data["company"]["currency"], "USD")
        self.assertEqual(data["user"]["name"], "Kennedy M")

        # Verify session endpoint retrieves this newly registered company
        comp_id = data["company"]["id"]
        code2, body2 = simulate_request("GET", f"/api/auth/session?company_id={comp_id}")
        self.assertEqual(code2, 200)
        data2 = json.loads(body2.decode("utf-8"))
        self.assertTrue(data2["authenticated"])
        self.assertEqual(data2["company"]["id"], comp_id)

    def test_dashboard_with_empty_company(self):
        # Register a brand new company (e.g. Alex registering)
        payload = {
            "company_name": "Alex Fresh Business",
            "user_name": "Alex",
            "currency": "USD",
        }
        code, body = simulate_request("POST", "/api/auth/register", body_data=payload)
        comp_id = json.loads(body.decode("utf-8"))["company"]["id"]

        # Call dashboard for this empty company
        code_dash, body_dash = simulate_request("GET", f"/api/dashboard?company_id={comp_id}")
        self.assertEqual(code_dash, 200)
        dash_data = json.loads(body_dash.decode("utf-8"))
        self.assertEqual(dash_data["briefing"]["business_health"], "Awaiting Data")
        self.assertEqual(dash_data["kpi_cards"]["revenue"]["value"], 0.0)
        self.assertEqual(dash_data["kpi_cards"]["net_profit"]["value"], 0.0)
        self.assertEqual(dash_data["kpi_cards"]["expenses"]["value"], 0.0)
        self.assertEqual(dash_data["kpi_cards"]["cash_balance"]["value"], 0.0)
        self.assertFalse(dash_data["cash"]["runway_risk"])
        self.assertEqual(dash_data["cash"]["monthly_burn_rate"], 0.0)
        self.assertEqual(dash_data["trends"], [])

        # Call forecasts for this empty company
        code_fc, body_fc = simulate_request("GET", f"/api/forecasts?company_id={comp_id}")
        self.assertEqual(code_fc, 200)
        fc_data = json.loads(body_fc.decode("utf-8"))
        self.assertIn("historical", fc_data["revenue_forecast"])
        self.assertEqual(fc_data["revenue_forecast"]["historical"], [])

        # Call AI query for this empty company
        ai_payload = {"question": "What is my cash runway?", "company_id": comp_id}
        code_ai, body_ai = simulate_request("POST", "/api/ai/query", body_data=ai_payload)
        self.assertEqual(code_ai, 200)
        ai_data = json.loads(body_ai.decode("utf-8"))
        self.assertTrue(ai_data["success"])
        self.assertIn("USD", ai_data["answer"]["explanation"])

    def test_system_reset(self):
        code, body = simulate_request("POST", "/api/system/reset")
        self.assertEqual(code, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])
        # Ensure companies count is 0 after reset
        comps = query_all("SELECT * FROM companies;")
        self.assertEqual(len(comps), 0)


if __name__ == "__main__":
    unittest.main()

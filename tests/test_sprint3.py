"""
Comprehensive Unit Tests for Sprint 3 Intelligence Layer.
Tests:
- Statistical Forecasting Engine & Confidence Interval Bands
- Proactive Early Warning Alert Engine
- Automated Management PDF/HTML Report Generator
- Controlled AI Analyst & Safe Tool Calling
- Sprint 3 REST API Endpoints
"""
import unittest
import os
import json
import tempfile
from database.db import init_db, get_connection, generate_uuid
from data.sample_generator import generate_abc_supermarket_dataset
from engine.importer import BusinessDataImporter
from engine.forecasting import ForecastingEngine
from engine.alerts_engine import EarlyWarningAlertEngine
from engine.reports import ManagementReportGenerator
from engine.ai_analyst import AIBusinessAnalyst
from tests.test_api_server import simulate_request


class TestSprint3Intelligence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_db_fd, cls.temp_db_path = tempfile.mkstemp(suffix=".db")
        init_db(cls.temp_db_path)
        os.environ["BUSINESS_PILOT_DB"] = cls.temp_db_path

        cls.company_id = "comp-sprint3-test"
        with get_connection(cls.temp_db_path) as conn:
            conn.execute(
                "INSERT INTO companies (id, name, currency) VALUES (?, 'Test Retail Mart', 'TZS');",
                (cls.company_id,),
            )

        # Ingest realistic sample data for mathematical forecasting & alerts
        excel_path = generate_abc_supermarket_dataset()
        importer = BusinessDataImporter(cls.company_id)
        importer.import_excel_workbook(excel_path)

    @classmethod
    def tearDownClass(cls):
        os.close(cls.temp_db_fd)
        if os.path.exists(cls.temp_db_path):
            os.remove(cls.temp_db_path)

    def test_statistical_revenue_forecasting(self):
        engine = ForecastingEngine(self.company_id)
        fc = engine.generate_revenue_forecast(horizon_months=3)

        self.assertIn("forecast_points", fc)
        self.assertEqual(len(fc["forecast_points"]), 3)
        self.assertGreater(fc["overall_confidence"], 0.6)

        # Verify confidence bands: lower_bound <= predicted_revenue <= upper_bound
        for pt in fc["forecast_points"]:
            self.assertLessEqual(pt["lower_bound"], pt["predicted_revenue"])
            self.assertGreaterEqual(pt["upper_bound"], pt["predicted_revenue"])

        self.assertTrue(len(fc["drivers"]) > 0)

    def test_inventory_stockout_forecast(self):
        engine = ForecastingEngine(self.company_id)
        stockouts = engine.generate_inventory_stockout_forecast()
        self.assertIsInstance(stockouts, list)
        if stockouts:
            self.assertIn("days_until_stockout", stockouts[0])
            self.assertIn("recommended_reorder_qty", stockouts[0])
            self.assertIn(stockouts[0]["urgency"], ["CRITICAL", "WARNING"])

    def test_early_warning_alerts_evaluation(self):
        engine = EarlyWarningAlertEngine(self.company_id)
        alerts = engine.evaluate_and_refresh_alerts()
        self.assertGreater(len(alerts), 0)

        # Verify alerts table query with severity ranking
        active = engine.get_active_alerts(severity="ALL")
        self.assertEqual(len(active), len(alerts))
        first_alert = active[0]
        self.assertIn("title", first_alert)
        self.assertIn("severity", first_alert)
        self.assertIn(first_alert["severity"], ["CRITICAL", "WARNING", "ATTENTION", "INFO"])

    def test_management_pdf_report_generation(self):
        generator = ManagementReportGenerator(self.company_id)
        pdf_bytes = generator.generate_pdf_report()
        self.assertGreater(len(pdf_bytes), 1000)
        # PDF files always start with '%PDF-'
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))

    def test_management_html_report_generation(self):
        generator = ManagementReportGenerator(self.company_id)
        html_str = generator.generate_html_report()
        self.assertIn("Management Board Pack", html_str)
        self.assertIn("AI Business Summary", html_str)

    def test_ai_analyst_intent_and_tool_calling(self):
        analyst = AIBusinessAnalyst(self.company_id)

        # 1. Profit Analysis
        res1 = analyst.answer_question("Why did net profit decrease this month?")
        self.assertEqual(res1["intent"], "PROFIT_ANALYSIS")
        self.assertIn("get_profit()", res1["tool_calls"])
        self.assertTrue(len(res1["citations"]) > 0)
        self.assertIn("factors explain this performance", res1["explanation"].lower())

        # 2. Cash Flow Analysis
        res2 = analyst.answer_question("When will our cash balance run out?")
        self.assertEqual(res2["intent"], "CASH_FLOW_ANALYSIS")
        self.assertIn("get_cash_flow()", res2["tool_calls"])

        # 3. Inventory Analysis
        res3 = analyst.answer_question("Which products are low on stock?")
        self.assertEqual(res3["intent"], "INVENTORY_ANALYSIS")
        self.assertIn("get_inventory()", res3["tool_calls"])

    def test_sprint3_api_endpoints(self):
        # 1. GET /api/forecasts
        status, headers, body = simulate_request("GET", f"/api/forecasts?company_id={self.company_id}")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("revenue_forecast", data)

        # 2. GET /api/alerts
        status, headers, body = simulate_request("GET", f"/api/alerts?company_id={self.company_id}")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("alerts", data)

        # 3. GET /api/reports/pdf
        status, headers, body = simulate_request("GET", f"/api/reports/pdf?company_id={self.company_id}")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("content-type"), "application/pdf")
        self.assertTrue(body.startswith(b"%PDF-"))

        # 4. POST /api/ai/query
        post_payload = json.dumps({"question": "Why did profit fall?", "company_id": self.company_id}).encode("utf-8")
        status, headers, body = simulate_request("POST", "/api/ai/query", body=post_payload)
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertIn("answer", data)
        self.assertEqual(data["answer"]["intent"], "PROFIT_ANALYSIS")


if __name__ == "__main__":
    unittest.main()

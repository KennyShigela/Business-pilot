"""
REST API and Web Server for BusinessPilot.
Serves executive business analytics, file upload pipelines, schema mapping,
and frontend dashboard assets.
"""
import os
import sys
import json
import re
import glob
import urllib.parse
import urllib.request
import io
from http.server import HTTPServer, BaseHTTPRequestHandler
from http.client import responses
from typing import Dict, Any, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.db import init_db, query_all, query_one, get_connection, generate_uuid
from data.sample_generator import generate_abc_supermarket_dataset
from engine.ingestion import SpreadsheetReader, StagingManager
from engine.mapping import SchemaMapper
from engine.quality import DataQualityAuditor
from engine.importer import BusinessDataImporter
from engine.analytics import BusinessAnalyticsEngine
from engine.forecasting import ForecastingEngine
from engine.alerts_engine import EarlyWarningAlertEngine
from engine.reports import ManagementReportGenerator
from engine.ai_analyst import AIBusinessAnalyst

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")


def get_upload_dir() -> str:
    """Return upload directory path, safely defaulting to /tmp on serverless (Vercel)."""
    if os.environ.get("VERCEL"):
        upload_dir = "/tmp/uploads"
    else:
        upload_dir = os.path.join(PROJECT_ROOT, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def is_endpoint(path: str, endpoint: str) -> bool:
    """Matches path against target endpoint flexibly (handles trailing slashes and prefix variations)."""
    clean = path.rstrip("/")
    target = endpoint.rstrip("/")
    if not clean or not target:
        return clean == target
    target_no_api = target[4:] if target.startswith("/api/") else None

    if clean == target:
        return True
    if target_no_api and clean == target_no_api:
        return True
    if clean.endswith("/" + target.lstrip("/")):
        return True
    if target_no_api and clean.endswith("/" + target_no_api.lstrip("/")):
        return True
    return False


def resolve_api_path(path: str, headers: Any = None, query: Optional[Dict[str, list]] = None, environ: Optional[Dict[str, Any]] = None) -> str:
    """
    Robustly resolves the canonical API path across all hosting platforms,
    Vercel rewrites, serverless function adapters, and local development.
    """
    candidate_paths = []

    # 1. Check explicit route parameters passed via query rewrite (e.g. ?__route__=$1 or ?route=...)
    if query:
        for q_key in ("__route__", "route", "_route", "__path__", "_path"):
            val = query.get(q_key, [None])[0]
            if val:
                val_str = str(val).strip()
                if not val_str.startswith("/"):
                    val_str = "/" + val_str
                if not val_str.startswith("/api/"):
                    val_str = "/api" + val_str
                candidate_paths.append(val_str)

    # 2. Check rewrite headers from headers and environ (case-insensitive)
    sources = []
    if headers:
        sources.append(headers)
    if environ:
        sources.append(environ)

    header_keys = (
        "x-matched-path",
        "x-forwarded-uri",
        "x-vercel-original-url",
        "x-real-path",
        "x-invoke-path",
        "x-original-url",
        "x-rewrite-path",
        "x-forwarded-path",
        "request_uri",
        "raw_uri",
        "http_x_matched_path",
        "http_x_forwarded_uri",
        "http_x_vercel_original_url",
        "http_x_real_path",
        "http_x_invoke_path",
    )
    for src in sources:
        for hk in header_keys:
            val = None
            if hasattr(src, "get"):
                val = (
                    src.get(hk)
                    or src.get(hk.upper())
                    or src.get(hk.replace("-", "_"))
                    or src.get(hk.replace("-", "_").upper())
                )
            if val and isinstance(val, (str, bytes)):
                val_s = val.decode("utf-8", errors="replace") if isinstance(val, bytes) else str(val)
                parsed_val = urllib.parse.urlparse(val_s).path.strip()
                if parsed_val:
                    candidate_paths.append(parsed_val)

    # 3. Add the incoming path itself
    parsed_incoming = urllib.parse.urlparse(path).path.strip()
    candidate_paths.append(parsed_incoming)

    # 4. Filter and select the best candidate
    entrypoint_names = {
        "/api/index.py", "/api/index", "/index.py", "/app.py", "/api", "/api/",
        "api/index.py", "api/index", "index.py", "app.py", "api", "api/", "/", ""
    }

    chosen = None
    for cand in candidate_paths:
        clean = cand.rstrip("/")
        if clean not in entrypoint_names:
            chosen = clean
            break

    if not chosen:
        chosen = candidate_paths[0].rstrip("/") if candidate_paths else "/"

    # Normalize script prefixes like /api/index.py/api/auth/register -> /api/auth/register
    for script_prefix in ("/api/index.py", "/api/index", "/index.py", "/app.py"):
        if chosen.startswith(script_prefix + "/"):
            chosen = chosen[len(script_prefix):]

    if not chosen.startswith("/"):
        chosen = "/" + chosen

    # If it starts with /auth/ or /dashboard or /analytics etc. but missing /api, prefix with /api
    if not chosen.startswith("/api"):
        api_segments = (
            "/auth/", "/dashboard", "/analytics", "/overview", "/sales",
            "/customers", "/inventory", "/expenses", "/cashflow", "/forecasts",
            "/alerts", "/reports", "/data-sources", "/import-google-sheet",
            "/confirm-import", "/upload-file", "/upload-staged-file",
            "/load-sample", "/system/", "/ai/", "/health", "/companies",
            "/download-file"
        )
        for seg in api_segments:
            if chosen == seg or chosen.startswith(seg):
                chosen = "/api" + chosen
                break

    return chosen


class BusinessPilotAPIHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for BusinessPilot API and Frontend."""

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, file_path: str, content_type: str = "text/html"):
        if not os.path.exists(file_path):
            self.send_error(404, "File Not Found")
            return
        with open(file_path, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        try:
            self._handle_get_internal()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send_json({"error": "Internal Server Error", "details": str(e)}, status=500)

    def _handle_get_internal(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        env = getattr(self, "environ", {})
        path = resolve_api_path(parsed.path, headers=self.headers, query=query, environ=env)

        # Merge any query parameters from headers/environ if present
        for orig_key in ("x-matched-path", "x-forwarded-uri", "x-vercel-original-url", "request_uri"):
            h_val = self.headers.get(orig_key) if hasattr(self.headers, "get") else None
            if not h_val and env:
                h_val = env.get(orig_key) or env.get(orig_key.upper())
            if h_val:
                try:
                    q_extra = urllib.parse.parse_qs(urllib.parse.urlparse(str(h_val)).query)
                    for qk, qv in q_extra.items():
                        if qk not in query:
                            query[qk] = qv
                except Exception:
                    pass

        # 1. Non-API routes: serve static frontend files immediately without DB access
        if not path.startswith("/api"):
            clean_path = path.lstrip("/")
            if not clean_path:
                clean_path = "index.html"

            file_path = os.path.join(FRONTEND_DIR, clean_path)
            if not os.path.exists(file_path):
                file_path = os.path.join(PROJECT_ROOT, clean_path)
            if not os.path.exists(file_path):
                file_path = os.path.join(FRONTEND_DIR, "index.html")
                if not os.path.exists(file_path):
                    file_path = os.path.join(PROJECT_ROOT, "index.html")

            content_type = "text/html"
            if clean_path.endswith(".css"):
                content_type = "text/css"
            elif clean_path.endswith(".js"):
                content_type = "application/javascript"
            elif clean_path.endswith(".json"):
                content_type = "application/json"
            elif clean_path.endswith(".svg"):
                content_type = "image/svg+xml"

            self._send_file(file_path, content_type)
            return

        # 2. Lightweight API routes without DB
        if is_endpoint(path, "/api/health"):
            self._send_json({"status": "ok", "system": "BusinessPilot BOS", "version": "1.0.0"})
            return

        elif is_endpoint(path, "/api") or path in ("/api", "/api/"):
            self._send_json({"status": "ok", "system": "BusinessPilot BOS API", "version": "1.0.0"})
            return

        # 3. Resolve company ID safely: from query parameter, or most recent company in DB
        req_company_id = query.get("company_id", [None])[0]
        if req_company_id and req_company_id.strip():
            company_id = req_company_id.strip()
        else:
            company_id = "unregistered-workspace"

        if is_endpoint(path, "/api/auth/session"):
            active_comp = None
            if req_company_id and req_company_id.strip():
                active_comp = query_one("SELECT * FROM companies WHERE id = ?;", (req_company_id.strip(),))

            all_comps = query_all("SELECT id, name, business_type, currency, country FROM companies ORDER BY name ASC;")
            if active_comp:
                user = query_one("SELECT id, name, email FROM users WHERE company_id = ? ORDER BY created_at ASC LIMIT 1;", (active_comp["id"],)) or {
                    "id": "user-default",
                    "name": "Business Owner",
                    "email": "",
                }
                self._send_json({
                    "authenticated": True,
                    "company": active_comp,
                    "user": user,
                    "companies": all_comps,
                })
            else:
                self._send_json({
                    "authenticated": False,
                    "company": None,
                    "user": None,
                    "companies": [],
                })
            return

        elif is_endpoint(path, "/api/companies"):
            companies = query_all("SELECT * FROM companies ORDER BY name ASC;")
            self._send_json({"companies": companies})
            return

        elif is_endpoint(path, "/api/dashboard"):
            analytics = BusinessAnalyticsEngine(company_id)
            rev = analytics.get_revenue_summary()
            pnl = analytics.get_pnl_statement()
            inv = analytics.get_inventory_health()
            cash = analytics.get_cash_flow_summary()
            trends = analytics.get_revenue_trends()
            briefing = analytics.generate_morning_briefing()

            company = query_one("SELECT * FROM companies WHERE id = ?;", (company_id,)) or {}

            self._send_json({
                "company": company,
                "briefing": briefing,
                "kpi_cards": briefing["kpi_cards"],
                "pnl": pnl,
                "inventory": {
                    "total_value": inv["total_inventory_value"],
                    "healthy_count": inv["healthy_count"],
                    "low_stock_count": inv["low_stock_count"],
                    "out_of_stock_count": inv["out_of_stock_count"],
                    "locked_capital": inv["locked_capital_slow_moving"],
                    "low_stock_items": inv["low_stock_alerts"][:5],
                },
                "cash": cash,
                "trends": trends,
            })
            return

        elif is_endpoint(path, "/api/analytics"):
            analytics = BusinessAnalyticsEngine(company_id)
            self._send_json({
                "revenue": analytics.get_revenue_summary(),
                "expenses": analytics.get_expense_summary(),
                "pnl": analytics.get_pnl_statement(),
                "trends": analytics.get_revenue_trends(),
            })
            return

        elif is_endpoint(path, "/api/sales"):
            limit = int(query.get("limit", [50])[0])
            sql = """
                SELECT 
                    s.id, s.invoice_number, s.sale_date, s.total, s.cost_of_goods, s.profit,
                    s.payment_status, c.name AS customer_name, c.customer_type
                FROM sales s
                LEFT JOIN customers c ON s.customer_id = c.id
                WHERE s.company_id = ?
                ORDER BY s.sale_date DESC, s.created_at DESC
                LIMIT ?;
            """
            sales = query_all(sql, (company_id, limit))
            summary = BusinessAnalyticsEngine(company_id).get_revenue_summary()
            self._send_json({"sales": sales, "summary": summary})
            return

        elif is_endpoint(path, "/api/customers"):
            analytics = BusinessAnalyticsEngine(company_id)
            cust_data = analytics.get_customer_profitability(limit=50)
            self._send_json(cust_data)
            return

        elif is_endpoint(path, "/api/inventory"):
            analytics = BusinessAnalyticsEngine(company_id)
            inv_data = analytics.get_inventory_health()
            sql_all = """
                SELECT 
                    p.id, p.sku, p.name, p.selling_price, p.cost_price, p.reorder_level,
                    COALESCE(SUM(im.quantity), 0.0) AS stock_on_hand,
                    ROUND(COALESCE(SUM(im.quantity), 0.0) * p.cost_price, 2) AS stock_value
                FROM products p
                LEFT JOIN inventory_movements im ON p.id = im.product_id
                WHERE p.company_id = ?
                GROUP BY p.id, p.sku, p.name, p.selling_price, p.cost_price, p.reorder_level
                ORDER BY stock_value DESC;
            """
            products = query_all(sql_all, (company_id,))
            self._send_json({"summary": inv_data, "products": products})
            return

        elif is_endpoint(path, "/api/expenses"):
            analytics = BusinessAnalyticsEngine(company_id)
            exp_summary = analytics.get_expense_summary()
            sql_all = """
                SELECT 
                    e.id, e.description, e.amount, e.expense_date, e.payment_method, e.status,
                    COALESCE(ec.name, 'General') AS category_name,
                    COALESCE(ec.type, 'OPERATING') AS category_type
                FROM expenses e
                LEFT JOIN expense_categories ec ON e.category_id = ec.id
                WHERE e.company_id = ?
                ORDER BY e.expense_date DESC
                LIMIT 50;
            """
            expenses = query_all(sql_all, (company_id,))
            self._send_json({"summary": exp_summary, "expenses": expenses})
            return

        elif is_endpoint(path, "/api/cashflow"):
            analytics = BusinessAnalyticsEngine(company_id)
            cash_summary = analytics.get_cash_flow_summary()
            # Projected next 60 days schedule
            bal = cash_summary["current_cash_balance"]
            burn = cash_summary["monthly_burn_rate"]
            daily_burn = burn / 30.0

            forecast_points = [
                {"day": "+0 (Today)", "balance": round(bal, 2)},
                {"day": "+7 days", "balance": round(bal - (daily_burn * 7) + (bal * 0.05), 2)},
                {"day": "+14 days", "balance": round(bal - (daily_burn * 14) + (bal * 0.08), 2)},
                {"day": "+30 days", "balance": round(bal - burn, 2)},
                {"day": "+60 days", "balance": round(bal - (burn * 2), 2)},
            ]
            self._send_json({"cash_summary": cash_summary, "forecast_points": forecast_points})
            return

        elif is_endpoint(path, "/api/forecasts"):
            engine = ForecastingEngine(company_id)
            rev_fc = engine.generate_revenue_forecast(horizon_months=3)
            stock_fc = engine.generate_inventory_stockout_forecast()
            self._send_json({"revenue_forecast": rev_fc, "stockout_forecast": stock_fc})
            return

        elif is_endpoint(path, "/api/alerts"):
            sev = query.get("severity", ["ALL"])[0]
            engine = EarlyWarningAlertEngine(company_id)
            # Evaluate & refresh alerts
            engine.evaluate_and_refresh_alerts()
            alerts = engine.get_active_alerts(severity=sev)
            self._send_json({"alerts": alerts, "count": len(alerts)})
            return

        elif is_endpoint(path, "/api/reports/pdf"):
            try:
                generator = ManagementReportGenerator(company_id)
                pdf_bytes = generator.generate_pdf_report()
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Disposition", 'attachment; filename="BusinessPilot_Board_Pack.pdf"')
                self.send_header("Content-Length", str(len(pdf_bytes)))
                self.end_headers()
                self.wfile.write(pdf_bytes)
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return

        elif is_endpoint(path, "/api/reports/html"):
            generator = ManagementReportGenerator(company_id)
            html_str = generator.generate_html_report()
            html_bytes = html_str.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(html_bytes)))
            self.end_headers()
            self.wfile.write(html_bytes)
            return

        elif is_endpoint(path, "/api/data-sources"):
            comp_id = query.get("company_id", [None])[0]
            if not comp_id:
                self._send_json({"files": [], "count": 0})
                return

            sql = """
                SELECT 
                    ds.id, ds.name, ds.source_type, ds.file_url, ds.status, ds.created_at,
                    COALESCE(ij.rows_successful, 0) AS total_rows,
                    COALESCE(ij.status, 'COMPLETED') AS job_status
                FROM data_sources ds
                LEFT JOIN import_jobs ij ON ds.id = ij.data_source_id
                WHERE ds.company_id = ?
                ORDER BY ds.created_at DESC;
            """
            sources = query_all(sql, (comp_id,))
            files = []
            for s in sources:
                fpath = s.get("file_url") or ""
                sheet_info = []
                total_rows = s.get("total_rows") or 0
                if fpath and os.path.exists(fpath):
                    try:
                        import pandas as pd
                        if fpath.lower().endswith((".xlsx", ".xls")):
                            xl = pd.ExcelFile(fpath)
                            for s_name in xl.sheet_names:
                                df_s = pd.read_excel(xl, sheet_name=s_name)
                                sheet_info.append({
                                    "name": s_name,
                                    "columns": len([c for c in df_s.columns if not str(c).startswith("Unnamed:")]),
                                    "rows": len(df_s)
                                })
                    except Exception:
                        pass
                files.append({
                    "id": s["id"],
                    "name": s["name"],
                    "source_type": s["source_type"],
                    "status": s["status"] or "Active",
                    "created_at": s["created_at"],
                    "total_rows": total_rows,
                    "sheets": sheet_info,
                    "sheet_count": len(sheet_info),
                    "path": fpath,
                })
            self._send_json({"files": files, "count": len(files)})
            return

        elif is_endpoint(path, "/api/download-file"):
            fname = query.get("file", ["LexCorp_Business_Operations.xlsx"])[0]
            safe_fname = os.path.basename(fname)
            fpath = os.path.join(PROJECT_ROOT, "uploads", safe_fname)
            if not os.path.exists(fpath):
                fpath = os.path.join(PROJECT_ROOT, "data", "samples", safe_fname)
            if os.path.exists(fpath):
                with open(fpath, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                self.send_header("Content-Disposition", f'attachment; filename="{safe_fname}"')
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "File Not Found")
                return

        elif is_endpoint(path, "/api/ai/status"):
            has_env_key = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
            self._send_json({
                "success": True,
                "has_env_key": has_env_key,
                "model": "gemini-1.5-flash",
                "free_tier_limits": {
                    "requests_per_minute": 15,
                    "tokens_per_minute": 1000000,
                    "requests_per_day": 1500,
                    "cost": "$0.00 (Completely Free via Google AI Studio)"
                },
                "pay_as_you_go_pricing": {
                    "input_tokens_per_million": "$0.075",
                    "output_tokens_per_million": "$0.30",
                    "average_cost_per_query": "~$0.0001"
                }
            })
            return

        self.send_error(404, "Endpoint not found")

    def do_POST(self):
        try:
            self._handle_post_internal()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send_json({"error": "Internal Server Error", "details": str(e)}, status=500)

    def _handle_post_internal(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        env = getattr(self, "environ", {})
        path = resolve_api_path(parsed.path, headers=self.headers, query=query, environ=env)

        # Merge any query parameters from headers/environ if present
        for orig_key in ("x-matched-path", "x-forwarded-uri", "x-vercel-original-url", "request_uri"):
            h_val = self.headers.get(orig_key) if hasattr(self.headers, "get") else None
            if not h_val and env:
                h_val = env.get(orig_key) or env.get(orig_key.upper())
            if h_val:
                try:
                    q_extra = urllib.parse.parse_qs(urllib.parse.urlparse(str(h_val)).query)
                    for qk, qv in q_extra.items():
                        if qk not in query:
                            query[qk] = qv
                except Exception:
                    pass

        # Extract body safely across BaseHTTPRequestHandler and WSGI/ASGI
        try:
            cl = int(
                self.headers.get("content-length")
                or self.headers.get("Content-Length")
                or (env.get("CONTENT_LENGTH") if env else 0)
                or 0
            )
        except Exception:
            cl = 0

        body = b""
        if hasattr(self, "raw_body") and self.raw_body:
            body = self.raw_body
        elif cl > 0:
            body = self.rfile.read(cl)
        else:
            try:
                body = self.rfile.read()
            except Exception:
                body = b""

        if not body and hasattr(self, "rfile") and hasattr(self.rfile, "getvalue"):
            body = self.rfile.getvalue()

        if is_endpoint(path, "/api/load-sample"):
            company_id = "company-abc-supermarket-001"
            init_db()

            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO companies (id, name, business_type, industry, country, currency)
                    VALUES (?, 'ABC Supermarket Ltd', 'Retail', 'Supermarket', 'Tanzania', 'TZS');
                    """,
                    (company_id,),
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO users (id, company_id, name, email, password_hash)
                    VALUES ('user-kennedy-001', ?, 'Kennedy', 'kennedy@abcsupermarket.co.tz', 'hash_secret_123');
                    """,
                    (company_id,),
                )

            excel_path = generate_abc_supermarket_dataset()
            importer = BusinessDataImporter(company_id)
            res = importer.import_excel_workbook(excel_path)
            self._send_json({"success": True, "message": "Loaded ABC Supermarket Ltd sample dataset", "result": res})
            return

        elif is_endpoint(path, "/api/upload-file"):
            try:
                data = json.loads(body.decode("utf-8"))
                file_name = data.get("file_name", "upload.xlsx")
                file_base64 = data.get("file_base64", "")
                company_id = data.get("company_id", "company-abc-supermarket-001")

                import base64
                file_bytes = base64.b64decode(file_base64)
                
                upload_dir = get_upload_dir()
                save_path = os.path.join(upload_dir, file_name)
                with open(save_path, "wb") as f:
                    f.write(file_bytes)

                # Inspect and Auto-map
                inspection = SpreadsheetReader.inspect_file(save_path)
                mapped_sheets = {}
                for sheet in inspection["sheets"].keys():
                    df = SpreadsheetReader.load_full_sheet(save_path, sheet_name=sheet)
                    mapping_res = SchemaMapper.map_columns(list(df.columns), sheet_name=sheet)
                    mapped_sheets[sheet] = mapping_res

                self._send_json({
                    "success": True,
                    "file_path": save_path,
                    "inspection": inspection,
                    "mappings": mapped_sheets,
                })
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=400)
            return

        elif is_endpoint(path, "/api/upload-staged-file"):
            try:
                data = json.loads(body.decode("utf-8")) if body else {}
                file_name = data.get("file_name", "LexCorp_Business_Operations.xlsx")
                company_id = data.get("company_id", "company-16cb6e90")

                upload_dir = get_upload_dir()
                target_path = os.path.join(upload_dir, file_name)

                if not os.path.exists(target_path):
                    src_sample = os.path.join(PROJECT_ROOT, "data", "samples", file_name)
                    if os.path.exists(src_sample):
                        import shutil
                        shutil.copy(src_sample, target_path)

                inspection = SpreadsheetReader.inspect_file(target_path)
                mapped_sheets = {}
                for sheet in inspection["sheets"].keys():
                    df = SpreadsheetReader.load_full_sheet(target_path, sheet_name=sheet)
                    mapping_res = SchemaMapper.map_columns(list(df.columns), sheet_name=sheet)
                    mapped_sheets[sheet] = mapping_res

                self._send_json({
                    "success": True,
                    "file_path": target_path,
                    "inspection": inspection,
                    "mappings": mapped_sheets,
                })
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=400)
            return

        elif is_endpoint(path, "/api/auth/register"):
            try:
                init_db()
                data = json.loads(body.decode("utf-8")) if body else {}
                company_name = data.get("company_name", "").strip()
                user_name = data.get("user_name", "Admin").strip()
                email = data.get("email", "").strip()
                currency = data.get("currency", "USD").strip().upper() or "USD"
                business_type = data.get("business_type", "Retail").strip()
                country = data.get("country", "Tanzania").strip()

                if not company_name:
                    self._send_json({"success": False, "error": "Company name is required."}, status=400)
                    return

                company_id = f"company-{generate_uuid()[:8]}"
                user_id = f"user-{generate_uuid()[:8]}"
                user_email = email if email else f"{user_name.lower().replace(' ', '')}_{company_id[8:]}@example.com"

                with get_connection() as conn:
                    conn.execute(
                        """
                        INSERT INTO companies (id, name, business_type, industry, country, currency, email)
                        VALUES (?, ?, ?, ?, ?, ?, ?);
                        """,
                        (company_id, company_name, business_type, business_type, country, currency, user_email),
                    )
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM users WHERE email = ?;", (user_email,))
                    existing = cursor.fetchone()
                    if existing:
                        user_id = existing[0]
                        conn.execute("UPDATE users SET company_id = ?, name = ? WHERE id = ?;", (company_id, user_name, user_id))
                    else:
                        conn.execute(
                            """
                            INSERT INTO users (id, company_id, name, email, password_hash)
                            VALUES (?, ?, ?, ?, 'demo_hash');
                            """,
                            (user_id, company_id, user_name, user_email),
                        )

                self._send_json({
                    "success": True,
                    "company": {
                        "id": company_id,
                        "name": company_name,
                        "currency": currency,
                        "business_type": business_type,
                        "country": country,
                    },
                    "user": {
                        "id": user_id,
                        "name": user_name,
                        "email": user_email,
                    },
                })
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=400)
            return

        elif is_endpoint(path, "/api/system/reset"):
            try:
                with get_connection() as conn:
                    conn.execute("PRAGMA foreign_keys = OFF;")
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
                    tables = [row[0] for row in cursor.fetchall()]
                    for t in tables:
                        conn.execute(f"DELETE FROM {t};")
                    conn.execute("PRAGMA foreign_keys = ON;")

                upload_dir = os.path.join(PROJECT_ROOT, "uploads")
                if os.path.exists(upload_dir):
                    for f in glob.glob(os.path.join(upload_dir, "*")):
                        try:
                            os.remove(f)
                        except Exception:
                            pass

                self._send_json({"success": True, "message": "All data cleared successfully. System ready for registration."})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=500)
            return

        elif is_endpoint(path, "/api/import-google-sheet"):
            try:
                data = json.loads(body.decode("utf-8"))
                url = data.get("url", "").strip()
                company_id = data.get("company_id", "company-default")

                if not url:
                    self._send_json({"success": False, "error": "Google Sheets link is required."}, status=400)
                    return

                sheet_match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
                if not sheet_match:
                    self._send_json({
                        "success": False,
                        "error": "Invalid Google Sheets link. Please provide a link formatted like: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/...",
                    }, status=400)
                    return

                sheet_id = sheet_match.group(1)
                export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"

                upload_dir = get_upload_dir()
                save_path = os.path.join(upload_dir, f"google_sheet_{sheet_id[:8]}.xlsx")

                # Try direct download
                try:
                    req = urllib.request.Request(
                        export_url,
                        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
                    )
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        content = resp.read()
                        with open(save_path, "wb") as f:
                            f.write(content)
                except Exception as net_err:
                    self._send_json({
                        "success": False,
                        "error": f"Direct Google Sheets download was unable to connect ({str(net_err)}). Please ensure link sharing is set to 'Anyone with the link can view'. Alternatively, in Google Sheets click: File > Download > Microsoft Excel (.xlsx) and drag-and-drop the file into the upload zone above!",
                    }, status=400)
                    return

                # Inspect and auto-map
                inspection = SpreadsheetReader.inspect_file(save_path)
                mapped_sheets = {}
                for sheet in inspection["sheets"].keys():
                    df = SpreadsheetReader.load_full_sheet(save_path, sheet_name=sheet)
                    mapping_res = SchemaMapper.map_columns(list(df.columns), sheet_name=sheet)
                    mapped_sheets[sheet] = mapping_res

                self._send_json({
                    "success": True,
                    "file_path": save_path,
                    "inspection": inspection,
                    "mappings": mapped_sheets,
                })
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=400)
            return

        elif is_endpoint(path, "/api/confirm-import"):
            try:
                data = json.loads(body.decode("utf-8"))
                file_path = data.get("file_path")
                company_id = data.get("company_id", "company-abc-supermarket-001")

                importer = BusinessDataImporter(company_id)
                res = importer.import_excel_workbook(file_path)

                # Proactively refresh alerts based on the newly imported data
                try:
                    EarlyWarningAlertEngine(company_id).evaluate_and_refresh_alerts()
                except Exception:
                    pass

                self._send_json({"success": True, "result": res})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=400)
            return

        elif is_endpoint(path, "/api/ai/query"):
            try:
                data = json.loads(body.decode("utf-8"))
                question = data.get("question", "")
                company_id = data.get("company_id", "company-abc-supermarket-001")
                conv_id = data.get("conversation_id")

                api_key = data.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

                analyst = AIBusinessAnalyst(company_id)
                answer_result = analyst.answer_question(question, conversation_id=conv_id, api_key=api_key)
                self._send_json({"success": True, "answer": answer_result})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, status=400)
            return

        self.send_error(404, "Endpoint not found")


class WSGIHandler(BusinessPilotAPIHandler):
    """Internal request handler for WSGI-adapted environments."""

    def __init__(self, path: str, method: str, body: bytes, headers: Dict[str, str], environ: Optional[Dict[str, Any]] = None):
        self.path = path
        self.command = method
        self.raw_body = body
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.headers = headers
        self.environ = environ or {}
        self.server_version = "BusinessPilot/1.0"
        self.sys_version = ""
        self.response_status = 200
        self.response_headers = []

    def send_response(self, code: int, message: Optional[str] = None):
        self.response_status = code

    def send_header(self, keyword: str, value: Any):
        self.response_headers.append((keyword, str(value)))

    def end_headers(self):
        pass

    def send_error(self, code: int, message: Optional[str] = None, explain: Optional[str] = None):
        self.response_status = code
        self.response_headers.append(("Content-Type", "application/json"))
        err_body = json.dumps({"error": message or str(code)}).encode("utf-8")
        self.wfile.write(err_body)


async def handle_asgi(scope: Dict[str, Any], receive: Any, send: Any):
    """ASGI 3 request processor for Vercel Python runtime."""
    if scope.get("type") == "lifespan":
        while True:
            msg = await receive()
            if msg.get("type") == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif msg.get("type") == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
        return

    if scope.get("type") != "http":
        return

    method = scope.get("method", "GET").upper()
    path = scope.get("path", "/")
    qs = scope.get("query_string", b"")
    if isinstance(qs, bytes):
        qs = qs.decode("utf-8", errors="replace")
    full_path = f"{path}?{qs}" if qs else path

    body = b""
    more_body = True
    while more_body:
        msg = await receive()
        body += msg.get("body", b"")
        more_body = msg.get("more_body", False)

    headers = {}
    for k, v in scope.get("headers", []):
        k_str = k.decode("latin1") if isinstance(k, bytes) else str(k)
        v_str = v.decode("latin1") if isinstance(v, bytes) else str(v)
        headers[k_str.lower()] = v_str
        headers[k_str.replace("_", "-").lower()] = v_str

    inst = WSGIHandler(full_path, method, body, headers, environ=scope)
    if method == "GET":
        inst.do_GET()
    elif method == "POST":
        inst.do_POST()
    elif method == "OPTIONS":
        inst.do_OPTIONS()
    else:
        inst.send_error(405, "Method Not Allowed")

    resp_headers = [
        (k.encode("latin1"), str(v).encode("latin1"))
        for k, v in inst.response_headers
    ]

    await send({
        "type": "http.response.start",
        "status": inst.response_status,
        "headers": resp_headers,
    })
    await send({
        "type": "http.response.body",
        "body": inst.wfile.getvalue(),
    })


class DualHandler(BusinessPilotAPIHandler):
    """
    Polymorphic handler that works seamlessly as:
    1. BaseHTTPRequestHandler for Vercel Serverless Functions and local HTTPServer
    2. WSGI callable (environ, start_response) for WSGI servers
    3. ASGI callable (scope, receive, send) for modern Vercel ASGI runtime
    """

    def __new__(cls, *args, **kwargs):
        # Case 1: WSGI (2 positional args: environ, start_response)
        if len(args) == 2 and callable(args[1]):
            environ, start_response = args
            return cls._handle_wsgi(environ, start_response)

        # Case 2: ASGI (3 positional args: scope, receive, send where scope is a dict)
        if len(args) == 3 and isinstance(args[0], dict) and "type" in args[0]:
            scope, receive, send = args
            return handle_asgi(scope, receive, send)

        # Case 3: BaseHTTPRequestHandler (request, client_address, server)
        return super().__new__(cls)

    @classmethod
    def _handle_wsgi(cls, environ: Dict[str, Any], start_response: Any):
        path = environ.get("PATH_INFO", "")
        query = environ.get("QUERY_STRING", "")
        full_path = f"{path}?{query}" if query else path
        method = environ.get("REQUEST_METHOD", "GET").upper()

        try:
            cl = int(environ.get("CONTENT_LENGTH", 0))
        except (ValueError, TypeError):
            cl = 0
        input_stream = environ.get("wsgi.input")
        body = input_stream.read(cl) if (input_stream and cl > 0) else b""

        headers = {}
        for k, v in environ.items():
            if k.startswith("HTTP_"):
                header_name = k[5:].replace("_", "-").lower()
                headers[header_name] = str(v)
                headers[k[5:].lower()] = str(v)
            elif k in ("CONTENT_TYPE", "CONTENT_LENGTH"):
                headers[k.replace("_", "-").lower()] = str(v)
                headers[k.lower()] = str(v)
            elif isinstance(v, (str, int, float)):
                headers[k.lower()] = str(v)
                headers[k.replace("_", "-").lower()] = str(v)

        inst = WSGIHandler(full_path, method, body, headers, environ=environ)
        if method == "GET":
            inst.do_GET()
        elif method == "POST":
            inst.do_POST()
        elif method == "OPTIONS":
            inst.do_OPTIONS()
        else:
            inst.send_error(405, "Method Not Allowed")

        reason = responses.get(inst.response_status, "OK")
        status_line = f"{inst.response_status} {reason}"
        start_response(status_line, inst.response_headers)
        return [inst.wfile.getvalue()]


def universal_app(*args, **kwargs):
    """Universal application entrypoint supporting ASGI, WSGI, and BaseHTTPRequestHandler."""
    if len(args) == 2 and callable(args[1]):
        return DualHandler._handle_wsgi(args[0], args[1])
    elif len(args) == 3 and isinstance(args[0], dict) and "type" in args[0]:
        return handle_asgi(args[0], args[1], args[2])
    return DualHandler(*args, **kwargs)


def run_server(port: int = 8080):
    init_db()
    server_address = ("", port)
    httpd = HTTPServer(server_address, BusinessPilotAPIHandler)
    print(f"🚀 BusinessPilot Executive Server running at http://localhost:{port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port)

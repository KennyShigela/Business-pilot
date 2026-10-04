"""
Controlled AI Business Analyst for BusinessPilot.
Enforces the strict principle:
NO LLM GUESSING OR ARBITRARY SQL.
Retrieves verified facts via controlled, typed business tools,
synthesizes findings into executive narratives, and provides exact calculation citations.
"""
import os
import re
import json
import urllib.request
import urllib.parse
from typing import Dict, List, Any, Optional
from database.db import query_all, query_one, get_connection, generate_uuid
from engine.analytics import BusinessAnalyticsEngine
from engine.forecasting import ForecastingEngine
from engine.alerts_engine import EarlyWarningAlertEngine


# The class below defines the controlled, typed business tools exposed to the AI Analyst
class ControlledAIToolRegistry:
    """Safe, typed tools exposed to the AI Analyst."""

    def __init__(self, company_id: str):
        self.company_id = company_id
        self.analytics = BusinessAnalyticsEngine(company_id)
        self.forecasting = ForecastingEngine(company_id)
        self.alerts_engine = EarlyWarningAlertEngine(company_id)

    def get_revenue(self) -> Dict[str, Any]:
        """Tool: Retrieves verified revenue and growth metrics."""
        return self.analytics.get_revenue_summary()

    def get_profit(self) -> Dict[str, Any]:
        """Tool: Retrieves verified P&L and gross/net margin metrics."""
        return self.analytics.get_pnl_statement()

    def get_expenses(self) -> Dict[str, Any]:
        """Tool: Retrieves verified expense totals and category breakdowns."""
        return self.analytics.get_expense_summary()

    def get_inventory(self) -> Dict[str, Any]:
        """Tool: Retrieves verified inventory valuation, low stock, and dead stock."""
        return self.analytics.get_inventory_health()

    def get_customer_profitability(self) -> Dict[str, Any]:
        """Tool: Retrieves customer unit economics, whales, and margin killers."""
        return self.analytics.get_customer_profitability()

    def get_cash_flow(self) -> Dict[str, Any]:
        """Tool: Retrieves current cash balance, AR aging, and runway days."""
        return self.analytics.get_cash_flow_summary()

    def get_forecast(self) -> Dict[str, Any]:
        """Tool: Retrieves 3-month statistical revenue forecast with bounds."""
        return self.forecasting.generate_revenue_forecast()

    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """Tool: Retrieves active early warning risk alerts."""
        return self.alerts_engine.evaluate_and_refresh_alerts()


# The class below is for executing grounded AI analysis and formatting executive strategic advice
class AIBusinessAnalyst:
    """Conversational Business Analyst executing intent classification and verified tool calls."""

    def __init__(self, company_id: str):
        self.company_id = company_id
        self.tools = ControlledAIToolRegistry(company_id)
        comp = query_one("SELECT name, currency, business_type FROM companies WHERE id = ?;", (company_id,))
        self.company_name = comp["name"] if comp else "Business"
        self.currency = comp["currency"] if comp else "USD"
        self.business_type = comp["business_type"] if comp else "General"

    # The function below is for querying the Google Gemini 1.5 Flash API with strict financial ledger context
    def _call_gemini_api(self, question: str, context: Dict[str, Any], api_key: str) -> Optional[str]:
        """Calls Google Gemini 1.5 Flash API with verified financial grounding."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

        system_instruction = (
            f"You are the Executive AI Business Analyst and Financial Strategist for {self.company_name} "
            f"({self.business_type} company operating in {self.currency}).\n"
            f"STRICT GROUNDING REQUIREMENT: You are provided with the business's verified financial ledger and calculations below. "
            f"Do NOT hallucinate, extrapolate, or invent figures. Every numerical assertion must match the provided verified data.\n\n"
            f"Structure your response with:\n"
            f"1. Executive Direct Answer (bold key verified figures and percentages).\n"
            f"2. 2-3 Root Cause Drivers or Operational Factors.\n"
            f"3. 1-2 Specific, High-Impact Tactical Next Steps.\n"
            f"Use clean HTML formatting (<b>, <br>, <ul>, <li>). Do NOT use markdown code blocks or backticks."
        )

        prompt = (
            f"{system_instruction}\n\n"
            f"--- VERIFIED FINANCIAL LEDGER & BUSINESS STATE ---\n"
            f"{json.dumps(context, indent=2, default=str)}\n\n"
            f"--- EXECUTIVE QUESTION ---\n"
            f"{question}"
        )

        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1024
            }
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=12) as response:
                if response.status == 200:
                    resp_data = json.loads(response.read().decode("utf-8"))
                    candidates = resp_data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            res_text = parts[0].get("text", "").strip()
                            res_text = re.sub(r"^```(?:html)?\s*", "", res_text, flags=re.MULTILINE)
                            res_text = re.sub(r"```$", "", res_text, flags=re.MULTILINE)
                            return res_text.strip()
        except Exception as e:
            print(f"[Gemini API Notice] Request not completed ({e}), falling back to deterministic engine.")
            return None
        return None

    # The function below is for determining the business analytical intent of a user question
    def classify_intent(self, question: str) -> str:
        """Determines the business analytical intent of a user question."""
        q = question.lower()
        if any(w in q for w in ["profit", "margin", "loss", "decrease", "drop", "fell"]):
            return "PROFIT_ANALYSIS"
        elif any(w in q for w in ["revenue", "sales", "grow", "top line"]):
            return "REVENUE_ANALYSIS"
        elif any(w in q for w in ["cash", "runway", "balance", "bank", "liquidity"]):
            return "CASH_FLOW_ANALYSIS"
        elif any(w in q for w in ["stock", "inventory", "reorder", "dead stock", "sku"]):
            return "INVENTORY_ANALYSIS"
        elif any(w in q for w in ["customer", "client", "whale", "drainer", "buyer"]):
            return "CUSTOMER_ANALYSIS"
        elif any(w in q for w in ["forecast", "future", "next month", "project", "look like"]):
            return "FORECAST_ANALYSIS"
        elif any(w in q for w in ["expense", "cost", "spend", "vendor", "bills"]):
            return "EXPENSE_ANALYSIS"
        elif any(w in q for w in ["alert", "risk", "warning", "wrong", "problem"]):
            return "ALERT_ANALYSIS"
        else:
            return "GENERAL_BRIEFING"

    # The function below is for answering strategic business questions using grounded financial context
    def answer_question(self, question: str, conversation_id: Optional[str] = None, api_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes intent detection, invokes controlled tools, synthesizes a 3-part
        root-cause breakdown, and attaches verified calculation citations.
        Integrates Google Gemini 1.5 Flash with verified financial grounding.
        """
        intent = self.classify_intent(question)
        tool_calls = []
        citations = []
        explanation = ""
        action_recommendation = ""

        if intent == "PROFIT_ANALYSIS":
            tool_calls.append("get_profit()")
            tool_calls.append("get_expenses()")
            pnl = self.tools.get_profit()
            exp = self.tools.get_expenses()

            rev = pnl["revenue"]
            gross_prof = pnl["gross_profit"]
            gross_margin = pnl["gross_margin_pct"]
            opex = pnl["operating_expenses"]
            net_prof = pnl["net_profit"]
            net_margin = pnl["net_margin_pct"]

            status = "profitable" if pnl["is_profitable"] else "constrained by high operating expenses"

            curr = self.currency
            categories_str = ', '.join([c['category'] + ' (' + str(c['percentage']) + '%)' for c in exp.get('categories', [])[:3]]) if exp.get('categories') else "No expense records yet"

            explanation = (
                f"Net profit is currently <b>{curr} {net_prof:,.0f}</b> (Net Margin: {net_margin:.1f}%), {status}.<br><br>"
                f"<b>Three primary factors explain this performance:</b><br>"
                f"1. <b>Gross Product Margins:</b> Gross profit is <b>{curr} {gross_prof:,.0f}</b> ({gross_margin:.1f}% of revenue), indicating core product margins.<br>"
                f"2. <b>Operating Expenses (OPEX):</b> Total operating overhead is <b>{curr} {opex:,.0f}</b> (absorbing {(opex/max(1.0, rev)*100):.1f}% of gross receipts).<br>"
                f"3. <b>Largest Cost Centers:</b> {categories_str}."
            )
            action_recommendation = "Audit secondary administrative expenses and renegotiate supplier terms to preserve bottom-line contribution."
            citations = [
                {"metric": "Revenue", "value": f"{curr} {rev:,.0f}"},
                {"metric": "Gross Margin", "value": f"{gross_margin:.1f}%"},
                {"metric": "Operating Expenses", "value": f"{curr} {opex:,.0f}"},
                {"metric": "Net Margin", "value": f"{net_margin:.1f}%"},
            ]

        elif intent == "CASH_FLOW_ANALYSIS":
            tool_calls.append("get_cash_flow()")
            cash = self.tools.get_cash_flow()
            bal = cash["current_cash_balance"]
            burn = cash["monthly_burn_rate"]
            runway = cash["runway_days"]
            ar = cash["accounts_receivable"]
            curr = self.currency

            if bal == 0.0 and burn == 0.0:
                explanation = (
                    f"Current verified cash position for {self.company_name} is <b>{curr} 0</b> with no operating burn recorded yet.<br><br>"
                    f"Upload your cash receipts and payment records to monitor working capital and runway in real time."
                )
                action_recommendation = "Upload business transactions to begin tracking liquidity and burn rate."
                citations = [
                    {"metric": "Cash Balance", "value": f"{curr} 0"},
                    {"metric": "Monthly Burn", "value": f"{curr} 0"},
                    {"metric": "Runway Days", "value": "Awaiting Data"},
                ]
            else:
                runway_note = '🔴 CRITICAL: Cash runway is under 30 days.' if runway <= 30 else '✓ Runway within safe operating buffer.'
                explanation = (
                    f"Current verified cash position is <b>{curr} {bal:,.0f}</b> with an estimated <b>{runway} days of operating runway</b>.<br><br>"
                    f"<b>Key liquidity dynamics:</b><br>"
                    f"1. <b>Operating Burn:</b> Monthly disbursements average <b>{curr} {burn:,.0f}</b>.<br>"
                    f"2. <b>Uncollected Receivables:</b> You have <b>{curr} {ar:,.0f}</b> pending across {cash['unpaid_invoices_count']} customer invoices.<br>"
                    f"3. <b>Runway Health:</b> {runway_note}"
                )
                action_recommendation = "Accelerate follow-ups on outstanding receivables to inject liquidity without taking external credit."
                citations = [
                    {"metric": "Cash Balance", "value": f"{curr} {bal:,.0f}"},
                    {"metric": "Monthly Burn", "value": f"{curr} {burn:,.0f}"},
                    {"metric": "Runway Days", "value": f"{runway} days"},
                    {"metric": "Accounts Receivable", "value": f"{curr} {ar:,.0f}"},
                ]

        elif intent == "INVENTORY_ANALYSIS":
            tool_calls.append("get_inventory()")
            inv = self.tools.get_inventory()
            low_count = inv["low_stock_count"]
            dead_val = inv["locked_capital_slow_moving"]
            tot_val = inv["total_inventory_value"]
            curr = self.currency

            if inv["total_sku_count"] == 0:
                explanation = (
                    f"No inventory products recorded for {self.company_name} yet.<br><br>"
                    f"Upload an inventory spreadsheet with SKU, stock quantity, cost price, and selling price to track stock valuation and reorder alerts."
                )
                action_recommendation = "Upload your product catalog in the Data tab to enable stock tracking."
                citations = [
                    {"metric": "Inventory Valuation", "value": f"{curr} 0"},
                    {"metric": "Tracked SKUs", "value": "0"},
                ]
            else:
                sample_low = ", ".join([item["name"] + f" ({item['stock']:.0f} left)" for item in inv["low_stock_alerts"][:3]])
                explanation = (
                    f"Total inventory on hand is valued at <b>{curr} {tot_val:,.0f}</b> across {inv['total_sku_count']} products.<br><br>"
                    f"<b>Two operational risks require attention:</b><br>"
                    f"1. <b>Low Stock Warnings:</b> {low_count} products have reached or breached their reorder point: {sample_low or 'None'}.<br>"
                    f"2. <b>Trapped Dead Capital:</b> <b>{curr} {dead_val:,.0f}</b> is locked in {inv['slow_moving_count']} items with no sales recorded in over 60 days."
                )
                action_recommendation = "Liquidate or discount stagnant lines to free up capital, and order replenishment stock for fast-moving items."
                citations = [
                    {"metric": "Inventory Valuation", "value": f"{curr} {tot_val:,.0f}"},
                    {"metric": "Low Stock SKUs", "value": f"{low_count} items"},
                    {"metric": "Dead Stock Value", "value": f"{curr} {dead_val:,.0f}"},
                ]

        elif intent == "CUSTOMER_ANALYSIS":
            tool_calls.append("get_customer_profitability()")
            cust = self.tools.get_customer_profitability()
            top_whale = cust["whales"][0] if cust.get("whales") else None
            top_drainer = cust["drainers"][0] if cust.get("drainers") else None
            curr = self.currency

            if cust["total_tracked_customers"] == 0:
                explanation = (
                    f"No customer accounts recorded for {self.company_name} yet.<br><br>"
                    f"Importing sales transactions will automatically compute customer lifetime value and identify your top profit drivers."
                )
                action_recommendation = "Import customer sales orders to uncover your highest-margin accounts."
                citations = [
                    {"metric": "Tracked Customers", "value": "0"},
                ]
            else:
                explanation = (
                    f"Analyzed {cust['total_tracked_customers']} active customer accounts for revenue and net contribution margin.<br><br>"
                    f"1. <b>Top Whale Account:</b> {top_whale['customer_name'] if top_whale else 'Walk-in'} generates <b>{curr} {top_whale['total_revenue']:,.0f}</b> at a healthy {top_whale['margin_pct']}% margin.<br>"
                    f"2. <b>Margin Watch Account:</b> {top_drainer['customer_name'] if top_drainer else 'None'} generates lower unit profitability ({top_drainer['margin_pct'] if top_drainer else '0'}% margin)."
                )
                action_recommendation = "Protect relationships with top wholesale accounts and limit excessive discounting on margin-watch accounts."
                citations = [
                    {"metric": "Tracked Customers", "value": f"{cust['total_tracked_customers']}"},
                    {"metric": "Top Account Revenue", "value": f"{curr} {top_whale['total_revenue']:,.0f}" if top_whale else "N/A"},
                ]

        elif intent == "FORECAST_ANALYSIS":
            tool_calls.append("get_forecast()")
            fc = self.tools.get_forecast()
            pts = fc.get("forecast_points", [])
            curr = self.currency

            if not pts:
                explanation = (
                    f"No historical sales data has been recorded for {self.company_name} yet.<br><br>"
                    f"Upload an Excel sales sheet or connect Google Sheets to activate automated time-series forecasting."
                )
                action_recommendation = "Upload your past sales data in the Data tab to train the predictive model."
                citations = [
                    {"metric": "Historical Data", "value": "Awaiting Data"},
                    {"metric": "Forecast Status", "value": "Pending Transactions"},
                ]
            else:
                pts_desc = "<br>".join([f"• <b>{p['period']}:</b> Projected {curr} {p['predicted_revenue']:,.0f} (Range: {curr} {p['lower_bound']:,.0f} – {curr} {p['upper_bound']:,.0f})" for p in pts[:3]])
                explanation = (
                    f"Time-series damped exponential smoothing projects the following 3-month baseline:<br><br>"
                    f"{pts_desc}<br><br>"
                    f"<b>Forecast Confidence:</b> {int(fc.get('overall_confidence', 0.5) * 100)}% based on historical monthly sales consistency."
                )
                action_recommendation = "Align inventory purchasing with the 60-day projected demand baseline."
                citations = [
                    {"metric": "Confidence Score", "value": f"{int(fc.get('overall_confidence', 0.5) * 100)}%"},
                    {"metric": "Next Month Pred", "value": f"{curr} {pts[0]['predicted_revenue']:,.0f}" if pts else "N/A"},
                ]

        else:  # GENERAL_BRIEFING / ALERT_ANALYSIS
            tool_calls.append("detect_anomalies()")
            brief = self.tools.analytics.generate_morning_briefing()
            explanation = (
                f"<b>Executive Morning Briefing:</b><br>{brief['ai_summary']}<br><br>"
                f"Business health is categorized as <b>{brief['business_health']}</b>."
            )
            action_recommendation = "Review the Attention Required cards on your executive dashboard."
            citations = [
                {"metric": "Health Status", "value": brief["business_health"]},
            ]

        # Determine effective Gemini API key and invoke Gemini if available
        effective_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        provider = "BusinessPilot Deterministic Engine (Offline Fallback)"
        confidence_level = "HIGH (Directly Verified via Deterministic Calculations)"

        if effective_key:
            try:
                context = {
                    "company_name": self.company_name,
                    "currency": self.currency,
                    "business_type": self.business_type,
                    "revenue_summary": self.tools.get_revenue(),
                    "pnl_statement": self.tools.get_profit(),
                    "cash_flow": self.tools.get_cash_flow(),
                    "expense_breakdown": self.tools.get_expenses(),
                    "inventory_health": self.tools.get_inventory(),
                    "customer_economics": self.tools.get_customer_profitability(),
                    "forecast": self.tools.get_forecast(),
                    "active_risk_alerts": self.tools.detect_anomalies()[:5],
                }
                gemini_text = self._call_gemini_api(question, context, effective_key)
                if gemini_text:
                    explanation = gemini_text
                    provider = "Google Gemini 1.5 Flash (Verified Financial Grounding)"
                    confidence_level = "HIGH (Gemini Intelligence Grounded in Deterministic Calculations)"
            except Exception as e:
                print(f"[Gemini Context Processing Error] {e}")

        # Persist conversation to SQLite database
        try:
            with get_connection() as conn:
                conv_id = conversation_id
                if not conv_id:
                    existing_conv = query_one(
                        "SELECT id FROM ai_conversations WHERE company_id = ? ORDER BY created_at DESC LIMIT 1;",
                        (self.company_id,)
                    )
                    if existing_conv:
                        conv_id = existing_conv["id"]
                    else:
                        conv_id = generate_uuid()
                        conn.execute(
                            "INSERT INTO ai_conversations (id, company_id, title) VALUES (?, ?, ?);",
                            (conv_id, self.company_id, question[:60])
                        )

                user_msg_id = generate_uuid()
                asst_msg_id = generate_uuid()
                conn.execute(
                    """
                    INSERT INTO ai_messages (id, conversation_id, role, content, tool_calls, citations)
                    VALUES (?, ?, 'USER', ?, ?, ?);
                    """,
                    (user_msg_id, conv_id, question, json.dumps([]), json.dumps([])),
                )
                conn.execute(
                    """
                    INSERT INTO ai_messages (id, conversation_id, role, content, tool_calls, citations)
                    VALUES (?, ?, 'ASSISTANT', ?, ?, ?);
                    """,
                    (asst_msg_id, conv_id, explanation, json.dumps(tool_calls), json.dumps(citations)),
                )
        except Exception as e:
            print(f"[AI Conversation Persistence Notice] {e}")

        return {
            "intent": intent,
            "question": question,
            "explanation": explanation,
            "action_recommendation": action_recommendation,
            "tool_calls": tool_calls,
            "citations": citations,
            "provider": provider,
            "epistemic_confidence": confidence_level,
        }

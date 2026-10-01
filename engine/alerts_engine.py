"""
Proactive Early Warning Alert Engine for BusinessPilot.
Continuously audits business health for cash cliffs, inventory stockouts,
dead stock accumulation, margin compression, and expense spikes.
"""
from typing import Dict, List, Any
from database.db import query_all, query_one, get_connection, generate_uuid
from engine.analytics import BusinessAnalyticsEngine
from engine.forecasting import ForecastingEngine


class EarlyWarningAlertEngine:
    """Proactively evaluates risk triggers and populates the alerts table."""

    def __init__(self, company_id: str):
        self.company_id = company_id
        self.analytics = BusinessAnalyticsEngine(company_id)
        self.forecasting = ForecastingEngine(company_id)

    def evaluate_and_refresh_alerts(self) -> List[Dict[str, Any]]:
        """
        Runs comprehensive risk detection across Cash, Inventory, Expenses, and Margins,
        clearing stale alerts and storing fresh active alerts in the database.
        """
        active_alerts = []

        rev = self.analytics.get_revenue_summary()
        pnl = self.analytics.get_pnl_statement()
        inv = self.analytics.get_inventory_health()
        cash = self.analytics.get_cash_flow_summary()
        stockouts = self.forecasting.generate_inventory_stockout_forecast()

        # If empty data state, return no active alerts
        if rev["total_revenue"] == 0 and pnl["operating_expenses"] == 0 and inv["total_inventory_value"] == 0:
            return []
        if cash["runway_days"] <= 30:
            active_alerts.append({
                "alert_type": "CASH_FLOW",
                "severity": "CRITICAL",
                "title": "Severe Cash Runway Cliff",
                "message": f"Projected cash runway is estimated at only {cash['runway_days']} days based on current burn rate. Immediate receivables collection or OPEX reduction required.",
                "metric": "runway_days",
                "threshold_value": 30.0,
                "actual_value": float(cash["runway_days"]),
            })
        elif cash["runway_days"] <= 60:
            active_alerts.append({
                "alert_type": "CASH_FLOW",
                "severity": "WARNING",
                "title": "Tight Cash Flow Runway",
                "message": f"Current cash balance of TZS {cash['current_cash_balance']:,.0f} provides approximately {cash['runway_days']} days of operating runway.",
                "metric": "runway_days",
                "threshold_value": 60.0,
                "actual_value": float(cash["runway_days"]),
            })

        # 2. INVENTORY STOCKOUT THREATS
        for so in stockouts[:3]:
            sev = "CRITICAL" if so["urgency"] == "CRITICAL" else "WARNING"
            active_alerts.append({
                "alert_type": "INVENTORY",
                "severity": sev,
                "title": f"Stockout Alert: {so['name']}",
                "message": f"'{so['name']}' has {so['current_stock']:.0f} units remaining and is projected to stock out in {so['days_until_stockout']:.1f} days at current sales velocity. Recommended reorder: {so['recommended_reorder_qty']} units.",
                "metric": "days_until_stockout",
                "threshold_value": 14.0,
                "actual_value": so["days_until_stockout"],
            })

        # 3. DEAD / INACTIVE INVENTORY
        if inv["locked_capital_slow_moving"] > 2000000:
            active_alerts.append({
                "alert_type": "INVENTORY",
                "severity": "WARNING",
                "title": "Excess Dead Stock Capital",
                "message": f"TZS {inv['locked_capital_slow_moving']:,.0f} is locked in {inv['slow_moving_count']} products with no sales recorded in over 60 days.",
                "metric": "locked_capital",
                "threshold_value": 2000000.0,
                "actual_value": float(inv["locked_capital_slow_moving"]),
            })

        # 4. UNPAID RECEIVABLES EXPOSURE
        if cash["accounts_receivable"] > (rev["total_revenue"] * 0.15) and cash["accounts_receivable"] > 1000000:
            active_alerts.append({
                "alert_type": "CUSTOMER",
                "severity": "ATTENTION",
                "title": "Outstanding Receivables Aging",
                "message": f"TZS {cash['accounts_receivable']:,.0f} remains uncollected across {cash['unpaid_invoices_count']} invoices. Recommend following up with wholesale accounts.",
                "metric": "accounts_receivable",
                "threshold_value": rev["total_revenue"] * 0.15,
                "actual_value": float(cash["accounts_receivable"]),
            })

        # 5. NET PROFIT MARGIN DRAG
        if not pnl["is_profitable"]:
            active_alerts.append({
                "alert_type": "MARGIN",
                "severity": "WARNING",
                "title": "Operating Margin Deficit",
                "message": f"Net operating loss of TZS {abs(pnl['net_profit']):,.0f} recorded. Operating expenses (TZS {pnl['operating_expenses']:,.0f}) exceed gross margin receipts.",
                "metric": "net_profit",
                "threshold_value": 0.0,
                "actual_value": float(pnl["net_profit"]),
            })

        # Persist to database
        with get_connection() as conn:
            conn.execute("DELETE FROM alerts WHERE company_id = ? AND status = 'ACTIVE';", (self.company_id,))
            for alt in active_alerts:
                aid = generate_uuid()
                conn.execute(
                    """
                    INSERT INTO alerts (
                        id, company_id, alert_type, severity, title, message, 
                        metric, threshold_value, actual_value, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE');
                    """,
                    (
                        aid,
                        self.company_id,
                        alt["alert_type"],
                        alt["severity"],
                        alt["title"],
                        alt["message"],
                        alt["metric"],
                        alt["threshold_value"],
                        alt["actual_value"],
                    ),
                )

        return active_alerts

    def get_active_alerts(self, severity: str = "ALL") -> List[Dict[str, Any]]:
        """Returns persisted active alerts, optionally filtered by severity."""
        sev_filter = ""
        params = [self.company_id]
        if severity != "ALL":
            sev_filter = "AND severity = ?"
            params.append(severity)

        sql = f"""
            SELECT id, alert_type, severity, title, message, metric, threshold_value, actual_value, status, created_at
            FROM alerts
            WHERE company_id = ? AND status = 'ACTIVE' {sev_filter}
            ORDER BY 
                CASE severity 
                    WHEN 'CRITICAL' THEN 1 
                    WHEN 'WARNING' THEN 2 
                    WHEN 'ATTENTION' THEN 3 
                    ELSE 4 
                END ASC,
                created_at DESC;
        """
        return query_all(sql, tuple(params))

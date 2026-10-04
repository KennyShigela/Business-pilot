"""
Deterministic Analytics Engine for BusinessPilot.
Performs verifiable, mathematically rigorous business calculations across
Revenue, Expenses, Profitability, Inventory Health, Customer Economics, and Cash Flow.
NO LLM HALLUCINATIONS — PURE VERIFIED CODE & DATABASE TRUTH.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from database.db import query_all, query_one, get_connection


# The class below is for calculating deterministic business analytics and financial KPIs
class BusinessAnalyticsEngine:
    """Calculates all executive and operational business metrics for a company."""

    def __init__(self, company_id: str):
        self.company_id = company_id

    # ---------------------------------------------------------
    # 1. REVENUE METRICS
    # ---------------------------------------------------------
    # The function below is for calculating total revenue, order count, AOV, and MoM growth
    def get_revenue_summary(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        """Calculates total revenue, order count, AOV, and MoM growth."""
        date_filter = ""
        params = [self.company_id]
        if start_date and end_date:
            date_filter = "AND s.sale_date BETWEEN ? AND ?"
            params.extend([start_date, end_date])

        sql = f"""
            SELECT 
                COALESCE(SUM(s.total), 0.0) AS total_revenue,
                COALESCE(SUM(s.cost_of_goods), 0.0) AS total_cogs,
                COALESCE(SUM(s.profit), 0.0) AS total_gross_profit,
                COALESCE(COUNT(s.id), 0) AS total_orders,
                COALESCE(SUM(si.quantity), 0.0) AS total_units_sold
            FROM sales s
            LEFT JOIN sale_items si ON s.id = si.sale_id
            WHERE s.company_id = ? {date_filter};
        """
        row = query_one(sql, tuple(params)) or {}
        tot_rev = float(row.get("total_revenue", 0.0))
        tot_cogs = float(row.get("total_cogs", 0.0))
        tot_orders = int(row.get("total_orders", 0))
        units_sold = float(row.get("total_units_sold", 0.0))
        gross_profit = float(row.get("total_gross_profit", tot_rev - tot_cogs))
        gross_margin = (gross_profit / tot_rev * 100) if tot_rev > 0 else 0.0
        aov = (tot_rev / tot_orders) if tot_orders > 0 else 0.0

        # MoM Growth calculation (compare current 30-day window to prior 30-day window)
        growth_sql = """
            SELECT 
                strftime('%Y-%m', sale_date) AS month,
                SUM(total) AS monthly_rev
            FROM sales
            WHERE company_id = ?
            GROUP BY strftime('%Y-%m', sale_date)
            ORDER BY month DESC
            LIMIT 2;
        """
        recent_months = query_all(growth_sql, (self.company_id,))
        mom_growth = 0.0
        if len(recent_months) >= 2:
            current_m = float(recent_months[0]["monthly_rev"])
            prior_m = float(recent_months[1]["monthly_rev"])
            if prior_m > 0:
                mom_growth = round(((current_m - prior_m) / prior_m) * 100, 1)

        return {
            "total_revenue": round(tot_rev, 2),
            "total_cogs": round(tot_cogs, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_margin_pct": round(gross_margin, 1),
            "total_orders": tot_orders,
            "units_sold": round(units_sold, 1),
            "average_order_value": round(aov, 2),
            "mom_growth_pct": mom_growth,
        }

    # The function below is for returning monthly revenue and gross profit series for trend charts
    def get_revenue_trends(self) -> List[Dict[str, Any]]:
        """Returns monthly revenue and gross profit series for trend charts."""
        sql = """
            SELECT 
                strftime('%Y-%m', sale_date) AS period,
                ROUND(SUM(total), 2) AS revenue,
                ROUND(SUM(cost_of_goods), 2) AS cogs,
                ROUND(SUM(profit), 2) AS gross_profit,
                COUNT(id) AS order_count
            FROM sales
            WHERE company_id = ?
            GROUP BY strftime('%Y-%m', sale_date)
            ORDER BY period ASC;
        """
        return query_all(sql, (self.company_id,))

    # ---------------------------------------------------------
    # 2. EXPENSES & COST METRICS
    # ---------------------------------------------------------
    # The function below is for calculating total expenses, category breakdown, and MoM trend
    def get_expense_summary(self) -> Dict[str, Any]:
        """Calculates total expenses, category breakdown, and MoM trend."""
        sql_total = """
            SELECT COALESCE(SUM(amount), 0.0) AS total_expenses
            FROM expenses
            WHERE company_id = ?;
        """
        tot_exp = float((query_one(sql_total, (self.company_id,)) or {}).get("total_expenses", 0.0))

        # Category breakdown
        sql_cats = """
            SELECT 
                COALESCE(ec.name, 'General') AS category,
                COALESCE(ec.type, 'OPERATING') AS category_type,
                COUNT(e.id) AS transaction_count,
                ROUND(SUM(e.amount), 2) AS total_amount,
                ROUND((SUM(e.amount) / ? * 100), 1) AS percentage
            FROM expenses e
            LEFT JOIN expense_categories ec ON e.category_id = ec.id
            WHERE e.company_id = ?
            GROUP BY category, category_type
            ORDER BY total_amount DESC;
        """
        categories = query_all(sql_cats, (max(1.0, tot_exp), self.company_id))

        # MoM Expense Growth
        sql_mom = """
            SELECT 
                strftime('%Y-%m', expense_date) AS month,
                SUM(amount) AS monthly_exp
            FROM expenses
            WHERE company_id = ?
            GROUP BY strftime('%Y-%m', expense_date)
            ORDER BY month DESC
            LIMIT 2;
        """
        recent = query_all(sql_mom, (self.company_id,))
        mom_growth = 0.0
        if len(recent) >= 2:
            curr = float(recent[0]["monthly_exp"])
            prev = float(recent[1]["monthly_exp"])
            if prev > 0:
                mom_growth = round(((curr - prev) / prev) * 100, 1)

        return {
            "total_expenses": round(tot_exp, 2),
            "category_count": len(categories),
            "top_category": categories[0]["category"] if categories else "None",
            "mom_growth_pct": mom_growth,
            "categories": categories,
        }

    # ---------------------------------------------------------
    # 3. PROFITABILITY & P&L STATEMENT
    # ---------------------------------------------------------
    # The function below is for producing a complete P&L bridge statement (Revenue -> COGS -> OPEX -> Net Profit)
    def get_pnl_statement(self) -> Dict[str, Any]:
        """Produces a complete P&L bridge: Revenue -> COGS -> Gross Margin -> OPEX -> Net Profit."""
        rev_data = self.get_revenue_summary()
        exp_data = self.get_expense_summary()

        rev = rev_data["total_revenue"]
        cogs = rev_data["total_cogs"]
        gross_profit = rev_data["gross_profit"]
        opex = exp_data["total_expenses"]

        operating_profit = round(gross_profit - opex, 2)  # EBITDA
        net_profit = operating_profit  # pre-tax for MVP
        net_margin_pct = round((net_profit / rev * 100), 1) if rev > 0 else 0.0

        return {
            "revenue": rev,
            "cogs": cogs,
            "gross_profit": gross_profit,
            "gross_margin_pct": rev_data["gross_margin_pct"],
            "operating_expenses": opex,
            "operating_profit": operating_profit,
            "net_profit": net_profit,
            "net_margin_pct": net_margin_pct,
            "is_profitable": net_profit > 0,
        }

    # ---------------------------------------------------------
    # 4. INVENTORY HEALTH & STOCK VALUE
    # ---------------------------------------------------------
    # The function below is for evaluating inventory health, safety stock, low stock items, and dead stock
    def get_inventory_health(self) -> Dict[str, Any]:
        """
        Reconstructs inventory quantities from movements,
        evaluates stock values, low stock items, and inactive dead stock (>60 days).
        """
        # Reconstruct stock per product from inventory_movements
        sql_stock = """
            SELECT 
                p.id AS product_id,
                p.sku,
                p.name AS product_name,
                p.reorder_level,
                p.cost_price,
                p.selling_price,
                COALESCE(SUM(im.quantity), 0.0) AS current_stock,
                MAX(im.movement_date) AS last_movement
            FROM products p
            LEFT JOIN inventory_movements im ON p.id = im.product_id
            WHERE p.company_id = ? AND p.is_active = 1
            GROUP BY p.id, p.sku, p.name, p.reorder_level, p.cost_price, p.selling_price;
        """
        products = query_all(sql_stock, (self.company_id,))

        total_value = 0.0
        low_stock_items = []
        out_of_stock_items = []
        healthy_items = []

        for prod in products:
            qty = float(prod["current_stock"])
            cost = float(prod["cost_price"])
            val = qty * cost
            total_value += val
            reorder = float(prod["reorder_level"])

            item_summary = {
                "product_id": prod["product_id"],
                "sku": prod["sku"],
                "name": prod["product_name"],
                "stock": qty,
                "value": round(val, 2),
                "reorder_level": reorder,
            }

            if qty <= 0:
                item_summary["status"] = "OUT_OF_STOCK"
                out_of_stock_items.append(item_summary)
            elif qty <= reorder:
                item_summary["status"] = "LOW_STOCK"
                low_stock_items.append(item_summary)
            else:
                item_summary["status"] = "HEALTHY"
                healthy_items.append(item_summary)

        # Inactive stock check (no sales in last 60 days)
        cutoff_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        sql_slow = """
            SELECT 
                p.id, p.sku, p.name,
                COALESCE(SUM(im.quantity), 0.0) AS stock,
                p.cost_price,
                (COALESCE(SUM(im.quantity), 0.0) * p.cost_price) AS locked_value
            FROM products p
            LEFT JOIN inventory_movements im ON p.id = im.product_id
            WHERE p.company_id = ?
            AND p.id NOT IN (
                SELECT DISTINCT si.product_id
                FROM sale_items si
                JOIN sales s ON si.sale_id = s.id
                WHERE s.sale_date >= ?
            )
            GROUP BY p.id, p.sku, p.name, p.cost_price
            HAVING stock > 0;
        """
        slow_moving = query_all(sql_slow, (self.company_id, cutoff_date))
        locked_capital = sum(float(r["locked_value"]) for r in slow_moving)

        return {
            "total_inventory_value": round(total_value, 2),
            "total_sku_count": len(products),
            "healthy_count": len(healthy_items),
            "low_stock_count": len(low_stock_items),
            "out_of_stock_count": len(out_of_stock_items),
            "slow_moving_count": len(slow_moving),
            "locked_capital_slow_moving": round(locked_capital, 2),
            "low_stock_alerts": low_stock_items,
            "out_of_stock_alerts": out_of_stock_items,
            "slow_moving_items": slow_moving,
        }

    # ---------------------------------------------------------
    # 5. CUSTOMER PROFITABILITY (WHALES VS DRAINERS)
    # ---------------------------------------------------------
    # The function below is for calculating customer profitability, top accounts, and margin drainers
    def get_customer_profitability(self, limit: int = 10) -> Dict[str, Any]:
        """Calculates Customer-level P&L, identifying high-margin Whales and Margin Killers."""
        sql = """
            SELECT 
                c.id AS customer_id,
                c.name AS customer_name,
                c.customer_type,
                COUNT(DISTINCT s.id) AS total_orders,
                ROUND(SUM(s.total), 2) AS total_revenue,
                ROUND(SUM(s.cost_of_goods), 2) AS total_cogs,
                ROUND(SUM(s.profit), 2) AS net_profit,
                ROUND((SUM(s.profit) / MAX(1.0, SUM(s.total)) * 100), 1) AS margin_pct,
                MAX(s.sale_date) AS last_purchase_date
            FROM customers c
            JOIN sales s ON c.id = s.customer_id
            WHERE c.company_id = ?
            GROUP BY c.id, c.name, c.customer_type
            ORDER BY total_revenue DESC;
        """
        all_customers = query_all(sql, (self.company_id,))

        whales = []
        drainers = []

        for cust in all_customers:
            rev = float(cust["total_revenue"])
            prof = float(cust["net_profit"])
            margin = float(cust["margin_pct"])

            if margin >= 25.0 and rev > 100000:
                whales.append(cust)
            elif margin < 10.0 or prof <= 0:
                drainers.append(cust)

        return {
            "total_tracked_customers": len(all_customers),
            "top_customers": all_customers[:limit],
            "whales": whales[:5],
            "drainers": drainers[:5],
        }

    # ---------------------------------------------------------
    # 6. CASH FLOW & RUNWAY
    # ---------------------------------------------------------
    # The function below is for calculating cash flow in/out, net cash position, AR aging, and runway days
    def get_cash_flow_summary(self) -> Dict[str, Any]:
        """Calculates Cash In (collected payments), Cash Out (expenses paid), Net Position, and Runway."""
        # Cash Collections
        sql_in = """
            SELECT COALESCE(SUM(amount), 0.0) AS cash_in
            FROM payments
            WHERE company_id = ? AND status = 'Completed';
        """
        cash_in = float((query_one(sql_in, (self.company_id,)) or {}).get("cash_in", 0.0))

        # Cash Disbursements (Expenses)
        sql_out = """
            SELECT COALESCE(SUM(amount), 0.0) AS cash_out
            FROM expenses
            WHERE company_id = ? AND status = 'Paid';
        """
        cash_out = float((query_one(sql_out, (self.company_id,)) or {}).get("cash_out", 0.0))

        net_cash = round(cash_in - cash_out, 2)

        # Accounts Receivable (Unpaid sales)
        sql_ar = """
            SELECT 
                COALESCE(SUM(total), 0.0) AS total_ar,
                COUNT(id) AS unpaid_invoices
            FROM sales
            WHERE company_id = ? AND payment_status != 'Paid';
        """
        ar_data = query_one(sql_ar, (self.company_id,)) or {}
        total_ar = float(ar_data.get("total_ar", 0.0))

        # If brand new company with no cash movement
        if cash_in == 0.0 and cash_out == 0.0:
            return {
                "current_cash_balance": 0.0,
                "total_cash_in": 0.0,
                "total_cash_out": 0.0,
                "accounts_receivable": round(total_ar, 2),
                "unpaid_invoices_count": int(ar_data.get("unpaid_invoices", 0)),
                "monthly_burn_rate": 0.0,
                "runway_months": 0.0,
                "runway_days": 0,
                "runway_risk": False,
            }

        # Monthly burn rate (average monthly expenses over last 3 months)
        sql_burn = """
            SELECT AVG(monthly_sum) AS avg_burn FROM (
                SELECT SUM(amount) AS monthly_sum
                FROM expenses
                WHERE company_id = ?
                GROUP BY strftime('%Y-%m', expense_date)
                ORDER BY strftime('%Y-%m', expense_date) DESC
                LIMIT 3
            );
        """
        burn_row = query_one(sql_burn, (self.company_id,)) or {}
        monthly_burn = float(burn_row.get("avg_burn") or 0.0)
        runway_months = round(max(0.0, net_cash) / max(1.0, monthly_burn), 1) if monthly_burn > 0 else 99.0

        return {
            "current_cash_balance": net_cash,
            "total_cash_in": round(cash_in, 2),
            "total_cash_out": round(cash_out, 2),
            "accounts_receivable": round(total_ar, 2),
            "unpaid_invoices_count": int(ar_data.get("unpaid_invoices", 0)),
            "monthly_burn_rate": round(monthly_burn, 2),
            "runway_months": runway_months,
            "runway_days": int(runway_months * 30),
            "runway_risk": runway_months < 2.0,
        }

    # ---------------------------------------------------------
    # 7. EXECUTIVE MORNING BRIEFING
    # ---------------------------------------------------------
    # The function below is for synthesizing the executive daily summary briefing and KPI cards
    def generate_morning_briefing(self) -> Dict[str, Any]:
        """
        Synthesizes the executive daily summary:
        Revenue, Profit, Cash position, Inventory warnings, Customer risks,
        and natural-language AI business summary.
        """
        rev = self.get_revenue_summary()
        pnl = self.get_pnl_statement()
        inv = self.get_inventory_health()
        cash = self.get_cash_flow_summary()
        cust = self.get_customer_profitability()

        # If brand new company with no data yet
        if rev["total_revenue"] == 0 and pnl["operating_expenses"] == 0 and inv["total_inventory_value"] == 0:
            return {
                "business_health": "Awaiting Data",
                "kpi_cards": {
                    "revenue": {"value": 0.0, "growth": 0.0},
                    "net_profit": {"value": 0.0, "margin": 0.0},
                    "expenses": {"value": 0.0, "growth": 0.0},
                    "cash_balance": {"value": 0.0, "runway_days": 0},
                },
                "warnings": {
                    "inventory_warnings": 0,
                    "customer_risks": 0,
                    "cash_cliff_days": 0,
                },
                "ai_summary": "Welcome to Business Pilot! No business transactions have been imported yet. Upload your first business spreadsheet (Excel, CSV, or Google Sheets) to instantly generate executive dashboards, cash flow forecasts, and AI insights.",
            }

        # Build rule-based AI summary bullets
        insights = []
        if rev["mom_growth_pct"] > 0:
            insights.append(f"Revenue increased {rev['mom_growth_pct']}% this month.")
        elif rev["total_revenue"] > 0:
            insights.append(f"Revenue contracted {abs(rev['mom_growth_pct'])}% this month.")

        if pnl["operating_expenses"] > (pnl["revenue"] * 0.7):
            insights.append("Operating expenses are consuming over 70% of gross revenue.")

        if inv["low_stock_count"] > 0:
            insights.append(f"{inv['low_stock_count']} inventory products have reached or fallen below reorder levels.")

        if inv["locked_capital_slow_moving"] > 0:
            insights.append(f"Capital of {inv['locked_capital_slow_moving']:,.0f} is locked in inventory inactive for over 60 days.")

        if cash["runway_risk"]:
            insights.append(f"CRITICAL: Cash runway is estimated at {cash['runway_days']} days based on current burn rate.")

        return {
            "business_health": "Profitable" if pnl["is_profitable"] else "At Risk",
            "kpi_cards": {
                "revenue": {"value": rev["total_revenue"], "growth": rev["mom_growth_pct"]},
                "net_profit": {"value": pnl["net_profit"], "margin": pnl["net_margin_pct"]},
                "expenses": {"value": pnl["operating_expenses"], "growth": self.get_expense_summary()["mom_growth_pct"]},
                "cash_balance": {"value": cash["current_cash_balance"], "runway_days": cash["runway_days"]},
            },
            "warnings": {
                "inventory_warnings": inv["low_stock_count"] + inv["out_of_stock_count"],
                "customer_risks": len(cust["drainers"]),
                "cash_cliff_days": cash["runway_days"],
            },
            "ai_summary": " ".join(insights) if insights else "Business operations are running normally.",
        }

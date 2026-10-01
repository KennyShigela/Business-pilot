"""
Unit tests for Deterministic Analytics Engine.
"""
import unittest
import os
import tempfile
from database.db import init_db, get_connection, generate_uuid
from engine.analytics import BusinessAnalyticsEngine


class TestBusinessAnalytics(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        init_db(self.temp_db_path)
        os.environ["BUSINESS_PILOT_DB"] = self.temp_db_path
        self.company_id = generate_uuid()

        # Seed realistic baseline data for calculations
        with get_connection(self.temp_db_path) as conn:
            conn.execute("INSERT INTO companies (id, name, currency) VALUES (?, 'Test Mart', 'TZS');", (self.company_id,))

            # Customer
            cust1 = generate_uuid()
            cust2 = generate_uuid()
            conn.execute("INSERT INTO customers (id, company_id, name, customer_type) VALUES (?, ?, 'Wholesale Client', 'Wholesale');", (cust1, self.company_id))
            conn.execute("INSERT INTO customers (id, company_id, name, customer_type) VALUES (?, ?, 'Retail Shopper', 'Retail');", (cust2, self.company_id))

            # Products
            p1 = generate_uuid()
            p2 = generate_uuid()
            conn.execute("INSERT INTO products (id, company_id, sku, name, selling_price, cost_price, reorder_level) VALUES (?, ?, 'P1', 'Rice 5kg', 15000, 10000, 20);", (p1, self.company_id))
            conn.execute("INSERT INTO products (id, company_id, sku, name, selling_price, cost_price, reorder_level) VALUES (?, ?, 'P2', 'Sugar 1kg', 3000, 2000, 50);", (p2, self.company_id))

            # Inventory Movements (Initial stock)
            conn.execute("INSERT INTO inventory_movements (id, company_id, product_id, movement_type, quantity, unit_cost) VALUES (?, ?, ?, 'PURCHASE', 100, 10000);", (generate_uuid(), self.company_id, p1))
            conn.execute("INSERT INTO inventory_movements (id, company_id, product_id, movement_type, quantity, unit_cost) VALUES (?, ?, ?, 'PURCHASE', 15, 2000);", (generate_uuid(), self.company_id, p2)) # Low stock!

            # Sales: Month 1 (August 2026) -> Total 100,000, COGS 60,000
            s1 = generate_uuid()
            conn.execute(
                """
                INSERT INTO sales (id, company_id, customer_id, invoice_number, sale_date, subtotal, total, cost_of_goods, profit, payment_status)
                VALUES (?, ?, ?, 'INV-001', '2026-08-15', 100000, 100000, 60000, 40000, 'Paid');
                """,
                (s1, self.company_id, cust1),
            )
            conn.execute("INSERT INTO sale_items (id, sale_id, product_id, quantity, unit_price, total, cost_price, profit) VALUES (?, ?, ?, 10, 10000, 100000, 6000, 40000);", (generate_uuid(), s1, p1))
            conn.execute("INSERT INTO payments (id, company_id, sale_id, amount, payment_method, payment_date) VALUES (?, ?, ?, 100000, 'M-Pesa', '2026-08-15');", (generate_uuid(), self.company_id, s1))

            # Sales: Month 2 (September 2026) -> Total 150,000, COGS 90,000
            s2 = generate_uuid()
            conn.execute(
                """
                INSERT INTO sales (id, company_id, customer_id, invoice_number, sale_date, subtotal, total, cost_of_goods, profit, payment_status)
                VALUES (?, ?, ?, 'INV-002', '2026-09-20', 150000, 150000, 90000, 60000, 'Paid');
                """,
                (s2, self.company_id, cust2),
            )
            conn.execute("INSERT INTO sale_items (id, sale_id, product_id, quantity, unit_price, total, cost_price, profit) VALUES (?, ?, ?, 10, 15000, 150000, 9000, 60000);", (generate_uuid(), s2, p1))
            conn.execute("INSERT INTO payments (id, company_id, sale_id, amount, payment_method, payment_date) VALUES (?, ?, ?, 150000, 'Cash', '2026-09-20');", (generate_uuid(), self.company_id, s2))

            # Expenses: 50,000 total (Rent 30,000, Transport 20,000)
            c_rent = generate_uuid()
            conn.execute("INSERT INTO expense_categories (id, company_id, name, type) VALUES (?, ?, 'Rent', 'OPERATING');", (c_rent, self.company_id))
            conn.execute("INSERT INTO expenses (id, company_id, category_id, amount, expense_date, status) VALUES (?, ?, ?, 30000, '2026-09-25', 'Paid');", (generate_uuid(), self.company_id, c_rent))
            conn.execute("INSERT INTO expenses (id, company_id, category_id, amount, expense_date, status) VALUES (?, ?, ?, 20000, '2026-09-26', 'Paid');", (generate_uuid(), self.company_id, c_rent))

        self.engine = BusinessAnalyticsEngine(self.company_id)

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_revenue_calculations(self):
        rev = self.engine.get_revenue_summary()
        self.assertEqual(rev["total_revenue"], 250000.0)
        self.assertEqual(rev["total_cogs"], 150000.0)
        self.assertEqual(rev["gross_profit"], 100000.0)
        self.assertEqual(rev["gross_margin_pct"], 40.0) # (100k / 250k) * 100
        self.assertEqual(rev["total_orders"], 2)
        self.assertEqual(rev["average_order_value"], 125000.0)
        # August 100k -> September 150k = +50% growth
        self.assertEqual(rev["mom_growth_pct"], 50.0)

    def test_pnl_statement(self):
        pnl = self.engine.get_pnl_statement()
        self.assertEqual(pnl["revenue"], 250000.0)
        self.assertEqual(pnl["gross_profit"], 100000.0)
        self.assertEqual(pnl["operating_expenses"], 50000.0)
        self.assertEqual(pnl["net_profit"], 50000.0)
        self.assertEqual(pnl["net_margin_pct"], 20.0) # (50k / 250k) * 100
        self.assertTrue(pnl["is_profitable"])

    def test_expense_summary_auto_summing(self):
        exp = self.engine.get_expense_summary()
        self.assertEqual(exp["total_expenses"], 50000.0)
        self.assertEqual(exp["category_count"], 1)
        self.assertEqual(exp["top_category"], "Rent")
        # Ensure the 2 entries (30,000 + 20,000) are auto-summed together
        rent_cat = exp["categories"][0]
        self.assertEqual(rent_cat["category"], "Rent")
        self.assertEqual(rent_cat["transaction_count"], 2)
        self.assertEqual(rent_cat["total_amount"], 50000.0)
        self.assertEqual(rent_cat["percentage"], 100.0)

    def test_inventory_health_detection(self):
        inv = self.engine.get_inventory_health()
        # Product 1 has 100 stock (> 20 reorder) -> Healthy
        # Product 2 has 15 stock (<= 50 reorder) -> Low stock
        self.assertEqual(inv["total_sku_count"], 2)
        self.assertEqual(inv["low_stock_count"], 1)
        self.assertEqual(inv["low_stock_alerts"][0]["name"], "Sugar 1kg")

    def test_cash_flow_and_runway(self):
        cash = self.engine.get_cash_flow_summary()
        self.assertEqual(cash["total_cash_in"], 250000.0)
        self.assertEqual(cash["total_cash_out"], 50000.0)
        self.assertEqual(cash["current_cash_balance"], 200000.0)
        self.assertGreater(cash["runway_months"], 0)

    def test_morning_briefing(self):
        briefing = self.engine.generate_morning_briefing()
        self.assertEqual(briefing["business_health"], "Profitable")
        self.assertIn("Revenue increased 50.0%", briefing["ai_summary"])
        self.assertEqual(briefing["warnings"]["inventory_warnings"], 1)


if __name__ == "__main__":
    unittest.main()

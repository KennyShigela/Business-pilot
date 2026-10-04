"""
Comprehensive Test Suite for Currency Detection, Live Online FX Conversion, and Notification Messaging.
"""
import os
import unittest
import tempfile
import pandas as pd
from engine.currency import (
    get_exchange_rate,
    convert_amount,
    normalize_currency_code,
    get_currency_display_name,
    fetch_live_rates,
    CurrencyDetector,
    EXCHANGE_RATES_TO_USD,
)
from engine.importer import BusinessDataImporter
from database.db import get_connection, generate_uuid, init_db


class TestCurrencyConversion(unittest.TestCase):
    """Tests exchange rate calculations and currency normalization."""

    def test_normalize_currency_code(self):
        self.assertEqual(normalize_currency_code("$"), "USD")
        self.assertEqual(normalize_currency_code("US$"), "USD")
        self.assertEqual(normalize_currency_code("usd"), "USD")
        self.assertEqual(normalize_currency_code("TZS"), "TZS")
        self.assertEqual(normalize_currency_code("tsh"), "TZS")
        self.assertEqual(normalize_currency_code("€"), "EUR")
        self.assertEqual(normalize_currency_code("euro"), "EUR")
        self.assertEqual(normalize_currency_code("£"), "GBP")
        self.assertEqual(normalize_currency_code("KES"), "KES")
        self.assertEqual(normalize_currency_code("UGX"), "UGX")

    def test_currency_display_names(self):
        self.assertEqual(get_currency_display_name("TZS"), "TZS Shillings")
        self.assertEqual(get_currency_display_name("KES"), "KES Shillings")
        self.assertEqual(get_currency_display_name("UGX"), "UGX Shillings")
        self.assertEqual(get_currency_display_name("USD"), "USD Dollars")
        self.assertEqual(get_currency_display_name("EUR"), "Euros (EUR)")
        self.assertEqual(get_currency_display_name("GBP"), "British Pounds (GBP)")

    def test_get_exchange_rate_benchmark(self):
        # Benchmark mode (offline)
        rate_usd_tzs = get_exchange_rate("USD", "TZS", live=False)
        self.assertAlmostEqual(rate_usd_tzs, 2648.76, delta=50.0)
        self.assertEqual(get_exchange_rate("USD", "USD", live=False), 1.0)
        self.assertEqual(get_exchange_rate("TZS", "TZS", live=False), 1.0)

    def test_live_online_rates_connectivity(self):
        # Verifies live market rates can be queried
        rates, is_live = fetch_live_rates()
        self.assertIn("TZS", rates)
        self.assertIn("USD", rates)
        self.assertGreater(rates["TZS"], 2000.0)

    def test_convert_amount(self):
        # Custom rate override
        custom = convert_amount(200.0, "USD", "TZS", rate=2600.0)
        self.assertEqual(custom, 520000.0)


class TestCurrencyDetection(unittest.TestCase):
    """Tests automatic detection of currency from headers and cells."""

    def test_detect_from_headers(self):
        # Dollar header
        df_usd = pd.DataFrame({"Invoice": ["INV-1"], "Amount ($)": [150.0]})
        res = CurrencyDetector.detect_currency_from_dataframe(df_usd)
        self.assertEqual(res["detected"], "USD")

        # Euro header
        df_eur = pd.DataFrame({"Item": ["Coffee"], "Price (€)": [4.50]})
        res = CurrencyDetector.detect_currency_from_dataframe(df_eur)
        self.assertEqual(res["detected"], "EUR")

        # TZS header
        df_tzs = pd.DataFrame({"Item": ["Sugar"], "Total (TZS)": [45000]})
        res = CurrencyDetector.detect_currency_from_dataframe(df_tzs)
        self.assertEqual(res["detected"], "TZS")

    def test_detect_from_cell_strings(self):
        # Dollar in cell
        df_usd = pd.DataFrame({"Product": ["Mouse", "Keyboard"], "Amount": ["$ 25.00", "$ 50.00"]})
        res = CurrencyDetector.detect_currency_from_dataframe(df_usd)
        self.assertEqual(res["detected"], "USD")

        # TZS in cell
        df_tzs = pd.DataFrame({"Product": ["Flour", "Sugar"], "Amount": ["TZS 12,000", "TZS 24,000"]})
        res = CurrencyDetector.detect_currency_from_dataframe(df_tzs)
        self.assertEqual(res["detected"], "TZS")

    def test_notification_message_generation(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
            csv_path = f.name
            f.write("Date,Product,Amount ($)\n")
            f.write("2026-10-01,Product A,100\n")

        try:
            det = CurrencyDetector.detect_workbook_currency(csv_path, default_currency="TZS")
            self.assertTrue(det["conversion_needed"])
            self.assertEqual(det["source_currency"], "USD")
            self.assertEqual(det["target_currency"], "TZS")
            expected_msg = "The file you uploaded had currencies different from TZS Shillings. We have converted the currencies to TZS Shillings and mapped the data."
            self.assertEqual(det["notification_message"], expected_msg)
        finally:
            if os.path.exists(csv_path):
                os.remove(csv_path)


class TestImporterCurrencyConversion(unittest.TestCase):
    """Tests end-to-end import with currency auto-conversion."""

    def setUp(self):
        init_db()
        self.test_company_id = f"test-comp-{generate_uuid()[:8]}"
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO companies (id, name, business_type, country, currency)
                VALUES (?, 'Currency Test Co', 'Retail', 'Tanzania', 'TZS');
                """,
                (self.test_company_id,),
            )

    def tearDown(self):
        # Clean up database completely to preserve pristine state
        with get_connection() as conn:
            conn.execute("DELETE FROM sales WHERE company_id = ?;", (self.test_company_id,))
            conn.execute("DELETE FROM sale_items WHERE sale_id NOT IN (SELECT id FROM sales);")
            conn.execute("DELETE FROM payments WHERE company_id = ?;", (self.test_company_id,))
            conn.execute("DELETE FROM inventory_movements WHERE company_id = ?;", (self.test_company_id,))
            conn.execute("DELETE FROM products WHERE company_id = ?;", (self.test_company_id,))
            conn.execute("DELETE FROM customers WHERE company_id = ?;", (self.test_company_id,))
            conn.execute("DELETE FROM expenses WHERE company_id = ?;", (self.test_company_id,))
            conn.execute("DELETE FROM import_jobs WHERE data_source_id IN (SELECT id FROM data_sources WHERE company_id = ?);", (self.test_company_id,))
            conn.execute("DELETE FROM data_sources WHERE company_id = ?;", (self.test_company_id,))
            conn.execute("DELETE FROM companies WHERE id = ?;", (self.test_company_id,))

    def test_usd_sheet_auto_converted_to_tzs(self):
        # Create a temporary USD spreadsheet
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
            csv_path = f.name
            f.write("Date,Client,Product Name,Quantity,Unit Price ($),Total ($)\n")
            f.write("2026-10-01,Test Client,Premium Headset,2,$100,$200\n")

        try:
            importer = BusinessDataImporter(self.test_company_id)
            res = importer.import_excel_workbook(csv_path)

            self.assertEqual(res["status"], "COMPLETED")
            self.assertEqual(res["total_rows_imported"], 1)
            self.assertTrue(res["currency_conversion"]["converted"])
            self.assertEqual(res["currency_conversion"]["source_currency"], "USD")
            self.assertEqual(res["currency_conversion"]["target_currency"], "TZS")
            self.assertGreater(res["currency_conversion"]["exchange_rate"], 2000.0)

            expected_notif = "The file you uploaded had currencies different from TZS Shillings. We have converted the currencies to TZS Shillings and mapped the data."
            self.assertEqual(res["currency_conversion"]["notification_message"], expected_notif)

            # Check database records
            expected_total = round(200.0 * res["currency_conversion"]["exchange_rate"], 2)
            expected_unit = round(100.0 * res["currency_conversion"]["exchange_rate"], 2)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT total, subtotal FROM sales WHERE company_id = ?;", (self.test_company_id,))
                sale_row = cursor.fetchone()
                self.assertIsNotNone(sale_row)
                self.assertEqual(sale_row[0], expected_total)

                # Check sale_items: quantity is 2 (NOT multiplied), unit_price is converted
                cursor.execute(
                    """
                    SELECT si.quantity, si.unit_price, si.total 
                    FROM sale_items si 
                    JOIN sales s ON si.sale_id = s.id 
                    WHERE s.company_id = ?;
                    """,
                    (self.test_company_id,),
                )
                item_row = cursor.fetchone()
                self.assertIsNotNone(item_row)
                self.assertEqual(item_row[0], 2.0)  # Quantity must remain 2!
                self.assertEqual(item_row[1], expected_unit)  # Unit price converted
                self.assertEqual(item_row[2], expected_total)  # Total converted

                # Check payments
                cursor.execute("SELECT amount FROM payments WHERE company_id = ?;", (self.test_company_id,))
                pay_row = cursor.fetchone()
                self.assertIsNotNone(pay_row)
                self.assertEqual(pay_row[0], expected_total)

        finally:
            if os.path.exists(csv_path):
                os.remove(csv_path)


if __name__ == "__main__":
    unittest.main()

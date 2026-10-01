"""
Unit tests for Data Quality Engine.
"""
import unittest
import pandas as pd
from engine.quality import DataQualityAuditor


class TestDataQuality(unittest.TestCase):
    def test_clean_currency(self):
        self.assertEqual(DataQualityAuditor.clean_currency("TZS 45,000"), 45000.0)
        self.assertEqual(DataQualityAuditor.clean_currency("$1,200.50"), 1200.50)
        self.assertEqual(DataQualityAuditor.clean_currency("28800.00"), 28800.0)
        self.assertEqual(DataQualityAuditor.clean_currency(""), 0.0)
        self.assertEqual(DataQualityAuditor.clean_currency(None), 0.0)

    def test_parse_flexible_date(self):
        valid, dt = DataQualityAuditor.parse_flexible_date("2026-09-30")
        self.assertTrue(valid)
        self.assertEqual(dt, "2026-09-30")

        valid, dt = DataQualityAuditor.parse_flexible_date("30/09/2026")
        self.assertTrue(valid)
        self.assertEqual(dt, "2026-09-30")

        valid, dt = DataQualityAuditor.parse_flexible_date("29-09-2026")
        self.assertTrue(valid)
        self.assertEqual(dt, "2026-09-29")

        valid, _ = DataQualityAuditor.parse_flexible_date("garbage-date")
        self.assertFalse(valid)

    def test_audit_dataframe_with_flaws(self):
        raw_rows = [
            {"Date": "2026-09-30", "Client": "Customer A", "Item": "Coca-Cola", "Qty": 2, "Price": 1200, "Total": 2400},
            {"Date": "2026-09-30", "Client": "Customer A", "Item": "Coca-Cola", "Qty": 2, "Price": 1200, "Total": 2400}, # duplicate
            {"Date": "2026-09-28", "Client": "Customer B", "Item": "Bread", "Qty": -3, "Price": 2000, "Total": 6000},    # negative qty
            {"Date": "bad-date", "Client": "Customer C", "Item": "Milk", "Qty": 1, "Price": 1500, "Total": 1500},        # bad date
            {"Date": "2026-09-26", "Client": "Customer D", "Item": "Water", "Qty": 5, "Price": 800, "Total": 4000},
        ]
        df = pd.DataFrame(raw_rows)
        mapping = {
            "Date": "sale_date",
            "Client": "customer_name",
            "Item": "product_name",
            "Qty": "quantity",
            "Price": "unit_price",
            "Total": "total_amount",
        }

        audit = DataQualityAuditor.audit_and_clean_dataframe(df, mapping, entity_type="sales")

        self.assertEqual(audit["total_rows"], 5)
        self.assertEqual(audit["duplicate_count"], 1)
        self.assertEqual(audit["negative_anomaly_count"], 1)
        self.assertEqual(audit["invalid_date_count"], 1)
        self.assertLess(audit["quality_score"], 100.0)
        self.assertEqual(len(audit["clean_records"]), 2) # 2 rows had no errors


if __name__ == "__main__":
    unittest.main()

"""
Unit tests for Ingestion and Smart Schema Mapping.
"""
import unittest
import os
import tempfile
import pandas as pd
from engine.mapping import SchemaMapper
from engine.ingestion import SpreadsheetReader, StagingManager
from database.db import init_db, query_all


class TestIngestionAndMapping(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        init_db(self.temp_db_path)
        os.environ["BUSINESS_PILOT_DB"] = self.temp_db_path

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_entity_detection_sales(self):
        sales_cols = ["Date", "Client", "Item", "Qty", "Price", "Amount"]
        entity, conf = SchemaMapper.detect_entity(sales_cols)
        self.assertEqual(entity, "sales")
        self.assertGreater(conf, 0.7)

    def test_entity_detection_expenses(self):
        exp_cols = ["Date", "Category", "Vendor", "Amount", "Description"]
        entity, conf = SchemaMapper.detect_entity(exp_cols)
        self.assertEqual(entity, "expenses")
        self.assertGreater(conf, 0.7)

    def test_column_mapping_confidence(self):
        cols = ["Client", "Item", "Qty", "Selling Price", "Date", "Amount"]
        result = SchemaMapper.map_columns(cols, target_entity="sales")

        self.assertEqual(result["detected_entity"], "sales")
        self.assertIn("Client", result["mappings"])
        self.assertEqual(result["mappings"]["Client"]["system_field"], "customer_name")
        self.assertEqual(result["mappings"]["Item"]["system_field"], "product_name")
        self.assertEqual(result["mappings"]["Qty"]["system_field"], "quantity")
        self.assertEqual(result["mappings"]["Selling Price"]["system_field"], "unit_price")
        self.assertEqual(result["mappings"]["Date"]["system_field"], "sale_date")
        self.assertEqual(result["mappings"]["Amount"]["system_field"], "total_amount")
        self.assertGreaterEqual(result["overall_confidence"], 0.90)

    def test_ambiguity_detection(self):
        cols = ["Date", "Item", "Amount Paid"]
        result = SchemaMapper.map_columns(cols, target_entity="sales")
        self.assertTrue(any(a["column"] == "Amount Paid" for a in result["ambiguities"]))

    def test_staging_manager(self):
        from database.db import get_connection
        with get_connection() as conn:
            conn.execute("INSERT OR IGNORE INTO companies (id, name) VALUES ('comp-test', 'Test Co');")
        source_id, job_id = StagingManager.create_import_job("comp-test", "dummy.csv")
        df = pd.DataFrame([
            {"Client": "Safari Hotel", "Amount": 45000},
            {"Client": "Amina Said", "Amount": 12000},
        ])
        staged = StagingManager.stage_raw_dataframe(job_id, df)
        self.assertEqual(staged, 2)

        rows = query_all("SELECT * FROM raw_import_rows WHERE import_job_id = ?;", (job_id,))
        self.assertEqual(len(rows), 2)
        self.assertIn("Safari Hotel", rows[0]["raw_data"])


if __name__ == "__main__":
    unittest.main()

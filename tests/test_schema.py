"""
Unit tests for Database Schema, Foreign Keys, and Multi-Tenancy.
"""
import unittest
import os
import tempfile
import sqlite3
from database.db import init_db, query_all, query_one, get_connection, generate_uuid


class TestDatabaseSchema(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        init_db(self.temp_db_path)

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_company_creation_and_isolation(self):
        comp1_id = generate_uuid()
        comp2_id = generate_uuid()

        with get_connection(self.temp_db_path) as conn:
            conn.execute(
                "INSERT INTO companies (id, name, currency) VALUES (?, 'Company Alpha', 'TZS');",
                (comp1_id,),
            )
            conn.execute(
                "INSERT INTO companies (id, name, currency) VALUES (?, 'Company Beta', 'USD');",
                (comp2_id,),
            )
            # Insert product for Company Alpha
            conn.execute(
                "INSERT INTO products (id, company_id, sku, name, selling_price, cost_price) VALUES (?, ?, 'P1', 'Coke', 1000, 700);",
                (generate_uuid(), comp1_id),
            )
            # Insert product for Company Beta
            conn.execute(
                "INSERT INTO products (id, company_id, sku, name, selling_price, cost_price) VALUES (?, ?, 'P1', 'Pepsi', 1100, 750);",
                (generate_uuid(), comp2_id),
            )

        # Multi-tenant isolation verification
        alpha_prods = query_all("SELECT * FROM products WHERE company_id = ?;", (comp1_id,), self.temp_db_path)
        beta_prods = query_all("SELECT * FROM products WHERE company_id = ?;", (comp2_id,), self.temp_db_path)

        self.assertEqual(len(alpha_prods), 1)
        self.assertEqual(alpha_prods[0]["name"], "Coke")
        self.assertEqual(len(beta_prods), 1)
        self.assertEqual(beta_prods[0]["name"], "Pepsi")

    def test_foreign_key_cascade(self):
        comp_id = generate_uuid()
        cust_id = generate_uuid()

        with get_connection(self.temp_db_path) as conn:
            conn.execute("INSERT INTO companies (id, name) VALUES (?, 'Test Co');", (comp_id,))
            conn.execute("INSERT INTO customers (id, company_id, name) VALUES (?, ?, 'Client X');", (cust_id, comp_id))

        # Verify customer exists after commit
        cust = query_one("SELECT * FROM customers WHERE id = ?;", (cust_id,), self.temp_db_path)
        self.assertIsNotNone(cust)

        # Delete company and verify cascade
        with get_connection(self.temp_db_path) as conn:
            conn.execute("DELETE FROM companies WHERE id = ?;", (comp_id,))

        cust_after = query_one("SELECT * FROM customers WHERE id = ?;", (cust_id,), self.temp_db_path)
        self.assertIsNone(cust_after)


if __name__ == "__main__":
    unittest.main()

"""
End-to-End Importer Pipeline for BusinessPilot.
Orchestrates:
1. Staging raw data
2. Automatic entity detection & column mapping
3. Quality auditing & cleaning
4. Committing validated business data into multi-tenant core tables.
"""
import os
import json
import pandas as pd
from typing import Dict, Any, Optional
from database.db import get_connection, generate_uuid, execute_write
from engine.ingestion import SpreadsheetReader, StagingManager
from engine.mapping import SchemaMapper
from engine.quality import DataQualityAuditor
from engine.currency import CurrencyDetector, get_exchange_rate


class BusinessDataImporter:
    """Orchestrates end-to-end import from file to verified database records."""

    def __init__(self, company_id: str):
        self.company_id = company_id
        # Determine company's base currency from database
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT currency FROM companies WHERE id = ?;", (company_id,))
            row = cursor.fetchone()
            self.company_currency = row[0] if row and row[0] else "TZS"

    def import_excel_workbook(
        self,
        file_path: str,
        exchange_rate: Optional[float] = None,
        source_currency: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Imports an entire multi-tab Excel workbook or single CSV with optional auto-currency conversion."""
        inspection = SpreadsheetReader.inspect_file(file_path)
        source_id, job_id = StagingManager.create_import_job(self.company_id, file_path)

        # Detect source currency if not explicitly provided
        currency_info = CurrencyDetector.detect_workbook_currency(file_path, default_currency=self.company_currency)
        detected_source = source_currency or currency_info.get("source_currency") or self.company_currency

        if exchange_rate is None:
            if detected_source != self.company_currency:
                exchange_rate = get_exchange_rate(detected_source, self.company_currency)
            else:
                exchange_rate = 1.0
        else:
            try:
                exchange_rate = float(exchange_rate)
            except (ValueError, TypeError):
                exchange_rate = 1.0

        conversion_applied = (exchange_rate != 1.0)

        sheets_results = {}
        total_rows_imported = 0
        total_rows_failed = 0

        for sheet_name in inspection["sheets"].keys():
            df = SpreadsheetReader.load_full_sheet(file_path, sheet_name=sheet_name)
            if df.empty:
                continue

            # Stage raw data for auditability
            StagingManager.stage_raw_dataframe(job_id, df)

            # Auto-detect entity and map columns with sheet_name hint
            mapping_result = SchemaMapper.map_columns(list(df.columns), sheet_name=sheet_name)
            entity_type = mapping_result["detected_entity"]
            col_mappings = {src: data["system_field"] for src, data in mapping_result["mappings"].items()}

            # Run Data Quality Audit
            audit_result = DataQualityAuditor.audit_and_clean_dataframe(df, col_mappings, entity_type=entity_type)

            # Save confirmed mappings
            SchemaMapper.save_confirmed_mappings(source_id, mapping_result["mappings"])

            # Commit clean records into core database tables with FX rate conversion
            committed_count = self._commit_clean_records(
                entity_type, audit_result["clean_records"], exchange_rate=exchange_rate
            )
            total_rows_imported += committed_count
            total_rows_failed += len(audit_result["error_records"])

            sheets_results[sheet_name] = {
                "detected_entity": entity_type,
                "entity_confidence": mapping_result["entity_confidence"],
                "quality_score": audit_result["quality_score"],
                "total_rows": audit_result["total_rows"],
                "valid_rows": committed_count,
                "errors_count": len(audit_result["error_records"]),
                "sample_errors": audit_result["error_records"][:3],
            }

        # Update import job completion status
        status = "COMPLETED" if total_rows_failed == 0 else "PARTIAL_SUCCESS"
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE import_jobs 
                SET status = ?, rows_successful = ?, rows_failed = ?, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (status, total_rows_imported, total_rows_failed, job_id),
            )

        return {
            "job_id": job_id,
            "status": status,
            "total_rows_imported": total_rows_imported,
            "total_rows_failed": total_rows_failed,
            "sheets": sheets_results,
            "currency_conversion": {
                "source_currency": detected_source,
                "target_currency": self.company_currency,
                "exchange_rate": exchange_rate,
                "converted": conversion_applied,
            },
        }

    def _commit_clean_records(self, entity_type: str, records: list, exchange_rate: float = 1.0) -> int:
        """Inserts audited clean records into multi-tenant tables, converting monetary values by exchange_rate."""
        if not records:
            return 0

        committed = 0
        with get_connection() as conn:
            if entity_type == "sales":
                for rec in records:
                    sale_id = generate_uuid()
                    item_id = generate_uuid()

                    # Find or create customer
                    cust_name = rec.get("customer_name", "Walk-in Customer")
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM customers WHERE company_id = ? AND name = ?",
                        (self.company_id, cust_name),
                    )
                    cust_row = cursor.fetchone()
                    if cust_row:
                        customer_id = cust_row[0]
                    else:
                        customer_id = generate_uuid()
                        conn.execute(
                            """
                            INSERT INTO customers (id, company_id, name, customer_type)
                            VALUES (?, ?, ?, 'Retail');
                            """,
                            (customer_id, self.company_id, cust_name),
                        )

                    # Monetary conversions via exchange_rate
                    raw_unit_price = float(rec.get("unit_price", 0.0))
                    raw_cost_price = float(rec.get("cost_price", 0.0))
                    raw_total = float(rec.get("total", 0.0))
                    raw_cogs = float(rec.get("cost_of_goods", 0.0))
                    raw_profit = float(rec.get("profit", 0.0))

                    unit_price = round(raw_unit_price * exchange_rate, 2)
                    cost_price = round(raw_cost_price * exchange_rate, 2)
                    total = round(raw_total * exchange_rate, 2)
                    cost_of_goods = round(raw_cogs * exchange_rate, 2)
                    profit = round(raw_profit * exchange_rate, 2)

                    # Find or create product
                    prod_name = rec.get("product_name", "General Item")
                    cursor.execute(
                        "SELECT id FROM products WHERE company_id = ? AND name = ?",
                        (self.company_id, prod_name),
                    )
                    prod_row = cursor.fetchone()
                    if prod_row:
                        product_id = prod_row[0]
                    else:
                        product_id = generate_uuid()
                        sku = f"SKU-{generate_uuid()[:8]}"
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO products (id, company_id, sku, name, selling_price, cost_price)
                            VALUES (?, ?, ?, ?, ?, ?);
                            """,
                            (product_id, self.company_id, sku, prod_name, unit_price, cost_price),
                        )
                        cursor.execute("SELECT id FROM products WHERE company_id = ? AND (name = ? OR sku = ?)", (self.company_id, prod_name, sku))
                        r = cursor.fetchone()
                        if r:
                            product_id = r[0]

                    # Insert Sale
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO sales (
                            id, company_id, customer_id, invoice_number, sale_date, 
                            subtotal, total, cost_of_goods, profit, payment_status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            sale_id,
                            self.company_id,
                            customer_id,
                            rec.get("invoice_number", f"INV-{sale_id[:8]}"),
                            rec.get("sale_date"),
                            total,
                            total,
                            cost_of_goods,
                            profit,
                            rec.get("payment_status", "Paid"),
                        ),
                    )

                    # Insert Sale Item
                    conn.execute(
                        """
                        INSERT INTO sale_items (
                            id, sale_id, product_id, quantity, unit_price, total, cost_price, profit
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            item_id,
                            sale_id,
                            product_id,
                            rec.get("quantity", 1.0),
                            unit_price,
                            total,
                            cost_price,
                            profit,
                        ),
                    )

                    # Record Inventory Movement (Deduction from stock)
                    im_id = generate_uuid()
                    conn.execute(
                        """
                        INSERT INTO inventory_movements (
                            id, company_id, product_id, movement_type, quantity, unit_cost, reference_type, reference_id, movement_date
                        ) VALUES (?, ?, ?, 'SALE', ?, ?, 'SALE', ?, ?);
                        """,
                        (
                            im_id,
                            self.company_id,
                            product_id,
                            -abs(rec.get("quantity", 1.0)),
                            cost_price,
                            sale_id,
                            rec.get("sale_date"),
                        ),
                    )

                    # If paid, record payment entry
                    if rec.get("payment_status") == "Paid":
                        pay_id = generate_uuid()
                        conn.execute(
                            """
                            INSERT INTO payments (
                                id, company_id, sale_id, customer_id, amount, payment_method, payment_date
                            ) VALUES (?, ?, ?, ?, ?, ?, ?);
                            """,
                            (
                                pay_id,
                                self.company_id,
                                sale_id,
                                customer_id,
                                total,
                                rec.get("payment_method", "Cash"),
                                rec.get("sale_date"),
                            ),
                        )

                    committed += 1

            elif entity_type == "expenses":
                # Pre-fetch existing categories for this company
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, name, type FROM expense_categories WHERE company_id = ?",
                    (self.company_id,),
                )
                existing_cats = {row[1]: (row[0], row[1], row[2]) for row in cursor.fetchall()}

                for rec in records:
                    exp_id = generate_uuid()
                    raw_cat = str(rec.get("category", "General Expense")).strip()
                    cat_type = str(rec.get("category_type", "OPERATING")).strip().upper() or "OPERATING"

                    # Normalize category to consolidate duplicate/typo entries e.g. 'Salries' -> 'Salaries'
                    norm_name = self.normalize_expense_category(raw_cat, list(existing_cats.keys()))

                    if norm_name in existing_cats:
                        cat_id = existing_cats[norm_name][0]
                    else:
                        cat_id = generate_uuid()
                        conn.execute(
                            """
                            INSERT INTO expense_categories (id, company_id, name, type)
                            VALUES (?, ?, ?, ?);
                            """,
                            (cat_id, self.company_id, norm_name, cat_type),
                        )
                        existing_cats[norm_name] = (cat_id, norm_name, cat_type)

                    desc = str(rec.get("description", "")).strip() or norm_name
                    raw_amount = float(rec.get("amount", 0.0))
                    amount = round(raw_amount * exchange_rate, 2)

                    conn.execute(
                        """
                        INSERT INTO expenses (
                            id, company_id, category_id, description, amount, expense_date, status
                        ) VALUES (?, ?, ?, ?, ?, ?, 'Paid');
                        """,
                        (
                            exp_id,
                            self.company_id,
                            cat_id,
                            desc,
                            amount,
                            rec.get("expense_date"),
                        ),
                    )
                    committed += 1

            elif entity_type == "inventory":
                for rec in records:
                    sku = rec.get("sku")
                    name = rec.get("product_name")
                    cost = round(float(rec.get("unit_cost", 0.0)) * exchange_rate, 2)
                    price = round(float(rec.get("selling_price", 0.0)) * exchange_rate, 2)
                    qty = float(rec.get("stock_quantity", 0.0))
                    reorder = float(rec.get("reorder_level", 10.0))

                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM products WHERE company_id = ? AND sku = ?", (self.company_id, sku))
                    row = cursor.fetchone()
                    if row:
                        prod_id = row[0]
                    else:
                        prod_id = generate_uuid()
                        conn.execute(
                            """
                            INSERT INTO products (id, company_id, sku, name, selling_price, cost_price, reorder_level)
                            VALUES (?, ?, ?, ?, ?, ?, ?);
                            """,
                            (prod_id, self.company_id, sku, name, price, cost, reorder),
                        )

                    # Initial stock purchase movement
                    im_id = generate_uuid()
                    conn.execute(
                        """
                        INSERT INTO inventory_movements (
                            id, company_id, product_id, movement_type, quantity, unit_cost, reference_type
                        ) VALUES (?, ?, ?, 'PURCHASE', ?, ?, 'INITIAL_IMPORT');
                        """,
                        (im_id, self.company_id, prod_id, qty, cost),
                    )
                    committed += 1

            elif entity_type == "customers":
                for rec in records:
                    cust_id = generate_uuid()
                    credit_limit = round(float(rec.get("credit_limit", 0.0)) * exchange_rate, 2)
                    payment_terms = int(rec.get("payment_terms", 0))

                    conn.execute(
                        """
                        INSERT OR REPLACE INTO customers (
                            id, company_id, customer_code, name, phone, customer_type, credit_limit, payment_terms
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            cust_id,
                            self.company_id,
                            rec.get("customer_code", f"CUST-{cust_id[:6]}"),
                            rec.get("customer_name"),
                            rec.get("phone", ""),
                            rec.get("customer_type", "Retail"),
                            credit_limit,
                            payment_terms,
                        ),
                    )
                    committed += 1

        return committed

    @staticmethod
    def normalize_expense_category(raw_name: str, existing_names: list) -> str:
        """Normalizes expense categories and groups typos/variations to enable auto-summing."""
        import difflib
        s = str(raw_name).strip()
        if not s or s.lower() == "nan":
            return "General Expense"

        s_canonical = s.title() if s.islower() else s
        s_clean = s.lower().replace("&", "and")

        # 1. Exact case-insensitive match
        for ex in existing_names:
            if ex.lower().replace("&", "and") == s_clean:
                return ex

        # 2. Fuzzy match against existing categories (similarity >= 0.82)
        best_match = None
        best_ratio = 0.0
        for ex in existing_names:
            ex_clean = ex.lower().replace("&", "and")
            ratio = difflib.SequenceMatcher(None, s_clean, ex_clean).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = ex

        if best_match and best_ratio >= 0.82:
            return best_match

        return s_canonical


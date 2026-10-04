"""
Data Quality Engine for BusinessPilot.
Performs rigorous pre-flight audits on uploaded business spreadsheets,
cleaning currencies, validating dates, flagging duplicates and negative anomalies,
and generating an overall data trustworthiness score.
"""
import re
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Tuple


# The class below is for running pre-flight data audits and cleaning spreadsheet values
class DataQualityAuditor:
    """Pre-flight quality auditor and data cleaner."""

    # The function below is for parsing currency strings and multipliers into standard numeric floats
    @staticmethod
    def clean_currency(val: Any) -> float:
        """Parses currency strings like '$1,200.50', 'TZS 45,000', '226M', '1.200.000,50' into float."""
        if pd.isna(val) or val == "" or val is None:
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)

        s = str(val).strip()
        # Accounting negative e.g. (1,500)
        is_negative = False
        if s.startswith("(") and s.endswith(")"):
            is_negative = True
            s = s[1:-1].strip()
        elif s.startswith("-"):
            is_negative = True
            s = s[1:].strip()

        # Multipliers (M, million, K, thousand, B, billion)
        multiplier = 1.0
        s_lower = s.lower()
        if s_lower.endswith("m") or "million" in s_lower:
            multiplier = 1_000_000.0
            s = re.sub(r"(?i)millions?|m", "", s).strip()
        elif s_lower.endswith("k") or "thousand" in s_lower:
            multiplier = 1_000.0
            s = re.sub(r"(?i)thousands?|k", "", s).strip()
        elif s_lower.endswith("b") or "billion" in s_lower:
            multiplier = 1_000_000_000.0
            s = re.sub(r"(?i)billions?|b", "", s).strip()

        # Strip currency symbols and letters
        s = re.sub(r"[^\d.,]", "", s).strip()
        if not s:
            return 0.0

        # Handle European vs Anglo-American thousands/decimals
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                # European: 1.200.000,50
                s = s.replace(".", "").replace(",", ".")
            else:
                # Standard: 1,200,000.50
                s = s.replace(",", "")
        elif "," in s:
            parts = s.split(",")
            if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
                s = s.replace(",", "")
            else:
                s = s.replace(",", ".")
        elif "." in s:
            parts = s.split(".")
            if len(parts) > 2:
                s = s.replace(".", "")

        try:
            res = float(s) * multiplier
            return -res if is_negative else res
        except ValueError:
            return 0.0

    # The function below is for parsing various date formats into standard ISO YYYY-MM-DD
    @staticmethod
    def parse_flexible_date(val: Any) -> Tuple[bool, str]:
        """
        Parses varied date representations into ISO 'YYYY-MM-DD' format.
        Handles pandas timestamps, strings like '2026-09-30', '30/09/2026', '09/30/2026'.
        """
        if pd.isna(val) or val == "" or val is None:
            return False, ""

        if isinstance(val, (datetime, pd.Timestamp)):
            return True, val.strftime("%Y-%m-%d")

        s = str(val).strip()
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
            "%d %b %Y",
            "%d %B %Y",
            "%b %d, %Y",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(s, fmt)
                return True, dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        try:
            dt = pd.to_datetime(s)
            return True, dt.strftime("%Y-%m-%d")
        except Exception:
            return False, s

    # The function below is for auditing and cleaning an entire DataFrame before database ingestion
    @classmethod
    def audit_and_clean_dataframe(
        cls, df: pd.DataFrame, mapping_spec: Dict[str, str], entity_type: str = "sales"
    ) -> Dict[str, Any]:
        """
        Audits raw dataframe against mapped fields:
        - Detects duplicate rows
        - Validates and standardizes dates
        - Cleans and casts numerical values
        - Flags anomalies (negative quantities, missing critical keys)
        - Computes overall Data Trustworthiness percentage
        """
        total_rows = len(df)
        if total_rows == 0:
            return {
                "total_rows": 0,
                "valid_rows": 0,
                "duplicate_count": 0,
                "missing_critical_count": 0,
                "invalid_date_count": 0,
                "negative_anomaly_count": 0,
                "quality_score": 100.0,
                "clean_records": [],
                "error_records": [],
            }

        # Invert mapping: system_field -> source_column
        sys_to_src = {v: k for k, v in mapping_spec.items()}

        clean_records = []
        error_records = []
        seen_keys = set()
        duplicate_count = 0
        invalid_date_count = 0
        negative_anomaly_count = 0
        missing_critical_count = 0

        for idx, row in df.iterrows():
            row_dict = row.to_dict()
            row_errors = []
            cleaned_row = {}

            # Check duplicates (based on signature)
            row_sig = tuple(str(row_dict.get(c, "")).strip().lower() for c in df.columns)
            if row_sig in seen_keys:
                duplicate_count += 1
                row_errors.append("Duplicate row detected")
            else:
                seen_keys.add(row_sig)

            # Process entity specific requirements
            if entity_type == "sales":
                # Date validation
                date_col = sys_to_src.get("sale_date")
                if date_col and date_col in row_dict:
                    valid_dt, parsed_dt = cls.parse_flexible_date(row_dict[date_col])
                    if not valid_dt:
                        invalid_date_count += 1
                        row_errors.append(f"Invalid date format: '{row_dict[date_col]}'")
                    else:
                        cleaned_row["sale_date"] = parsed_dt
                else:
                    cleaned_row["sale_date"] = datetime.now().strftime("%Y-%m-%d")

                # Customer
                cust_col = sys_to_src.get("customer_name")
                cleaned_row["customer_name"] = str(row_dict.get(cust_col, "Walk-in Customer")).strip()
                if not cleaned_row["customer_name"] or cleaned_row["customer_name"] == "nan":
                    cleaned_row["customer_name"] = "Walk-in Customer"

                # Product
                prod_col = sys_to_src.get("product_name")
                cleaned_row["product_name"] = str(row_dict.get(prod_col, "General Item")).strip()
                if not cleaned_row["product_name"] or cleaned_row["product_name"] == "nan":
                    missing_critical_count += 1
                    row_errors.append("Missing product name")

                # Quantity
                qty_col = sys_to_src.get("quantity")
                qty = cls.clean_currency(row_dict.get(qty_col, 1.0))
                if qty < 0:
                    negative_anomaly_count += 1
                    row_errors.append(f"Negative quantity: {qty}")
                cleaned_row["quantity"] = max(0.0, qty)

                # Unit Price
                price_col = sys_to_src.get("unit_price")
                unit_price = cls.clean_currency(row_dict.get(price_col, 0.0))
                cleaned_row["unit_price"] = unit_price

                # Cost Price (COGS)
                cost_col = sys_to_src.get("cost_price")
                cost_price = cls.clean_currency(row_dict.get(cost_col, 0.0))
                if cost_price == 0.0 and unit_price > 0:
                    # Default estimated cost if unstated (65% of price)
                    cost_price = round(unit_price * 0.65, 2)
                cleaned_row["cost_price"] = cost_price

                # Total Amount
                total_col = sys_to_src.get("total_amount")
                total = cls.clean_currency(row_dict.get(total_col, 0.0))
                if total == 0.0 and unit_price > 0:
                    total = round(cleaned_row["quantity"] * unit_price, 2)
                cleaned_row["total"] = total
                cleaned_row["cost_of_goods"] = round(cleaned_row["quantity"] * cost_price, 2)
                cleaned_row["profit"] = round(cleaned_row["total"] - cleaned_row["cost_of_goods"], 2)

                # Invoice number
                inv_col = sys_to_src.get("invoice_number")
                cleaned_row["invoice_number"] = str(row_dict.get(inv_col, f"INV-{idx+1:05d}")).strip()

                # Payment Status & Method
                status_col = sys_to_src.get("payment_status")
                cleaned_row["payment_status"] = str(row_dict.get(status_col, "Paid")).strip()
                method_col = sys_to_src.get("payment_method")
                cleaned_row["payment_method"] = str(row_dict.get(method_col, "Cash")).strip()

            elif entity_type == "expenses":
                date_col = sys_to_src.get("expense_date")
                valid_dt, parsed_dt = cls.parse_flexible_date(row_dict.get(date_col))
                cleaned_row["expense_date"] = parsed_dt if valid_dt else datetime.now().strftime("%Y-%m-%d")

                cat_col = sys_to_src.get("category")
                cleaned_row["category"] = str(row_dict.get(cat_col, "General Expense")).strip()

                type_col = sys_to_src.get("category_type")
                cleaned_row["category_type"] = str(row_dict.get(type_col, "OPERATING")).strip()

                amt_col = sys_to_src.get("amount")
                amount = cls.clean_currency(row_dict.get(amt_col, 0.0))
                cleaned_row["amount"] = abs(amount)

                ref_col = sys_to_src.get("reference_number")
                cleaned_row["reference_number"] = str(row_dict.get(ref_col, f"EXP-{idx+1:05d}")).strip()

                desc_col = sys_to_src.get("description")
                desc = str(row_dict.get(desc_col, "")).strip()
                if not desc or desc == "nan":
                    desc = cleaned_row["category"]
                cleaned_row["description"] = desc

                vend_col = sys_to_src.get("vendor")
                cleaned_row["vendor"] = str(row_dict.get(vend_col, "General Vendor")).strip()

            elif entity_type == "inventory":
                sku_col = sys_to_src.get("sku")
                cleaned_row["sku"] = str(row_dict.get(sku_col, f"SKU-{idx+1:04d}")).strip()

                prod_col = sys_to_src.get("product_name")
                cleaned_row["product_name"] = str(row_dict.get(prod_col, "Stock Item")).strip()

                qty_col = sys_to_src.get("stock_quantity")
                cleaned_row["stock_quantity"] = max(0.0, cls.clean_currency(row_dict.get(qty_col, 0.0)))

                cost_col = sys_to_src.get("unit_cost")
                cleaned_row["unit_cost"] = cls.clean_currency(row_dict.get(cost_col, 0.0))

                price_col = sys_to_src.get("selling_price")
                cleaned_row["selling_price"] = cls.clean_currency(row_dict.get(price_col, 0.0))

                reorder_col = sys_to_src.get("reorder_level")
                cleaned_row["reorder_level"] = max(0.0, cls.clean_currency(row_dict.get(reorder_col, 10.0)))

            elif entity_type == "customers":
                name_col = sys_to_src.get("customer_name")
                raw_name = str(row_dict.get(name_col, "")).strip()
                if not raw_name or raw_name == "nan":
                    missing_critical_count += 1
                    row_errors.append("Missing customer name")
                cleaned_row["customer_name"] = raw_name or "Unknown Customer"

                code_col = sys_to_src.get("customer_code")
                cleaned_row["customer_code"] = str(row_dict.get(code_col, f"CUST-{idx+1:04d}")).strip()

                phone_col = sys_to_src.get("phone")
                cleaned_row["phone"] = str(row_dict.get(phone_col, "")).strip()

                type_col = sys_to_src.get("customer_type")
                cleaned_row["customer_type"] = str(row_dict.get(type_col, "Retail")).strip()

                cred_col = sys_to_src.get("credit_limit")
                cleaned_row["credit_limit"] = cls.clean_currency(row_dict.get(cred_col, 0.0))

                terms_col = sys_to_src.get("payment_terms")
                cleaned_row["payment_terms"] = int(cls.clean_currency(row_dict.get(terms_col, 0)))

            if row_errors:
                error_records.append({
                    "row_number": idx + 1,
                    "errors": row_errors,
                    "raw": row_dict
                })
            else:
                clean_records.append(cleaned_row)

        valid_count = len(clean_records)
        total_flaws = duplicate_count + invalid_date_count + negative_anomaly_count + missing_critical_count
        quality_score = max(0.0, min(100.0, round(((total_rows - total_flaws) / max(1, total_rows)) * 100, 1)))

        return {
            "total_rows": total_rows,
            "valid_rows": valid_count,
            "duplicate_count": duplicate_count,
            "missing_critical_count": missing_critical_count,
            "invalid_date_count": invalid_date_count,
            "negative_anomaly_count": negative_anomaly_count,
            "quality_score": quality_score,
            "clean_records": clean_records,
            "error_records": error_records,
        }

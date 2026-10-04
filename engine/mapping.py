"""
Smart Schema Mapping Engine for BusinessPilot.
Automatically detects entities (Sales, Expenses, Inventory, Customers)
and maps varied spreadsheet headers to standardized database fields
with confidence scoring and ambiguity detection.
"""
import re
from typing import Dict, List, Any, Optional, Tuple
from database.db import get_connection, generate_uuid

# Target Schema Dictionaries with common aliases
STANDARD_FIELDS = {
    "sales": {
        "invoice_number": ["invoice", "invoice_number", "inv_num", "order_id", "order_number", "receipt_no", "ref", "sale_id", "transaction_id"],
        "sale_date": ["date", "sale_date", "order_date", "transaction_date", "invoice_date", "time", "timestamp"],
        "customer_name": ["customer", "client", "customer_name", "client_name", "buyer", "account", "customer_id"],
        "product_name": ["product", "item", "product_name", "item_name", "description", "item_description", "sku"],
        "quantity": ["quantity", "qty", "qty_sold", "units", "units_sold", "volume", "count", "number_of_items"],
        "unit_price": ["unit_price", "price", "selling_price", "rate", "unit_rate", "item_price"],
        "cost_price": ["cost", "unit_cost", "cost_price", "cogs", "buy_price", "purchase_price"],
        "discount": ["discount", "discount_amount", "rebate", "promo"],
        "tax": ["tax", "vat", "tax_amount", "gst"],
        "total_amount": ["total", "amount", "revenue", "total_amount", "net_amount", "gross_amount", "sales_value", "total_sales"],
        "payment_status": ["payment_status", "status", "paid_status", "payment_state"],
        "payment_method": ["payment_method", "method", "mode", "payment_type", "channel"],
    },
    "expenses": {
        "reference_number": ["expense_id", "id", "ref", "reference", "ref_no", "voucher_no", "code", "trans_id", "bill_no", "receipt_no"],
        "expense_date": ["date", "expense_date", "payment_date", "trans_date", "timestamp", "transaction_date"],
        "category": ["category", "expense_category", "cost_center", "account", "expense_type", "head", "budget_line"],
        "category_type": ["type", "category_type", "classification", "class", "group"],
        "description": ["description", "details", "memo", "note", "purpose", "item", "narration", "particulars"],
        "vendor": ["vendor", "supplier", "payee", "paid_to", "provider", "company", "contractor"],
        "amount": ["amount", "cost", "total", "expense_amount", "amount_paid", "total_amount", "sum", "value", "spent", "fee"],
        "payment_method": ["payment_method", "method", "paid_via", "bank", "mode", "payment_type"],
    },
    "inventory": {
        "sku": ["sku", "item_code", "product_code", "barcode", "code"],
        "product_name": ["product", "product_name", "item", "item_name", "name", "description"],
        "category": ["category", "product_category", "group", "department"],
        "stock_quantity": ["stock", "quantity", "qty_on_hand", "current_stock", "balance", "available", "units"],
        "unit_cost": ["cost", "unit_cost", "cost_price", "purchase_cost"],
        "selling_price": ["price", "selling_price", "retail_price", "unit_price"],
        "reorder_level": ["reorder_level", "min_stock", "safety_stock", "threshold"],
        "location": ["location", "warehouse", "branch", "store"],
    },
    "customers": {
        "customer_name": ["name", "customer_name", "client_name", "company_name", "full_name"],
        "customer_code": ["code", "customer_id", "client_id", "account_number"],
        "email": ["email", "e_mail", "email_address", "contact_email"],
        "phone": ["phone", "mobile", "telephone", "phone_number", "contact_number"],
        "address": ["address", "location", "city", "region"],
        "customer_type": ["type", "customer_type", "tier", "segment", "classification"],
        "credit_limit": ["credit_limit", "limit", "credit"],
        "payment_terms": ["terms", "payment_terms", "credit_days"],
    },
}

NUMERIC_FIELDS = {"amount", "total_amount", "unit_price", "cost_price", "quantity", "stock_quantity", "unit_cost", "selling_price", "discount", "tax"}

# The class below is for intelligent column schema mapping and entity classification
class SchemaMapper:
    """Intelligent column mapping and entity classifier."""

    # The function below is for normalizing column headers into clean lowercase snake_case
    @staticmethod
    def normalize_header(header: str) -> str:
        s = str(header).lower().strip()
        s = re.sub(r"[^\w\s]", "", s)
        s = re.sub(r"\s+", "_", s)
        return s

    # The function below is for stripping currency suffixes from column names
    @staticmethod
    def strip_currency_suffix(col: str) -> str:
        s = col.lower().strip()
        currencies = ["_tzs", "_usd", "_kes", "_eur", "_gbp", "_zar", "_ngn", "_inr", "_cad", "_tsh", "_shs"]
        for curr in currencies:
            if s.endswith(curr):
                return s[:-len(curr)]
        return s

    # The function below is for detecting if a column name represents an identifier or code
    @staticmethod
    def is_identifier_column(col: str) -> bool:
        s = col.lower().strip()
        return (
            s.endswith("_id")
            or s.endswith("_no")
            or s.endswith("_num")
            or s.endswith("_number")
            or s.endswith("_code")
            or s.endswith("_ref")
            or s in ["id", "code", "ref", "number", "no"]
            or s.startswith("id_")
        )

    # The function below is for detecting whether a spreadsheet represents Sales, Expenses, Inventory, or Customers
    @classmethod
    def detect_entity(cls, columns: List[str], sheet_name: Optional[str] = None) -> Tuple[str, float]:
        """
        Detects whether the columns belong to 'sales', 'expenses', 'inventory', or 'customers'.
        Uses column signature keywords, distinctiveness scoring, and sheet name hints.
        """
        if sheet_name:
            norm_sheet = cls.normalize_header(sheet_name)
            if norm_sheet in ["sales", "orders", "transactions", "invoices"]:
                return "sales", 0.99
            elif norm_sheet in ["expenses", "expenditure", "costs", "purchases"]:
                return "expenses", 0.99
            elif norm_sheet in ["inventory", "stock", "products", "items"]:
                return "inventory", 0.99
            elif norm_sheet in ["customers", "clients", "buyers", "accounts"]:
                return "customers", 0.99

        normalized_cols = [cls.normalize_header(c) for c in columns]

        signatures = {
            "sales": ["invoice", "qty", "quantity", "units_sold", "profit", "customer_name", "client", "selling_price"],
            "expenses": ["expense", "vendor", "payee", "cost_center", "category_type", "expense_date", "expense_id"],
            "inventory": ["sku", "stock", "reorder", "reorder_level", "stock_on_hand", "safety_stock"],
            "customers": ["customer_code", "customer_type", "credit_limit", "payment_terms", "phone"],
        }

        entity_scores = {}
        for entity, sig_words in signatures.items():
            score = 0.0
            for col in normalized_cols:
                for sig in sig_words:
                    if sig == col:
                        score += 3.0
                    elif sig in col or col in sig:
                        score += 1.5
            entity_scores[entity] = score

        best_entity = max(entity_scores, key=entity_scores.get)
        confidence = min(0.99, max(0.50, round(entity_scores[best_entity] / 6.0, 2)))
        return best_entity, confidence

    # The function below is for mapping raw spreadsheet headers to standard system fields with confidence scoring
    @classmethod
    def map_columns(cls, columns: List[str], target_entity: Optional[str] = None, sheet_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Maps raw column headers to standardized system fields using optimal candidate ranking.
        Prevents ID columns from stealing numeric fields and handles currency suffixes.
        """
        if not target_entity:
            target_entity, entity_conf = cls.detect_entity(columns, sheet_name=sheet_name)
        else:
            entity_conf = 1.0

        field_definitions = STANDARD_FIELDS.get(target_entity, STANDARD_FIELDS["sales"])
        candidates = []

        for raw_col in columns:
            norm_col = cls.normalize_header(raw_col)
            stripped_col = cls.strip_currency_suffix(norm_col)
            is_id = cls.is_identifier_column(norm_col)

            for sys_field, aliases in field_definitions.items():
                if is_id and sys_field in NUMERIC_FIELDS:
                    continue

                score = 0.0
                if norm_col in aliases or stripped_col in aliases:
                    score = 0.99
                elif any(norm_col.startswith(a) or stripped_col.startswith(a) for a in aliases):
                    score = 0.92
                elif any(norm_col.endswith(a) or stripped_col.endswith(a) for a in aliases):
                    score = 0.88
                elif any(a in norm_col or a in stripped_col for a in aliases):
                    matching_alias = next(a for a in aliases if a in norm_col or a in stripped_col)
                    if len(matching_alias) >= 4:
                        score = 0.75

                if score >= 0.70:
                    candidates.append((score, raw_col, sys_field))

        candidates.sort(key=lambda x: x[0], reverse=True)

        mapped_fields = {}
        used_cols = set()
        used_fields = set()

        for score, raw_col, sys_field in candidates:
            if raw_col not in used_cols and sys_field not in used_fields:
                used_cols.add(raw_col)
                used_fields.add(sys_field)
                mapped_fields[raw_col] = {
                    "system_field": sys_field,
                    "confidence": round(score, 2),
                    "target_entity": target_entity,
                }

        unmapped_columns = [c for c in columns if c not in used_cols]
        ambiguities = []
        for raw_col in columns:
            norm_col = cls.normalize_header(raw_col)
            if norm_col in ["amount_paid", "paid", "amount_received", "payment_amount"]:
                if target_entity == "sales":
                    ambiguities.append({
                        "column": raw_col,
                        "question": f"What does '{raw_col}' represent?",
                        "options": ["revenue", "payment_amount", "expense"],
                        "suggested": "revenue",
                    })

        overall_confidence = (
            round(sum(m["confidence"] for m in mapped_fields.values()) / len(columns), 2)
            if columns
            else 0.0
        )

        return {
            "detected_entity": target_entity,
            "entity_confidence": entity_conf,
            "overall_confidence": overall_confidence,
            "mapped_count": len(mapped_fields),
            "total_columns": len(columns),
            "mappings": mapped_fields,
            "unmapped_columns": unmapped_columns,
            "ambiguities": ambiguities,
        }

    # The function below is for saving user-confirmed column mappings into the data_mappings database table
    @staticmethod
    def save_confirmed_mappings(data_source_id: str, mappings: Dict[str, Dict[str, Any]]) -> None:
        """Saves user-confirmed column mappings into data_mappings table."""
        with get_connection() as conn:
            for source_col, details in mappings.items():
                mapping_id = generate_uuid()
                conn.execute(
                    """
                    INSERT INTO data_mappings (id, data_source_id, source_column, target_entity, target_field, confidence_score, confirmed_by_user)
                    VALUES (?, ?, ?, ?, ?, ?, 1);
                    """,
                    (
                        mapping_id,
                        data_source_id,
                        source_col,
                        details.get("target_entity", "sales"),
                        details.get("system_field", source_col),
                        details.get("confidence", 1.0),
                    ),
                )

"""
Sample Business Data Generator for BusinessPilot.
Generates realistic multi-tab Excel files (e.g. ABC Supermarket Ltd)
and realistic messy CSVs to stress-test data ingestion, mapping, quality audits,
and deterministic analytics.
"""
import os
import random
import pandas as pd
from datetime import datetime, timedelta

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(DATA_DIR, "samples")


def generate_abc_supermarket_dataset() -> str:
    """Generates a complete multi-tab Excel file for 'ABC Supermarket Ltd'."""
    os.makedirs(SAMPLES_DIR, exist_ok=True)
    target_file = os.path.join(SAMPLES_DIR, "ABC_Supermarket_Ltd.xlsx")

    random.seed(42)

    # 1. Product Master Data
    categories = {
        "Beverages": [
            ("Coca-Cola 500ml", 1200, 800),
            ("Fanta Orange 500ml", 1200, 800),
            ("Sprite 500ml", 1200, 800),
            ("Kilimanjaro Drinking Water 1.5L", 1500, 950),
            ("Azam Mango Juice 1L", 2500, 1800),
            ("Chai Bora Tea Bags 50s", 3500, 2400),
            ("Africafe Pure Instant Coffee 100g", 6500, 4800),
        ],
        "Food & Groceries": [
            ("Azam Wheat Flour 2kg", 4500, 3400),
            ("Bakhresa Maize Flour Sembe 5kg", 9500, 7200),
            ("Super Basmati Rice 5kg", 18500, 14000),
            ("Korie Cooking Oil 3L", 19000, 15500),
            ("Nida Table Salt 1kg", 800, 500),
            ("White Sugar 1kg", 3200, 2600),
            ("Tomato Paste Can 400g", 2800, 1900),
        ],
        "Household & Cleaning": [
            ("Omo Washing Powder 1kg", 5500, 4000),
            ("Sunlight Dishwashing Liquid 750ml", 4200, 3000),
            ("Whitedent Toothpaste 140g", 2200, 1500),
            ("Dettol Antiseptic Soap 175g", 3000, 2100),
            ("Harpic Toilet Cleaner 750ml", 6800, 4900),
            ("Kleen Soft Toilet Paper 4pk", 4800, 3400),
        ],
        "Electronics & Utilities": [
            ("Energizer AA Batteries 4pk", 5500, 3800),
            ("Extension Socket 4-way", 14500, 9800),
            ("LED Light Bulb 12W", 4500, 2800),
        ]
    }

    products_list = []
    sku_counter = 1
    for cat, items in categories.items():
        for name, sell_price, cost_price in items:
            products_list.append({
                "SKU": f"PROD-{sku_counter:04d}",
                "Product Name": name,
                "Category": cat,
                "Selling Price": sell_price,
                "Cost Price": cost_price,
                "Stock on Hand": random.randint(5, 180),
                "Reorder Level": random.choice([15, 20, 30]),
                "Supplier": "Bakhresa Group" if "Azam" in name or "Flour" in name else "Dar Wholesalers Ltd",
            })
            sku_counter += 1

    df_products = pd.DataFrame(products_list)

    # 2. Customers
    customers_data = [
        {"Customer ID": "CUST-001", "Customer Name": "Safari Hotel Dar", "Customer Type": "Wholesale", "Phone": "+255712000001", "Credit Limit": 5000000, "Terms Days": 30},
        {"Customer ID": "CUST-002", "Customer Name": "Mlimani Restaurant", "Customer Type": "Business", "Phone": "+255712000002", "Credit Limit": 3000000, "Terms Days": 15},
        {"Customer ID": "CUST-003", "Customer Name": "Kariakoo Canteen Ltd", "Customer Type": "Wholesale", "Phone": "+255712000003", "Credit Limit": 4000000, "Terms Days": 30},
        {"Customer ID": "CUST-004", "Customer Name": "Kennedy M.", "Customer Type": "VIP", "Phone": "+255754111222", "Credit Limit": 500000, "Terms Days": 0},
        {"Customer ID": "CUST-005", "Customer Name": "Amina Said", "Customer Type": "Retail", "Phone": "+255784333444", "Credit Limit": 0, "Terms Days": 0},
        {"Customer ID": "CUST-006", "Customer Name": "John Msaki", "Customer Type": "Retail", "Phone": "+255765555666", "Credit Limit": 0, "Terms Days": 0},
        {"Customer ID": "CUST-007", "Customer Name": "Mary Muro", "Customer Type": "Retail", "Phone": "+255713777888", "Credit Limit": 0, "Terms Days": 0},
        {"Customer ID": "CUST-008", "Customer Name": "Zanzibar Spice Cafe", "Customer Type": "Business", "Phone": "+255777999000", "Credit Limit": 2000000, "Terms Days": 14},
    ]
    df_customers = pd.DataFrame(customers_data)

    # 3. Sales Transactions (Covering the last 90 days)
    sales_records = []
    base_date = datetime(2026, 9, 30)

    payment_methods = ["M-Pesa", "Cash", "Airtel Money", "Bank", "Tigo Pesa"]
    weights_methods = [0.45, 0.30, 0.12, 0.08, 0.05]

    inv_counter = 2001
    for day_offset in range(90, -1, -1):
        sale_date = (base_date - timedelta(days=day_offset)).strftime("%Y-%m-%d")
        num_sales_today = random.randint(2, 6)

        for _ in range(num_sales_today):
            cust = random.choice(customers_data)
            prod = random.choice(products_list)
            qty = random.randint(1, 15) if cust["Customer Type"] != "Wholesale" else random.randint(10, 50)
            
            unit_price = prod["Selling Price"]
            unit_cost = prod["Cost Price"]
            total = round(qty * unit_price, 2)
            cogs = round(qty * unit_cost, 2)
            profit = round(total - cogs, 2)
            
            pay_method = random.choices(payment_methods, weights_methods)[0]
            # Wholesale customers sometimes have partial or unpaid credit status
            if cust["Customer Type"] == "Wholesale" and random.random() < 0.25:
                pay_status = "Unpaid"
            elif random.random() < 0.08:
                pay_status = "Partial"
            else:
                pay_status = "Paid"

            sales_records.append({
                "Invoice Number": f"INV-{inv_counter}",
                "Sale Date": sale_date,
                "Customer Name": cust["Customer Name"],
                "Customer Type": cust["Customer Type"],
                "Product Name": prod["Product Name"],
                "Category": prod["Category"],
                "Quantity": qty,
                "Unit Price": unit_price,
                "Cost Price": unit_cost,
                "Total Amount": total,
                "COGS": cogs,
                "Profit": profit,
                "Payment Method": pay_method,
                "Payment Status": pay_status,
            })
            inv_counter += 1

    df_sales = pd.DataFrame(sales_records)

    # 4. Expenses Records
    expense_categories = [
        ("Rent", "Main Store Commercial Rent", "OPERATING", 4500000, "Mlimani Holdings"),
        ("Salaries", "Staff Monthly Payroll", "OPERATING", 7800000, "Employee Bank Transfer"),
        ("Transport", "Delivery & Logistics Fuel", "SELLING", 1850000, "TotalEnergies Fuel"),
        ("Electricity", "TANESCO Power Bill", "OPERATING", 1250000, "TANESCO Luku"),
        ("Internet", "Fiber Internet & POS Connection", "OPERATING", 350000, "Zantel Telecom"),
        ("Marketing", "Social Media Ads & Flyers", "SELLING", 850000, "Dar Digital Media"),
        ("Maintenance", "Refrigeration Repair & Servicing", "OPERATING", 450000, "CoolCare Technicians"),
        ("Office Supplies", "Thermal Receipt Rolls & Stationery", "ADMINISTRATIVE", 280000, "Kariakoo Stationers"),
    ]

    expense_records = []
    # Generate monthly recurring expenses for 3 months
    for month_dt in [datetime(2026, 7, 28), datetime(2026, 8, 28), datetime(2026, 9, 28)]:
        for cat_name, desc, cat_type, base_amount, vendor in expense_categories:
            variance = random.uniform(0.95, 1.15) if cat_name in ["Transport", "Electricity", "Marketing"] else 1.0
            amount = round(base_amount * variance, 2)
            expense_records.append({
                "Expense Date": month_dt.strftime("%Y-%m-%d"),
                "Category": cat_name,
                "Category Type": cat_type,
                "Description": desc,
                "Amount": amount,
                "Vendor": vendor,
                "Payment Method": "Bank" if amount > 1000000 else "M-Pesa",
                "Status": "Paid"
            })

    df_expenses = pd.DataFrame(expense_records)

    # Write multi-tab Excel
    with pd.ExcelWriter(target_file, engine="openpyxl") as writer:
        df_sales.to_excel(writer, sheet_name="Sales", index=False)
        df_expenses.to_excel(writer, sheet_name="Expenses", index=False)
        df_products.to_excel(writer, sheet_name="Inventory", index=False)
        df_customers.to_excel(writer, sheet_name="Customers", index=False)

    return target_file


def generate_messy_csv_dataset() -> str:
    """Generates a realistic messy CSV with currency symbols, bad dates, and duplicate rows."""
    os.makedirs(SAMPLES_DIR, exist_ok=True)
    target_file = os.path.join(SAMPLES_DIR, "Messy_Sales_2026.csv")

    rows = [
        {"Date": "2026-09-30", "Client": "Safari Hotel Dar", "Item": "Coca-Cola 500ml", "Qty Sold": 24, "Selling Price": "TZS 1,200", "Amount Paid": "28,800.00"},
        {"Date": "30/09/2026", "Client": "Safari Hotel Dar", "Item": "Coca-Cola 500ml", "Qty Sold": 24, "Selling Price": "1,200", "Amount Paid": "28,800.00"}, # duplicate
        {"Date": "29-09-2026", "Client": "Kennedy M.", "Item": "Azam Wheat Flour 2kg", "Qty Sold": 2, "Selling Price": "4,500.00", "Amount Paid": "9,000"},
        {"Date": "28/09/2026", "Client": "Mlimani Restaurant", "Item": "Korie Cooking Oil 3L", "Qty Sold": 6, "Selling Price": "TZS 19,000", "Amount Paid": "114,000"},
        {"Date": "invalid-date", "Client": "Unknown Walkin", "Item": "LED Light Bulb 12W", "Qty Sold": 1, "Selling Price": "4500", "Amount Paid": "4500"}, # invalid date
        {"Date": "2026-09-27", "Client": "Amina Said", "Item": "", "Qty Sold": 3, "Selling Price": "1200", "Amount Paid": "3600"}, # missing product
        {"Date": "2026-09-26", "Client": "Zanzibar Spice Cafe", "Item": "Super Basmati Rice 5kg", "Qty Sold": -5, "Selling Price": "18,500", "Amount Paid": "92,500"}, # negative qty
        {"Date": "25/09/2026", "Client": "John Msaki", "Item": "Omo Washing Powder 1kg", "Qty Sold": 1, "Selling Price": "5,500", "Amount Paid": "5,500"},
        {"Date": "2026-09-24", "Client": "Mary Muro", "Item": "Dettol Antiseptic Soap 175g", "Qty Sold": 4, "Selling Price": "3000", "Amount Paid": "12000"},
    ]

    df = pd.DataFrame(rows)
    df.to_csv(target_file, index=False)
    return target_file


if __name__ == "__main__":
    excel_path = generate_abc_supermarket_dataset()
    csv_path = generate_messy_csv_dataset()
    print(f"Generated sample datasets successfully:\n1. {excel_path}\n2. {csv_path}")

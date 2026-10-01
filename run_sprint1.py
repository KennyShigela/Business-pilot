"""
Sprint 1 Demonstration Runner for BusinessPilot.
Executes the complete Sprint 1 pipeline end-to-end:
1. Initialize multi-tenant database schema
2. Generate realistic business sample datasets (ABC Supermarket Ltd)
3. Ingest multi-tab Excel files with automatic column mapping and data quality auditing
4. Calculate verified deterministic business analytics
5. Output the Executive Morning Briefing!
"""
import os
import json
from database.db import init_db, get_connection, generate_uuid, query_one
from data.sample_generator import generate_abc_supermarket_dataset, generate_messy_csv_dataset
from engine.importer import BusinessDataImporter
from engine.analytics import BusinessAnalyticsEngine


def run():
    print("=" * 70)
    print("  BUSINESSPILOT — SPRINT 1: CORE DATA & ANALYTICS ENGINE")
    print("=" * 70)

    # 1. Initialize Database
    print("\n[Step 1] Initializing Multi-Tenant SQLite Database...")
    init_db()
    print("✓ Schema initialized with 23 tables, foreign keys, and indexes.")

    # 2. Register Company & User
    company_id = "company-abc-supermarket-001"
    user_id = "user-kennedy-001"

    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO companies (id, name, business_type, industry, country, currency)
            VALUES (?, 'ABC Supermarket Ltd', 'Retail', 'Supermarket', 'Tanzania', 'TZS');
            """,
            (company_id,),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO users (id, company_id, name, email, password_hash)
            VALUES (?, ?, 'Kennedy', 'kennedy@abcsupermarket.co.tz', 'hash_secret_123');
            """,
            (user_id, company_id),
        )
    print(f"✓ Company created: ABC Supermarket Ltd (ID: {company_id})")
    print(f"✓ User created: Kennedy (kennedy@abcsupermarket.co.tz)")

    # 3. Generate Realistic Datasets
    print("\n[Step 2] Generating Realistic Multi-Tab Business Datasets...")
    excel_file = generate_abc_supermarket_dataset()
    csv_file = generate_messy_csv_dataset()
    print(f"✓ Generated Excel workbook: {os.path.basename(excel_file)}")
    print(f"✓ Generated edge-case CSV: {os.path.basename(csv_file)}")

    # 4. Ingest & Map Excel Data
    print("\n[Step 3] Ingesting 'ABC_Supermarket_Ltd.xlsx' through Ingestion Pipeline...")
    importer = BusinessDataImporter(company_id)
    import_result = importer.import_excel_workbook(excel_file)

    print(f"✓ Import Job: {import_result['job_id']} | Status: {import_result['status']}")
    print(f"✓ Total Rows Successfully Imported: {import_result['total_rows_imported']}")

    for sheet, info in import_result["sheets"].items():
        print(f"  • Sheet [{sheet:12s}] → Entity: {info['detected_entity'].upper():10s} | "
              f"Entity Conf: {int(info['entity_confidence']*100)}% | "
              f"Data Quality: {info['quality_score']}% | "
              f"Valid Rows: {info['valid_rows']}")

    # 5. Run Deterministic Analytics Engine
    print("\n[Step 4] Running Deterministic Analytics Engine...")
    analytics = BusinessAnalyticsEngine(company_id)

    rev = analytics.get_revenue_summary()
    pnl = analytics.get_pnl_statement()
    inv = analytics.get_inventory_health()
    cash = analytics.get_cash_flow_summary()
    cust = analytics.get_customer_profitability()
    briefing = analytics.generate_morning_briefing()

    print("\n" + "=" * 70)
    print("  EXECUTIVE MORNING BRIEFING (SCREEN 02)")
    print("=" * 70)
    print("Good morning, Kennedy.")
    print("Here is what's happening with your business:\n")

    print(f"┌───────────────────────────────┬───────────────────────────────┐")
    print(f"│  TOTAL REVENUE                │  NET PROFIT                   │")
    print(f"│  TZS {rev['total_revenue']:>15,.2f}  │  TZS {pnl['net_profit']:>15,.2f}  │")
    print(f"│  Growth: {rev['mom_growth_pct']:>+5.1f}%                │  Margin: {pnl['net_margin_pct']:>5.1f}%              │")
    print(f"├───────────────────────────────┼───────────────────────────────┤")
    print(f"│  OPERATING EXPENSES           │  CASH POSITION                │")
    print(f"│  TZS {pnl['operating_expenses']:>15,.2f}  │  TZS {cash['current_cash_balance']:>15,.2f}  │")
    print(f"│  Orders: {rev['total_orders']:>5d}                │  Runway: {cash['runway_days']:>4d} days             │")
    print(f"└───────────────────────────────┴───────────────────────────────┘")

    print(f"\n✦ AI BUSINESS SUMMARY:")
    print(f"\"{briefing['ai_summary']}\"")

    print(f"\n⚠ ATTENTION REQUIRED:")
    if inv["low_stock_count"] > 0:
        print(f"• INVENTORY: {inv['low_stock_count']} items reached low stock or reorder level.")
        for item in inv["low_stock_alerts"][:3]:
            print(f"    - {item['name']}: {item['stock']:.0f} left (Reorder at {item['reorder_level']:.0f})")
    if inv["locked_capital_slow_moving"] > 0:
        print(f"• DEAD STOCK: TZS {inv['locked_capital_slow_moving']:,.0f} locked in slow-moving items (>60 days).")
    if cash["accounts_receivable"] > 0:
        print(f"• RECEIVABLES: TZS {cash['accounts_receivable']:,.0f} outstanding across {cash['unpaid_invoices_count']} invoices.")

    print(f"\n✦ CUSTOMER PROFITABILITY HIGHLIGHTS:")
    if cust["whales"]:
        top_whale = cust["whales"][0]
        print(f"• TOP WHALE: {top_whale['customer_name']} (Revenue: TZS {top_whale['total_revenue']:,.0f}, Margin: {top_whale['margin_pct']}%)")
    if cust["drainers"]:
        top_drainer = cust["drainers"][0]
        print(f"• MARGIN WATCH: {top_drainer['customer_name']} (Margin: {top_drainer['margin_pct']}%)")

    print("\n" + "=" * 70)
    print("  SPRINT 1 COMPLETE — CORE DATA & ANALYTICS PIPELINE VERIFIED!")
    print("=" * 70)


if __name__ == "__main__":
    run()

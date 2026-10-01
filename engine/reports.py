"""
Automated Management Report Generator for BusinessPilot.
Generates comprehensive executive board packs in high-resolution PDF format (via ReportLab)
and clean HTML print-ready reports.
"""
import os
import io
from datetime import datetime
from typing import Dict, Any, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from database.db import query_one
from engine.analytics import BusinessAnalyticsEngine
from engine.forecasting import ForecastingEngine
from engine.alerts_engine import EarlyWarningAlertEngine


class ManagementReportGenerator:
    """Produces executive PDF board packs and HTML management briefings."""

    def __init__(self, company_id: str):
        self.company_id = company_id
        self.analytics = BusinessAnalyticsEngine(company_id)
        self.forecasting = ForecastingEngine(company_id)
        self.alerts_engine = EarlyWarningAlertEngine(company_id)

    def generate_pdf_report(self) -> bytes:
        """Builds a formatted multi-page executive PDF report and returns raw bytes."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        company = query_one("SELECT * FROM companies WHERE id = ?;", (self.company_id,)) or {
            "name": "ABC Supermarket Ltd",
            "currency": "TZS",
            "industry": "Retail",
        }

        rev = self.analytics.get_revenue_summary()
        pnl = self.analytics.get_pnl_statement()
        inv = self.analytics.get_inventory_health()
        cash = self.analytics.get_cash_flow_summary()
        cust = self.analytics.get_customer_profitability()
        briefing = self.analytics.generate_morning_briefing()
        active_alerts = self.alerts_engine.evaluate_and_refresh_alerts()

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#0f172a"),
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#64748b"),
        )
        h2_style = ParagraphStyle(
            "SectionH2",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=12,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "DocBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#334155"),
        )
        card_label_style = ParagraphStyle(
            "CardLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#64748b"),
        )
        card_val_style = ParagraphStyle(
            "CardVal",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=16,
            textColor=colors.HexColor("#0f172a"),
        )

        elements = []

        # --- Header ---
        elements.append(Paragraph(f"<b>BUSINESS PILOT EXECUTIVE REPORT</b>", ParagraphStyle("Brand", fontName="Helvetica-Bold", fontSize=9, textColor=colors.HexColor("#2563eb"))))
        elements.append(Paragraph(company.get("name", "Business Operating Report"), title_style))
        report_date = datetime.now().strftime("%B %d, %Y")
        elements.append(Paragraph(f"Monthly Management & Financial Intelligence Briefing · Generated on {report_date}", subtitle_style))
        elements.append(Spacer(1, 12))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0"), spaceAfter=14))

        # --- Executive Summary Box ---
        elements.append(Paragraph("1. Executive Summary & Health Scorecard", h2_style))
        elements.append(Paragraph(f"<b>AI Synthesis:</b> {briefing['ai_summary']}", body_style))
        elements.append(Spacer(1, 8))

        # 4 Metric Cards Table
        kpi_table_data = [
            [
                Paragraph("TOTAL REVENUE", card_label_style),
                Paragraph("NET PROFIT (EBITDA)", card_label_style),
                Paragraph("OPERATING EXPENSES", card_label_style),
                Paragraph("CASH POSITION", card_label_style),
            ],
            [
                Paragraph(f"TZS {rev['total_revenue']:,.0f}", card_val_style),
                Paragraph(f"TZS {pnl['net_profit']:,.0f}", card_val_style),
                Paragraph(f"TZS {pnl['operating_expenses']:,.0f}", card_val_style),
                Paragraph(f"TZS {cash['current_cash_balance']:,.0f}", card_val_style),
            ],
            [
                Paragraph(f"Growth: {rev['mom_growth_pct']:+.1f}% MoM", body_style),
                Paragraph(f"Margin: {pnl['net_margin_pct']:.1f}%", body_style),
                Paragraph(f"Orders: {rev['total_orders']:,}", body_style),
                Paragraph(f"Runway: {cash['runway_days']} days", body_style),
            ],
        ]
        kpi_table = Table(kpi_table_data, colWidths=[130, 130, 130, 130])
        kpi_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.append(kpi_table)
        elements.append(Spacer(1, 14))

        # --- Section 2: P&L Statement Bridge ---
        elements.append(Paragraph("2. Financial Performance & P&L Statement", h2_style))
        pnl_data = [
            ["Financial Line Item", "Amount (TZS)", "% of Revenue", "Notes"],
            ["Gross Sales Revenue", f"{pnl['revenue']:,.0f}", "100.0%", "Total verified transaction sales"],
            ["Cost of Goods Sold (COGS)", f"{pnl['cogs']:,.0f}", f"{(pnl['cogs']/max(1.0, pnl['revenue'])*100):.1f}%", "Direct inventory cost"],
            ["Gross Profit", f"{pnl['gross_profit']:,.0f}", f"{pnl['gross_margin_pct']:.1f}%", "Product margin contribution"],
            ["Operating Expenses (OPEX)", f"{pnl['operating_expenses']:,.0f}", f"{(pnl['operating_expenses']/max(1.0, pnl['revenue'])*100):.1f}%", "Rent, Payroll, Power, Logistics"],
            ["Net Profit (EBITDA)", f"{pnl['net_profit']:,.0f}", f"{pnl['net_margin_pct']:.1f}%", "Bottom-line operating return"],
        ]
        pnl_tbl = Table(pnl_data, colWidths=[180, 110, 80, 150])
        pnl_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
            ("FONTNAME", (0, 5), (-1, 5), "Helvetica-Bold"),
        ]))
        elements.append(pnl_tbl)
        elements.append(Spacer(1, 14))

        # --- Section 3: Critical Risks & Early Warnings ---
        elements.append(Paragraph("3. Early Warning Risk Matrix", h2_style))
        alert_rows = [["Severity", "Risk Category", "Trigger & Recommendation"]]
        for alt in active_alerts[:4]:
            alert_rows.append([
                alt["severity"],
                alt["title"],
                alt["message"]
            ])

        if len(alert_rows) > 1:
            alt_tbl = Table(alert_rows, colWidths=[70, 140, 310])
            alt_tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ]))
            elements.append(alt_tbl)
        else:
            elements.append(Paragraph("No critical risks active. All systems within normal operating thresholds.", body_style))
        elements.append(Spacer(1, 14))

        # --- Section 4: Operational Recommendations ---
        elements.append(Paragraph("4. Recommended Tactical Action Plan", h2_style))
        recs = [
            "1. <b>Cash Buffer Restoration:</b> Enforce strict Net-15 collection on outstanding wholesale customer invoices.",
            "2. <b>Inventory Reorder:</b> Immediately initiate purchase orders for low-stock SKUs approaching stockout thresholds.",
            "3. <b>Dead Stock Liquidation:</b> Discount or bundle slow-moving inventory to recover trapped working capital.",
            "4. <b>OPEX Optimization:</b> Audit logistics and transportation expenses to protect contribution margin.",
        ]
        for r in recs:
            elements.append(Paragraph(r, body_style))
            elements.append(Spacer(1, 3))

        doc.build(elements)
        return buffer.getvalue()

    def generate_html_report(self) -> str:
        """Builds print-ready HTML management briefing."""
        company = query_one("SELECT * FROM companies WHERE id = ?;", (self.company_id,)) or {
            "name": "ABC Supermarket Ltd",
            "currency": "TZS",
        }
        rev = self.analytics.get_revenue_summary()
        pnl = self.analytics.get_pnl_statement()
        cash = self.analytics.get_cash_flow_summary()
        briefing = self.analytics.generate_morning_briefing()

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <title>Executive Briefing - {company['name']}</title>
          <style>
            body {{ font-family: -apple-system, system-ui, sans-serif; padding: 40px; color: #0f172a; line-height: 1.5; }}
            .header {{ border-bottom: 2px solid #e2e8f0; padding-bottom: 16px; margin-bottom: 24px; }}
            .title {{ font-size: 26px; font-weight: 700; margin: 0; }}
            .sub {{ color: #64748b; font-size: 14px; margin-top: 4px; }}
            .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
            .card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; }}
            .card .lbl {{ font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase; }}
            .card .val {{ font-size: 20px; font-weight: 700; margin-top: 4px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
            th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #e2e8f0; font-size: 14px; }}
            th {{ background: #f1f5f9; font-weight: 600; }}
          </style>
        </head>
        <body>
          <div class="header">
            <h1 class="title">{company['name']} — Management Board Pack</h1>
            <div class="sub">Generated on {datetime.now().strftime("%B %d, %Y")} · Confidential Management Briefing</div>
          </div>
          <div style="background:#edf2f7; padding:16px; border-radius:8px; margin-bottom:24px;">
            <strong>AI Business Summary:</strong> {briefing['ai_summary']}
          </div>
          <div class="grid">
            <div class="card">
              <div class="lbl">Revenue</div>
              <div class="val">TZS {rev['total_revenue']:,.0f}</div>
              <div style="font-size:12px; color:#10b981;">{rev['mom_growth_pct']:+.1f}% MoM</div>
            </div>
            <div class="card">
              <div class="lbl">Net Profit</div>
              <div class="val">TZS {pnl['net_profit']:,.0f}</div>
              <div style="font-size:12px;">Margin: {pnl['net_margin_pct']:.1f}%</div>
            </div>
            <div class="card">
              <div class="lbl">Expenses</div>
              <div class="val">TZS {pnl['operating_expenses']:,.0f}</div>
              <div style="font-size:12px;">Orders: {rev['total_orders']:,}</div>
            </div>
            <div class="card">
              <div class="lbl">Cash Position</div>
              <div class="val">TZS {cash['current_cash_balance']:,.0f}</div>
              <div style="font-size:12px; color:#ef4444;">Runway: {cash['runway_days']} days</div>
            </div>
          </div>
        </body>
        </html>
        """

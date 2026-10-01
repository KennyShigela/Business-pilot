# Business Pilot — Business Operating System & Executive AI Analyst

> **Automated business intelligence, deterministic financial modeling, and grounded AI strategy from your spreadsheets.**

Business Pilot turns raw business spreadsheets (Excel, Google Sheets, CSV) containing sales, expenses, inventory, and customer records into real-time executive dashboards, cash flow forecasts, automated management briefings, and grounded AI insights.

---

## 🌟 Key Capabilities

### 1. Universal Ingestion & Self-Healing Pipeline
- **Zero-Config Import**: Drag-and-drop `.xlsx`, `.xls`, `.csv` files or paste a public Google Sheets share link.
- **Automated Entity Classification**: Automatically categorizes sheets and columns into Sales, Operating Expenses, Inventory Stock, and Customer Accounts.
- **Fuzzy Header Normalization**: Matches varied column naming conventions (`Selling Price` $\rightarrow$ `unit_price`, `Client` $\rightarrow$ `customer_name`, `Qty Sold` $\rightarrow$ `quantity`).
- **Data Quality Gatekeeper**: Detects anomalies, cleans multi-currency formats, standardizes dates, flags duplicate transactions, and computes a **Data Trustworthiness Score**.

### 2. Executive Financial Analytics & P&L
- **Revenue & Gross Profitability**: Tracks sales velocity, COGS, gross margin %, average order value (AOV), and month-over-month growth.
- **Dynamic P&L Financial Margin Bridge**: Waterfall visualization from Gross Revenue down to Operating Overhead (OPEX) and Net Profit.
- **Expense Intelligence**: Automatic categorization across Payroll, Rent, Marketing, Logistics, Utilities, and Administrative costs.

### 3. Cash Flow Runway & Predictive Forecasting
- **Direct Cash Flow & Runway Countdown**: Computes current liquidity, monthly cash burn rate, and operating runway days.
- **Accounts Receivable (AR) Aging**: Monitors unpaid customer invoices to accelerate collections and prevent liquidity crunches.
- **Time-Series Revenue Forecasting**: Damped exponential smoothing with 80% upper and lower confidence interval bands.

### 4. Inventory Health & Stockout Prevention
- **SKU Reorder Matrix**: Proactively flags items reaching safety stock thresholds before stockouts impact revenue.
- **Dead Stock Liquidation**: Identifies trapped capital in stagnant SKUs with zero sales in over 60 days.

### 5. Grounded AI Business Analyst (Powered by Google Gemini 1.5 Flash)
- **Zero Hallucinations**: Combines Google Gemini 1.5 Flash generative reasoning with **deterministic financial tool grounding**. All numerical assertions are cited directly from verified ledger calculations.
- **Executive Answers**: Delivers 3-part root cause drivers and tactical recommendations for complex strategic questions ("Why did margins drop?", "How can we extend runway by 30 days?").
- **Offline / Zero-Key Fallback**: Runs with complete functionality offline using the built-in deterministic calculation engine.

### 6. Industry-Tailored Workspaces
- **Retail & Supermarket Suite**: Point of Sale (POS) register logging, fast-moving SKU velocity, daily basket metrics, and shelf stockout warnings.
- **Wholesale & Distribution Suite**: B2B bulk invoicing, 30/60/90-day credit accounts, and pallet batch logistics.
- **Professional Services & Agency Suite**: Client retainer billing, project milestone invoicing, and consultant overhead burn.
- **Standard Business Suite**: General multi-currency executive P&L and financial management.

### 7. Automated Management Reports
- **Executive Board Pack PDF**: One-click professional multi-page board deck generated dynamically via ReportLab.
- **Instant HTML Morning Briefings**: Condensed executive summary formatted for instant C-suite review.

---

## 🛠️ Architecture & Tech Stack

| Layer | Technology |
| :--- | :--- |
| **Frontend** | Vanilla Modern JavaScript (ES6+), CSS3 Variables, Glassmorphism, IntersectionObserver figure animations |
| **Data Visualization** | Apache ECharts (Curved glowing bezier curves, multi-stop gradients, donut arcs) |
| **Backend & APIs** | Python 3.12 (Standard Library HTTP / Serverless compatible), SQLite with WAL mode & foreign keys |
| **Data Processing** | Pandas, NumPy, OpenPyXL |
| **Report Generation** | ReportLab PDF Engine |
| **AI Intelligence** | Google Gemini 1.5 Flash API + Grounded Financial Tool Registry |
| **Deployment** | Vercel (Serverless Functions + Static Asset Edge CDN) |

---

## 🚀 Quick Start (Local Development)

### Prerequisites
- Python 3.10+
- Node.js (optional, for Vercel CLI)

### 1. Clone & Setup
```bash
git clone https://github.com/YOUR_USERNAME/business-pilot.git
cd business-pilot
pip install -r requirements.txt
```

### 2. Start the Application
```bash
python3 backend/api_server.py 8080
```
Open your browser to: **`http://localhost:8080`**

---

## ☁️ Deployment to Vercel

Business Pilot is pre-configured with `vercel.json` and a serverless entrypoint in `api/index.py`:

```bash
# Deploy with Vercel CLI
npx vercel

# Deploy to production
npx vercel --prod
```

Or connect the GitHub repository directly in your **Vercel Dashboard** for automated CI/CD deployments.

---

## 📄 License
MIT License. Open-source for business owners, developers, and operators.

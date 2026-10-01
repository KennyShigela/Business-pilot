-- Multi-Tenant Business Operating System Database Schema
-- Compatible with PostgreSQL and SQLite

CREATE TABLE IF NOT EXISTS companies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    business_type TEXT,
    industry TEXT,
    email TEXT,
    phone TEXT,
    country TEXT DEFAULT 'Tanzania',
    currency TEXT DEFAULT 'TZS',
    timezone TEXT DEFAULT 'Africa/Dar_es_Salaam',
    logo_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS roles (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role_id TEXT REFERENCES roles(id) ON DELETE SET NULL,
    is_active INTEGER DEFAULT 1,
    last_login_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    customer_code TEXT,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    address TEXT,
    customer_type TEXT DEFAULT 'Retail', -- Individual, Business, Wholesale, Retail, VIP
    credit_limit REAL DEFAULT 0.0,
    payment_terms INTEGER DEFAULT 0, -- days
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS suppliers (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    supplier_code TEXT,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    address TEXT,
    payment_terms INTEGER DEFAULT 30, -- days
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS product_categories (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    sku TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    category_id TEXT REFERENCES product_categories(id) ON DELETE SET NULL,
    unit TEXT DEFAULT 'pcs',
    selling_price REAL NOT NULL DEFAULT 0.0,
    cost_price REAL NOT NULL DEFAULT 0.0,
    tax_rate REAL DEFAULT 0.18, -- 18% VAT standard
    reorder_level REAL DEFAULT 10.0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (company_id, sku)
);

CREATE TABLE IF NOT EXISTS inventory_locations (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Event-Sourced Inventory Movement Ledger (Reconstructable stock at any point in time)
CREATE TABLE IF NOT EXISTS inventory_movements (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    location_id TEXT REFERENCES inventory_locations(id) ON DELETE SET NULL,
    movement_type TEXT NOT NULL, -- PURCHASE, SALE, RETURN, ADJUSTMENT, TRANSFER_IN, TRANSFER_OUT, DAMAGE
    quantity REAL NOT NULL,      -- Positive for stock additions, negative for deductions
    unit_cost REAL NOT NULL DEFAULT 0.0,
    reference_type TEXT,         -- SALE, PURCHASE_ORDER, AUDIT
    reference_id TEXT,
    movement_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sales (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    customer_id TEXT REFERENCES customers(id) ON DELETE SET NULL,
    invoice_number TEXT NOT NULL,
    sale_date TIMESTAMP NOT NULL,
    subtotal REAL NOT NULL DEFAULT 0.0,
    discount REAL DEFAULT 0.0,
    tax REAL DEFAULT 0.0,
    total REAL NOT NULL DEFAULT 0.0,
    cost_of_goods REAL NOT NULL DEFAULT 0.0,
    profit REAL NOT NULL DEFAULT 0.0,
    payment_status TEXT DEFAULT 'Unpaid', -- Paid, Partial, Unpaid
    status TEXT DEFAULT 'Completed',     -- Completed, Cancelled, Draft
    created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (company_id, invoice_number)
);

CREATE TABLE IF NOT EXISTS sale_items (
    id TEXT PRIMARY KEY,
    sale_id TEXT NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity REAL NOT NULL,
    unit_price REAL NOT NULL,
    discount REAL DEFAULT 0.0,
    tax REAL DEFAULT 0.0,
    total REAL NOT NULL,
    cost_price REAL NOT NULL DEFAULT 0.0,
    profit REAL NOT NULL DEFAULT 0.0
);

-- Decoupled Payments (enables AR aging, installment & mobile money tracking)
CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    sale_id TEXT REFERENCES sales(id) ON DELETE SET NULL,
    customer_id TEXT REFERENCES customers(id) ON DELETE SET NULL,
    amount REAL NOT NULL,
    payment_method TEXT NOT NULL, -- Cash, Bank, M-Pesa, Airtel Money, Tigo Pesa, Card, Other
    payment_date TIMESTAMP NOT NULL,
    reference_number TEXT,
    status TEXT DEFAULT 'Completed', -- Completed, Pending, Failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS expense_categories (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type TEXT NOT NULL, -- OPERATING, ADMINISTRATIVE, SELLING, FINANCIAL, OTHER
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS expenses (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    category_id TEXT REFERENCES expense_categories(id) ON DELETE SET NULL,
    supplier_id TEXT REFERENCES suppliers(id) ON DELETE SET NULL,
    description TEXT,
    amount REAL NOT NULL,
    tax REAL DEFAULT 0.0,
    payment_method TEXT DEFAULT 'Bank',
    expense_date DATE NOT NULL,
    status TEXT DEFAULT 'Paid', -- Paid, Pending
    created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Staging & Data Ingestion Pipeline (Protects core tables from messy spreadsheet corruption)
CREATE TABLE IF NOT EXISTS data_sources (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL, -- EXCEL, CSV, GOOGLE_SHEETS, API, MANUAL
    name TEXT NOT NULL,
    file_url TEXT,
    external_id TEXT,
    status TEXT DEFAULT 'Active',
    last_synced_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS import_jobs (
    id TEXT PRIMARY KEY,
    data_source_id TEXT NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'PENDING', -- PENDING, PROCESSING, COMPLETED, FAILED
    rows_processed INTEGER DEFAULT 0,
    rows_successful INTEGER DEFAULT 0,
    rows_failed INTEGER DEFAULT 0,
    error_log TEXT, -- JSON array of error objects
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw_import_rows (
    id TEXT PRIMARY KEY,
    import_job_id TEXT NOT NULL REFERENCES import_jobs(id) ON DELETE CASCADE,
    row_number INTEGER NOT NULL,
    raw_data TEXT NOT NULL, -- JSON string of row key-values
    validation_status TEXT DEFAULT 'VALID', -- VALID, INVALID, WARNING
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS data_mappings (
    id TEXT PRIMARY KEY,
    data_source_id TEXT NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    source_column TEXT NOT NULL,
    target_entity TEXT NOT NULL, -- sales, customers, products, expenses
    target_field TEXT NOT NULL,  -- e.g. customer_name, quantity, unit_price
    confidence_score REAL NOT NULL,
    confirmed_by_user INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Analytics & Intelligence Tables
CREATE TABLE IF NOT EXISTS kpis (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    description TEXT,
    formula TEXT,
    target_value REAL,
    unit TEXT DEFAULT 'TZS',
    frequency TEXT DEFAULT 'Monthly',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (company_id, code)
);

CREATE TABLE IF NOT EXISTS kpi_values (
    id TEXT PRIMARY KEY,
    kpi_id TEXT NOT NULL REFERENCES kpis(id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    actual_value REAL NOT NULL,
    target_value REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS forecasts (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    forecast_type TEXT NOT NULL, -- SALES, REVENUE, CASH_FLOW, DEMAND, INVENTORY, EXPENSE
    metric TEXT NOT NULL,
    model_name TEXT NOT NULL,    -- HOLT_WINTERS, MOVING_AVERAGE, LINEAR_TREND
    forecast_date DATE NOT NULL,
    predicted_value REAL NOT NULL,
    lower_bound REAL,
    upper_bound REAL,
    confidence_score REAL DEFAULT 0.85,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    alert_type TEXT NOT NULL, -- CASH_FLOW, INVENTORY, EXPENSE, CUSTOMER, MARGIN
    severity TEXT NOT NULL,   -- CRITICAL, WARNING, ATTENTION, INFO
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    metric TEXT,
    threshold_value REAL,
    actual_value REAL,
    status TEXT DEFAULT 'ACTIVE', -- ACTIVE, ACKNOWLEDGED, RESOLVED
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_insights (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    insight_type TEXT NOT NULL, -- PROFIT_ANALYSIS, REVENUE_TREND, INVENTORY_RISK, CASH_FLOW
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    severity TEXT DEFAULT 'INFO',
    data_period_start DATE,
    data_period_end DATE,
    model TEXT DEFAULT 'deterministic-rules',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_conversations (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES ai_conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL, -- USER, ASSISTANT, SYSTEM
    content TEXT NOT NULL,
    tool_calls TEXT,    -- JSON string of tools used
    citations TEXT,     -- JSON string of data verified
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    old_values TEXT, -- JSON string
    new_values TEXT, -- JSON string
    ip_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for high-performance multi-tenant querying
CREATE INDEX IF NOT EXISTS idx_sales_company_date ON sales(company_id, sale_date);
CREATE INDEX IF NOT EXISTS idx_sale_items_sale ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_product ON sale_items(product_id);
CREATE INDEX IF NOT EXISTS idx_inventory_movements_comp_prod ON inventory_movements(company_id, product_id);
CREATE INDEX IF NOT EXISTS idx_expenses_comp_date ON expenses(company_id, expense_date);
CREATE INDEX IF NOT EXISTS idx_payments_comp_date ON payments(company_id, payment_date);
CREATE INDEX IF NOT EXISTS idx_alerts_comp_status ON alerts(company_id, status);

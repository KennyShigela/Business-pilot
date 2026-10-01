"""
Data models and typed definitions for BusinessPilot.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class Company:
    id: str
    name: str
    business_type: str = "Retail"
    industry: str = "Supermarket"
    country: str = "Tanzania"
    currency: str = "TZS"
    timezone: str = "Africa/Dar_es_Salaam"
    email: Optional[str] = None
    phone: Optional[str] = None
    logo_url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Customer:
    id: str
    company_id: str
    name: str
    customer_code: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    customer_type: str = "Retail" # Individual, Business, Wholesale, Retail, VIP
    credit_limit: float = 0.0
    payment_terms: int = 0 # days
    created_at: Optional[str] = None


@dataclass
class Product:
    id: str
    company_id: str
    sku: str
    name: str
    selling_price: float
    cost_price: float
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    unit: str = "pcs"
    tax_rate: float = 0.18
    reorder_level: float = 10.0
    is_active: bool = True
    created_at: Optional[str] = None


@dataclass
class InventoryMovement:
    id: str
    company_id: str
    product_id: str
    movement_type: str # PURCHASE, SALE, RETURN, ADJUSTMENT, TRANSFER_IN, TRANSFER_OUT, DAMAGE
    quantity: float
    unit_cost: float
    location_id: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    movement_date: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class SaleItem:
    id: str
    sale_id: str
    product_id: str
    quantity: float
    unit_price: float
    discount: float = 0.0
    tax: float = 0.0
    total: float = 0.0
    cost_price: float = 0.0
    profit: float = 0.0


@dataclass
class Sale:
    id: str
    company_id: str
    invoice_number: str
    sale_date: str
    subtotal: float
    discount: float = 0.0
    tax: float = 0.0
    total: float = 0.0
    cost_of_goods: float = 0.0
    profit: float = 0.0
    payment_status: str = "Unpaid" # Paid, Partial, Unpaid
    status: str = "Completed"
    customer_id: Optional[str] = None
    created_by: Optional[str] = None
    items: List[SaleItem] = field(default_factory=list)


@dataclass
class Payment:
    id: str
    company_id: str
    amount: float
    payment_method: str # Cash, Bank, M-Pesa, Airtel Money, Tigo Pesa, Card, Other
    payment_date: str
    sale_id: Optional[str] = None
    customer_id: Optional[str] = None
    reference_number: Optional[str] = None
    status: str = "Completed"


@dataclass
class Expense:
    id: str
    company_id: str
    amount: float
    expense_date: str
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    supplier_id: Optional[str] = None
    description: Optional[str] = None
    tax: float = 0.0
    payment_method: str = "Bank"
    status: str = "Paid"


@dataclass
class Alert:
    id: str
    company_id: str
    alert_type: str # CASH_FLOW, INVENTORY, EXPENSE, CUSTOMER, MARGIN
    severity: str   # CRITICAL, WARNING, ATTENTION, INFO
    title: str
    message: str
    metric: Optional[str] = None
    threshold_value: Optional[float] = None
    actual_value: Optional[float] = None
    status: str = "ACTIVE"
    created_at: Optional[str] = None

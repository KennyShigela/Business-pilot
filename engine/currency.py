"""
Currency Detection & Foreign Exchange (FX) Conversion Engine for BusinessPilot.
Provides:
1. Automatic detection of currency from uploaded spreadsheet column headers, cell formats, and values.
2. Robust multi-currency conversion table supporting African and global trade currencies (TZS, USD, KES, UGX, RWF, EUR, GBP, ZAR, NGN, etc.).
3. Real-time conversion calculation between spreadsheet currency and company's registered base currency.
"""
import re
import os
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple

# Base reference exchange rates against USD (1 USD = X Currency units)
# Updated realistic benchmark rates
EXCHANGE_RATES_TO_USD: Dict[str, float] = {
    "USD": 1.0,           # US Dollar
    "TZS": 2600.0,        # Tanzanian Shilling (~2,600 TZS per 1 USD)
    "KES": 130.0,         # Kenyan Shilling (~130 KES per 1 USD)
    "UGX": 3720.0,        # Ugandan Shilling (~3,720 UGX per 1 USD)
    "RWF": 1350.0,        # Rwandan Franc (~1,350 RWF per 1 USD)
    "BIF": 2900.0,        # Burundian Franc (~2,900 BIF per 1 USD)
    "EUR": 0.92,          # Euro (1 EUR ≈ 1.087 USD => ~2,826 TZS)
    "GBP": 0.78,          # British Pound (1 GBP ≈ 1.282 USD => ~3,333 TZS)
    "ZAR": 18.0,          # South African Rand
    "NGN": 1650.0,        # Nigerian Naira
    "GHS": 15.5,          # Ghanaian Cedi
    "CAD": 1.36,          # Canadian Dollar
    "AUD": 1.52,          # Australian Dollar
    "INR": 84.0,          # Indian Rupee
    "CNY": 7.25,          # Chinese Yuan
    "AED": 3.67,          # UAE Dirham
    "SAR": 3.75,          # Saudi Riyal
    "JPY": 152.0,         # Japanese Yen
    "CHF": 0.88,          # Swiss Franc
}

# Currency formatting names & symbols for UI display
CURRENCY_METADATA: Dict[str, Dict[str, str]] = {
    "USD": {"symbol": "$", "name": "US Dollar", "code": "USD"},
    "TZS": {"symbol": "TZS", "name": "Tanzanian Shilling", "code": "TZS"},
    "KES": {"symbol": "KSh", "name": "Kenyan Shilling", "code": "KES"},
    "UGX": {"symbol": "USh", "name": "Ugandan Shilling", "code": "UGX"},
    "RWF": {"symbol": "FRw", "name": "Rwandan Franc", "code": "RWF"},
    "BIF": {"symbol": "FBu", "name": "Burundian Franc", "code": "BIF"},
    "EUR": {"symbol": "€", "name": "Euro", "code": "EUR"},
    "GBP": {"symbol": "£", "name": "British Pound", "code": "GBP"},
    "ZAR": {"symbol": "R", "name": "South African Rand", "code": "ZAR"},
    "NGN": {"symbol": "₦", "name": "Nigerian Naira", "code": "NGN"},
    "GHS": {"symbol": "GH₵", "name": "Ghanaian Cedi", "code": "GHS"},
    "CAD": {"symbol": "C$", "name": "Canadian Dollar", "code": "CAD"},
    "AUD": {"symbol": "A$", "name": "Australian Dollar", "code": "AUD"},
    "INR": {"symbol": "₹", "name": "Indian Rupee", "code": "INR"},
    "CNY": {"symbol": "¥", "name": "Chinese Yuan", "code": "CNY"},
    "AED": {"symbol": "AED", "name": "UAE Dirham", "code": "AED"},
    "SAR": {"symbol": "SAR", "name": "Saudi Riyal", "code": "SAR"},
    "JPY": {"symbol": "¥", "name": "Japanese Yen", "code": "JPY"},
    "CHF": {"symbol": "CHF", "name": "Swiss Franc", "code": "CHF"},
}

# Aliases and symbols mapping to standard ISO code
CURRENCY_ALIASES: Dict[str, str] = {
    "$": "USD",
    "US$": "USD",
    "USD": "USD",
    "DOLLAR": "USD",
    "DOLLARS": "USD",
    "TZS": "TZS",
    "TSH": "TZS",
    "TSHS": "TZS",
    "T.SH": "TZS",
    "T.SHS": "TZS",
    "SHILLING": "TZS",
    "SHILLINGS": "TZS",
    "KES": "KES",
    "KSH": "KES",
    "KSHS": "KES",
    "K.SH": "KES",
    "UGX": "UGX",
    "USH": "UGX",
    "USHS": "UGX",
    "U.SH": "UGX",
    "RWF": "RWF",
    "FRW": "RWF",
    "BIF": "BIF",
    "€": "EUR",
    "EUR": "EUR",
    "EURO": "EUR",
    "EUROS": "EUR",
    "£": "GBP",
    "GBP": "GBP",
    "POUND": "GBP",
    "POUNDS": "GBP",
    "R": "ZAR",
    "ZAR": "ZAR",
    "RAND": "ZAR",
    "₦": "NGN",
    "NGN": "NGN",
    "NAIRA": "NGN",
    "₹": "INR",
    "INR": "INR",
    "RUPEE": "INR",
    "RUPEES": "INR",
    "¥": "JPY",
    "JPY": "JPY",
    "YEN": "JPY",
    "CNY": "CNY",
    "RMB": "CNY",
    "YUAN": "CNY",
    "AED": "AED",
    "DIRHAM": "AED",
    "SAR": "SAR",
    "RIYAL": "SAR",
    "C$": "CAD",
    "CAD": "CAD",
    "A$": "AUD",
    "AUD": "AUD",
    "CHF": "CHF",
    "FRANC": "CHF",
}


def normalize_currency_code(raw: Optional[str]) -> str:
    """Normalizes any currency string, abbreviation, or symbol into standard ISO-4217 code."""
    if not raw:
        return "TZS"
    cleaned = str(raw).strip().upper()
    if cleaned in CURRENCY_ALIASES:
        return CURRENCY_ALIASES[cleaned]
    # Check symbol stripping
    for sym, code in [("$", "USD"), ("€", "EUR"), ("£", "GBP"), ("₦", "NGN"), ("₹", "INR"), ("¥", "JPY")]:
        if sym in cleaned:
            return code
    # Partial matching for common text
    if "TZS" in cleaned or "TSH" in cleaned:
        return "TZS"
    if "USD" in cleaned or "DOLLAR" in cleaned:
        return "USD"
    if "EUR" in cleaned or "EURO" in cleaned:
        return "EUR"
    if "GBP" in cleaned or "POUND" in cleaned:
        return "GBP"
    if "KES" in cleaned or "KSH" in cleaned:
        return "KES"
    if "UGX" in cleaned or "USH" in cleaned:
        return "UGX"
    if "RWF" in cleaned:
        return "RWF"
    return cleaned if cleaned in EXCHANGE_RATES_TO_USD else "USD"


def get_exchange_rate(from_curr: str, to_curr: str) -> float:
    """
    Calculates conversion rate from from_curr to to_curr.
    Example:
        from USD to TZS: 2600.0 / 1.0 = 2600.0
        from TZS to USD: 1.0 / 2600.0 ≈ 0.0003846
        from EUR to TZS: 2600.0 / 0.92 ≈ 2826.087
    """
    f_code = normalize_currency_code(from_curr)
    t_code = normalize_currency_code(to_curr)

    if f_code == t_code:
        return 1.0

    f_usd_rate = EXCHANGE_RATES_TO_USD.get(f_code, 1.0)
    t_usd_rate = EXCHANGE_RATES_TO_USD.get(t_code, 1.0)

    # 1 from_unit = (1 / f_usd_rate) USD = (t_usd_rate / f_usd_rate) to_units
    rate = t_usd_rate / f_usd_rate
    return round(rate, 6)


def convert_amount(amount: float, from_curr: str, to_curr: str, rate: Optional[float] = None) -> float:
    """Converts a monetary amount using specified or looked-up FX exchange rate."""
    if amount == 0.0:
        return 0.0
    if rate is None:
        rate = get_exchange_rate(from_curr, to_curr)
    return round(float(amount) * rate, 2)


class CurrencyDetector:
    """Detects the active currency of spreadsheets by examining headers, cell strings, and columns."""

    # Regex patterns for finding currency in column header titles
    HEADER_PATTERNS = [
        (re.compile(r"[\(\[\{_\s](USD|\$|DOLLARS?)[\)\]\}\s]?", re.IGNORECASE), "USD"),
        (re.compile(r"[\(\[\{_\s](TZS|TSH|T\.SH|TANZANIAN[\s_]SHILLINGS?)[\)\]\}\s]?", re.IGNORECASE), "TZS"),
        (re.compile(r"[\(\[\{_\s](KES|KSH|KENYAN[\s_]SHILLINGS?)[\)\]\}\s]?", re.IGNORECASE), "KES"),
        (re.compile(r"[\(\[\{_\s](UGX|USH|UGANDAN[\s_]SHILLINGS?)[\)\]\}\s]?", re.IGNORECASE), "UGX"),
        (re.compile(r"[\(\[\{_\s](RWF|FRW|RWANDAN[\s_]FRANCS?)[\)\]\}\s]?", re.IGNORECASE), "RWF"),
        (re.compile(r"[\(\[\{_\s](EUR|€|EUROS?)[\)\]\}\s]?", re.IGNORECASE), "EUR"),
        (re.compile(r"[\(\[\{_\s](GBP|£|POUNDS?|STERLING)[\)\]\}\s]?", re.IGNORECASE), "GBP"),
        (re.compile(r"[\(\[\{_\s](ZAR|RAND)[\)\]\}\s]?", re.IGNORECASE), "ZAR"),
        (re.compile(r"[\(\[\{_\s](NGN|₦|NAIRA)[\)\]\}\s]?", re.IGNORECASE), "NGN"),
        (re.compile(r"[\(\[\{_\s](CAD|C\$)[\)\]\}\s]?", re.IGNORECASE), "CAD"),
        (re.compile(r"[\(\[\{_\s](AUD|A\$)[\)\]\}\s]?", re.IGNORECASE), "AUD"),
        (re.compile(r"[\(\[\{_\s](INR|₹|RUPEES?)[\)\]\}\s]?", re.IGNORECASE), "INR"),
        (re.compile(r"[\(\[\{_\s](AED|DIRHAMS?)[\)\]\}\s]?", re.IGNORECASE), "AED"),
    ]

    # Cell-level patterns
    CELL_PREFIX_PATTERNS = [
        (re.compile(r"^\s*(\$|US\$|USD)\s*[\d,.]+", re.IGNORECASE), "USD"),
        (re.compile(r"[\d,.]+\s*(USD|\$)\s*$", re.IGNORECASE), "USD"),
        (re.compile(r"^\s*(TZS|TSH|T\.SH)\s*[\d,.]+", re.IGNORECASE), "TZS"),
        (re.compile(r"[\d,.]+\s*(TZS|TSH)\s*$", re.IGNORECASE), "TZS"),
        (re.compile(r"^\s*(KES|KSH)\s*[\d,.]+", re.IGNORECASE), "KES"),
        (re.compile(r"[\d,.]+\s*(KES|KSH)\s*$", re.IGNORECASE), "KES"),
        (re.compile(r"^\s*(UGX|USH)\s*[\d,.]+", re.IGNORECASE), "UGX"),
        (re.compile(r"^\s*(RWF|FRW)\s*[\d,.]+", re.IGNORECASE), "RWF"),
        (re.compile(r"^\s*(€|EUR)\s*[\d,.]+", re.IGNORECASE), "EUR"),
        (re.compile(r"[\d,.]+\s*(€|EUR)\s*$", re.IGNORECASE), "EUR"),
        (re.compile(r"^\s*(£|GBP)\s*[\d,.]+", re.IGNORECASE), "GBP"),
        (re.compile(r"[\d,.]+\s*(£|GBP)\s*$", re.IGNORECASE), "GBP"),
        (re.compile(r"^\s*(₦|NGN)\s*[\d,.]+", re.IGNORECASE), "NGN"),
        (re.compile(r"^\s*(₹|INR)\s*[\d,.]+", re.IGNORECASE), "INR"),
        (re.compile(r"^\s*(R|ZAR)\s*[\d,.]+", re.IGNORECASE), "ZAR"),
        (re.compile(r"^\s*(AED)\s*[\d,.]+", re.IGNORECASE), "AED"),
    ]

    @classmethod
    def detect_currency_from_dataframe(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Inspects DataFrame headers and sample cell values to detect currency.
        Returns detection summary with votes and confidence.
        """
        votes: Dict[str, float] = {}
        evidence: List[str] = []

        # 1. Inspect Column Headers (Weight = 10 per header match)
        for col in df.columns:
            col_str = str(col).strip()
            for pattern, curr_code in cls.HEADER_PATTERNS:
                if pattern.search(col_str):
                    votes[curr_code] = votes.get(curr_code, 0.0) + 10.0
                    evidence.append(f"Header '{col_str}' contains indicator for {curr_code}")
                    break

        # 2. Inspect Dedicated Currency Column (Weight = 20)
        for col in df.columns:
            col_lower = str(col).lower()
            if col_lower in ["currency", "curr", "curr_code", "currency_code", "iso_currency"]:
                unique_vals = df[col].dropna().astype(str).str.strip().unique()
                for val in unique_vals[:5]:
                    norm = normalize_currency_code(val)
                    if norm:
                        votes[norm] = votes.get(norm, 0.0) + 20.0
                        evidence.append(f"Dedicated currency column '{col}' has value '{val}' -> {norm}")

        # 3. Inspect Cell Values in text/object columns (Weight = 1.0 per cell)
        sample_size = min(len(df), 40)
        sample_df = df.head(sample_size)

        for col in sample_df.columns:
            # Check string or object columns
            series = sample_df[col].dropna()
            for val in series:
                val_str = str(val).strip()
                if not val_str or len(val_str) > 50:
                    continue
                for pattern, curr_code in cls.CELL_PREFIX_PATTERNS:
                    if pattern.search(val_str):
                        votes[curr_code] = votes.get(curr_code, 0.0) + 1.0
                        if len(evidence) < 5:
                            evidence.append(f"Sample cell '{val_str}' indicates {curr_code}")
                        break

        # Calculate winning currency
        if not votes:
            return {
                "detected": None,
                "confidence": 0.0,
                "votes": votes,
                "evidence": "No explicit currency symbols or header labels detected.",
            }

        sorted_votes = sorted(votes.items(), key=lambda x: x[1], reverse=True)
        top_curr, top_score = sorted_votes[0]
        total_score = sum(votes.values())
        confidence = round(top_score / total_score, 2) if total_score > 0 else 0.5

        return {
            "detected": top_curr,
            "confidence": confidence,
            "votes": votes,
            "evidence": "; ".join(evidence[:3]),
        }

    @classmethod
    def detect_workbook_currency(cls, file_path: str, default_currency: str = "TZS") -> Dict[str, Any]:
        """
        Inspects an entire Excel workbook or CSV file across all sheets,
        detecting the source currency and comparing against default_currency.
        """
        if not os.path.exists(file_path):
            return {
                "source_currency": default_currency,
                "target_currency": default_currency,
                "conversion_needed": False,
                "exchange_rate": 1.0,
                "confidence": 0.0,
                "evidence": "File not found.",
                "rate_label": f"1 {default_currency} = 1.0 {default_currency}",
                "message": f"Currency matches business currency ({default_currency}).",
            }

        ext = os.path.splitext(file_path)[1].lower()
        sheets_votes: Dict[str, float] = {}
        all_evidence: List[str] = []
        sheets_detail: Dict[str, Any] = {}

        try:
            if ext in [".xlsx", ".xls"]:
                xl = pd.ExcelFile(file_path)
                for sheet in xl.sheet_names:
                    df = pd.read_excel(xl, sheet_name=sheet, nrows=50)
                    if df.empty:
                        continue
                    sheet_res = cls.detect_currency_from_dataframe(df)
                    sheets_detail[sheet] = sheet_res
                    if sheet_res["detected"]:
                        detected = sheet_res["detected"]
                        sheets_votes[detected] = sheets_votes.get(detected, 0.0) + sheet_res["votes"].get(detected, 1.0)
                        if sheet_res.get("evidence"):
                            all_evidence.append(f"[{sheet}] {sheet_res['evidence']}")

            elif ext == ".csv":
                for enc in ["utf-8", "latin-1", "cp1252"]:
                    try:
                        df = pd.read_csv(file_path, encoding=enc, nrows=50)
                        sheet_res = cls.detect_currency_from_dataframe(df)
                        sheets_detail["Sheet1"] = sheet_res
                        if sheet_res["detected"]:
                            detected = sheet_res["detected"]
                            sheets_votes[detected] = sheets_votes.get(detected, 0.0) + sheet_res["votes"].get(detected, 1.0)
                            if sheet_res.get("evidence"):
                                all_evidence.append(f"[CSV] {sheet_res['evidence']}")
                        break
                    except UnicodeDecodeError:
                        continue
        except Exception as e:
            all_evidence.append(f"Inspection notice: {str(e)}")

        target_curr = normalize_currency_code(default_currency)

        if sheets_votes:
            sorted_votes = sorted(sheets_votes.items(), key=lambda x: x[1], reverse=True)
            source_curr = sorted_votes[0][0]
            confidence = round(sorted_votes[0][1] / sum(sheets_votes.values()), 2)
        else:
            # If no currency symbol or code was detected anywhere, assume default company currency
            source_curr = target_curr
            confidence = 0.50

        conversion_needed = (source_curr != target_curr)
        rate = get_exchange_rate(source_curr, target_curr) if conversion_needed else 1.0

        if rate >= 1.0:
            rate_label = f"1 {source_curr} ≈ {rate:,.2f} {target_curr}"
        else:
            rate_label = f"1 {source_curr} ≈ {rate:.6f} {target_curr}"

        if conversion_needed:
            msg = (
                f"Auto-Conversion Active: Spreadsheet currency detected as {source_curr}."
                f" Values will automatically be converted to your business currency ({target_curr})"
                f" at {rate_label}."
            )
        else:
            msg = f"Spreadsheet currency matches your business currency ({target_curr}). No conversion needed."

        return {
            "source_currency": source_curr,
            "target_currency": target_curr,
            "conversion_needed": conversion_needed,
            "exchange_rate": rate,
            "rate_label": rate_label,
            "confidence": confidence,
            "evidence": "; ".join(all_evidence[:3]) if all_evidence else "Standard business format",
            "message": msg,
            "sheets_detail": sheets_detail,
        }

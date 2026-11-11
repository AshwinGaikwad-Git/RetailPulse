"""Conservative, explainable stock classification. See docs/methodology.md."""
from __future__ import annotations

import pandas as pd

CATEGORIES = ["Merchandise", "Services / postage / fees", "Adjustments", "Unknown"]
CODE_RULES = {
    "DOT": (CATEGORIES[1], "Explicit DOTCOM postage code"),
    "POST": (CATEGORIES[1], "Explicit postage code"),
    "BANK CHARGES": (CATEGORIES[1], "Explicit bank charges code"),
    "AMAZONFEE": (CATEGORIES[1], "Explicit Amazon fee code"),
    "C2": (CATEGORIES[1], "Explicit carriage code"),
    "M": (CATEGORIES[2], "Manual transaction code; not assumed merchandise"),
    "D": (CATEGORIES[2], "Discount code"),
    "ADJUST": (CATEGORIES[2], "Adjustment code"),
    "ADJUST2": (CATEGORIES[2], "Adjustment code"),
    "B": (CATEGORIES[2], "Explicit bad-debt adjustment code"),
    "CRUK": (CATEGORIES[3], "Commission-related code; commercial treatment is uncertain"),
    "S": (CATEGORIES[3], "Sample code; commercial treatment is uncertain"),
    "PADS": (CATEGORIES[3], "Non-standard code; economic treatment is not inferred from the abbreviation"),
}


def classify_products(data: pd.DataFrame) -> pd.DataFrame:
    """Add category and evidence without dropping or changing transaction values."""
    result = data.copy()
    code = result.StockCode.astype("string").str.strip().str.upper()
    description = result.Description.astype("string").str.strip().str.upper()
    result["Category"] = "Unknown"
    result["ClassificationReason"] = "No documented rule; review required"
    # A regular retail code plus a name is a merchandise candidate, not proof of cost/margin.
    regular = (code.str.fullmatch(r"\d{5}[A-Z]{0,2}", na=False).astype(bool)
               & description.notna() & description.ne("").fillna(False).astype(bool))
    result.loc[regular, ["Category", "ClassificationReason"]] = [
        "Merchandise", "Standard catalog code with a description (heuristic)"]
    services = description.str.fullmatch(
        r"DOTCOM POSTAGE|POSTAGE|BANK CHARGES|CARRIAGE|AMAZON FEE", na=False)
    result.loc[services, ["Category", "ClassificationReason"]] = [
        CATEGORIES[1], "Explicit service description"]
    adjustments = description.str.fullmatch(r"MANUAL|DISCOUNT|ADJUSTMENT|ADJUST BAD DEBT", na=False)
    result.loc[adjustments, ["Category", "ClassificationReason"]] = [
        CATEGORIES[2], "Explicit manual, discount, or adjustment description"]
    for stock, (category, reason) in CODE_RULES.items():
        result.loc[code.eq(stock).fillna(False), ["Category", "ClassificationReason"]] = [category, reason]
    return result

"""Recorded financial values and conservative, capacity-limited return matching."""
from __future__ import annotations

from collections import defaultdict
import numpy as np
import pandas as pd

from src.classification import classify_products
from src.data_cleaning import EXPECTED_COLUMNS, clean_data


def transaction_ledger(raw: pd.DataFrame) -> pd.DataFrame:
    """Keep all deduplicated source rows, including excluded and negative records."""
    missing = set(EXPECTED_COLUMNS) - set(raw.columns)
    if missing:
        raise ValueError(f"Missing expected columns: {sorted(missing)}")
    ledger = raw.drop_duplicates().copy().reset_index(drop=True)
    ledger["LineID"] = np.arange(len(ledger))
    for name in ["InvoiceNo", "StockCode", "CustomerID"]:
        ledger[name] = ledger[name].astype("string").str.strip()
    ledger["InvoiceDate"] = pd.to_datetime(ledger.InvoiceDate, errors="coerce")
    for name in ["Quantity", "UnitPrice"]:
        ledger[name] = pd.to_numeric(ledger[name], errors="coerce")
    ledger["TotalPrice"] = ledger.Quantity * ledger.UnitPrice
    ledger["IsCancellation"] = ledger.InvoiceNo.str.upper().str.startswith("C", na=False)
    ledger["IsNegativeQuantity"] = ledger.Quantity.lt(0)
    ledger["IsNegativeValue"] = ledger.TotalPrice.lt(0) & np.isfinite(ledger.TotalPrice)
    ledger["IsReturnRecord"] = ledger.IsCancellation | ledger.IsNegativeQuantity | ledger.IsNegativeValue
    ledger["RecordType"] = np.select(
        [ledger.IsCancellation, ledger.IsNegativeQuantity, ledger.IsNegativeValue],
        ["Credit-note invoice", "Negative quantity / adjustment", "Negative-value adjustment"],
        default="Other / positive record")
    return classify_products(ledger)


def revenue_metrics(ledger: pd.DataFrame, sales: pd.DataFrame) -> dict[str, float | int]:
    """Reconcile gross minus recorded negative values plus residual to signed ledger total."""
    finite = ledger.loc[np.isfinite(ledger.TotalPrice)]
    gross = float(sales.TotalPrice.sum())
    negative = float(-finite.loc[finite.TotalPrice.lt(0), "TotalPrice"].sum())
    net = float(finite.TotalPrice.sum())
    residual = net - gross + negative
    if abs(residual) < 1e-6:
        residual = 0.0  # Avoid presenting floating-point noise as an economic adjustment.
    categories = classify_products(sales) if "Category" not in sales else sales
    merchandise = float(categories.loc[categories.Category.eq("Merchandise"), "TotalPrice"].sum())
    return {
        "gross_positive_sales_gbp": gross,
        "recorded_credit_return_value_gbp": negative,
        "net_recorded_transaction_value_gbp": net,
        "other_signed_value_gbp": residual,
        "merchandise_positive_sales_gbp": merchandise,
        "non_merchandise_positive_sales_gbp": gross - merchandise,
        "return_record_rows": int(ledger.IsReturnRecord.sum()),
        "nonfinite_value_rows": int((~np.isfinite(ledger.TotalPrice)).sum()),
    }


def match_returns(ledger: pd.DataFrame) -> pd.DataFrame:
    """Match only one unambiguous earlier sales line at the same customer/code/price.

    Outstanding quantity is consumed once. Ambiguous or oversized returns remain
    unmatched; no guessed invoice link or multi-lot allocation is invented.
    Run on the complete ledger before filtering so prior sales remain visible.
    """
    columns = ["ReturnLineID", "ReturnInvoice", "InvoiceDate", "Country", "StockCode",
               "CustomerID", "ReturnValueGBP", "Status", "Reason", "MatchedSalesLineID",
               "MatchedInvoice", "ReturnedUnits"]
    lots: dict[tuple, list[dict]] = defaultdict(list)
    rows = []
    ordered = ledger.sort_values(["InvoiceDate", "LineID"], na_position="last")
    for row in ordered.itertuples(index=False):
        valid_key = pd.notna(row.CustomerID) and pd.notna(row.StockCode) and pd.notna(row.InvoiceDate)
        finite = np.isfinite(row.TotalPrice) and np.isfinite(row.UnitPrice)
        key = (row.CustomerID, row.StockCode, row.UnitPrice) if valid_key and finite else None
        if not row.IsReturnRecord:
            if key is not None and row.Quantity > 0 and row.UnitPrice > 0 and pd.notna(row.InvoiceNo):
                lots[key].append({"id": row.LineID, "invoice": row.InvoiceNo,
                                  "date": row.InvoiceDate, "remaining": float(row.Quantity)})
            continue
        result = dict(zip(columns, [row.LineID, row.InvoiceNo, row.InvoiceDate, row.Country,
                                   row.StockCode, row.CustomerID,
                                   -float(row.TotalPrice) if finite and row.TotalPrice < 0 else 0.0,
                                   "Unmatched", "", pd.NA, pd.NA,
                                   -float(row.Quantity) if row.Quantity < 0 else 0.0]))
        if key is None:
            result["Reason"] = "Missing customer, product, date, or finite value"
        elif not (row.Quantity < 0 and row.UnitPrice > 0):
            result["Reason"] = "Not a negative-quantity return at a positive unit price"
        else:
            candidates = [lot for lot in lots[key]
                          if lot["remaining"] > 0 and lot["date"] < row.InvoiceDate]
            if len(candidates) != 1:
                result["Reason"] = "No earlier available sale" if not candidates else "Multiple possible original sales"
            elif candidates[0]["remaining"] + 1e-9 < -row.Quantity:
                result["Reason"] = "Return exceeds remaining original quantity"
            else:
                lot = candidates[0]
                lot["remaining"] -= -row.Quantity
                result.update(Status="Matched", Reason="Unique earlier customer/code/price sales line",
                              MatchedSalesLineID=lot["id"], MatchedInvoice=lot["invoice"])
        rows.append(result)
    return pd.DataFrame(rows, columns=columns)


def duplicate_sensitivity(raw: pd.DataFrame) -> pd.DataFrame:
    """Compare identical valid-sales rules with exact duplicates retained vs removed."""
    sales, _ = clean_data(raw)
    # A unique auxiliary marker preserves original rows without changing the cleaning rules.
    retained = raw.copy()
    retained["_SensitivitySourceRow"] = np.arange(len(raw))
    kept, _ = clean_data(retained)
    rows = []
    for label, data in [("Remove exact duplicates (default)", sales), ("Keep exact duplicates", kept)]:
        rows.append({"Policy": label, "ValidSalesLines": len(data),
                     "GrossPositiveSalesGBP": float(data.TotalPrice.sum()),
                     "SalesInvoices": int(data.InvoiceNo.nunique())})
    return pd.DataFrame(rows)

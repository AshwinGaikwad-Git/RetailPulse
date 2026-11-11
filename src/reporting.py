"""Load once for the app, or export the extended RetailPulse analytical tables."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import pandas as pd

from src.analytics import segment_report
from src.classification import classify_products
from src.data_cleaning import (
    DATA_DIR, PROJECT_ROOT, build_rfm, clean_data, load_raw_data, locate_workbook,
)
from src.finance import duplicate_sensitivity, match_returns, revenue_metrics, transaction_ledger


@dataclass
class AnalysisBundle:
    """Shared cached frames are read-only; filter helpers always return copies."""
    sales: pd.DataFrame
    ledger: pd.DataFrame
    returns: pd.DataFrame
    audit: dict
    sensitivity: pd.DataFrame
    financials: dict
    rfm: pd.DataFrame
    workbook: str


def load_analysis(workbook: Path | None = None) -> AnalysisBundle:
    path = Path(workbook) if workbook is not None else locate_workbook()
    raw = load_raw_data(path)
    sales, audit = clean_data(raw)
    if sales.empty:
        raise ValueError("The workbook has no valid positive sales. Review its columns and cleaning audit.")
    sales = classify_products(sales)
    ledger = transaction_ledger(raw)
    returns = match_returns(ledger)
    sensitivity = duplicate_sensitivity(raw)
    financials = revenue_metrics(ledger, sales)
    rfm = build_rfm(sales)
    # Repeated labels dominate memory. Categoricals reduce cold-start/session memory.
    for frame in [sales, ledger]:
        for column in ["Country", "Category", "ClassificationReason"]:
            frame[column] = frame[column].astype("category")
    return AnalysisBundle(sales, ledger, returns, audit, sensitivity, financials, rfm, path.name)


def export_reports(bundle: AnalysisBundle, out: Path = DATA_DIR) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    bundle.returns.to_csv(out / "return_matches.csv", index=False)
    bundle.sensitivity.to_csv(out / "duplicate_sensitivity.csv", index=False)
    segment_report(bundle.sales, bundle.rfm).to_csv(out / "segment_summary.csv", index=False)
    categories = bundle.sales.groupby("Category", observed=True).agg(
        PositiveSalesGBP=("TotalPrice", "sum"), Lines=("InvoiceNo", "size"))
    categories.to_csv(out / "category_revenue.csv")
    rules = bundle.sales.groupby(["StockCode", "Category", "ClassificationReason"], observed=True).agg(
        Description=("Description", "first"), PositiveSalesGBP=("TotalPrice", "sum"))
    rules.to_csv(out / "product_classification.csv")
    result = {**bundle.financials, "matching": {
        "matched_rows": int(bundle.returns.Status.eq("Matched").sum()),
        "unmatched_rows": int(bundle.returns.Status.eq("Unmatched").sum()),
        "matched_recorded_credit_gbp": float(bundle.returns.loc[bundle.returns.Status.eq("Matched"), "ReturnValueGBP"].sum()),
        "unmatched_recorded_credit_gbp": float(bundle.returns.loc[bundle.returns.Status.eq("Unmatched"), "ReturnValueGBP"].sum()),
    }}
    (out / "financial_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(export_reports(load_analysis()), indent=2))

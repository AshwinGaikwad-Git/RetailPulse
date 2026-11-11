"""Verify generated real-data outputs against baseline and financial reconciliation."""
import json
import math
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def verify() -> None:
    summary = json.loads((ROOT / "analysis_summary.json").read_text())
    expected = {"revenue_gbp": 10642110.804, "valid_sales_lines": 524878,
                "unique_sales_invoices": 19960, "unique_customers": 4338}
    for name, value in expected.items():
        if not math.isclose(summary[name], value, abs_tol=1e-6):
            raise AssertionError(f"Baseline changed: {name}: {summary[name]} != {value}")
    audit = summary["audit"]
    assert audit["source_rows"] == audit["duplicate_rows"] + audit["valid_sales_rows"] + audit["invalid_or_cancelled_rows_excluded"]
    sales = pd.read_csv(ROOT / "dataset" / "cleaned_online_retail.csv",
                        usecols=["InvoiceNo", "CustomerID", "TotalPrice"],
                        dtype={"InvoiceNo": "string", "CustomerID": "string"})
    assert len(sales) == summary["valid_sales_lines"]
    assert sales.InvoiceNo.nunique() == summary["unique_sales_invoices"]
    assert sales.CustomerID.nunique() == summary["unique_customers"]
    assert math.isclose(sales.TotalPrice.sum(), summary["revenue_gbp"], abs_tol=1e-6)
    for filename, column in [("product_summary.csv", "Revenue"), ("monthly_revenue.csv", "RevenueGBP")]:
        frame = pd.read_csv(ROOT / "dataset" / filename)
        assert math.isclose(frame[column].sum(), summary["revenue_gbp"], abs_tol=1e-6)
    finance = json.loads((ROOT / "dataset" / "financial_summary.json").read_text())
    assert math.isclose(finance["gross_positive_sales_gbp"], summary["revenue_gbp"], abs_tol=1e-6)
    assert math.isclose(finance["gross_positive_sales_gbp"] - finance["recorded_credit_return_value_gbp"] + finance["other_signed_value_gbp"], finance["net_recorded_transaction_value_gbp"], abs_tol=1e-6)
    assert math.isclose(finance["merchandise_positive_sales_gbp"] + finance["non_merchandise_positive_sales_gbp"], summary["revenue_gbp"], abs_tol=1e-6)
    returns = pd.read_csv(ROOT / "dataset" / "return_matches.csv")
    assert returns.ReturnLineID.is_unique
    assert math.isclose(returns.ReturnValueGBP.sum(), finance["recorded_credit_return_value_gbp"], abs_tol=1e-6)
    rfm = pd.read_csv(ROOT / "dataset" / "customer_rfm.csv")
    segments = pd.read_csv(ROOT / "dataset" / "segment_summary.csv")
    assert len(rfm) == segments.Customers.sum() == summary["unique_customers"]
    assert math.isclose(rfm.Monetary.sum(), segments.Revenue.sum(), abs_tol=1e-6)
    assert rfm.Segment.value_counts().to_dict() == summary["rfm_segment_counts"]
    print("PASS: baseline metrics, cleaning audit, revenue bridge, categories, unique refunds, and RFM outputs reconcile.")


if __name__ == "__main__":
    verify()

"""Pure analytical functions shared by dashboard, exports and tests."""
from __future__ import annotations

from collections.abc import Sequence
import pandas as pd

from src.data_cleaning import build_rfm, cohort_retention

SEGMENT_ACTIONS = {
    "Champions": "Test loyalty rewards, early access and referral invitations.",
    "Loyal customers": "Test personalized recommendations, cross-selling and loyalty initiatives.",
    "At risk": "Test re-engagement messages, tailored promotions and customer feedback campaigns.",
    "Needs attention": "Test product education, targeted engagement and purchase incentives.",
}
SEGMENT_MEANINGS = {
    "Champions": "R >= 3, F >= 3 and M >= 3: recent, frequent and higher-spending customers.",
    "Loyal customers": "R >= 3 and F >= 2, after assigning Champions.",
    "At risk": "R <= 2 and F >= 3: historically frequent but less recent in this scope.",
    "Needs attention": "All remaining observed customers; a diverse group, not a diagnosis.",
}


def filter_transactions(data: pd.DataFrame, start=None, end=None,
                        countries: Sequence[str] | None = None,
                        stocks: Sequence[str] | None = None,
                        categories: Sequence[str] | None = None) -> pd.DataFrame:
    """Inclusive calendar dates; None selects all, an empty list selects none."""
    mask = pd.Series(True, index=data.index)
    if start is not None:
        mask &= data.InvoiceDate.ge(pd.Timestamp(start).normalize())
    if end is not None:
        mask &= data.InvoiceDate.lt(pd.Timestamp(end).normalize() + pd.Timedelta(days=1))
    for column, selected in [("Country", countries), ("StockCode", stocks), ("Category", categories)]:
        if selected is not None:
            mask &= data[column].isin(selected)
    return data.loc[mask].copy()


def sales_kpis(sales: pd.DataFrame) -> dict:
    revenue = float(sales.TotalPrice.sum())
    orders = int(sales.InvoiceNo.nunique())
    return {"Revenue": revenue, "Invoices": orders, "Customers": int(sales.CustomerID.nunique()),
            "AverageInvoice": revenue / orders if orders else 0.0}


def monthly_sales(sales: pd.DataFrame) -> pd.DataFrame:
    if sales.empty:
        return pd.DataFrame(columns=["Month", "Revenue", "Invoices", "AverageInvoice"])
    result = sales.groupby(sales.InvoiceDate.dt.to_period("M")).agg(
        Revenue=("TotalPrice", "sum"), Invoices=("InvoiceNo", "nunique"))
    result = result.reindex(pd.period_range(result.index.min(), result.index.max(), freq="M"), fill_value=0)
    result["AverageInvoice"] = result.Revenue.div(result.Invoices.where(result.Invoices.ne(0))).fillna(0)
    result.index = result.index.astype(str)
    return result.rename_axis("Month").reset_index()


def segment_report(sales: pd.DataFrame, rfm: pd.DataFrame | None = None) -> pd.DataFrame:
    """Segment AIV is segment spend / distinct customer-invoice pairs, not mean customer spend."""
    rfm = build_rfm(sales) if rfm is None else rfm
    if rfm.empty:
        return pd.DataFrame(columns=["Segment", "Customers", "Revenue", "AverageSpending",
                                     "AverageFrequency", "AverageInvoice", "CustomerShare", "RevenueShare"])
    report = rfm.groupby("Segment").agg(Customers=("Monetary", "size"), Revenue=("Monetary", "sum"),
        AverageSpending=("Monetary", "mean"), AverageFrequency=("Frequency", "mean"), Invoices=("Frequency", "sum"))
    report["AverageInvoice"] = report.Revenue / report.Invoices
    report["CustomerShare"] = report.Customers / report.Customers.sum()
    report["RevenueShare"] = report.Revenue / report.Revenue.sum()
    return report.sort_values("Revenue", ascending=False).reset_index()


def retention_tables(sales: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    known = sales.dropna(subset=["CustomerID"]).copy()
    if known.empty:
        return pd.DataFrame(), pd.DataFrame(columns=["Cohort", "Customers"]), pd.DataFrame(columns=["Month", "Customers"])
    first = known.groupby("CustomerID").InvoiceDate.min().dt.to_period("M")
    sizes = first.value_counts().sort_index().rename_axis("Cohort").rename("Customers").reset_index()
    sizes["Cohort"] = sizes.Cohort.astype(str)
    activity = known.groupby(known.InvoiceDate.dt.to_period("M")).CustomerID.nunique()
    activity = activity.rename_axis("Month").rename("Customers").reset_index()
    activity["Month"] = activity.Month.astype(str)
    return cohort_retention(sales), sizes, activity


def csv_bytes(data: pd.DataFrame, index: bool = False) -> bytes:
    """UTF-8 CSV for exports; escape spreadsheet formula prefixes in text cells."""
    safe = data.copy()
    for column in safe.select_dtypes(include=["object", "string"]).columns:
        safe[column] = safe[column].map(
            lambda value: "'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")) else value)
    return safe.to_csv(index=index).encode("utf-8-sig")

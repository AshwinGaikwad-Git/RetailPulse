"""Download, clean, analyze, and visualize the UCI Online Retail dataset."""
from __future__ import annotations

import json
import shutil
import urllib.request
import zipfile
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "dataset"
CHART_DIR = PROJECT_ROOT / "visualizations"
DATA_URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
LEGACY_DATA_URL = "https://archive.ics.uci.edu/ml/machine-learning-databases/00352/Online%20Retail.xlsx"
EXPECTED_COLUMNS = ["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country"]


def locate_workbook(data_dir: Path = DATA_DIR) -> Path:
    """Return the extracted workbook; download and extract the UCI archive if needed."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    candidates = sorted(data_dir.glob("*.xlsx"))
    if candidates:
        preferred = data_dir / "Online Retail.xlsx"
        if preferred in candidates:
            return preferred
        if len(candidates) == 1:
            return candidates[0]
        raise ValueError("Multiple workbooks found; name the intended source 'Online Retail.xlsx'.")
    archive = data_dir / "online_retail.zip"
    download_errors: list[str] = []
    if not archive.exists() or not zipfile.is_zipfile(archive):
        try:
            request = urllib.request.Request(DATA_URL, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=60) as response, archive.with_suffix(".part").open("wb") as target:
                shutil.copyfileobj(response, target)
            if not zipfile.is_zipfile(archive.with_suffix(".part")):
                raise ValueError("Downloaded response is not a ZIP archive")
            archive.with_suffix(".part").replace(archive)
        except Exception as exc:
            download_errors.append(f"official ZIP: {exc}")
    # The official legacy UCI endpoint serves the workbook directly rather than a ZIP.
    if not archive.exists() or not zipfile.is_zipfile(archive):
        try:
            request = urllib.request.Request(LEGACY_DATA_URL, headers={"User-Agent": "Mozilla/5.0"})
            direct_path = data_dir / "Online Retail.xlsx"
            with urllib.request.urlopen(request, timeout=60) as response, direct_path.with_suffix(".part").open("wb") as target:
                shutil.copyfileobj(response, target)
            if not zipfile.is_zipfile(direct_path.with_suffix(".part")):
                raise ValueError("Downloaded response is not an XLSX workbook")
            direct_path.with_suffix(".part").replace(direct_path)
            return direct_path
        except Exception as exc:
            download_errors.append(f"official legacy workbook: {exc}")
    try:
        with zipfile.ZipFile(archive) as zipped:
            members = [m for m in zipped.namelist() if Path(m).name == "Online Retail.xlsx"]
            if len(members) != 1:
                raise ValueError("Archive must contain exactly one Online Retail.xlsx workbook")
            destination = data_dir / "Online Retail.xlsx"
            with zipped.open(members[0]) as source, destination.with_suffix(".part").open("wb") as target:
                shutil.copyfileobj(source, target)
            destination.with_suffix(".part").replace(destination)
    except (zipfile.BadZipFile, OSError, ValueError) as exc:
        raise RuntimeError(
            f"Could not obtain the UCI workbook: {exc}. Download {DATA_URL} manually and "
            f"place Online Retail.xlsx in {data_dir}. Attempts: {'; '.join(download_errors)}"
        ) from exc
    candidates = sorted(data_dir.glob("*.xlsx"))
    if not candidates:
        raise FileNotFoundError(
            f"No Excel workbook found in {data_dir}. Download the UCI archive at {DATA_URL}, "
            f"or the direct workbook at {LEGACY_DATA_URL}, and place the extracted workbook here. "
            f"Download attempts: {'; '.join(download_errors) or 'archive extraction did not contain a workbook'}"
        )
    return candidates[0]


def load_raw_data(path: Path | str) -> pd.DataFrame:
    """Load the source workbook without modifying its rows."""
    frame = pd.read_excel(path, engine="openpyxl")
    missing = set(EXPECTED_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Workbook is missing expected columns: {sorted(missing)}")
    return frame


def clean_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Clean a copy; retain valid sales separately from cancellation/return records."""
    missing = set(EXPECTED_COLUMNS) - set(raw.columns)
    if missing:
        raise ValueError(f"Missing expected columns: {sorted(missing)}")
    audit = {"source_rows": int(len(raw)), "duplicate_rows": int(raw.duplicated().sum()),
             "missing_customer_rows": int(raw.CustomerID.isna().sum()),
             "cancellation_rows": int(raw.InvoiceNo.astype(str).str.upper().str.startswith("C", na=False).sum()),
             "nonpositive_quantity_rows": int(pd.to_numeric(raw.Quantity, errors="coerce").le(0).sum()),
             "nonpositive_price_rows": int(pd.to_numeric(raw.UnitPrice, errors="coerce").le(0).sum())}
    data = raw.drop_duplicates().copy()
    for column in ["InvoiceNo", "StockCode"]:
        data[column] = data[column].astype("string").str.strip()
    audit["deduplicated_rows"] = int(len(data))
    for column in ["Quantity", "UnitPrice"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data["InvoiceDate"] = pd.to_datetime(data["InvoiceDate"], errors="coerce")
    data["CustomerID"] = data["CustomerID"].astype("string")
    data["Description"] = data["Description"].astype("string").str.strip()
    data["TotalPrice"] = data["Quantity"] * data["UnitPrice"]
    data["Year"] = data.InvoiceDate.dt.year
    data["Month"] = data.InvoiceDate.dt.month
    data["YearMonth"] = data.InvoiceDate.dt.to_period("M").astype("string")
    data["Day"] = data.InvoiceDate.dt.day
    data["Weekday"] = data.InvoiceDate.dt.day_name()
    data["Hour"] = data.InvoiceDate.dt.hour
    audit["missing_dates_after_parse"] = int(data.InvoiceDate.isna().sum())
    # CustomerID is not imputed: anonymous purchases remain in transaction/revenue summaries.
    valid = data.loc[
        ~data.InvoiceNo.str.upper().str.startswith("C", na=False)
        & data.Quantity.gt(0) & data.UnitPrice.gt(0) & data.InvoiceDate.notna()
        & np.isfinite(data.TotalPrice) & data.InvoiceNo.notna() & data.StockCode.notna()
        & data.InvoiceNo.ne("") & data.StockCode.ne("")
    ].copy()
    audit["valid_sales_rows"] = int(len(valid))
    audit["missing_customer_rows_removed_from_customer_analysis"] = int(valid.CustomerID.isna().sum())
    audit["invalid_or_cancelled_rows_excluded"] = int(len(data) - len(valid))
    return valid, audit


def cancellation_summary(raw: pd.DataFrame) -> pd.DataFrame:
    """Summarize explicit credit-note invoices; negative quantities are also returns/adjustments."""
    raw = raw.drop_duplicates().copy()
    for column in ["Quantity", "UnitPrice"]:
        raw[column] = pd.to_numeric(raw[column], errors="coerce")
    cancel = raw.InvoiceNo.astype(str).str.strip().str.upper().str.startswith("C", na=False)
    negative = raw.Quantity.lt(0)
    return pd.DataFrame([{
        "deduplicated_source_rows": len(raw),
        "cancellation_or_negative_rows": int((cancel | negative).sum()),
        "cancellation_invoice_rows": int(cancel.sum()),
        "negative_quantity_rows": int(negative.sum()),
        "cancellation_invoice_value_abs": float((raw.loc[cancel, "Quantity"] * raw.loc[cancel, "UnitPrice"]).abs().sum()),
        "negative_quantity_value_abs": float((raw.loc[negative, "Quantity"] * raw.loc[negative, "UnitPrice"]).abs().sum()),
    }])


def build_rfm(data: pd.DataFrame) -> pd.DataFrame:
    """Calculate customer-level RFM using the day after the latest invoice as reference."""
    known = data.dropna(subset=["CustomerID"])
    if known.empty:
        return pd.DataFrame(columns=["Recency", "Frequency", "Monetary", "R", "F", "M", "Segment"]).rename_axis("CustomerID")
    snapshot = data.InvoiceDate.max().normalize() + pd.Timedelta(days=1)
    rfm = known.groupby("CustomerID").agg(
        Recency=("InvoiceDate", lambda dates: (snapshot - dates.max().normalize()).days),
        Frequency=("InvoiceNo", "nunique"), Monetary=("TotalPrice", "sum"))
    # Average percentile ranks keep identical values together, including tiny populations.
    for column, score in [("Recency", "R"), ("Frequency", "F"), ("Monetary", "M")]:
        rfm[score] = np.ceil(rfm[column].rank(method="average", pct=True) * 4).clip(1, 4).astype(int)
    rfm["R"] = 5 - rfm["R"]
    rfm["Segment"] = np.select(
        [rfm.R.ge(3) & rfm.F.ge(3) & rfm.M.ge(3), rfm.R.ge(3) & rfm.F.ge(2), rfm.R.le(2) & rfm.F.ge(3)],
        ["Champions", "Loyal customers", "At risk"], default="Needs attention")
    return rfm


def product_summary(data: pd.DataFrame) -> pd.DataFrame:
    """Aggregate by stock code; use its most frequent description as a display label."""
    products = data.groupby("StockCode").agg(Units=("Quantity", "sum"), Revenue=("TotalPrice", "sum"))
    labels = data.groupby("StockCode").Description.agg(
        lambda values: values.dropna().mode().iloc[0] if not values.dropna().empty else "Unknown product")
    products["Description"] = labels
    return products.sort_values("Revenue", ascending=False)


def cohort_retention(data: pd.DataFrame) -> pd.DataFrame:
    """Return zero for observed inactive months and NaN for unobserved future months."""
    known = data.dropna(subset=["CustomerID"]).copy()
    if known.empty:
        return pd.DataFrame()
    known["Cohort"] = known.groupby("CustomerID").InvoiceDate.transform("min").dt.to_period("M")
    known["Activity"] = known.InvoiceDate.dt.to_period("M")
    known["Age"] = known.Activity.astype("int64") - known.Cohort.astype("int64")
    last_month = data.InvoiceDate.max().to_period("M")
    counts = known.groupby(["Cohort", "Age"]).CustomerID.nunique().unstack()
    counts = counts.reindex(columns=range(int(last_month.ordinal - counts.index.min().ordinal) + 1)).fillna(0)
    retention = counts.div(counts[0], axis=0)
    for cohort in retention.index:
        retention.loc[cohort, retention.columns > last_month.ordinal - cohort.ordinal] = np.nan
    retention.columns.name = "MonthsSinceFirstPurchase"
    return retention


def _save_charts(data: pd.DataFrame, rfm: pd.DataFrame, out: Path = CHART_DIR) -> None:
    out.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="notebook", font_scale=1.0)
    monthly = data.groupby("YearMonth").TotalPrice.sum().sort_index()
    fig, ax = plt.subplots(figsize=(12, 5)); monthly.plot(ax=ax, color="#247ba0", marker="o", linewidth=2)
    ax.set(title="Monthly Revenue", xlabel="Invoice month", ylabel="Revenue (GBP)"); ax.tick_params(axis="x", rotation=45); fig.tight_layout(); fig.savefig(out / "monthly_revenue.png", dpi=160); plt.close(fig)
    daily = data.set_index("InvoiceDate").TotalPrice.resample("D").sum()
    fig, ax = plt.subplots(figsize=(12, 5)); daily.plot(ax=ax, color="#70c1b3", linewidth=1)
    ax.set(title="Daily Revenue", xlabel="Invoice date", ylabel="Revenue (GBP)"); fig.tight_layout(); fig.savefig(out / "daily_revenue.png", dpi=160); plt.close(fig)
    products = product_summary(data)
    best = products.nlargest(10, "Units").set_index("Description").Units.sort_values()
    fig, ax = plt.subplots(figsize=(10, 6)); best.plot.barh(ax=ax, color="#70c1b3"); ax.set(title="Top 10 Products by Units Sold", xlabel="Units", ylabel="Product"); fig.tight_layout(); fig.savefig(out / "top_products.png", dpi=160); plt.close(fig)
    countries = data.groupby("Country").TotalPrice.sum().nlargest(12).sort_values()
    fig, ax = plt.subplots(figsize=(10, 6)); countries.plot.barh(ax=ax, color="#f3a712"); ax.set(title="Top Countries by Revenue", xlabel="Revenue (GBP)", ylabel="Country"); fig.tight_layout(); fig.savefig(out / "country_revenue.png", dpi=160); plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 5)); sns.histplot(rfm.Monetary.clip(upper=rfm.Monetary.quantile(.99)), bins=40, ax=ax, color="#247ba0"); ax.set(title="Customer Spending Distribution (capped at 99th percentile)", xlabel="Customer revenue (GBP)"); fig.tight_layout(); fig.savefig(out / "customer_spending.png", dpi=160); plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 5)); data.groupby("Hour").TotalPrice.sum().plot.bar(ax=ax, color="#70c1b3"); ax.set(title="Revenue by Hour", xlabel="Invoice hour", ylabel="Revenue (GBP)"); fig.tight_layout(); fig.savefig(out / "hourly_sales.png", dpi=160); plt.close(fig)
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday = data.groupby("Weekday").TotalPrice.sum().reindex(order, fill_value=0)
    fig, ax = plt.subplots(figsize=(9, 5)); weekday.plot.bar(ax=ax, color="#f3a712"); ax.set(title="Revenue by Weekday", xlabel="Weekday", ylabel="Revenue (GBP)"); fig.tight_layout(); fig.savefig(out / "weekday_sales.png", dpi=160); plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 5)); sns.histplot(data.TotalPrice.clip(upper=data.TotalPrice.quantile(.99)), bins=50, ax=ax, color="#247ba0"); ax.set(title="Transaction Line Revenue (capped at 99th percentile)", xlabel="Line revenue (GBP)"); fig.tight_layout(); fig.savefig(out / "revenue_distribution.png", dpi=160); plt.close(fig)
    numeric = data[["Quantity", "UnitPrice", "TotalPrice", "Hour", "Day", "Month"]].corr()
    fig, ax = plt.subplots(figsize=(8, 6)); sns.heatmap(numeric, annot=True, cmap="vlag", center=0, fmt=".2f", ax=ax); ax.set(title="Numeric Feature Correlations"); fig.tight_layout(); fig.savefig(out / "correlation_heatmap.png", dpi=160); plt.close(fig)
    # Pareto curve across products; revenue share is calculated from actual line sales.
    product = products.Revenue
    share = product.cumsum() / product.sum()
    fig, ax = plt.subplots(figsize=(10, 5)); ax.plot(np.arange(1, len(share)+1), share.values, color="#247ba0"); ax.axhline(.8, color="#f3a712", linestyle="--", label="80% revenue"); ax.set(title="Product Revenue Pareto Curve", xlabel="Products ranked by revenue", ylabel="Cumulative revenue share"); ax.legend(); fig.tight_layout(); fig.savefig(out / "product_pareto.png", dpi=160); plt.close(fig)
    # Cohort retention by first purchase month and subsequent activity month.
    retention = cohort_retention(data)
    if not retention.empty:
        fig, ax = plt.subplots(figsize=(12, 7)); sns.heatmap(retention, cmap="Blues", vmin=0, vmax=1, annot=True, fmt=".0%", ax=ax); ax.set(title="Customer Cohort Retention", xlabel="Months since first purchase", ylabel="First purchase cohort"); fig.tight_layout(); fig.savefig(out / "cohort_retention.png", dpi=160); plt.close(fig)


def run_analysis(raw: pd.DataFrame | None = None, workbook: Path | None = None) -> dict:
    """Run the full pipeline, save transparent outputs, and return computed headline metrics."""
    workbook = Path(workbook) if workbook is not None else locate_workbook()
    if raw is None:
        raw = load_raw_data(workbook)
    sales, audit = clean_data(raw)
    if sales.empty:
        raise ValueError("No valid sales rows remain after cleaning; inspect the source workbook.")
    rfm = build_rfm(sales)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cancellation_summary(raw).to_csv(DATA_DIR / "return_cancellation_summary.csv", index=False)
    rfm.to_csv(DATA_DIR / "customer_rfm.csv")
    sales.to_csv(DATA_DIR / "cleaned_online_retail.csv", index=False)
    products = product_summary(sales)
    products.to_csv(DATA_DIR / "product_summary.csv")
    cohort_retention(sales).to_csv(DATA_DIR / "cohort_retention.csv")
    _save_charts(sales, rfm)
    monthly = sales.groupby("YearMonth").TotalPrice.sum()
    monthly.rename("RevenueGBP").to_csv(DATA_DIR / "monthly_revenue.csv")
    country = sales.groupby("Country").TotalPrice.sum().sort_values(ascending=False)
    orders = sales.groupby("InvoiceNo").TotalPrice.sum()
    customer_orders = sales.dropna(subset=["CustomerID"]).groupby("CustomerID").InvoiceNo.nunique()
    product = products.Revenue
    pareto_n = int((product.cumsum() / product.sum() < .8).sum() + 1)
    metrics = {"source_file": workbook.name, "audit": audit, "revenue_gbp": float(sales.TotalPrice.sum()),
        "valid_sales_lines": int(len(sales)), "unique_sales_invoices": int(sales.InvoiceNo.nunique()),
        "unique_customers": int(sales.CustomerID.nunique()), "average_order_value_gbp": float(orders.mean()),
        "top_country": str(country.index[0]), "top_country_revenue_gbp": float(country.iloc[0]),
        "top_revenue_product": str(products.iloc[0].Description), "top_product_stock_code": str(product.index[0]), "top_revenue_product_gbp": float(product.iloc[0]),
        "observation_start": str(sales.InvoiceDate.min()), "observation_end": str(sales.InvoiceDate.max()),
        "known_customer_revenue_gbp": float(sales.loc[sales.CustomerID.notna(), "TotalPrice"].sum()),
        "product_count": int(len(products)),
        "repeat_customer_share": float(customer_orders.gt(1).mean()) if len(customer_orders) else None,
        "peak_month": str(monthly.idxmax()), "peak_month_revenue_gbp": float(monthly.max()),
        "products_for_80pct_revenue": pareto_n, "rfm_segment_counts": {str(k): int(v) for k,v in rfm.Segment.value_counts().items()},
        "cohort_months": int(sales.InvoiceDate.dt.to_period("M").nunique())}
    (PROJECT_ROOT / "analysis_summary.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


if __name__ == "__main__":
    result = run_analysis()
    print(json.dumps(result, indent=2))

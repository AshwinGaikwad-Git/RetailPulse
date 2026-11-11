"""Five dashboard views. All calculations live in src; these functions present them."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.charts import PALETTE, bar, line, pareto, retention_heatmap, style
from src.analytics import (
    SEGMENT_ACTIONS, SEGMENT_MEANINGS, csv_bytes, monthly_sales, retention_tables,
    sales_kpis, segment_report,
)
from src.data_cleaning import build_rfm, product_summary
from src.finance import revenue_metrics
from src.reporting import AnalysisBundle


def money(value: float) -> str:
    return f"£{value:,.2f}"


def plot(fig, key: str):
    st.plotly_chart(fig, width="stretch", key=key, config={"displaylogo": False})


def download(label: str, frame: pd.DataFrame, filename: str, key: str):
    st.download_button(label, data=csv_bytes(frame), file_name=filename,
                       mime="text/csv", key=key, on_click="ignore")


def title(text: str, description: str):
    st.subheader(text)
    st.caption(description)


def kpis(sales: pd.DataFrame):
    metrics = sales_kpis(sales)
    labels = [("Positive sales revenue", money(metrics["Revenue"])),
              ("Distinct sales invoices", f"{metrics['Invoices']:,}"),
              ("Known purchasing customers", f"{metrics['Customers']:,}"),
              ("Average invoice value", money(metrics["AverageInvoice"]))]
    for column, (label, value) in zip(st.columns(4), labels):
        column.metric(label, value, border=True)


def countries(sales: pd.DataFrame) -> pd.DataFrame:
    return sales.groupby("Country", observed=True).TotalPrice.sum().sort_values(ascending=False).rename("Revenue").reset_index()


def executive(sales: pd.DataFrame, ledger: pd.DataFrame, bundle: AnalysisBundle):
    kpis(sales)
    st.caption("Revenue is positive sales before refunds. Invoice value covers only the selected lines of each invoice.")
    monthly = monthly_sales(sales)
    geographic = countries(sales)
    left, right = st.columns([1.55, 1])
    with left:
        title("Revenue over time", "Monthly positive sales · GBP")
        plot(line(monthly, "Month", "Revenue", True), "overview_monthly")
    with right:
        title("Leading markets", "Top 8 countries by positive revenue")
        plot(bar(geographic.head(8), "Revenue", "Country", True, True), "overview_countries")
    left, right = st.columns([1, 1.55])
    with left:
        title("Revenue mix", "Share across all countries in the selection")
        mix = geographic.head(6).copy()
        if len(geographic) > 6:
            mix = pd.concat([mix, pd.DataFrame({"Country": ["Other selected markets"], "Revenue": [geographic.iloc[6:].Revenue.sum()]})], ignore_index=True)
        fig = px.pie(mix, names="Country", values="Revenue", hole=.65, color_discrete_sequence=PALETTE)
        fig.update_traces(textposition="inside", textinfo="percent", hovertemplate="%{label}<br>GBP %{value:,.2f}<br>%{percent}<extra></extra>")
        fig.update_layout(showlegend=False)
        plot(style(fig), "overview_mix")
    with right:
        title("Invoice activity", "Distinct positive-sales invoices per month")
        plot(bar(monthly, "Month", "Invoices"), "overview_invoices")
    title("How concentrated is revenue?", "Stock-code contribution; service codes remain included unless filtered out")
    plot(pareto(product_summary(sales)), "overview_pareto")
    download("Download monthly summary", monthly, "retailpulse_monthly.csv", "overview_export")


def sales_analytics(sales: pd.DataFrame, ledger: pd.DataFrame, bundle: AnalysisBundle):
    performance, returns_tab = st.tabs(["Sales performance", "Returns & reconciliation"])
    with performance:
        kpis(sales)
        monthly = monthly_sales(sales)
        a, b = st.columns(2)
        with a:
            title("Monthly revenue", "GBP · positive sales before refunds")
            plot(line(monthly, "Month", "Revenue", True), "sales_monthly")
        with b:
            title("Monthly invoice volume", "Distinct invoices in each month")
            plot(bar(monthly, "Month", "Invoices"), "sales_volume")
        title("Average invoice value", "Selected revenue / selected distinct invoices in each month")
        plot(line(monthly, "Month", "AverageInvoice", True), "sales_aiv")
        products = product_summary(sales).reset_index()
        products["Product"] = products.StockCode.astype(str) + " · " + products.Description.astype(str)
        a, b = st.columns(2)
        with a:
            title("Top products by units", "Use the item category filter to separate merchandise and service codes")
            plot(bar(products.nlargest(10, "Units"), "Units", "Product", True), "sales_products")
        with b:
            title("Country sales", "Positive revenue · GBP")
            plot(bar(countries(sales).head(10), "Revenue", "Country", True, True), "sales_country")
        a, b = st.columns(2)
        with a:
            title("Product revenue distribution", "All stock-code totals; logarithmic revenue axis")
            fig = px.histogram(products, x="Revenue", nbins=45, log_x=True, color_discrete_sequence=PALETTE)
            plot(style(fig), "sales_distribution")
        with b:
            title("Revenue concentration", "Cumulative share of stock-code revenue")
            plot(pareto(products), "sales_pareto")
        title("Merchandise and non-merchandise", "Classification is documented; ambiguous codes remain Unknown")
        category = sales.groupby("Category", observed=True).agg(Revenue=("TotalPrice", "sum"), Lines=("InvoiceNo", "size")).reset_index()
        st.dataframe(category, hide_index=True, width="stretch")
        download("Download filtered sales", sales, "retailpulse_filtered_sales.csv", "sales_export")
        download("Download product summary", products, "retailpulse_products.csv", "products_export")
    with returns_tab:
        financials = revenue_metrics(ledger, sales)
        for column, label, key in zip(st.columns(3),
            ["Gross positive sales", "Recorded credit / return value", "Net recorded transaction value"],
            ["gross_positive_sales_gbp", "recorded_credit_return_value_gbp", "net_recorded_transaction_value_gbp"]):
            column.metric(label, money(financials[key]), border=True)
        st.info("Net recorded value is the signed sum of finite deduplicated source line values in the selection. "
                "It is not profit or an accounting revenue statement. Credits can refer to sales outside the selected dates.")
        bridge = pd.DataFrame({"Component": ["Gross positive sales", "Recorded negative values", "Other signed value", "Net recorded value"],
            "GBP": [financials["gross_positive_sales_gbp"], -financials["recorded_credit_return_value_gbp"],
                    financials["other_signed_value_gbp"], financials["net_recorded_transaction_value_gbp"]]})
        fig = go.Figure(go.Waterfall(x=bridge.Component, y=bridge.GBP,
            measure=["relative", "relative", "relative", "total"],
            increasing=dict(marker_color=PALETTE[0]), decreasing=dict(marker_color=PALETTE[2]), totals=dict(marker_color=PALETTE[1])))
        plot(style(fig), "revenue_bridge")
        st.caption("Gross − recorded negative values + other signed value = net recorded value. "
                   "Other signed value covers finite lines excluded from the positive-sales view. "
                   "The credit/return figure includes negative-price adjustments; overlapping flags are never summed twice.")
        matches = bundle.returns.loc[bundle.returns.ReturnLineID.isin(ledger.LineID)]
        title("Conservative return reconciliation", "Matches are computed on the complete ledger before filters; uncertain links remain unmatched")
        a, b = st.columns(2)
        a.metric("Matched return records", f"{matches.Status.eq('Matched').sum():,}")
        b.metric("Unmatched return records", f"{matches.Status.eq('Unmatched').sum():,}")
        st.caption("Matching requires a unique earlier customer + stock code + unit-price sales line with enough "
                   "remaining quantity. A credit note does not by itself prove a link to an original invoice.")
        st.dataframe(matches.head(200), hide_index=True, width="stretch")
        download("Download scoped return report", matches, "retailpulse_returns.csv", "returns_export")
        download("Download revenue reconciliation", bridge, "retailpulse_revenue_bridge.csv", "bridge_export")


def segmentation(sales: pd.DataFrame, ledger: pd.DataFrame, bundle: AnalysisBundle):
    rfm = bundle.rfm if len(sales) == len(bundle.sales) else build_rfm(sales)
    if rfm.empty:
        st.info("No identified customers in this selection. Anonymous sales still contribute to sales totals.")
        return
    st.caption("RFM uses the existing scoring rules, recalculated within the selected scope. "
               "With all filters cleared, segments match the original project. Spend and frequency below cover this selection.")
    report = segment_report(sales, rfm)
    counts = rfm.Segment.value_counts()
    cols = st.columns(5)
    cols[0].metric("Identifiable customers", f"{len(rfm):,}", border=True)
    for column, name in zip(cols[1:], SEGMENT_ACTIONS):
        column.metric(name.title(), f"{counts.get(name, 0):,}", border=True)
    a, b = st.columns(2)
    with a:
        title("Segment revenue", "Identified-customer positive sales only")
        plot(bar(report, "Segment", "Revenue", currency=True), "segments_revenue")
    with b:
        title("Average invoice value by segment", "Segment spending / sum of customer invoice counts")
        plot(bar(report, "Segment", "AverageInvoice", currency=True), "segments_aiv")
    a, b = st.columns(2)
    with a:
        title("Customer distribution", "Identified customers by RFM group")
        fig = px.pie(report, names="Segment", values="Customers", hole=.6, color_discrete_sequence=PALETTE)
        fig.update_traces(textinfo="percent+label", hovertemplate="%{label}<br>%{value:,} customers<br>%{percent}<extra></extra>")
        fig.update_layout(showlegend=False)
        plot(style(fig), "segments_customers")
    with b:
        title("Average customer spending", "Positive revenue per customer, not per invoice")
        plot(bar(report, "Segment", "AverageSpending", currency=True), "segments_spending")
    title("Customer segment explorer", "Choose a group to inspect its behavior and download its anonymous identifiers")
    selected = st.selectbox("Segment", ["All segments", *SEGMENT_ACTIONS], key="segment")
    customers = rfm if selected == "All segments" else rfm.loc[rfm.Segment.eq(selected)]
    if selected != "All segments":
        st.info(SEGMENT_MEANINGS[selected])
        st.write("**Suggested experiment:** " + SEGMENT_ACTIONS[selected])
    else:
        st.caption("Select a segment for suggested experiments. The dataset contains no marketing campaign outcomes.")
    if customers.empty:
        st.info("No customers belong to this segment under the current filters.")
    else:
        for column, label, value in zip(st.columns(4),
            ["Selected customers", "Spending in selection", "Average customer spending", "Average invoice frequency"],
            [f"{len(customers):,}", money(customers.Monetary.sum()), money(customers.Monetary.mean()), f"{customers.Frequency.mean():.2f}"]):
            column.metric(label, value, border=True)
        a, b, c = st.columns(3)
        for column, field, label in [(a, "Recency", "Recency (days)"), (b, "Frequency", "Frequency (invoices)"), (c, "Monetary", "Spending (GBP)")]:
            with column:
                title(label, "Selected segment · uncapped values")
                fig = px.histogram(customers, x=field, nbins=35, color_discrete_sequence=PALETTE)
                plot(style(fig, 270), "rfm_" + field)
        st.dataframe(customers.reset_index(), hide_index=True, width="stretch")
    download("Download selected customers", customers.reset_index(), "retailpulse_customer_segment.csv", "segment_export")
    st.dataframe(report, hide_index=True, width="stretch")
    download("Download segment comparison", report, "retailpulse_segments.csv", "segment_report_export")
    with st.expander("What each segment means"):
        for name in SEGMENT_ACTIONS:
            st.write(f"**{name}** — {SEGMENT_MEANINGS[name]} {SEGMENT_ACTIONS[name]}")
        st.caption("These labels suggest experiments; they do not predict future churn or prove campaign effectiveness.")


def retention(sales: pd.DataFrame, ledger: pd.DataFrame, bundle: AnalysisBundle):
    matrix, sizes, activity = retention_tables(sales)
    if matrix.empty:
        st.info("No identified customers are available for retention analysis in this selection.")
        return
    frequency = sales.dropna(subset=["CustomerID"]).groupby("CustomerID").InvoiceNo.nunique()
    a, b, c = st.columns(3)
    a.metric("Repeat purchasing customers", f"{frequency.gt(1).mean():.2%}", border=True)
    b.metric("Observed cohorts", f"{len(sizes):,}", border=True)
    c.metric("Known active customers", f"{len(frequency):,}", border=True)
    st.info("Cohorts are based on the first purchase observed within the current filters, not necessarily "
            "the customer's first-ever purchase. Blank cells are future months; zero means no activity in an observed month.")
    title("Cohort retention", "Share of each cohort purchasing in a later month")
    plot(retention_heatmap(matrix), "retention_heatmap")
    st.caption("Boundary months may be incomplete under the selected date range. December 2011 ends on the ninth. "
               "Historical return-purchase patterns do not establish future churn probabilities.")
    a, b = st.columns(2)
    with a:
        title("Monthly active customers", "Distinct known customers making a valid purchase")
        plot(line(activity, "Month", "Customers"), "retention_activity")
    with b:
        title("Cohort sizes", "Customers grouped by their first observed purchase month")
        plot(bar(sizes, "Cohort", "Customers"), "retention_sizes")
    download("Download retention matrix", matrix.rename_axis("Cohort").reset_index(), "retailpulse_retention.csv", "retention_export")
    download("Download cohort sizes", sizes, "retailpulse_cohort_sizes.csv", "cohort_sizes_export")


def data_quality(sales: pd.DataFrame, ledger: pd.DataFrame, bundle: AnalysisBundle):
    audit = bundle.audit
    st.info("The source audit and duplicate sensitivity below describe the complete workbook and stay fixed "
            "when filters change. The coverage metrics immediately below use your current selection.")
    gross = sales.TotalPrice.sum()
    identifiable = sales.loc[sales.CustomerID.notna(), "TotalPrice"].sum()
    a, b, c = st.columns(3)
    a.metric("Selected positive sales lines", f"{len(sales):,}", border=True)
    b.metric("Identifiable revenue coverage", f"{identifiable/gross:.2%}" if gross else "0.00%", border=True)
    c.metric("Selected anonymous sales lines", f"{sales.CustomerID.isna().sum():,}", border=True)
    title("Source cleaning audit", "Original workbook → exact deduplication → valid positive sales")
    for column, label, key in zip(st.columns(4),
        ["Original records", "Exact duplicates", "Excluded after deduplication", "Valid sales lines"],
        ["source_rows", "duplicate_rows", "invalid_or_cancelled_rows_excluded", "valid_sales_rows"]):
        column.metric(label, f"{audit[key]:,}", border=True)
    funnel = go.Figure(go.Funnel(y=["Source records", "After exact deduplication", "Valid positive sales"],
        x=[audit["source_rows"], audit["deduplicated_rows"], audit["valid_sales_rows"]],
        marker=dict(color=["#334E68", "#55A9B2", "#087F8C"]), textinfo="value+percent initial"))
    plot(style(funnel, 300), "quality_funnel")
    reasons = pd.DataFrame({"Source condition (overlapping)": ["Missing customer ID", "Credit-note invoice", "Non-positive quantity", "Non-positive price"],
        "Rows": [audit["missing_customer_rows"], audit["cancellation_rows"], audit["nonpositive_quantity_rows"], audit["nonpositive_price_rows"]]})
    st.dataframe(reasons, hide_index=True, width="stretch")
    st.caption("These source conditions overlap and must not be added. Missing customer IDs are not a sales exclusion. "
               "The exclusive reconciliation is source rows = duplicates + valid sales + excluded deduplicated rows.")
    a, b = st.columns(2)
    with a:
        title("Cancellation / quantity overlap", "Deduplicated records · complete workbook")
        full = bundle.ledger
        overlap = pd.DataFrame({"Condition": ["Cancellation only", "Negative quantity only", "Both flags"], "Rows": [
            int((full.IsCancellation & ~full.IsNegativeQuantity).sum()),
            int((~full.IsCancellation & full.IsNegativeQuantity).sum()),
            int((full.IsCancellation & full.IsNegativeQuantity).sum())]})
        st.dataframe(overlap, hide_index=True, width="stretch")
    with b:
        title("Duplicate sensitivity", "Same positive-sales rules; only the exact duplicate policy changes")
        st.dataframe(bundle.sensitivity, hide_index=True, width="stretch")
        difference = bundle.sensitivity.GrossPositiveSalesGBP.iloc[1] - bundle.sensitivity.GrossPositiveSalesGBP.iloc[0]
        st.caption(f"Keeping exact duplicates increases positive sales by {money(difference)}. "
                   "An invoice-line identifier is unavailable, so some identical lines could be genuine repeats.")
    with st.expander("Cleaning rules and limitations"):
        st.write("Raw source rows are preserved. Exact duplicates are removed on a copy. Valid sales require a non-cancelled "
                 "invoice, positive finite quantity × price, valid date, and present invoice/stock identifiers. "
                 "Missing customer IDs are never imputed. Negative rows stay in the separate ledger. "
                 "Non-merchandise classification uses documented code/description rules; standard catalog patterns "
                 "are a heuristic and ambiguous codes remain Unknown.")
    download("Download source audit", pd.DataFrame([audit]), "retailpulse_source_audit.csv", "quality_export")
    download("Download duplicate sensitivity", bundle.sensitivity, "retailpulse_duplicate_sensitivity.csv", "sensitivity_export")

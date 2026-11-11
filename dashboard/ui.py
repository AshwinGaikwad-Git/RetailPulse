"""Application shell, cached source loading and shared interactive filters."""
from __future__ import annotations

import logging
import threading
from pathlib import Path

import streamlit as st

from dashboard import pages
from src.analytics import filter_transactions
from src.classification import CATEGORIES
from src.data_cleaning import locate_workbook
from src.finance import revenue_metrics
from src.reporting import AnalysisBundle, load_analysis

LOGGER = logging.getLogger(__name__)
VIEWS = {
    "Executive Overview": ("Your retail business, in focus.", "Sales, markets and product concentration at a glance.", pages.executive),
    "Sales Analytics": ("Understand what drives sales.", "Explore product performance, markets and recorded returns.", pages.sales_analytics),
    "Customer Segmentation": ("Understand your customer segments.", "Explore established RFM groups and plan measurable retention experiments.", pages.segmentation),
    "Customer Retention": ("See who comes back.", "Cohort activity and repeat purchases across the observed window.", pages.retention),
    "Data Quality": ("Trust starts with the source.", "A transparent audit of cleaning decisions, exclusions and coverage.", pages.data_quality),
}
CSS = """
<style>
.stApp { background: #F6F8FB; }
.block-container { padding-top: 5rem; padding-bottom: 3rem; max-width: 1450px; }
[data-testid="stSidebar"] { background: #EDF2F7; border-right: 1px solid #DAE3EC; }
h1, h2, h3 { color: #183B56; letter-spacing: -.035em; }
h1 { font-size: 2.35rem !important; }
h3 { font-size: 1.15rem !important; margin-top: .65rem; }
[data-testid="stMetric"] { background: white; border-color: #E0E7EF; border-radius: 12px; padding: 1rem; }
[data-testid="stMetricValue"] { font-size: clamp(1.1rem, 1.8vw, 1.85rem); color: #123C4A; }
[data-testid="stMetricLabel"] { color: #486174; font-size: .8rem; }
[data-testid="stPlotlyChart"] { background: white; border: 1px solid #E4EBF2; border-radius: 12px; padding: .4rem; }
.eyebrow { color: #087F8C; font-size: .73rem; font-weight: 700; letter-spacing: .13em; text-transform: uppercase; }
.brand { font-size: 1.7rem; color: #123C4A; font-weight: 800; letter-spacing: -.06em; }
.brand span { color: #087F8C; }
.brand-note { color: #526A7D; font-size: .8rem; margin-bottom: 1.4rem; }
@media (max-width: 700px) {
 .block-container { padding: 5rem .8rem 1.2rem; }
 h1 { font-size: 1.8rem !important; }
 [data-testid="stMetricValue"] { font-size: 1.5rem; }
}
</style>
"""


@st.cache_resource(show_spinner=False, max_entries=1)
def cached_analysis(workbook: str, modified_ns: int, size: int) -> AnalysisBundle:
    """Cache a shared read-only bundle; source changes invalidate it automatically."""
    return load_analysis(Path(workbook))


@st.cache_resource(show_spinner=False)
def initialization_lock():
    return threading.RLock()


def get_bundle() -> AnalysisBundle:
    # Serialize cold downloads as well as initialization across simultaneous sessions.
    with initialization_lock():
        workbook = locate_workbook()
        stat = workbook.stat()
        return cached_analysis(str(workbook), stat.st_mtime_ns, stat.st_size)


def main():
    st.set_page_config(page_title="RetailPulse | Retail Analytics", page_icon="📊", layout="wide",
                       initial_sidebar_state="expanded")
    st.markdown(CSS, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown('<div class="brand">Retail<span>Pulse</span></div><div class="brand-note">RETAIL ANALYTICS & CUSTOMER INTELLIGENCE</div>', unsafe_allow_html=True)
        requested = st.query_params.get("page", "Executive Overview")
        default = list(VIEWS).index(requested) if requested in VIEWS else 0
        view = st.radio("Workspace", list(VIEWS), index=default, key="view")
    try:
        with st.spinner("Preparing the UCI workbook, sales ledger and customer insights. First load may take a minute…"):
            bundle = get_bundle()
    except Exception:
        LOGGER.exception("RetailPulse could not initialize the source workbook")
        st.error("The retail dataset could not be loaded. No sample metrics have been substituted.")
        st.info("Check your internet connection or download the official UCI archive, extract Online Retail.xlsx "
                "into dataset/, then retry. See README.md for setup instructions.")
        st.link_button("Open the official UCI dataset", "https://archive.ics.uci.edu/dataset/352/online+retail")
        if st.button("Retry loading"):
            st.rerun()
        return

    with st.sidebar:
        st.divider()
        st.markdown("**Refine your view**")
        minimum = bundle.ledger.InvoiceDate.min().date()
        maximum = bundle.ledger.InvoiceDate.max().date()
        dates = st.date_input("Date range", value=(minimum, maximum), min_value=minimum, max_value=maximum, key="dates")
        countries = st.multiselect("Country", sorted(bundle.ledger.Country.dropna().unique()), placeholder="All countries", key="countries")
        categories = st.multiselect("Item category", CATEGORIES, default=CATEGORIES, key="categories")
        stocks = sorted(bundle.ledger.StockCode.dropna().unique())
        selected_stocks = st.multiselect("Stock code", stocks, placeholder="All stock codes", key="stocks",
                                         help="Search by the original product/stock code. Product names are in Sales Analytics.")
        st.caption("Empty country/stock selections mean all. Clear all item categories to see the empty state.")
        if st.button("Reset filters", width="stretch"):
            for key in ["dates", "countries", "categories", "stocks", "segment"]:
                st.session_state.pop(key, None)
            st.rerun()
        st.divider()
        st.caption("UCI Online Retail · 2010–2011\n\nHistorical analysis · GBP\n\nSource: Chen (2015), CC BY 4.0")
    if len(dates) != 2:
        st.info("Choose an end date to complete the reporting range.")
        return
    filters = dict(start=dates[0], end=dates[1], countries=countries or None,
                   stocks=selected_stocks or None, categories=categories)
    sales = filter_transactions(bundle.sales, **filters)
    ledger = filter_transactions(bundle.ledger, **filters)
    headline, subtitle, render = VIEWS[view]
    st.markdown('<div class="eyebrow">Retail intelligence / ' + view + '</div>', unsafe_allow_html=True)
    st.title(headline)
    st.write(subtitle)
    st.caption(f"{dates[0]:%d %b %Y} — {dates[1]:%d %b %Y}  ·  {len(sales):,} positive sales lines in selection  ·  GBP")
    st.warning("December 2011 is incomplete: the source ends on 9 December. Compare complete reporting periods. "
               "Positive sales revenue is before refunds and is not profit.", icon="📅")
    if sales.empty and view != "Data Quality":
        st.info("No positive sales match these filters. Broaden the date range, countries, stock codes or item categories.")
        if not ledger.empty and view == "Sales Analytics":
            values = revenue_metrics(ledger, sales)
            st.metric("Net recorded value in the return-only selection", pages.money(values["net_recorded_transaction_value_gbp"]))
            scoped = bundle.returns.loc[bundle.returns.ReturnLineID.isin(ledger.LineID)]
            pages.download("Download scoped return report", scoped, "retailpulse_returns.csv", "empty_returns_export")
        return
    render(sales, ledger, bundle)
    st.divider()
    st.caption("RetailPulse · Descriptive historical analytics. Customer IDs are source pseudonymous identifiers; "
               "no names, emails or contact details are shown. Findings are hypotheses for investigation.")

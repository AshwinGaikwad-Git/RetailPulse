# Validation and implementation report

Validated locally on Windows with Python 3.12.14 on 12 November 2026. This report distinguishes
executed local checks from configuration supplied for later hosting.

## What was preserved

- `src/data_cleaning.py` and its established cleaning, RFM, product and cohort functions.
- The source workbook, original six CSV output tables and 11 generated charts.
- The existing notebook, re-executed with saved outputs; all 11 code cells completed.
- All 10 original regression tests.
- The earlier PDF walkthrough and its report-generation script.

The original outputs were regenerated from the same workbook, not removed or replaced with
synthetic data. The additional UI and financial modules reuse original analytical functions.

## Files created

- `streamlit_app.py`, `dashboard/__init__.py`, `dashboard/ui.py`, `dashboard/pages.py`,
  `dashboard/charts.py`: five-page application, filters, caching, charts and downloads.
- `src/__init__.py`, `src/analytics.py`, `src/classification.py`, `src/finance.py`,
  `src/reporting.py`: focused analytical extensions and report export.
- `tests/test_retailpulse.py`, `tests/test_dashboard.py`: additional analytical and interaction checks.
- `scripts/capture_dashboard.py`, `scripts/verify_results.py`, `scripts/validate_project.py`:
  browser capture, real-data consistency and end-to-end validation.
- `requirements-app.txt`, `requirements-dev.txt`: runtime and optional browser tooling.
- `.streamlit/config.toml`, `.github/workflows/ci.yml`, `Dockerfile`, `.dockerignore`:
  portable local/hosted setup and CI configuration.
- `assets/screenshots/`: actual screenshots of the running app, including mobile and filters.
- `docs/methodology.md`, `docs/deployment.md`, this report, and `LICENSE`.
- Additional generated outputs in `dataset/`: segment summary, category revenue, product
  classification, duplicate sensitivity, return matches and financial summary JSON.

## Files modified

- `README.md`: portfolio presentation, actual screenshots, results, methodology and commands.
- `requirements.txt`: application dependencies plus existing notebook tools.
- `requirements-lock.txt`: universal Python 3.12 lock with operating-system markers.
- `.gitignore`: secrets, temporary download files, caches and local reports.
- `notebooks/online_retail_analysis.ipynb`: refreshed execution outputs; existing analysis retained.
- Original generated CSVs, charts and `analysis_summary.json`: regenerated and reconciled.

## Executed checks

| Check | Local outcome |
|---|---|
| Original baseline tests | 10 passed before implementation |
| Full final unittest suite | 30 passed, 0 failures |
| Streamlit interaction tests | All five views; country/date/stock filters; reset; empty and anonymous selections; load-failure state passed |
| Dependency compatibility | `python -m pip check`: no broken requirements |
| Imports / compilation | Source, dashboard and scripts compile successfully |
| Original standalone pipeline | Executed successfully on the real workbook |
| Existing notebook | All 11 code cells re-executed without notebook error outputs |
| Extended reports | Generated from the real workbook |
| Numerical checks | Baseline, row reconciliation, sales/product/monthly totals, customer/segment totals, financial bridge and unique refunds passed |
| Dashboard startup | Local server health endpoint returned `ok`; real browser loaded analytical results |
| Real browser | Five views, exact France revenue KPI, four CSV downloads and mobile overflow checks passed |
| Visual review | Actual screenshots reviewed; header spacing, grouped country shares and cohort labels refined |

Test fixtures exist only within the test suite and never substitute for the real source in the UI.
The failure-state test intentionally mocks an offline source. Streamlit's bare-mode context
warnings during AppTest and the local notebook kernel transport warning did not prevent execution.

The final real-browser export checks verified 10,589 unique return records, 1,299 Champions
with no other segment in that customer export, the original 541,909-record audit, and filtered
monthly revenue summing to France's GBP 209,625.37 KPI. The 390px mobile viewport rendered
without horizontal main-content overflow. Eight genuine screenshots are stored in assets.

## Verified analytical results

| Metric | Verified value |
|---|---:|
| Original transaction lines | 541,909 |
| Exact duplicate rows | 5,268 |
| Valid positive sales lines | 524,878 |
| Gross positive sales | GBP 10,642,110.804 |
| Distinct sales invoices | 19,960 |
| Known purchasing customers | 4,338 |
| Recorded negative transaction value | GBP 916,103.85 |
| Net recorded transaction value | GBP 9,726,006.954 |
| Merchandise-classified positive revenue | GBP 10,246,820.87 |
| Other categories' positive revenue | GBP 395,289.934 |
| Matched return records | 4,802 |
| Unmatched return records | 5,787 |
| Recorded credit value on matched records | GBP 383,572.87 |
| Recorded credit value on unmatched records | GBP 532,530.98 |
| Positive revenue with exact duplicates retained | GBP 10,666,684.544 |

The unchanged default RFM populations are Champions 1,299; Loyal customers 515; At risk 565;
Needs attention 1,959. Exact duplicates retained would add GBP 24,573.74 to positive sales;
that sensitivity scenario is not the default methodology.

## Run and deploy

```
python -m streamlit run streamlit_app.py
```

Streamlit Community Cloud configuration is prepared: choose this entry point, Python 3.12,
root dependencies and outbound access to UCI. See `docs/deployment.md` for manual steps.
No public deployment, GitHub push or remote CI run has been performed. Docker is unavailable
in the local environment, so the supplied Dockerfile has not been built or run here.

## Remaining limitations and priorities

1. Matches are conservative candidate links; the source has no original-invoice reference on
   credits. Do not force ambiguous, absent or oversized returns into a guessed sale.
2. Standard catalog codes are a disclosed merchandise heuristic. Resolve Unknown and exceptional
   descriptions using retailer evidence before accounting or inventory decisions.
3. Net recorded value is a signed transaction sum, not profit or audited net revenue.
4. Date/product filters change analytical scope; they do not restore an unobserved customer history.
5. December 2011 and selected boundary months can be partial; historical patterns do not prove churn.
6. Host memory/cold-start behavior and Docker execution require validation on the target service.

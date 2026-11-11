# Local and deployment guide

## Local

Use Python 3.12. Create a virtual environment and install `requirements-lock.txt` for the
tested full analytical stack, or `requirements-app.txt` for dashboard-only runtime.
Run `python -m streamlit run streamlit_app.py` from the repository root. The entry point
uses file-relative source paths, not Windows-specific hardcoded paths.

The first browser session loads the workbook once and builds a cached, read-only analytical
bundle. A changed workbook size or modification time invalidates the cache. Filters operate
on copies. Nothing is uploaded to a third-party analytics service by the app.

The original source workbook is ~23 MB. Source and output CSVs are Git-ignored. On a fresh
checkout, the loader downloads the official UCI archive and extracts the expected workbook.
Cold start may take a minute or more depending on network and CPU. If downloads fail, the UI
shows a recovery message and source link, never invented data. Manually place `Online Retail.xlsx`
in `dataset/` when needed. No API key or secret is required.

## Streamlit Community Cloud (prepared, not deployed)

1. Review the repository, license and screenshots. Push to your GitHub repository yourself
   only when ready; no push or deployment has been performed by this implementation.
2. Create a Streamlit Community Cloud app from that repository and branch.
3. Choose `streamlit_app.py` as the entry point and Python 3.12 in Advanced settings.
4. The service reads the root `requirements.txt` and `.streamlit/config.toml`.
5. Allow outbound HTTPS to `archive.ics.uci.edu` for first-run source initialization.
6. Verify the five pages, reset filters, downloaded CSVs and baseline metrics on the live app.
7. Replace the README live-demo placeholder only after that URL works and has been verified.

The cached ledger, source loading and rendering need memory. Resource use depends on host,
sessions and exports. A deployment configuration is provided, but hosted memory limits and
network policy have not been validated on a live service. No Linux-specific path assumptions
are required. The universal lock file includes platform markers for Windows-only packages.

## Container option (configuration supplied)

```
docker build -t retailpulse .
docker run --rm -p 8501:8501 retailpulse
```

Optionally mount a local dataset folder as `/app/dataset` for an offline workbook. The container
only installs app dependencies and does not copy local workbooks, virtual environments or
secrets. Docker build/run must be verified on a machine with Docker; see the validation report
for whether this was executed locally.

## Checks before publishing

```
python -m unittest discover -s tests -v
python -m pip check
python src/data_cleaning.py
python -m src.reporting
python scripts/verify_results.py
```

The CI workflow runs deterministic tests and imports on push/PR. Its manually triggered second
job downloads the real source and verifies generated results; routine PRs do not depend on UCI
availability. CI has been configured, but no GitHub-hosted run is claimed until the workflow
is actually pushed and executed.

For screenshot reproduction, install `requirements-dev.txt`, run
`python -m playwright install chromium`, start the dashboard locally and run
`python scripts/capture_dashboard.py`. Those screenshots come from the actual app.

Official references:
- [Deploy an app](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
- [App dependencies](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)

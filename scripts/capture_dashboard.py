"""Validate a running local app and capture genuine screenshots (optional Playwright).

Start Streamlit first. Run: python scripts/capture_dashboard.py
"""
from pathlib import Path
import json
import csv
import io
import math
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
VIEWS = [
    ("Executive Overview", "executive-overview"),
    ("Sales Analytics", "sales-analytics"),
    ("Customer Segmentation", "customer-segmentation"),
    ("Customer Retention", "customer-retention"),
    ("Data Quality", "data-quality"),
]


with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    context = browser.new_context(viewport={"width": 1500, "height": 1150}, device_scale_factor=1)
    page = context.new_page()
    def settled():
        page.wait_for_timeout(400)
        page.wait_for_function("document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state') === 'notRunning'", timeout=180000)
    def top():
        page.get_by_test_id("stMain").evaluate("element => element.scrollTop = 0")
        page.wait_for_timeout(200)
    page.goto("http://127.0.0.1:8501", wait_until="domcontentloaded")
    page.get_by_test_id("stMetricValue").first.wait_for(timeout=240000)
    settled()
    assert page.get_by_test_id("stMetricValue").first.inner_text() == "£10,642,110.80"
    assert page.get_by_test_id("stException").count() == 0
    for label, filename in VIEWS:
        page.get_by_test_id("stSidebar").get_by_text(label, exact=True).click()
        settled()
        page.get_by_test_id("stMetricValue").first.wait_for(timeout=30000)
        assert page.get_by_test_id("stException").count() == 0, label
        top()
        page.screenshot(path=str(OUT / f"{filename}.png"))
        print("Captured", label, flush=True)
        if label == "Sales Analytics":
            page.get_by_role("tab", name="Returns & reconciliation").click()
            page.wait_for_timeout(500)
            page.screenshot(path=str(OUT / "returns-reconciliation.png"))
            with page.expect_download() as event:
                page.get_by_role("button", name="Download scoped return report", exact=True).click()
            path = OUT / "return-download-check.csv"
            event.value.save_as(str(path))
            rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
            assert len(rows) == 10589 and len({r['ReturnLineID'] for r in rows}) == len(rows)
            path.unlink()
        if label == "Customer Segmentation":
            selector = page.get_by_test_id("stSelectbox").locator("input")
            selector.click()
            selector.press("ArrowDown")
            selector.press("Enter")
            settled()
            with page.expect_download() as event:
                page.get_by_role("button", name="Download selected customers", exact=True).click()
            path = OUT / "customer-download-check.csv"
            event.value.save_as(str(path))
            rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
            assert len(rows) == 1299 and all(r['Segment'] == 'Champions' for r in rows)
            path.unlink()
    # A real download must contain exactly the audit represented by the app.
    with page.expect_download() as event:
        page.get_by_role("button", name="Download source audit", exact=True).click()
    download_path = OUT / "download-check.csv"
    event.value.save_as(str(download_path))
    assert "541909" in download_path.read_text(encoding="utf-8-sig")
    download_path.unlink()
    # Test a live country filter and verify its scoped data export.
    page.get_by_test_id("stSidebar").get_by_text("Executive Overview", exact=True).click()
    settled()
    country = page.get_by_test_id("stMultiSelect").filter(has=page.get_by_text("Country", exact=True))
    country.locator("input").fill("France")
    page.get_by_role("option", name="France", exact=True).click()
    page.keyboard.press("Escape")  # Multi-select stays open; close it before interacting with page controls.
    settled()
    assert page.get_by_test_id("stMetricValue").first.inner_text() == "£209,625.37"
    with page.expect_download() as event:
        page.get_by_role("button", name="Download monthly summary", exact=True).click()
    path = OUT / "monthly-download-check.csv"
    event.value.save_as(str(path))
    rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    assert math.isclose(sum(float(r['Revenue']) for r in rows), 209625.37, abs_tol=1e-6)
    path.unlink()
    top()
    page.screenshot(path=str(OUT / "filtered-france.png"))
    # Mobile: close the sidebar if expanded and check the main page has no horizontal overflow.
    page.set_viewport_size({"width": 390, "height": 844})
    collapse = page.get_by_test_id("stSidebarCollapseButton").locator("button")
    if collapse.is_visible():
        collapse.click()
    page.wait_for_timeout(700)
    top()
    page.screenshot(path=str(OUT / "mobile.png"))
    assert page.get_by_test_id("stException").count() == 0
    bounds = page.get_by_test_id("stMain").evaluate("e => ({scroll: e.scrollWidth, client: e.clientWidth})")
    assert bounds['scroll'] <= bounds['client'] + 1, bounds
    print(json.dumps({"pages": 5, "audit_download": "passed", "returns_download": "passed", "segment_download": "passed", "filtered_monthly_download": "passed", "country_filter": "passed", "mobile": "passed"}), flush=True)
    browser.close()

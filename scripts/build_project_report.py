"""Build the project walkthrough PDF from saved analytical results.

Optional report tools: python -m pip install reportlab pypdf
Run from the project root: python scripts/build_project_report.py
"""
import json
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "Python_EDA_Project_Walkthrough.pdf"
M = json.loads((ROOT / "analysis_summary.json").read_text(encoding="utf-8"))
NAVY = colors.HexColor("#16324F")
TEAL = colors.HexColor("#087E8B")
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="ReportTitle", fontName="Helvetica-Bold", fontSize=28,
                          leading=33, textColor=NAVY, spaceAfter=16))
styles.add(ParagraphStyle(name="ReportHeading", fontName="Helvetica-Bold", fontSize=18,
                          leading=23, textColor=NAVY, spaceAfter=12))
styles.add(ParagraphStyle(name="ReportBody", fontName="Helvetica", fontSize=10,
                          leading=15, spaceAfter=9))
styles.add(ParagraphStyle(name="ReportSmall", fontName="Helvetica", fontSize=8,
                          leading=11, textColor=colors.HexColor("#526273"), spaceAfter=7))
styles.add(ParagraphStyle(name="ReportCell", fontName="Helvetica", fontSize=9,
                          leading=12, alignment=TA_LEFT))
story = []


def paragraph(text, style="ReportBody"):
    story.append(Paragraph(text, styles[style]))


def heading(text):
    paragraph(text, "ReportHeading")


def table(headers, rows, widths):
    data = [[Paragraph(escape(str(v)), styles["ReportCell"]) for v in row]
            for row in [headers, *rows]]
    result = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDECF0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7FA")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, 0), 1, TEAL),
    ]))
    story.extend([result, Spacer(1, 12)])


def chart(name, max_height=190):
    path = ROOT / "visualizations" / name
    width, height = ImageReader(str(path)).getSize()
    scale = min(499 / width, max_height / height)
    story.append(Image(str(path), width=width * scale, height=height * scale))
    story.append(Spacer(1, 6))


def new_page(title):
    story.append(PageBreak())
    heading(title)


def footer(canvas, document):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D4DEE7"))
    canvas.line(48, 43, A4[0] - 48, 43)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(NAVY)
    canvas.drawString(48, 29, "Python EDA Project | Online Retail")
    canvas.drawRightString(A4[0] - 48, 29, f"{document.page}")
    canvas.restoreState()


paragraph("PROJECT WALKTHROUGH", "ReportSmall")
paragraph("Online Retail Analysis<br/>From source data to customer insights", "ReportTitle")
paragraph(f"Prepared {date.today():%d %B %Y} | Based on saved project results", "ReportSmall")
paragraph("<b>What we achieved:</b> a working, reproducible exploratory data analysis (EDA) "
          "project that downloads real retail transactions, cleans them, calculates business "
          "metrics, segments customers, and produces tables, charts, and an executed notebook.")
table(["Final result", "Value"], [
    ["Source transaction lines", f"{M['audit']['source_rows']:,}"],
    ["Valid positive sales lines", f"{M['valid_sales_lines']:,}"],
    ["Positive sales revenue before refunds", f"GBP {M['revenue_gbp']:,.2f}"],
    ["Distinct sales invoices", f"{M['unique_sales_invoices']:,}"],
    ["Known purchasing customers", f"{M['unique_customers']:,}"],
    ["Deliverables", "11 charts, 6 CSV tables, summary JSON, executed notebook"],
], [300, 199])
paragraph("<b>Where we started:</b> the code and notebook were largely written, but the "
          "dataset and charts were missing, dependencies were absent from the virtual "
          "environment, and there were no saved notebook results or automated tests.")
paragraph("<b>Where we are now:</b> the core EDA runs on the real workbook. Reliability "
          "issues were corrected, 10 regression tests pass, all 11 notebook code cells "
          "have executed, and analytical totals reconcile across outputs.")
paragraph("EDA means exploring and explaining historical data. This project produces "
          "descriptive evidence; it does not train a forecasting or churn model.")

new_page("1. The technology stack")
paragraph("Each tool has a specific job in the workflow. Python runs the analysis; "
          "the notebook explains it; CSV, JSON, and PNG files make the results reusable.")
table(["Technology", "What we used it for"], [
    ["Python 3.12.14", "Validated project runtime and reusable analysis functions."],
    ["Pandas", "Excel loading, cleaning, grouped sales metrics, RFM and cohort tables."],
    ["NumPy", "Numerical checks, score bands, conditional segment labels and missing values."],
    ["Matplotlib + Seaborn", "11 saved charts: trends, rankings, distributions, correlations and retention."],
    ["OpenPyXL", "Reading the original .xlsx workbook through Pandas."],
    ["Jupyter + IPython kernel", "A readable analysis notebook with saved tables, metrics and chart outputs."],
    ["nbformat + nbclient", "Notebook structure validation and automated execution of every code cell."],
    ["unittest + unittest.mock", "10 regression tests, including controlled download failure scenarios."],
    ["pathlib, urllib, zipfile, json", "Portable paths, source downloads, archive handling and metrics export."],
    ["VS Code, .venv, uv and pip", "Editing, isolated dependency setup, installation and compatibility checks."],
    ["requirements-lock.txt", "Exact tested package versions for repeatable installation."],
], [150, 349])
paragraph("<b>Report tools:</b> ReportLab generates this PDF; pypdf checks its pages and "
          "extractable text. They are optional reporting utilities, separate from the EDA's "
          "requirements files.", "ReportSmall")
paragraph("No database, cloud deployment, dashboard or machine-learning model was needed "
          "for the completed core analysis.")

new_page("2. How the data became usable")
paragraph("<b>Source:</b> the UCI Online Retail Excel workbook, covering 1 December 2010 "
          "to 9 December 2011. Its eight fields describe invoice, stock code, description, "
          "quantity, invoice time, unit price, customer ID and country.")
table(["Cleaning stage", "Rows", "Meaning"], [
    ["Original workbook", "541,909", "Source remains unchanged."],
    ["Exact duplicates removed", "5,268", "Assumed repeated records; identical legitimate lines cannot be distinguished."],
    ["Deduplicated records", "536,641", "Basis for the sales filter and return summary."],
    ["Invalid or cancelled lines excluded", "11,763", "Combined exclusion count; overlapping categories are counted once."],
    ["Valid sales view", "524,878", "Positive quantity and price, valid date and identifiers, finite line value."],
], [160, 65, 274])
paragraph("<b>Revenue calculation:</b> TotalPrice = Quantity x UnitPrice. Sales revenue "
          "sums valid positive line values. Invoice counts use distinct invoice numbers; "
          "average invoice value is total sales divided by the invoice count.")
paragraph("<b>Anonymous purchases:</b> missing customer IDs are retained in sales totals. "
          "The 132,186 valid anonymous lines are excluded only from customer-level analysis; "
          "IDs are never invented or filled in.")
paragraph("<b>Returns:</b> credit-note invoices and negative-quantity rows are summarized "
          "separately after deduplication. Their categories overlap and must not be added "
          "together. This project has not matched individual refunds to original orders.")
paragraph("<b>Reliability fixes:</b> downloads are written to temporary files before being "
          "published, corrupt archives trigger recovery, workbook selection is explicit, "
          "required columns are checked, and only the expected workbook is extracted.")
paragraph('Dataset citation: Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning '
          'Repository. <link href="https://doi.org/10.24432/C5BW33" color="#087E8B">'
          'doi:10.24432/C5BW33</link>. CC BY 4.0. Source attribution is also in README.md.', "ReportSmall")

new_page("3. Sales results and what they mean")
paragraph(f"Average invoice value is <b>GBP {M['average_order_value_gbp']:,.2f}</b>. The "
          f"United Kingdom contributes <b>{M['top_country_revenue_gbp']/M['revenue_gbp']:.2%}</b> "
          f"of positive sales. November 2011 leads with <b>GBP {M['peak_month_revenue_gbp']:,.2f}</b>.")
chart("monthly_revenue.png", 185)
paragraph("December 2011 contains only the first nine days. The final drop is not "
          "evidence of a full-month sales decline. One observation window is insufficient "
          "to establish recurring seasonality.", "ReportSmall")
chart("country_revenue.png", 190)
paragraph(f"<b>Revenue concentration:</b> {M['products_for_80pct_revenue']:,} of "
          f"{M['product_count']:,} stock codes ({M['products_for_80pct_revenue']/M['product_count']:.2%}) "
          "account for at least 80% of positive sales revenue. Stock codes, rather than "
          "descriptions, define products; their most common description supplies the label.")
paragraph("<b>Practical interpretation:</b> investigate UK operations and leading codes "
          "first. The highest-revenue code is DOTCOM POSTAGE (GBP 206,248.77), a service "
          "charge. Separate service items and investigate exceptional orders and refunds "
          "before making merchandise or stock recommendations.")

new_page("4. Customer behavior and retention")
paragraph(f"<b>{M['repeat_customer_share']:.2%}</b> of known purchasing customers placed more "
          "than one valid invoice during the observed window. This is a historical repeat "
          "purchase share, not a forecast of future loyalty.")
paragraph("<b>RFM explained:</b> Recency asks how recently someone bought, Frequency counts "
          "distinct invoices, and Monetary adds their positive sales. Four score bands "
          "use average percentile ranks so tied values receive identical scores. The "
          "reference date is the day after the last valid purchase in all sales.")
table(["Exploratory segment", "Customers"], [
    [key, f"{value:,}"] for key, value in M["rfm_segment_counts"].items()
], [350, 149])
chart("cohort_retention.png", 245)
paragraph("Each row groups customers by their first observed purchase month. A cell "
          "shows the share who purchased in that later month. Month zero is 100%; observed "
          "months with no returning customers are zero; future months stay blank. The final "
          "activity month is partial, and first observed purchase may not be true acquisition.", "ReportSmall")
paragraph("<b>Next action:</b> use these segments to design retention experiments and "
          "measure actual outcomes. Segment labels are simple exploratory rules, not "
          "validated churn predictions or campaign performance estimates.")

new_page("5. Deliverables, validation and next steps")
table(["File or folder", "What you can use it for"], [
    ["src/data_cleaning.py", "Run the complete reusable pipeline."],
    ["notebooks/online_retail_analysis.ipynb", "Follow the executed walkthrough and see saved findings."],
    ["dataset/", "Original workbook and six output CSVs: cleaned sales, RFM, returns, products, monthly sales and cohorts."],
    ["visualizations/", "11 PNG charts for trends, products, countries, customers and retention."],
    ["analysis_summary.json", "Computed headline metrics and cleaning audit."],
    ["tests/test_analysis.py", "Regression checks for key analytical rules and download recovery."],
    ["README.md + requirements files", "Methodology, findings, setup instructions and tested dependencies."],
], [213, 286])
paragraph("<b>Validation completed:</b> all 10 regression tests pass; all 11 notebook code "
          "cells executed without errors; installed dependencies passed compatibility checks. "
          "Sales totals reconcile across cleaned transactions, monthly and product outputs. "
          "RFM revenue matches known-customer sales; customer and segment counts agree; "
          "cohort values stay between zero and one. All 11 charts were visually reviewed.")
paragraph("<b>Run it again in VS Code:</b> select .venv/Scripts/python.exe as interpreter "
          "and notebook kernel. From the project root, run the following commands or open "
          "the notebook and choose Run All.")
paragraph("<font face='Courier' size='8'>python src/data_cleaning.py<br/>"
          "python -m unittest discover -s tests -v<br/>python -m pip check</font>")
paragraph("<b>Development priorities:</b> (1) classify merchandise versus service codes and "
          "reconcile credit notes to sales; (2) add configurable paths and a dashboard if "
          "needed; (3) obtain more periods before exploring forecasting, seasonality or "
          "customer lifetime value.")
paragraph("<b>Final outcome:</b> a completed and locally validated core EDA, with reusable "
          "outputs and documented assumptions. Positive sales are before refunds, not net "
          "revenue or profit. Product costs and campaign data are absent, so profitability "
          "and marketing effectiveness remain outside the evidence available.")

document = SimpleDocTemplate(str(OUTPUT), pagesize=A4, rightMargin=48, leftMargin=48,
                             topMargin=45, bottomMargin=58, title="Python EDA Project Walkthrough",
                             author="Python EDA Project", subject="Accomplishments, stack, methodology and results")
document.build(story, onFirstPage=footer, onLaterPages=footer)
print(OUTPUT)

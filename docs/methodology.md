# RetailPulse methodology

## Compatibility contract

The original `src/data_cleaning.py` functions, notebook and six EDA output tables are retained.
The default remains exact deduplication followed by the existing positive-sales filter.
The baseline is 541,909 source rows, 524,878 valid sales lines, GBP 10,642,110.804 positive
sales, 19,960 distinct sales invoices and 4,338 identifiable purchasing customers.
`scripts/verify_results.py` checks these values after generating outputs.

## Reporting scopes

- Executive, Sales, Segmentation and Retention use the inclusive date, country, stock-code
  and item-category selections. No selections for country/stock means all; no selected
  categories means no rows. Invoices containing several selected product lines count once.
- Average invoice value is the selected line revenue divided by distinct invoices; selecting
  products produces a partial-invoice value, not the complete original order value.
- The Data Quality source audit and duplicate sensitivity are intentionally global, explicitly
  labeled and independent of filters. Its revenue coverage cards use filtered sales.
- RFM is recomputed inside the current selection with the original scoring rules. Default
  unfiltered segments match the existing project. Cohorts similarly use first observed purchase
  within the selection; neither view claims that it observes a customer's full lifetime.
- Return matching runs on the complete ledger once, then return records are filtered by the
  return date/country/stock/category. A matched original sale may be outside the selected dates.
- December 2011 ends on the ninth; arbitrary date filters can also truncate boundary months.

## Cleaning and audit

The raw workbook is never overwritten. Cleaning happens on a copy. Exact duplicates are
assumed repeated records; genuine identical invoice lines cannot be distinguished without
an invoice-line identifier. IDs are not fabricated. Missing customer IDs remain in aggregate
sales but not customer analytics. Valid sales require non-cancelled invoices, positive quantity
and price, finite line value, valid dates and present invoice/stock identifiers.

The exclusive row reconciliation is:

```
source rows = exact duplicates + excluded deduplicated rows + valid positive sales rows
541,909     = 5,268            + 11,763                     + 524,878
```

Cancellation, non-positive quantity/price, and missing-ID source counts overlap. The source
audit does not present their sum as exclusions. A separate disjoint cancellation/negative-
quantity overlap table is displayed. Duplicate sensitivity applies identical sales rules with
and without deduplication; only the duplicate policy changes.

## Financial definitions

`transaction_ledger` retains all deduplicated rows, including lines excluded from positive
sales. `TotalPrice = Quantity × UnitPrice`; amounts are GBP, with original precision retained.

| Metric | Definition |
|---|---|
| Gross positive sales | Existing valid-sales sum; preserves the baseline |
| Recorded credit/return value | Absolute sum of all finite negative line values, counted once; includes negative-price adjustments |
| Net recorded transaction value | Signed sum of all finite deduplicated source line values in scope |
| Other signed value | Residual needed to reconcile excluded finite nonnegative lines or other differences between ledger and sales scopes |
| Merchandise positive sales | Valid-sales sum classified Merchandise |
| Non-merchandise positive sales | All other valid-sales categories, including Unknown; not all are proven fees |

```
gross positive sales - recorded negative value + other signed value = net recorded value
```

Nonfinite ledger values are excluded from signed sums and counted in the financial report.
The unfiltered ledger includes any finite undated rows; interactive date filters exclude
undated rows. The actual UCI workbook has no unparseable dates. Monetary values are floating
point, reconciled with a GBP 0.000001 tolerance; only display values are rounded to two decimals.
None of these metrics is profit, cash collection, or audited accounting revenue.

## Product classification

Rules live in `src/classification.py`, with evidence exported in `product_classification.csv`.
No classified row is deleted and no amount is changed.

1. A five-digit stock code with up to two letter suffixes and a nonempty description is a
   Merchandise candidate. This catalog-pattern heuristic is disclosed and can be refined.
2. Explicit service codes/descriptions: DOT / DOTCOM POSTAGE, POST / POSTAGE,
   BANK CHARGES, C2 / CARRIAGE, and AMAZONFEE / AMAZON FEE.
3. Explicit adjustment codes/descriptions: M / Manual, D / Discount, ADJUST, ADJUST2,
   B / Adjust bad debt, and exact adjustment descriptions.
4. CRUK, S, PADS, gift vouchers, unusual DCGS codes and unsupported codes remain Unknown
   unless an explicit documented rule supplies evidence. Unknown does not mean worthless
   or nonphysical. It means the economic classification needs review.

Exact code rules override descriptions, which override the regular catalog heuristic.
Product aggregation retains StockCode identity and uses the most frequent description as
a label. Case variants remain separate original stock identifiers, preserving the baseline.

## Return matching rules

Return records are the union of credit-note invoice flags, negative quantities and negative
values. A record satisfying several conditions is still a single return record. Negative-price
adjustments can carry financial value without being matchable merchandise returns.

A match requires:

1. Observed customer ID, stock code, timestamp and finite value.
2. Negative quantity and positive unit price on the return.
3. Exactly one earlier, non-cancelled positive sales line with the same customer, exact
   stock code and exact unit price, and remaining unreturned quantity.
4. Returned units do not exceed that line's remaining units. A matched quantity is consumed
   once, preventing repeated allocation across subsequent credits.

Same-timestamp records, multiple candidate lines, missing identifiers, oversized returns,
price mismatches and absent originals remain unmatched with an explicit reason. Multiple
partial original lines are not guessed or combined. Matches are evidence-based candidate
links, not invoice-reference proof: the source does not identify original invoice references
on credits. Credits may relate to purchases before the observation window. Financial negative
value is reported regardless of matching status; matching never subtracts a refund twice.

## RFM and segment-level reports

The default code is reused without methodology changes:

- Recency: days between a customer's latest purchase date and the day after the latest
  valid purchase in the selected sales view (including anonymous purchases for the reference).
- Frequency: distinct invoices per observed customer.
- Monetary: sum of positive selected sales per customer.
- Score: `ceil(average_percentile_rank × 4)`, bounded 1–4. Recency is reversed with `5 - score`.
  Ties remain together; groups need not be equally sized.
- Rules in priority order: Champions (`R>=3,F>=3,M>=3`), Loyal customers (`R>=3,F>=2`),
  At risk (`R<=2,F>=3`), then Needs attention.

Segment spending, mean spending, mean invoice frequency, customer share and known-customer
revenue share are exported. Segment average invoice value is total segment spending divided
by the sum of customers' distinct invoice counts (customer-invoice pairs). This avoids
confusing average customer spending with invoice value. Recommendations are retention
experiments; there are no campaign outcomes or validated churn labels in the dataset.

## Cohorts

Cohorts use each known customer's first observed purchase month in scope. Monthly active
customers are divided by cohort size. Observed inactive months are zero; unobserved future
months are NaN/blank. Month zero is 100%. The first cohort may include pre-existing customers;
the final observed month is incomplete. Repeat purchase share means customers with more
than one distinct selected valid invoice divided by selected purchasing customers.

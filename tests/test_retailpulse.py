"""Analytical regression tests independent of network access and the full workbook."""
import unittest
import pandas as pd
from pandas.testing import assert_frame_equal

from src.analytics import csv_bytes, filter_transactions, monthly_sales, sales_kpis, segment_report
from src.classification import classify_products
from src.data_cleaning import EXPECTED_COLUMNS, build_rfm, clean_data
from src.finance import duplicate_sensitivity, match_returns, revenue_metrics, transaction_ledger


def fixture():
    return pd.DataFrame([
        ['1', '12345', 'A product', 5, '2024-01-01 12:00', 10, '10', 'UK'],
        ['2', 'POST', 'POSTAGE', 1, '2024-02-01 15:00', 5, None, 'France'],
        ['C1', '12345', 'A product', -2, '2024-02-02 10:00', 10, '10', 'UK'],
        ['C2', '12345', 'A product', -3, '2024-02-03 10:00', 10, '10', 'UK'],
        ['C3', '12345', 'A product', -1, '2024-02-04 10:00', 10, '10', 'UK'],
        ['3', 'M', 'Manual', 1, '2024-02-05 11:00', -2, '10', 'UK'],
    ], columns=EXPECTED_COLUMNS)


class RetailPulseTests(unittest.TestCase):
    def test_financial_reconciliation_and_legacy_gross(self):
        raw = fixture()
        sales, _ = clean_data(raw)
        ledger = transaction_ledger(raw)
        m = revenue_metrics(ledger, sales)
        self.assertEqual(m['gross_positive_sales_gbp'], 55)
        self.assertEqual(m['recorded_credit_return_value_gbp'], 62)
        self.assertEqual(m['net_recorded_transaction_value_gbp'], -7)
        self.assertAlmostEqual(m['gross_positive_sales_gbp'] - m['recorded_credit_return_value_gbp'] + m['other_signed_value_gbp'], m['net_recorded_transaction_value_gbp'])
        self.assertEqual(m['merchandise_positive_sales_gbp'] + m['non_merchandise_positive_sales_gbp'], 55)

    def test_excluded_positive_cancelled_value_is_visible_in_bridge(self):
        raw = fixture().iloc[[0]].copy()
        cancelled = raw.copy()
        cancelled['InvoiceNo'] = 'Cpositive'
        raw = pd.concat([raw, cancelled], ignore_index=True)
        sales, _ = clean_data(raw)
        result = revenue_metrics(transaction_ledger(raw), sales)
        self.assertEqual(result['gross_positive_sales_gbp'], 50)
        self.assertEqual(result['other_signed_value_gbp'], 50)
        self.assertEqual(result['net_recorded_transaction_value_gbp'], 100)

    def test_returns_consume_capacity_once(self):
        result = match_returns(transaction_ledger(fixture()))
        self.assertEqual(result.Status.tolist(), ['Matched', 'Matched', 'Unmatched', 'Unmatched'])
        self.assertEqual(result.loc[result.Status.eq('Matched'), 'ReturnedUnits'].sum(), 5)
        self.assertEqual(result.ReturnLineID.nunique(), 4)

    def test_ambiguous_original_sales_are_unmatched(self):
        raw = fixture().iloc[[0, 0, 2]].copy()
        raw.iloc[1, raw.columns.get_loc('InvoiceNo')] = 'second-sale'
        result = match_returns(transaction_ledger(raw))
        self.assertEqual(result.iloc[0].Status, 'Unmatched')
        self.assertIn('Multiple', result.iloc[0].Reason)

    def test_missing_customer_and_same_timestamp_do_not_match(self):
        raw = fixture().iloc[[0, 2]].copy()
        raw['CustomerID'] = None
        self.assertEqual(match_returns(transaction_ledger(raw)).iloc[0].Status, 'Unmatched')
        raw['CustomerID'] = '10'
        raw['InvoiceDate'] = pd.Timestamp('2024-01-01')
        self.assertEqual(match_returns(transaction_ledger(raw)).iloc[0].Status, 'Unmatched')

    def test_duplicates_do_not_duplicate_refunds(self):
        raw = pd.concat([fixture(), fixture().iloc[[2]]], ignore_index=True)
        result = match_returns(transaction_ledger(raw))
        self.assertEqual(len(result), 4)
        self.assertEqual(result.ReturnValueGBP.sum(), 62)

    def test_duplicate_sensitivity(self):
        raw = pd.concat([fixture(), fixture().iloc[[0]]], ignore_index=True)
        result = duplicate_sensitivity(raw)
        self.assertEqual(result.GrossPositiveSalesGBP.tolist(), [55, 105])
        self.assertEqual(result.ValidSalesLines.tolist(), [2, 3])

    def test_classification_and_ambiguous_code(self):
        raw = fixture().iloc[[0, 1, 5]].copy()
        extra = raw.iloc[[0]].copy()
        extra['StockCode'] = 'mystery'
        raw = pd.concat([raw, extra])
        original = raw.copy(deep=True)
        result = classify_products(raw)
        self.assertEqual(result.Category.tolist(), ['Merchandise', 'Services / postage / fees', 'Adjustments', 'Unknown'])
        assert_frame_equal(raw, original)

    def test_missing_description_remains_unknown(self):
        raw = fixture().iloc[[0]].copy()
        raw['Description'] = None
        self.assertEqual(classify_products(raw).iloc[0].Category, 'Unknown')

    def test_date_filter_includes_entire_end_day(self):
        ledger = transaction_ledger(fixture())
        result = filter_transactions(ledger, '2024-02-01', '2024-02-02', countries=['UK'])
        self.assertEqual(result.InvoiceNo.tolist(), ['C1'])
        self.assertTrue(filter_transactions(ledger, stocks=[]).empty)
        self.assertTrue(filter_transactions(ledger, '2025-01-01', '2024-01-01').empty)

    def test_aggregation_consistency_and_anonymous_revenue(self):
        sales, _ = clean_data(fixture())
        kpis = sales_kpis(sales)
        monthly = monthly_sales(sales)
        report = segment_report(sales)
        self.assertEqual(kpis['Revenue'], monthly.Revenue.sum())
        self.assertEqual(kpis['Customers'], 1)
        self.assertEqual(report.Revenue.sum(), 50)
        self.assertEqual(report.iloc[0].AverageInvoice, 50)

    def test_rfm_preserved_and_segment_rules(self):
        rows = []
        delays = [1, 10, 2, 5, 80, 3, 100, 0]
        for customer in range(8):
            for order in range(customer + 1):
                rows.append([f'{customer}-{order}', '12345', 'Product', 1,
                             pd.Timestamp('2024-06-01') - pd.Timedelta(days=delays[customer]),
                             1, str(customer), 'UK'])
        raw = pd.DataFrame(rows, columns=EXPECTED_COLUMNS)
        sales, _ = clean_data(raw)
        rfm = build_rfm(sales)
        report = segment_report(sales, rfm)
        self.assertEqual(report.Customers.sum(), 8)
        self.assertEqual(report.Revenue.sum(), sales.TotalPrice.sum())
        self.assertEqual(rfm.loc['0', 'Segment'], 'Needs attention')
        self.assertEqual(rfm.loc['2', 'Segment'], 'Loyal customers')
        self.assertEqual(rfm.loc['4', 'Segment'], 'At risk')
        self.assertEqual(rfm.loc['5', 'Segment'], 'Champions')
        for row in rfm.itertuples():
            expected = ('Champions' if row.R >= 3 and row.F >= 3 and row.M >= 3 else
                        'Loyal customers' if row.R >= 3 and row.F >= 2 else
                        'At risk' if row.R <= 2 and row.F >= 3 else 'Needs attention')
            self.assertEqual(row.Segment, expected)

    def test_empty_inputs(self):
        raw = fixture().iloc[:0]
        sales, _ = clean_data(raw)
        ledger = transaction_ledger(raw)
        self.assertTrue(match_returns(ledger).empty)
        self.assertEqual(revenue_metrics(ledger, sales)['net_recorded_transaction_value_gbp'], 0)
        self.assertEqual(sales_kpis(sales)['AverageInvoice'], 0)
        self.assertTrue(monthly_sales(sales).empty)
        self.assertTrue(segment_report(sales).empty)

    def test_exports_match_selection_and_escape_formulas(self):
        sales, _ = clean_data(fixture())
        selected = filter_transactions(sales, countries=['France'])
        text = csv_bytes(selected).decode('utf-8-sig')
        self.assertIn('France', text)
        self.assertNotIn('A product', text)
        self.assertIn("'=1+1", csv_bytes(pd.DataFrame({'Text':['=1+1']})).decode('utf-8-sig'))


if __name__ == '__main__':
    unittest.main()

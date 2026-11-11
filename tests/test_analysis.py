"""Regression checks for cleaning, customer scoring, cohorts, and input recovery."""
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from pandas.testing import assert_frame_equal

from src.data_cleaning import (
    EXPECTED_COLUMNS, build_rfm, cancellation_summary, clean_data,
    cohort_retention, locate_workbook, product_summary,
)


def transactions():
    return pd.DataFrame([
        ["1", "A", "First name", 2, "2024-01-01", 5, "10", "UK"],
        ["2", "A", "Changed name", 1, "2024-03-01", 5, "10", "UK"],
        ["3", "B", "First name", 1, "2024-03-02", 8, "20", "UK"],
        ["4", "B", "First name", 1, "2024-03-03", 8, None, "UK"],
        ["C1", "A", "First name", -1, "2024-01-02", 5, "10", "UK"],
        ["5", "A", "First name", 0, "2024-01-02", 5, "10", "UK"],
        ["6", "A", "First name", 1, "invalid", 5, "10", "UK"],
    ], columns=EXPECTED_COLUMNS)


class AnalysisTests(unittest.TestCase):
    def test_cleaning_reconciles_and_preserves_raw(self):
        raw = pd.concat([transactions(), transactions().iloc[[0]]], ignore_index=True)
        original = raw.copy(deep=True)
        sales, audit = clean_data(raw)
        assert_frame_equal(raw, original)
        self.assertEqual(len(sales), 4)
        self.assertEqual(sales.TotalPrice.sum(), 31)
        self.assertEqual(sales.CustomerID.isna().sum(), 1)
        self.assertEqual(audit['source_rows'], audit['duplicate_rows'] + audit['valid_sales_rows'] + audit['invalid_or_cancelled_rows_excluded'])

    def test_returns_are_deduplicated_and_overlap_explicitly(self):
        raw = pd.concat([transactions(), transactions().iloc[[4]]], ignore_index=True)
        result = cancellation_summary(raw).iloc[0]
        self.assertEqual(result.cancellation_or_negative_rows, 1)
        self.assertEqual(result.cancellation_invoice_value_abs, 5)

    def test_rfm_single_customer_and_full_window_snapshot(self):
        raw = transactions().iloc[[0, 3]]
        sales, _ = clean_data(raw)
        result = build_rfm(sales)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0].Recency, 63)
        self.assertEqual(result.iloc[0].Frequency, 1)

    def test_rfm_ties_do_not_depend_on_customer_identity(self):
        raw = transactions().iloc[[0, 0, 0, 0]].copy()
        raw['InvoiceNo'] = ['1', '2', '3', '4']
        raw['CustomerID'] = ['40', '10', '30', '20']
        result = build_rfm(clean_data(raw)[0])
        for score in ['R', 'F', 'M']:
            self.assertEqual(result[score].nunique(), 1)

    def test_cohorts_distinguish_zero_from_future(self):
        result = cohort_retention(clean_data(transactions())[0])
        january, march = pd.Period('2024-01'), pd.Period('2024-03')
        self.assertEqual(result.loc[january, 1], 0)
        self.assertEqual(result.loc[january, 2], 1)
        self.assertTrue(pd.isna(result.loc[march, 1]))
        self.assertTrue((result[0] == 1).all())

    def test_products_use_stock_codes_and_reconcile(self):
        sales, _ = clean_data(transactions())
        products = product_summary(sales)
        self.assertEqual(len(products), 2)
        self.assertEqual(products.loc['A', 'Units'], 3)
        self.assertEqual(products.Revenue.sum(), sales.TotalPrice.sum())

    def test_empty_customer_population(self):
        sales, _ = clean_data(transactions().iloc[[3]])
        self.assertTrue(build_rfm(sales).empty)
        self.assertTrue(cohort_retention(sales).empty)

    def test_missing_schema_is_actionable(self):
        with self.assertRaisesRegex(ValueError, 'StockCode'):
            clean_data(transactions().drop(columns='StockCode'))

    def test_corrupt_archive_is_replaced_without_extracting_other_members(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('Online Retail.xlsx', b'workbook fixture')
            archive.writestr('../unexpected.txt', b'ignored')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'online_retail.zip').write_bytes(b'broken')
            with patch('urllib.request.urlopen', return_value=io.BytesIO(buffer.getvalue())):
                result = locate_workbook(root)
            self.assertEqual(result.read_bytes(), b'workbook fixture')
            self.assertEqual(sorted(p.name for p in root.iterdir()), ['Online Retail.xlsx', 'online_retail.zip'])

    def test_failed_download_does_not_publish_partial_workbook(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('urllib.request.urlopen', side_effect=OSError('offline')):
                with self.assertRaises(RuntimeError):
                    locate_workbook(Path(directory))
            self.assertFalse(list(Path(directory).glob('*.xlsx')))


if __name__ == '__main__':
    unittest.main()

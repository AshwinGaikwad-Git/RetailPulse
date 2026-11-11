"""Streamlit interaction tests with an isolated analytical fixture, never fake demo data."""
from pathlib import Path
from datetime import date
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from src.classification import classify_products
from src.data_cleaning import EXPECTED_COLUMNS, build_rfm, clean_data
from src.finance import duplicate_sensitivity, match_returns, revenue_metrics, transaction_ledger
from src.reporting import AnalysisBundle

APP = str(Path(__file__).resolve().parents[1] / 'streamlit_app.py')


def bundle_fixture():
    raw = pd.DataFrame([
        ['1', '12345', 'Product A', 2, pd.Timestamp('2011-01-01'), 10, '10', 'UK'],
        ['2', '12345', 'Product A', 3, pd.Timestamp('2011-02-01'), 10, '10', 'UK'],
        ['3', 'POST', 'POSTAGE', 1, pd.Timestamp('2011-02-02'), 5, None, 'France'],
        ['C1', '12345', 'Product A', -1, pd.Timestamp('2011-02-03'), 10, '10', 'UK'],
    ], columns=EXPECTED_COLUMNS)
    sales, audit = clean_data(raw)
    sales = classify_products(sales)
    ledger = transaction_ledger(raw)
    return AnalysisBundle(sales, ledger, match_returns(ledger), audit,
        duplicate_sensitivity(raw), revenue_metrics(ledger, sales), build_rfm(sales), 'fixture.xlsx')


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.patch = patch('dashboard.ui.get_bundle', return_value=bundle_fixture())
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_all_five_pages_render(self):
        app = AppTest.from_file(APP, default_timeout=30).run()
        self.assertFalse(app.exception)
        for page in ['Sales Analytics', 'Customer Segmentation', 'Customer Retention', 'Data Quality']:
            app.radio(key='view').set_value(page).run()
            self.assertFalse(app.exception, page)

    def test_country_filter_updates_kpis(self):
        app = AppTest.from_file(APP, default_timeout=30).run()
        self.assertEqual(app.metric[0].value, '£55.00')
        app.multiselect(key='countries').set_value(['France']).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, '£5.00')
        self.assertEqual(app.metric[2].value, '0')

    def test_date_and_stock_filters_update_kpis(self):
        app = AppTest.from_file(APP, default_timeout=30).run()
        app.date_input(key='dates').set_value((date(2011, 2, 1), date(2011, 2, 3))).run()
        self.assertEqual(app.metric[0].value, '£35.00')
        app.multiselect(key='stocks').set_value(['POST']).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, '£5.00')

    def test_empty_category_selection_and_reset(self):
        app = AppTest.from_file(APP, default_timeout=30).run()
        app.multiselect(key='categories').set_value([]).run()
        self.assertFalse(app.exception)
        self.assertTrue(any('No positive sales' in x.value for x in app.info))
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, '£55.00')

    def test_segment_explorer_and_anonymous_only_state(self):
        app = AppTest.from_file(APP, default_timeout=30).run()
        app.radio(key='view').set_value('Customer Segmentation').run()
        app.selectbox(key='segment').set_value('Needs attention').run()
        self.assertFalse(app.exception)
        app.multiselect(key='countries').set_value(['France']).run()
        self.assertFalse(app.exception)
        self.assertTrue(any('No identified customers' in x.value for x in app.info))

    def test_load_failure_has_actionable_state(self):
        with patch('dashboard.ui.get_bundle', side_effect=OSError('offline')):
            app = AppTest.from_file(APP, default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertTrue(any('official UCI archive' in x.value for x in app.info))


if __name__ == '__main__':
    unittest.main()

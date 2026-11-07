from django.test import SimpleTestCase

from apps.reports.exports import _safe_spreadsheet_value


class SpreadsheetFormulaInjectionTests(SimpleTestCase):
    def test_formula_prefixes_are_neutralized(self):
        for value in ("=1+1", "+SUM(A1:A2)", "-2+3", "@SUM(A1)", "  =1+1"):
            with self.subTest(value=value):
                self.assertTrue(_safe_spreadsheet_value(value).startswith("'"))

    def test_plain_text_and_numbers_are_preserved(self):
        self.assertEqual(_safe_spreadsheet_value("ITAM report"), "ITAM report")
        self.assertEqual(_safe_spreadsheet_value(125), 125)
        self.assertEqual(_safe_spreadsheet_value(None), "")

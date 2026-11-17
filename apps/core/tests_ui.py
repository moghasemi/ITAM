"""Regression checks for the Metronic-based Django template shell."""
from django.contrib.staticfiles import finders
from django.template.loader import get_template
from django.test import SimpleTestCase


class MetronicTemplateCompilationTests(SimpleTestCase):
    def test_shared_and_key_templates_compile(self):
        for template_name in (
            "base.html",
            "accounts/login.html",
            "core/dashboard.html",
            "partials/form_fields.html",
            "partials/filter_bar.html",
        ):
            with self.subTest(template=template_name):
                self.assertIsNotNone(get_template(template_name))

    def test_metronic_vendor_assets_are_local(self):
        for asset_path in (
            "vendor/metronic9/assets/css/styles.css",
            "vendor/metronic9/assets/vendors/keenicons/styles.bundle.css",
            "vendor/metronic9/assets/vendors/ktui/ktui.min.js",
            "vendor/metronic9/assets/vendors/apexcharts/apexcharts.min.js",
            "vendor/vazirmatn/Vazirmatn-wght.woff2",
        ):
            with self.subTest(asset=asset_path):
                self.assertIsNotNone(finders.find(asset_path))

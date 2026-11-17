"""Regression checks for the Metronic-based Django template shell."""
from django.contrib.staticfiles import finders
from django.template.loader import get_template
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase

from apps.core.context_processors import site_context


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


class ScopedCenterSelectorContextTests(SimpleTestCase):
    def test_province_admin_center_selector_uses_active_scoped_centers(self):
        scoped_centers = Mock()
        active_centers = Mock()
        visible_centers = [object(), object()]
        scoped_centers.filter.return_value = active_centers
        active_centers.order_by.return_value = visible_centers
        user = SimpleNamespace(
            is_authenticated=True,
            is_admin_province=True,
            is_superuser=False,
            center=None,
            get_scoped_centers=Mock(return_value=scoped_centers),
        )
        request = SimpleNamespace(user=user)

        context = site_context(request)

        user.get_scoped_centers.assert_called_once_with()
        scoped_centers.filter.assert_called_once_with(is_active=True)
        active_centers.order_by.assert_called_once_with("-is_headquarters", "name")
        self.assertEqual(context["all_centers"], visible_centers)

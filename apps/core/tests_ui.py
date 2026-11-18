"""Regression checks for the Metronic-based Django template shell."""
from pathlib import Path

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
            "partials/metronic/sidebar.html",
            "partials/metronic/header.html",
            "partials/metronic/footer.html",
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


class MetronicSidebarLayoutContractTests(SimpleTestCase):
    def test_sidebar_and_content_share_metronic_width_token(self):
        css_path = finders.find("css/itam-metronic.css")
        self.assertIsNotNone(css_path)
        css = Path(css_path).read_text(encoding="utf-8")
        compact_css = "".join(css.split())

        # The bridge mirrors Metronic's token; it must not invent a second width.
        self.assertIn(
            "body.app-body{--itam-sidebar-width:var(--sidebar-width,280px);",
            compact_css,
        )
        self.assertIn(
            ".itam-wrapper{min-width:0;margin-inline-start:0;",
            compact_css,
        )
        self.assertNotIn("--itam-sidebar-width:258px", compact_css)

    def test_collapsed_sidebar_updates_metronic_and_itam_width_tokens(self):
        css_path = finders.find("css/itam-metronic.css")
        self.assertIsNotNone(css_path)
        css = "".join(Path(css_path).read_text(encoding="utf-8").split())

        self.assertIn(
            "body.itam-sidebar-collapsed{--sidebar-width:var(--sidebar-width-collapse,80px);"
            "--itam-sidebar-width:var(--sidebar-width-collapse,80px)}",
            css,
        )


class MetronicShellCompositionTests(SimpleTestCase):
    def test_base_template_delegates_shell_regions_to_shared_partials(self):
        template = get_template("base.html")
        source = Path(template.origin.name).read_text(encoding="utf-8")

        for partial in (
            'partials/metronic/sidebar.html',
            'partials/metronic/header.html',
            'partials/metronic/footer.html',
        ):
            with self.subTest(partial=partial):
                self.assertIn('{% include "' + partial + '" %}', source)


class MetronicShellAccessibilityContractTests(SimpleTestCase):
    def test_authenticated_shell_has_skip_link_and_focusable_main_target(self):
        template = get_template("base.html")
        source = Path(template.origin.name).read_text(encoding="utf-8")

        self.assertIn('class="itam-skip-link" href="#content"', source)
        self.assertIn('id="content" role="main" tabindex="-1"', source)

        sidebar_template = get_template("partials/metronic/sidebar.html")
        sidebar_source = Path(sidebar_template.origin.name).read_text(encoding="utf-8")
        self.assertIn('id="sidebar" aria-label="ناوبری اصلی" tabindex="-1"', sidebar_source)

    def test_mobile_sidebar_script_manages_inert_state_and_keyboard_focus(self):
        script_path = finders.find("js/itam.js")
        self.assertIsNotNone(script_path)
        script = Path(script_path).read_text(encoding="utf-8")

        self.assertIn('sidebar.setAttribute("aria-hidden"', script)
        self.assertIn('sidebar.setAttribute("inert"', script)
        self.assertIn('if(event.key==="Escape")', script)
        self.assertIn('if(event.key!=="Tab")return;', script)
        self.assertIn('firstMenuLink.focus()', script)
        self.assertIn('link.setAttribute("aria-label",accessibleLabel)', script)
        self.assertNotIn(".user-chip", script)
        self.assertNotIn(".user-menu", script)


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


class MetronicDashboardCompositionTests(SimpleTestCase):
    def test_dashboard_uses_metronic_cards_and_responsive_sections(self):
        template = get_template("core/dashboard.html")
        source = Path(template.origin.name).read_text(encoding="utf-8")

        self.assertIn('class="itam-dashboard"', source)
        self.assertIn('class="kt-card itam-dashboard-stat"', source)
        self.assertIn('class="kt-card itam-dashboard-panel"', source)
        self.assertIn('class="itam-dashboard-main-grid"', source)
        self.assertIn('class="itam-dashboard-content-grid"', source)
        self.assertIn('aria-labelledby="monthly-chart-title"', source)

    def test_dashboard_preserves_existing_context_and_workflow_links(self):
        template = get_template("core/dashboard.html")
        source = Path(template.origin.name).read_text(encoding="utf-8")

        for context_key in (
            "assets_total", "open_tickets", "overdue_response", "overdue_resolve",
            "awaiting_user_confirm", "awaiting_it_confirm", "visits_planned",
            "visits_overdue", "pending_snapshots_count", "monthly_series",
            "calendar.work_start", "setting.work_day_labels", "sla_paused_count",
            "my_visits", "recent_tickets", "pending_snapshots", "upcoming_visits",
            "recent_events", "top_assets",
        ):
            with self.subTest(context_key=context_key):
                self.assertIn(context_key, source)

        for route_name in (
            "tickets:create", "tickets:list", "tickets:detail",
            "assets:create", "assets:snapshot_pending", "assets:snapshot_detail",
            "assets:detail", "maintenance:my_visits", "maintenance:visit_detail",
        ):
            with self.subTest(route=route_name):
                self.assertIn("{% url '" + route_name + "'", source)

        self.assertIn("{% if user.is_technician and my_visits %}", source)
        self.assertIn('id="itam-monthly-chart"', source)
        self.assertIn('id="itam-monthly-series"', source)
        self.assertIn("window.ApexCharts", source)

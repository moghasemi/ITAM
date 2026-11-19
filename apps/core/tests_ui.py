"""Regression checks for the Metronic-based Django template shell."""
from pathlib import Path
import re

from django.contrib.staticfiles import finders
from django.template.loader import get_template
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase

from apps.core.context_processors import site_context
from apps.core.templatetags.itam_tags import filter_metronic_badge_variant


class MetronicTemplateCompilationTests(SimpleTestCase):
    def test_shared_and_key_templates_compile(self):
        for template_name in (
            "base.html",
            "partials/metronic/sidebar.html",
            "partials/metronic/header.html",
            "partials/metronic/footer.html",
            "accounts/login.html",
            "core/dashboard.html",
            "assets/asset_list.html",
            "assets/asset_detail.html",
            "assets/asset_form.html",
            "tickets/ticket_list.html",
            "tickets/ticket_detail.html",
            "tickets/ticket_form.html",
            "maintenance/visit_list.html",
            "maintenance/visit_detail.html",
            "maintenance/visit_form.html",
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
        self.assertIn('json_script:"itam-monthly-series"', source)
        self.assertIn("window.ApexCharts", source)


class MetronicOperationalPageCompositionTests(SimpleTestCase):
    def _source(self, template_name):
        template = get_template(template_name)
        return Path(template.origin.name).read_text(encoding="utf-8")

    def test_operational_templates_use_metronic_cards_and_responsive_tables(self):
        for template_name in (
            "assets/asset_list.html", "assets/asset_detail.html", "assets/asset_form.html",
            "tickets/ticket_list.html", "tickets/ticket_detail.html", "tickets/ticket_form.html",
            "maintenance/visit_list.html", "maintenance/visit_detail.html", "maintenance/visit_form.html",
        ):
            with self.subTest(template=template_name):
                source = self._source(template_name)
                self.assertIn('class="itam-ops-page', source)
                self.assertIn("kt-card", source)

        for template_name in (
            "assets/asset_list.html", "assets/asset_detail.html",
            "tickets/ticket_list.html", "tickets/ticket_detail.html",
            "maintenance/visit_list.html", "maintenance/visit_detail.html",
        ):
            with self.subTest(template=template_name):
                self.assertIn("itam-ops-table-wrap", self._source(template_name))

    def test_asset_pages_preserve_snapshot_qr_and_ticket_workflows(self):
        listing = self._source("assets/asset_list.html")
        detail = self._source("assets/asset_detail.html")
        form = self._source("assets/asset_form.html")
        for token in ("assets:create", "assets:hwagent_batch_import", "assets:label_print",
                      "assets:hardware_report", "assets:detail", "tickets:create"):
            self.assertIn("{% url '" + token + "'", listing)
        for token in ("can_edit", "can_snapshot", "object.requires_component_tracking",
                      "object.current_snapshot", "asset_relationships", "components",
                      "snapshots", "tickets", "visits", "attachments", "data-tabs"):
            self.assertIn(token, detail)
        self.assertIn("data-computer-only", form)
        self.assertIn("data-peripheral-only", form)
        self.assertIn("id_category", form)

    def test_ticket_pages_preserve_sla_roles_and_all_workflow_actions(self):
        listing = self._source("tickets/ticket_list.html")
        detail = self._source("tickets/ticket_detail.html")
        form = self._source("tickets/ticket_form.html")
        for token in ("open_count", "ticket.response_met", "ticket.resolve_met",
                      "tickets:create", "tickets:detail"):
            self.assertIn(token, listing)
        for token in ("is_manager_side", "can_user_confirm", "is_it", "sla.is_paused",
                      "tickets:acknowledge", "tickets:arrive", "tickets:start", "tickets:pause",
                      "tickets:resume", "tickets:resolve", "tickets:user_confirm",
                      "tickets:user_reject", "tickets:it_confirm", "tickets:cancel",
                      "tickets:add_part", "tickets:add_attachment", "tickets:add_note",
                      "ticket.response_minutes_used", "ticket.resolve_minutes_used"):
            self.assertIn(token, detail)
        self.assertIn("tickets:list", form)
        self.assertIn("ساعت SLA", form)

    def test_maintenance_pages_preserve_visit_states_permissions_and_post_actions(self):
        listing = self._source("maintenance/visit_list.html")
        detail = self._source("maintenance/visit_detail.html")
        form = self._source("maintenance/visit_form.html")
        for token in ("counts.planned", "counts.in_progress", "counts.done", "counts.missed",
                      "can_create", "maintenance:visit_create", "reports:visits"):
            self.assertIn(token, listing)
        for token in ("can_manage", "can_confirm", "object.is_overdue",
                      "maintenance:visit_start", "maintenance:visit_bulk_healthy",
                      "maintenance:visit_confirm", "maintenance:visit_complete",
                      "maintenance:check_edit", "checks", "stats.conditions"):
            self.assertIn(token, detail)
        self.assertIn("maintenance:visit_list", form)


class MetronicMigrationCoverageTests(SimpleTestCase):
    """Guard the completed migration wave and retired shell selectors."""

    def test_remaining_application_templates_use_metronic_component_hooks(self):
        template_names = (
            "accounts/password_change.html", "accounts/profile.html", "accounts/profile_form.html",
            "accounts/user_detail.html", "accounts/user_form.html", "accounts/user_list.html",
            "accounts/user_password.html", "org/center_list.html", "org/contract_list.html",
            "org/contract_detail.html", "org/contractor_list.html", "org/contractor_detail.html",
            "org/assignment_list.html", "org/contract_form.html", "org/contractor_form.html",
            "org/department_list.html", "org/location_list.html", "org/simple_form.html",
            "org/assignment_form.html", "core/audit_list.html", "core/notification_list.html",
            "core/search.html", "assets/attachment_form.html", "assets/category_list.html",
            "assets/component_type_list.html", "assets/snapshot_detail.html", "assets/snapshot_form.html",
            "assets/snapshot_pending.html", "assets/snapshot_start.html", "assets/hardware_change_report.html",
            "assets/hwagent_batch_import.html", "assets/hwagent_upload.html", "assets/simple_form.html",
            "tickets/my_tickets.html", "maintenance/my_visits.html", "maintenance/it_request_detail.html",
            "maintenance/repair_detail.html", "maintenance/workflow_list.html", "maintenance/workflow_form.html",
            "maintenance/check_form.html", "reports/home.html", "reports/sla.html", "reports/inventory.html",
            "reports/contractors.html", "reports/failures.html", "reports/repairs.html", "reports/visits.html",
            "integrations/endpoint_list.html", "integrations/endpoint_form.html", "integrations/api_call_list.html",
            "integrations/outbox_detail.html", "integrations/outbox_list.html",
        )
        for template_name in template_names:
            with self.subTest(template=template_name):
                source = Path(get_template(template_name).origin.name).read_text(encoding="utf-8")
                self.assertRegex(source, r"kt-(?:card|btn|table)")

    def test_retired_pre_metronic_shell_classes_are_not_used_in_templates(self):
        template_root = Path(__file__).resolve().parents[2] / "templates"
        retired_classes = {
            "app-shell", "sidebar", "sidebar-brand", "brand-mark", "brand-text", "sidebar-nav",
            "nav-section", "nav-item", "nav-icon", "nav-count", "sidebar-footer", "topbar",
            "topbar-search", "topbar-actions", "icon-btn", "menu-toggle", "user-chip", "user-meta",
            "user-menu", "link-danger", "page-head", "page-title", "page-subtitle", "page-actions",
            "breadcrumbs",
        }
        for template_path in template_root.rglob("*.html"):
            source = template_path.read_text(encoding="utf-8")
            for class_value in re.findall(r"class=[\\\"']([^\\\"']+)[\\\"']", source):
                for class_name in class_value.split():
                    self.assertNotIn(class_name, retired_classes, msg=f"{template_path}: obsolete class {class_name}")


    def test_retired_shell_selectors_are_absent_from_compatibility_stylesheet(self):
        css_path = finders.find("css/itam.css")
        self.assertIsNotNone(css_path)
        css = Path(css_path).read_text(encoding="utf-8")
        for selector in (".app-shell", ".sidebar", ".topbar", ".menu-toggle", ".user-meta",
                         ".user-menu", ".page-actions", ".page-head"):
            with self.subTest(selector=selector):
                self.assertNotRegex(css, re.escape(selector) + r"(?![\\w-])")


class MetronicSharedPartialMigrationTests(SimpleTestCase):
    def test_shared_partials_use_metronic_hooks_and_keep_compatibility_hooks(self):
        expected = {
            "partials/form_fields.html": ("kt-form-item", "kt-form-label", "kt-form-control", "kt-form-message", "form-row"),
            "partials/filter_bar.html": ("kt-form-item", "kt-form-label", "kt-btn-primary", "filter-bar"),
            "partials/pagination.html": ("kt-pagination", "kt-pagination-item", "kt-btn-outline", "pagination"),
            "partials/formset.html": ("kt-form-item", "kt-form-control", "kt-form-message", "data-formset-add"),
            "partials/empty.html": ("kt-alert", "empty-state", 'role="status"'),
            "partials/messages.html": ("kt-alert", "kt-alert-destructive", "alert-danger", "kt-alert-close", "aria-live", "data-dismiss"),
            "partials/action_button.html": ("kt-btn", "data-confirm", "csrf_token"),
        }
        for template_name, tokens in expected.items():
            with self.subTest(template=template_name):
                source = Path(get_template(template_name).origin.name).read_text(encoding="utf-8")
                for token in tokens:
                    self.assertIn(token, source)


class MetronicPrintAndAgentFinalizationTests(SimpleTestCase):
    def test_dedicated_print_templates_use_metronic_print_components(self):
        for template_name in ("assets/label_print.html", "maintenance/visit_print.html", "tickets/ticket_print.html"):
            with self.subTest(template=template_name):
                template = get_template(template_name)
                source = Path(template.origin.name).read_text(encoding="utf-8")
                self.assertIn("itam-print-page", source)
                if template_name == "assets/label_print.html":
                    # Label sheets use a dedicated physical label grid, not dashboard cards.
                    self.assertIn("itam-label-card", source)
                else:
                    self.assertIn("kt-card", source)
                self.assertIn("no-print", source)

        for template_name in ("maintenance/visit_print.html", "tickets/ticket_print.html"):
            source = Path(get_template(template_name).origin.name).read_text(encoding="utf-8")
            self.assertIn("kt-table", source)
            self.assertIn("itam-print-signatures", source)

    def test_print_styles_cover_shell_suppression_and_label_dimensions(self):
        css_path = finders.find("css/itam-metronic.css")
        self.assertIsNotNone(css_path)
        css = Path(css_path).read_text(encoding="utf-8")
        for token in ("@media print", ".itam-sidebar", ".itam-header", ".itam-page-content", ".itam-skip-link", ".messages", "@page itam-landscape", "@page itam-label", "page:itam-label", ".itam-label-print .itam-print-heading", ".itam-label-card", "62mm", "gap:3mm", ".itam-print-signatures"):
            with self.subTest(token=token):
                self.assertIn(token, css)
        self.assertNotIn(r"\n  @page", css)

    def test_standalone_hwagent_has_no_chart_cdn_and_uses_accessible_tabs(self):
        agent_path = Path(__file__).resolve().parents[2] / "HWAgent" / "index.html"
        source = agent_path.read_text(encoding="utf-8")
        self.assertNotIn("cdn.jsdelivr.net", source)
        self.assertNotIn("new Chart(", source)
        self.assertIn('role="tablist"', source)
        self.assertIn('role="tab"', source)
        self.assertIn('role="tabpanel"', source)
        self.assertIn('aria-controls=', source)
        self.assertIn('aria-labelledby=', source)
        self.assertIn('aria-selected=', source)
        self.assertIn('hidden>', source)
        self.assertIn('ArrowLeft', source)
        self.assertIn('ArrowRight', source)
        self.assertIn('tabIndex', source)
        self.assertIn('name="viewport"', source)
        self.assertIn("renderMeters(", source)
        self.assertIn("prefers-reduced-motion", source)


class MetronicDashboardAccessibilityAndRoleTests(SimpleTestCase):
    def test_approval_only_snapshot_widgets_are_role_gated(self):
        source = Path(get_template("core/dashboard.html").origin.name).read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count("{% if user.is_admin_it %}"), 3)
        self.assertIn('aria-labelledby="pending-snapshots-title"', source)
        self.assertIn('pending_snapshots_count', source)

    def test_dashboard_tables_are_keyboard_accessible_regions(self):
        source = Path(get_template("core/dashboard.html").origin.name).read_text(encoding="utf-8")
        self.assertEqual(source.count('role="region" tabindex="0" aria-label="جدول'), 5)
        self.assertGreaterEqual(source.count('<th scope="col">'), 20)

    def test_itam_status_colors_map_to_metronic_badge_variants(self):
        expected = {
            "danger": "destructive", "neutral": "secondary", "primary": "primary",
            "success": "success", "warning": "warning", "info": "info",
        }
        for source, target in expected.items():
            with self.subTest(source=source):
                self.assertEqual(filter_metronic_badge_variant(source), target)
        self.assertEqual(filter_metronic_badge_variant(None), "secondary")

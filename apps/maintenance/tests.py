"""Regression tests for maintenance access boundaries."""
import datetime as dt

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.core.constants import EVENT_VISIT_PLANNED, VISIT_DONE
from apps.core.models import Notification, OutboxEvent
from apps.assets.models import Asset, AssetCategory
from apps.org.models import Center, Contract, ContractCenterAssignment, Contractor, OrganizationalUnit

from .forms import VisitForm
from .models import MaintenanceVisit, VisitAssetCheck
from .services import (
    can_confirm_visit, can_manage_visit, confirm_visit, complete_visit, save_check,
    visible_checks, visible_visits,
)
from .views import VisitCreateView, VisitUpdateView, _emit_visit_planned


class ProvincialMaintenanceScopeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        national = OrganizationalUnit.objects.create(
            name="Test National", code="MNT-NAT", unit_type=OrganizationalUnit.UNIT_NATIONAL
        )
        cls.province = OrganizationalUnit.objects.create(
            name="Province One", code="MNT-P1",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        other_province = OrganizationalUnit.objects.create(
            name="Province Two", code="MNT-P2",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        county_one = OrganizationalUnit.objects.create(
            name="County One", code="MNT-C1",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=cls.province,
        )
        county_two = OrganizationalUnit.objects.create(
            name="County Two", code="MNT-C2",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=other_province,
        )
        cls.center = Center.objects.create(
            name="Maintenance Center One", code="MNT-CENTER1", parent_unit=county_one
        )
        cls.other_center = Center.objects.create(
            name="Maintenance Center Two", code="MNT-CENTER2", parent_unit=county_two
        )
        cls.contractor = Contractor.objects.create(name="Maintenance Test Contractor")
        cls.contract = Contract.objects.create(
            contractor=cls.contractor, province=cls.province,
            number="MNT-CONTRACT-1", title="Provincial contract",
            is_provincial=True,
            start_date=timezone.localdate() - dt.timedelta(days=10),
            end_date=timezone.localdate() + dt.timedelta(days=100),
            visit_interval_days=30,
        )
        cls.provincial_admin = User.objects.create_user(
            username="maintenance-provincial-admin", password="TestPass!9382",
            role=User.ROLE_ADMIN_PROVINCE, org_unit=cls.province,
        )
        cls.contract.centers.add(cls.center, cls.other_center)
        ContractCenterAssignment.objects.create(
            contract=cls.contract, center=cls.center,
            start_date=timezone.localdate(),
            status=ContractCenterAssignment.STATUS_ACTIVE,
            assigned_by=cls.provincial_admin,
        )
        category = AssetCategory.objects.create(name="Maintenance Test Category", code="MNT")
        cls.asset = Asset.objects.create(
            asset_tag="MNT-ASSET-1", category=category, contract=cls.contract,
            center=cls.center, status="active",
        )
        cls.other_asset = Asset.objects.create(
            asset_tag="MNT-ASSET-2", category=category, contract=cls.contract,
            center=cls.other_center, status="active",
        )
        cls.visit = MaintenanceVisit.objects.create(
            number="MNT-VISIT-1", contract=cls.contract, contractor=cls.contractor,
            center=None, sequence_number=1,
            scheduled_date=timezone.localdate(),
        )
        cls.own_check = VisitAssetCheck.objects.create(visit=cls.visit, asset=cls.asset)
        cls.foreign_check = VisitAssetCheck.objects.create(visit=cls.visit, asset=cls.other_asset)
        cls.center_it = User.objects.create_user(
            username="maintenance-center-it", password="TestPass!9382",
            role=User.ROLE_ADMIN_IT, center=cls.center,
        )

    def test_provincial_admin_cannot_select_or_schedule_foreign_contract(self):
        foreign_contract = Contract.objects.create(
            contractor=self.contractor,
            province=self.other_center.parent_unit.parent,
            number="MNT-CONTRACT-FOREIGN",
            title="Foreign contract",
            is_provincial=False,
            start_date=timezone.localdate() - dt.timedelta(days=10),
            end_date=timezone.localdate() + dt.timedelta(days=100),
            visit_interval_days=30,
        )
        foreign_contract.centers.add(self.other_center)

        form = VisitForm(user=self.provincial_admin)
        self.assertFalse(form.fields["contract"].queryset.filter(
            pk=foreign_contract.pk
        ).exists())

        view = VisitCreateView()
        view.request = type("Request", (), {"user": self.provincial_admin})()
        visit = MaintenanceVisit(
            contract=foreign_contract,
            contractor=self.contractor,
            scheduled_date=timezone.localdate(),
        )
        with self.assertRaises(PermissionDenied):
            view._bind_visit_center(visit)

    def test_provincial_admin_only_sees_checks_for_scoped_assets(self):
        checks = visible_checks(self.provincial_admin, self.visit)
        self.assertEqual(set(checks.values_list("pk", flat=True)), {self.own_check.pk})

    def test_provincial_admin_cannot_save_check_for_foreign_asset(self):
        with self.assertRaises(PermissionDenied):
            save_check(self.foreign_check, self.provincial_admin, notes="unauthorized change")
        self.foreign_check.refresh_from_db()
        self.assertEqual(self.foreign_check.notes, "")

    def test_check_edit_endpoint_hides_foreign_asset_check(self):
        client = Client()
        client.force_login(self.provincial_admin)
        response = client.get(reverse("maintenance:check_edit", args=[self.foreign_check.pk]))
        self.assertEqual(response.status_code, 404)

    def test_province_admin_cannot_open_foreign_visit_edit_page(self):
        foreign_contract = Contract.objects.create(
            contractor=self.contractor,
            province=self.other_center.parent_unit.parent,
            number="MNT-CONTRACT-FOREIGN-VISIT",
            title="Foreign visit contract",
            start_date=timezone.localdate() - dt.timedelta(days=1),
            end_date=timezone.localdate() + dt.timedelta(days=30),
        )
        foreign_visit = MaintenanceVisit.objects.create(
            contract=foreign_contract,
            contractor=self.contractor,
            center=None,
            sequence_number=1,
            scheduled_date=timezone.localdate(),
        )
        client = Client()
        client.force_login(self.provincial_admin)
        response = client.get(reverse("maintenance:visit_update", args=[foreign_visit.pk]))
        self.assertEqual(response.status_code, 404)

    def test_technician_cannot_access_visit_or_check_misbound_to_another_contract_province(self):
        second_contract = Contract.objects.create(
            contractor=self.contractor,
            province=self.other_center.parent_unit.parent,
            number="MNT-CONTRACT-2",
            title="Second province contract",
            is_provincial=True,
            start_date=timezone.localdate() - dt.timedelta(days=10),
            end_date=timezone.localdate() + dt.timedelta(days=100),
            visit_interval_days=30,
        )
        province_admin_b = User.objects.create_user(
            username="maintenance-province-b-admin",
            password="TestPass!9382",
            role=User.ROLE_ADMIN_PROVINCE,
            org_unit=self.other_center.parent_unit.parent,
        )
        ContractCenterAssignment.objects.create(
            contract=second_contract, center=self.other_center,
            start_date=timezone.localdate(),
            status=ContractCenterAssignment.STATUS_ACTIVE,
            assigned_by=province_admin_b,
        )
        technician = User.objects.create_user(
            username="maintenance-multi-province-tech",
            password="TestPass!9382",
            role=User.ROLE_TECHNICIAN,
            contractor=self.contractor,
        )
        # The technician legitimately has active contracts in both provinces.
        self.assertTrue(technician.get_active_contractor_contracts().filter(
            pk__in=[self.contract.pk, second_contract.pk]
        ).count() == 2)

        # A check for a Province Two asset must not be attached to a Province One visit.
        self.assertFalse(visible_checks(technician, self.visit).filter(
            pk=self.foreign_check.pk
        ).exists())
        with self.assertRaises(PermissionDenied):
            save_check(self.foreign_check, technician, notes="cross-province tampering")

        # Even with both provinces in the technician's center scope, the visit's
        # center must belong to the same province as its contract.
        misbound_visit = MaintenanceVisit.objects.create(
            number="MNT-VISIT-MISBOUND",
            contract=self.contract,
            contractor=self.contractor,
            center=self.other_center,
            sequence_number=2,
            scheduled_date=timezone.localdate(),
        )
        self.assertFalse(visible_visits(technician).filter(
            pk=misbound_visit.pk
        ).exists())
        self.assertFalse(can_manage_visit(technician, misbound_visit))

        # A visit whose center is local but whose contract belongs to another
        # province must also be hidden from provincial and center IT users.
        misbound_local_center_visit = MaintenanceVisit.objects.create(
            number="MNT-MISBOUND-LOCAL",
            contract=second_contract,
            contractor=self.contractor,
            center=self.center,
            sequence_number=3,
            scheduled_date=timezone.localdate(),
        )
        self.assertFalse(visible_visits(self.provincial_admin).filter(
            pk=misbound_local_center_visit.pk
        ).exists())
        self.assertFalse(visible_visits(self.center_it).filter(
            pk=misbound_local_center_visit.pk
        ).exists())

    def test_technician_sees_only_checks_assigned_to_the_visit_contract(self):
        from .services import visible_checks

        same_province_center = Center.objects.create(
            name="مرکز هم‌استانی با قرارداد دیگر",
            code="MNT-CENTER1-OTHER-CONTRACT",
            parent_unit=self.center.parent_unit,
        )
        second_contract = Contract.objects.create(
            contractor=self.contractor,
            province=self.province,
            number="MNT-CONTRACT-OTHER-CENTER",
            title="قرارداد دیگر در همان استان",
            start_date=timezone.localdate() - dt.timedelta(days=5),
            end_date=timezone.localdate() + dt.timedelta(days=30),
        )
        ContractCenterAssignment.objects.create(
            contract=second_contract, center=same_province_center,
            start_date=timezone.localdate(),
            status=ContractCenterAssignment.STATUS_ACTIVE,
            assigned_by=self.provincial_admin,
        )
        other_asset = Asset.objects.create(
            asset_tag="MNT-ASSET-OTHER-CONTRACT",
            category=self.asset.category, contract=second_contract,
            center=same_province_center, status="active",
        )
        other_contract_check = VisitAssetCheck.objects.create(
            visit=self.visit, asset=other_asset,
        )
        technician = User.objects.create_user(
            username="maintenance-same-province-tech",
            password="TestPass!9382", role=User.ROLE_TECHNICIAN,
            contractor=self.contractor,
        )

        self.assertTrue(visible_visits(technician).filter(pk=self.visit.pk).exists())
        visible_ids = set(visible_checks(technician, self.visit).values_list("pk", flat=True))
        self.assertIn(self.own_check.pk, visible_ids)
        self.assertNotIn(other_contract_check.pk, visible_ids)

    def test_center_it_cannot_open_visit_scheduling_page(self):
        client = Client()
        client.force_login(self.center_it)
        response = client.get(reverse("maintenance:visit_create"))
        self.assertEqual(response.status_code, 403)


    def test_center_it_can_review_and_confirm_province_wide_visit_for_own_assets(self):
        self.assertTrue(visible_visits(self.center_it).filter(pk=self.visit.pk).exists())
        checks = visible_checks(self.center_it, self.visit)
        self.assertEqual(set(checks.values_list("pk", flat=True)), {self.own_check.pk})
        self.assertTrue(can_confirm_visit(self.center_it, self.visit))
        self.assertFalse(can_manage_visit(self.center_it, self.visit))
        with self.assertRaises(ValidationError):
            confirm_visit(self.visit, self.center_it, "تایید زودهنگام")

        self.visit.status = "done"
        self.visit.save(update_fields=["status", "updated_at"])
        self.assertTrue(can_confirm_visit(self.center_it, self.visit))
        confirm_visit(self.visit, self.center_it, "تایید مرکز")
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.it_confirmed_by_id, self.center_it.pk)
        self.assertIsNotNone(self.visit.it_confirmed_at)

    def test_center_it_cannot_confirm_visit_without_a_scoped_asset(self):
        other_it = User.objects.create_user(
            username="maintenance-other-center-it", password="TestPass!9382",
            role=User.ROLE_ADMIN_IT, center=self.other_center,
        )
        self.assertFalse(visible_visits(other_it).filter(pk=self.visit.pk).exists())
        self.assertFalse(can_confirm_visit(other_it, self.visit))



    def test_missed_visit_notifications_are_center_scoped(self):
        from .services import mark_missed_visits

        second_center = Center.objects.create(
            name="Maintenance Center One-B",
            code="MNT-CENTER1-B",
            parent_unit=self.center.parent_unit,
        )
        self.contract.centers.add(second_center)
        ContractCenterAssignment.objects.create(
            contract=self.contract, center=second_center,
            start_date=timezone.localdate(),
            status=ContractCenterAssignment.STATUS_ACTIVE,
            assigned_by=self.provincial_admin,
        )
        it_a = User.objects.create_user(
            username="maintenance-it-a", password="pass12345",
            role=User.ROLE_ADMIN_IT, center=self.center,
        )
        it_b = User.objects.create_user(
            username="maintenance-it-b", password="pass12345",
            role=User.ROLE_ADMIN_IT, center=second_center,
        )
        yesterday = timezone.localdate() - dt.timedelta(days=1)
        visit_a = MaintenanceVisit.objects.create(
            number="MNT-MISSED-A", contract=self.contract, contractor=self.contractor,
            center=self.center, sequence_number=10,
            scheduled_date=yesterday - dt.timedelta(days=5),
            scheduled_end_date=yesterday,
        )
        visit_b = MaintenanceVisit.objects.create(
            number="MNT-MISSED-B", contract=self.contract, contractor=self.contractor,
            center=second_center, sequence_number=11,
            scheduled_date=yesterday - dt.timedelta(days=5),
            scheduled_end_date=yesterday,
        )

        mark_missed_visits()

        self.assertTrue(it_a.notifications.filter(
            title=f"بازدید {visit_a.number} انجام نشد"
        ).exists())
        self.assertFalse(it_b.notifications.filter(
            title=f"بازدید {visit_a.number} انجام نشد"
        ).exists())
        self.assertTrue(it_b.notifications.filter(
            title=f"بازدید {visit_b.number} انجام نشد"
        ).exists())
        self.assertFalse(it_a.notifications.filter(
            title=f"بازدید {visit_b.number} انجام نشد"
        ).exists())




    def test_country_admin_can_schedule_current_province_visit(self):
        country_admin = User.objects.create_user(
            username="maintenance-country-admin",
            password="TestPass!9382",
            role=User.ROLE_ADMIN_COUNTRY,
        )
        view = VisitCreateView()
        view.request = type("Request", (), {"user": country_admin})()
        visit = MaintenanceVisit(
            contract=self.contract,
            contractor=self.contractor,
            scheduled_date=timezone.localdate(),
        )
        view._bind_visit_center(visit)
        self.assertIsNone(visit.center)
        self.assertEqual(visit.contractor_id, self.contractor.pk)

    def test_visit_form_hides_workflow_status_and_excludes_expired_contracts(self):
        expired = Contract.objects.create(
            contractor=self.contractor,
            province=self.province,
            number="MNT-CONTRACT-EXPIRED",
            title="Expired contract",
            start_date=timezone.localdate() - dt.timedelta(days=100),
            end_date=timezone.localdate() - dt.timedelta(days=1),
            visit_interval_days=30,
        )
        form = VisitForm(user=self.provincial_admin)
        self.assertNotIn("status", form.fields)
        self.assertFalse(form.fields["contract"].queryset.filter(pk=expired.pk).exists())

    def test_visit_update_form_keeps_contract_and_sequence_immutable(self):
        request = RequestFactory().get("/maintenance/visits/")
        request.user = self.provincial_admin
        view = VisitUpdateView()
        view.request = request
        view.args = ()
        view.kwargs = {}
        view.object = self.visit
        form = view.get_form()
        self.assertNotIn("contract", form.fields)
        self.assertNotIn("sequence_number", form.fields)
        self.assertNotIn("status", form.fields)

    def test_requesters_cannot_view_contractor_visit_reports(self):
        requester = User.objects.create_user(
            username="maintenance-requester",
            password="TestPass!9382",
            role=User.ROLE_REQUESTER,
            center=self.center,
        )
        self.assertFalse(visible_visits(requester).filter(pk=self.visit.pk).exists())
        self.assertFalse(visible_checks(requester, self.visit).exists())

    def test_technician_only_sees_visits_assigned_to_them_or_unassigned(self):
        technician_a = User.objects.create_user(
            username="maintenance-tech-a",
            password="TestPass!9382",
            role=User.ROLE_TECHNICIAN,
            contractor=self.contractor,
        )
        technician_b = User.objects.create_user(
            username="maintenance-tech-b",
            password="TestPass!9382",
            role=User.ROLE_TECHNICIAN,
            contractor=self.contractor,
        )
        self.visit.technician = technician_a
        self.visit.save(update_fields=["technician", "updated_at"])
        self.assertTrue(visible_visits(technician_a).filter(pk=self.visit.pk).exists())
        self.assertFalse(visible_visits(technician_b).filter(pk=self.visit.pk).exists())
        self.assertFalse(can_manage_visit(technician_b, self.visit))

        self.visit.technician = None
        self.visit.save(update_fields=["technician", "updated_at"])
        self.assertTrue(visible_visits(technician_a).filter(pk=self.visit.pk).exists())
        self.assertTrue(visible_visits(technician_b).filter(pk=self.visit.pk).exists())

    def test_force_completion_requires_authorized_actor_and_audited_reason(self):
        from django.core.exceptions import PermissionDenied

        technician = User.objects.create_user(
            username="maintenance-force-tech",
            password="TestPass!9382",
            role=User.ROLE_TECHNICIAN,
            contractor=self.contractor,
        )
        with self.assertRaises(PermissionDenied):
            complete_visit(
                self.visit,
                technician,
                force=True,
                force_reason="دلیل آزمایشی",
            )
        with self.assertRaises(ValidationError):
            complete_visit(self.visit, self.provincial_admin, force=True)

        complete_visit(
            self.visit,
            self.provincial_admin,
            force=True,
            force_reason="عدم دسترسی به تجهیز در زمان بازدید",
        )
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.status, VISIT_DONE)
        self.assertIsNone(self.visit.technician_id)
        self.assertIn("عدم دسترسی به تجهیز", self.visit.report_text)

    def test_completed_visit_cannot_be_reconfirmed_or_have_checks_edited(self):
        self.visit.status = VISIT_DONE
        self.visit.save(update_fields=["status", "updated_at"])
        confirm_visit(self.visit, self.center_it, "تایید اولیه")
        with self.assertRaises(ValidationError):
            confirm_visit(self.visit, self.center_it, "تلاش برای بازنویسی تایید")
        with self.assertRaises(ValidationError):
            save_check(
                self.own_check,
                self.provincial_admin,
                notes="تغییر پس از تایید",
            )

    def test_manual_visit_planning_emits_outbox_event(self):
        _emit_visit_planned(self.visit, self.provincial_admin)
        self.assertTrue(
            OutboxEvent.objects.filter(
                event_type=EVENT_VISIT_PLANNED,
                aggregate_type="MaintenanceVisit",
                aggregate_id=str(self.visit.pk),
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.center_it,
                title=f"بازدید {self.visit.number} برنامه‌ریزی شد",
            ).exists()
        )

    def test_inactive_center_assets_do_not_block_visit_completion(self):
        from .services import complete_visit, populate_checks

        inactive_center = Center.objects.create(
            name="Inactive Maintenance Center",
            code="MNT-CENTER-INACTIVE",
            parent_unit=self.center.parent_unit,
            is_active=False,
        )
        inactive_asset = Asset.objects.create(
            asset_tag="MNT-ASSET-INACTIVE",
            category=self.asset.category,
            contract=self.contract,
            center=inactive_center,
            status="active",
        )
        visit = MaintenanceVisit.objects.create(
            number="MNT-VISIT-ACTIVE-SCOPE",
            contract=self.contract,
            contractor=self.contractor,
            center=None,
            sequence_number=20,
            scheduled_date=timezone.localdate(),
        )

        populate_checks(visit)
        self.assertFalse(visit.checks.filter(asset=inactive_asset).exists())

        # A legacy check may remain after its center is deactivated; it must
        # not become an invisible blocker for the operational completion flow.
        VisitAssetCheck.objects.create(visit=visit, asset=inactive_asset, checked=False)
        visit.checks.filter(asset__center__is_active=True).update(checked=True)

        complete_visit(visit, self.provincial_admin)
        visit.refresh_from_db()
        self.assertEqual(visit.status, "done")

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.assets.models import Asset, AssetCategory
from apps.integrations.models import ApiCallLog, OutboxEvent
from apps.integrations.views import visible_outbox_events
from apps.org.models import Center, OrganizationalUnit


class OutboxCenterScopeTests(TestCase):
    def setUp(self):
        national = OrganizationalUnit.objects.create(
            name="کشور لاگ", code="OUTBOX-NAT",
            unit_type=OrganizationalUnit.UNIT_NATIONAL,
        )
        province = OrganizationalUnit.objects.create(
            name="استان لاگ", code="OUTBOX-PROV",
            unit_type=OrganizationalUnit.UNIT_PROVINCE, parent=national,
        )
        county = OrganizationalUnit.objects.create(
            name="شهرستان لاگ", code="OUTBOX-COUNTY",
            unit_type=OrganizationalUnit.UNIT_COUNTY, parent=province,
        )
        self.center_a = Center.objects.create(
            name="مرکز الف لاگ", code="OUTBOX-A", parent_unit=county,
        )
        self.center_b = Center.objects.create(
            name="مرکز ب لاگ", code="OUTBOX-B", parent_unit=county,
        )
        self.user = User.objects.create_user(
            username="outbox-it-a", password="test-password",
            role=User.ROLE_ADMIN_IT, center=self.center_a,
        )
        category = AssetCategory.objects.create(name="رایانه لاگ", code="OUTBOX-PC")
        self.asset_a = Asset.objects.create(
            asset_tag="OUTBOX-ASSET-A", category=category, center=self.center_a,
        )
        self.asset_b = Asset.objects.create(
            asset_tag="OUTBOX-ASSET-B", category=category, center=self.center_b,
        )
        self.event_a = OutboxEvent.objects.create(
            event_type="asset.created", aggregate_type="Asset",
            aggregate_id=str(self.asset_a.pk), payload={"asset_tag": self.asset_a.asset_tag},
        )
        self.event_b = OutboxEvent.objects.create(
            event_type="asset.created", aggregate_type="Asset",
            aggregate_id=str(self.asset_b.pk), payload={"asset_tag": self.asset_b.asset_tag},
        )
        self.unknown_event = OutboxEvent.objects.create(
            event_type="asset.updated", aggregate_type="UnmappedAggregate",
            aggregate_id="1", payload={"private": "must remain hidden"},
        )
        ApiCallLog.objects.create(
            event=self.event_a, method="POST", url="https://internal.example/a",
            request_body="center-a payload", ok=True,
        )
        ApiCallLog.objects.create(
            event=self.event_b, method="POST", url="https://internal.example/b",
            request_body="center-b payload", ok=True,
        )

    def test_event_queryset_is_limited_to_users_center(self):
        visible_ids = set(visible_outbox_events(self.user).values_list("pk", flat=True))
        self.assertEqual(visible_ids, {self.event_a.pk})

    def test_outbox_list_and_detail_do_not_disclose_foreign_events(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("integrations:outbox_list"))
        self.assertEqual(response.status_code, 200)
        visible_ids = {event.pk for event in response.context["object_list"]}
        self.assertEqual(visible_ids, {self.event_a.pk})

        own_detail = self.client.get(
            reverse("integrations:outbox_detail", args=[self.event_a.pk])
        )
        foreign_detail = self.client.get(
            reverse("integrations:outbox_detail", args=[self.event_b.pk])
        )
        self.assertEqual(own_detail.status_code, 200)
        self.assertEqual(foreign_detail.status_code, 404)

    def test_api_call_logs_are_limited_to_visible_events(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("integrations:api_call_list"))
        self.assertEqual(response.status_code, 200)
        visible_logs = list(response.context["object_list"])
        self.assertEqual(len(visible_logs), 1)
        self.assertEqual(visible_logs[0].event_id, self.event_a.pk)

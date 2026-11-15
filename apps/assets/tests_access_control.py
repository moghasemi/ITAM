"""Regression tests for global asset taxonomy administration."""

from django.test import TestCase

from apps.accounts.models import User


class CenterItAssetTaxonomyAuthorizationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.center_it = User.objects.create_user(
            username="center-it-taxonomy",
            password="Strong-Test-Password-2026!",
            role=User.ROLE_ADMIN_IT,
        )

    def test_center_it_cannot_manage_global_asset_categories_or_component_types(self):
        self.client.login(username="center-it-taxonomy", password="Strong-Test-Password-2026!")
        paths = (
            "/assets/categories/",
            "/assets/categories/add/",
            "/assets/categories/1/edit/",
            "/assets/component-types/",
            "/assets/component-types/add/",
            "/assets/component-types/1/edit/",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)

"""End-to-end session/CSRF contract for store UI and existing RBAC."""
import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from .models import Schedule, UserWarehouseAccess, Warehouse


class StoreSessionAuthTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.store = Warehouse.objects.create(
            code="T_BAN", name="Toko Bandara", kind="STORE", odoo_id=405
        )
        Warehouse.objects.create(
            code="JP", name="Dapur Jajan Pasar", kind="KITCHEN", odoo_id=406
        )
        Schedule.objects.create(code="SUBUH", name="Subuh")
        user = get_user_model().objects.create_user(username="store1", password="correct-test-pass")
        group = Group.objects.create(name="STORE")
        user.groups.add(group)
        UserWarehouseAccess.objects.create(user=user, warehouse=self.store)
        self.user = user

    def test_csrf_required_for_login_and_authenticated_me(self):
        login_url = reverse("store-session-login")
        payload = json.dumps({"username": "store1", "password": "correct-test-pass"})
        self.assertEqual(
            self.client.post(login_url, payload, content_type="application/json").status_code,
            403,
        )
        csrf = self.client.get(reverse("store-session-csrf"))
        self.assertEqual(csrf.status_code, 200)
        token = self.client.cookies["csrftoken"].value
        logged = self.client.post(
            login_url, payload, content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(logged.status_code, 200, logged.content)
        response = self.client.get(reverse("store-session-me"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stores"][0]["code"], "T_BAN")
        self.assertEqual(response.json()["kitchens"][0]["code"], "JP")
        self.assertEqual(response.json()["schedules"][0]["code"], "SUBUH")
        token = self.client.cookies["csrftoken"].value
        self.assertEqual(
            self.client.post(
                reverse("store-session-logout"),
                HTTP_X_CSRFTOKEN=token,
            ).status_code, 200
        )
        self.assertEqual(self.client.get(reverse("store-session-me")).status_code, 401)

    def test_react_workspace_served_from_existing_django_port(self):
        # CI builds frontend/dist/index.html before backend tests.
        response = self.client.get(reverse("store-workspace"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admin Toko")
        self.assertContains(response, "/static/frontend/assets/")

    def test_default_schedules_seed_does_not_override_existing(self):
        from django.core.management import call_command

        Schedule.objects.filter(code="SUBUH").update(name="Subuh Custom")
        call_command("seed_order_schedules", verbosity=0)
        call_command("seed_order_schedules", verbosity=0)
        self.assertEqual(Schedule.objects.get(code="SUBUH").name, "Subuh Custom")
        self.assertEqual(
            set(Schedule.objects.values_list("code", flat=True)),
            {"SUBUH", "PAGI", "SIANG"},
        )

    def test_bad_password_and_disallowed_group(self):
        self.client.get(reverse("store-session-csrf"))
        token = self.client.cookies["csrftoken"].value
        url = reverse("store-session-login")
        wrong = json.dumps({"username": "store1", "password": "wrong"})
        self.assertEqual(self.client.post(
            url, wrong, content_type="application/json", HTTP_X_CSRFTOKEN=token
        ).status_code, 401)
        group = Group.objects.create(name="PACKING")
        self.user.groups.clear()
        self.user.groups.add(group)
        self.assertEqual(self.client.post(
            url, json.dumps({"username": "store1", "password": "correct-test-pass"}),
            content_type="application/json", HTTP_X_CSRFTOKEN=token
        ).status_code, 401)

    def test_superuser_can_open_every_store(self):
        Warehouse.objects.create(
            code="T_KD", name="Toko Kedaton", kind="STORE", odoo_id=407
        )
        user = get_user_model().objects.create_superuser(
            username="admin-ro", password="a-test-password", email="admin@example.test"
        )
        self.client.force_login(user)
        response = self.client.get(reverse("store-session-me"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["user"]["admin"])
        self.assertEqual({x["code"] for x in response.json()["stores"]}, {"T_BAN", "T_KD"})

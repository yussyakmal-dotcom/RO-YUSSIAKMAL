"""Regression tests: block category mapping and inspect true MO operation types."""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from .odoo_readonly import OdooReadOnlyClient


class MoOperationTypesTests(SimpleTestCase):
    def test_legacy_category_mapping_always_fails_even_with_apply(self):
        for args in [(), ("--apply",)]:
            with self.assertRaises(CommandError):
                call_command("init_kitchen_mapping", *args, stdout=StringIO())

    def test_operation_types_are_read_only(self):
        rows = [
            {
                "id": 101, "name": "ROTI: Manufacturing",
                "code": "mrp_operation",
                "warehouse_id": [15, "Dapur Roti"],
                "default_location_src_id": [20, "ROTI/Stock"],
                "default_location_dest_id": [20, "ROTI/Stock"],
            }
        ]
        output = StringIO()
        with patch.object(OdooReadOnlyClient, "from_env") as client_factory:
            client = client_factory.return_value
            client.all_records.return_value = iter(rows)
            call_command("odoo_mo_operation_types", stdout=output)

        client.all_records.assert_called_once_with(
            "stock.picking.type",
            ["id", "name", "code", "warehouse_id",
             "default_location_src_id", "default_location_dest_id"],
            domain=[["code", "=", "mrp_operation"]],
        )
        text = output.getvalue()
        self.assertIn('"odoo_operation_type_id": 101', text)
        self.assertIn('"warehouse_name": "Dapur Roti"', text)
        self.assertIn("READ-ONLY", text)

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ro_core", "0002_order_template_flags"),
    ]

    operations = [
        migrations.AlterField(
            model_name="storeorder",
            name="status",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("DRAFT", "Draft"),
                    ("KIRIM", "Kirim"),
                    ("PROSES_PRODUKSI", "Proses Produksi"),
                    ("NO_ORDER", "No Order"),
                ],
                default="DRAFT",
            ),
        ),
    ]

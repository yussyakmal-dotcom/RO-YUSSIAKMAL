from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ro_core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="productionassignment",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="productionassignment",
            name="sort_order",
            field=models.PositiveIntegerField(default=0),
        ),
    ]

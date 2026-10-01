from django.db import migrations


def add_initial_items(apps, schema_editor):
    PriceItem = apps.get_model("prices", "PriceItem")
    for order, name in enumerate(("نقدی ۲۴", "نقدی ۴۸", "سکه تمام", "نیم‌سکه")):
        PriceItem.objects.get_or_create(
            name=name,
            defaults={"unit": "ریال", "sort_order": order},
        )


class Migration(migrations.Migration):
    dependencies = [("prices", "0001_initial")]

    operations = [migrations.RunPython(add_initial_items, migrations.RunPython.noop)]

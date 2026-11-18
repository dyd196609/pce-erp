from decimal import Decimal

from django.db import migrations


STANDARD_UNITS = (
    ("kg", "千克", "kg", "mass", 4),
    ("m", "米", "m", "length", 4),
    ("m2", "平方米", "m²", "area", 4),
    ("根", "根", "根", "count", 0),
    ("桶", "桶", "桶", "count", 0),
    ("袋", "袋", "袋", "count", 0),
)


def seed_standard_units(apps, schema_editor):
    UnitOfMeasure = apps.get_model("masterdata", "UnitOfMeasure")
    for code, name, symbol, dimension, decimal_places in STANDARD_UNITS:
        unit, created = UnitOfMeasure.objects.get_or_create(
            company_id=1,
            code=code,
            defaults={
                "name": name,
                "symbol": symbol,
                "dimension": dimension,
                "decimal_places": decimal_places,
                "conversion_base_id": None,
                "conversion_factor": Decimal("1"),
                "is_active": True,
            },
        )
        if not created:
            unit.name = name
            unit.symbol = symbol
            unit.dimension = dimension
            unit.decimal_places = decimal_places
            unit.conversion_base_id = None
            unit.conversion_factor = Decimal("1")
            unit.is_active = True
            unit.save(update_fields=(
                "name", "symbol", "dimension", "decimal_places",
                "conversion_base", "conversion_factor", "is_active",
            ))


def remove_standard_units(apps, schema_editor):
    UnitOfMeasure = apps.get_model("masterdata", "UnitOfMeasure")
    # The approved production baseline contains none of these six codes.
    # PROTECT relationships deliberately make rollback fail safely if a future
    # authorized business write has started using one of them.
    UnitOfMeasure.objects.filter(
        company_id=1,
        code__in=[row[0] for row in STANDARD_UNITS],
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("masterdata", "0011_foundation_identity_uom_and_encoders"),
    ]

    operations = [
        migrations.RunPython(seed_standard_units, remove_standard_units),
    ]

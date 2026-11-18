from django.db import migrations, models


DELIVERY_LOCATION_CYCLE = (
    ("湖北", "武汉"),
    ("四川", "成都"),
    ("福建", "厦门"),
    ("河南", "郑州"),
    ("陕西", "西安"),
    ("安徽", "合肥"),
    ("广东", "广州"),
    ("浙江", "宁波"),
    ("江苏", "苏州"),
    ("山东", "济南"),
)


def _company_name(name):
    value = str(name or "").strip()
    return value if value.endswith("公司") else f"{value}有限公司"


def populate_supplier_delivery_address(apps, schema_editor):
    Supplier = apps.get_model("procurement", "Supplier")
    for index, supplier in enumerate(Supplier.objects.order_by("code", "id")):
        if str(supplier.delivery_address or "").strip():
            continue
        province, city = DELIVERY_LOCATION_CYCLE[index % len(DELIVERY_LOCATION_CYCLE)]
        supplier.delivery_address = (
            f"{province}省{city}市{_company_name(supplier.name)}"
        )
        supplier.save(update_fields=["delivery_address"])


class Migration(migrations.Migration):
    dependencies = [
        ("procurement", "0017_supplier_category_classification_v11428427227"),
    ]

    operations = [
        migrations.AddField(
            model_name="supplier",
            name="delivery_address",
            field=models.CharField(default="", max_length=255),
        ),
        migrations.RunPython(
            populate_supplier_delivery_address, migrations.RunPython.noop
        ),
    ]

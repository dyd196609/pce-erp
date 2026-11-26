from django.db import migrations, models
import django.db.models.deletion


def link_existing_units(apps, schema_editor):
    Material = apps.get_model("masterdata", "Material")
    UnitOfMeasure = apps.get_model("masterdata", "UnitOfMeasure")
    for material in Material.objects.all().iterator():
        base_text = str(material.unit or "").strip()
        if base_text:
            base, _ = UnitOfMeasure.objects.get_or_create(
                company_id=material.company_id,
                code=base_text,
                defaults={"name": base_text, "is_active": True},
            )
            material.base_uom_id = base.pk
        purchase_text = str(material.purchase_unit or "").strip()
        if purchase_text:
            purchase, _ = UnitOfMeasure.objects.get_or_create(
                company_id=material.company_id,
                code=purchase_text,
                defaults={"name": purchase_text, "is_active": True},
            )
            material.purchase_uom_id = purchase.pk
        material.save(update_fields=["base_uom_id", "purchase_uom_id"])


class Migration(migrations.Migration):
    dependencies = [("masterdata", "0008_material_supply_governance_a0")]

    operations = [
        migrations.CreateModel(
            name="UnitOfMeasure",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=20)),
                ("name", models.CharField(max_length=50)),
                ("company_id", models.BigIntegerField()),
                ("decimal_places", models.PositiveSmallIntegerField(default=4)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "unit_of_measure", "ordering": ["company_id", "code"]},
        ),
        migrations.AddConstraint(
            model_name="unitofmeasure",
            constraint=models.UniqueConstraint(fields=("company_id", "code"), name="uom_company_code_unique"),
        ),
        migrations.AddConstraint(
            model_name="unitofmeasure",
            constraint=models.CheckConstraint(condition=models.Q(decimal_places__lte=6), name="uom_decimal_places_lte_6"),
        ),
        migrations.AddField(
            model_name="material", name="base_uom",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="base_materials", to="masterdata.unitofmeasure"),
        ),
        migrations.AddField(
            model_name="material", name="purchase_uom",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="purchase_materials", to="masterdata.unitofmeasure"),
        ),
        migrations.RunPython(link_existing_units, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunSQL(
                sql=(
                    "CREATE TABLE IF NOT EXISTS code_rule ("
                    "id integer NOT NULL PRIMARY KEY AUTOINCREMENT, "
                    "entity_type varchar(50) NOT NULL, prefix varchar(20) NULL, "
                    "date_format varchar(20) NULL, seq_length integer NOT NULL DEFAULT 4, "
                    "current_seq integer NOT NULL DEFAULT 0, company_id bigint NOT NULL, "
                    "created_at datetime NOT NULL, "
                    "CONSTRAINT code_rule_company_entity_unique UNIQUE(company_id, entity_type))"
                ),
                reverse_sql="DROP TABLE IF EXISTS code_rule",
            )],
            state_operations=[
                migrations.AlterModelOptions(
                    name="coderule",
                    options={"managed": True, "verbose_name": "编码规则", "verbose_name_plural": "编码规则"},
                ),
                migrations.AlterField(
                    model_name="coderule", name="entity_type",
                    field=models.CharField(max_length=50),
                ),
                migrations.AddConstraint(
                    model_name="coderule",
                    constraint=models.UniqueConstraint(fields=("company_id", "entity_type"), name="code_rule_company_entity_unique"),
                ),
            ],
        ),
    ]

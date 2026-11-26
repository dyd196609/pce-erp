"""Allow same material under distinct roles; preserve legacy empty-role uniqueness."""
from django.db import migrations, models
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Coalesce, NullIf, Trim, Upper


def role():
    return Upper(Trim(Coalesce(
        NullIf(KeyTextTransform("structureRole", "order_specification"), models.Value("null")),
        models.Value(""), output_field=models.CharField(),
    )))


class Migration(migrations.Migration):
    dependencies = [("pde", "0046_engineering_calculation_continuation")]
    operations = [
        migrations.RemoveConstraint("bomitem", "pde_bom_item_parent_material_unique"),
        migrations.RemoveConstraint("bomitem", "pde_bom_item_root_material_unique"),
        migrations.AddConstraint("bomitem", models.UniqueConstraint(
            models.F("bom_version"), models.F("parent_item"), models.F("material"), role(),
            condition=models.Q(parent_item__isnull=False), name="pde_bom_item_parent_material_role_unique",
        )),
        migrations.AddConstraint("bomitem", models.UniqueConstraint(
            models.F("bom_version"), models.F("material"), role(),
            condition=models.Q(parent_item__isnull=True), name="pde_bom_item_root_material_role_unique",
        )),
    ]

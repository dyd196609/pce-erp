from django.db import migrations, models
import django.db.models.deletion


def populate_plan_scope(apps, schema_editor):
    PlanRevision = apps.get_model("pde", "ProductDesignPlanRevision")
    for revision in PlanRevision.objects.select_related(
        "design_item__sales_order_item__sales_order",
    ).all().iterator():
        item = revision.design_item
        revision.order_id = item.sales_order_item.sales_order_id
        revision.design_group = f"DES-{item.sales_order_item.line_no:02d}"
        revision.save(update_fields=["order", "design_group"])


class Migration(migrations.Migration):
    dependencies = [
        ("pde", "0028_product_design_plan_content_completion"),
        ("sales", "0005_sales_order_item_tax_snapshot"),
    ]

    operations = [
        migrations.AddField(
            model_name="productdesignplanrevision",
            name="order",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="product_design_plan_revisions",
                to="sales.salesorder",
                verbose_name="销售订单",
            ),
        ),
        migrations.AddField(
            model_name="productdesignplanrevision",
            name="design_group",
            field=models.CharField(blank=True, default="", max_length=16, verbose_name="设计分组"),
            preserve_default=False,
        ),
        migrations.RenameField(
            model_name="productdesignplanrevision",
            old_name="designer",
            new_name="designer_employee",
        ),
        migrations.RenameField(
            model_name="productdesignplanrevision",
            old_name="plan_nature",
            new_name="plan_type",
        ),
        migrations.RenameField(
            model_name="productdesignplanrevision",
            old_name="change_reason",
            new_name="adjustment_reason",
        ),
        migrations.AlterField(
            model_name="productdesignplanrevision",
            name="design_item",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="plan_revisions",
                to="pde.productdesignitem",
                verbose_name="历史产品设计项关联",
            ),
        ),
        migrations.RunPython(populate_plan_scope, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="productdesignplanrevision",
            name="order",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="product_design_plan_revisions",
                to="sales.salesorder",
                verbose_name="销售订单",
            ),
        ),
        migrations.AlterField(
            model_name="productdesignplanrevision",
            name="design_group",
            field=models.CharField(max_length=16, verbose_name="设计分组"),
        ),
        migrations.RemoveConstraint(
            model_name="productdesignplanrevision",
            name="pde_design_plan_item_revision_unique",
        ),
        migrations.AddConstraint(
            model_name="productdesignplanrevision",
            constraint=models.UniqueConstraint(
                condition=models.Q(("design_item__isnull", True)),
                fields=("order", "design_group", "revision"),
                name="pde_design_plan_group_revision_unique",
            ),
        ),
        migrations.AlterModelOptions(
            name="productdesignplanrevision",
            options={"ordering": ("order_id", "design_group", "revision")},
        ),
    ]

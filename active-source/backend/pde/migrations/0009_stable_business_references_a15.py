from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("pde", "0008_engineering_fact_source_a15"),
        ("planning", "0004_engineering_and_plan_compatibility_a15"),
        ("sales", "0002_sales_order_engineering_refs_a15"),
    ]

    operations = [
        migrations.AddField(
            model_name="manufacturinginputreference", name="target_demand",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="engineering_input_references", to="planning.demand", verbose_name="稳定计划需求目标"),
        ),
        migrations.AlterField(
            model_name="productengineeringreadiness", name="order_no",
            field=models.CharField(blank=True, default="", help_text="历史只读兼容投影；新数据必须使用SalesOrder/SalesOrderItem正式引用。", max_length=64, verbose_name="兼容CRM订单号"),
        ),
        migrations.AddField(
            model_name="productengineeringreadiness", name="sales_order",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="engineering_readiness_records", to="sales.salesorder", verbose_name="正式销售订单"),
        ),
        migrations.AddField(
            model_name="productengineeringreadiness", name="sales_order_item",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="engineering_readiness", to="sales.salesorderitem", verbose_name="正式销售订单明细"),
        ),
    ]

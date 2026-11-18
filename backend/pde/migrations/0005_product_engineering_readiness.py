from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("pde", "0004_pde_manufacturing_output"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductEngineeringReadiness",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order_no", models.CharField(max_length=64, unique=True, verbose_name="CRM订单号")),
                ("delivery_date", models.DateField(verbose_name="客户交期")),
                ("engineering_status", models.CharField(choices=[("not_started", "未开始"), ("engineering_preparing", "工程准备中"), ("bom_completed", "BOM已完成"), ("routing_completed", "工艺路线已完成"), ("document_completed", "工程资料已完成"), ("manufacturing_ready", "制造准备完成"), ("mrp_ready", "MRP输入已准备"), ("completed", "已完成")], default="not_started", max_length=32, verbose_name="工程状态")),
                ("bom_status", models.CharField(choices=[("not_started", "未开始"), ("engineering_preparing", "工程准备中"), ("bom_completed", "BOM已完成"), ("routing_completed", "工艺路线已完成"), ("document_completed", "工程资料已完成"), ("manufacturing_ready", "制造准备完成"), ("mrp_ready", "MRP输入已准备"), ("completed", "已完成")], default="not_started", max_length=32, verbose_name="BOM状态")),
                ("routing_status", models.CharField(choices=[("not_started", "未开始"), ("engineering_preparing", "工程准备中"), ("bom_completed", "BOM已完成"), ("routing_completed", "工艺路线已完成"), ("document_completed", "工程资料已完成"), ("manufacturing_ready", "制造准备完成"), ("mrp_ready", "MRP输入已准备"), ("completed", "已完成")], default="not_started", max_length=32, verbose_name="工艺状态")),
                ("document_status", models.CharField(choices=[("not_started", "未开始"), ("engineering_preparing", "工程准备中"), ("bom_completed", "BOM已完成"), ("routing_completed", "工艺路线已完成"), ("document_completed", "工程资料已完成"), ("manufacturing_ready", "制造准备完成"), ("mrp_ready", "MRP输入已准备"), ("completed", "已完成")], default="not_started", max_length=32, verbose_name="资料状态")),
                ("manufacturing_output_status", models.CharField(choices=[("not_started", "未开始"), ("engineering_preparing", "工程准备中"), ("bom_completed", "BOM已完成"), ("routing_completed", "工艺路线已完成"), ("document_completed", "工程资料已完成"), ("manufacturing_ready", "制造准备完成"), ("mrp_ready", "MRP输入已准备"), ("completed", "已完成")], default="not_started", max_length=32, verbose_name="制造输出状态")),
                ("mrp_ready_status", models.CharField(choices=[("not_started", "未开始"), ("engineering_preparing", "工程准备中"), ("bom_completed", "BOM已完成"), ("routing_completed", "工艺路线已完成"), ("document_completed", "工程资料已完成"), ("manufacturing_ready", "制造准备完成"), ("mrp_ready", "MRP输入已准备"), ("completed", "已完成")], default="not_started", max_length=32, verbose_name="MRP状态")),
                ("delivery_risk", models.CharField(choices=[("on_track", "交期正常"), ("attention", "需要关注"), ("delayed", "存在延期风险"), ("blocked", "工程阻断")], default="on_track", max_length=24, verbose_name="交期风险")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="engineering_readiness_records", to="pde.productdefinition")),
            ],
            options={
                "db_table": "pde_product_engineering_readiness",
                "ordering": ("delivery_date", "order_no"),
            },
        ),
    ]

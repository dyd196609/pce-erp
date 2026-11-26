from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0005_sales_order_item_tax_snapshot"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesorder",
            name="business_purpose",
            field=models.CharField(
                blank=True,
                choices=[
                    ("FORMAL_SALE", "正式销售订单"),
                    ("DEVELOPMENT_VALIDATION", "开发验证订单"),
                    ("SYSTEM_TEST", "系统测试订单"),
                ],
                help_text="订单级正式业务用途；历史空值由只读兼容服务解释，不自动回填。",
                max_length=32,
                null=True,
                verbose_name="业务用途",
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("planning", "0005_order_planning_chain_v1"),
    ]

    operations = [
        migrations.AlterField(
            model_name="planningrequirement",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "草稿"),
                    ("calculated", "已计算"),
                    ("confirmed", "已确认"),
                    ("closed", "已关闭"),
                ],
                default="calculated",
                max_length=20,
            ),
        ),
    ]

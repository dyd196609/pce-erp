from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("system", "0008_position_effective_period"),
    ]

    operations = [
        migrations.AddField(
            model_name="responsibility",
            name="status",
            field=models.CharField(
                choices=[
                    ("DRAFT", "草稿"),
                    ("ACTIVE", "生效"),
                    ("SUSPENDED", "暂停"),
                    ("EXPIRED", "失效"),
                ],
                default="DRAFT",
                max_length=12,
                verbose_name="状态",
            ),
        ),
        migrations.AddField(
            model_name="responsibility",
            name="effective_from",
            field=models.DateField(blank=True, null=True, verbose_name="生效日期"),
        ),
        migrations.AddField(
            model_name="responsibility",
            name="effective_to",
            field=models.DateField(blank=True, null=True, verbose_name="失效日期"),
        ),
    ]

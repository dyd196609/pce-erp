from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("system", "0007_remove_department_cost_center_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="position",
            name="effective_from",
            field=models.DateField(blank=True, null=True, verbose_name="生效日期"),
        ),
        migrations.AddField(
            model_name="position",
            name="effective_to",
            field=models.DateField(blank=True, null=True, verbose_name="失效日期"),
        ),
    ]

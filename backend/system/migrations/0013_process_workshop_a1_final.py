import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("system", "0012_remove_process_system_process_standard_hours_nonnegative_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="process",
            name="workshop",
            field=models.ForeignKey(
                blank=True,
                help_text="真实资料只确认车间时可维护；工作中心可后续补齐。",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="operations",
                to="system.workshop",
                verbose_name="所属车间/生产区域",
            ),
        ),
    ]

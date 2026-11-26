from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pde", "0019_manufacturing_structure_wave2"),
        ("system", "0015_process_default_transition_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="routingstep",
            name="effective_transition_mode",
            field=models.CharField(
                blank=True,
                choices=[("GENERAL", "一般工序"), ("KITTING", "齐套工序")],
                help_text="路线步骤覆盖值；为空时继承正式工序默认转序方式。",
                max_length=16,
                null=True,
                verbose_name="有效转序方式",
            ),
        ),
    ]

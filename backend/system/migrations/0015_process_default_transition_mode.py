from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("system", "0014_workshop_encoder_and_operation_measurement"),
    ]

    operations = [
        migrations.AddField(
            model_name="process",
            name="default_transition_mode",
            field=models.CharField(
                choices=[("GENERAL", "一般工序"), ("KITTING", "齐套工序")],
                default="GENERAL",
                help_text="工序默认值；具体路线步骤存在覆盖值时，以路线步骤为准。",
                max_length=16,
                verbose_name="默认转序方式",
            ),
        ),
    ]

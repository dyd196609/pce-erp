from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bank_send_task", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="banksendtask",
            name="batch_id",
            field=models.CharField(default="", max_length=80),
            preserve_default=False,
        ),
    ]

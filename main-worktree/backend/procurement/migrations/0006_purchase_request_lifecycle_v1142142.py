from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("procurement", "0005_scm_business_object_recovery_v1142813")]

    operations = [
        migrations.AddField(
            model_name="purchaserequest",
            name="purchase_department",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="purchaserequest",
            name="required_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]

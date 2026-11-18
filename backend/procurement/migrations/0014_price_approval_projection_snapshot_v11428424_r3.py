from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("procurement", "0013_price_approval_legacy_projection_v11428424_r3")]

    operations = [
        migrations.AddField(
            model_name="priceapprovalpreparation",
            name="source_projection_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

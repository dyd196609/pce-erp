from django.db import migrations, models


def migrate_validation_state(apps, schema_editor):
    PaymentOrderPrepare = apps.get_model(
        "payment_order_prepare",
        "PaymentOrderPrepare",
    )
    PaymentOrderPrepare.objects.filter(
        status="prepared",
        validation_status="passed",
    ).update(status="submitted")
    PaymentOrderPrepare.objects.filter(status="draft").update(status="prepared")


class Migration(migrations.Migration):
    dependencies = [
        ("payment_order_prepare", "0001_initial"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="paymentorderprepare",
            name="pop_status_valid",
        ),
        migrations.RunPython(
            migrate_validation_state,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="paymentorderprepare",
            name="status",
            field=models.CharField(
                choices=[
                    ("prepared", "Prepared"),
                    ("submitted", "Submitted"),
                ],
                default="prepared",
                max_length=24,
            ),
        ),
        migrations.AddConstraint(
            model_name="paymentorderprepare",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=["prepared", "submitted"]),
                name="pop_status_valid",
            ),
        ),
    ]

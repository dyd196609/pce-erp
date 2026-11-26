from django.db import migrations, models


def migrate_draft_to_prepared(apps, schema_editor):
    PaymentRequest = apps.get_model("payment_request", "PaymentRequest")
    PaymentRequest.objects.filter(status="draft").update(status="prepared")


class Migration(migrations.Migration):
    dependencies = [
        ("payment_request", "0001_initial"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="paymentrequest",
            name="payreq_status_valid",
        ),
        migrations.RunPython(
            migrate_draft_to_prepared,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="paymentrequest",
            name="status",
            field=models.CharField(
                choices=[
                    ("prepared", "Prepared"),
                    ("submitted", "Submitted"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                ],
                default="prepared",
                max_length=24,
            ),
        ),
        migrations.AddConstraint(
            model_name="paymentrequest",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    status__in=["prepared", "submitted", "approved", "rejected"]
                ),
                name="payreq_status_valid",
            ),
        ),
    ]

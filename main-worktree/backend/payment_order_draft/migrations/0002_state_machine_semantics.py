from django.db import migrations, models


def migrate_draft_to_created(apps, schema_editor):
    PaymentOrderDraft = apps.get_model("payment_order_draft", "PaymentOrderDraft")
    PaymentOrderDraft.objects.filter(status="draft").update(status="created")


class Migration(migrations.Migration):
    dependencies = [
        ("payment_order_draft", "0001_initial"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="paymentorderdraft",
            name="pod_status_valid",
        ),
        migrations.RunPython(
            migrate_draft_to_created,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="paymentorderdraft",
            name="status",
            field=models.CharField(
                choices=[
                    ("created", "Created"),
                    ("reviewed", "Reviewed"),
                ],
                default="created",
                max_length=24,
            ),
        ),
        migrations.AddConstraint(
            model_name="paymentorderdraft",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=["created", "reviewed"]),
                name="pod_status_valid",
            ),
        ),
    ]

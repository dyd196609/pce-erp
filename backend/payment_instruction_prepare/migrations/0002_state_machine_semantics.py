from django.db import migrations, models


def migrate_validation_state(apps, schema_editor):
    PaymentInstructionPrepare = apps.get_model(
        "payment_instruction_prepare",
        "PaymentInstructionPrepare",
    )
    PaymentInstructionPrepare.objects.filter(
        status="prepared",
        validation_status="passed",
    ).update(status="validated")
    PaymentInstructionPrepare.objects.filter(status="draft").update(status="prepared")


class Migration(migrations.Migration):
    dependencies = [
        ("payment_instruction_prepare", "0001_initial"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="paymentinstructionprepare",
            name="pinsp_status_valid",
        ),
        migrations.RunPython(
            migrate_validation_state,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="paymentinstructionprepare",
            name="status",
            field=models.CharField(
                choices=[
                    ("prepared", "Prepared"),
                    ("validated", "Validated"),
                ],
                default="prepared",
                max_length=24,
            ),
        ),
        migrations.AddConstraint(
            model_name="paymentinstructionprepare",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=["prepared", "validated"]),
                name="pinsp_status_valid",
            ),
        ),
    ]

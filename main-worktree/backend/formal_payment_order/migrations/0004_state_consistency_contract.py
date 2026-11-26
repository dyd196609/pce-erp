# Generated for V1.14.2.8.4.7.54.1.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("formal_payment_order", "0003_formalpaymentorder_execution_gate"),
        ("workflow_runtime", "0002_business_state_transition"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="FormalPaymentOrderFreeze",
            new_name="FormalPaymentOrderFreezeSnapshot",
        ),
    ]

from django.db import migrations, models


def backfill_source_scenario_codes(apps, schema_editor):
    Order = apps.get_model("formal_payment_order", "FormalPaymentOrder")
    Review = apps.get_model("payment_risk_review", "PaymentRiskReview")
    scenario_by_review = dict(Review.objects.values_list("pk", "scenario_code"))
    for order in Order.objects.order_by("order_no"):
        scenario_code = scenario_by_review.get(order.source_risk_review_id) or (
            f"SERVER_SCENARIO_{order.source_risk_review_id:08d}"
        )
        Order.objects.filter(pk=order.pk).update(source_scenario_code=scenario_code)


class Migration(migrations.Migration):
    dependencies = [
        ("payment_risk_review", "0002_paymentriskreview_scenario_code"),
        ("formal_payment_order", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="formalpaymentorder",
            name="source_scenario_code",
            field=models.CharField(editable=False, max_length=80, null=True),
        ),
        migrations.RunPython(backfill_source_scenario_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="formalpaymentorder",
            name="source_scenario_code",
            field=models.CharField(editable=False, max_length=80),
        ),
        migrations.AddConstraint(
            model_name="formalpaymentorder",
            constraint=models.CheckConstraint(
                condition=~models.Q(source_scenario_code=""),
                name="fpo_source_scenario_not_empty",
            ),
        ),
    ]

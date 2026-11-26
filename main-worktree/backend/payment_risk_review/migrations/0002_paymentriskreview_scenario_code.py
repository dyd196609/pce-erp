from django.db import migrations, models


SCENARIO_CODE_MAP = {
    "SUCCESS_STANDARD_01": "SUCCESS_01",
    "SUCCESS_STANDARD_02": "SUCCESS_02",
    "SUCCESS_HIGH_AMOUNT": "SUCCESS_03",
    "SUCCESS_LOW_AMOUNT": "SUCCESS_04",
    "SUCCESS_MULTI_LINE": "SUCCESS_05",
    "SUCCESS_MULTI_SUPPLIER": "SUCCESS_06",
    "SUCCESS_IDEMPOTENCY": "SUCCESS_07",
    "SUCCESS_ROUTE_VALID": "SUCCESS_08",
}


def backfill_server_scenario_codes(apps, schema_editor):
    Review = apps.get_model("payment_risk_review", "PaymentRiskReview")
    Execution = apps.get_model("payment_risk_review", "RiskReviewExecution")
    for review in Review.objects.order_by("review_no"):
        execution = (
            Execution.objects.filter(review_id=review.pk)
            .order_by("-review_version")
            .first()
        )
        scenario_code = ""
        key = execution.idempotency_key if execution else ""
        for legacy_code, normalized_code in SCENARIO_CODE_MAP.items():
            if key.startswith(f"V52-{legacy_code}-"):
                scenario_code = normalized_code
                break
        if not scenario_code:
            scenario_code = f"SERVER_SCENARIO_{review.pk:08d}"
        Review.objects.filter(pk=review.pk).update(scenario_code=scenario_code)


class Migration(migrations.Migration):
    dependencies = [
        ("payment_risk_review", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentriskreview",
            name="scenario_code",
            field=models.CharField(editable=False, max_length=80, null=True),
        ),
        migrations.RunPython(backfill_server_scenario_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="paymentriskreview",
            name="scenario_code",
            field=models.CharField(editable=False, max_length=80),
        ),
        migrations.AddConstraint(
            model_name="paymentriskreview",
            constraint=models.CheckConstraint(
                condition=~models.Q(scenario_code=""),
                name="prr_scenario_code_not_empty",
            ),
        ),
    ]

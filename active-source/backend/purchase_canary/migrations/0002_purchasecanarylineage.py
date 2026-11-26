from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("purchase_canary", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PurchaseCanaryLineage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("canary_lineage_id", models.CharField(max_length=100, unique=True)),
                ("scenario_code", models.CharField(max_length=80)),
                ("scenario_class", models.CharField(default="pass_through", max_length=40)),
                ("scenario_role", models.CharField(max_length=120)),
                ("current_module_code", models.CharField(default="account-payable-draft", max_length=80)),
                ("current_object_type", models.CharField(default="purchaseAccountsPayableDraft", max_length=80)),
                ("current_object_id", models.PositiveBigIntegerField()),
                ("current_object_no", models.CharField(max_length=100)),
                ("downstream_eligible", models.BooleanField(default=True)),
                ("reserved_for_next_module", models.CharField(default="payable_confirmation_prepare", max_length=100)),
                ("next_stage_consumed", models.BooleanField(default=False)),
                ("upstream_object_nos", models.JSONField(default=list)),
                ("source_relation_hash", models.CharField(max_length=64)),
                ("blocking_module", models.CharField(blank=True, max_length=80)),
                ("blocking_rule_code", models.CharField(blank=True, max_length=100)),
                ("blocking_reason", models.CharField(blank=True, max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("batch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lineages", to="purchase_canary.purchasecanarybatch")),
            ],
            options={
                "db_table": "pce_purchase_canary_lineage",
                "ordering": ("scenario_code",),
            },
        ),
        migrations.AddConstraint(
            model_name="purchasecanarylineage",
            constraint=models.UniqueConstraint(fields=("batch", "scenario_code"), name="uq_purchase_canary_lineage_scenario"),
        ),
        migrations.AddConstraint(
            model_name="purchasecanarylineage",
            constraint=models.UniqueConstraint(fields=("batch", "current_object_no"), name="uq_purchase_canary_lineage_object"),
        ),
    ]

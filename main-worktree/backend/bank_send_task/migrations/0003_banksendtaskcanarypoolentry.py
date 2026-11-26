from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("bank_send_preparation", "0001_initial"),
        ("bank_send_task", "0002_banksendtask_batch_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="BankSendTaskCanaryPoolEntry",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("pool_no", models.CharField(max_length=80, unique=True)),
                ("tenant_id", models.CharField(max_length=64)),
                ("batch_id", models.CharField(max_length=80)),
                (
                    "pool_type",
                    models.CharField(
                        choices=[
                            ("normal", "Normal"),
                            ("blocked", "Blocked"),
                            ("reserve", "Reserve"),
                        ],
                        max_length=16,
                    ),
                ),
                ("scenario_code", models.CharField(max_length=80)),
                ("eligibility_snapshot", models.JSONField(default=dict)),
                ("blocking_reason", models.CharField(blank=True, max_length=120)),
                ("reserve_activated", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "source_preparation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bank_send_task_canary_entries",
                        to="bank_send_preparation.banksendpreparation",
                    ),
                ),
            ],
            options={"db_table": "bank_send_task_canary_pool"},
        ),
        migrations.AddConstraint(
            model_name="banksendtaskcanarypoolentry",
            constraint=models.UniqueConstraint(
                fields=("tenant_id", "batch_id", "scenario_code"),
                name="bst_canary_scenario_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="banksendtaskcanarypoolentry",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("pool_type__in", ["normal", "blocked", "reserve"])
                ),
                name="bst_canary_pool_type_valid",
            ),
        ),
    ]

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bank_send_execution_simulation", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BankSendSimulationAudit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("audit_no", models.CharField(max_length=144, unique=True)),
                ("simulation_no", models.CharField(max_length=112)),
                ("tenant_id", models.CharField(max_length=64)),
                ("batch_id", models.CharField(max_length=80)),
                ("audit_type", models.CharField(choices=[
                    ("simulation_created", "Simulation created"),
                    ("simulation_validated", "Simulation validated"),
                    ("simulation_started", "Simulation started"),
                    ("simulation_completed", "Simulation completed"),
                    ("simulation_failed", "Simulation failed"),
                    ("simulation_recovered", "Simulation recovered"),
                ], max_length=32)),
                ("occurred_at", models.DateTimeField()),
                ("reason", models.CharField(max_length=320)),
                ("audit_reference", models.CharField(max_length=200, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("operator", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bank_send_simulation_audits", to=settings.AUTH_USER_MODEL)),
                ("simulation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="independent_audits", to="bank_send_execution_simulation.banksendexecutionsimulation")),
            ],
            options={"db_table": "bank_send_simulation_audits"},
        ),
        migrations.AddConstraint(
            model_name="banksendsimulationaudit",
            constraint=models.UniqueConstraint(fields=("simulation", "audit_type"), name="bssa_simulation_audit_type_unique"),
        ),
        migrations.CreateModel(
            name="BankSendProductionIsolationGate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("gate_no", models.CharField(max_length=112, unique=True)),
                ("tenant_id", models.CharField(max_length=64)),
                ("batch_id", models.CharField(max_length=80)),
                ("simulation_environment", models.BooleanField(default=True)),
                ("production_connection_enabled", models.BooleanField(default=False)),
                ("production_secret_available", models.BooleanField(default=False)),
                ("production_send_allowed", models.BooleanField(default=False)),
                ("payment_execution_allowed", models.BooleanField(default=False)),
                ("approval_status", models.CharField(default="not_approved", max_length=40)),
                ("status", models.CharField(choices=[("created", "Created"), ("checked", "Checked"), ("isolated", "Isolated")], max_length=16)),
                ("version", models.PositiveIntegerField(default=1)),
                ("checks", models.JSONField(default=dict)),
                ("audit_events", models.JSONField(default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_bank_send_production_isolation_gates", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "bank_send_production_isolation_gates"},
        ),
        migrations.AddConstraint(
            model_name="banksendproductionisolationgate",
            constraint=models.UniqueConstraint(fields=("tenant_id", "batch_id"), name="bspig_tenant_batch_unique"),
        ),
        migrations.AddConstraint(
            model_name="banksendproductionisolationgate",
            constraint=models.CheckConstraint(condition=models.Q(("status__in", ["created", "checked", "isolated"])), name="bspig_status_valid"),
        ),
        migrations.AddConstraint(
            model_name="banksendproductionisolationgate",
            constraint=models.CheckConstraint(condition=models.Q(("production_connection_enabled", False)), name="bspig_production_connection_disabled"),
        ),
        migrations.AddConstraint(
            model_name="banksendproductionisolationgate",
            constraint=models.CheckConstraint(condition=models.Q(("production_secret_available", False)), name="bspig_production_secret_absent"),
        ),
        migrations.AddConstraint(
            model_name="banksendproductionisolationgate",
            constraint=models.CheckConstraint(condition=models.Q(("production_send_allowed", False)), name="bspig_production_send_forbidden"),
        ),
        migrations.AddConstraint(
            model_name="banksendproductionisolationgate",
            constraint=models.CheckConstraint(condition=models.Q(("payment_execution_allowed", False)), name="bspig_payment_execution_forbidden"),
        ),
    ]

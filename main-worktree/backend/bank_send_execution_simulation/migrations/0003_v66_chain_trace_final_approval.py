from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("bank_send_execution_simulation", "0002_v65_simulation_audit_isolation_gate"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BankSendChainTrace",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("trace_no", models.CharField(max_length=128, unique=True)),
                ("tenant_id", models.CharField(max_length=64)),
                ("batch_id", models.CharField(max_length=80)),
                ("formal_payment_order_no", models.CharField(max_length=80)),
                ("bank_send_preparation_no", models.CharField(max_length=80)),
                ("bank_send_task_no", models.CharField(max_length=80)),
                ("bank_send_execution_gate_no", models.CharField(max_length=96)),
                ("bank_send_request_no", models.CharField(max_length=96)),
                ("simulation_no", models.CharField(max_length=112)),
                ("simulation_audit_no", models.CharField(max_length=144)),
                ("isolation_gate_no", models.CharField(max_length=112)),
                ("trace_complete", models.BooleanField(default=False)),
                ("trace_source", models.CharField(default="server", editable=False, max_length=16)),
                ("node_snapshot", models.JSONField(default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_bank_send_chain_traces", to=settings.AUTH_USER_MODEL)),
                ("isolation_gate", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="chain_traces", to="bank_send_execution_simulation.banksendproductionisolationgate")),
                ("source_simulation", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="chain_trace", to="bank_send_execution_simulation.banksendexecutionsimulation")),
            ],
            options={"db_table": "bank_send_chain_traces"},
        ),
        migrations.CreateModel(
            name="BankSendFinalApproval",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("approval_no", models.CharField(max_length=128, unique=True)),
                ("trace_no", models.CharField(max_length=128)),
                ("request_no", models.CharField(max_length=96)),
                ("tenant_id", models.CharField(max_length=64)),
                ("batch_id", models.CharField(max_length=80)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("first_approved", "First approved"), ("second_approved", "Second approved"), ("final_locked", "Final locked")], max_length=32)),
                ("version", models.PositiveIntegerField(default=1)),
                ("checks", models.JSONField(default=dict)),
                ("audit_events", models.JSONField(default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_bank_send_final_approvals", to=settings.AUTH_USER_MODEL)),
                ("trace", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="final_approval", to="bank_send_execution_simulation.banksendchaintrace")),
            ],
            options={"db_table": "bank_send_final_approvals"},
        ),
        migrations.CreateModel(
            name="BankSendFinalApprovalDecision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("stage", models.CharField(choices=[("first", "First approval"), ("second", "Second approval")], max_length=16)),
                ("role", models.CharField(max_length=64)),
                ("occurred_at", models.DateTimeField()),
                ("reason", models.CharField(max_length=320)),
                ("audit_reference", models.CharField(max_length=200, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("approval", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="decisions", to="bank_send_execution_simulation.banksendfinalapproval")),
                ("operator", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bank_send_final_approval_decisions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "bank_send_final_approval_decisions"},
        ),
        migrations.AddConstraint(
            model_name="banksendchaintrace",
            constraint=models.CheckConstraint(condition=models.Q(("trace_source", "server")), name="bsct_trace_source_server"),
        ),
        migrations.AddConstraint(
            model_name="banksendfinalapproval",
            constraint=models.CheckConstraint(condition=models.Q(("status__in", ["pending", "first_approved", "second_approved", "final_locked"])), name="bsfa_status_valid"),
        ),
        migrations.AddConstraint(
            model_name="banksendfinalapprovaldecision",
            constraint=models.UniqueConstraint(fields=("approval", "stage"), name="bsfad_approval_stage_unique"),
        ),
        migrations.AddConstraint(
            model_name="banksendfinalapprovaldecision",
            constraint=models.CheckConstraint(condition=models.Q(("role__in", ["bank_send_business_reviewer", "bank_send_fund_owner"])), name="bsfad_role_valid"),
        ),
    ]

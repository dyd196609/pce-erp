"""Only one new receipt table; the Daily path never traverses old MPS migrations."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("planning", "0013_production_work_orders")]
    operations = [migrations.CreateModel(name="ProductionWorkOrderWorkshopReceipt", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("status", models.CharField(max_length=20, choices=[("received", "本车间工序已接收")], default="received")),
        ("version", models.PositiveIntegerField(default=0)),
        ("work_order_version", models.PositiveIntegerField()),
        ("work_order_snapshot_hash", models.CharField(max_length=64)),
        ("source_snapshot", models.JSONField()), ("snapshot_hash", models.CharField(max_length=64)),
        ("qualification_snapshot", models.JSONField()), ("qualification_hash", models.CharField(max_length=64)),
        ("idempotency_key", models.CharField(max_length=120)), ("request_hash", models.CharField(max_length=64)),
        ("received_at", models.DateTimeField(auto_now_add=True)),
        ("company", models.ForeignKey(to="system.company", on_delete=django.db.models.deletion.PROTECT)),
        ("work_order", models.ForeignKey(to="planning.productionworkorder", on_delete=django.db.models.deletion.PROTECT, related_name="workshop_receipts")),
        ("workshop", models.ForeignKey(to="system.workshop", on_delete=django.db.models.deletion.PROTECT)),
        ("received_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, related_name="production_workshop_receipts")),
    ], options={"db_table": "planning_work_order_workshop_receipt", "default_permissions": (), "constraints": [
        models.UniqueConstraint(fields=("work_order", "workshop"), name="wo_workshop_receipt_unique"),
        models.UniqueConstraint(fields=("company", "idempotency_key"), name="wo_workshop_receipt_idem"),
        models.CheckConstraint(condition=models.Q(status="received"), name="wo_workshop_receipt_state"),
        models.CheckConstraint(condition=models.Q(version=0), name="wo_workshop_receipt_version"),
    ]})]

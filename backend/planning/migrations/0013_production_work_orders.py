"""Only two new MES tables. Target 0013 never traverses the old MPS branch."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def fk(target, **kwargs):
    return models.ForeignKey(to=target, on_delete=django.db.models.deletion.PROTECT, **kwargs)


class Migration(migrations.Migration):
    dependencies = [("planning", "0011_formal_production_scheduling")]
    operations = [
        migrations.CreateModel(name="ProductionWorkOrder", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("no", models.CharField(max_length=80)),
            ("quantity", models.DecimalField(max_digits=18, decimal_places=4)),
            ("status", models.CharField(max_length=20, choices=[("draft", "已生成，待下达"), ("released", "已下达")], default="draft")),
            ("version", models.PositiveIntegerField(default=0)),
            ("source_snapshot", models.JSONField()), ("snapshot_hash", models.CharField(max_length=64)),
            ("idempotency_key", models.CharField(max_length=120)), ("request_hash", models.CharField(max_length=64)),
            ("release_idempotency_key", models.CharField(max_length=120, blank=True, default="")),
            ("release_request_hash", models.CharField(max_length=64, blank=True, default="")),
            ("released_at", models.DateTimeField(null=True, blank=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("company", fk("system.company")),
            ("production_plan", models.OneToOneField(to="planning.productionplan", on_delete=django.db.models.deletion.PROTECT, related_name="production_work_order")),
            ("source_schedule", fk("planning.formalproductionschedule")),
            ("material", fk("masterdata.material")), ("uom", fk("masterdata.unitofmeasure")),
            ("created_by", fk(settings.AUTH_USER_MODEL, related_name="generated_production_work_orders")),
            ("released_by", fk(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="released_production_work_orders")),
        ], options={"db_table": "planning_production_work_order", "default_permissions": (), "constraints": [
            models.UniqueConstraint(fields=("company", "no"), name="wo_company_no_unique"),
            models.UniqueConstraint(fields=("company", "idempotency_key"), name="wo_company_generation_idem"),
            models.UniqueConstraint(fields=("company", "release_idempotency_key"), condition=~models.Q(release_idempotency_key=""), name="wo_company_release_idem"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="wo_quantity_positive"),
            models.CheckConstraint(condition=models.Q(status__in=("draft", "released")), name="wo_allowed_status"),
        ]}),
        migrations.CreateModel(name="ProductionWorkOrderOperation", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("sequence", models.PositiveIntegerField()), ("dependency_only", models.BooleanField(default=False)),
            ("workload_quantity", models.CharField(max_length=100, null=True, blank=True)),
            ("source_snapshot", models.JSONField()), ("snapshot_hash", models.CharField(max_length=64)),
            ("work_order", fk("planning.productionworkorder", related_name="operations")),
            ("root_step", fk("pde.routingstep", related_name="root_work_order_operations")),
            ("effective_step", fk("pde.routingstep", related_name="effective_work_order_operations")),
            ("root_routing_version", fk("pde.routingversion", related_name="root_work_order_operations")),
            ("effective_routing_version", fk("pde.routingversion", related_name="effective_work_order_operations")),
            ("operation", fk("system.process")), ("work_center", fk("pde.workcenter", null=True, blank=True)),
            ("workload_uom", fk("masterdata.unitofmeasure", null=True, blank=True)),
        ], options={"db_table": "planning_production_work_order_operation", "default_permissions": (),
            "ordering": ("work_order_id", "sequence"), "constraints": [
                models.UniqueConstraint(fields=("work_order", "sequence"), name="wo_operation_sequence_unique"),
                models.UniqueConstraint(fields=("work_order", "root_step"), name="wo_operation_root_unique"),
                models.CheckConstraint(condition=(models.Q(workload_quantity__isnull=True, workload_uom__isnull=True)
                    | models.Q(workload_quantity__isnull=False, workload_uom__isnull=False)), name="wo_workload_uom_pair"),
            ]}),
    ]

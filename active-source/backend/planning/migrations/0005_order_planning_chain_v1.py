import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def seed_order_planning_permissions(apps, schema_editor):
    Permission = apps.get_model("system", "Permission")
    Role = apps.get_model("system", "Role")
    RolePermission = apps.get_model("system", "RolePermission")
    role, _ = Role.objects.update_or_create(
        code="order_planning_operator",
        defaults={"name": "订单计划员", "description": "订单需求、MPS与MRP建议运行"},
    )
    for code, name in (
        ("planning.mps.generate", "生成订单主生产计划建议"),
        ("planning.mrp.generate", "生成订单物料需求建议"),
    ):
        permission, _ = Permission.objects.update_or_create(
            code=code, defaults={"name": name, "module": "PLAN"},
        )
        RolePermission.objects.get_or_create(role=role, permission=permission)
    view_permission = Permission.objects.filter(code="planning.view").first()
    if view_permission:
        RolePermission.objects.get_or_create(role=role, permission=view_permission)


class Migration(migrations.Migration):
    dependencies = [
        ("planning", "0004_engineering_and_plan_compatibility_a15"),
        ("sales", "0004_order_operating_system_v1"),
        ("pde", "0019_manufacturing_structure_wave2"),
        ("system", "0014_workshop_encoder_and_operation_measurement"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MasterProductionScheduleRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("run_no", models.CharField(max_length=80, unique=True)),
                ("status", models.CharField(choices=[("proposed", "建议待复核"), ("reviewed", "已人工复核")], default="proposed", max_length=20)),
                ("request_id", models.CharField(max_length=160)),
                ("idempotency_key", models.CharField(max_length=160)),
                ("source_version", models.CharField(default="ORDER-MPS-V1", max_length=40)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mps_runs", to="system.company")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_mps_runs", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "planning_mps_run", "ordering": ["-id"]},
        ),
        migrations.CreateModel(
            name="MasterProductionScheduleLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("line_no", models.PositiveIntegerField()),
                ("required_date", models.DateField()),
                ("total_qty", models.DecimalField(decimal_places=4, max_digits=18)),
                ("engineering_mode", models.CharField(max_length=24)),
                ("status", models.CharField(default="proposed", max_length=20)),
                ("material", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mps_lines", to="masterdata.material")),
                ("product_definition", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="mps_lines", to="pde.productdefinition")),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lines", to="planning.masterproductionschedulerun")),
                ("uom", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="mps_lines", to="masterdata.unitofmeasure")),
            ],
            options={"db_table": "planning_mps_line", "ordering": ["run_id", "line_no"]},
        ),
        migrations.CreateModel(
            name="MPSDemandAllocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("allocated_qty", models.DecimalField(decimal_places=4, max_digits=18)),
                ("demand", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="mps_allocation", to="planning.demand")),
                ("mps_line", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="demand_allocations", to="planning.masterproductionscheduleline")),
            ],
            options={"db_table": "planning_mps_demand_allocation"},
        ),
        migrations.CreateModel(
            name="MaterialRequirementsPlanningRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("run_no", models.CharField(max_length=80, unique=True)),
                ("status", models.CharField(choices=[("proposed", "建议待复核"), ("blocked", "存在阻断")], default="proposed", max_length=20)),
                ("request_id", models.CharField(max_length=160)),
                ("idempotency_key", models.CharField(max_length=160)),
                ("source_version", models.CharField(default="ORDER-MRP-V1", max_length=40)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mrp_runs", to="system.company")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_mrp_runs", to=settings.AUTH_USER_MODEL)),
                ("mps_run", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="mrp_run", to="planning.masterproductionschedulerun")),
            ],
            options={"db_table": "planning_mrp_run", "ordering": ["-id"]},
        ),
        migrations.CreateModel(
            name="MaterialRequirementProposal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("line_no", models.PositiveIntegerField()),
                ("required_qty", models.DecimalField(decimal_places=4, max_digits=18)),
                ("current_inventory", models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True)),
                ("allocated_inventory", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                ("net_requirement", models.DecimalField(decimal_places=4, max_digits=18)),
                ("required_date", models.DateField()),
                ("supply_type", models.CharField(choices=[("MAKE", "自制"), ("BUY", "外购"), ("UNRESOLVED", "待解析")], max_length=20)),
                ("suggested_action", models.CharField(max_length=80)),
                ("inventory_status", models.CharField(default="INTEGRATED", max_length=32)),
                ("status", models.CharField(choices=[("proposed", "建议待复核"), ("blocked", "已阻断")], default="proposed", max_length=20)),
                ("block_reason", models.CharField(blank=True, default="", max_length=300)),
                ("trace_facts", models.JSONField(blank=True, default=dict)),
                ("demand", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mrp_proposals", to="planning.demand")),
                ("material", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mrp_proposals", to="masterdata.material")),
                ("mps_line", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mrp_proposals", to="planning.masterproductionscheduleline")),
                ("mrp_run", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="proposals", to="planning.materialrequirementsplanningrun")),
                ("product_definition", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="mrp_proposals", to="pde.productdefinition")),
                ("source_bom_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="mrp_proposals", to="pde.bomitem")),
                ("source_bom_version", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="mrp_proposals", to="pde.bomversion")),
                ("uom", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="mrp_proposals", to="masterdata.unitofmeasure")),
            ],
            options={"db_table": "planning_mrp_proposal", "ordering": ["mrp_run_id", "line_no"]},
        ),
        migrations.AddConstraint(model_name="masterproductionschedulerun", constraint=models.UniqueConstraint(fields=("company", "idempotency_key"), name="uniq_mps_company_idempotency")),
        migrations.AddConstraint(model_name="masterproductionschedulerun", constraint=models.UniqueConstraint(fields=("company", "request_id"), name="uniq_mps_company_request")),
        migrations.AddConstraint(model_name="masterproductionscheduleline", constraint=models.UniqueConstraint(fields=("run", "line_no"), name="uniq_mps_run_line")),
        migrations.AddConstraint(model_name="masterproductionscheduleline", constraint=models.CheckConstraint(condition=models.Q(("total_qty__gt", 0)), name="mps_line_qty_positive")),
        migrations.AddConstraint(model_name="mpsdemandallocation", constraint=models.CheckConstraint(condition=models.Q(("allocated_qty__gt", 0)), name="mps_allocation_qty_positive")),
        migrations.AddConstraint(model_name="materialrequirementsplanningrun", constraint=models.UniqueConstraint(fields=("company", "idempotency_key"), name="uniq_mrp_company_idempotency")),
        migrations.AddConstraint(model_name="materialrequirementsplanningrun", constraint=models.UniqueConstraint(fields=("company", "request_id"), name="uniq_mrp_company_request")),
        migrations.AddConstraint(model_name="materialrequirementproposal", constraint=models.UniqueConstraint(fields=("mrp_run", "line_no"), name="uniq_mrp_run_line")),
        migrations.AddConstraint(model_name="materialrequirementproposal", constraint=models.CheckConstraint(condition=models.Q(("required_qty__gt", 0)), name="mrp_required_qty_positive")),
        migrations.AddConstraint(model_name="materialrequirementproposal", constraint=models.CheckConstraint(condition=models.Q(("net_requirement__gte", 0)), name="mrp_net_qty_nonnegative")),
        migrations.RunPython(seed_order_planning_permissions, migrations.RunPython.noop),
    ]

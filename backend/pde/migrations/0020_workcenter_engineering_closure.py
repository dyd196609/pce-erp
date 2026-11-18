import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pde", "0019_manufacturing_structure_wave2"),
        ("system", "0014_workshop_encoder_and_operation_measurement"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductionLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, verbose_name="生产线编码")),
                ("name", models.CharField(max_length=120, verbose_name="生产线名称")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否启用")),
                ("effective_from", models.DateField(blank=True, null=True, verbose_name="生效日期")),
                ("effective_to", models.DateField(blank=True, null=True, verbose_name="失效日期")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="production_lines", to="system.company", verbose_name="所属公司")),
                ("workshop", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="production_lines", to="system.workshop", verbose_name="所属车间")),
            ],
            options={"db_table": "pde_production_line", "ordering": ("company_id", "code")},
        ),
        migrations.AddConstraint(
            model_name="productionline",
            constraint=models.UniqueConstraint(fields=("company", "code"), name="pde_production_line_company_code_unique"),
        ),
        migrations.AlterField(
            model_name="workcenter",
            name="department",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="production_work_centers", to="system.department", verbose_name="所属部门（可由车间推导）"),
        ),
        migrations.AddField(
            model_name="workcenter",
            name="production_line",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="work_centers", to="pde.productionline", verbose_name="所属生产线（可选）"),
        ),
        migrations.CreateModel(
            name="Station",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, verbose_name="工位编码")),
                ("name", models.CharField(max_length=120, verbose_name="工位名称")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否启用")),
                ("effective_from", models.DateField(blank=True, null=True, verbose_name="生效日期")),
                ("effective_to", models.DateField(blank=True, null=True, verbose_name="失效日期")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="production_stations", to="system.company", verbose_name="所属公司")),
                ("production_line", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="stations", to="pde.productionline", verbose_name="所属生产线（可选）")),
                ("work_center", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="stations", to="pde.workcenter", verbose_name="所属工作中心（可选）")),
                ("workshop", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="production_stations", to="system.workshop", verbose_name="所属车间")),
            ],
            options={"db_table": "pde_station", "ordering": ("company_id", "code")},
        ),
        migrations.AddConstraint(
            model_name="station",
            constraint=models.UniqueConstraint(fields=("company", "code"), name="pde_station_company_code_unique"),
        ),
        migrations.CreateModel(
            name="WorkCenterOperationCapability",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("assignment_role", models.CharField(choices=[("primary", "主工作中心"), ("alternative", "备选工作中心")], default="alternative", max_length=16, verbose_name="资源角色")),
                ("capability_code", models.CharField(blank=True, max_length=80, verbose_name="能力编码")),
                ("capability_parameters", models.JSONField(blank=True, default=dict, verbose_name="能力参数")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否启用")),
                ("effective_from", models.DateField(blank=True, null=True, verbose_name="生效日期")),
                ("effective_to", models.DateField(blank=True, null=True, verbose_name="失效日期")),
                ("operation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="work_center_capabilities", to="system.process", verbose_name="工序")),
                ("work_center", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="operation_capabilities", to="pde.workcenter", verbose_name="工作中心")),
            ],
            options={"db_table": "pde_work_center_operation_capability", "ordering": ("operation_id", "assignment_role", "work_center_id")},
        ),
        migrations.AddConstraint(
            model_name="workcenteroperationcapability",
            constraint=models.UniqueConstraint(fields=("work_center", "operation"), name="pde_wc_operation_capability_unique"),
        ),
        migrations.AddConstraint(
            model_name="workcenteroperationcapability",
            constraint=models.CheckConstraint(condition=models.Q(("assignment_role__in", ("primary", "alternative"))), name="pde_wc_operation_role_valid"),
        ),
        migrations.CreateModel(
            name="WorkCenterTeamAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_primary", models.BooleanField(default=False, verbose_name="是否主班组")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否启用")),
                ("team", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="work_center_assignments", to="system.team", verbose_name="班组")),
                ("work_center", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="team_assignments", to="pde.workcenter", verbose_name="工作中心")),
            ],
            options={"db_table": "pde_work_center_team_assignment", "ordering": ("work_center_id", "team_id")},
        ),
        migrations.AddConstraint(
            model_name="workcenterteamassignment",
            constraint=models.UniqueConstraint(fields=("work_center", "team"), name="pde_wc_team_assignment_unique"),
        ),
    ]

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("pde", "0006_production_master_data_a1"),
        ("system", "0010_positionworkflowresponsibility_workflow_node"),
    ]

    operations = [
        migrations.AlterField(
            model_name="process", name="team",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="processes", to="system.team", verbose_name="所属班组"),
        ),
        migrations.AddField(model_name="process", name="company", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="production_operations", to="system.company", verbose_name="所属公司")),
        migrations.AddField(model_name="process", name="work_center", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="operations", to="pde.workcenter", verbose_name="默认工作中心")),
        migrations.AddField(model_name="process", name="standard_hours", field=models.DecimalField(decimal_places=4, default=0, max_digits=12, verbose_name="标准工时")),
        migrations.AddField(model_name="process", name="skill_required", field=models.CharField(blank=True, max_length=160, verbose_name="技能要求")),
        migrations.AddField(model_name="process", name="quality_check_required", field=models.BooleanField(default=False, verbose_name="是否质量检查点")),
        migrations.AddField(model_name="process", name="effective_from", field=models.DateField(blank=True, null=True, verbose_name="生效日期")),
        migrations.AddField(model_name="process", name="effective_to", field=models.DateField(blank=True, null=True, verbose_name="失效日期")),
        migrations.AddConstraint(model_name="process", constraint=models.UniqueConstraint(fields=("company", "code"), name="uniq_system_process_company_code")),
        migrations.AddConstraint(model_name="process", constraint=models.CheckConstraint(condition=models.Q(standard_hours__gte=0), name="system_process_standard_hours_nonnegative")),
    ]


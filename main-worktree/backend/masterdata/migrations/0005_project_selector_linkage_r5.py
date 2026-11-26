from django.db import migrations, models
import django.db.models.deletion


def enrich_project_master(apps, schema_editor):
    ProjectMaster = apps.get_model("masterdata", "ProjectMaster")
    CostCenter = apps.get_model("masterdata", "CostCenter")
    project = ProjectMaster.objects.filter(code="PRJ-PCE-ERP-2026").first()
    cost_center = CostCenter.objects.filter(code="CC-PROCUREMENT").first()
    if project:
        project.owner = "周丽"
        project.recommended_cost_center = cost_center
        project.save(update_fields=["owner", "recommended_cost_center"])


class Migration(migrations.Migration):
    dependencies = [("masterdata", "0004_enterprise_procurement_dimensions_r4")]

    operations = [
        migrations.AddField(model_name="projectmaster", name="owner", field=models.CharField(blank=True, default="", max_length=100)),
        migrations.AddField(model_name="projectmaster", name="recommended_cost_center", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="recommended_projects", to="masterdata.costcenter")),
        migrations.RunPython(enrich_project_master, migrations.RunPython.noop),
    ]

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def bind_formal_relations(apps, schema_editor):
    Employee = apps.get_model("pfm", "Employee")
    Department = apps.get_model("system", "Department")
    Position = apps.get_model("system", "Position")

    for employee in Employee.objects.all().order_by("pk"):
        department = None
        if employee.department_id:
            department = Department.objects.filter(pk=employee.department_id).first()
        if department is None and employee.department_name:
            department = Department.objects.filter(
                name=employee.department_name.strip(), is_active=True,
            ).order_by("pk").first()

        position = None
        if employee.position:
            position_query = Position.objects.filter(
                name=employee.position.strip(), is_active=True,
            )
            if department is not None:
                position = position_query.filter(department=department).order_by("pk").first()
            position = position or position_query.order_by("pk").first()

        Employee.objects.filter(pk=employee.pk).update(
            department_ref_id=department.pk if department else None,
            position_ref_id=position.pk if position else None,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("pfm", "0001_initial"),
        ("system", "0003_menu_rolemenu"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="employee",
            name="user",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="employee_profile",
                to=settings.AUTH_USER_MODEL,
                verbose_name="关联用户",
            ),
        ),
        migrations.AddField(
            model_name="employee",
            name="department_ref",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="employee_profiles",
                to="system.department",
                verbose_name="正式部门",
            ),
        ),
        migrations.AddField(
            model_name="employee",
            name="position_ref",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="employee_profiles",
                to="system.position",
                verbose_name="正式岗位",
            ),
        ),
        migrations.RunPython(bind_formal_relations, migrations.RunPython.noop),
    ]

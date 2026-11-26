from django.db import migrations, models


UNSPECIFIED_DISPLAY_ORDER = 2147483647


def backfill_operation_display_order(apps, schema_editor):
    Process = apps.get_model("system", "Process")
    company_ids = list(
        Process.objects.order_by().values_list("company_id", flat=True).distinct()
    )
    for company_id in company_ids:
        rows = list(Process.objects.filter(company_id=company_id).order_by("pk"))
        opening = next((row for row in rows if row.name == "开料"), None)
        pinpi = next((row for row in rows if row.name == "拼皮"), None)
        if opening and pinpi:
            ordered = [opening, pinpi] + [
                row for row in rows if row.pk not in {opening.pk, pinpi.pk}
            ]
        else:
            ordered = rows
        for display_order, row in enumerate(ordered, start=1):
            Process.objects.filter(pk=row.pk).update(display_order=display_order)


class Migration(migrations.Migration):

    dependencies = [
        ("system", "0015_process_default_transition_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="process",
            name="display_order",
            field=models.PositiveIntegerField(
                default=UNSPECIFIED_DISPLAY_ORDER,
                help_text="仅表示工序主数据默认展示顺序；不替代任何RoutingStep.sequence。",
                verbose_name="展示顺序",
            ),
        ),
        migrations.RunPython(backfill_operation_display_order, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="process",
            constraint=models.CheckConstraint(
                condition=models.Q(("display_order__gt", 0)),
                name="system_process_display_order_positive",
            ),
        ),
        migrations.AlterModelOptions(
            name="process",
            options={
                "ordering": ["company_id", "display_order", "pk"],
                "verbose_name": "工序",
                "verbose_name_plural": "工序",
            },
        ),
    ]

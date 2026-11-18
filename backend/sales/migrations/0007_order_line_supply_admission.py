import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0006_salesorder_business_purpose"),
        ("system", "0018_normalize_process_display_order_schema"),
        ("pfm", "0003_enterprise_organization_model_v1"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [migrations.CreateModel(
        name="SalesOrderItemSupplyAdmission",
        fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("supply_type", models.CharField(choices=[("MAKE", "自产"), ("BUY", "采购")], max_length=16)),
            ("responsibility_type", models.CharField(default="ORDER_LINE_SUPPLY_ADMISSION_CONFIRMER", max_length=64)),
            ("confirmed_at", models.DateTimeField()),
            ("idempotency_key", models.CharField(max_length=160, unique=True)),
            ("request_hash", models.CharField(max_length=64)),
            ("fact_hash", models.CharField(max_length=64)),
            ("reason", models.CharField(max_length=300)),
            ("source_snapshot", models.JSONField()),
            ("responsibility_snapshot", models.JSONField()),
            ("sales_order_item", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="supply_admission", to="sales.salesorderitem")),
            ("confirmed_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ("employee", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="pfm.employee")),
            ("position_responsibility", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="system.positionresponsibility")),
            ("workflow_responsibility", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="system.positionworkflowresponsibility")),
            ("audit_record", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to="system.organizationoperatingauditrecord")),
        ],
        options={"db_table": "sales_order_item_supply_admission", "constraints": [
            models.CheckConstraint(condition=models.Q(supply_type__in=("MAKE", "BUY")), name="sales_item_supply_type_supported"),
            models.CheckConstraint(condition=models.Q(responsibility_type="ORDER_LINE_SUPPLY_ADMISSION_CONFIRMER"), name="sales_item_supply_responsibility_type"),
        ]},
    )]

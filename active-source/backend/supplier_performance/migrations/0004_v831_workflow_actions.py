import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("supplier_performance", "0003_v83_payable_payment_request"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField(
            model_name="supplierpayableconfirmation",
            name="legal_entity_id",
            field=models.CharField(default="LE-CANARY-001", max_length=80),
        ),
        migrations.AddField(
            model_name="supplierpaymentrequest",
            name="legal_entity_id",
            field=models.CharField(default="LE-CANARY-001", max_length=80),
        ),
        migrations.CreateModel(
            name="SupplierSettlementActionAudit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action_no", models.CharField(max_length=80, unique=True)),
                ("action_code", models.CharField(max_length=80)),
                ("role", models.CharField(max_length=80)),
                ("object_type", models.CharField(max_length=80)),
                ("object_id", models.BigIntegerField()),
                ("object_no", models.CharField(max_length=80)),
                ("before_status", models.CharField(max_length=40)),
                ("after_status", models.CharField(max_length=40)),
                ("reason", models.CharField(max_length=240)),
                ("tenant_id", models.CharField(max_length=64)),
                ("legal_entity_id", models.CharField(max_length=80)),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                (
                    "operator",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="supplier_settlement_action_audits",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "supplier_settlement_action_audits"},
        ),
        migrations.AddIndex(
            model_name="suppliersettlementactionaudit",
            index=models.Index(
                fields=["object_type", "object_id", "timestamp"],
                name="supplier_sa_object_v831_idx",
            ),
        ),
    ]

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("procurement", "0011_quote_comparison_fact_v11428423_r5")]

    operations = [
        migrations.CreateModel(
            name="PriceApprovalPreparation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("approval_prepare_no", models.CharField(max_length=160, unique=True)),
                ("source_quotation_evidence", models.JSONField(default=list)),
                ("supplier_candidates", models.JSONField(default=list)),
                ("material_lines", models.JSONField(default=list)),
                ("comparison_basis", models.JSONField(default=dict)),
                ("historical_price_reference", models.JSONField(blank=True, default=list)),
                ("selected_supplier", models.JSONField(blank=True, default=dict)),
                ("review_opinion", models.TextField(blank=True, default="")),
                ("exception_note", models.TextField(blank=True, default="")),
                ("approval_opinion", models.TextField(blank=True, default="")),
                ("status", models.CharField(choices=[("draft", "草稿"), ("reviewing", "核价中"), ("approved", "已核准"), ("rejected", "已驳回")], default="draft", max_length=20)),
                ("decision_version", models.PositiveIntegerField(default=0)),
                ("reviewer", models.CharField(blank=True, default="", max_length=120)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("source_comparison", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="price_approval_preparation", to="procurement.quotecomparisonfact")),
            ],
            options={"db_table": "scm_price_approval_preparation", "ordering": ["-id"]},
        ),
        migrations.AddConstraint(
            model_name="priceapprovalpreparation",
            constraint=models.CheckConstraint(condition=models.Q(("decision_version__gte", 0)), name="scm_pap_decision_version_nonnegative"),
        ),
    ]

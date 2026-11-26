import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("procurement", "0010_supplier_quotation_v11428422")]

    operations = [
        migrations.CreateModel(
            name="QuoteComparisonFact",
            fields=[
                ("fact_id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("comparison_no", models.CharField(max_length=120)),
                ("source_inquiry_no", models.CharField(max_length=100)),
                ("source_quotation_ids", models.JSONField(default=list)),
                ("supplier_quote_evidence", models.JSONField(default=list)),
                ("material_code", models.CharField(max_length=100)),
                ("material_name", models.CharField(max_length=240)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=18)),
                ("quotation_amount", models.JSONField(default=list)),
                ("lowest_price", models.DecimalField(decimal_places=4, max_digits=18)),
                ("comparison_result", models.JSONField(default=dict)),
                ("source_type", models.CharField(choices=[("runtime_fact", "运行时事实"), ("server_fact", "服务端事实"), ("canary_fact", "金丝雀事实")], max_length=24)),
                ("fact_version", models.PositiveIntegerField(default=1)),
                ("verified_status", models.CharField(choices=[("pending_verification", "待人工核验"), ("verified", "已人工核验"), ("blocked", "阻断固化")], default="pending_verification", max_length=24)),
                ("generated_at", models.DateTimeField()),
                ("source_runtime_key", models.CharField(blank=True, default="", max_length=180)),
                ("source_fingerprint", models.CharField(max_length=64, unique=True)),
                ("verified_by", models.CharField(blank=True, default="", max_length=120)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "scm_quote_comparison_fact", "ordering": ["comparison_no", "fact_version"]},
        ),
        migrations.AddConstraint(
            model_name="quotecomparisonfact",
            constraint=models.UniqueConstraint(fields=("comparison_no", "fact_version"), name="scm_qcf_comparison_version_unique"),
        ),
        migrations.AddConstraint(
            model_name="quotecomparisonfact",
            constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="scm_qcf_quantity_positive"),
        ),
        migrations.AddConstraint(
            model_name="quotecomparisonfact",
            constraint=models.CheckConstraint(condition=models.Q(("lowest_price__gte", 0)), name="scm_qcf_lowest_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="quotecomparisonfact",
            constraint=models.CheckConstraint(condition=models.Q(("fact_version__gte", 1)), name="scm_qcf_version_positive"),
        ),
    ]

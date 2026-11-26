import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("procurement", "0012_price_approval_preparation_v11428424")]

    operations = [
        migrations.AlterField(
            model_name="priceapprovalpreparation",
            name="source_comparison",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="price_approval_preparation", to="procurement.quotecomparisonfact"),
        ),
        migrations.AddField(model_name="priceapprovalpreparation", name="source_projection_id",
            field=models.CharField(blank=True, max_length=80, null=True, unique=True)),
        migrations.AddField(model_name="priceapprovalpreparation", name="source_legacy_comparison_no",
            field=models.CharField(blank=True, default="", max_length=160)),
        migrations.AddField(model_name="priceapprovalpreparation", name="source_trace_alias_id",
            field=models.CharField(blank=True, default="", max_length=120)),
        migrations.AddField(model_name="priceapprovalpreparation", name="fact_origin",
            field=models.CharField(choices=[("production_fact", "正式事实"),
                ("legacy_verified_fact", "历史验证事实"), ("canary_fact", "金丝雀事实")],
                default="production_fact", max_length=32)),
        migrations.AddField(model_name="priceapprovalpreparation", name="source_confidence",
            field=models.CharField(blank=True, default="A", max_length=8)),
        migrations.AddConstraint(model_name="priceapprovalpreparation",
            constraint=models.CheckConstraint(condition=(
                models.Q(fact_origin="production_fact", source_comparison__isnull=False,
                    source_projection_id__isnull=True)
                | models.Q(fact_origin="legacy_verified_fact", source_comparison__isnull=True,
                    source_projection_id__isnull=False)),
                name="scm_pap_exactly_one_fact_source")),
    ]

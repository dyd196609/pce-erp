from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("pde", "0007_production_master_permissions_and_codes_a1")]

    operations = [
        migrations.AlterField(
            model_name="productdefinition", name="product_code",
            field=models.CharField(max_length=64, verbose_name="产品编码"),
        ),
        migrations.AlterField(
            model_name="productdefinition", name="version",
            field=models.CharField(blank=True, default="", help_text="只由正式ProductVersion发布动作同步，不是独立版本事实源。", max_length=40, verbose_name="兼容版本投影"),
        ),
        migrations.AddConstraint(
            model_name="productdefinition",
            constraint=models.UniqueConstraint(fields=("company", "product_code"), name="pde_product_company_code_unique"),
        ),
        migrations.AlterField(
            model_name="productbom", name="bom_code",
            field=models.CharField(blank=True, max_length=64, null=True, verbose_name="BOM编码"),
        ),
        migrations.AlterField(
            model_name="productbom", name="status",
            field=models.CharField(choices=[("draft", "草稿"), ("released", "已发布"), ("obsolete", "已失效")], default="draft", max_length=24, verbose_name="状态"),
        ),
        migrations.AddConstraint(
            model_name="productbom",
            constraint=models.UniqueConstraint(fields=("company", "bom_code"), name="pde_bom_company_code_unique"),
        ),
        migrations.AlterField(
            model_name="routing", name="routing_code",
            field=models.CharField(blank=True, max_length=64, null=True, verbose_name="工艺路线编码"),
        ),
        migrations.AlterField(
            model_name="routing", name="status",
            field=models.CharField(choices=[("draft", "草稿"), ("released", "已发布"), ("obsolete", "已失效")], default="draft", max_length=24, verbose_name="状态"),
        ),
        migrations.AddConstraint(
            model_name="routing",
            constraint=models.UniqueConstraint(fields=("company", "routing_code"), name="pde_routing_company_code_unique"),
        ),
        migrations.AlterField(
            model_name="engineeringdocument", name="version",
            field=models.CharField(blank=True, default="", help_text="只由正式EngineeringDocumentVersion发布动作同步。", max_length=40, verbose_name="兼容版本投影"),
        ),
        migrations.AddField(
            model_name="productmanufacturingoutput", name="engineering_document_version",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_outputs", to="pde.engineeringdocumentversion", verbose_name="工程资料版本"),
        ),
        migrations.AlterField(
            model_name="productmanufacturingoutput", name="release_status",
            field=models.CharField(choices=[("draft", "草稿"), ("engineering_review", "工程评审中"), ("released_to_manufacturing", "已发布至制造"), ("inactive", "已失效")], default="draft", max_length=32, verbose_name="发布状态"),
        ),
        migrations.AddField(
            model_name="manufacturinginputreference", name="source_manufacturing_output",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="stable_input_references", to="pde.productmanufacturingoutput", verbose_name="稳定工程发布来源"),
        ),
        migrations.RemoveConstraint(
            model_name="productmanufacturingoutput", name="pde_mfg_output_version_set_unique",
        ),
        migrations.AddConstraint(
            model_name="productmanufacturingoutput",
            constraint=models.UniqueConstraint(fields=("product", "product_version", "bom_version", "routing_version", "engineering_document_version"), name="pde_mfg_output_version_set_unique"),
        ),
    ]

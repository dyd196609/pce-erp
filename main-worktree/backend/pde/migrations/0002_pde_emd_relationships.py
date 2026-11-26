from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("pde", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="productdefinition",
            name="emd_material_code",
            field=models.CharField(
                default="",
                help_text="引用企业主数据中心的成品或半成品物料，不在PDE分配物料编码。",
                max_length=64,
                verbose_name="EMD产品物料编码",
            ),
            preserve_default=False,
        ),
        migrations.CreateModel(
            name="EngineeringDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("document_no", models.CharField(max_length=64, unique=True, verbose_name="资料编号")),
                ("document_name", models.CharField(max_length=200, verbose_name="资料名称")),
                ("document_type", models.CharField(choices=[("process", "工艺文件"), ("technical", "技术资料"), ("version_record", "版本记录")], max_length=32, verbose_name="资料类型")),
                ("version", models.CharField(max_length=40, verbose_name="版本")),
                ("status", models.CharField(choices=[("draft", "草稿"), ("released", "已发布"), ("obsolete", "已作废")], default="draft", max_length=24, verbose_name="状态")),
                ("effective_date", models.DateField(blank=True, null=True, verbose_name="生效日期")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="engineering_documents", to="pde.productdefinition")),
                ("product_bom", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="engineering_documents", to="pde.productbom")),
                ("routing", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="engineering_documents", to="pde.routing")),
            ],
            options={"db_table": "pde_engineering_document", "ordering": ("document_no",)},
        ),
    ]

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("procurement", "0008_purchase_request_enterprise_model_r4")]

    operations = [
        migrations.AddField(model_name="purchaserequest", name="application_reason", field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="purchaserequest", name="purchase_purpose", field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="purchaserequest", name="technical_description", field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="purchaserequest", name="delivery_requirements", field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="purchaserequest", name="note_description", field=models.TextField(blank=True, default="")),
        migrations.AddField(model_name="purchaserequest", name="approval_status", field=models.CharField(blank=True, default="not_submitted", max_length=24)),
        migrations.AddField(model_name="purchaserequest", name="approval_current_node", field=models.CharField(blank=True, default="申请人起草", max_length=120)),
        migrations.AddField(model_name="purchaserequest", name="approval_current_approver", field=models.CharField(blank=True, default="", max_length=120)),
        migrations.AddField(model_name="purchaserequest", name="approval_result", field=models.CharField(blank=True, default="", max_length=120)),
        migrations.AddField(model_name="purchaserequestitem", name="demand_reason", field=models.CharField(blank=True, default="", max_length=500)),
        migrations.AddField(model_name="purchaserequestitem", name="substitute_requirement", field=models.CharField(blank=True, default="", max_length=500)),
        migrations.CreateModel(
            name="PurchaseRequestApprovalRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=32)),
                ("from_status", models.CharField(max_length=24)),
                ("to_status", models.CharField(max_length=24)),
                ("node_name", models.CharField(max_length=120)),
                ("actor", models.CharField(blank=True, default="", max_length=120)),
                ("comment", models.CharField(blank=True, default="", max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("purchase_request", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="approval_records", to="procurement.purchaserequest")),
            ],
            options={"db_table": "scm_purchase_request_approval_record", "ordering": ["created_at", "id"]},
        ),
    ]

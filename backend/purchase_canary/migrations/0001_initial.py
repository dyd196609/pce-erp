from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="PurchaseCanaryBatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("batch_id", models.CharField(max_length=80, unique=True)),
                ("tenant_id", models.CharField(max_length=80)),
                ("purpose", models.CharField(default="persistent_demonstration", max_length=80)),
                ("version", models.CharField(default="V1.14.2.8.4.7.45.1", max_length=40)),
                ("schema_version", models.CharField(default="purchase-canary-v1", max_length=40)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "pce_purchase_canary_batch"},
        ),
        migrations.CreateModel(
            name="PurchaseCanaryScenario",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=64)),
                ("name", models.CharField(max_length=100)),
                ("expected_outcome", models.CharField(max_length=80)),
                ("block_reason", models.CharField(blank=True, max_length=240)),
                ("scenario_hash", models.CharField(max_length=64)),
                ("batch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="scenarios", to="purchase_canary.purchasecanarybatch")),
            ],
            options={"db_table": "pce_purchase_canary_scenario"},
        ),
        migrations.CreateModel(
            name="PurchaseCanaryModuleObject",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence", models.PositiveSmallIntegerField()),
                ("module_code", models.CharField(max_length=80)),
                ("module_name", models.CharField(max_length=100)),
                ("route_path", models.CharField(max_length=200)),
                ("object_no", models.CharField(max_length=100)),
                ("object_status", models.CharField(max_length=80)),
                ("upstream_object_no", models.CharField(blank=True, max_length=100)),
                ("downstream_object_no", models.CharField(blank=True, max_length=100)),
                ("next_step_allowed", models.BooleanField(default=False)),
                ("block_reason", models.CharField(blank=True, max_length=240)),
                ("evidence_hash", models.CharField(max_length=64)),
                ("scenario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="module_objects", to="purchase_canary.purchasecanaryscenario")),
            ],
            options={"db_table": "pce_purchase_canary_module_object", "ordering": ("sequence",)},
        ),
        migrations.CreateModel(
            name="PurchaseCanaryRelation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_object_no", models.CharField(max_length=100)),
                ("target_object_no", models.CharField(max_length=100)),
                ("relation_type", models.CharField(default="next_step", max_length=40)),
                ("relation_hash", models.CharField(max_length=64)),
                ("scenario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="relations", to="purchase_canary.purchasecanaryscenario")),
            ],
            options={"db_table": "pce_purchase_canary_relation"},
        ),
        migrations.AddConstraint(model_name="purchasecanaryscenario", constraint=models.UniqueConstraint(fields=("batch", "code"), name="uq_purchase_canary_batch_scenario")),
        migrations.AddConstraint(model_name="purchasecanarymoduleobject", constraint=models.UniqueConstraint(fields=("scenario", "module_code"), name="uq_purchase_canary_scenario_module")),
        migrations.AddConstraint(model_name="purchasecanarymoduleobject", constraint=models.UniqueConstraint(fields=("scenario", "object_no"), name="uq_purchase_canary_scenario_object")),
        migrations.AddConstraint(model_name="purchasecanaryrelation", constraint=models.UniqueConstraint(fields=("scenario", "source_object_no", "target_object_no"), name="uq_purchase_canary_relation")),
    ]

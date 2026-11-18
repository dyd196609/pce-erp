from django.db import models


class PurchaseCanaryBatch(models.Model):
    batch_id = models.CharField(max_length=80, unique=True)
    tenant_id = models.CharField(max_length=80)
    purpose = models.CharField(max_length=80, default="persistent_demonstration")
    version = models.CharField(max_length=40, default="V1.14.2.8.4.7.45.1")
    schema_version = models.CharField(max_length=40, default="purchase-canary-v1")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pce_purchase_canary_batch"


class PurchaseCanaryScenario(models.Model):
    batch = models.ForeignKey(PurchaseCanaryBatch, on_delete=models.CASCADE, related_name="scenarios")
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=100)
    expected_outcome = models.CharField(max_length=80)
    block_reason = models.CharField(max_length=240, blank=True)
    scenario_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "pce_purchase_canary_scenario"
        constraints = [
            models.UniqueConstraint(fields=("batch", "code"), name="uq_purchase_canary_batch_scenario"),
        ]


class PurchaseCanaryModuleObject(models.Model):
    scenario = models.ForeignKey(PurchaseCanaryScenario, on_delete=models.CASCADE, related_name="module_objects")
    sequence = models.PositiveSmallIntegerField()
    module_code = models.CharField(max_length=80)
    module_name = models.CharField(max_length=100)
    route_path = models.CharField(max_length=200)
    object_no = models.CharField(max_length=100)
    object_status = models.CharField(max_length=80)
    upstream_object_no = models.CharField(max_length=100, blank=True)
    downstream_object_no = models.CharField(max_length=100, blank=True)
    next_step_allowed = models.BooleanField(default=False)
    block_reason = models.CharField(max_length=240, blank=True)
    evidence_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "pce_purchase_canary_module_object"
        ordering = ("sequence",)
        constraints = [
            models.UniqueConstraint(fields=("scenario", "module_code"), name="uq_purchase_canary_scenario_module"),
            models.UniqueConstraint(fields=("scenario", "object_no"), name="uq_purchase_canary_scenario_object"),
        ]


class PurchaseCanaryRelation(models.Model):
    scenario = models.ForeignKey(PurchaseCanaryScenario, on_delete=models.CASCADE, related_name="relations")
    source_object_no = models.CharField(max_length=100)
    target_object_no = models.CharField(max_length=100)
    relation_type = models.CharField(max_length=40, default="next_step")
    relation_hash = models.CharField(max_length=64)

    class Meta:
        db_table = "pce_purchase_canary_relation"
        constraints = [
            models.UniqueConstraint(
                fields=("scenario", "source_object_no", "target_object_no"),
                name="uq_purchase_canary_relation",
            ),
        ]


class PurchaseCanaryLineage(models.Model):
    batch = models.ForeignKey(PurchaseCanaryBatch, on_delete=models.CASCADE, related_name="lineages")
    canary_lineage_id = models.CharField(max_length=100, unique=True)
    scenario_code = models.CharField(max_length=80)
    scenario_class = models.CharField(max_length=40, default="pass_through")
    scenario_role = models.CharField(max_length=120)
    current_module_code = models.CharField(max_length=80, default="account-payable-draft")
    current_object_type = models.CharField(max_length=80, default="purchaseAccountsPayableDraft")
    current_object_id = models.PositiveBigIntegerField()
    current_object_no = models.CharField(max_length=100)
    downstream_eligible = models.BooleanField(default=True)
    reserved_for_next_module = models.CharField(max_length=100, default="payable_confirmation_prepare")
    next_stage_consumed = models.BooleanField(default=False)
    upstream_object_nos = models.JSONField(default=list)
    source_relation_hash = models.CharField(max_length=64)
    blocking_module = models.CharField(max_length=80, blank=True)
    blocking_rule_code = models.CharField(max_length=100, blank=True)
    blocking_reason = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pce_purchase_canary_lineage"
        ordering = ("scenario_code",)
        constraints = [
            models.UniqueConstraint(
                fields=("batch", "scenario_code"),
                name="uq_purchase_canary_lineage_scenario",
            ),
            models.UniqueConstraint(
                fields=("batch", "current_object_no"),
                name="uq_purchase_canary_lineage_object",
            ),
        ]

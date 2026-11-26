from django.db import transaction

from .catalog import BATCH_ID, MODULES, PURPOSE, SCENARIOS, TENANT_ID, scenario_rows, stable_hash
from .models import PurchaseCanaryBatch, PurchaseCanaryModuleObject, PurchaseCanaryRelation, PurchaseCanaryScenario


def _upsert(model, lookup, values):
    instance = model.objects.filter(**lookup).first()
    if instance is None:
        return model.objects.create(**lookup, **values), True
    changed = False
    for key, value in values.items():
        if getattr(instance, key) != value:
            setattr(instance, key, value)
            changed = True
    if changed:
        instance.save(update_fields=list(values))
    return instance, changed


@transaction.atomic
def ensure_canary_group():
    batch, changed = _upsert(PurchaseCanaryBatch, {"batch_id": BATCH_ID}, {
        "tenant_id": TENANT_ID, "purpose": PURPOSE, "version": "V1.14.2.8.4.7.45.3",
        "schema_version": "purchase-canary-lineage-v2",
    })
    changed_count = int(changed)
    for code, name, outcome, scenario_reason in SCENARIOS:
        rows = scenario_rows(code)
        scenario_hash = stable_hash({"code": code, "rows": rows, "outcome": outcome})
        scenario, row_changed = _upsert(PurchaseCanaryScenario, {"batch": batch, "code": code}, {
            "name": name, "expected_outcome": outcome, "block_reason": scenario_reason,
            "scenario_hash": scenario_hash,
        })
        changed_count += int(row_changed)
        object_numbers = [row["object_no"] for row in rows]
        for index, row in enumerate(rows):
            upstream = object_numbers[index - 1] if index else ""
            downstream = object_numbers[index + 1] if index + 1 < len(rows) else ""
            block_reason = "" if row["next_step_allowed"] else (
                scenario_reason or ("当前已到达采购应付账款草稿，未执行任何下游确认" if index == len(rows) - 1 else "后续步骤未放行")
            )
            values = {
                **row, "upstream_object_no": upstream, "downstream_object_no": downstream,
                "block_reason": block_reason,
            }
            values.pop("module_code")
            values["evidence_hash"] = stable_hash(values)
            _, item_changed = _upsert(PurchaseCanaryModuleObject, {
                "scenario": scenario, "module_code": row["module_code"],
            }, values)
            changed_count += int(item_changed)
        for source_no, target_no in zip(object_numbers, object_numbers[1:]):
            relation_values = {"relation_type": "next_step"}
            relation_values["relation_hash"] = stable_hash([code, source_no, target_no])
            _, relation_changed = _upsert(PurchaseCanaryRelation, {
                "scenario": scenario, "source_object_no": source_no, "target_object_no": target_no,
            }, relation_values)
            changed_count += int(relation_changed)
    return batch, changed_count


def verify_canary_group():
    batch = PurchaseCanaryBatch.objects.get(batch_id=BATCH_ID, tenant_id=TENANT_ID, purpose=PURPOSE)
    scenarios = list(batch.scenarios.prefetch_related("module_objects", "relations").order_by("code"))
    errors = []
    if len(scenarios) != len(SCENARIOS):
        errors.append(f"scenario_count:{len(scenarios)}")
    for scenario in scenarios:
        objects = list(scenario.module_objects.all())
        if len(objects) != len(MODULES):
            errors.append(f"{scenario.code}:module_count:{len(objects)}")
        if scenario.relations.count() != len(MODULES) - 1:
            errors.append(f"{scenario.code}:relation_count:{scenario.relations.count()}")
        if scenario.scenario_hash != stable_hash({
            "code": scenario.code,
            "rows": scenario_rows(scenario.code),
            "outcome": scenario.expected_outcome,
        }):
            errors.append(f"{scenario.code}:hash")
    return {
        "result": "passed" if not errors else "failed",
        "batchId": batch.batch_id,
        "tenantId": batch.tenant_id,
        "purpose": batch.purpose,
        "scenarioCount": len(scenarios),
        "moduleCountPerScenario": len(MODULES),
        "relationCountPerScenario": len(MODULES) - 1,
        "errors": errors,
    }

import hashlib
import json

from django.conf import settings

from .models import (
    PurchaseCanaryBatch,
    PurchaseCanaryModuleObject,
    PurchaseCanaryScenario,
)


CONTRACT_VERSION = "PCE-CANARY-OPERATION-DATA-V1.0"
VERSION = "V1.14.2.8.4.7.57.1"
DEFAULT_BATCH_ID = "PCE-CANARY-OPERATION-DATA-V1"
PAYABLE_CHECK_MODULE = "payable-check"
PRESERVE_PURPOSE = "payable_check_real_user_operation_acceptance"

STATE_ACTIONS = {
    "pending_check": {
        "registryStatus": "draft",
        "availableActions": [
            "complete-payable-check",
            "batch-complete-payable-check",
        ],
        "expectedAction": "complete-payable-check",
    },
    "checked": {
        "registryStatus": "checked",
        "availableActions": [
            "enter-supplier-settlement",
            "batch-enter-supplier-settlement",
        ],
        "expectedAction": "enter-supplier-settlement",
    },
}


def _hash(payload):
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def operation_batch_id():
    return getattr(
        settings,
        "PCE_CANARY_OPERATION_BATCH_ID",
        DEFAULT_BATCH_ID,
    )


def operation_legal_entity_id():
    return getattr(
        settings,
        "PCE_CANARY_OPERATION_LEGAL_ENTITY_ID",
        "LEGAL-V45",
    )


def operation_pool_enabled():
    return bool(
        getattr(settings, "PCE_CANARY_OPERATION_DATA_ENABLED", False)
    )


def ensure_payable_check_operation_pool():
    batch, _ = PurchaseCanaryBatch.objects.update_or_create(
        batch_id=operation_batch_id(),
        defaults={
            "tenant_id": "tenant-canary-operation-v571",
            "purpose": PRESERVE_PURPOSE,
            "version": VERSION,
            "schema_version": CONTRACT_VERSION,
        },
    )
    for state, prefix in (("pending_check", "PENDING"), ("checked", "CHECKED")):
        for sequence in range(1, 9):
            scenario_code = f"PAYABLE_CHECK_{prefix}_{sequence:02d}"
            action = STATE_ACTIONS[state]
            scenario_payload = {
                "moduleCode": PAYABLE_CHECK_MODULE,
                "scenarioCode": scenario_code,
                "objectState": state,
                "availableActions": action["availableActions"],
                "expectedAction": action["expectedAction"],
                "preservePurpose": PRESERVE_PURPOSE,
            }
            scenario, _ = PurchaseCanaryScenario.objects.update_or_create(
                batch=batch,
                code=scenario_code,
                defaults={
                    "name": f"采购应付核对{state}-{sequence:02d}",
                    "expected_outcome": action["expectedAction"],
                    "block_reason": "",
                    "scenario_hash": _hash(scenario_payload),
                },
            )
            object_no = f"PCO571{prefix[:3]}{sequence:04d}"
            PurchaseCanaryModuleObject.objects.update_or_create(
                scenario=scenario,
                module_code=PAYABLE_CHECK_MODULE,
                defaults={
                    "sequence": sequence,
                    "module_name": "采购应付核对",
                    "route_path": "/finance/payable-checks",
                    "object_no": object_no,
                    "object_status": state,
                    "upstream_object_no": f"PYP571{sequence:04d}",
                    "downstream_object_no": "",
                    "next_step_allowed": state == "checked",
                    "block_reason": "",
                    "evidence_hash": _hash(
                        {**scenario_payload, "objectNo": object_no}
                    ),
                },
            )
    return batch


def payable_check_operation_rows(batch=None):
    batch = batch or PurchaseCanaryBatch.objects.filter(
        batch_id=operation_batch_id()
    ).first()
    if not batch:
        return []
    objects = PurchaseCanaryModuleObject.objects.filter(
        scenario__batch=batch,
        module_code=PAYABLE_CHECK_MODULE,
        scenario__code__startswith="PAYABLE_CHECK_",
    ).select_related("scenario").order_by(
        "object_status",
        "scenario__code",
    )
    rows = []
    for item in objects:
        state = item.object_status
        action = STATE_ACTIONS.get(state)
        if not action:
            continue
        sequence = int(item.scenario.code.rsplit("_", 1)[-1])
        rows.append({
            "id": item.pk,
            "moduleCode": PAYABLE_CHECK_MODULE,
            "scenarioCode": item.scenario.code,
            "objectState": state,
            "registryStatus": action["registryStatus"],
            "availableActions": list(action["availableActions"]),
            "expectedAction": action["expectedAction"],
            "preservePurpose": PRESERVE_PURPOSE,
            "objectNo": item.object_no,
            "sourceObjectNo": item.upstream_object_no,
            "legalEntityId": operation_legal_entity_id(),
            "supplierName": f"V57.1金丝雀供应商{sequence:02d}",
            "sourcePurchaseOrderNo": f"PO571{sequence:04d}",
            "totalCheckedQty": sequence,
            "totalCheckedAmount": f"{sequence * 100}.00",
            "amountDifference": "0.00",
            "currentStateSource": "server",
            "evidenceHash": item.evidence_hash,
        })
    return rows


def payable_check_operation_facts(rows):
    pending_count = sum(
        item["objectState"] == "pending_check" for item in rows
    )
    checked_count = sum(item["objectState"] == "checked" for item in rows)
    facts = {
        "contractVersion": CONTRACT_VERSION,
        "version": VERSION,
        "moduleCode": PAYABLE_CHECK_MODULE,
        "currentStateSource": "server",
        "objectCount": len(rows),
        "pendingCheckCount": pending_count,
        "checkedCount": checked_count,
        "mixedSelectionSupported": pending_count > 0 and checked_count > 0,
        "operationPoolConsistent": (
            len(rows) == 16
            and pending_count == 8
            and checked_count == 8
        ),
        "preservePurpose": PRESERVE_PURPOSE,
        "businessWriteRequestCount": 0,
    }
    return {**facts, "factsHash": _hash(facts)}

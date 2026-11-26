import hashlib
import json

from django.db import transaction
from django.utils import timezone

from workflow_runtime.fact_loads import build_fact_load_facts
from workflow_runtime.facts import business_state_transition_facts
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state,
    transition_business_object,
)

from .bank_connector import BankConnectorAdapter
from .models import (
    BankSendExecutionFailure,
    BankSendExecutionFramework,
    BankSendExecutionIdempotency,
    BankSendProductionSafetyReview,
    BankSendRequestSignature,
    BankSendResponseReceipt,
)
from .v67 import protection_counts as v67_protection_counts


VERSION = "V1.14.2.8.4.7.68"
FRAMEWORK_MODULE_CODE = "bank-send-execution-framework-review"
ADAPTER_MODULE_CODE = "bank-connector-adapter-review"
FRAMEWORK_OBJECT_TYPE = "bank_send_execution_framework"
FRAMEWORK_TRANSITIONS = (
    ("draft", "designed"),
    ("designed", "security_reviewed"),
)
FRAMEWORK_EXPECTED_TRANSITIONS = {
    "draft": (),
    "designed": (
        ("draft", "designed", "design-bank-send-execution-framework"),
    ),
    "security_reviewed": (
        ("draft", "designed", "design-bank-send-execution-framework"),
        (
            "designed",
            "security_reviewed",
            "review-bank-send-framework-security",
        ),
    ),
}
FRAMEWORK_STATUS_LABELS = {
    "draft": "框架草稿",
    "designed": "框架设计完成",
    "security_reviewed": "生产安全评审通过",
}


def protection_counts():
    return {
        **v67_protection_counts(),
        "frameworkWriteCount": BankSendExecutionFramework.objects.count(),
        "reviewWriteCount": BankSendProductionSafetyReview.objects.count(),
        "signatureWriteCount": BankSendRequestSignature.objects.count(),
        "idempotencyWriteCount": BankSendExecutionIdempotency.objects.count(),
        "failureWriteCount": BankSendExecutionFailure.objects.count(),
        "receiptWriteCount": BankSendResponseReceipt.objects.count(),
        "bankMessageSendWriteCount": 0,
        "paymentExecutionWriteCount": 0,
        "financialImpactWriteCount": 0,
        "businessProgressWriteCount": 0,
        "productionSendRecordCount": 0,
    }


def _transition(framework, source, target, action_code, user, reason):
    reference = (
        f"BankSendExecutionFrameworkAudit:"
        f"{framework.framework_no}:{action_code}"
    )
    framework.audit_events = [
        *framework.audit_events,
        {
            "actionCode": action_code,
            "operator": user.get_username(),
            "timestamp": timezone.now().isoformat(),
            "reason": reason,
            "auditReference": reference,
        },
    ]
    framework.save(update_fields=["audit_events", "updated_at"])
    transition_business_object(
        business_object=framework,
        object_type=FRAMEWORK_OBJECT_TYPE,
        source_state=source,
        target_state=target,
        action_code=action_code,
        operator=user,
        reason=reason,
        audit_reference=reference,
        allowed_transitions=FRAMEWORK_TRANSITIONS,
    )


def create_execution_framework(*, source_review, user, environment="simulation"):
    existing = BankSendExecutionFramework.objects.filter(
        source_review_id=source_review.pk
    ).first()
    if existing:
        return existing
    if source_review.status != "locked":
        raise ValueError("Locked production release review required")
    if environment not in {"simulation", "sandbox"}:
        raise ValueError("Production environment is forbidden")
    with transaction.atomic():
        framework = create_business_object_with_initial_state(
            model=BankSendExecutionFramework,
            initial_state="draft",
            framework_no=f"BSEF-{source_review.review_no}",
            source_review=source_review,
            tenant_id=source_review.tenant_id,
            batch_id=source_review.batch_id,
            environment=environment,
            interface_mode="simulated",
            execution_mode="design_only",
            production_connection_enabled=False,
            production_secret_available=False,
            send_permission_enabled=False,
            payment_permission_enabled=False,
            design_snapshot={
                "adapter": "BankConnectorAdapter",
                "methods": [
                    "prepareRequest",
                    "signRequest",
                    "sendRequest",
                    "queryResult",
                ],
                "allMethodsSimulationOnly": True,
                "networkClientPresent": False,
            },
            audit_events=[],
            created_by=user,
        )
        _transition(
            framework,
            "draft",
            "designed",
            "design-bank-send-execution-framework",
            user,
            "design_only_simulation_adapter_completed",
        )
    return BankSendExecutionFramework.objects.get(pk=framework.pk)


def evaluate_safety(framework):
    adapter = BankConnectorAdapter(environment=framework.environment)
    probe = adapter.prepareRequest({"probe": "V68"})
    checks = {
        "FRAMEWORK-001": bool(framework.pk),
        "FRAMEWORK-002": (
            framework.design_snapshot.get("adapter")
            == "BankConnectorAdapter"
            and framework.design_snapshot.get("allMethodsSimulationOnly")
            is True
        ),
        "FRAMEWORK-003": (
            framework.production_connection_enabled is False
        ),
        "FRAMEWORK-004": framework.production_secret_available is False,
        "FRAMEWORK-005": BankSendRequestSignature is not None,
        "FRAMEWORK-006": BankSendExecutionIdempotency is not None,
        "FRAMEWORK-007": BankSendExecutionFailure is not None,
        "FRAMEWORK-008": BankSendResponseReceipt is not None,
        "SECURITY-001": protection_counts()["productionSendRecordCount"] == 0,
        "SECURITY-002": protection_counts()["paymentExecutionWriteCount"] == 0,
        "SECURITY-003": protection_counts()["financialImpactWriteCount"] == 0,
        "NETWORK-001": probe["networkCallPerformed"] is False,
    }
    return {**checks, "passed": all(checks.values()), "factSource": "server"}


def perform_safety_review(*, framework, user):
    if framework.status not in {"designed", "security_reviewed"}:
        raise ValueError("Designed framework required")
    checks = evaluate_safety(framework)
    if not checks["passed"]:
        raise ValueError("Production safety review failed")
    with transaction.atomic():
        review, _ = BankSendProductionSafetyReview.objects.get_or_create(
            framework=framework,
            defaults={
                "review_no": f"BSPSR-{framework.framework_no}",
                "result": "passed",
                "checks": checks,
                "reviewed_by": user,
                "reviewed_at": timezone.now(),
            },
        )
        if framework.status == "designed":
            _transition(
                framework,
                "designed",
                "security_reviewed",
                "review-bank-send-framework-security",
                user,
                "production_connection_and_real_send_remain_disabled",
            )
    return (
        BankSendExecutionFramework.objects.get(pk=framework.pk),
        review,
    )


def create_simulated_artifacts(*, request, user, execution_version=1):
    payload = {
        "requestNo": request.request_no,
        "tenantId": request.tenant_id,
        "batchId": request.batch_id,
        "amount": request.amount_snapshot,
        "currency": request.validation_snapshot.get("currencyCode", "CNY"),
    }
    adapter = BankConnectorAdapter(environment="simulation")
    prepared = adapter.prepareRequest(payload)
    signed = adapter.signRequest(prepared)
    simulated_receipt = adapter.sendRequest(signed)
    adapter.queryResult(simulated_receipt)
    with transaction.atomic():
        signature, _ = BankSendRequestSignature.objects.get_or_create(
            request=request,
            defaults={
                "signature_no": f"BSRS-{request.request_no}",
                "request_no": request.request_no,
                "algorithm": signed["algorithm"],
                "payload_hash": prepared["payloadHash"],
                "certificate_mode": "simulation_only",
            },
        )
        key = hashlib.sha256(
            f"{request.request_no}:{execution_version}".encode()
        ).hexdigest()
        idempotency, _ = BankSendExecutionIdempotency.objects.get_or_create(
            request=request,
            execution_version=execution_version,
            defaults={
                "idempotency_key": key,
                "request_no": request.request_no,
                "status": "simulated",
                "simulation_result": {
                    **simulated_receipt,
                    "duplicateSend": False,
                },
            },
        )
        failure, _ = BankSendExecutionFailure.objects.get_or_create(
            failure_no=f"BSEFAIL-{request.request_no}-TIMEOUT",
            defaults={
                "request": request,
                "request_no": request.request_no,
                "failure_type": "timeout",
                "failure_reason": "simulated_timeout_no_retry",
                "retry_allowed": False,
                "simulated": True,
            },
        )
        response_payload = json.dumps(
            simulated_receipt, sort_keys=True, separators=(",", ":")
        )
        receipt, _ = BankSendResponseReceipt.objects.get_or_create(
            request=request,
            defaults={
                "receipt_no": f"BSRR-{request.request_no}",
                "request_no": request.request_no,
                "response_status": "accepted",
                "response_time": timezone.now(),
                "response_hash": hashlib.sha256(
                    response_payload.encode()
                ).hexdigest(),
                "simulated": True,
            },
        )
    return {
        "signature": signature,
        "idempotency": idempotency,
        "failure": failure,
        "receipt": receipt,
        "networkCallPerformed": False,
        "realBankMessageSent": False,
    }


def _transition_facts(framework):
    facts = business_state_transition_facts(
        business_object=framework,
        object_type=FRAMEWORK_OBJECT_TYPE,
        expected_transitions=FRAMEWORK_EXPECTED_TRANSITIONS,
        audit_target_type="BankSendExecutionFramework",
    )
    history = facts["statusTransitionHistory"]
    actual = tuple(
        (row["sourceState"], row["targetState"], row["actionCode"])
        for row in history
    )
    expected = FRAMEWORK_EXPECTED_TRANSITIONS.get(framework.status)
    references = {
        (row["actionCode"], row["auditReference"])
        for row in framework.audit_events
    }
    facts["stateMachineConsistent"] = (
        expected is not None
        and actual == tuple(expected)
        and [row["version"] for row in history]
        == list(range(1, len(history) + 1))
        and all(
            row["reason"]
            and (row["actionCode"], row["auditReference"]) in references
            for row in history
        )
    )
    return facts


def serialize_framework(framework):
    review = getattr(framework, "safety_review", None)
    return {
        "id": framework.pk,
        "frameworkNo": framework.framework_no,
        "sourceReviewNo": framework.source_review.review_no,
        "tenantId": framework.tenant_id,
        "batchId": framework.batch_id,
        "environment": framework.environment,
        "environmentLabel": (
            "隔离模拟" if framework.environment == "simulation" else "银行沙箱"
        ),
        "interfaceMode": framework.interface_mode,
        "interfaceModeLabel": "模拟",
        "executionMode": framework.execution_mode,
        "status": framework.status,
        "statusCode": framework.status,
        "statusLabel": FRAMEWORK_STATUS_LABELS[framework.status],
        "productionConnectionEnabled": False,
        "productionSecretAvailable": False,
        "sendPermissionEnabled": False,
        "paymentPermissionEnabled": False,
        "designSnapshot": framework.design_snapshot,
        "safetyReview": {
            "reviewNo": review.review_no,
            "result": review.result,
            "checks": review.checks,
            "reviewedBy": review.reviewed_by.get_username(),
            "reviewedAt": review.reviewed_at.isoformat(),
        } if review else None,
        "realSendCapabilityOpen": False,
        "frameworkExistsMeansSendEnabled": False,
        **_transition_facts(framework),
    }


def serialize_adapter_review(framework):
    request = framework.source_review.trace.source_simulation.source_request
    signature = getattr(request, "simulation_signature", None)
    receipt = getattr(request, "simulation_response_receipt", None)
    idempotency = request.execution_idempotencies.order_by("pk").first()
    failure = request.execution_framework_failures.order_by("pk").first()
    return {
        "id": framework.pk,
        "frameworkNo": framework.framework_no,
        "interfaceName": "BankConnectorAdapter",
        "environment": framework.environment,
        "environmentLabel": "模拟允许",
        "status": "simulation_only",
        "statusLabel": "仅模拟",
        "callMode": "本地纯函数模拟",
        "productionMode": "关闭",
        "methods": framework.design_snapshot.get("methods", []),
        "signature": {
            "signatureNo": signature.signature_no,
            "requestNo": signature.request_no,
            "algorithm": signature.algorithm,
            "payloadHash": signature.payload_hash,
            "certificateMode": signature.certificate_mode,
        } if signature else None,
        "idempotency": {
            "idempotencyKey": idempotency.idempotency_key,
            "requestNo": idempotency.request_no,
            "executionVersion": idempotency.execution_version,
            "status": idempotency.status,
        } if idempotency else None,
        "failure": {
            "failureNo": failure.failure_no,
            "failureType": failure.failure_type,
            "failureReason": failure.failure_reason,
            "retryAllowed": failure.retry_allowed,
            "simulated": failure.simulated,
        } if failure else None,
        "receipt": {
            "receiptNo": receipt.receipt_no,
            "responseStatus": receipt.response_status,
            "responseTime": receipt.response_time.isoformat(),
            "responseHash": receipt.response_hash,
            "simulated": receipt.simulated,
        } if receipt else None,
        "networkCallPerformed": False,
        "realBankMessageSent": False,
        "factSource": "server",
    }


def _base_facts(*, fact_type, api_url, tenant_id, batch_id, count):
    return {
        "factType": fact_type,
        "factSource": "server",
        "recordCount": count,
        **protection_counts(),
        **build_fact_load_facts(
            fact_load_status="success",
            api_url=api_url,
            http_status=200,
            tenant_id=tenant_id,
            batch_id=batch_id,
        ),
    }


def framework_facts(rows, *, tenant_id, batch_id):
    return {
        **_base_facts(
            fact_type="BankSendExecutionFrameworkFacts",
            api_url="/api/finance/bank-send-execution-framework-reviews/",
            tenant_id=tenant_id,
            batch_id=batch_id,
            count=len(rows),
        ),
        "frameworkCount": len(rows),
        "securityReviewedCount": sum(
            row["status"] == "security_reviewed" for row in rows
        ),
        "simulationModeCount": sum(
            row["interfaceMode"] == "simulated" for row in rows
        ),
        "productionConnectionCount": 0,
        "realSendCapabilityCount": 0,
    }


def adapter_facts(rows, *, tenant_id, batch_id):
    return {
        **_base_facts(
            fact_type="BankConnectorAdapterReviewFacts",
            api_url="/api/finance/bank-connector-adapter-reviews/",
            tenant_id=tenant_id,
            batch_id=batch_id,
            count=len(rows),
        ),
        "adapterCount": len(rows),
        "simulationAllowedCount": len(rows),
        "productionEnabledCount": 0,
        "signatureCount": sum(bool(row["signature"]) for row in rows),
        "idempotencyCount": sum(bool(row["idempotency"]) for row in rows),
        "failureModelCount": sum(bool(row["failure"]) for row in rows),
        "receiptCount": sum(bool(row["receipt"]) for row in rows),
        "networkCallCount": 0,
    }

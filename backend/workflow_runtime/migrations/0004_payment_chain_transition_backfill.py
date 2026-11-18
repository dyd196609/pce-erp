from django.db import migrations


AUDIT_PREFIX = "BusinessActionAuditRecord:"


def _audit(Audit, *, target_type, target_id, action_code, latest=False):
    query = Audit.objects.filter(
        target_type=target_type,
        target_id=target_id,
        action_code=action_code,
        result="committed",
    ).order_by("-created_at" if latest else "created_at", "-pk" if latest else "pk")
    return query.first()


def _transition(
    Transition,
    *,
    object_type,
    business_object,
    source_state,
    target_state,
    action_code,
    audit,
    version,
    reason,
    workflow_instance_id=None,
):
    if audit is None:
        raise RuntimeError(
            f"Missing authoritative audit for {object_type}:{business_object.pk} "
            f"{source_state}->{target_state}"
        )
    transition, _ = Transition.objects.get_or_create(
        object_type=object_type,
        object_id=business_object.pk,
        version=version,
        defaults={
            "source_state": source_state,
            "target_state": target_state,
            "action_code": action_code,
            "workflow_instance_id": workflow_instance_id,
            "operator_id": audit.actor_id,
            "reason": reason,
            "audit_reference": f"{AUDIT_PREFIX}{audit.pk}",
        },
    )
    Transition.objects.filter(pk=transition.pk).update(timestamp=audit.created_at)


def backfill_payment_chain_transitions(apps, schema_editor):
    Audit = apps.get_model("reconciliation", "BusinessActionAuditRecord")
    Transition = apps.get_model("workflow_runtime", "BusinessStateTransition")
    PaymentRequestPrepare = apps.get_model(
        "payment_request_prepare",
        "PaymentRequestPrepare",
    )
    PaymentRequest = apps.get_model("payment_request", "PaymentRequest")
    PaymentInstructionPrepare = apps.get_model(
        "payment_instruction_prepare",
        "PaymentInstructionPrepare",
    )
    PaymentOrderPrepare = apps.get_model(
        "payment_order_prepare",
        "PaymentOrderPrepare",
    )
    PaymentOrderDraft = apps.get_model(
        "payment_order_draft",
        "PaymentOrderDraft",
    )

    for obj in PaymentRequestPrepare.objects.filter(status="prepared"):
        audit = _audit(
            Audit,
            target_type="payment_request_prepare",
            target_id=obj.pk,
            action_code="VALIDATE_PAYMENT_REQUEST_PREPARE",
        )
        _transition(
            Transition,
            object_type="payment_request_prepare",
            business_object=obj,
            source_state="draft",
            target_state="prepared",
            action_code="VALIDATE_PAYMENT_REQUEST_PREPARE",
            audit=audit,
            version=1,
            reason="Historical validation evidence backfill",
        )

    for obj in PaymentRequest.objects.exclude(status="prepared"):
        submit_audit = _audit(
            Audit,
            target_type="PaymentRequest",
            target_id=obj.pk,
            action_code="SUBMIT_PAYMENT_REQUEST",
        )
        _transition(
            Transition,
            object_type="payment_request",
            business_object=obj,
            source_state="prepared",
            target_state="submitted",
            action_code="SUBMIT_PAYMENT_REQUEST",
            audit=submit_audit,
            version=1,
            reason="Historical submission evidence backfill",
            workflow_instance_id=obj.workflow_instance_id,
        )
        if obj.status in {"approved", "rejected"}:
            action_code = (
                "APPROVE_PAYMENT_REQUEST"
                if obj.status == "approved"
                else "REJECT_PAYMENT_REQUEST"
            )
            decision_audit = _audit(
                Audit,
                target_type="PaymentRequest",
                target_id=obj.pk,
                action_code=action_code,
                latest=True,
            )
            _transition(
                Transition,
                object_type="payment_request",
                business_object=obj,
                source_state="submitted",
                target_state=obj.status,
                action_code=action_code,
                audit=decision_audit,
                version=2,
                reason="Historical final approval evidence backfill",
                workflow_instance_id=obj.workflow_instance_id,
            )

    for obj in PaymentInstructionPrepare.objects.filter(status="validated"):
        audit = _audit(
            Audit,
            target_type="paymentInstructionPrepare",
            target_id=obj.pk,
            action_code="VALIDATE_PAYMENT_INSTRUCTION_PREPARE",
        )
        _transition(
            Transition,
            object_type="payment_instruction_prepare",
            business_object=obj,
            source_state="prepared",
            target_state="validated",
            action_code="VALIDATE_PAYMENT_INSTRUCTION_PREPARE",
            audit=audit,
            version=1,
            reason="Historical validation evidence backfill",
        )

    for obj in PaymentOrderPrepare.objects.filter(status="submitted"):
        audit = _audit(
            Audit,
            target_type="paymentOrderPrepare",
            target_id=obj.pk,
            action_code="VALIDATE_PAYMENT_ORDER_PREPARE",
        )
        _transition(
            Transition,
            object_type="payment_order_prepare",
            business_object=obj,
            source_state="prepared",
            target_state="submitted",
            action_code="VALIDATE_PAYMENT_ORDER_PREPARE",
            audit=audit,
            version=1,
            reason="Historical validation evidence backfill",
        )

    for obj in PaymentOrderDraft.objects.filter(status="reviewed"):
        audit = _audit(
            Audit,
            target_type="paymentOrderDraft",
            target_id=obj.pk,
            action_code="REVIEW_PAYMENT_ORDER_DRAFT",
        )
        _transition(
            Transition,
            object_type="payment_order_draft",
            business_object=obj,
            source_state="created",
            target_state="reviewed",
            action_code="REVIEW_PAYMENT_ORDER_DRAFT",
            audit=audit,
            version=1,
            reason="Historical review evidence backfill",
        )


class Migration(migrations.Migration):
    dependencies = [
        ("workflow_runtime", "0003_transition_fact_integrity"),
        ("payment_request_prepare", "0001_initial"),
        ("payment_request", "0002_state_machine_semantics"),
        ("payment_instruction_prepare", "0002_state_machine_semantics"),
        ("payment_order_prepare", "0002_state_machine_semantics"),
        ("payment_order_draft", "0002_state_machine_semantics"),
    ]

    operations = [
        migrations.RunPython(
            backfill_payment_chain_transitions,
            migrations.RunPython.noop,
        ),
    ]

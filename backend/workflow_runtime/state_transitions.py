from django.db import connection
from django.db.models import Max

from .models import BusinessStateTransition


class BusinessStateTransitionError(ValueError):
    pass


def transition_business_object(
    *,
    business_object,
    object_type,
    source_state,
    target_state,
    action_code,
    operator,
    reason,
    audit_reference,
    workflow_instance=None,
    allowed_transitions,
    status_field="status",
    version_field="version",
    updated_at_field="updated_at",
):
    if not connection.in_atomic_block:
        raise BusinessStateTransitionError(
            "Business state transitions require an active database transaction"
        )
    if not reason or not str(reason).strip():
        raise BusinessStateTransitionError("Transition reason is required")
    if not audit_reference or not str(audit_reference).strip():
        raise BusinessStateTransitionError("Transition audit reference is required")
    current_status = getattr(business_object, status_field)
    if current_status != source_state:
        raise BusinessStateTransitionError(
            f"Expected {source_state}, found {current_status}"
        )
    if (source_state, target_state) not in set(allowed_transitions):
        raise BusinessStateTransitionError(
            f"Transition {source_state}->{target_state} is not allowed"
        )
    last_version = (
        BusinessStateTransition.objects.filter(
            object_type=object_type,
            object_id=business_object.pk,
        ).aggregate(value=Max("version"))["value"]
        or 0
    )
    setattr(business_object, status_field, target_state)
    if version_field:
        setattr(
            business_object,
            version_field,
            getattr(business_object, version_field) + 1,
        )
    business_object._business_state_transition_authorized = True
    update_fields = [status_field]
    if version_field:
        update_fields.append(version_field)
    if updated_at_field:
        update_fields.append(updated_at_field)
    try:
        business_object.save(update_fields=update_fields)
    finally:
        business_object._business_state_transition_authorized = False
    return BusinessStateTransition.objects.create(
        object_type=object_type,
        object_id=business_object.pk,
        source_state=source_state,
        target_state=target_state,
        action_code=action_code,
        workflow_instance=workflow_instance,
        operator=operator,
        reason=str(reason).strip(),
        audit_reference=str(audit_reference).strip(),
        version=last_version + 1,
    )


def create_business_object_with_initial_state(
    *,
    model,
    initial_state,
    status_field="status",
    **fields,
):
    if not connection.in_atomic_block:
        raise BusinessStateTransitionError(
            "Business object initialization requires an active database transaction"
        )
    business_object = model(**fields)
    setattr(business_object, status_field, initial_state)
    business_object._business_state_initialization_authorized = True
    try:
        business_object.save(force_insert=True)
    finally:
        business_object._business_state_initialization_authorized = False
    return business_object


def record_projected_business_transition(
    *,
    object_type,
    object_id,
    source_state,
    target_state,
    action_code,
    operator,
    reason,
    audit_reference,
    workflow_instance=None,
    allowed_transitions,
):
    """Persist a transition for an immutable source object's workflow projection.

    This is for a business state that is owned by the workflow projection rather
    than by a mutable status field on the source document.  It deliberately does
    not update the source object.  The caller must provide the committed audit and
    workflow facts in the same transaction.
    """

    if not connection.in_atomic_block:
        raise BusinessStateTransitionError(
            "Projected business state transitions require an active database transaction"
        )
    if not str(object_type or "").strip() or not int(object_id or 0):
        raise BusinessStateTransitionError("Projected transition object identity is required")
    if not reason or not str(reason).strip():
        raise BusinessStateTransitionError("Transition reason is required")
    if not audit_reference or not str(audit_reference).strip():
        raise BusinessStateTransitionError("Transition audit reference is required")
    if (source_state, target_state) not in set(allowed_transitions):
        raise BusinessStateTransitionError(
            f"Transition {source_state}->{target_state} is not allowed"
        )
    previous = (
        BusinessStateTransition.objects.select_for_update()
        .filter(object_type=object_type, object_id=object_id)
        .order_by("-version", "-pk")
        .first()
    )
    if previous and previous.target_state != source_state:
        raise BusinessStateTransitionError(
            f"Expected projected source {previous.target_state}, found {source_state}"
        )
    if BusinessStateTransition.objects.select_for_update().filter(
        object_type=object_type,
        object_id=object_id,
        source_state=source_state,
        target_state=target_state,
        action_code=action_code,
    ).exists():
        raise BusinessStateTransitionError("Projected business transition already exists")
    return BusinessStateTransition.objects.create(
        object_type=str(object_type).strip(),
        object_id=int(object_id),
        source_state=source_state,
        target_state=target_state,
        action_code=action_code,
        workflow_instance=workflow_instance,
        operator=operator,
        reason=str(reason).strip(),
        audit_reference=str(audit_reference).strip(),
        version=(previous.version + 1) if previous else 1,
    )


__all__ = [
    "BusinessStateTransitionError",
    "create_business_object_with_initial_state",
    "record_projected_business_transition",
    "transition_business_object",
]

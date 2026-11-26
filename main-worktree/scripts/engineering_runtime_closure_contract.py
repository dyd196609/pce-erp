"""Pure contract checks used by the engineering runtime STRICT Gate.

The checks deliberately avoid snapshotting requirement primary keys, material
identities, design-item identities, or quantities.  A legitimate new
requirement is accepted only when its released mapping, immutable creation
audit, source-detail lineage, and governed write identities remain complete.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


FORMAL_PURPOSE = "FORMAL_SALE"
DEVELOPMENT_PURPOSE = "DEVELOPMENT_VALIDATION"
PURPOSE_CORRECTION_ACTION = "sales.order.correct_business_identity"
CURRENT_REQUIREMENT_ACTION = "production.engineering.material_requirement.create"
LEGACY_REQUIREMENT_ACTION = "production.engineering.material_requirement.r1.create"
CURRENT_REQUIREMENT_SERVICE = "PCE-SAVED-FACT-MATERIAL-REQUIREMENT-HANDOFF-V1"
LEGACY_REQUIREMENT_SERVICE = "PCE-R1-SAVED-FACT-MATERIAL-REQUIREMENT-HANDOFF-V1"


def _decimal_equal(left: object, right: object) -> bool:
    try:
        return Decimal(str(left)) == Decimal(str(right))
    except (InvalidOperation, TypeError, ValueError):
        return False


def _assess_bom_source_links(row: dict[str, object], prefix: str) -> list[str]:
    """Validate an optional generated-BOM provenance link for one requirement."""
    risks: list[str] = []
    links = list(row.get("bomSourceLinks") or [])
    if row.get("bomSourceLinkCount") != len(links):
        risks.append(f"{prefix} BOM source link count and detail differ")
    if len(links) > 1:
        risks.append(f"{prefix} belongs to multiple generated BOM items")
    for link in links:
        if link.get("requirementId") != row.get("id"):
            risks.append(f"{prefix} BOM source link targets another requirement")
        if link.get("sourceCalculationId") != row.get("calculationId"):
            risks.append(f"{prefix} BOM source link belongs to another calculation")
        if link.get("materialId") != row.get("materialId"):
            risks.append(f"{prefix} BOM source link uses another material")
        if link.get("uomCode") != row.get("uomCode"):
            risks.append(f"{prefix} BOM source link uses another UOM")
        if not _decimal_equal(link.get("contributedQuantity"), row.get("netQuantity")):
            risks.append(f"{prefix} BOM source contribution differs from net quantity")
        if not link.get("bomItemId") or not link.get("bomVersionId"):
            risks.append(f"{prefix} BOM source link identity is incomplete")
    return risks


def assess_purpose_contract(facts: dict[str, object]) -> list[str]:
    """Validate the persisted purpose against its unique governed correction."""
    risks: list[str] = []
    current = facts.get("currentPurpose")
    if current != FORMAL_PURPOSE:
        risks.append("target order current purpose is not FORMAL_SALE")
    if facts.get("correctionActionCount") != 1:
        risks.append("target order does not have exactly one purpose correction action")

    action = facts.get("correctionAction") or {}
    audit = action.get("audit") or {}
    before = audit.get("beforeIdentity") or {}
    after = audit.get("afterIdentity") or {}
    actor = audit.get("actor") or {}
    authorization = audit.get("authorization") or {}
    workflow = audit.get("workflowResponsibility") or {}

    if action.get("actionCode") != PURPOSE_CORRECTION_ACTION:
        risks.append("purpose correction action code is invalid")
    if action.get("auditActionCode") != PURPOSE_CORRECTION_ACTION:
        risks.append("purpose correction audit action code is invalid")
    if action.get("auditTargetId") != facts.get("orderId"):
        risks.append("purpose correction audit targets another order")
    if action.get("actorId") != action.get("auditActorId"):
        risks.append("purpose correction actor and audit actor differ")
    if not action.get("idempotencyKey") or not action.get("requestId"):
        risks.append("purpose correction idempotency or request identity is missing")
    if action.get("auditRecordId") != action.get("auditId"):
        risks.append("purpose correction action is not linked to its audit")
    if before.get("businessPurpose") != DEVELOPMENT_PURPOSE:
        risks.append("purpose correction before-value is not DEVELOPMENT_VALIDATION")
    if after.get("businessPurpose") != current:
        risks.append("purpose correction after-value does not match the current purpose")
    if after.get("orderVersion") != facts.get("orderVersion"):
        risks.append("purpose correction after-version does not match the current order")
    if audit.get("protectedIdentityBefore") != audit.get("protectedIdentityAfter"):
        risks.append("purpose correction changed protected commercial identity")
    if actor.get("isSuperuser") is not False or actor.get("isActive") is not True:
        risks.append("purpose correction actor is not an active non-superuser")
    if not actor.get("employeeId") or actor.get("employeeStatus") != "active":
        risks.append("purpose correction actor lacks an active employee identity")
    if authorization.get("allowed") is not True:
        risks.append("purpose correction authorization was not allowed")
    if authorization.get("actionCode") != "sales.order.update":
        risks.append("purpose correction authorization action is invalid")
    if str(authorization.get("organizationId")) != str(facts.get("companyId")):
        risks.append("purpose correction authorization organization is invalid")
    if workflow.get("businessActionCode") != "sales.order.update" or not workflow.get("responsibilityCode"):
        risks.append("purpose correction workflow responsibility is incomplete")
    if audit.get("orderWriteCount") != 1:
        risks.append("purpose correction order write count is not one")
    if audit.get("businessStateTransitionCount") != 0 or audit.get("downstreamWriteCount") != 0:
        risks.append("purpose correction unexpectedly changed lifecycle or downstream facts")
    if not audit.get("reason"):
        risks.append("purpose correction reason is missing")
    return risks


def assess_requirement_contract(facts: dict[str, object]) -> list[str]:
    """Validate a sales-order requirement set without a fixed record count."""
    risks: list[str] = []
    order_no = str(facts.get("orderNo") or "")
    company_id = facts.get("companyId")
    rows = list(facts.get("requirements") or [])
    mapping_ids = list(facts.get("releasedMappingRuleIds") or [])

    if facts.get("scopeType") != "SALES_ORDER" or not order_no:
        risks.append("requirement contract scope is not an explicit sales order")
    row_ids = [row.get("id") for row in rows]
    if len(row_ids) != len(set(row_ids)):
        risks.append("duplicate requirement primary key in target scope")
    row_mapping_ids = [(row.get("trace") or {}).get("mappingRuleId") for row in rows]
    if None in row_mapping_ids:
        risks.append("requirement mapping identity is missing")
    if len(row_mapping_ids) != len(set(row_mapping_ids)):
        risks.append("multiple requirements consume the same mapping")
    if set(mapping_ids) != set(row_mapping_ids):
        risks.append("released order mapping and material requirement sets differ")

    rows_by_calculation: dict[object, list[dict[str, object]]] = {}
    for row in rows:
        rows_by_calculation.setdefault(row.get("calculationId"), []).append(row)

    for row in rows:
        row_id = row.get("id")
        prefix = f"requirement {row_id}"
        trace = row.get("trace") or {}
        mapping = row.get("mapping") or {}
        audit = row.get("audit") or {}
        audit_after = audit.get("after") or {}
        audit_request = audit_after.get("request") or {}
        actor = audit.get("actor") or {}
        mapping_id = trace.get("mappingRuleId")

        risks.extend(_assess_bom_source_links(row, prefix))

        if row.get("salesOrderId") != facts.get("orderId") or row.get("companyId") != company_id:
            risks.append(f"{prefix} escaped the governed order/company scope")
        if row.get("sourceDetailCalculationId") != row.get("calculationId"):
            risks.append(f"{prefix} source detail belongs to another calculation")
        if not _decimal_equal(row.get("calculatedQuantity"), row.get("netQuantity")):
            risks.append(f"{prefix} calculated and net quantities differ")
        try:
            positive = Decimal(str(row.get("netQuantity"))) > 0
        except (InvalidOperation, TypeError, ValueError):
            positive = False
        if not positive:
            risks.append(f"{prefix} quantity is not positive")
        if trace.get("sourceDetailId") != row.get("sourceDetailId"):
            risks.append(f"{prefix} trace source detail differs from the persisted relation")
        if trace.get("calculationReexecuted") is not False:
            risks.append(f"{prefix} does not preserve the no-recalculation contract")
        if not trace.get("authorizationReference"):
            risks.append(f"{prefix} authorization reference is missing")
        if mapping.get("id") != mapping_id or mapping.get("status") != "released":
            risks.append(f"{prefix} mapping is absent or not released")
        if mapping.get("companyId") != company_id:
            risks.append(f"{prefix} mapping belongs to another company")
        if not str(mapping.get("ruleCode") or "").startswith(f"MRM.{order_no}."):
            risks.append(f"{prefix} mapping is not scoped to the target order")
        if mapping.get("specificationHash") != trace.get("mappingSpecificationHash"):
            risks.append(f"{prefix} mapping specification was changed after handoff")
        if audit.get("count") != 1 or audit.get("targetId") != row_id:
            risks.append(f"{prefix} does not have exactly one matching creation audit")
        if actor.get("isSuperuser") is not False or actor.get("isActive") is not True:
            risks.append(f"{prefix} audit actor is not an active non-superuser")
        if not actor.get("employeeId") or actor.get("employeeStatus") != "active":
            risks.append(f"{prefix} audit actor lacks an active employee identity")
        if not audit.get("reason") or not str(audit.get("reason")).startswith("USER_INSTRUCTION:"):
            risks.append(f"{prefix} audit does not preserve user authorization evidence")
        if audit.get("authorizationAllowed") is not True:
            risks.append(f"{prefix} creation authorization is incomplete or denied")

        action = audit.get("actionCode")
        if action == CURRENT_REQUIREMENT_ACTION:
            if trace.get("serviceCode") != CURRENT_REQUIREMENT_SERVICE:
                risks.append(f"{prefix} current handoff service identity is invalid")
            expected = {
                "mappingRuleId": mapping_id,
                "calculationId": row.get("calculationId"),
                "materialId": row.get("materialId"),
                "sourceDetailId": row.get("sourceDetailId"),
            }
            actual = {
                "mappingRuleId": audit_request.get("mappingRuleId"),
                "calculationId": audit_request.get("calculationId"),
                "materialId": audit_request.get("materialId"),
                "sourceDetailId": audit_after.get("sourceDetailId"),
            }
            if actual != expected:
                risks.append(f"{prefix} persisted facts differ from the creation audit")
            if audit_after.get("requirementId") != row_id:
                risks.append(f"{prefix} audit requirement identity differs")
            if not _decimal_equal(audit_request.get("quantity"), row.get("netQuantity")):
                risks.append(f"{prefix} quantity differs from the creation audit")
            if audit_request.get("uom") != row.get("uomCode"):
                risks.append(f"{prefix} UOM differs from the creation audit")
            if audit_request.get("authorizationReference") != trace.get("authorizationReference"):
                risks.append(f"{prefix} authorization reference differs from the creation audit")
            if audit_after.get("calculationReexecuted") is not False or audit_after.get("bomGenerated") is not False:
                risks.append(f"{prefix} audit violates no-recalculation/no-BOM handoff")
            if row.get("writeRequestCount") != 1 or row.get("externalIdentityCount") != 1:
                risks.append(f"{prefix} governed write or external identity is incomplete")
            if row.get("bomSourceLinkCount") not in (0, 1):
                risks.append(f"{prefix} current BOM source link cardinality is invalid")
        elif action == LEGACY_REQUIREMENT_ACTION:
            if trace.get("serviceCode") != LEGACY_REQUIREMENT_SERVICE:
                risks.append(f"{prefix} legacy handoff service identity is invalid")
            expected = {
                "requirementId": row_id,
                "mappingRuleId": mapping_id,
                "sourceDetailId": row.get("sourceDetailId"),
                "materialId": row.get("materialId"),
            }
            actual = {key: audit_after.get(key) for key in expected}
            if actual != expected:
                risks.append(f"{prefix} legacy facts differ from the creation audit")
            if not _decimal_equal(audit_after.get("netQuantity"), row.get("netQuantity")):
                risks.append(f"{prefix} legacy quantity differs from the creation audit")
            if audit_after.get("uom") != row.get("uomCode"):
                risks.append(f"{prefix} legacy UOM differs from the creation audit")
            if audit_after.get("calculationReexecuted") is not False:
                risks.append(f"{prefix} legacy audit violates no-recalculation handoff")
            if row.get("writeRequestCount") != 0 or row.get("externalIdentityCount") != 0:
                risks.append(f"{prefix} legacy handoff unexpectedly uses the newer write identity")
            if row.get("bomSourceLinkCount") != 1:
                risks.append(f"{prefix} historical BOM source link is not protected")
        else:
            risks.append(f"{prefix} has an unsupported creation audit action")

    for calculation_id, calculation_rows in rows_by_calculation.items():
        linked_rows = [
            row for row in calculation_rows
            if list(row.get("bomSourceLinks") or [])
        ]
        if linked_rows and len(linked_rows) != len(calculation_rows):
            risks.append(
                f"calculation {calculation_id} has a partially generated BOM requirement set"
            )
        version_ids = {
            link.get("bomVersionId")
            for row in linked_rows
            for link in list(row.get("bomSourceLinks") or [])
            if link.get("bomVersionId") is not None
        }
        if len(version_ids) > 1:
            risks.append(
                f"calculation {calculation_id} requirements belong to multiple BOM versions"
            )
    return risks


def assess_database_gate(facts: dict[str, object]) -> list[str]:
    risks: list[str] = []
    if facts.get("queryOnly") != 1:
        risks.append("database query_only is not enabled")
    if facts.get("integrityCheck") != "ok":
        risks.append("database integrity_check failed")
    if facts.get("foreignKeyCheck") != []:
        risks.append("database foreign_key_check failed")
    if facts.get("shaBefore") != facts.get("shaAfter"):
        risks.append("database file hash changed")
    if facts.get("countsBefore") != facts.get("countsAfter"):
        risks.append("database model counts changed")
    return risks

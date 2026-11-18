from pde.baseline_usage_service import production_baselines, production_status
"""Server-activated, physically pinned development use of the saved-fact kernel.

There is no HTTP switch and no CRM policy override. Ordinary entry points never
receive this internal admission. The activation binds an exact copy, actor,
contract and immutable engineering evidence before any business DML.
"""
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path

from django.conf import settings
from django.db import connections

SCOPE = "SYSTEM_TEST_MATERIAL_HANDOFF_DEVELOPMENT_ONLY_V1"
CONTINUATION_SCOPE = "SYSTEM_TEST_MATERIAL_HANDOFF_CONTINUATION_V2"
FINITE_SCOPE = "SYSTEM_TEST_MATERIAL_HANDOFF_FINITE_CONTRACTS_V3"
_TOKEN = object()


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), default=str).encode()).hexdigest()


def _fail(code, message):
    from .saved_fact_material_requirement_service import SavedFactMaterialRequirementError
    raise SavedFactMaterialRequirementError(code, message)


def _load_pin():
    config = getattr(settings, "PCE_SYSTEM_TEST_MATERIAL_HANDOFF", None)
    if not isinstance(config, dict) or config.get("enabled") is not True:
        _fail("SYSTEM_TEST_HANDOFF_NOT_ACTIVATED", "服务端未激活受控测试材料承接。")
    root = Path(__file__).resolve().parents[2] / "work"
    receipt = Path(config.get("receiptPath", "")).resolve()
    if not receipt.is_relative_to(root) or not receipt.is_file():
        _fail("SYSTEM_TEST_HANDOFF_PIN_INVALID", "缺少工作区内服务端激活凭据。")
    data = receipt.read_bytes()
    if sha256(data).hexdigest() != config.get("receiptSha256"):
        _fail("SYSTEM_TEST_HANDOFF_PIN_HASH_MISMATCH", "激活凭据内容已变化。")
    pin = json.loads(data)
    if pin.get("scope") not in {SCOPE, CONTINUATION_SCOPE, FINITE_SCOPE} or pin.get("developmentOnly") is not True:
        _fail("SYSTEM_TEST_HANDOFF_PIN_INVALID", "激活用途不属于受控开发验证。")
    target = Path(pin.get("databasePath", "")).resolve()
    if (not target.is_relative_to(root) or not target.name.endswith("-system-test-material.sqlite3")
            or target.is_symlink() or not target.is_file()):
        _fail("SYSTEM_TEST_HANDOFF_DATABASE_FORBIDDEN", "仅允许专属独立材料验证副本。")
    stat = target.stat()
    identity = [stat.st_dev, stat.st_ino]
    if stat.st_nlink != 1 or identity != pin.get("physicalIdentity") or identity in pin.get("protectedPhysicalIdentities", []):
        _fail("SYSTEM_TEST_HANDOFF_PHYSICAL_IDENTITY_MISMATCH", "数据库物理身份不符或命中保护对象。")
    for alias in connections:
        conn = connections[alias]
        if (conn.settings_dict.get("ENGINE") != "django.db.backends.sqlite3"
                or conn.settings_dict.get("NAME") != str(target)):
            _fail("SYSTEM_TEST_HANDOFF_DATABASE_FORBIDDEN", "连接配置未精确绑定验证副本。")
    conn = connections["default"]
    conn.ensure_connection()
    actual = conn.connection.execute("PRAGMA database_list").fetchall()
    if actual != [(0, "main", str(target))]:
        _fail("SYSTEM_TEST_HANDOFF_DATABASE_FORBIDDEN", "实际连接身份不符或存在附加数据库。")
    return pin, config["receiptSha256"]


@dataclass(frozen=True)
class _Admission:
    token: object
    operation: str
    receipt_hash: str
    proof: dict
    adoption: object = None

    def as_dict(self):
        return dict(self.proof)


def _validate(*, user, contract, operation):
    pin, receipt_hash = _load_pin()
    if operation not in {"preview", "apply", "readback"} or operation not in pin.get("allowedActions", []):
        _fail("SYSTEM_TEST_HANDOFF_ACTION_DENIED", "激活凭据未允许本动作。")
    if (not user or not user.is_active or user.is_superuser
            or user.pk != pin.get("actorId") or user.company_id != pin.get("companyId")):
        _fail("SYSTEM_TEST_HANDOFF_ACTOR_DENIED", "受控操作者或公司不符。")
    contract_hash = digest(asdict(contract))
    allowed = pin.get("contracts", []) if pin["scope"] == FINITE_SCOPE else []
    selected = [entry for entry in allowed if entry.get("contractHash") == contract_hash]
    if (pin["scope"] == FINITE_SCOPE and len(selected) != 1) or (
            pin["scope"] != FINITE_SCOPE and contract_hash != pin.get("contractHash")):
        _fail("SYSTEM_TEST_HANDOFF_CONTRACT_MISMATCH", "材料、数量或来源合同不属于服务端激活范围。")
    from .models import EngineeringCalculationRecord, OrderEngineeringBaselineItem
    from .baseline_source_identity import resolve_baseline_source_identity
    record = EngineeringCalculationRecord.objects.select_related(
        "sales_order_item__sales_order", "engineering_instance", "source_record",
    ).filter(pk=contract.calculation_id, company_id=pin["companyId"]).first()
    obj = pin.get("objectScope", {})
    if not record:
        _fail("SYSTEM_TEST_HANDOFF_OBJECT_MISMATCH", "激活核算对象不存在。")
    order = record.sales_order_item.sales_order
    if (order.pk != obj.get("orderId") or order.business_purpose != "SYSTEM_TEST"
            or record.sales_order_item_id != obj.get("itemId")
            or record.engineering_instance_id != obj.get("oeiId")
            or record.source_record_id != obj.get("sourceId")
            or record.status != "completed" or record.scope != "order_engineering"
            or record.engineering_instance.status != "calculated"):
        _fail("SYSTEM_TEST_HANDOFF_OBJECT_MISMATCH", "仅允许激活的SYSTEM_TEST已核算主体。")
    if digest(record.trace) != pin.get("calculationTraceHash") or record.result_hash != pin.get("calculationResultHash"):
        _fail("SYSTEM_TEST_HANDOFF_FROZEN_EVIDENCE_CHANGED", "冻结核算证据已变化。")
    snapshots = record.trace.get("objectInputSnapshot") or []
    if len(snapshots) != 1 or snapshots[0].get("designItemId") != obj.get("designItemId"):
        _fail("SYSTEM_TEST_HANDOFF_OBJECT_MISMATCH", "本激活仅允许一个精确设计对象。")
    item = OrderEngineeringBaselineItem.objects.select_related(
        "baseline", "design_item__sales_order_item__sales_order", "design_revision",
        "source_record", "source_attribute",
    ).filter(pk=obj.get("baselineItemId"), baseline_id=obj.get("baselineId"),
             design_item_id=obj.get("designItemId"), design_revision_id=obj.get("designRevisionId")).first()
    if not item or production_status(item.baseline) != "confirmed":
        _fail("SYSTEM_TEST_HANDOFF_FROZEN_EVIDENCE_CHANGED", "缺少激活的已确认精确基线修订。")
    identity = resolve_baseline_source_identity(item)
    if identity != snapshots[0]["input"].get("sourceIdentity"):
        _fail("SYSTEM_TEST_HANDOFF_FROZEN_EVIDENCE_CHANGED", "来源身份与核算冻结对象不一致。")
    if (contract.require_design_material_reference is not False
            or contract.allow_missing_design_revision_when_source_identity_confirmed
            or contract.source_external_identity_id is not None):
        _fail("SYSTEM_TEST_HANDOFF_CONTRACT_MISMATCH", "本路径使用显式测试Mapping，不改写冻结设计材料引用。")
    facts = list(record.derived_facts.order_by("pk").values())
    details = list(record.details.order_by("pk").values())
    if digest({"facts": facts, "details": details}) != pin.get("savedFactsHash"):
        _fail("SYSTEM_TEST_HANDOFF_FROZEN_EVIDENCE_CHANGED", "已保存事实或明细已变化。")
    from masterdata.models import Material
    material = Material.objects.select_related("base_uom").filter(
        pk=contract.material_id, code=contract.material_code, company_id=user.company_id,
        is_active=True, unit_status="confirmed",
    ).first()
    if (not material or not material.base_uom_id or not material.base_uom.is_active
            or material.base_uom.company_id != user.company_id
            or material.base_uom.code != contract.output_uom_code
            or (pin["scope"] != FINITE_SCOPE and (
                not material.is_produced or digest(material_proof(material)) != pin.get("materialProofHash")))
            or (pin["scope"] == FINITE_SCOPE and (
                digest({**material_proof(material), "purchased": material.is_purchased}) != selected[0].get("materialProofHash")
                or contract.supply_type != selected[0].get("supplyType")
                or contract.order_specification.get("testSupplySelection") is not True))):
        _fail("SYSTEM_TEST_HANDOFF_MATERIAL_MISMATCH", "显式测试材料、半成品层级或单位条件不符。")
    _validate_requirement_limits(pin, record, contract, user)
    return _Admission(_TOKEN, operation, receipt_hash, {
        "admissionMode": pin["scope"], "developmentOnly": True,
        "formalCRMAdmitted": False, "formalManufacturingEligible": False,
        "receiptSha256": receipt_hash, "objectScope": obj,
        "sourceIdentity": identity, "contractHash": contract_hash,
    })


def _row(obj):
    return {field.attname: getattr(obj, field.attname) for field in obj._meta.concrete_fields}


def requirement_evidence(requirement):
    """Validate a predecessor's actual persisted chain, then fingerprint it.

    A caller cannot substitute a declared ID or an archived report for the
    requirement, source identities, committed ledgers, audits and transitions.
    """
    from masterdata.models import MasterDataWriteRequest, ExternalIdentity
    from system.models import OrganizationOperatingAuditRecord
    from workflow_runtime.models import BusinessStateTransition
    from .engineering_rule_foundation import specification_hash
    from .models import EngineeringRuleDefinition
    req = requirement
    role = str(req.order_specification.get("structureRole") or "").upper()
    company_id = req.calculation.company_id
    ledgers = list(MasterDataWriteRequest.objects.filter(
        organization_id=company_id, entity_type="EngineeringMaterialRequirement",
        action_code="production.engineering.material_requirement.create",
        status=MasterDataWriteRequest.Status.COMMITTED, target_entity_id=str(req.pk),
    ).select_related("source_identity"))
    if len(ledgers) != 1:
        _fail("SYSTEM_TEST_HANDOFF_PREDECESSOR_INVALID", "承接需求没有唯一真实已提交账本。")
    ledger = ledgers[0]
    audit = OrganizationOperatingAuditRecord.objects.filter(
        pk=ledger.result.get("auditId"), target_type="EngineeringMaterialRequirement",
        target_id=req.pk, organization_id=company_id,
        action_code="production.engineering.material_requirement.create",
    ).first()
    rule = EngineeringRuleDefinition.objects.filter(
        pk=req.trace.get("mappingRuleId"), company_id=company_id, status="released",
    ).first()
    if (not audit or not rule or not role or role != req.trace.get("structureRole")
            or audit.actor_id != req.trace.get("operatorId")
            or digest(audit.after_snapshot.get("request")) != ledger.request_hash
            or ledger.result.get("requirementId") != req.pk
            or ledger.result.get("mappingRuleId") != rule.pk
            or req.trace.get("mappingSpecificationHash") != specification_hash(rule.specification)
            or req.source_detail.calculation_id != req.calculation_id):
        _fail("SYSTEM_TEST_HANDOFF_PREDECESSOR_INVALID", "承接需求、规则、账本或真实审计不一致。")
    identity = ledger.source_identity
    fingerprint = digest({"mappingSpecificationHash": specification_hash(rule.specification),
                          "calculationResultHash": req.calculation.result_hash,
                          "quantity": str(req.calculated_quantity), "materialId": req.material_id})
    if (identity.organization_id != company_id or identity.mapping_status != ExternalIdentity.MappingStatus.MATCH
            or identity.target_entity_type != "engineering-material-requirements"
            or identity.target_entity_id != str(req.pk) or identity.source_fingerprint != fingerprint):
        _fail("SYSTEM_TEST_HANDOFF_PREDECESSOR_INVALID", "承接需求来源身份不一致。")
    mapping_ledgers = list(MasterDataWriteRequest.objects.filter(
        organization_id=company_id, entity_type="engineering-rule-definitions",
        action_code="production.master_data.create", status=MasterDataWriteRequest.Status.COMMITTED,
        target_entity_id=str(rule.pk),
    ).select_related("source_identity"))
    if len(mapping_ledgers) != 1:
        _fail("SYSTEM_TEST_HANDOFF_PREDECESSOR_INVALID", "承接Mapping没有唯一已提交来源账本。")
    mapping_ledger = mapping_ledgers[0]
    mapping_identity = mapping_ledger.source_identity
    if (mapping_identity.mapping_status != ExternalIdentity.MappingStatus.MATCH
            or mapping_identity.target_entity_type != "engineering-rule-definitions"
            or mapping_identity.target_entity_id != str(rule.pk)
            or mapping_identity.source_fingerprint != specification_hash(rule.specification)):
        _fail("SYSTEM_TEST_HANDOFF_PREDECESSOR_INVALID", "承接Mapping来源身份不一致。")
    transitions = list(BusinessStateTransition.objects.filter(
        object_type="EngineeringRuleDefinition", object_id=rule.pk,
    ).order_by("version"))
    if [(t.source_state, t.target_state) for t in transitions] != [
        ("", "draft"), ("draft", "reviewed"), ("reviewed", "released"),
    ]:
        _fail("SYSTEM_TEST_HANDOFF_PREDECESSOR_INVALID", "承接Mapping状态转换证据不完整。")
    rule_audits = []
    for item in transitions:
        prefix, _, audit_id = item.audit_reference.partition(":")
        match = OrganizationOperatingAuditRecord.objects.filter(
            pk=audit_id if audit_id.isdigit() else None,
            target_type="EngineeringRuleDefinition", target_id=rule.pk,
            organization_id=company_id, actor_id=item.operator_id,
            action_code=item.action_code,
        ).first() if prefix == "OrganizationOperatingAuditRecord" else None
        if not match:
            _fail("SYSTEM_TEST_HANDOFF_PREDECESSOR_INVALID", "承接Mapping转换缺少对应真实审计。")
        rule_audits.append(match)
    if mapping_ledger.result.get("auditId") != rule_audits[0].pk:
        _fail("SYSTEM_TEST_HANDOFF_PREDECESSOR_INVALID", "承接Mapping创建账本与审计不一致。")
    previous = req.order_specification.get("developmentValidation") or {}
    if (previous.get("admissionMode") not in {SCOPE, CONTINUATION_SCOPE, FINITE_SCOPE}
            or previous.get("developmentOnly") is not True or previous.get("formalCRMAdmitted") is not False):
        _fail("SYSTEM_TEST_HANDOFF_PREDECESSOR_INVALID", "承接需求缺少受控开发来源证明。")
    return {"requirement": _row(req), "ledger": _row(ledger), "identity": _row(identity),
            "audit": _row(audit), "mapping": _row(rule), "mappingLedger": _row(mapping_ledger),
            "mappingIdentity": _row(mapping_identity), "transitions": [_row(t) for t in transitions],
            "mappingAudits": [_row(a) for a in rule_audits]}


def _validate_requirement_limits(pin, record, contract, user):
    existing_requirements = list(record.material_requirements.values_list("pk", flat=True))
    if pin["scope"] in {CONTINUATION_SCOPE, FINITE_SCOPE}:
        from .models import EngineeringMaterialRequirement
        predecessors = pin.get("preservedRequirements")
        if not isinstance(predecessors, list) or not predecessors:
            _fail("SYSTEM_TEST_HANDOFF_PREDECESSOR_INVALID", "接续激活必须明确承接已有需求。")
        ids = [p.get("requirementId") for p in predecessors]
        if len(set(ids)) != len(ids):
            _fail("SYSTEM_TEST_HANDOFF_PREDECESSOR_INVALID", "承接需求身份重复。")
        roles = set()
        for predecessor in predecessors:
            req = EngineeringMaterialRequirement.objects.filter(
                pk=predecessor.get("requirementId"), calculation_id=record.pk,
            ).select_related("calculation", "source_detail").first()
            if not req:
                _fail("SYSTEM_TEST_HANDOFF_PREDECESSOR_INVALID", "承接需求缺失或跨核算范围。")
            evidence = requirement_evidence(req)
            role = str(req.order_specification.get("structureRole") or "").upper()
            previous = req.order_specification["developmentValidation"]
            if (digest(evidence) != predecessor.get("evidenceHash")
                    or predecessor.get("role") != role
                    or predecessor.get("ledgerId") != evidence["ledger"]["id"]
                    or predecessor.get("previousReceiptSha256") != previous.get("receiptSha256")
                    or previous.get("objectScope") != pin.get("objectScope")):
                _fail("SYSTEM_TEST_HANDOFF_PREDECESSOR_CHANGED", "承接需求及真实账本证明已变化。")
            roles.add(role)
        if str(contract.purpose_code).upper() in roles:
            _fail("SYSTEM_TEST_HANDOFF_DUPLICATE_ROLE", "本次结构角色已由承接需求覆盖，禁止重复生成。")
        # Preserved IDs are immutable facts, not a new write allowance. Only one
        # additional requirement belonging to this activation may be present.
        existing_requirements = [pk for pk in existing_requirements if pk not in ids]
        if pin["scope"] == FINITE_SCOPE:
            from masterdata.models import MasterDataWriteRequest
            contracts = pin.get("contracts", [])
            keys = [entry.get("idempotencyKey") for entry in contracts]
            hashes = [entry.get("contractHash") for entry in contracts]
            if (not keys or any(not key for key in keys) or len(set(keys)) != len(keys)
                    or len(set(hashes)) != len(hashes) or len(existing_requirements) > len(contracts)):
                _fail("SYSTEM_TEST_HANDOFF_REQUIREMENT_LIMIT", "有限合同清单无效或超额。")
            from .models import EngineeringMaterialRequirement
            for req in EngineeringMaterialRequirement.objects.filter(pk__in=existing_requirements):
                matching = [entry for entry in contracts if entry.get("contractHash") == (
                    req.order_specification.get("developmentValidation") or {}).get("contractHash")]
                if len(matching) != 1 or not MasterDataWriteRequest.objects.filter(
                    organization_id=user.company_id, entity_type="EngineeringMaterialRequirement",
                    action_code="production.engineering.material_requirement.create",
                    status=MasterDataWriteRequest.Status.COMMITTED,
                    idempotency_key=matching[0]["idempotencyKey"] + ":REQUIREMENT",
                    target_entity_id=str(req.pk),
                ).exists():
                    _fail("SYSTEM_TEST_HANDOFF_REQUIREMENT_LIMIT", "已有新增需求不属于有限合同提交结果。")
            return
    if len(existing_requirements) > 1:
        _fail("SYSTEM_TEST_HANDOFF_REQUIREMENT_LIMIT", "本激活最多允许一条材料需求。")
    if existing_requirements:
        from masterdata.models import MasterDataWriteRequest
        if not MasterDataWriteRequest.objects.filter(
            organization_id=user.company_id,
            action_code="production.engineering.material_requirement.create",
            entity_type="EngineeringMaterialRequirement",
            idempotency_key=contract.requirement_idempotency_key,
            status=MasterDataWriteRequest.Status.COMMITTED,
            target_entity_id=str(existing_requirements[0]),
        ).exists():
            _fail("SYSTEM_TEST_HANDOFF_REQUIREMENT_LIMIT", "已有需求不属于本激活的已提交结果，禁止增加第二条。")


def material_proof(material):
    unit = material.base_uom
    return {"id": material.pk, "code": material.code, "companyId": material.company_id,
            "active": material.is_active, "type": material.material_type,
            "produced": material.is_produced, "specification": material.specification,
            "unitStatus": material.unit_status, "unitId": unit.pk,
            "unitCode": unit.code, "unitDimension": unit.dimension,
            "unitActive": unit.is_active, "factor": str(unit.conversion_factor)}


def verify_admission(admission, *, user, contract):
    if not isinstance(admission, _Admission) or admission.token is not _TOKEN:
        _fail("SYSTEM_TEST_HANDOFF_CONTEXT_INVALID", "缺少服务端验证的开发上下文。")
    fresh = _validate(user=user, contract=contract, operation=admission.operation)
    if fresh.receipt_hash != admission.receipt_hash or fresh.proof != admission.proof:
        _fail("SYSTEM_TEST_HANDOFF_CONTEXT_INVALID", "开发上下文已变化。")
    return fresh


def preview(*, user, contract):
    from .saved_fact_material_requirement_service import _preview_saved_fact_material_requirement
    admission = _validate(user=user, contract=contract, operation="preview")
    return _preview_saved_fact_material_requirement(user=user, contract=contract, _development_context=admission)


def apply(*, user, contract):
    from .saved_fact_material_requirement_service import _apply_saved_fact_material_requirement
    admission = _validate(user=user, contract=contract, operation="apply")
    return _apply_saved_fact_material_requirement(user=user, contract=contract, _development_context=admission)


def readback(*, user, contract):
    from .saved_fact_material_requirement_service import _readback_saved_fact_material_requirement
    admission = _validate(user=user, contract=contract, operation="readback")
    return _readback_saved_fact_material_requirement(user=user, contract=contract, _development_context=admission)

"""Source-scoped attestations in existing identity/audit authorities; no approval engine."""
import hashlib
import json
from decimal import Decimal, InvalidOperation

from django.db import transaction
from masterdata.models import ExternalIdentity, Material, UnitOfMeasure
from pde.formal_import_actor_context import resolve_formal_import_actor, FormalImportActorContextError
from pde.models import ProductCategory, ProductDefinition, Routing
from system.authorization import AuthorizationService
from system.models import Department, Process, OrganizationOperatingAuditRecord, UserRoleScopeAssignment
from .models import Customer
from .services import SalesBusinessError
from .source_semantics import RULE_VERSION
from .whole_house_preview import whole_house_order_preview

SOURCE_SYSTEM = "PCE_GOVERNED_EXCEL"
SOURCE_TYPE = "BUSINESS_SOURCE_WORKBOOK"
SOURCE_OBJECT_TYPE = "SALES_ORDER"
ACTIONS = {
    "save-mapping": ("保存映射草稿", "sales.order.update"),
    "confirm-source": ("确认来源使用资格", "sales.order.confirm"),
    "confirm-mapping": ("确认映射及商业数量", "sales.order.confirm"),
    "create-draft": ("创建销售订单草稿", "sales.order.create"),
}


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest().upper()


def governed_source_contract():
    p = whole_house_order_preview()
    facts = {k: p[k] for k in ("source", "order", "productGroups", "sourceLineIdentities")}
    return {**facts, "sourceFingerprint": canonical_hash(facts), "ruleVersion": RULE_VERSION}


def identity_query(company_id):
    return ExternalIdentity.objects.filter(organization_id=company_id, source_system=SOURCE_SYSTEM,
        source_type=SOURCE_TYPE, source_object_type=SOURCE_OBJECT_TYPE,
        external_id=governed_source_contract()["order"]["externalOrderNo"])


def source_actor(user, action, department_id=None):
    permission = ACTIONS[action][1]
    try:
        actor = resolve_formal_import_actor(user=user, organization_id=user.company_id, action_code=permission)
    except FormalImportActorContextError as error:
        raise SalesBusinessError(error.code, error.message, 403)
    assignment = UserRoleScopeAssignment.objects.get(user=user, organization_id=user.company_id, role_id=actor["roleId"], active=True)
    # Explicit import attestations require organization or a known department scope;
    # even a superuser must have this real role/position/responsibility binding.
    if assignment.scope_code not in ("ORGANIZATION", "ALL") and not (
        assignment.scope_code == "DEPARTMENT" and department_id and assignment.department_id == int(department_id)
    ):
        raise SalesBusinessError("SOURCE_SCOPE_DENIED", "来源办理需要本组织授权，或与映射销售部门一致的部门授权。", 403)
    decision = AuthorizationService.decide(user=user, action_code=permission, organization_id=user.company_id,
        business_object={"organizationId": user.company_id, "departmentId": department_id},
        context={"actionType": action, "businessWrite": True})
    if not decision.get("allowed"):
        raise SalesBusinessError("SOURCE_SCOPE_DENIED", decision.get("reason", "来源办理范围不足。"), 403)
    return actor, decision


def mapping_candidates(company_id):
    customers = list(Customer.objects.filter(company_id=company_id, is_active=True).values("id", "code", "name"))
    exact = [r for r in customers if r["name"] == "温岭江公馆"]
    external = list(ExternalIdentity.objects.filter(organization_id=company_id, target_entity_type__in=["Customer", "customers"],
        source_system="07经销商.xlsx", source_type="USER_VALIDATED_XLSX", source_object_type="DEALER_SOURCE_ROW",
        mapping_status="MATCH").values("id", "external_id", "target_entity_id", "source_system"))
    formal = [r for r in external if r["target_entity_id"] in {str(c["id"]) for c in exact}]
    units = list(UnitOfMeasure.objects.filter(company_id=company_id, is_active=True).values("id", "code", "name", "dimension", "decimal_places", "conversion_base_id", "conversion_factor"))
    for u in units:
        u["conversion_factor"] = str(u["conversion_factor"])
    materials = list(Material.objects.filter(company_id=company_id, is_active=True, material_type__in=["finished", "semi"]).values("id", "code", "name", "specification", "material_type", "base_uom_id", "unit_status"))
    source_rows = governed_source_contract()["sourceLineIdentities"]
    engineering = []
    for code in sorted({r["engineeringSourceCode"] for r in source_rows}):
        aliases = list(ExternalIdentity.objects.filter(organization_id=company_id, source_system="PCE_FOUNDATION_WAVE1",
            source_type="APPROVED_XLSX", source_object_type="SEMI_FINISHED_MATERIAL_SOURCE", target_entity_type="materials",
            external_id=f"05半成品板材.xlsx|半成品板材|CODE:{code}", mapping_status="MATCH"))
        targets = {int(a.target_entity_id) for a in aliases if str(a.target_entity_id).isdigit()}
        matches = list(Material.objects.filter(company_id=company_id, is_active=True, pk__in=targets).values("id", "code", "name", "material_type", "base_uom_id", "unit_status"))
        engineering.append({"sourceCode": code, "unique": len(matches) == 1, "matches": matches,
            "externalIdentityIds": [a.pk for a in aliases], "basis": "已批准05半成品板材来源稳定外部身份，精确匹配，同组织启用目标；仅作工程引用"})
    routing_refs = []
    for source_code in sorted({r["rawFields"]["sourceEngineeredMaterialName"] for r in source_rows}):
        aliases = list(ExternalIdentity.objects.filter(organization_id=company_id, source_system="02工艺路线.xlsx",
            source_type="USER_VALIDATED_XLSX", source_object_type="ROUTING", target_entity_type="routings", external_id=source_code, mapping_status="MATCH"))
        ids = {int(a.target_entity_id) for a in aliases if str(a.target_entity_id).isdigit()}
        matches = list(Routing.objects.filter(company_id=company_id, pk__in=ids, is_active=True).values("id", "routing_code", "name"))
        routing_refs.append({"sourceCode": source_code, "unique": len(matches) == 1, "matches": matches,
            "externalIdentityIds": [a.pk for a in aliases], "basis": "已确认02工艺路线外部身份；是工艺引用，不是销售明细或制造就绪承诺"})
    return {
        "organizationId": company_id, "customers": customers, "customerExactMatches": exact,
        "customerExternalMappings": formal,
        "resolvedCustomerId": exact[0]["id"] if len(exact) == 1 and formal else None,
        "customerBasis": "同组织启用客户的唯一同名命中，并由既有 MATCH 外部身份交叉核实；否则仅候选。",
        "departments": list(Department.objects.filter(company_id=company_id, is_active=True).values("id", "code", "name")),
        "departmentDifference": "归档没有销售部门代码；接单人当前任职不能证明历史销售部门。",
        "materials": materials, "units": units,
        "categories": list(ProductCategory.objects.filter(company_id=company_id, is_active=True, name__in=["房门", "饰面", "柜体"]).values("id", "code", "name")),
        "products": list(ProductDefinition.objects.filter(company_id=company_id, is_active=True).values("id", "product_code", "product_name", "material_id", "status")),
        "engineeringMaterials": engineering, "routingReferences": routing_refs,
        "engineeringProcesses": list(Process.objects.filter(company_id=company_id, is_active=True,
            quantity_driver__in=["饰面数量", "柜体数量", "房门数量"]).values("id", "code", "name", "quantity_driver", "calculation_basis", "calculation_uom_id")),
        "productDifference": "来源产品类型是类别，工程编码不是销售产品编码；候选不自动选中。需要新对象时使用既有主数据维护。",
        "unitBasis": "选定正式产品后，以其已确认 base_uom 为业务单位；凭据单位仅允许正式同维度、同换算基准的精确换算。",
    }


def validate_resolution(company_id, resolution):
    """Engineering references are a partition, NOT additive commercial quantities.

    Each unique commercial document position contributes exactly once. Cross-
    category merges and one-source-to-many splits are deliberately unsupported.
    """
    validate_draft_shape(resolution)
    if not Customer.objects.filter(pk=resolution.get("customerId"), company_id=company_id, is_active=True).exists():
        raise SalesBusinessError("CUSTOMER_INVALID", "请选择本组织启用客户，并补充非唯一匹配依据。", 409)
    if not Department.objects.filter(pk=resolution.get("departmentId"), company_id=company_id, is_active=True).exists():
        raise SalesBusinessError("DEPARTMENT_INVALID", "请选择有历史归属依据的本组织销售部门。", 409)
    for key in ("customerEvidence", "departmentEvidence"):
        if not str(resolution.get(key) or "").strip():
            raise SalesBusinessError("SOURCE_MAPPING_EVIDENCE_REQUIRED", f"缺少 {key} 的凭据定位及适用范围。", 409)
    source = {r["salesOrderItemNo"]: r for r in governed_source_contract()["sourceLineIdentities"]}
    used, commercial = set(), set()
    items, checks = [], []
    lines = resolution.get("lines") or []
    if not isinstance(lines, list) or not lines or len(lines) > len(source):
        raise SalesBusinessError("SOURCE_LINES_REQUIRED", "需建立有商业凭据的销售行；不预设行数。", 409)
    for i, line in enumerate(lines, 1):
        if not isinstance(line, dict):
            raise SalesBusinessError("SOURCE_MAPPING_INVALID", "销售行映射格式无效。", 400)
        for key in ("commercialPosition", "productIdentity", "configuration", "space", "deliveryResponsibility", "mappingEvidence", "quantityEvidence"):
            if not str(line.get(key) or "").strip():
                raise SalesBusinessError("SOURCE_LINE_EVIDENCE_REQUIRED", f"第 {i} 行缺少 {key}；不适用也需明确说明及依据。", 409)
        if line["commercialPosition"] in commercial:
            raise SalesBusinessError("SOURCE_COMMERCIAL_DUPLICATE", "同一商业凭据行不得重复生成销售数量。", 409)
        commercial.add(line["commercialPosition"])
        refs = line.get("sourceLineIds") or []
        if not isinstance(refs, list) or not refs or any(not isinstance(r, str) for r in refs):
            raise SalesBusinessError("SOURCE_REFERENCE_REQUIRED", f"第 {i} 行需要来源行关联。", 409)
        if len(set(refs)) != len(refs) or used.intersection(refs):
            raise SalesBusinessError("SOURCE_REFERENCE_DUPLICATE", "来源行不得重复计入或拆入多条销售行；一对多需另行提供拆分规则，本版不支持。", 409)
        if not set(refs).issubset(source):
            raise SalesBusinessError("SOURCE_REFERENCE_UNKNOWN", "存在不属于本来源版本的行身份。", 409)
        if len({source[r]["productType"] for r in refs}) != 1:
            raise SalesBusinessError("SOURCE_ILLEGAL_AGGREGATION", "不允许跨类别无依据聚合；请分开建立商业行。", 409)
        # Known source identity differences cannot be overwritten by an assertion.
        for field, key in (("sourceSpecification", "configuration"), ("sourceSpace", "space"), ("sourceProductName", "productIdentity")):
            known = {source[r]["rawFields"].get(field) for r in refs} - {None, ""}
            if known and known != {line[key]}:
                raise SalesBusinessError("SOURCE_IDENTITY_CONFLICT", "来源中已知的产品、配置或空间与拟建明细冲突。", 409)
        used.update(refs)
        material = Material.objects.select_related("base_uom").filter(pk=line.get("materialId"), company_id=company_id, is_active=True, material_type__in=["finished", "semi"]).first()
        if not material:
            raise SalesBusinessError("SOURCE_SALES_PRODUCT_INVALID", "销售行必须映射本组织正式成品或半成品；不能用采购原材料代替。", 409)
        base = material.base_uom
        if not base or material.unit_status != "confirmed" or not base.is_active or base.company_id != company_id:
            raise SalesBusinessError("SOURCE_PRODUCT_UOM_UNCONFIRMED", "产品基本单位尚未正式确认，请从既有物料维护入口处理。", 409)
        unit = UnitOfMeasure.objects.filter(pk=line.get("quantityUomId"), company_id=company_id, is_active=True).first()
        if not unit or unit.dimension != base.dimension or (unit.conversion_base_id or unit.pk) != (base.conversion_base_id or base.pk):
            raise SalesBusinessError("SOURCE_UOM_MISMATCH", "凭据单位与产品业务单位缺少正式同维度换算关系。", 409)
        if line.get("quantityBasis") != "COMMERCIAL_DOCUMENT" or not isinstance(line.get("quantity"), str):
            raise SalesBusinessError("SOURCE_QUANTITY_BASIS_INVALID", "商业数量必须来自独立商业凭据并以十进制字符串提交；不能复制工序合计。", 409)
        try:
            quantity = Decimal(line["quantity"])
            if not quantity.is_finite() or quantity <= 0 or len(line["quantity"]) > 40:
                raise InvalidOperation
            if quantity != quantity.quantize(Decimal(1).scaleb(-unit.decimal_places)):
                raise SalesBusinessError("SOURCE_QUANTITY_PRECISION_UNRESOLVED", "凭据数量超过所选单位正式精度；禁止有损舍入。", 409)
            converted = quantity * unit.conversion_factor / base.conversion_factor
            places = min(4, base.decimal_places)
            if converted != converted.quantize(Decimal(1).scaleb(-places)) or converted >= Decimal("100000000000000"):
                raise SalesBusinessError("SOURCE_QUANTITY_PRECISION_UNRESOLVED", "精确换算量无法由销售数量字段和单位精度无损表达；本版不舍入、不改变模型。", 409)
            if converted * base.conversion_factor != quantity * unit.conversion_factor:
                raise SalesBusinessError("SOURCE_QUANTITY_CONSERVATION_FAILED", "数量换算不能精确守恒。", 409)
        except (InvalidOperation, ValueError, ZeroDivisionError):
            raise SalesBusinessError("SOURCE_QUANTITY_INVALID", "商业数量无效或无法精确表达。", 409)
        business_qty = format(converted.normalize(), "f")
        check = {"lineNo": i, "commercialPosition": line["commercialPosition"], "sourceReferenceCount": len(refs),
            "rawCommercialQuantity": line["quantity"], "quantityUomId": unit.pk, "businessQuantity": business_qty,
            "businessUomId": base.pk, "productId": material.pk, "productCode": material.code,
            "quantityRoleLabel": "商业凭据行计入一次；工程来源只关联，不加总销售量", "conservationStatusLabel": "精确守恒",
            "unitRule": {"sourceFactor": str(unit.conversion_factor), "targetFactor": str(base.conversion_factor), "dimension": base.dimension, "precision": places},
            "masterFingerprint": canonical_hash({"material": [material.code, material.name, material.specification, material.unit_status], "unit": [unit.pk, unit.decimal_places, str(unit.conversion_factor)], "base": [base.pk, base.decimal_places, str(base.conversion_factor)]})}
        checks.append(check)
        items.append({"lineNo": i, "materialId": material.pk, "uomId": base.pk, "quantity": business_qty,
            "requiredDate": governed_source_contract()["order"]["deliveryDate"], "externalLineNo": line["commercialPosition"],
            "customerProductName": line["productIdentity"], "specification": line["configuration"], "spaceName": line["space"],
            "engineeringMode": "ORDER_ENGINEERED", "engineeringRequirements": line["mappingEvidence"],
            "engineeringAttributes": [{"sequence": seq, "rawSource": "08订单排产信息（样版）.xlsx", "rawSheet": "生产计划",
                "externalSource": ref, "rawField": "source_line_identity", "rawValue": source[ref],
                "canonicalField": "external_source_line_identity", "normalizedValue": ref,
                "valueType": "code", "sourceType": "ENGINEERING_INPUT"} for seq, ref in enumerate(refs, 1)]})
    if used != set(source):
        raise SalesBusinessError("SOURCE_MAPPING_INCOMPLETE", f"还有 {len(set(source)-used)} 条来源行未关联，禁止部分记录静默丢失。", 409)
    return items, checks


def validate_draft_shape(resolution):
    if not isinstance(resolution, dict) or not isinstance(resolution.get("lines"), list):
        raise SalesBusinessError("SOURCE_MAPPING_INVALID", "映射必须包含销售行列表；允许空草稿，不允许格式损坏。", 400)
    for key in ("customerId", "departmentId"):
        if resolution.get(key) is not None and (type(resolution[key]) is not int or resolution[key] <= 0):
            raise SalesBusinessError("SOURCE_MAPPING_INVALID", "主数据身份必须为有效 ID。", 400)
    if len(resolution["lines"]) > 37:
        raise SalesBusinessError("SOURCE_MAPPING_INVALID", "当前规则不支持超过来源数的拆分。", 400)
    for line in resolution["lines"]:
        if not isinstance(line, dict) or not isinstance(line.get("sourceLineIds"), list) or any(not isinstance(ref, str) for ref in line["sourceLineIds"]):
            raise SalesBusinessError("SOURCE_MAPPING_INVALID", "来源关联必须是稳定身份列表。", 400)
        for key in ("materialId", "quantityUomId"):
            if line.get(key) is not None and (type(line[key]) is not int or line[key] <= 0):
                raise SalesBusinessError("SOURCE_MAPPING_INVALID", "产品或单位身份必须为有效 ID。", 400)
        for key in ("commercialPosition", "productIdentity", "configuration", "space", "deliveryResponsibility", "mappingEvidence", "quantityEvidence", "quantity", "quantityBasis"):
            if not isinstance(line.get(key, ""), str) or len(line.get(key, "")) > 200:
                raise SalesBusinessError("SOURCE_MAPPING_INVALID", "商业行字段须为不超过 200 字的文本。", 400)


def review_state(company_id):
    contract = governed_source_contract()
    identity = identity_query(company_id).first()
    meta = (identity.audit_metadata or {}) if identity else {}
    resolution = meta.get("resolution") or {"customerId": None, "departmentId": None, "customerEvidence": "", "departmentEvidence": "", "lines": []}
    checks, blocker = [], None
    try:
        _, checks = validate_resolution(company_id, resolution)
    except (SalesBusinessError, TypeError, ValueError) as error:
        blocker = {"code": getattr(error, "code", "SOURCE_MAPPING_INVALID"), "message": str(error)}
    binding = {"organizationId": company_id, "sourceFingerprint": contract["sourceFingerprint"], "resolutionHash": canonical_hash(resolution),
        "revision": meta.get("revision", 0), "ruleVersion": RULE_VERSION, "masterChecksHash": canonical_hash(checks),
        "headerMasterHash": canonical_hash({
            "customer": list(Customer.objects.filter(company_id=company_id, pk=resolution.get("customerId")).values("id", "code", "name", "is_active")),
            "department": list(Department.objects.filter(company_id=company_id, pk=resolution.get("departmentId")).values("id", "code", "name", "is_active")),
        })}
    audits = list(OrganizationOperatingAuditRecord.objects.filter(organization_id=company_id, target_type="SalesSourceReview", target_id=identity.pk).order_by("pk")) if identity else []
    effective = {}
    for audit in audits:
        snapshot = audit.after_snapshot or {}
        if snapshot.get("binding") == binding and audit.action_code in ("sales.source.confirm-source", "sales.source.confirm-mapping"):
            effective[audit.action_code.rsplit(".", 1)[-1]] = audit.pk
    blockers = ([blocker] if blocker else [])
    for scope, message in (("confirm-source", "待有权责任人确认来源使用资格。"), ("confirm-mapping", "待有权责任人确认映射及商业数量口径。")):
        if scope not in effective:
            blockers.append({"code": scope, "message": message})
    return {"identityId": identity.pk if identity else None, "targetOrderId": identity.target_entity_id if identity else None,
        "resolution": resolution, "binding": binding, "checks": checks, "blockers": blockers,
        "allowed": not blockers, "statusLabel": "可创建销售草稿" if not blockers else "待办理",
        "sourceStatusLabel": "来源资格已确认" if "confirm-source" in effective else "来源尚待业务确认",
        "mappingStatusLabel": "映射和数量已确认" if "confirm-mapping" in effective else "映射和数量待确认",
        "effectiveConfirmations": effective,
        "audits": [{"id": a.pk, "actionLabel": ACTIONS.get(a.action_code.rsplit(".", 1)[-1], ("来源记录",))[0],
            "actorId": a.actor_id, "createdAt": a.created_at.isoformat(), "evidence": a.reason,
            "effective": a.pk in effective.values()} for a in audits]}


@transaction.atomic
def perform_source_action(*, user, action, payload):
    if action not in ACTIONS or action == "create-draft":
        raise SalesBusinessError("SOURCE_ACTION_INVALID", "来源动作不存在。", 400)
    state = review_state(user.company_id)
    resolution = payload.get("resolution") if action == "save-mapping" else state["resolution"]
    if not isinstance(resolution, dict) or len(json.dumps(resolution, ensure_ascii=False)) > 200000:
        raise SalesBusinessError("SOURCE_MAPPING_INVALID", "映射草稿格式或长度无效。", 400)
    validate_draft_shape(resolution)
    actor, _ = source_actor(user, action, resolution.get("departmentId"))
    if payload.get("binding") != state["binding"]:
        raise SalesBusinessError("SOURCE_PREVIEW_STALE", "来源或映射已变化，请刷新后重新核对。", 409)
    evidence = str(payload.get("evidence") or "").strip()
    if not evidence or len(evidence) > 300:
        raise SalesBusinessError("SOURCE_CONFIRMATION_EVIDENCE_REQUIRED", "请填写 1—300 字凭据定位、适用范围及办理依据。", 409)
    if action != "save-mapping" and payload.get("confirmed") is not True:
        raise SalesBusinessError("SOURCE_CONFIRMATION_REQUIRED", "请显式确认本动作范围；不包含订单审批或需求生成。", 409)
    if action == "confirm-mapping":
        validate_resolution(user.company_id, resolution)
    identity, _ = ExternalIdentity.objects.get_or_create(organization_id=user.company_id, source_system=SOURCE_SYSTEM,
        source_type=SOURCE_TYPE, source_object_type=SOURCE_OBJECT_TYPE, external_id=governed_source_contract()["order"]["externalOrderNo"],
        defaults={"target_entity_type": "SalesOrder", "mapping_status": "REVIEW", "source_fingerprint": state["binding"]["sourceFingerprint"]})
    identity = ExternalIdentity.objects.select_for_update().get(pk=identity.pk)
    if review_state(user.company_id)["binding"] != state["binding"]:
        raise SalesBusinessError("SOURCE_PREVIEW_STALE", "其他办理人已修改，请刷新。", 409)
    if identity.target_entity_id:
        raise SalesBusinessError("SOURCE_TARGET_ALREADY_MAPPED", "已建档来源不能重新编辑或重复确认；请走原订单受控变更。", 409)
    if action == "save-mapping":
        meta = dict(identity.audit_metadata or {})
        meta.update(resolution=resolution, revision=state["binding"]["revision"] + 1)
        identity.audit_metadata = meta
        identity.source_fingerprint = state["binding"]["sourceFingerprint"]
        identity.save(update_fields=["audit_metadata", "source_fingerprint"])
    after = review_state(user.company_id)
    OrganizationOperatingAuditRecord.objects.create(organization_id=user.company_id, actor=user,
        action_code=f"sales.source.{action}", target_type="SalesSourceReview", target_id=identity.pk,
        target_label=identity.external_id, reason=evidence,
        before_snapshot={"binding": state["binding"]}, after_snapshot={"binding": after["binding"], "resolution": resolution, "actorContext": actor, "scope": action})
    return review_state(user.company_id)

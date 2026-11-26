"""Governed non-production development-contract sample for engineering source 11.

The sample is a mode of the existing SalesOrder authority.  It never creates a
parallel contract/order model, publishes downstream work, or writes price master
data.  Business writes are additionally locked to the named B acceptance DB.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
import os
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from masterdata.models import ExternalIdentity, MasterDataWriteRequest, Material, UnitOfMeasure
from pde.models import EngineeringSourceRecord
from pfm.models import Employee
from system.authorization import AuthorizationService
from system.models import Department, OrganizationOperatingAuditRecord

from .models import Customer, SalesOrder
from .services import SalesBusinessError, create_order, update_order, update_order_item


SAMPLE_CONTRACT_NO = "PCE-DEV-SC-20260915-001"
SAMPLE_VERSION = "V1.0"
EXPECTED_SOURCE_VERSION = "R20260915144257758338"
EXPECTED_SOURCE_CONTENT_HASH = "a79160cecfe149dd3615ffc55a128ac3b9cca4ad4286127ec05f67f1f8531644"
EXPECTED_DATABASE = Path(r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3")
SOURCE_SYSTEM = "PCE_ENGINEERING_SOURCE"
SOURCE_TYPE = "DEVELOPMENT_CONTRACT_SAMPLE"
SOURCE_OBJECT_TYPE = "SALES_ORDER"
ACTION_CODE = "sales.development_contract.sample.save"
MONEY = Decimal("0.01")

LINE_DEFINITIONS = (
    {"code": "DEV-L01", "name": "单开房门（按工程配置）", "quantity": "5", "unit": "扇", "unitPrice": "2800", "requiredDate": "2026-10-20", "product": "房门", "component": "单开门"},
    {"code": "DEV-L02", "name": "单面门套（按工程配置）", "quantity": "3", "unit": "套", "unitPrice": "600", "requiredDate": "2026-10-20", "product": "房门", "component": "单面套"},
    {"code": "DEV-L03", "name": "柜体配套部件包（开发组合）", "quantity": "1", "unit": "套", "unitPrice": "48000", "requiredDate": "2026-10-28", "product": "柜体", "component": None},
    {"code": "DEV-L04", "name": "L型木饰面（按工程配置）", "quantity": "1", "unit": "块", "unitPrice": "1800", "requiredDate": "2026-10-28", "product": "饰面", "component": "木饰面L型"},
)


def _money(value):
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def calculate_quote(lines):
    if not isinstance(lines, list) or len(lines) != 4:
        raise SalesBusinessError("DEVELOPMENT_CONTRACT_LINES_INVALID", "开发合同必须保留4条商业行。", 409)
    calculated = []
    totals = {"gross": Decimal("0"), "net": Decimal("0"), "tax": Decimal("0")}
    expected_codes = [row["code"] for row in LINE_DEFINITIONS]
    if [str(row.get("code") or "") for row in lines] != expected_codes:
        raise SalesBusinessError("DEVELOPMENT_CONTRACT_LINES_INVALID", "商业行身份或顺序已变化，禁止静默替换。", 409)
    for source in lines:
        try:
            quantity = Decimal(str(source.get("quantity")))
            unit_price = Decimal(str(source.get("unitPrice")))
            tax_rate = Decimal(str(source.get("taxRate", "0.13")))
        except (InvalidOperation, TypeError):
            raise SalesBusinessError("DEVELOPMENT_CONTRACT_NUMBER_INVALID", "数量、单价或税率不是有效数字。")
        if quantity <= 0 or unit_price < 0 or tax_rate < 0 or tax_rate > 1:
            raise SalesBusinessError("DEVELOPMENT_CONTRACT_NUMBER_INVALID", "数量必须大于0，单价及税率必须在合法范围。")
        if source.get("priceTaxMode") != "tax_inclusive":
            raise SalesBusinessError("DEVELOPMENT_CONTRACT_PRICE_MODE_INVALID", "本样本只采用含税单价口径。", 409)
        gross = _money(quantity * unit_price)
        net = _money(gross / (Decimal("1") + tax_rate))
        tax = _money(gross - net)
        row = {**source, "quantity": str(quantity), "unitPrice": str(unit_price), "taxRate": str(tax_rate),
               "grossAmount": str(gross), "netAmount": str(net), "taxAmount": str(tax)}
        calculated.append(row)
        totals["gross"] += gross; totals["net"] += net; totals["tax"] += tax
    return {"lines": calculated, "totals": {key: str(_money(value)) for key, value in totals.items()}}


def _source_and_groups(company_id, source_record_id):
    source = EngineeringSourceRecord.objects.filter(pk=source_record_id, company_id=company_id).first()
    if not source:
        raise SalesBusinessError("ENGINEERING_SOURCE_NOT_FOUND", "当前公司范围内未找到工程来源。", 404)
    if source.source_version != EXPECTED_SOURCE_VERSION or source.content_hash.lower() != EXPECTED_SOURCE_CONTENT_HASH:
        raise SalesBusinessError("DEVELOPMENT_CONTRACT_SOURCE_MISMATCH", "开发合同样本只适用于已核对的明确来源修订和内容指纹。", 409)
    rows = source.source_payload.get("engineeringRows", []) if isinstance(source.source_payload, dict) else []
    groups = {definition["code"]: [] for definition in LINE_DEFINITIONS}
    for row in rows:
        product, component = str(row.get("product") or ""), str(row.get("component") or "")
        if product == "房门" and component == "单开门": code = "DEV-L01"
        elif product == "房门" and component == "单面套": code = "DEV-L02"
        elif product == "柜体": code = "DEV-L03"
        elif product == "饰面" and component == "木饰面L型": code = "DEV-L04"
        else: raise SalesBusinessError("DEVELOPMENT_CONTRACT_SOURCE_UNMAPPED", "存在不能归入4条开发商业行的工程来源。", 409)
        groups[code].append(row)
    counts = {key: len(value) for key, value in groups.items()}
    if counts != {"DEV-L01": 5, "DEV-L02": 3, "DEV-L03": 62, "DEV-L04": 1}:
        raise SalesBusinessError("DEVELOPMENT_CONTRACT_SOURCE_COUNT_MISMATCH", f"工程来源实际分组为{counts}，未执行写入。", 409)
    ids = [str(row.get("id") or "") for values in groups.values() for row in values]
    if len(ids) != 71 or any(not value for value in ids) or len(set(ids)) != 71:
        raise SalesBusinessError("DEVELOPMENT_CONTRACT_SOURCE_IDENTITY_INVALID", "71条来源稳定身份缺失或重复。", 409)
    return source, groups


def _configured_source_and_groups(company_id):
    matches = list(EngineeringSourceRecord.objects.filter(
        company_id=company_id,
        source_version=EXPECTED_SOURCE_VERSION,
        content_hash__iexact=EXPECTED_SOURCE_CONTENT_HASH,
    ).values_list("pk", flat=True))
    if len(matches) != 1:
        raise SalesBusinessError(
            "DEVELOPMENT_CONTRACT_ENTRY_SOURCE_UNRESOLVED",
            "开发合同样本没有解析到唯一的明确关联工程来源；未回退到历史来源。",
            409,
            {"configuredSourceVersion": EXPECTED_SOURCE_VERSION, "matchCount": len(matches)},
        )
    return _source_and_groups(company_id, matches[0])


def _authorization(user, action):
    return AuthorizationService.decide(user=user, action_code=action, organization_id=user.company_id,
        business_object={"organizationId": user.company_id}, context={"actionType": "DEVELOPMENT_CONTRACT_SAMPLE", "businessWrite": action != "sales.order.view"})


def _actor_readiness(user, action):
    decision = _authorization(user, action)
    if not decision.get("allowed"):
        return {
            "ready": False,
            "code": decision.get("decisionCode", "PERMISSION_DENIED"),
            "reason": decision.get("reason", "销售订单权限校验失败。"),
        }
    employee = Employee.objects.select_related("position_ref").filter(
        user=user, status="active", position_ref__is_active=True,
    ).first()
    if not employee:
        return {
            "ready": False,
            "code": "SALES_ACTOR_EMPLOYEE_REQUIRED",
            "reason": "销售执行账户必须关联在职员工和正式岗位。",
        }
    return {
        "ready": True,
        "code": "READY",
        "reason": "销售账户、员工、岗位、业务动作权限和公司范围校验通过。",
        "actor": {
            "userId": user.pk,
            "username": user.username,
            "employeeId": employee.pk,
            "employeeNo": employee.employee_no,
            "positionId": employee.position_ref_id,
            "positionCode": employee.position_ref.code,
            "organizationId": user.company_id,
            "permissionCode": action,
            "authorizationDecision": decision.get("decisionCode"),
        },
    }


def _default_contract(groups):
    lines = []
    for definition in LINE_DEFINITIONS:
        refs = groups[definition["code"]]
        lines.append({**definition, "taxRate": "0.13", "priceTaxMode": "tax_inclusive",
            "sourceRowCount": len(refs), "sourceRowIds": [str(row["id"]) for row in refs],
            "sourceRows": [{"id": row["id"], "position": f"{row.get('sourceSheet')}!第{row.get('sourceRow')}行",
                "space": row.get("space"), "product": row.get("product"), "component": row.get("component"),
                "quantity": row.get("quantity"), "unit": row.get("unit")} for row in refs]})
    calculated = calculate_quote(lines)
    return {
        "contractNo": SAMPLE_CONTRACT_NO, "contractVersion": SAMPLE_VERSION, "purpose": "DEVELOPMENT_ONLY",
        "supplierName": "掌云智造科技有限公司", "customerName": "上海王燕", "projectName": "上海 大居苑",
        "sourceOrderNo": "1-4-正", "orderDate": "2026-09-15", "quoteValidUntil": "2026-09-30",
        "customerRequiredDate": "2026-10-30", "committedDeliveryDate": "2026-10-28",
        "engineeringConfirmationTarget": "2026-09-18", "currency": "CNY",
        "supplierContact": "冯美", "supplierPhonePlaceholder": "00000000000（测试占位）", "supplierEmailPlaceholder": "sales@example.invalid",
        "customerContact": "上海王燕", "customerPhonePlaceholder": "00000000000（测试占位）", "customerEmailPlaceholder": "buyer@example.invalid",
        "deliveryAddressPlaceholder": "上海市·上海 大居苑·开发收货点",
        "transportInstallation": "报价包含本样本所列产品的运送及安装，不另列运装费",
        "paymentNodes": [{"name": "下单定金", "ratio": "0.30"}, {"name": "发货前", "ratio": "0.60"}, {"name": "安装验收后尾款", "ratio": "0.10"}],
        **calculated,
    }


def build_development_contract_entry(*, company_id, user):
    """Resolve the normal workbench entry from the sample configuration.

    The process-center route does not carry a source row id.  This resolver
    binds the visible entry to the unique configured version + content hash,
    while the contract detail endpoint retains the formal sales view gate.
    """
    source, groups = _configured_source_and_groups(company_id)
    contract = _default_contract(groups)
    view_decision = _authorization(user, "sales.order.view")
    return {
        "entryLabel": "开发合同与报价",
        "contractNo": contract["contractNo"],
        "customerName": contract["customerName"],
        "projectName": contract["projectName"],
        "sourceOrderNo": contract["sourceOrderNo"],
        "purposeLabel": "开发联调样本",
        "sourceRowCount": sum(len(value) for value in groups.values()),
        "commercialLineCount": len(LINE_DEFINITIONS),
        "grossAmount": contract["totals"]["gross"],
        "viewDecision": view_decision,
        "target": {
            "path": "/sales/orders",
            "query": {"mode": "development-contract", "sourceRecord": source.pk},
        },
        "strictFacts": {
            "factSource": "development contract sample configuration + EngineeringSourceRecord",
            "configuredSourceVersion": EXPECTED_SOURCE_VERSION,
            "configuredSourceContentHash": EXPECTED_SOURCE_CONTENT_HASH,
            "resolvedSourceRecordId": source.pk,
            "resolvedSourceRowCount": sum(len(value) for value in groups.values()),
            "historicalFallbackUsed": False,
            "businessWriteCount": 0,
        },
    }


def _persisted_contract(order, groups):
    meta = (order.delivery_information or {}).get("developmentContract", {})
    lines = []
    by_code = {item.external_line_no: item for item in order.items.select_related("uom", "material").order_by("line_no")}
    defaults = _default_contract(groups)
    for definition in LINE_DEFINITIONS:
        item = by_code.get(definition["code"])
        if not item: return None
        lines.append({**definition, "quantity": str(item.quantity.normalize()), "unitPrice": str(item.unit_price.normalize()),
            "taxRate": str(item.tax_rate.normalize()), "priceTaxMode": item.price_tax_mode,
            "sourceRowCount": len(groups[definition["code"]]), "sourceRowIds": [str(row["id"]) for row in groups[definition["code"]]],
            "sourceRows": defaults["lines"][[row["code"] for row in LINE_DEFINITIONS].index(definition["code"])]["sourceRows"]})
    return {**defaults, **meta, "lines": calculate_quote(lines)["lines"], "totals": calculate_quote(lines)["totals"]}


def build_development_contract_preview(*, company_id, source_record_id, user):
    view_decision = _authorization(user, "sales.order.view")
    if not view_decision["allowed"]:
        raise SalesBusinessError(view_decision["decisionCode"], view_decision["reason"], 403)
    source, groups = _source_and_groups(company_id, source_record_id)
    order = SalesOrder.objects.prefetch_related("items__uom", "items__material").filter(company_id=company_id, contract_reference=SAMPLE_CONTRACT_NO).first()
    contract = _persisted_contract(order, groups) if order else _default_contract(groups)
    action = "sales.order.update" if order else "sales.order.create"
    authorization, actor = _authorization(user, action), _actor_readiness(user, action)
    blockers = []
    if not authorization["allowed"]: blockers.append({"code": authorization["decisionCode"], "message": authorization["reason"]})
    if not actor["ready"]: blockers.append({"code": actor["code"], "message": actor["reason"]})
    return {
        "pageId": "sales-orders", "subview": "development-contract", "sampleStatus": "SAVED_DRAFT" if order else "UNSAVED_SAMPLE",
        "statusLabel": "已保存开发合同草稿" if order else "待以正式销售身份保存",
        "contract": contract, "source": {"id": source.pk, "version": source.source_version, "rowCount": 71, "contentHash": source.content_hash},
        "order": None if not order else {"id": order.pk, "orderNo": order.order_no, "status": order.status, "statusLabel": order.get_status_display(), "version": order.version},
        "authorization": {"requiredAction": action, "decision": authorization, "actorReadiness": actor, "canSave": authorization["allowed"] and actor["ready"], "blockers": blockers},
        "navigation": {"thisPage": f"/sales/orders?mode=development-contract&sourceRecord={source.pk}", "salesOrders": "/sales/orders", "engineeringSource": f"/pde/engineering-calculations?page=input&sourceRecord={source.pk}&engineeringVersion={source.source_version}"},
        "strictFacts": {"factSource": "EngineeringSourceRecord + SalesOrder/SalesOrderItem + formal authorization", "sourceRecordId": source.pk,
            "sourceVersion": source.source_version, "sourceRowCount": 71, "mappedSourceRowCount": sum(len(value) for value in groups.values()),
            "commercialLineCount": 4, "salesOrderCount": 1 if order else 0, "businessWriteCount": 0, "planningWriteCount": 0},
    }


def _assert_b_database():
    actual = Path(settings.DATABASES["default"]["NAME"]).resolve()
    if actual != EXPECTED_DATABASE.resolve() or os.environ.get("PCE_DATABASE_IDENTITY") != "PDE-OPERABLE-ACCEPTANCE-20260912" or os.environ.get("PCE_NON_PRODUCTION_ACCEPTANCE") != "1":
        raise SalesBusinessError("DEVELOPMENT_CONTRACT_DATABASE_BLOCKED", "只允许在指定非生产B库保存开发合同样本。", 403)


def _ensure_sample_masters(user, source_record_id):
    unit_ids, created_units, created_materials = {}, [], []
    for code in ("扇", "套", "块"):
        unit = UnitOfMeasure.objects.filter(company_id=user.company_id, code=code, is_active=True).first()
        if not unit:
            unit = UnitOfMeasure(company_id=user.company_id, code=code, name=code, symbol=code, dimension="count", decimal_places=4)
            unit.full_clean(); unit.save(); created_units.append(unit.pk)
        unit_ids[code] = unit.pk
    for definition in LINE_DEFINITIONS:
        material, created = Material.objects.get_or_create(company_id=user.company_id, code=f"DEV-SC-{definition['code']}", defaults={
            "name": definition["name"], "specification": f"[DEVELOPMENT_ONLY] {SAMPLE_CONTRACT_NO}", "unit": definition["unit"],
            "unit_status": "confirmed", "base_uom_id": unit_ids[definition["unit"]], "material_type": "finished", "price": 0,
            "is_purchased": False, "is_produced": False, "created_by": user.pk,
        })
        if not created and (material.specification != f"[DEVELOPMENT_ONLY] {SAMPLE_CONTRACT_NO}" or material.base_uom_id != unit_ids[definition["unit"]]):
            raise SalesBusinessError("DEVELOPMENT_SAMPLE_MATERIAL_CONFLICT", f"过渡产品编码{material.code}已被其它用途占用。", 409)
        material.full_clean()
        if created: created_materials.append(material.pk)
    if created_units or created_materials:
        OrganizationOperatingAuditRecord.objects.create(action_code="sales.development_contract.sample_master.create", actor=user,
            organization_id=user.company_id, target_type="DevelopmentContractSampleMaster", target_id=source_record_id,
            target_label=SAMPLE_CONTRACT_NO, reason="用户授权的非生产开发合同样本过渡产品/单位",
            before_snapshot={"units": [], "materials": []}, after_snapshot={"units": created_units, "materials": created_materials, "priceMasterWrites": 0})
    return unit_ids, {definition["code"]: Material.objects.get(company_id=user.company_id, code=f"DEV-SC-{definition['code']}") for definition in LINE_DEFINITIONS}


def _normalized_payload(payload, groups):
    defaults = _default_contract(groups)
    allowed_header = ("quoteValidUntil", "customerRequiredDate", "committedDeliveryDate", "supplierContact", "customerContact", "deliveryAddressPlaceholder", "transportInstallation")
    contract = {**defaults, **{key: payload[key] for key in allowed_header if key in payload}}
    contract.update(calculate_quote(payload.get("lines") or defaults["lines"]))
    for expected, actual in zip(LINE_DEFINITIONS, contract["lines"]):
        if str(actual.get("quantity")) != expected["quantity"] or actual.get("unit") != expected["unit"] or actual.get("sourceRowIds") != defaults["lines"][[row["code"] for row in LINE_DEFINITIONS].index(expected["code"])]["sourceRowIds"]:
            raise SalesBusinessError("DEVELOPMENT_CONTRACT_MAPPING_FIXED", "本样本商业数量、单位和71行来源映射必须保持用户已授权值。", 409)
    return contract


@transaction.atomic
def save_development_contract(*, user, source_record_id, payload, idempotency_key):
    _assert_b_database()
    source, groups = _source_and_groups(user.company_id, source_record_id)
    current = SalesOrder.objects.select_for_update().filter(company_id=user.company_id, contract_reference=SAMPLE_CONTRACT_NO).first()
    action = "sales.order.update" if current else "sales.order.create"
    decision = _authorization(user, action)
    if not decision["allowed"]: raise SalesBusinessError(decision["decisionCode"], decision["reason"], 403)
    actor_readiness = _actor_readiness(user, action)
    if not actor_readiness["ready"]:
        raise SalesBusinessError(actor_readiness["code"], actor_readiness["reason"], 403)
    actor = actor_readiness["actor"]
    contract = _normalized_payload(payload, groups)
    key = str(idempotency_key or "").strip()
    if not key: raise SalesBusinessError("IDEMPOTENCY_KEY_REQUIRED", "保存必须提供幂等键。")
    request_hash = hashlib.sha256(json.dumps(contract, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest().upper()
    identity, _ = ExternalIdentity.objects.select_for_update().get_or_create(organization_id=user.company_id, source_system=SOURCE_SYSTEM,
        source_type=SOURCE_TYPE, source_object_type=SOURCE_OBJECT_TYPE, external_id=f"EngineeringSourceRecord:{source.pk}",
        defaults={"target_entity_type": "SalesOrder", "mapping_status": "REVIEW", "source_fingerprint": source.content_hash,
            "audit_metadata": {"contractNo": SAMPLE_CONTRACT_NO, "sourceVersion": source.source_version}})
    write_request, created = MasterDataWriteRequest.objects.select_for_update().get_or_create(organization_id=user.company_id,
        action_code=ACTION_CODE, entity_type="SalesOrder", idempotency_key=key,
        defaults={"request_hash": request_hash, "source_identity": identity, "audit_metadata": {"contractNo": SAMPLE_CONTRACT_NO}})
    if not created:
        if write_request.request_hash != request_hash: raise SalesBusinessError("IDEMPOTENCY_CONFLICT", "同一幂等键已用于不同合同内容。", 409)
        if write_request.status == MasterDataWriteRequest.Status.COMMITTED:
            return build_development_contract_preview(company_id=user.company_id, source_record_id=source.pk, user=user), True
    unit_ids, materials = _ensure_sample_masters(user, source.pk)
    delivery = {"developmentContract": {key: value for key, value in contract.items() if key not in ("lines", "totals")},
        "committedDeliveryDate": contract["committedDeliveryDate"], "quoteValidUntil": contract["quoteValidUntil"],
        "paymentNodes": contract["paymentNodes"], "developmentOnly": True, "externalCommunicationAllowed": False,
        "sourceRecordId": source.pk, "sourceVersion": source.source_version}
    if not current:
        items = []
        for definition, line in zip(LINE_DEFINITIONS, contract["lines"]):
            items.append({"lineNo": len(items)+1, "materialId": materials[definition["code"]].pk, "uomId": unit_ids[definition["unit"]],
                "quantity": definition["quantity"], "unitPrice": line["unitPrice"], "taxRate": line["taxRate"], "priceTaxMode": "tax_inclusive",
                "requiredDate": definition["requiredDate"], "externalLineNo": definition["code"], "customerProductName": definition["name"],
                "engineeringMode": "ORDER_ENGINEERED", "engineeringRequirements": f"开发合同样本；来源{source.pk}/{source.source_version}；关联{len(groups[definition['code']])}行",
                "engineeringAttributes": [{"sequence": index, "rawSource": f"EngineeringSourceRecord:{source.pk}", "rawSheet": row.get("sourceSheet") or "",
                    "externalSource": row["id"], "rawField": "source_line_identity", "rawValue": row, "canonicalField": "external_source_line_identity",
                    "normalizedValue": row["id"], "valueType": "code", "sourceType": "ENGINEERING_INPUT"} for index, row in enumerate(groups[definition["code"]], 1)]})
        owner = Employee.objects.filter(department_ref__company_id=user.company_id, employee_no="EMP103", status="active").first()
        customer = Customer.objects.filter(company_id=user.company_id, code="DLR-S07-002", is_active=True).first()
        department = Department.objects.filter(company_id=user.company_id, code="YXB", is_active=True).first()
        if not owner or not customer or not department: raise SalesBusinessError("DEVELOPMENT_CONTRACT_MASTER_MISSING", "客户、营销部或业务员正式引用缺失。", 409)
        current, _, audit = create_order(user=user, authorization=decision, business_purpose=SalesOrder.BusinessPurpose.DEVELOPMENT_VALIDATION, payload={"customerId": customer.pk, "departmentId": department.pk,
            "salesOwnerId": owner.pk, "orderDate": contract["orderDate"], "requiredDate": contract["customerRequiredDate"], "currency": "CNY",
            "orderType": "project", "orderSource": "import", "projectReference": contract["projectName"], "contractReference": SAMPLE_CONTRACT_NO,
            "externalSourceNo": contract["sourceOrderNo"], "deliveryInformation": delivery, "acceptanceMarker": "DEVELOPMENT_ONLY",
            "remark": "非生产开发联调样本；不是已签真实合同；禁止外发、收款、开票及发货。", "items": items,
            "sourceIntakeFacts": {"sourceRecordId": source.pk, "sourceVersion": source.source_version, "mappingCounts": {key: len(value) for key, value in groups.items()}}})
    else:
        current, audit = update_order(user=user, order_id=current.pk, authorization=decision, payload={"version": current.version,
            "requiredDate": contract["customerRequiredDate"], "deliveryInformation": delivery, "reason": "保存非生产开发合同样本"})
        by_code = {item.external_line_no: item for item in current.items.all()}
        if set(by_code) != {row["code"] for row in LINE_DEFINITIONS}: raise SalesBusinessError("DEVELOPMENT_CONTRACT_ORDER_SHAPE_CHANGED", "已存订单明细身份与4条样本行不一致。", 409)
        for definition, line in zip(LINE_DEFINITIONS, contract["lines"]):
            current, _, audit = update_order_item(user=user, order_id=current.pk, item_id=by_code[definition["code"]].pk, authorization=decision,
                payload={"version": current.version, "unitPrice": line["unitPrice"], "taxRate": line["taxRate"], "priceTaxMode": "tax_inclusive",
                    "requiredDate": definition["requiredDate"], "reason": "保存非生产开发合同样本报价"})
    identity.target_entity_type = "SalesOrder"; identity.target_entity_id = str(current.pk); identity.mapping_status = ExternalIdentity.MappingStatus.MATCH
    identity.source_fingerprint = source.content_hash; identity.audit_metadata = {**(identity.audit_metadata or {}), "contractNo": SAMPLE_CONTRACT_NO,
        "orderId": current.pk, "orderNo": current.order_no, "requestHash": request_hash, "actor": actor}; identity.save()
    write_request.status = MasterDataWriteRequest.Status.COMMITTED; write_request.target_entity_id = str(current.pk)
    write_request.result = {"salesOrderId": current.pk, "orderNo": current.order_no, "auditId": audit.pk}; write_request.save(update_fields=["status", "target_entity_id", "result", "updated_at"])
    return build_development_contract_preview(company_id=user.company_id, source_record_id=source.pk, user=user), False

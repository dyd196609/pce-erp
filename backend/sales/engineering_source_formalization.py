"""Read-only bridge from a governed engineering source to Sales intake.

The projection deliberately does not create or update Sales, PDE, Planning or
master-data rows.  It exposes the exact source facts and the prerequisites that
must be resolved before the existing SalesOrder service may be used.
"""

from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model

from masterdata.models import Material, UnitOfMeasure
from pde.formal_import_actor_context import (
    FormalImportActorContextError,
    resolve_formal_import_actor,
)
from pde.models import (
    EngineeringCalculationRecord,
    EngineeringMaterialRequirement,
    EngineeringOperationRequirement,
    EngineeringRuleDefinition,
    EngineeringSourceRecord,
    OrderEngineeringInstance,
    ProductDefinition,
)
from planning.models import Demand, PlanningRequirement
from pfm.models import Employee
from system.authorization import AuthorizationService
from system.models import Department

from .models import Customer, SalesOrder


SOURCE_ACTIONS = (
    "sales.order.view",
    "sales.order.create",
    "sales.order.update",
    "sales.order.confirm",
)


def _decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _authorization(user, action):
    decision = AuthorizationService.decide(
        user=user,
        action_code=action,
        organization_id=user.company_id,
        business_object={"organizationId": user.company_id},
        context={"actionType": "ENGINEERING_SOURCE_FORMALIZATION", "businessWrite": action != "sales.order.view"},
    )
    return {
        "actionCode": action,
        "allowed": decision["allowed"],
        "decisionCode": decision["decisionCode"],
        "reason": decision["reason"],
        "roleCodes": decision["roleCodes"],
        "scope": decision["scope"],
    }


def _actor_readiness(user, action):
    try:
        actor = resolve_formal_import_actor(
            user=user,
            organization_id=user.company_id,
            action_code=action,
        )
    except FormalImportActorContextError as error:
        return {"ready": False, "code": error.code, "reason": error.message}
    return {
        "ready": True,
        "code": "READY",
        "reason": "账户、员工、岗位、职责、角色、权限与组织范围均已通过正式办理人校验。",
        "actor": actor,
    }


def _known_operator_rows(company_id):
    User = get_user_model()
    rows = []
    for user in User.objects.filter(
        company_id=company_id,
        is_active=True,
    ).order_by("username"):
        actions = [_authorization(user, action) for action in SOURCE_ACTIONS]
        if user.username not in ("pce_sales_r13", "pce_plan_r12") and not any(row["allowed"] for row in actions):
            continue
        employee_id = Employee.objects.filter(user=user).values_list("id", flat=True).first()
        rows.append({
            "userId": user.pk,
            "username": user.username,
            "companyId": user.company_id,
            "employeeId": employee_id,
            "actions": actions,
            "sourceActorReadiness": _actor_readiness(user, "sales.order.create"),
            "engineeringView": _authorization(user, "production.engineering.calculation.view"),
            "engineeringExecute": _authorization(user, "production.engineering.calculation.execute"),
            "planningView": _authorization(user, "planning.view"),
        })
    return rows


def _source_row(row, unit_matches, engineering_material_matches):
    source_id = str(row.get("id") or "")
    quantity = _decimal(row.get("quantity"))
    unit = str(row.get("unit") or row.get("unitName") or "").strip()
    material_code = str(row.get("materialCode") or "").strip()
    process_code = str(row.get("materialProcessCode") or "").strip()
    return {
        "sourceRowId": source_id,
        "sourceSheet": str(row.get("sourceSheet") or row.get("sourceType") or ""),
        "sourceRow": row.get("sourceRow"),
        "sourceCellRange": f"{row.get('sourceSheet') or row.get('sourceType')}!第{row.get('sourceRow')}行",
        "space": str(row.get("space") or ""),
        "product": str(row.get("product") or row.get("productCategoryName") or ""),
        "component": str(row.get("component") or ""),
        "dimensions": {
            "length": row.get("length"), "width": row.get("width"), "thickness": row.get("thickness"),
        },
        "quantity": str(quantity) if quantity is not None else "",
        "sourceUom": unit,
        "formalUomMatches": unit_matches.get(unit, []),
        "materialCode": material_code,
        "materialProcessCode": process_code,
        "routingProcessCode": str(row.get("routingProcessCode") or ""),
        "engineeringMaterialMatches": engineering_material_matches.get(process_code, []),
        "salesMaterialStatus": "UNRESOLVED" if not material_code else "SOURCE_CODE_REQUIRES_FORMAL_MATCH",
        "edgeMode": str(row.get("edgeMode") or ""),
        "visibleCondition": str(row.get("visibleCondition") or ""),
        "processingNote": str(row.get("processingNote") or ""),
        "sourceEvidence": row.get("sourceEvidence") if isinstance(row.get("sourceEvidence"), dict) else {},
    }


def build_engineering_source_formalization_preview(*, company_id, source_record_id, user):
    source = EngineeringSourceRecord.objects.filter(pk=source_record_id, company_id=company_id).first()
    if not source:
        raise ValueError("ENGINEERING_SOURCE_NOT_FOUND")
    payload = source.source_payload if isinstance(source.source_payload, dict) else {}
    raw_rows = payload.get("engineeringRows") if isinstance(payload.get("engineeringRows"), list) else []
    business = payload.get("businessOrderReference") if isinstance(payload.get("businessOrderReference"), dict) else {}

    source_units = sorted({str(row.get("unit") or row.get("unitName") or "").strip() for row in raw_rows if str(row.get("unit") or row.get("unitName") or "").strip()})
    units = defaultdict(list)
    for row in UnitOfMeasure.objects.filter(company_id=company_id, is_active=True).order_by("code", "pk"):
        if row.code in source_units or row.name in source_units or row.symbol in source_units:
            value = {"id": row.pk, "code": row.code, "name": row.name, "symbol": row.symbol}
            for key in {row.code, row.name, row.symbol} - {""}:
                units[key].append(value)

    process_codes = sorted({str(row.get("materialProcessCode") or "").strip() for row in raw_rows if str(row.get("materialProcessCode") or "").strip()})
    engineering_materials = defaultdict(list)
    for row in Material.objects.filter(company_id=company_id, is_active=True, code__in=process_codes).order_by("code", "pk"):
        engineering_materials[row.code].append({
            "id": row.pk, "code": row.code, "name": row.name,
            "specification": row.specification, "baseUomId": row.base_uom_id,
        })

    rows = [_source_row(row, units, engineering_materials) for row in raw_rows]
    summary_groups = defaultdict(lambda: {"rowCount": 0, "sourceQuantity": Decimal("0"), "sourceRowIds": []})
    for row in rows:
        key = (row["product"] or "来源未提供", row["component"] or "来源未提供", row["sourceUom"] or "来源未提供")
        group = summary_groups[key]
        group["rowCount"] += 1
        group["sourceRowIds"].append(row["sourceRowId"])
        quantity = _decimal(row["quantity"])
        if quantity is not None:
            group["sourceQuantity"] += quantity
    source_groups = [{
        "product": key[0], "component": key[1], "sourceUom": key[2],
        "rowCount": value["rowCount"], "sourceQuantity": str(value["sourceQuantity"]),
        "sourceRowIds": value["sourceRowIds"],
        "businessMeaning": "工程来源分组，仅用于人工核对；不是销售行或销售数量。",
    } for key, value in sorted(summary_groups.items())]

    source_order_no = str(business.get("sourceOrderNo") or "").strip()
    customer_name = str(business.get("customerName") or "").strip()
    project_name = str(business.get("projectName") or "").strip()
    matching_orders = SalesOrder.objects.select_related("customer", "department").filter(company_id=company_id)
    matching_orders = matching_orders.filter(external_source_no=source_order_no) if source_order_no else matching_orders.none()
    matching_order_rows = [{
        "id": row.pk, "orderNo": row.order_no, "status": row.status,
        "statusLabel": row.get_status_display(), "externalSourceNo": row.external_source_no,
        "customerId": row.customer_id, "customerName": row.customer.name,
        "projectReference": row.project_reference, "departmentId": row.department_id,
    } for row in matching_orders.order_by("pk")]
    customer_rows = list(Customer.objects.filter(company_id=company_id, is_active=True, name=customer_name).values("id", "code", "name")) if customer_name else []
    department_rows = list(Department.objects.filter(company_id=company_id, is_active=True).order_by("code", "pk").values("id", "code", "name"))
    released_rules = EngineeringRuleDefinition.objects.filter(company_id=company_id, status="released")

    current_actions = [_authorization(user, action) for action in SOURCE_ACTIONS]
    blockers = [
        {"code": "COMMERCIAL_LINES_UNCONFIRMED", "message": "71 条工程来源如何组成真实销售明细尚未确认；工程行数和工程数量不能直接当销售行与销售数量。"},
        {"code": "SALES_MATERIAL_UNRESOLVED", "message": "全部来源行的正式销售物料编码为空；两个加工物料编码只能作为工程候选，不能自动替代客户购买产品。"},
        {"code": "SALES_DATES_UNCONFIRMED", "message": "订单日期、客户要求交期及企业承诺交期均未由本来源提供。"},
        {"code": "PRICE_TAX_UNCONFIRMED", "message": "销售单价、币种、含税/未税口径及税率未提供；现有 SalesOrderItem 仅有单价字段，没有销售税率快照字段。"},
        {"code": "FORMAL_RULES_INCOMPLETE", "message": f"当前组织仅有 {released_rules.count()} 条已发布正式工程规则，不能把 388 项页面预览复制成正式核算记录。"},
    ]
    unresolved_units = [unit for unit in source_units if not units.get(unit)]
    if unresolved_units:
        blockers.append({"code": "SOURCE_UOM_UNRESOLVED", "message": f"来源单位 { '、'.join(unresolved_units) } 没有同组织启用的正式单位记录。"})
    actor_readiness = _actor_readiness(user, "sales.order.create")
    if not actor_readiness["ready"]:
        blockers.append({"code": actor_readiness["code"], "message": actor_readiness["reason"]})
    if not all(next((row["allowed"] for row in current_actions if row["actionCode"] == action), False) for action in ("sales.order.view", "sales.order.create", "sales.order.confirm")):
        blockers.append({"code": "SALES_ACTION_AUTHORIZATION_INCOMPLETE", "message": "当前登录身份未同时具备查看、创建和确认来源资格所需的销售动作权限。"})

    common = {
        "factSource": "EngineeringSourceRecord + formal master data + formal authorization service",
        "sourceRecordId": source.pk,
        "sourceVersion": source.source_version,
        "sourceContentHash": source.content_hash,
        "businessWriteCount": 0,
        "planningWriteCount": 0,
    }
    return {
        "previewCode": "ENGINEERING_SOURCE_SALES_FORMALIZATION_DO1",
        "readOnly": True,
        "formalApplicationAllowed": False,
        "statusLabel": "待商业事实与正式办理身份",
        "source": {
            "id": source.pk, "sourceNo": source.source_no, "sourceName": source.source_name,
            "sourceType": source.source_type, "sourceVersion": source.source_version,
            "contentHash": source.content_hash, "status": source.status,
            "rowCount": len(rows), "registeredScope": payload.get("registeredSourceScope") or {},
        },
        "businessOrderReference": {
            "sourceOrderNo": source_order_no, "customerName": customer_name,
            "projectName": project_name, "sourceEvidence": str(business.get("sourceEvidence") or ""),
            "sameWorkbookOrderConfirmed": bool(business.get("sameWorkbookOrderConfirmed")),
            "matchedSalesOrderId": business.get("matchedSalesOrderId"),
        },
        "matchingSalesOrders": matching_order_rows,
        "customerCandidates": customer_rows,
        "departmentCandidates": department_rows,
        "sourceGroups": source_groups,
        "sourceRows": rows,
        "unitResolution": [{"sourceUom": unit, "matches": units.get(unit, []), "resolved": len(units.get(unit, [])) == 1} for unit in source_units],
        "engineeringMaterialCandidates": [{"sourceCode": code, "matches": engineering_materials.get(code, []), "salesUseConfirmed": False} for code in process_codes],
        "productDefinitionCandidateCount": ProductDefinition.objects.filter(company_id=company_id, is_active=True).count(),
        "formalEngineering": {
            "releasedRuleCount": released_rules.count(),
            "releasedRules": list(released_rules.order_by("rule_code", "pk").values("id", "rule_code", "rule_name", "rule_kind")),
            "orderEngineeringInstanceCount": OrderEngineeringInstance.objects.filter(source_record=source).count(),
            "calculationCount": EngineeringCalculationRecord.objects.filter(source_record=source).count(),
            "materialRequirementCount": EngineeringMaterialRequirement.objects.filter(calculation__source_record=source).count(),
            "operationRequirementCount": EngineeringOperationRequirement.objects.filter(calculation__source_record=source).count(),
        },
        "planning": {
            "demandCount": Demand.objects.filter(sales_order_item__sales_order__in=matching_orders).count(),
            "planningRequirementCount": PlanningRequirement.objects.filter(demand__sales_order_item__sales_order__in=matching_orders).count(),
            "statusLabel": "未形成订单需求；本轮未生成 Demand/MPS/MRP/计划任务。",
        },
        "currentUser": {
            "userId": user.pk, "username": user.username, "companyId": user.company_id,
            "employeeId": Employee.objects.filter(user=user).values_list("id", flat=True).first(), "actions": current_actions,
            "sourceActorReadiness": actor_readiness,
        },
        "knownOperatorChecks": _known_operator_rows(company_id),
        "blockers": blockers,
        "questions": [
            {"code": "SALES_LINE_STRUCTURE", "question": "请按真实合同/报价说明销售明细：每行购买的正式产品、对应来源行稳定身份、商业数量和单位；也可直接提供原报价/合同明细供核对。"},
            {"code": "ORDER_HEADER", "question": "请确认订单日期、客户要求交期、企业承诺交期，以及应归属的销售部门。"},
            {"code": "PRICE_TAX", "question": "请确认每条销售行的单价、币种、含税或未税口径及税率；当前销售模型尚无税率快照字段，确认后才能决定是否需要受控扩展。"},
        ],
        "navigation": {
            "salesOrders": "/sales/orders",
            "engineeringSource": f"/pde/engineering-calculations?page=input&sourceRecord={source.pk}&engineeringVersion={source.source_version}",
            "thisPage": f"/sales/orders?mode=engineering-source-formalization&sourceRecord={source.pk}",
        },
        "apiFacts": common, "pageFacts": common, "diagnosticFacts": common, "strictFacts": common,
    }

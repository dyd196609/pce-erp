"""Read-only engineering input choices and operation-plan projection.

The module only joins existing formal facts. It does not import workbook lists,
create employees, publish plans, or introduce a second planning write path.
"""

from datetime import date

from django.db.models import Q

from masterdata.models import UnitOfMeasure
from pfm.formal_employee import formal_employee_queryset
from pfm.models import Employee
from planning.models import ProductionPlan
from system.authorization import scope_employee_queryset

from .manufacturing_structure_service import ManufacturingStructureError, ManufacturingStructureService
from .models import (
    EngineeringBreakdownOption, OrderEngineeringInstance, ProductCategory,
    ProductDefinition,
)
from .engineering_condition_options import normalize_visible_condition, visible_condition_options


RESPONSIBILITY_ROLES = {
    "salesperson": {
        "label": "业务员",
        "codes": ("RESP_SALES_CUSTOMER_001", "RESP_SALES_ORDER_002"),
    },
    "designer": {
        "label": "设计师",
        "codes": ("RESP_TECH_DESIGN_004", "RESP_TECH_VERIFY_005"),
    },
    "breakdownOwner": {
        "label": "拆单负责人",
        "codes": ("RESP_TECH_PROCESS_001", "RESP_TECH_CHANGE_003"),
    },
}


def _effective(queryset, *, start="effective_from", end="effective_to"):
    today = date.today()
    return queryset.filter(
        Q(**{f"{start}__isnull": True}) | Q(**{f"{start}__lte": today}),
        Q(**{f"{end}__isnull": True}) | Q(**{f"{end}__gte": today}),
    )


def _employee_queryset(user, role):
    codes = RESPONSIBILITY_ROLES[role]["codes"]
    queryset = formal_employee_queryset(
        Employee.objects.select_related("department_ref", "position_ref"),
        company_id=user.company_id,
    ).filter(
        position_ref__responsibility_mappings__active=True,
        position_ref__responsibility_mappings__responsibility__code__in=codes,
        position_ref__responsibility_mappings__responsibility__status="ACTIVE",
        position_ref__responsibility_mappings__responsibility__is_active=True,
    )
    return scope_employee_queryset(queryset, user).distinct().order_by("employee_no", "pk")


def _employee_row(employee):
    department_name = employee.department_ref.name if employee.department_ref_id else (employee.department_name or "")
    position_name = employee.position_ref.name if employee.position_ref_id else (employee.position or "")
    return {
        "employeeId": employee.pk,
        "employeeNo": employee.employee_no,
        "fullName": employee.full_name,
        "label": f"{employee.full_name}（{employee.employee_no}）",
        "departmentName": department_name,
        "positionName": position_name,
        "statusLabel": employee.get_status_display(),
        "selectable": employee.status == "active",
    }


def _option_row(row):
    return {
        "id": row.pk,
        "optionType": row.option_type,
        "optionTypeLabel": row.get_option_type_display(),
        "code": row.code,
        "name": row.name,
        "label": row.name,
        "statusLabel": "启用" if row.is_active else "已停用",
        "selectable": row.is_active,
        "sourceReference": row.source_reference,
    }


def _active_engineering_options(user):
    rows = _effective(EngineeringBreakdownOption.objects.filter(
        company_id=user.company_id, is_active=True,
    )).order_by("option_type", "code", "pk")
    grouped = {key: [] for key, _label in EngineeringBreakdownOption.OptionType.choices}
    for row in rows:
        grouped[row.option_type].append(_option_row(row))
    return grouped


def build_engineering_input_options(user):
    categories = _effective(ProductCategory.objects.filter(
        company_id=user.company_id, is_active=True,
    )).order_by("code", "pk")
    products = _effective(ProductDefinition.objects.filter(
        company_id=user.company_id, is_active=True,
    )).order_by("product_code", "pk")
    units = UnitOfMeasure.objects.filter(
        company_id=user.company_id, is_active=True,
    ).order_by("code", "pk")
    employee_roles = {}
    governed_options = _active_engineering_options(user)
    for role, definition in RESPONSIBILITY_ROLES.items():
        options = [_employee_row(row) for row in _employee_queryset(user, role)]
        employee_roles[role] = {
            "label": definition["label"],
            "responsibilityCodes": list(definition["codes"]),
            "options": options,
            "statusLabel": "可选择" if options else "暂无符合正式岗位职责且在职的员工",
        }
    return {
        "source": "server-formal-master-data",
        "productCategories": [{
            "id": row.pk, "code": row.code, "name": row.name,
            "label": f"{row.name}（{row.code}）", "statusLabel": "启用",
        } for row in categories],
        "products": [{
            "id": row.pk, "code": row.product_code, "name": row.product_name,
            "label": f"{row.product_name}（{row.product_code}）", "statusLabel": "启用",
        } for row in products],
        "units": [{
            "id": row.pk, "code": row.code, "name": row.name,
            "label": f"{row.name}（{row.code}）", "statusLabel": "启用",
        } for row in units],
        "employeeRoles": employee_roles,
        "doorOpeningDirections": governed_options[EngineeringBreakdownOption.OptionType.DOOR_OPENING_DIRECTION],
        "lineStyles": governed_options[EngineeringBreakdownOption.OptionType.LINE_STYLE],
        "edgeMethods": governed_options[EngineeringBreakdownOption.OptionType.EDGE_METHOD],
        "visibleConditions": visible_condition_options(),
        "packagingMethods": governed_options[EngineeringBreakdownOption.OptionType.PACKAGING_METHOD],
        "packagingMethodState": {
            "statusLabel": "可维护，尚无启用选项" if not governed_options[EngineeringBreakdownOption.OptionType.PACKAGING_METHOD] else "可选择",
            "maintenanceEntry": "/foundation/master-data/engineering-breakdown-options?view=maintain&workspace=engineering-breakdown",
            "sourceWorkbookValuesImported": False,
        },
        "maintenanceEntries": {
            "employees": "/foundation/pfm/employees",
            "productCategories": "/foundation/master-data/product-categories",
            "products": "/foundation/master-data/products",
            "units": "/foundation/master-data/units",
            "operations": "/foundation/master-data/operations",
            "routings": "/foundation/master-data/routings",
            "engineeringBreakdownOptions": "/foundation/master-data/engineering-breakdown-options?workspace=engineering-breakdown",
        },
    }


def normalize_draft_context(user, payload):
    assignments = payload.get("responsibilityAssignments")
    assignments = assignments if isinstance(assignments, dict) else {}
    normalized = {}
    for role, definition in RESPONSIBILITY_ROLES.items():
        value = assignments.get(role)
        value = value if isinstance(value, dict) else {}
        employee_id = value.get("employeeId")
        if employee_id in (None, ""):
            normalized[role] = None
            continue
        try:
            employee_id = int(employee_id)
        except (TypeError, ValueError):
            raise ValueError(f"ENGINEERING_RESPONSIBILITY_EMPLOYEE_INVALID:{role}")
        eligible = _employee_queryset(user, role).filter(pk=employee_id).first()
        if not eligible:
            employee = Employee.objects.filter(pk=employee_id).first()
            if not employee:
                reason = "NOT_FOUND"
            elif employee.status != "active":
                reason = "INACTIVE"
            elif not employee.position_ref_id:
                reason = "FORMAL_POSITION_REQUIRED"
            else:
                reason = "ROLE_OR_SCOPE_MISMATCH"
            raise ValueError(f"ENGINEERING_RESPONSIBILITY_EMPLOYEE_NOT_ELIGIBLE:{role}:{reason}")
        normalized[role] = {**_employee_row(eligible), "roleLabel": definition["label"]}

    packaging = payload.get("packagingMethod")
    packaging = packaging if isinstance(packaging, dict) else {}
    packaging_id = packaging.get("id")
    packaging_row = None
    if packaging_id not in (None, ""):
        try:
            packaging_id = int(packaging_id)
        except (TypeError, ValueError):
            raise ValueError("ENGINEERING_PACKAGING_METHOD_INVALID")
        packaging_row = _effective(EngineeringBreakdownOption.objects.filter(
            pk=packaging_id, company_id=user.company_id, is_active=True,
            option_type=EngineeringBreakdownOption.OptionType.PACKAGING_METHOD,
        )).first()
        if not packaging_row:
            raise ValueError("ENGINEERING_PACKAGING_METHOD_INVALID")
    return {
        "responsibilityAssignments": normalized,
        "packagingMethod": {
            "id": packaging_row.pk if packaging_row else None,
            "code": packaging_row.code if packaging_row else "",
            "name": packaging_row.name if packaging_row else "",
            "statusLabel": "已选择" if packaging_row else "未维护",
            "sourceWorkbookValueImported": False,
        },
    }


def normalize_confirmed_business_facts(user, payload):
    """Persist user-confirmed facts without turning cross-company people into operative assignments."""
    raw = payload.get("confirmedResponsibilityFacts")
    raw = raw if isinstance(raw, dict) else {}
    facts = {}
    for role, definition in RESPONSIBILITY_ROLES.items():
        value = raw.get(role)
        value = value if isinstance(value, dict) else {}
        employee_id = value.get("employeeId")
        if employee_id in (None, ""):
            continue
        employee = formal_employee_queryset(
            Employee.objects.select_related("position_ref", "department_ref")
        ).filter(pk=employee_id).first()
        if not employee:
            raise ValueError(f"ENGINEERING_CONFIRMED_EMPLOYEE_NOT_FORMAL:{role}")
        eligible_role = Employee.objects.filter(
            pk=employee.pk,
            position_ref__responsibility_mappings__active=True,
            position_ref__responsibility_mappings__responsibility__code__in=definition["codes"],
            position_ref__responsibility_mappings__responsibility__status="ACTIVE",
            position_ref__responsibility_mappings__responsibility__is_active=True,
        ).exists()
        if not eligible_role:
            raise ValueError(f"ENGINEERING_CONFIRMED_EMPLOYEE_ROLE_MISMATCH:{role}")
        same_company = employee.position_ref.company_id == user.company_id
        facts[role] = {
            **_employee_row(employee),
            "roleLabel": definition["label"],
            "employeeCompanyId": employee.position_ref.company_id,
            "referenceStatus": "OPERATIVE_REFERENCE_AVAILABLE" if same_company else "CONFIRMED_CROSS_COMPANY_NOT_OPERATIVE",
            "statusLabel": "可形成正式责任人引用" if same_company else "人选已确认；与当前来源企业作用域不一致，尚未形成操作性引用",
        }
    order = payload.get("businessOrderReference")
    order = order if isinstance(order, dict) else {}
    order_no = str(order.get("sourceOrderNo") or "").strip()[:100]
    return {
        "confirmedResponsibilityFacts": facts,
        "businessOrderReference": {
            "sourceOrderNo": order_no,
            "customerName": str(order.get("customerName") or "").strip()[:200],
            "projectName": str(order.get("projectName") or "").strip()[:200],
            "sourceEvidence": str(order.get("sourceEvidence") or "").strip()[:500],
            "sameWorkbookOrderConfirmed": bool(order.get("sameWorkbookOrderConfirmed")),
            "matchedSalesOrderId": None,
            "stableOrderLinkStatus": "SOURCE_ORDER_NOT_ESTABLISHED",
            "statusLabel": "同一来源订单已确认；正式销售订单尚未建立或未唯一匹配",
        },
    }


def normalize_draft_row_references(user, item, index):
    category_id = item.get("productCategoryId")
    if category_id not in (None, ""):
        category = _effective(ProductCategory.objects.filter(
            pk=category_id, company_id=user.company_id, is_active=True,
        )).first()
        if not category:
            raise ValueError(f"ENGINEERING_PRODUCT_CATEGORY_INVALID:{index}")
        item["productCategoryId"] = category.pk
        item["productCategoryCode"] = category.code
        item["productCategoryName"] = category.name
    unit_id = item.get("unitId")
    if unit_id not in (None, ""):
        unit = UnitOfMeasure.objects.filter(
            pk=unit_id, company_id=user.company_id, is_active=True,
        ).first()
        if not unit:
            raise ValueError(f"ENGINEERING_UOM_INVALID:{index}")
        item["unitId"] = unit.pk
        item["unit"] = unit.code
        item["unitName"] = unit.name
    option_fields = {
        "doorOpeningDirectionOptionId": EngineeringBreakdownOption.OptionType.DOOR_OPENING_DIRECTION,
        "lineStyleOptionId": EngineeringBreakdownOption.OptionType.LINE_STYLE,
        "edgeMethodOptionId": EngineeringBreakdownOption.OptionType.EDGE_METHOD,
    }
    for field, option_type in option_fields.items():
        option_id = item.get(field)
        if option_id in (None, ""):
            continue
        try:
            option_id = int(option_id)
        except (TypeError, ValueError):
            raise ValueError(f"ENGINEERING_OPTION_INVALID:{index}:{field}")
        option = _effective(EngineeringBreakdownOption.objects.filter(
            pk=option_id, company_id=user.company_id, is_active=True,
            option_type=option_type,
        )).first()
        if not option:
            raise ValueError(f"ENGINEERING_OPTION_INVALID:{index}:{field}")
        item[field] = option.pk
        item[field.removesuffix("Id") + "Code"] = option.code
        item[field.removesuffix("Id") + "Name"] = option.name
        if field == "edgeMethodOptionId":
            item.setdefault("edgeModeOriginal", item.get("edgeMode") or "")
            item["edgeMode"] = option.name
    visible = normalize_visible_condition(
        code=item.get("visibleConditionCode"), value=item.get("visibleCondition"),
    )
    if visible:
        item["visibleConditionCode"] = visible["code"]
        item["visibleCondition"] = visible["name"]
        item["visibleConditionSnapshot"] = visible
    return item


def build_production_plan_projection(company_id, orders):
    instance_ids = [row.get("orderEngineeringInstanceId") for row in orders if row.get("orderEngineeringInstanceId")]
    instances = {
        row.pk: row for row in OrderEngineeringInstance.objects.filter(
            company_id=company_id, pk__in=instance_ids,
        ).select_related("source_record", "sales_order_item", "baseline_product_version")
    }
    sales_item_ids = [row.get("salesOrderItemId") for row in orders if row.get("salesOrderItemId")]
    plans = {
        row.planning_requirement.demand.sales_order_item_id: row
        for row in ProductionPlan.objects.filter(
            planning_requirement__demand__sales_order_item_id__in=sales_item_ids,
        ).select_related(
            "planning_requirement__demand", "planning_requirement__demand__product_version",
        )
    }
    result = {}
    for order in orders:
        sales_item_id = order.get("salesOrderItemId")
        instance = instances.get(order.get("orderEngineeringInstanceId"))
        projection = {
            "salesOrderItemId": sales_item_id,
            "orderEngineeringInstanceId": order.get("orderEngineeringInstanceId"),
            "engineeringVersion": order.get("sourceVersion"),
            "planId": None,
            "planNo": None,
            "planBatch": None,
            "routingVersionId": None,
            "routingVersion": None,
            "statusLabel": "未排计划",
            "rows": [],
            "readSource": "planning.ProductionPlan + pde.RoutingStep",
            "businessWriteSideEffectCount": 0,
        }
        if not instance:
            projection["statusLabel"] = "工程实例未建立，无法读取工序计划"
            result[str(sales_item_id)] = projection
            continue
        try:
            resolved = ManufacturingStructureService.resolve_effective_routing(instance)
        except ManufacturingStructureError as exc:
            projection["statusLabel"] = "适用工艺路线未建立" if exc.code == "NO_EFFECTIVE_ROUTING" else "适用工艺路线无法唯一确定"
            projection["detail"] = exc.message
            result[str(sales_item_id)] = projection
            continue
        version = resolved["routing_version"]
        plan = plans.get(sales_item_id)
        projection.update({
            "routingVersionId": version.pk,
            "routingVersion": version.routing_version,
            "routingCode": resolved["routing"].routing_code,
            "resolvedScopeLabel": {
                "ORDER_ENGINEERING": "订单工程",
                "PRODUCT_DEFINITION": "产品",
                "PRODUCT_CATEGORY": "产品分类",
            }.get(resolved["resolved_scope"], "正式工艺路线"),
        })
        row_status = "未排计划"
        if plan:
            demand = plan.planning_requirement.demand
            mismatch = bool(
                demand.product_version_id and instance.baseline_product_version_id
                and demand.product_version_id != instance.baseline_product_version_id
            )
            projection.update({
                "planId": plan.pk,
                "planNo": plan.plan_no,
                "planBatch": plan.run_batch or plan.plan_no,
                "planStatusLabel": plan.get_status_display(),
            })
            if mismatch:
                projection["statusLabel"] = "生产计划与当前工程版本不匹配"
                row_status = projection["statusLabel"]
            else:
                projection["statusLabel"] = "计划已建立，工序计划日期未维护"
                row_status = "计划日期未维护"
        projection["rows"] = [{
            "key": f"{instance.pk}:{version.pk}:{step.applies_to_item_id or 'PRODUCT'}:{step.pk}",
            "sequence": step.sequence,
            "operationId": step.operation_id,
            "operationCode": step.operation.code,
            "operationName": step.operation.name,
            "objectId": step.applies_to_item_id,
            "objectLabel": step.applies_to_item.material.name if step.applies_to_item_id else "整项产品",
            "planBatch": projection["planBatch"],
            "plannedStartDate": None,
            "plannedFinishDate": None,
            "statusLabel": row_status,
        } for step in version.steps.select_related(
            "operation", "applies_to_item__material",
        ).filter(is_active=True).order_by("sequence", "pk")]
        result[str(sales_item_id)] = projection
    return result

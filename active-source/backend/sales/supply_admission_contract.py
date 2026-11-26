"""The only registered action contract for order-line supply confirmation."""

PROCESS_CODE = "ORDER_LINE_SUPPLY_ADMISSION_CONFIRMATION"
NODE_CODE = "SUPPLY_ADMISSION_CONFIRM"
ACTION_CODE = "sales.order_item.supply_admission.confirm"
MODULE_CODE = "order-line-supply-admission"
ROLE_CODE = "order_line_supply_admission_confirmer"
RESPONSIBILITY_TYPE = "ORDER_LINE_SUPPLY_ADMISSION_CONFIRMER"
PMC_RESPONSIBILITY_CODE = "RESP_PMC_MATERIAL_002"
OBJECT_TYPE = "SalesOrderItemSupplyAdmission"
NAME = "订单行供应承接确认"
ROLE_NAME = "订单行供应承接确认责任人"
ROLE_DESCRIPTION = "仅确认订单行MAKE/BUY供应承接；不授予订单审批、工程发布或Demand创建权限。"
ALLOWED_ORDER_STATES = ("approved", "confirmed")


def register_actions():
    from workflow_runtime.action_permissions import ActionPermissionPolicy, POLICIES, OBJECT_FACT_SOURCES, MODULE_ACTIONS

    source = ("sales", "SalesOrderItem", "supply_admission_order_status")
    if MODULE_CODE in OBJECT_FACT_SOURCES and OBJECT_FACT_SOURCES[MODULE_CODE] != source:
        raise RuntimeError("订单行供应确认服务端事实源冲突。")
    OBJECT_FACT_SOURCES[MODULE_CODE] = source
    MODULE_ACTIONS[MODULE_CODE] = ((ACTION_CODE, ALLOWED_ORDER_STATES),)

    for code, scope, states in ((ACTION_CODE, "single", ALLOWED_ORDER_STATES), ("view-supply-admission", "view", ("*",))):
        policy = ActionPermissionPolicy(
            actionCode=code, moduleCode=MODULE_CODE, requiredPermission=ACTION_CODE,
            role=(ROLE_CODE,), organizationScope="legal_entity",
            serverValidator="workflow_runtime.ActionPermissionValidator",
            allowedStatuses=states, scope=scope,
        )
        key = (MODULE_CODE, code)
        if key in POLICIES and POLICIES[key] != policy:
            raise RuntimeError("订单行供应承接动作契约冲突，禁止覆盖现有注册。")
        POLICIES[key] = policy

from system.authorization import BusinessPermissionAuthorization


class DirectPurchaseAuthorization:
    """Server-owned DIRECT permission decision using formal persisted authority facts."""

    PERMISSION_CODE = "procurement.direct_purchase_order.create"

    @classmethod
    def decide(cls, user, legal_entity_id=None):
        if not legal_entity_id:
            if user and user.is_authenticated and user.is_active and user.is_superuser:
                return BusinessPermissionAuthorization.decide(user, cls.PERMISSION_CODE)
            return {
                **BusinessPermissionAuthorization.decide(user, cls.PERMISSION_CODE),
                "reason": "尚未确定供应商所属法人组织，不能校验直接采购授权。",
            }
        decision = BusinessPermissionAuthorization.decide(user, cls.PERMISSION_CODE, legal_entity_id)
        decision["reason"] = (
            "当前用户在该法人组织具有直接采购正式权限。"
            if decision["allowed"] else "当前用户在该法人组织没有直接采购正式权限。"
        )
        return decision

    @classmethod
    def decide_any_scope(cls, user):
        decision = BusinessPermissionAuthorization.decide(user, cls.PERMISSION_CODE)
        decision["reason"] = (
            "当前用户具有至少一个法人组织的直接采购正式权限。"
            if decision["allowed"] else "当前用户没有直接采购正式权限。"
        )
        return decision


class SupplierMaterialPriceAuthorization:
    PERMISSION_CODE = "masterdata.supplier_material_price.manual_maintain"

    @classmethod
    def decide(cls, user, legal_entity_id=None):
        return BusinessPermissionAuthorization.decide(user, cls.PERMISSION_CODE, legal_entity_id)

    @classmethod
    def decide_any_scope(cls, user):
        return BusinessPermissionAuthorization.decide(user, cls.PERMISSION_CODE)


class ProcurementModeRouter:
    ROUTES = {
        "STANDARD": {"routeCode": "STANDARD_PURCHASE_FLOW", "targetPath": "/scm/purchase-inquiry",
                     "status": "READY", "requiresDirectAuthorization": False},
        "AGREED_PRICE": {"routeCode": "AGREED_PRICE_PURCHASE_REQUEST", "targetPath": "/scm/purchase-request/agreed-price",
                        "status": "PURCHASE_REQUEST_CREATION_READY", "requiresDirectAuthorization": False},
        "DIRECT": {"routeCode": "DIRECT_PURCHASE_WORKBENCH", "targetPath": "/scm/purchase-order/create",
                   "status": "READY", "requiresDirectAuthorization": True},
    }

    @classmethod
    def resolve(cls, purchase_mode, user=None, legal_entity_id=None):
        mode = str(purchase_mode or "").strip().upper()
        if mode not in cls.ROUTES:
            return {"allowed": False, "purchaseMode": mode, "reason": "采购方式无效。"}
        result = {"allowed": True, "purchaseMode": mode, **cls.ROUTES[mode]}
        if mode == "DIRECT":
            authorization = DirectPurchaseAuthorization.decide(user, legal_entity_id)
            result.update({"allowed": authorization["allowed"], "authorization": authorization,
                           "reason": authorization["reason"]})
        return result

from rest_framework import serializers
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from masterdata.models import BudgetCategory, CostCenter, ExpenseCategory, Material, ProjectMaster
from pfm.formal_employee import formal_employee_queryset
from pfm.models import Employee
from system.models import Department

from .models import PurchaseRequest, PurchaseRequestItem, Supplier, PurchaseOrder, PurchaseOrderItem


class PurchaseRequestLegacySerializer(serializers.ModelSerializer):
    requestNo = serializers.CharField(source="request_no", read_only=True)
    requestDate = serializers.DateField(source="request_date")
    purchaseDepartment = serializers.CharField(source="purchase_department", allow_blank=True, required=False)
    totalQuantity = serializers.DecimalField(source="quantity", max_digits=18, decimal_places=4, read_only=True)
    requiredDate = serializers.DateField(source="required_date", allow_null=True, required=False)
    statusLabel = serializers.CharField(source="get_status_display", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = PurchaseRequest
        fields = [
            "id", "requestNo", "requestDate", "requester", "department",
            "purchaseDepartment", "items", "totalQuantity", "requiredDate",
            "status", "statusLabel", "createdAt", "updatedAt",
        ]
        read_only_fields = ["status"]

    def validate_items(self, value):
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError("采购申请至少需要一条物料明细")
        normalized = []
        for index, item in enumerate(value, start=1):
            if not isinstance(item, dict):
                raise serializers.ValidationError(f"第{index}行物料明细格式无效")
            try:
                quantity = Decimal(str(item.get("quantity")))
            except (InvalidOperation, TypeError, ValueError):
                raise serializers.ValidationError(f"第{index}行数量无效")
            if quantity <= 0:
                raise serializers.ValidationError(f"第{index}行数量必须大于0")
            required_fields = {
                "materialCode": "物料编码",
                "materialName": "物料名称",
                "specification": "规格型号",
                "unit": "单位",
                "requiredDate": "需求日期",
            }
            for field, label in required_fields.items():
                if not str(item.get(field) or "").strip():
                    raise serializers.ValidationError(f"第{index}行{label}不能为空")
            try:
                date.fromisoformat(str(item["requiredDate"]))
            except (TypeError, ValueError):
                raise serializers.ValidationError(f"第{index}行需求日期格式无效")
            normalized.append({
                "materialCode": str(item["materialCode"]).strip(),
                "materialName": str(item["materialName"]).strip(),
                "specification": str(item["specification"]).strip(),
                "unit": str(item["unit"]).strip(),
                "quantity": str(quantity),
                "requiredDate": str(item["requiredDate"]),
                "remark": str(item.get("remark") or "").strip(),
            })
        return normalized

    def validate(self, attrs):
        if self.instance and self.instance.status != "draft":
            raise serializers.ValidationError("只有草稿状态的采购申请允许编辑")
        items = attrs.get("items", self.instance.items if self.instance else [])
        attrs["quantity"] = sum((Decimal(str(item["quantity"])) for item in items), Decimal("0"))
        return attrs


class PurchaseRequestSerializer(serializers.ModelSerializer):
    requestNo = serializers.CharField(source="request_no", read_only=True)
    requestDate = serializers.DateField(source="request_date")
    requesterEmployeeId = serializers.IntegerField(write_only=True)
    departmentId = serializers.IntegerField(write_only=True)
    usageDepartmentId = serializers.IntegerField(write_only=True)
    purchaseDepartmentId = serializers.IntegerField(write_only=True)
    projectId = serializers.IntegerField(write_only=True)
    costCenterId = serializers.IntegerField(write_only=True)
    expenseCategoryId = serializers.IntegerField(write_only=True)
    budgetCategoryId = serializers.IntegerField(write_only=True)
    purchaseDepartment = serializers.CharField(source="purchase_department", read_only=True)
    usageDepartment = serializers.CharField(source="usage_department", read_only=True)
    projectCode = serializers.CharField(source="project_code", read_only=True)
    projectName = serializers.CharField(source="project_name", read_only=True)
    projectStage = serializers.CharField(source="project_stage", read_only=True)
    costCenterCode = serializers.CharField(source="cost_center_code", read_only=True)
    costCenterName = serializers.CharField(source="cost_center_name", read_only=True)
    expenseCategoryCode = serializers.CharField(source="expense_category_code", read_only=True)
    expenseCategoryName = serializers.CharField(source="expense_category_name", read_only=True)
    budgetCategoryCode = serializers.CharField(source="budget_category_code", read_only=True)
    budgetCategoryName = serializers.CharField(source="budget_category_name", read_only=True)
    applicationReason = serializers.CharField(source="application_reason", allow_blank=True, required=False)
    purchasePurpose = serializers.CharField(source="purchase_purpose", allow_blank=True, required=False)
    technicalDescription = serializers.CharField(source="technical_description", allow_blank=True, required=False)
    deliveryRequirements = serializers.CharField(source="delivery_requirements", allow_blank=True, required=False)
    noteDescription = serializers.CharField(source="note_description", allow_blank=True, required=False)
    approvalStatus = serializers.CharField(source="approval_status", read_only=True)
    approvalCurrentNode = serializers.CharField(source="approval_current_node", read_only=True)
    approvalCurrentApprover = serializers.CharField(source="approval_current_approver", read_only=True)
    approvalResult = serializers.CharField(source="approval_result", read_only=True)
    approvalHistory = serializers.SerializerMethodField()
    inquiryEligibility = serializers.SerializerMethodField()
    organizationRisk = serializers.SerializerMethodField()
    requestType = serializers.ChoiceField(source="request_type", choices=PurchaseRequest.REQUEST_TYPE_CHOICES)
    requestTypeLabel = serializers.CharField(source="get_request_type_display", read_only=True)
    purchaseMode = serializers.ChoiceField(source="purchase_mode", choices=PurchaseRequest.PURCHASE_MODE_CHOICES)
    purchaseModeLabel = serializers.CharField(source="get_purchase_mode_display", read_only=True)
    sourceType = serializers.ChoiceField(source="source_type", choices=PurchaseRequest.SOURCE_TYPE_CHOICES)
    sourceTypeLabel = serializers.CharField(source="get_source_type_display", read_only=True)
    sourcePurchasePlanId = serializers.IntegerField(source="source_purchase_plan_id", read_only=True)
    sourcePurchasePlanNo = serializers.SerializerMethodField()
    sourcePlanningRequirementNo = serializers.SerializerMethodField()
    sourceDemandNo = serializers.SerializerMethodField()
    items = serializers.ListField(write_only=True, allow_empty=False)
    totalQuantity = serializers.DecimalField(source="quantity", max_digits=18, decimal_places=4, read_only=True)
    requiredDate = serializers.DateField(source="required_date", allow_null=True, required=False)
    statusLabel = serializers.CharField(source="get_status_display", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = PurchaseRequest
        fields = [
            "id", "requestNo", "requestDate", "requesterEmployeeId",
            "departmentId", "usageDepartmentId", "purchaseDepartmentId", "requester", "department",
            "usageDepartment", "purchaseDepartment", "projectId", "projectCode", "projectName", "projectStage",
            "costCenterId", "costCenterCode", "costCenterName", "expenseCategoryId",
            "expenseCategoryCode", "expenseCategoryName", "budgetCategoryId", "budgetCategoryCode", "budgetCategoryName",
            "applicationReason", "purchasePurpose", "technicalDescription", "deliveryRequirements", "noteDescription",
            "approvalStatus", "approvalCurrentNode", "approvalCurrentApprover", "approvalResult", "approvalHistory", "inquiryEligibility",
            "organizationRisk",
            "requestType", "requestTypeLabel", "purchaseMode", "purchaseModeLabel", "sourceType",
            "sourceTypeLabel", "sourcePurchasePlanId", "sourcePurchasePlanNo",
            "sourcePlanningRequirementNo", "sourceDemandNo",
            "items", "totalQuantity", "requiredDate", "status",
            "statusLabel", "createdAt", "updatedAt",
        ]
        read_only_fields = ["requester", "department", "status"]

    @staticmethod
    def _normalize_items(items):
        normalized = []
        for index, item in enumerate(items, start=1):
            try:
                material = Material.objects.select_related("category").get(
                    pk=item.get("materialId"), is_active=True, is_purchased=True
                )
            except (Material.DoesNotExist, TypeError, ValueError):
                raise serializers.ValidationError({"items": f"第{index}行必须选择有效的可采购物料主数据"})
            try:
                quantity = Decimal(str(item.get("quantity")))
            except (InvalidOperation, TypeError, ValueError):
                raise serializers.ValidationError({"items": f"第{index}行数量无效"})
            if quantity <= 0:
                raise serializers.ValidationError({"items": f"第{index}行数量必须大于0"})
            required_date = item.get("requiredDate")
            try:
                parsed_date = date.fromisoformat(str(required_date))
            except (TypeError, ValueError):
                raise serializers.ValidationError({"items": f"第{index}行需求日期不能为空且必须有效"})
            suggested_supplier = None
            if item.get("suggestedSupplierId"):
                try:
                    suggested_supplier = Supplier.objects.get(pk=item["suggestedSupplierId"], is_active=True)
                except Supplier.DoesNotExist:
                    raise serializers.ValidationError({"items": f"第{index}行建议供应商必须来自有效供应商主数据"})
            substitute_material = None
            if item.get("substituteMaterialId"):
                try:
                    substitute_material = Material.objects.get(pk=item["substituteMaterialId"], is_active=True)
                except Material.DoesNotExist:
                    raise serializers.ValidationError({"items": f"第{index}行替代物料必须来自有效物料主数据"})
            normalized.append({
                "material": material,
                "materialId": material.pk,
                "materialCode": material.code,
                "materialName": material.name,
                "specification": material.specification or "",
                "unit": material.purchase_unit or material.unit,
                "materialCategory": material.category.name if material.category else "",
                "suggestedSupplier": suggested_supplier,
                "suggestedSupplierId": suggested_supplier.pk if suggested_supplier else None,
                "suggestedSupplierCode": suggested_supplier.code if suggested_supplier else "",
                "suggestedSupplierName": suggested_supplier.name if suggested_supplier else "",
                "demandReason": str(item.get("demandReason") or "").strip(),
                "technicalRequirements": str(item.get("technicalRequirements") or "").strip(),
                "brandRequirements": str(item.get("brandRequirements") or "").strip(),
                "substituteRequirement": str(item.get("substituteRequirement") or "").strip(),
                "substituteMaterial": substitute_material,
                "substituteMaterialId": substitute_material.pk if substitute_material else None,
                "substituteMaterialCode": substitute_material.code if substitute_material else "",
                "substituteMaterialName": substitute_material.name if substitute_material else "",
                "purchaseRemark": str(item.get("purchaseRemark") or "").strip(),
                "purchaseAttribute": "可采购" if material.is_purchased else "不可采购",
                "quantity": quantity,
                "requiredDate": parsed_date,
                "remark": str(item.get("remark") or "").strip(),
            })
        return normalized

    def validate(self, attrs):
        if self.instance and self.instance.status != "draft":
            raise serializers.ValidationError("只有草稿状态的采购申请允许编辑")
        try:
            employee = formal_employee_queryset().get(pk=attrs.pop("requesterEmployeeId"))
            department = Department.objects.get(pk=attrs.pop("departmentId"), is_active=True)
            usage_department = Department.objects.get(pk=attrs.pop("usageDepartmentId"), is_active=True)
            purchase_department = Department.objects.get(pk=attrs.pop("purchaseDepartmentId"), is_active=True)
            project = ProjectMaster.objects.get(pk=attrs.pop("projectId"), is_active=True)
            cost_center = CostCenter.objects.get(pk=attrs.pop("costCenterId"), is_active=True)
            expense_category = ExpenseCategory.objects.get(pk=attrs.pop("expenseCategoryId"), is_active=True)
            budget_category = BudgetCategory.objects.get(pk=attrs.pop("budgetCategoryId"), is_active=True)
        except (Employee.DoesNotExist, Department.DoesNotExist, ProjectMaster.DoesNotExist,
                CostCenter.DoesNotExist, ExpenseCategory.DoesNotExist, BudgetCategory.DoesNotExist,
                KeyError, TypeError, ValueError):
            raise serializers.ValidationError("申请人、申请部门和采购部门必须来自有效基础资料")
        normalized_items = self._normalize_items(attrs.pop("items"))
        attrs.update({
            "requester_employee_id": employee.pk,
            "requester_employee_no": employee.employee_no,
            "requester": employee.full_name,
            "department_master": department,
            "department": department.name,
            "usage_department_master": usage_department,
            "usage_department": usage_department.name,
            "purchase_department_master": purchase_department,
            "purchase_department": purchase_department.name,
            "project": project,
            "project_code": project.code,
            "project_name": project.name,
            "project_stage": project.stage,
            "cost_center": cost_center,
            "cost_center_code": cost_center.code,
            "cost_center_name": cost_center.name,
            "expense_category": expense_category,
            "expense_category_code": expense_category.code,
            "expense_category_name": expense_category.name,
            "budget_category": budget_category,
            "budget_category_code": budget_category.code,
            "budget_category_name": budget_category.name,
            "quantity": sum((row["quantity"] for row in normalized_items), Decimal("0")),
            "_normalized_items": normalized_items,
        })
        return attrs

    @staticmethod
    def _persist_items(instance, normalized_items):
        instance.request_items.all().delete()
        legacy_items = []
        for line_no, row in enumerate(normalized_items, start=1):
            PurchaseRequestItem.objects.create(
                purchase_request=instance, material=row["material"],
                material_code=row["materialCode"], material_name=row["materialName"],
                specification=row["specification"], unit=row["unit"],
                material_category=row["materialCategory"], purchase_attribute=row["purchaseAttribute"],
                suggested_supplier=row["suggestedSupplier"],
                suggested_supplier_code=row["suggestedSupplierCode"],
                suggested_supplier_name=row["suggestedSupplierName"],
                demand_reason=row["demandReason"],
                technical_requirements=row["technicalRequirements"],
                brand_requirements=row["brandRequirements"],
                substitute_requirement=row["substituteRequirement"],
                substitute_material=row["substituteMaterial"],
                substitute_material_code=row["substituteMaterialCode"],
                substitute_material_name=row["substituteMaterialName"],
                purchase_remark=row["purchaseRemark"],
                quantity=row["quantity"], required_date=row["requiredDate"],
                remark=row["remark"], line_no=line_no,
            )
            legacy_items.append({key: str(value) if key in {"quantity", "requiredDate"} else value for key, value in row.items() if key not in {"material", "suggestedSupplier", "substituteMaterial"}})
        instance.items = legacy_items
        instance.save(update_fields=["items", "updated_at"])

    @transaction.atomic
    def create(self, validated_data):
        normalized_items = validated_data.pop("_normalized_items")
        instance = PurchaseRequest.objects.create(**validated_data)
        self._persist_items(instance, normalized_items)
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        normalized_items = validated_data.pop("_normalized_items")
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        self._persist_items(instance, normalized_items)
        return instance

    def get_approvalHistory(self, instance):
        return [{
            "action": row.action,
            "fromStatus": row.from_status,
            "toStatus": row.to_status,
            "nodeName": row.node_name,
            "actor": row.actor,
            "comment": row.comment,
            "createdAt": row.created_at.isoformat(),
        } for row in instance.approval_records.all()]

    def get_sourcePurchasePlanNo(self, instance):
        return instance.source_purchase_plan.plan_no if instance.source_purchase_plan_id else ""

    def get_sourcePlanningRequirementNo(self, instance):
        return (instance.source_purchase_plan.planning_requirement.requirement_no
                if instance.source_purchase_plan_id else "")

    def get_sourceDemandNo(self, instance):
        return (instance.source_purchase_plan.planning_requirement.demand.demand_no
                if instance.source_purchase_plan_id else "")

    def get_inquiryEligibility(self, instance):
        eligible = instance.status == "approved" and instance.purchase_mode == "STANDARD"
        if instance.purchase_mode == "AGREED_PRICE":
            reason = "既定价格采购已审批，等待既定价格确认；禁止进入询价准备"
            next_status = "AGREED_PRICE_PURCHASE_REQUEST_READY_FOR_PRICE_CONFIRMATION"
        elif eligible:
            reason = "审批通过，可进入询价准备"
            next_status = "INQUIRY_PREPARATION_READY"
        else:
            reason = "采购申请尚未审批通过"
            next_status = "PURCHASE_REQUEST_APPROVAL_PENDING"
        return {
            "eligible": eligible,
            "reason": reason,
            "nextStatus": next_status,
            "items": [{
                "purchaseRequestItemId": row.pk,
                "lineNo": row.line_no,
                "materialId": row.material_id,
                "materialCode": row.material_code,
                "materialName": row.material_name,
                "specification": row.specification,
                "unit": row.unit,
                "quantity": str(row.quantity),
                "requiredDate": row.required_date.isoformat(),
                "demandReason": row.demand_reason,
                "technicalRequirements": row.technical_requirements,
                "brandRequirements": row.brand_requirements,
                "substituteRequirement": row.substitute_requirement,
                "suggestedSupplierCode": row.suggested_supplier_code,
                "suggestedSupplierName": row.suggested_supplier_name,
                "supplierId": row.supplier_id,
                "supplierMaterialPriceId": row.supplier_material_price_id,
                "priceRecordCode": row.price_record_code,
                "unitPriceSnapshot": (str(row.unit_price_snapshot)
                                      if row.unit_price_snapshot is not None else ""),
                "taxRateSnapshot": (str(row.tax_rate_snapshot)
                                    if row.tax_rate_snapshot is not None else ""),
                "currencySnapshot": row.currency_snapshot,
                "priceEffectiveDateSnapshot": (row.price_effective_date_snapshot.isoformat()
                                               if row.price_effective_date_snapshot else None),
            } for row in instance.request_items.all()] if eligible else [],
            "inquiryObjectCreated": False,
        }

    @staticmethod
    def _employee_matches_request_department(employee, department):
        if not employee or not department:
            return False
        return employee.department_ref_id == department.pk

    def get_organizationRisk(self, instance):
        """组织职责差异只形成审批风险，不阻断采购申请保存或提交。"""
        employee = formal_employee_queryset().filter(pk=instance.requester_employee_id).first()
        department = instance.department_master
        purchase_department = instance.purchase_department_master
        risks = []
        if not self._employee_matches_request_department(employee, department):
            risks.append({
                "code": "REQUESTER_DEPARTMENT_MISMATCH",
                "message": "申请人与请购部门不一致，请在审批中确认业务合理性",
            })
        if purchase_department and "采购" not in purchase_department.name:
            risks.append({
                "code": "NON_STANDARD_PURCHASE_ORGANIZATION",
                "message": "采购部门非标准采购组织，请审批确认",
            })
        if not risks:
            return {
                "code": "NONE",
                "codes": [],
                "level": "none",
                "blocking": False,
                "requiresApprovalAttention": False,
                "message": "",
            }
        return {
            "code": risks[0]["code"] if len(risks) == 1 else "MULTIPLE_ORGANIZATION_RISKS",
            "codes": [risk["code"] for risk in risks],
            "level": "warning",
            "blocking": False,
            "requiresApprovalAttention": True,
            "message": "；".join(risk["message"] for risk in risks),
            "requesterDepartment": employee.department_name if employee else "",
            "requestDepartment": department.name if department else instance.department,
            "purchaseDepartment": (
                purchase_department.name if purchase_department else instance.purchase_department
            ),
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        rows = instance.request_items.select_related("material").all()
        if rows.exists():
            data["items"] = [{
                "id": row.pk, "materialId": row.material_id,
                "materialCode": row.material_code, "materialName": row.material_name,
                "specification": row.specification, "unit": row.unit,
                "materialCategory": row.material_category,
                "purchaseAttribute": row.purchase_attribute,
                "suggestedSupplierId": row.suggested_supplier_id,
                "suggestedSupplierCode": row.suggested_supplier_code,
                "suggestedSupplierName": row.suggested_supplier_name,
                "demandReason": row.demand_reason,
                "technicalRequirements": row.technical_requirements,
                "brandRequirements": row.brand_requirements,
                "substituteRequirement": row.substitute_requirement,
                "substituteMaterialId": row.substitute_material_id,
                "substituteMaterialCode": row.substitute_material_code,
                "substituteMaterialName": row.substitute_material_name,
                "purchaseRemark": row.purchase_remark,
                "quantity": str(row.quantity), "requiredDate": row.required_date.isoformat(),
                "remark": row.remark,
            } for row in rows]
        else:
            data["items"] = instance.items or []
        data["requesterEmployeeId"] = instance.requester_employee_id
        data["departmentId"] = instance.department_master_id
        data["usageDepartmentId"] = instance.usage_department_master_id
        data["purchaseDepartmentId"] = instance.purchase_department_master_id
        data["projectId"] = instance.project_id
        data["costCenterId"] = instance.cost_center_id
        data["expenseCategoryId"] = instance.expense_category_id
        data["budgetCategoryId"] = instance.budget_category_id
        return data


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = "__all__"


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(source="material.name", read_only=True)
    specification = serializers.CharField(
        source="material.specification", read_only=True
    )

    class Meta:
        model = PurchaseOrderItem
        fields = [
            "id",
            "material",
            "material_name",
            "specification",
            "quantity",
            "unit_price",
            "amount",
            "expected_date",
        ]


class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = PurchaseOrderItemSerializer(many=True, required=False)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    status_display = serializers.SerializerMethodField()
    total_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, coerce_to_string=False
    )
    days_to_expiry = serializers.SerializerMethodField()
    urgency_level = serializers.SerializerMethodField()
    is_fulfilled = serializers.SerializerMethodField()

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_days_to_expiry(self, obj):
        return obj.days_to_expiry

    def get_urgency_level(self, obj):
        return obj.urgency_level

    def get_is_fulfilled(self, obj):
        return obj.is_fulfilled

    class Meta:
        model = PurchaseOrder
        fields = "__all__"

    def get_status_display(self, obj):
        return dict(PurchaseOrder.STATUS_CHOICES).get(obj.status, obj.status)

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        order = PurchaseOrder.objects.create(**validated_data)
        for item_data in items_data:
            PurchaseOrderItem.objects.create(po=order, **item_data)
        # 重新计算总金额
        order.total_amount = sum(item.amount for item in order.items.all())
        order.save()
        return order

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", [])
        instance = super().update(instance, validated_data)
        # 删除旧明细，重新创建
        instance.items.all().delete()
        for item_data in items_data:
            PurchaseOrderItem.objects.create(po=instance, **item_data)
        instance.total_amount = sum(item.amount for item in instance.items.all())
        instance.save()
        return instance


# ========== 报表序列化器 ==========
class DepartmentPurchaseReportSerializer(serializers.Serializer):
    """采购订单-部门采购表"""

    department_id = serializers.IntegerField()
    department_name = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    order_count = serializers.IntegerField()
    amount_diff_rate = serializers.DecimalField(
        max_digits=8, decimal_places=2, allow_null=True
    )
    percentage = serializers.DecimalField(max_digits=5, decimal_places=2)  # 部门占比

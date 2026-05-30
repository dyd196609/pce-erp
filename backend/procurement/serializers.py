from rest_framework import serializers
from .models import Supplier, PurchaseOrder, PurchaseOrderItem


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

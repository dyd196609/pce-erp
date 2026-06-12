from rest_framework import serializers
from .models import (
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseApprovalRecord,
    PurchaseExecutionRecord,
)


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseOrderItem
        fields = "__all__"
        read_only_fields = ["order"]


class PurchaseApprovalRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseApprovalRecord
        fields = "__all__"


class PurchaseExecutionRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseExecutionRecord
        fields = "__all__"


class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = PurchaseOrderItemSerializer(many=True, required=False)
    approval_records = PurchaseApprovalRecordSerializer(many=True, read_only=True)
    execution_records = PurchaseExecutionRecordSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = "__all__"

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        order = PurchaseOrder.objects.create(**validated_data)
        self._save_items(order, items_data)
        return order

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if items_data is not None:
            instance.items.all().delete()
            self._save_items(instance, items_data)

        return instance

    def _save_items(self, order, items_data):
        total_plan_amount = 0

        for item_data in items_data:
            plan_quantity = item_data.get("plan_quantity") or 0
            plan_unit_price = item_data.get("plan_unit_price") or 0
            plan_amount = plan_quantity * plan_unit_price

            item_data["plan_amount"] = plan_amount
            total_plan_amount += plan_amount

            PurchaseOrderItem.objects.create(order=order, **item_data)

        order.total_plan_amount = total_plan_amount
        order.save()

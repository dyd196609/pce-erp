from decimal import Decimal
from uuid import uuid4

from django.db import OperationalError, connection, transaction
from rest_framework import serializers

from .delivery_evidence import (
    DOCUMENTS, REGISTER_ACTION, business_today, can_record_delivery, delivery_batches,
    delivery_evidence_facts, order_delivery_info, verified_delivery_records,
)
from .enterprise_authority import audit
from .models import SalesOrder
from .views import SalesBaseView, envelope


class DeliveryRegistration(serializers.Serializer):
    recordKind = serializers.ChoiceField(choices=("batch", "policy", "acceptance"))
    expectedVersion = serializers.IntegerField(min_value=1)
    documentType = serializers.ChoiceField(choices=DOCUMENTS, required=False)
    sourceNo = serializers.CharField(max_length=120, required=False)
    businessDate = serializers.DateField(input_formats=["%Y-%m-%d"], required=False)
    salesOrderItemId = serializers.IntegerField(min_value=1, required=False)
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4,
                                       min_value=Decimal("0.0001"), required=False)
    contractClause = serializers.CharField(max_length=300, required=False)
    wholeOrderAcceptance = serializers.BooleanField(required=False, default=False)

    def validate(self, fields):
        required = {
            "batch": ("documentType", "sourceNo", "businessDate", "salesOrderItemId", "quantity"),
            "policy": ("documentType", "contractClause"),
            "acceptance": ("sourceNo", "businessDate"),
        }
        missing = [name for name in required[fields["recordKind"]] if name not in fields]
        if missing:
            raise serializers.ValidationError("请完整填写本次交付凭证或合同约定。")
        return fields


def reject(code, message, status=400):
    return envelope(error={"code": code, "message": message}, http_status=status)


def registered_body(order, items, fields, facts):
    kind = fields["recordKind"]
    record = {"recordKind": kind}
    if kind == "policy":
        contract_no = order.contract_reference.strip()
        if not contract_no or fields["documentType"] == "order_acceptance":
            raise serializers.ValidationError("请先核对原订单上的正式合同编号和约定的分批交付凭证。")
        return {**record, "contractNo": contract_no, "contractClause": fields["contractClause"],
                "documentType": fields["documentType"], "wholeOrderAcceptance": fields["wholeOrderAcceptance"]}
    day = fields["businessDate"]
    if day < order.order_date or day > business_today():
        raise serializers.ValidationError("凭证业务日期须在原订单日期至今天之间。")
    record.update(sourceNo=fields["sourceNo"], businessDate=day.isoformat())
    if kind == "acceptance":
        if not facts["wholeOrderAcceptanceRequired"]:
            raise serializers.ValidationError("原合同没有已登记的整单验收约定。")
        if not facts["allLinesFulfilledDate"] or record["businessDate"] < facts["allLinesFulfilledDate"]:
            raise serializers.ValidationError("全部应交行足额后，方可登记该整单验收日期。")
        return {**record, "contractNo": order.contract_reference.strip(), "documentType": "order_acceptance"}
    item = next((item for item in items if item.pk == fields["salesOrderItemId"]), None)
    if item is None or not item.uom_id:
        raise serializers.ValidationError("请选择本单有正式计量单位的订单行。")
    document = fields["documentType"]
    if document != facts["batchDocumentType"]:
        raise serializers.ValidationError("本批凭证类型须与签收默认规则或已登记的合同约定一致。")
    return {**record, "documentType": document, "salesOrderItemId": item.pk, "lineNo": item.line_no,
            "quantity": str(fields["quantity"]), "uomCode": item.uom.code,
            "actualDeliveryDate": record["businessDate"]}


def is_same_slot(stored, record):
    if stored["recordKind"] != record["recordKind"]:
        return False
    return (record["recordKind"] != "batch"
            or (stored["sourceNo"], stored["salesOrderItemId"]) == (record["sourceNo"], record["salesOrderItemId"]))


class SalesDeliveryEvidenceView(SalesBaseView):
    def post(self, request, order_id):
        try:
            return self.register(request, order_id)
        except serializers.ValidationError as exc:
            return reject("SALES_DELIVERY_EVIDENCE_INVALID", "；".join(map(str, exc.detail)))
        except OperationalError as exc:
            if connection.vendor != "sqlite" or "locked" not in str(exc).lower():
                raise
            return reject("SALES_DELIVERY_VERSION_CONFLICT", "订单正在更新，请重读原订单后核对凭证。", 409)

    @transaction.atomic
    def register(self, request, order_id):
        order = SalesOrder.objects.select_for_update().filter(pk=order_id, company_id=request.user.company_id).first()
        if not order or not can_record_delivery(request.user, order):
            return reject("SALES_DELIVERY_SCOPE_DENIED", "当前岗位无权登记该订单的交付凭证。", 403)
        serializer = DeliveryRegistration(data=request.data)
        serializer.is_valid(raise_exception=True)
        fields = serializer.validated_data
        items = list(order.items.select_related("uom", "material").order_by("line_no"))
        info = dict(order_delivery_info(order))
        stored_records = verified_delivery_records(order, info)
        facts = delivery_evidence_facts(order, items, stored_records)
        record = registered_body(order, items, fields, facts)
        for stored in stored_records.values():
            if not is_same_slot(stored, record):
                continue
            keys_to_ignore = {"deliveryAuditId", "verifiedAt", "verifiedBy", "batchNo"}
            if {key: value for key, value in stored.items() if key not in keys_to_ignore} == record:
                return envelope({"deliveryTiming": facts, "version": order.version, "idempotent": True,
                                 "auditId": stored["deliveryAuditId"]})
            return reject("SALES_DELIVERY_EVIDENCE_CONFLICT", "本单已有同一凭证登记或合同约定，请回查原记录。", 409)
        if fields["expectedVersion"] != order.version:
            return reject("SALES_DELIVERY_VERSION_CONFLICT", "订单已更新，请刷新后重新核对凭证。", 409)
        kind = record["recordKind"]
        if kind == "policy" and stored_records:
            return reject("SALES_DELIVERY_POLICY_LOCKED", "本单已有核验凭证，不能直接更改交付约定。", 409)
        if kind == "batch":
            # Generate a stable identifier unrelated to external document number and line numbering.
            record["batchNo"] = f"DLV-{uuid4().hex}"
        audit_entry = audit(request.user, REGISTER_ACTION, order, order.order_no, "核对销售交付凭证",
                            {"orderVersion": order.version},
                            {"deliveryEvidence": record, "orderVersion": order.version + 1})
        checked = {**record, "deliveryAuditId": audit_entry.pk}
        if kind == "batch":
            info["batches"] = [*delivery_batches(info), checked]
        else:
            info["verifiedDeliveryPolicy" if kind == "policy" else "verifiedOrderAcceptance"] = checked
        order.delivery_information = info
        order.version += 1
        order.save(update_fields=["delivery_information", "version", "updated_at"])
        return envelope({"deliveryTiming": delivery_evidence_facts(order, items), "version": order.version,
                         "idempotent": False, "auditId": audit_entry.pk}, http_status=201)
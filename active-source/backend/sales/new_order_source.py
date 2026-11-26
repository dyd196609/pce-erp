import hashlib
import json
import os
from decimal import Decimal
from time import sleep
from uuid import uuid4

from django.db import OperationalError, connection, transaction
from rest_framework import serializers

from masterdata.models import Material, UnitOfMeasure
from pde.models import EngineeringSourceRecord
from system.models import Company, OrganizationOperatingAuditRecord, UserRoleScopeAssignment
from workflow_runtime.state_transitions import transition_business_object

from .models import OrderSourceFormalScope
from .services import SalesBusinessError, _workflow_actor, resolve_order_line_master_data
from .views import SalesBaseView, envelope

ACTION = "sales.order_source.create"
CONFIRM_ACTION = "sales.order_source.confirm"
REGISTER_SCOPE_ACTION = "sales.order_source.register_scope"
DEPARTMENT = 9


class SourceLine(serializers.Serializer):
    product = serializers.CharField(max_length=120)
    component = serializers.CharField(max_length=120)
    unit = serializers.CharField(max_length=40)
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))
    finishedGoodsSubstitution = serializers.JSONField(required=False)

    def validate(self, data):
        if 'finishedGoodsSubstitution' in data:
            from pde.finished_goods_substitution import validate_declaration
            try:
                validate_declaration(data['finishedGoodsSubstitution'],source=True)
                if Decimal(str(data['finishedGoodsSubstitution']['rangeEnd']))>data['quantity']:
                    raise SalesBusinessError('SUBSTITUTION_SCOPE_MISMATCH','替代范围不得超出本来源行数量。',409)
            except SalesBusinessError as exc:
                raise serializers.ValidationError({'finishedGoodsSubstitution':exc.message})
        return data


class SourceInput(serializers.Serializer):
    departmentId = serializers.IntegerField()
    projectName = serializers.CharField(max_length=180)
    customerName = serializers.CharField(max_length=120)
    rows = SourceLine(many=True, allow_empty=False, max_length=200)


def source_facts(source):
    audit = None
    if source.status == "confirmed":
        audit = OrganizationOperatingAuditRecord.objects.select_related("actor").filter(
            action_code=CONFIRM_ACTION, organization_id=source.company_id,
            target_type="EngineeringSourceRecord", target_id=source.pk,
            after_snapshot__sourceVersion=source.source_version,
            after_snapshot__contentHash=source.content_hash,
        ).first()
    return {
        "id": source.pk,
        "sourceNo": source.source_no,
        "sourceVersion": source.source_version,
        "contentHash": source.content_hash,
        "statusLabel": "待评审" if source.status == "draft" else source.get_status_display(),
        "payload": source.source_payload,
        "confirmation": {
            "actorName": audit.actor.real_name or audit.actor.username,
            "confirmedAt": audit.created_at.isoformat(),
        } if audit else None,
    }


class NewOrderSourceView(SalesBaseView):
    def access(self, request, department, action=ACTION, position_code="YXB-SALES"):
        if request.user.company_id != 1 or department != DEPARTMENT:
            return envelope(None, {"code": "SOURCE_SCOPE_DENIED", "message": "来源超出销售组织范围。"}, 403)
        _, denied = self.authorize(request, action, department)
        if denied is not None:
            return denied
        if action in {CONFIRM_ACTION, REGISTER_SCOPE_ACTION} and not UserRoleScopeAssignment.objects.filter(
            user=request.user, organization_id=request.user.company_id, department_id=department,
            scope_code="DEPARTMENT", active=True, role__rolepermission__permission__code=action,
        ).exists():
            return envelope(None, {"code": "SOURCE_SCOPE_DENIED", "message": "确认权限未覆盖当前销售组织。"}, 403)
        try:
            employee, position, _, _ = _workflow_actor(request.user, action)
        except SalesBusinessError as error:
            return self.fail(error)
        if position.code != position_code or position.department_id != department or employee.department_ref_id != department:
            return envelope(None, {"code": "SOURCE_POSITION_DENIED", "message": "当前岗位不在接单来源办理范围内。"}, 403)
        return None

    def get(self, request, source_record_id=None):
        denied = self.access(request, DEPARTMENT)
        confirmation_denied = self.access(request, DEPARTMENT, CONFIRM_ACTION, "YXB-MGR")
        if denied is not None and (source_record_id is None or confirmation_denied is not None):
            return denied
        if source_record_id is None:
            return envelope({"departmentId": DEPARTMENT})
        source = EngineeringSourceRecord.objects.filter(
            pk=source_record_id, company_id=request.user.company_id,
            source_payload__crmIntake__departmentId=DEPARTMENT,
        ).first()
        if source is None:
            return envelope(None, {"code": "SOURCE_NOT_FOUND", "message": "未找到接单来源。"}, 404)
        facts = {**source_facts(source), "canConfirm": confirmation_denied is None and source.status == "draft"}
        if os.environ.get("PCE_CRM_REGISTERED_SCOPE_ENABLED") == "1" and source.status == "confirmed":
            registered = OrderSourceFormalScope.objects.select_related("registered_by").filter(
                source=source, source_version=source.source_version, content_hash=source.content_hash,
            ).first()
            facts["formalScope"] = {
                "items": registered.items, "registeredBy": registered.registered_by.username,
                "registeredAt": registered.registered_at.isoformat(),
            } if registered else None
            facts["canRegisterScope"] = registered is None and self.access(
                request, DEPARTMENT, REGISTER_SCOPE_ACTION, "YXB-MGR",
            ) is None
            if facts["canRegisterScope"]:
                facts["scopeOptions"] = {
                    "materials": list(Material.objects.filter(company_id=source.company_id, is_active=True)
                                      .order_by("code").values("id", "code", "name")),
                    "units": list(UnitOfMeasure.objects.filter(company_id=source.company_id, is_active=True)
                                  .order_by("code").values("id", "code", "name")),
                }
        return envelope(facts)

    @transaction.atomic
    def post(self, request):
        form = SourceInput(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        denied = self.access(request, data["departmentId"])
        if denied is not None:
            return denied
        rows = [
            {**row, "quantity": str(row["quantity"]), "sourceRowId": str(index)}
            for index, row in enumerate(data["rows"], 1)
        ]
        payload = {
            "crmIntake": {"departmentId": DEPARTMENT},
            "businessOrderReference": {
                "projectName": data["projectName"], "customerName": data["customerName"],
            },
            "engineeringRows": rows,
        }
        source = EngineeringSourceRecord.objects.create(
            company_id=request.user.company_id, source_no=f"CRM-{uuid4().hex.upper()}",
            source_name=data["projectName"], source_type="design_package",
            source_version="1", source_payload=payload,
            content_hash=hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
        )
        facts = source_facts(source)
        OrganizationOperatingAuditRecord.objects.create(
            action_code=ACTION, actor=request.user, organization_id=source.company_id,
            target_type="EngineeringSourceRecord", target_id=source.pk,
            target_label=source.source_no, reason="保存待评审接单来源",
            before_snapshot={}, after_snapshot=facts,
        )
        return envelope(facts, http_status=201)

    
class ConfirmOrderSourceView(NewOrderSourceView):
    def post(self, request, source_record_id):
        # SQLite cannot upgrade a stale read transaction after a competing write.
        for attempt in range(4):
            try:
                return self.confirm(request, source_record_id)
            except OperationalError as error:
                if connection.vendor != "sqlite" or "locked" not in str(error).lower():
                    raise
                if attempt == 3:
                    return envelope(None, {"code": "SOURCE_BUSY", "message": "来源正在办理，请刷新后重试。"}, 409)
                sleep(0.05 * (attempt + 1))

    @transaction.atomic
    def confirm(self, request, source_record_id):
        denied = self.access(request, DEPARTMENT, CONFIRM_ACTION, "YXB-MGR")
        if denied is not None:
            return denied
        Company.objects.select_for_update().get(pk=request.user.company_id)
        sources = EngineeringSourceRecord.objects.filter(company_id=request.user.company_id)
        source = sources.filter(pk=source_record_id, source_payload__crmIntake__departmentId=DEPARTMENT).first()
        if source is None:
            return envelope(None, {"code": "SOURCE_NOT_FOUND", "message": "未找到范围内的接单来源。"}, 404)
        digest = hashlib.sha256(json.dumps(source.source_payload, sort_keys=True).encode()).hexdigest()
        if (request.data.get("sourceVersion") != source.source_version
                or request.data.get("contentHash") != source.content_hash or digest != source.content_hash):
            return envelope(None, {"code": "SOURCE_STALE", "message": "来源版本或内容已变化，请刷新后重新核对。"}, 409)
        if sources.filter(source_no=source.source_no, status="confirmed").exclude(pk=source.pk).exists():
            return envelope(None, {"code": "SOURCE_VERSION_CONFLICT", "message": "该来源已有其他已确认版本。"}, 409)
        if source.status == "confirmed":
            return envelope(source_facts(source))
        if source.status != "draft":
            return envelope(None, {"code": "SOURCE_STATE_DENIED", "message": "仅可确认待评审来源。"}, 409)
        audit = OrganizationOperatingAuditRecord.objects.create(
            action_code=CONFIRM_ACTION, actor=request.user, organization_id=source.company_id,
            target_type="EngineeringSourceRecord", target_id=source.pk, target_label=source.source_no,
            reason="确认标准新单来源",
            before_snapshot={"status": "draft"},
            after_snapshot={"status": "confirmed", "sourceVersion": source.source_version, "contentHash": digest},
        )
        transition_business_object(
            business_object=source, object_type="EngineeringSourceRecord", source_state="draft",
            target_state="confirmed", action_code=CONFIRM_ACTION, operator=request.user,
            reason=audit.reason, audit_reference=str(audit.pk), allowed_transitions={("draft", "confirmed")},
            version_field=None,
        )
        return envelope(source_facts(source))

class FormalScopeLine(serializers.Serializer):
    sourceRowId = serializers.CharField(max_length=80)
    materialId = serializers.IntegerField(min_value=1)
    uomId = serializers.IntegerField(min_value=1)
    quantity = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))


class FormalScopeInput(serializers.Serializer):
    sourceVersion = serializers.CharField(max_length=40)
    contentHash = serializers.CharField(max_length=64)
    items = FormalScopeLine(many=True, allow_empty=False, max_length=200)


class RegisterOrderSourceScopeView(NewOrderSourceView):
    @transaction.atomic
    def post(self, request, source_record_id):
        if os.environ.get("PCE_CRM_REGISTERED_SCOPE_ENABLED") != "1":
            return envelope(None, {"code": "SCOPE_DISABLED", "message": "当前环境未启用正式范围登记。"}, 404)
        denied = self.access(request, DEPARTMENT, REGISTER_SCOPE_ACTION, "YXB-MGR")
        if denied is not None:
            return denied
        form = FormalScopeInput(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        source = EngineeringSourceRecord.objects.select_for_update().filter(
            pk=source_record_id, company_id=request.user.company_id,
            source_payload__crmIntake__departmentId=DEPARTMENT,
        ).first()
        if source is None:
            return envelope(None, {"code": "SOURCE_NOT_FOUND", "message": "未找到范围内的接单来源。"}, 404)
        digest = hashlib.sha256(json.dumps(source.source_payload, sort_keys=True).encode()).hexdigest()
        if (source.status != "confirmed" or source.source_version != data["sourceVersion"]
                or source.content_hash != data["contentHash"] or digest != source.content_hash
                or EngineeringSourceRecord.objects.filter(
                    company_id=source.company_id, source_no=source.source_no, status="confirmed",
                ).exclude(pk=source.pk).exists()):
            return envelope(None, {"code": "SOURCE_STALE", "message": "来源状态、版本或内容已变化。"}, 409)
        source_keys = {str(row["sourceRowId"]) for row in source.source_payload["engineeringRows"]}
        keys = [row["sourceRowId"] for row in data["items"]]
        if len(keys) != len(set(keys)) or set(keys) != source_keys:
            return envelope(None, {"code": "SCOPE_ROWS_INVALID", "message": "登记范围须逐一覆盖来源明细。"}, 409)
        items = []
        for line_no, row in enumerate(data["items"], 1):
            try:
                material, unit = resolve_order_line_master_data(source.company_id, row, line_no)
            except SalesBusinessError as error:
                return self.fail(error)
            items.append({
                "key": row["sourceRowId"], "materialId": material.pk, "uomId": unit.pk,
                "materialName": material.name, "unit": unit.code, "quantity": str(row["quantity"]),
            })
        registered, created = OrderSourceFormalScope.objects.get_or_create(
            source=source, defaults={
                "source_version": source.source_version, "content_hash": source.content_hash,
                "items": items, "registered_by": request.user,
            },
        )
        if not created and (registered.items != items or registered.content_hash != source.content_hash
                            or registered.source_version != source.source_version):
            return envelope(None, {"code": "SCOPE_ALREADY_REGISTERED", "message": "该来源已有不同的正式登记范围。"}, 409)
        return envelope({
            "items": registered.items, "registeredBy": registered.registered_by.username,
            "registeredAt": registered.registered_at.isoformat(),
        }, http_status=201 if created else 200)

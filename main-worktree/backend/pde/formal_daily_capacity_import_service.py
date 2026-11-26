"""Narrow, user-confirmed daily-capacity import through the formal write chain.

Only missing, explicitly authorized CapacityProductType references and
StandardCapacity records can be created. Manufacturing resources and existing
engineering/business objects are exclusively read and never maintained here.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from hashlib import sha256
import json

from .daily_capacity_import_service import DailyCapacityImportError, DailyCapacityImportService, _decimal, _normalized_name


CONTRACT = "PCE-APS-FORMAL-DAILY-CAPACITY-IMPORT-V1"
RULES_CONTRACT = "PCE-APS-CAPACITY-SOURCE-RULES-V1"
SOURCE_SYSTEM = "PCE_APS_FORMAL_CAPACITY_IMPORT"


def _hash(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _valid_on(row, on_date):
    return (row.is_active and (not row.effective_from or row.effective_from <= on_date)
            and (not row.effective_to or row.effective_to >= on_date))


def _same_payload(row, payload):
    for field in row._meta.concrete_fields:
        if field.attname in payload and getattr(row, field.attname) != field.to_python(payload[field.attname]):
            return False
    return True


class FormalDailyCapacityImportService:
    @classmethod
    def preview(cls, path, *, company_id, expected_source_sha256, field_facts, allow_product_type_creation=False):
        """Read-only review using current Process UOM and exact Routing FKs."""
        from masterdata.models import CodeRule
        from system.models import Process
        from .models import CapacityProductType, StandardCapacity, WorkCenter, WorkCenterOperationCapability

        facts = dict(field_facts or {})
        if not isinstance(allow_product_type_creation, bool):
            raise DailyCapacityImportError("PCT_AUTHORIZATION_REQUIRED", "产品类型引用新增授权必须明确为布尔值。")
        reference = facts.get("businessFactReference")
        if not isinstance(reference, (str, dict)) or not reference:
            raise DailyCapacityImportError("BUSINESS_FACT_REFERENCE_REQUIRED", "正式导入必须提供本轮用户确认及授权引用。")
        try:
            effective = date.fromisoformat(str(facts["effectiveDate"]))
        except (KeyError, ValueError):
            raise DailyCapacityImportError("EFFECTIVE_DATE_REQUIRED", "必须提供业务确认的产能生效日期。")
        for field in ("preparationDays", "transferDays"):
            if field not in facts or Decimal(_decimal(facts[field], field=field)) != Decimal("0.1"):
                raise DailyCapacityImportError("CONFIRMED_DAY_TIME_REQUIRED", "本轮准备及转运时间必须各为明确的0.1天。")
        parsed = DailyCapacityImportService.parse(path)
        if not expected_source_sha256 or parsed["sourceSha256"] != expected_source_sha256:
            raise DailyCapacityImportError("SOURCE_CHANGED", "来源SHA256与本轮已审核事实不一致。")

        operations = list(Process.objects.filter(company_id=company_id).select_related("calculation_uom", "workshop"))
        by_name = {}
        for name in [c["processName"] for c in parsed["processColumns"]] + ["拼皮"]:
            matched = [p for p in operations if p.name == name]
            if len(matched) != 1 or not matched[0].is_active:
                raise DailyCapacityImportError("PROCESS_EXACT_MATCH_REQUIRED", "来源工序必须唯一精确匹配启用的正式Process。", {"name": name})
            operation = matched[0]
            uom = operation.calculation_uom
            if not uom or not uom.is_active or uom.company_id != company_id:
                raise DailyCapacityImportError("PROCESS_UOM_REQUIRED", "正式工序核算单位缺失、停用或跨公司，必须停止。", {"processCode": operation.code})
            if operation.name == "房门组装":
                correct_uom = uom.dimension == "count" and uom.name == "套"
            else:
                correct_uom = uom.dimension == "area" and uom.name == "平方米"
            if not correct_uom:
                raise DailyCapacityImportError("CONFIRMED_UOM_MISMATCH", "当前工序核算单位与本轮已确认平方米/套口径不一致。", {"processCode": operation.code})
            confirmed = DailyCapacityImportService._field_value(facts, "capacityUomId",
                {"sourceCell": "", "productTypeCode": ""}, operation)
            if confirmed is None or isinstance(confirmed, bool) or str(confirmed) != str(uom.pk):
                raise DailyCapacityImportError("CONFIRMED_UOM_MISMATCH", "用户已确认的单位映射与当前Process核算单位不一致或缺失。", {"processCode": operation.code})
            by_name[name] = operation
        if "贴皮" not in by_name:
            raise DailyCapacityImportError("VENEER_SCOPE_REQUIRED", "拼皮适用范围必须来自Excel贴皮非空产品事实。")
        old_preview = DailyCapacityImportService.preview(path, company_id=company_id, field_facts=facts)
        if (old_preview["centreBlockers"] or old_preview["productTypeBlockers"] or old_preview["capacityBlockers"]):
            raise DailyCapacityImportError("FORMAL_IMPORT_BLOCKED", "来源关系、现有资源或业务字段事实未通过。",
                {k: old_preview[k] for k in ("centreBlockers", "productTypeBlockers", "capacityBlockers")})
        resources = {}
        for plan in old_preview["centrePlans"]:
            if not plan["workCenterId"] or not plan["capabilityId"] or plan["action"] != "REUSE":
                raise DailyCapacityImportError("EXISTING_RESOURCE_REQUIRED", "本轮禁止创建工作中心或工序能力；当前正式关联必须已经存在。", {"processCode": plan["processCode"]})
            resources[plan["processId"]] = (WorkCenter.objects.get(pk=plan["workCenterId"]),
                                            WorkCenterOperationCapability.objects.get(pk=plan["capabilityId"]))
        splicing = by_name["拼皮"]
        matching_centres = list(WorkCenter.objects.filter(company_id=company_id, workshop_id=splicing.workshop_id))
        matching_centres = [w for w in matching_centres if _normalized_name(w.name) == _normalized_name("拼皮工作中心")]
        if len(matching_centres) != 1:
            raise DailyCapacityImportError("EXISTING_RESOURCE_REQUIRED", "拼皮必须复用唯一既有正式工作中心。")
        splicing_wc = matching_centres[0]
        splicing_caps = list(WorkCenterOperationCapability.objects.filter(work_center=splicing_wc, operation=splicing))
        if len(splicing_caps) != 1:
            raise DailyCapacityImportError("EXISTING_RESOURCE_REQUIRED", "拼皮必须具备唯一既有工作中心能力关联。")
        resources[splicing.pk] = (splicing_wc, splicing_caps[0])
        for operation in by_name.values():
            wc, capability = resources[operation.pk]
            if (not _valid_on(operation, effective) or not operation.workshop_id or not operation.workshop.is_active
                    or operation.workshop.company_id != company_id or wc.company_id != company_id
                    or wc.workshop_id != operation.workshop_id or capability.operation_id != operation.pk
                    or capability.work_center_id != wc.pk or not _valid_on(wc, effective)
                    or not _valid_on(capability, effective)):
                raise DailyCapacityImportError("EXISTING_RESOURCE_INACTIVE_OR_SCOPE_INVALID", "当前工序、工作中心或能力关联无效、跨范围或已失效。", {"processCode": operation.code})

        type_plans = old_preview["productTypePlans"]
        missing_types = [p["code"] for p in type_plans if not p["productTypeId"]]
        if missing_types and not allow_product_type_creation:
            raise DailyCapacityImportError("PCT_AUTHORIZATION_REQUIRED", "缺失产品类型引用；未经明确授权必须停止，不得自动建立。", {"missingCodes": missing_types})
        for plan in type_plans:
            if plan["productTypeId"] and not _valid_on(CapacityProductType.objects.get(pk=plan["productTypeId"]), effective):
                raise DailyCapacityImportError("PRODUCT_TYPE_INACTIVE", "既有产品类型引用在生效日期无效。", {"code": plan["code"]})
        scope = {f["productTypeCode"] for f in parsed["capacities"] if f["processName"] == "贴皮"}
        manifests = {}
        for product in parsed["products"]:
            code = product["code"]
            nonblank = [f for f in parsed["capacities"] if f["productTypeCode"] == code]
            blank = [f for f in parsed["missingCells"] if f["productTypeCode"] == code]
            applicable = {by_name[f["processName"]].pk for f in nonblank}
            non_applicable = {by_name[f["processName"]].pk for f in blank}
            auxiliary = {by_name[f["processName"]].pk for f in nonblank if f["sourceStatus"] == "ZERO_CAPACITY"}
            (applicable if code in scope else non_applicable).add(splicing.pk)
            manifests[code] = {"contractVersion": RULES_CONTRACT, "sourceSha256": parsed["sourceSha256"],
                "productTypeCode": code, "effectiveDate": effective.isoformat(),
                "applicableOperationIds": sorted(applicable), "nonApplicableOperationIds": sorted(non_applicable),
                "auxiliaryOperationIds": sorted(auxiliary), "preparationDays": "0.1", "transferDays": "0.1",
                "businessFactReference": reference}
        capacity_plans = []
        source_rows = [{**f, "sourceKind": "EXCEL_BUSINESS_SOURCE"} for f in parsed["capacities"]]
        source_rows += [{"productTypeCode": p["code"], "processName": "拼皮", "sourceValue": "60",
                         "sourceStatus": "POSITIVE", "sourceKind": "USER_CONFIRMED_SUPPLEMENT", "sourceCell": None}
                        for p in parsed["products"] if p["code"] in scope]
        existing_rows = list(StandardCapacity.objects.filter(company_id=company_id, effective_from=effective)
                             .select_related("product_type"))
        for fact in source_rows:
            operation = by_name[fact["processName"]]
            wc = resources[operation.pk][0]
            role = "AUXILIARY_NO_INDEPENDENT_DATE" if fact["sourceStatus"] == "ZERO_CAPACITY" else "INDEPENDENT_DAILY_CAPACITY"
            conditions = {"sourceSha256": parsed["sourceSha256"], "sourceProductTypeCode": fact["productTypeCode"],
                "sourceSheet": parsed["sheetName"], "sourceKind": fact["sourceKind"], "sourceCell": fact["sourceCell"],
                "capacityRole": role, "apsSourceRules": manifests[fact["productTypeCode"]]}
            if fact["sourceKind"] == "USER_CONFIRMED_SUPPLEMENT":
                conditions.update({"supplementReference": reference, "applicabilitySource": "EXCEL_NONBLANK_VENEERING_PRODUCT_SCOPE"})
            payload = {"company_id": company_id, "name": f"{fact['productTypeCode']} {operation.name}日产能",
                "resource_scope": "work_center", "work_center_id": wc.pk, "operation_id": operation.pk,
                "quantity": fact["sourceValue"], "uom_id": operation.calculation_uom_id,
                "measurement_status": "zero_capacity" if fact["sourceStatus"] == "ZERO_CAPACITY" else "measured",
                "time_basis": "day", "time_basis_quantity": "1", "time_unit": "DAY", "standard_hours": None,
                "preparation_days": "0.1", "transfer_days": "0.1", "effective_from": effective.isoformat(),
                "is_active": True, "conditions": conditions}
            matched = [row for row in existing_rows if row.product_type_id
                       and row.product_type.code == fact["productTypeCode"]
                       and row.operation_id == operation.pk and row.work_center_id == wc.pk]
            if len(matched) > 1 or (matched and not _same_payload(matched[0], payload)):
                raise DailyCapacityImportError("CAPACITY_EXISTING_CONFLICT", "已有日产能与本轮真实来源/配套规则不一致，禁止覆盖。",
                    {"productTypeCode": fact["productTypeCode"], "processCode": operation.code})
            capacity_plans.append({**fact, "processId": operation.pk, "processCode": operation.code,
                "workCenterId": wc.pk, "workCenterCode": wc.code, "uomId": operation.calculation_uom_id,
                "existingCapacityId": matched[0].pk if matched else None, "payload": payload})
        if any(not p["existingCapacityId"] for p in capacity_plans) and not CodeRule.objects.filter(
                company_id=company_id, entity_type="production_standard_capacity").exists():
            raise DailyCapacityImportError("CAPACITY_CODE_RULE_REQUIRED", "缺少正式标准产能编号规则，不得绕过编号链。")
        counts = {"total": len(capacity_plans), "positive": sum(p["sourceStatus"] == "POSITIVE" for p in capacity_plans),
                  "zero": sum(p["sourceStatus"] == "ZERO_CAPACITY" for p in capacity_plans),
                  "supplement": len(scope), "blankNotApplicable": len(parsed["missingCells"])}
        result = {"contractVersion": CONTRACT, "companyId": company_id, "sourceSha256": parsed["sourceSha256"],
            "sourcePath": parsed["sourcePath"], "sourceCounts": parsed["counts"], "standardCapacityCounts": counts,
            "productTypePlans": type_plans, "capacityPlans": capacity_plans, "ruleManifests": manifests,
            "resourceReferences": [{"processId": op.pk, "workCenterId": resources[op.pk][0].pk,
                                    "capabilityId": resources[op.pk][1].pk, "uomId": op.calculation_uom_id}
                                   for op in sorted(by_name.values(), key=lambda p: p.pk)],
            "plannedWrites": {"productTypes": len(missing_types), "standardCapacities": sum(not p["existingCapacityId"] for p in capacity_plans),
                              "workCenters": 0, "capabilities": 0, "workCenterCodeRules": 0}, "writeCount": 0,
            "capacityImportReady": True, "planningReady": False}
        result["previewFingerprint"] = _hash(result)
        return result

    @classmethod
    def apply(cls, path, *, user, company_id, expected_source_sha256, field_facts, allow_product_type_creation=False, reason):
        from django.db import transaction
        from system.authorization import AuthorizationService
        from system.models import Company
        from .models import CapacityProductType, StandardCapacity
        from .production_foundation_service import ENTITY_CONFIG, ProductionFoundationService, _actor_chain

        if not str(reason or "").strip() or not getattr(user, "pk", None) or not getattr(user, "is_active", False):
            raise DailyCapacityImportError("ACTOR_REASON_REQUIRED", "必须提供启用的正式操作人和业务原因。")
        if user.company_id != company_id:
            raise DailyCapacityImportError("ACTOR_COMPANY_MISMATCH", "正式导入账户必须属于目标公司。")
        def authorize():
            decision = AuthorizationService.decide(user=user, action_code="production.master_data.capacity.maintain",
                organization_id=company_id, business_object={"organizationId": company_id, "entity": "formal-daily-capacity-import"})
            if not decision.get("allowed"):
                raise DailyCapacityImportError("PERMISSION_DENIED", "当前账户无正式产能维护权限。", {"authorization": decision})
            _actor_chain(user)
        authorize()
        initial = cls.preview(path, company_id=company_id, expected_source_sha256=expected_source_sha256,
                              field_facts=field_facts, allow_product_type_creation=allow_product_type_creation)
        with transaction.atomic():
            Company.objects.select_for_update().get(pk=company_id)
            authorize()
            reviewed = cls.preview(path, company_id=company_id, expected_source_sha256=expected_source_sha256,
                                   field_facts=field_facts, allow_product_type_creation=allow_product_type_creation)
            if reviewed["previewFingerprint"] != initial["previewFingerprint"]:
                raise DailyCapacityImportError("PREVIEW_CHANGED", "导入前来源/单位/正式关系发生变化，必须重新审核。")
            result = {"contractVersion": CONTRACT, "sourceSha256": reviewed["sourceSha256"],
                "sourceCounts": reviewed["sourceCounts"], "standardCapacityCounts": reviewed["standardCapacityCounts"],
                "ruleManifests": reviewed["ruleManifests"], "previewFingerprint": reviewed["previewFingerprint"],
                "createdProductTypes": [], "reusedProductTypes": [], "createdCapacities": [], "reusedCapacities": [],
                "auditIds": [], "actionRequestIds": [], "workCenterWriteCount": 0, "capabilityWriteCount": 0,
                "workCenterCodeRuleWriteCount": 0, "planningReady": False}
            def create(entity, payload, *, external_id, source_type):
                identity = {"sourceSystem": SOURCE_SYSTEM, "sourceType": source_type, "sourceObjectType": entity,
                    "externalId": external_id, "sourceFingerprint": reviewed["sourceSha256"],
                    "auditMetadata": {"contractVersion": CONTRACT, "sourceSha256": reviewed["sourceSha256"],
                        "sourceKind": payload.get("conditions", {}).get("sourceKind", "USER_AUTHORIZED_REFERENCE"),
                        "businessFactReference": field_facts["businessFactReference"]}}
                response = ProductionFoundationService.write(entity, user=user, payload={**payload, "reason": reason},
                    idempotency_key=f"aps-formal-capacity:{_hash([entity, identity, payload])}", source_identity=identity)
                target = ENTITY_CONFIG[entity][0].objects.get(pk=response["row"]["id"])
                if not _same_payload(target, payload):
                    raise DailyCapacityImportError("SOURCE_TARGET_PAYLOAD_CONFLICT", "来源身份返回的正式对象与当前事实不一致。", {"entity": entity})
                if response.get("auditId") and not response.get("idempotentReplay"):
                    result["auditIds"].append(response["auditId"])
                if response.get("actionRequestId"):
                    result["actionRequestIds"].append(response["actionRequestId"])
                return target.pk
            types = {}
            for plan in reviewed["productTypePlans"]:
                if plan["productTypeId"]:
                    types[plan["code"]] = plan["productTypeId"]
                    result["reusedProductTypes"].append(plan["productTypeId"])
                else:
                    types[plan["code"]] = create("capacity-product-types", {"company_id": company_id, "code": plan["code"],
                        "name": plan["name"], "product_category_id": plan["productCategoryId"],
                        "manufacturing_process_type_id": plan["manufacturingProcessTypeId"], "is_active": True},
                        external_id=f"product-type:{plan['code']}", source_type="USER_AUTHORIZED_REFERENCE")
                    result["createdProductTypes"].append(types[plan["code"]])
            for plan in reviewed["capacityPlans"]:
                payload = {**plan["payload"], "product_type_id": types[plan["productTypeCode"]]}
                if plan["existingCapacityId"]:
                    row = StandardCapacity.objects.select_for_update().get(pk=plan["existingCapacityId"])
                    if not _same_payload(row, payload):
                        raise DailyCapacityImportError("CAPACITY_EXISTING_CONFLICT", "既有正式产能发生变化，禁止覆盖。")
                    result["reusedCapacities"].append(row.pk)
                else:
                    source_id = (f"{reviewed['sourceSha256']}:{plan['sourceCell']}:{field_facts['effectiveDate']}"
                                 if plan["sourceKind"] == "EXCEL_BUSINESS_SOURCE"
                                 else f"user-supplement:splicing:{plan['productTypeCode']}:{field_facts['effectiveDate']}")
                    created = create("standard-capacities", payload, external_id=source_id,
                        source_type="BUSINESS_SOURCE" if plan["sourceKind"] == "EXCEL_BUSINESS_SOURCE" else "USER_CONFIRMED_SUPPLEMENT")
                    result["createdCapacities"].append(created)
            result["businessWriteCount"] = len(result["createdProductTypes"]) + len(result["createdCapacities"])
            result["auditIds"] = sorted(set(result["auditIds"]))
            result["actionRequestIds"] = sorted(set(result["actionRequestIds"]))
            return result

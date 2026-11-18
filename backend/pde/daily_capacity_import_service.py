"""Read real capacity matrices and import governed APS daily foundation facts.

The XLSX parser is deliberately independent of Django. Preview never writes.
Apply only extends work centres/capabilities, product types and daily capacity;
routings, Process, BOMs, calendars and scheduling objects are never modified.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import posixpath
import re
import unicodedata
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile


CONTRACT = "PCE-APS-DAILY-CAPACITY-IMPORT-V1"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


class DailyCapacityImportError(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details or {}


def _normalized_name(value):
    # Same lossless normalization as masterdata.material_identity.
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value)).strip()).casefold()


def _decimal(value, *, field, allow_zero=True):
    if isinstance(value, bool):
        raise DailyCapacityImportError("INVALID_QUANTITY", f"{field}不能是布尔值。")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise DailyCapacityImportError("INVALID_QUANTITY", f"{field}必须为真实数字。")
    if not result.is_finite() or result < 0 or (not allow_zero and result == 0):
        raise DailyCapacityImportError("INVALID_QUANTITY", f"{field}必须为有限非负数。")
    return format(result, "f")


def _digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


class DailyCapacityImportService:
    @staticmethod
    def parse(path, *, sheet_name="标准产能"):
        """Read-only wide-to-long transformation with cell-level provenance."""
        source = Path(path).resolve()
        try:
            content = source.read_bytes()
            archive = ZipFile(BytesIO(content))
            if sum(item.file_size for item in archive.infolist()) > 64 * 1024 * 1024:
                raise DailyCapacityImportError("SOURCE_TOO_LARGE", "产能来源文件解压内容过大。")
            with archive:
                book = ET.fromstring(archive.read("xl/workbook.xml"))
                sheets = [s for s in book.findall("m:sheets/m:sheet", NS)
                          if s.get("name") == sheet_name]
                if len(sheets) != 1:
                    raise DailyCapacityImportError("SOURCE_SHEET_MISSING", "必须存在唯一标准产能工作表。")
                relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
                targets = {r.get("Id"): r.get("Target") for r in relationships}
                target = targets[sheets[0].get(f"{{{REL_NS}}}id")]
                member = (target.lstrip("/") if target.startswith("/")
                          else posixpath.normpath(posixpath.join("xl", target)))
                strings = []
                if "xl/sharedStrings.xml" in archive.namelist():
                    strings = ["".join(t.text or "" for t in si.findall(".//m:t", NS))
                               for si in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
                sheet = ET.fromstring(archive.read(member))
        except DailyCapacityImportError:
            raise
        except (OSError, BadZipFile, KeyError, ET.ParseError) as exc:
            raise DailyCapacityImportError("SOURCE_READ_FAILED", "无法读取真实产能来源文件。") from exc

        cells, cell_types = {}, {}
        for cell in sheet.findall("m:sheetData/m:row/m:c", NS):
            ref = cell.get("r")
            if cell.find("m:f", NS) is not None:
                raise DailyCapacityImportError("SOURCE_FORMULA_UNSUPPORTED", "来源公式必须由业务确认后导入。", {"cell": ref})
            raw = cell.find("m:v", NS)
            value = raw.text if raw is not None else None
            kind = cell.get("t", "n")
            if kind == "s" and value is not None:
                try:
                    value = strings[int(value)]
                except (ValueError, IndexError) as exc:
                    raise DailyCapacityImportError("SOURCE_READ_FAILED", "来源字符串索引无效。", {"cell": ref}) from exc
            elif kind == "inlineStr":
                value = "".join(t.text or "" for t in cell.findall(".//m:t", NS))
            cells[ref], cell_types[ref] = value, kind
        expected = {"A1": "序号", "B1": "半成品编码", "C1": "半成品名称"}
        if any(cells.get(ref) != label for ref, label in expected.items()):
            raise DailyCapacityImportError("SOURCE_HEADER_MISMATCH", "来源必须包含序号、半成品编码及半成品名称。")
        columns = []
        for ref, value in cells.items():
            if not re.fullmatch(r"[A-Z]+1", ref) or ref in expected or value in (None, ""):
                continue
            if not isinstance(value, str) or not value.endswith("产能") or value == "产能":
                raise DailyCapacityImportError("SOURCE_HEADER_MISMATCH", "工序列必须使用真实工序名称加产能。", {"cell": ref})
            columns.append({"column": ref[:-1], "header": value, "processName": value[:-2]})
        names = [c["processName"] for c in columns]
        if not names or len(set(names)) != len(names):
            raise DailyCapacityImportError("SOURCE_PROCESS_DUPLICATE", "来源工序列不能为空或重复。")
        products, capacity_facts, missing_cells = [], [], []
        rows = sorted({int(re.search(r"\d+$", ref).group()) for ref in cells} - {1})
        seen = set()
        for row in rows:
            code, name = cells.get(f"B{row}"), cells.get(f"C{row}")
            if code in (None, "") and name in (None, ""):
                if any(cells.get(f"{col['column']}{row}") not in (None, "") for col in columns):
                    raise DailyCapacityImportError("SOURCE_PRODUCT_MISSING", "有产能值的行缺少产品类型。", {"row": row})
                continue
            if not isinstance(code, str) or not name or code != code.strip() or code.count("/") != 1:
                raise DailyCapacityImportError("SOURCE_PRODUCT_INVALID", "半成品编码及名称必须完整且可追溯。", {"row": row})
            if code in seen:
                raise DailyCapacityImportError("SOURCE_PRODUCT_DUPLICATE", "来源半成品编码重复。", {"code": code})
            seen.add(code)
            products.append({"code": code, "name": str(name), "sourceRow": row,
                             "manufacturingProcessTypeCode": code.split("/")[0],
                             "productCategoryCode": code.split("/")[1]})
            for col in columns:
                ref = f"{col['column']}{row}"
                fact = {"productTypeCode": code, "processName": col["processName"],
                        "sourceRow": row, "sourceCell": ref, "sourceHeader": col["header"]}
                value = cells.get(ref)
                if value in (None, ""):
                    missing_cells.append({**fact, "sourceValue": None, "sourceStatus": "MISSING"})
                    continue
                if cell_types.get(ref) != "n":
                    raise DailyCapacityImportError("SOURCE_CAPACITY_NOT_NUMERIC", "产能必须是Excel原始数字。", {"cell": ref})
                quantity = _decimal(value, field=ref)
                capacity_facts.append({**fact, "sourceValue": quantity,
                                       "sourceStatus": "ZERO_CAPACITY" if Decimal(quantity) == 0 else "POSITIVE"})
        if not products:
            raise DailyCapacityImportError("SOURCE_EMPTY", "来源没有真实半成品数据。")
        return {"contractVersion": CONTRACT, "sourcePath": str(source), "sourceSha256": sha256(content).hexdigest(),
                "sheetName": sheet_name, "products": products, "processColumns": columns,
                "capacities": capacity_facts, "missingCells": missing_cells,
                "counts": {"products": len(products), "processColumns": len(columns),
                           "positive": sum(f["sourceStatus"] == "POSITIVE" for f in capacity_facts),
                           "zero": sum(f["sourceStatus"] == "ZERO_CAPACITY" for f in capacity_facts),
                           "nonblank": len(capacity_facts), "blank": len(missing_cells)},
                "sourceMissingFields": ["capacityUOM", "effectiveDate", "preparationDays", "transferDays"]}

    @staticmethod
    def _field_value(field_facts, field, fact, operation):
        supplied = []
        if field in field_facts and field_facts[field] not in (None, ""):
            supplied.append(field_facts[field])
        for suffix, keys in (("ByCell", (fact["sourceCell"],)),
                             ("ByProductType", (fact["productTypeCode"],)),
                             ("ByProcess", (operation.name, operation.code, str(operation.pk)))):
            mapping = field_facts.get(field + suffix) or {}
            for key in keys:
                if key in mapping and mapping[key] not in (None, ""):
                    supplied.append(mapping[key])
        if len({str(v) for v in supplied}) > 1:
            raise DailyCapacityImportError("FIELD_FACT_CONFLICT", "同一产能事实的补充数据互相冲突。",
                                           {"field": field, "cell": fact["sourceCell"]})
        return supplied[0] if supplied else None

    @classmethod
    def preview(cls, path, *, company_id, field_facts=None):
        from masterdata.models import UnitOfMeasure
        from system.models import Company, Process
        from .models import CapacityProductType, Routing, WorkCenter, WorkCenterOperationCapability

        parsed, supplements = cls.parse(path), dict(field_facts or {})
        if not Company.objects.filter(pk=company_id, is_active=True).exists():
            raise DailyCapacityImportError("ORGANIZATION_INACTIVE", "目标公司不存在或未启用。")
        operation_rows = list(Process.objects.filter(company_id=company_id).select_related("workshop"))
        centres = list(WorkCenter.objects.filter(company_id=company_id))
        centre_plans, centre_blockers, operation_map = [], [], {}
        for col in parsed["processColumns"]:
            matched = [p for p in operation_rows if p.name == col["processName"]]
            if len(matched) != 1:
                centre_blockers.append({"code": "PROCESS_EXACT_MATCH_REQUIRED", "processName": col["processName"]})
                continue
            op = matched[0]
            operation_map[op.name] = op
            if not op.is_active or not op.workshop_id or not op.workshop.is_active or op.workshop.company_id != company_id:
                centre_blockers.append({"code": "PROCESS_WORKSHOP_REQUIRED", "processName": op.name})
                continue
            name = f"{op.name}工作中心"
            candidates = [wc for wc in centres if wc.workshop_id == op.workshop_id
                          and _normalized_name(wc.name) == _normalized_name(name)]
            if len(candidates) > 1 or (candidates and not candidates[0].is_active):
                centre_blockers.append({"code": "WORK_CENTER_MERGE_REVIEW_REQUIRED", "processName": op.name})
                continue
            wc = candidates[0] if candidates else None
            capability = (WorkCenterOperationCapability.objects.filter(work_center=wc, operation=op).first()
                          if wc else None)
            if capability and not capability.is_active:
                centre_blockers.append({"code": "CAPABILITY_INACTIVE", "processName": op.name})
            centre_plans.append({"processId": op.pk, "processCode": op.code, "processName": op.name,
                                 "workshopId": op.workshop_id, "departmentId": op.workshop.department_id,
                                 "name": name, "workCenterId": wc.pk if wc else None,
                                 "existingCode": wc.code if wc else None,
                                 "capabilityId": capability.pk if capability else None,
                                 "action": "REUSE" if wc else "CREATE"})
        type_plans, type_blockers = [], []
        for product in parsed["products"]:
            routings = list(Routing.objects.filter(company_id=company_id, routing_code=product["code"])
                            .select_related("product_category", "manufacturing_process_type"))
            if len(routings) != 1:
                type_blockers.append({"code": "ROUTING_EXACT_MATCH_REQUIRED", "productTypeCode": product["code"]})
                continue
            routing = routings[0]
            if (not routing.is_active or not routing.product_category_id or not routing.manufacturing_process_type_id
                    or routing.product_category.company_id != company_id
                    or routing.manufacturing_process_type.company_id != company_id
                    or not routing.product_category.is_active
                    or not routing.manufacturing_process_type.is_active):
                type_blockers.append({"code": "ROUTING_PRODUCT_TYPE_RELATION_INVALID", "productTypeCode": product["code"]})
                continue
            # The complete source code maps to one formal Routing. Its current
            # foreign keys own category/type identity; source code fragments
            # are not aliases for automatically allocated master-data codes.
            existing = CapacityProductType.objects.filter(company_id=company_id, code=product["code"]).first()
            if existing and (existing.name != product["name"] or not existing.is_active
                             or existing.product_category_id != routing.product_category_id
                             or existing.manufacturing_process_type_id != routing.manufacturing_process_type_id):
                type_blockers.append({"code": "PRODUCT_TYPE_EXISTING_CONFLICT", "productTypeCode": product["code"]})
            type_plans.append({**product, "routingId": routing.pk,
                               "productCategoryId": routing.product_category_id,
                               "manufacturingProcessTypeId": routing.manufacturing_process_type_id,
                               "productTypeId": existing.pk if existing else None})
        capacity_plans, capacity_blockers, remaining = [], [], Counter()
        valid_uoms = set(UnitOfMeasure.objects.filter(company_id=company_id, is_active=True).values_list("pk", flat=True))
        for fact in parsed["capacities"]:
            op = operation_map.get(fact["processName"])
            if not op:
                continue
            values = {}
            for field in ("capacityUomId", "effectiveDate", "preparationDays", "transferDays"):
                try:
                    values[field] = cls._field_value(supplements, field, fact, op)
                except DailyCapacityImportError as exc:
                    values[field] = None
                    capacity_blockers.append({"code": exc.code, "field": field, "cell": fact["sourceCell"]})
            for field in ("capacityUomId", "effectiveDate"):
                if values[field] is None:
                    capacity_blockers.append({"code": "BUSINESS_FIELD_FACT_REQUIRED", "field": field, "cell": fact["sourceCell"]})
            if values["capacityUomId"] is not None:
                try:
                    if isinstance(values["capacityUomId"], bool):
                        raise ValueError("boolean unit")
                    values["capacityUomId"] = int(values["capacityUomId"])
                except (TypeError, ValueError):
                    values["capacityUomId"] = None
                if values["capacityUomId"] not in valid_uoms:
                    capacity_blockers.append({"code": "UOM_SCOPE_INVALID", "cell": fact["sourceCell"]})
            if values["effectiveDate"] is not None:
                try:
                    values["effectiveDate"] = date.fromisoformat(str(values["effectiveDate"])).isoformat()
                except ValueError:
                    capacity_blockers.append({"code": "EFFECTIVE_DATE_INVALID", "cell": fact["sourceCell"]})
            for field in ("preparationDays", "transferDays"):
                if values[field] is None:
                    remaining[field] += 1
                else:
                    try:
                        values[field] = _decimal(values[field], field=field)
                    except DailyCapacityImportError as exc:
                        capacity_blockers.append({"code": exc.code, "field": field, "cell": fact["sourceCell"]})
            capacity_plans.append({**fact, **values, "processId": op.pk, "processCode": op.code})
        return {**parsed, "companyId": company_id, "centrePlans": centre_plans,
                "productTypePlans": type_plans, "capacityPlans": capacity_plans,
                "centreBlockers": centre_blockers, "productTypeBlockers": type_blockers,
                "capacityBlockers": capacity_blockers,
                "centresReady": not centre_blockers,
                "capacityImportReady": not centre_blockers and not type_blockers and not capacity_blockers,
                "planningReady": False, "remainingMissing": dict(remaining),
                "processesOutsideSource": [{"id": p.pk, "code": p.code, "name": p.name}
                                           for p in operation_rows if p.name not in operation_map],
                "writeCount": 0}

    @classmethod
    def apply(cls, path, *, user, company_id, expected_source_sha256, mode="centres_only", field_facts=None, reason):
        """Actor-authorized atomic import. A changed source never silently replays."""
        from django.db import transaction
        from masterdata.models import CodeRule
        from system.authorization import AuthorizationService
        from system.models import Company
        from .models import CapacityProductType, StandardCapacity, WorkCenter, WorkCenterOperationCapability
        from .production_foundation_service import ENTITY_CONFIG, ProductionFoundationService, _actor_chain, _audit

        if mode not in {"centres_only", "all"} or not str(reason or "").strip():
            raise DailyCapacityImportError("IMPORT_SCOPE_REQUIRED", "必须明确导入范围和业务原因。")
        if not getattr(user, "pk", None) or not getattr(user, "is_active", False):
            raise DailyCapacityImportError("ACTOR_REQUIRED", "必须指定已启用的正式操作账户。")
        # The shared create ledger derives organization from the actor when a
        # capability model has no company column. Fail closed for that boundary.
        if user.company_id != company_id:
            raise DailyCapacityImportError("ACTOR_COMPANY_MISMATCH", "导入账户所属公司必须与目标公司一致。")
        preview = cls.preview(path, company_id=company_id, field_facts=field_facts)
        if not expected_source_sha256 or preview["sourceSha256"] != expected_source_sha256:
            raise DailyCapacityImportError("SOURCE_CHANGED", "来源文件与已确认SHA256不一致。")
        if preview["centreBlockers"] or (mode == "all" and not preview["capacityImportReady"]):
            raise DailyCapacityImportError("IMPORT_BLOCKED", "当前事实不足以执行所选导入范围。",
                                           {k: preview[k] for k in ("centreBlockers", "productTypeBlockers", "capacityBlockers")})
        actions = ["production.master_data.resource.maintain"]
        if mode == "all":
            actions += ["production.master_data.capacity.maintain"]
        decisions = {}
        for action in actions:
            decisions[action] = AuthorizationService.decide(user=user, action_code=action,
                organization_id=company_id, business_object={"organizationId": company_id, "entity": "daily-capacity-import"})
            if not decisions[action].get("allowed"):
                raise DailyCapacityImportError("PERMISSION_DENIED", "正式导入权限校验失败。", {"authorization": decisions[action]})
        chain = _actor_chain(user)
        with transaction.atomic():
            Company.objects.select_for_update().get(pk=company_id)
            # Requery current authoritative data under the same transaction.
            preview = cls.preview(path, company_id=company_id, field_facts=field_facts)
            if preview["sourceSha256"] != expected_source_sha256 or preview["centreBlockers"]:
                raise DailyCapacityImportError("IMPORT_REVALIDATION_FAILED", "来源或正式资源事实在执行前发生变化。")
            if mode == "all" and not preview["capacityImportReady"]:
                raise DailyCapacityImportError("IMPORT_BLOCKED", "正式产能事实重验失败。")
            result = {"contractVersion": CONTRACT, "sourceSha256": preview["sourceSha256"], "mode": mode,
                      "createdWorkCenters": [], "reusedWorkCenters": [], "createdCapabilities": [],
                      "createdProductTypes": [], "createdCapacities": [], "reusedCapacities": [],
                      "codeRuleChanged": False, "auditIds": [], "planningReady": False,
                      "remainingMissing": preview["remainingMissing"], "sourceCounts": preview["counts"]}
            if any(plan["action"] == "CREATE" for plan in preview["centrePlans"]):
                rule, created = CodeRule.objects.select_for_update().get_or_create(company_id=company_id,
                    entity_type="production_work_center", defaults={"prefix": "WC", "date_format": "", "seq_length": 3})
                before = {"prefix": rule.prefix, "date_format": rule.date_format, "seq_length": rule.seq_length,
                          "current_seq": rule.current_seq, "created": created}
                existing_numbers = [int(m.group(1)) for code in WorkCenter.objects.filter(company_id=company_id).values_list("code", flat=True)
                                    if (m := re.fullmatch(r"WC(\d{3})", code))]
                already_daily = rule.prefix == "WC" and not rule.date_format and rule.seq_length == 3
                rule.current_seq = max([rule.current_seq if already_daily else 0, *existing_numbers])
                rule.prefix, rule.date_format, rule.seq_length = "WC", "", 3
                after = {"prefix": rule.prefix, "date_format": rule.date_format, "seq_length": rule.seq_length, "current_seq": rule.current_seq}
                if created or any(before[k] != after[k] for k in after):
                    rule.full_clean()
                    rule.save()
                    audit = _audit(user=user, organization_id=company_id,
                        action_code=actions[0], instance=rule, before=before, after=after, reason=reason,
                        authorization=decisions[actions[0]], execution_chain=chain,
                        audit_context={"contractVersion": CONTRACT, "sourceSha256": preview["sourceSha256"], "configuration": "WC001 numbering"})
                    result["codeRuleChanged"], result["auditIds"] = True, [audit.pk]

            def write(entity, payload, external_id):
                identity = {"sourceSystem": "PCE_APS_CAPACITY_XLSX", "sourceType": "BUSINESS_SOURCE",
                            "sourceObjectType": entity, "externalId": external_id,
                            "sourceFingerprint": preview["sourceSha256"],
                            "auditMetadata": {"contractVersion": CONTRACT, "sourceSha256": preview["sourceSha256"],
                                              "sourceSheet": preview["sheetName"], "businessFactReference": (field_facts or {}).get("businessFactReference")}}
                payload = {**payload, "reason": reason}
                response = ProductionFoundationService.write(entity, user=user, payload=payload,
                    idempotency_key=f"aps-capacity:{_digest([entity, external_id, payload])}", source_identity=identity)
                model = ENTITY_CONFIG[entity][0]
                target = model.objects.get(pk=response["row"]["id"])
                for field in model._meta.concrete_fields:
                    if field.attname in payload:
                        expected = field.to_python(payload[field.attname])
                        if getattr(target, field.attname) != expected:
                            raise DailyCapacityImportError("SOURCE_TARGET_PAYLOAD_CONFLICT",
                                "来源身份对应的正式对象与当前导入事实不一致，禁止静默重用。",
                                {"entity": entity, "field": field.attname, "id": target.pk})
                if response.get("auditId"):
                    result["auditIds"].append(response["auditId"])
                return response["row"]["id"]

            wc_by_process = {}
            for plan in preview["centrePlans"]:
                wc_id = plan["workCenterId"]
                if wc_id:
                    wc = WorkCenter.objects.get(pk=wc_id)
                    result["reusedWorkCenters"].append({"id": wc.pk, "code": wc.code, "name": wc.name})
                else:
                    wc_id = write("work-centers", {"company_id": company_id, "workshop_id": plan["workshopId"],
                        "department_id": plan["departmentId"], "name": plan["name"]},
                        f"workshop:{plan['workshopId']}:process:{plan['processId']}")
                    wc = WorkCenter.objects.get(pk=wc_id)
                    result["createdWorkCenters"].append({"id": wc.pk, "code": wc.code, "name": wc.name})
                wc_by_process[plan["processId"]] = wc_id
                if not plan["capabilityId"]:
                    primary_exists = WorkCenterOperationCapability.objects.filter(operation_id=plan["processId"], assignment_role="primary", is_active=True).exists()
                    cap_id = write("work-center-operation-capabilities", {"work_center_id": wc_id,
                        "operation_id": plan["processId"], "assignment_role": "alternative" if primary_exists else "primary"},
                        f"process:{plan['processId']}:work-center:{wc_id}")
                    result["createdCapabilities"].append(cap_id)
            if mode == "all":
                types = {}
                for plan in preview["productTypePlans"]:
                    type_id = plan["productTypeId"] or write("capacity-product-types", {
                        "company_id": company_id, "code": plan["code"], "name": plan["name"],
                        "product_category_id": plan["productCategoryId"],
                        "manufacturing_process_type_id": plan["manufacturingProcessTypeId"]}, f"product-type:{plan['code']}")
                    types[plan["code"]] = type_id
                    if not plan["productTypeId"]:
                        result["createdProductTypes"].append(type_id)
                for fact in preview["capacityPlans"]:
                    payload = {"company_id": company_id, "name": f"{fact['productTypeCode']} {fact['processName']}日产能",
                        "resource_scope": "work_center", "work_center_id": wc_by_process[fact["processId"]],
                        "operation_id": fact["processId"], "product_type_id": types[fact["productTypeCode"]],
                        "quantity": fact["sourceValue"], "uom_id": fact["capacityUomId"],
                        "measurement_status": "zero_capacity" if fact["sourceStatus"] == "ZERO_CAPACITY" else "measured",
                        "time_basis": "day", "time_basis_quantity": "1", "time_unit": "DAY",
                        "preparation_days": fact["preparationDays"], "transfer_days": fact["transferDays"],
                        "effective_from": fact["effectiveDate"],
                        "conditions": {"sourceSha256": preview["sourceSha256"], "sourceSheet": preview["sheetName"],
                                       "sourceCell": fact["sourceCell"], "sourceProductTypeCode": fact["productTypeCode"]}}
                    existing = list(StandardCapacity.objects.filter(company_id=company_id, product_type_id=payload["product_type_id"],
                        work_center_id=payload["work_center_id"], operation_id=payload["operation_id"], effective_from=fact["effectiveDate"]))
                    if existing:
                        expected = {k: str(v) if k in {"quantity", "time_basis_quantity", "preparation_days", "transfer_days", "effective_from"} and v is not None else v
                                    for k, v in payload.items()}
                        def same(row):
                            for key, value in expected.items():
                                actual = getattr(row, key)
                                if key in {"quantity", "time_basis_quantity", "preparation_days", "transfer_days"}:
                                    if (actual is None) != (value is None) or (actual is not None and Decimal(actual) != Decimal(value)):
                                        return False
                                elif str(actual) != str(value):
                                    return False
                            return row.is_active
                        if len(existing) != 1 or not same(existing[0]):
                            raise DailyCapacityImportError("CAPACITY_EXISTING_CONFLICT", "已有正式产能与来源事实不一致，禁止覆盖。", {"cell": fact["sourceCell"]})
                        result["reusedCapacities"].append(existing[0].pk)
                    else:
                        capacity_id = write("standard-capacities", payload,
                            f"{preview['sourceSha256']}:{preview['sheetName']}:{fact['sourceCell']}:{fact['effectiveDate']}")
                        result["createdCapacities"].append(capacity_id)
            result["businessWriteCount"] = sum(len(result[key]) for key in
                ("createdWorkCenters", "createdCapabilities", "createdProductTypes", "createdCapacities"))
            result["auditIds"] = sorted(set(result["auditIds"]))
            return result

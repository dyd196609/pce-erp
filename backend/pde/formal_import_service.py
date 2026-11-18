"""Wave 1 formal spreadsheet import orchestration over the canonical write service.

This module owns parsing, validation and batch orchestration only.  The actual
business write, authorization, source identity, audit and row readback remain
owned by :class:`ProductionFoundationService`.
"""

from __future__ import annotations

import csv
import io
import json
from decimal import Decimal, InvalidOperation
from hashlib import sha256

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from django.core.exceptions import ValidationError
from django.db import transaction

from masterdata.models import Material, UnitOfMeasure
from system.models import Department, Process, Workshop

from .models import Equipment, WorkCenter
from .formal_import_actor_context import (
    FormalImportActorContextError,
    preview_actor_binding as build_preview_actor_binding,
    resolve_formal_import_actor,
)
from .production_foundation_service import (
    ENTITY_CONFIG,
    ProductionFoundationError,
    ProductionFoundationService,
)


class FormalImportError(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _field(name, label, kind="text", *, required=False, default=None, choices=None, choice_labels=None):
    return {
        "name": name, "label": label, "type": kind, "required": required,
        "default": default, "choices": list(choices or []),
        "choiceLabels": dict(choice_labels or {}),
    }


YES_NO_LABELS = {True: "是", False: "否"}
UNIT_STATUS_LABELS = {"confirmed": "已确认", "not_confirmed": "未确认"}
MATERIAL_TYPE_LABELS = {
    "raw": "原材料", "semi": "半成品", "finished": "成品",
    "auxiliary": "辅料", "fixed_asset": "固定资产",
}
PRODUCT_MODE_LABELS = {"standard": "标准制造", "order_engineered": "订单工程"}
PRODUCT_STATUS_LABELS = {"draft": "草稿", "designed": "已设计", "released": "已发布"}
OPERATION_KIND_LABELS = {"atomic": "单一工序", "group": "工序组"}
CALCULATION_BASIS_LABELS = {
    "count": "数量", "length": "长度", "area": "面积", "volume": "体积",
    "mass": "质量", "time": "时间", "other": "其他", "undetermined": "未确定",
}
TRANSITION_MODE_LABELS = {"GENERAL": "普通转序", "KITTING": "齐套转序"}
RESOURCE_SCOPE_LABELS = {
    "work_center": "工作中心", "operation": "工序", "equipment": "设备", "composite": "组合资源",
}
MEASUREMENT_STATUS_LABELS = {"measured": "已测量", "not_determinable": "无法确定"}
TIME_BASIS_LABELS = {
    "not_maintained": "未维护", "hour": "小时", "shift": "班次",
    "day": "天", "batch": "批次", "custom": "自定义",
}


FORMAL_IMPORT_SCHEMAS = {
    "customers": {
        "label": "客户/经销商", "identity": "code",
        "fields": [_field("code", "编码", required=True), _field("name", "名称", required=True), _field("is_active", "启用状态", "boolean", default=True)],
    },
    "suppliers": {
        "label": "供应商", "identity": "code",
        "fields": [_field("code", "供应商编码", required=True), _field("name", "供应商名称", required=True), _field("delivery_address", "交付地址", required=True), _field("category", "分类", default="待分类"), _field("credit_rating", "信用等级", choices=("A", "B", "C", "D"), default="B"), _field("lead_time", "提前期", "integer", default=0), _field("is_active", "启用", "boolean", default=True)],
    },
    "materials": {
        "label": "物料档案", "identity": "code",
        "fields": [_field("code", "编码", required=True), _field("name", "名称", required=True), _field("specification", "规格型号"), _field("unit", "计量单位"), _field("unit_status", "单位状态", choices=("confirmed", "not_confirmed"), choice_labels=UNIT_STATUS_LABELS, default="not_confirmed"), _field("material_type", "物料类型", choices=("raw", "semi", "finished", "auxiliary", "fixed_asset"), choice_labels=MATERIAL_TYPE_LABELS, default="raw"), _field("is_purchased", "采购属性", "boolean", default=False), _field("is_produced", "产品属性", "boolean", default=False), _field("is_active", "启用状态", "boolean", default=True)],
    },
    "products": {
        "label": "产品定义", "identity": "product_code",
        "fields": [_field("product_code", "产品编码", required=True), _field("product_name", "产品名称", required=True), _field("emd_material_code", "EMD物料编码", required=True), _field("specification", "规格"), _field("model", "型号"), _field("manufacturing_definition_mode", "制造定义模式", choices=("standard", "order_engineered"), choice_labels=PRODUCT_MODE_LABELS, default="standard"), _field("status", "状态", choices=("draft", "designed", "released"), choice_labels=PRODUCT_STATUS_LABELS, default="draft"), _field("is_active", "启用", "boolean", default=True)],
    },
    "workshops": {
        "label": "车间/生产区域", "identity": "code",
        "fields": [_field("code", "编码", required=True), _field("name", "名称", required=True), _field("department_code", "所属部门"), _field("is_active", "启用状态", "boolean", default=True)],
    },
    "operations": {
        "label": "工序", "identity": "code",
        "fields": [_field("code", "工序编码", required=True), _field("name", "工序名称", required=True), _field("workshop_code", "车间编码"), _field("work_center_code", "工作中心编码"), _field("operation_kind", "工序类型", choices=("atomic", "group"), choice_labels=OPERATION_KIND_LABELS, default="atomic"), _field("calculation_basis", "核算维度", choices=("count", "length", "area", "volume", "mass", "time", "other", "undetermined"), choice_labels=CALCULATION_BASIS_LABELS, default="undetermined"), _field("calculation_uom_code", "核算单位编码"), _field("default_transition_mode", "默认转序方式", choices=("GENERAL", "KITTING"), choice_labels=TRANSITION_MODE_LABELS, default="GENERAL"), _field("is_active", "启用", "boolean", default=True)],
    },
    "work-centers": {
        "label": "工作中心", "identity": "code",
        "fields": [_field("code", "工作中心编码", required=True), _field("name", "工作中心名称", required=True), _field("department_code", "部门编码", required=True), _field("workshop_code", "车间编码"), _field("standard_labor_capacity", "标准人工产能", "decimal", default=0), _field("machine_hours", "机器工时", "decimal", default=0), _field("unit_labor_cost", "单位人工成本", "decimal", default=0), _field("manufacturing_overhead", "制造费用", "decimal", default=0), _field("is_active", "启用", "boolean", default=True)],
    },
    "equipment": {
        "label": "设备资料", "identity": "code",
        "fields": [_field("code", "设备编码", required=True), _field("name", "设备名称", required=True), _field("equipment_type", "设备类型"), _field("work_center_code", "工作中心编码", required=True), _field("capacity_per_hour", "小时产能", "decimal", default=0), _field("interface_identity", "接口标识"), _field("is_active", "启用", "boolean", default=True)],
    },
    "standard-capacities": {
        "label": "标准产能", "identity": "code",
        "fields": [_field("code", "产能编码", required=True), _field("name", "产能名称", required=True), _field("resource_scope", "资源范围", choices=("work_center", "operation", "equipment", "composite"), choice_labels=RESOURCE_SCOPE_LABELS, required=True), _field("resource_code", "资源编码"), _field("uom_code", "计量单位编码", required=True), _field("measurement_status", "测量状态", choices=("measured", "not_determinable"), choice_labels=MEASUREMENT_STATUS_LABELS, default="measured"), _field("quantity", "标准产能数量", "decimal"), _field("time_basis", "时间基准", choices=("not_maintained", "hour", "shift", "day", "batch", "custom"), choice_labels=TIME_BASIS_LABELS, default="not_maintained"), _field("time_basis_quantity", "时间基准数量", "decimal"), _field("standard_hours", "标准工时", "decimal"), _field("is_active", "启用", "boolean", default=True)],
    },
}


class FormalImportService:
    @staticmethod
    def schema(entity):
        schema = FORMAL_IMPORT_SCHEMAS.get(entity)
        if not schema or entity not in ENTITY_CONFIG:
            raise FormalImportError("IMPORT_ENTITY_NOT_APPLICABLE", "该对象不在Wave1正式导入适用范围内。")
        return schema

    @classmethod
    def template_bytes(cls, entity):
        schema = cls.schema(entity)
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = cls.worksheet_name(schema)
        headers = [field["label"] for field in schema["fields"]]
        worksheet.append(headers)
        worksheet.append([cls._example(field) for field in schema["fields"]])
        header_fill = PatternFill("solid", fgColor="1F4E78")
        for index, field in enumerate(schema["fields"], start=1):
            cell = worksheet.cell(1, index)
            cell.font = Font(color="FFFFFF", bold=True)
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
            worksheet.column_dimensions[cell.column_letter].width = max(14, min(28, len(field["label"]) * 2 + 6))
            display_choices = cls._display_choices(field)
            if display_choices:
                formula = '"' + ",".join(display_choices) + '"'
                validation = DataValidation(type="list", formula1=formula, allow_blank=not field["required"])
                validation.errorTitle = "输入不符合模板规则"
                validation.error = f"请选择{field['label']}的中文选项。"
                validation.promptTitle = field["label"]
                validation.prompt = "请选择下拉列表中的正式业务值。"
                worksheet.add_data_validation(validation)
                validation.add(f"{cell.column_letter}2:{cell.column_letter}1048576")
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = f"A1:{worksheet.cell(1, len(headers)).column_letter}2"
        stream = io.BytesIO()
        workbook.save(stream)
        return stream.getvalue()

    @staticmethod
    def worksheet_name(schema):
        # Excel forbids ASCII '/', so preserve the canonical name with its
        # visually equivalent full-width Chinese separator.
        return schema["label"].replace("/", "／")[:31]

    @staticmethod
    def _display_choices(field):
        if field["type"] == "boolean":
            return ["是", "否"]
        return [field["choiceLabels"].get(value, value) for value in field["choices"]]

    @staticmethod
    def _example(field):
        if field["required"]:
            if field["choices"]:
                return field["choiceLabels"].get(field["choices"][0], field["choices"][0])
            return f"请填写{field['label']}"
        if field["default"] is not None:
            if isinstance(field["default"], bool):
                return YES_NO_LABELS[field["default"]]
            return field["choiceLabels"].get(field["default"], field["default"])
        return ""

    @classmethod
    def preview(cls, entity, *, uploaded_file, organization_id, actor_binding=None):
        schema = cls.schema(entity)
        content = uploaded_file.read()
        source_fingerprint = sha256(entity.encode("utf-8") + b"\0" + content).hexdigest()
        binding_bytes = json.dumps(
            actor_binding or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        fingerprint = sha256(source_fingerprint.encode("ascii") + b"\0" + binding_bytes).hexdigest()
        file_name = str(getattr(uploaded_file, "name", "") or "导入文件")
        content_type = str(getattr(uploaded_file, "content_type", "") or "")
        file_type = cls.detect_file_type(file_name=file_name, content=content, content_type=content_type)
        rows, file_errors = cls._parse(content, schema, file_type=file_type)
        results = []
        seen = set()
        for index, raw in enumerate(rows, start=2):
            result = cls._validate_row(entity, schema, raw, index, organization_id, seen)
            results.append(result)
        errors = file_errors + [error for row in results for error in row["errors"]]
        counts = {
            "total": len(results),
            "ready": sum(row["state"] == "READY" for row in results),
            "review": sum(row["state"] == "REVIEW" for row in results),
            "blocked": sum(row["state"] == "BLOCKED" for row in results),
            "create": sum(row["decision"] == "CREATE" for row in results),
            "match": sum(row["decision"] == "MATCH" for row in results),
            "validationErrors": len(errors),
            "identityConflicts": sum(row["state"] == "REVIEW" for row in results),
        }
        return {
            "factLoadStatus": "success", "entity": entity, "schemaVersion": "WAVE1-FORMAL-IMPORT-SCHEMA-V1.0",
            "fileName": file_name, "fileType": file_type, "worksheetName": cls.worksheet_name(schema) if file_type == "xlsx" else None,
            "sourceFingerprint": source_fingerprint,
            "previewFingerprint": fingerprint, "previewActorBinding": actor_binding or {}, "writeCount": 0, "counts": counts,
            "canCommit": bool(results) and not errors and not counts["review"] and not counts["blocked"],
            "rows": results, "errors": errors, "warnings": [],
        }

    @staticmethod
    def detect_file_type(*, file_name, content, content_type=""):
        extension = str(file_name or "").lower().rsplit(".", 1)
        extension = f".{extension[-1]}" if len(extension) == 2 else ""
        is_xlsx = content.startswith(b"PK\x03\x04")
        if extension == ".xlsx":
            if not is_xlsx:
                raise FormalImportError("IMPORT_FILE_SIGNATURE_INVALID", "文件扩展名为.xlsx，但内容不是有效的Excel工作簿。")
            return "xlsx"
        if extension == ".csv":
            if is_xlsx:
                raise FormalImportError("IMPORT_FILE_SIGNATURE_INVALID", "文件扩展名为.csv，但内容是Excel工作簿。")
            return "csv"
        raise FormalImportError(
            "IMPORT_FILE_TYPE_UNSUPPORTED",
            "仅支持.xlsx或.csv导入文件。",
            {"fileName": file_name, "contentType": content_type},
        )

    @staticmethod
    def _parse(content, schema, *, file_type):
        if file_type == "xlsx":
            return FormalImportService._parse_xlsx(content, schema)
        if file_type == "csv":
            return FormalImportService._parse_csv(content, schema)
        raise FormalImportError("IMPORT_FILE_TYPE_UNSUPPORTED", "仅支持.xlsx或.csv导入文件。")

    @staticmethod
    def _parse_csv(content, schema):
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise FormalImportError("IMPORT_ENCODING_INVALID", "CSV必须使用UTF-8编码，或改用当前页面下载的Excel模板。") from exc
        if not text.strip():
            raise FormalImportError("IMPORT_FILE_EMPTY", "导入文件为空。")
        reader = csv.DictReader(io.StringIO(text))
        expected = [field["name"] for field in schema["fields"]]
        actual = reader.fieldnames or []
        missing = [name for name in expected if name not in actual]
        unknown = [name for name in actual if name not in expected]
        errors = []
        if missing or unknown:
            errors.append({"rowNumber": 1, "field": "header", "errorType": "SCHEMA_MISMATCH", "message": "模板列与当前正式Schema不一致。", "suggestedAction": "重新下载当前页面导入模板。", "details": {"missing": missing, "unknown": unknown}})
            return [], errors
        return [dict(row) for row in reader if any(str(value or "").strip() for value in row.values())], errors

    @staticmethod
    def _parse_xlsx(content, schema):
        try:
            workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception as exc:
            raise FormalImportError("IMPORT_FILE_INVALID", "无法读取Excel文件，请重新下载当前页面模板。") from exc
        expected_sheet = FormalImportService.worksheet_name(schema)
        if workbook.sheetnames != [expected_sheet]:
            return [], [{
                "rowNumber": 1, "field": "worksheet", "fieldLabel": "工作表",
                "errorType": "WORKSHEET_MISMATCH", "message": f"工作表名称必须为“{expected_sheet}”。",
                "suggestedAction": "重新下载当前页面中文导入模板。",
                "details": {"expected": [expected_sheet], "actual": workbook.sheetnames},
            }]
        worksheet = workbook[expected_sheet]
        values = list(worksheet.iter_rows(values_only=True))
        if not values:
            raise FormalImportError("IMPORT_FILE_EMPTY", "导入文件为空。")
        header_to_name = {field["label"]: field["name"] for field in schema["fields"]}
        actual = [str(value or "").strip() for value in values[0]]
        expected = list(header_to_name)
        missing = [label for label in expected if label not in actual]
        unknown = [label for label in actual if label not in expected]
        if missing or unknown:
            return [], [{
                "rowNumber": 1, "field": "header", "fieldLabel": "表头",
                "errorType": "SCHEMA_MISMATCH", "message": "中文模板列与当前正式Schema不一致。",
                "suggestedAction": "重新下载当前页面中文导入模板。",
                "details": {"missing": missing, "unknown": unknown},
            }]
        rows = []
        for values_row in values[1:]:
            raw = {header_to_name[label]: value for label, value in zip(actual, values_row)}
            if any(str(value or "").strip() for value in raw.values()):
                rows.append(raw)
        return rows, []

    @classmethod
    def _validate_row(cls, entity, schema, raw, row_number, organization_id, seen):
        errors, payload = [], {}
        for field in schema["fields"]:
            name, value = field["name"], str(raw.get(field["name"], "") or "").strip()
            if not value and field["default"] is not None:
                value = field["default"]
            if value == "" and field["required"]:
                errors.append(cls._error(row_number, name, "REQUIRED", f"{field['label']}不能为空。", "填写必填值后重新预览。"))
                continue
            if value == "":
                continue
            try:
                payload[name] = cls._convert(value, field)
            except ValueError as exc:
                errors.append(cls._error(row_number, name, "TYPE_OR_ENUM_INVALID", str(exc), "按模板字段说明修正值。"))
        identity = str(payload.get(schema["identity"], "")).strip()
        if identity:
            if identity in seen:
                errors.append(cls._error(row_number, schema["identity"], "DUPLICATE_IN_FILE", "文件内业务编码重复。", "每个业务编码仅保留一行。"))
            seen.add(identity)
        try:
            cls._resolve_references(entity, payload, organization_id)
        except FormalImportError as exc:
            errors.append(cls._error(row_number, exc.details.get("field", "reference"), exc.code, exc.message, "先维护有效的同公司引用，再重新预览。"))
        if entity != "equipment":
            payload["company_id"] = organization_id
        existing = cls._existing(entity, schema, payload, organization_id) if identity else None
        decision, state = "CREATE", "READY"
        if existing:
            differences = cls._differences(existing, payload)
            if differences:
                decision, state = "CONFLICT", "REVIEW"
                errors.append(cls._error(row_number, schema["identity"], "IDENTITY_CONFLICT", "业务编码已存在且字段值不同。", "人工核对现有正式数据；本导入只允许新增或完全匹配。", {"fields": differences}))
            else:
                decision, state = "MATCH", "READY"
        if not errors and decision == "CREATE":
            model = ENTITY_CONFIG[entity][0]
            try:
                model(**payload).full_clean(validate_unique=False, validate_constraints=False)
            except ValidationError as exc:
                detail = getattr(exc, "message_dict", {"row": exc.messages})
                for field, messages in detail.items():
                    errors.append(cls._error(row_number, field, "MODEL_VALIDATION_FAILED", "；".join(messages), "修正业务字段后重新预览。"))
        if errors and state != "REVIEW":
            state = "BLOCKED"
        field_labels = {field["name"]: field["label"] for field in schema["fields"]}
        field_labels.update({"header": "表头", "worksheet": "工作表", "reference": "引用字段", "row": "整行"})
        for error in errors:
            error.setdefault("fieldLabel", field_labels.get(error.get("field"), error.get("field", "字段")))
        public_payload = {key: (str(value) if isinstance(value, Decimal) else value) for key, value in payload.items() if key != "company_id"}
        display_data = []
        for field in schema["fields"]:
            if field["name"] in public_payload:
                display_data.append({
                    "label": field["label"],
                    "value": cls._display_value(field, public_payload[field["name"]]),
                })
        return {
            "rowNumber": row_number, "state": state, "stateLabel": {"READY": "可导入", "REVIEW": "需复核", "BLOCKED": "已阻断"}[state],
            "decision": decision, "decisionLabel": {"CREATE": "新建", "MATCH": "匹配已有", "CONFLICT": "冲突"}[decision],
            "identity": identity, "data": public_payload, "displayData": display_data, "errors": errors,
        }

    @staticmethod
    def _display_value(field, value):
        if field["type"] == "boolean" and isinstance(value, bool):
            return YES_NO_LABELS[value]
        return field["choiceLabels"].get(value, value)

    @staticmethod
    def _convert(value, field):
        if field["type"] == "boolean":
            normalized = str(value).strip().lower()
            if normalized in {"true", "1", "yes", "y", "是", "启用"}:
                value = True
            elif normalized in {"false", "0", "no", "n", "否", "停用"}:
                value = False
            else:
                raise ValueError(f"{field['label']}必须为“是”或“否”。")
        elif field["type"] == "integer":
            try: value = int(value)
            except (TypeError, ValueError): raise ValueError(f"{field['label']}必须为整数。")
        elif field["type"] == "decimal":
            try: value = Decimal(str(value))
            except InvalidOperation: raise ValueError(f"{field['label']}必须为数字。")
        if field["choices"]:
            display_to_code = {label: code for code, label in field["choiceLabels"].items()}
            value = display_to_code.get(value, value)
            if value not in field["choices"]:
                allowed = FormalImportService._display_choices(field)
                raise ValueError(f"{field['label']}必须为：{'、'.join(allowed)}。")
        return value

    @staticmethod
    def _lookup(model, organization_id, value, field):
        model_fields = {item.name for item in model._meta.fields}
        company_filter = (
            {"company_id": organization_id}
            if "company" in model_fields or "company_id" in model_fields
            else {"work_center__company_id": organization_id}
        )
        qs = model.objects.filter(**company_filter)
        row = qs.filter(code=value).first() or qs.filter(name=value).first()
        if not row or (hasattr(row, "is_active") and not row.is_active):
            raise FormalImportError("REFERENCE_NOT_FOUND", f"同公司有效引用不存在：{field}={value}", {"field": field})
        return row.pk

    @classmethod
    def _resolve_references(cls, entity, payload, organization_id):
        mapping = {
            "department_code": (Department, "department_id"), "workshop_code": (Workshop, "workshop_id"),
            "work_center_code": (WorkCenter, "work_center_id"), "calculation_uom_code": (UnitOfMeasure, "calculation_uom_id"),
            "uom_code": (UnitOfMeasure, "uom_id"),
        }
        for source, (model, target) in mapping.items():
            value = payload.pop(source, None)
            if value:
                payload[target] = cls._lookup(model, organization_id, value, source)
        if entity == "products":
            code = payload.get("emd_material_code")
            material = Material.objects.filter(company_id=organization_id, code=code, is_active=True).first()
            if material:
                payload["material_id"] = material.pk
        if entity == "standard-capacities":
            code = payload.pop("resource_code", None)
            scope = payload.get("resource_scope")
            resource = {"work_center": (WorkCenter, "work_center_id"), "operation": (Process, "operation_id"), "equipment": (Equipment, "equipment_id")}.get(scope)
            if resource and not code and not payload.get(resource[1]):
                raise FormalImportError("REFERENCE_REQUIRED", "该资源范围必须填写资源编码。", {"field": "resource_code"})
            if resource and code:
                payload[resource[1]] = cls._lookup(resource[0], organization_id, code, "resource_code")

    @staticmethod
    def _existing(entity, schema, payload, organization_id):
        model = ENTITY_CONFIG[entity][0]
        lookup = {schema["identity"]: payload[schema["identity"]]}
        names = {field.name for field in model._meta.fields}
        if "company" in names or "company_id" in names:
            lookup["company_id"] = organization_id
        elif entity == "equipment" and payload.get("work_center_id"):
            lookup["work_center_id"] = payload["work_center_id"]
        return model.objects.filter(**lookup).first()

    @staticmethod
    def _differences(instance, payload):
        differences = []
        for field, expected in payload.items():
            actual = getattr(instance, field, None)
            if isinstance(actual, Decimal) or isinstance(expected, Decimal):
                try:
                    equal = Decimal(str(actual)) == Decimal(str(expected))
                except InvalidOperation:
                    equal = False
            else:
                equal = actual == expected
            if not equal:
                differences.append(field)
        return differences

    @staticmethod
    def _error(row, field, kind, message, action, details=None):
        result = {"rowNumber": row, "field": field, "errorType": kind, "message": message, "suggestedAction": action}
        if details: result["details"] = details
        return result

    @classmethod
    @transaction.atomic
    def commit(cls, entity, *, uploaded_file, organization_id, user, preview_fingerprint, idempotency_key, confirmed, preview_actor_binding=None):
        if confirmed is not True:
            raise FormalImportError("EXPLICIT_CONFIRMATION_REQUIRED", "正式写入前必须明确确认。")
        if not str(idempotency_key or "").strip():
            raise FormalImportError("IDEMPOTENCY_KEY_REQUIRED", "正式导入必须提供批次幂等键。")
        current_binding = build_preview_actor_binding(user=user, organization_id=organization_id)
        if preview_actor_binding and preview_actor_binding != current_binding:
            raise FormalImportError(
                "PREVIEW_ACTOR_CONTEXT_CHANGED",
                "当前登录身份已变化，请重新预览后再确认导入。",
                {"previewActorBinding": preview_actor_binding, "currentActorBinding": current_binding},
            )
        # A commit is a privileged business write.  Resolve the formal actor
        # before comparing file details so an unauthorized identity receives
        # an explicit permission/actor-chain denial rather than a misleading
        # preview mismatch or ordinary non-committable result.
        try:
            actor_context = resolve_formal_import_actor(
                user=user,
                organization_id=organization_id,
                action_code=ENTITY_CONFIG[entity][1],
            )
        except FormalImportActorContextError as exc:
            raise FormalImportError(exc.code, exc.message, exc.details) from exc
        preview = cls.preview(
            entity, uploaded_file=uploaded_file, organization_id=organization_id,
            actor_binding=current_binding,
        )
        if preview["previewFingerprint"] != str(preview_fingerprint or ""):
            raise FormalImportError("PREVIEW_FINGERPRINT_MISMATCH", "上传文件与已确认预览不一致。")
        if not preview["canCommit"]:
            raise FormalImportError("IMPORT_NOT_COMMITTABLE", "存在REVIEW或BLOCKED行，不得正式写入。", {"counts": preview["counts"], "errors": preview["errors"]})
        created, matched, audit_ids, readback = 0, 0, [], []
        for row in preview["rows"]:
            if row["decision"] == "MATCH":
                matched += 1
                continue
            payload = dict(row["data"])
            cls._resolve_references(entity, payload, organization_id)
            if entity != "equipment": payload["company_id"] = organization_id
            payload["reason"] = "Wave1正式导入"
            row_key = f"{idempotency_key}:{row['identity']}"
            result = ProductionFoundationService.write(
                entity, user=user, payload=payload, idempotency_key=row_key,
                source_identity={
                    "sourceSystem": "PCE", "sourceType": f"{preview['fileType'].upper()}_IMPORT",
                    "sourceObjectType": f"{entity}:formal-import", "externalId": row_key,
                    "sourceFingerprint": preview["previewFingerprint"],
                    "auditMetadata": {
                        "contractVersion": "WAVE1-FORMAL-IMPORT-AUDIT-V1.0",
                        "importRunId": str(idempotency_key),
                        "sourceFile": preview["fileName"],
                        "sourceFileType": preview["fileType"],
                        "objectType": entity,
                        "previewFingerprint": preview["previewFingerprint"],
                        "rowNumber": row["rowNumber"],
                        "schemaVersion": preview["schemaVersion"],
                        "actorContext": actor_context,
                    },
                },
            )
            created += 0 if result.get("idempotentReplay") else 1
            if result.get("auditId"): audit_ids.append(result["auditId"])
            readback.append(result["row"])
        return {
            "status": "COMMITTED", "entity": entity, "previewFingerprint": preview["previewFingerprint"],
            "created": created, "matched": matched, "auditIds": audit_ids, "readback": readback,
            "actorContext": actor_context,
            "formalReadbackCount": len(ProductionFoundationService.list(entity, organization_id=organization_id)),
        }

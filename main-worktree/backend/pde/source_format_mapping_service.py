"""Versioned source-format normalization over existing engineering rule records.

Only explicitly referenced mappings affect new source payloads.  This module
does not alter engineering attributes, applicability decisions or requirements.
"""
from copy import deepcopy
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import StringIO
import json
import re


CONTRACT = "PCE-SOURCE-FORMAT-MAPPING-V1"
SOURCE_TYPES = frozenset(("CUSTOMER", "SITE_MEASUREMENT", "SALES", "DESIGN",
    "ENGINEERING_INPUT", "ENGINEERING_DERIVED", "MASTER_DATA", "RULE_PARAMETER", "AGGREGATED"))
MAX_SOURCE_BYTES = 1024 * 1024
MAX_ROWS = 1000
MAX_FIELDS = 100
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class SourceFormatMappingError(ValueError):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details or {}


def _fail(code, message, **details):
    raise SourceFormatMappingError(code, message, details)


def _json_safe(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _hash(value):
    return sha256(json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _content_hash(value):
    return sha256(value.encode("utf-8")).hexdigest() if isinstance(value, str) else _hash(value)


def validate_mapping(config):
    """Validate data-only parsing instructions, without loading Django or data."""
    if not isinstance(config, dict) or config.get("contractVersion") != CONTRACT:
        _fail("SOURCE_FORMAT_MAPPING_INVALID", "来源格式映射合同无效。")
    if config.get('format')=='XLSX_ADAPTER':
        from .engineering_workbook_source_service import validate_workbook_mapping
        return validate_workbook_mapping(config)
    if config.get("format") not in ("CSV", "JSON_ROWS"):
        _fail("SOURCE_FORMAT_UNSUPPORTED", "来源格式仅支持CSV或JSON行数组。")
    decimal_separator = config.get("decimalSeparator", ".")
    thousands_separator = config.get("thousandsSeparator", "")
    if (decimal_separator not in (".", ",") or thousands_separator not in ("", ".", ",", " ")
            or decimal_separator == thousands_separator):
        _fail("SOURCE_NUMBER_FORMAT_INVALID", "小数符与千分位符必须明确且不同。")
    delimiter = config.get("delimiter", ",")
    if not isinstance(delimiter, str) or len(delimiter) != 1 or delimiter in ("\r", "\n", '"', "\x00"):
        _fail("SOURCE_DELIMITER_INVALID", "CSV分隔符必须是一个有效字符。")
    fields = config.get("fields")
    if not isinstance(fields, list) or not 1 <= len(fields) <= MAX_FIELDS:
        _fail("SOURCE_FORMAT_FIELDS_REQUIRED", "必须维护1至100个来源字段映射。")
    raw_names, canonical_names = set(), set()
    for field in fields:
        if not isinstance(field, dict):
            _fail("SOURCE_FORMAT_FIELD_INVALID", "来源字段映射必须是对象。")
        raw, canonical = field.get("rawField"), field.get("canonicalName")
        if (not isinstance(raw, str) or not raw.strip() or raw != raw.strip()
                or not isinstance(canonical, str) or not NAME.fullmatch(canonical)):
            _fail("SOURCE_FORMAT_FIELD_INVALID", "原始字段及规范字段名称无效。")
        if raw in raw_names or canonical in canonical_names:
            _fail("SOURCE_FORMAT_FIELD_DUPLICATE", "原始字段和规范字段映射必须分别唯一。")
        raw_names.add(raw)
        canonical_names.add(canonical)
        if field.get("sourceType") not in SOURCE_TYPES or field.get("valueType") not in ("decimal", "integer", "text"):
            _fail("SOURCE_FORMAT_FIELD_INVALID", "来源类型或规范值类型无效。", canonicalName=canonical)
        if field.get("blankPolicy", "NULL") not in ("NULL", "ERROR"):
            _fail("SOURCE_FORMAT_BLANK_POLICY_INVALID", "空值处理只能为保留空值或报错。")
        tokens = []
        for key in ("zeroTokens", "blankTokens"):
            items = field.get(key, [])
            if (not isinstance(items, list) or any(not isinstance(item, str) or item != item.strip() for item in items)
                    or len(items) != len(set(items)) or len(items) > 100):
                _fail("SOURCE_FORMAT_TOKENS_INVALID", "0值与空值标记必须是无重复文本数组。", field=key)
            tokens.append(set(items))
        if "" in tokens[0] or "0" in tokens[1] or tokens[0] & tokens[1]:
            _fail("SOURCE_FORMAT_TOKENS_CONFLICT", "0与空值标记不得冲突，数字0不可映射为空值。")
        for token in tokens[1]:
            try:
                number = token.replace(thousands_separator, "") if thousands_separator else token
                if Decimal(number.replace(decimal_separator, ".")) == 0:
                    _fail("SOURCE_FORMAT_TOKENS_CONFLICT", "数字0不可配置为空值标记。")
            except InvalidOperation:
                pass
        if field.get("valueType") == "text" and tokens[0]:
            _fail("SOURCE_FORMAT_TOKENS_INVALID", "文本字段不接受数字0映射。")
        for key in ("unit", "unitDimension"):
            value = field.get(key)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                _fail("SOURCE_FORMAT_UNIT_INVALID", "单位及维度必须是正式标识文本或空值。", field=key)
    scope = config.get("scopeEquals", {})
    if (not isinstance(scope, dict) or any(not isinstance(key, str) or not key.strip()
            or not (value is None or type(value) in (str, int, bool)) for key, value in scope.items())):
        _fail("SOURCE_FORMAT_SCOPE_INVALID", "来源格式适用范围必须是明确的字段值条件。")
    return config


def _rows(config, content):
    try:
        encoded = content.encode("utf-8") if isinstance(content, str) else json.dumps(
            content, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError):
        _fail("SOURCE_FORMAT_CONTENT_INVALID", "原始内容必须是有效文本或JSON行数组。")
    if len(encoded) > MAX_SOURCE_BYTES:
        _fail("SOURCE_FORMAT_CONTENT_TOO_LARGE", "单个来源格式内容不得超过1MiB。")
    if config["format"] == "CSV":
        if not isinstance(content, str):
            _fail("SOURCE_FORMAT_CONTENT_INVALID", "CSV原始内容必须是文本。")
        try:
            reader = csv.DictReader(StringIO(content.lstrip("\ufeff")), delimiter=config.get("delimiter", ","), strict=True)
            headers = reader.fieldnames or []
            if not headers or any(not name or name != name.strip() for name in headers) or len(headers) != len(set(headers)):
                _fail("SOURCE_FORMAT_HEADERS_INVALID", "CSV表头不能为空、重复或包含首尾空格。")
            result = []
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    _fail("SOURCE_FORMAT_ROW_INVALID", "CSV行与表头列数不一致。", rowNumber=len(result) + 1)
                result.append(row)
                if len(result) > MAX_ROWS:
                    _fail("SOURCE_FORMAT_TOO_MANY_ROWS", "来源内容最多允许1000行。")
        except csv.Error as exc:
            _fail("SOURCE_FORMAT_PARSE_FAILED", "CSV原始内容无法按当前格式解析。", reason=str(exc))
    else:
        if isinstance(content, str):
            try:
                result = json.loads(content, parse_float=Decimal,
                    parse_constant=lambda _value: _fail("SOURCE_FORMAT_CONTENT_INVALID", "JSON不允许非有限数值。"))
            except (ValueError, TypeError) as exc:
                if isinstance(exc, SourceFormatMappingError):
                    raise
                _fail("SOURCE_FORMAT_PARSE_FAILED", "JSON原始内容必须是行对象数组。")
        else:
            result = deepcopy(content)
    if not isinstance(result, list) or not result or len(result) > MAX_ROWS:
        _fail("SOURCE_FORMAT_ROWS_REQUIRED", "来源内容必须包含1至1000行。")
    required = {field["rawField"] for field in config["fields"]}
    for index, row in enumerate(result):
        if not isinstance(row, dict) or any(not isinstance(key, str) for key in row):
            _fail("SOURCE_FORMAT_ROW_INVALID", "来源行必须是字段对象。", rowNumber=index + 1)
        missing = sorted(required - set(row))
        if missing:
            _fail("SOURCE_FORMAT_FIELD_MISSING", "来源行缺少配置的原始字段；缺字段不能当作空值。",
                rowNumber=index + 1, fields=missing)
    return result


def _value(raw, field, config, row_number):
    if isinstance(raw, bool) or isinstance(raw, (dict, list)):
        _fail("SOURCE_FORMAT_VALUE_INVALID", "来源字段不能是布尔值或复合对象。", rowNumber=row_number, rawField=field["rawField"])
    token = str(raw).strip() if raw is not None else None
    if token in (None, "") or token in field.get("blankTokens", []):
        if field.get("blankPolicy", "NULL") == "ERROR":
            _fail("SOURCE_FORMAT_BLANK_NOT_ALLOWED", "当前字段不允许空值。", rowNumber=row_number, rawField=field["rawField"])
        return None
    if field["valueType"] == "text":
        return token
    if token in field.get("zeroTokens", []):
        return "0"
    if isinstance(raw, float):
        _fail("SOURCE_FORMAT_DECIMAL_TEXT_REQUIRED", "JSON小数请使用原始JSON文本或十进制字符串，避免浮点精度丢失。",
            rowNumber=row_number, rawField=field["rawField"])
    decimal_separator = config.get("decimalSeparator", ".")
    thousands_separator = config.get("thousandsSeparator", "")
    # Raw JSON numbers already use JSON's decimal syntax; separators apply to
    # source text only.  Grouping is validated before separators are removed.
    if isinstance(raw, (Decimal, int)):
        canonical = str(raw)
    else:
        thousands = re.escape(thousands_separator)
        integer = rf"(?:[0-9]+|[0-9]{{1,3}}(?:{thousands}[0-9]{{3}})+)" if thousands_separator else r"[0-9]+"
        pattern = rf"[+-]?{integer}(?:{re.escape(decimal_separator)}[0-9]+)?"
        if not re.fullmatch(pattern, token):
            _fail("SOURCE_FORMAT_NUMBER_INVALID", "原始数值不符合当前小数及千分位格式。", rowNumber=row_number, rawField=field["rawField"])
        canonical = token.replace(thousands_separator, "") if thousands_separator else token
        canonical = canonical.replace(decimal_separator, ".")
    try:
        value = Decimal(canonical)
    except (InvalidOperation, TypeError, ValueError):
        _fail("SOURCE_FORMAT_NUMBER_INVALID", "来源数值无法转换为精确十进制数。")
    if not value.is_finite() or len(value.as_tuple().digits) > 50 or abs(value.adjusted()) > 100:
        _fail("SOURCE_FORMAT_NUMBER_INVALID", "来源数值必须是有限且精度受控的十进制数。")
    if field["valueType"] == "integer" and value != value.to_integral_value():
        _fail("SOURCE_FORMAT_INTEGER_REQUIRED", "规范整数字段不能包含小数。", rawField=field["rawField"])
    return format(value, "f")


def normalize_content(config, raw_content):
    """Normalize actual source rows; never infer capacity or applicability."""
    validate_mapping(config)
    rows = _rows(config, raw_content)
    normalized = []
    for index, row in enumerate(rows):
        inputs = {}
        for field in config["fields"]:
            inputs[field["canonicalName"]] = {
                "value": _value(row[field["rawField"]], field, config, index + 1),
                "valueType": field["valueType"], "sourceType": field["sourceType"],
                "unit": field.get("unit"), "unitDimension": field.get("unitDimension"),
            }
        normalized.append({"rowNumber": index + 1, "raw": _json_safe(row), "canonicalInputs": inputs})
    return {"contractVersion": CONTRACT, "format": config["format"], "rowCount": len(rows),
        "rawContentHash": _content_hash(raw_content), "mappingHash": _hash(config), "rows": normalized}


def normalize_source_payload(payload, *, company_id, on_date=None):
    """Resolve one precise current released rule and replace client projections."""
    from django.utils import timezone
    from .engineering_rule_foundation import EngineeringRuleError, specification_hash, validate_specification
    from .models import EngineeringRuleDefinition
    from masterdata.models import UnitOfMeasure

    if not isinstance(payload, dict):
        _fail("SOURCE_FORMAT_PAYLOAD_INVALID", "来源快照必须是对象。")
    result = deepcopy(payload)
    if "sourceFormatReference" not in result:
        return result
    reference = result["sourceFormatReference"]
    if (not isinstance(reference, dict) or type(reference.get("ruleId")) is not int
            or reference["ruleId"] <= 0 or not isinstance(reference.get("ruleVersion"), str)
            or not isinstance(reference.get("specificationHash"), str)):
        _fail("SOURCE_FORMAT_REFERENCE_INVALID", "来源格式必须精确引用规则ID、版本和规范Hash。")
    now = timezone.now()
    current_date = on_date or (timezone.localtime(now).date() if timezone.is_aware(now) else now.date())
    if not isinstance(current_date, date):
        _fail("SOURCE_FORMAT_DATE_INVALID", "来源格式验证日期无效。")
    rule = EngineeringRuleDefinition.objects.filter(pk=reference["ruleId"], company_id=company_id).first()
    if (not rule or rule.status != "released" or rule.version != reference["ruleVersion"]
            or specification_hash(rule.specification) != reference["specificationHash"]):
        _fail("SOURCE_FORMAT_RULE_REFERENCE_MISMATCH", "来源格式规则必须属于当前公司、已发布且精确版本及Hash一致。")
    if ((rule.effective_from and rule.effective_from > current_date)
            or (rule.effective_to and rule.effective_to < current_date)):
        _fail("SOURCE_FORMAT_RULE_NOT_EFFECTIVE", "来源格式规则当前尚未生效或已失效。")
    try:
        validate_specification(rule.specification)
    except EngineeringRuleError as exc:
        raise SourceFormatMappingError(exc.code, exc.message, exc.details)
    config = rule.specification.get("sourceFormatMapping")
    validate_mapping(config)
    fields=([field for sheet in config['sheets'] for field in sheet['fields']]
        if config.get('format')=='XLSX_ADAPTER' else config['fields'])
    for field in fields:
        if field.get("unit"):
            unit = UnitOfMeasure.objects.filter(company_id=company_id, code=field["unit"], is_active=True).first()
            if not unit or unit.dimension != field.get("unitDimension"):
                _fail("SOURCE_FORMAT_UNIT_REFERENCE_INVALID", "映射单位必须精确对应当前公司启用的正式单位和维度。",
                    canonicalName=field["canonicalName"])
        elif field.get("unitDimension") not in (None, "dimensionless"):
            _fail("SOURCE_FORMAT_UNIT_REFERENCE_INVALID", "有量纲字段必须配置当前公司正式单位。",
                canonicalName=field["canonicalName"])
    context = result.get("sourceContext", {})
    if not isinstance(context, dict) or any(key not in context or context[key] != value
            for key, value in config.get("scopeEquals", {}).items()):
        _fail("SOURCE_FORMAT_SCOPE_MISMATCH", "当前来源不符合规则配置的适用范围。")
    if "rawContent" not in result:
        _fail("SOURCE_FORMAT_CONTENT_REQUIRED", "来源格式映射必须保留原始内容。")
    if config.get('format')=='XLSX_ADAPTER':
        from .engineering_workbook_source_service import normalize_workbook_payload
        return normalize_workbook_payload(result,company_id=company_id,mapping_rule=rule,config=config)
    normalization = normalize_content(config, result["rawContent"])
    selected = result.get("sourceFormatRow", 0 if normalization["rowCount"] == 1 else None)
    if type(selected) is not int or not 0 <= selected < normalization["rowCount"]:
        _fail("SOURCE_FORMAT_ROW_SELECTION_REQUIRED", "多行来源必须明确选择本来源对象的零基行索引。")
    normalization.update({"sourceFormatReference": deepcopy(reference), "selectedRow": selected})
    result["normalization"] = normalization
    result["canonicalInputs"] = deepcopy(normalization["rows"][selected]["canonicalInputs"])
    return result


def mapped_order_inputs(source, existing_inputs, *, on_date=None):
    """Consume explicit mappings without overwriting existing engineering facts."""
    payload = source.source_payload
    if not isinstance(payload, dict) or "sourceFormatReference" not in payload:
        return existing_inputs
    from .engineering_workbook_source_service import is_workbook_source
    if is_workbook_source(source):
        _fail('WORKBOOK_SOURCE_IS_METHOD_EVIDENCE','工作簿版本是明确选择的核算方法来源，不能替换既有工程对象来源字段')
    projected = normalize_source_payload(payload, company_id=source.company_id, on_date=on_date)
    if (payload.get("normalization") != projected["normalization"]
            or payload.get("canonicalInputs") != projected["canonicalInputs"]
            or source.content_hash != projected["normalization"]["rawContentHash"]):
        _fail("SOURCE_FORMAT_SNAPSHOT_MISMATCH", "正式来源映射快照与原始内容重新核验不一致，不得静默覆盖。")
    mapped = projected["canonicalInputs"]
    if existing_inputs:
        if set(existing_inputs) != set(mapped):
            _fail("SOURCE_FORMAT_ENGINEERING_INPUT_CONFLICT", "来源映射与既有订单工程字段范围不一致。")
        for name, candidate in mapped.items():
            existing = existing_inputs[name]
            value = existing.get("value") if isinstance(existing, dict) else existing
            expected = candidate["value"]
            same_value = value == expected
            if value is not None and expected is not None and candidate["valueType"] in ("decimal", "integer"):
                try:
                    same_value = not isinstance(value, bool) and Decimal(str(value)) == Decimal(expected)
                except (InvalidOperation, TypeError, ValueError):
                    same_value = False
            if (not same_value or not isinstance(existing, dict)
                    or existing.get("unit") != candidate.get("unit")
                    or existing.get("sourceType") != candidate.get("sourceType")):
                _fail("SOURCE_FORMAT_ENGINEERING_INPUT_CONFLICT", "来源映射与既有订单工程事实不一致，不得自动替换。", canonicalName=name)
    return mapped

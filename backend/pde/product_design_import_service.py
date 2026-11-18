"""Preview/commit pipeline for the governed product-design workbook."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json

from django.db import transaction
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from masterdata.models import Material, UnitOfMeasure

from .engineering_condition_options import normalize_visible_condition
from .models import EngineeringBreakdownOption, ManufacturingProcessType, ProductCategory, ProductDesignItem
from .order_demand_preparation_service import _target_facts
from .product_design_service import (
    ProductDesignError, _color_version_options, _process_configuration_options, add_product_design_item, product_design_facts,
    product_design_list_field_contract, save_design_content,
)


WORKSHEET_NAME = "产品设计导入"
IMPORT_AUXILIARY_HEADERS = ("操作", "订单行号", "修订原因")


def product_design_import_headers():
    """Keep every business column identical to list/export, then append helpers."""
    business_headers = tuple(field["label"] for field in product_design_list_field_contract())
    return business_headers + IMPORT_AUXILIARY_HEADERS


HEADERS = product_design_import_headers()
PREVIOUS_BUSINESS_HEADERS = tuple(
    "材料规格" if field["label"] == "物料规格" else field["label"]
    for field in product_design_list_field_contract()
    if field["key"] not in {"plannedStartDate", "plannedFinishDate"}
)
PREVIOUS_HEADERS = PREVIOUS_BUSINESS_HEADERS + IMPORT_AUXILIARY_HEADERS
LEGACY_BUSINESS_HEADERS = (
    "产品标识", "所属订单行", "设计分组", "来源名称", "空间/安装位置", "来源位置",
    "实物数量", "商业数量", "单位", "产品分类", "正式产品定义", "工程对象状态",
    "材料编码", "材料名称", "材料规格", "Routing编码", "Routing名称", "油漆工艺编码",
    "油漆工艺名称", "封边方式", "见光条件", "颜色/版号", "设计长度", "设计宽度",
    "第三尺寸", "设计负责人", "设计状态", "设计修订号", "完成状态",
)
LEGACY_HEADERS = LEGACY_BUSINESS_HEADERS + ("操作", "订单行号", "第三尺寸语义", "设计说明", "修订原因")


def build_product_design_import_template():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = WORKSHEET_NAME
    sheet.append(["产品设计导入模板"])
    sheet.append(["前置业务字段与产品设计列表/导出名称、顺序、含义完全一致；末尾字段仅为导入辅助字段。"])
    sheet.append(["商业数量来自销售合同，不允许通过导入修改；实物数量表达实际设计、生产对象数量。"])
    sheet.append(["工艺配置填写 Routing 编码；油漆工艺独立填写，不得混用。"])
    sheet.append(list(HEADERS))
    for cell in sheet[5]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = PatternFill("solid", fgColor="1F4E78")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    sheet.freeze_panes = "A6"
    sheet.auto_filter.ref = f"A5:{sheet.cell(5, len(HEADERS)).column_letter}5"
    for index, header in enumerate(HEADERS, start=1):
        sheet.column_dimensions[sheet.cell(5, index).column_letter].width = min(max(len(header) + 6, 14), 28)

    metadata = workbook.create_sheet("字段说明")
    metadata.append(["字段名称", "业务含义", "数据来源", "是否允许编辑", "是否允许导入", "主数据来源"])
    for field in product_design_list_field_contract():
        metadata.append([
            field["label"], field["businessMeaning"], field["source"],
            "是" if field["editable"] else "否",
            "是" if field["importable"] else "否",
            field["masterSource"],
        ])
    for cell in metadata[1]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = PatternFill("solid", fgColor="1F4E78")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    metadata.freeze_panes = "A2"
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def _text(value):
    return str(value or "").strip()


def _file_bytes(uploaded_file):
    uploaded_file.seek(0)
    content = uploaded_file.read()
    uploaded_file.seek(0)
    if not content:
        raise ProductDesignError("PRODUCT_DESIGN_IMPORT_EMPTY", "导入文件为空。")
    return content


def _master_by_code(model, company_id, code, label, **filters):
    text = _text(code)
    if not text:
        return None, None
    matches = list(model.objects.filter(company_id=company_id, code=text, is_active=True, **filters)[:2])
    if len(matches) != 1:
        return None, f"{label}代码“{text}”未唯一匹配当前企业正式资料"
    return matches[0], None


def parse_product_design_import(uploaded_file, company_id):
    content = _file_bytes(uploaded_file)
    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise ProductDesignError("PRODUCT_DESIGN_IMPORT_INVALID", "无法解析Excel文件。") from exc
    try:
        if WORKSHEET_NAME not in workbook.sheetnames:
            raise ProductDesignError(
                "PRODUCT_DESIGN_IMPORT_SHEET_INVALID",
                f"工作表必须命名为“{WORKSHEET_NAME}”。",
                details={"actualSheets": workbook.sheetnames},
            )
        sheet = workbook[WORKSHEET_NAME]
        headers = tuple(_text(sheet.cell(5, column).value) for column in range(1, sheet.max_column + 1))
        while headers and not headers[-1]:
            headers = headers[:-1]
        if headers not in {HEADERS, PREVIOUS_HEADERS, LEGACY_HEADERS}:
            raise ProductDesignError(
                "PRODUCT_DESIGN_IMPORT_HEADERS_INVALID", "导入表头与正式模板不一致。",
                details={"expected": HEADERS, "actual": headers},
            )
        order, _source, _review, _workflow, _approval = _target_facts(company_id)
        items = {
            item.item_no: item for item in ProductDesignItem.objects.filter(
                company_id=company_id, sales_order_item__sales_order=order,
            ).select_related("sales_order_item")
        }
        rows, seen_updates = [], set()
        for row_no in range(6, sheet.max_row + 1):
            values = [sheet.cell(row_no, column).value for column in range(1, len(headers) + 1)]
            if not any(value not in (None, "") for value in values):
                continue
            source = dict(zip(headers, values))
            if headers == PREVIOUS_HEADERS:
                source["物料规格"] = source.pop("材料规格", None)
                source["设计计划开工日期"] = None
                source["设计计划完工日期"] = None
            elif headers == LEGACY_HEADERS:
                source["实物单位"] = source.pop("单位", None)
                source["设计尺寸单位"] = None
                source["物料规格"] = source.pop("材料规格", None)
                for field in product_design_list_field_contract():
                    source.setdefault(field["label"], None)
            operation = _text(source["操作"])
            errors, changes = [], []
            if operation not in {"新增", "更新"}:
                errors.append("操作只能是新增或更新")
            item = None
            stable_id = _text(source["产品标识"])
            if operation == "更新":
                if not stable_id:
                    errors.append("更新必须填写产品标识")
                elif stable_id in seen_updates:
                    errors.append("同一文件不得重复更新同一产品标识")
                else:
                    seen_updates.add(stable_id)
                    item = items.get(stable_id)
                    if not item:
                        errors.append("产品标识不属于当前订单或当前企业")
            if operation == "新增":
                try:
                    line_no = int(source["订单行号"])
                except (TypeError, ValueError):
                    line_no = None
                    errors.append("新增必须填写1至4的订单行号")
                if line_no not in {row.line_no for row in order.items.all()}:
                    errors.append("订单行号不属于当前订单")
                if not _text(source["来源名称"]):
                    errors.append("新增必须填写来源名称")
            uom, error = _master_by_code(UnitOfMeasure, company_id, source["实物单位"], "实物单位")
            if error:
                errors.append(error)
            design_uom, error = _master_by_code(UnitOfMeasure, company_id, source["设计尺寸单位"], "设计尺寸单位")
            if error:
                errors.append(error)
            if design_uom and design_uom.dimension != UnitOfMeasure.Dimension.LENGTH:
                errors.append("设计尺寸单位必须是长度单位")
            category, error = _master_by_code(ProductCategory, company_id, source["产品分类"], "产品分类")
            if error:
                errors.append(error)
            material, error = _master_by_code(Material, company_id, source["材料编码"], "材料")
            if error:
                errors.append(error)
            if not material and (_text(source["材料名称"]) or _text(source["物料规格"])):
                errors.append("填写材料名称或物料规格时必须同时填写可唯一匹配的材料编码")
            if material and _text(source["材料名称"]) and _text(source["材料名称"]) != material.name:
                errors.append("材料名称与材料编码对应的正式主数据不一致")
            if material and _text(source["物料规格"]) and _text(source["物料规格"]) != _text(material.specification):
                errors.append("物料规格与材料编码对应的正式主数据不一致")
            configuration = None
            configuration_code = _text(source["Routing编码"])
            if not configuration_code and _text(source["Routing名称"]):
                errors.append("填写工艺配置名称时必须同时填写 Routing 编码")
            if configuration_code:
                matches = [row for row in _process_configuration_options(company_id) if row["code"] == configuration_code]
                if len(matches) != 1:
                    errors.append(f"工艺配置代码“{configuration_code}”未唯一匹配当前企业已发布的 Routing 正式工艺路线")
                elif not item:
                    errors.append("新增设计项尚无来源产品关系，不能通过导入猜测工艺配置")
                elif item.pk not in matches[0]["compatibleItemIds"]:
                    errors.append(f"Routing编码“{configuration_code}”不适用于该产品分类或产品标识")
                elif not matches[0].get("paintProcessTypeId"):
                    errors.append(
                        f"工艺配置代码“{configuration_code}”没有唯一可核实的油漆工艺关系；"
                        "保留当前来源值，不允许通过导入猜测保存"
                    )
                else:
                    configuration = matches[0]
            if configuration and _text(source["Routing名称"]) and _text(source["Routing名称"]) != configuration["name"]:
                errors.append("工艺配置名称与 Routing 编码对应的正式主数据不一致")
            paint, error = _master_by_code(ManufacturingProcessType, company_id, source["油漆工艺编码"], "油漆工艺")
            if error:
                errors.append(error)
            if not paint and _text(source["油漆工艺名称"]):
                errors.append("填写油漆工艺名称时必须同时填写油漆工艺编码")
            if paint and _text(source["油漆工艺名称"]) and _text(source["油漆工艺名称"]) != paint.name:
                errors.append("油漆工艺名称与油漆工艺编码对应的正式主数据不一致")
            if configuration and paint and configuration.get("paintProcessTypeId") != paint.pk:
                errors.append("油漆工艺与完整工艺配置的现有正式关系不一致")
            edge, error = _master_by_code(
                EngineeringBreakdownOption, company_id, source["封边方式"], "封边方式",
                option_type=EngineeringBreakdownOption.OptionType.EDGE_METHOD,
            )
            if error:
                errors.append(error)
            visible = None
            if _text(source["见光条件"]):
                try:
                    visible = normalize_visible_condition(code=_text(source["见光条件"]), allow_blank=False)
                except ValueError:
                    errors.append("见光条件代码不是受治理选项")
            dimension_semantic = _text(source["第三尺寸语义"])
            if dimension_semantic and dimension_semantic not in {"墙厚", "部件厚", "实际厚度"}:
                errors.append("第三尺寸语义必须是墙厚、部件厚或实际厚度")
            if not _text(source["修订原因"]):
                errors.append("修订原因不能为空")
            design_data = {}
            for header, key in (
                ("设计长度", "designLength"), ("设计宽度", "designWidth"),
                ("第三尺寸", "designThickness"),
            ):
                if source[header] not in (None, ""):
                    try:
                        number = str(source[header])
                        if float(number) <= 0:
                            raise ValueError
                        design_data[key] = number
                    except (TypeError, ValueError):
                        errors.append(f"{header}必须大于0")
            if category:
                design_data["productCategoryId"] = category.pk
            if uom:
                design_data["physicalUomId"] = uom.pk
            if design_uom:
                design_data["designUomId"] = design_uom.pk
            if material:
                design_data["materialId"] = material.pk
            if configuration:
                design_data["processConfigurationId"] = configuration["id"]
            if paint:
                design_data["paintProcessTypeId"] = paint.pk
            if edge:
                design_data["edgeMethodId"] = edge.pk
            if visible:
                design_data["visibleConditionCode"] = visible["code"]
            color_value = _text(source["颜色/版号"])
            if color_value:
                color_matches = [
                    option for option in _color_version_options(company_id)
                    if color_value in {option["id"], option["code"], option["name"]}
                ]
                if len(color_matches) != 1:
                    errors.append(f"颜色/版号“{color_value}”未唯一匹配当前订单受控候选")
                else:
                    design_data["colorVersionOptionId"] = color_matches[0]["id"]
            if _text(source["设计说明"]):
                design_data["designNotes"] = _text(source["设计说明"])
            if _text(source["配置说明"]):
                design_data["configurationNotes"] = _text(source["配置说明"])
            if _text(source["五金要求"]):
                design_data["hardware"] = _text(source["五金要求"])
            if _text(source["玻璃要求"]):
                design_data["glass"] = _text(source["玻璃要求"])
            if _text(source["资料引用"]):
                design_data["documentReferences"] = [
                    value.strip() for value in _text(source["资料引用"]).replace("；", ";").split(";") if value.strip()
                ]
            if item:
                current = item.design_revisions.order_by("-revision").first()
                changes.append({
                    "stableProductId": stable_id,
                    "fromVersion": item.version,
                    "toFields": sorted(design_data),
                    "createsRevision": bool(design_data),
                    "currentRevision": current.revision if current else None,
                })
            normalized = {
                "operation": operation, "stableProductId": stable_id,
                "orderLineNo": int(source["订单行号"]) if str(source["订单行号"] or "").isdigit() else None,
                "itemName": _text(source["来源名称"]),
                "installationPosition": _text(source["空间/安装位置"]),
                "physicalQuantity": source["实物数量"],
                "physicalUomId": uom.pk if uom else None,
                "physicalUomCode": _text(source["实物单位"]),
                "designUomId": design_uom.pk if design_uom else None,
                "productCategoryId": category.pk if category else None,
                "productCategoryCode": _text(source["产品分类"]),
                "designLength": design_data.get("designLength"),
                "designWidth": design_data.get("designWidth"),
                "designThickness": design_data.get("designThickness"),
                "dimensionSemantic": dimension_semantic,
                "designData": design_data, "reason": _text(source["修订原因"]),
            }
            rows.append({
                "rowNumber": row_no, "operation": operation,
                "stableProductId": stable_id, "itemName": normalized["itemName"],
                "valid": not errors, "errors": errors, "changes": changes,
                "normalized": normalized,
            })
    finally:
        workbook.close()
    canonical = [{key: value for key, value in row.items() if key != "changes"} for row in rows]
    fingerprint = sha256(json.dumps({
        "companyId": company_id, "orderId": order.pk,
        "fileSha256": sha256(content).hexdigest(), "rows": canonical,
    }, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return {
        "worksheetName": WORKSHEET_NAME, "orderNo": order.order_no,
        "rows": rows, "rowCount": len(rows),
        "validCount": sum(1 for row in rows if row["valid"]),
        "errorCount": sum(1 for row in rows if not row["valid"]),
        "previewFingerprint": fingerprint,
        "fileSha256": sha256(content).hexdigest(),
    }


@transaction.atomic
def commit_product_design_import(*, uploaded_file, user, preview_fingerprint, idempotency_key, confirmed):
    if not confirmed:
        raise ProductDesignError("PRODUCT_DESIGN_IMPORT_CONFIRMATION_REQUIRED", "正式导入前必须确认预览变化。")
    if not _text(idempotency_key):
        raise ProductDesignError("IDEMPOTENCY_KEY_REQUIRED", "正式导入必须提供幂等键。")
    preview = parse_product_design_import(uploaded_file, user.company_id)
    if preview["previewFingerprint"] != _text(preview_fingerprint):
        raise ProductDesignError("PRODUCT_DESIGN_IMPORT_PREVIEW_CHANGED", "文件或当前订单已变化，请重新预览。", 409)
    if preview["errorCount"] or not preview["rows"]:
        raise ProductDesignError("PRODUCT_DESIGN_IMPORT_ERRORS", "导入预览存在错误或没有业务行，禁止提交。", 409)
    results = []
    for row in preview["rows"]:
        normalized = row["normalized"]
        row_key = f"{idempotency_key}:row-{row['rowNumber']}"
        if normalized["operation"] == "新增":
            facts, replayed = add_product_design_item(
                user=user, payload=normalized, idempotency_key=row_key,
            )
        else:
            item = ProductDesignItem.objects.get(
                company_id=user.company_id, item_no=normalized["stableProductId"],
            )
            facts, replayed = save_design_content(
                user=user,
                payload={
                    "designItemIds": [item.pk],
                    "expectedVersions": {str(item.pk): item.version},
                    "designNature": "FORMAL", "designData": normalized["designData"],
                    "reason": normalized["reason"],
                },
                idempotency_key=row_key,
            )
        results.append({
            "rowNumber": row["rowNumber"], "operation": normalized["operation"],
            "stableProductId": normalized["stableProductId"], "idempotentReplay": replayed,
        })
    return {
        "success": True, "previewFingerprint": preview["previewFingerprint"],
        "committedCount": len(results), "results": results,
        "readback": product_design_facts(user.company_id, user=user),
    }

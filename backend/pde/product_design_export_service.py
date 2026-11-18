from hashlib import sha256
from io import BytesIO
import json

from django.db import transaction
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from system.models import OrganizationOperatingAuditRecord

from .product_design_service import (
    ProductDesignError,
    product_design_facts,
    product_design_list_field_contract,
)


EXPORT_ACTION = "production.product_design.export"


def _excel_safe(value):
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return value


@transaction.atomic
def export_product_design_excel(*, user, payload):
    requested_ids = payload.get("designItemIds")
    if not isinstance(requested_ids, list) or not requested_ids:
        raise ProductDesignError("PRODUCT_DESIGN_EXPORT_SCOPE_REQUIRED", "当前筛选结果为0条，未生成空导出文件。")
    if len(requested_ids) != len(set(map(str, requested_ids))):
        raise ProductDesignError("PRODUCT_DESIGN_EXPORT_SCOPE_INVALID", "导出范围包含重复产品标识。")
    facts = product_design_facts(user.company_id, user=user)
    indexed = {str(row["id"]): row for row in facts["rows"]}
    ordered = []
    for raw_id in requested_ids:
        row = indexed.get(str(raw_id))
        if not row:
            raise ProductDesignError("PRODUCT_DESIGN_EXPORT_SCOPE_INVALID", "导出范围包含不属于当前企业或当前订单的产品。", 403)
        ordered.append(row)
    expected = payload.get("expectedVersions") or {}
    stale = [row["itemNo"] for row in ordered if str(expected.get(str(row["id"]), row["version"])) != str(row["version"])]
    if stale:
        raise ProductDesignError("PRODUCT_DESIGN_EXPORT_STALE", "导出前数据已更新，请刷新列表后重试。", 409, {"staleItems": stale})

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "产品设计当前结果"
    field_contract = product_design_list_field_contract()
    sheet.append([field["label"] for field in field_contract])
    for row in ordered:
        values = row.get("listValues") or {}
        sheet.append([_excel_safe(values.get(field["key"])) for field in field_contract])
    for cell in sheet[1]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = PatternFill("solid", fgColor="1F4E78")
        cell.alignment = Alignment(horizontal="center", vertical="center")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        width = min(max(len(str(cell.value or "")) for cell in column) + 2, 42)
        sheet.column_dimensions[column[0].column_letter].width = max(width, 12)
    metadata = workbook.create_sheet("字段说明")
    metadata.append(["字段名称", "业务含义", "数据来源", "是否允许编辑", "是否允许导入", "主数据来源"])
    for field in field_contract:
        metadata.append([
            field["label"], field["businessMeaning"], field["source"],
            "是" if field["editable"] else "否",
            "是" if field["importable"] else "否",
            field["masterSource"],
        ])
    for cell in metadata[1]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = PatternFill("solid", fgColor="1F4E78")
        cell.alignment = Alignment(horizontal="center", vertical="center")
    metadata.freeze_panes = "A2"
    metadata.auto_filter.ref = metadata.dimensions
    for column in metadata.columns:
        width = min(max(len(str(cell.value or "")) for cell in column) + 2, 52)
        metadata.column_dimensions[column[0].column_letter].width = max(width, 14)
    stream = BytesIO()
    workbook.save(stream)
    content = stream.getvalue()
    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code=EXPORT_ACTION, actor=user, organization_id=user.company_id,
        target_type="ProductDesignExport", target_id=ordered[0]["id"],
        target_label=f"{len(ordered)}项产品设计当前结果",
        reason="用户导出当前筛选、排序后的产品设计Excel。",
        before_snapshot={"businessWrite": False, "filterSummary": payload.get("filterSummary"), "sortSummary": payload.get("sortSummary")},
        after_snapshot={"recordCount": len(ordered), "businessKeys": [row["itemNo"] for row in ordered], "format": "xlsx", "sha256": sha256(content).hexdigest().upper()},
    )
    return content, audit

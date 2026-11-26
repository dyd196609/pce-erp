"""Formal product-design planning, content and completion service."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import uuid

from django.db import transaction
from django.db.models import Q

from masterdata.models import ExternalIdentity, MasterDataWriteRequest, Material, UnitOfMeasure
from pfm.models import Employee
from system.authorization import AuthorizationService
from system.models import OrganizationOperatingAuditRecord
from sales.models import SalesOrder, SalesOrderItemEngineeringAttribute
from workflow_runtime.models import ApprovalDecision, WorkflowInstance

from .models import (
    EngineeringBreakdownOption, EngineeringSourceRecord, ManufacturingProcessType,
    ProductCategory, ProductDefinition, ProductDesignCompletionRecord,
    OrderCrossFunctionalReview, ProductDesignItem, ProductDesignPlanRevision,
    ProductDesignRevision, Routing,
)
from .crm_order_admission import CRMOrderAdmissionError, require_crm_order_admission
from .order_demand_preparation_service import (
    OrderDemandPreparationError, _target_facts, requirement_facts,
)
from .engineering_condition_options import normalize_visible_condition, visible_condition_options


PERMISSION_CODE = "production.engineering.source.maintain"
SOURCE_PREFIX = "PCE-PRODUCT-DESIGN"
ACTION_INITIALIZE = "pde.product_design.items.initialize"
ACTION_PLAN_SAVE = "pde.product_design.plan.save"
ACTION_DESIGN_SAVE = "pde.product_design.content.save"
ACTION_COMPLETE = "pde.product_design.completion.record"
ACTION_ITEM_ADD = "pde.product_design.item.add"
ACTION_ITEM_DELETE = "pde.product_design.item.delete"
ACTION_CONFIRMED_CORRECTIONS = "pde.product_design.confirmed_source_corrections.apply"
REGISTERED_WORKBOOK_SHA256 = "7ED132C13F6F7B13F5805F3872EC06528D9342A8E821A4D6F3D8B571243FB122"
TRI_SHEET = "三合一生产单"
INSTALLATION_MERGE_RANGES = (
    (7, 18, "图1\n厨房", "F7:F18"),
    (19, 21, "图3\n厨房", "F19:F21"),
    (22, 23, "图3厨房", "F22:F23"),
    (24, 30, "图3厨房", "F24:F30"),
    (31, 35, "图5\n主卧衣柜", "F31:F35"),
    (37, 39, "图9\n电视柜", "F37:F39"),
    (40, 48, "图9\n电视柜", "F40:F48"),
    (49, 54, "图11\n阳台吊柜", "F49:F54"),
    (55, 61, "图12\n阳台高柜", "F55:F61"),
    (62, 70, "图13入户鞋柜", "F62:F70"),
    (71, 72, "图14\n客厅背景", "F71:F72"),
)
EXPLICIT_DOOR_COMPONENTS = frozenset({
    "单开门", "双开门", "造型柜门", "平板柜门", "格栅柜门", "玻璃柜门",
})
ALLOWED_DESIGN_FIELDS = (
    "designLength", "designWidth", "designThickness", "materialId",
    "productCategoryId", "productDefinitionId", "physicalUomId", "designUomId",
    "materialProcessTypeId", "paintProcessTypeId", "edgeMethodId",
    "processConfigurationId",
    "finishOrColor", "colorVersionOptionId", "visibleCondition", "visibleConditionCode",
    "configurationNotes", "designNotes",
    "hardware", "glass", "documentReferences", "calculationInputs", "finishedGoodsSubstitution",
)

# The page list and the Excel export consume this exact server-owned contract.
# Keep labels and order here so neither surface can invent a second projection.
PRODUCT_DESIGN_LIST_FIELD_CONTRACT = (
    {"key": "productIdentifier", "label": "产品标识", "source": "ProductDesignItem.item_no", "editable": False, "importable": False, "masterSource": "ProductDesignItem"},
    {"key": "orderLine", "label": "所属订单行", "source": "SalesOrder.order_no + SalesOrderItem.line_no", "editable": False, "importable": False, "masterSource": "SalesOrder / SalesOrderItem"},
    {"key": "designGroup", "label": "设计分组", "source": "SalesOrderItem.line_no 受控映射", "editable": False, "importable": False, "masterSource": "PDE设计分组规则"},
    {"key": "productName", "label": "来源名称", "source": "ProductDesignItem.item_name", "editable": False, "importable": True, "masterSource": "ProductDesignItem"},
    {"key": "installationPosition", "label": "空间/安装位置", "source": "ProductDesignItem安装位置/空间快照", "editable": False, "importable": True, "masterSource": "工程来源记录"},
    {"key": "sourcePosition", "label": "来源位置", "source": "EngineeringSourceRecord来源Sheet/行", "editable": False, "importable": False, "masterSource": "EngineeringSourceRecord"},
    {"key": "physicalQuantity", "label": "实物数量", "source": "ProductDesignItem.physical_quantity", "editable": False, "importable": True, "masterSource": "ProductDesignItem"},
    {"key": "commercialQuantity", "label": "商业数量", "source": "SalesOrderItem.quantity", "editable": False, "importable": False, "masterSource": "SalesOrderItem"},
    {"key": "physicalUnit", "label": "实物单位", "source": "ProductDesignItem.physical_uom/快照", "editable": True, "importable": True, "masterSource": "UnitOfMeasure", "inputKey": "physicalUomId", "section": "数量与实物单位", "singleEditable": True, "batchEditable": True},
    {"key": "productCategory", "label": "产品分类", "source": "ProductDesignItem.product_category", "editable": True, "importable": True, "masterSource": "ProductCategory"},
    {"key": "formalProductDefinition", "label": "正式产品定义", "source": "ProductDesignItem.product_definition（仅持久化显式关联）", "editable": True, "importable": False, "masterSource": "ProductDefinition"},
    {"key": "engineeringIdentityStatus", "label": "工程对象状态", "source": "Customer Engineering服务端事实派生", "editable": False, "importable": False, "masterSource": "ProductDesignItem / EngineeringSourceRecord"},
    {"key": "materialCode", "label": "材料编码", "source": "当前ProductDesignRevision.material/来源匹配", "editable": True, "importable": True, "masterSource": "masterdata.Material"},
    {"key": "materialName", "label": "材料名称", "source": "当前ProductDesignRevision.material/来源匹配", "editable": True, "importable": True, "masterSource": "masterdata.Material"},
    {"key": "materialSpecification", "label": "物料规格", "source": "当前ProductDesignRevision.material/来源匹配", "editable": True, "importable": True, "masterSource": "masterdata.Material"},
    {"key": "processConfigurationCode", "label": "Routing编码", "source": "当前ProductDesignRevision Routing快照/来源值", "editable": True, "importable": True, "masterSource": "pde.Routing"},
    {"key": "processConfigurationName", "label": "Routing名称", "source": "当前ProductDesignRevision Routing快照/正式匹配", "editable": True, "importable": True, "masterSource": "pde.Routing"},
    {"key": "paintProcessCode", "label": "油漆工艺编码", "source": "当前ProductDesignRevision.paint_process_type/来源匹配", "editable": True, "importable": True, "masterSource": "ManufacturingProcessType"},
    {"key": "paintProcessName", "label": "油漆工艺名称", "source": "当前ProductDesignRevision.paint_process_type/来源匹配", "editable": True, "importable": True, "masterSource": "ManufacturingProcessType"},
    {"key": "edgeMethod", "label": "封边方式", "source": "当前ProductDesignRevision.edge_method/来源值", "editable": True, "importable": True, "masterSource": "EngineeringBreakdownOption"},
    {"key": "visibleCondition", "label": "见光条件", "source": "当前ProductDesignRevision.design_data/来源值", "editable": True, "importable": True, "masterSource": "PDE见光条件治理选项"},
    {"key": "colorVersion", "label": "颜色/版号", "source": "当前ProductDesignRevision.design_data/来源受控候选", "editable": True, "importable": True, "masterSource": "产品设计来源受控候选"},
    {"key": "designDimensionUnit", "label": "设计尺寸单位", "source": "当前ProductDesignRevision.design_uom", "editable": True, "importable": True, "masterSource": "UnitOfMeasure", "inputKey": "designUomId", "section": "设计尺寸", "singleEditable": True, "batchEditable": True},
    {"key": "designLength", "label": "设计长度", "source": "当前ProductDesignRevision/已有设计资料", "editable": True, "importable": True, "masterSource": "ProductDesignRevision"},
    {"key": "designWidth", "label": "设计宽度", "source": "当前ProductDesignRevision/已有设计资料", "editable": True, "importable": True, "masterSource": "ProductDesignRevision"},
    {"key": "thirdDimension", "label": "第三尺寸", "source": "当前ProductDesignRevision/已有设计资料", "editable": True, "importable": True, "masterSource": "ProductDesignRevision"},
    {"key": "thirdDimensionSemantic", "label": "第三尺寸语义", "source": "Customer Engineering来源及当前设计事实", "editable": False, "importable": True, "masterSource": "ProductDesignItem.existing_design_data"},
    {"key": "configurationNotes", "label": "配置说明", "source": "当前ProductDesignRevision.design_data/已有设计资料", "editable": True, "importable": True, "masterSource": "ProductDesignRevision"},
    {"key": "designNotes", "label": "设计说明", "source": "当前ProductDesignRevision.design_data/已有设计资料", "editable": True, "importable": True, "masterSource": "ProductDesignRevision"},
    {"key": "hardware", "label": "五金要求", "source": "当前ProductDesignRevision.design_data/已有设计资料", "editable": True, "importable": True, "masterSource": "ProductDesignRevision"},
    {"key": "glass", "label": "玻璃要求", "source": "当前ProductDesignRevision.design_data/已有设计资料", "editable": True, "importable": True, "masterSource": "ProductDesignRevision"},
    {"key": "documentReferences", "label": "资料引用", "source": "当前ProductDesignRevision.design_data/已有设计资料", "editable": True, "importable": True, "masterSource": "ProductDesignRevision"},
    {"key": "designDataNatureLabel", "label": "设计资料性质", "source": "当前ProductDesignRevision.design_nature/ProductDesignItem.design_data_nature", "editable": False, "importable": False, "masterSource": "ProductDesignRevision / ProductDesignItem"},
    {"key": "currentRevisionReason", "label": "当前修订原因", "source": "当前ProductDesignRevision.change_reason", "editable": False, "importable": False, "masterSource": "ProductDesignRevision"},
    {"key": "designer", "label": "设计负责人", "source": "当前ProductDesignPlanRevision.designer_employee", "editable": True, "importable": False, "masterSource": "pfm.Employee"},
    {"key": "plannedStartDate", "label": "设计计划开工日期", "source": "当前订单及设计分组最新ProductDesignPlanRevision.planned_start_date", "editable": False, "importable": False, "masterSource": "ProductDesignPlanRevision"},
    {"key": "plannedFinishDate", "label": "设计计划完工日期", "source": "当前订单及设计分组最新ProductDesignPlanRevision.planned_finish_date", "editable": False, "importable": False, "masterSource": "ProductDesignPlanRevision"},
    {"key": "designStatus", "label": "设计状态", "source": "计划与当前设计修订服务端派生", "editable": False, "importable": False, "masterSource": "ProductDesignPlanRevision / ProductDesignRevision"},
    {"key": "designRevisionLabel", "label": "设计修订号", "source": "当前ProductDesignRevision.revision", "editable": False, "importable": False, "masterSource": "ProductDesignRevision"},
    {"key": "completionStatus", "label": "完成状态", "source": "当前ProductDesignCompletionRecord服务端派生", "editable": False, "importable": False, "masterSource": "ProductDesignCompletionRecord"},
)

PRODUCT_DESIGN_FIELD_BUSINESS_MEANINGS = {
    "productIdentifier": "当前订单内稳定识别具体产品设计项的业务标识。",
    "orderLine": "该设计项所属的销售订单及订单行。",
    "designGroup": "该设计项所属的订单级产品设计分组（DES-01/DES-02/DES-03/DES-04）。",
    "productName": "订单工程来源中的产品或部件名称；不是正式产品定义。",
    "installationPosition": "设计对象在项目中的空间或安装位置。",
    "sourcePosition": "该设计事实可追溯到的原始来源工作表及行号。",
    "physicalQuantity": "实际需要设计、生产的对象数量；不得与销售合同数量混算。",
    "commercialQuantity": "销售合同约定的商业数量；不得与具体设计对象数量混算。",
    "physicalUnit": "实物数量使用的正式计量单位；不得用于解释设计尺寸。",
    "productCategory": "用于产品设计及 Routing 适用关系判断的正式产品分类。",
    "formalProductDefinition": "显式持久化关联的正式产品定义；来源名称不得自动填入。",
    "engineeringIdentityStatus": "区分已关联正式产品、来源产品待正式化和客户定制工程对象。",
    "materialCode": "正式材料主数据编码。",
    "materialName": "正式材料主数据名称。",
    "materialSpecification": "正式材料主数据规格；不得复用油漆工艺字段。",
    "processConfigurationCode": "适用于当前产品分类或产品的已发布 Routing 编码。",
    "processConfigurationName": "适用于当前产品分类或产品的已发布 Routing 名称。",
    "paintProcessCode": "独立于 Routing 的正式油漆工艺编码。",
    "paintProcessName": "独立于 Routing 的正式油漆工艺名称。",
    "edgeMethod": "产品设计要求的封边方式。",
    "visibleCondition": "产品设计要求的见光条件。",
    "colorVersion": "产品设计使用的颜色或版号；没有正式主档时保留受控来源值。",
    "designLength": "当前产品设计长度。",
    "designWidth": "当前产品设计宽度。",
    "thirdDimension": "按产品类型表达墙厚、部件厚或实际厚度的第三尺寸。",
    "thirdDimensionSemantic": "说明第三尺寸在当前设计对象中表达墙厚、部件厚或实际厚度；由既有工程来源确定。",
    "designDimensionUnit": "设计长度、设计宽度及适用第三尺寸的正式计量单位；不得用于表达产品数量。",
    "configurationNotes": "当前产品设计的配置约束及补充说明。",
    "designNotes": "当前产品设计说明。",
    "hardware": "当前产品设计中的五金要求；无正式主档时保留受控来源值。",
    "glass": "当前产品设计中的玻璃要求；无正式主档时保留受控来源值。",
    "documentReferences": "与当前产品设计关联的图纸、文件或其它资料引用。",
    "designDataNatureLabel": "区分正式设计修订、已有设计资料带入和开发演练模拟设计。",
    "currentRevisionReason": "当前有效设计修订形成时记录的业务原因。",
    "designer": "当前订单设计分组已登记的设计负责人。",
    "plannedStartDate": "当前订单同一设计分组最新有效计划的计划开工日期；未登记时如实为空。",
    "plannedFinishDate": "当前订单同一设计分组最新有效计划的计划完工日期；未登记时如实为空。",
    "designStatus": "由服务端计划与设计修订事实派生的设计状态。",
    "designRevisionLabel": "当前有效产品设计修订号。",
    "completionStatus": "由服务端设计完成记录派生的完成状态。",
}
PRODUCT_DESIGN_FIELD_RUNTIME = {
    "productCategory": {"inputKey": "productCategoryId", "section": "对象身份、来源与产品关联", "singleEditable": True, "batchEditable": True},
    "formalProductDefinition": {"inputKey": "productDefinitionId", "section": "对象身份、来源与产品关联", "singleEditable": True, "batchEditable": False},
    "physicalQuantity": {"section": "数量与实物单位"},
    "commercialQuantity": {"section": "数量与实物单位"},
    "materialCode": {"inputKey": "materialId", "section": "材料", "singleEditable": True, "batchEditable": True},
    "materialName": {"inputKey": "materialId", "section": "材料", "singleEditable": True, "batchEditable": True},
    "materialSpecification": {"inputKey": "materialId", "section": "材料", "singleEditable": True, "batchEditable": True},
    "processConfigurationCode": {"inputKey": "processConfigurationId", "section": "工艺配置及独立油漆工艺", "singleEditable": True, "batchEditable": True},
    "processConfigurationName": {"inputKey": "processConfigurationId", "section": "工艺配置及独立油漆工艺", "singleEditable": True, "batchEditable": True},
    "paintProcessCode": {"inputKey": "paintProcessTypeId", "section": "工艺配置及独立油漆工艺", "singleEditable": True, "batchEditable": True},
    "paintProcessName": {"inputKey": "paintProcessTypeId", "section": "工艺配置及独立油漆工艺", "singleEditable": True, "batchEditable": True},
    "edgeMethod": {"inputKey": "edgeMethodId", "section": "其它现有设计内容", "singleEditable": True, "batchEditable": True},
    "visibleCondition": {"inputKey": "visibleConditionCode", "section": "其它现有设计内容", "singleEditable": True, "batchEditable": True},
    "colorVersion": {"inputKey": "colorVersionOptionId", "section": "其它现有设计内容", "singleEditable": True, "batchEditable": True},
    "designLength": {"inputKey": "designLength", "section": "设计尺寸", "singleEditable": True, "batchEditable": True},
    "designWidth": {"inputKey": "designWidth", "section": "设计尺寸", "singleEditable": True, "batchEditable": True},
    "thirdDimension": {"inputKey": "designThickness", "section": "设计尺寸", "singleEditable": True, "batchEditable": True},
    "thirdDimensionSemantic": {"section": "设计尺寸", "singleEditable": False, "batchEditable": False},
    "configurationNotes": {"inputKey": "configurationNotes", "section": "其它现有设计内容", "singleEditable": True, "batchEditable": True},
    "designNotes": {"inputKey": "designNotes", "section": "设计说明、修订原因和历史追溯", "singleEditable": True, "batchEditable": True},
    "hardware": {"inputKey": "hardware", "section": "其它现有设计内容", "singleEditable": True, "batchEditable": True},
    "glass": {"inputKey": "glass", "section": "其它现有设计内容", "singleEditable": True, "batchEditable": True},
    "documentReferences": {"inputKey": "documentReferences", "section": "其它现有设计内容", "singleEditable": True, "batchEditable": True},
    "designDataNatureLabel": {"section": "设计说明、修订原因和历史追溯"},
    "currentRevisionReason": {"section": "设计说明、修订原因和历史追溯"},
    "designer": {"section": "设计说明、修订原因和历史追溯", "singleEditable": False, "batchEditable": False},
    "plannedStartDate": {"section": "设计计划只读投影", "singleEditable": False, "batchEditable": False},
    "plannedFinishDate": {"section": "设计计划只读投影", "singleEditable": False, "batchEditable": False},
    "designStatus": {"section": "设计说明、修订原因和历史追溯"},
    "designRevisionLabel": {"section": "设计说明、修订原因和历史追溯"},
    "completionStatus": {"section": "设计说明、修订原因和历史追溯"},
}
_UNSET = object()


class ProductDesignError(ValueError):
    def __init__(self, code, message, http_status=400, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}


def _canonical_hash(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


def _source_no(company_id, item_id):
    return f"{SOURCE_PREFIX}-{company_id}-{item_id}"


def _employee_company_id(employee):
    if employee.position_ref_id:
        return employee.position_ref.company_id
    if employee.department_ref_id:
        return employee.department_ref.company_id
    return None


def _employee_snapshot(employee):
    position = employee.position_ref
    department = employee.department_ref
    return {
        "employeeId": employee.pk, "employeeNo": employee.employee_no,
        "fullName": employee.full_name,
        "departmentName": department.name if department else (employee.department_name or ""),
        "positionName": position.name if position else (employee.position or ""),
        "statusLabel": employee.get_status_display(),
    }


def _designer_options(source, company_id):
    payload = source.source_payload if isinstance(source.source_payload, dict) else {}
    confirmed = payload.get("confirmedResponsibilityFacts") or {}
    candidates, seen = [], set()
    for key in ("designer", "breakdownOwner"):
        employee_id = (confirmed.get(key) or {}).get("employeeId")
        if not employee_id or employee_id in seen:
            continue
        employee = Employee.objects.select_related("position_ref", "department_ref").filter(
            pk=employee_id, status="active",
        ).first()
        if not employee or _employee_company_id(employee) != company_id:
            continue
        if employee.position_ref_id and not employee.position_ref.is_active:
            continue
        seen.add(employee_id)
        candidates.append(_employee_snapshot(employee))
    return candidates


def _raw(attribute):
    return attribute.raw_value if isinstance(attribute.raw_value, dict) else {}


def _evidence(raw, code):
    values = raw.get("sourceEvidence") if isinstance(raw.get("sourceEvidence"), dict) else {}
    value = values.get(code)
    return value.get("value") if isinstance(value, dict) else None


def _match_exact(queryset, value, *, fields=("code", "name")):
    text = str(value or "").strip()
    if not text:
        return {"status": "NO_SOURCE_VALUE", "sourceValue": text, "matchedId": None, "candidateIds": []}
    matches = []
    for field in fields:
        matches.extend(queryset.filter(**{field: text}).values_list("pk", flat=True))
    ids = sorted(set(matches))
    if len(ids) == 1:
        return {"status": "EXACT", "sourceValue": text, "matchedId": ids[0], "candidateIds": ids}
    if not ids:
        return {"status": "NO_MATCH", "sourceValue": text, "matchedId": None, "candidateIds": []}
    return {"status": "MULTIPLE_MATCHES", "sourceValue": text, "matchedId": None, "candidateIds": ids}


def _match_material_source(company_id, value):
    """Resolve a source material code through formal code or persisted identity.

    Product-design source codes are not necessarily formal ``Material.code``
    values.  A persisted ExternalIdentity is the stable cross-source identity;
    names and specifications remain mutable master-data payload and therefore
    must not participate in identity resolution.
    """
    text = str(value or "").strip()
    if not text:
        return {
            "status": "NO_SOURCE_VALUE", "sourceValue": text,
            "matchedId": None, "candidateIds": [], "identityIds": [],
        }

    materials = Material.objects.filter(company_id=company_id, is_active=True)
    direct = _match_exact(materials, text)
    direct_ids = set(direct.get("candidateIds") or [])
    identities = list(ExternalIdentity.objects.filter(
        organization_id=company_id,
        source_system="PCE_FOUNDATION_WAVE1",
        source_type="APPROVED_XLSX",
        target_entity_type="materials",
        external_id__endswith=f"|CODE:{text}",
    ).order_by("pk"))

    applicable = []
    invalid_identity_ids = []
    for identity in identities:
        metadata = identity.audit_metadata if isinstance(identity.audit_metadata, dict) else {}
        if str(metadata.get("sourceCode") or "").strip() != text:
            invalid_identity_ids.append(identity.pk)
            continue
        if identity.mapping_status != ExternalIdentity.MappingStatus.MATCH:
            invalid_identity_ids.append(identity.pk)
            continue
        target_id = str(identity.target_entity_id or "").strip()
        if not target_id.isdigit() or not materials.filter(pk=int(target_id)).exists():
            invalid_identity_ids.append(identity.pk)
            continue
        applicable.append((identity.pk, int(target_id)))

    identity_ids = [identity_id for identity_id, _ in applicable]
    identity_target_ids = {target_id for _, target_id in applicable}
    candidate_ids = sorted(direct_ids | identity_target_ids)
    if invalid_identity_ids:
        return {
            "status": "IDENTITY_INTEGRITY_ERROR", "sourceValue": text,
            "matchedId": None, "candidateIds": candidate_ids,
            "identityIds": identity_ids,
            "invalidIdentityIds": invalid_identity_ids,
        }
    if len(candidate_ids) == 1:
        matched_id = candidate_ids[0]
        return {
            "status": "IDENTITY_MATCH" if identity_target_ids else "EXACT",
            "sourceValue": text, "matchedId": matched_id,
            "candidateIds": candidate_ids, "identityIds": identity_ids,
            "matchMethod": "EXTERNAL_IDENTITY" if identity_target_ids else "FORMAL_CODE_OR_NAME",
        }
    if not candidate_ids:
        return {
            "status": "NO_MATCH", "sourceValue": text,
            "matchedId": None, "candidateIds": [], "identityIds": [],
        }
    return {
        "status": "MULTIPLE_MATCHES", "sourceValue": text,
        "matchedId": None, "candidateIds": candidate_ids,
        "identityIds": identity_ids,
    }


def _process_configuration_id(code):
    text = str(code or "").strip()
    return f"SOURCE-PROCESS-CONFIG-{sha256(text.encode('utf-8')).hexdigest()[:16].upper()}"


def _formal_routing_queryset(company_id):
    today = date.today()
    return Routing.objects.filter(
        company_id=company_id,
        is_active=True,
        status="released",
    ).filter(
        Q(effective_from__isnull=True) | Q(effective_from__lte=today),
        Q(effective_to__isnull=True) | Q(effective_to__gte=today),
    ).select_related("product_category", "product", "manufacturing_process_type")


def _formal_product_definition_queryset(company_id):
    today = date.today()
    return ProductDefinition.objects.filter(
        company_id=company_id, is_active=True, status="released",
    ).filter(
        Q(effective_from__isnull=True) | Q(effective_from__lte=today),
        Q(effective_to__isnull=True) | Q(effective_to__gte=today),
    ).select_related("category")


def _source_process_configuration(item):
    data = item.existing_design_data if isinstance(item.existing_design_data, dict) else {}
    code = str(data.get("routingProcessCode") or "").strip()
    if not code:
        return {"id": None, "code": "", "label": "", "source": "source-empty"}
    applicable = Q(pk__isnull=True)
    if item.product_category_id:
        applicable |= Q(applicability_scope="PRODUCT_CATEGORY", product_category_id=item.product_category_id)
    if item.product_definition_id:
        applicable |= Q(applicability_scope="PRODUCT_DEFINITION", product_id=item.product_definition_id)
    routes = list(_formal_routing_queryset(item.company_id).filter(applicable, routing_code=code)[:2])
    if len(routes) == 1:
        route = routes[0]
        return {
            "id": str(route.pk), "routeId": route.pk, "code": route.routing_code,
            "label": route.name or route.routing_code, "source": "pde.Routing",
        }
    return {
        "id": _process_configuration_id(code),
        "code": code, "label": code, "source": "existing-design-source-unmatched",
    }


def _source_projection(attribute, source, company_id):
    raw = _raw(attribute)
    product = str(raw.get("product") or "").strip()
    component = str(raw.get("component") or "").strip()
    unit = str(raw.get("unitName") or raw.get("unit") or "").strip()
    material_code = str(raw.get("materialProcessCode") or "").strip()
    routing_code = str(raw.get("routingProcessCode") or "").strip()
    paint = str(_evidence(raw, "I") or "").strip()
    edge = str(raw.get("edgeMode") or "").strip()
    category_match = _match_exact(ProductCategory.objects.filter(company_id=company_id, is_active=True), product)
    # A source name is Customer Engineering evidence, not a ProductDefinition identity.
    # Formal products may only be linked by an explicit, validated user action.
    product_definition_match = {
        "status": "SOURCE_IDENTITY_ONLY" if product else "NO_SOURCE_VALUE",
        "sourceValue": product,
        "matchedId": None,
        "candidateIds": [],
    }
    uom_match = _match_exact(UnitOfMeasure.objects.filter(company_id=company_id, is_active=True), unit)
    material_match = _match_material_source(company_id, material_code)
    paint_match = _match_exact(ManufacturingProcessType.objects.filter(company_id=company_id, is_active=True), paint)
    edge_match = _match_exact(
        EngineeringBreakdownOption.objects.filter(
            company_id=company_id, is_active=True,
            option_type=EngineeringBreakdownOption.OptionType.EDGE_METHOD,
        ), edge,
    )
    provenance = {
        "sourceFile": attribute.raw_source, "sourceSheet": attribute.raw_sheet,
        "sourceRow": raw.get("sourceRow"),
        "sourceObject": attribute.external_source or f"ATTR-{attribute.pk}",
        "sourceVersion": source.source_version, "sourceContentHash": source.content_hash,
        "rawValue": raw,
    }
    original = {
        "customerRequirement": raw.get("customerRequirement") or "",
        "space": raw.get("space") or "",
        "installationPosition": raw.get("installationPosition") or raw.get("space") or "",
        "physicalQuantity": raw.get("quantity"), "physicalUnit": unit,
        "sourceProduct": product, "sourceComponent": component,
        "provenance": provenance,
    }
    design = {
        "designLength": raw.get("length"), "designWidth": raw.get("width"),
        "designThickness": raw.get("thickness"), "materialProcessCode": material_code,
        "routingProcessCode": routing_code, "paintProcess": paint,
        "finishOrColor": _evidence(raw, "AD") or _evidence(raw, "V") or "",
        "visibleCondition": raw.get("visibleCondition") or "",
        "edgeMethod": edge, "processingNote": raw.get("processingNote") or "",
        "hardware": raw.get("hardware") or "", "glass": raw.get("glass") or "",
        "provenance": provenance,
    }
    matches = {
        "productCategory": category_match, "productDefinition": product_definition_match,
        "physicalUom": uom_match,
        "material": material_match,
        "processConfiguration": {
            "status": "SOURCE_EXACT" if routing_code else "NO_SOURCE_VALUE",
            "sourceValue": routing_code,
            "matchedId": _process_configuration_id(routing_code) if routing_code else None,
            "candidateIds": [_process_configuration_id(routing_code)] if routing_code else [],
        },
        "materialProcess": {
            "status": "NOT_USED_FOR_FULL_CONFIGURATION",
            "sourceValue": routing_code, "matchedId": None, "candidateIds": [],
        },
        "paintProcess": paint_match, "edgeMethod": edge_match,
    }
    return original, design, provenance, matches


def _authorize(user, action_code):
    decision = AuthorizationService.decide(
        user=user, action_code=PERMISSION_CODE, organization_id=user.company_id,
        business_object={"organizationId": user.company_id},
        context={"actionType": action_code, "businessWrite": True},
    )
    if not decision.get("allowed"):
        raise ProductDesignError(
            decision.get("decisionCode", "PERMISSION_DENIED"),
            decision.get("reason", "当前账户没有产品设计维护权限。"), 403,
        )
    return decision


def _write_request(*, user, action_code, entity_type, key, request_body):
    if not str(key or "").strip():
        raise ProductDesignError("IDEMPOTENCY_KEY_REQUIRED", "业务保存必须提供幂等键。")
    request_hash = _canonical_hash(request_body)
    scope_ids = request_body.get("itemIds") or [request_body.get("orderId") or "company"]
    scope_key = ",".join(str(value) for value in scope_ids)
    source_identity, _ = ExternalIdentity.objects.get_or_create(
        organization_id=user.company_id,
        source_system="PCE_PRODUCT_DESIGN",
        source_type="BUSINESS_ACTION_SCOPE",
        source_object_type=entity_type,
        external_id=f"{action_code}:{scope_key}",
        defaults={
            "target_entity_type": entity_type,
            "mapping_status": ExternalIdentity.MappingStatus.REVIEW,
            "source_fingerprint": _canonical_hash({"actionCode": action_code, "scope": scope_ids}),
            "audit_metadata": {"actionCode": action_code, "scope": scope_ids},
        },
    )
    record, created = MasterDataWriteRequest.objects.select_for_update().get_or_create(
        organization_id=user.company_id, action_code=action_code,
        entity_type=entity_type, idempotency_key=str(key).strip(),
        defaults={
            "request_hash": request_hash, "source_identity": source_identity,
            "audit_metadata": request_body,
        },
    )
    if not created and record.request_hash != request_hash:
        raise ProductDesignError("IDEMPOTENCY_CONFLICT", "同一幂等键已用于不同业务内容。", 409)
    return record, created, request_hash


def _commit_request(record, result):
    record.status = MasterDataWriteRequest.Status.COMMITTED
    record.result = result
    record.target_entity_id = str(result.get("targetId") or result.get("auditId") or "")
    record.save(update_fields=["status", "result", "target_entity_id", "updated_at"])


def _legacy_draft_for_group(company_id, sales_order_item_id):
    return EngineeringSourceRecord.objects.filter(
        company_id=company_id, source_no=_source_no(company_id, sales_order_item_id),
    ).order_by("-pk").first()


def _source_row_identity(item):
    raw = _raw(item.source_attribute)
    try:
        source_row = int(raw.get("sourceRow"))
    except (TypeError, ValueError):
        source_row = None
    return str(item.source_attribute.raw_sheet or ""), source_row, raw


def _installation_mapping(sheet, source_row):
    if sheet != TRI_SHEET or source_row is None:
        return None
    for first_row, last_row, value, merged_range in INSTALLATION_MERGE_RANGES:
        if first_row <= source_row <= last_row:
            return {
                "value": value, "mergedRange": merged_range,
                "topLeftCell": f"F{first_row}", "sourceRow": source_row,
            }
    return None


def _is_explicit_door(item):
    sheet, _source_row, raw = _source_row_identity(item)
    component = str(raw.get("component") or "").strip()
    source_product = str(raw.get("product") or "").strip()
    if component not in EXPLICIT_DOOR_COMPONENTS:
        return False
    if sheet == "房门单":
        return source_product == "房门"
    return sheet == TRI_SHEET and source_product == "柜体"


def _effective_surface_conditions(item):
    latest = item.design_revisions.select_related("edge_method").order_by("-revision").first()
    existing = item.existing_design_data if isinstance(item.existing_design_data, dict) else {}
    data = latest.design_data if latest and isinstance(latest.design_data, dict) else {}
    edge = latest.edge_method.name if latest and latest.edge_method_id else existing.get("edgeMethod")
    visible = data.get("visibleCondition") if latest else existing.get("visibleCondition")
    return str(edge or ""), str(visible or "")


@transaction.atomic
def apply_confirmed_source_corrections(*, user, idempotency_key):
    """Apply the confirmed merge repair and explicit door surface requirement."""
    decision = _authorize(user, ACTION_CONFIRMED_CORRECTIONS)
    order, source, review, _workflow, approval = _target_facts(user.company_id, lock=True)
    registered = (source.source_payload or {}).get("registeredSourceScope") or {}
    if registered.get("workbookSha256") != REGISTERED_WORKBOOK_SHA256:
        raise ProductDesignError(
            "PRODUCT_DESIGN_SOURCE_WORKBOOK_MISMATCH",
            "当前订单不是已核实合并区域的权威工作簿版本，禁止套用位置映射。", 409,
        )
    items = list(ProductDesignItem.objects.select_for_update().filter(
        company_id=user.company_id, sales_order_item__sales_order=order,
    ).select_related("source_attribute").prefetch_related("design_revisions__edge_method"))
    if len(items) != 71:
        raise ProductDesignError("PRODUCT_DESIGN_SCOPE_MISMATCH", "当前订单设计项不是已核实的71项范围。", 409)
    request_body = {
        "orderId": order.pk, "orderNo": order.order_no,
        "itemIds": [item.pk for item in items],
        "sourceRecordId": source.pk, "sourceVersion": source.source_version,
        "workbookSha256": REGISTERED_WORKBOOK_SHA256,
        "installationMergeRanges": [row[3] for row in INSTALLATION_MERGE_RANGES],
        "doorRequirement": {"edgeMethodCode": "EDGE-FOUR-SIDES", "visibleConditionCode": "DOUBLE_FACE"},
    }
    request, created, request_hash = _write_request(
        user=user, action_code=ACTION_CONFIRMED_CORRECTIONS,
        entity_type="ProductDesignConfirmedCorrection", key=idempotency_key,
        request_body=request_body,
    )
    if not created and request.status == MasterDataWriteRequest.Status.COMMITTED:
        return product_design_facts(user.company_id, user=user), True, request.result

    installation_impact = []
    for item in items:
        sheet, source_row, _raw_value = _source_row_identity(item)
        mapping = _installation_mapping(sheet, source_row)
        if not mapping or item.installation_position_snapshot == mapping["value"]:
            continue
        before = item.installation_position_snapshot
        original = dict(item.original_requirement or {})
        original["installationPosition"] = mapping["value"]
        original["installationPositionRepair"] = {
            "authority": "REGISTERED_WORKBOOK_MERGED_RANGE",
            "workbookSha256": REGISTERED_WORKBOOK_SHA256,
            "sourceSheet": sheet, **mapping,
            "originalCellValuePreserved": True,
        }
        item.space_snapshot = mapping["value"]
        item.installation_position_snapshot = mapping["value"]
        item.original_requirement = original
        item.version += 1
        item.save(update_fields=[
            "space_snapshot", "installation_position_snapshot", "original_requirement",
            "version", "updated_at",
        ])
        installation_impact.append({
            "designItemId": item.pk, "itemNo": item.item_no,
            "sourceSheet": sheet, "sourceRow": source_row,
            "before": before, "after": mapping["value"],
            "mergedRange": mapping["mergedRange"], "topLeftCell": mapping["topLeftCell"],
        })

    door_impact, changed_door_items = [], []
    for item in items:
        if not _is_explicit_door(item):
            continue
        sheet, source_row, raw = _source_row_identity(item)
        edge_before, visible_before = _effective_surface_conditions(item)
        changed = edge_before != "四边" or visible_before != "双"
        door_impact.append({
            "designItemId": item.pk, "itemNo": item.item_no,
            "sourceSheet": sheet, "sourceRow": source_row,
            "sourceProduct": raw.get("product"), "sourceComponent": raw.get("component"),
            "edgeBefore": edge_before, "edgeAfter": "四边",
            "visibleBefore": visible_before, "visibleAfter": "双",
            "changed": changed, "decisionBasis": "用户本次明确业务裁决",
        })
        if changed:
            changed_door_items.append(item)
    edge_method = EngineeringBreakdownOption.objects.filter(
        company_id=user.company_id, is_active=True,
        option_type=EngineeringBreakdownOption.OptionType.EDGE_METHOD,
        code="EDGE-FOUR-SIDES", name="四边",
    ).first()
    if not edge_method:
        raise ProductDesignError("EDGE_METHOD_MASTER_MISSING", "正式封边选项“四边”不存在。", 409)
    if changed_door_items:
        save_design_content(
            user=user,
            payload={
                "action": "SAVE_DESIGN",
                "designItemIds": [item.pk for item in changed_door_items],
                "expectedVersions": {str(item.pk): item.version for item in changed_door_items},
                "designNature": "FORMAL",
                "designData": {
                    "edgeMethodId": edge_method.pk,
                    "visibleConditionCode": "DOUBLE_FACE",
                },
                "reason": "用户明确裁决：所有实际门类封边=四边、见光条件=双；非门配件不适用。",
            },
            idempotency_key=f"{idempotency_key}:door-surface",
        )
    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code=ACTION_CONFIRMED_CORRECTIONS, actor=user,
        organization_id=user.company_id,
        target_type="ProductDesignConfirmedCorrection", target_id=order.pk,
        target_label=f"{order.order_no} 安装位置与门类要求补齐",
        reason="按权威工作簿合并范围恢复安装位置，并落实用户确认的实际门类四边/双面见光要求。",
        before_snapshot={
            "blankInstallationPositionCount": len(installation_impact),
            "doorRequirementChangeCount": len(changed_door_items),
        },
        after_snapshot={
            "installationImpact": installation_impact,
            "doorImpact": door_impact,
            "unchangedDoorCount": sum(1 for row in door_impact if not row["changed"]),
            "excludedSemantics": ["单面套", "双面套", "门套", "门框", "抽面", "饰面"],
            "sourceRecordId": source.pk, "sourceVersion": source.source_version,
            "reviewId": review.pk, "approvalDecisionId": approval.pk,
            "requestHash": request_hash, "authorization": decision,
        },
    )
    result = {
        "targetId": order.pk, "auditId": audit.pk,
        "installationChangedCount": len(installation_impact),
        "doorClassifiedCount": len(door_impact),
        "doorChangedCount": len(changed_door_items),
        "doorUnchangedCount": sum(1 for row in door_impact if not row["changed"]),
        "installationImpact": installation_impact, "doorImpact": door_impact,
    }
    _commit_request(request, result)
    return product_design_facts(user.company_id, user=user), False, result


@transaction.atomic
def initialize_product_design_items(*, user, idempotency_key, expected_count=71):
    decision = _authorize(user, ACTION_INITIALIZE)
    order, source, review, workflow, approval = _target_facts(user.company_id, lock=True)
    request_body = {
        "orderId": order.pk, "orderNo": order.order_no,
        "sourceRecordId": source.pk, "sourceVersion": source.source_version,
        "expectedCount": int(expected_count),
    }
    write_request, created, request_hash = _write_request(
        user=user, action_code=ACTION_INITIALIZE, entity_type="ProductDesignItemBatch",
        key=idempotency_key, request_body=request_body,
    )
    if not created and write_request.status == MasterDataWriteRequest.Status.COMMITTED:
        return product_design_facts(user.company_id, user=user), True
    order_items = list(order.items.order_by("line_no").prefetch_related("engineering_attributes"))
    source_attributes = [
        attribute for item in order_items
        for attribute in item.engineering_attributes.order_by("sequence", "pk")
    ]
    if len(source_attributes) != int(expected_count):
        raise ProductDesignError(
            "DESIGN_ITEM_COUNT_MISMATCH",
            f"来源设计项应为{expected_count}条，实际为{len(source_attributes)}条。", 409,
        )
    created_count = completion_count = 0
    d1_linked = False
    for sales_item in order_items:
        group_no = f"{order.order_no}-DES-{sales_item.line_no:02d}"
        for attribute in sales_item.engineering_attributes.order_by("sequence", "pk"):
            original, design, provenance, matches = _source_projection(attribute, source, user.company_id)
            raw = _raw(attribute)
            design_item, item_created = ProductDesignItem.objects.get_or_create(
                source_attribute=attribute,
                defaults={
                    "company_id": user.company_id, "sales_order_item": sales_item,
                    "source_record": source, "item_no": f"{group_no}-SRC-{attribute.pk:04d}",
                    "item_name": str(raw.get("component") or raw.get("product") or f"来源行{attribute.pk}"),
                    "space_snapshot": str(raw.get("space") or "")[:240],
                    "installation_position_snapshot": str(raw.get("installationPosition") or raw.get("space") or "")[:240],
                    "physical_quantity": raw.get("quantity") if raw.get("quantity") not in (None, "") else None,
                    "physical_uom_id": matches["physicalUom"]["matchedId"],
                    "physical_uom_snapshot": str(raw.get("unitName") or raw.get("unit") or "")[:80],
                    "product_category_id": matches["productCategory"]["matchedId"],
                    "product_definition_id": None,
                    "original_requirement": original, "existing_design_data": design,
                    "design_data_nature": "EXISTING_DESIGN_IMPORTED",
                    "source_version": source.source_version, "source_content_hash": source.content_hash,
                    "match_results": matches,
                },
            )
            if design_item.company_id != user.company_id or design_item.sales_order_item_id != sales_item.pk:
                raise ProductDesignError("DESIGN_ITEM_IDENTITY_CONFLICT", "稳定来源行已关联到其它设计对象。", 409)
            created_count += int(item_created)
            identity, _ = ExternalIdentity.objects.get_or_create(
                organization_id=user.company_id, source_system="PCE_PRODUCT_DESIGN",
                source_type="SOURCE_BACKED_DESIGN_ITEM",
                source_object_type="SALES_ENGINEERING_ATTRIBUTE",
                external_id=attribute.external_source or f"SalesOrderItemEngineeringAttribute:{attribute.pk}",
                defaults={
                    "target_entity_type": "ProductDesignItem", "target_entity_id": str(design_item.pk),
                    "mapping_status": ExternalIdentity.MappingStatus.MATCH,
                    "source_fingerprint": _canonical_hash(provenance),
                    "audit_metadata": {"itemNo": design_item.item_no, "sourceRecordId": source.pk},
                },
            )
            if identity.target_entity_id and identity.target_entity_id != str(design_item.pk):
                raise ProductDesignError("DESIGN_ITEM_EXTERNAL_IDENTITY_CONFLICT", "来源稳定身份已映射到其它对象。", 409)
            if not design_item.completion_records.exists():
                ProductDesignCompletionRecord.objects.create(
                    design_item=design_item, sequence=1,
                    completion_nature="HISTORICAL_EVIDENCE", actual_completion_date=None,
                    completion_basis="用户确认本单来源工作簿为已完成设计；历史实际完成日期无独立依据，保持待补。",
                    recorded_by=user, action_code=ACTION_INITIALIZE,
                )
                completion_count += 1
        legacy = _legacy_draft_for_group(user.company_id, sales_item.pk)
        if legacy:
            payload = legacy.source_payload if isinstance(legacy.source_payload, dict) else {}
            original_values = payload.get("originalValues") or []
            stable_id = (original_values[0] or {}).get("stableId") if len(original_values) == 1 else None
            candidates = ProductDesignItem.objects.filter(sales_order_item=sales_item)
            target = candidates.filter(source_attribute__external_source=stable_id).first() if stable_id else None
            target = target or (candidates.first() if candidates.count() == 1 else None)
            if not target:
                raise ProductDesignError("LEGACY_D1_TARGET_AMBIGUOUS", "既有D1无法唯一关联到具体设计项。", 409)
            revision, _ = ProductDesignRevision.objects.get_or_create(
                legacy_source_record=legacy,
                defaults={
                    "design_item": target, "revision": int(payload.get("revision") or 1),
                    "design_nature": "SIMULATED_FOR_TEST", "design_data": {},
                    "source_provenance": {
                        "legacyEngineeringSourceRecordId": legacy.pk,
                        "sourceVersion": legacy.source_version, "contentHash": legacy.content_hash,
                    },
                    "master_match_results": {},
                    "change_reason": "兼容关联既有D1；不复制、不重写原记录。", "created_by": user,
                },
            )
            if revision.design_item_id != target.pk:
                raise ProductDesignError("LEGACY_D1_LINK_CONFLICT", "既有D1已关联到其它设计项。", 409)
            d1_linked = True
    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code=ACTION_INITIALIZE, actor=user, organization_id=user.company_id,
        target_type="ProductDesignItemBatch", target_id=source.pk,
        target_label=f"{order.order_no} 产品设计项初始化",
        reason="按已确认71条工程来源建立具体产品设计项并补录已有完成事实。",
        before_snapshot={"createdItemCount": 0},
        after_snapshot={
            "orderNo": order.order_no, "sourceRecordId": source.pk,
            "sourceVersion": source.source_version, "sourceCount": len(source_attributes),
            "createdItemCount": created_count, "createdCompletionCount": completion_count,
            "d1CompatibilityLinked": d1_linked, "requestHash": request_hash,
            "reviewId": review.pk, "approvalDecisionId": approval.pk,
            "downstreamWriteCount": 0, "authorization": decision,
        },
    )
    _commit_request(write_request, {
        "targetId": source.pk, "auditId": audit.pk, "createdItemCount": created_count,
        "createdCompletionCount": completion_count, "d1CompatibilityLinked": d1_linked,
    })
    return product_design_facts(user.company_id, user=user), False


def _parse_date(value, field, *, required=True):
    if value in (None, ""):
        if required:
            raise ProductDesignError("DESIGN_DATE_REQUIRED", f"{field}不能为空。")
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ProductDesignError("DESIGN_DATE_INVALID", f"{field}必须是有效日期。") from exc


def _selected_items(user, payload, *, lock=True):
    ids = payload.get("designItemIds") or ([payload.get("designItemId")] if payload.get("designItemId") else [])
    try:
        ids = [int(value) for value in ids]
    except (TypeError, ValueError) as exc:
        raise ProductDesignError("DESIGN_ITEM_SELECTION_INVALID", "设计项选择无效。") from exc
    if not ids or len(ids) != len(set(ids)):
        raise ProductDesignError("DESIGN_ITEM_SELECTION_INVALID", "必须明确选择且不得重复选择产品设计项。")
    query = ProductDesignItem.objects.select_related(
        "sales_order_item__sales_order", "source_record",
    ).filter(company_id=user.company_id, pk__in=ids)
    if lock:
        query = query.select_for_update()
    items = list(query.order_by("pk"))
    if len(items) != len(ids):
        raise ProductDesignError("DESIGN_ITEM_SCOPE_INVALID", "存在不属于当前企业的产品设计项。", 403)
    expected = payload.get("expectedVersions") or {}
    conflicts = [
        {"designItemId": item.pk, "expected": expected.get(str(item.pk)), "actual": item.version}
        for item in items if str(expected.get(str(item.pk), item.version)) != str(item.version)
    ]
    if conflicts:
        raise ProductDesignError("DESIGN_ITEM_VERSION_CONFLICT", "产品设计项已更新，请刷新后继续。", 409, {"conflicts": conflicts})
    try:
        require_crm_order_admission(
            company_id=user.company_id,
            source_record_id={item.source_record_id for item in items},
            source_order_no={item.sales_order_item.sales_order.external_source_no for item in items},
            source_version={item.source_version for item in items},
            lock=lock,
        )
    except CRMOrderAdmissionError as exc:
        raise ProductDesignError(
            exc.code, exc.message, exc.http_status, {"crmOrderAdmission": exc.details},
        ) from exc
    return items


def _valid_designer(user, employee_id):
    employee = Employee.objects.select_related("position_ref", "department_ref").filter(
        pk=employee_id, status="active",
    ).first()
    if not employee or _employee_company_id(employee) != user.company_id:
        raise ProductDesignError("DESIGNER_INVALID", "设计师必须是当前企业在职员工。", 409)
    source = _target_facts(user.company_id)[1]
    if employee.pk not in {row["employeeId"] for row in _designer_options(source, user.company_id)}:
        raise ProductDesignError("DESIGNER_RESPONSIBILITY_INVALID", "设计师必须来自已确认的设计职责范围。", 409)
    return employee


def _audit_batch(user, action_code, items, reason, before, after):
    return OrganizationOperatingAuditRecord.objects.create(
        action_code=action_code, actor=user, organization_id=user.company_id,
        target_type="ProductDesignItemBatch", target_id=items[0].pk,
        target_label=f"{len(items)}项产品设计", reason=str(reason or "产品设计业务办理")[:300],
        before_snapshot=before, after_snapshot=after,
    )


def _design_group(line_no):
    return f"DES-{int(line_no):02d}"


def _latest_group_plan(order_id, design_group, *, lock=False):
    query = ProductDesignPlanRevision.objects.filter(
        order_id=order_id, design_group=design_group,
    ).select_related(
        "designer_employee__position_ref", "designer_employee__department_ref",
    )
    if lock:
        query = query.select_for_update()
    records = list(query.order_by("-revision", "design_item_id", "-pk"))
    if not records:
        return None
    highest_revision = records[0].revision
    same_revision = [row for row in records if row.revision == highest_revision]
    return next((row for row in same_revision if row.design_item_id is None), same_revision[0])


def _selected_design_groups(order, payload):
    raw_groups = payload.get("designGroups") or []
    if not isinstance(raw_groups, (list, tuple)):
        raise ProductDesignError(
            "DESIGN_GROUP_SELECTION_INVALID",
            "请选择需要安排计划的产品设计分组。",
        )
    groups = [str(value or "").strip().upper() for value in raw_groups]
    if not groups or any(not value for value in groups):
        raise ProductDesignError(
            "DESIGN_GROUP_SELECTION_REQUIRED",
            "请选择需要安排计划的产品设计分组。",
        )
    if len(groups) != len(set(groups)):
        raise ProductDesignError("DESIGN_GROUP_SELECTION_INVALID", "产品设计分组不得重复选择。")
    available = {_design_group(item.line_no): item for item in order.items.all()}
    invalid = [value for value in groups if value not in available]
    if invalid:
        raise ProductDesignError(
            "DESIGN_GROUP_SCOPE_INVALID",
            "存在不属于当前订单的产品设计分组。",
            403,
            {"invalidDesignGroups": invalid},
        )
    return groups, available


@transaction.atomic
def save_design_plan(*, user, payload, idempotency_key):
    decision = _authorize(user, ACTION_PLAN_SAVE)
    order, _source, _review, _workflow, _approval = _target_facts(user.company_id, lock=True)
    groups, sales_items = _selected_design_groups(order, payload)
    designer = _valid_designer(user, payload.get("designerEmployeeId"))
    start = _parse_date(payload.get("plannedStartDate"), "计划开始设计日期")
    finish = _parse_date(payload.get("plannedFinishDate"), "计划完成设计日期")
    actual_start = _parse_date(payload.get("actualStartDate"), "实际开始设计日期", required=False)
    if finish < start:
        raise ProductDesignError("PLAN_DATE_ORDER_INVALID", "计划完成日期不得早于计划开始日期。")
    plan_type = str(payload.get("planType") or payload.get("planNature") or "FORMAL")
    if plan_type not in {value for value, _ in ProductDesignPlanRevision.PLAN_TYPE_CHOICES}:
        raise ProductDesignError("PLAN_TYPE_INVALID", "计划性质无效。")
    if actual_start and actual_start < start and plan_type != "HISTORICAL_EVIDENCE":
        raise ProductDesignError("ACTUAL_START_DATE_INVALID", "实际开始日期早于计划开始日期时必须有历史依据。")
    reason = str(payload.get("adjustmentReason") or payload.get("reason") or "").strip()
    if not reason:
        reason = "设计计划首次安排" if all(
            _latest_group_plan(order.pk, group) is None for group in groups
        ) else "设计计划调整"
    request_body = {
        "orderId": order.pk, "designGroups": groups, "designerEmployeeId": designer.pk,
        "start": start.isoformat(), "finish": finish.isoformat(),
        "actualStart": actual_start.isoformat() if actual_start else None,
        "planType": plan_type, "adjustmentReason": reason,
    }
    request, created, request_hash = _write_request(user=user, action_code=ACTION_PLAN_SAVE, entity_type="ProductDesignPlanRevision", key=idempotency_key, request_body=request_body)
    if not created and request.status == MasterDataWriteRequest.Status.COMMITTED:
        return product_design_facts(user.company_id, user=user), True
    changed, unchanged, before = [], [], []
    affected_item_count = 0
    for group in groups:
        latest = _latest_group_plan(order.pk, group, lock=True)
        before.append(_plan_snapshot(latest))
        affected_item_count += sales_items[group].product_design_items.count()
        if latest and latest.designer_employee_id == designer.pk and latest.planned_start_date == start and latest.planned_finish_date == finish and latest.actual_start_date == actual_start and latest.plan_type == plan_type:
            unchanged.append(group)
            continue
        revision = ProductDesignPlanRevision.objects.create(
            order=order, design_group=group, design_item=None,
            revision=(latest.revision + 1 if latest else 1),
            designer_employee=designer, planned_start_date=start, planned_finish_date=finish,
            actual_start_date=actual_start, plan_type=plan_type, adjustment_reason=reason,
            previous_revision=latest, created_by=user,
        )
        changed.append(revision.pk)
    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code=ACTION_PLAN_SAVE, actor=user, organization_id=user.company_id,
        target_type="ProductDesignPlanRevisionBatch", target_id=order.pk,
        target_label=f"{order.order_no} / {','.join(groups)}", reason=reason[:300],
        before_snapshot=before,
        after_snapshot={
            "orderId": order.pk, "orderNo": order.order_no, "designGroups": groups,
            "affectedDesignItemCount": affected_item_count,
            "changedRevisionIds": changed, "unchangedDesignGroups": unchanged,
            "requestHash": request_hash, "authorization": decision,
        },
    )
    _commit_request(request, {"targetId": order.pk, "auditId": audit.pk, "changedRevisionIds": changed, "unchangedDesignGroups": unchanged})
    return product_design_facts(user.company_id, user=user), False


def _decimal(value, field, field_code):
    if value in (None, ""):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ProductDesignError(
            "DESIGN_NUMBER_INVALID",
            f"{field_code} 当前值“{value}”不是有效数字；请输入大于0的数字后重试。",
            details={"field": field_code, "fieldLabel": field, "currentValue": value,
                     "reason": "NOT_A_NUMBER", "suggestedAction": "请输入大于0的数字后重试。"},
        ) from exc
    if result <= 0:
        raise ProductDesignError(
            "DESIGN_NUMBER_INVALID",
            f"{field_code} 当前值“{value}”必须大于0；请更正该字段后重试。",
            details={"field": field_code, "fieldLabel": field, "currentValue": value,
                     "reason": "MUST_BE_GREATER_THAN_ZERO", "suggestedAction": "请更正该字段后重试。"},
        )
    return result


def _dimension_semantic(item, current_values=None):
    current_values = current_values or {}
    existing = item.existing_design_data if isinstance(item.existing_design_data, dict) else {}
    semantic = str(current_values.get("dimensionSemantic") or existing.get("dimensionSemantic") or "").strip()
    if semantic:
        return semantic
    return "实际厚度"


def _uom_root_id(unit):
    return unit.conversion_base_id or unit.pk


def _convert_design_dimension(value, source_uom, target_uom, field_code):
    if value is None or source_uom.pk == target_uom.pk:
        return value
    if (
        source_uom.dimension != UnitOfMeasure.Dimension.LENGTH
        or target_uom.dimension != UnitOfMeasure.Dimension.LENGTH
        or _uom_root_id(source_uom) != _uom_root_id(target_uom)
    ):
        raise ProductDesignError(
            "DESIGN_UOM_CONVERSION_UNAVAILABLE",
            "设计尺寸单位缺少正式同维度换算关系，不能只改变单位标签。", 409,
            {
                "field": "designUomId", "fieldLabel": "设计尺寸单位",
                "sourceUnit": source_uom.name, "targetUnit": target_uom.name,
                "affectedDimension": field_code,
                "reason": "NO_GOVERNED_LENGTH_CONVERSION",
                "suggestedAction": "请维护同一换算基准的长度单位，或保持当前尺寸单位。",
            },
        )
    converted = Decimal(str(value)) * source_uom.conversion_factor / target_uom.conversion_factor
    quantized = converted.quantize(Decimal("0.000001"))
    if converted != quantized:
        raise ProductDesignError(
            "DESIGN_UOM_CONVERSION_PRECISION_UNRESOLVED",
            "设计尺寸单位换算结果无法无损写入当前精度，已阻断保存。", 409,
            {"field": "designUomId", "affectedDimension": field_code, "convertedValue": str(converted)},
        )
    return quantized


@transaction.atomic
def add_product_design_item(*, user, payload, idempotency_key):
    decision = _authorize(user, ACTION_ITEM_ADD)
    order, source, review, _workflow, approval = _target_facts(user.company_id, lock=True)
    try:
        line_no = int(payload.get("orderLineNo"))
    except (TypeError, ValueError) as exc:
        raise ProductDesignError("DESIGN_ORDER_LINE_REQUIRED", "新增必须选择当前订单行。") from exc
    sales_item = order.items.select_for_update().filter(line_no=line_no).first()
    if not sales_item:
        raise ProductDesignError("DESIGN_ORDER_LINE_INVALID", "订单行不属于当前订单。", 409)
    item_name = str(payload.get("itemName") or "").strip()
    reason = str(payload.get("reason") or "").strip()
    if not item_name or not reason:
        raise ProductDesignError("DESIGN_ITEM_REQUIRED", "产品名称与新增依据不能为空。")
    quantity = _decimal(payload.get("physicalQuantity"), "实物数量", "physicalQuantity")
    uom = None
    if payload.get("physicalUomId"):
        uom = _master(UnitOfMeasure, payload.get("physicalUomId"), user.company_id, "实物单位", is_active=True)
    elif payload.get("physicalUomCode"):
        uom = UnitOfMeasure.objects.filter(
            company_id=user.company_id, is_active=True, code=str(payload["physicalUomCode"]).strip(),
        ).first()
    if not uom:
        raise ProductDesignError("DESIGN_UOM_INVALID", "新增必须精确匹配当前企业正式计量单位。", 409)
    design_uom = None
    if payload.get("designUomId"):
        design_uom = _master(UnitOfMeasure, payload.get("designUomId"), user.company_id, "设计尺寸单位", is_active=True)
        if design_uom.dimension != UnitOfMeasure.Dimension.LENGTH:
            raise ProductDesignError("DESIGN_UOM_DIMENSION_INVALID", "设计尺寸单位必须是长度单位。", 409)
    category = None
    if payload.get("productCategoryId"):
        category = _master(ProductCategory, payload.get("productCategoryId"), user.company_id, "产品分类", is_active=True)
    elif payload.get("productCategoryCode"):
        category = ProductCategory.objects.filter(
            company_id=user.company_id, is_active=True, code=str(payload["productCategoryCode"]).strip(),
        ).first()
    if not category:
        raise ProductDesignError("DESIGN_CATEGORY_INVALID", "新增必须精确匹配当前企业正式产品分类。", 409)
    dimensions = {
        "designLength": _decimal(payload.get("designLength"), "设计长度", "designLength"),
        "designWidth": _decimal(payload.get("designWidth"), "设计宽度", "designWidth"),
        "designThickness": _decimal(payload.get("designThickness"), "第三尺寸", "designThickness"),
    }
    dimension_semantic = str(payload.get("dimensionSemantic") or "").strip()
    allowed_semantics = {"墙厚", "部件厚", "实际厚度"}
    if dimension_semantic not in allowed_semantics:
        raise ProductDesignError("DESIGN_DIMENSION_SEMANTIC_INVALID", "第三尺寸语义必须是墙厚、部件厚或实际厚度。")
    request_body = {
        "orderId": order.pk, "orderLineNo": line_no, "itemName": item_name,
        "installationPosition": str(payload.get("installationPosition") or "").strip(),
        "physicalQuantity": str(quantity), "physicalUomId": uom.pk,
        "designUomId": design_uom.pk if design_uom else None,
        "productCategoryId": category.pk, "dimensions": {key: str(value) for key, value in dimensions.items()},
        "dimensionSemantic": dimension_semantic, "reason": reason,
    }
    request, created, request_hash = _write_request(
        user=user, action_code=ACTION_ITEM_ADD, entity_type="ProductDesignItem",
        key=idempotency_key, request_body=request_body,
    )
    if not created and request.status == MasterDataWriteRequest.Status.COMMITTED:
        return product_design_facts(user.company_id, user=user), True
    sequence = (sales_item.engineering_attributes.order_by("-sequence").values_list("sequence", flat=True).first() or 0) + 1
    external_source = f"PCE-DESIGN-USER-{uuid.uuid5(uuid.NAMESPACE_URL, request_hash)}"
    raw = {
        "sourceRow": None, "product": category.name, "component": item_name,
        "space": request_body["installationPosition"],
        "installationPosition": request_body["installationPosition"],
        "quantity": str(quantity), "unit": uom.code, "unitName": uom.name,
        "length": str(dimensions["designLength"]), "width": str(dimensions["designWidth"]),
        "thickness": str(dimensions["designThickness"]),
        "designUomId": design_uom.pk if design_uom else None,
        "designUomLabel": design_uom.name if design_uom else "",
        "dimensionSemantic": dimension_semantic,
        "entryReason": reason, "sourceType": "USER_ENTRY",
    }
    attribute = SalesOrderItemEngineeringAttribute.objects.create(
        sales_order_item=sales_item, sequence=sequence,
        raw_source="产品设计管理用户录入", raw_sheet="产品设计导入",
        external_source=external_source, raw_field="产品设计项",
        raw_value=raw, canonical_field="product_design_item",
        normalized_value=raw, value_type="json", unit=uom,
        source_type="DESIGN", created_by=user,
    )
    group_no = f"{order.order_no}-DES-{sales_item.line_no:02d}"
    item = ProductDesignItem.objects.create(
        company_id=user.company_id, sales_order_item=sales_item,
        source_record=source, source_attribute=attribute,
        item_no=f"{group_no}-USR-{attribute.pk:04d}", item_name=item_name,
        space_snapshot=request_body["installationPosition"],
        installation_position_snapshot=request_body["installationPosition"],
        physical_quantity=quantity, physical_uom=uom, physical_uom_snapshot=uom.name,
        product_category=category,
        original_requirement={
            "space": request_body["installationPosition"],
            "installationPosition": request_body["installationPosition"],
            "physicalQuantity": str(quantity), "physicalUnit": uom.name,
            "provenance": {"sourceObject": external_source, "sourceType": "USER_ENTRY"},
        },
        existing_design_data={
            **{key: str(value) for key, value in dimensions.items()},
            "designUomId": design_uom.pk if design_uom else None,
            "designUomLabel": design_uom.name if design_uom else "",
            "dimensionSemantic": dimension_semantic,
            "provenance": {"sourceObject": external_source, "sourceType": "USER_ENTRY"},
        },
        design_data_nature="FORMAL", source_version=source.source_version,
        source_content_hash=source.content_hash,
        match_results={
            "productCategory": {"status": "EXACT", "matchedId": category.pk},
            "physicalUom": {"status": "EXACT", "matchedId": uom.pk},
        },
    )
    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code=ACTION_ITEM_ADD, actor=user, organization_id=user.company_id,
        target_type="ProductDesignItem", target_id=item.pk, target_label=item.item_no,
        reason=reason, before_snapshot={},
        after_snapshot={
            "itemNo": item.item_no, "orderNo": order.order_no,
            "orderLineNo": line_no, "sourceType": "USER_ENTRY",
            "reviewId": review.pk, "approvalDecisionId": approval.pk,
            "requestHash": request_hash, "authorization": decision,
        },
    )
    _commit_request(request, {"targetId": item.pk, "auditId": audit.pk, "itemNo": item.item_no})
    return product_design_facts(user.company_id, user=user), False


@transaction.atomic
def delete_product_design_item(*, user, payload, idempotency_key):
    decision = _authorize(user, ACTION_ITEM_DELETE)
    items = _selected_items(user, payload)
    if len(items) != 1:
        raise ProductDesignError("DESIGN_DELETE_SINGLE_ONLY", "删除必须逐项确认。")
    item = items[0]
    design_group = _design_group(item.sales_order_item.line_no)
    references = {
        "planRevisions": ProductDesignPlanRevision.objects.filter(
            order_id=item.sales_order_item.sales_order_id,
            design_group=design_group,
        ).count(),
        "designRevisions": item.design_revisions.count(),
        "completionRecords": item.completion_records.count(),
    }
    if any(references.values()) or item.design_data_nature != "FORMAL" or not item.source_attribute.external_source.startswith("PCE-DESIGN-USER-"):
        raise ProductDesignError(
            "DESIGN_ITEM_DELETE_PROTECTED",
            "该设计项已有来源、修订、计划或完成历史，禁止物理删除；历史必须保留。",
            409, {"references": references, "itemNo": item.item_no},
        )
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise ProductDesignError("DESIGN_DELETE_REASON_REQUIRED", "删除必须填写原因。")
    request_body = {"itemIds": [item.pk], "itemNo": item.item_no, "reason": reason}
    request, created, request_hash = _write_request(
        user=user, action_code=ACTION_ITEM_DELETE, entity_type="ProductDesignItem",
        key=idempotency_key, request_body=request_body,
    )
    if not created and request.status == MasterDataWriteRequest.Status.COMMITTED:
        return product_design_facts(user.company_id, user=user), True
    snapshot = {
        "id": item.pk, "itemNo": item.item_no, "itemName": item.item_name,
        "salesOrderItemId": item.sales_order_item_id,
        "sourceAttributeId": item.source_attribute_id,
    }
    attribute = item.source_attribute
    target_id = item.pk
    item.delete()
    attribute.delete()
    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code=ACTION_ITEM_DELETE, actor=user, organization_id=user.company_id,
        target_type="ProductDesignItem", target_id=target_id,
        target_label=snapshot["itemNo"], reason=reason,
        before_snapshot=snapshot,
        after_snapshot={"deleted": True, "requestHash": request_hash, "authorization": decision},
    )
    _commit_request(request, {"targetId": target_id, "auditId": audit.pk, "deleted": True})
    return product_design_facts(user.company_id, user=user), False


def _master(model, object_id, company_id, label, field_code=None, **filters):
    if object_id in (None, ""):
        return None
    field_names = {field.name for field in model._meta.fields}
    query = model.objects.filter(pk=object_id, **filters)
    if "company" in field_names:
        query = query.filter(company_id=company_id)
    elif "company_id" in field_names:
        query = query.filter(company_id=company_id)
    obj = query.first()
    if not obj:
        raise ProductDesignError(
            "DESIGN_MASTER_INVALID", f"{label}不是当前企业有效正式资料。", 409,
            {
                "field": field_code or label,
                "fieldLabel": label,
                "currentValue": object_id,
                "reason": "NOT_CURRENT_ENTERPRISE_ACTIVE_MASTER",
                "suggestedAction": f"请重新选择当前企业有效的{label}后重试。",
            },
        )
    return obj


@transaction.atomic
def save_design_content(*, user, payload, idempotency_key):
    decision = _authorize(user, ACTION_DESIGN_SAVE)
    items = _selected_items(user, payload)
    if any(item.design_data_nature == "SIMULATED_FOR_TEST" and (item.source_attribute.canonical_field or "").startswith("PCE-SOURCE-ROW:") for item in items):
        from .product_design_instance_service import resolve
        instance, line, source = resolve(user, payload.get("instanceContext") or {}, lock=True)
        if any(item.sales_order_item_id != line.pk or item.source_record_id != source.pk or item.source_version != source.source_version or item.source_content_hash != source.content_hash for item in items):
            raise ProductDesignError("DESIGN_CONTEXT_MISMATCH", "所选设计项与当前工程上下文不一致。", 409)
        if payload.get("designNature") != "SIMULATED_FOR_TEST":
            raise ProductDesignError("DESIGN_TEST_NATURE_REQUIRED", "测试来源设计必须保留测试模拟性质。", 409)
    order_nos = {item.sales_order_item.sales_order.order_no for item in items}
    order_no = next(iter(order_nos)) if len(order_nos) == 1 else None
    values = payload.get("designData")
    if not isinstance(values, dict):
        raise ProductDesignError("DESIGN_DATA_REQUIRED", "必须提交结构化设计数据。")
    illegal = sorted(set(values) - set(ALLOWED_DESIGN_FIELDS))
    if illegal:
        raise ProductDesignError("DESIGN_FIELD_NOT_ALLOWED", "包含未受控设计字段。", details={"fields": illegal})
    nature = str(payload.get("designNature") or "FORMAL")
    if nature not in {value for value, _ in ProductDesignRevision.DESIGN_NATURE_CHOICES}:
        raise ProductDesignError("DESIGN_NATURE_INVALID", "设计数据性质无效。")
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise ProductDesignError("DESIGN_REASON_REQUIRED", "设计保存必须填写修订说明。")
    if "materialProcessTypeId" in values:
        raise ProductDesignError(
            "PROCESS_CONFIGURATION_TYPE_INVALID",
            "工艺配置必须提交完整配置身份，不能提交油漆工艺类型ID。", 409,
        )
    if "designThickness" in values or "designUomId" in values:
        semantics = {
            _dimension_semantic(
                item,
                _design_snapshot(item.design_revisions.order_by("-revision").first()) or {},
            )
            for item in items
        }
        if len(semantics) > 1:
            raise ProductDesignError(
                "DESIGN_DIMENSION_SEMANTIC_MIXED",
                "所选设计项的第三尺寸语义不同，不能在同一批次修改第三尺寸或设计尺寸单位。", 409,
                {"field": "designUomId" if "designUomId" in values else "designThickness", "semantics": sorted(semantics)},
            )
    length = _decimal(values.get("designLength"), "设计长度", "designLength") if "designLength" in values else _UNSET
    width = _decimal(values.get("designWidth"), "设计宽度", "designWidth") if "designWidth" in values else _UNSET
    thickness = _decimal(values.get("designThickness"), "设计厚度", "designThickness") if "designThickness" in values else _UNSET
    def supplied_master(field, model, label, **filters):
        return _master(model, values.get(field), user.company_id, label, field_code=field, **filters) if field in values else _UNSET
    material = supplied_master("materialId", Material, "材料", is_active=True)
    product_category = supplied_master("productCategoryId", ProductCategory, "产品分类", is_active=True)
    product_definition = supplied_master("productDefinitionId", ProductDefinition, "产品", is_active=True, status="released")
    physical_uom = supplied_master("physicalUomId", UnitOfMeasure, "实物单位", is_active=True)
    design_uom = supplied_master("designUomId", UnitOfMeasure, "设计尺寸单位", is_active=True)
    paint_process = supplied_master("paintProcessTypeId", ManufacturingProcessType, "油漆工艺", is_active=True)
    edge_method = supplied_master("edgeMethodId", EngineeringBreakdownOption, "封边方式", is_active=True, option_type=EngineeringBreakdownOption.OptionType.EDGE_METHOD)
    normalized = {field: values.get(field) for field in ALLOWED_DESIGN_FIELDS if field in values}
    if "finishedGoodsSubstitution" in normalized:
        from .finished_goods_substitution import validate_declaration
        from sales.services import SalesBusinessError
        try:
            for design_item in items:
                validate_declaration(normalized["finishedGoodsSubstitution"], item=design_item.sales_order_item)
        except SalesBusinessError as exc:
            raise ProductDesignError(exc.code, exc.message, exc.http_status) from exc
    if "calculationInputs" in normalized:
        from .design_calculation_input_service import normalize_contract
        from .engineering_calculation_service import EngineeringCalculationError
        try:
            normalized["calculationInputs"] = normalize_contract(normalized["calculationInputs"])
        except EngineeringCalculationError as exc:
            raise ProductDesignError(exc.code, exc.message, details=exc.details) from exc
    visible = normalize_visible_condition(
        code=values.get("visibleConditionCode"), value=values.get("visibleCondition"),
    ) if "visibleConditionCode" in values or "visibleCondition" in values else None
    if visible is not None:
        normalized["visibleConditionCode"] = visible["code"]
        normalized["visibleCondition"] = visible["name"]
        normalized["visibleConditionSnapshot"] = visible
    color_options = {row["id"]: row for row in _color_version_options(user.company_id)}
    color_option_id = str(values.get("colorVersionOptionId") or "").strip()
    if color_option_id:
        color_option = color_options.get(color_option_id)
        if not color_option:
            raise ProductDesignError("COLOR_VERSION_OPTION_INVALID", "颜色/版号不是当前企业现有来源候选。", 409)
        normalized["finishOrColor"] = color_option["name"]
        normalized["colorVersionOptionId"] = color_option["id"]
        normalized["colorVersionSnapshot"] = color_option
    configuration_options = {
        row["id"]: row for row in _process_configuration_options(user.company_id)
    }
    configuration_option = _UNSET
    configuration_paint = _UNSET
    if "processConfigurationId" in values:
        configuration_id = str(values.get("processConfigurationId") or "").strip()
        configuration_option = configuration_options.get(configuration_id)
        if not configuration_option:
            raise ProductDesignError(
                "PROCESS_CONFIGURATION_INVALID",
                "工艺配置不是当前企业已发布且适用于该产品的 Routing 正式工艺路线。", 409,
                {"field": "processConfigurationId", "fieldLabel": "工艺配置", "currentValue": configuration_id,
                 "reason": "NOT_RELEASED_APPLICABLE_ROUTING", "suggestedAction": "请选择页面提供的已发布有效Routing正式路线；如无匹配请保留来源值。"},
            )
        linked_paint_id = configuration_option.get("paintProcessTypeId")
        if not linked_paint_id:
            raise ProductDesignError(
                "PROCESS_CONFIGURATION_PAINT_UNRESOLVED",
                "该完整工艺配置没有唯一可核实的油漆工艺关系，已保留来源值但禁止猜测保存。", 409,
                {"processConfigurationCode": configuration_option["code"]},
            )
        configuration_paint = _master(
            ManufacturingProcessType, linked_paint_id, user.company_id, "配置关联油漆工艺", field_code="paintProcessTypeId", is_active=True,
        )
        if paint_process is not _UNSET and (
            paint_process is None or paint_process.pk != configuration_paint.pk
        ):
            raise ProductDesignError(
                "PROCESS_CONFIGURATION_PAINT_INCOMPATIBLE",
                "所选油漆工艺与完整工艺配置的现有正式关系不一致。", 409,
                {"processConfigurationCode": configuration_option["code"], "expectedPaintProcessId": configuration_paint.pk},
            )
        normalized.update({
            "processConfigurationId": configuration_option["id"],
            "processConfigurationCode": configuration_option["code"],
            "processConfigurationLabel": configuration_option["label"],
            "processConfigurationSnapshot": {
                "id": configuration_option["id"], "code": configuration_option["code"],
                "label": configuration_option["label"], "source": configuration_option["source"],
                "paintProcessTypeId": configuration_paint.pk,
                "paintProcessCode": configuration_paint.code,
                "paintProcessName": configuration_paint.name,
            },
        })
    if product_definition is not _UNSET and product_definition is not None:
        today = date.today()
        if (
            product_definition.effective_from and product_definition.effective_from > today
        ) or (
            product_definition.effective_to and product_definition.effective_to < today
        ):
            raise ProductDesignError(
                "PRODUCT_DEFINITION_NOT_EFFECTIVE",
                "所选产品定义当前不在有效期内。", 409,
                {"field": "productDefinitionId", "currentValue": product_definition.pk},
            )
    request_body = {"itemIds": [x.pk for x in items], "designData": normalized, "nature": nature, "reason": reason}
    request, created, request_hash = _write_request(user=user, action_code=ACTION_DESIGN_SAVE, entity_type="ProductDesignRevision", key=idempotency_key, request_body=request_body)
    if not created and request.status == MasterDataWriteRequest.Status.COMMITTED:
        return product_design_facts(user.company_id, user=user, order_no=order_no), True
    changed, unchanged, before = [], [], []
    for item in items:
        latest = item.design_revisions.order_by("-revision").first()
        current = _design_snapshot(latest)
        existing = item.existing_design_data if isinstance(item.existing_design_data, dict) else {}
        current_values = current or existing
        effective_length = current_values.get("designLength") if length is _UNSET else length
        effective_width = current_values.get("designWidth") if width is _UNSET else width
        effective_thickness = current_values.get("designThickness") if thickness is _UNSET else thickness
        effective_material = (latest.material if latest and latest.material_id else None) if material is _UNSET else material
        effective_category = item.product_category if product_category is _UNSET else product_category
        effective_product = item.product_definition if product_definition is _UNSET else product_definition
        effective_physical_uom = item.physical_uom if physical_uom is _UNSET else physical_uom
        if effective_product and effective_category and effective_product.category_id not in {None, effective_category.pk}:
            raise ProductDesignError(
                "PRODUCT_DEFINITION_CATEGORY_MISMATCH",
                "所选产品定义不适用于当前产品分类。", 409,
                {
                    "field": "productDefinitionId", "currentValue": effective_product.pk,
                    "reason": "PRODUCT_CATEGORY_NOT_APPLICABLE",
                    "suggestedAction": "请选择当前产品分类下的正式产品定义。",
                },
            )
        effective_design_uom = (latest.design_uom if latest and latest.design_uom_id else None) if design_uom is _UNSET else design_uom
        existing_design_uom = UnitOfMeasure.objects.filter(
            pk=existing.get("designUomId"), company_id=user.company_id, is_active=True,
        ).first() if existing.get("designUomId") else None
        if design_uom is _UNSET and effective_design_uom is None:
            effective_design_uom = existing_design_uom
        previous_design_uom = latest.design_uom if latest and latest.design_uom_id else existing_design_uom
        dimension_values = {
            "designLength": effective_length,
            "designWidth": effective_width,
            "designThickness": effective_thickness,
        }
        if effective_design_uom and effective_design_uom.dimension != UnitOfMeasure.Dimension.LENGTH:
            raise ProductDesignError(
                "DESIGN_UOM_DIMENSION_INVALID",
                "设计尺寸单位必须是当前企业有效的长度单位。", 409,
                {"field": "designUomId", "currentValue": effective_design_uom.pk, "dimension": effective_design_uom.dimension},
            )
        if design_uom is not _UNSET and previous_design_uom != effective_design_uom and any(value is not None for value in dimension_values.values()):
            if effective_design_uom is None:
                raise ProductDesignError(
                    "DESIGN_UOM_CLEAR_BLOCKED",
                    "已有设计尺寸时不能清空设计尺寸单位。", 409,
                    {"field": "designUomId", "reason": "DIMENSION_VALUES_EXIST"},
                )
            for field_code, supplied_value in (("designLength", length), ("designWidth", width), ("designThickness", thickness)):
                current_value = current_values.get(field_code)
                if current_value is None or supplied_value is not _UNSET:
                    continue
                if previous_design_uom is None:
                    raise ProductDesignError(
                        "DESIGN_UOM_SOURCE_UNKNOWN",
                        "现有尺寸没有可靠尺寸单位，不能自动指定新单位；请同时明确填写全部已有尺寸值。", 409,
                        {"field": "designUomId", "affectedDimension": field_code, "reason": "SOURCE_UNIT_NOT_MAINTAINED"},
                    )
                converted = _convert_design_dimension(current_value, previous_design_uom, effective_design_uom, field_code)
                if field_code == "designLength":
                    effective_length = converted
                elif field_code == "designWidth":
                    effective_width = converted
                else:
                    effective_thickness = converted
        effective_material_process = latest.material_process_type if latest and latest.material_process_type_id else None
        source_configuration = _source_process_configuration(item)
        current_configuration_id = (
            current_values.get("processConfigurationId")
            or source_configuration.get("id")
        )
        current_configuration = configuration_options.get(current_configuration_id)
        if configuration_option is not _UNSET:
            if item.pk not in configuration_option["compatibleItemIds"]:
                raise ProductDesignError(
                    "PROCESS_CONFIGURATION_NOT_APPLICABLE",
                    "所选 Routing 正式工艺路线与目标产品的类别或产品适用关系不匹配。", 409,
                    {"designItemId": item.pk, "processConfigurationCode": configuration_option["code"]},
                )
            effective_paint_process = configuration_paint
        else:
            effective_paint_process = (latest.paint_process_type if latest and latest.paint_process_type_id else None) if paint_process is _UNSET else paint_process
            if paint_process is not _UNSET and current_configuration:
                linked_paint_id = current_configuration.get("paintProcessTypeId")
                if not linked_paint_id:
                    raise ProductDesignError(
                        "PROCESS_CONFIGURATION_PAINT_UNRESOLVED",
                        "当前完整工艺配置没有唯一可核实的油漆工艺关系；可保留现值，但不能单独改写油漆工艺。", 409,
                        {
                            "designItemId": item.pk,
                            "processConfigurationCode": current_configuration["code"],
                            "paintLinkReason": current_configuration.get("paintLinkReason"),
                        },
                    )
                if paint_process is None or paint_process.pk != linked_paint_id:
                    raise ProductDesignError(
                        "PROCESS_CONFIGURATION_PAINT_INCOMPATIBLE",
                        "所选油漆工艺与当前完整工艺配置的现有正式关系不一致。", 409,
                        {
                            "designItemId": item.pk,
                            "processConfigurationCode": current_configuration["code"],
                            "expectedPaintProcessId": linked_paint_id,
                        },
                    )
        effective_edge_method = (latest.edge_method if latest and latest.edge_method_id else None) if edge_method is _UNSET else edge_method
        effective_data = {
            key: normalized[key] if key in normalized else current_values.get(key)
            for key in ("processConfigurationId", "processConfigurationCode", "processConfigurationLabel", "processConfigurationSnapshot", "finishOrColor", "colorVersionOptionId", "colorVersionSnapshot", "visibleCondition", "visibleConditionCode", "visibleConditionSnapshot", "configurationNotes", "designNotes", "hardware", "glass", "documentReferences", "calculationInputs", "finishedGoodsSubstitution")
        }
        if "calculationInputs" in normalized:
            from .design_calculation_input_service import freeze_contract_units
            from .engineering_calculation_service import EngineeringCalculationError
            try:
                effective_data["calculationInputs"] = freeze_contract_units(
                    normalized["calculationInputs"], company_id=user.company_id,
                    design_uom_id=effective_design_uom.pk if effective_design_uom else None,
                    physical_uom_id=effective_physical_uom.pk if effective_physical_uom else None,
                )
                if effective_data["calculationInputs"].get('ruleFamily')=='ROOM_DOOR' and effective_data["calculationInputs"]["paintProcessTypeId"] != (effective_paint_process.pk if effective_paint_process else None):
                    raise ProductDesignError("NATIVE_CALCULATION_PAINT_REFERENCE_MISMATCH", "核算涂装工艺引用与设计修订不一致。")
            except EngineeringCalculationError as exc:
                raise ProductDesignError(exc.code, exc.message, details=exc.details) from exc
        if not effective_data.get("processConfigurationId") and source_configuration.get("id"):
            effective_data.update({
                "processConfigurationId": source_configuration["id"],
                "processConfigurationCode": source_configuration["code"],
                "processConfigurationLabel": source_configuration["label"],
                "processConfigurationSnapshot": {
                    "id": source_configuration["id"],
                    "code": source_configuration["code"],
                    "label": source_configuration["label"],
                    "source": "existing-design-source",
                    "paintLinkStatus": (current_configuration or {}).get("paintLinkStatus", "NO_MATCH"),
                    "paintLinkReason": (current_configuration or {}).get("paintLinkReason", "现有来源值尚无唯一正式油漆关系。"),
                },
            })
        before.append(current)
        comparable = {
            "designLength": str(effective_length) if effective_length is not None else None,
            "designWidth": str(effective_width) if effective_width is not None else None,
            "designThickness": str(effective_thickness) if effective_thickness is not None else None,
            "materialId": effective_material.pk if effective_material else None,
            "productCategoryId": effective_category.pk if effective_category else None,
            "productDefinitionId": effective_product.pk if effective_product else None,
            "physicalUomId": effective_physical_uom.pk if effective_physical_uom else None,
            "designUomId": effective_design_uom.pk if effective_design_uom else None,
            "materialProcessTypeId": effective_material_process.pk if effective_material_process else None,
            "paintProcessTypeId": effective_paint_process.pk if effective_paint_process else None,
            "edgeMethodId": effective_edge_method.pk if effective_edge_method else None,
            **{key: effective_data.get(key) for key in ("processConfigurationId", "processConfigurationCode", "processConfigurationLabel", "finishOrColor", "colorVersionOptionId", "visibleCondition", "visibleConditionCode", "configurationNotes", "designNotes", "hardware", "glass", "documentReferences", "calculationInputs", "finishedGoodsSubstitution")},
        }
        if current and current.get("comparison") == comparable and current.get("designNature") == nature:
            unchanged.append(item.pk)
            continue
        revision = ProductDesignRevision.objects.create(
            design_item=item, revision=(latest.revision + 1 if latest else 1), design_nature=nature,
            design_length=effective_length, design_width=effective_width, design_thickness=effective_thickness,
            design_uom=effective_design_uom,
            material=effective_material, material_process_type=effective_material_process,
            paint_process_type=effective_paint_process, edge_method=effective_edge_method,
            design_data=effective_data,
            source_provenance={"basedOnSourceRecordId": item.source_record_id, "basedOnSourceVersion": item.source_version, "existingDesignDataHash": _canonical_hash(item.existing_design_data)},
            master_match_results={"productCategory": effective_category.pk if effective_category else None, "productDefinition": effective_product.pk if effective_product else None, "physicalUom": effective_physical_uom.pk if effective_physical_uom else None, "designUom": effective_design_uom.pk if effective_design_uom else None, "material": effective_material.pk if effective_material else None, "materialProcess": effective_material_process.pk if effective_material_process else None, "paintProcess": effective_paint_process.pk if effective_paint_process else None, "edgeMethod": effective_edge_method.pk if effective_edge_method else None},
            change_reason=reason, created_by=user,
        )
        item.version += 1
        item.product_category = effective_category
        item.product_definition = effective_product
        item.physical_uom = effective_physical_uom
        item.physical_uom_snapshot = effective_physical_uom.name if effective_physical_uom else item.physical_uom_snapshot
        item.save(update_fields=["product_category", "product_definition", "physical_uom", "physical_uom_snapshot", "version", "updated_at"])
        changed.append(revision.pk)
    audit = _audit_batch(user, ACTION_DESIGN_SAVE, items, reason, before, {"changedRevisionIds": changed, "unchangedItemIds": unchanged, "requestHash": request_hash, "authorization": decision})
    _commit_request(request, {"targetId": items[0].pk, "auditId": audit.pk, "changedRevisionIds": changed, "unchangedItemIds": unchanged})
    return product_design_facts(user.company_id, user=user, order_no=order_no), False


@transaction.atomic
def record_design_completion(*, user, payload, idempotency_key):
    decision = _authorize(user, ACTION_COMPLETE)
    items = _selected_items(user, payload)
    nature = str(payload.get("completionNature") or "FORMAL")
    if nature not in {value for value, _ in ProductDesignCompletionRecord.COMPLETION_NATURE_CHOICES}:
        raise ProductDesignError("COMPLETION_NATURE_INVALID", "完成记录性质无效。")
    actual_date = _parse_date(payload.get("actualCompletionDate"), "实际完成设计日期", required=nature not in {"HISTORICAL_EVIDENCE", "REWORK"})
    basis = str(payload.get("completionBasis") or "").strip()
    if not basis:
        raise ProductDesignError("COMPLETION_BASIS_REQUIRED", "完成登记必须填写依据/说明。")
    designer = _valid_designer(user, payload.get("designerEmployeeId")) if payload.get("designerEmployeeId") else None
    request_body = {
        "itemIds": [x.pk for x in items], "nature": nature,
        "actualCompletionDate": actual_date.isoformat() if actual_date else None,
        "basis": basis, "designerId": designer.pk if designer else None,
    }
    request, created, request_hash = _write_request(user=user, action_code=ACTION_COMPLETE, entity_type="ProductDesignCompletionRecord", key=idempotency_key, request_body=request_body)
    if not created and request.status == MasterDataWriteRequest.Status.COMMITTED:
        return product_design_facts(user.company_id, user=user), True
    created_ids, unchanged_ids, before = [], [], []
    for item in items:
        latest_plan = _latest_group_plan(
            item.sales_order_item.sales_order_id,
            _design_group(item.sales_order_item.line_no),
        )
        latest_design = item.design_revisions.order_by("-revision").first()
        latest_completion = item.completion_records.order_by("-sequence").first()
        before.append(_completion_snapshot(latest_completion, latest_plan))
        if actual_date and latest_plan and actual_date < latest_plan.planned_start_date and nature != "HISTORICAL_EVIDENCE":
            raise ProductDesignError("COMPLETION_DATE_INVALID", "实际完成日期早于计划开始日期时必须使用有依据的历史补录。", 409, {"designItemId": item.pk})
        if latest_completion and (
            latest_completion.completion_nature == nature
            and latest_completion.actual_completion_date == actual_date
            and latest_completion.completion_basis == basis
            and latest_completion.completed_designer_id == (designer.pk if designer else None)
        ):
            unchanged_ids.append(item.pk)
            continue
        record = ProductDesignCompletionRecord.objects.create(
            design_item=item, sequence=(latest_completion.sequence + 1 if latest_completion else 1),
            completion_nature=nature, actual_completion_date=actual_date,
            completion_basis=basis, plan_revision=latest_plan,
            design_revision=latest_design, completed_designer=designer,
            recorded_by=user, action_code=ACTION_COMPLETE,
        )
        item.version += 1
        item.save(update_fields=["version", "updated_at"])
        created_ids.append(record.pk)
    audit = _audit_batch(user, ACTION_COMPLETE, items, basis, before, {"completionRecordIds": created_ids, "unchangedItemIds": unchanged_ids, "requestHash": request_hash, "actualCompletionDate": actual_date.isoformat() if actual_date else None, "completionNature": nature, "authorization": decision})
    _commit_request(request, {"targetId": items[0].pk, "auditId": audit.pk, "completionRecordIds": created_ids, "unchangedItemIds": unchanged_ids})
    return product_design_facts(user.company_id, user=user), False


def _plan_snapshot(record):
    if not record:
        return None
    return {
        "id": record.pk, "revision": record.revision,
        "orderId": record.order_id, "designGroup": record.design_group,
        "designer": _employee_snapshot(record.designer_employee),
        "plannedStartDate": record.planned_start_date.isoformat(),
        "plannedFinishDate": record.planned_finish_date.isoformat(),
        "actualStartDate": record.actual_start_date.isoformat() if record.actual_start_date else None,
        "planType": record.plan_type, "planTypeLabel": record.get_plan_type_display(),
        "planNature": record.plan_type, "planNatureLabel": record.get_plan_type_display(),
        "adjustmentReason": record.adjustment_reason,
        "changeReason": record.adjustment_reason, "registeredAt": record.created_at.isoformat(),
    }


def _legacy_solution(record):
    if not record:
        return {}
    payload = record.source_payload if isinstance(record.source_payload, dict) else {}
    return payload.get("designSolution") or {}


def _design_snapshot(record):
    if not record:
        return None
    legacy = _legacy_solution(record.legacy_source_record) if record.legacy_source_record_id else {}
    data = record.design_data or {}
    comparison = {
        "designLength": str(record.design_length) if record.design_length is not None else None,
        "designWidth": str(record.design_width) if record.design_width is not None else None,
        "designThickness": str(record.design_thickness) if record.design_thickness is not None else None,
        "materialId": record.material_id,
        "productCategoryId": record.design_item.product_category_id,
        "productDefinitionId": record.design_item.product_definition_id,
        "physicalUomId": record.design_item.physical_uom_id,
        "designUomId": record.design_uom_id,
        "materialProcessTypeId": record.material_process_type_id,
        "paintProcessTypeId": record.paint_process_type_id, "edgeMethodId": record.edge_method_id,
        **{key: data.get(key) for key in ("processConfigurationId", "processConfigurationCode", "processConfigurationLabel", "finishOrColor", "colorVersionOptionId", "visibleCondition", "visibleConditionCode", "configurationNotes", "designNotes", "hardware", "glass", "documentReferences", "calculationInputs", "finishedGoodsSubstitution")},
    }
    return {
        "id": record.pk, "revision": record.revision,
        "designNature": record.design_nature, "designNatureLabel": ("获准业务设计修订（测试业务）" if record.approval_id and record.approval_scope == "TEST_BUSINESS" else record.get_design_nature_display()),
        "originNature": record.origin_nature, "approvalScope": record.approval_scope, "approvalId": record.approval_id, "predecessorRevisionId": record.predecessor_revision_id,
        "designLength": comparison["designLength"], "designWidth": comparison["designWidth"],
        "designThickness": comparison["designThickness"],
        "materialId": record.material_id,
        "materialCode": record.material.code if record.material_id else "",
        "materialName": record.material.name if record.material_id else "",
        "materialSpecification": record.material.specification if record.material_id else "",
        "designUomId": record.design_uom_id,
        "designUomLabel": record.design_uom.name if record.design_uom_id else "",
        "materialProcessTypeId": record.material_process_type_id,
        "materialProcessLabel": record.material_process_type.name if record.material_process_type_id else "",
        "processConfigurationId": data.get("processConfigurationId"),
        "processConfigurationCode": data.get("processConfigurationCode") or data.get("routingProcessCode") or "",
        "processConfigurationLabel": data.get("processConfigurationLabel") or data.get("processConfigurationCode") or data.get("routingProcessCode") or "",
        "paintProcessTypeId": record.paint_process_type_id,
        "paintProcessCode": record.paint_process_type.code if record.paint_process_type_id else "",
        "paintProcessLabel": record.paint_process_type.name if record.paint_process_type_id else "",
        "edgeMethodId": record.edge_method_id,
        "edgeMethodLabel": record.edge_method.name if record.edge_method_id else "",
        **data,
        "legacyD1": {"sourceRecordId": record.legacy_source_record_id, "sourceVersion": record.legacy_source_record.source_version, "contentHash": record.legacy_source_record.content_hash, "solution": legacy} if record.legacy_source_record_id else None,
        "comparison": comparison, "changeReason": record.change_reason,
        "registeredAt": record.created_at.isoformat(),
    }


def _completion_snapshot(record, plan=None):
    if not record:
        return None
    delta = (record.actual_completion_date - plan.planned_finish_date).days if record.actual_completion_date and plan else None
    return {
        "id": record.pk, "sequence": record.sequence,
        "completionNature": record.completion_nature,
        "completionNatureLabel": record.get_completion_nature_display(),
        "actualCompletionDate": record.actual_completion_date.isoformat() if record.actual_completion_date else None,
        "actualCompletionDateLabel": record.actual_completion_date.isoformat() if record.actual_completion_date else "历史完成日期待补",
        "completionBasis": record.completion_basis,
        "completedDesigner": _employee_snapshot(record.completed_designer) if record.completed_designer_id else None,
        "registeredAt": record.recorded_at.isoformat(), "calendarDayVariance": delta,
        "completionAssessment": "无法判定" if delta is None else ("按期完成" if delta <= 0 else f"延期{delta}个自然日"),
        "performanceIncluded": record.completion_nature == "FORMAL" and bool(record.actual_completion_date),
    }


def _status(plan, design, completion):
    if completion:
        if completion["completionNature"] == "REWORK":
            return "返工/变更中"
        if completion["actualCompletionDate"]:
            return "完成已登记"
        return "已有设计完成·日期待补"
    if design:
        return "设计中"
    if plan:
        return "已安排"
    return "待安排"


def _group_plan_status(plan, rows):
    if not plan:
        return "未登记"
    completed = [
        row for row in rows
        if row.get("completion") and row["completion"].get("completionNature") != "REWORK"
    ]
    if rows and len(completed) == len(rows):
        return "已完成"
    if any(row.get("designRevision") for row in rows):
        return "设计中"
    return "计划中"


def product_design_list_field_contract():
    """Return a copy safe for API/export consumers."""
    return [
        {
            "section": "对象身份、来源与产品关联",
            "inputKey": None,
            "singleEditable": bool(field["editable"]),
            "batchEditable": False,
            "quantityOrUnit": field["key"] in {"physicalQuantity", "commercialQuantity", "physicalUnit", "designDimensionUnit"},
            "readOnly": not field["editable"],
            "positions": {
                "list": "主列表",
                "comprehensive": "综合设计区",
                "singleEdit": "单行编辑" if field["editable"] else "只读资料",
                "export": "产品设计当前结果",
                "importTemplate": "业务字段" if field["importable"] else "只读参考字段",
            },
            "saveReadbackRule": "保存后生成ProductDesignRevision并从服务端回读" if field["editable"] else "只读投影，不允许导入或保存改写",
            **PRODUCT_DESIGN_FIELD_RUNTIME.get(field["key"], {}),
            **field,
            "businessMeaning": PRODUCT_DESIGN_FIELD_BUSINESS_MEANINGS[field["key"]],
        }
        for field in PRODUCT_DESIGN_LIST_FIELD_CONTRACT
    ]


def _design_status(plan, design, data_nature):
    if design:
        return "已形成设计修订"
    if data_nature == "EXISTING_DESIGN_IMPORTED":
        return "已有设计资料带入"
    if plan:
        return "已安排"
    return "待安排"


def _completion_status(completion):
    if not completion:
        return "未完成"
    if completion["completionNature"] == "REWORK":
        return "返工/变更中"
    if completion["actualCompletionDate"]:
        return "已完成"
    return "已有完成事实·日期待补"


def _engineering_identity(item):
    """Classify Customer Engineering without inventing a ProductDefinition."""
    if item.product_definition_id:
        return {
            "code": "FORMAL_PRODUCT_LINKED",
            "label": "已关联正式产品",
            "formalProductLinked": True,
            "standardProductReleaseBlocked": False,
            "standardBomBlocked": False,
            "orderEngineeringAllowed": True,
            "basis": "ProductDesignItem.product_definition",
        }
    original = item.original_requirement if isinstance(item.original_requirement, dict) else {}
    existing = item.existing_design_data if isinstance(item.existing_design_data, dict) else {}
    provenance = original.get("provenance") or existing.get("provenance") or {}
    user_entry = provenance.get("sourceType") == "USER_ENTRY" or "-USR-" in item.item_no
    return {
        "code": "CUSTOMER_ENGINEERING" if user_entry else "SOURCE_PRODUCT_UNFORMALIZED",
        "label": "客户定制工程对象" if user_entry else "来源产品待正式化",
        "formalProductLinked": False,
        "standardProductReleaseBlocked": True,
        "standardBomBlocked": True,
        "orderEngineeringAllowed": True,
        "basis": "Customer Engineering user entry" if user_entry else "EngineeringSourceRecord source identity",
    }


def _list_values(row, *, matched_material=None, matched_paint=None, matched_edge=None, source_configuration=None):
    design = row.get("designRevision") or {}
    existing = row.get("existingDesign") or {}
    provenance = row.get("sourceProvenance") or {}
    source_configuration = source_configuration or {}
    material_code = design.get("materialCode") or (matched_material.code if matched_material else "") or existing.get("materialProcessCode") or ""
    material_name = design.get("materialName") or (matched_material.name if matched_material else "")
    material_specification = design.get("materialSpecification") or (matched_material.specification if matched_material else "")
    configuration_code = design.get("processConfigurationCode") or source_configuration.get("code") or existing.get("routingProcessCode") or ""
    configuration_name = design.get("processConfigurationLabel") or source_configuration.get("label") or ""
    if configuration_code and source_configuration.get("source") == "existing-design-source-unmatched" and not design:
        configuration_name = "未匹配正式工艺路线，保留来源值"
    paint_code = design.get("paintProcessCode") or (matched_paint.code if matched_paint else "")
    paint_name = design.get("paintProcessLabel") or (matched_paint.name if matched_paint else "") or existing.get("paintProcess") or ""
    edge_name = design.get("edgeMethodLabel") or (matched_edge.name if matched_edge else "") or existing.get("edgeMethod") or ""
    source_sheet = str(provenance.get("sourceSheet") or "").strip()
    source_row = provenance.get("sourceRow")
    source_position = f"{source_sheet}!{source_row}" if source_sheet and source_row not in (None, "") else source_sheet or "来源位置未登记"
    current = design or existing
    return {
        "productIdentifier": row.get("itemNo") or "",
        "orderLine": f"{row.get('orderNo') or ''} / {row.get('orderLineNo') or ''}",
        "designGroup": row.get("designGroup") or "",
        "productName": row.get("productName") or "",
        "installationPosition": row.get("installationPosition") or row.get("spaceLabel") or "",
        "sourcePosition": source_position,
        "physicalQuantity": row.get("physicalQuantity"),
        "commercialQuantity": row.get("commercialQuantity"),
        "physicalUnit": row.get("physicalUom") or "",
        "unit": row.get("physicalUom") or "",  # compatibility alias; not part of the formal field contract
        "productCategory": row.get("productCategoryLabel") or "来源分类未匹配",
        "formalProductDefinition": row.get("productDefinitionLabel") or "未关联",
        "engineeringIdentityStatus": row.get("engineeringIdentityStatusLabel") or "来源产品待正式化",
        "materialCode": material_code,
        "materialName": material_name,
        "materialSpecification": material_specification,
        "processConfigurationCode": configuration_code,
        "processConfigurationName": configuration_name,
        "paintProcessCode": paint_code,
        "paintProcessName": paint_name,
        "edgeMethod": edge_name,
        "visibleCondition": current.get("visibleCondition") or "",
        "colorVersion": current.get("finishOrColor") or "",
        "designLength": current.get("designLength"),
        "designWidth": current.get("designWidth"),
        "thirdDimension": current.get("designThickness"),
        "thirdDimensionSemantic": row.get("dimensionSemantic") or "",
        "designDimensionUnit": design.get("designUomLabel") or existing.get("designUomLabel") or "",
        "configurationNotes": current.get("configurationNotes") or "",
        "designNotes": current.get("designNotes") or "",
        "hardware": current.get("hardware") or "",
        "glass": current.get("glass") or "",
        "documentReferences": "; ".join(current.get("documentReferences") or []) if isinstance(current.get("documentReferences"), list) else (current.get("documentReferences") or ""),
        "designDataNatureLabel": design.get("designNatureLabel") or row.get("designDataNatureLabel") or "",
        "currentRevisionReason": design.get("changeReason") or "",
        "designer": row.get("ownerLabel") or "待安排",
        "plannedStartDate": row.get("plannedStartDate") or "",
        "plannedFinishDate": row.get("plannedFinishDate") or "",
        "designStatus": _design_status(row.get("plan"), row.get("designRevision"), row.get("designDataNature")),
        "designRevisionLabel": f"R{design['revision']}" if design.get("revision") else "未形成",
        "completionStatus": _completion_status(row.get("completion")),
    }


def _color_version_options(company_id):
    values = []
    for payload in ProductDesignItem.objects.filter(company_id=company_id).values_list("existing_design_data", flat=True):
        if isinstance(payload, dict) and str(payload.get("finishOrColor") or "").strip():
            values.append(str(payload["finishOrColor"]).strip())
    for payload in ProductDesignRevision.objects.filter(design_item__company_id=company_id).values_list("design_data", flat=True):
        if isinstance(payload, dict) and str(payload.get("finishOrColor") or "").strip():
            values.append(str(payload["finishOrColor"]).strip())
    return [{
        "id": f"SOURCE-COLOR-VERSION-{sha256(value.encode('utf-8')).hexdigest()[:16].upper()}",
        "code": f"SOURCE-{sha256(value.encode('utf-8')).hexdigest()[:12].upper()}",
        "name": value, "source": "existing-design-source", "statusLabel": "来源受控候选",
        "sourceCount": values.count(value),
    } for value in sorted(set(values))]


def _process_configuration_options(company_id):
    """Project valid product-design configurations from the formal Routing master.

    Routing is the configuration authority.  ManufacturingProcessType remains the
    independent paint/process dimension linked by the governed Routing relation.
    Source-only codes are returned only as disabled historical readback options.
    """
    items = list(ProductDesignItem.objects.filter(company_id=company_id).only(
        "id", "product_category_id", "product_definition_id", "existing_design_data",
    ))
    by_category = {}
    by_product = {}
    for item in items:
        if item.product_category_id:
            by_category.setdefault(item.product_category_id, []).append(item.pk)
        if item.product_definition_id:
            by_product.setdefault(item.product_definition_id, []).append(item.pk)

    result = []
    formal_codes = set()
    for route in _formal_routing_queryset(company_id).order_by("routing_code", "pk"):
        if route.applicability_scope == "PRODUCT_CATEGORY":
            compatible_ids = by_category.get(route.product_category_id, [])
        elif route.applicability_scope == "PRODUCT_DEFINITION":
            compatible_ids = by_product.get(route.product_id, [])
        else:
            compatible_ids = []
        if not compatible_ids:
            continue
        process = route.manufacturing_process_type
        selectable = bool(process and process.is_active)
        formal_codes.add(str(route.routing_code or "").strip())
        result.append({
            "id": str(route.pk), "routeId": route.pk,
            "code": route.routing_code, "name": route.name or route.routing_code,
            "label": route.name or route.routing_code,
            "source": "pde.Routing", "sourceCount": len(compatible_ids),
            "compatibleItemIds": compatible_ids,
            "applicabilityScope": route.applicability_scope,
            "productCategoryId": route.product_category_id,
            "productDefinitionId": route.product_id,
            "paintProcessTypeId": process.pk if process else None,
            "paintProcessCode": process.code if process else "",
            "paintProcessName": process.name if process else "",
            "paintLinkStatus": "EXACT" if selectable else "NO_MATCH",
            "paintLinkReason": (
                f"Routing正式关系关联油漆工艺 {process.code} · {process.name}。"
                if selectable else "Routing未关联有效油漆工艺，不能用于新设计保存。"
            ),
            "selectable": selectable,
            "statusLabel": "正式工艺路线 · 已发布" if selectable else "正式工艺路线 · 油漆关系无效",
        })

    unmatched = {}
    for item in items:
        existing = item.existing_design_data if isinstance(item.existing_design_data, dict) else {}
        code = str(existing.get("routingProcessCode") or "").strip()
        if not code or code in formal_codes:
            continue
        entry = unmatched.setdefault(code, {
            "id": _process_configuration_id(code), "routeId": None,
            "code": code, "name": code, "label": code,
            "source": "existing-design-source-unmatched", "sourceCount": 0,
            "compatibleItemIds": [], "paintProcessTypeId": None,
            "paintProcessCode": "", "paintProcessName": "",
            "paintLinkStatus": "NO_FORMAL_ROUTING",
            "paintLinkReason": "来源已有，但未匹配当前企业已发布且有效的Routing主表记录；仅回显，不可作为新选择保存。",
            "selectable": False,
            "statusLabel": "来源已有 · Routing未匹配（仅回显）",
        })
        entry["sourceCount"] += 1
        entry["compatibleItemIds"].append(item.pk)
    result.extend(unmatched[code] for code in sorted(unmatched))
    return result


def _master_options(company_id):
    return {
        "productCategories": list(ProductCategory.objects.filter(company_id=company_id, is_active=True).values("id", "code", "name")),
        "products": list(_formal_product_definition_queryset(company_id).values(
            "id", "product_code", "product_name", "specification", "category_id",
        )),
        "uoms": list(UnitOfMeasure.objects.filter(company_id=company_id, is_active=True).values(
            "id", "code", "name", "symbol", "dimension", "conversion_base_id", "conversion_factor", "decimal_places",
        )),
        "materials": list(Material.objects.filter(company_id=company_id, is_active=True).values("id", "code", "name", "specification", "base_uom_id")),
        "processConfigurations": _process_configuration_options(company_id),
        "paintProcessTypes": list(ManufacturingProcessType.objects.filter(company_id=company_id, is_active=True).values("id", "code", "name")),
        "processTypes": list(ManufacturingProcessType.objects.filter(company_id=company_id, is_active=True).values("id", "code", "name")),
        "edgeMethods": list(EngineeringBreakdownOption.objects.filter(company_id=company_id, is_active=True, option_type=EngineeringBreakdownOption.OptionType.EDGE_METHOD).values("id", "code", "name")),
        "visibleConditions": visible_condition_options(),
        "colorVersionOptions": _color_version_options(company_id),
        "unavailableFormalMasters": ["颜色/版号正式主档", "五金规格", "玻璃规格"],
    }


def _product_design_read_context(company_id, order_no=None):
    """Resolve an existing customer-engineering scope without sample preparation rules."""
    design_items = ProductDesignItem.objects.filter(company_id=company_id)
    if order_no:
        order = SalesOrder.objects.filter(company_id=company_id, order_no=order_no).first()
        if not order or not design_items.filter(sales_order_item__sales_order=order).exists():
            raise OrderDemandPreparationError(
                "PRODUCT_DESIGN_ORDER_NOT_FOUND",
                "未找到当前公司范围内已建立产品设计关系的指定销售订单。",
                404,
            )
    else:
        order_ids = list(
            design_items.order_by().values_list(
                "sales_order_item__sales_order_id", flat=True,
            ).distinct()
        )
        if not order_ids:
            raise OrderDemandPreparationError(
                "PRODUCT_DESIGN_CONTEXT_NOT_FOUND",
                "当前公司尚无可读取的客户订单产品设计关系。",
                404,
            )
        if len(order_ids) != 1:
            raise OrderDemandPreparationError(
                "PRODUCT_DESIGN_ORDER_CONTEXT_REQUIRED",
                "当前公司存在多个产品设计订单，请明确选择订单后读取。",
                409,
                {"orderCount": len(order_ids)},
            )
        order = SalesOrder.objects.filter(company_id=company_id, pk=order_ids[0]).first()

    source_ids = list(
        design_items.filter(
            sales_order_item__sales_order=order, source_record_id__isnull=False,
        ).order_by().values_list("source_record_id", flat=True).distinct()
    )
    source = None
    if source_ids:
        # The page has one order-level source context. Multiple persisted source
        # authorities must be selected explicitly instead of silently taking the first.
        if len(source_ids) != 1:
            raise OrderDemandPreparationError(
                "PRODUCT_DESIGN_SOURCE_CONTEXT_AMBIGUOUS",
                "当前订单关联多个工程来源，请先明确来源范围后读取。",
                409,
                {"sourceCount": len(source_ids)},
            )
        source = EngineeringSourceRecord.objects.filter(
            company_id=company_id, pk=source_ids[0],
        ).first()

    review = None
    workflow = None
    approval = None
    if source:
        review = OrderCrossFunctionalReview.objects.filter(
            company_id=company_id,
            source_record=source,
            record_status="SUBMITTED",
        ).order_by("-review_version", "-pk").first()
    if review:
        workflow = WorkflowInstance.objects.filter(
            document_type="PDEProductionFeasibilityReview",
            document_id=review.pk,
            status=WorkflowInstance.Status.APPROVED,
        ).order_by("-version", "-pk").first()
    if workflow:
        approval = ApprovalDecision.objects.select_related("actor").filter(
            task__workflow_instance=workflow,
            decision="approved",
        ).order_by("-completed_at", "-pk").first()
    return order, source, review, workflow, approval


def product_design_facts(company_id, user=None, order_no=None, instance_context=None):
    if instance_context:
        from .product_design_instance_service import resolve
        instance, line, source = resolve(user, instance_context)
        order = line.sales_order
        if order_no and order_no != order.order_no:
            raise ProductDesignError("DESIGN_ORDER_CONTEXT_MISMATCH", "订单编号与工程实例不一致。", 409)
        from .order_engineering_intake_service import _authorization
        authorization = _authorization(instance_context["authorizationId"])
        review = authorization.predecessor_relation.pde_review
        workflow = authorization.workflow_instance
        approval = authorization.approval_decision
    else:
        order, source, review, workflow, approval = _product_design_read_context(
            company_id, order_no=order_no,
        )
    requirement_by_line = {
        int(row["requirementNo"].rsplit("-", 1)[-1]): row
        for row in requirement_facts(company_id)
        if row.get("orderNo") == order.order_no
    }
    items = ProductDesignItem.objects.filter(
        company_id=company_id, sales_order_item__sales_order=order,
    ).select_related(
        "sales_order_item", "sales_order_item__material", "sales_order_item__uom",
        "source_attribute", "source_record", "product_category", "product_definition", "physical_uom",
    ).prefetch_related(
        "design_revisions__material", "design_revisions__material_process_type",
        "design_revisions__paint_process_type", "design_revisions__edge_method",
        "design_revisions__legacy_source_record", "completion_records__completed_designer__position_ref",
        "completion_records__completed_designer__department_ref",
    ).order_by("sales_order_item__line_no", "source_attribute_id")
    group_plan_records = {}
    for record in ProductDesignPlanRevision.objects.filter(order=order).select_related(
        "designer_employee__position_ref", "designer_employee__department_ref",
    ).order_by("design_group", "revision", "pk"):
        current = group_plan_records.get(record.design_group)
        if (
            current is None
            or record.revision > current.revision
            or (
                record.revision == current.revision
                and current.design_item_id is not None
                and record.design_item_id is None
            )
        ):
            group_plan_records[record.design_group] = record
    material_by_id = {row.pk: row for row in Material.objects.filter(company_id=company_id)}
    process_by_id = {row.pk: row for row in ManufacturingProcessType.objects.filter(company_id=company_id)}
    edge_by_id = {row.pk: row for row in EngineeringBreakdownOption.objects.filter(
        company_id=company_id, option_type=EngineeringBreakdownOption.OptionType.EDGE_METHOD,
    )}
    # Historical persisted links remain readable even if a product later becomes inactive.
    # Selection options are separately restricted to current released definitions.
    product_by_id = {row.pk: row for row in ProductDefinition.objects.filter(company_id=company_id)}
    rows = []
    for item in items:
        sales_item = item.sales_order_item
        design_group = _design_group(sales_item.line_no)
        plan_record = group_plan_records.get(design_group)
        design_record = item.design_revisions.order_by("-revision").first()
        completion_record = item.completion_records.order_by("-sequence").first()
        plan = _plan_snapshot(plan_record)
        design = _design_snapshot(design_record)
        completion = _completion_snapshot(completion_record, plan_record)
        requirement = requirement_by_line.get(sales_item.line_no) or {}
        existing = item.existing_design_data or {}
        original = item.original_requirement or {}
        current_matches = dict(item.match_results or {})
        # Master-data identities can be formally corrected after a design item
        # was initialized.  Re-resolve the source material on every read so the
        # UI, strict facts and save form consume the same current server fact
        # instead of a stale initialization snapshot.
        material_source_value = str(existing.get("materialProcessCode") or "").strip()
        if material_source_value:
            current_matches["material"] = _match_material_source(
                company_id, material_source_value,
            )
        effective_product = product_by_id.get(item.product_definition_id)
        effective_category = item.product_category or (effective_product.category if effective_product else None)
        identity = _engineering_identity(item)
        source_configuration = _source_process_configuration(item)
        current_matches["processConfiguration"] = {
            "status": "SOURCE_EXACT" if source_configuration["id"] else "NO_SOURCE_VALUE",
            "sourceValue": source_configuration["code"],
            "matchedId": source_configuration["id"],
            "candidateIds": [source_configuration["id"]] if source_configuration["id"] else [],
        }
        row = {
            "id": item.pk, "version": item.version, "itemNo": item.item_no,
            "designObjectNo": item.item_no,
            "groupNo": f"{order.order_no}-{design_group}",
            "designGroup": design_group,
            "orderNo": order.order_no, "orderLineNo": sales_item.line_no,
            "productName": item.item_name, "spaceLabel": item.space_snapshot or "来源未维护空间",
            "installationPosition": item.installation_position_snapshot,
            "requirementNo": requirement.get("requirementNo", ""),
            "requirementStatusLabel": requirement.get("statusLabel", "需求待形成"),
            "commercialQuantity": str(sales_item.quantity),
            "commercialUom": sales_item.uom.name if sales_item.uom_id else "",
            "physicalQuantity": str(item.physical_quantity) if item.physical_quantity is not None else None,
            "physicalUom": item.physical_uom_snapshot, "productItemCount": 1,
            "physicalUomId": item.physical_uom_id,
            "productCategoryId": effective_category.pk if effective_category else None,
            "productCategoryLabel": effective_category.name if effective_category else "",
            "productDefinitionId": effective_product.pk if effective_product else None,
            "productDefinitionLabel": effective_product.product_name if effective_product else "",
            "productDefinitionPersisted": bool(item.product_definition_id),
            "productDefinitionBindingSource": "ProductDesignItem.product_definition" if item.product_definition_id else "unlinked",
            "engineeringIdentityStatusCode": identity["code"],
            "engineeringIdentityStatusLabel": identity["label"],
            "engineeringIdentityFacts": identity,
            "originalRequirement": original, "existingDesign": existing,
            "designDataNature": item.design_data_nature,
            "designDataNatureLabel": item.get_design_data_nature_display(),
            "matchResults": current_matches, "plan": plan,
            "designRevision": design, "completion": completion,
            "dimensionSemantic": _dimension_semantic(item, design or existing),
            "ownerLabel": (plan or {}).get("designer", {}).get("fullName") or "待安排",
            "plannedStartDate": (plan or {}).get("plannedStartDate"),
            "plannedFinishDate": (plan or {}).get("plannedFinishDate"),
            "actualCompletionDate": (completion or {}).get("actualCompletionDate"),
            "actualCompletionDateLabel": (completion or {}).get("actualCompletionDateLabel") or "未登记",
            "completionAssessment": (completion or {}).get("completionAssessment") or "无法判定",
            "progressLabel": _status(plan, design, completion),
            "sourceProvenance": existing.get("provenance") or original.get("provenance") or {},
            "legacyD1": (design or {}).get("legacyD1"),
        }
        material_match_id = (current_matches.get("material") or {}).get("matchedId")
        paint_match_id = (current_matches.get("paintProcess") or {}).get("matchedId")
        edge_match_id = (current_matches.get("edgeMethod") or {}).get("matchedId")
        row["listValues"] = _list_values(
            row,
            matched_material=material_by_id.get(material_match_id),
            matched_paint=process_by_id.get(paint_match_id),
            matched_edge=edge_by_id.get(edge_match_id),
            source_configuration=source_configuration,
        )
        row.update(row["listValues"])
        rows.append(row)
    groups = []
    for sales_item in order.items.select_related("material", "uom").order_by("line_no"):
        group_rows = [row for row in rows if row["orderLineNo"] == sales_item.line_no]
        design_group = _design_group(sales_item.line_no)
        plan_snapshot = _plan_snapshot(group_plan_records.get(design_group))
        groups.append({
            "groupNo": f"{order.order_no}-{design_group}",
            "designGroup": design_group,
            "orderLineNo": sales_item.line_no,
            "productName": sales_item.customer_product_name or sales_item.material.name,
            "productItemCount": len(group_rows), "physicalQuantityTotal": None,
            "commercialQuantity": str(sales_item.quantity),
            "commercialUom": sales_item.uom.name if sales_item.uom_id else "",
            "completedItemCount": sum(1 for row in group_rows if row["completion"] and row["completion"]["completionNature"] != "REWORK"),
            "datedCompletionCount": sum(1 for row in group_rows if row["actualCompletionDate"]),
            "plan": plan_snapshot,
            "planStatusLabel": _group_plan_status(plan_snapshot, group_rows),
        })
    authorization = AuthorizationService.decide(
        user=user, action_code=PERMISSION_CODE, organization_id=company_id,
        business_object={"organizationId": company_id},
        context={"actionType": "PRODUCT_DESIGN_MANAGEMENT", "businessWrite": True},
    ) if user is not None else None
    return {
        "rows": rows, "groups": groups,
        "listFieldContract": product_design_list_field_contract(),
        "orderContext": {
            "orderId": order.pk, "orderNo": order.order_no,
            "orderStatusLabel": order.get_status_display(), "orderVersion": order.version,
            "customer": order.customer.name, "project": order.project_reference,
            "contractReference": order.contract_reference, "sourceOrderNo": order.external_source_no,
            "requestedDeliveryDate": order.required_delivery_date.isoformat(),
            "committedDeliveryDate": (order.delivery_information or {}).get("committedDeliveryDate"),
        },
        "sourceContext": {
            "sourceRecordId": source.pk if source else None,
            "sourceNo": source.source_no if source else "",
            "sourceVersion": source.source_version if source else "",
            "sourceContentHash": source.content_hash if source else "",
            "sourceNature": "SOURCE",
            "projectName": (
                ((source.source_payload or {}).get("businessOrderReference", {}).get("projectName") if source else None)
                or order.project_reference
            ),
        },
        "reviewContext": {
            "reviewId": review.pk if review else None,
            "reviewVersion": review.review_version if review else None,
            "conclusionLabel": review.get_conclusion_display() if review else "未关联评审",
            "signatureLabel": (
                f"{review.items.filter(is_removed=False, signature_status='SIGNED').count()}/"
                f"{review.items.filter(is_removed=False).count()}已签认"
                if review else "未关联评审"
            ),
            "approvalDecisionId": approval.pk if approval else None,
            "approvalActor": (approval.actor.real_name or approval.actor.username) if approval else "",
            "approvalCompletedAt": approval.completed_at.isoformat() if approval and approval.completed_at else "",
        },
        "designerOptions": _designer_options(source, company_id) if source else [],
        "masterOptions": _master_options(company_id), "authorization": authorization,
        "initialized": len(rows) > 0, "recordCount": len(rows), "groupCount": len(groups),
        "plannedCount": sum(1 for row in rows if row["plan"]),
        "plannedGroupCount": sum(1 for group in groups if group["plan"]),
        "designRevisionCount": sum(1 for row in rows if row["designRevision"]),
        "completedFactCount": sum(1 for row in rows if row["completion"] and row["completion"]["completionNature"] != "REWORK"),
        "datedCompletionCount": sum(1 for row in rows if row["actualCompletionDate"]),
        "performanceIncludedCount": sum(1 for row in rows if row["completion"] and row["completion"]["performanceIncluded"]),
        "formalProductLinkedCount": sum(1 for row in rows if row["engineeringIdentityStatusCode"] == "FORMAL_PRODUCT_LINKED"),
        "sourceProductUnformalizedCount": sum(1 for row in rows if row["engineeringIdentityStatusCode"] == "SOURCE_PRODUCT_UNFORMALIZED"),
        "customerEngineeringCount": sum(1 for row in rows if row["engineeringIdentityStatusCode"] == "CUSTOMER_ENGINEERING"),
        "expectedSourceCounts": {
            **{
                f"DES-{sales_item.line_no:02d}": sales_item.engineering_attributes.count()
                for sales_item in order.items.order_by("line_no")
            },
            "total": sum(
                sales_item.engineering_attributes.count()
                for sales_item in order.items.all()
            ),
        },
        "actualSourceCounts": {**{f"DES-{group['orderLineNo']:02d}": group["productItemCount"] for group in groups}, "total": len(rows)},
        "legacyD1Count": sum(1 for row in rows if row["legacyD1"]),
        "permanentProductCreated": False, "productVersionCreated": False,
        "orderEngineeringInstanceCreated": False, "publishedDownstreamObjectCount": 0,
    }


def save_product_design_draft(*, user, payload, idempotency_key):
    """Backward-compatible adapter for the previously delivered D1 endpoint."""
    if not ProductDesignItem.objects.filter(company_id=user.company_id, sales_order_item_id=payload.get("salesOrderItemId")).exists():
        raise ProductDesignError("DESIGN_PREPARATION_REQUIRED", "请先明确办理首次准备，再保存设计。", 409)
    item = ProductDesignItem.objects.filter(
        company_id=user.company_id,
        sales_order_item_id=int(payload.get("salesOrderItemId") or 0),
    ).order_by("pk").first()
    if not item:
        raise ProductDesignError("DESIGN_OBJECT_NOT_FOUND", "产品设计对象不属于当前订单。", 404)
    solution = payload.get("designSolution") or {}
    translated = {
        "action": "SAVE_DESIGN", "designItemIds": [item.pk],
        "expectedVersions": {str(item.pk): item.version},
        "designNature": "SIMULATED_FOR_TEST",
        "designData": {
            "designLength": solution.get("length"), "designWidth": solution.get("width"),
            "designThickness": solution.get("thickness"), "finishOrColor": solution.get("color"),
            "configurationNotes": solution.get("configurationNotes"),
            "designNotes": solution.get("designNotes"), "hardware": solution.get("hardware"),
            "glass": solution.get("glass"), "documentReferences": [],
        },
        "reason": payload.get("reason") or "兼容保存产品设计草稿",
    }
    return save_design_content(user=user, payload=translated, idempotency_key=idempotency_key)


def design_draft_item_ids(company_id):
    return set(ProductDesignItem.objects.filter(company_id=company_id, design_revisions__isnull=False).values_list("sales_order_item_id", flat=True))


def design_group_progress(company_id):
    progress = {}
    for item in ProductDesignItem.objects.filter(company_id=company_id).select_related(
        "sales_order_item__sales_order",
    ).prefetch_related("design_revisions", "completion_records"):
        row = progress.setdefault(item.sales_order_item_id, {
            "itemCount": 0, "plannedCount": 0, "designRevisionCount": 0,
            "completedFactCount": 0, "datedCompletionCount": 0,
        })
        row["itemCount"] += 1
        row["plannedCount"] += int(bool(_latest_group_plan(
            item.sales_order_item.sales_order_id,
            _design_group(item.sales_order_item.line_no),
        )))
        row["designRevisionCount"] += int(item.design_revisions.exists())
        completion = item.completion_records.order_by("-sequence").first()
        if completion and completion.completion_nature != "REWORK":
            row["completedFactCount"] += 1
            row["datedCompletionCount"] += int(bool(completion.actual_completion_date))
    for row in progress.values():
        total = row["itemCount"]
        if row["completedFactCount"] == total and row["datedCompletionCount"] == total:
            row.update(statusLabel=f"设计完成已登记（{total}/{total}）", nextActionLabel="复核设计完成记录")
        elif row["completedFactCount"] == total:
            row.update(statusLabel=f"已有设计完成·历史日期待补（{total}/{total}）", nextActionLabel="按依据登记历史完成日期")
        elif row["designRevisionCount"]:
            row.update(statusLabel=f"产品设计中（{row['designRevisionCount']}/{total}）", nextActionLabel="继续逐项完善产品设计")
        elif row["plannedCount"]:
            row.update(statusLabel=f"设计计划已安排（{row['plannedCount']}/{total}）", nextActionLabel="按计划办理产品设计")
        else:
            row.update(statusLabel=f"已有设计资料已带入（{total}项）", nextActionLabel="登记设计计划与完成依据")
    return progress


def handle_product_design_action(*, user, payload, idempotency_key):
    action = str(payload.get("action") or "").upper()
    if payload.get("instanceContext") and action not in {"INITIALIZE_ITEMS", "SAVE_DESIGN"}:
        raise ProductDesignError("DESIGN_INSTANCE_ACTION_NOT_AVAILABLE", "本实例接续目前支持首次准备与设计内容保存；其它办理请使用已核定的正式流程。", 409)
    if action == "INITIALIZE_ITEMS":
        from .product_design_instance_service import prepare
        return prepare(user, payload.get("instanceContext") or {}, idempotency_key)
    if action == "SAVE_PLAN":
        return save_design_plan(user=user, payload=payload, idempotency_key=idempotency_key)
    if action == "SAVE_DESIGN":
        return save_design_content(user=user, payload=payload, idempotency_key=idempotency_key)
    if action == "RECORD_COMPLETION":
        return record_design_completion(user=user, payload=payload, idempotency_key=idempotency_key)
    if action == "ADD_ITEM":
        return add_product_design_item(user=user, payload=payload, idempotency_key=idempotency_key)
    if action == "DELETE_ITEM":
        return delete_product_design_item(user=user, payload=payload, idempotency_key=idempotency_key)
    if action == "APPLY_CONFIRMED_CORRECTIONS":
        facts, replayed, _result = apply_confirmed_source_corrections(
            user=user, idempotency_key=idempotency_key,
        )
        return facts, replayed
    if payload.get("salesOrderItemId"):
        return save_product_design_draft(user=user, payload=payload, idempotency_key=idempotency_key)
    raise ProductDesignError("PRODUCT_DESIGN_ACTION_INVALID", "未识别的产品设计动作。")

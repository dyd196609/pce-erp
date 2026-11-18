"""Order engineering baseline facts and controlled save/confirm workflow."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json

from django.db import connection, transaction
from django.db.models import Max
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from pfm.models import Employee
from sales.models import SalesOrder
from system.authorization import AuthorizationService
from system.models import OrganizationOperatingAuditRecord, User
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import create_business_object_with_initial_state, transition_business_object

from .models import OrderEngineeringBaseline, OrderEngineeringBaselineItem, ProductDesignItem, ProductDesignPlanRevision


SAVE_PERMISSION = "production.engineering.baseline.save"
CONFIRM_PERMISSION = "production.engineering.baseline.confirm"
SAVE_ACTION = "pde.order_engineering_baseline.save_draft"
CONFIRM_ACTION = "pde.order_engineering_baseline.confirm"
BASELINE_TABLES = {"pde_order_engineering_baseline", "pde_order_engineering_baseline_item"}


class ProductVersionManagementError(ValueError):
    def __init__(self, code, message, http_status=400, details=None):
        self.code, self.message, self.http_status, self.details = code, message, http_status, details or {}
        super().__init__(message)


def _canonical(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(payload):
    return sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _meaningful(value):
    if value in (None, "", [], {}):
        return False
    if isinstance(value, dict):
        return any(_meaningful(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_meaningful(item) for item in value)
    return True


def _baseline_tables_deployed():
    return BASELINE_TABLES.issubset(set(connection.introspection.table_names()))


def _permission(user, code, order_id=None):
    if not user:
        return {"allowed": False, "decisionCode": "USER_CONTEXT_REQUIRED", "reason": "需要当前登录用户。"}
    return AuthorizationService.decide(
        user=user, action_code=code, organization_id=user.company_id,
        business_object={"organizationId": user.company_id, "salesOrderId": order_id},
        context={"moduleCode": "PDE", "businessWrite": True},
    )


def _order_options(company_id):
    design_order_ids = set(ProductDesignItem.objects.filter(company_id=company_id).values_list("sales_order_item__sales_order_id", flat=True))
    options = []
    orders = SalesOrder.objects.filter(company_id=company_id).select_related("customer").prefetch_related("items__material")
    for order in orders.order_by("-updated_at", "-pk"):
        design_count = ProductDesignItem.objects.filter(company_id=company_id, sales_order_item__sales_order=order).count()
        purchased_finished_count = sum(1 for item in order.items.all() if item.material.material_type == "finished" and item.material.is_purchased and not item.material.is_produced)
        if not design_count and not purchased_finished_count:
            continue
        options.append({
            "orderId": order.pk, "orderNo": order.order_no, "customer": order.customer.name,
            "statusLabel": order.get_status_display(), "orderLineCount": order.items.count(),
            "designItemCount": design_count, "purchasedFinishedGoodLineCount": purchased_finished_count,
            "hasDesignScope": order.pk in design_order_ids,
        })
    return options


def _content_snapshot(item, revision):
    source_attribute = item.source_attribute
    base = {
        "designItem": {
            "id": item.pk, "version": item.version, "itemNo": item.item_no, "itemName": item.item_name,
            "space": item.space_snapshot, "installationPosition": item.installation_position_snapshot,
            "physicalQuantity": str(item.physical_quantity) if item.physical_quantity is not None else None,
            "physicalUomId": item.physical_uom_id, "physicalUom": item.physical_uom_snapshot,
            "productCategoryId": item.product_category_id, "productDefinitionId": item.product_definition_id,
            "originalRequirement": item.original_requirement, "existingDesignData": item.existing_design_data,
            "matchResults": item.match_results, "designDataNature": item.design_data_nature,
        },
        "source": {
            "recordId": item.source_record_id, "attributeId": item.source_attribute_id,
            "sourceNo": item.source_record.source_no, "sourceType": item.source_record.source_type,
            "sourceStatus": item.source_record.status, "sourceVersion": item.source_version,
            "sourceContentHash": item.source_content_hash, "rawSource": source_attribute.raw_source,
            "rawSheet": source_attribute.raw_sheet, "externalSource": source_attribute.external_source,
            "rawField": source_attribute.raw_field, "rawValue": source_attribute.raw_value,
            "normalizedValue": source_attribute.normalized_value, "valueType": source_attribute.value_type,
            "unitId": source_attribute.unit_id,
        },
        "revision": None,
    }
    if revision:
        base["revision"] = {
            "id": revision.pk, "revision": revision.revision, "designNature": revision.design_nature,
            "designLength": str(revision.design_length) if revision.design_length is not None else None,
            "designWidth": str(revision.design_width) if revision.design_width is not None else None,
            "designThickness": str(revision.design_thickness) if revision.design_thickness is not None else None,
            "designUomId": revision.design_uom_id, "materialId": revision.material_id,
            "materialProcessTypeId": revision.material_process_type_id,
            "paintProcessTypeId": revision.paint_process_type_id, "edgeMethodId": revision.edge_method_id,
            "designData": revision.design_data, "sourceProvenance": revision.source_provenance,
            "masterMatchResults": revision.master_match_results, "changeReason": revision.change_reason,
            "createdById": revision.created_by_id, "createdAt": revision.created_at.isoformat(),
        }
    if revision and revision.approval_id:
        approval=revision.approval
        base['approval']={'approvalId':approval.pk,'decisionId':approval.final_decision_id,'sourceRevisionId':approval.source_revision_id,'contentHash':approval.content_hash,'approvalScope':approval.approval_scope,'originNature':approval.origin_nature,'processVersion':approval.process_version}
    return base


def _candidate_row(item, plan):
    revision = item.design_revisions.order_by("-revision", "-pk").first()
    product = item.product_definition
    formal_version = product.product_versions.order_by("-effective_date", "-pk").first() if product else None
    snapshot = _content_snapshot(item, revision)
    has_existing, has_source = _meaningful(item.existing_design_data), _meaningful(item.source_attribute.raw_value)
    source_matches = item.source_version == item.source_record.source_version and item.source_content_hash == item.source_record.content_hash
    if revision and revision.approval_id:
        source_type = 'DESIGN_REVISION'
        try:
            from .baseline_usage_service import successor_evidence
            successor_evidence(revision)
            confirmable, blocker_code, blocker_label = True, '', ''
            eligibility_code, eligibility_label = 'APPROVED_SUCCESSOR', '精确资料已批准，后继可用于对应业务用途'
        except Exception as exc:
            if not hasattr(exc, 'code'):raise
            confirmable, blocker_code, blocker_label = False, exc.code, str(exc)
            eligibility_code, eligibility_label = 'APPROVAL_INVALID', '批准依据无效'
    elif revision:
        source_type = "DESIGN_REVISION"
        if revision.design_nature in {"FORMAL", "EXISTING_DESIGN_IMPORTED"} and source_matches:
            confirmable, blocker_code, blocker_label = True, "", ""
            eligibility_code, eligibility_label = "CONFIRMABLE_REVISION", "设计修订可用于确认"
        elif revision.design_nature == "SIMULATED_FOR_TEST":
            confirmable = False
            blocker_code, blocker_label = "SIMULATED_REVISION_NOT_CONFIRMABLE", "模拟设计修订仅供验证，不能确认正式工程基线。"
            eligibility_code, eligibility_label = "DRAFT_ONLY_SIMULATED_REVISION", "可保存草稿，不能确认"
        else:
            confirmable = False
            blocker_code, blocker_label = "SOURCE_SNAPSHOT_CHANGED", "设计项引用的来源版本已变化，需先核对当前来源。"
            eligibility_code, eligibility_label = "DRAFT_ONLY_STALE_SOURCE", "来源已变化，需核对"
    elif has_existing:
        source_type = "PERSISTED_DESIGN_CONTENT"
        if item.design_data_nature == "SIMULATED_FOR_TEST":
            confirmable = False
            blocker_code, blocker_label = "SIMULATED_CONTENT_NOT_CONFIRMABLE", "模拟工程内容仅供验证，不能确认正式工程基线。"
            eligibility_code, eligibility_label = "DRAFT_ONLY_SIMULATED_CONTENT", "可保存草稿，不能确认"
        elif not has_source:
            confirmable = False
            blocker_code, blocker_label = "SOURCE_EVIDENCE_REQUIRED", "已有工程内容，但缺少可回查的原始来源内容。"
            eligibility_code, eligibility_label = "DRAFT_ONLY_SOURCE_EVIDENCE_GAP", "有工程内容，待补齐来源证据"
        elif not source_matches:
            confirmable = False
            blocker_code, blocker_label = "SOURCE_SNAPSHOT_CHANGED", "设计项引用的来源版本已变化，需先核对当前来源。"
            eligibility_code, eligibility_label = "DRAFT_ONLY_STALE_SOURCE", "来源已变化，需核对"
        else:
            confirmable, blocker_code, blocker_label = True, "", ""
            eligibility_code, eligibility_label = "CONFIRMABLE_FIRST_CONTROLLED_BASELINE", "真实工程内容可由本次确认形成首次受控基线依据"
    elif has_source:
        source_type, confirmable = "SOURCE_CONTENT", False
        blocker_code, blocker_label = "DESIGN_CONTENT_REQUIRED", "存在稳定来源内容，但尚未形成设计内容。"
        eligibility_code, eligibility_label = "DRAFT_SOURCE_ONLY", "仅有来源，待形成设计内容"
    else:
        source_type, confirmable = "MISSING", False
        blocker_code, blocker_label = "ENGINEERING_CONTENT_MISSING", "缺少当前动作所需的工程内容。"
        eligibility_code, eligibility_label = "BLOCKED_MISSING_CONTENT", "缺少工程内容"
    group = f"DES-{item.sales_order_item.line_no:02d}"
    return {
        "designItemId": item.pk, "designItemVersion": item.version, "itemNo": item.item_no,
        "itemName": item.item_name, "designGroup": group, "orderLineNo": item.sales_order_item.line_no,
        "identityCode": "FORMAL_PRODUCT" if product else "CUSTOMER_ENGINEERING",
        "identityLabel": "正式产品关联" if product else "无正式产品的客户工程对象",
        "productDefinitionId": product.pk if product else None, "productCode": product.product_code if product else "",
        "productName": product.product_name if product else "",
        "formalProductVersionId": formal_version.pk if formal_version else None,
        "formalProductVersionNo": formal_version.version_no if formal_version else "",
        "formalProductApplicabilityLabel": "已关联" if formal_version else ("尚未关联" if product else "不适用"),
        "approvalScope": revision.approval_scope if revision else "", "originNature": revision.origin_nature if revision else item.design_data_nature,
        "designRevisionId": revision.pk if revision else None, "designRevision": revision.revision if revision else None,
        "designRevisionLabel": f"R{revision.revision}" if revision else "尚无独立设计修订号",
        "designNature": revision.design_nature if revision else item.design_data_nature,
        "designRevisionReason": revision.change_reason if revision else "",
        "designRevisionCreatedAt": revision.created_at.isoformat() if revision else "",
        "sourceRecordId": item.source_record_id, "sourceAttributeId": item.source_attribute_id,
        "sourceNo": item.source_record.source_no, "sourceVersion": item.source_version,
        "sourceStatus": item.source_record.status, "sourceSnapshotMatchesCurrent": source_matches,
        "responsibleEmployee": plan.designer_employee.full_name if plan else "未安排",
        "snapshotSourceType": source_type, "snapshotSourceTypeLabel": dict(OrderEngineeringBaselineItem.SOURCE_TYPE_CHOICES)[source_type],
        "hasPersistedEngineeringContent": has_existing, "draftSaveAllowed": source_type != "MISSING",
        "confirmable": confirmable, "confirmBlockerCode": blocker_code, "confirmBlockerLabel": blocker_label,
        "baselineEligibilityCode": eligibility_code, "baselineEligibilityLabel": eligibility_label,
        "saveImpactLabel": "可纳入草稿快照" if source_type != "MISSING" else "阻断草稿保存",
        "confirmImpactLabel": "可用于确认" if confirmable else "阻断基线确认",
        "calculationImpactLabel": "当前工程资料仍可按既有规则参与核算；是否要求已确认基线由具体下游动作另行校验",
        "contentSnapshot": snapshot, "contentSnapshotHash": _hash(snapshot),
    }


def _candidate_hash(rows):
    return _hash([{
        "designItemId": row["designItemId"], "designItemVersion": row["designItemVersion"],
        "designRevisionId": row["designRevisionId"], "sourceRecordId": row["sourceRecordId"],
        "sourceAttributeId": row["sourceAttributeId"], "sourceVersion": row["sourceVersion"],
        "contentSnapshotHash": row["contentSnapshotHash"], "confirmBlockerCode": row["confirmBlockerCode"],
    } for row in rows])


def _user_display_name(user):
    name = Employee.objects.filter(user_id=user.pk).values_list("full_name", flat=True).first()
    return name or user.real_name or user.username


def _baseline_user(baseline, field):
    user = baseline._state.fields_cache.get(field)
    if user is None:
        user = User.objects.only("id", "username", "real_name").get(pk=getattr(baseline, field + "_id"))
    return user


def _baseline_display_users(queryset):
    return queryset.select_related("created_by", "confirmed_by").only(
        *[field.attname for field in OrderEngineeringBaseline._meta.concrete_fields],
        "created_by__id", "created_by__username", "created_by__real_name",
        "confirmed_by__id", "confirmed_by__username", "confirmed_by__real_name",
    )


SNAPSHOT_FIELD_DEFINITIONS = (
    ("designItem.itemName", "工程对象名称"),
    ("designItem.space", "空间"),
    ("designItem.installationPosition", "安装位置"),
    ("designItem.physicalQuantity", "数量"),
    ("designItem.physicalUom", "数量单位"),
    ("designItem.originalRequirement", "原始需求"),
    ("designItem.existingDesignData", "已保存工程内容"),
    ("revision.revision", "设计修订号（R）"),
    ("revision.designNature", "设计性质"),
    ("revision.designLength", "长度"),
    ("revision.designWidth", "宽度"),
    ("revision.designThickness", "厚度"),
    ("revision.designUomId", "尺寸单位（稳定编号）"),
    ("revision.materialId", "材料（稳定编号）"),
    ("revision.materialProcessTypeId", "材料工艺（稳定编号）"),
    ("revision.paintProcessTypeId", "涂装工艺（稳定编号）"),
    ("revision.edgeMethodId", "封边方式（稳定编号）"),
    ("revision.designData", "设计参数"),
    ("revision.changeReason", "修订说明"),
    ("source.sourceNo", "来源编号"),
    ("source.sourceVersion", "来源版本"),
    ("source.rawValue", "来源保存值"),
    ("source.normalizedValue", "来源规范值"),
)


def _snapshot_value(snapshot, path):
    value = snapshot
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _display_value(value):
    if value in (None, "", [], {}):
        return "该版未记录"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(", ", ": "))
    return str(value)


def _snapshot_display_fields(snapshot):
    snapshot = snapshot or {}
    return [{
        "fieldCode": path,
        "fieldLabel": label,
        "value": _snapshot_value(snapshot, path),
        "displayValue": _display_value(_snapshot_value(snapshot, path)),
        "recorded": _meaningful(_snapshot_value(snapshot, path)),
    } for path, label in SNAPSHOT_FIELD_DEFINITIONS]


def _snapshot_business_values(snapshot):
    return {path: _snapshot_value(snapshot or {}, path) for path, _ in SNAPSHOT_FIELD_DEFINITIONS}


def _baseline_comparison(older, newer):
    if not older or not newer:
        return {
            "available": False,
            "statusLabel": "暂无其他已保存版本可比较",
            "olderBaseline": None,
            "newerBaseline": None,
            "summary": {"added": 0, "removed": 0, "changed": 0, "same": 0},
            "items": [],
            "baselineChanges": [],
        }
    older_items = {row.design_item_id: row for row in older.items.all()}
    newer_items = {row.design_item_id: row for row in newer.items.all()}
    compared = []
    for design_item_id in sorted(set(older_items) | set(newer_items)):
        before, after = older_items.get(design_item_id), newer_items.get(design_item_id)
        if before is None:
            category, fields = "added", []
        elif after is None:
            category, fields = "removed", []
        else:
            before_values = _snapshot_business_values(before.content_snapshot)
            after_values = _snapshot_business_values(after.content_snapshot)
            fields = [{
                "fieldCode": path,
                "fieldLabel": label,
                "beforeValue": before_values[path],
                "beforeDisplay": _display_value(before_values[path]),
                "afterValue": after_values[path],
                "afterDisplay": _display_value(after_values[path]),
            } for path, label in SNAPSHOT_FIELD_DEFINITIONS if before_values[path] != after_values[path]]
            category = "changed" if fields else "same"
        source = after or before
        compared.append({
            "designItemId": design_item_id,
            "itemNo": source.item_no_snapshot,
            "itemName": source.item_name_snapshot,
            "changeCategory": category,
            "changeCategoryLabel": {"added": "新增项目", "removed": "移除项目", "changed": "业务内容变化", "same": "内容相同"}[category],
            "changedFieldCount": len(fields),
            "changedFields": fields,
        })
    counts = Counter(row["changeCategory"] for row in compared)
    baseline_changes = []
    for code, label, before, after in (
        ("status", "基线状态", older.get_status_display(), newer.get_status_display()),
        ("createdBy", "保存人", _user_display_name(_baseline_user(older, "created_by")), _user_display_name(_baseline_user(newer, "created_by"))),
        ("createdAt", "保存时间", older.created_at.isoformat(), newer.created_at.isoformat()),
        ("confirmedBy", "确认人", _user_display_name(_baseline_user(older, "confirmed_by")) if older.confirmed_by_id else "尚未确认", _user_display_name(_baseline_user(newer, "confirmed_by")) if newer.confirmed_by_id else "尚未确认"),
        ("confirmedAt", "确认时间", older.confirmed_at.isoformat() if older.confirmed_at else "尚未确认", newer.confirmed_at.isoformat() if newer.confirmed_at else "尚未确认"),
    ):
        if before != after:
            baseline_changes.append({"fieldCode": code, "fieldLabel": label, "beforeDisplay": before, "afterDisplay": after})
    return {
        "available": True,
        "statusLabel": f"正在比较 {older.baseline_no} → {newer.baseline_no}",
        "olderBaseline": {"baselineId": older.pk, "baselineNo": older.baseline_no, "statusLabel": older.get_status_display()},
        "newerBaseline": {"baselineId": newer.pk, "baselineNo": newer.baseline_no, "statusLabel": newer.get_status_display()},
        "summary": {"added": counts["added"], "removed": counts["removed"], "changed": counts["changed"], "same": counts["same"]},
        "items": compared,
        "baselineChanges": baseline_changes,
    }


def _baseline_facts(baseline, include_items=False):
    created_by = _baseline_user(baseline, "created_by")
    confirmed_by = _baseline_user(baseline, "confirmed_by") if baseline.confirmed_by_id else None
    transitions = list(BusinessStateTransition.objects.filter(object_type="OrderEngineeringBaseline", object_id=baseline.pk).order_by("version").values("source_state", "target_state", "action_code", "operator_id", "reason", "audit_reference", "version", "timestamp"))
    row = {
        "baselineId": baseline.pk, "baselineNo": baseline.baseline_no, "sequence": baseline.sequence, "approvalScope": baseline.approval_scope,
        "statusCode": baseline.status, "statusLabel": baseline.get_status_display(), "reason": baseline.reason,
        "candidateId": baseline.candidate_hash, "snapshotHash": baseline.snapshot_hash,
        "scopeItemCount": baseline.scope_item_count, "confirmableItemCount": baseline.confirmable_item_count,
        "blockerCount": baseline.blocker_count, "blockerSummary": baseline.blocker_summary,
        "version": baseline.version, "createdBy": created_by.username,
        "createdByName": _user_display_name(created_by),
        "createdAt": baseline.created_at.isoformat(), "confirmedBy": confirmed_by.username if confirmed_by else "",
        "confirmedByName": _user_display_name(confirmed_by) if confirmed_by else "",
        "confirmedAt": baseline.confirmed_at.isoformat() if baseline.confirmed_at else "",
        "statusTransitionHistory": [{**entry, "timestamp": entry["timestamp"].isoformat()} for entry in transitions],
        "statusTransitionCount": len(transitions),
        "stateMachineConsistent": all(entry["version"] == index for index, entry in enumerate(transitions, 1)),
    }
    if include_items:
        row["items"] = [{
            "baselineItemId": item.pk, "designItemId": item.design_item_id,
            "itemNo": item.item_no_snapshot, "itemName": item.item_name_snapshot,
            "designItemVersion": item.design_item_version, "designRevisionId": item.design_revision_id,
            "designRevision": item.design_revision_no, "designNature": item.design_nature_snapshot,
            "sourceRecordId": item.source_record_id, "sourceAttributeId": item.source_attribute_id,
            "approvalScope": (item.content_snapshot.get("approval") or {}).get("approvalScope", ""), "originNature": (item.content_snapshot.get("approval") or {}).get("originNature", ""),
            "sourceType": item.source_type, "sourceTypeLabel": item.get_source_type_display(),
            "sourceVersion": item.source_version_snapshot, "sourceContentHash": item.source_content_hash_snapshot,
            "contentHash": item.content_hash, "contentSnapshot": item.content_snapshot,
            "snapshotDisplayFields": _snapshot_display_fields(item.content_snapshot),
            "confirmable": item.confirmable, "blockerCode": item.blocker_code, "blockerLabel": item.blocker_label,
        } for item in baseline.items.select_related("design_item", "design_revision").order_by("design_item_id")]
    return row


def _saved_baselines(order):
    return [_baseline_facts(row) for row in _baseline_display_users(OrderEngineeringBaseline.objects.filter(company_id=order.company_id, sales_order=order)).order_by("-sequence")]


def _diff_facts(rows, latest):
    if not latest:
        return {"statusCode": "NOT_AVAILABLE_NO_SAVED_BASELINE", "statusLabel": "尚未建立已保存基线，暂无可比较版本", "added": [], "changed": [], "removed": []}
    saved, current = {item.design_item_id: item for item in latest.items.all()}, {row["designItemId"]: row for row in rows}
    added = [row["itemNo"] for key, row in current.items() if key not in saved]
    removed = [item.item_no_snapshot for key, item in saved.items() if key not in current]
    changed = [row["itemNo"] for key, row in current.items() if key in saved and row["contentSnapshotHash"] != saved[key].content_hash]
    return {
        "statusCode": "NO_CHANGE" if not (added or removed or changed) else "CHANGED",
        "statusLabel": "当前工程资料与最近基线一致" if not (added or removed or changed) else "当前工程资料与最近基线存在差异",
        "comparedBaselineId": latest.pk, "comparedBaselineNo": latest.baseline_no,
        "added": added, "changed": changed, "removed": removed,
    }


def product_version_management_facts(company_id, order_no=None, user=None, baseline_id=None):
    options = _order_options(company_id)
    selected = None
    if order_no:
        selected = next((row for row in options if row["orderNo"] == order_no), None)
        if not selected:
            raise ProductVersionManagementError("ORDER_SCOPE_NOT_VISIBLE", "当前公司范围内未找到指定订单的产品版本或工程基线范围。", 404)
    elif len(options) == 1:
        selected = options[0]
    deployed = _baseline_tables_deployed()
    save_decision = _permission(user, SAVE_PERMISSION, selected["orderId"] if selected else None) if deployed else {}
    confirm_decision = _permission(user, CONFIRM_PERMISSION, selected["orderId"] if selected else None) if deployed else {}
    if not deployed:
        persistence = {
            "statusCode": "MODEL_NOT_DEPLOYED", "statusLabel": "订单工程基线保存能力尚未部署",
            "saveDraftAllowed": False, "confirmAllowed": False,
            "reason": "当前环境未应用订单工程基线增量迁移；原只读页面继续可用，读取不会访问缺失表。",
            "requiredAuthorization": "在明确环境应用 pde.0030 并配置正式动作权限",
        }
    else:
        persistence = {
            "statusCode": "READY" if save_decision.get("allowed") else "PERMISSION_REQUIRED",
            "statusLabel": "订单工程基线持久能力已部署" if save_decision.get("allowed") else "已部署，当前账号尚无保存权限",
            "saveDraftAllowed": bool(save_decision.get("allowed")), "confirmAllowed": bool(confirm_decision.get("allowed")),
            "reason": "保存草稿与确认分别经过服务端权限、幂等、并发、事务、审计和提交后回读。",
            "requiredAuthorization": "通过统一角色管理授予准确动作权限" if not save_decision.get("allowed") else "无",
            "savePermission": {"code": SAVE_PERMISSION, "decisionCode": save_decision.get("decisionCode"), "reason": save_decision.get("reason")},
            "confirmPermission": {"code": CONFIRM_PERMISSION, "decisionCode": confirm_decision.get("decisionCode"), "reason": confirm_decision.get("reason")},
        }
    common = {
        "orderOptions": options, "selectedOrder": selected, "savedBaselines": [],
        "savedBaselineStatus": "尚未建立", "savedBaselineStatusCode": "NOT_ESTABLISHED",
        "persistenceCapability": persistence,
        "boundaryFacts": {
            "productDesignRevision": "单个订单设计项的内容修订",
            "orderEngineeringBaseline": "同一订单范围内工程内容及来源的不可变受控快照",
            "productVersion": "可复用正式ProductDefinition的版本；无正式产品客户工程显示不适用",
            "bomVersion": "制造结构版本；保存或确认工程基线不会自动生成",
            "calculationBoundary": "现有工程资料保存、读取及工程核算能力继续保留；只有明确下游动作声明时才要求已确认基线",
            "viewWriteCount": 0,
        },
    }
    if not selected:
        return {**common, "scopeSelectionRequired": len(options) > 1, "candidateRows": [], "candidateBaseline": None, "gapFacts": [], "gapSummary": [], "diffFacts": {"statusCode": "ORDER_SCOPE_REQUIRED", "statusLabel": "请先选择订单范围"}, "nextAction": "选择一个当前公司可见订单后读取候选工程基线。"}
    order = SalesOrder.objects.select_related("customer", "sales_owner").get(company_id=company_id, pk=selected["orderId"])
    items = list(ProductDesignItem.objects.filter(company_id=company_id, sales_order_item__sales_order=order).select_related("sales_order_item", "source_record", "source_attribute", "physical_uom", "product_definition", "product_category").prefetch_related("design_revisions", "product_definition__product_versions").order_by("sales_order_item__line_no", "source_attribute_id", "pk"))
    plans = {}
    for plan in ProductDesignPlanRevision.objects.filter(order=order).select_related("designer_employee").order_by("design_group", "revision", "pk"):
        plans[plan.design_group] = plan
    rows = [_candidate_row(item, plans.get(f"DES-{item.sales_order_item.line_no:02d}")) for item in items]
    gaps = [{
        "designItemId": row["designItemId"], "itemNo": row["itemNo"], "code": row["confirmBlockerCode"],
        "message": row["confirmBlockerLabel"], "sourceType": row["snapshotSourceType"],
        "saveImpactLabel": row["saveImpactLabel"], "confirmImpactLabel": row["confirmImpactLabel"],
        "calculationImpactLabel": row["calculationImpactLabel"],
    } for row in rows if row["confirmBlockerCode"]]
    counts = Counter(row["snapshotSourceType"] for row in rows)
    blockers = Counter(row["confirmBlockerCode"] for row in rows if row["confirmBlockerCode"])
    gap_summary = [{
        "code": code, "label": next(row["confirmBlockerLabel"] for row in rows if row["confirmBlockerCode"] == code),
        "count": count, "itemNos": [row["itemNo"] for row in rows if row["confirmBlockerCode"] == code],
    } for code, count in sorted(blockers.items())]
    purchased_only = not rows and selected["purchasedFinishedGoodLineCount"] > 0
    candidate_id = _candidate_hash(rows) if rows else ""
    candidate = {
        "candidateId": candidate_id, "orderId": order.pk, "orderNo": order.order_no,
        "designItemCount": len(rows), "draftSnapshotItemCount": sum(row["draftSaveAllowed"] for row in rows),
        "confirmableItemCount": sum(row["confirmable"] for row in rows), "gapCount": len(gaps),
        "sourceTypeCounts": dict(counts),
        "statusCode": "PURCHASED_FINISHED_GOOD_BYPASS" if purchased_only else ("CONFIRMABLE" if rows and not gaps else "DRAFT_SNAPSHOT_AVAILABLE" if rows and all(row["draftSaveAllowed"] for row in rows) else "GAPS_PRESENT"),
        "statusLabel": "采购成品无需产品设计基线" if purchased_only else ("候选范围满足确认条件" if rows and not gaps else "工程内容可保存草稿，确认仍有条件未满足" if rows and all(row["draftSaveAllowed"] for row in rows) else "候选范围存在工程内容缺项"),
        "isPersisted": False, "isConfirmed": False, "manufacturingPublished": False,
    }
    saved, latest, selected_baseline, history_comparison = [], None, None, _baseline_comparison(None, None)
    if deployed:
        saved = _saved_baselines(order)
        baseline_rows = list(_baseline_display_users(OrderEngineeringBaseline.objects.filter(
            company_id=company_id, sales_order=order,
        )).prefetch_related("items").order_by("sequence"))
        latest = baseline_rows[-1] if baseline_rows else None
        if baseline_id:
            selected_baseline = next((row for row in baseline_rows if row.pk == int(baseline_id)), None)
            if not selected_baseline:
                raise ProductVersionManagementError("BASELINE_NOT_FOUND", "指定订单工程基线不存在或不属于当前范围。", 404)
        elif latest:
            selected_baseline = latest
        if selected_baseline and len(baseline_rows) > 1:
            selected_index = baseline_rows.index(selected_baseline)
            older = baseline_rows[selected_index - 1] if selected_index > 0 else selected_baseline
            newer = selected_baseline if selected_index > 0 else baseline_rows[selected_index + 1]
            history_comparison = _baseline_comparison(older, newer)
    selected_facts = _baseline_facts(selected_baseline, include_items=True) if selected_baseline else None
    if selected_facts:
        current_by_id = {row["designItemId"]: row for row in rows}
        for item in selected_facts["items"]:
            current = current_by_id.get(item["designItemId"])
            item["currentConfirmable"] = current["confirmable"] if current else False
            item["currentConfirmBlockerLabel"] = current["confirmBlockerLabel"] if current else "当前工程范围已不存在本项。"
    return {
        **common, "scopeSelectionRequired": False,
        "selectedOrder": {**selected, "project": order.project_reference, "requiredDeliveryDate": order.required_delivery_date.isoformat(), "salesOwner": order.sales_owner.full_name if order.sales_owner_id else "未安排"},
        "candidateRows": rows, "candidateBaseline": candidate, "savedBaselines": saved,
        "savedBaselineStatus": saved[0]["statusLabel"] if saved else "尚未建立",
        "savedBaselineStatusCode": saved[0]["statusCode"] if saved else "NOT_ESTABLISHED",
        "selectedBaseline": selected_facts,
        "historyComparison": history_comparison,
        "gapFacts": gaps, "gapSummary": gap_summary, "diffFacts": _diff_facts(rows, latest),
        "nextAction": "当前工程资料可继续按既有规则保存、读取和核算；可先保存真实来源草稿。基线确认只在全部对象满足明确确认条件后开放，且不会自动生成BOM、生产计划或重置评审。",
    }


def _authorize(user, permission_code, order_id):
    decision = _permission(user, permission_code, order_id)
    if not decision.get("allowed"):
        raise ProductVersionManagementError(decision.get("decisionCode", "PERMISSION_DENIED"), decision.get("reason", "当前账号没有该业务动作权限。"), 403)
    return decision


def _write_request(*, user, action_code, entity_type, key, request_body):
    key = str(key or "").strip()
    if not key:
        raise ProductVersionManagementError("IDEMPOTENCY_KEY_REQUIRED", "业务保存必须提供幂等键。")
    request_hash = _hash(request_body)
    scope = request_body.get("orderNo") or request_body.get("baselineId") or "company"
    source_identity, _ = ExternalIdentity.objects.get_or_create(
        organization_id=user.company_id, source_system="PCE_ORDER_ENGINEERING_BASELINE",
        source_type="BUSINESS_ACTION_SCOPE", source_object_type=entity_type,
        external_id=f"{action_code}:{scope}",
        defaults={"target_entity_type": entity_type, "mapping_status": ExternalIdentity.MappingStatus.REVIEW, "source_fingerprint": _hash({"actionCode": action_code, "scope": scope}), "audit_metadata": {"actionCode": action_code, "scope": scope}},
    )
    record, created = MasterDataWriteRequest.objects.select_for_update().get_or_create(
        organization_id=user.company_id, action_code=action_code, entity_type=entity_type, idempotency_key=key,
        defaults={"request_hash": request_hash, "source_identity": source_identity, "audit_metadata": request_body},
    )
    if not created and record.request_hash != request_hash:
        raise ProductVersionManagementError("IDEMPOTENCY_CONFLICT", "同一幂等键已用于不同业务内容。", 409)
    return record, created


def _commit_request(record, result):
    record.status, record.result, record.target_entity_id = MasterDataWriteRequest.Status.COMMITTED, result, str(result.get("baselineId") or "")
    record.save(update_fields=["status", "result", "target_entity_id", "updated_at"])


@transaction.atomic
def save_order_engineering_baseline_draft(*, user, payload, idempotency_key):
    if not _baseline_tables_deployed():
        raise ProductVersionManagementError("MODEL_NOT_DEPLOYED", "当前环境尚未部署订单工程基线模型。", 409)
    order_no, reason = str(payload.get("orderNo") or "").strip(), str(payload.get("reason") or "").strip()
    expected_candidate = str(payload.get("candidateId") or "").strip()
    if not order_no or not reason or not expected_candidate:
        raise ProductVersionManagementError("BASELINE_DRAFT_INPUT_REQUIRED", "保存草稿必须提供订单、候选范围标识和保存原因。")
    order = SalesOrder.objects.select_for_update().filter(company_id=user.company_id, order_no=order_no).first()
    if not order:
        raise ProductVersionManagementError("ORDER_SCOPE_NOT_VISIBLE", "当前公司范围内未找到指定订单。", 404)
    authorization = _authorize(user, SAVE_PERMISSION, order.pk)
    facts = product_version_management_facts(user.company_id, order_no=order_no, user=user)
    candidate, rows = facts["candidateBaseline"], facts["candidateRows"]
    if expected_candidate != candidate["candidateId"]:
        raise ProductVersionManagementError("CANDIDATE_STALE", "保存期间工程来源或设计资料已变化，请重新读取后再保存。", 409, {"expectedCandidateId": expected_candidate, "currentCandidateId": candidate["candidateId"]})
    if not rows or any(not row["draftSaveAllowed"] for row in rows):
        raise ProductVersionManagementError("DRAFT_SCOPE_INCOMPLETE", "当前整单范围存在缺少工程内容的对象，不能保存不完整的整单草稿。", 409)
    request_body = {"orderNo": order_no, "candidateId": expected_candidate, "reason": reason}
    request, created = _write_request(user=user, action_code=SAVE_ACTION, entity_type="OrderEngineeringBaseline", key=idempotency_key, request_body=request_body)
    if not created and request.status == MasterDataWriteRequest.Status.COMMITTED:
        return product_version_management_facts(user.company_id, order_no=order_no, user=user, baseline_id=request.result.get("baselineId")), True
    scopes={row.get('approvalScope','') for row in rows}
    if len(scopes)!=1:
        raise ProductVersionManagementError('BASELINE_MIXED_APPROVAL_SCOPE','不同批准用途不能混存为一份基线。',409)
    scope=next(iter(scopes))
    sequence = (OrderEngineeringBaseline.objects.filter(sales_order=order).aggregate(value=Max("sequence"))["value"] or 0) + 1
    blocker_summary = dict(Counter(row["confirmBlockerCode"] for row in rows if row["confirmBlockerCode"]))
    baseline = create_business_object_with_initial_state(
        model=OrderEngineeringBaseline, initial_state="draft", company_id=user.company_id,
        sales_order=order, approval_scope=scope, baseline_no=f"EB-{order.order_no}-{sequence:03d}", sequence=sequence,
        reason=reason, candidate_hash=candidate["candidateId"],
        snapshot_hash=_hash([row["contentSnapshotHash"] for row in rows]), scope_item_count=len(rows),
        confirmable_item_count=sum(row["confirmable"] for row in rows),
        blocker_count=sum(not row["confirmable"] for row in rows), blocker_summary=blocker_summary, created_by=user,
    )
    for row in rows:
        OrderEngineeringBaselineItem.objects.create(
            baseline=baseline, design_item_id=row["designItemId"], design_revision_id=row["designRevisionId"],
            source_record_id=row["sourceRecordId"], source_attribute_id=row["sourceAttributeId"],
            source_type=row["snapshotSourceType"], item_no_snapshot=row["itemNo"], item_name_snapshot=row["itemName"],
            design_item_version=row["designItemVersion"], design_revision_no=row["designRevision"],
            design_nature_snapshot=row["designNature"], source_version_snapshot=row["sourceVersion"],
            source_content_hash_snapshot=row["contentSnapshot"]["source"]["sourceContentHash"],
            content_snapshot=row["contentSnapshot"], content_hash=row["contentSnapshotHash"],
            confirmable=row["confirmable"], blocker_code=row["confirmBlockerCode"], blocker_label=row["confirmBlockerLabel"],
        )
    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code=SAVE_ACTION, actor=user, organization_id=user.company_id,
        target_type="OrderEngineeringBaseline", target_id=baseline.pk, target_label=baseline.baseline_no,
        reason=reason, before_snapshot={},
        after_snapshot={"baselineId": baseline.pk, "baselineNo": baseline.baseline_no, "status": baseline.status, "scopeItemCount": baseline.scope_item_count, "candidateHash": baseline.candidate_hash, "snapshotHash": baseline.snapshot_hash, "authorization": authorization},
    )
    result = {"baselineId": baseline.pk, "baselineNo": baseline.baseline_no, "auditId": audit.pk, "version": baseline.version}
    _commit_request(request, result)
    return product_version_management_facts(user.company_id, order_no=order_no, user=user, baseline_id=baseline.pk), False


@transaction.atomic
def confirm_order_engineering_baseline(*, user, payload, idempotency_key):
    if not _baseline_tables_deployed():
        raise ProductVersionManagementError("MODEL_NOT_DEPLOYED", "当前环境尚未部署订单工程基线模型。", 409)
    baseline_id, expected_version = payload.get("baselineId"), payload.get("expectedVersion")
    reason = str(payload.get("reason") or "").strip()
    if not baseline_id or expected_version in (None, "") or not reason:
        raise ProductVersionManagementError("BASELINE_CONFIRM_INPUT_REQUIRED", "确认必须提供基线、当前版本和确认原因。")
    baseline = OrderEngineeringBaseline.objects.select_for_update().select_related("sales_order").filter(pk=baseline_id, company_id=user.company_id).first()
    if not baseline:
        raise ProductVersionManagementError("BASELINE_NOT_FOUND", "订单工程基线不存在或不属于当前范围。", 404)
    authorization = _authorize(user, CONFIRM_PERMISSION, baseline.sales_order_id)
    request_body = {"baselineId": baseline.pk, "expectedVersion": int(expected_version), "reason": reason}
    request, created = _write_request(user=user, action_code=CONFIRM_ACTION, entity_type="OrderEngineeringBaseline", key=idempotency_key, request_body=request_body)
    if not created and request.status == MasterDataWriteRequest.Status.COMMITTED:
        return product_version_management_facts(user.company_id, order_no=baseline.sales_order.order_no, user=user, baseline_id=baseline.pk), True
    if baseline.status != "draft":
        raise ProductVersionManagementError("BASELINE_STATUS_INVALID", "只有草稿工程基线允许确认。", 409)
    if baseline.version != int(expected_version):
        raise ProductVersionManagementError("BASELINE_VERSION_CONFLICT", "工程基线已被其他人员更新，请重新读取。", 409, {"expectedVersion": expected_version, "currentVersion": baseline.version})
    if baseline.blocker_count:
        raise ProductVersionManagementError("BASELINE_CONFIRM_BLOCKED", "当前草稿仍包含不能用于确认的工程对象。", 409, {"blockerCount": baseline.blocker_count, "blockerSummary": baseline.blocker_summary})
    current = product_version_management_facts(user.company_id, order_no=baseline.sales_order.order_no, user=user)
    if current["candidateBaseline"]["candidateId"] != baseline.candidate_hash:
        raise ProductVersionManagementError("BASELINE_SOURCE_CHANGED", "保存后工程来源或设计资料已变化；旧草稿保留，请保存新的草稿后再确认。", 409, {"savedCandidateId": baseline.candidate_hash, "currentCandidateId": current["candidateBaseline"]["candidateId"]})
    from .baseline_usage_service import validate_baseline
    validate_baseline(baseline, purpose=baseline.approval_scope or 'PRODUCTION_USE', allow_draft=True)
    audit = OrganizationOperatingAuditRecord.objects.create(
        action_code=CONFIRM_ACTION, actor=user, organization_id=user.company_id,
        target_type="OrderEngineeringBaseline", target_id=baseline.pk, target_label=baseline.baseline_no,
        reason=reason, before_snapshot={"status": baseline.status, "version": baseline.version},
        after_snapshot={"status": "confirmed", "version": baseline.version + 1, "snapshotHash": baseline.snapshot_hash, "authorization": authorization},
    )
    transition_business_object(
        business_object=baseline, object_type="OrderEngineeringBaseline", source_state="draft", target_state="confirmed",
        action_code=CONFIRM_ACTION, operator=user, reason=reason,
        audit_reference=f"OrganizationOperatingAuditRecord:{audit.pk}", allowed_transitions=(("draft", "confirmed"),),
    )
    baseline.confirmed_by, baseline.confirmed_at = user, timezone.now()
    baseline._baseline_confirmation_metadata_authorized = True
    try:
        baseline.save(update_fields=["confirmed_by", "confirmed_at", "updated_at"])
    finally:
        baseline._baseline_confirmation_metadata_authorized = False
    result = {"baselineId": baseline.pk, "baselineNo": baseline.baseline_no, "auditId": audit.pk, "version": baseline.version}
    _commit_request(request, result)
    return product_version_management_facts(user.company_id, order_no=baseline.sales_order.order_no, user=user, baseline_id=baseline.pk), False


def handle_product_version_management_action(*, user, payload, idempotency_key):
    action = str(payload.get("action") or "").strip()
    if action == "saveDraft":
        return save_order_engineering_baseline_draft(user=user, payload=payload, idempotency_key=idempotency_key)
    if action == "confirmBaseline":
        return confirm_order_engineering_baseline(user=user, payload=payload, idempotency_key=idempotency_key)
    raise ProductVersionManagementError("ACTION_NOT_SUPPORTED", "不支持的订单工程基线动作。")

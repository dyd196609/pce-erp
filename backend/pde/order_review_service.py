from hashlib import sha256
import json
import uuid

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from pfm.formal_employee import formal_employee_queryset
from pfm.models import Employee
from system.authorization import AuthorizationService
from system.models import UserRoleScopeAssignment
from pce_backend.identity_context import database_identity
from workflow_runtime.state_transitions import transition_business_object

from .models import (EngineeringSourceRecord, OrderCrossFunctionalReview,
    OrderCrossFunctionalReviewItem, OrderReviewItemAudit, OrderReviewParticipantGrant,
    OrderReviewSalesOrderRelation, OrderReviewTemplate)
from .crm_sales_order_identity import assess_relation_identity, source_business_identity
from .review_permission_catalog import review_item_permission, review_permission_config
from .order_review_approval import (
    OrderReviewApprovalError, build_approval_facts, create_pending_approval,
    decide_final_approval,
)

REVIEW_CONFIG = {
    "CRM_ORDER_REVIEW": {"moduleCode": "CRM", "title": "订单评审", "purpose": "判断能否接单，以及按什么商业条件接单。"},
    "PDE_PRODUCTION_FEASIBILITY": {"moduleCode": "PDE", "title": "生产可行性评审", "purpose": "判断当前工程是否能够实现，以及需要补齐什么条件。"},
}
STANDARD_REASONS = ["依据不足", "条件未落实", "风险不可接受", "需补充确认", "其它"]

class ReviewBusinessError(Exception):
    def __init__(self, code, message, http_status=400):
        self.code, self.message, self.http_status = code, message, http_status
        super().__init__(message)

def _order_reference(payload):
    value = payload.get("businessOrderReference") if isinstance(payload, dict) else {}
    return value if isinstance(value, dict) else {}

def _row_count(payload):
    if isinstance(payload.get("crmIntake"), dict) and isinstance(payload.get("engineeringRows"), list):
        return len(payload["engineeringRows"])
    scope = payload.get("registeredSourceScope") if isinstance(payload, dict) else {}
    if isinstance(scope, dict) and scope.get("sourceCount") is not None: return int(scope.get("sourceCount") or 0)
    for key in ("sourceRows", "rows", "records"):
        if isinstance(payload.get(key), list): return len(payload[key])
    return 0

def _item_content(item):
    return {"text": item.item_text, "evidence": item.evidence_note, "decision": item.decision,
        "reasonCode": item.disagreement_reason_code, "reasonText": item.disagreement_reason_text,
        "responsibleEmployeeId": item.responsible_employee_id, "sourceVersion": item.review.source_version,
        "templateVersion": item.review.template_version}

def _content_hash(item):
    return sha256(json.dumps(_item_content(item), ensure_ascii=False, sort_keys=True).encode()).hexdigest()

def _item_row(item, *, current_employee_id=None, employee_access=None, item_eligibility=None,
        responsibility_match=None):
    employee = item.responsible_employee
    access = (employee_access or {}).get(employee.pk, {}) if employee else {}
    eligibility = (item_eligibility or {}).get(item.item_code, {})
    employee_item_allowed = bool(employee and employee.pk in eligibility.get("eligibleEmployeeIds", []))
    current_is_responsible = bool(
        employee and current_employee_id and employee.pk == current_employee_id
    )
    can_current_sign = bool(
        current_is_responsible
        and access.get("canSignOwnItems")
        and employee_item_allowed
    )
    if item.signature_status == "SIGNED" and item.signature_content_hash == _content_hash(item):
        signing_readiness = {
            "statusCode": "ALREADY_SIGNED",
            "statusLabel": "已完成本人签认",
            "executable": False,
            "disabledReason": "该项已经完成有效本人签认。",
        }
    elif item.review.record_status != "DRAFT":
        signing_readiness = {
            "statusCode": "REVIEW_STATE_NOT_SIGNABLE",
            "statusLabel": "当前版本不可签认",
            "executable": False,
            "disabledReason": "当前评审或版本不允许签认。",
        }
    elif not employee:
        signing_readiness = {
            "statusCode": "RESPONSIBLE_EMPLOYEE_REQUIRED",
            "statusLabel": "责任人待确定",
            "executable": False,
            "disabledReason": "尚未指定本项责任人。",
        }
    elif not current_is_responsible:
        signing_readiness = {
            "statusCode": "OTHER_EMPLOYEE_RESPONSIBLE",
            "statusLabel": "由责任人本人签认",
            "executable": False,
            "disabledReason": "该项由其他责任人签认。",
        }
    elif not can_current_sign:
        signing_readiness = {
            "statusCode": "OWN_SIGN_QUALIFICATION_MISSING",
            "statusLabel": "本人签认资格不足",
            "executable": False,
            "disabledReason": (
                access.get("signatureRoutingBlock")
                or eligibility.get("missingReason")
                or "当前身份缺少本项本人签认资格。"
            ),
        }
    elif not item.decision:
        signing_readiness = {
            "statusCode": "OWN_OPINION_NOT_SAVED",
            "statusLabel": "本人意见待保存",
            "executable": False,
            "disabledReason": "请先保存本人意见。",
        }
    elif item.decision == "DISAGREE" and (
        not item.disagreement_reason_code
        or (
            item.disagreement_reason_code == "其它"
            and not item.disagreement_reason_text.strip()
        )
    ):
        signing_readiness = {
            "statusCode": "OWN_OPINION_INCOMPLETE",
            "statusLabel": "必填内容待完成",
            "executable": False,
            "disabledReason": "本项必填内容尚未完成。",
        }
    else:
        signing_readiness = {
            "statusCode": "READY_TO_SIGN_OWN_ITEM",
            "statusLabel": "可由本人签认",
            "executable": True,
            "disabledReason": "",
        }
    return {"id": item.pk, "stableKey": item.stable_key, "itemKind": item.item_kind,
        "itemCode": item.item_code, "itemText": item.item_text, "evidenceNote": item.evidence_note,
        "decision": item.decision, "decisionLabel": item.get_decision_display() if item.decision else "请选择",
        "disagreementReasonCode": item.disagreement_reason_code, "disagreementReasonText": item.disagreement_reason_text,
        "responsibleEmployeeId": item.responsible_employee_id,
        "responsibleEmployee": ({"id": employee.pk, "employeeNo": employee.employee_no, "name": employee.full_name,
            "hasActiveLoginAccount": bool(employee.user_id and employee.user and employee.user.is_active),
            "username": employee.user.username if employee.user_id else "",
            "firstLoginSetupComplete": access.get("firstLoginSetupComplete", False),
            "canViewReview": access.get("canViewReview", False),
            "canMaintainOwnOpinion": access.get("canMaintainOwnOpinion", False),
            "canSignOwnItems": access.get("canSignOwnItems", False),
            "hasItemQualification": employee_item_allowed,
            "signatureEntryReady": bool(access.get("signatureEntryReady", False) and employee_item_allowed),
            "signatureRoutingBlock": (access.get("signatureRoutingBlock") or eligibility.get("missingReason") or "未指定责任人") if not employee_item_allowed else access.get("signatureRoutingBlock", "")} if employee else None),
        "itemPermissionCode": eligibility.get("permissionCode", ""),
        "eligibleEmployeeIds": eligibility.get("eligibleEmployeeIds", []),
        "responsibilityMatch": responsibility_match or {},
        "canCurrentUserEdit": bool(current_is_responsible and access.get("canMaintainOwnOpinion") and employee_item_allowed),
        "canCurrentUserSign": can_current_sign,
        "signingReadiness": signing_readiness,
        "signatureStatus": item.signature_status, "signatureStatusLabel": item.get_signature_status_display(),
        "signedEmployee": ({"id": item.signed_employee_id_snapshot, "employeeNo": item.signed_employee_no_snapshot, "name": item.signed_employee_name_snapshot} if item.signed_employee_id_snapshot else None),
        "signedAt": item.signed_at.isoformat() if item.signed_at else None, "contentRevision": item.content_revision,
        "canRemove": item.item_kind == "OTHER" and item.review.record_status == "DRAFT", "isRemoved": item.is_removed}

def summarize_items(items):
    active = [i for i in items if not i.is_removed]
    invalid = []
    for item in active:
        if not item.decision: invalid.append(f"{item.item_code} 未判定")
        if item.decision == "DISAGREE" and not item.disagreement_reason_code: invalid.append(f"{item.item_code} 不同意原因未选择")
        if item.decision == "DISAGREE" and item.disagreement_reason_code == "其它" and not item.disagreement_reason_text.strip(): invalid.append(f"{item.item_code} 其它原因未说明")
        if not item.responsible_employee_id: invalid.append(f"{item.item_code} 未指定责任人")
        if item.signature_status != "SIGNED" or item.signature_content_hash != _content_hash(item): invalid.append(f"{item.item_code} 未有效签认")
    agree = sum(i.decision == "AGREE" for i in active); disagree = sum(i.decision == "DISAGREE" for i in active)
    return {"total": len(active), "agree": agree, "disagree": disagree, "pending": sum(not i.decision for i in active),
        "signed": sum(i.signature_status == "SIGNED" and i.signature_content_hash == _content_hash(i) for i in active),
        "complete": not invalid, "incompleteReasons": invalid,
        "derivedConclusion": "REJECT" if not invalid and disagree else ("ACCEPT" if not invalid else "")}

def _audit(review, actor, action, item=None, before=None, after=None):
    stamp = timezone.now().isoformat()
    payload = {"review": review.pk, "item": item.pk if item else None, "action": action, "actor": actor.pk,
        "at": stamp, "before": before or {}, "after": after or {}, "nonce": uuid.uuid4().hex}
    return OrderReviewItemAudit.objects.create(review=review, item=item, action=action, actor=actor,
        before_snapshot=before or {}, after_snapshot=after or {},
        audit_hash=sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest())

def _ensure_assignment_object_grants(review, actor):
    """Create object/version grants for qualified assignees without adding roles."""
    if review.review_type != "PDE_PRODUCTION_FEASIBILITY":
        return []
    assigned = list(
        review.items.filter(is_removed=False, responsible_employee__isnull=False)
        .select_related("responsible_employee__user")
    )
    by_employee = {}
    for item in assigned:
        by_employee.setdefault(item.responsible_employee_id, []).append(item)
    created = []
    actions = review_permission_config(review.review_type)["actions"]
    for employee_id, items in by_employee.items():
        employee = items[0].responsible_employee
        account = employee.user if employee.user_id else None
        if not account or not account.is_active:
            continue
        if any(
            not _employee_item_eligibility(
                employee, review.review_type, item.item_code, review.company_id, actions,
            )["eligible"]
            for item in items
        ):
            continue
        grant, was_created = OrderReviewParticipantGrant.objects.get_or_create(
            review=review,
            employee=employee,
            user=account,
            defaults={
                "company_id": review.company_id,
                "review_version_snapshot": review.review_version,
                "source_version_snapshot": review.source_version,
                "can_view": True,
                "can_maintain_own_opinion": True,
                "can_sign_own_items": True,
                "active": True,
                "reason": "通过正式责任分配形成当前评审对象及版本授权",
                "created_by": actor,
                "audit_hash": sha256(json.dumps({
                    "reviewId": review.pk,
                    "employeeId": employee_id,
                    "userId": account.pk,
                    "reviewVersion": review.review_version,
                    "sourceVersion": review.source_version,
                    "itemCodes": sorted(item.item_code for item in items),
                    "at": timezone.now().isoformat(),
                }, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
            },
        )
        if was_created:
            created.append(grant.pk)
            _audit(review, actor, "PARTICIPANT_OBJECT_GRANT_CREATED", None, {}, {
                "grantId": grant.pk,
                "employeeId": employee_id,
                "userId": account.pk,
                "reviewVersion": review.review_version,
                "sourceVersion": review.source_version,
                "itemCodes": sorted(item.item_code for item in items),
                "roleWrites": 0,
                "permissionWrites": 0,
            })
    return created

def resolve_source(user, source_record_id=None):
    queryset = EngineeringSourceRecord.objects.filter(company_id=user.company_id); requested = None
    if source_record_id:
        requested = queryset.filter(pk=source_record_id).first()
        if not requested: raise ReviewBusinessError("SOURCE_NOT_VISIBLE", "当前公司范围内未找到指定工程来源。", 404)
        queryset = queryset.filter(source_no=requested.source_no)
    else:
        from sales.services import SalesBusinessError
        try:
            from sales.development_contract_sample import build_development_contract_entry
            entry = build_development_contract_entry(company_id=user.company_id, user=user)
            configured_id = entry.get("target", {}).get("query", {}).get("sourceRecord")
            requested = queryset.filter(pk=configured_id).first()
        except SalesBusinessError:
            requested = None
        if not requested:
            raise ReviewBusinessError(
                "REVIEW_OBJECT_REQUIRED",
                "当前流程没有确定唯一评审对象，请从已关联的订单、客户和项目入口进入后重新读取。",
                409,
            )
        queryset = queryset.filter(source_no=requested.source_no)
    candidates = list(queryset.order_by("-created_at", "-pk")[:100])
    source = next((row for row in candidates if _order_reference(row.source_payload).get("sourceOrderNo")), requested)
    if not source: raise ReviewBusinessError("ORDER_SOURCE_NOT_FOUND", "当前公司没有可用于评审的订单工程来源。", 404)
    return source


def _participant_grant(user, review, *, employee=None):
    if not user or not review or not getattr(user, "is_active", False):
        return None
    employee = employee or formal_employee_queryset(company_id=review.company_id).filter(
        user_id=user.pk
    ).first()
    if not employee or user.company_id != review.company_id:
        return None
    grant = OrderReviewParticipantGrant.objects.filter(
        review=review, company_id=review.company_id, employee=employee, user=user,
        active=True, review_version_snapshot=review.review_version,
        source_version_snapshot=review.source_version,
    ).first()
    if not grant:
        return None
    if not review.items.filter(responsible_employee=employee, is_removed=False).exists():
        return None
    return grant


def _crm_participant_employee(user, review, *, employee=None):
    """Resolve the formal employee identity behind CRM item responsibility."""
    if (
        not user or not review or review.review_type != "CRM_ORDER_REVIEW"
        or not getattr(user, "is_active", False)
        or user.company_id != review.company_id
    ):
        return None
    queryset = formal_employee_queryset(company_id=review.company_id).filter(user_id=user.pk)
    if employee is not None:
        queryset = queryset.filter(pk=employee.pk)
    return queryset.first()


def _crm_participant_has_item_responsibility(user, review, *, employee=None):
    """Use the current CRM Review item assignment as the object boundary."""
    employee = _crm_participant_employee(user, review, employee=employee)
    return bool(
        employee
        and review.items.filter(
            responsible_employee=employee,
            is_removed=False,
        ).exists()
    )


def _capability_facts(*, allowed, action_code, disabled_reason=""):
    return {
        "actionCode": action_code,
        "visible": bool(allowed),
        "executable": bool(allowed),
        "disabledReason": "" if allowed else disabled_reason,
    }

def _authorization(user, action_code, company_id):
    return AuthorizationService.decide(
        user=user, action_code=action_code, organization_id=company_id,
        business_object={"companyId": company_id},
    )

def _item_authorization(user, review_type, item_code, company_id):
    permission = review_item_permission(review_type, item_code)
    if review_type != "PDE_PRODUCTION_FEASIBILITY":
        return {"allowed": True, "actionCode": "NOT_APPLICABLE"}
    if str(item_code).startswith("O"):
        # Dynamic OTHER rows have no reusable template-item qualification. Their
        # scope is the explicit review/version responsibility assignment; the
        # caller still enforces the relevant own-opinion/sign action permission.
        return {
            "allowed": True,
            "actionCode": "ASSIGNED_OTHER_ITEM_SCOPE",
            "reason": "其它评审事项资格来自当前评审版本的正式责任分配。",
        }
    if not permission:
        return {"allowed": False, "actionCode": "", "reason": f"事项 {item_code} 没有正式事项权限映射。"}
    if user.is_superuser:
        formal = UserRoleScopeAssignment.objects.filter(
            user=user,
            organization_id=company_id,
            active=True,
            role__rolepermission__permission__code=permission[0],
        ).exists()
        if not formal:
            return {
                "allowed": False,
                "actionCode": permission[0],
                "reason": "系统管理员身份不替代PDE具体事项资格。",
            }
    return _authorization(user, permission[0], company_id)

def _employee_item_eligibility(employee, review_type, item_code, company_id, actions):
    account = employee.user if employee.user_id else None
    permission = review_item_permission(review_type, item_code)
    if review_type != "PDE_PRODUCTION_FEASIBILITY":
        return {"eligible": bool(account and account.is_active), "permissionCode": "", "reason": ""}
    if not account or not account.is_active:
        return {"eligible": False, "permissionCode": permission[0] if permission else "", "reason": "未关联当前公司有效登录账户"}
    if review_type == "PDE_PRODUCTION_FEASIBILITY" and str(item_code).startswith("O"):
        action_decisions = [
            _authorization(account, actions[key][0], company_id)
            for key in ("view", "maintainOwnOpinion", "signOwnItems")
        ]
        eligible = all(row.get("allowed") for row in action_decisions)
        return {
            "eligible": eligible,
            "permissionCode": "",
            "reason": "" if eligible else "缺少查看／本人意见／本人签认操作权限",
        }
    item_decision = _item_authorization(account, review_type, item_code, company_id)
    action_decisions = [
        _authorization(account, actions[key][0], company_id)
        for key in ("view", "maintainOwnOpinion", "signOwnItems")
    ]
    eligible = bool(item_decision.get("allowed") and all(row.get("allowed") for row in action_decisions))
    return {
        "eligible": eligible,
        "permissionCode": permission[0] if permission else "",
        "reason": "" if eligible else (
            f"缺少事项权限 {permission[0]} 或查看／本人意见／本人签认操作权限" if permission
            else f"事项 {item_code} 没有正式事项权限映射"
        ),
    }


def _responsibility_role_sources(employee, review_type, item_code, company_id, actions):
    account = employee.user if employee.user_id else None
    if not account:
        return []
    permission = review_item_permission(review_type, item_code)
    required_codes = {
        actions[key][0] for key in ("view", "maintainOwnOpinion", "signOwnItems")
    }
    if permission:
        required_codes.add(permission[0])
    assignments = (
        UserRoleScopeAssignment.objects.filter(
            user=account, organization_id=company_id, active=True,
            role__rolepermission__permission__code__in=required_codes,
        )
        .select_related("role")
        .prefetch_related("role__rolepermission_set__permission")
        .distinct()
        .order_by("role__code", "pk")
    )
    sources = []
    for assignment in assignments:
        granted = sorted({
            row.permission.code
            for row in assignment.role.rolepermission_set.all()
            if row.permission.code in required_codes
        })
        if granted:
            sources.append({
                "assignmentId": assignment.pk,
                "roleCode": assignment.role.code,
                "roleName": assignment.role.name,
                "scopeCode": assignment.scope_code,
                "permissionCodes": granted,
            })
    return sources


def _responsibility_candidate(employee, review_type, item_code, company_id, actions):
    account = employee.user if employee.user_id else None
    return {
        "employeeId": employee.pk,
        "employeeNo": employee.employee_no,
        "employeeName": employee.full_name,
        "position": employee.position_ref.name if employee.position_ref else (employee.position or "未关联正式岗位"),
        "username": account.username if account else "",
        "accountActive": bool(account and account.is_active),
        "firstLoginSetupComplete": bool(account and account.has_usable_password()),
        "roleSources": _responsibility_role_sources(
            employee, review_type, item_code, company_id, actions,
        ),
    }


def _responsibility_match_plan(*, review_type, company_id, template, employees, actions,
        existing_review=None):
    existing_by_code = {}
    if existing_review:
        existing_by_code = {
            item.item_code: item
            for item in existing_review.items.select_related(
                "responsible_employee__user", "responsible_employee__position_ref",
            ).filter(is_removed=False, item_kind="FIXED")
        }
    rows = []
    for template_item in template.items.filter(is_applicable=True):
        existing_item = existing_by_code.get(template_item.item_code)
        if existing_item and existing_item.responsible_employee_id:
            employee = existing_item.responsible_employee
            candidate = _responsibility_candidate(
                employee, review_type, template_item.item_code, company_id, actions,
            )
            rows.append({
                "itemCode": template_item.item_code,
                "itemText": template_item.item_text,
                "statusCode": "CURRENT_VERSION_ASSIGNED",
                "statusLabel": "当前版本已有责任人",
                "proposedEmployeeId": employee.pk,
                "selected": candidate,
                "candidates": [candidate],
                "candidateCount": 1,
                "matchBasis": "优先保留当前正式评审版本已经保存的责任记录；角色变化不会在刷新时覆盖该记录。",
                "requiresManualResolution": False,
            })
            continue
        candidates = []
        missing_reasons = set()
        for employee in employees:
            eligibility = _employee_item_eligibility(
                employee, review_type, template_item.item_code, company_id, actions,
            )
            if eligibility["eligible"]:
                candidates.append(_responsibility_candidate(
                    employee, review_type, template_item.item_code, company_id, actions,
                ))
            elif eligibility.get("reason"):
                missing_reasons.add(eligibility["reason"])
        if len(candidates) == 1:
            selected = candidates[0]
            login_pending = not selected["firstLoginSetupComplete"]
            status_code = "AUTO_MATCHED_UNIQUE_LOGIN_PENDING" if login_pending else "AUTO_MATCHED_UNIQUE"
            status_label = "已自动匹配，账号待安全初始化" if login_pending else "已按正式分工自动匹配"
            basis = "当前公司、事项权限、查看、维护本人意见、签认本人项目及有效范围共同筛选后，仅有一名合格正式员工。"
            requires_manual = False
            proposed_id = selected["employeeId"]
        elif len(candidates) > 1:
            selected = None
            status_code = "PENDING_MULTIPLE_CANDIDATES"
            status_label = "责任人待确定"
            basis = f"现有正式配置产生 {len(candidates)} 名合格员工，且没有可复用的明确默认分工；系统不会按顺序随机选人。"
            requires_manual = True
            proposed_id = None
        else:
            selected = None
            status_code = "MISSING_QUALIFIED_RESPONSIBLE"
            status_label = "该事项缺少责任配置"
            basis = "；".join(sorted(missing_reasons)[:3]) or "未找到同时具备正式员工、有效账户、事项资格、本人动作与适用范围的人员。"
            requires_manual = True
            proposed_id = None
        rows.append({
            "itemCode": template_item.item_code,
            "itemText": template_item.item_text,
            "statusCode": status_code,
            "statusLabel": status_label,
            "proposedEmployeeId": proposed_id,
            "selected": selected,
            "candidates": candidates,
            "candidateCount": len(candidates),
            "matchBasis": basis,
            "requiresManualResolution": requires_manual,
        })
    return rows

def _allowed(*decisions):
    return any(decision and decision.get("allowed") for decision in decisions)

def _context(
        user, review_type, source_record_id, *, crm_order_relation_id=None,
        sales_order_id=None, formal_context_required=False):
    config = REVIEW_CONFIG.get(review_type)
    if not config: raise ReviewBusinessError("REVIEW_TYPE_INVALID", "评审类型无效。")
    permission_config = review_permission_config(review_type)
    if not permission_config:
        raise ReviewBusinessError("REVIEW_PERMISSION_CONFIG_MISSING", "评审权限目录配置缺失。", 500)
    actions = permission_config["actions"]
    formal_context = None
    if review_type == "PDE_PRODUCTION_FEASIBILITY" and formal_context_required:
        from .order_demand_preparation_service import (
            OrderDemandPreparationError,
            _resolve_formal_preparation_context,
        )
        try:
            formal_context = _resolve_formal_preparation_context(
                user.company_id,
                crm_order_relation_id=crm_order_relation_id,
                sales_order_id=sales_order_id,
            )
        except OrderDemandPreparationError as exc:
            raise ReviewBusinessError(exc.code, exc.message, exc.http_status) from exc
        source = formal_context["source"]
        if source_record_id not in (None, ""):
            try:
                requested_source_id = int(source_record_id)
            except (TypeError, ValueError) as exc:
                raise ReviewBusinessError(
                    "PDE_REVIEW_SOURCE_SELECTOR_INVALID",
                    "PDE产品需求评审来源标识无效。",
                ) from exc
            if requested_source_id != source.pk:
                raise ReviewBusinessError(
                    "PDE_REVIEW_FORMAL_CONTEXT_MISMATCH",
                    "页面提交的来源与0032正式前置关系不一致，已失败关闭。",
                    409,
                )
        payload = source.source_payload or {}
        order_ref = _order_reference(payload)
        contract = None
        order_no = formal_context["crm_review"].source_order_no
    else:
        source = resolve_source(user, source_record_id)
        payload, order_ref = source.source_payload or {}, _order_reference(source.source_payload or {}); contract = None
        try:
            from sales.development_contract_sample import build_development_contract_entry
            candidate = build_development_contract_entry(company_id=source.company_id, user=user)
            if int(candidate.get("target", {}).get("query", {}).get("sourceRecord") or 0) == source.pk: contract = candidate
        except Exception: pass
        order_no = str((contract or {}).get("sourceOrderNo") or order_ref.get("sourceOrderNo") or source.source_no)
    template = OrderReviewTemplate.objects.prefetch_related("items").filter(review_type=review_type, is_active=True).order_by("-effective_from", "-id").first()
    if not template: raise ReviewBusinessError("REVIEW_TEMPLATE_MISSING", "未找到当前评审类型的有效正式模板。", 409)
    current_review = OrderCrossFunctionalReview.objects.filter(
        company_id=source.company_id, source_order_no=order_no, review_type=review_type,
    ).order_by("-review_version").first()
    if formal_context:
        current_review = OrderCrossFunctionalReview.objects.filter(company_id=source.company_id, review_type=review_type, pde_predecessor_relation__crm_order_relation_id=formal_context["relation"].pk).order_by("-review_version").first()
    participant_grant = _participant_grant(user, current_review)
    crm_item_responsibility = _crm_participant_has_item_responsibility(user, current_review)
    view_role = _authorization(user, actions["view"][0], source.company_id)
    manage = _authorization(user, actions["manageDraft"][0], source.company_id)
    own_opinion_role = _authorization(user, actions["maintainOwnOpinion"][0], source.company_id)
    sign_role = _authorization(user, actions["signOwnItems"][0], source.company_id)
    submit = _authorization(user, actions["submit"][0], source.company_id)
    final_approve = _authorization(user, actions["finalApprove"][0], source.company_id) if actions.get("finalApprove") else None
    legacy_view = _authorization(user, permission_config["legacyViewAction"], source.company_id)
    legacy_manage = _authorization(user, permission_config["legacyManageAction"], source.company_id)
    elevated_view = _allowed(manage, submit, final_approve, legacy_view, legacy_manage)
    module_view = bool(view_role["allowed"] or elevated_view)
    participant_view = bool(
        view_role["allowed"]
        and (
            crm_item_responsibility
            if review_type == "CRM_ORDER_REVIEW"
            else participant_grant and participant_grant.can_view
        )
    )
    normal_flow_without_review = bool(current_review is None and source_record_id is None and module_view)
    if not module_view:
        company_name = getattr(getattr(source, "company", None), "name", "当前公司")
        scope_denied = view_role.get("decisionCode") == "SCOPE_DENIED"
        raise ReviewBusinessError(
            "REVIEW_SCOPE_DENIED" if scope_denied else "VIEW_PERMISSION_DENIED",
            (
                f"当前账号 {user.username} 已登记“{permission_config['moduleName']} - 查看”动作，但公司或数据范围不覆盖当前流程；评审对象授权未评估。"
                if scope_denied else
                f"当前账号 {user.username} 在 {company_name}（公司ID {source.company_id}）缺少“{permission_config['moduleName']} - 查看”动作权限；评审对象授权未评估。"
            ),
            403,
        )
    if current_review is not None and not (participant_view or elevated_view):
        raise ReviewBusinessError(
            "REVIEW_OBJECT_ACCESS_REQUIRED",
            "当前账号已具备生产可行性评审模块查看资格，但尚未获得当前评审对象、版本及本人责任分配；请由有权准备人员在正式评审中保存责任人。",
            403,
        )
    if current_review is None and not normal_flow_without_review and not elevated_view:
        raise ReviewBusinessError(
            "REVIEW_OBJECT_ACCESS_REQUIRED",
            "当前账号已具备生产可行性评审模块查看资格，但指定来源尚未形成可由本人读取的正式评审对象；请从正常业务流程进入，或由有权准备人员建立评审并保存责任人。",
            403,
        )
    if normal_flow_without_review:
        view_reason = "已具备模块查看资格；当前尚未建立正式评审，责任分配与对象授权尚未形成。"
        view_decision = "ALLOWED_MODULE_VIEW_REVIEW_NOT_ESTABLISHED"
    elif participant_view:
        if review_type == "CRM_ORDER_REVIEW":
            view_reason = "有效员工身份、角色权限、组织范围与当前评审本人责任项目共同允许查看。"
            view_decision = "ALLOWED_CRM_ROLE_SCOPE_AND_ITEM_RESPONSIBILITY"
        else:
            view_reason = "角色权限与当前评审对象、版本及本人责任授权共同允许查看。"
            view_decision = "ALLOWED_REVIEW_ROLE_AND_OBJECT"
    else:
        view_reason = "正式准备、提交或审批职责允许查看。"
        view_decision = "ALLOWED_COMPATIBILITY"
    view = {**view_role, "allowed": True,
        "reason": view_reason,
        "decisionCode": view_decision,
        "formalReviewEstablished": current_review is not None,
        "moduleViewQualified": module_view,
        "facts": _capability_facts(allowed=True, action_code=actions["view"][0])}
    decisions = {
        "manage": manage, "ownOpinion": own_opinion_role, "sign": sign_role,
        "submit": submit, "finalApprove": final_approve, "legacyView": legacy_view, "legacyManage": legacy_manage,
    }
    return (
        config, permission_config, source, payload, order_ref, contract, order_no,
        template, view, decisions, participant_grant, crm_item_responsibility,
        formal_context,
    )

def _review_row(row, *, user=None):
    approval = build_approval_facts(user=user, review=row) if user else None
    final_decision = (approval or {}).get("finalDecision") or {}
    conclusion = final_decision.get("decision") or ""
    conclusion_label = final_decision.get("decisionLabel") or "尚无最终审批结论"
    return {"id": row.pk, "reviewVersion": row.review_version, "reviewType": row.review_type, "title": row.get_review_type_display(),
        "recordStatus": row.record_status, "statusLabel": row.get_record_status_display(), "conclusion": conclusion or "",
        "conclusionLabel": conclusion_label or "尚无最终审批结论", "reviewOpinion": row.review_opinion,
        "reviewer": {"id": row.reviewer_id, "name": row.reviewer.real_name},
        "executedAt": (row.submitted_at or row.created_at).isoformat(), "sourceRecordId": row.source_record_id,
        "sourceVersion": row.source_version, "templateVersion": row.template_version, "summary": row.item_summary,
        "opinionSummaryLabel": f"同意 {int((row.item_summary or {}).get('agree') or 0)} 项／不同意 {int((row.item_summary or {}).get('disagree') or 0)} 项",
        "approval": approval, "auditHash": row.audit_hash}


def _formal_sales_order_projection(*, review, company_id, relation=None):
    """Read the existing formal Review -> SalesOrder relation without creating it."""
    from .admission_chain_revocation import active_crm_order_relations

    revoked_relation = None
    if relation is not None and hasattr(relation, "admission_chain_revocation"):
        revoked_relation = relation
        relation = None
    if relation is None and review:
        relation = (
            active_crm_order_relations(
                OrderReviewSalesOrderRelation.objects.select_related(
                "review__source_record", "sales_order__customer",
                ).prefetch_related(
                "scope_items__sales_order_item__material",
                "scope_items__sales_order_item__uom",
                )
            )
            .filter(company_id=company_id, review_id=review.pk)
            .first()
        )
        if relation is None:
            revoked_relation = (
                OrderReviewSalesOrderRelation.objects.select_related("sales_order")
                .filter(
                    company_id=company_id,
                    review_id=review.pk,
                    admission_chain_revocation__isnull=False,
                )
                .first()
            )
    if not relation:
        revoked = revoked_relation is not None
        return {
            "formalSalesOrderEstablished": False,
            "formalSalesOrderCondition": (
                "历史正式订单关系已撤销；当前不存在有效的旧0032 / PDE / OEI准入链。"
                if revoked else
                "尚未建立正式销售订单；本页评审仅绑定当前来源及版本，不替代正式订单建立。"
            ),
            "formalSalesOrderRevoked": revoked,
            "revokedFormalSalesOrderRelationId": (
                revoked_relation.pk if revoked_relation else None
            ),
            "formalSalesOrderRelationId": None,
            "formalSalesOrderId": None,
            "formalSalesOrderNo": "",
            "formalSalesOrderStatusCode": "",
            "formalSalesOrderStatusLabel": "",
            "formalSalesOrderCustomerName": "",
            "formalSalesOrderProjectReference": "",
            "formalSalesOrderContractReference": "",
            "sourceBusinessIdentityStatusCode": (
                "REVOKED" if revoked else "NOT_AVAILABLE"
            ),
            "sourceBusinessIdentityStatusLabel": (
                "历史正式关系已撤销" if revoked else "尚未建立正式销售订单"
            ),
            "sourceBusinessIdentityConsistent": False,
            "sourceBusinessIdentityComparisons": [],
        }
    order = relation.sales_order
    identity = assess_relation_identity(relation)
    condition = (
        "已建立正式销售订单；来源业务身份一致。"
        if identity["allowed"] else
        "已存在正式销售订单关系，但来源业务身份冲突或证明不完整；该关系仅只读保留，禁止继续作为下游准入依据。"
    )
    return {
        "formalSalesOrderEstablished": True,
        "formalSalesOrderRevoked": False,
        "revokedFormalSalesOrderRelationId": None,
        "formalSalesOrderCondition": condition,
        "formalSalesOrderRelationId": relation.pk,
        "formalSalesOrderId": order.pk,
        "formalSalesOrderNo": order.order_no,
        "formalSalesOrderStatusCode": order.status,
        "formalSalesOrderStatusLabel": order.get_status_display(),
        "formalSalesOrderCustomerName": order.customer.name,
        "formalSalesOrderProjectReference": order.project_reference,
        "formalSalesOrderContractReference": order.contract_reference,
        "sourceBusinessIdentityStatusCode": identity["statusCode"],
        "sourceBusinessIdentityStatusLabel": identity["statusLabel"],
        "sourceBusinessIdentityConsistent": identity["allowed"],
        "sourceBusinessIdentityComparisons": identity["comparisons"],
    }

def _eligible_employees(company_id):
    return formal_employee_queryset(
        Employee.objects.select_related("department_ref", "position_ref"),
        company_id=company_id,
    ).order_by("employee_no")

def build_review_facts(
        *, user, review_type, source_record_id=None, crm_order_relation_id=None,
        sales_order_id=None, formal_context_required=False):
    (
        config, permission_config, source, payload, order_ref, contract, order_no,
        template, view, decisions, participant_grant, crm_item_responsibility,
        formal_context,
    ) = _context(
        user, review_type, source_record_id,
        crm_order_relation_id=crm_order_relation_id,
        sales_order_id=sales_order_id,
        formal_context_required=formal_context_required,
    )
    actions = permission_config["actions"]
    reviews = list(OrderCrossFunctionalReview.objects.select_related("reviewer").filter(company_id=source.company_id, source_order_no=order_no, review_type=review_type).order_by("-review_version"))
    if formal_context:
        reviews = [r for r in reviews if getattr(r, "pde_predecessor_relation", None) and r.pde_predecessor_relation.crm_order_relation_id == formal_context["relation"].pk]
    draft = next((r for r in reviews if r.record_status == "DRAFT"), None); submitted = [r for r in reviews if r.record_status == "SUBMITTED"]
    draft_items = list(draft.items.select_related("responsible_employee__user", "review").filter(is_removed=False)) if draft else []
    latest_submitted = submitted[0] if submitted else None
    formal_review = draft or latest_submitted
    formal_sales_order = _formal_sales_order_projection(
        review=formal_review, company_id=source.company_id,
        relation=formal_context["relation"] if formal_context else None,
    )
    submitted_items = list(latest_submitted.items.select_related("responsible_employee__user", "review").filter(is_removed=False)) if latest_submitted else []
    display_items = draft_items if draft else submitted_items
    other_type = "PDE_PRODUCTION_FEASIBILITY" if review_type == "CRM_ORDER_REVIEW" else "CRM_ORDER_REVIEW"
    if formal_context and review_type == "PDE_PRODUCTION_FEASIBILITY":
        other = formal_context["crm_review"]
    else:
        other = OrderCrossFunctionalReview.objects.select_related("reviewer").filter(company_id=source.company_id, source_order_no=order_no, review_type=other_type, record_status="SUBMITTED").order_by("-review_version").first()
    eligible_employees = list(_eligible_employees(source.company_id).select_related("user"))
    current_employee = next((employee for employee in eligible_employees if employee.user_id == user.pk), None)
    full_write_allowed = _allowed(decisions["manage"], decisions["legacyManage"])
    responsibility_plan = _responsibility_match_plan(
        review_type=review_type,
        company_id=source.company_id,
        template=template,
        employees=eligible_employees,
        actions=actions,
        existing_review=formal_review,
    ) if review_type == "PDE_PRODUCTION_FEASIBILITY" else []
    responsibility_by_code = {row["itemCode"]: row for row in responsibility_plan}
    employee_access = {}
    for employee in eligible_employees:
        if not employee.user_id or not employee.user or not employee.user.is_active:
            employee_access[employee.pk] = {"firstLoginSetupComplete": False, "canViewReview": False,
                "canMaintainOwnOpinion": False, "canSignOwnItems": False,
                "signatureEntryReady": False, "signatureRoutingBlock": "未关联有效登录账号"}
            continue
        employee_grant = _participant_grant(employee.user, draft or latest_submitted, employee=employee)
        crm_employee_responsibility = _crm_participant_has_item_responsibility(
            employee.user, draft or latest_submitted, employee=employee,
        )
        employee_view = _authorization(employee.user, actions["view"][0], source.company_id)
        employee_manage = _authorization(employee.user, actions["manageDraft"][0], source.company_id)
        employee_opinion = _authorization(employee.user, actions["maintainOwnOpinion"][0], source.company_id)
        employee_sign = _authorization(employee.user, actions["signOwnItems"][0], source.company_id)
        employee_legacy_view = _authorization(employee.user, permission_config["legacyViewAction"], source.company_id)
        employee_legacy_manage = _authorization(employee.user, permission_config["legacyManageAction"], source.company_id)
        participant_view_qualified = (
            crm_employee_responsibility
            if review_type == "CRM_ORDER_REVIEW"
            else employee_grant and employee_grant.can_view
        )
        participant_opinion_qualified = (
            crm_employee_responsibility
            if review_type == "CRM_ORDER_REVIEW"
            else employee_grant and employee_grant.can_maintain_own_opinion
        )
        participant_sign_qualified = (
            crm_employee_responsibility
            if review_type == "CRM_ORDER_REVIEW"
            else employee_grant and employee_grant.can_sign_own_items
        )
        can_view = bool(_allowed(employee_manage, employee_legacy_view, employee_legacy_manage)
            or (employee_view["allowed"] and participant_view_qualified))
        can_opinion = bool(_allowed(employee_manage, employee_legacy_manage)
            or (employee_opinion["allowed"] and participant_opinion_qualified))
        can_sign = bool(_allowed(employee_manage, employee_legacy_manage)
            or (employee_sign["allowed"] and participant_sign_qualified))
        first_login_ready = employee.user.has_usable_password()
        if not first_login_ready:
            block = "账号已建立，首次登录安全设置待本人完成"
        elif not can_view:
            block = "缺少当前评审查看授权"
        elif not can_sign:
            block = "缺少本人负责项目签认授权"
        else:
            block = ""
        employee_access[employee.pk] = {"firstLoginSetupComplete": first_login_ready,
            "canViewReview": can_view, "canMaintainOwnOpinion": can_opinion,
            "canSignOwnItems": can_sign, "signatureEntryReady": not block,
            "signatureRoutingBlock": block}
    item_eligibility = {}
    for template_item in template.items.filter(is_applicable=True):
        eligible_ids = []
        missing_reasons = []
        permission = review_item_permission(review_type, template_item.item_code)
        for employee in eligible_employees:
            decision = _employee_item_eligibility(
                employee, review_type, template_item.item_code, source.company_id, actions,
            )
            if decision["eligible"]:
                eligible_ids.append(employee.pk)
            elif decision["reason"]:
                missing_reasons.append(decision["reason"])
        item_eligibility[template_item.item_code] = {
            "permissionCode": permission[0] if permission else "",
            "permissionName": permission[1] if permission else "",
            "eligibleEmployeeIds": eligible_ids,
            "missingReason": (missing_reasons[0] if missing_reasons else ""),
        }
    for other_code in sorted({
        item.item_code for item in display_items if item.item_kind == "OTHER"
    }):
        eligible_ids = []
        missing_reasons = []
        for employee in eligible_employees:
            decision = _employee_item_eligibility(
                employee, review_type, other_code, source.company_id, actions,
            )
            if decision["eligible"]:
                eligible_ids.append(employee.pk)
            elif decision["reason"]:
                missing_reasons.append(decision["reason"])
        item_eligibility[other_code] = {
            "permissionCode": "",
            "permissionName": "本次评审版本正式责任分配",
            "eligibleEmployeeIds": eligible_ids,
            "missingReason": (missing_reasons[0] if missing_reasons else ""),
        }
    other_candidate_ids = []
    other_candidate_missing_reasons = []
    for employee in eligible_employees:
        decision = _employee_item_eligibility(
            employee, review_type, "O00", source.company_id, actions,
        )
        if decision["eligible"]:
            other_candidate_ids.append(employee.pk)
        elif decision["reason"]:
            other_candidate_missing_reasons.append(decision["reason"])
    if review_type != "PDE_PRODUCTION_FEASIBILITY":
        other_candidate_status = "NOT_APPLICABLE"
        other_candidate_label = "本模块沿用现有责任人选择规则"
    elif not full_write_allowed:
        other_candidate_status = "SELECTION_PERMISSION_DENIED"
        other_candidate_label = "当前身份没有新增事项责任选择资格"
    elif other_candidate_ids:
        other_candidate_status = "AVAILABLE"
        other_candidate_label = f"已取得 {len(other_candidate_ids)} 名符合条件的正式责任候选"
    else:
        other_candidate_status = "NO_ELIGIBLE_CANDIDATES"
        other_candidate_label = "未找到符合条件的责任人"
    other_responsibility_candidates = {
        "statusCode": other_candidate_status,
        "statusLabel": other_candidate_label,
        "ruleCode": "PDE_OTHER_RESPONSIBILITY_ACTION_QUALIFICATION_V1",
        "ruleDescription": "按当前公司正式员工、有效账户、角色范围以及查看、维护本人意见、签认本人项目三项动作资格筛选；不要求预先持有尚未形成的对象授权。",
        "requiredActionCodes": [
            actions[key][0]
            for key in ("view", "maintainOwnOpinion", "signOwnItems")
        ],
        "eligibleEmployeeIds": (
            other_candidate_ids
            if review_type == "PDE_PRODUCTION_FEASIBILITY" and full_write_allowed
            else []
        ),
        "candidateCount": (
            len(other_candidate_ids)
            if review_type == "PDE_PRODUCTION_FEASIBILITY" and full_write_allowed
            else None
        ),
        "selectionExecutable": bool(
            review_type == "PDE_PRODUCTION_FEASIBILITY" and full_write_allowed
        ),
        "disabledReason": (
            "" if full_write_allowed else "当前账号没有本评审完整草稿维护及责任选择资格。"
        ),
        "noCandidateReason": (
            "；".join(sorted(set(other_candidate_missing_reasons)))
            if full_write_allowed and not other_candidate_ids
            else ""
        ),
        "readCreatesBusinessRecords": False,
    }
    employees = [{"id": e.pk, "employeeNo": e.employee_no, "name": e.full_name,
        "department": e.department_ref.name if e.department_ref else (e.department_name or "未关联正式部门"),
        "position": e.position_ref.name if e.position_ref else (e.position or "未关联正式岗位"),
        "username": e.user.username if e.user_id else "",
        "canCurrentUserSign": e.user_id == user.pk,
        "hasActiveLoginAccount": bool(e.user_id and e.user and e.user.is_active),
        **employee_access[e.pk]} for e in eligible_employees]
    template_items = [{"stableKey": f"FIXED-{i.item_code}", "itemKind": "FIXED", "itemCode": i.item_code,
        "itemText": i.item_text, "evidenceNote": "", "decision": "", "disagreementReasonCode": "",
        "disagreementReasonText": "", "responsibleEmployeeId": (
            responsibility_by_code.get(i.item_code, {}).get("proposedEmployeeId")
            if full_write_allowed else None
        ), "signatureStatus": "UNSIGNED",
        "signatureStatusLabel": "未签认", "signedAt": None, "reasonOptions": i.disagreement_reasons or STANDARD_REASONS,
        "itemPermissionCode": item_eligibility[i.item_code]["permissionCode"],
        "eligibleEmployeeIds": item_eligibility[i.item_code]["eligibleEmployeeIds"],
        "responsibilityMatch": responsibility_by_code.get(i.item_code, {}) if full_write_allowed else {},
        "canRemove": False} for i in template.items.filter(is_applicable=True)]
    assigned_employee_ids = sorted({i.responsible_employee_id for i in display_items if i.responsible_employee_id})
    responsible_readiness = []
    for employee in eligible_employees:
        if employee.pk not in assigned_employee_ids:
            continue
        assigned = [i for i in display_items if i.responsible_employee_id == employee.pk]
        access = employee_access[employee.pk]
        missing_item_permissions = [
            item_eligibility.get(i.item_code, {}).get("missingReason")
            or item_eligibility.get(i.item_code, {}).get("permissionCode")
            or f"事项 {i.item_code} 未登记"
            for i in assigned
            if employee.pk not in item_eligibility.get(i.item_code, {}).get("eligibleEmployeeIds", [])
        ]
        account_real_name = employee.user.real_name if employee.user_id else ""
        normal_login_ready = bool(employee.user_id and employee.user and employee.user.is_active and employee.user.has_usable_password())
        actual_login_verified = bool(normal_login_ready and employee.user.last_login)
        if actual_login_verified:
            login_status = "已完成安全设置并有实际登录记录"
        elif normal_login_ready:
            login_status = "初始密码已可用，待本人首次登录验证"
        else:
            login_status = "账号已建立；系统无本人自助首次设置入口，待账户管理员设置初始密码"
        responsible_readiness.append({"employeeId": employee.pk, "employeeNo": employee.employee_no,
            "name": employee.full_name, "username": employee.user.username if employee.user_id else "未关联账号",
            "accountActive": bool(employee.user_id and employee.user and employee.user.is_active),
            "firstLoginSetupComplete": access.get("firstLoginSetupComplete", False),
            "canAttemptNormalLogin": normal_login_ready,
            "actualLoginVerified": actual_login_verified,
            "lastLoginAt": employee.user.last_login.isoformat() if actual_login_verified else None,
            "loginPreparationStatusLabel": login_status,
            "accountRealName": account_real_name,
            "identityNote": (f"账号显示实名为“{account_real_name}”，正式签认身份以关联员工“{employee.full_name}（{employee.employee_no}）”及认证记录为准。"
                if account_real_name and account_real_name != employee.full_name else "账号显示实名与关联员工一致。"),
            "canViewReview": access.get("canViewReview", False),
            "canMaintainOwnOpinion": access.get("canMaintainOwnOpinion", False),
            "canSignOwnItems": access.get("canSignOwnItems", False),
            "signatureEntryReady": bool(access.get("signatureEntryReady", False) and not missing_item_permissions),
            "remainingCondition": ("缺少事项资格：" + "、".join(missing_item_permissions)) if missing_item_permissions else (access.get("signatureRoutingBlock") or "无"),
            "assignedItemCodes": [i.item_code for i in assigned],
            "signedItemCount": sum(i.signature_status == "SIGNED" and i.signature_content_hash == _content_hash(i) for i in assigned)})
    eligible_submitters = []
    for employee in eligible_employees:
        account = employee.user if employee.user_id else None
        if not account or not account.is_active or not account.has_usable_password():
            continue
        decision = AuthorizationService.decide(
            user=account, action_code=actions["submit"][0], organization_id=source.company_id,
            business_object={"companyId": source.company_id},
        )
        legacy_decision = _authorization(account, permission_config["legacyManageAction"], source.company_id)
        if _allowed(decision, legacy_decision):
            eligible_submitters.append({"employeeId": employee.pk, "employeeNo": employee.employee_no,
                "name": employee.full_name, "username": account.username,
                "permissionAction": actions["submit"][0],
                "authorizationSource": "legacyCompatibility" if legacy_decision["allowed"] and not decision["allowed"] else "reviewPermission",
                "qualification": "具备正式提交资格"})
    full_write = _capability_facts(allowed=full_write_allowed, action_code=actions["manageDraft"][0],
        disabled_reason="当前账号没有本评审完整草稿维护权限。")
    participant_opinion_qualified = (
        crm_item_responsibility
        if review_type == "CRM_ORDER_REVIEW"
        else participant_grant and participant_grant.can_maintain_own_opinion
    )
    participant_sign_qualified = (
        crm_item_responsibility
        if review_type == "CRM_ORDER_REVIEW"
        else participant_grant and participant_grant.can_sign_own_items
    )
    own_opinion_allowed = bool(
        full_write_allowed
        or (decisions["ownOpinion"]["allowed"] and participant_opinion_qualified)
    )
    sign_allowed = bool(
        (review_type != "PDE_PRODUCTION_FEASIBILITY" and full_write_allowed)
        or (decisions["sign"]["allowed"] and participant_sign_qualified)
    )
    submit_allowed = _allowed(decisions["submit"], decisions["legacyManage"])
    if decisions["ownOpinion"]["allowed"] and not formal_review:
        own_opinion_disabled = "已具备本人意见动作资格；正式评审、责任人及对象授权尚未形成。"
    elif decisions["ownOpinion"]["allowed"] and not participant_opinion_qualified:
        own_opinion_disabled = "已具备本人意见动作资格；尚未获得当前评审对象、版本及本人责任分配。"
    else:
        own_opinion_disabled = "当前角色未获得维护本人意见动作权限。"
    if decisions["sign"]["allowed"] and not formal_review:
        sign_disabled = "已具备本人签认动作资格；正式评审、责任人及对象授权尚未形成。"
    elif decisions["sign"]["allowed"] and not participant_sign_qualified:
        sign_disabled = "已具备本人签认动作资格；尚未获得当前评审对象、版本及本人责任分配。"
    else:
        sign_disabled = "当前角色未获得签认本人项目动作权限。"
    own_opinion = _capability_facts(allowed=own_opinion_allowed, action_code=actions["maintainOwnOpinion"][0],
        disabled_reason=own_opinion_disabled)
    sign_facts = _capability_facts(allowed=sign_allowed, action_code=actions["signOwnItems"][0],
        disabled_reason=sign_disabled)
    submit_facts = _capability_facts(allowed=submit_allowed, action_code=actions["submit"][0],
        disabled_reason="当前账号没有本评审正式提交权限。")
    if formal_context:
        relation = formal_context["relation"]
        order = formal_context["order"]
        crm_review = formal_context["crm_review"]
        scope_items = formal_context["scope_items"]
        source_identity = source_business_identity(source, crm_review)
        order_context = {
            "sourceOrderNo": source_identity["sourceOrderNo"],
            "customer": source_identity["customerName"] or "来源未提供",
            "project": source_identity["projectReference"] or source.source_name,
            "contractNo": "尚未形成正式合同记录",
            "quotedGrossAmount": None,
            "crmOrderRelationId": relation.pk,
            "salesOrderId": order.pk,
            "salesOrderNo": order.order_no,
            "salesOrderStatusCode": order.status,
            "salesOrderStatusLabel": order.get_status_display(),
            "salesOrderVersion": order.version,
            "applicableOrderItems": [{
                "salesOrderItemId": item.pk, "lineNo": item.line_no,
                "materialCode": item.material.code, "materialName": item.material.name,
                "quantity": str(item.quantity), "unit": item.uom.name,
            } for item in scope_items],
            "salesOrderItemIds": [item.pk for item in scope_items],
            "salesOrderItemLineNos": [item.line_no for item in scope_items],
            "scopeMode": relation.scope_mode,
            "scopeItemCount": len(scope_items),
            "crmReviewId": crm_review.pk,
            "crmReviewVersion": crm_review.review_version,
            "sourceRecordId": source.pk,
            "sourceVersion": source.source_version,
            "sourceContentHash": source.content_hash,
            "resolutionBasis": relation.resolution_basis,
            "formalContextResolved": True,
            **formal_sales_order,
        }
    else:
        order_context = {
            "sourceOrderNo": order_no,
            "customer": (contract or {}).get("customerName") or order_ref.get("customerName") or order_ref.get("customer") or payload.get("customer") or "来源未提供",
            "project": (contract or {}).get("projectName") or order_ref.get("projectName") or order_ref.get("project") or payload.get("project") or "来源未提供",
            "contractNo": (contract or {}).get("contractNo") or "尚未形成正式合同记录",
            "quotedGrossAmount": (contract or {}).get("grossAmount"),
            "formalContextResolved": False,
            **formal_sales_order,
        }
    return {"factSource": "server", "databaseIdentity": database_identity(),
        "reviewAvailability": {
            "statusCode": "FORMAL_REVIEW_ESTABLISHED" if formal_review else "FORMAL_REVIEW_NOT_ESTABLISHED",
            "statusLabel": "正式评审已建立" if formal_review else "尚未建立正式评审／待准备人员保存",
            "formalReviewEstablished": bool(formal_review),
            "moduleViewQualified": bool(view.get("moduleViewQualified")),
            "objectGrantStatus": (
                "NOT_REQUIRED_CRM_ITEM_RESPONSIBILITY"
                if review_type == "CRM_ORDER_REVIEW" and crm_item_responsibility else
                "CURRENT_REVIEW_GRANTED" if participant_grant else
                ("NOT_APPLICABLE_UNTIL_REVIEW_EXISTS" if not formal_review else "NOT_REQUIRED_FOR_PREPARER")
            ),
            "nextStep": (
                "由有权准备人员核对系统按既有角色分工生成的责任安排；明确事项无需逐项重选，异常事项单独处理，一次保存后系统按对象和版本形成本人办理授权。"
                if not formal_review else
                (
                    "按当前评审、版本及本人责任项目办理。"
                    if review_type == "CRM_ORDER_REVIEW" else
                    "按当前评审、版本、责任人及对象授权办理。"
                )
            ),
        },
        "review": {**config, "reviewType": review_type, "template": {"id": template.pk, "version": template.version, "title": template.title},
            "templateItems": template_items, "draft": _review_row(draft, user=user) if draft else None,
            "draftItems": [_item_row(i, current_employee_id=current_employee.pk if current_employee else None, employee_access=employee_access, item_eligibility=item_eligibility, responsibility_match=responsibility_by_code.get(i.item_code, {}) if full_write_allowed else {}) for i in draft_items],
            "submittedItems": [_item_row(i, current_employee_id=current_employee.pk if current_employee else None, employee_access=employee_access, item_eligibility=item_eligibility, responsibility_match=responsibility_by_code.get(i.item_code, {}) if full_write_allowed else {}) for i in submitted_items],
            "displayItems": [_item_row(i, current_employee_id=current_employee.pk if current_employee else None, employee_access=employee_access, item_eligibility=item_eligibility, responsibility_match=responsibility_by_code.get(i.item_code, {}) if full_write_allowed else {}) for i in display_items],
            "draftSummary": summarize_items(draft_items) if draft else {"total": len(template_items), "agree": 0, "disagree": 0, "pending": len(template_items), "signed": 0, "complete": False, "incompleteReasons": ["尚未保存草稿"], "derivedConclusion": ""},
            "displaySummary": summarize_items(display_items) if display_items else {"total": len(template_items), "agree": 0, "disagree": 0, "pending": len(template_items), "signed": 0, "complete": False, "incompleteReasons": ["尚未保存草稿"], "derivedConclusion": ""},
            "latest": _review_row(latest_submitted, user=user) if latest_submitted else None,
            "history": [_review_row(r, user=user) for r in submitted[1:]]},
        "source": {"id": source.pk, "sourceNo": source.source_no, "sourceName": source.source_name, "sourceVersion": source.source_version,
            "contentHash": source.content_hash, "sourceRowCount": _row_count(payload), "statusLabel": source.get_status_display()},
        "intakeSourceRows": payload.get("engineeringRows", []) if review_type == "CRM_ORDER_REVIEW" and isinstance(payload.get("crmIntake"), dict) else [],
        "orderContext": order_context,
        "employees": employees, "responsibleReadiness": responsible_readiness,
        "otherResponsibilityCandidates": other_responsibility_candidates,
        "responsibilityPlan": {
            "visible": bool(full_write_allowed and review_type == "PDE_PRODUCTION_FEASIBILITY"),
            "authority": "system.UserRoleScopeAssignment → RolePermission → Permission → Employee/User",
            "previewOnly": not bool(formal_review),
            "rows": responsibility_plan if full_write_allowed else [],
            "summary": {
                "total": len(responsibility_plan),
                "automatic": sum(row["statusCode"].startswith("AUTO_MATCHED_UNIQUE") for row in responsibility_plan),
                "preserved": sum(row["statusCode"] == "CURRENT_VERSION_ASSIGNED" for row in responsibility_plan),
                "pendingMultiple": sum(row["statusCode"] == "PENDING_MULTIPLE_CANDIDATES" for row in responsibility_plan),
                "missing": sum(row["statusCode"] == "MISSING_QUALIFIED_RESPONSIBLE" for row in responsibility_plan),
                "loginPending": sum(row["statusCode"] == "AUTO_MATCHED_UNIQUE_LOGIN_PENDING" for row in responsibility_plan),
            },
        },
        "reasonOptions": STANDARD_REASONS, "crossReviewFeedback": _review_row(other, user=user) if other else None,
        "approval": build_approval_facts(user=user, review=latest_submitted) if latest_submitted else build_approval_facts(user=user, review=None),
        "currentActor": {"userId": user.pk, "username": user.username,
            "employee": ({"id": current_employee.pk, "employeeNo": current_employee.employee_no, "name": current_employee.full_name} if current_employee else None)},
        "submissionProcess": {
            "allItemSignaturesRequired": True,
            "comprehensiveApprovalImplemented": True,
            "comprehensiveApprovalLabel": "提交后进入独立最终审批",
            "submittedReviewCreatesApprovalTask": True,
            "signatureEntry": "业务流程中心 → 对应模块 → 当前评审节点 → 查看页面（或新标签打开）",
            "postSubmitResult": "全部项目有效签认后，“正式提交评审”只锁定意见快照并进入待审批；同意／不同意数量仅供审批人参考，不自动形成最终结论。",
            "firstLoginSetup": {
                "selfServiceAvailable": False,
                "statement": "当前版本没有本人自助首次密码设置入口。",
                "administratorPath": "左侧“组织结构” → “用户账户” → 对应账号行“编辑” → 明确开启“重置密码” → 两次输入新密码 → 填写原因 → “保存”",
                "completionRule": "账号具有可用密码表示登录准备完成；本人成功登录后才标记为已有实际登录记录。",
            },
            "eligibleSubmitters": eligible_submitters,
            "legalSubmitterAvailable": bool(eligible_submitters),
            "submitterGap": ("" if eligible_submitters else
                f"未找到同时具备有效员工身份、可用登录账号和 {actions['submit'][0]} 的合法提交人；系统管理员虽可通过技术门禁，但没有正式员工关联，不能作为本次业务提交人。"),
            "minimumFutureApproval": ("" if eligible_submitters else
                f"如需完成正式提交，须另行明确批准一个现有正式员工账号取得 {actions['submit'][0]} 及相应数据范围；本轮未新增该权限。"),
        },
        "authorization": {"view": view["facts"], "fullDraftEdit": full_write,
            "draftEdit": own_opinion, "ownOpinion": own_opinion,
            "sign": {**sign_facts, "requiresOwnEmployeeIdentity": True},
            "submit": submit_facts,
            "saveReason": own_opinion.get("disabledReason") or decisions["manage"]["reason"],
            "scopeLabel": (
                "角色权限 + 组织范围 + 当前评审本人负责项目"
                if review_type == "CRM_ORDER_REVIEW" and crm_item_responsibility and not full_write_allowed else
                "角色权限 + 当前评审对象 + 当前有效版本 + 本人负责项目" if participant_grant and not full_write_allowed else
                ("模块查看资格；正式评审、责任人和对象授权尚未形成" if not formal_review and not full_write_allowed else "现有正式角色与数据范围")
            ),
            "permissionCatalog": {"moduleName": permission_config["moduleName"],
                "actions": {key: value[0] for key, value in actions.items()},
                "itemPermissions": {key: value[0] for key, value in (permission_config.get("itemPermissions") or {}).items()},
                "legacyCompatibility": {"view": permission_config["legacyViewAction"], "manageAndSubmit": permission_config["legacyManageAction"]}}},
        "separationFacts": {"independentRecord": True, "independentConclusion": True, "crossReviewDoesNotChangeThisReview": True,
            "sourceVersionChangeRequiresNewReview": True, "serverTemplateAuthority": True, "noAutomaticDecision": True}}

def _require_capability(facts, key, code, fallback):
    capability = facts["authorization"].get(key) or {}
    if not capability.get("executable"):
        raise ReviewBusinessError(code, capability.get("disabledReason") or fallback, 403)


def _assert_participant_draft_payload(review, incoming, employee, *, own_only=False):
    existing = {i.stable_key: i for i in review.items.filter(is_removed=False)}
    incoming_by_key = {str(row.get("stableKey") or ""): row for row in incoming}
    required = {key for key, item in existing.items() if item.responsible_employee_id == employee.pk} if own_only else set(existing)
    if set(incoming_by_key) != required or len(incoming) != len(incoming_by_key):
        raise ReviewBusinessError("OWN_OPINION_SCOPE_DENIED", "本人意见维护不得新增、移除或遗漏评审项目。", 403)
    for stable in required:
        item = existing[stable]
        raw = incoming_by_key[stable]
        if str(raw.get("itemKind") or "") != item.item_kind or str(raw.get("itemText") or "").strip() != item.item_text:
            raise ReviewBusinessError("OWN_OPINION_SCOPE_DENIED", "本人意见维护不得改写评审项目身份或内容。", 403)
        raw_employee_id = raw.get("responsibleEmployeeId") or None
        if raw_employee_id != item.responsible_employee_id:
            raise ReviewBusinessError("OWN_OPINION_SCOPE_DENIED", "本人意见维护不得变更责任人。", 403)
        editable = item.responsible_employee_id == employee.pk
        proposed = {
            "evidence": str(raw.get("evidenceNote") or "").strip(),
            "decision": str(raw.get("decision") or ""),
            "reasonCode": str(raw.get("disagreementReasonCode") or ""),
            "reasonText": str(raw.get("disagreementReasonText") or "").strip(),
        }
        current = {"evidence": item.evidence_note, "decision": item.decision,
            "reasonCode": item.disagreement_reason_code, "reasonText": item.disagreement_reason_text}
        if not editable and proposed != current:
            raise ReviewBusinessError("OWN_OPINION_SCOPE_DENIED", f"{item.item_code} 不是当前员工本人负责项目，禁止修改。", 403)
        if editable and proposed != current:
            if own_only and raw.get("contentRevision") != item.content_revision:
                raise ReviewBusinessError("OWN_OPINION_CHANGED", f"事项 {item.item_code} 已变化，请保留输入并重新读取后核对。", 409)
            item_decision = _item_authorization(
                employee.user, review.review_type, item.item_code, review.company_id,
            )
            if not item_decision.get("allowed"):
                raise ReviewBusinessError(
                    "ITEM_PERMISSION_DENIED",
                    f"缺少事项 {item.item_code} 的正式评审资格，禁止维护该项本人意见。",
                    403,
                )

def _validate_basis(review, source, data, template):
    if data.get("expectedSourceVersion") != source.source_version or data.get("expectedContentHash") != source.content_hash: raise ReviewBusinessError("REVIEW_BASIS_CHANGED", "工程来源或版本已变化，请刷新后基于最新依据重新评审。", 409)
    if str(data.get("expectedTemplateVersion") or "") != template.version: raise ReviewBusinessError("REVIEW_TEMPLATE_CHANGED", "评审模板版本已变化，请刷新后重新核对。", 409)
    if review and review.record_status != "DRAFT": raise ReviewBusinessError("REVIEW_ALREADY_SUBMITTED", "已提交评审不可原地修改，请发起新版本复评。", 409)


def _review_context_kwargs(facts, *, formal_context_required):
    order_context = facts.get("orderContext") or {}
    return {
        "crm_order_relation_id": order_context.get("crmOrderRelationId"),
        "sales_order_id": order_context.get("salesOrderId"),
        "formal_context_required": formal_context_required,
    }

@transaction.atomic
def save_draft(
        *, user, review_type, source_record_id, data, idempotency_key,
        crm_order_relation_id=None, sales_order_id=None,
        formal_context_required=False):
    if review_type == "PDE_PRODUCTION_FEASIBILITY" and formal_context_required and crm_order_relation_id and sales_order_id:
        from .crm_order_version_carry_forward import CarryForwardError, enabled, prepare_proof
        try:
            config = review_permission_config(review_type)
            preparer = _allowed(
                _authorization(user, config["actions"]["manageDraft"][0], user.company_id),
                _authorization(user, config["legacyManageAction"], user.company_id),
            )
            if enabled() and preparer:
                prepare_proof(user=user, relation_id=crm_order_relation_id, sales_order_id=sales_order_id)
        except CarryForwardError as error:
            raise ReviewBusinessError("CRM_VERSION_CARRY_DENIED", str(error), 409) from error
    facts = build_review_facts(
        user=user, review_type=review_type, source_record_id=source_record_id,
        crm_order_relation_id=crm_order_relation_id,
        sales_order_id=sales_order_id,
        formal_context_required=formal_context_required,
    )
    actions = review_permission_config(review_type)["actions"]
    _require_capability(facts, "draftEdit", "SAVE_PERMISSION_DENIED", "当前账号不能维护本评审草稿。")
    source = EngineeringSourceRecord.objects.select_for_update().get(pk=facts["source"]["id"])
    template = OrderReviewTemplate.objects.prefetch_related("items").get(pk=facts["review"]["template"]["id"])
    review_id = data.get("reviewId")
    current_draft_id = (facts["review"].get("draft") or {}).get("id")
    if formal_context_required and review_type == "PDE_PRODUCTION_FEASIBILITY" and review_id and str(review_id) != str(current_draft_id):
        raise ReviewBusinessError("REVIEW_CONTEXT_MISMATCH", "保存的草稿与当前订单评审上下文不一致，已停止保存。", 409)
    key = str(idempotency_key or "").strip()
    review = OrderCrossFunctionalReview.objects.select_for_update().filter(
        pk=review_id, company_id=source.company_id, review_type=review_type,
    ).first() if review_id else None
    if not review and key:
        idempotent = OrderCrossFunctionalReview.objects.select_for_update().filter(
            company_id=source.company_id, review_type=review_type, idempotency_key=key,
        ).first()
        if idempotent:
            if review_type == "PDE_PRODUCTION_FEASIBILITY":
                from .pde_engineering_preparation_admission import (
                    PDEEngineeringPreparationAdmissionError,
                    require_pde_review_predecessor_relation,
                )
                try:
                    require_pde_review_predecessor_relation(
                        pde_review=idempotent, lock=True,
                    )
                except PDEEngineeringPreparationAdmissionError as exc:
                    raise ReviewBusinessError(exc.code, exc.message, exc.http_status) from exc
            return build_review_facts(
                user=user, review_type=review_type, source_record_id=source.pk,
                **_review_context_kwargs(
                    facts, formal_context_required=formal_context_required,
                ),
            )
    if not review:
        review = OrderCrossFunctionalReview.objects.select_for_update().filter(
            company_id=source.company_id,
            source_order_no=facts["orderContext"]["sourceOrderNo"],
            review_type=review_type,
            record_status="DRAFT",
        ).order_by("-review_version").first()
    _validate_basis(review, source, data, template)
    full_draft_edit = facts["authorization"]["fullDraftEdit"].get("executable") is True
    responsibility_plan = {
        row["itemCode"]: row
        for row in (facts.get("responsibilityPlan", {}).get("rows") or [])
    }
    if not full_draft_edit:
        if not review:
            raise ReviewBusinessError("OWN_OPINION_SCOPE_DENIED", "本人意见维护只能作用于已建立的当前评审草稿。", 403)
        employee = formal_employee_queryset(company_id=source.company_id).filter(user_id=user.pk).first()
        if not employee:
            raise ReviewBusinessError("SIGNER_EMPLOYEE_REQUIRED", "当前账号未关联有效正式员工。", 403)
        _assert_participant_draft_payload(review, data.get("items") if isinstance(data.get("items"), list) else [], employee, own_only=data.get("ownOpinionOnly") is True)
    if not review:
        existing = OrderCrossFunctionalReview.objects.select_for_update().filter(company_id=source.company_id, source_order_no=facts["orderContext"]["sourceOrderNo"], review_type=review_type).order_by("-review_version").first()
        version = (existing.review_version if existing else 0) + 1; key = key or uuid.uuid4().hex
        review = OrderCrossFunctionalReview.objects.create(company=source.company, source_record=source, review_type=review_type,
            source_order_no=facts["orderContext"]["sourceOrderNo"], source_version=source.source_version, source_content_hash=source.content_hash,
            review_version=version, reviewer=user, idempotency_key=key,
            audit_hash=sha256(f"draft:{source.pk}:{review_type}:{key}:{timezone.now().isoformat()}".encode()).hexdigest(),
            record_status="DRAFT", template_version=template.version)
        if review_type == "PDE_PRODUCTION_FEASIBILITY":
            from .pde_engineering_preparation_admission import (
                create_pde_review_predecessor_relation,
            )
            create_pde_review_predecessor_relation(
                pde_review=review, user=user,
                crm_order_relation_id=facts["orderContext"].get("crmOrderRelationId"),
            )
    elif review_type == "PDE_PRODUCTION_FEASIBILITY":
        from .pde_engineering_preparation_admission import (
            PDEEngineeringPreparationAdmissionError,
            require_pde_review_predecessor_relation,
        )
        try:
            require_pde_review_predecessor_relation(pde_review=review, lock=True)
        except PDEEngineeringPreparationAdmissionError as exc:
            raise ReviewBusinessError(exc.code, exc.message, exc.http_status) from exc
    incoming = data.get("items") if isinstance(data.get("items"), list) else []
    fixed = {f"FIXED-{i.item_code}": i for i in template.items.filter(is_applicable=True)}
    existing_items = {i.stable_key: i for i in review.items.select_related("review").all()}; seen = set()
    for index, raw in enumerate(incoming, 1):
        stable = str(raw.get("stableKey") or "").strip(); kind = str(raw.get("itemKind") or "")
        if kind == "FIXED":
            if stable not in fixed: raise ReviewBusinessError("FIXED_ITEM_INVALID", "固定评审项目身份或模板不一致。", 409)
            template_item, text, code = fixed[stable], fixed[stable].item_text, fixed[stable].item_code
        else:
            text = str(raw.get("itemText") or "").strip()
            if not text: continue
            if text == "其它": raise ReviewBusinessError("OTHER_ITEM_CONTENT_REQUIRED", "其它评审项必须填写具体内容，不能只写“其它”。")
            stable = stable if stable.startswith("OTHER-") else f"OTHER-{uuid.uuid4().hex}"; template_item, code, kind = None, f"O{index:02d}", "OTHER"
        seen.add(stable); employee_id = raw.get("responsibleEmployeeId") or None
        match = responsibility_plan.get(code, {}) if kind == "FIXED" else {}
        proposed_employee_id = match.get("proposedEmployeeId")
        if (full_draft_edit and proposed_employee_id and not employee_id
                and match.get("statusCode", "").startswith("AUTO_MATCHED_UNIQUE")):
            employee_id = proposed_employee_id
        if (full_draft_edit and proposed_employee_id and employee_id
                and int(employee_id) != int(proposed_employee_id)
                and match.get("statusCode", "").startswith("AUTO_MATCHED_UNIQUE")):
            raise ReviewBusinessError(
                "RESPONSIBILITY_MATCH_CHANGED",
                f"事项 {code} 的唯一正式责任匹配已变化，请刷新后重新核对。",
                409,
            )
        if employee_id and not _eligible_employees(source.company_id).filter(pk=employee_id).exists(): raise ReviewBusinessError("RESPONSIBLE_EMPLOYEE_INVALID", "所选责任人不是当前公司的有效正式员工。")
        existing_item = existing_items.get(stable)
        if employee_id and (not existing_item or existing_item.responsible_employee_id != employee_id):
            employee = _eligible_employees(source.company_id).select_related("user").get(pk=employee_id)
            eligibility = _employee_item_eligibility(
                employee, review_type, code, source.company_id, actions,
            )
            if not eligibility["eligible"]:
                raise ReviewBusinessError(
                    "RESPONSIBLE_ITEM_PERMISSION_DENIED",
                    f"所选责任人缺少事项 {code} 的正式资格或必要本人办理动作权限。",
                    403,
                )
        values = {"item_kind": kind, "template_item": template_item, "item_code": code, "item_text": text,
            "evidence_note": str(raw.get("evidenceNote") or "").strip(), "decision": str(raw.get("decision") or ""),
            "disagreement_reason_code": str(raw.get("disagreementReasonCode") or ""), "disagreement_reason_text": str(raw.get("disagreementReasonText") or "").strip(),
            "responsible_employee_id": employee_id, "display_order": existing_item.display_order if existing_item and not full_draft_edit else index, "is_removed": False, "removed_at": None}
        if values["decision"] not in ("", "AGREE", "DISAGREE"): raise ReviewBusinessError("DECISION_INVALID", "判定只允许同意或不同意。")
        item = existing_items.get(stable)
        if item:
            before = _item_content(item); changed = any(getattr(item, field) != value for field, value in values.items())
            if changed:
                if (item.responsible_employee_id != employee_id
                        and item.responsible_employee_id is not None
                        and not str(raw.get("responsibilityChangeReason") or "").strip()):
                    raise ReviewBusinessError(
                        "RESPONSIBILITY_CHANGE_REASON_REQUIRED",
                        f"事项 {code} 已有正式责任人；调整时必须填写责任变更原因。",
                    )
                for field, value in values.items(): setattr(item, field, value)
                item.content_revision += 1
                if item.signature_status == "SIGNED":
                    item.signature_status = "UNSIGNED"; item.signed_by_user = None; item.signed_at = None; item.signed_employee_id_snapshot = None
                    item.signed_employee_no_snapshot = ""; item.signed_employee_name_snapshot = ""; item.signature_content_hash = ""
                    _audit(review, user, "SIGNATURE_INVALIDATED", item, before, _item_content(item))
                item.save(); _audit(review, user, "ITEM_EDIT", item, before, {
                    **_item_content(item),
                    "responsibilityChangeReason": str(raw.get("responsibilityChangeReason") or "").strip(),
                })
        else:
            item = OrderCrossFunctionalReviewItem.objects.create(review=review, stable_key=stable, **values); _audit(review, user, "ITEM_ADD", item, {}, _item_content(item))
            if match.get("statusCode", "").startswith("AUTO_MATCHED_UNIQUE") and employee_id:
                _audit(review, user, "RESPONSIBILITY_AUTO_ASSIGNED", item, {}, {
                    "itemCode": code,
                    "employeeId": employee_id,
                    "statusCode": match.get("statusCode"),
                    "matchBasis": match.get("matchBasis"),
                    "roleSources": (match.get("selected") or {}).get("roleSources", []),
                    "candidateCount": match.get("candidateCount"),
                })
    # The client cannot omit fixed template rows to reduce the review scope.
    for stable, template_item in fixed.items():
        if stable in existing_items or stable in seen:
            continue
        match = responsibility_plan.get(template_item.item_code, {})
        employee_id = match.get("proposedEmployeeId") if full_draft_edit else None
        item = OrderCrossFunctionalReviewItem.objects.create(
            review=review, stable_key=stable, item_kind="FIXED", template_item=template_item,
            item_code=template_item.item_code, item_text=template_item.item_text,
            responsible_employee_id=employee_id, display_order=template_item.display_order,
        )
        _audit(review, user, "FIXED_ITEM_ENFORCED", item, {}, _item_content(item))
        if match.get("statusCode", "").startswith("AUTO_MATCHED_UNIQUE") and employee_id:
            _audit(review, user, "RESPONSIBILITY_AUTO_ASSIGNED", item, {}, {
                "itemCode": template_item.item_code,
                "employeeId": employee_id,
                "statusCode": match.get("statusCode"),
                "matchBasis": match.get("matchBasis"),
                "roleSources": (match.get("selected") or {}).get("roleSources", []),
                "candidateCount": match.get("candidateCount"),
            })
    for stable, item in existing_items.items():
        if full_draft_edit and item.item_kind == "OTHER" and not item.is_removed and stable not in seen:
            before = _item_content(item); item.is_removed = True; item.removed_at = timezone.now(); item.content_revision += 1
            if item.signature_status == "SIGNED": item.signature_status = "UNSIGNED"; item.signed_at = None; item.signed_by_user = None; item.signature_content_hash = ""
            item.save(); _audit(review, user, "ITEM_REMOVE", item, before, {"removed": True, **_item_content(item)})
    current = list(review.items.select_related("review").filter(is_removed=False)); review.item_summary = summarize_items(current)
    update_fields = ["item_summary", "updated_at"]
    if full_draft_edit:
        review.reviewer = user
        update_fields.insert(1, "reviewer")
    review.save(update_fields=update_fields); _audit(review, user, "DRAFT_SAVE", None, {}, review.item_summary)
    _ensure_assignment_object_grants(review, user)
    return build_review_facts(
        user=user, review_type=review_type, source_record_id=source.pk,
        **_review_context_kwargs(
            facts, formal_context_required=formal_context_required,
        ),
    )

@transaction.atomic
def sign_items(
        *, user, review_type, source_record_id, data,
        crm_order_relation_id=None, sales_order_id=None,
        formal_context_required=False):
    facts = build_review_facts(
        user=user, review_type=review_type, source_record_id=source_record_id,
        crm_order_relation_id=crm_order_relation_id,
        sales_order_id=sales_order_id,
        formal_context_required=formal_context_required,
    )
    _require_capability(facts, "sign", "SIGN_PERMISSION_DENIED", "当前账号不能签认本评审。")
    review = OrderCrossFunctionalReview.objects.select_for_update().filter(pk=data.get("reviewId"), record_status="DRAFT", review_type=review_type).first()
    if not review: raise ReviewBusinessError("DRAFT_NOT_FOUND", "未找到可签认的草稿。", 404)
    if formal_context_required and review_type == "PDE_PRODUCTION_FEASIBILITY" and review.pk != (facts["review"].get("draft") or {}).get("id"):
        raise ReviewBusinessError("REVIEW_CONTEXT_MISMATCH", "签认草稿与当前正式订单上下文不一致。", 409)
    source = EngineeringSourceRecord.objects.get(pk=facts["source"]["id"]); template = OrderReviewTemplate.objects.get(pk=facts["review"]["template"]["id"]); _validate_basis(review, source, data, template)
    employee = formal_employee_queryset(company_id=source.company_id).filter(user_id=user.pk).first()
    if not employee: raise ReviewBusinessError("SIGNER_EMPLOYEE_REQUIRED", "当前登录账号未关联有效正式员工，不能签认。", 403)
    ids = data.get("itemIds") if isinstance(data.get("itemIds"), list) else []
    rows = list(review.items.select_for_update().select_related("review").filter(pk__in=ids, is_removed=False))
    if not rows: raise ReviewBusinessError("SIGN_ITEMS_REQUIRED", "请选择本人负责且已完成判定的项目。")
    for item in rows:
        expected_revisions = data.get("expectedItemRevisions")
        if expected_revisions is not None and (not isinstance(expected_revisions, dict) or expected_revisions.get(str(item.pk)) != item.content_revision):
            raise ReviewBusinessError("SIGN_CONTENT_CHANGED", f"事项 {item.item_code} 已变化，请重新核对已保存内容后签认。", 409)
        if item.responsible_employee_id != employee.pk: raise ReviewBusinessError("IMPERSONATION_FORBIDDEN", f"{item.item_code} 不是当前员工本人负责的项目，禁止代签。", 403)
        item_decision = _item_authorization(user, review_type, item.item_code, source.company_id)
        if not item_decision.get("allowed"):
            raise ReviewBusinessError("ITEM_PERMISSION_DENIED", f"缺少事项 {item.item_code} 的正式评审资格，禁止签认。", 403)
        if not item.decision or (item.decision == "DISAGREE" and (not item.disagreement_reason_code or (item.disagreement_reason_code == "其它" and not item.disagreement_reason_text.strip()))): raise ReviewBusinessError("ITEM_INCOMPLETE", f"{item.item_code} 判定或不同意原因尚未完成。")
    now = timezone.now()
    for item in rows:
        if item.signature_status == "SIGNED" and item.signature_content_hash == _content_hash(item) and item.signed_by_user_id == user.pk:
            continue
        item.signature_status = "SIGNED"; item.signed_by_user = user; item.signed_employee_id_snapshot = employee.pk
        item.signed_employee_no_snapshot = employee.employee_no; item.signed_employee_name_snapshot = employee.full_name
        item.signed_at = now; item.signature_content_hash = _content_hash(item); item.save()
        _audit(review, user, "ITEM_SIGN", item, {}, {"employeeId": employee.pk, "employeeNo": employee.employee_no, "employeeName": employee.full_name, "signedAt": now.isoformat(), "contentHash": item.signature_content_hash})
    review.item_summary = summarize_items(list(review.items.select_related("review").filter(is_removed=False))); review.save(update_fields=["item_summary", "updated_at"])
    return build_review_facts(
        user=user, review_type=review_type, source_record_id=source.pk,
        **_review_context_kwargs(
            facts, formal_context_required=formal_context_required,
        ),
    )

@transaction.atomic
def submit_review(
        *, user, review_type, source_record_id, data,
        crm_order_relation_id=None, sales_order_id=None,
        formal_context_required=False):
    facts = build_review_facts(
        user=user, review_type=review_type, source_record_id=source_record_id,
        crm_order_relation_id=crm_order_relation_id,
        sales_order_id=sales_order_id,
        formal_context_required=formal_context_required,
    )
    _require_capability(facts, "submit", "SUBMIT_PERMISSION_DENIED", "当前账号没有正式提交权限。")
    review = OrderCrossFunctionalReview.objects.select_for_update().filter(pk=data.get("reviewId"), record_status="DRAFT", review_type=review_type).first()
    if not review: raise ReviewBusinessError("DRAFT_NOT_FOUND", "草稿不存在、已提交或重复提交。", 409)
    if review_type == "PDE_PRODUCTION_FEASIBILITY":
        from .pde_engineering_preparation_admission import (
            PDEEngineeringPreparationAdmissionError,
            require_pde_review_predecessor_relation,
        )
        try:
            require_pde_review_predecessor_relation(pde_review=review, lock=True)
        except PDEEngineeringPreparationAdmissionError as exc:
            raise ReviewBusinessError(exc.code, exc.message, exc.http_status) from exc
    source = EngineeringSourceRecord.objects.get(pk=facts["source"]["id"]); template = OrderReviewTemplate.objects.get(pk=facts["review"]["template"]["id"]); _validate_basis(review, source, data, template)
    summary = summarize_items(list(review.items.select_related("review").filter(is_removed=False)))
    if not summary["complete"]: raise ReviewBusinessError("REVIEW_INCOMPLETE", "评审尚未完成：" + "；".join(summary["incompleteReasons"][:5]))
    now = timezone.now()
    review.item_summary = summary
    review.submitted_at = now
    review.reviewer = user
    review.conclusion = ""
    review.save(update_fields=["item_summary", "submitted_at", "reviewer", "conclusion", "updated_at"])
    workflow, task = create_pending_approval(review)
    audit = _audit(review, user, "REVIEW_SUBMIT", None, {}, {
        "summary": summary,
        "opinionCountsAreReferenceOnly": True,
        "finalDecision": None,
        "approvalStatus": "PENDING",
        "workflowInstanceId": workflow.pk,
        "approvalTaskId": task.pk,
        "submittedAt": now.isoformat(),
    })
    transition_business_object(
        business_object=review,
        object_type="CRMOrderReview" if review_type == "CRM_ORDER_REVIEW" else "PDEProductionFeasibilityReview",
        source_state="DRAFT",
        target_state="SUBMITTED",
        action_code=review_permission_config(review_type)["actions"]["submit"][0],
        operator=user,
        reason="锁定已完整签认的意见快照并送交独立最终审批。",
        audit_reference=f"OrderReviewItemAudit:{audit.pk}",
        workflow_instance=workflow,
        allowed_transitions={("DRAFT", "SUBMITTED")},
        status_field="record_status",
        version_field=None,
    )
    return build_review_facts(
        user=user, review_type=review_type, source_record_id=source.pk,
        **_review_context_kwargs(
            facts, formal_context_required=formal_context_required,
        ),
    )


@transaction.atomic
def final_approve_review(
        *, user, review_type, source_record_id, data, idempotency_key,
        crm_order_relation_id=None, sales_order_id=None,
        formal_context_required=False):
    facts = build_review_facts(
        user=user, review_type=review_type, source_record_id=source_record_id,
        crm_order_relation_id=crm_order_relation_id,
        sales_order_id=sales_order_id,
        formal_context_required=formal_context_required,
    )
    review_id = data.get("reviewId") or (facts.get("review", {}).get("latest") or {}).get("id")
    try:
        decide_final_approval(
            user=user,
            review_type=review_type,
            review_id=review_id,
            data=data,
            idempotency_key=idempotency_key,
        )
    except OrderReviewApprovalError as exc:
        raise ReviewBusinessError(exc.code, exc.message, exc.http_status) from exc
    return build_review_facts(
        user=user, review_type=review_type, source_record_id=source_record_id,
        **_review_context_kwargs(
            facts, formal_context_required=formal_context_required,
        ),
    )

@transaction.atomic
def append_review(
        *, user, review_type, source_record_id, data, idempotency_key,
        crm_order_relation_id=None, sales_order_id=None,
        formal_context_required=False):
    """Legacy immutable append retained for historical clients; new UI uses itemized actions."""
    facts = build_review_facts(
        user=user, review_type=review_type, source_record_id=source_record_id,
        crm_order_relation_id=crm_order_relation_id,
        sales_order_id=sales_order_id,
        formal_context_required=formal_context_required,
    )
    _require_capability(facts, "fullDraftEdit", "SAVE_PERMISSION_DENIED", "当前账号没有评审完整维护权限。")
    source = EngineeringSourceRecord.objects.select_for_update().get(pk=facts["source"]["id"])
    if data.get("expectedSourceVersion") != source.source_version or data.get("expectedContentHash") != source.content_hash: raise ReviewBusinessError("REVIEW_BASIS_CHANGED", "工程来源或版本已变化，请刷新后基于最新依据重新评审。", 409)
    opinion, conclusion, key = str(data.get("reviewOpinion") or "").strip(), str(data.get("conclusion") or "").strip(), str(idempotency_key or "").strip()
    if not opinion: raise ReviewBusinessError("REVIEW_OPINION_REQUIRED", "请填写评审意见。")
    if conclusion not in dict(OrderCrossFunctionalReview.CONCLUSIONS): raise ReviewBusinessError("REVIEW_CONCLUSION_REQUIRED", "请选择有效的评审结论。")
    if not key: raise ReviewBusinessError("IDEMPOTENCY_KEY_REQUIRED", "保存评审必须提供幂等标识。")
    if OrderCrossFunctionalReview.objects.filter(company_id=source.company_id, review_type=review_type, idempotency_key=key).exists():
        return build_review_facts(
            user=user, review_type=review_type, source_record_id=source.pk,
            **_review_context_kwargs(
                facts, formal_context_required=formal_context_required,
            ),
        )
    latest = OrderCrossFunctionalReview.objects.filter(company_id=source.company_id, review_type=review_type, source_order_no=facts["orderContext"]["sourceOrderNo"]).order_by("-review_version").first(); version = (latest.review_version if latest else 0) + 1
    audit = {"source": source.pk, "type": review_type, "version": version, "conclusion": conclusion, "actor": user.pk, "at": timezone.now().isoformat()}
    review = OrderCrossFunctionalReview.objects.create(company=source.company, source_record=source, review_type=review_type, source_order_no=facts["orderContext"]["sourceOrderNo"], source_version=source.source_version, source_content_hash=source.content_hash, review_version=version, conclusion=conclusion, review_opinion=opinion, evidence=data.get("evidence") if isinstance(data.get("evidence"), dict) else {}, missing_conditions=data.get("missingConditions") if isinstance(data.get("missingConditions"), list) else [], responsibility_feedback=data.get("responsibilityFeedback") if isinstance(data.get("responsibilityFeedback"), dict) else {}, reviewer=user, idempotency_key=key, audit_hash=sha256(json.dumps(audit, sort_keys=True).encode()).hexdigest(), record_status="SUBMITTED", submitted_at=timezone.now())
    if review_type == "PDE_PRODUCTION_FEASIBILITY":
        from .pde_engineering_preparation_admission import (
            PDEEngineeringPreparationAdmissionError,
            create_pde_review_predecessor_relation,
        )
        try:
            create_pde_review_predecessor_relation(
                pde_review=review, user=user,
                crm_order_relation_id=facts["orderContext"].get("crmOrderRelationId"),
            )
        except PDEEngineeringPreparationAdmissionError as exc:
            raise ReviewBusinessError(exc.code, exc.message, exc.http_status) from exc
    return build_review_facts(
        user=user, review_type=review_type, source_record_id=source.pk,
        **_review_context_kwargs(
            facts, formal_context_required=formal_context_required,
        ),
    )

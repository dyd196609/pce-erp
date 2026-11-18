"""Native quote comparison -> draft preparation; no selection or approval."""
from decimal import Decimal, InvalidOperation
import copy
import uuid

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from masterdata.models import MasterDataWriteRequest
from pde.product_design_service import _canonical_hash, _write_request, _commit_request
from system.authorization import AuthorizationService
from system.models import OrganizationOperatingAuditRecord
from workflow_runtime.models import BusinessStateTransition
from workflow_runtime.state_transitions import record_projected_business_transition
from .models import (PurchaseInquiry, PurchaseRequestItem, Supplier,
                     SupplierQuotation, QuoteComparisonFact, PriceApprovalPreparation)
from .fact_read_access import (validate_read_identity, read_qualification,
                              context_allowed, object_read_context, permission_role_evidence)
from .scm_read_permission_catalog import QUOTATION_SCOPE

CONTRACT = "PCE-NATIVE-QUOTE-COMPARISON-REGISTRATION-V1"
ACTION = "SAVE_QUOTE_COMPARISON"
PERMISSION = "procurement.quote_comparison.register"
PERMISSION_NAME = "正式报价比较登记及准备生成"
ENTITY = "QuoteComparisonRegistration"
ACTION_CONTRACT = {"actionCode": ACTION, "requiredPermission": PERMISSION,
    "role": "buyer", "organizationScope": "EXISTING_ROLE_SCOPE",
    "serverValidator": "procurement.comparison_registration_service.register_comparison",
    "creates": ["QuoteComparisonFact", "PriceApprovalPreparation:draft"],
    "forbidden": ["PRICE_CONFIRM", "PRICE_APPROVE", "ORDER_APPROVE", "PAYMENT_EXECUTE"]}


class ComparisonRegistrationError(ValueError):
    def __init__(self, code, message, status=409):
        self.code, self.message, self.http_status = code, message, status
        super().__init__(message)


def fail(code, message, status=409):
    raise ComparisonRegistrationError(code, message, status)


def identifier(value):
    if isinstance(value, bool) or not str(value or "").isdigit() or int(value) <= 0:
        fail("COMPARISON_ID_INVALID", "必须提供准确的原生对象标识。", 400)
    return int(value)


def text(value, name, limit=240):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        fail("COMPARISON_INPUT_INVALID", f"{name}必须明确且在长度限制内。", 400)
    return value.strip()


def number(value):
    try:
        if isinstance(value, bool):raise ValueError()
        result = Decimal(str(value))
        if not result.is_finite() or result <= 0 or result != result.quantize(Decimal(".0001")):
            raise ValueError()
        return result
    except (InvalidOperation, ValueError, TypeError):
        fail("COMPARISON_QUANTITY_OR_PRICE_INVALID", "来源数量和报价单价必须为准确的正数，不得猜补或舍入。")


def execution_allowed(user, context):
    if user.is_superuser:return False
    facts = {**context, "departmentId": context.get("departmentId") or "__NOT_PROVIDED__",
             "ownerUserId": context.get("ownerUserId") or "__NOT_PROVIDED__"}
    return any(row.role_code == "buyer" and AuthorizationService._scope_matches(row, user, facts, {})
               for row in permission_role_evidence(user, PERMISSION, context["organizationId"]))


def execution_qualification(user):
    validate_read_identity(user)
    if user.is_superuser or not any(row.role_code == "buyer" and
            PERMISSION in AuthorizationService.permission_codes_for_user(user, {row.role_code})
            for row in AuthorizationService.authority_evidence(user)):
        fail("COMPARISON_EXECUTION_DENIED", "当前岗位没有正式比较登记及准备生成资格。", 403)


def _source_objects(user, inquiry_id, item_id, *, write=False, lock=False):
    validate_read_identity(user)
    if write:execution_qualification(user)
    read_qualification(user, QUOTATION_SCOPE)
    inquiries = PurchaseInquiry.objects.select_related("source_purchase_request")
    if lock:inquiries = inquiries.select_for_update()
    inquiry = inquiries.filter(pk=identifier(inquiry_id)).first()
    if inquiry is None:fail("COMPARISON_SOURCE_NOT_FOUND", "来源不存在或不在当前授权范围。", 404)
    request = inquiry.source_purchase_request
    context = object_read_context(request)
    if context is None:fail("COMPARISON_SOURCE_UNPROVEN", "原申请企业和责任范围尚无准确证明。")
    if not context_allowed(user, QUOTATION_SCOPE, context):
        fail("COMPARISON_SOURCE_NOT_FOUND", "来源不存在或不在当前授权范围。", 404)
    if write and (context["organizationId"] != user.company_id or not execution_allowed(user, context)):
        fail("COMPARISON_EXECUTION_DENIED", "本来源超出当前普通采购员的原执行范围。", 403)
    items = PurchaseRequestItem.objects.select_related("material")
    if lock:items = items.select_for_update()
    item = items.filter(pk=identifier(item_id), purchase_request=request).first()
    if item is None:fail("COMPARISON_SOURCE_LINE_NOT_FOUND", "申请行不属于当前询价来源。", 404)
    return inquiry, item, context


def _line(items, request_item):
    if not isinstance(items, list):fail("COMPARISON_SOURCE_LINE_UNPROVEN", "原生明细行缺少准确持久来源。")
    matches = [row for row in items if isinstance(row, dict) and
               type(row.get("lineNo")) is int and row["lineNo"] == request_item.line_no]
    if len(matches) != 1:fail("COMPARISON_SOURCE_LINE_UNPROVEN", "原生明细行缺失或有歧义，不能按相同物料猜配。")
    row = matches[0]
    if (row.get("materialId") != request_item.material_id or
            row.get("materialCode") != request_item.material_code or
            str(row.get("specification") or "") != request_item.specification):
        fail("COMPARISON_MATERIAL_MISMATCH", "原申请与原生报价的物料或规格不一致。")
    if not request_item.unit or row.get("unit") != request_item.unit:
        fail("COMPARISON_UNIT_MISMATCH", "报价单位与原申请不一致或未提供，不能换算猜配。")
    if number(row.get("quantity")) != request_item.quantity:
        fail("COMPARISON_QUANTITY_MISMATCH", "报价数量与本次批准申请行不一致。")
    return row


def _source_bundle(inquiry, item, context, *, lock=False):
    request = inquiry.source_purchase_request
    if request.purchase_mode != "STANDARD" or request.status != "approved" or request.approval_status != "completed":
        fail("COMPARISON_SOURCE_STATE_INVALID", "来源须为原流程已批准的标准采购申请。")
    if item.material.company_id != context["organizationId"] or item.material.code != item.material_code:
        fail("COMPARISON_MATERIAL_UNPROVEN", "原物料身份或企业归属不能准确证明。")
    inquiry_line = _line(inquiry.items, item)
    data = inquiry.quotation if isinstance(inquiry.quotation, dict) else {}
    candidates = data.get("supplierCandidates")
    if not isinstance(candidates, list) or not candidates:
        fail("COMPARISON_CANDIDATE_UNPROVEN", "原询价没有可证明的供应商候选范围。")
    expected = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):fail("COMPARISON_CANDIDATE_UNPROVEN", "原供应商候选范围格式不合法。")
        sid = str(candidate.get("supplierId") or candidate.get("supplierCode") or "").strip()
        if not sid or sid in expected:fail("COMPARISON_CANDIDATE_UNPROVEN", "原供应商候选标识缺失或重复。")
        suppliers = Supplier.objects.filter(company_id=context["organizationId"])
        supplier = (suppliers.filter(pk=identifier(candidate["supplierId"])).first()
                    if candidate.get("supplierId") else suppliers.filter(code=candidate.get("supplierCode")).first())
        if supplier is None or (candidate.get("supplierCode") and candidate["supplierCode"] != supplier.code):
            fail("COMPARISON_SUPPLIER_UNPROVEN", "候选供应商的正式身份或企业归属不能证明。")
        expected[sid] = {"id": supplier.pk, "code": supplier.code, "name": supplier.name}
    quotations = SupplierQuotation.objects.filter(source_inquiry=inquiry).order_by("id")
    if lock:quotations = quotations.select_for_update()
    quotations = list(quotations)
    if set(row.supplier_id for row in quotations) != set(expected):
        fail("COMPARISON_QUOTES_INCOMPLETE", "原候选报价尚未全部收齐，或出现范围外报价。")
    rows = []
    for quotation in quotations:
        if quotation.quotation_status != "received" or quotation.received_at is None:
            fail("COMPARISON_QUOTES_NOT_RECEIVED", "参与比较的原生报价尚未接收完成。")
        line = _line(quotation.items, item)
        price = number(line.get("unitPrice"))
        currency = str(quotation.currency or "").strip()
        if not currency:fail("COMPARISON_CURRENCY_MISSING", "原报价币种未提供。")
        supplier = expected[quotation.supplier_id]
        rows.append({"quotationId": quotation.pk, "quotationNo": quotation.quotation_no,
            "sourceInquiryId": inquiry.pk, "supplierId": quotation.supplier_id,
            "supplierMasterId": supplier["id"], "supplierCode": supplier["code"],
            "supplierName": quotation.supplier_name, "quotationStatus": quotation.quotation_status,
            "receivedAt": quotation.received_at.isoformat(), "sourceUpdatedAt": quotation.updated_at.isoformat(),
            "currency": currency, "requestLineNo": item.line_no, "unit": item.unit,
            "quantity": str(item.quantity), "unitPrice": str(price),
            "derivedLineAmount": str(item.quantity * price), "quotationDocumentAmount": str(quotation.amount),
            "lineSnapshot": copy.deepcopy(line)})
    if len({row["currency"] for row in rows}) != 1:
        fail("COMPARISON_CURRENCY_MISMATCH", "不同币种不能直接比较，本包不执行汇率换算。")
    snapshot = {"contractVersion": CONTRACT, "companyId": context["organizationId"],
        "request": {"id": request.pk, "no": request.request_no, "status": request.status,
            "approvalStatus": request.approval_status},
        "requestItem": {"id": item.pk, "lineNo": item.line_no, "materialId": item.material_id,
            "materialCode": item.material_code, "materialName": item.material_name,
            "specification": item.specification, "unit": item.unit, "quantity": str(item.quantity)},
        "inquiry": {"id": inquiry.pk, "no": inquiry.inquiry_no, "lineSnapshot": copy.deepcopy(inquiry_line)},
        "supplierCandidates": [{"sourceSupplierId": sid, **expected[sid]} for sid in sorted(expected)],
        "quotations": rows}
    return snapshot


def comparison_number(inquiry, item):
    # A generated business number, never a parser for object type or permission.
    return "QC-" + _canonical_hash({"inquiryNo": inquiry.inquiry_no,
                                   "requestItemId": item.pk})[:24].upper()


def _comparison_payload(snapshot, note):
    rows = snapshot["quotations"]
    prices = sorted({Decimal(row["unitPrice"]) for row in rows})
    return {"contractVersion": CONTRACT, "sourceSnapshot": snapshot,
        "sourceFingerprint": _canonical_hash(snapshot),
        "basis": {"policy": "SAME_SOURCE_LINE_UNIT_CURRENCY_QUANTITY_UNIT_PRICE_ONLY",
            "note": note, "currency": rows[0]["currency"], "unit": snapshot["requestItem"]["unit"],
            "quantity": snapshot["requestItem"]["quantity"],
            "tax": None, "freight": None, "deliveryTerms": None, "validUntil": None,
            "missingConditionStatus": "NOT_PROVIDED_NOT_ASSUMED"},
        "comparisonRows": [{**row, "priceRank": prices.index(Decimal(row["unitPrice"])) + 1} for row in rows],
        "lowestUnitPrice": str(prices[0]), "selectedSupplier": None,
        "automaticLowestQuoteSelected": False, "priceApproved": False}


def verify_registered_fact(fact, *, require_preparation=True):
    value = fact.comparison_result
    if not isinstance(value, dict) or value.get("contractVersion") != CONTRACT:
        fail("COMPARISON_REGISTRATION_UNPROVEN", "该比较缺少原生正式登记证明。")
    reg = value.get("registration");snapshot = value.get("sourceSnapshot")
    if not isinstance(reg, dict) or not isinstance(snapshot, dict):
        fail("COMPARISON_REGISTRATION_UNPROVEN", "正式来源和登记关系缺失。")
    try:
        payload = _comparison_payload(snapshot, value["basis"]["note"])
        expected = {**payload, "registration": reg}
        proof = {k: v for k, v in reg.items() if k != "auditId"}
        event = OrganizationOperatingAuditRecord.objects.filter(pk=reg["auditId"],
            action_code=PERMISSION, target_type="PurchaseInquiry", target_id=snapshot["inquiry"]["id"],
            organization_id=snapshot["companyId"], actor_id=reg["actorId"]).first()
        request = MasterDataWriteRequest.objects.filter(pk=reg["writeRequestId"],
            organization_id=snapshot["companyId"], action_code=PERMISSION, entity_type=ENTITY).first()
        evidence = [{"supplierId": row["supplierId"], "supplierCode": row["supplierCode"],
            "supplierName": row["supplierName"], "quotationNo": row["quotationNo"],
            "quotationAmount": row["derivedLineAmount"], "quotationDocumentAmount": row["quotationDocumentAmount"],
            "quotationStatus": row["quotationStatus"], "receivedAt": row["receivedAt"],
            "currency": row["currency"], "unit": row["unit"], "quantity": row["quantity"],
            "unitPrice": row["unitPrice"]} for row in snapshot["quotations"]]
        if (value != expected or fact.source_type != "server_fact" or
                fact.source_fingerprint != _canonical_hash(payload) or
                reg["registrationFingerprint"] != fact.source_fingerprint or
                reg["sourceFingerprint"] != payload["sourceFingerprint"] or
                str(fact.pk) != reg["factId"] or fact.fact_version != reg["factVersion"] or
                fact.comparison_no != reg["comparisonNo"] or fact.source_inquiry_no != snapshot["inquiry"]["no"] or
                fact.source_quotation_ids != [row["quotationId"] for row in snapshot["quotations"]] or
                fact.supplier_quote_evidence != evidence or
                fact.material_code != snapshot["requestItem"]["materialCode"] or
                fact.material_name != snapshot["requestItem"]["materialName"] or
                fact.quantity != Decimal(snapshot["requestItem"]["quantity"]) or
                fact.lowest_price != Decimal(payload["lowestUnitPrice"]) or
                fact.quotation_amount != [{"quotationId": row["quotationId"], "lineAmount": row["derivedLineAmount"],
                    "documentAmount": row["quotationDocumentAmount"]} for row in snapshot["quotations"]] or
                event is None or event.after_snapshot.get("registration") != proof or
                not event.after_snapshot.get("authorization", {}).get("allowed") or request is None or
                request.request_hash != _canonical_hash(request.audit_metadata) or
                request.audit_metadata.get("actorId") != reg["actorId"]):
            fail("COMPARISON_REGISTRATION_UNPROVEN", "正式比较与原生来源、动作或审计证明不一致。")
        previous_id = reg.get("previousFactId")
        if (fact.fact_version == 1 and previous_id is not None) or (fact.fact_version > 1 and
                not QuoteComparisonFact.objects.filter(pk=previous_id, comparison_no=fact.comparison_no,
                    fact_version=fact.fact_version - 1).exists()):
            fail("COMPARISON_VERSION_UNPROVEN", "比较版本缺少准确的原版承接关系。")
        if require_preparation:
            preparation = PriceApprovalPreparation.objects.filter(source_comparison=fact).first()
            if (preparation is None or request.status != "COMMITTED" or
                    request.result.get("factId") != str(fact.pk) or
                    request.result.get("preparationId") != preparation.pk or
                    request.result.get("auditId") != event.pk or
                    event.after_snapshot.get("preparationId") != preparation.pk or
                    not BusinessStateTransition.objects.filter(object_type="PriceApprovalPreparation",
                        object_id=preparation.pk, source_state="", target_state="draft",
                        action_code=PERMISSION, operator_id=reg["actorId"], version=1,
                        audit_reference=f"OrganizationOperatingAuditRecord:{event.pk}").exists()):
                fail("COMPARISON_PREPARATION_LINK_UNPROVEN", "比较、准备及原生初始化事实没有准确承接。")
        return snapshot, event, request
    except (KeyError, TypeError, ValueError, InvalidOperation, IndexError, AttributeError, ValidationError) as error:
        if isinstance(error, ComparisonRegistrationError):raise
        fail("COMPARISON_REGISTRATION_UNPROVEN", "正式比较来源证明格式不完整。")


def registration_context(*, user, inquiry_id, item_id):
    inquiry, item, context = _source_objects(user, inquiry_id, item_id)
    snapshot = _source_bundle(inquiry, item, context)
    facts = list(QuoteComparisonFact.objects.filter(comparison_no=comparison_number(inquiry, item)).order_by("fact_version"))
    for fact in facts:verify_registered_fact(fact)
    return {"contractVersion": CONTRACT, "sourceSnapshot": snapshot,
        "sourceFingerprint": _canonical_hash(snapshot), "comparisonNo": comparison_number(inquiry, item),
        "expectedPreviousFactId": str(facts[-1].pk) if facts else None,
        "expectedPreviousVersion": facts[-1].fact_version if facts else 0,
        "canRegister": execution_allowed(user, context) and not user.is_superuser,
        "statusCode": "SOURCE_VERIFIED_NOT_A_REGISTRATION", "statusLabel": "来源已核对，尚非登记结果",
        "automaticReplayAllowed": False, "businessWriteCount": 0}


def _result(row):
    return {**row.result, "resultState": "COMMITTED", "idempotencyKey": row.idempotency_key,
            "receiptAsOf": row.updated_at.isoformat(),
            "preparationStateMeaning": "INITIAL_STATE_AT_REGISTRATION_NOT_CURRENT_ELIGIBILITY",
            "executionAuthorizedByResult": False,
            "automaticReplayAllowed": False}


def action_result(*, user, inquiry_id, item_id, key):
    inquiry, item, _ = _source_objects(user, inquiry_id, item_id, write=True)
    key = text(key, "同次动作键", 160)
    row = MasterDataWriteRequest.objects.filter(organization_id=user.company_id,
        action_code=PERMISSION, entity_type=ENTITY, idempotency_key=key).first()
    if row and (row.audit_metadata.get("actorId") != user.pk or
                row.audit_metadata.get("inquiryId") != inquiry.pk or row.audit_metadata.get("requestItemId") != item.pk):
        fail("COMPARISON_RESULT_NOT_FOUND", "该同次动作不属于当前身份及来源。", 404)
    if row and row.status == "COMMITTED":
        fact = QuoteComparisonFact.objects.filter(pk=row.result.get("factId")).first()
        if fact is None:fail("COMPARISON_REGISTRATION_UNPROVEN", "原动作结果缺少正式比较。")
        verify_registered_fact(fact)
        return {**_result(row), "businessWriteCount": 0}
    return {"resultState": "UNKNOWN", "idempotencyKey": key, "result": None,
            "automaticReplayAllowed": False, "businessWriteCount": 0}


def authorize_preparation_creation(*, user, fact, registration_request=None):
    execution_qualification(user)
    snapshot, event, request = verify_registered_fact(fact, require_preparation=registration_request is None)
    inquiry, item, context = _source_objects(user, snapshot["inquiry"]["id"], snapshot["requestItem"]["id"], write=True, lock=True)
    if _canonical_hash(_source_bundle(inquiry, item, context, lock=True)) != fact.comparison_result["sourceFingerprint"]:
        fail("COMPARISON_SOURCE_CHANGED", "当前来源与本次比较版本不同，请查询原动作或重新登记准确版本。")
    if registration_request is not None and (not transaction.get_connection().in_atomic_block or
            registration_request.pk != request.pk or request.status != "RESERVED" or
            request.audit_metadata.get("actorId") != user.pk):
        fail("COMPARISON_PREPARATION_ACTION_REQUIRED", "准备只能承接同事务的原正式登记动作。", 403)
    return event, request


@transaction.atomic
def register_comparison(*, user, payload):
    execution_qualification(user)
    keys = {"inquiryId", "requestItemId", "expectedSourceFingerprint", "expectedPreviousFactId",
            "expectedPreviousVersion", "basisNote", "reason", "idempotencyKey"}
    if not isinstance(payload, dict) or set(payload) != keys:
        fail("COMPARISON_INPUT_INVALID", "须提交原生来源行、来源摘要、准确前版、比较依据和同次动作键；不得提交角色、范围或状态。", 400)
    note = text(payload["basisNote"], "比较依据说明")
    reason = text(payload["reason"], "登记原因")
    key = text(payload["idempotencyKey"], "同次动作键", 160)
    inquiry, item, context = _source_objects(user, payload["inquiryId"], payload["requestItemId"], write=True, lock=True)
    snapshot = _source_bundle(inquiry, item, context, lock=True)
    if payload["expectedSourceFingerprint"] != _canonical_hash(snapshot):
        fail("COMPARISON_SOURCE_CHANGED", "原报价或来源已变化，须重新读取准确来源，不得自动重放。")
    body = {**payload, "actorId": user.pk, "itemIds": [item.pk], "sourceModel": "procurement.PurchaseRequestItem"}
    prior = MasterDataWriteRequest.objects.filter(organization_id=user.company_id, action_code=PERMISSION, idempotency_key=key).first()
    if prior and prior.audit_metadata.get("actorId") != user.pk:
        fail("COMPARISON_RESULT_NOT_FOUND", "该同次动作不属于当前身份。", 404)
    request, created, _ = _write_request(user=user, action_code=PERMISSION, entity_type=ENTITY, key=key, request_body=body)
    if not created:
        if request.status != "COMMITTED":fail("COMPARISON_RESULT_UNKNOWN", "原动作结果尚未核实，请先查询同次结果。")
        fact = QuoteComparisonFact.objects.get(pk=request.result["factId"]);verify_registered_fact(fact)
        return {**_result(request), "idempotentReplay": True, "businessWriteCount": 0}
    no = comparison_number(inquiry, item)
    versions = list(QuoteComparisonFact.objects.select_for_update().filter(comparison_no=no).order_by("fact_version"))
    for old in versions:verify_registered_fact(old)
    previous = versions[-1] if versions else None
    expected_id = str(previous.pk) if previous else None
    expected_version = previous.fact_version if previous else 0
    if (type(payload["expectedPreviousVersion"]) is not int or payload["expectedPreviousVersion"] != expected_version or
            payload["expectedPreviousFactId"] != expected_id):
        fail("COMPARISON_VERSION_CONFLICT", "正式比较版本已变化；不得按时间猜选或覆盖原版。")
    value = _comparison_payload(snapshot, note)
    fingerprint = _canonical_hash(value)
    if QuoteComparisonFact.objects.filter(source_fingerprint=fingerprint).exists():
        fail("COMPARISON_ALREADY_REGISTERED", "同一来源和依据已经登记，请读取原事实及同次结果。")
    fact_id = uuid.uuid4();version = expected_version + 1
    proof = {"contractVersion": CONTRACT, "actionCode": ACTION, "factId": str(fact_id),
        "factVersion": version, "comparisonNo": no, "actorId": user.pk,
        "registeredAt": timezone.now().isoformat(), "previousFactId": expected_id,
        "sourceFingerprint": value["sourceFingerprint"], "registrationFingerprint": fingerprint,
        "writeRequestId": request.pk}
    decision = AuthorizationService.decide(user=user, action_code=PERMISSION,
        organization_id=context["organizationId"], business_object=context)
    event = OrganizationOperatingAuditRecord.objects.create(action_code=PERMISSION, actor=user,
        organization_id=context["organizationId"], target_type="PurchaseInquiry", target_id=inquiry.pk,
        target_label=inquiry.inquiry_no, reason=reason,
        before_snapshot={"previousFactId": expected_id, "previousVersion": expected_version},
        after_snapshot={"registration": proof, "authorization": decision})
    value["registration"] = {**proof, "auditId": event.pk}
    rows = snapshot["quotations"]
    evidence = [{"supplierId": row["supplierId"], "supplierCode": row["supplierCode"],
        "supplierName": row["supplierName"], "quotationNo": row["quotationNo"],
        "quotationAmount": row["derivedLineAmount"], "quotationDocumentAmount": row["quotationDocumentAmount"],
        "quotationStatus": row["quotationStatus"], "receivedAt": row["receivedAt"],
        "currency": row["currency"], "unit": row["unit"], "quantity": row["quantity"], "unitPrice": row["unitPrice"]} for row in rows]
    fact = QuoteComparisonFact.objects.create(fact_id=fact_id, comparison_no=no,
        source_inquiry_no=inquiry.inquiry_no, source_quotation_ids=[row["quotationId"] for row in rows],
        supplier_quote_evidence=evidence, material_code=item.material_code, material_name=item.material_name,
        quantity=item.quantity, quotation_amount=[{"quotationId": row["quotationId"],
            "lineAmount": row["derivedLineAmount"], "documentAmount": row["quotationDocumentAmount"]} for row in rows],
        lowest_price=value["lowestUnitPrice"], comparison_result=value, source_type="server_fact",
        fact_version=version, generated_at=timezone.now(), source_fingerprint=fingerprint)
    from .price_approval_preparation_service import create_price_approval_preparation
    preparation, was_created = create_price_approval_preparation(fact_id=str(fact.pk), expected_version=version,
        actor=user, registration_request=request)
    if not was_created:fail("COMPARISON_PREPARATION_CONFLICT", "新的比较版本已有其他准备，须核实原动作。")
    event.after_snapshot = {**event.after_snapshot, "preparationId": preparation.pk,
        "preparationNo": preparation.approval_prepare_no, "initialState": "draft"}
    event.save(update_fields=["after_snapshot"])
    record_projected_business_transition(object_type="PriceApprovalPreparation", object_id=preparation.pk,
        source_state="", target_state="draft", action_code=PERMISSION, operator=user,
        reason=reason, audit_reference=f"OrganizationOperatingAuditRecord:{event.pk}", allowed_transitions={("", "draft")})
    result = {"factId": str(fact.pk), "comparisonNo": no, "factVersion": version,
        "targetId": str(fact.pk), "objectType": "QuoteComparisonFact",
        "preparationId": preparation.pk, "approvalPrepareNo": preparation.approval_prepare_no,
        "statusCode": "draft", "statusLabel": "草稿（待核价）", "auditId": event.pk,
        "sourceFingerprint": value["sourceFingerprint"], "selectedSupplier": None,
        "priceApproved": False, "idempotentReplay": False, "businessWriteCount": 2}
    _commit_request(request, result)
    verify_registered_fact(fact)
    return _result(request)


def serialize_registered_comparison(fact):
    snapshot, event, _ = verify_registered_fact(fact)
    value = fact.comparison_result;registration = value["registration"]
    return {"objectId": str(fact.pk), "objectType": "QuoteComparisonFact", "objectNo": fact.comparison_no,
        "factId": str(fact.pk), "quoteComparisonNo": fact.comparison_no, "factVersion": fact.fact_version,
        "sourceInquiryId": snapshot["inquiry"]["id"], "sourceInquiryNo": fact.source_inquiry_no,
        "sourcePurchaseRequestId": snapshot["request"]["id"], "sourcePurchaseRequestNo": snapshot["request"]["no"],
        "sourcePurchaseRequestItemId": snapshot["requestItem"]["id"], "materialCode": fact.material_code,
        "materialName": fact.material_name, "quantity": str(fact.quantity), "unit": snapshot["requestItem"]["unit"],
        "basis": value["basis"], "comparisonRows": value["comparisonRows"], "lowestUnitPrice": str(fact.lowest_price),
        "registeredAt": registration["registeredAt"], "registeredByUserId": event.actor_id,
        "registrationAuditId": event.pk, "sourceFingerprint": value["sourceFingerprint"],
        "previousFactId": registration["previousFactId"], "verifiedStatus": fact.verified_status,
        "statusCode": "registered", "statusLabel": "已登记，待核价", "selectedSupplier": None,
        "priceApproved": False, "automaticLowestQuoteSelected": False, "factSource": "server"}

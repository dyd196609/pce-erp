from pde.baseline_usage_service import production_baselines, production_status
"""Controlled registration of one order-engineering document and its first draft.

The caller supplies business identity only (order/line and the three confirmed
document facts).  All technical references are resolved from persisted server
facts and the two writes deliberately remain separate: if the header commits
and the first-version write fails, the header is retained and reported as a
partial write.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
import re

from django.core.exceptions import ValidationError
from django.db import transaction


from system.authorization import AuthorizationService

from .admission_chain_revocation import active_order_engineering_instances
from .crm_order_admission import CRMOrderAdmissionError, require_current_order_admission
from .manufacturing_structure_service import (
    ManufacturingStructureError,
    ManufacturingStructureService,
)
from .models import (
    BOMVersion,
    EngineeringCalculationRecord,
    EngineeringDocument,
    EngineeringDocumentVersion,
    ManufacturingReleaseSubjectType,
    OrderEngineeringBaseline,
    ProductManufacturingOutput,
)
from .production_foundation_service import (
    ProductionFoundationError,
    ProductionFoundationService,
    _actor_chain,
)


class OrderEngineeringDocumentRegistrationError(Exception):
    def __init__(self, code, message, *, outcome="BLOCKED_BEFORE_WRITE", details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.outcome = outcome
        self.details = details or {}

    def as_dict(self):
        return {
            "outcome": self.outcome,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


@dataclass(frozen=True)
class ResolvedOrderEngineeringDocumentChain:
    company: object
    order: object
    sales_order_item: object
    instance: object
    baseline: object
    calculation: object
    bom_version: object
    routing: object
    routing_version: object
    routing_step_count: int
    admission: object

    @property
    def identity(self):
        return {
            "companyId": self.company.pk,
            "salesOrderId": self.order.pk,
            "salesOrderItemId": self.sales_order_item.pk,
            "orderEngineeringInstanceId": self.instance.pk,
            "engineeringBaselineId": self.baseline.pk,
            "engineeringCalculationId": self.calculation.pk,
            "productBomId": self.bom_version.bom_id,
            "bomVersionId": self.bom_version.pk,
            "routingId": self.routing.pk,
            "routingVersionId": self.routing_version.pk,
            "routingStepCount": self.routing_step_count,
            "releaseSubjectType": ManufacturingReleaseSubjectType.ORDER_ENGINEERED_PRODUCT,
        }

    def as_dict(self):
        return {
            "company": {"id": self.company.pk, "code": self.company.code},
            "salesOrder": {"id": self.order.pk, "orderNo": self.order.order_no},
            "salesOrderItem": {
                "id": self.sales_order_item.pk,
                "lineNo": self.sales_order_item.line_no,
            },
            "orderEngineeringInstance": {
                "id": self.instance.pk,
                "instanceNo": self.instance.instance_no,
                "status": self.instance.status,
            },
            "engineeringBaseline": {
                "id": self.baseline.pk,
                "baselineNo": self.baseline.baseline_no,
                "status": self.baseline.status,
            },
            "engineeringCalculation": {
                "id": self.calculation.pk,
                "calculationNo": self.calculation.calculation_no,
                "revision": self.calculation.revision,
                "status": self.calculation.status,
            },
            "productBom": {
                "id": self.bom_version.bom_id,
                "bomCode": self.bom_version.bom.bom_code,
            },
            "bomVersion": {
                "id": self.bom_version.pk,
                "bomVersion": self.bom_version.bom_version,
                "revision": self.bom_version.revision,
                "status": self.bom_version.status,
            },
            "routing": {
                "id": self.routing.pk,
                "routingCode": self.routing.routing_code,
                "name": self.routing.name,
                "status": self.routing.status,
            },
            "routingVersion": {
                "id": self.routing_version.pk,
                "routingVersion": self.routing_version.routing_version,
                "revision": self.routing_version.revision,
                "status": self.routing_version.status,
                "stepCount": self.routing_step_count,
            },
            "releaseSubjectType": ManufacturingReleaseSubjectType.ORDER_ENGINEERED_PRODUCT,
        }


class OrderEngineeringDocumentRegistrationService:
    PERMISSION = "production.engineering.document.maintain"
    SOURCE_SYSTEM = "PCE"
    SOURCE_TYPE = "FORMAL_BUSINESS_REGISTRATION"
    SOURCE_OBJECT_TYPE = "ORDER_ENGINEERING_DOCUMENT_REGISTRATION"
    CONTINUATION_CONTRACT = "PCE-ORDER-ENGINEERING-DOCUMENT-VERSION-CONTINUATION-V1"

    @staticmethod
    def _digest(value):
        return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), default=str).encode("utf-8")).hexdigest()

    @staticmethod
    def _saved_row(row):
        return json.loads(json.dumps({field.attname: getattr(row, field.attname)
            for field in row._meta.concrete_fields}, default=str))

    @classmethod
    def _continuation_lineage(cls, previous, current, *, company_id, item_id, instance_id):
        from .engineering_calculation_continuation_service import continuation_proof
        from .models import EngineeringCalculationContinuation, LegacyInFlightOrderAdoption

        proofs, seen = [], set()
        while current.pk != previous.pk and len(proofs) < 32:
            if current.pk in seen:
                break
            seen.add(current.pk)
            row = EngineeringCalculationContinuation.objects.select_related(
                "previous_calculation", "new_calculation", "baseline", "adoption",
                "write_request", "audit_record").filter(
                    company_id=company_id, new_calculation_id=current.pk, status="committed").first()
            if (row is None and current.supersedes_id and not LegacyInFlightOrderAdoption.objects.filter(
                    company_id=company_id,sales_order_id=current.sales_order_item.sales_order_id).exists()):
                from .formal_engineering_continuation_service import native_successor_proof
                try:
                    proof=native_successor_proof(current.supersedes,current,company_id=company_id,
                        item_id=item_id,instance_id=instance_id)
                except Exception as exc:
                    if not hasattr(exc,'code') and not isinstance(exc,ValidationError):raise
                    raise OrderEngineeringDocumentRegistrationError('DOCUMENT_CONTINUATION_MAIN_UNPROVEN',
                        '原生新单主核算接续证明未通过；历史承接不得降级绕过0046。',
                        details={'cause':getattr(exc,'code','VALIDATION_ERROR')}) from exc
                proofs.append(proof);current=current.supersedes
                continue
            if (row is None or row.sales_order_item_id != item_id
                    or row.engineering_instance_id != instance_id):
                break
            try:
                proofs.append(continuation_proof(row))
            except Exception as exc:
                if not hasattr(exc, "code") and not isinstance(exc, ValidationError):
                    raise
                raise OrderEngineeringDocumentRegistrationError(
                    "DOCUMENT_CONTINUATION_MAIN_UNPROVEN", "新主核算接续的原生证明未通过。",
                    details={"cause": getattr(exc, "code", "VALIDATION_ERROR")}) from exc
            current = row.previous_calculation
        if current.pk != previous.pk or not proofs:
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_CONTINUATION_LINEAGE_REQUIRED", "新主核算必须有回到前驱资料固定核算的完整0046接续链。")
        return list(reversed(proofs))

    @classmethod
    def _continuation_creation_proof(cls, version, identity, context_hash):
        from masterdata.models import ExternalIdentity, MasterDataWriteRequest
        from system.models import OrganizationOperatingAuditRecord
        from .production_foundation_service import _snapshot

        try:
            version.full_clean()
        except ValidationError as exc:
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_CONTINUATION_EXISTING_UNPROVEN", "已有资料版本的精确关系校验未通过。") from exc

        source = ExternalIdentity.objects.filter(
            organization_id=identity["organizationId"], source_system=cls.SOURCE_SYSTEM,
            source_type=cls.SOURCE_TYPE, source_object_type=cls.CONTINUATION_CONTRACT,
            external_id=identity["externalId"]).first()
        if (not source or source.mapping_status != "MATCH"
                or source.target_entity_type != "engineering-document-versions"
                or source.target_entity_id != str(version.pk)
                or source.source_fingerprint != context_hash
                or source.audit_metadata.get("contextHash") != context_hash
                or cls._digest(source.audit_metadata.get("contextSnapshot")) != context_hash):
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_CONTINUATION_EXISTING_UNPROVEN", "已有新资料版本缺少一致的正式接续来源证明。")
        requests = list(MasterDataWriteRequest.objects.filter(
            organization_id=identity["organizationId"], source_identity=source,
            action_code="production.master_data.create", entity_type="engineering-document-versions",
            target_entity_id=str(version.pk), status="COMMITTED").order_by("pk"))
        originals = [row for row in requests if row.result.get("auditId")]
        if len(originals) != 1:
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_CONTINUATION_EXISTING_UNPROVEN", "资料接续缺少唯一原生创建请求及审计。")
        request = originals[0]
        audit = OrganizationOperatingAuditRecord.objects.select_related("actor").only(
            "id", "organization_id", "action_code", "target_type", "target_id", "actor_id",
            "reason", "before_snapshot", "after_snapshot", "actor__id", "actor__username",
            "actor__company_id").filter(pk=request.result["auditId"],
            organization_id=identity["organizationId"], action_code=cls.PERMISSION,
            target_type="EngineeringDocumentVersion", target_id=version.pk).first()
        stored = request.result.get("row") or {}
        current = _snapshot(version)
        fields = {field.attname for field in version._meta.concrete_fields}
        if (not audit or audit.actor_id != request.audit_metadata.get("operatorId")
                or audit.actor.company_id != identity["organizationId"]
                or audit.before_snapshot.get("state") != {}
                or audit.after_snapshot.get("authorization", {}).get("allowed") is not True
                or audit.after_snapshot.get("executionChain", {}).get("account") != audit.actor.username
                or audit.after_snapshot.get("importContext", {}).get("contextHash") != context_hash
                or audit.after_snapshot.get("importContext") != source.audit_metadata
                or stored.get("status") != "draft"
                or set(stored) != fields
                or any(stored.get(key) != current.get(key) for key in fields - {"status", "updated_at"})
                or audit.after_snapshot.get("state") != stored):
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_CONTINUATION_EXISTING_UNPROVEN", "资料接续版本与原生创建审计不一致。")
        payload_keys = ("document_id", "document_name", "document_version", "release_subject_type",
            "order_engineering_instance_id", "order_engineering_baseline_id", "engineering_calculation_id",
            "related_bom_id", "related_routing_id")
        source_intent = {"sourceSystem": source.source_system, "sourceType": source.source_type,
            "sourceObjectType": source.source_object_type, "externalId": source.external_id,
            "sourceFingerprint": source.source_fingerprint, "auditMetadata": source.audit_metadata}
        expected_request = cls._digest({"entity": "engineering-document-versions",
            "payload": {**{key: stored[key] for key in payload_keys}, "reason": audit.reason},
            "sourceIdentity": source_intent})
        if request.request_hash != expected_request:
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_CONTINUATION_EXISTING_UNPROVEN", "资料创建请求Hash与原生载荷不一致。")
        if version.status in {"reviewed", "released"}:
            from .engineering_document_version_review_service import review_readback
            from .engineering_document_version_release_service import (release_readback,
                project_release_content_integrity)
            review = review_readback(version)
            if (not review.get("completed") or not review.get("projectionConsistent")
                    or not project_release_content_integrity(version).get("valid")
                    or version.status == "released" and not release_readback(version).get("completed")):
                raise OrderEngineeringDocumentRegistrationError(
                    "DOCUMENT_CONTINUATION_EXISTING_UNPROVEN", "已有版本的评审或发布状态缺少原生证明。")
        elif version.status != "draft":
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_CONTINUATION_EXISTING_UNPROVEN", "已有接续版本当前状态不支持重放办理。")
        return {"sourceIdentityId": source.pk, "actionRequestId": request.pk, "auditId": audit.pk}

    @classmethod
    def _prepare_version_continuation(cls, *, user, predecessor_version_id, order_no, line_no,
            baseline_id, calculation_id, bom_version_id, routing_version_id, authorization_reference,
            lock=False):
        from .engineering_document_version_release_service import (release_readback,
            project_release_content_integrity, project_release_source_completeness)
        from .engineering_document_version_review_service import review_readback
        from .bom_version_control_service import _assert_upstream_gates, release_readback as bom_release_readback
        from .manufacturing_output_generation_service import _saved_requirement_integrity

        selections = (predecessor_version_id, baseline_id, calculation_id, bom_version_id, routing_version_id)
        if any(type(value) is not int or value <= 0 for value in selections):
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_CONTINUATION_SCOPE_REQUIRED", "必须明确前驱资料版本及新基线、核算、BOM和路线版本。")
        if not str(authorization_reference or "").strip():
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_CONTINUATION_AUTHORITY_REQUIRED", "资料版本接续必须提供本次授权依据。")
        if not user or not user.is_authenticated or not user.is_active or user.is_superuser:
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_CONTINUATION_BUSINESS_ACTOR_REQUIRED", "资料接续必须由具正式人员资格的现有业务账号办理。")
        authorization = AuthorizationService.decide(user=user, action_code=cls.PERMISSION,
            organization_id=user.company_id, business_object={"organizationId": user.company_id})
        if not authorization.get("allowed"):
            raise OrderEngineeringDocumentRegistrationError(
                authorization.get("decisionCode", "PERMISSION_DENIED"),
                authorization.get("reason", "当前账户无权维护工程资料。"))
        try:
            execution_chain = _actor_chain(user)
        except ProductionFoundationError as exc:
            raise OrderEngineeringDocumentRegistrationError(exc.code, exc.message, details=exc.details) from exc
        query = EngineeringDocumentVersion.objects.select_related("document", "related_bom__bom",
            "related_routing__routing", "engineering_calculation", "order_engineering_baseline",
            "order_engineering_instance__sales_order_item__sales_order")
        if lock:
            query = query.select_for_update()
        previous = query.filter(pk=predecessor_version_id).first()
        if (previous is None or previous.release_subject_type != ManufacturingReleaseSubjectType.ORDER_ENGINEERED_PRODUCT
                or not previous.order_engineering_instance_id
                or previous.order_engineering_instance.company_id != user.company_id):
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_CONTINUATION_PREDECESSOR_INVALID", "前驱必须是当前公司真实的订单工程资料版本。")
        document_query = EngineeringDocument.objects.filter(pk=previous.document_id)
        if lock:
            document_query = document_query.select_for_update()
        document = document_query.get()
        previous.document = document
        old_release = release_readback(previous)
        old_review = review_readback(previous)
        old_integrity = project_release_content_integrity(previous)
        old_sources = project_release_source_completeness(previous)
        if (previous.status != "released" or not old_release.get("completed")
                or not old_review.get("projectionConsistent")
                or not old_integrity.get("valid") or not old_sources.get("complete")):
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_CONTINUATION_PREDECESSOR_UNPROVEN", "前驱资料缺少完整原生评审、发布或固定内容证明。")
        chain = cls.resolve_chain(user=user, order_no=order_no, line_no=line_no, baseline_id=baseline_id,
            calculation_id=calculation_id, bom_version_id=bom_version_id, routing_version_id=routing_version_id)
        if (document.order_engineering_instance_id != chain.instance.pk
                or previous.order_engineering_instance_id != chain.instance.pk
                or document.product_bom_id != chain.bom_version.bom_id
                or document.routing_id != chain.routing.pk
                or chain.calculation.pk == previous.engineering_calculation_id
                or chain.baseline.pk == previous.order_engineering_baseline_id):
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_CONTINUATION_SOURCE_MISMATCH", "新来源必须沿用同一资料头、订单工程实例、BOM主表和路线主表，且为独立新基线及主核算。")
        lineage = cls._continuation_lineage(previous.engineering_calculation, chain.calculation,
            company_id=user.company_id, item_id=chain.sales_order_item.pk, instance_id=chain.instance.pk)
        if chain.bom_version.status != "released" or not bom_release_readback(chain.bom_version).get("released"):
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_CONTINUATION_BOM_UNRELEASED", "新准确BOM版本必须已经通过原生正式发布。")
        try:
            _assert_upstream_gates(chain.bom_version)
            requirements = list(chain.calculation.material_requirements.select_related(
                "material", "uom", "source_detail__rule").order_by("pk"))
            for requirement in requirements:
                _saved_requirement_integrity(requirement)
        except Exception as exc:
            if not hasattr(exc, "code") and not isinstance(exc, ValidationError):
                raise
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_CONTINUATION_MATERIAL_SOURCE_UNPROVEN", "新BOM或材料需求的原生来源证明未通过。",
                details={"cause": getattr(exc, "code", "VALIDATION_ERROR")}) from exc
        if not requirements:
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_CONTINUATION_MATERIAL_SOURCE_UNPROVEN", "新版本必须保留完整非空正式材料来源。")
        siblings = list(query.filter(document_id=document.pk).order_by("pk"))
        exact = [row for row in siblings if (row.order_engineering_baseline_id, row.engineering_calculation_id,
            row.related_bom_id, row.related_routing_id) == (baseline_id, calculation_id, bom_version_id, routing_version_id)]
        if len(exact) > 1:
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_CONTINUATION_TARGET_AMBIGUOUS", "同一准确来源存在多个资料版本，拒绝静默选择。")
        existing = exact[0] if exact else None
        other_successors = [row for row in siblings if row.pk != previous.pk
            and (not existing or row.pk != existing.pk) and row.status in {"draft", "reviewed"}]
        numbers = []
        for row in siblings:
            match = re.fullmatch(r"V([1-9][0-9]*)\.0", row.document_version)
            if not match:
                raise OrderEngineeringDocumentRegistrationError(
                    "DOCUMENT_CONTINUATION_VERSION_SEQUENCE_UNPROVEN", "已有资料版本不符合正式Vn.0序列，禁止猜测后续编号。")
            numbers.append(int(match.group(1)))
        if not existing and (other_successors or any(row.status == "released"
                and int(row.document_version[1:-2]) > int(previous.document_version[1:-2]) for row in siblings)):
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_CONTINUATION_COMPETING_VERSION", "存在其他待办理版本或更新已发布版本，请明确当前正式前驱。")
        version_no = existing.document_version if existing else f"V{max(numbers) + 1}.0"
        header_identity = {key: getattr(document, key) for key in ("id", "document_no", "document_name",
            "document_type", "release_subject_type", "product_id", "order_engineering_instance_id", "product_bom_id", "routing_id")}
        context = {"contractVersion": cls.CONTINUATION_CONTRACT, "documentIdentity": header_identity,
            "predecessor": cls._saved_row(previous), "predecessorRelease": old_release,
            "predecessorStableContentHash": old_integrity["stableCurrentContentHash"],
            "chain": chain.identity, "mainContinuationProofs": lineage, "documentVersion": version_no,
            "materialRequirements": [cls._saved_row(row) for row in requirements],
            "bom": cls._saved_row(chain.bom_version),
            "bomItems": list(chain.bom_version.items.order_by("pk").values()),
            "bomSourceLinks": list(chain.bom_version.items.order_by("pk").values(
                "source_requirements__id", "source_requirements__bom_item_id",
                "source_requirements__material_requirement_id", "source_requirements__contributed_quantity")),
            "routingVersion": cls._saved_row(chain.routing_version),
            "routingSteps": list(chain.routing_version.steps.order_by("pk").values())}
        context = json.loads(json.dumps(context, default=str))
        context_hash = cls._digest(context)
        target = {"documentId": document.pk, "predecessorVersionId": previous.pk, **chain.identity}
        identity = {"organizationId": user.company_id,
            "externalId": "DocumentVersionContinuation:" + cls._digest(target)}
        creation = cls._continuation_creation_proof(existing, identity, context_hash) if existing else None
        return {"contextHash": context_hash, "contextSnapshot": context, "chainObject": chain,
            "document": document, "previous": previous, "existing": existing, "versionNo": version_no,
            "identity": identity, "authorization": authorization, "executionChain": execution_chain,
            "creationProof": creation}

    @classmethod
    def preview_version_continuation(cls, **kwargs):
        prepared = cls._prepare_version_continuation(**kwargs)
        return {"contractVersion": cls.CONTINUATION_CONTRACT, "contextHash": prepared["contextHash"],
            "contextSnapshot": prepared["contextSnapshot"], "chain": prepared["chainObject"].as_dict(),
            "documentVersion": prepared["versionNo"], "predecessorVersionId": prepared["previous"].pk,
            "existingVersionId": prepared["existing"].pk if prepared["existing"] else None,
            "idempotentComplete": bool(prepared["existing"]), "businessWriteCount": 0}

    @classmethod
    @transaction.atomic
    def apply_version_continuation(cls, *, expected_context_hash, idempotency_key, reason, **kwargs):
        key, reason = str(idempotency_key or "").strip(), str(reason or "").strip()
        if not key or len(key) > 150 or not reason or len(reason) > 300:
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_CONTINUATION_WRITE_INTENT_REQUIRED", "必须提供有效幂等键和真实接续原因。")
        prepared = cls._prepare_version_continuation(**kwargs, lock=True)
        if expected_context_hash != prepared["contextHash"]:
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_CONTINUATION_STALE_PREVIEW", "前驱或准确新来源已变化，请重新读取完整接续预览。")
        chain, document, previous = (prepared[key] for key in ("chainObject", "document", "previous"))
        before_header, before_previous = cls._saved_row(document), cls._saved_row(previous)
        source = {"sourceSystem": cls.SOURCE_SYSTEM, "sourceType": cls.SOURCE_TYPE,
            "sourceObjectType": cls.CONTINUATION_CONTRACT, "externalId": prepared["identity"]["externalId"],
            "sourceFingerprint": prepared["contextHash"], "auditMetadata": {
                "channel": "OrderEngineeringDocumentRegistrationService", "contractVersion": cls.CONTINUATION_CONTRACT,
                "authorizationReference": str(kwargs["authorization_reference"]).strip(),
                "contextHash": prepared["contextHash"], "contextSnapshot": prepared["contextSnapshot"]}}
        payload = {"document_id": document.pk, "document_name": previous.document_name,
            "document_version": prepared["versionNo"], "release_subject_type": ManufacturingReleaseSubjectType.ORDER_ENGINEERED_PRODUCT,
            "order_engineering_instance_id": chain.instance.pk, "order_engineering_baseline_id": chain.baseline.pk,
            "engineering_calculation_id": chain.calculation.pk, "related_bom_id": chain.bom_version.pk,
            "related_routing_id": chain.routing_version.pk, "reason": reason}
        try:
            written = ProductionFoundationService.write("engineering-document-versions", user=kwargs["user"],
                payload=payload, idempotency_key=key, source_identity=source)
        except ProductionFoundationError as exc:
            raise OrderEngineeringDocumentRegistrationError(exc.code, exc.message, details=exc.details) from exc
        version = EngineeringDocumentVersion.objects.get(pk=written["row"]["id"])
        proof = cls._continuation_creation_proof(version, prepared["identity"], prepared["contextHash"])
        document.refresh_from_db(); previous.refresh_from_db()
        if cls._saved_row(document) != before_header or cls._saved_row(previous) != before_previous:
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_CONTINUATION_PREDECESSOR_CHANGED", "资料接续不得修改原资料主表或已发布前驱。")
        return {"contractVersion": cls.CONTINUATION_CONTRACT, "contextHash": prepared["contextHash"],
            "idempotentReplay": bool(prepared["existing"]), "businessWriteCount": 0 if prepared["existing"] else 1,
            "chain": chain.as_dict(), "readback": cls._readback(document=document, version=version, chain=chain),
            "creationProof": proof, "write": written, "predecessorUnchanged": True, "documentHeaderUnchanged": True}

    @classmethod
    def _one(cls, queryset, *, code, message):
        rows = list(queryset[:2])
        if len(rows) != 1:
            raise OrderEngineeringDocumentRegistrationError(
                code,
                message,
                details={"candidateCount": len(rows), "failClosed": True},
            )
        return rows[0]

    @classmethod
    def resolve_chain(cls, *, user, order_no, line_no, baseline_id=None,
                      calculation_id=None, bom_version_id=None, routing_version_id=None):
        selections = [baseline_id, calculation_id, bom_version_id, routing_version_id]
        if any(value is not None and (isinstance(value, bool) or not str(value).isdigit() or int(value) <= 0)
               for value in selections):
            raise OrderEngineeringDocumentRegistrationError("ENGINEERING_VERSION_ID_INVALID", "明确选择的工程版本必须是有效正整数。")
        baseline_id, calculation_id, bom_version_id, routing_version_id = [
            None if value is None else int(value) for value in selections]
        order_no = str(order_no or "").strip()
        try:
            line_no = int(line_no)
        except (TypeError, ValueError) as exc:
            raise OrderEngineeringDocumentRegistrationError(
                "ORDER_LINE_INVALID", "订单行必须是有效整数。",
            ) from exc
        if not order_no or line_no <= 0:
            raise OrderEngineeringDocumentRegistrationError(
                "ORDER_LINE_REQUIRED", "必须提供正式订单号和正整数订单行。",
            )

        instance = cls._one(
            active_order_engineering_instances().select_related(
                "company", "sales_order_item__sales_order", "source_record",
            ).filter(
                company_id=user.company_id,
                sales_order_item__sales_order__order_no=order_no,
                sales_order_item__line_no=line_no,
            ),
            code="ORDER_ENGINEERING_INSTANCE_NOT_UNIQUE",
            message="订单号和订单行未能唯一解析活动订单工程实例。",
        )
        item = instance.sales_order_item
        order = item.sales_order
        if instance.status not in {"calculated", "released"}:
            raise OrderEngineeringDocumentRegistrationError(
                "ORDER_ENGINEERING_INSTANCE_NOT_CALCULATED",
                "订单工程实例尚未完成工程转换。",
                details={"instanceId": instance.pk, "status": instance.status},
            )
        if instance.source_record.status != "confirmed":
            raise OrderEngineeringDocumentRegistrationError(
                "ENGINEERING_SOURCE_NOT_CONFIRMED", "工程来源不是已确认正式事实。",
            )

        baseline_query = production_baselines().select_related("company", "sales_order").filter(
                company_id=instance.company_id,
                sales_order_id=order.pk,
                status="confirmed",
                items__design_item__sales_order_item_id=item.pk,
                items__source_record_id=instance.source_record_id,
                items__confirmable=True,
            ).distinct()
        if baseline_id is not None:
            baseline_query = baseline_query.filter(pk=baseline_id)
        baseline = cls._one(
            baseline_query,
            code="CONFIRMED_BASELINE_NOT_UNIQUE",
            message="未能唯一解析覆盖当前订单行与来源的已确认工程基线。",
        )
        calculation_query = EngineeringCalculationRecord.objects.select_related(
                "company", "engineering_instance", "source_record", "sales_order_item",
            ).filter(
                company_id=instance.company_id,
                engineering_instance_id=instance.pk,
                sales_order_item_id=item.pk,
                source_record_id=instance.source_record_id,
                status="completed",
            )
        if calculation_id is not None:
            calculation_query = calculation_query.filter(pk=calculation_id)
        # Legacy unambiguous calls retain their contract. Explicit version
        # selection must prove the calculation was made from this baseline.
        if baseline_id is not None or calculation_id is not None:
            calculation_query = calculation_query.filter(trace__baselineReference__id=baseline.pk,
                trace__baselineReference__snapshotHash=baseline.snapshot_hash)
        calculation = cls._one(
            calculation_query,
            code="COMPLETED_CALCULATION_NOT_UNIQUE",
            message="未能唯一解析当前订单行的已完成工程核算。",
        )
        bom_query = BOMVersion.objects.select_related("bom", "order_engineering_instance", "source_calculation").filter(
                order_engineering_instance_id=instance.pk,
                source_calculation_id=calculation.pk,
                bom_scope="order_specific",
            )
        if bom_version_id is not None:
            bom_query = bom_query.filter(pk=bom_version_id)
        bom_version = cls._one(
            bom_query,
            code="ORDER_BOM_VERSION_NOT_UNIQUE",
            message="未能唯一解析由当前工程核算形成的按单BOM版本。",
        )
        if (
            not bom_version.bom_id
            or bom_version.bom.order_engineering_instance_id != instance.pk
            or bom_version.bom.company_id != instance.company_id
        ):
            raise OrderEngineeringDocumentRegistrationError(
                "ORDER_BOM_HEADER_MISMATCH", "按单BOM版本与订单工程实例归属不一致。",
            )

        try:
            exact_context = {
                "organizationId": instance.company_id,
                "salesOrderItemId": item.pk,
                "orderEngineeringInstanceId": instance.pk,
                "orderEngineeringBaselineId": baseline.pk,
                "engineeringCalculationId": calculation.pk,
                "bomVersionId": bom_version.pk,
            }
            resolved_routing = ManufacturingStructureService.resolve_effective_routing(
                instance,
                exact_version_context=exact_context,
            )
            if routing_version_id is not None and resolved_routing["routing_version"].pk != int(routing_version_id):
                raise ManufacturingStructureError(
                    "EXPLICIT_ROUTING_VERSION_MISMATCH", "所选工艺版本与正式上下文解析结果不一致。",
                    {"selectedRoutingVersionId": routing_version_id,
                     "resolvedRoutingVersionId": resolved_routing["routing_version"].pk},
                )
        except ManufacturingStructureError as exc:
            raise OrderEngineeringDocumentRegistrationError(
                exc.code, exc.message, details=exc.details,
            ) from exc
        routing = resolved_routing["routing"]
        routing_version = resolved_routing["routing_version"]
        routing_step_count = routing_version.steps.count()
        if routing.status != "released" or routing_version.status != "released":
            raise OrderEngineeringDocumentRegistrationError(
                "ROUTING_NOT_RELEASED", "正式解析结果不是已发布工艺路线及版本。",
            )
        if routing_step_count <= 0:
            raise OrderEngineeringDocumentRegistrationError(
                "ROUTING_STEPS_REQUIRED", "正式工艺路线版本没有工序。",
            )

        try:
            admission = require_current_order_admission(
                order=order,
                lock=False,
                sales_order_item_id=item.pk,
                engineering_instance_id=instance.pk,
                calculation_id=calculation.pk,
            )
        except CRMOrderAdmissionError as exc:
            raise OrderEngineeringDocumentRegistrationError(
                exc.code, exc.message, details=exc.details,
            ) from exc

        return ResolvedOrderEngineeringDocumentChain(
            company=instance.company,
            order=order,
            sales_order_item=item,
            instance=instance,
            baseline=baseline,
            calculation=calculation,
            bom_version=bom_version,
            routing=routing,
            routing_version=routing_version,
            routing_step_count=routing_step_count,
            admission=admission,
        )

    @staticmethod
    def _normalized_inputs(*, document_no, document_name, document_type):
        values = {
            "documentNo": str(document_no or "").strip(),
            "documentName": str(document_name or "").strip(),
            "documentType": str(document_type or "").strip(),
        }
        if not values["documentNo"] or not values["documentName"]:
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_FACTS_REQUIRED", "资料编号和资料名称不能为空。",
            )
        if len(values["documentNo"]) > 64 or len(values["documentName"]) > 200:
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_FACTS_TOO_LONG", "资料编号或资料名称超过正式模型长度。",
            )
        legal_types = {code for code, _label in EngineeringDocument.DOCUMENT_TYPE_CHOICES}
        if values["documentType"] not in legal_types:
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_TYPE_INVALID", "资料类型不是现有正式枚举。",
                details={"legalTypes": sorted(legal_types)},
            )
        return values

    @staticmethod
    def _document_mismatches(document, chain, facts):
        expected = {
            "document_name": facts["documentName"],
            "document_type": facts["documentType"],
            "release_subject_type": ManufacturingReleaseSubjectType.ORDER_ENGINEERED_PRODUCT,
            "product_id": None,
            "order_engineering_instance_id": chain.instance.pk,
            "product_bom_id": chain.bom_version.bom_id,
            "routing_id": chain.routing.pk,
            "status": "draft",
            "version": "",
        }
        return {
            field: {"expected": value, "actual": getattr(document, field)}
            for field, value in expected.items()
            if getattr(document, field) != value
        }

    @staticmethod
    def _version_mismatches(version, document, chain, facts):
        expected = {
            "document_id": document.pk,
            "document_name": facts["documentName"],
            "document_version": "V1.0",
            "release_subject_type": ManufacturingReleaseSubjectType.ORDER_ENGINEERED_PRODUCT,
            "product_version_id": None,
            "related_product_id": None,
            "order_engineering_instance_id": chain.instance.pk,
            "order_engineering_baseline_id": chain.baseline.pk,
            "engineering_calculation_id": chain.calculation.pk,
            "related_bom_id": chain.bom_version.pk,
            "related_routing_id": chain.routing_version.pk,
            "status": "draft",
        }
        return {
            field: {"expected": value, "actual": getattr(version, field)}
            for field, value in expected.items()
            if getattr(version, field) != value
        }

    @classmethod
    def _counts(cls, *, chain, document_no):
        return {
            "engineeringDocument": EngineeringDocument.objects.filter(
                document_no=document_no,
            ).count(),
            "engineeringDocumentVersion": EngineeringDocumentVersion.objects.filter(
                document__document_no=document_no,
            ).count(),
            "productManufacturingOutput": ProductManufacturingOutput.objects.filter(
                order_engineering_instance_id=chain.instance.pk,
            ).count(),
        }

    @classmethod
    def preflight(
        cls, *, user, order_no, line_no, document_no, document_name, document_type,
        baseline_id=None, calculation_id=None, bom_version_id=None, routing_version_id=None,
    ):
        facts = cls._normalized_inputs(
            document_no=document_no,
            document_name=document_name,
            document_type=document_type,
        )
        chain = cls.resolve_chain(user=user, order_no=order_no, line_no=line_no,
            baseline_id=baseline_id, calculation_id=calculation_id,
            bom_version_id=bom_version_id, routing_version_id=routing_version_id)
        decision = AuthorizationService.decide(
            user=user,
            action_code=cls.PERMISSION,
            organization_id=chain.company.pk,
            business_object={"organizationId": chain.company.pk},
        )
        if not decision.get("allowed"):
            raise OrderEngineeringDocumentRegistrationError(
                decision.get("decisionCode", "PERMISSION_DENIED"),
                decision.get("reason", "当前账户无权登记工程资料。"),
                details={"authorization": decision},
            )
        try:
            execution_chain = _actor_chain(user)
        except ProductionFoundationError as exc:
            raise OrderEngineeringDocumentRegistrationError(
                exc.code, exc.message, details=exc.details,
            ) from exc

        document = EngineeringDocument.objects.filter(
            document_no=facts["documentNo"],
        ).first()
        document_mismatches = (
            cls._document_mismatches(document, chain, facts) if document else {}
        )
        if document_mismatches:
            raise OrderEngineeringDocumentRegistrationError(
                "DOCUMENT_NUMBER_CONFLICT",
                "资料编号已被其他业务事实占用，禁止改号绕过。",
                details={"documentId": document.pk, "mismatches": document_mismatches},
            )

        version = None
        if document:
            versions = list(document.document_versions.order_by("pk")[:2])
            if len(versions) > 1:
                raise OrderEngineeringDocumentRegistrationError(
                    "FIRST_VERSION_CARDINALITY_CONFLICT",
                    "目标资料已存在多个版本，不能作为本次首版幂等对象。",
                    details={"documentId": document.pk, "versionIds": [row.pk for row in versions]},
                )
            version = versions[0] if versions else None
            version_mismatches = (
                cls._version_mismatches(version, document, chain, facts) if version else {}
            )
            if version_mismatches:
                raise OrderEngineeringDocumentRegistrationError(
                    "FIRST_VERSION_CONFLICT",
                    "既有首版与本次确认事实不一致。",
                    details={"versionId": version.pk, "mismatches": version_mismatches},
                )

        return {
            "facts": facts,
            "chainObject": chain,
            "chain": chain.as_dict(),
            "authorization": decision,
            "executionChain": execution_chain,
            "document": document,
            "version": version,
            "counts": cls._counts(chain=chain, document_no=facts["documentNo"]),
            "idempotentComplete": bool(document and version),
        }

    @classmethod
    def _source_identity(cls, *, chain, facts, entity_kind):
        identity = {
            **chain.identity,
            **facts,
            "entityKind": entity_kind,
        }
        fingerprint = sha256(json.dumps(
            identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        return {
            "sourceSystem": cls.SOURCE_SYSTEM,
            "sourceType": cls.SOURCE_TYPE,
            "sourceObjectType": cls.SOURCE_OBJECT_TYPE,
            "externalId": (
                f"{chain.order.order_no}:L{chain.sales_order_item.line_no}:"
                f"{facts['documentNo']}:{entity_kind}"
            ),
            "sourceFingerprint": fingerprint,
            "auditMetadata": {
                "channel": "OrderEngineeringDocumentRegistrationService",
                "orderNo": chain.order.order_no,
                "orderLineNo": chain.sales_order_item.line_no,
                "entityKind": entity_kind,
                "chain": chain.identity,
            },
        }

    @classmethod
    def _readback(cls, *, document, version, chain):
        return {
            "engineeringDocument": {
                "id": document.pk,
                "documentNo": document.document_no,
                "documentName": document.document_name,
                "documentType": document.document_type,
                "status": document.status,
                "versionProjection": document.version,
                "releaseSubjectType": document.release_subject_type,
                "orderEngineeringInstanceId": document.order_engineering_instance_id,
                "productBomId": document.product_bom_id,
                "routingId": document.routing_id,
            },
            "engineeringDocumentVersion": None if version is None else {
                "id": version.pk,
                "documentId": version.document_id,
                "documentName": version.document_name,
                "documentVersion": version.document_version,
                "status": version.status,
                "releaseSubjectType": version.release_subject_type,
                "orderEngineeringInstanceId": version.order_engineering_instance_id,
                "engineeringBaselineId": version.order_engineering_baseline_id,
                "engineeringCalculationId": version.engineering_calculation_id,
                "bomVersionId": version.related_bom_id,
                "routingVersionId": version.related_routing_id,
            },
            "calculationStatus": chain.calculation.status,
            "bomVersionStatus": chain.bom_version.status,
            "routingStatus": chain.routing.status,
            "routingVersionStatus": chain.routing_version.status,
            "routingStepCount": chain.routing_step_count,
            "reviewExecuted": False,
            "publicationExecuted": False,
            "manufacturingPublicationExecuted": False,
            "ecnEntered": False,
        }

    @classmethod
    def register(
        cls, *, user, order_no, line_no, document_no, document_name, document_type,
        idempotency_key, reason,
        baseline_id=None, calculation_id=None, bom_version_id=None, routing_version_id=None,
    ):
        key = str(idempotency_key or "").strip()
        if not key or len(key) > 150:
            raise OrderEngineeringDocumentRegistrationError(
                "IDEMPOTENCY_KEY_INVALID", "登记请求必须提供不超过150字符的幂等键。",
            )
        reason = str(reason or "").strip()
        if not reason:
            raise OrderEngineeringDocumentRegistrationError(
                "REGISTRATION_REASON_REQUIRED", "正式登记必须提供业务原因。",
            )

        before = cls.preflight(
            user=user, order_no=order_no, line_no=line_no,
            document_no=document_no, document_name=document_name,
            document_type=document_type,
            baseline_id=baseline_id, calculation_id=calculation_id,
            bom_version_id=bom_version_id, routing_version_id=routing_version_id,
        )
        facts = before["facts"]
        chain = before["chainObject"]
        document = before["document"]
        version = before["version"]
        document_write = None
        version_write = None

        if before["idempotentComplete"]:
            return {
                "outcome": "PASS",
                "idempotentReplay": True,
                "beforeCounts": before["counts"],
                "afterCounts": before["counts"],
                "chain": chain.as_dict(),
                "readback": cls._readback(
                    document=document, version=version, chain=chain,
                ),
                "writes": {"engineeringDocument": None, "engineeringDocumentVersion": None},
            }

        if document is None:
            try:
                document_write = ProductionFoundationService.write(
                    "engineering-documents",
                    user=user,
                    payload={
                        "document_no": facts["documentNo"],
                        "document_name": facts["documentName"],
                        "document_type": facts["documentType"],
                        "release_subject_type": ManufacturingReleaseSubjectType.ORDER_ENGINEERED_PRODUCT,
                        "order_engineering_instance_id": chain.instance.pk,
                        "product_bom_id": chain.bom_version.bom_id,
                        "routing_id": chain.routing.pk,
                        "reason": reason,
                    },
                    idempotency_key=f"{key}:document",
                    source_identity=cls._source_identity(
                        chain=chain, facts=facts, entity_kind="DOCUMENT",
                    ),
                )
            except ProductionFoundationError as exc:
                raise OrderEngineeringDocumentRegistrationError(
                    exc.code, exc.message, details=exc.details,
                ) from exc
            document = EngineeringDocument.objects.filter(
                document_no=facts["documentNo"],
            ).first()
            mismatches = (
                cls._document_mismatches(document, chain, facts) if document else {"missing": True}
            )
            if mismatches:
                raise OrderEngineeringDocumentRegistrationError(
                    "DOCUMENT_READBACK_MISMATCH",
                    "工程资料主表写入后Readback与目标链不一致。",
                    outcome="PARTIAL_WRITE" if document else "BLOCKED_BEFORE_WRITE",
                    details={"mismatches": mismatches},
                )

        refreshed_chain = cls.resolve_chain(user=user, order_no=order_no, line_no=line_no,
            baseline_id=baseline_id, calculation_id=calculation_id,
            bom_version_id=bom_version_id, routing_version_id=routing_version_id)
        if refreshed_chain.identity != chain.identity:
            raise OrderEngineeringDocumentRegistrationError(
                "CHAIN_CHANGED_AFTER_DOCUMENT_WRITE",
                "主表登记后上游链发生变化，已停止首版创建。",
                outcome="PARTIAL_WRITE",
                details={"before": chain.identity, "after": refreshed_chain.identity},
            )
        chain = refreshed_chain

        try:
            version_write = ProductionFoundationService.write(
                "engineering-document-versions",
                user=user,
                payload={
                    "document_id": document.pk,
                    "document_name": facts["documentName"],
                    # document_version is intentionally omitted: the canonical
                    # service must generate the first version as V1.0.
                    "release_subject_type": ManufacturingReleaseSubjectType.ORDER_ENGINEERED_PRODUCT,
                    "order_engineering_instance_id": chain.instance.pk,
                    "order_engineering_baseline_id": chain.baseline.pk,
                    "engineering_calculation_id": chain.calculation.pk,
                    "related_bom_id": chain.bom_version.pk,
                    "related_routing_id": chain.routing_version.pk,
                    "reason": reason,
                },
                idempotency_key=f"{key}:version",
                source_identity=cls._source_identity(
                    chain=chain, facts=facts, entity_kind="FIRST_VERSION",
                ),
            )
        except ProductionFoundationError as exc:
            version = EngineeringDocumentVersion.objects.filter(
                document=document, document_version="V1.0",
            ).first()
            if version and not cls._version_mismatches(version, document, chain, facts):
                version_write = {"idempotentReplay": True, "readbackRecovered": True}
            else:
                raise OrderEngineeringDocumentRegistrationError(
                    exc.code,
                    exc.message,
                    outcome="PARTIAL_WRITE",
                    details={
                        **exc.details,
                        "documentId": document.pk,
                        "retainedDocument": True,
                        "recoveryTheme": "repair first-version creation only; do not recreate or delete the header",
                    },
                ) from exc

        version = EngineeringDocumentVersion.objects.filter(document=document).first()
        mismatches = (
            cls._version_mismatches(version, document, chain, facts) if version else {"missing": True}
        )
        if mismatches:
            raise OrderEngineeringDocumentRegistrationError(
                "FIRST_VERSION_READBACK_MISMATCH",
                "首版写入后Readback不是目标V1.0草稿或上游绑定不一致。",
                outcome="PARTIAL_WRITE",
                details={
                    "documentId": document.pk,
                    "retainedDocument": True,
                    "mismatches": mismatches,
                },
            )

        chain.calculation.refresh_from_db()
        chain.bom_version.refresh_from_db()
        chain.routing.refresh_from_db()
        chain.routing_version.refresh_from_db()
        after_counts = cls._counts(chain=chain, document_no=facts["documentNo"])
        if after_counts["productManufacturingOutput"] != before["counts"]["productManufacturingOutput"]:
            raise OrderEngineeringDocumentRegistrationError(
                "UNAUTHORIZED_MANUFACTURING_OUTPUT_WRITE",
                "登记过程出现未经授权的制造发布记录变化。",
                outcome="PARTIAL_WRITE",
                details={"before": before["counts"], "after": after_counts},
            )

        return {
            "outcome": "PASS",
            "idempotentReplay": bool(
                (document_write or {}).get("idempotentReplay")
                and (version_write or {}).get("idempotentReplay")
            ),
            "beforeCounts": before["counts"],
            "afterCounts": after_counts,
            "chain": chain.as_dict(),
            "readback": cls._readback(document=document, version=version, chain=chain),
            "writes": {
                "engineeringDocument": None if document_write is None else {
                    "auditId": document_write.get("auditId"),
                    "sourceIdentityId": document_write.get("sourceIdentityId"),
                    "actionRequestId": document_write.get("actionRequestId"),
                    "idempotentReplay": document_write.get("idempotentReplay", False),
                },
                "engineeringDocumentVersion": None if version_write is None else {
                    "auditId": version_write.get("auditId"),
                    "sourceIdentityId": version_write.get("sourceIdentityId"),
                    "actionRequestId": version_write.get("actionRequestId"),
                    "idempotentReplay": version_write.get("idempotentReplay", False),
                },
            },
        }


__all__ = [
    "OrderEngineeringDocumentRegistrationError",
    "OrderEngineeringDocumentRegistrationService",
    "ResolvedOrderEngineeringDocumentChain",
]

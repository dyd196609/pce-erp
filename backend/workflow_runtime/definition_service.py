import hashlib
import json
import re
from threading import RLock

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import DatabaseError, IntegrityError, OperationalError, transaction
from django.db.models import Q

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from system.authorization import AuthorizationService
from system.models import OrganizationOperatingAuditRecord, Permission

from .models import ProcessDefinition, WorkflowNodeDefinition


WORKFLOW_DEFINITION_CONTRACT = "PCE-FORMAL-WORKFLOW-DEFINITION-V1.0"
WORKFLOW_CATALOG_ATOMIC_CONTRACT = "PCE-WORKFLOW-CATALOG-ATOMIC-MINIMAL-TEMPLATE-V1.0"
WORKFLOW_DEFINITION_PERMISSION = "system.organization.workflow_responsibility.manage"
ATOMIC_MINIMAL_TEMPLATE_ACTION = "CREATE_ATOMIC_MINIMAL_TEMPLATE"
ATOMIC_IDENTITY_SOURCE = "PCE_WORKFLOW_DEFINITION_CATALOG"
ATOMIC_IDENTITY_TYPE = "IDEMPOTENCY_REQUEST"
ATOMIC_IDENTITY_OBJECT = "WorkflowAtomicMinimalTemplate"
ACTION_PERMISSIONS = {
    "SAVE_PROCESS_DEFINITION": WORKFLOW_DEFINITION_PERMISSION,
    "SAVE_WORKFLOW_NODE": WORKFLOW_DEFINITION_PERMISSION,
}
CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
_CATALOG_ATOMIC_PROCESS_LOCK = RLock()


class WorkflowDefinitionError(Exception):
    def __init__(self, code, message, *, http_status=400, decision=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.decision = decision


def serialize_node(row):
    return {
        "id": row.pk,
        "processDefinitionId": row.process_definition_id,
        "nodeCode": row.node_code,
        "nodeName": row.node_name,
        "sequence": row.sequence,
        "businessActionCode": row.business_action_code,
        "active": row.active,
        "description": row.description,
    }


def serialize_definition(row, *, include_nodes=False):
    payload = {
        "id": row.pk,
        "definitionCode": row.definition_code,
        "definitionName": row.definition_name,
        "businessDomain": row.business_domain,
        "description": row.description,
        "documentType": row.document_type,
        "version": row.version,
        "active": row.active,
        "definitionHash": row.definition_hash,
        "nodeCount": row.nodes.count(),
    }
    if include_nodes:
        payload["nodes"] = [serialize_node(node) for node in row.nodes.all()]
    return payload


def _required(payload, key, label):
    value = str(payload.get(key) or "").strip()
    if not value:
        raise WorkflowDefinitionError("FIELD_REQUIRED", f"{label}不能为空。")
    return value


def _optional_id(payload, key):
    value = payload.get(key)
    if value in (None, ""):
        return None
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise WorkflowDefinitionError("INVALID_ID", f"{key}必须是有效整数。")
    if value <= 0:
        raise WorkflowDefinitionError("INVALID_ID", f"{key}必须是正整数。")
    return value


def _active(payload):
    value = payload.get("active", True)
    if not isinstance(value, bool):
        raise WorkflowDefinitionError("INVALID_ACTIVE", "active必须是布尔值。")
    return value


def _positive_integer(value, label):
    if isinstance(value, bool):
        raise WorkflowDefinitionError("INVALID_INTEGER", f"{label}必须是正整数。")
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        raise WorkflowDefinitionError("INVALID_INTEGER", f"{label}必须是正整数。")
    if normalized <= 0:
        raise WorkflowDefinitionError("INVALID_INTEGER", f"{label}必须是正整数。")
    return normalized


def _validate_code(value, label):
    if not CODE_PATTERN.fullmatch(value):
        raise WorkflowDefinitionError(
            "INVALID_CODE", f"{label}必须以大写字母开头，且只能包含大写字母、数字和下划线。"
        )


def _canonical_hash(value):
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _unsupported_fields(payload, allowed, label):
    unknown = sorted(set(payload) - set(allowed))
    if unknown:
        raise WorkflowDefinitionError(
            "UNSUPPORTED_FIELD",
            f"{label}包含不允许提交的字段：{', '.join(unknown)}。",
        )


def _normalize_atomic_minimal_template_payload(*, payload, user):
    if not isinstance(payload, dict):
        raise WorkflowDefinitionError("INVALID_PAYLOAD", "原子Template配置必须提交JSON对象。")
    _unsupported_fields(payload, {"definition", "node", "reason"}, "原子配置")
    definition_input = payload.get("definition")
    node_input = payload.get("node")
    if not isinstance(definition_input, dict) or not isinstance(node_input, dict):
        raise WorkflowDefinitionError(
            "FIELD_REQUIRED", "原子配置必须同时提交definition与唯一初始node。"
        )
    _unsupported_fields(
        definition_input,
        {
            "definitionCode", "definitionName", "businessDomain", "description",
            "documentType", "version", "active",
        },
        "definition",
    )
    _unsupported_fields(
        node_input,
        {
            "nodeCode", "nodeName", "sequence", "businessActionCode", "active",
            "description",
        },
        "node",
    )
    definition_code = _required(definition_input, "definitionCode", "流程编码").upper()
    node_code = _required(node_input, "nodeCode", "节点编码").upper()
    _validate_code(definition_code, "流程编码")
    _validate_code(node_code, "节点编码")
    definition = {
        "definitionCode": definition_code,
        "definitionName": _required(definition_input, "definitionName", "流程名称"),
        "businessDomain": _required(definition_input, "businessDomain", "业务域").upper(),
        "description": str(definition_input.get("description") or "").strip(),
        # Object type is a canonical business identity. Preserve its governed case.
        "documentType": _required(definition_input, "documentType", "单据类型"),
        "version": _positive_integer(definition_input.get("version", 1), "Definition version"),
        "active": _active(definition_input),
    }
    node = {
        "nodeCode": node_code,
        "nodeName": _required(node_input, "nodeName", "节点名称"),
        "sequence": _positive_integer(node_input.get("sequence"), "节点顺序"),
        "businessActionCode": _required(
            node_input, "businessActionCode", "业务动作编码"
        ),
        "active": _active(node_input),
        "description": str(node_input.get("description") or "").strip(),
    }
    reason = str(payload.get("reason") or "").strip()
    if len(reason) < 2:
        raise WorkflowDefinitionError("REASON_REQUIRED", "请填写本次修改原因。")
    if len(reason) > 300:
        raise WorkflowDefinitionError("INVALID_REASON", "修改原因不得超过300个字符。")

    definition_candidate = ProcessDefinition(
        definition_code=definition["definitionCode"],
        definition_name=definition["definitionName"],
        business_domain=definition["businessDomain"],
        description=definition["description"],
        document_type=definition["documentType"],
        version=definition["version"],
        active=definition["active"],
        definition_hash="",
    )
    node_candidate = WorkflowNodeDefinition(
        process_definition_id=0,
        node_code=node["nodeCode"],
        node_name=node["nodeName"],
        sequence=node["sequence"],
        business_action_code=node["businessActionCode"],
        active=node["active"],
        description=node["description"],
    )
    try:
        definition_candidate.full_clean(
            exclude=["definition_hash"], validate_unique=False, validate_constraints=False
        )
        node_candidate.full_clean(
            exclude=["process_definition"], validate_unique=False, validate_constraints=False
        )
    except ValidationError as error:
        raise WorkflowDefinitionError("PAYLOAD_VALIDATION_FAILED", str(error))

    target_identity = {
        "definitionCode": definition["definitionCode"],
        "documentType": definition["documentType"],
        "version": definition["version"],
        "active": definition["active"],
    }
    command = {
        "operationType": ATOMIC_MINIMAL_TEMPLATE_ACTION,
        "actor": {"userId": user.pk, "organizationId": user.company_id},
        "targetIdentity": target_identity,
        "definition": definition,
        "node": node,
    }
    return {
        "definition": definition,
        "node": node,
        "reason": reason,
        "targetIdentity": target_identity,
        "command": command,
        "requestHash": _canonical_hash(command),
    }


def _snapshot_definition(row):
    return serialize_definition(row, include_nodes=True) if row else {}


def _refresh_hash(row):
    fact = {
        "definitionCode": row.definition_code,
        "definitionName": row.definition_name,
        "businessDomain": row.business_domain,
        "description": row.description,
        "documentType": row.document_type,
        "version": row.version,
        "active": row.active,
        "nodes": [
            {
                "nodeCode": node.node_code,
                "nodeName": node.node_name,
                "sequence": node.sequence,
                "businessActionCode": node.business_action_code,
                "active": node.active,
                "description": node.description,
            }
            for node in row.nodes.order_by("sequence", "node_code")
        ],
    }
    row.definition_hash = hashlib.sha256(
        json.dumps(fact, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    row.save(update_fields=["definition_hash"])


class WorkflowDefinitionCatalogService:
    @staticmethod
    def authorize(user):
        decision = AuthorizationService.decide(
            user=user,
            action_code=WORKFLOW_DEFINITION_PERMISSION,
            organization_id=str(user.company_id),
        )
        if not decision["allowed"]:
            raise WorkflowDefinitionError(
                decision["decisionCode"], decision["reason"], http_status=403, decision=decision
            )
        return decision

    @classmethod
    def list(cls, *, user):
        decision = cls.authorize(user)
        rows = ProcessDefinition.objects.prefetch_related("nodes").order_by(
            "business_domain", "definition_code"
        )
        return {
            "definitions": [serialize_definition(row) for row in rows],
            "total": rows.count(),
            "authorization": decision,
        }

    @classmethod
    def detail(cls, *, user, definition_id):
        decision = cls.authorize(user)
        row = ProcessDefinition.objects.prefetch_related("nodes").filter(pk=definition_id).first()
        if not row:
            raise WorkflowDefinitionError("OBJECT_NOT_FOUND", "流程定义不存在。", http_status=404)
        return {"definition": serialize_definition(row, include_nodes=True), "authorization": decision}


class WorkflowDefinitionOperatingService:
    @classmethod
    def execute(cls, *, user, action, payload):
        action = str(action or "").strip().upper()
        payload = payload or {}
        permission_code = ACTION_PERMISSIONS.get(action)
        if not permission_code:
            raise WorkflowDefinitionError("ACTION_NOT_REGISTERED", "流程定义维护动作未注册。")
        reason = str(payload.get("reason") or "").strip()
        if len(reason) < 2:
            raise WorkflowDefinitionError("REASON_REQUIRED", "请填写本次修改原因。")
        decision = AuthorizationService.decide(
            user=user,
            action_code=permission_code,
            organization_id=str(user.company_id),
        )
        if not decision["allowed"]:
            raise WorkflowDefinitionError(
                decision["decisionCode"], decision["reason"], http_status=403, decision=decision
            )
        try:
            with transaction.atomic():
                result = getattr(cls, f"_{action.lower()}")(user=user, payload=payload, reason=reason)
        except WorkflowDefinitionError:
            raise
        except (IntegrityError, ObjectDoesNotExist, ValidationError, ValueError) as error:
            raise WorkflowDefinitionError("PERSISTENCE_VALIDATION_FAILED", str(error))
        return {
            "contractVersion": WORKFLOW_DEFINITION_CONTRACT,
            "actionCode": action,
            "requiredPermission": permission_code,
            "authorization": decision,
            **result,
        }

    @classmethod
    def configure_atomic_minimal_template(cls, *, user, payload, idempotency_key):
        """Create one definition and its first node as one idempotent command."""

        request_identity = str(idempotency_key or "").strip()
        if not request_identity:
            raise WorkflowDefinitionError(
                "IDEMPOTENCY_KEY_REQUIRED",
                "原子Template配置必须提供非空Idempotency-Key。",
            )
        if len(request_identity) > 160:
            raise WorkflowDefinitionError(
                "IDEMPOTENCY_KEY_INVALID", "Idempotency-Key不得超过160个字符。"
            )
        try:
            decision = AuthorizationService.decide(
                user=user,
                action_code=WORKFLOW_DEFINITION_PERMISSION,
                organization_id=str(user.company_id),
            )
        except DatabaseError as error:
            raise WorkflowDefinitionError(
                "CATALOG_AUTHORIZATION_DEPENDENCY_UNAVAILABLE",
                "Workflow Catalog授权依赖读取失败。",
                http_status=503,
            ) from error
        if not decision["allowed"]:
            raise WorkflowDefinitionError(
                decision["decisionCode"], decision["reason"], http_status=403, decision=decision
            )

        normalized = _normalize_atomic_minimal_template_payload(payload=payload, user=user)
        request_hash = normalized["requestHash"]
        try:
            # SQLite ignores select_for_update and may otherwise reject both
            # near-simultaneous writers. The in-process lock gives one request
            # a deterministic commit opportunity; the database row lock and
            # unique constraints remain the cross-process authority.
            with _CATALOG_ATOMIC_PROCESS_LOCK:
                core_result = cls._commit_atomic_minimal_template(
                    user=user,
                    normalized=normalized,
                    request_identity=request_identity,
                )
        except WorkflowDefinitionError:
            raise
        except IntegrityError as error:
            replay = cls._recover_committed_atomic_replay(
                user=user,
                request_identity=request_identity,
                request_hash=request_hash,
            )
            if replay:
                core_result = replay
            else:
                raise WorkflowDefinitionError(
                    "WORKFLOW_CATALOG_CONCURRENT_CONFLICT",
                    "并发Catalog请求发生唯一性竞争；本请求未提交，请使用同一Idempotency-Key安全重试。",
                    http_status=409,
                ) from error
        except OperationalError as error:
            replay = cls._recover_committed_atomic_replay(
                user=user,
                request_identity=request_identity,
                request_hash=request_hash,
                tolerate_database_error=True,
            )
            if replay:
                core_result = replay
            elif any(marker in str(error).lower() for marker in ("locked", "deadlock", "serialize")):
                raise WorkflowDefinitionError(
                    "WORKFLOW_CATALOG_CONCURRENT_REQUEST_RETRY",
                    "并发Catalog请求尚未形成可读提交；本请求未提交，请使用同一Idempotency-Key安全重试。",
                    http_status=409,
                ) from error
            else:
                raise WorkflowDefinitionError(
                    "WORKFLOW_CATALOG_DEPENDENCY_UNAVAILABLE",
                    "Workflow Catalog持久化依赖暂不可用。",
                    http_status=503,
                ) from error
        except (ObjectDoesNotExist, ValidationError, ValueError) as error:
            raise WorkflowDefinitionError("PERSISTENCE_VALIDATION_FAILED", str(error)) from error
        except DatabaseError as error:
            raise WorkflowDefinitionError(
                "WORKFLOW_CATALOG_DEPENDENCY_UNAVAILABLE",
                "Workflow Catalog持久化依赖暂不可用。",
                http_status=503,
            ) from error

        return {
            "contractVersion": WORKFLOW_CATALOG_ATOMIC_CONTRACT,
            "actionCode": ATOMIC_MINIMAL_TEMPLATE_ACTION,
            "requiredPermission": WORKFLOW_DEFINITION_PERMISSION,
            "authorization": decision,
            **core_result,
        }

    @classmethod
    def _commit_atomic_minimal_template(cls, *, user, normalized, request_identity):
        definition_data = normalized["definition"]
        node_data = normalized["node"]
        request_hash = normalized["requestHash"]
        identity_lookup = {
            "organization_id": user.company_id,
            "source_system": ATOMIC_IDENTITY_SOURCE,
            "source_type": ATOMIC_IDENTITY_TYPE,
            "source_object_type": ATOMIC_IDENTITY_OBJECT,
            "external_id": f"{user.pk}:{request_identity}",
        }
        ledger_lookup = {
            "organization_id": user.company_id,
            "action_code": ATOMIC_MINIMAL_TEMPLATE_ACTION,
            "idempotency_key": request_identity,
        }

        with transaction.atomic():
            # This existing global permission row is the catalog serialization lock.
            # It prevents two different request identities from racing past business
            # uniqueness checks without introducing a new schema object.
            maintenance_permission = Permission.objects.select_for_update().filter(
                code=WORKFLOW_DEFINITION_PERMISSION
            ).first()
            if not maintenance_permission:
                raise WorkflowDefinitionError(
                    "CATALOG_PERMISSION_DEPENDENCY_UNAVAILABLE",
                    "Workflow Catalog正式维护权限主数据不存在。",
                    http_status=503,
                )
            business_action = Permission.objects.select_for_update().filter(
                code=node_data["businessActionCode"]
            ).first()
            if not business_action:
                raise WorkflowDefinitionError(
                    "BUSINESS_ACTION_NOT_FOUND",
                    "业务动作编码未在正式权限主数据中登记，原子配置未写入。",
                    http_status=422,
                )

            ledger = MasterDataWriteRequest.objects.select_for_update().select_related(
                "source_identity"
            ).filter(**ledger_lookup).first()
            if ledger:
                return cls._atomic_replay_from_ledger(
                    ledger=ledger,
                    request_hash=request_hash,
                )

            existing_identity = ExternalIdentity.objects.select_for_update().filter(
                **identity_lookup
            ).first()
            if existing_identity:
                raise WorkflowDefinitionError(
                    "WORKFLOW_CATALOG_REQUEST_IDENTITY_CONFLICT",
                    "当前request identity已有ExternalIdentity但没有完整顶层WriteRequest；不得自动认领历史事实。",
                    http_status=409,
                )

            cls._assert_no_atomic_configuration_conflict(definition_data=definition_data)

            identity = ExternalIdentity.objects.create(
                **identity_lookup,
                target_entity_type="ProcessDefinition",
                target_entity_id="",
                mapping_status=ExternalIdentity.MappingStatus.CREATE,
                source_fingerprint=request_hash,
                audit_metadata={
                    "contractVersion": WORKFLOW_CATALOG_ATOMIC_CONTRACT,
                    "operationType": ATOMIC_MINIMAL_TEMPLATE_ACTION,
                    "requestIdentity": request_identity,
                    "payloadHash": request_hash,
                    "actorId": user.pk,
                    "organizationId": user.company_id,
                    "targetIdentity": normalized["targetIdentity"],
                },
            )
            ledger = MasterDataWriteRequest.objects.create(
                **ledger_lookup,
                entity_type="WorkflowAtomicMinimalTemplate",
                request_hash=request_hash,
                source_identity=identity,
                status=MasterDataWriteRequest.Status.RESERVED,
                target_entity_id="",
                result={},
                audit_metadata={
                    "contractVersion": WORKFLOW_CATALOG_ATOMIC_CONTRACT,
                    "actorId": user.pk,
                    "organizationId": user.company_id,
                },
            )

            definition = ProcessDefinition(
                definition_code=definition_data["definitionCode"],
                definition_name=definition_data["definitionName"],
                business_domain=definition_data["businessDomain"],
                description=definition_data["description"],
                document_type=definition_data["documentType"],
                version=definition_data["version"],
                active=definition_data["active"],
                definition_hash="",
            )
            definition.save()
            node = WorkflowNodeDefinition(
                process_definition=definition,
                node_code=node_data["nodeCode"],
                node_name=node_data["nodeName"],
                sequence=node_data["sequence"],
                business_action_code=node_data["businessActionCode"],
                active=node_data["active"],
                description=node_data["description"],
            )
            node.save()
            _refresh_hash(definition)

            definition_snapshot = serialize_definition(definition, include_nodes=True)
            node_snapshot = serialize_node(node)
            audit_snapshot = {
                "definition": definition_snapshot,
                "node": node_snapshot,
                "atomicConfiguration": {
                    "contractVersion": WORKFLOW_CATALOG_ATOMIC_CONTRACT,
                    "operationType": ATOMIC_MINIMAL_TEMPLATE_ACTION,
                    "requestIdentity": request_identity,
                    "payloadHash": request_hash,
                    "actorId": user.pk,
                    "organizationId": user.company_id,
                    "externalIdentityId": identity.pk,
                    "writeRequestId": ledger.pk,
                },
            }
            audit = cls._audit(
                user=user,
                action=ATOMIC_MINIMAL_TEMPLATE_ACTION,
                target=definition,
                target_type="ProcessDefinition",
                label=f"{definition.definition_code} - {definition.definition_name}",
                reason=normalized["reason"],
                before={},
                after=audit_snapshot,
            )

            identity.target_entity_id = str(definition.pk)
            identity.mapping_status = ExternalIdentity.MappingStatus.MATCH
            identity.audit_metadata = {
                **identity.audit_metadata,
                "definitionId": definition.pk,
                "nodeId": node.pk,
                "auditId": audit.pk,
            }
            identity.save(update_fields=[
                "target_entity_id", "mapping_status", "audit_metadata", "last_seen",
            ])

            result = {
                "requestIdentity": request_identity,
                "payloadHash": request_hash,
                "definition": definition_snapshot,
                "node": node_snapshot,
                "writeRequestId": ledger.pk,
                "externalIdentityId": identity.pk,
                "auditId": audit.pk,
                "configurationStatus": "COMMITTED",
                "idempotentReplay": False,
            }
            ledger.status = MasterDataWriteRequest.Status.COMMITTED
            ledger.target_entity_id = str(definition.pk)
            ledger.result = result
            ledger.audit_metadata = {
                **ledger.audit_metadata,
                "definitionId": definition.pk,
                "nodeId": node.pk,
                "auditId": audit.pk,
            }
            ledger.save(update_fields=[
                "status", "target_entity_id", "result", "audit_metadata", "updated_at",
            ])
            return result

    @classmethod
    def _assert_no_atomic_configuration_conflict(cls, *, definition_data):
        conflict_query = Q(definition_code=definition_data["definitionCode"])
        if definition_data["active"]:
            conflict_query |= Q(
                document_type__iexact=definition_data["documentType"], active=True
            )
        conflicts = list(
            ProcessDefinition.objects.select_for_update().prefetch_related("nodes")
            .filter(conflict_query).order_by("pk")
        )
        if not conflicts:
            return
        partial = [row for row in conflicts if row.nodes.count() == 0]
        if partial:
            raise WorkflowDefinitionError(
                "WORKFLOW_CATALOG_PARTIAL_CONFIGURATION_CONFLICT",
                "存在Definition但缺少Node的历史半配置；不得由新原子请求自动认领或补写。",
                http_status=409,
            )
        same_code = [
            row for row in conflicts
            if row.definition_code == definition_data["definitionCode"]
        ]
        if same_code:
            raise WorkflowDefinitionError(
                "WORKFLOW_CATALOG_DEFINITION_CONFLICT",
                "Definition Code已被既有完整配置占用；不同request identity不得合并历史事实。",
                http_status=409,
            )
        raise WorkflowDefinitionError(
            "WORKFLOW_CATALOG_ACTIVE_TEMPLATE_CONFLICT",
            "该canonical business object已有活动Template；不得创建重复活动Definition。",
            http_status=409,
        )

    @classmethod
    def _atomic_replay_from_ledger(cls, *, ledger, request_hash):
        if ledger.request_hash != request_hash:
            raise WorkflowDefinitionError(
                "IDEMPOTENCY_PAYLOAD_CONFLICT",
                "同一Idempotency-Key已用于不同actor、目标或规范化payload。",
                http_status=409,
            )
        if ledger.status != MasterDataWriteRequest.Status.COMMITTED:
            raise WorkflowDefinitionError(
                "WORKFLOW_CATALOG_INCOMPLETE_REQUEST_CONFLICT",
                "当前request identity没有完整已提交结果；不得自动认领部分配置。",
                http_status=409,
            )
        result = dict(ledger.result or {})
        definition_id = (result.get("definition") or {}).get("id")
        node_id = (result.get("node") or {}).get("id")
        definition = ProcessDefinition.objects.prefetch_related("nodes").filter(
            pk=definition_id
        ).first()
        node = WorkflowNodeDefinition.objects.filter(
            pk=node_id, process_definition_id=definition_id
        ).first()
        if (
            not definition
            or not node
            or str(ledger.target_entity_id) != str(definition_id)
            or str(ledger.source_identity.target_entity_id) != str(definition_id)
            or result.get("writeRequestId") != ledger.pk
            or result.get("externalIdentityId") != ledger.source_identity_id
        ):
            raise WorkflowDefinitionError(
                "WORKFLOW_CATALOG_COMMITTED_RESULT_DRIFT",
                "已提交Catalog请求的Definition、Node或账本引用不完整；拒绝伪造重放结果。",
                http_status=409,
            )
        return {**result, "idempotentReplay": True}

    @classmethod
    def _recover_committed_atomic_replay(
        cls, *, user, request_identity, request_hash, tolerate_database_error=False
    ):
        try:
            ledger = MasterDataWriteRequest.objects.select_related("source_identity").filter(
                organization_id=user.company_id,
                action_code=ATOMIC_MINIMAL_TEMPLATE_ACTION,
                idempotency_key=request_identity,
            ).first()
            if not ledger:
                return None
            return cls._atomic_replay_from_ledger(ledger=ledger, request_hash=request_hash)
        except WorkflowDefinitionError:
            raise
        except DatabaseError:
            if tolerate_database_error:
                return None
            raise

    @staticmethod
    def _audit(*, user, action, target, target_type, label, reason, before, after):
        return OrganizationOperatingAuditRecord.objects.create(
            action_code=action,
            actor=user,
            organization_id=user.company_id,
            target_type=target_type,
            target_id=target.pk,
            target_label=label,
            reason=reason,
            before_snapshot=before,
            after_snapshot=after,
        )

    @classmethod
    def _save_process_definition(cls, *, user, payload, reason):
        row_id = _optional_id(payload, "id")
        row = ProcessDefinition.objects.select_for_update().filter(pk=row_id).first() if row_id else None
        if row_id and not row:
            raise WorkflowDefinitionError("OBJECT_NOT_FOUND", "流程定义不存在。", http_status=404)
        before = _snapshot_definition(row)
        code = _required(payload, "definitionCode", "流程编码").upper()
        _validate_code(code, "流程编码")
        if row and row.definition_code != code:
            raise WorkflowDefinitionError("IMMUTABLE_CODE", "已建立流程的编码不允许修改。")
        if not row:
            row = ProcessDefinition(definition_hash="")
        row.definition_code = code
        row.definition_name = _required(payload, "definitionName", "流程名称")
        row.business_domain = _required(payload, "businessDomain", "业务域").upper()
        row.description = str(payload.get("description") or "").strip()
        row.document_type = _required(payload, "documentType", "单据类型").upper()
        try:
            row.version = int(payload.get("version") or 1)
        except (TypeError, ValueError):
            raise WorkflowDefinitionError("INVALID_VERSION", "version必须是正整数。")
        if row.version <= 0:
            raise WorkflowDefinitionError("INVALID_VERSION", "version必须是正整数。")
        row.active = _active(payload)
        row.full_clean(exclude=["definition_hash"])
        row.save()
        _refresh_hash(row)
        after = _snapshot_definition(row)
        audit = cls._audit(
            user=user, action="SAVE_PROCESS_DEFINITION", target=row,
            target_type="ProcessDefinition", label=f"{row.definition_code} - {row.definition_name}",
            reason=reason, before=before, after=after,
        )
        return {"definition": after, "auditId": audit.pk}

    @classmethod
    def _save_workflow_node(cls, *, user, payload, reason):
        row_id = _optional_id(payload, "id")
        row = WorkflowNodeDefinition.objects.select_for_update().filter(pk=row_id).first() if row_id else None
        if row_id and not row:
            raise WorkflowDefinitionError("OBJECT_NOT_FOUND", "流程节点不存在。", http_status=404)
        before = serialize_node(row) if row else {}
        definition_id = _optional_id(payload, "processDefinitionId")
        if not definition_id:
            raise WorkflowDefinitionError("FIELD_REQUIRED", "流程定义不能为空。")
        definition = ProcessDefinition.objects.select_for_update().filter(pk=definition_id).first()
        if not definition:
            raise WorkflowDefinitionError("OBJECT_NOT_FOUND", "流程定义不存在。", http_status=404)
        if row and row.process_definition_id != definition_id:
            raise WorkflowDefinitionError("IMMUTABLE_PROCESS", "节点所属流程不允许修改。")
        code = _required(payload, "nodeCode", "节点编码").upper()
        _validate_code(code, "节点编码")
        if row and row.node_code != code:
            raise WorkflowDefinitionError("IMMUTABLE_CODE", "已建立节点的编码不允许修改。")
        action_code = _required(payload, "businessActionCode", "业务动作编码")
        if not Permission.objects.filter(code=action_code).exists():
            raise WorkflowDefinitionError(
                "BUSINESS_ACTION_NOT_FOUND", "业务动作编码未在正式权限主数据中登记。"
            )
        try:
            sequence = int(payload.get("sequence"))
        except (TypeError, ValueError):
            raise WorkflowDefinitionError("INVALID_SEQUENCE", "节点顺序必须是正整数。")
        if sequence <= 0:
            raise WorkflowDefinitionError("INVALID_SEQUENCE", "节点顺序必须是正整数。")
        if not row:
            row = WorkflowNodeDefinition(process_definition=definition)
        row.node_code = code
        row.node_name = _required(payload, "nodeName", "节点名称")
        row.sequence = sequence
        row.business_action_code = action_code
        row.active = _active(payload)
        row.description = str(payload.get("description") or "").strip()
        row.full_clean()
        row.save()
        _refresh_hash(definition)
        after = serialize_node(row)
        audit = cls._audit(
            user=user, action="SAVE_WORKFLOW_NODE", target=row,
            target_type="WorkflowNodeDefinition", label=f"{definition.definition_code}/{row.node_code}",
            reason=reason, before=before, after=after,
        )
        return {
            "node": after,
            "definition": serialize_definition(definition, include_nodes=True),
            "auditId": audit.pk,
        }

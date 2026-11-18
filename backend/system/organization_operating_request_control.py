"""Request-level idempotency for formal organization operating writes.

This module deliberately reuses the shared master-data identity and write-request
tables.  It owns no business object and must only be called inside the same
``transaction.atomic`` block as the corresponding business write and audit.
"""

from dataclasses import dataclass
from hashlib import sha256
import json

from masterdata.models import ExternalIdentity, MasterDataWriteRequest


ORGANIZATION_WRITE_REQUEST_CONTRACT = (
    "PCE-ORGANIZATION-OPERATING-REQUEST-IDEMPOTENCY-V1"
)
IDEMPOTENT_ORGANIZATION_ACTIONS = frozenset({
    "SAVE_RESPONSIBILITY",
    "SAVE_POSITION_RESPONSIBILITY",
})

_ENTITY_TYPES = {
    "SAVE_RESPONSIBILITY": "Responsibility",
    "SAVE_POSITION_RESPONSIBILITY": "PositionResponsibility",
}
_SOURCE_SYSTEM = "PCE_ORGANIZATION_OPERATING"
_SOURCE_TYPE = "FORMAL_BUSINESS_COMMAND"


class OrganizationRequestControlError(Exception):
    def __init__(self, code, message, *, http_status=409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def is_idempotent_organization_action(action):
    return str(action or "").strip().upper() in IDEMPOTENT_ORGANIZATION_ACTIONS


def _text(value):
    return str(value or "").strip()


def _identifier(value):
    value = _text(value)
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def _boolean(value, default=True):
    if value in (None, ""):
        return bool(default)
    if isinstance(value, str):
        return value.strip().lower() not in {"false", "0", "no", "off"}
    return bool(value)


def normalize_organization_write_payload(*, action, payload, actor_id, organization_id):
    """Return only server-recognized business semantics in stable JSON form."""

    action = str(action or "").strip().upper()
    payload = payload or {}
    common = {
        "action": action,
        "actorId": int(actor_id),
        "actorOrganizationId": int(organization_id),
        "reason": _text(payload.get("reason")),
    }
    if action == "SAVE_RESPONSIBILITY":
        return {
            **common,
            "id": _identifier(payload.get("id")),
            "code": _text(payload.get("code")),
            "name": _text(payload.get("name")),
            "description": _text(payload.get("description")),
            "category": _text(
                payload.get("businessDomain") or payload.get("category")
            ),
            "status": _text(payload.get("status") or "DRAFT").upper(),
            "effectiveFrom": _text(payload.get("effectiveFrom")) or None,
            "effectiveTo": _text(payload.get("effectiveTo")) or None,
        }
    if action == "SAVE_POSITION_RESPONSIBILITY":
        return {
            **common,
            "id": _identifier(payload.get("id")),
            "positionId": _identifier(payload.get("positionId")),
            "responsibilityId": _identifier(payload.get("responsibilityId")),
            "isPrimary": _boolean(payload.get("isPrimary"), False),
            "active": _boolean(payload.get("active"), True),
        }
    raise OrganizationRequestControlError(
        "IDEMPOTENCY_ACTION_NOT_SUPPORTED",
        "当前组织维护动作未注册请求级幂等合同。",
        http_status=400,
    )


def organization_write_payload_hash(*, action, payload, actor_id, organization_id):
    normalized = normalize_organization_write_payload(
        action=action,
        payload=payload,
        actor_id=actor_id,
        organization_id=organization_id,
    )
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return normalized, sha256(encoded).hexdigest()


@dataclass
class OrganizationWriteRequestControl:
    action: str
    entity_type: str
    request_identity: str
    scoped_key: str
    request_hash: str
    normalized_payload: dict
    actor_id: int
    organization_id: int
    identity: ExternalIdentity
    ledger: MasterDataWriteRequest
    replay_result: dict | None = None

    @property
    def is_replay(self):
        return self.replay_result is not None

    @property
    def audit_context(self):
        return {
            "contractVersion": ORGANIZATION_WRITE_REQUEST_CONTRACT,
            "requestIdentity": self.request_identity,
            "payloadHash": self.request_hash,
            "actionCode": self.action,
            "actorId": self.actor_id,
            "organizationId": self.organization_id,
            "writeRequestId": self.ledger.pk,
            "externalIdentityId": self.identity.pk,
            "idempotentReplay": False,
        }

    def commit(self, *, result, target_entity_id, audit_id):
        """Commit the identity and ledger after business object and audit exist."""

        target_entity_id = str(target_entity_id)
        identity_metadata = {
            **self.identity.audit_metadata,
            "writeRequestId": self.ledger.pk,
            "auditId": audit_id,
            "targetEntityId": target_entity_id,
        }
        self.identity.target_entity_type = self.entity_type
        self.identity.target_entity_id = target_entity_id
        self.identity.mapping_status = ExternalIdentity.MappingStatus.MATCH
        self.identity.source_fingerprint = self.request_hash
        self.identity.audit_metadata = identity_metadata
        self.identity.full_clean()
        self.identity.save(update_fields=[
            "target_entity_type",
            "target_entity_id",
            "mapping_status",
            "source_fingerprint",
            "audit_metadata",
            "last_seen",
        ])

        self.ledger.status = MasterDataWriteRequest.Status.COMMITTED
        self.ledger.target_entity_id = target_entity_id
        self.ledger.result = result
        self.ledger.audit_metadata = {
            **self.ledger.audit_metadata,
            "auditId": audit_id,
            "externalIdentityId": self.identity.pk,
            "targetEntityId": target_entity_id,
        }
        self.ledger.save(update_fields=[
            "status",
            "target_entity_id",
            "result",
            "audit_metadata",
            "updated_at",
        ])

    @classmethod
    def prepare(cls, *, user, action, payload, request_identity):
        action = str(action or "").strip().upper()
        request_identity = str(request_identity or "").strip()
        if not request_identity:
            raise OrganizationRequestControlError(
                "IDEMPOTENCY_KEY_REQUIRED",
                "Responsibility正式维护动作必须提供Idempotency-Key。",
                http_status=400,
            )
        scoped_key = f"actor:{user.pk}:{request_identity}"
        if len(scoped_key) > MasterDataWriteRequest._meta.get_field(
            "idempotency_key"
        ).max_length:
            raise OrganizationRequestControlError(
                "IDEMPOTENCY_KEY_TOO_LONG",
                "Idempotency-Key超出正式账本允许长度。",
                http_status=400,
            )

        entity_type = _ENTITY_TYPES[action]
        normalized, request_hash = organization_write_payload_hash(
            action=action,
            payload=payload,
            actor_id=user.pk,
            organization_id=user.company_id,
        )
        ledger_lookup = {
            "organization_id": user.company_id,
            "action_code": action,
            "idempotency_key": scoped_key,
        }
        identity_lookup = {
            "organization_id": user.company_id,
            "source_system": _SOURCE_SYSTEM,
            "source_type": _SOURCE_TYPE,
            "source_object_type": action,
            "external_id": f"actor:{user.pk}:{request_identity}",
        }

        ledger = (
            MasterDataWriteRequest.objects.select_for_update()
            .select_related("source_identity")
            .filter(**ledger_lookup)
            .first()
        )
        if ledger:
            cls._validate_committed_history(
                ledger=ledger,
                identity_lookup=identity_lookup,
                entity_type=entity_type,
                request_hash=request_hash,
                actor_id=user.pk,
                organization_id=user.company_id,
                action=action,
            )
            replay_result = dict(ledger.result)
            committed_write_count = int(replay_result.get("writeCount") or 0)
            replay_result.update({
                "idempotentReplay": True,
                "writeCount": 0,
                "replayedCommittedWriteCount": committed_write_count,
            })
            return cls(
                action=action,
                entity_type=entity_type,
                request_identity=request_identity,
                scoped_key=scoped_key,
                request_hash=request_hash,
                normalized_payload=normalized,
                actor_id=user.pk,
                organization_id=user.company_id,
                identity=ledger.source_identity,
                ledger=ledger,
                replay_result=replay_result,
            )

        orphan_identity = (
            ExternalIdentity.objects.select_for_update()
            .filter(**identity_lookup)
            .first()
        )
        if orphan_identity:
            raise OrganizationRequestControlError(
                "IDEMPOTENCY_HISTORY_INCOMPLETE",
                "当前request identity存在孤立ExternalIdentity，未形成完整COMMITTED请求；禁止自动认领。",
            )

        identity = ExternalIdentity.objects.create(
            **identity_lookup,
            target_entity_type=entity_type,
            target_entity_id="",
            mapping_status=ExternalIdentity.MappingStatus.CREATE,
            source_fingerprint=request_hash,
            audit_metadata={
                "contractVersion": ORGANIZATION_WRITE_REQUEST_CONTRACT,
                "requestIdentity": request_identity,
                "payloadHash": request_hash,
                "actionCode": action,
                "actorId": user.pk,
                "organizationId": user.company_id,
            },
        )
        ledger = MasterDataWriteRequest.objects.create(
            **ledger_lookup,
            entity_type=entity_type,
            request_hash=request_hash,
            source_identity=identity,
            status=MasterDataWriteRequest.Status.RESERVED,
            target_entity_id="",
            result={},
            audit_metadata={
                "contractVersion": ORGANIZATION_WRITE_REQUEST_CONTRACT,
                "requestIdentity": request_identity,
                "payloadHash": request_hash,
                "actionCode": action,
                "actorId": user.pk,
                "organizationId": user.company_id,
            },
        )
        return cls(
            action=action,
            entity_type=entity_type,
            request_identity=request_identity,
            scoped_key=scoped_key,
            request_hash=request_hash,
            normalized_payload=normalized,
            actor_id=user.pk,
            organization_id=user.company_id,
            identity=identity,
            ledger=ledger,
        )

    @staticmethod
    def _validate_committed_history(
        *, ledger, identity_lookup, entity_type, request_hash,
        actor_id, organization_id, action,
    ):
        if ledger.request_hash != request_hash:
            raise OrganizationRequestControlError(
                "IDEMPOTENCY_PAYLOAD_CONFLICT",
                "同一Idempotency-Key已绑定不同规范化payload。",
            )
        if ledger.status != MasterDataWriteRequest.Status.COMMITTED:
            raise OrganizationRequestControlError(
                "IDEMPOTENCY_HISTORY_INCOMPLETE",
                "同一request identity存在非COMMITTED历史事实；禁止自动认领或继续写入。",
            )
        identity = ledger.source_identity
        identity_matches = all((
            identity.organization_id == identity_lookup["organization_id"],
            identity.source_system == identity_lookup["source_system"],
            identity.source_type == identity_lookup["source_type"],
            identity.source_object_type == identity_lookup["source_object_type"],
            identity.external_id == identity_lookup["external_id"],
            identity.target_entity_type == entity_type,
            identity.target_entity_id == ledger.target_entity_id,
            identity.mapping_status == ExternalIdentity.MappingStatus.MATCH,
            identity.source_fingerprint == request_hash,
        ))
        ledger_metadata = ledger.audit_metadata or {}
        identity_metadata = identity.audit_metadata or {}
        metadata_matches = all((
            ledger_metadata.get("contractVersion")
                == ORGANIZATION_WRITE_REQUEST_CONTRACT,
            identity_metadata.get("contractVersion")
                == ORGANIZATION_WRITE_REQUEST_CONTRACT,
            ledger_metadata.get("actionCode") == action,
            identity_metadata.get("actionCode") == action,
            int(ledger_metadata.get("actorId") or -1) == actor_id,
            int(identity_metadata.get("actorId") or -1) == actor_id,
            int(ledger_metadata.get("organizationId") or -1) == organization_id,
            int(identity_metadata.get("organizationId") or -1) == organization_id,
            ledger_metadata.get("payloadHash") == request_hash,
            identity_metadata.get("payloadHash") == request_hash,
        ))
        result = ledger.result
        result_matches = bool(
            isinstance(result, dict)
            and result.get("writeRequestId") == ledger.pk
            and result.get("externalIdentityId") == identity.pk
            and str(result.get("target", {}).get("id")) == ledger.target_entity_id
            and result.get("auditId")
        )
        if not identity_matches or not metadata_matches or not result_matches:
            raise OrganizationRequestControlError(
                "IDEMPOTENCY_HISTORY_INCOMPLETE",
                "COMMITTED请求的WriteRequest、ExternalIdentity、对象或Audit引用不完整；禁止重放。",
            )

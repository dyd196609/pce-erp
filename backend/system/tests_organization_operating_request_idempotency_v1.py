from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import DatabaseError, close_old_connections
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from masterdata.models import ExternalIdentity, MasterDataWriteRequest

from .models import (
    Company,
    Department,
    OrganizationOperatingAuditRecord,
    Permission,
    Position,
    PositionResponsibility,
    Responsibility,
    Role,
    RolePermission,
    User,
    UserRoleScopeAssignment,
)
from .organization_operating_request_control import (
    ORGANIZATION_WRITE_REQUEST_CONTRACT,
    organization_write_payload_hash,
)


ENDPOINT = "/api/access-control/enterprise-organization-model/"


class OrganizationRequestControlFixture:
    reason = "组织写入幂等隔离测试"

    def create_facts(self, suffix):
        self.company = Company.objects.create(
            code=f"ORG-IDEM-{suffix}", name=f"组织幂等测试公司{suffix}"
        )
        self.department = Department.objects.create(
            code=f"ORG-IDEM-DEPT-{suffix}", name="组织幂等测试部门",
            company=self.company,
        )
        self.position = Position.objects.create(
            code=f"ORG-IDEM-POS-{suffix}", name="组织幂等测试岗位",
            company=self.company, department=self.department, is_active=True,
        )
        self.permission, _ = Permission.objects.get_or_create(
            code="system.organization.responsibility.manage",
            defaults={"name": "岗位职责维护", "module": "SYSTEM"},
        )
        self.role = Role.objects.create(
            code=f"ORG_IDEM_ROLE_{suffix}", name=f"组织幂等测试角色{suffix}"
        )
        RolePermission.objects.create(role=self.role, permission=self.permission)
        self.user = User.objects.create_user(
            username=f"org_idem_user_{suffix}", password=None,
            company_id=self.company.pk,
        )
        UserRoleScopeAssignment.objects.create(
            user=self.user, role=self.role, organization=self.company,
            scope_code="ORGANIZATION", active=True,
            business_hash=f"org-idem-{suffix}",
        )
        self.denied = User.objects.create_user(
            username=f"org_idem_denied_{suffix}", password=None,
            company_id=self.company.pk,
        )

    def post(self, action, payload, *, key, user=None):
        client = APIClient()
        client.force_authenticate(user=user or self.user)
        kwargs = {"HTTP_IDEMPOTENCY_KEY": key} if key is not None else {}
        return client.post(
            ENDPOINT,
            {"action": action, "payload": {"reason": self.reason, **payload}},
            format="json",
            **kwargs,
        )

    def draft_payload(self, code="GENERIC_CATALOG_RESPONSIBILITY"):
        return {
            "code": code,
            "name": "通用目录维护责任",
            "description": "仅存在于隔离测试数据库",
            "businessDomain": "SYSTEM_GOVERNANCE",
            "status": "DRAFT",
        }

    def create_draft(self, *, code="GENERIC_CATALOG_RESPONSIBILITY", key="draft-key"):
        payload = self.draft_payload(code)
        response = self.post("SAVE_RESPONSIBILITY", payload, key=key)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["data"]["target"]["id"], payload

    def activate(self, responsibility_id, *, code="GENERIC_CATALOG_RESPONSIBILITY", key="activate-key"):
        payload = {
            "id": responsibility_id,
            "code": code,
            "name": "通用目录维护责任",
            "description": "仅存在于隔离测试数据库",
            "businessDomain": "SYSTEM_GOVERNANCE",
            "status": "ACTIVE",
            "effectiveFrom": "2026-10-07",
        }
        response = self.post("SAVE_RESPONSIBILITY", payload, key=key)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["data"]


class OrganizationOperatingRequestIdempotencyV1Tests(
    OrganizationRequestControlFixture, TestCase
):
    def setUp(self):
        self.create_facts(self._testMethodName[-12:])

    def target_counts(self):
        return {
            "responsibility": Responsibility.objects.count(),
            "positionResponsibility": PositionResponsibility.objects.count(),
            "audit": OrganizationOperatingAuditRecord.objects.count(),
            "identity": ExternalIdentity.objects.filter(
                source_system="PCE_ORGANIZATION_OPERATING"
            ).count(),
            "request": MasterDataWriteRequest.objects.filter(
                audit_metadata__contractVersion=ORGANIZATION_WRITE_REQUEST_CONTRACT
            ).count(),
        }

    def test_01_missing_key_fails_before_write(self):
        response = self.post(
            "SAVE_RESPONSIBILITY", self.draft_payload(), key=None,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "IDEMPOTENCY_KEY_REQUIRED")
        self.assertEqual(self.target_counts(), {
            "responsibility": 0, "positionResponsibility": 0, "audit": 0,
            "identity": 0, "request": 0,
        })

    def test_02_first_responsibility_commit_has_one_ledger_identity_and_audit(self):
        responsibility_id, _ = self.create_draft(key="responsibility-first")
        data = MasterDataWriteRequest.objects.get().result
        ledger = MasterDataWriteRequest.objects.get()
        identity = ExternalIdentity.objects.get(
            source_system="PCE_ORGANIZATION_OPERATING"
        )
        audit = OrganizationOperatingAuditRecord.objects.get()
        self.assertEqual(ledger.status, MasterDataWriteRequest.Status.COMMITTED)
        self.assertEqual(ledger.target_entity_id, str(responsibility_id))
        self.assertEqual(identity.mapping_status, ExternalIdentity.MappingStatus.MATCH)
        self.assertEqual(identity.target_entity_id, str(responsibility_id))
        self.assertEqual(data["auditId"], audit.pk)
        self.assertEqual(audit.after_snapshot["requestControl"]["requestIdentity"], "responsibility-first")
        self.assertEqual(self.target_counts()["responsibility"], 1)

    def test_03_same_key_same_payload_replays_without_any_write(self):
        payload = self.draft_payload()
        first = self.post("SAVE_RESPONSIBILITY", payload, key="safe-replay")
        counts = self.target_counts()
        replay = self.post("SAVE_RESPONSIBILITY", dict(reversed(list(payload.items()))), key="safe-replay")
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(replay.status_code, 200, replay.content)
        replay_data = replay.json()["data"]
        self.assertTrue(replay_data["idempotentReplay"])
        self.assertEqual(replay_data["writeCount"], 0)
        self.assertEqual(replay_data["target"]["id"], first.json()["data"]["target"]["id"])
        self.assertEqual(self.target_counts(), counts)

    def test_04_same_key_different_payload_returns_409(self):
        payload = self.draft_payload()
        self.post("SAVE_RESPONSIBILITY", payload, key="payload-conflict")
        counts = self.target_counts()
        response = self.post(
            "SAVE_RESPONSIBILITY", {**payload, "name": "另一项责任"},
            key="payload-conflict",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "IDEMPOTENCY_PAYLOAD_CONFLICT")
        self.assertEqual(self.target_counts(), counts)

    def test_05_network_unknown_retry_recovers_first_committed_result(self):
        payload = self.draft_payload()
        committed = self.post("SAVE_RESPONSIBILITY", payload, key="network-recovery")
        counts = self.target_counts()
        recovered = self.post("SAVE_RESPONSIBILITY", payload, key="network-recovery")
        self.assertEqual(recovered.status_code, 200, recovered.content)
        self.assertTrue(recovered.json()["data"]["idempotentReplay"])
        self.assertEqual(
            recovered.json()["data"]["auditId"], committed.json()["data"]["auditId"]
        )
        self.assertEqual(self.target_counts(), counts)

    def test_06_whitespace_and_display_fields_do_not_change_payload_hash(self):
        payload = self.draft_payload()
        first = self.post(
            "SAVE_RESPONSIBILITY",
            {**payload, "name": "  通用目录维护责任  ", "displayLabel": "首次显示"},
            key="canonical-payload",
        )
        replay = self.post(
            "SAVE_RESPONSIBILITY",
            {**payload, "displayLabel": "另一个显示文本"},
            key="canonical-payload",
        )
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(replay.status_code, 200, replay.content)
        self.assertTrue(replay.json()["data"]["idempotentReplay"])

    def test_07_same_text_key_isolated_by_action(self):
        responsibility_id, _ = self.create_draft(key="same-text-key")
        self.activate(responsibility_id, key="activate-for-relation")
        response = self.post("SAVE_POSITION_RESPONSIBILITY", {
            "positionId": self.position.pk,
            "responsibilityId": responsibility_id,
            "isPrimary": True,
            "active": True,
        }, key="same-text-key")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(MasterDataWriteRequest.objects.filter(
            idempotency_key=f"actor:{self.user.pk}:same-text-key"
        ).count(), 2)

    def test_08_reserved_history_fails_closed(self):
        payload = {"reason": self.reason, **self.draft_payload()}
        _, request_hash = organization_write_payload_hash(
            action="SAVE_RESPONSIBILITY", payload=payload,
            actor_id=self.user.pk, organization_id=self.company.pk,
        )
        identity = ExternalIdentity.objects.create(
            organization_id=self.company.pk,
            source_system="PCE_ORGANIZATION_OPERATING",
            source_type="FORMAL_BUSINESS_COMMAND",
            source_object_type="SAVE_RESPONSIBILITY",
            external_id=f"actor:{self.user.pk}:reserved-history",
            target_entity_type="Responsibility",
            mapping_status=ExternalIdentity.MappingStatus.CREATE,
            source_fingerprint=request_hash,
            audit_metadata={
                "contractVersion": ORGANIZATION_WRITE_REQUEST_CONTRACT,
                "requestIdentity": "reserved-history", "payloadHash": request_hash,
                "actionCode": "SAVE_RESPONSIBILITY", "actorId": self.user.pk,
                "organizationId": self.company.pk,
            },
        )
        MasterDataWriteRequest.objects.create(
            organization_id=self.company.pk,
            action_code="SAVE_RESPONSIBILITY",
            entity_type="Responsibility",
            idempotency_key=f"actor:{self.user.pk}:reserved-history",
            request_hash=request_hash,
            source_identity=identity,
            status=MasterDataWriteRequest.Status.RESERVED,
            audit_metadata=identity.audit_metadata,
        )
        response = self.post(
            "SAVE_RESPONSIBILITY", self.draft_payload(), key="reserved-history"
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "IDEMPOTENCY_HISTORY_INCOMPLETE")
        self.assertEqual(Responsibility.objects.count(), 0)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 0)

    def test_09_orphan_external_identity_fails_closed(self):
        ExternalIdentity.objects.create(
            organization_id=self.company.pk,
            source_system="PCE_ORGANIZATION_OPERATING",
            source_type="FORMAL_BUSINESS_COMMAND",
            source_object_type="SAVE_RESPONSIBILITY",
            external_id=f"actor:{self.user.pk}:orphan-history",
            target_entity_type="Responsibility",
            mapping_status=ExternalIdentity.MappingStatus.CREATE,
        )
        response = self.post(
            "SAVE_RESPONSIBILITY", self.draft_payload(), key="orphan-history"
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "IDEMPOTENCY_HISTORY_INCOMPLETE")
        self.assertEqual(Responsibility.objects.count(), 0)

    def test_10_permission_failure_has_zero_business_and_ledger_writes(self):
        response = self.post(
            "SAVE_RESPONSIBILITY", self.draft_payload(), key="denied",
            user=self.denied,
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.target_counts(), {
            "responsibility": 0, "positionResponsibility": 0, "audit": 0,
            "identity": 0, "request": 0,
        })

    def test_11_illegal_initial_state_rolls_back_reserved_facts(self):
        response = self.post(
            "SAVE_RESPONSIBILITY",
            {**self.draft_payload(), "status": "ACTIVE", "effectiveFrom": "2026-10-07"},
            key="illegal-state",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "RESPONSIBILITY_MUST_START_DRAFT")
        self.assertEqual(self.target_counts(), {
            "responsibility": 0, "positionResponsibility": 0, "audit": 0,
            "identity": 0, "request": 0,
        })

    def test_12_audit_failure_rolls_back_object_identity_and_ledger(self):
        with patch(
            "system.organization_operating.OrganizationOperatingAuditRecord.objects.create",
            side_effect=DatabaseError("isolated audit failure"),
        ):
            response = self.post(
                "SAVE_RESPONSIBILITY", self.draft_payload(), key="audit-failure"
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.target_counts(), {
            "responsibility": 0, "positionResponsibility": 0, "audit": 0,
            "identity": 0, "request": 0,
        })

    def test_13_write_request_failure_rolls_back_identity(self):
        with patch(
            "system.organization_operating_request_control.MasterDataWriteRequest.objects.create",
            side_effect=DatabaseError("isolated ledger failure"),
        ):
            response = self.post(
                "SAVE_RESPONSIBILITY", self.draft_payload(), key="ledger-failure"
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.target_counts(), {
            "responsibility": 0, "positionResponsibility": 0, "audit": 0,
            "identity": 0, "request": 0,
        })

    def test_14_lifecycle_actions_use_independent_committed_requests(self):
        responsibility_id, _ = self.create_draft(key="lifecycle-create")
        activated = self.activate(responsibility_id, key="lifecycle-activate")
        self.assertEqual(activated["target"]["status"], Responsibility.Status.ACTIVE)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.filter(
            action_code="SAVE_RESPONSIBILITY"
        ).count(), 2)
        self.assertEqual(MasterDataWriteRequest.objects.filter(
            action_code="SAVE_RESPONSIBILITY",
            status=MasterDataWriteRequest.Status.COMMITTED,
        ).count(), 2)

    def test_15_different_key_same_responsibility_code_is_409(self):
        self.create_draft(key="business-key-one")
        counts = self.target_counts()
        response = self.post(
            "SAVE_RESPONSIBILITY", self.draft_payload(), key="business-key-two"
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "RESPONSIBILITY_CODE_CONFLICT")
        self.assertEqual(self.target_counts(), counts)

    def active_responsibility(self):
        responsibility_id, _ = self.create_draft(key="relation-source-create")
        self.activate(responsibility_id, key="relation-source-activate")
        return responsibility_id

    def relation_payload(self, responsibility_id):
        return {
            "positionId": self.position.pk,
            "responsibilityId": responsibility_id,
            "isPrimary": True,
            "active": True,
        }

    def test_16_first_position_responsibility_commit_has_companion_facts(self):
        responsibility_id = self.active_responsibility()
        before = self.target_counts()
        response = self.post(
            "SAVE_POSITION_RESPONSIBILITY", self.relation_payload(responsibility_id),
            key="relation-first",
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        self.assertFalse(data["idempotentReplay"])
        self.assertEqual(PositionResponsibility.objects.count(), 1)
        self.assertEqual(self.target_counts()["audit"], before["audit"] + 1)
        self.assertEqual(self.target_counts()["identity"], before["identity"] + 1)
        self.assertEqual(self.target_counts()["request"], before["request"] + 1)

    def test_17_position_responsibility_same_key_replays(self):
        responsibility_id = self.active_responsibility()
        payload = self.relation_payload(responsibility_id)
        first = self.post("SAVE_POSITION_RESPONSIBILITY", payload, key="relation-replay")
        counts = self.target_counts()
        replay = self.post("SAVE_POSITION_RESPONSIBILITY", payload, key="relation-replay")
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(replay.status_code, 200, replay.content)
        self.assertTrue(replay.json()["data"]["idempotentReplay"])
        self.assertEqual(replay.json()["data"]["writeCount"], 0)
        self.assertEqual(self.target_counts(), counts)

    def test_18_position_responsibility_same_key_payload_conflict_is_409(self):
        responsibility_id = self.active_responsibility()
        payload = self.relation_payload(responsibility_id)
        self.post("SAVE_POSITION_RESPONSIBILITY", payload, key="relation-conflict")
        counts = self.target_counts()
        response = self.post(
            "SAVE_POSITION_RESPONSIBILITY", {**payload, "isPrimary": False},
            key="relation-conflict",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "IDEMPOTENCY_PAYLOAD_CONFLICT")
        self.assertEqual(self.target_counts(), counts)

    def test_19_different_key_same_relation_is_409_without_second_audit(self):
        responsibility_id = self.active_responsibility()
        payload = self.relation_payload(responsibility_id)
        self.post("SAVE_POSITION_RESPONSIBILITY", payload, key="relation-one")
        counts = self.target_counts()
        response = self.post("SAVE_POSITION_RESPONSIBILITY", payload, key="relation-two")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "POSITION_RESPONSIBILITY_CONFLICT")
        self.assertEqual(self.target_counts(), counts)

    def test_20_missing_position_rolls_back_request_control(self):
        responsibility_id = self.active_responsibility()
        before = self.target_counts()
        response = self.post("SAVE_POSITION_RESPONSIBILITY", {
            **self.relation_payload(responsibility_id), "positionId": 999999,
        }, key="missing-position")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.target_counts(), before)

    def test_21_missing_responsibility_rolls_back_request_control(self):
        before = self.target_counts()
        response = self.post("SAVE_POSITION_RESPONSIBILITY", {
            "positionId": self.position.pk, "responsibilityId": 999999,
            "isPrimary": True, "active": True,
        }, key="missing-responsibility")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.target_counts(), before)

    def test_22_inactive_responsibility_cannot_be_assigned(self):
        responsibility_id, _ = self.create_draft(key="inactive-source")
        before = self.target_counts()
        response = self.post(
            "SAVE_POSITION_RESPONSIBILITY", self.relation_payload(responsibility_id),
            key="inactive-relation",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "RESPONSIBILITY_INACTIVE")
        self.assertEqual(self.target_counts(), before)

    def test_23_existing_relation_can_only_be_updated_by_explicit_relation_id(self):
        responsibility_id = self.active_responsibility()
        created = self.post(
            "SAVE_POSITION_RESPONSIBILITY", self.relation_payload(responsibility_id),
            key="relation-create-for-update",
        ).json()["data"]
        response = self.post("SAVE_POSITION_RESPONSIBILITY", {
            **self.relation_payload(responsibility_id),
            "id": created["target"]["id"], "isPrimary": False,
        }, key="relation-update")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(PositionResponsibility.objects.get().is_primary)

    def test_24_self_scope_does_not_gain_global_responsibility_write(self):
        self_scope_user = User.objects.create_user(
            username=f"self_scope_{self.user.pk}", password=None,
            company_id=self.company.pk,
        )
        UserRoleScopeAssignment.objects.create(
            user=self_scope_user, role=self.role, organization=self.company,
            scope_code="SELF", active=True, business_hash="self-scope",
        )
        response = self.post(
            "SAVE_RESPONSIBILITY", self.draft_payload(), key="self-scope-denied",
            user=self_scope_user,
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "SCOPE_DENIED")
        self.assertEqual(Responsibility.objects.count(), 0)
        self.assertFalse(MasterDataWriteRequest.objects.filter(
            idempotency_key=f"actor:{self_scope_user.pk}:self-scope-denied"
        ).exists())

    def test_25_same_text_key_from_another_actor_is_not_a_replay(self):
        self.create_draft(key="actor-scoped-key")
        second_user = User.objects.create_user(
            username=f"second_actor_{self.user.pk}", password=None,
            company_id=self.company.pk,
        )
        UserRoleScopeAssignment.objects.create(
            user=second_user, role=self.role, organization=self.company,
            scope_code="ORGANIZATION", active=True, business_hash="second-actor",
        )
        response = self.post(
            "SAVE_RESPONSIBILITY", self.draft_payload(), key="actor-scoped-key",
            user=second_user,
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "RESPONSIBILITY_CODE_CONFLICT")
        self.assertEqual(Responsibility.objects.count(), 1)


class OrganizationOperatingRequestConcurrencyV1Tests(
    OrganizationRequestControlFixture, TransactionTestCase
):
    reset_sequences = True

    def setUp(self):
        self.create_facts("CONCURRENT")

    def threaded_post(self, barrier, *, key):
        close_old_connections()
        client = APIClient()
        client.force_authenticate(user=self.user)
        barrier.wait(timeout=10)
        response = client.post(
            ENDPOINT,
            {
                "action": "SAVE_RESPONSIBILITY",
                "payload": {"reason": self.reason, **self.draft_payload()},
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        result = (response.status_code, response.json())
        close_old_connections()
        return result

    def test_26_concurrent_same_key_commits_once_and_replays(self):
        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(self.threaded_post, barrier, key="concurrent-same")
                for _ in range(2)
            ]
            results = [future.result(timeout=20) for future in futures]
        self.assertEqual([status for status, _ in results], [200, 200])
        self.assertEqual(Responsibility.objects.count(), 1)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 1)
        self.assertEqual(ExternalIdentity.objects.filter(
            source_system="PCE_ORGANIZATION_OPERATING"
        ).count(), 1)
        self.assertEqual(MasterDataWriteRequest.objects.filter(
            action_code="SAVE_RESPONSIBILITY"
        ).count(), 1)
        self.assertEqual(sum(
            bool(body["data"]["idempotentReplay"]) for _, body in results
        ), 1)

    def test_27_concurrent_different_keys_same_code_has_one_409(self):
        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(self.threaded_post, barrier, key=key)
                for key in ("concurrent-one", "concurrent-two")
            ]
            results = [future.result(timeout=20) for future in futures]
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        self.assertEqual(Responsibility.objects.count(), 1)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.count(), 1)
        self.assertEqual(ExternalIdentity.objects.filter(
            source_system="PCE_ORGANIZATION_OPERATING"
        ).count(), 1)
        self.assertEqual(MasterDataWriteRequest.objects.filter(
            action_code="SAVE_RESPONSIBILITY"
        ).count(), 1)

    def threaded_relation_post(self, barrier, *, key, responsibility_id):
        close_old_connections()
        client = APIClient()
        client.force_authenticate(user=self.user)
        barrier.wait(timeout=10)
        response = client.post(
            ENDPOINT,
            {
                "action": "SAVE_POSITION_RESPONSIBILITY",
                "payload": {
                    "reason": self.reason,
                    "positionId": self.position.pk,
                    "responsibilityId": responsibility_id,
                    "isPrimary": True,
                    "active": True,
                },
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        result = (response.status_code, response.json())
        close_old_connections()
        return result

    def test_28_concurrent_different_keys_same_relation_has_one_409(self):
        responsibility_id, _ = self.create_draft(key="concurrent-relation-source")
        self.activate(
            responsibility_id,
            key="concurrent-relation-source-activate",
        )
        audit_before = OrganizationOperatingAuditRecord.objects.count()
        identity_before = ExternalIdentity.objects.filter(
            source_system="PCE_ORGANIZATION_OPERATING"
        ).count()
        request_before = MasterDataWriteRequest.objects.filter(
            audit_metadata__contractVersion=ORGANIZATION_WRITE_REQUEST_CONTRACT
        ).count()
        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(
                    self.threaded_relation_post,
                    barrier,
                    key=key,
                    responsibility_id=responsibility_id,
                )
                for key in ("concurrent-relation-one", "concurrent-relation-two")
            ]
            results = [future.result(timeout=20) for future in futures]
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        self.assertEqual(PositionResponsibility.objects.count(), 1)
        self.assertEqual(
            OrganizationOperatingAuditRecord.objects.count(), audit_before + 1
        )
        self.assertEqual(ExternalIdentity.objects.filter(
            source_system="PCE_ORGANIZATION_OPERATING"
        ).count(), identity_before + 1)
        self.assertEqual(MasterDataWriteRequest.objects.filter(
            audit_metadata__contractVersion=ORGANIZATION_WRITE_REQUEST_CONTRACT
        ).count(), request_before + 1)

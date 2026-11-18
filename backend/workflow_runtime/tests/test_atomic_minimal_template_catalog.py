import copy
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from system.models import Company, OrganizationOperatingAuditRecord, Permission, User
from workflow_runtime.definition_service import (
    ATOMIC_MINIMAL_TEMPLATE_ACTION,
    WORKFLOW_CATALOG_ATOMIC_CONTRACT,
    WORKFLOW_DEFINITION_PERMISSION,
    WorkflowDefinitionError,
    WorkflowDefinitionOperatingService,
)
from workflow_runtime.models import ProcessDefinition, WorkflowNodeDefinition


class AtomicMinimalTemplateCatalogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            id=991, code="ATC", name="原子Catalog测试公司"
        )
        cls.admin = User.objects.create_superuser(
            username="atomic-catalog-admin",
            password="secret",
            real_name="原子Catalog管理员",
            company_id=cls.company.pk,
        )
        Permission.objects.get_or_create(
            code=WORKFLOW_DEFINITION_PERMISSION,
            defaults={"name": "岗位流程责任维护", "module": "SYSTEM"},
        )
        Permission.objects.get_or_create(
            code="catalog.atomic.action",
            defaults={"name": "原子Catalog测试动作", "module": "WORKFLOW"},
        )
        Permission.objects.get_or_create(
            code="catalog.atomic.alternative",
            defaults={"name": "原子Catalog替代动作", "module": "WORKFLOW"},
        )

    def payload(self, **definition_overrides):
        definition = {
            "definitionCode": "ATOMIC_MINIMAL_FLOW",
            "definitionName": "原子最小流程",
            "businessDomain": "PDE",
            "description": "一次请求创建流程和首节点",
            "documentType": "AtomicCatalogObject",
            "version": 1,
            "active": True,
            **definition_overrides,
        }
        return {
            "definition": definition,
            "node": {
                "nodeCode": "FORMAL_REVIEW",
                "nodeName": "正式评审",
                "sequence": 1,
                "businessActionCode": "catalog.atomic.action",
                "active": True,
                "description": "唯一初始节点",
            },
            "reason": "验证原子最小Template配置",
        }

    @staticmethod
    def counts():
        return {
            "definitions": ProcessDefinition.objects.count(),
            "nodes": WorkflowNodeDefinition.objects.count(),
            "identities": ExternalIdentity.objects.count(),
            "requests": MasterDataWriteRequest.objects.count(),
            "audits": OrganizationOperatingAuditRecord.objects.count(),
        }

    def execute(self, key="atomic-key-1", payload=None):
        return WorkflowDefinitionOperatingService.configure_atomic_minimal_template(
            user=self.admin,
            payload=payload or self.payload(),
            idempotency_key=key,
        )

    def assert_zero_delta(self, before):
        self.assertEqual(self.counts(), before)

    def test_atomic_success_writes_exactly_one_complete_top_level_command(self):
        before = self.counts()
        result = self.execute()

        after = self.counts()
        self.assertEqual(after["definitions"], before["definitions"] + 1)
        self.assertEqual(after["nodes"], before["nodes"] + 1)
        self.assertEqual(after["identities"], before["identities"] + 1)
        self.assertEqual(after["requests"], before["requests"] + 1)
        self.assertEqual(after["audits"], before["audits"] + 1)
        self.assertEqual(result["contractVersion"], WORKFLOW_CATALOG_ATOMIC_CONTRACT)
        self.assertEqual(result["actionCode"], ATOMIC_MINIMAL_TEMPLATE_ACTION)
        self.assertFalse(result["idempotentReplay"])
        self.assertEqual(result["definition"]["nodeCount"], 1)
        self.assertEqual(result["definition"]["nodes"][0]["id"], result["node"]["id"])
        self.assertEqual(len(result["definition"]["definitionHash"]), 64)

        ledger = MasterDataWriteRequest.objects.get(pk=result["writeRequestId"])
        identity = ExternalIdentity.objects.get(pk=result["externalIdentityId"])
        audit = OrganizationOperatingAuditRecord.objects.get(pk=result["auditId"])
        self.assertEqual(ledger.status, MasterDataWriteRequest.Status.COMMITTED)
        self.assertEqual(ledger.action_code, ATOMIC_MINIMAL_TEMPLATE_ACTION)
        self.assertEqual(ledger.request_hash, result["payloadHash"])
        self.assertEqual(identity.mapping_status, ExternalIdentity.MappingStatus.MATCH)
        self.assertEqual(identity.target_entity_id, str(result["definition"]["id"]))
        self.assertEqual(audit.action_code, ATOMIC_MINIMAL_TEMPLATE_ACTION)
        self.assertEqual(
            audit.after_snapshot["atomicConfiguration"]["requestIdentity"],
            "atomic-key-1",
        )
        self.assertEqual(
            audit.after_snapshot["atomicConfiguration"]["organizationId"],
            self.company.pk,
        )

    def test_same_key_same_normalized_payload_is_safe_replay_without_writes(self):
        first = self.execute(key="stable-order-key")
        after_first = self.counts()
        reordered = {
            "reason": "不同重试说明不会改变配置语义",
            "node": {
                "description": "  唯一初始节点  ",
                "active": True,
                "businessActionCode": "catalog.atomic.action",
                "sequence": 1,
                "nodeName": " 正式评审 ",
                "nodeCode": "formal_review",
            },
            "definition": {
                "active": True,
                "version": 1,
                "documentType": " AtomicCatalogObject ",
                "description": " 一次请求创建流程和首节点 ",
                "businessDomain": "pde",
                "definitionName": " 原子最小流程 ",
                "definitionCode": "atomic_minimal_flow",
            },
        }
        replay = self.execute(key="stable-order-key", payload=reordered)

        self.assertTrue(replay["idempotentReplay"])
        self.assertEqual(replay["definition"]["id"], first["definition"]["id"])
        self.assertEqual(replay["node"]["id"], first["node"]["id"])
        self.assertEqual(replay["writeRequestId"], first["writeRequestId"])
        self.assertEqual(replay["externalIdentityId"], first["externalIdentityId"])
        self.assertEqual(replay["auditId"], first["auditId"])
        self.assertEqual(self.counts(), after_first)

    def test_payload_hash_covers_every_formal_configuration_field(self):
        self.execute(key="field-coverage-key")
        after_first = self.counts()
        mutations = (
            ("definition", "definitionCode", "ATOMIC_MINIMAL_FLOW_CHANGED"),
            ("definition", "definitionName", "不同流程名称"),
            ("definition", "businessDomain", "SCM"),
            ("definition", "description", "不同流程说明"),
            ("definition", "documentType", "DifferentObject"),
            ("definition", "version", 2),
            ("definition", "active", False),
            ("node", "nodeCode", "SECOND_REVIEW"),
            ("node", "nodeName", "不同节点名称"),
            ("node", "sequence", 2),
            ("node", "businessActionCode", "catalog.atomic.alternative"),
            ("node", "active", False),
            ("node", "description", "不同节点说明"),
        )
        for section, field, value in mutations:
            with self.subTest(section=section, field=field):
                changed = copy.deepcopy(self.payload())
                changed[section][field] = value
                with self.assertRaises(WorkflowDefinitionError) as caught:
                    self.execute(key="field-coverage-key", payload=changed)
                self.assertEqual(caught.exception.code, "IDEMPOTENCY_PAYLOAD_CONFLICT")
                self.assertEqual(caught.exception.http_status, 409)
                self.assertEqual(self.counts(), after_first)

    def test_request_identity_is_bound_to_current_actor(self):
        self.execute(key="actor-bound-key")
        after_first = self.counts()
        other_admin = User.objects.create_superuser(
            username="other-atomic-admin",
            password="secret",
            real_name="另一名Catalog管理员",
            company_id=self.company.pk,
        )
        with self.assertRaises(WorkflowDefinitionError) as caught:
            WorkflowDefinitionOperatingService.configure_atomic_minimal_template(
                user=other_admin,
                payload=self.payload(),
                idempotency_key="actor-bound-key",
            )
        self.assertEqual(caught.exception.code, "IDEMPOTENCY_PAYLOAD_CONFLICT")
        self.assertEqual(caught.exception.http_status, 409)
        self.assertEqual(self.counts(), after_first)

    def test_node_save_failure_rolls_back_definition_ledgers_and_audit(self):
        before = self.counts()
        with patch.object(
            WorkflowNodeDefinition,
            "save",
            side_effect=ValidationError("simulated node persistence failure"),
        ):
            with self.assertRaises(WorkflowDefinitionError):
                self.execute(key="node-failure-key")
        self.assert_zero_delta(before)

    def test_node_uniqueness_conflict_rolls_back_every_atomic_object(self):
        before = self.counts()
        with patch.object(
            WorkflowNodeDefinition,
            "save",
            side_effect=IntegrityError("uniq_workflow_definition_node_code"),
        ):
            with self.assertRaises(WorkflowDefinitionError) as caught:
                self.execute(key="node-unique-conflict-key")
        self.assertEqual(caught.exception.code, "WORKFLOW_CATALOG_CONCURRENT_CONFLICT")
        self.assertEqual(caught.exception.http_status, 409)
        self.assert_zero_delta(before)

    def test_audit_failure_rolls_back_definition_node_and_ledgers(self):
        before = self.counts()
        with patch(
            "workflow_runtime.definition_service.OrganizationOperatingAuditRecord.objects.create",
            side_effect=ValidationError("simulated audit failure"),
        ):
            with self.assertRaises(WorkflowDefinitionError):
                self.execute(key="audit-failure-key")
        self.assert_zero_delta(before)

    def test_illegal_business_action_is_rejected_before_first_write(self):
        payload = self.payload()
        payload["node"]["businessActionCode"] = "catalog.action.does_not_exist"
        before = self.counts()
        with self.assertRaises(WorkflowDefinitionError) as caught:
            self.execute(key="missing-action-key", payload=payload)
        self.assertEqual(caught.exception.code, "BUSINESS_ACTION_NOT_FOUND")
        self.assertEqual(caught.exception.http_status, 422)
        self.assert_zero_delta(before)

    def test_definition_and_active_object_conflicts_are_zero_write(self):
        existing = ProcessDefinition.objects.create(
            definition_code="EXISTING_ATOMIC_FLOW",
            definition_name="既有完整流程",
            business_domain="PDE",
            description="",
            document_type="ExistingAtomicObject",
            version=1,
            active=True,
            definition_hash="0" * 64,
        )
        WorkflowNodeDefinition.objects.create(
            process_definition=existing,
            node_code="REVIEW",
            node_name="评审",
            sequence=1,
            business_action_code="catalog.atomic.action",
            active=True,
        )
        cases = (
            self.payload(
                definitionCode="EXISTING_ATOMIC_FLOW",
                documentType="OtherAtomicObject",
            ),
            self.payload(
                definitionCode="DIFFERENT_ATOMIC_FLOW",
                documentType="ExistingAtomicObject",
            ),
        )
        for index, payload in enumerate(cases):
            with self.subTest(index=index):
                before = self.counts()
                with self.assertRaises(WorkflowDefinitionError) as caught:
                    self.execute(key=f"definition-conflict-{index}", payload=payload)
                self.assertEqual(caught.exception.http_status, 409)
                self.assert_zero_delta(before)

    def test_partial_historical_definition_is_not_claimed_or_completed(self):
        partial = ProcessDefinition.objects.create(
            definition_code="PARTIAL_ATOMIC_FLOW",
            definition_name="历史半配置",
            business_domain="PDE",
            description="",
            document_type="PartialAtomicObject",
            version=1,
            active=True,
            definition_hash="0" * 64,
        )
        before = self.counts()
        with self.assertRaises(WorkflowDefinitionError) as caught:
            self.execute(
                key="partial-history-key",
                payload=self.payload(
                    definitionCode=partial.definition_code,
                    documentType=partial.document_type,
                ),
            )
        self.assertEqual(
            caught.exception.code, "WORKFLOW_CATALOG_PARTIAL_CONFIGURATION_CONFLICT"
        )
        self.assertEqual(caught.exception.http_status, 409)
        self.assertEqual(partial.nodes.count(), 0)
        self.assert_zero_delta(before)

    def test_existing_complete_configuration_does_not_fabricate_request_history(self):
        existing = ProcessDefinition.objects.create(
            definition_code="COMPLETE_WITHOUT_REQUEST",
            definition_name="既有完整配置",
            business_domain="PDE",
            description="",
            document_type="CompleteWithoutRequest",
            version=1,
            active=True,
            definition_hash="0" * 64,
        )
        WorkflowNodeDefinition.objects.create(
            process_definition=existing,
            node_code="REVIEW",
            node_name="评审",
            sequence=1,
            business_action_code="catalog.atomic.action",
            active=True,
        )
        before = self.counts()
        with self.assertRaises(WorkflowDefinitionError) as caught:
            self.execute(
                key="complete-history-key",
                payload=self.payload(
                    definitionCode=existing.definition_code,
                    documentType=existing.document_type,
                ),
            )
        self.assertEqual(caught.exception.code, "WORKFLOW_CATALOG_DEFINITION_CONFLICT")
        self.assertEqual(MasterDataWriteRequest.objects.filter(
            idempotency_key="complete-history-key"
        ).count(), 0)
        self.assert_zero_delta(before)

    def test_unauthorized_actor_and_client_supplied_ids_are_zero_write(self):
        viewer = User.objects.create_user(
            username="atomic-catalog-viewer",
            password="secret",
            real_name="Catalog只读人员",
            company_id=self.company.pk,
        )
        before = self.counts()
        with self.assertRaises(WorkflowDefinitionError) as denied:
            WorkflowDefinitionOperatingService.configure_atomic_minimal_template(
                user=viewer, payload=self.payload(), idempotency_key="denied-key"
            )
        self.assertEqual(denied.exception.http_status, 403)
        self.assert_zero_delta(before)

        invalid = self.payload()
        invalid["definition"]["id"] = 99
        with self.assertRaises(WorkflowDefinitionError) as unsupported:
            self.execute(key="client-id-key", payload=invalid)
        self.assertEqual(unsupported.exception.code, "UNSUPPORTED_FIELD")
        self.assert_zero_delta(before)

    def test_network_response_loss_retry_returns_first_committed_result(self):
        ignored_first_response = self.execute(key="network-retry-key")
        after_first = self.counts()
        recovered = self.execute(key="network-retry-key")
        self.assertTrue(recovered["idempotentReplay"])
        self.assertEqual(
            recovered["definition"]["id"],
            ignored_first_response["definition"]["id"],
        )
        self.assertEqual(recovered["node"]["id"], ignored_first_response["node"]["id"])
        self.assertEqual(self.counts(), after_first)

    def test_atomic_api_requires_header_and_returns_authoritative_ids_and_409(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        path = "/api/workflow/definitions/atomic-minimal-template/"

        unsafe_legacy_route = client.post(
            "/api/workflow/definitions/",
            {"action": ATOMIC_MINIMAL_TEMPLATE_ACTION, "payload": self.payload()},
            format="json",
            HTTP_IDEMPOTENCY_KEY="must-not-fallback",
        )
        self.assertEqual(unsafe_legacy_route.status_code, 400)
        self.assertEqual(unsafe_legacy_route.data["error"]["code"], "ACTION_NOT_REGISTERED")

        missing = client.post(path, self.payload(), format="json")
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.data["error"]["code"], "IDEMPOTENCY_KEY_REQUIRED")

        first = client.post(
            path, self.payload(), format="json", HTTP_IDEMPOTENCY_KEY="api-atomic-key"
        )
        replay = client.post(
            path, self.payload(), format="json", HTTP_IDEMPOTENCY_KEY="api-atomic-key"
        )
        changed = self.payload(definitionName="冲突名称")
        conflict = client.post(
            path, changed, format="json", HTTP_IDEMPOTENCY_KEY="api-atomic-key"
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(conflict.status_code, 409)
        self.assertFalse(first.data["data"]["idempotentReplay"])
        self.assertTrue(replay.data["data"]["idempotentReplay"])
        self.assertEqual(
            first.data["data"]["definition"]["id"],
            replay.data["data"]["definition"]["id"],
        )
        self.assertEqual(
            conflict.data["error"]["code"], "IDEMPOTENCY_PAYLOAD_CONFLICT"
        )
        self.assertTrue(first.data["meta"]["productionUserDataWritten"])
        self.assertFalse(replay.data["meta"]["productionUserDataWritten"])


class AtomicMinimalTemplateCatalogConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.company = Company.objects.create(
            id=992, code="ATCX", name="原子Catalog并发测试公司"
        )
        self.admin = User.objects.create_superuser(
            username="atomic-concurrency-admin",
            password="secret",
            real_name="原子并发管理员",
            company_id=self.company.pk,
        )
        Permission.objects.get_or_create(
            code=WORKFLOW_DEFINITION_PERMISSION,
            defaults={"name": "岗位流程责任维护", "module": "SYSTEM"},
        )
        Permission.objects.get_or_create(
            code="catalog.concurrent.action",
            defaults={"name": "Catalog并发测试动作", "module": "WORKFLOW"},
        )

    def payload(self):
        return {
            "definition": {
                "definitionCode": "CONCURRENT_ATOMIC_FLOW",
                "definitionName": "并发原子流程",
                "businessDomain": "PDE",
                "description": "并发合同",
                "documentType": "ConcurrentAtomicObject",
                "version": 1,
                "active": True,
            },
            "node": {
                "nodeCode": "REVIEW",
                "nodeName": "评审",
                "sequence": 1,
                "businessActionCode": "catalog.concurrent.action",
                "active": True,
                "description": "",
            },
            "reason": "验证Catalog并发合同",
        }

    def run_competition(self, keys):
        barrier = Barrier(len(keys))

        def worker(key):
            close_old_connections()
            try:
                user = User.objects.get(pk=self.admin.pk)
                barrier.wait(timeout=10)
                result = WorkflowDefinitionOperatingService.configure_atomic_minimal_template(
                    user=user, payload=self.payload(), idempotency_key=key
                )
                return {"ok": True, "replay": result["idempotentReplay"]}
            except WorkflowDefinitionError as error:
                return {"ok": False, "code": error.code, "status": error.http_status}
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=len(keys)) as executor:
            return list(executor.map(worker, keys))

    def assert_single_committed_configuration(self):
        definition = ProcessDefinition.objects.get(
            definition_code="CONCURRENT_ATOMIC_FLOW"
        )
        self.assertEqual(definition.nodes.count(), 1)
        self.assertEqual(MasterDataWriteRequest.objects.filter(
            action_code=ATOMIC_MINIMAL_TEMPLATE_ACTION,
            target_entity_id=str(definition.pk),
            status=MasterDataWriteRequest.Status.COMMITTED,
        ).count(), 1)
        self.assertEqual(ExternalIdentity.objects.filter(
            source_system="PCE_WORKFLOW_DEFINITION_CATALOG",
            target_entity_id=str(definition.pk),
        ).count(), 1)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.filter(
            action_code=ATOMIC_MINIMAL_TEMPLATE_ACTION,
            target_id=definition.pk,
        ).count(), 1)

    def test_same_request_identity_concurrent_commits_at_most_once(self):
        results = self.run_competition(["same-concurrent-key", "same-concurrent-key"])
        self.assertEqual(sum(row["ok"] and not row.get("replay") for row in results), 1)
        self.assertTrue(all(row["ok"] or row.get("status") == 409 for row in results))
        self.assert_single_committed_configuration()

    def test_different_request_identities_same_definition_commit_at_most_once(self):
        results = self.run_competition(["different-key-a", "different-key-b"])
        self.assertEqual(sum(row["ok"] and not row.get("replay") for row in results), 1)
        self.assertEqual(sum(not row["ok"] and row.get("status") == 409 for row in results), 1)
        self.assert_single_committed_configuration()

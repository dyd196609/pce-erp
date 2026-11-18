from unittest.mock import patch

from django.test import TestCase

from pfm.models import Employee
from system.authorization import AuthorizationService
from system.models import (
    Company, Department, OrganizationOperatingAuditRecord, Permission, Position, Role,
    RolePermission, User, UserRoleScopeAssignment,
)
from sales.services import SalesBusinessError

from .models import (
    OrderCrossFunctionalReview, OrderCrossFunctionalReviewItem, OrderReviewItemAudit,
    OrderReviewParticipantGrant,
)
from .order_review_service import (
    ReviewBusinessError, build_review_facts, final_approve_review, save_draft,
    sign_items, submit_review,
)
from .order_review_approval import (
    OrderReviewApprovalError, ensure_order_review_approval_configuration,
    reconcile_legacy_submitted_review,
)
from .models import EngineeringSourceRecord
from .review_permission_catalog import (
    converge_active_review_participant_roles, ensure_review_permission_catalog,
)
from workflow_runtime.models import (
    ApprovalDecision, ApprovalTask, BusinessStateTransition, WorkflowInstance,
)


class OrderReviewItemizedTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code="ITEMIZED", name="逐项评审隔离测试公司")
        self.user = User.objects.create_user(username="itemized_reviewer", password="unused", real_name="逐项评审人", company_id=self.company.pk, is_superuser=True)
        department = Department.objects.create(company=self.company, code="REV", name="评审部")
        position = Position.objects.create(company=self.company, department=department, code="REV-POS", name="逐项评审测试岗位")
        self.employee = Employee.objects.create(user=self.user, employee_no="REV001", full_name="逐项评审人", status="active", department_ref=department, position_ref=position)
        self.other = User.objects.create_user(username="other_reviewer", password="unused", real_name="其他评审人", company_id=self.company.pk, is_superuser=True)
        self.other_employee = Employee.objects.create(user=self.other, employee_no="REV002", full_name="其他评审人", status="active", department_ref=department, position_ref=position)
        self.participant = User.objects.create_user(username="review_participant", password="unused", real_name="对象级参与人", company_id=self.company.pk)
        self.participant_employee = Employee.objects.create(user=self.participant, employee_no="REV003", full_name="对象级参与人", status="active", department_ref=department, position_ref=position)
        self.source = EngineeringSourceRecord.objects.create(company=self.company, source_no="SOURCE-I", source_name="逐项来源", source_type="controlled_import", source_version="R1", content_hash="b" * 64, status="confirmed", source_payload={"businessOrderReference": {"sourceOrderNo": "I-1", "customer": "测试客户", "project": "测试项目"}, "registeredSourceScope": {"sourceCount": 2}})
        ensure_review_permission_catalog()
        ensure_order_review_approval_configuration("PDE_PRODUCTION_FEASIBILITY")
        self.full_pde_role = Role.objects.create(
            code="test_full_pde_item_worker", name="隔离测试PDE全事项办理角色",
        )
        for permission in Permission.objects.filter(
            code__startswith="pde.production_feasibility_review."
        ):
            RolePermission.objects.create(role=self.full_pde_role, permission=permission)
        for account in (self.user, self.other):
            UserRoleScopeAssignment.objects.create(
                user=account, role=self.full_pde_role, organization=self.company,
                scope_code="ORGANIZATION", active=True,
                business_hash=f"test-full-pde-{account.pk}",
            )

    def assign_participant_role(self, review_type="CRM_ORDER_REVIEW"):
        role_code = {
            "CRM_ORDER_REVIEW": "crm_order_review_participant",
            "PDE_PRODUCTION_FEASIBILITY": "pde_production_feasibility_review_participant",
        }[review_type]
        return UserRoleScopeAssignment.objects.create(
            user=self.participant, role=Role.objects.get(code=role_code),
            organization=self.company, scope_code="ORGANIZATION", active=True,
            business_hash=f"test-{review_type}-{self.participant.pk}",
        )

    def make_pde_item_worker(self, suffix, item_codes=("01",), usable_password=True):
        account = User.objects.create_user(
            username=f"pde_auto_{suffix}",
            password="unused" if usable_password else None,
            real_name=f"自动责任人{suffix}", company_id=self.company.pk,
        )
        employee = Employee.objects.create(
            user=account, employee_no=f"AUTO-{suffix}", full_name=f"自动责任人{suffix}",
            status="active", department_ref=self.employee.department_ref,
            position_ref=self.employee.position_ref,
        )
        role = Role.objects.create(code=f"pde_auto_role_{suffix}", name=f"自动责任角色{suffix}")
        codes = {
            "pde.production_feasibility_review.view",
            "pde.production_feasibility_review.maintain_own_opinion",
            "pde.production_feasibility_review.sign_own_items",
            *{f"pde.production_feasibility_review.item.{code}" for code in item_codes},
        }
        for permission in Permission.objects.filter(code__in=codes):
            RolePermission.objects.create(role=role, permission=permission)
        UserRoleScopeAssignment.objects.create(
            user=account, role=role, organization=self.company,
            scope_code="SELF", active=True, business_hash=f"pde-auto-{suffix}",
        )
        return account, employee, role

    def keep_preparer_but_remove_test_item_candidates(self):
        UserRoleScopeAssignment.objects.filter(
            user__in=(self.user, self.other), role=self.full_pde_role,
        ).delete()

    def facts(self, review_type="PDE_PRODUCTION_FEASIBILITY"):
        return build_review_facts(user=self.user, review_type=review_type, source_record_id=self.source.pk)

    def rows(self, review_type="PDE_PRODUCTION_FEASIBILITY", decision="AGREE", other=()):
        rows = []
        for row in self.facts(review_type)["review"]["templateItems"]:
            rows.append({**row, "decision": decision, "responsibleEmployeeId": self.employee.pk})
        for index, value in enumerate(other):
            rows.append({"stableKey": f"OTHER-TEST-{index}", "itemKind": "OTHER", "itemText": value, "evidenceNote": "补充依据", "decision": decision, "responsibleEmployeeId": self.employee.pk})
        return rows

    def save(self, rows, review_type="PDE_PRODUCTION_FEASIBILITY", review_id=None):
        return save_draft(user=self.user, review_type=review_type, source_record_id=self.source.pk, idempotency_key=f"key-{review_type}-{review_id or 'new'}", data={"reviewId": review_id, "expectedSourceVersion": "R1", "expectedContentHash": "b" * 64, "expectedTemplateVersion": "V1.0", "items": rows})

    def test_no_other_items_and_incomplete_draft_refresh(self):
        result = self.save(self.rows(decision=""))
        self.assertEqual(result["review"]["draftSummary"]["total"], 9)
        self.assertEqual(result["review"]["draftSummary"]["pending"], 9)
        self.assertFalse(result["review"]["draftSummary"]["complete"])
        self.assertEqual(OrderCrossFunctionalReview.objects.get().conclusion, "")

    def test_fixed_items_cannot_be_omitted_by_direct_request(self):
        result = self.save([])
        self.assertEqual(result["review"]["draftSummary"]["total"], 9)
        self.assertEqual(result["review"]["draftSummary"]["pending"], 9)
        self.assertTrue(OrderReviewItemAudit.objects.filter(action="FIXED_ITEM_ENFORCED").exists())

    def test_blank_other_is_not_persisted_and_multiple_other_are_counted(self):
        rows = self.rows(other=("包装方案可执行。", "特殊运输条件可满足。"))
        rows.append({"stableKey": "OTHER-BLANK", "itemKind": "OTHER", "itemText": ""})
        result = self.save(rows)
        self.assertEqual(result["review"]["draftSummary"]["total"], 11)
        self.assertEqual(len([r for r in result["review"]["draftItems"] if r["itemKind"] == "OTHER"]), 2)

    def test_unsaved_other_candidates_use_formal_rule_without_business_writes(self):
        before = {
            "reviews": OrderCrossFunctionalReview.objects.count(),
            "items": OrderCrossFunctionalReviewItem.objects.count(),
            "grants": OrderReviewParticipantGrant.objects.count(),
            "audits": OrderReviewItemAudit.objects.count(),
        }
        facts = self.facts()
        candidates = facts["otherResponsibilityCandidates"]

        self.assertEqual(candidates["statusCode"], "AVAILABLE")
        self.assertTrue(candidates["selectionExecutable"])
        self.assertEqual(
            set(candidates["requiredActionCodes"]),
            {
                "pde.production_feasibility_review.view",
                "pde.production_feasibility_review.maintain_own_opinion",
                "pde.production_feasibility_review.sign_own_items",
            },
        )
        self.assertEqual(
            set(candidates["eligibleEmployeeIds"]),
            {self.employee.pk, self.other_employee.pk},
        )
        self.assertFalse(candidates["readCreatesBusinessRecords"])
        self.assertEqual(before, {
            "reviews": OrderCrossFunctionalReview.objects.count(),
            "items": OrderCrossFunctionalReviewItem.objects.count(),
            "grants": OrderReviewParticipantGrant.objects.count(),
            "audits": OrderReviewItemAudit.objects.count(),
        })

    def test_unsaved_other_candidates_are_not_disclosed_to_non_preparer(self):
        participant, participant_employee, _role = self.make_pde_item_worker(
            "candidate_reader", item_codes=("01",)
        )
        rows = self.rows(decision="")
        rows[0]["responsibleEmployeeId"] = participant_employee.pk
        self.save(rows)
        facts = build_review_facts(
            user=participant,
            review_type="PDE_PRODUCTION_FEASIBILITY",
            source_record_id=self.source.pk,
        )
        candidates = facts["otherResponsibilityCandidates"]

        self.assertEqual(candidates["statusCode"], "SELECTION_PERMISSION_DENIED")
        self.assertFalse(candidates["selectionExecutable"])
        self.assertEqual(candidates["eligibleEmployeeIds"], [])
        self.assertIsNone(candidates["candidateCount"])

    def test_unsaved_other_candidates_report_no_qualified_employee(self):
        self.keep_preparer_but_remove_test_item_candidates()
        self.user.is_superuser = False
        self.user.save(update_fields=["is_superuser"])
        self.other.is_superuser = False
        self.other.save(update_fields=["is_superuser"])
        legacy_role = Role.objects.create(
            code="test_other_candidate_preparer_only",
            name="隔离测试其它事项准备角色",
        )
        RolePermission.objects.create(
            role=legacy_role,
            permission=Permission.objects.get(
                code="production.engineering.readiness.maintain"
            ),
        )
        UserRoleScopeAssignment.objects.create(
            user=self.user,
            role=legacy_role,
            organization=self.company,
            scope_code="ORGANIZATION",
            active=True,
            business_hash="test-other-candidate-preparer-only",
        )

        candidates = self.facts()["otherResponsibilityCandidates"]

        self.assertEqual(candidates["statusCode"], "NO_ELIGIBLE_CANDIDATES")
        self.assertEqual(candidates["eligibleEmployeeIds"], [])
        self.assertEqual(candidates["candidateCount"], 0)
        self.assertIn("缺少查看", candidates["noCandidateReason"])

    def test_assigned_other_item_uses_own_actions_without_full_draft_permission(self):
        assignment = self.assign_participant_role("PDE_PRODUCTION_FEASIBILITY")
        self.assertFalse(RolePermission.objects.filter(
            role=assignment.role,
            permission__code="pde.production_feasibility_review.manage_draft",
        ).exists())
        rows = self.rows(other=("包装方式需补充专项确认。",))
        rows[-1]["responsibleEmployeeId"] = self.participant_employee.pk
        created = self.save(rows)
        review_id = created["review"]["draft"]["id"]

        participant_facts = build_review_facts(
            user=self.participant,
            review_type="PDE_PRODUCTION_FEASIBILITY",
            source_record_id=self.source.pk,
        )
        other_row = next(
            row for row in participant_facts["review"]["draftItems"]
            if row["itemKind"] == "OTHER"
        )
        self.assertTrue(other_row["canCurrentUserEdit"])
        self.assertTrue(other_row["canCurrentUserSign"])
        self.assertEqual(other_row["itemPermissionCode"], "")
        self.assertEqual(
            other_row["signingReadiness"]["statusCode"],
            "READY_TO_SIGN_OWN_ITEM",
        )

        payload_rows = participant_facts["review"]["draftItems"]
        for row in payload_rows:
            if row["id"] == other_row["id"]:
                row["evidenceNote"] = "本人补充依据"
                row["decision"] = "AGREE"
        updated = save_draft(
            user=self.participant,
            review_type="PDE_PRODUCTION_FEASIBILITY",
            source_record_id=self.source.pk,
            idempotency_key="participant-other-own-opinion",
            data={"reviewId": review_id, "expectedSourceVersion": "R1",
                "expectedContentHash": "b" * 64, "expectedTemplateVersion": "V1.0",
                "items": payload_rows},
        )
        updated_other = next(
            row for row in updated["review"]["draftItems"]
            if row["itemKind"] == "OTHER"
        )
        signed = sign_items(
            user=self.participant,
            review_type="PDE_PRODUCTION_FEASIBILITY",
            source_record_id=self.source.pk,
            data={"reviewId": review_id, "itemIds": [updated_other["id"]],
                "expectedSourceVersion": "R1", "expectedContentHash": "b" * 64,
                "expectedTemplateVersion": "V1.0"},
        )
        self.assertEqual(next(
            row for row in signed["review"]["draftItems"]
            if row["id"] == updated_other["id"]
        )["signatureStatus"], "SIGNED")

        forged_rows = list(signed["review"]["draftItems"])
        forged_rows.append({"stableKey": "OTHER-FORGED", "itemKind": "OTHER",
            "itemText": "参与人无权新增结构", "responsibleEmployeeId": self.participant_employee.pk})
        with self.assertRaises(ReviewBusinessError) as structure_denied:
            save_draft(
                user=self.participant,
                review_type="PDE_PRODUCTION_FEASIBILITY",
                source_record_id=self.source.pk,
                idempotency_key="participant-other-structure-denied",
                data={"reviewId": review_id, "expectedSourceVersion": "R1",
                    "expectedContentHash": "b" * 64, "expectedTemplateVersion": "V1.0",
                    "items": forged_rows},
            )
        self.assertEqual(structure_denied.exception.code, "OWN_OPINION_SCOPE_DENIED")

    def test_disagreement_reason_and_other_reason_are_required(self):
        rows = self.rows(); rows[0]["decision"] = "DISAGREE"
        result = self.save(rows); review = OrderCrossFunctionalReview.objects.get()
        with self.assertRaises(ReviewBusinessError) as caught:
            submit_review(user=self.user, review_type=review.review_type, source_record_id=self.source.pk, data={"reviewId": review.pk, "expectedSourceVersion": "R1", "expectedContentHash": "b" * 64, "expectedTemplateVersion": "V1.0"})
        self.assertEqual(caught.exception.code, "REVIEW_INCOMPLETE")
        rows[0]["disagreementReasonCode"] = "其它"; self.save(rows, review_id=review.pk)
        self.assertTrue(any("其它原因未说明" in reason for reason in OrderCrossFunctionalReview.objects.get().item_summary["incompleteReasons"]))

    def test_own_batch_sign_and_impersonation_rejected(self):
        result = self.save(self.rows()); review_id = result["review"]["draft"]["id"]; ids = [r["id"] for r in result["review"]["draftItems"]]
        self.assertTrue(all(row["canCurrentUserSign"] for row in result["review"]["draftItems"]))
        self.assertTrue(all(row["responsibleEmployee"]["hasActiveLoginAccount"] for row in result["review"]["draftItems"]))
        self.assertTrue(all(row["responsibleEmployee"]["signatureEntryReady"] for row in result["review"]["draftItems"]))
        with self.assertRaises(ReviewBusinessError) as caught:
            sign_items(user=self.other, review_type="PDE_PRODUCTION_FEASIBILITY", source_record_id=self.source.pk, data={"reviewId": review_id, "itemIds": ids, "expectedSourceVersion": "R1", "expectedContentHash": "b" * 64, "expectedTemplateVersion": "V1.0"})
        self.assertEqual(caught.exception.code, "SIGN_PERMISSION_DENIED")
        result = sign_items(user=self.user, review_type="PDE_PRODUCTION_FEASIBILITY", source_record_id=self.source.pk, data={"reviewId": review_id, "itemIds": ids, "expectedSourceVersion": "R1", "expectedContentHash": "b" * 64, "expectedTemplateVersion": "V1.0"})
        self.assertEqual(result["review"]["draftSummary"]["signed"], 9)

    def test_signing_readiness_explains_other_responsible_and_unsaved_opinion(self):
        rows = self.rows(decision="")
        rows[0]["responsibleEmployeeId"] = self.other_employee.pk
        result = self.save(rows)
        by_code = {row["itemCode"]: row for row in result["review"]["draftItems"]}

        self.assertEqual(
            by_code["01"]["signingReadiness"]["statusCode"],
            "OTHER_EMPLOYEE_RESPONSIBLE",
        )
        self.assertEqual(
            by_code["01"]["signingReadiness"]["disabledReason"],
            "该项由其他责任人签认。",
        )
        self.assertEqual(
            by_code["02"]["signingReadiness"]["statusCode"],
            "OWN_OPINION_NOT_SAVED",
        )
        self.assertEqual(
            by_code["02"]["signingReadiness"]["disabledReason"],
            "请先保存本人意见。",
        )

    def test_pde_item_permissions_are_distinct_enforced_and_batch_atomic(self):
        item_permissions = list(Permission.objects.filter(
            code__startswith="pde.production_feasibility_review.item."
        ).order_by("code"))
        self.assertEqual([row.code.rsplit(".", 1)[-1] for row in item_permissions], [
            "01", "02", "03", "04", "05", "06", "07", "08", "09",
        ])
        governed_role = Role.objects.get(code="pde_production_feasibility_review_participant")
        self.assertFalse(RolePermission.objects.filter(
            role=governed_role, permission__in=item_permissions,
        ).exists())
        permission_count = Permission.objects.count()
        ensure_review_permission_catalog()
        self.assertEqual(Permission.objects.count(), permission_count)

        worker = User.objects.create_user(
            username="pde_item_0405", password="unused", real_name="用料物料评审人",
            company_id=self.company.pk,
        )
        worker_employee = Employee.objects.create(
            user=worker, employee_no="REV0405", full_name="用料物料评审人", status="active",
            department_ref=self.employee.department_ref, position_ref=self.employee.position_ref,
        )
        worker_role = Role.objects.create(code="test_pde_item_0405", name="用料与物料准备评审")
        allowed_codes = {
            "pde.production_feasibility_review.view",
            "pde.production_feasibility_review.maintain_own_opinion",
            "pde.production_feasibility_review.sign_own_items",
            "pde.production_feasibility_review.item.04",
            "pde.production_feasibility_review.item.05",
        }
        for permission in Permission.objects.filter(code__in=allowed_codes):
            RolePermission.objects.create(role=worker_role, permission=permission)
        UserRoleScopeAssignment.objects.create(
            user=worker, role=worker_role, organization=self.company,
            scope_code="ORGANIZATION", active=True, business_hash="pde-item-0405",
        )

        rows = self.rows()
        rows[3]["responsibleEmployeeId"] = worker_employee.pk
        rows[4]["responsibleEmployeeId"] = worker_employee.pk
        saved = self.save(rows)
        review = OrderCrossFunctionalReview.objects.get(pk=saved["review"]["draft"]["id"])
        self.assertTrue(OrderReviewParticipantGrant.objects.filter(
            review=review, employee=worker_employee, user=worker, active=True,
        ).exists())
        worker_facts = build_review_facts(
            user=worker, review_type="PDE_PRODUCTION_FEASIBILITY",
            source_record_id=self.source.pk,
        )
        by_code = {row["itemCode"]: row for row in worker_facts["review"]["draftItems"]}
        self.assertTrue(by_code["04"]["canCurrentUserEdit"])
        self.assertTrue(by_code["05"]["canCurrentUserSign"])
        self.assertFalse(by_code["07"]["canCurrentUserEdit"])

        forged = self.rows()
        forged[3]["responsibleEmployeeId"] = worker_employee.pk
        forged[4]["responsibleEmployeeId"] = worker_employee.pk
        forged[6]["responsibleEmployeeId"] = worker_employee.pk
        with self.assertRaises(ReviewBusinessError) as assignment_denied:
            self.save(forged, review_id=review.pk)
        self.assertEqual(assignment_denied.exception.code, "RESPONSIBLE_ITEM_PERMISSION_DENIED")

        item04 = review.items.get(item_code="04")
        item05 = review.items.get(item_code="05")
        item07 = review.items.get(item_code="07")
        OrderCrossFunctionalReviewItem.objects.filter(pk=item07.pk).update(
            responsible_employee=worker_employee,
        )
        sign_items(user=worker, review_type="PDE_PRODUCTION_FEASIBILITY",
            source_record_id=self.source.pk, data={"reviewId": review.pk,
                "itemIds": [item04.pk], "expectedSourceVersion": "R1",
                "expectedContentHash": "b" * 64, "expectedTemplateVersion": "V1.0"})
        with self.assertRaises(ReviewBusinessError) as batch_denied:
            sign_items(user=worker, review_type="PDE_PRODUCTION_FEASIBILITY",
                source_record_id=self.source.pk, data={"reviewId": review.pk,
                    "itemIds": [item05.pk, item07.pk], "expectedSourceVersion": "R1",
                    "expectedContentHash": "b" * 64, "expectedTemplateVersion": "V1.0"})
        self.assertEqual(batch_denied.exception.code, "ITEM_PERMISSION_DENIED")
        item05.refresh_from_db()
        self.assertEqual(item05.signature_status, "UNSIGNED")

        RolePermission.objects.filter(
            role=worker_role,
            permission__code="pde.production_feasibility_review.item.04",
        ).delete()
        refreshed = build_review_facts(
            user=worker, review_type="PDE_PRODUCTION_FEASIBILITY",
            source_record_id=self.source.pk,
        )
        self.assertFalse(next(
            row for row in refreshed["review"]["draftItems"] if row["itemCode"] == "04"
        )["canCurrentUserEdit"])

    def test_change_invalidates_signature(self):
        result = self.save(self.rows()); review_id = result["review"]["draft"]["id"]; first = result["review"]["draftItems"][0]
        sign_items(user=self.user, review_type="PDE_PRODUCTION_FEASIBILITY", source_record_id=self.source.pk, data={"reviewId": review_id, "itemIds": [first["id"]], "expectedSourceVersion": "R1", "expectedContentHash": "b" * 64, "expectedTemplateVersion": "V1.0"})
        rows = self.rows(); rows[0]["evidenceNote"] = "依据已更新"; result = self.save(rows, review_id=review_id)
        self.assertEqual(result["review"]["draftItems"][0]["signatureStatus"], "UNSIGNED")
        self.assertTrue(OrderReviewItemAudit.objects.filter(action="SIGNATURE_INVALIDATED").exists())

    def test_responsible_employee_can_be_cleared_saved_and_reselected(self):
        result = self.save(self.rows()); review_id = result["review"]["draft"]["id"]; first = result["review"]["draftItems"][0]
        sign_items(user=self.user, review_type="PDE_PRODUCTION_FEASIBILITY", source_record_id=self.source.pk, data={"reviewId": review_id, "itemIds": [first["id"]], "expectedSourceVersion": "R1", "expectedContentHash": "b" * 64, "expectedTemplateVersion": "V1.0"})
        rows = self.rows(); rows[0]["responsibleEmployeeId"] = None
        rows[0]["responsibilityChangeReason"] = "隔离测试：原责任安排需要调整"
        cleared = self.save(rows, review_id=review_id)
        cleared_item = cleared["review"]["draftItems"][0]
        self.assertIsNone(cleared_item["responsibleEmployeeId"])
        self.assertEqual(cleared_item["signatureStatus"], "UNSIGNED")
        self.assertTrue(OrderReviewItemAudit.objects.filter(action="SIGNATURE_INVALIDATED").exists())
        refreshed = self.facts()["review"]["draftItems"][0]
        self.assertIsNone(refreshed["responsibleEmployeeId"])
        rows[0]["responsibleEmployeeId"] = self.other_employee.pk
        rows[0]["responsibilityChangeReason"] = "隔离测试：重新指定合格责任人"
        reselected = self.save(rows, review_id=review_id)["review"]["draftItems"][0]
        self.assertEqual(reselected["responsibleEmployeeId"], self.other_employee.pk)

    def test_negative_other_removal_is_audited(self):
        rows = self.rows(other=("特殊条件不满足。",)); rows[-1]["decision"] = "DISAGREE"; rows[-1]["disagreementReasonCode"] = "风险不可接受"
        result = self.save(rows); review_id = result["review"]["draft"]["id"]
        self.save(self.rows(), review_id=review_id)
        self.assertTrue(OrderReviewItemAudit.objects.filter(action="ITEM_REMOVE", before_snapshot__decision="DISAGREE").exists())

    def test_complete_pde_disagreement_submits_pending_and_duplicate_is_blocked(self):
        rows = self.rows(); rows[0]["decision"] = "DISAGREE"; rows[0]["disagreementReasonCode"] = "条件未落实"
        result = self.save(rows); review_id = result["review"]["draft"]["id"]; ids = [r["id"] for r in result["review"]["draftItems"]]
        sign_items(user=self.user, review_type="PDE_PRODUCTION_FEASIBILITY", source_record_id=self.source.pk, data={"reviewId": review_id, "itemIds": ids, "expectedSourceVersion": "R1", "expectedContentHash": "b" * 64, "expectedTemplateVersion": "V1.0"})
        result = submit_review(user=self.user, review_type="PDE_PRODUCTION_FEASIBILITY", source_record_id=self.source.pk, data={"reviewId": review_id, "expectedSourceVersion": "R1", "expectedContentHash": "b" * 64, "expectedTemplateVersion": "V1.0"})
        self.assertEqual(result["review"]["latest"]["conclusion"], "")
        self.assertEqual(result["approval"]["statusCode"], "PENDING")
        self.assertTrue(result["submissionProcess"]["comprehensiveApprovalImplemented"])
        self.assertTrue(result["submissionProcess"]["submittedReviewCreatesApprovalTask"])
        self.assertEqual(WorkflowInstance.objects.filter(
            document_type="PDEProductionFeasibilityReview", document_id=review_id,
        ).count(), 1)
        self.assertTrue(OrderReviewItemAudit.objects.filter(action="REVIEW_SUBMIT").exists())
        with self.assertRaises(ReviewBusinessError):
            submit_review(user=self.user, review_type="PDE_PRODUCTION_FEASIBILITY", source_record_id=self.source.pk, data={"reviewId": review_id, "expectedSourceVersion": "R1", "expectedContentHash": "b" * 64, "expectedTemplateVersion": "V1.0"})

    def test_pde_custom_role_approver_can_decide_disagreement_without_rewriting_it(self):
        rows = self.rows(); rows[0]["decision"] = "DISAGREE"; rows[0]["disagreementReasonCode"] = "条件未落实"
        prepared = self.save(rows); review_id = prepared["review"]["draft"]["id"]
        sign_items(user=self.user, review_type="PDE_PRODUCTION_FEASIBILITY", source_record_id=self.source.pk,
            data={"reviewId": review_id, "itemIds": [row["id"] for row in prepared["review"]["draftItems"]],
                "expectedSourceVersion": "R1", "expectedContentHash": "b" * 64, "expectedTemplateVersion": "V1.0"})
        submitted = submit_review(user=self.user, review_type="PDE_PRODUCTION_FEASIBILITY", source_record_id=self.source.pk,
            data={"reviewId": review_id, "expectedSourceVersion": "R1", "expectedContentHash": "b" * 64,
                "expectedTemplateVersion": "V1.0"})
        latest = submitted["review"]["latest"]
        approved = final_approve_review(user=self.other, review_type="PDE_PRODUCTION_FEASIBILITY",
            source_record_id=self.source.pk, idempotency_key="pde-custom-role-approval",
            data={"reviewId": review_id, "expectedReviewVersion": latest["reviewVersion"],
                "expectedSourceVersion": latest["sourceVersion"], "decision": "APPROVE",
                "approvalOpinion": "风险措施落实后通过。", "riskHandling": "跟踪未落实条件。",
                "actionId": "pde-custom-role-approval-action"})
        self.assertEqual(approved["approval"]["finalDecision"]["decision"], "APPROVE")
        self.assertEqual(OrderCrossFunctionalReview.objects.get(pk=review_id).items.filter(decision="DISAGREE").count(), 1)

    def test_handoff_reports_login_state_and_employee_linked_submitter(self):
        result = self.save(self.rows("CRM_ORDER_REVIEW"), "CRM_ORDER_REVIEW")
        readiness = next(row for row in result["responsibleReadiness"] if row["employeeId"] == self.employee.pk)
        self.assertTrue(readiness["canAttemptNormalLogin"])
        self.assertFalse(readiness["actualLoginVerified"])
        self.assertIn("待本人首次登录验证", readiness["loginPreparationStatusLabel"])
        self.assertFalse(result["submissionProcess"]["firstLoginSetup"]["selfServiceAvailable"])
        self.assertIn("重置密码", result["submissionProcess"]["firstLoginSetup"]["administratorPath"])
        submitters = result["submissionProcess"]["eligibleSubmitters"]
        self.assertTrue(result["submissionProcess"]["legalSubmitterAvailable"])
        self.assertTrue(any(row["employeeId"] == self.employee.pk for row in submitters))

    def test_superuser_without_employee_is_not_reported_as_business_submitter(self):
        self.employee.user = None
        self.employee.save(update_fields=["user"])
        self.other_employee.user = None
        self.other_employee.save(update_fields=["user"])
        facts = build_review_facts(user=self.user, review_type="CRM_ORDER_REVIEW", source_record_id=self.source.pk)
        self.assertFalse(facts["submissionProcess"]["legalSubmitterAvailable"])
        self.assertEqual(facts["submissionProcess"]["eligibleSubmitters"], [])
        self.assertIn("没有正式员工关联", facts["submissionProcess"]["submitterGap"])

    def test_crm_and_pde_drafts_are_independent(self):
        self.save(self.rows("CRM_ORDER_REVIEW"), "CRM_ORDER_REVIEW")
        self.save(self.rows("PDE_PRODUCTION_FEASIBILITY"), "PDE_PRODUCTION_FEASIBILITY")
        self.assertEqual(OrderCrossFunctionalReview.objects.filter(review_type="CRM_ORDER_REVIEW").count(), 1)
        self.assertEqual(OrderCrossFunctionalReview.objects.filter(review_type="PDE_PRODUCTION_FEASIBILITY").count(), 1)

    def test_signature_routing_reports_missing_login_without_granting_one(self):
        employee_without_login = Employee.objects.create(
            employee_no="REV-NO-LOGIN", full_name="无登录账号责任人", status="active",
            department_ref=self.employee.department_ref, position_ref=self.employee.position_ref,
        )
        rows = self.rows()
        rows[0]["responsibleEmployeeId"] = employee_without_login.pk
        with self.assertRaises(ReviewBusinessError) as denied:
            self.save(rows)
        self.assertEqual(denied.exception.code, "RESPONSIBLE_ITEM_PERMISSION_DENIED")
        self.assertEqual(self.facts()["currentActor"]["employee"]["id"], self.employee.pk)

    @patch("sales.development_contract_sample.build_development_contract_entry")
    def test_normal_flow_uses_configured_review_object_not_latest_source(self, entry):
        newer = EngineeringSourceRecord.objects.create(
            company=self.company, source_no="UNRELATED", source_name="不相关的较新来源",
            source_type="controlled_import", source_version="R2", content_hash="c" * 64,
            status="confirmed", source_payload={"businessOrderReference": {"sourceOrderNo": "OTHER"}},
        )
        entry.return_value = {"target": {"query": {"sourceRecord": self.source.pk}}}
        result = build_review_facts(user=self.user, review_type="PDE_PRODUCTION_FEASIBILITY")
        self.assertEqual(result["source"]["id"], self.source.pk)
        self.assertNotEqual(result["source"]["id"], newer.pk)

    @patch("sales.development_contract_sample.build_development_contract_entry", side_effect=SalesBusinessError("ENTRY_MISSING", "missing"))
    def test_normal_flow_without_configured_object_is_explicit(self, _entry):
        with self.assertRaises(ReviewBusinessError) as caught:
            build_review_facts(user=self.user, review_type="PDE_PRODUCTION_FEASIBILITY")
        self.assertEqual(caught.exception.code, "REVIEW_OBJECT_REQUIRED")

    def test_view_denial_identifies_account_company_and_read_permission(self):
        viewer = User.objects.create_user(
            username="review_read_denied", password="unused", real_name="无读取权限账号",
            company_id=self.company.pk,
        )
        with self.assertRaises(ReviewBusinessError) as caught:
            build_review_facts(user=viewer, review_type="CRM_ORDER_REVIEW", source_record_id=self.source.pk)
        self.assertEqual(caught.exception.code, "VIEW_PERMISSION_DENIED")
        self.assertIn("review_read_denied", caught.exception.message)
        self.assertIn(f"公司ID {self.company.pk}", caught.exception.message)
        self.assertIn("订单评审 - 查看", caught.exception.message)

    @patch("sales.development_contract_sample.build_development_contract_entry")
    def test_pde_module_view_reports_no_formal_review_without_requiring_object_grant(self, entry):
        role = Role.objects.create(code="custom_pde_010203", name="自建工艺评审角色")
        codes = {
            "pde.production_feasibility_review.view",
            "pde.production_feasibility_review.maintain_own_opinion",
            "pde.production_feasibility_review.sign_own_items",
            "pde.production_feasibility_review.item.01",
            "pde.production_feasibility_review.item.02",
            "pde.production_feasibility_review.item.03",
        }
        for permission in Permission.objects.filter(code__in=codes):
            RolePermission.objects.create(role=role, permission=permission)
        UserRoleScopeAssignment.objects.create(
            user=self.participant, role=role, organization=self.company,
            scope_code="SELF", active=True, business_hash="custom-pde-010203",
        )
        entry.return_value = {"target": {"query": {"sourceRecord": self.source.pk}}}

        facts = build_review_facts(
            user=self.participant,
            review_type="PDE_PRODUCTION_FEASIBILITY",
        )

        self.assertEqual(facts["reviewAvailability"]["statusCode"], "FORMAL_REVIEW_NOT_ESTABLISHED")
        self.assertTrue(facts["authorization"]["view"]["executable"])
        self.assertFalse(facts["authorization"]["fullDraftEdit"]["executable"])
        self.assertFalse(facts["authorization"]["ownOpinion"]["executable"])
        self.assertFalse(facts["authorization"]["sign"]["executable"])
        self.assertFalse(facts["authorization"]["submit"]["executable"])
        self.assertIn("已具备本人意见动作资格", facts["authorization"]["ownOpinion"]["disabledReason"])
        self.assertIn("正式评审", facts["authorization"]["sign"]["disabledReason"])
        self.assertEqual(OrderReviewParticipantGrant.objects.count(), 0)

    def test_unique_role_worker_is_auto_matched_saved_and_granted_without_manual_selection(self):
        self.keep_preparer_but_remove_test_item_candidates()
        _, worker, _ = self.make_pde_item_worker("unique", ("01",))

        facts = self.facts()
        match = next(row for row in facts["responsibilityPlan"]["rows"] if row["itemCode"] == "01")
        self.assertEqual(match["statusCode"], "AUTO_MATCHED_UNIQUE")
        self.assertEqual(match["proposedEmployeeId"], worker.pk)
        self.assertEqual(match["candidateCount"], 1)
        self.assertTrue(match["selected"]["roleSources"])
        row01 = next(row for row in facts["review"]["templateItems"] if row["itemCode"] == "01")
        self.assertEqual(row01["responsibleEmployeeId"], worker.pk)

        saved = self.save(facts["review"]["templateItems"])
        review = OrderCrossFunctionalReview.objects.get(pk=saved["review"]["draft"]["id"])
        self.assertEqual(review.items.get(item_code="01").responsible_employee_id, worker.pk)
        self.assertIsNone(review.items.get(item_code="02").responsible_employee_id)
        self.assertTrue(OrderReviewParticipantGrant.objects.filter(
            review=review, employee=worker, user=worker.user, active=True,
        ).exists())
        self.assertTrue(OrderReviewItemAudit.objects.filter(
            review=review, item__item_code="01", action="RESPONSIBILITY_AUTO_ASSIGNED",
        ).exists())

    def test_duplicate_roles_for_same_employee_are_deduplicated_but_two_employees_are_pending(self):
        self.keep_preparer_but_remove_test_item_candidates()
        account, worker, _ = self.make_pde_item_worker("dedupe", ("01",))
        duplicate_role = Role.objects.create(code="pde_auto_role_dedupe_2", name="同员工第二角色")
        for permission in Permission.objects.filter(code__in={
            "pde.production_feasibility_review.view",
            "pde.production_feasibility_review.maintain_own_opinion",
            "pde.production_feasibility_review.sign_own_items",
            "pde.production_feasibility_review.item.01",
        }):
            RolePermission.objects.create(role=duplicate_role, permission=permission)
        UserRoleScopeAssignment.objects.create(
            user=account, role=duplicate_role, organization=self.company,
            scope_code="SELF", active=True, business_hash="pde-auto-dedupe-2",
        )
        first = next(row for row in self.facts()["responsibilityPlan"]["rows"] if row["itemCode"] == "01")
        self.assertEqual(first["candidateCount"], 1)
        self.assertEqual(first["proposedEmployeeId"], worker.pk)
        self.assertEqual(len(first["selected"]["roleSources"]), 2)

        self.make_pde_item_worker("second", ("01",))
        second = next(row for row in self.facts()["responsibilityPlan"]["rows"] if row["itemCode"] == "01")
        self.assertEqual(second["statusCode"], "PENDING_MULTIPLE_CANDIDATES")
        self.assertEqual(second["candidateCount"], 2)
        self.assertIsNone(second["proposedEmployeeId"])

    def test_auto_preparation_is_partial_idempotent_and_reports_login_pending(self):
        self.keep_preparer_but_remove_test_item_candidates()
        _, worker, _ = self.make_pde_item_worker("login_pending", ("01",), usable_password=False)
        facts = self.facts()
        match = next(row for row in facts["responsibilityPlan"]["rows"] if row["itemCode"] == "01")
        self.assertEqual(match["statusCode"], "AUTO_MATCHED_UNIQUE_LOGIN_PENDING")
        self.assertEqual(match["proposedEmployeeId"], worker.pk)

        payload = {"reviewId": None, "expectedSourceVersion": "R1",
            "expectedContentHash": "b" * 64, "expectedTemplateVersion": "V1.0",
            "items": facts["review"]["templateItems"]}
        first = save_draft(user=self.user, review_type="PDE_PRODUCTION_FEASIBILITY",
            source_record_id=self.source.pk, idempotency_key="auto-idempotent", data=payload)
        second = save_draft(user=self.user, review_type="PDE_PRODUCTION_FEASIBILITY",
            source_record_id=self.source.pk, idempotency_key="auto-idempotent", data=payload)
        self.assertEqual(first["review"]["draft"]["id"], second["review"]["draft"]["id"])
        self.assertEqual(OrderCrossFunctionalReview.objects.count(), 1)
        self.assertEqual(OrderReviewParticipantGrant.objects.count(), 1)
        self.assertEqual(OrderReviewItemAudit.objects.filter(
            action="RESPONSIBILITY_AUTO_ASSIGNED",
        ).count(), 1)
        self.assertEqual(second["review"]["draftSummary"]["pending"], 9)

    def test_custom_010203_role_can_handle_only_assigned_items_after_preparer_save(self):
        role = Role.objects.create(code="custom_pde_010203_flow", name="自建工艺评审角色办理链")
        codes = {
            "pde.production_feasibility_review.view",
            "pde.production_feasibility_review.maintain_own_opinion",
            "pde.production_feasibility_review.sign_own_items",
            "pde.production_feasibility_review.item.01",
            "pde.production_feasibility_review.item.02",
            "pde.production_feasibility_review.item.03",
        }
        for permission in Permission.objects.filter(code__in=codes):
            RolePermission.objects.create(role=role, permission=permission)
        UserRoleScopeAssignment.objects.create(
            user=self.participant, role=role, organization=self.company,
            scope_code="SELF", active=True, business_hash="custom-pde-010203-flow",
        )
        rows = self.rows()
        for row in rows[:3]:
            row["responsibleEmployeeId"] = self.participant_employee.pk
        saved = self.save(rows)
        review = OrderCrossFunctionalReview.objects.get(pk=saved["review"]["draft"]["id"])
        self.assertTrue(OrderReviewParticipantGrant.objects.filter(
            review=review, employee=self.participant_employee, user=self.participant, active=True,
        ).exists())

        facts = build_review_facts(
            user=self.participant, review_type="PDE_PRODUCTION_FEASIBILITY",
            source_record_id=self.source.pk,
        )
        self.assertFalse(facts["authorization"]["fullDraftEdit"]["executable"])
        self.assertFalse(facts["authorization"]["submit"]["executable"])
        by_code = {row["itemCode"]: row for row in facts["review"]["draftItems"]}
        self.assertTrue(all(by_code[code]["canCurrentUserEdit"] for code in ("01", "02", "03")))
        self.assertTrue(all(by_code[code]["canCurrentUserSign"] for code in ("01", "02", "03")))
        self.assertFalse(by_code["04"]["canCurrentUserEdit"])

        payload = [dict(row) for row in facts["review"]["draftItems"]]
        payload[0]["decision"] = "DISAGREE"
        payload[0]["disagreementReasonCode"] = "条件未落实"
        updated = save_draft(
            user=self.participant, review_type="PDE_PRODUCTION_FEASIBILITY",
            source_record_id=self.source.pk, idempotency_key="custom-010203-own-opinion",
            data={"reviewId": review.pk, "expectedSourceVersion": "R1",
                "expectedContentHash": "b" * 64, "expectedTemplateVersion": "V1.0",
                "items": payload},
        )
        own = next(row for row in updated["review"]["draftItems"] if row["itemCode"] == "01")
        signed = sign_items(
            user=self.participant, review_type="PDE_PRODUCTION_FEASIBILITY",
            source_record_id=self.source.pk,
            data={"reviewId": review.pk, "itemIds": [own["id"]],
                "expectedSourceVersion": "R1", "expectedContentHash": "b" * 64,
                "expectedTemplateVersion": "V1.0"},
        )
        self.assertEqual(next(
            row for row in signed["review"]["draftItems"] if row["itemCode"] == "01"
        )["signatureStatus"], "SIGNED")

        forged = [dict(row) for row in signed["review"]["draftItems"]]
        row04 = next(row for row in forged if row["itemCode"] == "04")
        row04["decision"] = "DISAGREE"
        row04["disagreementReasonCode"] = "风险不可接受"
        with self.assertRaises(ReviewBusinessError) as denied:
            save_draft(
                user=self.participant, review_type="PDE_PRODUCTION_FEASIBILITY",
                source_record_id=self.source.pk, idempotency_key="custom-010203-forged-04",
                data={"reviewId": review.pk, "expectedSourceVersion": "R1",
                    "expectedContentHash": "b" * 64, "expectedTemplateVersion": "V1.0",
                    "items": forged},
            )
        self.assertEqual(denied.exception.code, "OWN_OPINION_SCOPE_DENIED")

    def test_object_grant_allows_only_own_opinion_and_signature_not_submit_or_order_update(self):
        self.assign_participant_role()
        rows = self.rows("CRM_ORDER_REVIEW")
        rows[0]["responsibleEmployeeId"] = self.participant_employee.pk
        result = self.save(rows, "CRM_ORDER_REVIEW")
        review = OrderCrossFunctionalReview.objects.get(pk=result["review"]["draft"]["id"])
        OrderReviewParticipantGrant.objects.create(
            review=review, company=self.company, employee=self.participant_employee,
            user=self.participant, review_version_snapshot=review.review_version,
            source_version_snapshot=review.source_version, can_view=True,
            can_maintain_own_opinion=True, can_sign_own_items=True, active=True,
            reason="隔离测试对象级授权", created_by=self.user, audit_hash="d" * 64,
        )
        facts = build_review_facts(user=self.participant, review_type="CRM_ORDER_REVIEW", source_record_id=self.source.pk)
        self.assertTrue(facts["authorization"]["view"]["executable"])
        self.assertTrue(facts["authorization"]["ownOpinion"]["executable"])
        self.assertTrue(facts["authorization"]["sign"]["executable"])
        self.assertFalse(facts["authorization"]["fullDraftEdit"]["executable"])
        self.assertFalse(facts["authorization"]["submit"]["executable"])
        self.assertFalse(AuthorizationService.decide(
            user=self.participant, action_code="sales.order.update",
            organization_id=self.company.pk, business_object={"companyId": self.company.pk},
        )["allowed"])

        payload_rows = [dict(row) for row in facts["review"]["draftItems"]]
        payload_rows[0]["decision"] = "DISAGREE"
        payload_rows[0]["disagreementReasonCode"] = "条件未落实"
        saved = save_draft(user=self.participant, review_type="CRM_ORDER_REVIEW",
            source_record_id=self.source.pk, idempotency_key="participant-own-opinion",
            data={"reviewId": review.pk, "expectedSourceVersion": "R1",
                "expectedContentHash": "b" * 64, "expectedTemplateVersion": "V1.0",
                "items": payload_rows})
        own = saved["review"]["draftItems"][0]
        self.assertEqual(own["decision"], "DISAGREE")

        payload_rows = [dict(row) for row in saved["review"]["draftItems"]]
        payload_rows[1]["decision"] = "DISAGREE"
        payload_rows[1]["disagreementReasonCode"] = "风险不可接受"
        with self.assertRaises(ReviewBusinessError) as denied:
            save_draft(user=self.participant, review_type="CRM_ORDER_REVIEW",
                source_record_id=self.source.pk, idempotency_key="participant-other-opinion",
                data={"reviewId": review.pk, "expectedSourceVersion": "R1",
                    "expectedContentHash": "b" * 64, "expectedTemplateVersion": "V1.0",
                    "items": payload_rows})
        self.assertEqual(denied.exception.code, "OWN_OPINION_SCOPE_DENIED")

        sign_payload = {"reviewId": review.pk, "itemIds": [own["id"]],
            "expectedSourceVersion": "R1", "expectedContentHash": "b" * 64,
            "expectedTemplateVersion": "V1.0"}
        sign_items(user=self.participant, review_type="CRM_ORDER_REVIEW", source_record_id=self.source.pk, data=sign_payload)
        sign_items(user=self.participant, review_type="CRM_ORDER_REVIEW", source_record_id=self.source.pk, data=sign_payload)
        self.assertEqual(OrderReviewItemAudit.objects.filter(action="ITEM_SIGN", actor=self.participant).count(), 1)
        with self.assertRaises(ReviewBusinessError) as submit_denied:
            submit_review(user=self.participant, review_type="CRM_ORDER_REVIEW", source_record_id=self.source.pk, data=sign_payload)
        self.assertEqual(submit_denied.exception.code, "SUBMIT_PERMISSION_DENIED")

    def test_object_grant_does_not_open_an_unrelated_review_object(self):
        self.assign_participant_role()
        rows = self.rows("CRM_ORDER_REVIEW")
        rows[0]["responsibleEmployeeId"] = self.participant_employee.pk
        result = self.save(rows, "CRM_ORDER_REVIEW")
        review = OrderCrossFunctionalReview.objects.get(pk=result["review"]["draft"]["id"])
        OrderReviewParticipantGrant.objects.create(
            review=review, company=self.company, employee=self.participant_employee,
            user=self.participant, review_version_snapshot=review.review_version,
            source_version_snapshot=review.source_version, reason="隔离测试对象级授权",
            created_by=self.user, audit_hash="e" * 64,
        )
        unrelated = EngineeringSourceRecord.objects.create(
            company=self.company, source_no="UNRELATED-REVIEW", source_name="范围外来源",
            source_type="controlled_import", source_version="R2", content_hash="c" * 64,
            status="confirmed", source_payload={"businessOrderReference": {"sourceOrderNo": "OUT-1"}},
        )
        with self.assertRaises(ReviewBusinessError) as denied:
            build_review_facts(user=self.participant, review_type="CRM_ORDER_REVIEW", source_record_id=unrelated.pk)
        self.assertEqual(denied.exception.code, "REVIEW_OBJECT_ACCESS_REQUIRED")

    def test_object_grant_without_role_is_denied_and_role_revocation_closes_access(self):
        rows = self.rows("CRM_ORDER_REVIEW")
        rows[0]["responsibleEmployeeId"] = self.participant_employee.pk
        result = self.save(rows, "CRM_ORDER_REVIEW")
        review = OrderCrossFunctionalReview.objects.get(pk=result["review"]["draft"]["id"])
        OrderReviewParticipantGrant.objects.create(
            review=review, company=self.company, employee=self.participant_employee,
            user=self.participant, review_version_snapshot=review.review_version,
            source_version_snapshot=review.source_version, reason="隔离测试双重门禁",
            created_by=self.user, audit_hash="f" * 64,
        )
        with self.assertRaises(ReviewBusinessError) as denied:
            build_review_facts(user=self.participant, review_type="CRM_ORDER_REVIEW", source_record_id=self.source.pk)
        self.assertEqual(denied.exception.code, "VIEW_PERMISSION_DENIED")

        assignment = self.assign_participant_role()
        facts = build_review_facts(user=self.participant, review_type="CRM_ORDER_REVIEW", source_record_id=self.source.pk)
        self.assertTrue(facts["authorization"]["view"]["executable"])
        self.assertFalse(facts["authorization"]["submit"]["executable"])

        assignment.active = False
        assignment.save(update_fields=["active"])
        with self.assertRaises(ReviewBusinessError) as revoked:
            build_review_facts(user=self.participant, review_type="CRM_ORDER_REVIEW", source_record_id=self.source.pk)
        self.assertEqual(revoked.exception.code, "VIEW_PERMISSION_DENIED")

    def test_both_review_modules_require_live_role_and_object_grant(self):
        for review_type in ("CRM_ORDER_REVIEW", "PDE_PRODUCTION_FEASIBILITY"):
            with self.subTest(review_type=review_type):
                if review_type == "PDE_PRODUCTION_FEASIBILITY":
                    RolePermission.objects.get_or_create(
                        role=Role.objects.get(code="pde_production_feasibility_review_participant"),
                        permission=Permission.objects.get(
                            code="pde.production_feasibility_review.item.01",
                        ),
                    )
                    assignment = self.assign_participant_role(review_type)
                else:
                    assignment = None
                rows = self.rows(review_type)
                rows[0]["responsibleEmployeeId"] = self.participant_employee.pk
                result = self.save(rows, review_type)
                review = OrderCrossFunctionalReview.objects.get(
                    pk=result["review"]["draft"]["id"],
                )
                grant, _ = OrderReviewParticipantGrant.objects.get_or_create(
                    review=review, employee=self.participant_employee, user=self.participant,
                    defaults={
                        "company": self.company,
                        "review_version_snapshot": review.review_version,
                        "source_version_snapshot": review.source_version,
                        "reason": f"隔离测试{review_type}对象授权", "created_by": self.user,
                        "audit_hash": ("1" if review_type == "CRM_ORDER_REVIEW" else "2") * 64,
                    },
                )
                assignment = assignment or self.assign_participant_role(review_type)

                allowed = build_review_facts(
                    user=self.participant, review_type=review_type,
                    source_record_id=self.source.pk,
                )
                self.assertTrue(allowed["authorization"]["view"]["executable"])
                self.assertTrue(allowed["authorization"]["ownOpinion"]["executable"])
                self.assertTrue(allowed["authorization"]["sign"]["executable"])
                self.assertFalse(allowed["authorization"]["submit"]["executable"])

                assignment.active = False
                assignment.save(update_fields=["active"])
                with self.assertRaises(ReviewBusinessError) as role_revoked:
                    build_review_facts(
                        user=self.participant, review_type=review_type,
                        source_record_id=self.source.pk,
                    )
                self.assertEqual(role_revoked.exception.code, "VIEW_PERMISSION_DENIED")

                assignment.active = True
                assignment.save(update_fields=["active"])
                grant.active = False
                grant.save(update_fields=["active"])
                with self.assertRaises(ReviewBusinessError) as object_revoked:
                    build_review_facts(
                        user=self.participant, review_type=review_type,
                        source_record_id=self.source.pk,
                    )
                self.assertEqual(object_revoked.exception.code, "REVIEW_OBJECT_ACCESS_REQUIRED")

    def test_participant_role_convergence_is_additive_idempotent_and_password_safe(self):
        rows = self.rows("CRM_ORDER_REVIEW")
        rows[0]["responsibleEmployeeId"] = self.participant_employee.pk
        result = self.save(rows, "CRM_ORDER_REVIEW")
        review = OrderCrossFunctionalReview.objects.get(pk=result["review"]["draft"]["id"])
        OrderReviewParticipantGrant.objects.create(
            review=review, company=self.company, employee=self.participant_employee,
            user=self.participant, review_version_snapshot=review.review_version,
            source_version_snapshot=review.source_version, reason="隔离测试归口",
            created_by=self.user, audit_hash="a" * 64,
        )
        password_before = self.participant.password
        first = converge_active_review_participant_roles(actor=self.user, reason="隔离测试首次归口")
        second = converge_active_review_participant_roles(actor=self.user, reason="隔离测试幂等重放")
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.password, password_before)
        self.assertEqual(len(first["createdAssignmentIds"]), 1)
        self.assertEqual(second["createdAssignmentIds"], [])
        self.assertEqual(len(second["unchangedAssignmentIds"]), 1)
        self.assertEqual(UserRoleScopeAssignment.objects.filter(
            user=self.participant, role__code="crm_order_review_participant", active=True,
        ).count(), 1)
        self.assertEqual(OrganizationOperatingAuditRecord.objects.filter(
            action_code="CONVERGE_REVIEW_PARTICIPANT_ROLE",
        ).count(), 1)

    def _submit_crm_for_final_approval(self, *, disagreement=False):
        ensure_order_review_approval_configuration()
        rows = self.rows("CRM_ORDER_REVIEW")
        rows.append({
            "stableKey": "OTHER-CRM-TEST", "itemKind": "OTHER", "itemText": "补充商业风险评审",
            "evidenceNote": "隔离测试依据", "decision": "AGREE",
            "responsibleEmployeeId": self.employee.pk,
        })
        if disagreement:
            for row in rows[:2]:
                row["decision"] = "DISAGREE"
                row["disagreementReasonCode"] = "风险不可接受"
        result = self.save(rows, "CRM_ORDER_REVIEW")
        review_id = result["review"]["draft"]["id"]
        item_ids = [row["id"] for row in result["review"]["draftItems"]]
        sign_items(user=self.user, review_type="CRM_ORDER_REVIEW", source_record_id=self.source.pk,
            data={"reviewId": review_id, "itemIds": item_ids, "expectedSourceVersion": "R1",
                "expectedContentHash": "b" * 64, "expectedTemplateVersion": "V1.0"})
        return submit_review(user=self.user, review_type="CRM_ORDER_REVIEW", source_record_id=self.source.pk,
            data={"reviewId": review_id, "expectedSourceVersion": "R1",
                "expectedContentHash": "b" * 64, "expectedTemplateVersion": "V1.0"})

    def _approval_user(self):
        approver = User.objects.create_user(
            username="order_final_approver", password="unused", real_name="订单审批人",
            company_id=self.company.pk,
        )
        UserRoleScopeAssignment.objects.create(
            user=approver, role=Role.objects.get(code="crm_order_review_final_approver"),
            organization=self.company, scope_code="ORGANIZATION", active=True,
            business_hash="order-final-approver-test",
        )
        return approver

    def test_crm_disagreement_submission_is_pending_not_auto_rejected_and_items_remain_visible(self):
        result = self._submit_crm_for_final_approval(disagreement=True)
        review = OrderCrossFunctionalReview.objects.get(review_type="CRM_ORDER_REVIEW")
        self.assertEqual(review.conclusion, "")
        self.assertEqual(result["approval"]["statusCode"], "PENDING_APPROVER_CONFIGURATION")
        self.assertIsNone(result["approval"]["finalDecision"])
        self.assertEqual(len(result["review"]["submittedItems"]), 9)
        self.assertEqual(len(result["review"]["displayItems"]), 9)
        self.assertEqual(WorkflowInstance.objects.filter(document_id=review.pk).count(), 1)
        self.assertEqual(ApprovalTask.objects.filter(workflow_instance__document_id=review.pk).count(), 1)

    def test_crm_all_agree_submission_still_waits_for_approval(self):
        result = self._submit_crm_for_final_approval(disagreement=False)
        self.assertEqual(result["review"]["latest"]["conclusion"], "")
        self.assertEqual(result["review"]["latest"]["conclusionLabel"], "尚无最终审批结论")
        self.assertEqual(ApprovalDecision.objects.count(), 0)

    def test_formal_approver_can_approve_disagreement_without_changing_opinions(self):
        submitted = self._submit_crm_for_final_approval(disagreement=True)
        approver = self._approval_user()
        latest = submitted["review"]["latest"]
        result = final_approve_review(
            user=approver, review_type="CRM_ORDER_REVIEW", source_record_id=self.source.pk,
            idempotency_key="approve-disagreement-idempotency",
            data={"reviewId": latest["id"], "expectedReviewVersion": latest["reviewVersion"],
                "expectedSourceVersion": latest["sourceVersion"], "decision": "APPROVE",
                "approvalOpinion": "在风险措施落实条件下同意。", "riskHandling": "列入交付风险清单并由销售跟踪。",
                "actionId": "approve-disagreement-action"},
        )
        self.assertEqual(result["approval"]["finalDecision"]["decision"], "APPROVE")
        self.assertEqual(OrderCrossFunctionalReview.objects.get(pk=latest["id"]).items.filter(decision="DISAGREE").count(), 2)
        self.assertEqual(ApprovalDecision.objects.count(), 1)

    def test_superuser_without_formal_approver_role_cannot_approve(self):
        submitted = self._submit_crm_for_final_approval()
        latest = submitted["review"]["latest"]
        with self.assertRaises(ReviewBusinessError) as denied:
            final_approve_review(
                user=self.user, review_type="CRM_ORDER_REVIEW", source_record_id=self.source.pk,
                idempotency_key="superuser-denied", data={"reviewId": latest["id"],
                    "expectedReviewVersion": latest["reviewVersion"], "expectedSourceVersion": latest["sourceVersion"],
                    "decision": "APPROVE", "approvalOpinion": "尝试审批", "riskHandling": "",
                    "actionId": "superuser-denied-action"},
            )
        self.assertEqual(denied.exception.code, "FINAL_APPROVAL_PERMISSION_DENIED")

    def test_formal_approver_can_reject_all_agree_with_recorded_risk_reason(self):
        submitted = self._submit_crm_for_final_approval()
        approver = self._approval_user()
        latest = submitted["review"]["latest"]
        result = final_approve_review(
            user=approver, review_type="CRM_ORDER_REVIEW", source_record_id=self.source.pk,
            idempotency_key="reject-all-agree-idempotency",
            data={"reviewId": latest["id"], "expectedReviewVersion": latest["reviewVersion"],
                "expectedSourceVersion": latest["sourceVersion"], "decision": "REJECT",
                "approvalOpinion": "综合风险仍不可接受。", "riskHandling": "补充商业条件后重新送审。",
                "actionId": "reject-all-agree-action"},
        )
        self.assertEqual(result["approval"]["finalDecision"]["decision"], "REJECT")
        self.assertEqual(OrderCrossFunctionalReview.objects.get(pk=latest["id"]).items.filter(decision="DISAGREE").count(), 0)

    def test_conflicting_final_decision_requires_risk_handling(self):
        submitted = self._submit_crm_for_final_approval(disagreement=True)
        approver = self._approval_user()
        latest = submitted["review"]["latest"]
        with self.assertRaises(ReviewBusinessError) as denied:
            final_approve_review(
                user=approver, review_type="CRM_ORDER_REVIEW", source_record_id=self.source.pk,
                idempotency_key="missing-risk-idempotency",
                data={"reviewId": latest["id"], "expectedReviewVersion": latest["reviewVersion"],
                    "expectedSourceVersion": latest["sourceVersion"], "decision": "APPROVE",
                    "approvalOpinion": "拟通过", "riskHandling": "", "actionId": "missing-risk-action"},
            )
        self.assertEqual(denied.exception.code, "RISK_HANDLING_REQUIRED")
        self.assertEqual(ApprovalDecision.objects.count(), 0)

    def test_final_approval_version_guard_idempotency_and_no_overwrite(self):
        submitted = self._submit_crm_for_final_approval()
        approver = self._approval_user()
        latest = submitted["review"]["latest"]
        base = {"reviewId": latest["id"], "expectedReviewVersion": latest["reviewVersion"],
            "expectedSourceVersion": latest["sourceVersion"], "decision": "APPROVE",
            "approvalOpinion": "同意。", "riskHandling": "", "actionId": "stable-approval-action"}
        with self.assertRaises(ReviewBusinessError) as mismatch:
            final_approve_review(user=approver, review_type="CRM_ORDER_REVIEW", source_record_id=self.source.pk,
                idempotency_key="mismatch", data={**base, "expectedReviewVersion": 999})
        self.assertEqual(mismatch.exception.code, "REVIEW_VERSION_MISMATCH")
        final_approve_review(user=approver, review_type="CRM_ORDER_REVIEW", source_record_id=self.source.pk,
            idempotency_key="stable-idempotency", data=base)
        final_approve_review(user=approver, review_type="CRM_ORDER_REVIEW", source_record_id=self.source.pk,
            idempotency_key="stable-idempotency", data=base)
        self.assertEqual(ApprovalDecision.objects.count(), 1)
        with self.assertRaises(ReviewBusinessError) as completed:
            final_approve_review(user=approver, review_type="CRM_ORDER_REVIEW", source_record_id=self.source.pk,
                idempotency_key="second-idempotency", data={**base, "decision": "REJECT", "actionId": "second-action"})
        self.assertEqual(completed.exception.code, "APPROVAL_ALREADY_COMPLETED")

    def test_pde_exact_current_submission_reconciliation_is_idempotent_and_has_no_decision(self):
        rows = self.rows("PDE_PRODUCTION_FEASIBILITY")
        result = self.save(rows, "PDE_PRODUCTION_FEASIBILITY")
        review_id = result["review"]["draft"]["id"]
        item_ids = [row["id"] for row in result["review"]["draftItems"]]
        sign_items(
            user=self.user, review_type="PDE_PRODUCTION_FEASIBILITY",
            source_record_id=self.source.pk,
            data={"reviewId": review_id, "itemIds": item_ids,
                "expectedSourceVersion": "R1", "expectedContentHash": "b" * 64,
                "expectedTemplateVersion": "V1.0"},
        )
        submit_review(
            user=self.user, review_type="PDE_PRODUCTION_FEASIBILITY",
            source_record_id=self.source.pk,
            data={"reviewId": review_id, "expectedSourceVersion": "R1",
                "expectedContentHash": "b" * 64, "expectedTemplateVersion": "V1.0"},
        )
        review = OrderCrossFunctionalReview.objects.get(pk=review_id)
        workflow_query = WorkflowInstance.objects.filter(
            document_type="PDEProductionFeasibilityReview", document_id=review.pk,
        )
        BusinessStateTransition.objects.filter(workflow_instance__in=workflow_query).delete()
        ApprovalTask.objects.filter(workflow_instance__in=workflow_query).delete()
        workflow_query.delete()
        OrderCrossFunctionalReview.objects.filter(pk=review.pk).update(conclusion="ACCEPT")
        review.refresh_from_db()
        arguments = {
            "review": review, "actor": self.user, "reason": "精确授权隔离测试",
            "expected_review_type": "PDE_PRODUCTION_FEASIBILITY",
            "expected_review_version": review.review_version,
            "expected_source_order_no": review.source_order_no,
            "expected_source_version": review.source_version,
            "authorization_audit_id": 999,
        }
        created = reconcile_legacy_submitted_review(**arguments)
        reused = reconcile_legacy_submitted_review(**arguments)
        self.assertEqual(created["mode"], "CREATED_PENDING_RELATION")
        self.assertEqual(reused["mode"], "IDEMPOTENT_REUSE")
        self.assertEqual(WorkflowInstance.objects.filter(document_id=review.pk).count(), 1)
        self.assertEqual(ApprovalTask.objects.filter(workflow_instance__document_id=review.pk).count(), 1)
        self.assertEqual(ApprovalDecision.objects.filter(task__workflow_instance__document_id=review.pk).count(), 0)
        self.assertEqual(OrderReviewItemAudit.objects.filter(
            review=review, action="APPROVAL_RELATION_CONTINUED",
        ).count(), 1)

    def test_pde_reconciliation_rejects_imprecise_target(self):
        review = OrderCrossFunctionalReview.objects.create(
            company=self.company, source_record=self.source, source_order_no="I-1",
            source_version="R1", review_type="PDE_PRODUCTION_FEASIBILITY",
            review_version=2, template_version="V1.0", reviewer=self.user,
            record_status="SUBMITTED", conclusion="ACCEPT",
        )
        with self.assertRaises(OrderReviewApprovalError) as denied:
            reconcile_legacy_submitted_review(
                review=review, actor=self.user, reason="错误版本测试",
                expected_review_type="PDE_PRODUCTION_FEASIBILITY",
                expected_review_version=1, expected_source_order_no="I-1",
                expected_source_version="R1", authorization_audit_id=999,
            )
        self.assertEqual(denied.exception.code, "RECONCILIATION_TARGET_MISMATCH")
        self.assertEqual(WorkflowInstance.objects.filter(document_id=review.pk).count(), 0)

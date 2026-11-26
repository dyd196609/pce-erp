"""Strict read-only gate for CALC-3 RoutingVersion 43 dedicated release."""

import inspect
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pce_backend.settings")

import django  # noqa: E402

django.setup()

from masterdata.models import MasterDataWriteRequest  # noqa: E402
from pde.models import RoutingVersion  # noqa: E402
from pde.production_foundation_service import EngineeringLifecycleService  # noqa: E402
from pde.routing_version_release_service import (  # noqa: E402
    RELEASE_ACTION,
    RELEASE_PERMISSION,
    REQUIRED_RESPONSIBILITY_CODE,
    eligible_release_actors,
    project_release_preflight,
    release_routing_version,
)
from pde.routing_version_review_service import review_readback  # noqa: E402
from system.models import (  # noqa: E402
    OrganizationOperatingAuditRecord,
    Permission,
    PositionResponsibility,
    Responsibility,
    RolePermission,
    User,
    UserRoleScopeAssignment,
)
from workflow_runtime.models import ApprovalDecision, BusinessStateTransition  # noqa: E402


def check(name, condition, evidence):
    return {"name": name, "status": "PASS" if condition else "FAIL", "evidence": evidence}


def main():
    version = RoutingVersion.objects.select_related("routing__company").get(pk=43)
    current_user = User.objects.get(username="pce_emp104")
    admin = User.objects.filter(is_superuser=True).order_by("pk").first()
    generic_user = User.objects.filter(username="pce_plan_r12").first()
    preflight = project_release_preflight(version, current_user)
    review = review_readback(version)
    release_roles = list(
        RolePermission.objects.filter(permission__code=RELEASE_PERMISSION)
        .values_list("role__code", flat=True)
    )
    responsibility_positions = list(
        PositionResponsibility.objects.filter(
            responsibility__code=REQUIRED_RESPONSIBILITY_CODE,
            active=True,
        ).values_list("position__code", flat=True)
    )
    release_source = inspect.getsource(release_routing_version)
    generic_source = inspect.getsource(EngineeringLifecycleService.transition)
    component = (
        ROOT / "frontend/src/meta/pages/components/RoutingVersionReadback.vue"
    ).read_text(encoding="utf-8")
    api = (ROOT / "frontend/src/api/pde.js").read_text(encoding="utf-8")
    checks = [
        check(
            "01_identity",
            version.pk == 43 and version.routing_id == 31
            and version.routing.routing_code == "QSFB/FM"
            and version.routing_version == "V2.0" and version.revision == 2,
            f"Routing {version.routing_id} / RoutingVersion {version.pk} / {version.routing_version} / Rev{version.revision}",
        ),
        check(
            "02_formal_state_unchanged",
            version.status == "reviewed" and version.approval_state == "workflow_approved",
            f"{version.status}/{version.approval_state}",
        ),
        check("03_steps_preserved", version.steps.count() == 28, version.steps.count()),
        check(
            "04_review_preserved",
            review["completed"] and review["workflowInstanceId"] == 6
            and review["decisionId"] == 6 and review["actorUsername"] == "pce_emp104",
            review,
        ),
        check(
            "05_dedicated_permission_catalog",
            Permission.objects.filter(code=RELEASE_PERMISSION).count() == 1,
            RELEASE_PERMISSION,
        ),
        check(
            "06_no_implicit_role_grant",
            not release_roles,
            {"releaseRoleCodes": release_roles},
        ),
        check(
            "07_no_implicit_responsibility_appointment",
            not Responsibility.objects.filter(code=REQUIRED_RESPONSIBILITY_CODE).exists()
            and not responsibility_positions,
            {"responsibilityCode": REQUIRED_RESPONSIBILITY_CODE, "positionCodes": responsibility_positions},
        ),
        check(
            "08_no_eligible_publisher_yet",
            eligible_release_actors(version.routing.company_id, version.pk) == [],
            preflight["eligibleReleaseActors"],
        ),
        check(
            "09_current_reviewer_not_auto_publisher",
            not preflight["currentActor"] and not preflight["releaseAllowed"],
            {"currentActor": preflight["currentActor"], "releaseAllowed": preflight["releaseAllowed"]},
        ),
        check(
            "10_human_authorization_blocker",
            preflight["decisionCode"] == "HUMAN_PUBLISHER_AUTHORIZATION_REQUIRED"
            and preflight["humanPublisherAuthorizationRequired"],
            {"decisionCode": preflight["decisionCode"], "firstBlocker": preflight["firstBlockerCode"]},
        ),
        check(
            "11_review_content_current",
            preflight["contentIntegrity"]["valid"]
            and preflight["completeness"]["complete"],
            preflight["contentIntegrity"],
        ),
        check(
            "12_generic_permission_not_dedicated",
            bool(generic_user)
            and not any(row["userId"] == generic_user.pk for row in preflight["eligibleReleaseActors"]),
            generic_user.username if generic_user else "missing",
        ),
        check(
            "13_admin_cannot_bypass",
            bool(admin)
            and not any(row["userId"] == admin.pk for row in preflight["eligibleReleaseActors"]),
            admin.username if admin else "missing",
        ),
        check(
            "14_transaction_and_concurrency_guard",
            "@transaction.atomic" in release_source
            and "RoutingVersion.objects.select_for_update()" in release_source
            and "BusinessStateTransition.objects.select_for_update()" in release_source,
            "atomic + RoutingVersion row lock + release-fact lock",
        ),
        check(
            "15_generic_release_block_preserved",
            "ROUTING_VERSION_DEDICATED_CONTROL_REQUIRED" in generic_source,
            "generic lifecycle still rejects RoutingVersion release",
        ),
        check(
            "16_no_release_fact_created",
            not BusinessStateTransition.objects.filter(
                object_type="RoutingVersion", object_id=43, action_code=RELEASE_ACTION,
            ).exists()
            and not MasterDataWriteRequest.objects.filter(
                action_code=RELEASE_ACTION, target_entity_id="43",
            ).exists()
            and not OrganizationOperatingAuditRecord.objects.filter(
                action_code=RELEASE_ACTION, target_id=43,
            ).exists(),
            "transition/request/audit = 0",
        ),
        check(
            "17_review_decision_not_duplicated",
            ApprovalDecision.objects.filter(
                task__workflow_instance_id=6,
                action_id="pde.routing_version.review",
            ).count() == 1,
            "WorkflowInstance 6 review decisions = 1",
        ),
        check(
            "18_history_preserved",
            RoutingVersion.objects.filter(pk=31, status="released").count() == 1,
            "RoutingVersion 31 remains released",
        ),
        check(
            "19_page_contract",
            "routing-version-formal-release" in component
            and "正式评审与正式发布是两个不同业务动作" in component
            and "!version.releasePreflight.releaseAllowed" in component
            and "/api/pde/routing-versions/${versionId}/release/" in api,
            "existing detail page exposes a disabled dedicated release action",
        ),
    ]
    failed = [row for row in checks if row["status"] != "PASS"]
    result = {
        "gate": "PDE-CALC3-ROUTING-VERSION-DEDICATED-RELEASE",
        "status": "PASS" if not failed else "FAIL",
        "technicalState": "TECHNICAL READY" if not failed else "BLOCKED",
        "businessDecision": preflight["decisionCode"],
        "releaseExecuted": False,
        "checks": checks,
        "preflight": preflight,
        "releasePermissionRoleCount": len(release_roles),
        "publisherAssignmentCount": UserRoleScopeAssignment.objects.filter(
            role__rolepermission__permission__code=RELEASE_PERMISSION,
            organization_id=version.routing.company_id,
            active=True,
        ).distinct().count(),
        "databaseBusinessWriteCount": 0,
    }
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

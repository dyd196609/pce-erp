import hashlib
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from sales.new_order_source import ACTION, CONFIRM_ACTION, DEPARTMENT, REGISTER_SCOPE_ACTION
from sales.services import PROCESS_CODE
from system.models import (
    Company, Department, Permission, Position, PositionWorkflowResponsibility,
    Responsibility, Role, RolePermission, User, UserRoleScopeAssignment,
)
from workflow_runtime.models import ProcessDefinition, WorkflowNodeDefinition


class Command(BaseCommand):
    help = "Register the CRM source action for the isolated sales acceptance account."

    def add_arguments(self, parser):
        parser.add_argument("--isolated-db", required=True, type=Path)
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--confirmation", action="store_true")
        mode.add_argument("--formal-scope", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        expected = options["isolated_db"]
        configured = os.environ.get("PCE_DATABASE_PATH")
        if not expected.is_absolute() or not expected.is_file() or not configured:
            raise CommandError("Specify an existing absolute isolated database path explicitly.")
        expected = expected.resolve()
        daily = (Path(settings.BASE_DIR) / "db.sqlite3").resolve()
        if daily.exists() and expected.samefile(daily):
            raise CommandError("The daily database cannot be used.")
        if connection.vendor != "sqlite" or Path(configured).resolve() != expected:
            raise CommandError("The configured SQLite database differs from --isolated-db.")
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA database_list")
            opened = next(Path(row[2]).resolve() for row in cursor.fetchall() if row[1] == "main")
        if opened != expected:
            raise CommandError("SQLite opened a different database.")

        scope = options["formal_scope"]
        confirm = options["confirmation"] or scope
        original = Path(settings.BASE_DIR).parent / "work" / "crm-source-browser-14.sqlite3"
        if confirm and (not expected.is_relative_to(original.parent.resolve())
                        or (original.exists() and expected.samefile(original))):
            raise CommandError("Confirmation registration requires a separate work database.")
        action = CONFIRM_ACTION if confirm else ACTION
        position_code = "YXB-MGR" if confirm else "YXB-SALES"
        username = "pce_review_emp110" if confirm else "pce_sales_r13"
        role_code = "crm_source_confirmation" if confirm else "crm_source_acceptance"
        label = "确认标准新单来源" if confirm else "新建接单来源"
        if scope:
            action, role_code, label = REGISTER_SCOPE_ACTION, "crm_source_formal_scope", "登记正式订单行范围"
            if expected.name != "crm-formal-scope-verify.sqlite3":
                raise CommandError("Formal scope registration requires its verification database.")
        company = Company.objects.get(pk=1, code="COMP001")
        department = Department.objects.get(pk=DEPARTMENT, company=company)
        position = Position.objects.get(code=position_code, department=department, is_active=True)
        user = User.objects.get(username=username, company_id=company.pk, is_active=True)
        employee = getattr(user, "employee_profile", None)
        if (employee is None or employee.status != "active" or
                employee.position_ref_id != position.pk or employee.department_ref_id != department.pk):
            raise CommandError("The acceptance account does not hold the expected active sales position.")

        if not UserRoleScopeAssignment.objects.filter(user=user, active=True).exclude(role__code=role_code).exists():
            raise CommandError("Adding a formal grant would change the account's legacy authorization source.")

        permission, _ = Permission.objects.get_or_create(
            code=action, defaults={"name": label, "module": "SALES"},
        )
        role, _ = Role.objects.get_or_create(
            code=role_code, defaults={"name": label},
        )
        grants = UserRoleScopeAssignment.objects.filter(role=role)
        if grants.exclude(user=user, organization=company, department=department, scope_code="DEPARTMENT", active=True).exists():
            raise CommandError("The dedicated role already has an unexpected holder or scope.")
        if RolePermission.objects.filter(role=role).exclude(permission=permission).exists():
            raise CommandError("The dedicated role already contains an unexpected permission.")
        if RolePermission.objects.filter(permission=permission).exclude(role=role).exists():
            raise CommandError("The dedicated permission is already granted to another role.")
        RolePermission.objects.get_or_create(role=role, permission=permission)
        grants.get_or_create(
            role=role, user=user, organization=company,
            defaults={
                "department": department, "scope_code": "DEPARTMENT",
                "business_hash": hashlib.sha256(
                    f"{user.pk}:{role.pk}:{company.pk}:{department.pk}:DEPARTMENT".encode()
                ).hexdigest(),
            },
        )
        process = ProcessDefinition.objects.get(definition_code=PROCESS_CODE, active=True)
        node, _ = WorkflowNodeDefinition.objects.get_or_create(
            process_definition=process, node_code="REGISTER_ORDER_SOURCE_SCOPE" if scope else ("CONFIRM_ORDER_SOURCE" if confirm else "CREATE_ORDER_SOURCE"),
            defaults={"node_name": label, "sequence": 7 if scope else (6 if confirm else 5), "business_action_code": action},
        )
        if not node.active or node.business_action_code != action:
            raise CommandError("The existing source node does not match the dedicated action.")
        responsibility = Responsibility.objects.get(code="RESP_SALES_ORDER_002", is_active=True)
        mapping, _ = PositionWorkflowResponsibility.objects.get_or_create(
            position=position, workflow_code=PROCESS_CODE, node_code=node.node_code,
            ownership_type="OWNER",
            defaults={"responsibility": responsibility, "workflow_node": node, "active": True},
        )
        if not mapping.active or mapping.responsibility_id != responsibility.pk or mapping.workflow_node_id != node.pk:
            raise CommandError("The existing position mapping does not match the dedicated node.")
        self.stdout.write(f"{opened} | {company.code}/{department.pk}/{position.code} | {user.username} | {action}")

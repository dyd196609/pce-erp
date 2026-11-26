import hashlib
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from pfm.models import Employee
from system.models import Company, Department, Position, Role, User
from workflow_runtime.models import UserOrganizationRoleAuthority


def authority_hash(payload):
    value = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class Command(BaseCommand):
    help = "Create or refresh governed development accounts for ERP access-control acceptance."

    def add_arguments(self, parser):
        parser.add_argument("--buyer-password")
        parser.add_argument("--direct-password")
        parser.add_argument("--cleanup", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["cleanup"]:
            self._cleanup()
            return
        if not options["buyer_password"] or not options["direct_password"]:
            raise CommandError("Both governed test-account passwords are required.")

        company = Company.objects.filter(is_active=True).order_by("pk").first()
        if company is None:
            raise CommandError("No active Company exists.")
        department = Department.objects.filter(
            company=company, name="采购部", is_active=True,
        ).order_by("pk").first()
        if department is None:
            raise CommandError("No active 采购部 exists in the selected Company.")

        buyer_position = Position.objects.filter(
            company=company, department=department, name="采购员", is_active=True,
        ).order_by("pk").first()
        direct_position = Position.objects.filter(
            company=company, department=department, name__in=["采购主管", "采购经理"], is_active=True,
        ).order_by("pk").first()
        if buyer_position is None or direct_position is None:
            raise CommandError("采购员及采购主管/采购经理正式岗位必须存在。")

        buyer_role = Role.objects.get(code="buyer")
        direct_role = Role.objects.get(code="direct_purchase_authorized")
        buyer = self._ensure_identity(
            username="pce_buyer_r10",
            password=options["buyer_password"],
            employee_no="EMP-R10-BUYER",
            full_name="权限测试普通采购员",
            company=company,
            department=department,
            position=buyer_position,
        )
        direct = self._ensure_identity(
            username="pce_direct_r10",
            password=options["direct_password"],
            employee_no="EMP-R10-DIRECT",
            full_name="权限测试直接采购授权人员",
            company=company,
            department=department,
            position=direct_position,
        )
        self._set_authority(buyer, buyer_role, company.pk, "SELF")
        self._set_authority(direct, direct_role, company.pk, "")
        self.stdout.write(self.style.SUCCESS(
            "ERP access test identities ready: ordinary buyer and direct-purchase authorized user."
        ))

    def _ensure_identity(self, *, username, password, employee_no, full_name,
                         company, department, position):
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={"real_name": full_name, "company_id": company.pk},
        )
        user.real_name = full_name
        user.company_id = company.pk
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.set_password(password)
        user.save()
        employee, _ = Employee.objects.get_or_create(
            employee_no=employee_no,
            defaults={"full_name": full_name},
        )
        employee.full_name = full_name
        employee.status = "active"
        employee.department_ref = department
        employee.position_ref = position
        employee.department_id = department.pk
        employee.department_name = department.name
        employee.position = position.name
        employee.user = user
        employee.save()
        return user

    def _set_authority(self, user, role, legal_entity_id, department_marker):
        UserOrganizationRoleAuthority.objects.filter(user=user).delete()
        payload = {
            "userId": user.pk,
            "roleCode": role.code,
            "legalEntityId": str(legal_entity_id),
            "departmentId": department_marker,
            "scopeCode": "SELF" if department_marker == "SELF" else "ORGANIZATION",
            "version": 1,
        }
        UserOrganizationRoleAuthority.objects.create(
            user=user,
            role_code=role.code,
            legal_entity_id=str(legal_entity_id),
            department_id=department_marker,
            active=True,
            version=1,
            business_hash=authority_hash(payload),
        )

    def _cleanup(self):
        usernames = ["pce_buyer_r10", "pce_direct_r10"]
        users = list(User.objects.filter(username__in=usernames))
        UserOrganizationRoleAuthority.objects.filter(user__in=users).delete()
        Employee.objects.filter(employee_no__in=["EMP-R10-BUYER", "EMP-R10-DIRECT"]).delete()
        User.objects.filter(username__in=usernames).delete()
        self.stdout.write(self.style.SUCCESS("ERP access test identities removed."))

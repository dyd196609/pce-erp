import hashlib

from django.core.management.base import BaseCommand

from system.models import Permission, Role, RolePermission, User
from workflow_runtime.action_permissions import (
    ADMIN_ROLE,
    BANK_OPERATOR_ROLE,
    BATCH_OPERATOR_ROLE,
    OPERATOR_ROLE,
    VIEWER_ROLE,
    POLICIES,
)
from workflow_runtime.models import UserOrganizationRoleAuthority


class Command(BaseCommand):
    help = "Seed isolated V55.2 browser actors and authoritative permissions."

    def handle(self, *args, **options):
        role_specs = {
            VIEWER_ROLE: lambda policy: VIEWER_ROLE in policy.role,
            OPERATOR_ROLE: lambda policy: OPERATOR_ROLE in policy.role,
            BATCH_OPERATOR_ROLE: lambda policy: BATCH_OPERATOR_ROLE
            in policy.role,
            ADMIN_ROLE: lambda policy: ADMIN_ROLE in policy.role,
            BANK_OPERATOR_ROLE: lambda policy: (
                BANK_OPERATOR_ROLE in policy.role
            ),
        }
        roles = {}
        for role_code in role_specs:
            role, _ = Role.objects.update_or_create(
                code=role_code,
                defaults={
                    "name": role_code,
                    "description": "V55.2 isolated action permission authority",
                },
            )
            roles[role_code] = role

        permissions = {}
        for policy in POLICIES.values():
            permission, _ = Permission.objects.update_or_create(
                code=policy.requiredPermission,
                defaults={
                    "name": policy.actionCode,
                    "module": policy.moduleCode,
                },
            )
            permissions[policy.requiredPermission] = permission

        for role_code, selector in role_specs.items():
            role = roles[role_code]
            for policy in POLICIES.values():
                if selector(policy):
                    RolePermission.objects.get_or_create(
                        role=role,
                        permission=permissions[policy.requiredPermission],
                    )

        actors = {
            "v552-viewer": (VIEWER_ROLE, ("LEGAL-V45", "LEGAL-V45-B")),
            "v552-operator": (OPERATOR_ROLE, ("LEGAL-V45", "LEGAL-V45-B")),
            "v552-batch-operator": (
                BATCH_OPERATOR_ROLE,
                ("LEGAL-V45", "LEGAL-V45-B"),
            ),
            "v552-outscope": (BATCH_OPERATOR_ROLE, ("LEGAL-OTHER",)),
            "v59-bank-operator": (
                BANK_OPERATOR_ROLE,
                ("LEGAL-V45", "LEGAL-V45-B"),
            ),
        }
        for username, (role_code, legal_entity_ids) in actors.items():
            user, _ = User.objects.update_or_create(
                username=username,
                defaults={
                    "real_name": username,
                    "company_id": 1,
                    "is_active": True,
                    "is_staff": False,
                },
            )
            user.set_unusable_password()
            user.save(update_fields=["password"])
            for legal_entity_id in legal_entity_ids:
                digest = hashlib.sha256(
                    f"{username}|{role_code}|{legal_entity_id}|V55.2".encode()
                ).hexdigest()
                UserOrganizationRoleAuthority.objects.update_or_create(
                    user=user,
                    role_code=role_code,
                    legal_entity_id=legal_entity_id,
                    defaults={
                        "department_id": "FINANCE",
                        "active": True,
                        "version": 1,
                        "business_hash": digest,
                    },
                )

        self.stdout.write(
            self.style.SUCCESS(
                "V55.2 isolated role authorities ready: "
                "viewer/operator/batch-operator/outscope"
            )
        )

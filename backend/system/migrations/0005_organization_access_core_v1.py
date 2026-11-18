import hashlib
import json

import django.db.models.deletion
from django.db import migrations, models


ACTION_CODE = "system.organization_directory.view"


def _business_hash(payload):
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def seed_access_core_v1(apps, schema_editor):
    Company = apps.get_model("system", "Company")
    Department = apps.get_model("system", "Department")
    Permission = apps.get_model("system", "Permission")
    Role = apps.get_model("system", "Role")
    RolePermission = apps.get_model("system", "RolePermission")
    Assignment = apps.get_model("system", "UserRoleScopeAssignment")
    LegacyAuthority = apps.get_model(
        "workflow_runtime", "UserOrganizationRoleAuthority"
    )

    permission, _ = Permission.objects.update_or_create(
        code=ACTION_CODE,
        defaults={"name": "组织目录查看", "module": "SYSTEM"},
    )
    for role in Role.objects.filter(
        code__in=("superadmin", "buyer", "direct_purchase_authorized")
    ):
        RolePermission.objects.get_or_create(role=role, permission=permission)

    for legacy in LegacyAuthority.objects.filter(active=True).iterator():
        role = Role.objects.filter(code=legacy.role_code).first()
        if role is None:
            continue
        organization_id = str(legacy.legal_entity_id or "").strip()
        organization = Company.objects.filter(pk=organization_id).first()
        if organization is None:
            organization = Company.objects.filter(pk=legacy.user.company_id).first()
        if organization is None:
            continue

        marker = str(legacy.department_id or "").strip()
        department = None
        if marker == "SELF":
            scope_code = "SELF"
        elif marker == "ALL":
            scope_code = "ALL"
        elif marker:
            department = Department.objects.filter(
                pk=marker,
                company=organization,
            ).first()
            scope_code = "DEPARTMENT" if department else "ORGANIZATION"
        else:
            scope_code = "ORGANIZATION"
        payload = {
            "userId": legacy.user_id,
            "roleCode": role.code,
            "organizationId": organization.pk,
            "departmentId": department.pk if department else None,
            "scopeCode": scope_code,
            "version": max(int(legacy.version or 1), 1),
        }
        Assignment.objects.update_or_create(
            user_id=legacy.user_id,
            role=role,
            organization=organization,
            defaults={
                "department": department,
                "scope_code": scope_code,
                "active": True,
                "version": payload["version"],
                "business_hash": _business_hash(payload),
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("system", "0004_erp_access_foundation"),
        ("workflow_runtime", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserRoleScopeAssignment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "scope_code",
                    models.CharField(
                        choices=[
                            ("SELF", "本人"),
                            ("DEPARTMENT", "本部门"),
                            ("ORGANIZATION", "本组织"),
                            ("ALL", "全部"),
                            ("CUSTOM", "自定义（预留）"),
                        ],
                        default="ORGANIZATION",
                        max_length=20,
                        verbose_name="数据范围",
                    ),
                ),
                ("active", models.BooleanField(default=True, verbose_name="是否启用")),
                ("version", models.PositiveIntegerField(default=1, verbose_name="版本")),
                ("business_hash", models.CharField(max_length=64, verbose_name="业务哈希")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="user_role_scope_assignments",
                        to="system.department",
                        verbose_name="授权部门",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="user_role_scope_assignments",
                        to="system.company",
                        verbose_name="授权组织",
                    ),
                ),
                (
                    "role",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="user_scope_assignments",
                        to="system.role",
                        verbose_name="系统角色",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="role_scope_assignments",
                        to="system.user",
                        verbose_name="登录账户",
                    ),
                ),
            ],
            options={
                "verbose_name": "用户角色数据范围",
                "verbose_name_plural": "用户角色数据范围",
                "db_table": "system_user_role_scope_assignments",
            },
        ),
        migrations.AddConstraint(
            model_name="userrolescopeassignment",
            constraint=models.UniqueConstraint(
                fields=("user", "role", "organization"),
                name="uniq_system_user_role_organization_scope",
            ),
        ),
        migrations.AddConstraint(
            model_name="userrolescopeassignment",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(scope_code="DEPARTMENT", department__isnull=False)
                    | ~models.Q(scope_code="DEPARTMENT")
                ),
                name="system_department_scope_requires_department",
            ),
        ),
        migrations.RunPython(seed_access_core_v1, migrations.RunPython.noop),
    ]

from django.db.models import Count, Q

from .models import (
    Department,
    OrganizationOperatingAuditRecord,
    Position,
    PositionResponsibility,
    Responsibility,
)


RESPONSIBILITY_CATALOG_CONTRACT = "PCE-RESPONSIBILITY-CATALOG-V1"
RESPONSIBILITY_FACT_SOURCE = "system.Responsibility"


def _date(value):
    return value.isoformat() if value else None


def _audit_time(value):
    return value.isoformat() if value else None


class ResponsibilityCatalogService:
    """Read-only projection whose root fact is always system.Responsibility."""

    @classmethod
    def list(cls):
        rows = Responsibility.objects.annotate(
            active_position_count=Count(
                "position_mappings",
                filter=Q(position_mappings__active=True),
                distinct=True,
            )
        ).order_by("code", "pk")
        latest_audits = cls._latest_audits([row.pk for row in rows])
        return {
            "contractVersion": RESPONSIBILITY_CATALOG_CONTRACT,
            "factSource": RESPONSIBILITY_FACT_SOURCE,
            "relationshipSource": "system.PositionResponsibility",
            "items": [
                cls._summary(row, latest_audits.get(row.pk)) for row in rows
            ],
        }

    @classmethod
    def detail(cls, responsibility_id):
        row = Responsibility.objects.filter(pk=responsibility_id).first()
        if not row:
            return None
        mappings = PositionResponsibility.objects.select_related(
            "position", "position__department", "position__company"
        ).filter(responsibility=row, active=True).order_by(
            "position__company__code", "position__code", "pk"
        )
        audits = list(
            OrganizationOperatingAuditRecord.objects.select_related("actor")
            .filter(target_type="Responsibility", target_id=row.pk)
            .order_by("created_at", "pk")
        )
        created = audits[0] if audits else None
        modified = audits[-1] if audits else None
        return {
            "contractVersion": RESPONSIBILITY_CATALOG_CONTRACT,
            "factSource": RESPONSIBILITY_FACT_SOURCE,
            "relationshipSource": "system.PositionResponsibility",
            "auditSource": "system.OrganizationOperatingAuditRecord",
            "item": {
                **cls._summary(row, modified),
                "positionCount": len(mappings),
                "positions": [
                    {
                        "mappingId": mapping.pk,
                        "positionId": mapping.position_id,
                        "positionCode": mapping.position.code,
                        "positionName": mapping.position.name,
                        "departmentName": mapping.position.department.name,
                        "companyName": mapping.position.company.name,
                        "responsibilityType": (
                            "PRIMARY" if mapping.is_primary else "SUPPORTING"
                        ),
                    }
                    for mapping in mappings
                ],
                "audit": {
                    "createdBy": cls._actor_name(created),
                    "createdTime": _audit_time(created.created_at) if created else None,
                    "lastModifiedBy": cls._actor_name(modified),
                    "lastModifiedTime": (
                        _audit_time(modified.created_at) if modified else None
                    ),
                    "reason": modified.reason if modified else "",
                },
            },
        }

    @classmethod
    def assignment_context(cls, *, company_id, decision):
        """Scope-aware Position facts needed by the existing assignment UI."""
        scope = decision.get("scope", {})
        scope_codes = set(scope.get("codes") or [])
        departments = Department.objects.filter(company_id=company_id)
        if not ({"ALL", "ORGANIZATION"} & scope_codes):
            departments = departments.filter(pk__in=scope.get("departmentIds") or [])
        departments = list(departments.order_by("code", "pk"))
        department_ids = [row.pk for row in departments]

        positions = list(
            Position.objects.select_related(
                "company", "department", "job_family", "job_level",
                "parent_position", "default_role",
            )
            .filter(company_id=company_id, department_id__in=department_ids)
            .order_by("department__code", "code", "pk")
        )
        mappings_by_position = {}
        mappings = PositionResponsibility.objects.select_related(
            "responsibility"
        ).filter(position_id__in=[row.pk for row in positions], active=True).order_by(
            "position_id", "responsibility__code", "pk"
        )
        for mapping in mappings:
            mappings_by_position.setdefault(mapping.position_id, []).append(mapping)

        return {
            "contractVersion": "PCE-POSITION-RESPONSIBILITY-ASSIGNMENT-CONTEXT-V1",
            "factSource": "system.Position",
            "relationshipSource": "system.PositionResponsibility",
            "companyId": company_id,
            "departments": [
                {
                    "id": row.pk,
                    "code": row.code,
                    "name": row.name,
                    "companyId": row.company_id,
                    "isActive": row.is_active,
                }
                for row in departments
            ],
            "positions": [
                cls._assignment_position(row, mappings_by_position.get(row.pk, []))
                for row in positions
            ],
        }

    @staticmethod
    def _summary(row, latest_audit=None):
        return {
            "id": row.pk,
            "code": row.code,
            "name": row.name,
            "description": row.description,
            "category": row.category,
            "businessDomain": row.category,
            "status": row.status,
            "statusLabel": row.get_status_display(),
            "effectiveFrom": _date(row.effective_from),
            "effectiveTo": _date(row.effective_to),
            "isActive": row.is_active,
            "positionCount": getattr(row, "active_position_count", None),
            "lastModifiedAt": (
                _audit_time(latest_audit.created_at) if latest_audit else None
            ),
        }

    @staticmethod
    def _assignment_position(row, mappings):
        responsibility_labels = [
            f"{mapping.responsibility.code} · {mapping.responsibility.name}"
            for mapping in mappings
        ]
        return {
            "id": row.pk,
            "code": row.code,
            "name": row.name,
            "companyId": row.company_id,
            "departmentId": row.department_id,
            "departmentName": row.department.name,
            "jobFamilyId": row.job_family_id,
            "jobFamilyName": row.job_family.name if row.job_family else "待维护",
            "jobLevelId": row.job_level_id,
            "jobLevelName": row.job_level.name if row.job_level else "待维护",
            "parentPositionId": row.parent_position_id,
            "parentPositionName": row.parent_position.name if row.parent_position else "",
            "defaultRoleId": row.default_role_id,
            "defaultRoleName": row.default_role.name if row.default_role else "待维护",
            "description": row.description,
            "responsibilitySummary": row.responsibility_summary,
            "responsibilityNames": [mapping.responsibility.name for mapping in mappings],
            "responsibilityText": "；".join(responsibility_labels) or "待维护",
            "effectiveFrom": _date(row.effective_from),
            "effectiveTo": _date(row.effective_to),
            "statusLabel": "启用" if row.is_active else "停用",
            "isActive": row.is_active,
        }

    @staticmethod
    def _latest_audits(responsibility_ids):
        result = {}
        rows = (
            OrganizationOperatingAuditRecord.objects.select_related("actor")
            .filter(target_type="Responsibility", target_id__in=responsibility_ids)
            .order_by("target_id", "-created_at", "-pk")
        )
        for row in rows:
            result.setdefault(row.target_id, row)
        return result

    @staticmethod
    def _actor_name(audit):
        if not audit:
            return ""
        return audit.actor.real_name or audit.actor.username

from dataclasses import dataclass

from .models import (
    ApprovalPolicyAuthority,
    ApprovalRouteAuthority,
    SegregationOfDutiesAuthority,
    UserOrganizationRoleAuthority,
)


@dataclass(frozen=True)
class AuthorityEvidence:
    provider: str
    repository: str
    authority_object: str
    authority_id: str
    version: int
    business_hash: str
    payload: dict


class ApprovalPolicyRepository:
    def resolve(self, document_type, legal_entity_id, amount, currency):
        return ApprovalPolicyAuthority.objects.filter(
            document_type=document_type,
            legal_entity_id=legal_entity_id,
            amount_min__lte=amount,
            amount_max__gte=amount,
            currency=currency,
            active=True,
        ).order_by("amount_min").first()


class ApprovalPolicyProvider:
    provider_code = "approval_policy_authority_provider"
    repository_code = "approval_policy_authority_repository"

    def read(self, document_type, legal_entity_id, amount, currency):
        row = ApprovalPolicyRepository().resolve(document_type, legal_entity_id, amount, currency)
        if not row:
            return None
        return AuthorityEvidence(
            self.provider_code, self.repository_code, "ApprovalPolicyAuthority",
            str(row.pk), row.version, row.business_hash,
            {
                "policyId": row.pk, "policyCode": row.policy_code,
                "documentType": row.document_type, "legalEntityId": row.legal_entity_id,
                "amountMin": str(row.amount_min), "amountMax": str(row.amount_max),
                "currency": row.currency, "active": row.active,
                "stepCount": row.step_count, "version": row.version,
            },
        )


class ApprovalRouteRepository:
    def resolve(self, policy_id):
        return ApprovalRouteAuthority.objects.filter(
            policy_id=policy_id, active=True
        ).first()


class ApprovalRouteProvider:
    provider_code = "approval_route_authority_provider"
    repository_code = "approval_route_authority_repository"

    def read(self, policy_id):
        row = ApprovalRouteRepository().resolve(policy_id)
        if not row:
            return None
        return AuthorityEvidence(
            self.provider_code, self.repository_code, "ApprovalRouteAuthority",
            str(row.pk), row.version, row.business_hash,
            {
                "routeId": row.pk, "routeCode": row.route_code,
                "policyId": row.policy_id, "steps": row.steps,
                "active": row.active, "version": row.version,
            },
        )


class UserOrganizationRoleRepository:
    def list_for_user(self, user_id, legal_entity_id):
        return UserOrganizationRoleAuthority.objects.filter(
            user_id=user_id, legal_entity_id=legal_entity_id, active=True
        )


class UserOrganizationRoleProvider:
    provider_code = "user_organization_role_authority_provider"
    repository_code = "user_organization_role_authority_repository"

    def read(self, user_id, legal_entity_id):
        rows = list(UserOrganizationRoleRepository().list_for_user(user_id, legal_entity_id))
        return AuthorityEvidence(
            self.provider_code, self.repository_code, "UserOrganizationRoleAuthority",
            str(user_id), max((row.version for row in rows), default=0),
            "|".join(sorted(row.business_hash for row in rows)),
            {
                "userId": user_id,
                "roleCodes": sorted({row.role_code for row in rows}),
                "legalEntityIds": sorted({row.legal_entity_id for row in rows}),
                "departmentIds": sorted({row.department_id for row in rows if row.department_id}),
                "active": bool(rows),
            },
        )


class SegregationOfDutiesProvider:
    provider_code = "segregation_of_duties_authority_provider"
    repository_code = "segregation_of_duties_authority_repository"

    def read(self, document_type):
        row = SegregationOfDutiesAuthority.objects.filter(
            document_type=document_type
        ).first()
        if not row:
            return None
        return AuthorityEvidence(
            self.provider_code, self.repository_code, "SegregationOfDutiesAuthority",
            str(row.pk), row.version, row.business_hash,
            {
                "documentType": row.document_type,
                "applicantCannotApprove": row.applicant_cannot_approve,
                "sameDepartmentRestriction": row.same_department_restriction,
                "sameUserRestriction": row.same_user_restriction,
                "requiredRoleSeparation": row.required_role_separation,
                "version": row.version,
            },
        )


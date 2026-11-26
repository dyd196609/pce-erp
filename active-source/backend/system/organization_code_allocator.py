from django.db import transaction

from masterdata.models import CodeRule

from .models import Company


ENTITY_ROLE = "system_role"
ENTITY_ORGANIZATION_UNIT = "organization_unit"
ENTITY_DEPARTMENT = "department"
ENTITY_JOB_FAMILY = "job_family"
ENTITY_JOB_LEVEL = "job_level"
ENTITY_POSITION = "position"
ENTITY_EMPLOYEE = "employee"


def ensure_code_rule(*, company_id, entity_type):
    """Return the governed rule for an organization object, creating only its configuration."""
    company = Company.objects.get(pk=company_id)
    prefixes = {
        ENTITY_ROLE: f"ROLE-{company.code}-",
        ENTITY_ORGANIZATION_UNIT: f"OU-{company.code}-",
        ENTITY_DEPARTMENT: f"DEPT-{company.code}-",
        ENTITY_JOB_FAMILY: f"JF-{company.code}-",
        ENTITY_JOB_LEVEL: f"JL-{company.code}-",
        ENTITY_POSITION: f"POS-{company.code}-",
        ENTITY_EMPLOYEE: f"EMP-{company.code}-",
    }
    if entity_type not in prefixes:
        raise ValueError(f"尚未登记自动编号对象：{entity_type}")
    with transaction.atomic():
        rule, _ = CodeRule.objects.select_for_update().get_or_create(
            company_id=company.pk,
            entity_type=entity_type,
            defaults={
                "prefix": prefixes[entity_type],
                "date_format": "",
                "seq_length": 4,
                "current_seq": 0,
            },
        )
        if rule.prefix != prefixes[entity_type] or rule.date_format or rule.seq_length != 4:
            raise ValueError("现有编码规则与正式规则不一致，请先核对，未自动覆盖。")
        return rule


def allocate_code(*, company_id, entity_type):
    ensure_code_rule(company_id=company_id, entity_type=entity_type)
    return CodeRule.next_code(entity_type=entity_type, company_id=company_id)

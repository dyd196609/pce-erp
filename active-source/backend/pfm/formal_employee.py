"""Authoritative query boundaries for employee archives and formal candidates."""

from django.db.models import F

from .models import Employee


def employee_archive_queryset(queryset=None):
    """Return every persisted Employee archive row without eligibility filtering."""

    return queryset if queryset is not None else Employee.objects.all()


def account_link_employee_queryset(queryset=None):
    """Return active archive employees that do not yet own a User account.

    Account linking is an identity-discovery boundary, not a formal business
    candidate boundary.  An incomplete Department/Position chain therefore
    must not hide an otherwise active, unlinked employee from the selector.
    """

    return employee_archive_queryset(queryset).filter(
        status="active",
        user__isnull=True,
    )


def organization_complete_employee_queryset(queryset=None, *, company_id=None):
    """Return employees whose active Department/Position/Company chain agrees.

    Employee lifecycle status is deliberately not part of this structural check.
    """

    queryset = employee_archive_queryset(queryset).filter(
        department_ref__is_active=True,
        department_ref__company__is_active=True,
        position_ref__is_active=True,
        position_ref__department_id=F("department_ref_id"),
        position_ref__company_id=F("department_ref__company_id"),
    )
    if company_id is not None:
        queryset = queryset.filter(department_ref__company_id=company_id)
    return queryset.distinct()


def formal_employee_queryset(queryset=None, *, company_id=None):
    """Return active employees whose complete active organization chain agrees."""

    return organization_complete_employee_queryset(
        queryset, company_id=company_id
    ).filter(status="active")


def is_formal_employee(employee, *, company_id=None):
    if employee is None or employee.pk is None:
        return False
    return formal_employee_queryset(company_id=company_id).filter(pk=employee.pk).exists()

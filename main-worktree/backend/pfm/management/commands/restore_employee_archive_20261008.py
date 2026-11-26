import hashlib
import json
import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from pfm.formal_employee import (
    employee_archive_queryset,
    formal_employee_queryset,
    organization_complete_employee_queryset,
)
from pfm.models import Employee
from system.models import Company, OrganizationOperatingAuditRecord, User


EXPECTED_DATABASE = Path(
    r"D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3"
).resolve()
EXPECTED_BACKUP = Path(
    r"D:\Dev-PCE\CheckpointArchive\pde-operable-acceptance.before-employee-master-convergence-20261008.sqlite3"
).resolve()
EXPECTED_BACKUP_SHA256 = (
    "14862727F5C046561D8ED3BC78D177B35ADAA955C6D193CD81B85348CAE21580"
)
RESTORE_EMPLOYEE_NOS = ("EMP054", "EMP073")
STATUS_RESTORE_EMPLOYEE_NOS = ("EMP012", "EMP018", "PDE-ACCEPT-E1")
TARGET_EMPLOYEE_NOS = RESTORE_EMPLOYEE_NOS + STATUS_RESTORE_EMPLOYEE_NOS
ACTION_CODE = "EMPLOYEE_ARCHIVE_RESTORE_CORRECTION_20261008"


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _columns(cursor):
    cursor.execute("PRAGMA table_info(employee)")
    return [row[1] for row in cursor.fetchall()]


def _rows(cursor, columns, employee_nos=TARGET_EMPLOYEE_NOS):
    placeholders = ",".join("?" for _ in employee_nos)
    cursor.execute(
        f"SELECT * FROM employee WHERE employee_no IN ({placeholders}) ORDER BY id",
        employee_nos,
    )
    return {
        row[columns.index("employee_no")]: dict(zip(columns, row))
        for row in cursor.fetchall()
    }


def _database_snapshot(database_path, employee_nos=TARGET_EMPLOYEE_NOS):
    with sqlite3.connect(f"file:{database_path}?mode=ro", uri=True) as database:
        cursor = database.cursor()
        columns = _columns(cursor)
        rows = _rows(cursor, columns, employee_nos)
    return columns, rows


def _json_value(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def _json_row(row):
    return {key: _json_value(value) for key, value in row.items()}


def _assert_status_only_difference(current, backup, employee_no):
    unexpected = {
        key: {"current": _json_value(current.get(key)), "backup": _json_value(value)}
        for key, value in backup.items()
        if key not in {"status", "updated_at"} and current.get(key) != value
    }
    if unexpected:
        raise CommandError(
            f"NON_CLEANUP_FIELD_DRIFT:{employee_no}:{json.dumps(unexpected, ensure_ascii=False)}"
        )


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


class Command(BaseCommand):
    help = "Precisely restore the five Employee facts changed by the 2026-10-08 cleanup."

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--expected-current-sha256", default="")
        parser.add_argument("--actor-username", default="admin")

    def handle(self, *args, **options):
        database_path = Path(settings.DATABASES["default"]["NAME"]).resolve()
        backup_path = EXPECTED_BACKUP
        if database_path != EXPECTED_DATABASE:
            raise CommandError(f"DATABASE_IDENTITY_MISMATCH:{database_path}")
        if not backup_path.exists():
            raise CommandError(f"BACKUP_NOT_FOUND:{backup_path}")
        backup_sha = _sha256(backup_path)
        if backup_sha != EXPECTED_BACKUP_SHA256:
            raise CommandError(f"BACKUP_SHA_MISMATCH:{backup_sha}")

        current_sha = _sha256(database_path)
        expected_sha = str(options["expected_current_sha256"] or "").strip().upper()
        if options["apply"] and current_sha != expected_sha:
            raise CommandError(f"DATABASE_SHA_MISMATCH:{current_sha}")

        backup_columns, backup_rows = _database_snapshot(backup_path)
        current_columns, current_rows = _database_snapshot(database_path)
        if current_columns != backup_columns:
            raise CommandError("EMPLOYEE_SCHEMA_MISMATCH")
        if set(backup_rows) != set(TARGET_EMPLOYEE_NOS):
            raise CommandError(f"BACKUP_TARGET_MISMATCH:{sorted(backup_rows)}")

        employee_count_before = employee_archive_queryset().count()
        pending_restore = employee_count_before == 122
        already_restored = employee_count_before == 124
        if not pending_restore and not already_restored:
            raise CommandError(f"EMPLOYEE_COUNT_BASELINE_MISMATCH:{employee_count_before}")

        if pending_restore:
            for employee_no in RESTORE_EMPLOYEE_NOS:
                if employee_no in current_rows:
                    raise CommandError(f"RESTORE_TARGET_ALREADY_EXISTS:{employee_no}")
                backup_id = backup_rows[employee_no]["id"]
                if Employee.objects.filter(pk=backup_id).exists():
                    raise CommandError(f"RESTORE_ID_CONFLICT:{backup_id}")
            for employee_no in STATUS_RESTORE_EMPLOYEE_NOS:
                if employee_no not in current_rows:
                    raise CommandError(f"STATUS_TARGET_MISSING:{employee_no}")
                _assert_status_only_difference(
                    current_rows[employee_no], backup_rows[employee_no], employee_no
                )
        else:
            for employee_no in TARGET_EMPLOYEE_NOS:
                if _json_row(current_rows.get(employee_no, {})) != _json_row(
                    backup_rows[employee_no]
                ):
                    raise CommandError(f"RESTORED_ROW_DRIFT:{employee_no}")

        result = {
            "contractVersion": "PCE-EMPLOYEE-ARCHIVE-RESTORE-20261008-V1",
            "applied": False,
            "mode": "PENDING_RESTORE" if pending_restore else "READBACK_RESTORED",
            "databasePath": str(database_path),
            "backupPath": str(backup_path),
            "databaseSha256Before": current_sha,
            "backupSha256": backup_sha,
            "employeeCountBefore": employee_count_before,
            "schemaColumnsMatch": True,
            "plan": [
                {
                    "employeeNo": employee_no,
                    "employeeId": backup_rows[employee_no]["id"],
                    "action": (
                        "RESTORE_EXACT_ARCHIVE_ROW"
                        if employee_no in RESTORE_EMPLOYEE_NOS
                        else "RESTORE_PRE_CLEANUP_STATUS_AND_TIMESTAMP"
                    ),
                    "before": _json_row(current_rows.get(employee_no, {"exists": False})),
                    "after": _json_row(backup_rows[employee_no]),
                }
                for employee_no in TARGET_EMPLOYEE_NOS
            ],
        }

        if options["apply"]:
            if not pending_restore:
                raise CommandError("RESTORE_ALREADY_APPLIED")
            actor = User.objects.filter(username=options["actor_username"]).first()
            if not actor or not actor.is_active:
                raise CommandError("ACTIVE_AUDIT_ACTOR_NOT_FOUND")
            audit_organization = Company.objects.filter(pk=actor.company_id).first()
            if not audit_organization:
                raise CommandError("AUDIT_ACTOR_COMPANY_NOT_FOUND")
            audit_ids = []
            quote = connection.ops.quote_name
            quoted_columns = ", ".join(quote(column) for column in current_columns)
            placeholders = ", ".join(["%s"] * len(current_columns))
            with transaction.atomic():
                with connection.cursor() as cursor:
                    for employee_no in RESTORE_EMPLOYEE_NOS:
                        restored = backup_rows[employee_no]
                        cursor.execute(
                            f"INSERT INTO {quote('employee')} ({quoted_columns}) "
                            f"VALUES ({placeholders})",
                            [restored[column] for column in current_columns],
                        )
                    for employee_no in STATUS_RESTORE_EMPLOYEE_NOS:
                        restored = backup_rows[employee_no]
                        cursor.execute(
                            f"UPDATE {quote('employee')} SET {quote('status')} = %s, "
                            f"{quote('updated_at')} = %s WHERE {quote('id')} = %s",
                            [restored["status"], restored["updated_at"], restored["id"]],
                        )

                restored_objects = {
                    row.employee_no: row
                    for row in Employee.objects.select_related("department_ref__company")
                    .filter(employee_no__in=TARGET_EMPLOYEE_NOS)
                }
                for plan in result["plan"]:
                    employee = restored_objects[plan["employeeNo"]]
                    organization = (
                        employee.department_ref.company
                        if employee.department_ref_id else audit_organization
                    )
                    audit = OrganizationOperatingAuditRecord.objects.create(
                        action_code=ACTION_CODE,
                        actor=actor,
                        organization=organization,
                        target_type="Employee",
                        target_id=employee.pk,
                        target_label=f"{employee.employee_no} {employee.full_name}",
                        reason=(
                            "用户人工验收确认员工档案应保留全部历史Employee；"
                            "本次从只读Before备份精准恢复清理前事实，不授予业务候选资格。"
                        ),
                        before_snapshot=plan["before"],
                        after_snapshot={**plan["after"], "restoreAction": plan["action"]},
                    )
                    audit_ids.append(audit.pk)

            post_columns, current_rows = _database_snapshot(database_path)
            if post_columns != current_columns:
                raise CommandError("POST_RESTORE_EMPLOYEE_SCHEMA_MISMATCH")
            for employee_no in TARGET_EMPLOYEE_NOS:
                if _json_row(current_rows[employee_no]) != _json_row(backup_rows[employee_no]):
                    raise CommandError(f"POST_RESTORE_ROW_MISMATCH:{employee_no}")
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA foreign_key_check")
                foreign_key_violations = cursor.fetchall()
            if foreign_key_violations:
                raise CommandError(f"FOREIGN_KEY_VIOLATION:{foreign_key_violations}")
            result.update({
                "applied": True,
                "auditIds": audit_ids,
                "employeeCountAfter": employee_archive_queryset().count(),
                "organizationCompleteCountAfter": organization_complete_employee_queryset().count(),
                "organizationIncompleteCountAfter": (
                    employee_archive_queryset().count()
                    - organization_complete_employee_queryset().count()
                ),
                "inactiveHistoryCountAfter": employee_archive_queryset()
                .exclude(status="active").count(),
                "formalCandidateBaseCountAfter": formal_employee_queryset().count(),
                "foreignKeyViolations": foreign_key_violations,
                "databaseSha256After": _sha256(database_path),
            })
        else:
            result.update({
                "employeeCountCurrent": employee_archive_queryset().count(),
                "organizationCompleteCountCurrent": organization_complete_employee_queryset().count(),
                "organizationIncompleteCountCurrent": (
                    employee_archive_queryset().count()
                    - organization_complete_employee_queryset().count()
                ),
                "inactiveHistoryCountCurrent": employee_archive_queryset()
                .exclude(status="active").count(),
                "formalCandidateBaseCountCurrent": formal_employee_queryset().count(),
                "correctionAuditCountCurrent": OrganizationOperatingAuditRecord.objects.filter(
                    action_code=ACTION_CODE
                ).count(),
                "databaseSha256After": current_sha,
            })

        _write_json(Path(options["output"]).resolve(), result)
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))

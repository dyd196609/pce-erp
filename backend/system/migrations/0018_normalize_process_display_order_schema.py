from django.db import migrations


TARGET_MARKERS = (
    "display_order integer unsigned NOT NULL DEFAULT 2147483647",
    "CHECK(display_order > 0)",
)


def normalize_sqlite_process_schema(apps, schema_editor):
    """Converge the historical SQLite column form without changing model state or data."""
    connection = schema_editor.connection
    if connection.vendor != "sqlite":
        return

    with connection.cursor() as cursor:
        row = cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'system_process'"
        ).fetchone()
        if row is None:
            raise RuntimeError("system_process is missing; migration baseline cannot be normalized")

        current_sql = row[0] or ""
        if all(marker in current_sql for marker in TARGET_MARKERS):
            return

        foreign_keys_enabled = cursor.execute("PRAGMA foreign_keys").fetchone()[0]
        cursor.execute("PRAGMA foreign_keys = OFF")
        try:
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute(
                '''
                CREATE TABLE "new__system_process" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                    "name" varchar(100) NOT NULL,
                    "code" varchar(20) NOT NULL,
                    "description" text NOT NULL,
                    "is_active" bool NOT NULL,
                    "team_id" bigint NULL REFERENCES "system_team" ("id") DEFERRABLE INITIALLY DEFERRED,
                    "company_id" bigint NULL REFERENCES "system_company" ("id") DEFERRABLE INITIALLY DEFERRED,
                    "work_center_id" bigint NULL REFERENCES "pde_work_center" ("id") DEFERRABLE INITIALLY DEFERRED,
                    "standard_hours" decimal NULL,
                    "skill_required" varchar(160) NOT NULL,
                    "quality_check_required" bool NOT NULL,
                    "effective_from" date NULL,
                    "effective_to" date NULL,
                    "workshop_id" bigint NULL REFERENCES "system_workshop" ("id") DEFERRABLE INITIALLY DEFERRED,
                    "operation_kind" varchar(20) NOT NULL,
                    "calculation_basis" varchar(20) NOT NULL,
                    "calculation_uom_id" bigint NULL REFERENCES "unit_of_measure" ("id") DEFERRABLE INITIALLY DEFERRED,
                    "quantity_driver" varchar(120) NOT NULL,
                    "default_transition_mode" varchar(16) NOT NULL,
                    display_order integer unsigned NOT NULL DEFAULT 2147483647 CHECK(display_order > 0),
                    CONSTRAINT "uniq_system_process_company_code" UNIQUE ("company_id", "code"),
                    CONSTRAINT "system_process_hours_null_or_positive"
                        CHECK (("standard_hours" IS NULL OR "standard_hours" > '0')))
                '''
            )
            cursor.execute(
                '''
                INSERT INTO "new__system_process" (
                    "id", "name", "code", "description", "is_active", "team_id",
                    "company_id", "work_center_id", "standard_hours", "skill_required",
                    "quality_check_required", "effective_from", "effective_to", "workshop_id",
                    "operation_kind", "calculation_basis", "calculation_uom_id",
                    "quantity_driver", "default_transition_mode", "display_order"
                )
                SELECT
                    "id", "name", "code", "description", "is_active", "team_id",
                    "company_id", "work_center_id", "standard_hours", "skill_required",
                    "quality_check_required", "effective_from", "effective_to", "workshop_id",
                    "operation_kind", "calculation_basis", "calculation_uom_id",
                    "quantity_driver", "default_transition_mode", "display_order"
                FROM "system_process"
                '''
            )
            cursor.execute('DROP TABLE "system_process"')
            cursor.execute('ALTER TABLE "new__system_process" RENAME TO "system_process"')
            cursor.execute(
                'CREATE INDEX "system_process_team_id_af2fe1c8" '
                'ON "system_process" ("team_id")'
            )
            cursor.execute(
                'CREATE INDEX "system_process_company_id_be3ab9c0" '
                'ON "system_process" ("company_id")'
            )
            cursor.execute(
                'CREATE INDEX "system_process_work_center_id_e2f298cc" '
                'ON "system_process" ("work_center_id")'
            )
            cursor.execute(
                'CREATE INDEX "system_process_workshop_id_27c684fb" '
                'ON "system_process" ("workshop_id")'
            )
            cursor.execute(
                'CREATE INDEX "system_process_calculation_uom_id_d515c658" '
                'ON "system_process" ("calculation_uom_id")'
            )

            violations = cursor.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise RuntimeError(
                    f"system_process normalization produced foreign-key violations: {violations[:10]}"
                )
            cursor.execute("COMMIT")
        except Exception:
            try:
                cursor.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            if foreign_keys_enabled:
                cursor.execute("PRAGMA foreign_keys = ON")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("system", "0017_team_operation_capability"),
    ]

    operations = [
        migrations.RunPython(
            normalize_sqlite_process_schema,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

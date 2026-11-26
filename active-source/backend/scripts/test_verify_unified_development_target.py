from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_unified_development_target import (
    REQUIRED_MIGRATIONS,
    REQUIRED_TABLES,
    verify_database,
)


class UnifiedDevelopmentTargetPreflightTests(unittest.TestCase):
    def test_zero_employee_database_is_not_rejected_when_technical_contract_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "employee-neutral.sqlite3"
            connection = sqlite3.connect(database)
            try:
                for table in sorted(REQUIRED_TABLES | {"django_migrations"}):
                    if table == "django_migrations":
                        connection.execute("CREATE TABLE django_migrations (app TEXT, name TEXT)")
                    else:
                        connection.execute(f'CREATE TABLE "{table}" (id INTEGER PRIMARY KEY)')
                connection.executemany(
                    "INSERT INTO django_migrations (app, name) VALUES (?, ?)",
                    sorted(REQUIRED_MIGRATIONS),
                )
                connection.commit()
            finally:
                connection.close()

            facts = verify_database(database.resolve())
            self.assertEqual(facts["integrityCheck"], "ok")
            self.assertEqual(facts["databaseOpenMode"], "read-only")


if __name__ == "__main__":
    unittest.main()

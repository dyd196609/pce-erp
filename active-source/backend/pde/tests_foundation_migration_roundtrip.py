from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class FoundationMigrationRoundTripTests(TransactionTestCase):
    """Proves the new schema can roll back and reapply in the isolated test DB."""

    def test_foundation_schema_reverse_and_reapply(self):
        executor = MigrationExecutor(connection)
        executor.migrate([("system", "0013_process_workshop_a1_final")])
        executor = MigrationExecutor(connection)
        executor.migrate([("masterdata", "0010_material_unit_confirmation_a1_final")])
        tables = set(connection.introspection.table_names())
        self.assertNotIn("masterdata_external_identity", tables)
        self.assertNotIn("masterdata_write_request", tables)

        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        tables = set(connection.introspection.table_names())
        self.assertIn("masterdata_external_identity", tables)
        self.assertIn("masterdata_write_request", tables)
        columns = {
            column.name
            for column in connection.introspection.get_table_description(
                connection.cursor(), "system_process",
            )
        }
        self.assertTrue({"operation_kind", "calculation_basis", "calculation_uom_id", "quantity_driver"} <= columns)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT code, name, dimension FROM unit_of_measure "
                "WHERE company_id = 1 AND code IN ('kg', 'm', 'm2', '根', '桶', '袋')"
            )
            initialized = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
        self.assertEqual(initialized, {
            "kg": ("千克", "mass"), "m": ("米", "length"),
            "m2": ("平方米", "area"), "根": ("根", "count"),
            "桶": ("桶", "count"), "袋": ("袋", "count"),
        })

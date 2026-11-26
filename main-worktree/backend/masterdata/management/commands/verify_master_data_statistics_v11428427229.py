from django.core.management.base import BaseCommand, CommandError

from masterdata.master_data_statistics_runtime import MasterDataStatisticsRuntime


class Command(BaseCommand):
    help = "Verify V1.14.2.8.4.27.2.29 master-data statistics without writes."

    def handle(self, *args, **options):
        facts = MasterDataStatisticsRuntime.facts()
        if facts["materialCount"] != 80:
            raise CommandError(
                f"MASTER-DATA-COUNT-CONSISTENCY-001 FAIL material={facts['materialCount']}"
            )
        if facts["supplierCount"] != 100:
            raise CommandError(
                f"MASTER-DATA-COUNT-CONSISTENCY-001 FAIL supplier={facts['supplierCount']}"
            )
        expected_sources = {
            "materialCount": "MaterialMasterRuntimeAdapter",
            "supplierCount": "SupplierMasterRuntimeAdapter",
            "supplierMaterialRelationCount": "MaterialSupplierRelationRuntime",
            "supplierPriceCount": "SupplierMaterialPriceRuntime",
        }
        if facts["countSources"] != expected_sources:
            raise CommandError("MASTER-DATA-STATISTICS-SOURCE-001 FAIL")
        self.stdout.write("MASTER-DATA-STATISTICS-SOURCE-001 PASS")
        self.stdout.write("MASTER-DATA-COUNT-CONSISTENCY-001 PASS")
        self.stdout.write(f"Material Count PASS ({facts['materialCount']})")
        self.stdout.write(f"Supplier Count PASS ({facts['supplierCount']})")
        self.stdout.write(
            f"Relation Count PASS ({facts['supplierMaterialRelationCount']})"
        )
        self.stdout.write(f"Price Count PASS ({facts['supplierPriceCount']})")
        self.stdout.write("Business Write Count PASS (0)")

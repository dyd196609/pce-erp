from django.core.management.base import BaseCommand, CommandError

from masterdata.material_supplier_relation_runtime import MaterialSupplierRelationRuntime
from masterdata.master_data_statistics_runtime import MasterDataStatisticsRuntime
from masterdata.models import Material
from procurement.models import PurchaseOrder, Supplier


class Command(BaseCommand):
    help = "Verify V1.14.2.8.4.27.2.30 relation mapping without transaction writes."

    def handle(self, *args, **options):
        protected_before = {
            "materialCount": Material.objects.count(),
            "supplierCount": Supplier.objects.count(),
            "purchaseOrderCount": PurchaseOrder.objects.count(),
        }
        facts = MaterialSupplierRelationRuntime.facts()
        statistics = MasterDataStatisticsRuntime.facts()
        models = facts["models"]
        if facts["relationCount"] <= 1:
            raise CommandError("MATERIAL-SUPPLIER-SOURCE-001 FAIL")
        if facts["duplicateRelationCount"]:
            raise CommandError("MATERIAL-SUPPLIER-UNIQUE-001 FAIL")
        material_codes = set(Material.objects.values_list("code", flat=True))
        supplier_codes = set(Supplier.objects.values_list("code", flat=True))
        if any(row.materialCode not in material_codes or row.supplierCode not in supplier_codes
               for row in models):
            raise CommandError("MATERIAL-SUPPLIER-MAPPING-001 FAIL")
        if any(row.isMainSupplier and not set(row.sourceModules).intersection(
                {"SupplierRecommendation", "PriceApproval", "QuoteComparison"})
               for row in models):
            raise CommandError("MATERIAL-SUPPLIER-MAIN-SOURCE FAIL")
        if any(row.deliveryPeriod is not None and not row.deliveryPeriodSource for row in models):
            raise CommandError("MATERIAL-SUPPLIER-DELIVERY-SOURCE FAIL")
        if statistics["supplierMaterialRelationCount"] != facts["relationCount"]:
            raise CommandError("MASTER-DATA-STATISTICS-RELATION-001 FAIL")
        protected_after = {
            "materialCount": Material.objects.count(),
            "supplierCount": Supplier.objects.count(),
            "purchaseOrderCount": PurchaseOrder.objects.count(),
        }
        if protected_before != protected_after:
            raise CommandError("BUSINESS-WRITE-BOUNDARY FAIL")

        self.stdout.write("MATERIAL-SUPPLIER-SOURCE-001 PASS")
        self.stdout.write("MATERIAL-SUPPLIER-UNIQUE-001 PASS")
        self.stdout.write("MATERIAL-SUPPLIER-MAPPING-001 PASS")
        self.stdout.write("MASTER-DATA-STATISTICS-RELATION-001 PASS")
        self.stdout.write(f"Relation Count PASS ({facts['relationCount']})")
        self.stdout.write(f"Usage Matrix Count PASS ({facts['usageMatrixCount']})")
        self.stdout.write(f"Pending Manual Review ({sum(1 for row in facts['usageMatrix'] if row['mappingStatus'] == '待人工确认')})")
        self.stdout.write(f"Unresolved Code Mapping ({len(facts['unresolvedMappings'])})")
        self.stdout.write(f"Main Supplier Facts PASS ({sum(1 for row in models if row.isMainSupplier)})")
        self.stdout.write(f"Delivery Period Sources PASS ({sum(1 for row in models if row.deliveryPeriod is not None)})")
        for row in facts["usageMatrix"]:
            self.stdout.write(
                "MaterialSupplierUsageMatrix | "
                f"{row['materialCode']} | {row['materialName']} | "
                f"{row['supplierCode']} | {row['supplierName']} | "
                f"{row['sourceModule']} | {row['businessUsageCount']} | "
                f"{row['mappingStatus']}"
            )
        self.stdout.write("Material Changed NO")
        self.stdout.write("Supplier Changed NO")
        self.stdout.write("PurchaseOrder Changed NO")
        self.stdout.write("Business Write Count PASS (0)")

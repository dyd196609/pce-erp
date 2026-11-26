import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from pde.acceptance_isolation import verify_acceptance_connections
from pde.engineering_calculation_service import OrderEngineeringClosureService
from pde.models import BOMItem, BOMVersion, ProductBOM
from pde.order_bom_handoff_service import order_bom_handoff
from sales.models import SalesOrder
from system.models import User


ORDER_NO = "SO202609180003"
CALCULATION_ID = 3


def _bom_counts(order):
    headers = ProductBOM.objects.filter(
        order_engineering_instance__sales_order_item__sales_order=order,
    )
    versions = BOMVersion.objects.filter(
        Q(source_calculation__sales_order_item__sales_order=order)
        | Q(order_engineering_instance__sales_order_item__sales_order=order)
    ).distinct()
    return {
        "productBomCount": headers.count(),
        "bomVersionCount": versions.count(),
        "bomItemCount": BOMItem.objects.filter(bom_version__in=versions).count(),
    }


class Command(BaseCommand):
    help = "Run the authorized read-only Calculation 3 BOM preview and line-1 handoff."

    def add_arguments(self, parser):
        parser.add_argument("--actor", required=True)

    def handle(self, *args, **options):
        try:
            verify_acceptance_connections(settings.DATABASES)
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        user = User.objects.filter(username=options["actor"], is_active=True).first()
        if user is None:
            raise CommandError("FORMAL_ACTOR_NOT_FOUND")
        order = SalesOrder.objects.filter(company_id=user.company_id, order_no=ORDER_NO).first()
        if order is None:
            raise CommandError("FORMAL_ORDER_NOT_FOUND")

        before = _bom_counts(order)
        direct = OrderEngineeringClosureService.preview_bom(
            user=user,
            calculation_id=CALCULATION_ID,
        )
        handoff = order_bom_handoff(user=user, order_id=order.pk)
        line1 = next(row for row in handoff["records"] if row["lineNo"] == 1)
        objects = [
            {
                "objectNo": row["objectNo"],
                "formalMaterialRequirementCount": row["formalMaterialRequirementCount"],
            }
            for row in line1["objects"]
        ]
        missing = [
            row["objectNo"] for row in line1["objects"]
            if not row["formalMaterialRequirementCount"]
        ]
        after = _bom_counts(order)
        payload = {
            "database": str(Path(settings.DATABASES["default"]["NAME"]).resolve()),
            "mode": "READ_ONLY_PREVIEW",
            "actor": user.username,
            "orderId": order.pk,
            "orderNo": order.order_no,
            "calculationId": CALCULATION_ID,
            "directPreview": direct,
            "line1Coverage": {
                "objectCount": line1["objectCount"],
                "coveredObjectCount": sum(
                    bool(row["formalMaterialRequirementCount"])
                    for row in line1["objects"]
                ),
                "objects": objects,
                "missingObjectNos": missing,
                "firstBlocker": missing[0] if missing else None,
            },
            "bomHandoffStatus": handoff["bomHandoffStatus"],
            "businessWriteCount": handoff["businessWriteCount"],
            "bomCountsBefore": before,
            "bomCountsAfter": after,
            "bomCountsUnchanged": before == after,
        }
        self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2, default=str))

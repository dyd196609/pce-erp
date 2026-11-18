import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from pde.models import EngineeringSourceRecord
from sales.crm_source_establishment import (
    SalesOrderCRMSourceEstablishmentError,
    establish_sales_order_current_crm_source,
    inspect_crm_source_establishment,
)
from sales.models import SalesOrder


class Command(BaseCommand):
    help = "Establish one governed current CRM Source for an existing SalesOrder."

    def add_arguments(self, parser):
        parser.add_argument("--actor", required=True)
        parser.add_argument("--order-no", required=True)
        parser.add_argument("--source-record-id", type=int, required=True)
        parser.add_argument("--expected-source-version", required=True)
        parser.add_argument("--expected-source-content-hash", required=True)
        parser.add_argument("--expected-customer-name", required=True)
        parser.add_argument("--expected-project-reference", required=True)
        parser.add_argument("--expected-external-source-no", required=True)
        parser.add_argument("--expected-engineering-row-count", type=int, required=True)
        parser.add_argument("--idempotency-key", required=True)
        parser.add_argument("--reason", required=True)
        parser.add_argument("--inspect-only", action="store_true")

    def handle(self, *args, **options):
        actor = get_user_model().objects.filter(username=options["actor"]).first()
        if not actor:
            raise CommandError("执行账户不存在。")
        order = SalesOrder.objects.select_related("customer").filter(
            order_no=options["order_no"],
        ).first()
        if not order:
            raise CommandError("目标销售订单不存在。")
        source = EngineeringSourceRecord.objects.filter(
            pk=options["source_record_id"],
        ).first()
        if not source:
            raise CommandError("目标CRM来源不存在。")
        try:
            if options["inspect_only"]:
                result = inspect_crm_source_establishment(
                    order=order, source=source, actor=actor,
                )
            else:
                result = establish_sales_order_current_crm_source(
                    actor=actor,
                    order_id=order.pk,
                    expected_order_no=options["order_no"],
                    source_record_id=source.pk,
                    expected_source_version=options["expected_source_version"],
                    expected_source_content_hash=options["expected_source_content_hash"],
                    expected_customer_name=options["expected_customer_name"],
                    expected_project_reference=options["expected_project_reference"],
                    expected_external_source_no=options["expected_external_source_no"],
                    expected_engineering_row_count=options["expected_engineering_row_count"],
                    idempotency_key=options["idempotency_key"],
                    reason=options["reason"],
                )
        except SalesOrderCRMSourceEstablishmentError as exc:
            raise CommandError(json.dumps({
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }, ensure_ascii=False)) from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))

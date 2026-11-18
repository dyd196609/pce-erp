import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from sales.models import SalesOrder
from sales.order_business_identity_correction import (
    SalesOrderBusinessIdentityCorrectionError,
    correct_sales_order_business_identity,
)


class Command(BaseCommand):
    help = "Execute the governed SalesOrder formal business-identity correction action."

    def add_arguments(self, parser):
        parser.add_argument("--actor", required=True)
        parser.add_argument("--order-no", required=True)
        parser.add_argument("--expected-customer-id", type=int, required=True)
        parser.add_argument("--expected-project-reference", required=True)
        parser.add_argument("--expected-external-source-no", required=True)
        parser.add_argument("--expected-contract-reference", required=True)
        parser.add_argument("--expected-remark", required=True)
        parser.add_argument("--expected-item-count", type=int, required=True)
        parser.add_argument("--target-business-purpose", default="FORMAL_SALE")
        parser.add_argument("--idempotency-key", required=True)
        parser.add_argument("--request-id", required=True)
        parser.add_argument("--reason", required=True)

    def handle(self, *args, **options):
        actor = get_user_model().objects.filter(username=options["actor"]).first()
        if not actor:
            raise CommandError("执行账户不存在。")
        order = SalesOrder.objects.filter(order_no=options["order_no"]).only("id").first()
        if not order:
            raise CommandError("目标销售订单不存在。")
        try:
            result = correct_sales_order_business_identity(
                actor=actor,
                order_id=order.pk,
                expected_order_no=options["order_no"],
                expected_customer_id=options["expected_customer_id"],
                expected_project_reference=options["expected_project_reference"],
                expected_external_source_no=options["expected_external_source_no"],
                expected_contract_reference=options["expected_contract_reference"],
                expected_remark=options["expected_remark"],
                expected_item_count=options["expected_item_count"],
                target_business_purpose=options["target_business_purpose"],
                idempotency_key=options["idempotency_key"],
                request_id=options["request_id"],
                reason=options["reason"],
                source="management-command",
            )
        except SalesOrderBusinessIdentityCorrectionError as exc:
            payload = {"code": exc.code, "message": exc.message, "details": exc.details}
            raise CommandError(json.dumps(payload, ensure_ascii=False)) from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))

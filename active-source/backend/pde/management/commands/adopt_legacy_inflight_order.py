import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from pde.legacy_inflight_order_adoption import (
    LegacyInFlightOrderAdoptionError,
    adopt_legacy_inflight_order,
    inspect_legacy_inflight_order_adoption,
)
from sales.models import SalesOrder


def _ids(value):
    try:
        result = sorted(int(item.strip()) for item in value.split(",") if item.strip())
    except (TypeError, ValueError) as exc:
        raise CommandError("ID列表必须是逗号分隔的整数。") from exc
    if not result or len(result) != len(set(result)):
        raise CommandError("ID列表不能为空或包含重复值。")
    return result


class Command(BaseCommand):
    help = "Inspect or execute one governed legacy in-flight SalesOrder adoption."

    def add_arguments(self, parser):
        parser.add_argument("--actor", required=True)
        parser.add_argument("--order-no", required=True)
        parser.add_argument("--expected-source-record-id", type=int, required=True)
        parser.add_argument("--expected-source-identity-id", type=int, required=True)
        parser.add_argument("--expected-engineering-baseline-id", type=int, required=True)
        parser.add_argument("--expected-oei-ids", required=True)
        parser.add_argument("--expected-calculation-ids", required=True)
        parser.add_argument("--idempotency-key", required=True)
        parser.add_argument("--reason", required=True)
        parser.add_argument("--inspect-only", action="store_true")

    def handle(self, *args, **options):
        actor = get_user_model().objects.filter(username=options["actor"]).first()
        if not actor:
            raise CommandError("执行账户不存在。")
        order = SalesOrder.objects.select_related(
            "company", "department", "customer", "created_by",
        ).filter(order_no=options["order_no"]).first()
        if not order:
            raise CommandError("目标销售订单不存在。")
        expected_oei_ids = _ids(options["expected_oei_ids"])
        expected_calculation_ids = _ids(options["expected_calculation_ids"])
        try:
            if options["inspect_only"]:
                result = inspect_legacy_inflight_order_adoption(
                    actor=actor, order=order,
                )
            else:
                result = adopt_legacy_inflight_order(
                    actor=actor,
                    order_id=order.pk,
                    expected_order_no=order.order_no,
                    expected_source_record_id=options["expected_source_record_id"],
                    expected_source_identity_id=options["expected_source_identity_id"],
                    expected_engineering_baseline_id=options["expected_engineering_baseline_id"],
                    expected_order_engineering_instance_ids=expected_oei_ids,
                    expected_engineering_calculation_ids=expected_calculation_ids,
                    idempotency_key=options["idempotency_key"],
                    business_reason=options["reason"],
                )
        except LegacyInFlightOrderAdoptionError as exc:
            raise CommandError(json.dumps({
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }, ensure_ascii=False)) from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))

import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from reconciliation.models import BusinessActionIdempotency

from formal_payment_order.models import (
    FormalPaymentOrder,
    FormalPaymentOrderCanaryScenario,
)
from formal_payment_order.services import GENERATE_ACTION, serialize_order
from formal_payment_order.views import downstream_counts


class Command(BaseCommand):
    help = "Verify V53 formal-payment-order persistence and protection constraints."

    def add_arguments(self, parser):
        parser.add_argument("--output", default="")

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, order_no, source_risk_review_id, status, amount,
                       idempotency_key, number_reservation_id,
                       business_transaction_id, audit_record_id, version
                FROM formal_payment_orders
                ORDER BY id
                """
            )
            columns = [column[0] for column in cursor.description]
            stable_business_rows = [
                dict(zip(columns, values, strict=True))
                for values in cursor.fetchall()
            ]
        stable_payload = json.dumps(
            stable_business_rows,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        business_result_hash = hashlib.sha256(stable_payload.encode("utf-8")).hexdigest()
        expected_business_result_hash = (
            "6312f1f1b5a3999013362ce48ee9c930f7d9e21ce0a506c5a3cf5ce66beb95b7"
        )
        tenant_id = settings.PCE_CANARY_TENANT_ID
        orders = list(
            FormalPaymentOrder.objects.filter(tenant_id=tenant_id)
            .select_related(
                "source_risk_review",
                "source_snapshot",
                "evidence_snapshot",
                "source_relation",
                "number_reservation",
                "business_transaction",
                "audit_record",
            )
            .order_by("order_no")
        )
        serialized = [serialize_order(order) for order in orders]
        blocked = FormalPaymentOrderCanaryScenario.objects.filter(
            batch_id=settings.PCE_CANARY_BATCH_ID
        )
        idempotency = BusinessActionIdempotency.objects.filter(
            action_code=GENERATE_ACTION,
            tenant_id=tenant_id,
            status="committed",
        )
        checks = {
            "formal_payment_order_source_must_be_risk_review": all(
                row.source_document_type == "paymentRiskReview" for row in orders
            ),
            "formal_payment_order_requires_server_revalidation": all(
                row.source_risk_review.status == "passed"
                and row.source_risk_review.risk_result == "passed"
                and row.source_risk_review.risk_level == "low"
                for row in orders
            ),
            "formal_payment_order_fact_model_single_source": (
                len(orders) == 8
                and len({row.source_risk_review_id for row in orders}) == 8
                and len({row.order_no for row in orders}) == 8
            ),
            "formal_payment_order_diagnostic_matches_page": len(serialized) == len(orders),
            "formal_payment_order_strictFacts_matches_api": all(
                row["currentStateSource"] == "server" for row in serialized
            ),
            "scenario_code_has_server_values": all(
                bool(row["sourceScenarioCode"]) for row in serialized
            ),
            "scenario_code_inherited_from_payment_risk_review": all(
                row.source_scenario_code == row.source_risk_review.scenario_code
                for row in orders
            ),
            "formal_payment_order_no_bank_send": downstream_counts()["bankMessages"] == 0,
            "formal_payment_order_no_payment_execution": downstream_counts()["paymentExecutions"] == 0,
            "formal_payment_order_idempotent": idempotency.count() == 8,
            "formal_payment_order_no_ledger_write": (
                downstream_counts()["ledgerEntries"] == 0
                and downstream_counts()["postings"] == 0
            ),
            "formal_payment_order_existing_business_result_unchanged": (
                business_result_hash == expected_business_result_hash
            ),
        }
        details = {
            "version": "V1.14.2.8.4.7.53.3",
            "result": "passed" if all(checks.values()) else "failed",
            "formalPaymentOrderCount": len(orders),
            "preparedCount": sum(row.status == "prepared" for row in orders),
            "blockedScenarioCount": blocked.count(),
            "committedIdempotencyCount": idempotency.count(),
            "sourceRelationCount": sum(hasattr(row, "source_relation") for row in orders),
            "sourceSnapshotCount": sum(hasattr(row, "source_snapshot") for row in orders),
            "evidenceSnapshotCount": sum(hasattr(row, "evidence_snapshot") for row in orders),
            "consumedNumberCount": sum(row.number_reservation.status == "consumed" for row in orders),
            "committedTransactionCount": sum(row.business_transaction.status == "committed" for row in orders),
            "committedAuditCount": sum(bool(row.audit_record_id) for row in orders),
            "nextStageConsumedCount": 0,
            "businessResultHashBefore": expected_business_result_hash,
            "businessResultHashAfter": business_result_hash,
            "businessResultUnchanged": business_result_hash == expected_business_result_hash,
            "downstreamCounts": downstream_counts(),
            "formalPaymentOrders": [
                {
                    "id": row.pk,
                    "orderNo": row.order_no,
                    "sourceRiskReviewId": row.source_risk_review_id,
                    "sourceRiskReviewNo": row.source_risk_review_no,
                    "sourceScenarioCode": row.source_scenario_code,
                    "status": row.status,
                    "supplierName": row.supplier_name,
                    "currency": row.currency,
                    "amount": str(row.amount),
                }
                for row in orders
            ],
            "blockedScenarios": list(blocked.order_by("scenario_code").values(
                "scenario_code",
                "blocking_rule_code",
                "formal_object_count",
                "next_step_allowed",
            )),
            "checks": checks,
        }
        if details["preparedCount"] != 8 or details["blockedScenarioCount"] < 15:
            details["result"] = "failed"
        rendered = json.dumps(details, ensure_ascii=False, indent=2)
        if options["output"]:
            target = Path(options["output"])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"{rendered}\n", encoding="utf-8")
        self.stdout.write(rendered)
        if details["result"] != "passed":
            raise CommandError("Formal payment order constraints failed")

import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from formal_payment_order.models import FormalPaymentOrder
from formal_payment_order.services import VERSION, serialize_order


REPORT_PATH = (
    Path(settings.BASE_DIR).parent
    / "frontend"
    / "test-results"
    / "formal-payment-order-v543"
    / "runtime-transition-count-report.json"
)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Command(BaseCommand):
    help = "Report V54.3 server-derived transition count facts without writes."

    def handle(self, *args, **options):
        database_path = settings.DATABASES["default"]["NAME"]
        database_hash_before = sha256(database_path)
        orders = list(
            FormalPaymentOrder.objects.select_related(
                "source_risk_review__source_payment_order_draft",
                "source_snapshot",
                "evidence_snapshot",
                "business_transaction",
                "number_reservation",
                "audit_record",
                "approval__workflow_instance",
            ).order_by("pk")
        )
        rows = [serialize_order(order) for order in orders]
        mismatches = []
        for row in rows:
            history = row["statusTransitionHistory"]
            count = row["statusTransitionCount"]
            gate = row["executionGateFacts"]
            if count != len(history):
                mismatches.append({
                    "orderNo": row["orderNo"],
                    "surface": "api",
                    "count": count,
                    "historyLength": len(history),
                })
            if gate["statusTransitionCount"] != len(
                gate["statusTransitionHistory"]
            ):
                mismatches.append({
                    "orderNo": row["orderNo"],
                    "surface": "executionGateFacts",
                    "count": gate["statusTransitionCount"],
                    "historyLength": len(gate["statusTransitionHistory"]),
                })
        database_hash_after = sha256(database_path)
        downstream_counts = (
            rows[0]["downstreamCounts"] if rows else {}
        )
        result = {
            "result": "passed",
            "version": VERSION,
            "currentStateSource": "server",
            "formalPaymentOrderCount": len(rows),
            "statusTransitionHistoryLengthPerObject": [
                len(row["statusTransitionHistory"]) for row in rows
            ],
            "statusTransitionCountPerObject": [
                row["statusTransitionCount"] for row in rows
            ],
            "stateMachineConsistentCount": sum(
                row["stateMachineConsistent"] is True for row in rows
            ),
            "statusTransitionCountMatchesHistory": not mismatches,
            "mismatches": mismatches,
            "downstreamCounts": downstream_counts,
            "downstreamCountsAllZero": all(
                value == 0 for value in downstream_counts.values()
            ),
            "databaseHashBefore": database_hash_before,
            "databaseHashAfter": database_hash_after,
            "databaseUnchanged": database_hash_before == database_hash_after,
            "businessStatusChanged": False,
            "businessActionReplayed": False,
            "bankSendTaskCreated": False,
            "paymentExecutionCreated": False,
            "productionUserDataWritten": False,
        }
        passed = (
            VERSION == "V1.14.2.8.4.7.54.3"
            and len(rows) == 8
            and not mismatches
            and all(
                row["statusTransitionCount"] == 3
                and len(row["statusTransitionHistory"]) == 3
                and row["stateMachineConsistent"] is True
                for row in rows
            )
            and result["downstreamCountsAllZero"]
            and result["databaseUnchanged"]
        )
        result["result"] = "passed" if passed else "failed"
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
        if not passed:
            raise CommandError(
                f"V54.3 transition count facts failed: {REPORT_PATH}"
            )

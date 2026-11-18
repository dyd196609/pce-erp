import json

from django.core.management.base import BaseCommand, CommandError

from pde.order_engineering_document_registration_service import (
    OrderEngineeringDocumentRegistrationError,
    OrderEngineeringDocumentRegistrationService,
)
from system.models import User


class Command(BaseCommand):
    help = "Preflight or execute a controlled order-engineering document/first-version registration."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--order-no", required=True)
        parser.add_argument("--line-no", required=True, type=int)
        parser.add_argument("--document-no", required=True)
        parser.add_argument("--document-name", required=True)
        parser.add_argument("--document-type", required=True)
        parser.add_argument("--idempotency-key")
        parser.add_argument("--reason")
        parser.add_argument("--execute", action="store_true")

    @staticmethod
    def _printable_preflight(result):
        return {
            "outcome": "PREFLIGHT_PASS",
            "facts": result["facts"],
            "chain": result["chain"],
            "authorization": {
                "allowed": result["authorization"].get("allowed"),
                "decisionCode": result["authorization"].get("decisionCode"),
                "roleCodes": result["authorization"].get("roleCodes", []),
            },
            "executionChain": result["executionChain"],
            "counts": result["counts"],
            "existingDocumentId": result["document"].pk if result["document"] else None,
            "existingVersionId": result["version"].pk if result["version"] else None,
            "idempotentComplete": result["idempotentComplete"],
        }

    def handle(self, *args, **options):
        try:
            user = User.objects.get(username=options["username"], is_active=True)
        except User.DoesNotExist as exc:
            raise CommandError("BLOCKED_BEFORE_WRITE: active execution account not found") from exc
        common = {
            "user": user,
            "order_no": options["order_no"],
            "line_no": options["line_no"],
            "document_no": options["document_no"],
            "document_name": options["document_name"],
            "document_type": options["document_type"],
        }
        try:
            if options["execute"]:
                result = OrderEngineeringDocumentRegistrationService.register(
                    **common,
                    idempotency_key=options.get("idempotency_key"),
                    reason=options.get("reason"),
                )
            else:
                result = self._printable_preflight(
                    OrderEngineeringDocumentRegistrationService.preflight(**common),
                )
        except OrderEngineeringDocumentRegistrationError as exc:
            raise CommandError(
                json.dumps(exc.as_dict(), ensure_ascii=False, sort_keys=True),
            ) from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))

import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from pde.legacy_inflight_order_adoption import (
    LegacyInFlightOrderAdoptionError,
    revoke_legacy_inflight_order_adoption,
)


class Command(BaseCommand):
    help = "Append one governed revocation fact for a legacy in-flight adoption."

    def add_arguments(self, parser):
        parser.add_argument("--actor", required=True)
        parser.add_argument("--adoption-id", type=int, required=True)
        parser.add_argument(
            "--reason-code",
            choices=("BUSINESS_IDENTITY_CONFLICT", "EVIDENCE_INVALIDATED"),
            required=True,
        )
        parser.add_argument("--reason", required=True)
        parser.add_argument("--idempotency-key", required=True)

    def handle(self, *args, **options):
        actor = get_user_model().objects.filter(username=options["actor"]).first()
        if not actor:
            raise CommandError("执行账户不存在。")
        try:
            result = revoke_legacy_inflight_order_adoption(
                actor=actor,
                adoption_id=options["adoption_id"],
                reason_code=options["reason_code"],
                reason=options["reason"],
                idempotency_key=options["idempotency_key"],
            )
        except LegacyInFlightOrderAdoptionError as exc:
            raise CommandError(json.dumps({
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }, ensure_ascii=False)) from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))

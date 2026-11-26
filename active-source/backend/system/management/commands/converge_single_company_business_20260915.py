import json

from django.core.management.base import BaseCommand, CommandError

from system.single_company_convergence import (
    SingleCompanyBusinessConvergenceService,
    SingleCompanyConvergenceError,
    resolve_users,
)


class Command(BaseCommand):
    help = "Preview or apply the user-approved single-company convergence in the named non-production B database."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--actor", default="admin")
        parser.add_argument("--foundation-actor", default="emd_emp047")
        parser.add_argument("--reason", default="用户2026-09-15确认唯一经营主体为掌云并授权本轮受控收敛")

    def handle(self, *args, **options):
        try:
            if not options["apply"]:
                result = {"mode": "READ_ONLY_PREFLIGHT", **SingleCompanyBusinessConvergenceService.inspect()}
            else:
                actor, foundation_actor = resolve_users(
                    actor_username=options["actor"],
                    foundation_actor_username=options["foundation_actor"],
                )
                result = {
                    "mode": "APPLIED",
                    **SingleCompanyBusinessConvergenceService.execute(
                        actor=actor,
                        foundation_actor=foundation_actor,
                        reason=options["reason"],
                    ),
                }
        except SingleCompanyConvergenceError as exc:
            raise CommandError(json.dumps({"code": exc.code, "message": exc.message, "details": exc.details}, ensure_ascii=False)) from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))

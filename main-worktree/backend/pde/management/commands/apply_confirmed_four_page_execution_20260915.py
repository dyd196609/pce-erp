import json

from django.core.management.base import BaseCommand, CommandError

from pde.confirmed_engineering_conditions import (
    ConfirmedEngineeringConditionError,
    ConfirmedEngineeringConditionService,
    TASK_ID,
)
from system.models import User
from system.single_company_convergence import (
    SingleCompanyBusinessConvergenceService,
    SingleCompanyConvergenceError,
)


class Command(BaseCommand):
    help = "Apply the exact approved COMP002 cleanup and/or confirmed source-10 engineering inputs."

    def add_arguments(self, parser):
        parser.add_argument("--confirmed-task-id", required=True)
        parser.add_argument("--apply-company", action="store_true")
        parser.add_argument("--apply-engineering", action="store_true")
        parser.add_argument("--company-actor", default="admin")
        parser.add_argument("--engineering-actor", default="pce_plan_r12")

    def handle(self, *args, **options):
        if options["confirmed_task_id"] != TASK_ID:
            raise CommandError("CONFIRMED_TASK_ID_MISMATCH")
        if not options["apply_company"] and not options["apply_engineering"]:
            raise CommandError("AN_EXPLICIT_APPLY_SCOPE_IS_REQUIRED")
        try:
            company_actor = User.objects.get(username=options["company_actor"], is_active=True)
            engineering_actor = User.objects.get(username=options["engineering_actor"], is_active=True)
            result = {"taskId": TASK_ID, "company": None, "engineering": None}
            if options["apply_company"]:
                result["company"] = SingleCompanyBusinessConvergenceService.delete_approved_example_company(
                    actor=company_actor,
                )
            if options["apply_engineering"]:
                result["engineering"] = ConfirmedEngineeringConditionService.execute(
                    actor=engineering_actor,
                )
        except User.DoesNotExist as exc:
            raise CommandError("APPROVED_EXISTING_ACTOR_NOT_FOUND") from exc
        except (SingleCompanyConvergenceError, ConfirmedEngineeringConditionError) as exc:
            raise CommandError(json.dumps(
                {"code": exc.code, "message": exc.message, "details": exc.details},
                ensure_ascii=False, default=str,
            )) from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))

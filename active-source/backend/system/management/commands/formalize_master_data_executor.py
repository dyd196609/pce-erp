import json

from django.core.management.base import BaseCommand, CommandError

from masterdata.validated_fact_formalization_service import ValidatedFactFormalizationService
from pde.production_foundation_service import ProductionFoundationError
from system.master_data_executor_formalization_service import (
    ExecutorFormalizationError,
    MasterDataExecutorFormalizationService,
)
from system.models import User


class Command(BaseCommand):
    help = "Formalize the manually approved EMP047 executor chain, then the authorized Group 1 facts."

    def handle(self, *args, **options):
        try:
            admin = User.objects.get(username="admin", is_superuser=True, is_active=True)
            executor_result = MasterDataExecutorFormalizationService.execute(actor=admin)
            executor = User.objects.get(username="emd_emp047", is_active=True)
            base_data_result = ValidatedFactFormalizationService.execute(executor)
        except (User.DoesNotExist, ExecutorFormalizationError, ProductionFoundationError) as error:
            code = getattr(error, "code", "IDENTITY_NOT_FOUND")
            message = getattr(error, "message", str(error))
            raise CommandError(f"{code}: {message}")
        self.stdout.write(json.dumps({
            "executor": executor_result,
            "baseData": base_data_result,
        }, ensure_ascii=True, indent=2, default=str))

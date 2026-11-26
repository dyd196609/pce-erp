import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from bank_send_execution_simulation.models import (
    BankSendProductionReleaseReview,
)
from bank_send_execution_simulation.v68 import (
    create_execution_framework,
    create_simulated_artifacts,
    perform_safety_review,
    protection_counts,
)


class Command(BaseCommand):
    help = "Create V68 isolated execution framework design artifacts"

    def handle(self, *args, **options):
        database_name = str(settings.DATABASES["default"]["NAME"])
        if (
            not getattr(settings, "PCE_CANARY_DEMO_MODE", False)
            or "v68-isolated" not in database_name.lower()
        ):
            raise CommandError("V68 command requires the isolated V68 database")
        user_model = get_user_model()
        owner = user_model.objects.get(
            username=getattr(
                settings, "PCE_CANARY_USERNAME", "purchase-canary-demo"
            )
        )
        source_review = BankSendProductionReleaseReview.objects.select_related(
            "trace__source_simulation__source_request"
        ).get(status="locked")
        framework = create_execution_framework(
            source_review=source_review,
            user=owner,
            environment="simulation",
        )
        request = source_review.trace.source_simulation.source_request
        create_simulated_artifacts(
            request=request,
            user=owner,
            execution_version=1,
        )
        framework, safety_review = perform_safety_review(
            framework=framework,
            user=owner,
        )
        result = {
            "result": "passed",
            "version": "V1.14.2.8.4.7.68",
            "frameworkStatus": framework.status,
            "safetyReviewResult": safety_review.result,
            "environment": framework.environment,
            "interfaceMode": framework.interface_mode,
            "executionMode": framework.execution_mode,
            **protection_counts(),
            "productionUserDataWritten": False,
        }
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))

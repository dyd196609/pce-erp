from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from system.models import User

from pde.formal_engineering_continuation_service import formal_rule_blueprints
from pde.models import EngineeringRuleDefinition
from pde.production_foundation_service import EngineeringLifecycleService, ProductionFoundationService


class Command(BaseCommand):
    help = "Register and release the two accepted engineering rule packages through formal services."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--confirm-isolated", action="store_true")

    def handle(self, *args, **options):
        database_path = Path(str(settings.DATABASES["default"]["NAME"])).resolve()
        protected = Path("D:/Dev-PCE/Acceptance/PDE-Operable-20260912/pde-operable-acceptance.sqlite3").resolve()
        developer = Path("D:/Dev-PCE/Source/backend/db.sqlite3").resolve()
        if (
            not options["confirm_isolated"]
            or database_path in {protected, developer}
            or "isolated" not in database_path.name.lower()
        ):
            raise CommandError(
                "This command is restricted to an explicitly confirmed database whose filename contains 'isolated'."
            )
        user = User.objects.filter(username=options["username"], is_active=True).first()
        if not user:
            raise CommandError("The requested active test identity was not found.")
        results = []
        for blueprint in formal_rule_blueprints():
            blueprint["company_id"] = user.company_id
            rule = EngineeringRuleDefinition.objects.filter(
                company_id=user.company_id,
                rule_code=blueprint["rule_code"],
                version=blueprint["version"],
            ).first()
            if rule:
                if rule.specification != blueprint["specification"]:
                    raise CommandError(
                        f"Existing {rule.rule_code}@{rule.version} does not match the accepted package contract."
                    )
                created = False
            else:
                result = ProductionFoundationService.write(
                    "engineering-rule-definitions",
                    user=user,
                    payload=blueprint,
                    idempotency_key=f"formal-engineering-rule:{blueprint['rule_code']}:{blueprint['version']}",
                    source_identity={
                        "sourceSystem": "PDE_FORMAL_ENGINEERING_CONTINUATION",
                        "sourceType": "CONTROLLED_RULE_REGISTRATION",
                        "sourceObjectType": "AcceptedEngineeringRulePackage",
                        "externalId": f"{blueprint['rule_code']}@{blueprint['version']}",
                        "auditMetadata": {"isolatedDatabase": database_path.name},
                    },
                )
                rule = EngineeringRuleDefinition.objects.get(pk=result["row"]["id"])
                created = True
            transitions = []
            if rule.status == "draft":
                result = EngineeringLifecycleService.transition(
                    "engineering-rule-definitions", object_id=rule.pk,
                    target_status="reviewed", user=user,
                    reason="隔离环境验证既有已验收规则包的正式评审状态转换",
                )
                transitions.append(result["auditId"])
                rule.refresh_from_db()
            if rule.status == "reviewed":
                result = EngineeringLifecycleService.transition(
                    "engineering-rule-definitions", object_id=rule.pk,
                    target_status="released", user=user,
                    reason="隔离环境发布既有已验收规则包用于正式接续链验证",
                )
                transitions.append(result["auditId"])
                rule.refresh_from_db()
            if rule.status != "released":
                raise CommandError(f"Rule {rule.rule_code}@{rule.version} did not reach released status.")
            results.append({
                "id": rule.pk, "rule": f"{rule.rule_code}@{rule.version}",
                "created": created, "status": rule.status, "transitionAuditIds": transitions,
            })
        self.stdout.write(self.style.SUCCESS(str({
            "database": str(database_path), "testIdentity": user.username, "rules": results,
        })))

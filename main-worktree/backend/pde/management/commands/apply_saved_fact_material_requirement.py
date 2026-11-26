"""Preview, apply, or read back one saved-fact material requirement contract."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from system.models import User

from pde.saved_fact_material_requirement_service import (
    SavedFactInputBinding,
    SavedFactMaterialRequirementContract,
    SavedFactMaterialRequirementError,
    apply_saved_fact_material_requirement,
    preview_saved_fact_material_requirement,
    readback_saved_fact_material_requirement,
)


def _contract(payload: dict) -> SavedFactMaterialRequirementContract:
    try:
        inputs = tuple(
            SavedFactInputBinding(
                variable=str(row["variable"]),
                fact_code=str(row["factCode"]),
                expected_uom_code=row.get("expectedUomCode"),
                unit_dimension=row.get("unitDimension"),
                unit_required=bool(row.get("unitRequired", True)),
                positive_required=bool(row.get("positiveRequired", True)),
                integer_required=bool(row.get("integerRequired", False)),
            )
            for row in payload["inputs"]
        )
        return SavedFactMaterialRequirementContract(
            mapping_no=str(payload["mappingNo"]),
            mapping_rule_code=str(payload["mappingRuleCode"]),
            mapping_version=str(payload["mappingVersion"]),
            rule_name=str(payload["ruleName"]),
            order_no=str(payload["orderNo"]),
            calculation_id=int(payload["calculationId"]),
            design_item_no=str(payload["designItemNo"]),
            material_id=int(payload["materialId"]),
            material_code=str(payload["materialCode"]),
            output_uom_code=str(payload["outputUomCode"]),
            output_name=str(payload["outputName"]),
            expression=str(payload["expression"]),
            inputs=inputs,
            primary_source_fact_code=str(payload["primarySourceFactCode"]),
            expected_quantity=Decimal(str(payload["expectedQuantity"])),
            authorization_reference=str(payload["authorizationReference"]),
            idempotency_key=str(payload["idempotencyKey"]),
            purpose_code=str(payload["purposeCode"]),
            quantity_basis=str(payload.get("quantityBasis", "ORDER_TOTAL")),
            item_role=str(payload.get("itemRole", "material")),
            requirement_type=str(payload.get("requirementType", "manufacturing")),
            supply_type=str(payload.get("supplyType", "MAKE")),
            scrap_rate=(
                Decimal(str(payload["scrapRate"]))
                if payload.get("scrapRate") is not None else None
            ),
            order_specification=dict(payload.get("orderSpecification") or {}),
            provenance=dict(payload.get("provenance") or {}),
            output_scale=int(payload.get("outputScale", 6)),
            output_unit_dimension=payload.get("outputUnitDimension", "area"),
            require_design_material_reference=payload.get(
                "requireDesignMaterialReference", True
            ),
            source_external_identity_id=(
                int(payload["sourceExternalIdentityId"])
                if payload.get("sourceExternalIdentityId") is not None else None
            ),
            allow_missing_design_revision_when_source_identity_confirmed=bool(
                payload.get(
                    "allowMissingDesignRevisionWhenSourceIdentityConfirmed", False
                )
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CommandError(f"CONTRACT_INVALID: {exc}") from exc


class Command(BaseCommand):
    help = "Use the formal saved-fact formula service; default mode is zero-write preview."

    def add_arguments(self, parser):
        parser.add_argument("--contract-file", required=True)
        parser.add_argument("--actor", required=True)
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--apply", action="store_true")
        mode.add_argument("--readback", action="store_true")

    def handle(self, *args, **options):
        contract_path = Path(options["contract_file"]).resolve()
        if not contract_path.is_file():
            raise CommandError("CONTRACT_FILE_NOT_FOUND")
        try:
            payload = json.loads(contract_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"CONTRACT_FILE_INVALID: {exc}") from exc
        actor = User.objects.filter(username=options["actor"], is_active=True).first()
        if not actor:
            raise CommandError("FORMAL_ACTOR_NOT_FOUND")
        contract = _contract(payload)
        try:
            if options["apply"]:
                result = apply_saved_fact_material_requirement(user=actor, contract=contract)
            elif options["readback"]:
                result = readback_saved_fact_material_requirement(user=actor, contract=contract)
            else:
                result = preview_saved_fact_material_requirement(user=actor, contract=contract)
        except SavedFactMaterialRequirementError as exc:
            raise CommandError(json.dumps({
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }, ensure_ascii=False, default=str)) from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))


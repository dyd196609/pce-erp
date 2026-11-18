"""Formalize only user-validated Group 1 facts and Group 2 product categories."""

from hashlib import sha256
import json
from pathlib import Path
from contextlib import nullcontext

from django.conf import settings
from django.db import transaction

from masterdata.base_data_comparison_runtime import build_batch1_comparison
from masterdata.models import ExternalIdentity, MasterDataWriteRequest, UnitOfMeasure
from pde.models import ProductCategory, ProductDefinition, ProductVersion, ProductConfiguration
from pde.production_foundation_service import (
    ProductionFoundationError,
    ProductionFoundationService,
    _actor_chain,
)
from procurement.models import Supplier
from sales.models import Customer
from system.authorization import AuthorizationService
from system.models import OrganizationOperatingAuditRecord


SOURCE_PATH = Path(__file__).with_name("base_data_comparison_source.json")
ACTION_CODE = "masterdata.validated_fact.formalize"
VERSION = "BASE-DATA-VALIDATED-FACT-FORMALIZATION-V1.0"
PRODUCT_CATEGORIES = ("房门", "柜体", "饰面")


def _norm(value):
    return "".join(str(value or "").casefold().split())


def _db_hash():
    path = Path(settings.DATABASES["default"]["NAME"])
    return sha256(path.read_bytes()).hexdigest().upper()


def _counts(company_id):
    return {
        "customers": Customer.objects.filter(company_id=company_id).count(),
        "suppliers": Supplier.objects.filter(company_id=company_id).count(),
        "uoms": UnitOfMeasure.objects.filter(company_id=company_id).count(),
        "productCategories": ProductCategory.objects.filter(company_id=company_id).count(),
        "productDefinitions": ProductDefinition.objects.filter(company_id=company_id).count(),
        "productVersions": ProductVersion.objects.filter(product__company_id=company_id).count(),
        "productConfigurations": ProductConfiguration.objects.filter(template__company_id=company_id).count(),
        "externalIdentities": ExternalIdentity.objects.filter(organization_id=company_id).count(),
        "writeRequests": MasterDataWriteRequest.objects.filter(organization_id=company_id).count(),
    }


def _source_identity(source, row, object_type):
    external_id = str(row.get("sequence") or row.get("sourceValue") or row.get("sourceRow"))
    fingerprint = sha256(json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "sourceSystem": source.get("fileName") or "PCE_VALIDATED_SOURCE",
        "sourceType": "USER_VALIDATED_XLSX",
        "sourceObjectType": object_type,
        "externalId": external_id,
        "sourceFingerprint": fingerprint,
        "auditMetadata": {
            "sourceFile": source.get("fileName"),
            "sourceSheet": source.get("sheet"),
            "sourceRow": row.get("sourceRow"),
            "sourceSha256": source.get("sha256"),
            "validation": "USER_VALIDATED",
            "formalizationVersion": VERSION,
        },
    }


def _identity_binding(company_id, identity):
    return ExternalIdentity.objects.filter(
        organization_id=company_id,
        source_system=identity["sourceSystem"],
        source_type=identity["sourceType"],
        source_object_type=identity["sourceObjectType"],
        external_id=identity["externalId"],
    ).first()


def _is_exact_identity_replay(*, company_id, entity, identity, instance):
    source_row = _identity_binding(company_id, identity)
    if not source_row:
        return False
    if source_row.target_entity_type != entity or source_row.target_entity_id != str(instance.pk):
        raise ProductionFoundationError(
            "SOURCE_IDENTITY_TARGET_CONFLICT", "来源身份已绑定其他正式对象。"
        )
    return source_row.mapping_status == ExternalIdentity.MappingStatus.MATCH


@transaction.atomic
def _bind_existing(*, user, company_id, entity, identity, instance, reason, execution_chain):
    lookup = {
        "organization_id": company_id,
        "source_system": identity["sourceSystem"],
        "source_type": identity["sourceType"],
        "source_object_type": identity["sourceObjectType"],
        "external_id": identity["externalId"],
    }
    source_row, _ = ExternalIdentity.objects.select_for_update().get_or_create(
        **lookup,
        defaults={
            "target_entity_type": entity,
            "target_entity_id": str(instance.pk),
            "mapping_status": ExternalIdentity.MappingStatus.MATCH,
            "source_fingerprint": identity.get("sourceFingerprint", ""),
            "audit_metadata": identity.get("auditMetadata") or {},
        },
    )
    if source_row.target_entity_type != entity or (
        source_row.target_entity_id and source_row.target_entity_id != str(instance.pk)
    ):
        raise ProductionFoundationError("SOURCE_IDENTITY_TARGET_CONFLICT", "来源身份已绑定其他正式对象。")
    source_row.target_entity_id = str(instance.pk)
    source_row.mapping_status = ExternalIdentity.MappingStatus.MATCH
    source_row.source_fingerprint = identity.get("sourceFingerprint", "")
    source_row.audit_metadata = identity.get("auditMetadata") or {}
    source_row.full_clean()
    source_row.save()
    key = f"{VERSION}:{entity}:{identity['externalId']}"
    request_hash = sha256(json.dumps({"entity": entity, "identity": identity}, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    ledger, created = MasterDataWriteRequest.objects.select_for_update().get_or_create(
        organization_id=company_id,
        action_code="masterdata.validated_fact.match_existing",
        idempotency_key=key,
        defaults={
            "entity_type": entity,
            "request_hash": request_hash,
            "source_identity": source_row,
            "status": MasterDataWriteRequest.Status.COMMITTED,
            "target_entity_id": str(instance.pk),
            "result": {"matchedExisting": True, "targetId": instance.pk},
            "audit_metadata": {"operatorId": user.pk, "formalizationVersion": VERSION},
        },
    )
    if not created and ledger.request_hash != request_hash:
        raise ProductionFoundationError("IDEMPOTENCY_PAYLOAD_CONFLICT", "同一来源身份的匹配内容发生变化。")
    if created:
        OrganizationOperatingAuditRecord.objects.create(
            action_code="masterdata.validated_fact.match_existing",
            actor=user,
            organization_id=company_id,
            target_type=instance.__class__.__name__,
            target_id=instance.pk,
            target_label=str(getattr(instance, "code", None) or instance.pk),
            reason=reason,
            before_snapshot={"state": "EXISTING", "factSource": "server"},
            after_snapshot={
                "state": "SOURCE_IDENTITY_BOUND",
                "sourceIdentityId": source_row.pk,
                "executionChain": execution_chain,
                "factSource": "server",
            },
        )
    return {"matchedExisting": True, "created": False, "targetId": instance.pk}


def _upsert_source_object(*, user, company_id, entity, source, row, model, name_field, payload, object_type, execution_chain):
    identity = _source_identity(source, row, object_type)
    matches = list(model.objects.filter(company_id=company_id))
    matches = [item for item in matches if _norm(getattr(item, name_field)) == _norm(row["sourceName"])]
    if len(matches) > 1:
        return {"blocked": True, "reason": "DUPLICATE_FORMAL_NAME", "sourceName": row["sourceName"]}
    if matches:
        if _is_exact_identity_replay(
            company_id=company_id, entity=entity, identity=identity, instance=matches[0],
        ):
            return {"matchedExisting": True, "created": False, "targetId": matches[0].pk}
        return _bind_existing(
            user=user, company_id=company_id, entity=entity, identity=identity,
            instance=matches[0], reason="人工已验证来源匹配现有正式对象", execution_chain=execution_chain,
        )
    result = ProductionFoundationService.write(
        entity,
        user=user,
        payload=payload,
        idempotency_key=f"{VERSION}:{entity}:{identity['externalId']}",
        source_identity=identity,
    )
    return {"matchedExisting": bool(result.get("idempotentReplay")), "created": not result.get("idempotentReplay"), "targetId": result["row"]["id"]}


class ValidatedFactFormalizationService:
    @staticmethod
    def facts(company_id):
        snapshot = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
        comparisons = {
            entity: build_batch1_comparison(entity, company_id)
            for entity in ("customers", "suppliers", "uoms")
        }
        categories = list(ProductCategory.objects.filter(company_id=company_id, name__in=PRODUCT_CATEGORIES).values("id", "code", "name", "industry_type", "is_active"))
        return {
            "version": VERSION,
            "factSource": "server",
            "sourceVersion": snapshot["version"],
            "databaseSha256": _db_hash(),
            "counts": _counts(company_id),
            "group1": {
                "customers": comparisons["customers"]["summary"],
                "suppliers": comparisons["suppliers"]["summary"],
                "uoms": comparisons["uoms"]["summary"],
            },
            "productCategories": categories,
            "productCategoryRequiredNames": list(PRODUCT_CATEGORIES),
            "productionBusinessOrderWriteCount": 0,
        }

    @classmethod
    def execute(cls, user):
        company_id = user.company_id
        decision = AuthorizationService.decide(
            user=user,
            action_code=ACTION_CODE,
            organization_id=company_id,
            business_object={"organizationId": company_id},
        )
        if not decision.get("allowed"):
            raise ProductionFoundationError(decision.get("decisionCode", "PERMISSION_DENIED"), decision.get("reason", "当前账户无正式化权限。"))
        execution_chain = _actor_chain(user)
        snapshot = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
        sources = snapshot["sources"]
        before = {"databaseSha256": _db_hash(), "counts": _counts(company_id)}
        results = {
            "customers": {"sourceAcceptedCount": 0, "createdCount": 0, "matchedExistingCount": 0, "blockedCount": 0, "simulatedFieldCount": 0},
            "suppliers": {"sourceValidCount": 0, "createdCount": 0, "matchedExistingCount": 0, "blockedEmptyNameCount": 0, "simulatedFieldCount": 0},
            "uoms": {"existingMappingCount": 0, "squareResult": "PENDING", "areaResult": "PENDING"},
            "productCategories": {"createdCount": 0, "matchedExistingCount": 0, "names": []},
        }
        # Each source write owns its own atomic/idempotent transaction. Keeping
        # all 121 source decisions plus audits in one SQLite rollback journal
        # is operationally fragile and adds no cross-object business invariant.
        with nullcontext():
            for row in sources["customers"]["rows"]:
                results["customers"]["sourceAcceptedCount"] += 1
                seq = int(row["sequence"])
                outcome = _upsert_source_object(
                    user=user, company_id=company_id, entity="customers", source=sources["customers"], row=row,
                    model=Customer, name_field="name", object_type="DEALER_SOURCE_ROW",
                    payload={
                        "company_id": company_id, "code": f"DLR-S07-{seq:03d}",
                        "name": row["sourceName"], "is_active": True,
                        "acceptance_marker": "DEALER|WHOLE_HOUSE_SOURCE|USER_VALIDATED",
                        "reason": "07经销商来源已人工验证；按经销商语义正式化",
                    },
                    execution_chain=execution_chain,
                )
                if outcome.get("blocked"):
                    results["customers"]["blockedCount"] += 1
                elif outcome["created"]:
                    results["customers"]["createdCount"] += 1
                else:
                    results["customers"]["matchedExistingCount"] += 1

            for row in sources["suppliers"]["rows"]:
                if not str(row.get("sourceName") or "").strip():
                    results["suppliers"]["blockedEmptyNameCount"] += 1
                    continue
                results["suppliers"]["sourceValidCount"] += 1
                seq = int(row["sequence"])
                outcome = _upsert_source_object(
                    user=user, company_id=company_id, entity="suppliers", source=sources["suppliers"], row=row,
                    model=Supplier, name_field="name", object_type="SUPPLIER_SOURCE_ROW",
                    payload={
                        "company_id": company_id, "code": f"WH-SUP-{seq:03d}",
                        "name": row["sourceName"], "category": "全屋定制/整木来源供应商",
                        "delivery_address": "SIMULATED_FOR_TEST",
                        "is_active": True, "data_origin": "WHOLE_HOUSE_SOURCE_REAL",
                        "source_evidence": [{
                            "sourceFile": sources["suppliers"]["fileName"],
                            "sourceSheet": sources["suppliers"]["sheet"],
                            "sourceRow": row["sourceRow"],
                            "sourceSha256": sources["suppliers"]["sha256"],
                            "fieldProvenance": {
                                "name": "REAL",
                                "delivery_address": "SIMULATED_FOR_TEST",
                                "otherAuxiliaryFields": "UNKNOWN",
                            },
                        }],
                        "enrichment_audit": [],
                        "reason": "09供应商有效名称已人工验证；空名称行明确排除",
                    },
                    execution_chain=execution_chain,
                )
                if outcome["created"]:
                    results["suppliers"]["createdCount"] += 1
                    results["suppliers"]["simulatedFieldCount"] += 1
                else:
                    results["suppliers"]["matchedExistingCount"] += 1

            uom_comparison = build_batch1_comparison("uoms", company_id)
            source_meta = {"fileName": "GROUP1_UOM_NORMALIZATION", "sheet": "USER_DECISION", "sha256": snapshot["version"]}
            for row in uom_comparison["rows"]:
                value = row["sourceValue"]
                identity = _source_identity(source_meta, {"sourceValue": value}, "UOM_SOURCE_VALUE")
                if value == "面积":
                    identity["sourceObjectType"] = "CALCULATION_BASIS_SOURCE_VALUE"
                    marker = type("CalculationBasisMarker", (), {"pk": company_id, "code": "AREA"})()
                    _bind_existing(user=user, company_id=company_id, entity="calculation-basis", identity=identity, instance=marker, reason="用户裁决：面积不是UOM，归入calculation_basis=AREA", execution_chain=execution_chain)
                    results["uoms"]["areaResult"] = "NOT_A_UOM / calculation_basis=AREA"
                    continue
                formal = row.get("formalMatch") or row.get("candidateFormal")
                if not formal:
                    raise ProductionFoundationError("UOM_MAPPING_MISSING", f"已验证UOM没有正式匹配：{value}")
                unit = UnitOfMeasure.objects.get(pk=formal["id"], company_id=company_id)
                _bind_existing(user=user, company_id=company_id, entity="units", identity=identity, instance=unit, reason=f"用户确认UOM归一：{value} → {unit.code}/{unit.name}", execution_chain=execution_chain)
                if value == "平方":
                    results["uoms"]["squareResult"] = f"{unit.code} / {unit.name} / {unit.symbol}"
                else:
                    results["uoms"]["existingMappingCount"] += 1

            for name in PRODUCT_CATEGORIES:
                existing = list(ProductCategory.objects.filter(company_id=company_id, name=name))
                if len(existing) > 1:
                    raise ProductionFoundationError("DUPLICATE_PRODUCT_CATEGORY", f"产品分类名称重复：{name}")
                identity = {
                    "sourceSystem": "08订单排产信息（样版）.xlsx",
                    "sourceType": "USER_VALIDATED_XLSX",
                    "sourceObjectType": "PRODUCT_CATEGORY",
                    "externalId": name,
                    "sourceFingerprint": sha256(name.encode("utf-8")).hexdigest(),
                    "auditMetadata": {"validation": "USER_VALIDATED", "formalizationVersion": VERSION},
                }
                if existing:
                    if not _is_exact_identity_replay(
                        company_id=company_id,
                        entity="product-categories",
                        identity=identity,
                        instance=existing[0],
                    ):
                        _bind_existing(user=user, company_id=company_id, entity="product-categories", identity=identity, instance=existing[0], reason="Group 2产品分类人工验收通过", execution_chain=execution_chain)
                    results["productCategories"]["matchedExistingCount"] += 1
                else:
                    result = ProductionFoundationService.write(
                        "product-categories", user=user,
                        payload={"company_id": company_id, "name": name, "industry_type": "wholeHouseWood", "is_active": True, "reason": "Group 2产品分类人工验收通过"},
                        idempotency_key=f"{VERSION}:product-category:{name}", source_identity=identity,
                    )
                    results["productCategories"]["createdCount"] += int(not result.get("idempotentReplay"))
                    results["productCategories"]["matchedExistingCount"] += int(bool(result.get("idempotentReplay")))
                results["productCategories"]["names"].append(name)

            OrganizationOperatingAuditRecord.objects.create(
                action_code=ACTION_CODE, actor=user, organization_id=company_id,
                target_type="ValidatedBaseDataFormalization", target_id=company_id,
                target_label=VERSION, reason="仅正式化Group 1已验证事实及三个产品分类",
                before_snapshot={**before, "authorization": decision, "factSource": "server"},
                after_snapshot={"results": results, "executionChain": execution_chain, "factSource": "server"},
            )
        after = {"databaseSha256": _db_hash(), "counts": _counts(company_id)}
        return {
            "version": VERSION, "before": before, "after": after,
            "results": results, "authorization": decision,
            "executionChain": execution_chain,
            "productionBusinessOrderWriteCount": 0,
            "materialWriteCount": 0,
        }

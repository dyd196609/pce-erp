import hashlib
import json
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from purchase_accounts_payable_draft.models import PurchaseAccountsPayableDraft
from purchase_accounts_payable_draft.services import generate_purchase_accounts_payable_draft
from purchase_canary.models import PurchaseCanaryBatch, PurchaseCanaryLineage
from purchase_canary.services import ensure_canary_group
from purchase_invoice_prepare.models import (
    LegalEntityInvoiceAuthorityRecord,
    PurchaseInvoicePrepare,
    SupplierInvoiceAuthorityRecord,
)
from purchase_invoice_prepare.services import generate_purchase_invoice_prepare
from purchase_invoice_prepare.v44_services import save_invoice_data, validate_invoice_data
from reconciliation.models import (
    BusinessActionAuditRecord,
    BusinessActionTransaction,
    PayableCheckAuthorityRecord,
    PurchaseReconciliation,
    PurchaseReconciliationCheckExecution,
    PurchaseReconciliationEvidence,
    SupplierSettlementAuthorityRecord,
)
from system.models import User
from workflow_runtime.state_transitions import (
    create_business_object_with_initial_state,
    transition_business_object,
)


TENANT_ID = "tenant-canary-demo"
COMPANY_ID = 45
VERSION = "V1.14.2.8.4.7.45.3"


def digest(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def line(item, quantity, unit_price, amount_excluding_tax, tax_rate, tax_amount, amount_including_tax):
    return {
        "itemCode": item,
        "itemName": f"{item} Material",
        "specification": "STD",
        "quantity": quantity,
        "unit": "EA",
        "unitPrice": unit_price,
        "amountExcludingTax": amount_excluding_tax,
        "taxRate": tax_rate,
        "taxAmount": tax_amount,
        "amountIncludingTax": amount_including_tax,
    }


LINEAGES = (
    {
        "code": "SUCCESS_STANDARD_01", "role": "standard_primary", "slug": "happy",
        "supplier_id": "SUP-V45", "supplier_name": "V45 Supplier",
        "seller_tax_id": "913100000000000045", "legal_entity_id": "LEGAL-V45",
        "legal_entity_name": "V45 Legal Entity", "buyer_tax_id": "914100000000000045",
        "ledger_book_id": "LEDGER-V45", "quantity": "10.0000", "ex": "100.00",
        "tax": "13.00", "total": "113.00", "invoice_type": "vat_special",
        "invoice_code": "V45CODE001", "invoice_number": "V45INV000001",
        "lines": (line("MAT-V45-01", "10.0000", "10.000000", "100.00", "0.130000", "13.00", "113.00"),),
    },
    {
        "code": "SUCCESS_STANDARD_02", "role": "standard_secondary", "slug": "standard-02",
        "supplier_id": "SUP-V45", "supplier_name": "V45 Supplier",
        "seller_tax_id": "913100000000000045", "legal_entity_id": "LEGAL-V45",
        "legal_entity_name": "V45 Legal Entity", "buyer_tax_id": "914100000000000045",
        "ledger_book_id": "LEDGER-V45", "quantity": "20.0000", "ex": "200.00",
        "tax": "26.00", "total": "226.00", "invoice_type": "vat_special",
        "invoice_code": "V45CODE002", "invoice_number": "V45INV000002",
        "lines": (line("MAT-V45-02", "20.0000", "10.000000", "200.00", "0.130000", "26.00", "226.00"),),
    },
    {
        "code": "SUCCESS_SECOND_SUPPLIER", "role": "supplier_diversity", "slug": "supplier-02",
        "supplier_id": "SUP-V45-B", "supplier_name": "V45 Supplier B",
        "seller_tax_id": "913100000000000046", "legal_entity_id": "LEGAL-V45",
        "legal_entity_name": "V45 Legal Entity", "buyer_tax_id": "914100000000000045",
        "ledger_book_id": "LEDGER-V45", "quantity": "30.0000", "ex": "300.00",
        "tax": "39.00", "total": "339.00", "invoice_type": "vat_special",
        "invoice_code": "V45CODE003", "invoice_number": "V45INV000003",
        "lines": (line("MAT-V45-03", "30.0000", "10.000000", "300.00", "0.130000", "39.00", "339.00"),),
    },
    {
        "code": "SUCCESS_MULTI_LINE", "role": "multi_line_invoice", "slug": "multi-line",
        "supplier_id": "SUP-V45-B", "supplier_name": "V45 Supplier B",
        "seller_tax_id": "913100000000000046", "legal_entity_id": "LEGAL-V45",
        "legal_entity_name": "V45 Legal Entity", "buyer_tax_id": "914100000000000045",
        "ledger_book_id": "LEDGER-V45", "quantity": "20.0000", "ex": "200.00",
        "tax": "26.00", "total": "226.00", "invoice_type": "vat_special",
        "invoice_code": "V45CODE004", "invoice_number": "V45INV000004",
        "lines": (
            line("MAT-V45-04A", "15.0000", "10.000000", "150.00", "0.130000", "19.50", "169.50"),
            line("MAT-V45-04B", "5.0000", "10.000000", "50.00", "0.130000", "6.50", "56.50"),
        ),
    },
    {
        "code": "SUCCESS_HIGH_AMOUNT", "role": "high_amount_boundary", "slug": "high-amount",
        "supplier_id": "SUP-V45-C", "supplier_name": "V45 Supplier C",
        "seller_tax_id": "913100000000000047", "legal_entity_id": "LEGAL-V45",
        "legal_entity_name": "V45 Legal Entity", "buyer_tax_id": "914100000000000045",
        "ledger_book_id": "LEDGER-V45", "quantity": "100.0000", "ex": "1000.00",
        "tax": "130.00", "total": "1130.00", "invoice_type": "vat_special",
        "invoice_code": "V45CODE005", "invoice_number": "V45INV000005",
        "lines": (line("MAT-V45-05", "100.0000", "10.000000", "1000.00", "0.130000", "130.00", "1130.00"),),
    },
    {
        "code": "SUCCESS_LOW_AMOUNT", "role": "low_amount_boundary", "slug": "low-amount",
        "supplier_id": "SUP-V45-C", "supplier_name": "V45 Supplier C",
        "seller_tax_id": "913100000000000047", "legal_entity_id": "LEGAL-V45",
        "legal_entity_name": "V45 Legal Entity", "buyer_tax_id": "914100000000000045",
        "ledger_book_id": "LEDGER-V45", "quantity": "1.0000", "ex": "10.00",
        "tax": "1.30", "total": "11.30", "invoice_type": "vat_special",
        "invoice_code": "V45CODE006", "invoice_number": "V45INV000006",
        "lines": (line("MAT-V45-06", "1.0000", "10.000000", "10.00", "0.130000", "1.30", "11.30"),),
    },
    {
        "code": "SUCCESS_ALTERNATE_VALID_TAX_PROFILE", "role": "alternate_tax_profile", "slug": "tax-profile",
        "supplier_id": "SUP-V45-C", "supplier_name": "V45 Supplier C",
        "seller_tax_id": "913100000000000047", "legal_entity_id": "LEGAL-V45-B",
        "legal_entity_name": "V45 Legal Entity B", "buyer_tax_id": "914100000000000046",
        "ledger_book_id": "LEDGER-V45-B", "quantity": "50.0000", "ex": "500.00",
        "tax": "30.00", "total": "530.00", "invoice_type": "vat_electronic",
        "invoice_code": "", "invoice_number": "V45ELEC000007",
        "lines": (line("MAT-V45-07", "50.0000", "10.000000", "500.00", "0.060000", "30.00", "530.00"),),
    },
    {
        "code": "SUCCESS_IDEMPOTENCY_RECOVERY", "role": "idempotency_recovery_reserve", "slug": "recovery",
        "supplier_id": "SUP-V45-B", "supplier_name": "V45 Supplier B",
        "seller_tax_id": "913100000000000046", "legal_entity_id": "LEGAL-V45-B",
        "legal_entity_name": "V45 Legal Entity B", "buyer_tax_id": "914100000000000046",
        "ledger_book_id": "LEDGER-V45-B", "quantity": "70.0000", "ex": "700.00",
        "tax": "91.00", "total": "791.00", "invoice_type": "vat_special",
        "invoice_code": "V45CODE008", "invoice_number": "V45INV000008",
        "lines": (line("MAT-V45-08", "70.0000", "10.000000", "700.00", "0.130000", "91.00", "791.00"),),
    },
)


class Command(BaseCommand):
    help = "Idempotently maintain eight formal pass-through purchase canary lineages."

    def handle(self, *args, **options):
        if not getattr(settings, "PCE_CANARY_DEMO_MODE", False):
            raise CommandError("This command is restricted to PCE_CANARY_DEMO_MODE")
        if settings.PCE_CANARY_TENANT_ID != TENANT_ID:
            raise CommandError("Unexpected persistent canary tenant")
        ensure_canary_group()
        batch = PurchaseCanaryBatch.objects.get(batch_id=settings.PCE_CANARY_BATCH_ID)
        if batch.version != VERSION or batch.schema_version != "purchase-canary-lineage-v2":
            batch.version = VERSION
            batch.schema_version = "purchase-canary-lineage-v2"
            batch.save(update_fields=["version", "schema_version"])
        before = self.counts()
        user = self.ensure_user()
        output = []
        for index, spec in enumerate(LINEAGES, start=1):
            with transaction.atomic():
                reconciliation = self.ensure_reconciliation(user, spec, index)
            prepare = self.ensure_prepare(user, reconciliation, spec)
            result = self.ensure_draft(user, prepare, spec)
            draft = PurchaseAccountsPayableDraft.objects.get(source_purchase_invoice_prepare=prepare)
            lineage = self.ensure_lineage(batch, spec, reconciliation, prepare, draft)
            output.append({
                "scenarioCode": lineage.scenario_code,
                "canaryLineageId": lineage.canary_lineage_id,
                "reconciliationNo": reconciliation.reconciliation_no,
                "prepareNo": prepare.prepare_no,
                "draftNo": draft.draft_no,
                "invoiceNumber": draft.invoice_number,
                "idempotencyKey": draft.idempotency_key,
                "numberReservationId": draft.number_reservation_id,
                "transactionId": draft.business_transaction.transaction_id,
                "auditRecordId": draft.audit_record_id,
                "classification": result["classification"],
                "sourceRelationHash": lineage.source_relation_hash,
            })
        if output[0]["reconciliationNo"] != "PRC20260700000001" or output[0]["prepareNo"] != "PIP20260700000001" or output[0]["draftNo"] != "APD20260700000001":
            raise CommandError(f"First lineage stable numbers changed: {output[0]}")
        if batch.lineages.filter(downstream_eligible=True, next_stage_consumed=False).count() < 8:
            raise CommandError("downstreamEligibleLineageCount is below 8")
        self.stdout.write(json.dumps({
            "result": "passed", "version": VERSION, "tenantId": TENANT_ID,
            "canaryBatchId": batch.batch_id, "before": before, "after": self.counts(),
            "downstreamEligibleLineageCount": len(output), "nextStageConsumedCount": 0,
            "lineages": output,
        }, ensure_ascii=False, sort_keys=True))

    def ensure_user(self):
        user, created = User.objects.get_or_create(username="purchase-canary-demo", defaults={
            "real_name": "Persistent Purchase Canary", "company_id": COMPANY_ID,
            "is_superuser": True, "is_staff": True, "is_active": True,
        })
        changed = []
        for field, value in {
            "real_name": "Persistent Purchase Canary", "company_id": COMPANY_ID,
            "is_superuser": True, "is_staff": True, "is_active": True,
        }.items():
            if getattr(user, field) != value:
                setattr(user, field, value)
                changed.append(field)
        if created:
            user.set_unusable_password()
            changed.append("password")
        if changed:
            user.save(update_fields=changed)
        return user

    def transition_fixture_reconciliation(self, source, user, idempotency_key):
        evidence = {
            "sourceStatus": PurchaseReconciliation.Status.DRAFT,
            "targetStatus": PurchaseReconciliation.Status.MATCHED,
            "checkResultCode": "PRC_CHECK_MATCHED",
            "differenceCount": 0,
        }
        evidence_hash = digest(evidence)
        tx = BusinessActionTransaction.objects.create(
            transaction_id=f"PRC-CANARY-CHECK-{uuid.uuid4().hex}",
            action_code="complete_purchase_reconciliation",
            idempotency_key=idempotency_key,
            tenant_id=source.tenant_id,
            source_key=source.source_key,
            command_id=f"PRC-CANARY-CMD-{uuid.uuid4().hex}",
            transaction_plan_id="purchase-reconciliation-check-atomic-v1",
            review_id=f"reconciliation-check:{source.pk}:2",
            review_hash=evidence_hash,
            status=BusinessActionTransaction.Status.COMMITTED,
            outcome="checked",
            commit_status="committed",
            recovery_status="not_required",
            result_hash=evidence_hash,
            reconciliation=source,
        )
        audit = BusinessActionAuditRecord.objects.create(
            transaction=tx,
            action_code=tx.action_code,
            tenant_id=source.tenant_id,
            actor=user,
            source_key=source.source_key,
            reconciliation=source,
            result="committed",
            target_type="purchase_reconciliation",
            target_id=source.pk,
            target_no=source.reconciliation_no,
            review_id=tx.review_id,
            review_hash=evidence_hash,
            command_id=tx.command_id,
            idempotency_key=idempotency_key,
            actor_name=user.get_username(),
            tenant_or_scope=f"{source.tenant_id}:company:{source.company_id}",
            evidence_hash=evidence_hash,
            evidence=evidence,
        )
        transition_business_object(
            business_object=source,
            object_type="purchase_reconciliation",
            source_state=PurchaseReconciliation.Status.DRAFT,
            target_state=PurchaseReconciliation.Status.MATCHED,
            action_code=tx.action_code,
            operator=user,
            reason="Isolated canary fixture reconciliation check completed",
            audit_reference=f"BusinessActionAuditRecord:{audit.pk}",
            allowed_transitions={
                (
                    PurchaseReconciliation.Status.DRAFT,
                    PurchaseReconciliation.Status.MATCHED,
                ),
            },
        )

    def ensure_reconciliation(self, user, spec, index):
        slug = spec["slug"]
        now = timezone.now()
        settlement, _ = SupplierSettlementAuthorityRecord.objects.get_or_create(
            authority_object_id=f"settlement-canary-{slug}",
            defaults={
                "settlement_no": f"SET202607{index:08d}", "tenant_id": TENANT_ID,
                "company_id": COMPANY_ID, "supplier_id": spec["supplier_id"],
                "supplier_name": spec["supplier_name"], "legal_entity_id": spec["legal_entity_id"],
                "ledger_book_id": spec["ledger_book_id"], "currency": "CNY",
                "amount": Decimal(spec["total"]), "quantity": Decimal(spec["quantity"]),
                "business_status": "ready_for_reconciliation", "authority_version": 1,
                "business_hash": digest(["settlement", slug]), "occurred_at": now,
            },
        )
        payable, _ = PayableCheckAuthorityRecord.objects.get_or_create(
            authority_object_id=f"payable-check-canary-{slug}",
            defaults={
                "payable_check_no": f"PYC202607{index:08d}", "tenant_id": TENANT_ID,
                "company_id": COMPANY_ID, "supplier_id": spec["supplier_id"],
                "legal_entity_id": spec["legal_entity_id"], "ledger_book_id": spec["ledger_book_id"],
                "currency": "CNY", "checked_amount": Decimal(spec["total"]),
                "checked_quantity": Decimal(spec["quantity"]), "business_status": "payable_prepared",
                "authority_version": 1, "business_hash": digest(["payable", slug]), "occurred_at": now,
            },
        )
        reconciliation_no = f"PRC202607{index:08d}"
        source = PurchaseReconciliation.objects.filter(
            reconciliation_no=reconciliation_no,
        ).first()
        if source is None:
            source = create_business_object_with_initial_state(
                model=PurchaseReconciliation,
                initial_state=PurchaseReconciliation.Status.DRAFT,
                reconciliation_no=reconciliation_no,
                tenant_id=TENANT_ID,
                company_id=COMPANY_ID,
                source_key=f"supplier-settlement:{TENANT_ID}:{slug}",
                source_supplier_settlement_no=settlement.settlement_no,
                source_payable_check_no=payable.payable_check_no,
                source_payable_prepare_no=f"PYP202607{index:08d}",
                purchase_order_no=f"PO202607{index:08d}",
                price_approval_no=f"PRA202607{index:08d}",
                supplier_id=spec["supplier_id"],
                supplier_name=spec["supplier_name"],
                legal_entity_id=spec["legal_entity_id"],
                ledger_book_id=spec["ledger_book_id"],
                currency="CNY",
                exchange_rate=Decimal("1.00000000"),
                accounting_period="2026-07",
                settlement_amount=Decimal(spec["total"]),
                quantity=Decimal(spec["quantity"]),
                unit="EA",
                source_candidate_id=f"candidate-canary-{slug}",
                simulation_request_id=f"simulation-request-canary-{slug}",
                simulation_result_id=f"simulation-result-canary-{slug}",
                source_snapshot_hash=digest(["source", slug]),
                review_id=f"review-canary-{slug}",
                review_hash=digest(["review", slug]),
                command_id=f"command-canary-{slug}",
                transaction_plan_id="purchase-reconciliation-atomic-v1",
                idempotency_key=f"reconciliation-canary-{slug}",
                created_by=user,
                check_result_code="",
                difference_count=0,
                checked_at=None,
                checked_by=None,
                version=1,
            )
            source.check_result_code = "PRC_CHECK_MATCHED"
            source.difference_count = 0
            source.checked_at = now
            source.checked_by = user
            source.save(update_fields=[
                "check_result_code",
                "difference_count",
                "checked_at",
                "checked_by",
                "updated_at",
            ])
            self.transition_fixture_reconciliation(
                source,
                user,
                f"reconciliation-check-canary-{slug}",
            )
            source.refresh_from_db()
        for authority_type, provider, repository, authority, number in (
            ("supplier_settlement", "SupplierSettlementEvidenceProvider", "SupplierSettlementAuthorityRepository", settlement, settlement.settlement_no),
            ("payable_check", "PayableCheckEvidenceProvider", "PayableCheckAuthorityRepository", payable, payable.payable_check_no),
        ):
            PurchaseReconciliationEvidence.objects.get_or_create(
                reconciliation=source, authority_type=authority_type,
                authority_object_id=authority.authority_object_id,
                defaults={
                    "provider_code": provider, "repository_code": repository,
                    "authority_object_no": number, "authority_version": authority.authority_version,
                    "business_hash": authority.business_hash,
                    "evidence": {"source": authority_type, "independentAuthority": True},
                },
            )
        PurchaseReconciliationCheckExecution.objects.get_or_create(
            idempotency_key=f"reconciliation-check-canary-{slug}",
            defaults={
                "reconciliation": source, "request_hash": digest(["check", slug]),
                "expected_version": 1, "result_status": "matched",
                "check_result_code": "PRC_CHECK_MATCHED", "difference_count": 0,
                "actor": user, "result_payload": {"result": "matched", "differenceCount": 0},
            },
        )
        return source

    def ensure_prepare(self, user, source, spec):
        slug = spec["slug"]
        generated = generate_purchase_invoice_prepare(
            user=user, reconciliation_id=source.pk,
            idempotency_key=f"pip-canary-{slug}-generate",
            expected_reconciliation_version=2, expected_check_version=2,
            explicit_user_action=True,
        )
        prepare = PurchaseInvoicePrepare.objects.get(pk=generated["data"]["id"])
        SupplierInvoiceAuthorityRecord.objects.get_or_create(
            tenant_id=TENANT_ID, supplier_id=spec["supplier_id"],
            defaults={
                "company_id": COMPANY_ID, "supplier_name": spec["supplier_name"],
                "seller_tax_id": spec["seller_tax_id"], "status": "active",
                "authority_version": 1, "business_hash": digest(["supplier-invoice", spec["supplier_id"]]),
            },
        )
        LegalEntityInvoiceAuthorityRecord.objects.get_or_create(
            tenant_id=TENANT_ID, legal_entity_id=spec["legal_entity_id"],
            defaults={
                "company_id": COMPANY_ID, "legal_entity_name": spec["legal_entity_name"],
                "buyer_tax_id": spec["buyer_tax_id"], "ledger_book_id": spec["ledger_book_id"],
                "currency": "CNY", "status": "active", "authority_version": 1,
                "business_hash": digest(["legal-invoice", spec["legal_entity_id"]]),
            },
        )
        if prepare.current_data_version == 0:
            lines = [{"lineNo": number, **value} for number, value in enumerate(spec["lines"], start=1)]
            save_invoice_data(
                user=user, prepare_id=prepare.pk, idempotency_key=f"pip-canary-{slug}-save",
                expected_version=prepare.version, expected_data_version=0, explicit_user_action=True,
                invoice_data={
                    "invoiceType": spec["invoice_type"], "invoiceCode": spec["invoice_code"],
                    "invoiceNumber": spec["invoice_number"], "invoiceDate": "2026-07-23",
                    "sellerName": spec["supplier_name"], "sellerTaxId": spec["seller_tax_id"],
                    "buyerName": spec["legal_entity_name"], "buyerTaxId": spec["buyer_tax_id"],
                    "currency": "CNY", "amountExcludingTax": spec["ex"],
                    "taxAmount": spec["tax"], "amountIncludingTax": spec["total"], "lines": lines,
                },
            )
            prepare.refresh_from_db()
        if prepare.validation_status != "passed":
            validate_invoice_data(
                user=user, prepare_id=prepare.pk,
                idempotency_key=f"pip-canary-{slug}-validate",
                expected_version=prepare.version, expected_data_version=prepare.current_data_version,
                expected_reconciliation_version=source.version,
                expected_check_version=prepare.source_check_version, explicit_user_action=True,
            )
            prepare.refresh_from_db()
        return prepare

    def ensure_draft(self, user, prepare, spec):
        source = prepare.source_purchase_reconciliation
        return generate_purchase_accounts_payable_draft(
            user=user, source_prepare_id=prepare.pk,
            idempotency_key=f"apd-canary-{spec['slug']}-generate",
            expected_prepare_version=prepare.version,
            expected_invoice_data_version=prepare.current_data_version,
            expected_validation_version=prepare.current_validation_version,
            expected_reconciliation_version=source.version,
            expected_check_version=prepare.source_check_version, explicit_user_action=True,
        )

    def ensure_lineage(self, batch, spec, reconciliation, prepare, draft):
        upstream = [
            reconciliation.price_approval_no, reconciliation.purchase_order_no,
            reconciliation.source_payable_prepare_no,
            reconciliation.source_supplier_settlement_no,
            reconciliation.source_payable_check_no, reconciliation.reconciliation_no,
            prepare.prepare_no, draft.draft_no,
        ]
        relation_hash = digest({
            "scenarioCode": spec["code"], "upstreamObjectNos": upstream,
            "invoiceNumber": draft.invoice_number, "sourceKey": draft.source_key,
            "idempotencyKey": draft.idempotency_key,
        })
        values = {
                "canary_lineage_id": f"{batch.batch_id}:{spec['code']}",
                "scenario_class": "pass_through", "scenario_role": spec["role"],
                "current_module_code": "account-payable-draft",
                "current_object_type": "purchaseAccountsPayableDraft",
                "current_object_id": draft.pk, "current_object_no": draft.draft_no,
                "downstream_eligible": True,
                "reserved_for_next_module": "payable_confirmation_prepare",
                "next_stage_consumed": False, "upstream_object_nos": upstream,
                "source_relation_hash": relation_hash, "blocking_module": "",
                "blocking_rule_code": "", "blocking_reason": "",
        }
        lineage = PurchaseCanaryLineage.objects.filter(
            batch=batch, scenario_code=spec["code"]
        ).first()
        if lineage is None:
            lineage = PurchaseCanaryLineage.objects.create(
                batch=batch, scenario_code=spec["code"], **values
            )
        else:
            changed = []
            for field, value in values.items():
                if getattr(lineage, field) != value:
                    setattr(lineage, field, value)
                    changed.append(field)
            if changed:
                lineage.save(update_fields=[*changed, "updated_at"])
        return lineage

    def counts(self):
        return {
            "supplierSettlementAuthorities": SupplierSettlementAuthorityRecord.objects.filter(tenant_id=TENANT_ID).count(),
            "payableCheckAuthorities": PayableCheckAuthorityRecord.objects.filter(tenant_id=TENANT_ID).count(),
            "purchaseReconciliations": PurchaseReconciliation.objects.filter(tenant_id=TENANT_ID).count(),
            "purchaseInvoicePrepares": PurchaseInvoicePrepare.objects.filter(tenant_id=TENANT_ID).count(),
            "purchaseAccountsPayableDrafts": PurchaseAccountsPayableDraft.objects.filter(tenant_id=TENANT_ID).count(),
            "lineages": PurchaseCanaryLineage.objects.filter(batch__batch_id=settings.PCE_CANARY_BATCH_ID).count(),
        }

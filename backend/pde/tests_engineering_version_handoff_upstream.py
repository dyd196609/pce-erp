"""Version handoff regressions; synthetic data in the isolated test database.

The established document release fixture supplies its two upstream proof stubs.
Output generation/release, duties, immutable identities and transactions are
real. These tests do not establish a formal document or business admission.
"""
from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection, transaction
from django.utils import timezone

from masterdata.models import ExternalIdentity, MasterDataWriteRequest
from planning.models import Demand
from sales.manufacturing_input import ManufacturingInputError, resolve_order_engineered_input
from system.models import OrganizationOperatingAuditRecord
from workflow_runtime.models import BusinessStateTransition

from .formal_engineering_continuation_service import _calculation_has_fixed_consumers, _retire_unconsumed_calculation
from .manufacturing_output_generation_service import (
    ACTION, ManufacturingOutputError, candidate_projection, generate_manufacturing_output,
    generation_readback, resolve_sources, validate_selected_output,
)
from .manufacturing_output_release_service import (
    ACTION as RELEASE_ACTION, release_manufacturing_output, release_preflight,
)
from .models import (
    BOMVersion, BOMItemSourceRequirement, EngineeringCalculationRecord, EngineeringDocumentVersion,
    EngineeringCalculationDetail, EngineeringDerivedFact, EngineeringMaterialRequirement, EngineeringRuleDefinition,
    OrderEngineeringBaseline, OrderEngineeringBaselineItem,
    ProductManufacturingOutput, RoutingStep, RoutingVersion,
)
from .order_engineering_document_registration_service import (
    OrderEngineeringDocumentRegistrationError, OrderEngineeringDocumentRegistrationService,
)
from .tests_manufacturing_output_generation import MODULE, SCOPE
from .tests_manufacturing_output_release import fixture
from .product_version_management_service import _baseline_facts, _baseline_display_users


def finalize_runtime_fixture(owner, calculation, baseline, bom=None):
    """Synthetic saved source facts; native output generation/release remain real.

    This supplies upstream immutable input/audit records, not an import, formula
    execution or formal-production certificate. No runtime validator is patched.
    """
    from . import formal_engineering_continuation_service as formal
    from .engineering_rule_foundation import specification_hash
    from .product_version_management_service import _content_snapshot
    from .saved_fact_material_requirement_service import SERVICE_CODE, REQUIREMENT_ACTION_CODE, _hash
    actor = getattr(owner,'executor',None) or owner.actor
    calculation.refresh_from_db(); baseline.refresh_from_db()
    rows = list(baseline.items.select_related('design_item').order_by(
        'design_item__sales_order_item__line_no','source_attribute_id','design_item_id','pk'))
    for row in rows:
        if not all(key in row.content_snapshot for key in ('designItem', 'source', 'revision')):
            # The older model-only fixture predates object input persistence.
            # Build its synthetic source before any native output/adoption.
            design = row.design_item
            existing = deepcopy(design.existing_design_data or {})
            existing.setdefault('provenance', {'sourceSheet':'FIXTURE','sourceRow':design.pk})
            type(design).objects.filter(pk=design.pk).update(existing_design_data=existing,
                source_content_hash=row.source_record.content_hash)
            design.refresh_from_db()
            snapshot = _content_snapshot(design, row.design_revision)
            type(row).objects.filter(pk=row.pk).update(content_snapshot=snapshot,
                source_content_hash_snapshot=row.source_record.content_hash)
            row.content_snapshot = snapshot
            row.source_content_hash_snapshot = row.source_record.content_hash
        actual = formal._hash(row.content_snapshot)
        if row.content_hash != actual:
            type(row).objects.filter(pk=row.pk).update(content_hash=actual);row.content_hash=actual
    header = formal._hash([row.content_hash for row in rows])
    if baseline.snapshot_hash != header:
        type(baseline).objects.filter(pk=baseline.pk).update(snapshot_hash=header,scope_item_count=len(rows))
        baseline.refresh_from_db()
    selected = sorted((row for row in rows if row.design_item.sales_order_item_id==calculation.sales_order_item_id),
        key=lambda row:(row.source_attribute_id,row.design_item_id,row.pk))
    reference = formal._baseline_reference(baseline,selected)
    facts = list(calculation.derived_facts.select_related('source_detail__rule','uom').order_by('sequence','pk'))
    if not facts:
        spec = {'rulePackage':{'code':'RUNTIME-FIXTURE','version':'V1'},
            'inputs':[{'canonicalName':'quantity','valueType':'decimal','unit':owner.uom.code,
                'unitDimension':'count','sourceType':'ENGINEERING_INPUT','required':True}],
            'outputs':[{'canonicalName':'runtime_quantity','valueType':'decimal','unit':owner.uom.code,
                'unitDimension':'count','resultDomain':'DERIVED_FACT'}],
            'expression':'quantity','dependencies':[],'decimalPrecision':28,'outputScale':6,
            'roundingMode':'ROUND_HALF_UP','priority':1}
        rule=EngineeringRuleDefinition(company=owner.company,rule_code=f'RUNTIME-{calculation.pk}',
            rule_name='isolated saved fact',version='V1',rule_kind='formula',specification=spec,status='released')
        rule._business_state_initialization_authorized=True;rule.save()
        completed_at=timezone.now()
        detail=EngineeringCalculationDetail.objects.create(calculation=calculation,sequence=1,rule=rule,
            rule_code=rule.rule_code,rule_version=rule.version,expression_snapshot='quantity',
            input_snapshot={},output_name='runtime_quantity',output_value={'decimal':'1'},uom=owner.uom,
            precision=28,rounding='ROUND_HALF_UP',status='succeeded',
            started_at=completed_at,finished_at=completed_at)
        facts=[EngineeringDerivedFact.objects.create(calculation=calculation,source_detail=detail,rule=rule,
            fact_code=f'RUNTIME-{calculation.pk}',canonical_field='runtime_quantity',value={'decimal':'1'},
            uom=owner.uom,source_path='isolated.saved.fixture',trace={'unitSnapshot':owner.uom.code})]
    trace=deepcopy(calculation.trace or {})
    results=trace.get('resultSnapshot') or [{'factId':fact.pk,'detailId':fact.source_detail_id,
        'canonicalField':fact.canonical_field,'value':fact.value,'unit':fact.uom.code if fact.uom_id else None,
        'ruleCode':fact.source_detail.rule_code,'ruleVersion':fact.source_detail.rule_version} for fact in facts]
    graph=trace.get('ruleGraphSnapshot') or [{'id':fact.source_detail.rule_id,
        'ruleCode':fact.source_detail.rule_code,'version':fact.source_detail.rule_version,
        'specificationHash':specification_hash(fact.source_detail.rule.specification)} for fact in facts]
    inputs=[formal._snapshot_design_input(row) for row in selected]
    objects=[{'baselineItemId':row['baselineItemId'],'designItemId':row['designItemId'],
        'designItemNo':row['designItemNo'],'sourceAttributeId':row['sourceAttributeId'],
        'sourceKey':row['sourceKey'],'contentHash':row['baselineContentHash'],
        'sourceVersion':row['sourceVersion'],'sourceContentHash':row['sourceContentHash'],'input':row} for row in inputs]
    input_hash=formal.calculation_input_hash(reference,objects)
    trace.update(baselineReference=reference,resultSnapshot=results,ruleGraphSnapshot=graph,
        resultHash=formal._hash(results),objectInputSnapshot=objects,objectInputSnapshotHash=input_hash,
        sourceReference={'id':calculation.source_record_id,'sourceNo':calculation.source_record.source_no,
            'sourceVersion':calculation.source_record.source_version,'contentHash':calculation.source_record.content_hash})
    if trace != calculation.trace:
        type(calculation).objects.filter(pk=calculation.pk).update(trace=trace,
            input_hash=input_hash,result_hash=formal._hash(results),rule_graph_hash=formal._hash(graph))
        calculation.refresh_from_db()
    existing=list(OrganizationOperatingAuditRecord.objects.filter(organization_id=owner.company.pk,
        target_type='EngineeringCalculationRecord',target_id=calculation.pk))
    if not any((row.after_snapshot or {}).get('state',{}).get('status')=='completed' for row in existing):
        keys=('company_id','scope','source_record_id','sales_order_item_id','engineering_instance_id',
            'input_hash','rule_graph_hash','result_hash','trace')
        state={key:getattr(calculation,key) for key in keys}
        audit=OrganizationOperatingAuditRecord.objects.create(organization=owner.company,actor=actor,
            target_type='EngineeringCalculationRecord',target_id=calculation.pk,action_code='production.engineering.calculation.execute',
            target_label='isolated saved-main fixture',reason='isolated upstream completed record',
            after_snapshot={'state':{**state,'status':'completed'},'authorization':{'allowed':True},
                'executionChain':{'account':actor.username}})
        BusinessStateTransition.objects.create(object_type='EngineeringCalculationRecord',object_id=calculation.pk,
            source_state='running',target_state='completed',action_code='production.engineering.calculation.execute',
            operator=actor,reason='isolated upstream completed record',
            audit_reference=f'OrganizationOperatingAuditRecord:{audit.pk}',version=1)
    if bom is None:return
    for item in bom.items.order_by('line_no','pk'):
        if item.source_requirements.exists():continue
        fact=facts[item.line_no-1]
        source_facts=[{'factId':fact.pk,'sourceDetailId':fact.source_detail_id,
            'value':str(fact.value['decimal']),'uom':fact.uom.code if fact.uom_id else None}]
        output={'materialId':item.material_id,'quantityBasis':'ORDER_TOTAL','itemRole':item.item_role,
            'requirementType':item.requirement_type,'supplyType':item.supply_type,
            'orderSpecification':item.order_specification,'scrapRate':str(item.scrap_rate) if item.scrap_rate is not None else None}
        mapping=EngineeringRuleDefinition(company=owner.company,rule_code=f'RUNTIME-MATERIAL-{calculation.pk}-{item.pk}',
            rule_name='isolated saved material',version='V1',rule_kind='formula',specification={'outputs':[output]},status='released')
        mapping._business_state_initialization_authorized=True;mapping.save()
        req=EngineeringMaterialRequirement.objects.create(calculation=calculation,source_detail=fact.source_detail,
            sequence=fact.source_detail.sequence,material=item.material,quantity_basis='ORDER_TOTAL',
            calculated_quantity=item.quantity,order_quantity=calculation.sales_order_item.quantity,
            net_quantity=item.quantity,uom=item.uom,item_role=item.item_role,requirement_type=item.requirement_type,
            supply_type=item.supply_type,order_specification=item.order_specification,
            scrap_rate_status=item.scrap_rate_status,scrap_rate=item.scrap_rate,
            source_path='isolated.saved.material',trace={'serviceCode':SERVICE_CODE,'mappingRuleId':mapping.pk,
                'mappingSpecificationHash':specification_hash(mapping.specification),'operatorId':actor.pk,
                'sourceFacts':source_facts})
        body={'mappingRuleId':mapping.pk,'mappingSpecificationHash':specification_hash(mapping.specification),
            'calculationId':calculation.pk,'calculationResultHash':calculation.result_hash,
            'materialId':req.material_id,'quantity':str(req.net_quantity),'uom':req.uom.code}
        audit=OrganizationOperatingAuditRecord.objects.create(organization=owner.company,actor=actor,
            target_type='EngineeringMaterialRequirement',target_id=req.pk,action_code=REQUIREMENT_ACTION_CODE,
            target_label='isolated saved material',reason='isolated input authority',
            after_snapshot={'request':body,'sourceFacts':source_facts})
        identity=ExternalIdentity.objects.create(organization_id=owner.company.pk,source_system='FIXTURE',
            source_type='SAVED_MATERIAL',source_object_type='EngineeringMaterialRequirement',
            external_id=f'material-{req.pk}',target_entity_type='engineering-material-requirements',target_entity_id=str(req.pk))
        MasterDataWriteRequest.objects.create(organization_id=owner.company.pk,source_identity=identity,
            action_code=REQUIREMENT_ACTION_CODE,entity_type='EngineeringMaterialRequirement',target_entity_id=str(req.pk),
            idempotency_key=f'runtime-material-{req.pk}',request_hash=_hash(body),status='COMMITTED',
            audit_metadata={'actor':{'accountId':actor.pk}},
            result={'requirementId':req.pk,'mappingRuleId':mapping.pk,'auditId':audit.pk,
                'quantity':str(req.net_quantity),'uom':req.uom.code})
        BOMItemSourceRequirement.objects.create(bom_item=item,material_requirement=req,contributed_quantity=item.quantity)


@override_settings(PCE_MANUFACTURING_OUTPUT_GENERATION_SCOPE=SCOPE)
class EngineeringVersionHandoffUpstreamTests(TestCase):
    def setUp(self):
        fixture(self)
        finalize_runtime_fixture(self,self.calculation,self.baseline,self.order_bom_version)
        for stub in (
            patch(f"{MODULE}.release_readback", return_value={"completed": True, "businessStateTransitionId": 999}),
            patch(f"{MODULE}.project_release_content_integrity", return_value={"valid": True, "stableCurrentContentHash": "verified-fixture"}),
        ):
            stub.start()
            self.addCleanup(stub.stop)

    def _counts(self):
        return tuple(model.objects.count() for model in (
            ProductManufacturingOutput, MasterDataWriteRequest, ExternalIdentity,
            OrganizationOperatingAuditRecord, BusinessStateTransition, Demand,
        ))

    def _generate(self, doc=None, predecessor=None, key="root-output"):
        arguments = {} if doc is None else {
            "sales_order_item_id": self.order_item.pk, "document_version_id": doc.pk,
            "predecessor_output_id": predecessor.pk if predecessor else None,
        }
        candidate = candidate_projection(self.executor, **arguments)
        self.assertTrue(candidate["sourceReady"], candidate)
        payload = {"salesOrderItemId": self.order_item.pk, "sourceFingerprint": candidate["sourceFingerprint"],
            "action": ACTION, "reason": "隔离版本承接生成"}
        if doc is not None:
            payload.update(engineeringDocumentVersionId=doc.pk,
                predecessorOutputId=predecessor.pk if predecessor else None)
        result = generate_manufacturing_output(user=self.executor, payload=payload, idempotency_key=key)
        return ProductManufacturingOutput.objects.get(pk=result["row"]["id"]), result

    def _release(self, output, key):
        preflight = release_preflight(output, self.executor)
        self.assertTrue(preflight["releaseAllowed"], preflight)
        result = release_manufacturing_output(user=self.executor, output_id=output.pk,
            payload={"action": RELEASE_ACTION, "reason": "隔离版本承接发布",
                "sourceFingerprint": preflight["sourceFingerprint"]}, idempotency_key=key)
        output.refresh_from_db()
        return result

    def _successor_sources(self):
        from system.models import Permission, RolePermission
        from .routing_version_successor_service import ROUTING_PERMISSION, RoutingVersionSuccessorService
        baseline = OrderEngineeringBaseline(
            company=self.company, sales_order=self.order, baseline_no="HANDOFF-BL-2", sequence=2,
            status="draft", reason="隔离新版本", candidate_hash="1" * 64, snapshot_hash="2" * 64,
            scope_item_count=1, confirmable_item_count=1, blocker_count=0, created_by=self.executor,
        )
        baseline._business_state_initialization_authorized = True
        baseline.save()
        old_item = self.baseline.items.get()
        values = {field.attname: deepcopy(getattr(old_item, field.attname))
            for field in OrderEngineeringBaselineItem._meta.concrete_fields
            if not field.primary_key and field.attname != "baseline_id"}
        OrderEngineeringBaselineItem.objects.create(baseline=baseline, **values)
        OrderEngineeringBaseline.objects.filter(pk=baseline.pk).update(status="confirmed")
        baseline.refresh_from_db()
        calculation = EngineeringCalculationRecord.objects.create(
            company=self.company, source_record=self.source, sales_order_item=self.order_item,
            engineering_instance=self.instance, scope="order_engineering", calculation_no="HANDOFF-CALC-2",
            rule_set_version="RSC-RULE-V1", revision=2, supersedes=self.calculation,
            result_hash="3" * 64, status="completed",
            trace={"baselineReference": {"id": baseline.pk, "snapshotHash": baseline.snapshot_hash}},
        )
        bom = BOMVersion.objects.create(bom=self.order_bom, bom_version="HANDOFF-2", revision=2,
            bom_scope="order_specific", order_engineering_instance=self.instance,
            source_calculation=calculation, status="draft")
        for old in self.order_bom_version.items.all():
            old.pk = None
            old.bom_version = bom
            old.save()
        permission,_=Permission.objects.get_or_create(code=ROUTING_PERMISSION,
            defaults={'name':'isolated native route successor','module':'PDE'})
        RolePermission.objects.get_or_create(role=self.executing_role,permission=permission)
        mapped=RoutingVersionSuccessorService.create(source_id=self.category_routing_version.pk,
            user=self.executor,idempotency_key='isolated-route-successor',reason='隔离正式步骤继任映射')
        route=RoutingVersion.objects.get(pk=mapped['routingVersionId'])
        document = EngineeringDocumentVersion.objects.create(
            document=self.order_document, document_name="承接后的工程资料", document_version="R2",
            release_subject_type="ORDER_ENGINEERED_PRODUCT", order_engineering_instance=self.instance,
            order_engineering_baseline=baseline, engineering_calculation=calculation,
            related_bom=bom, related_routing=route,
        )
        for obj in (bom, route, document):
            type(obj).objects.filter(pk=obj.pk).update(status="released")
            obj.refresh_from_db()
        finalize_runtime_fixture(self,calculation,baseline,bom)
        return baseline, calculation, bom, route, document

    def test_successor_keeps_root_identity_and_native_proofs_unchanged(self):
        root, first = self._generate()
        self._release(root, "root-release")
        before = ProductManufacturingOutput.objects.filter(pk=root.pk).values().get()
        original_audits = list(OrganizationOperatingAuditRecord.objects.values().order_by("pk"))
        _, _, _, _, document = self._successor_sources()
        successor, made = self._generate(document, root, "successor-output")
        self._release(successor, "successor-release")
        self.assertEqual((successor.revision, successor.predecessor_id), (2, root.pk))
        self.assertEqual(before, ProductManufacturingOutput.objects.filter(pk=root.pk).values().get())
        self.assertEqual(original_audits, list(OrganizationOperatingAuditRecord.objects.filter(
            pk__in=[row["id"] for row in original_audits]).values().order_by("pk")))
        self.assertTrue(validate_selected_output(root)["releaseReadback"]["completed"])
        self.assertTrue(validate_selected_output(successor)["releaseReadback"]["completed"])
        self.assertTrue(generation_readback(successor)["completed"])
        self.assertNotEqual(first["writeRequestId"], made["writeRequestId"])
        self.order_item.refresh_from_db()
        self.assertIsNone(self.order_item.manufacturing_output_id)
        self.assertEqual(Demand.objects.count(), 0)

    def test_explicit_successor_replay_uses_one_exact_combination(self):
        root, _ = self._generate()
        self._release(root, "root-release")
        document = self._successor_sources()[-1]
        successor, _ = self._generate(document, root, "successor-output")
        self._release(successor, "successor-release")
        counts = self._counts()
        replay, result = self._generate(document, root, "successor-new-key")
        self.assertEqual(replay.pk, successor.pk)
        self.assertTrue(result["idempotentReplay"])
        self.assertEqual(counts, self._counts())

    def test_multiple_versions_require_explicit_selection_and_preserve_demand_pin(self):
        root, _ = self._generate()
        self._release(root, "root-release")
        document = self._successor_sources()[-1]
        successor, _ = self._generate(document, root, "successor-output")
        self._release(successor, "successor-release")
        before = self._counts()
        with self.assertRaises(ManufacturingInputError):
            resolve_order_engineered_input(self.order_item)
        self.assertEqual(resolve_order_engineered_input(self.order_item, output_id=root.pk)["output"].pk, root.pk)
        self.assertEqual(resolve_order_engineered_input(self.order_item, output_id=successor.pk)["output"].pk, successor.pk)
        self.assertEqual(before, self._counts())
        demand = Demand.objects.create(demand_no="HANDOFF-DEMAND", source_type="sales_order",
            source_document_type="SalesOrder", source_document_id=str(self.order.pk), source_document_no=self.order.order_no,
            sales_order_item=self.order_item, manufacturing_output=root, material=self.finished, required_qty=1,
            required_date=self.order_item.required_date, department=self.department, reason="固定历史组合",
            created_by=self.executor)
        demand.full_clean()
        # A historical Demand remains pinned, but an unselected new request
        # must not silently inherit it when two manufacturing versions exist.
        with self.assertRaises(ManufacturingInputError) as caught:
            resolve_order_engineered_input(self.order_item)
        self.assertEqual(caught.exception.code, "ORDER_ENGINEERING_OUTPUT_NOT_UNIQUE")
        self.assertEqual(resolve_order_engineered_input(self.order_item, output_id=root.pk)["output"].pk, root.pk)
        self.assertEqual(resolve_order_engineered_input(self.order_item, output_id=successor.pk)["output"].pk, successor.pk)
        demand.refresh_from_db()
        self.assertEqual(demand.manufacturing_output_id, root.pk)

    def test_missing_predecessor_and_unselected_document_fail_closed(self):
        root, _ = self._generate()
        self._release(root, "root-release")
        document = self._successor_sources()[-1]
        before = self._counts()
        candidate = candidate_projection(self.executor)
        self.assertFalse(candidate["sourceReady"])
        candidate = candidate_projection(self.executor, sales_order_item_id=self.order_item.pk,
            document_version_id=document.pk)
        self.assertEqual(candidate["firstBlockerCode"], "MANUFACTURING_OUTPUT_PREDECESSOR_REQUIRED")
        self.assertEqual(before, self._counts())

    def test_wrong_company_or_incomplete_old_release_cannot_be_predecessor(self):
        root, _ = self._generate()
        document = self._successor_sources()[-1]
        before = self._counts()
        candidate = candidate_projection(self.executor, sales_order_item_id=self.order_item.pk,
            document_version_id=document.pk, predecessor_output_id=root.pk)
        self.assertEqual(candidate["firstBlockerCode"], "ORDER_ENGINEERING_OUTPUT_NOT_RELEASED")
        self.assertEqual(before, self._counts())
        self._release(root, "root-release")
        from types import SimpleNamespace
        with self.assertRaises(ManufacturingOutputError):
            validate_selected_output(root, user=SimpleNamespace(company_id=self.company.pk + 1))

    def test_consumed_calculation_stays_eligible_for_pinned_output(self):
        self.assertFalse(_calculation_has_fixed_consumers(self.calculation))
        root, _ = self._generate()
        self._release(root, "root-release")
        self.assertTrue(_calculation_has_fixed_consumers(self.calculation))
        _, calculation, _, _, _ = self._successor_sources()
        before = self._counts()
        _retire_unconsumed_calculation(self.calculation, calculation, user=self.executor,
            decision={"allowed": True}, execution_chain={"source": "isolated fixture"})
        self.calculation.refresh_from_db()
        self.assertEqual(self.calculation.status, "completed")
        self.assertEqual(before, self._counts())
        self.assertTrue(validate_selected_output(root)["releaseReadback"]["completed"])

    def test_unconsumed_revision_retains_original_retirement_behavior(self):
        _, calculation, _, _, _ = self._successor_sources()
        _retire_unconsumed_calculation(self.calculation, calculation, user=self.executor,
            decision={"allowed": True}, execution_chain={"source": "isolated fixture"})
        self.calculation.refresh_from_db()
        self.assertEqual(self.calculation.status, "superseded")
        transition = BusinessStateTransition.objects.get(object_type="EngineeringCalculationRecord",
            object_id=self.calculation.pk, target_state="superseded")
        self.assertEqual(transition.operator_id, self.executor.pk)

    def test_explicit_document_chain_refuses_another_baseline_trace(self):
        baseline, calculation, bom, route, _ = self._successor_sources()
        service = OrderEngineeringDocumentRegistrationService
        arguments = {"user": self.executor, "order_no": self.order.order_no, "line_no": 1,
            "baseline_id": baseline.pk, "calculation_id": self.calculation.pk,
            "bom_version_id": bom.pk, "routing_version_id": route.pk}
        with self.assertRaises(OrderEngineeringDocumentRegistrationError) as caught:
            service.resolve_chain(**arguments)
        self.assertEqual(caught.exception.code, "COMPLETED_CALCULATION_NOT_UNIQUE")
        # The matching calculation remains a different, explicit identity.
        self.assertNotEqual(calculation.pk, self.calculation.pk)

    def test_late_transaction_failure_leaves_old_version_untouched(self):
        root, _ = self._generate()
        self._release(root, "root-release")
        document = self._successor_sources()[-1]
        before = self._counts()
        old = ProductManufacturingOutput.objects.filter(pk=root.pk).values().get()
        with patch(f"{MODULE}.transition_business_object", side_effect=RuntimeError("isolated successor fault")):
            with self.assertRaises(RuntimeError):
                self._generate(document, root, "failed-successor")
        self.assertEqual(before, self._counts())
        self.assertEqual(old, ProductManufacturingOutput.objects.filter(pk=root.pk).values().get())

    def test_baseline_display_join_and_lazy_user_reads_keep_business_facts_without_credentials(self):
        baseline = OrderEngineeringBaseline.objects.get(pk=self.baseline.pk)
        before = OrderEngineeringBaseline.objects.filter(pk=baseline.pk).values().get()
        changes = connection.connection.total_changes
        with CaptureQueriesContext(connection) as queries:
            lazy = _baseline_facts(baseline, include_items=True)
            joined_baseline = _baseline_display_users(OrderEngineeringBaseline.objects.filter(pk=baseline.pk)).get()
            joined = _baseline_facts(joined_baseline, include_items=True)
        self.assertEqual(lazy, joined)
        self.assertEqual(joined["createdBy"], self.user.username)
        self.assertEqual(joined["createdByName"], self.user.real_name)
        self.assertEqual(before, OrderEngineeringBaseline.objects.filter(pk=baseline.pk).values().get())
        self.assertEqual(changes, connection.connection.total_changes)
        account_reads = [query["sql"].lower() for query in queries.captured_queries
            if "user_system" in query["sql"].lower()]
        self.assertTrue(account_reads)
        for sql in account_reads:
            self.assertNotIn('"password"', sql)
            self.assertNotIn('"email"', sql)
            self.assertNotIn('"mobile"', sql)

    def test_saved_output_consumption_never_reopens_generation_candidate_or_external_source(self):
        output,_=self._generate();self._release(output,'saved-runtime-release')
        frozen=OrganizationOperatingAuditRecord.objects.get(pk=generation_readback(output)['auditId']).after_snapshot['sourceFingerprint']
        before=self._counts();changes=connection.connection.total_changes
        with patch(f'{MODULE}.resolve_sources',side_effect=FileNotFoundError('unavailable external import')):
            proof=validate_selected_output(output,user=self.executor)
        self.assertEqual(proof['sourceFingerprint'],frozen)
        self.assertEqual(before,self._counts());self.assertEqual(changes,connection.connection.total_changes)

    def test_saved_output_authority_is_not_replaced_by_current_full_column_hash(self):
        output,_=self._generate();self._release(output,'stable-runtime-release')
        frozen=OrganizationOperatingAuditRecord.objects.get(pk=generation_readback(output)['auditId']).after_snapshot['sourceFingerprint']
        # Extra ORM navigation/metadata cannot become a new source authority.
        output.future_internal_metadata='a newly deployed optional field'
        with patch(f'{MODULE}.resolve_sources',side_effect=AssertionError('current import identity must not be reconstructed')):
            proof=validate_selected_output(output)
        self.assertEqual(proof['sourceFingerprint'],frozen)

    def test_saved_output_internal_baseline_fact_bom_and_request_tamper_fail_closed(self):
        output,_=self._generate();self._release(output,'tamper-runtime-release')
        fact=output.engineering_calculation.derived_facts.get()
        item=output.bom_version.items.get();link=item.source_requirements.get()
        requirement=link.material_requirement
        ledger=MasterDataWriteRequest.objects.get(entity_type='EngineeringMaterialRequirement',target_entity_id=str(requirement.pk))
        baseline_item=output.order_engineering_baseline.items.get()
        main=output.engineering_calculation
        completion=BusinessStateTransition.objects.get(object_type='EngineeringCalculationRecord',object_id=main.pk)
        audit=OrganizationOperatingAuditRecord.objects.get(pk=int(completion.audit_reference.split(':')[-1]))
        changes={
            'factValue':lambda:EngineeringDerivedFact.objects.filter(pk=fact.pk).update(value={'decimal':'9'}),
            'baselineContent':lambda:OrderEngineeringBaselineItem.objects.filter(pk=baseline_item.pk).update(content_snapshot={'unapproved':'changed'}),
            'bomQuantity':lambda:type(item)._base_manager.filter(pk=item.pk).update(quantity=Decimal('9')),
            'linkQuantity':lambda:type(link).objects.filter(pk=link.pk).update(contributed_quantity=Decimal('9')),
            'bomPurpose':lambda:type(item)._base_manager.filter(pk=item.pk).update(item_role='component'),
            'savedQuantityLedger':lambda:MasterDataWriteRequest.objects.filter(pk=ledger.pk).update(result={**ledger.result,'quantity':'9'}),
            'mainInputHash':lambda:EngineeringCalculationRecord.objects.filter(pk=main.pk).update(input_hash='0'*64),
            'mainAction':lambda:BusinessStateTransition.objects.filter(pk=completion.pk).update(action_code='unrelated.action'),
            'mainAuditReference':lambda:BusinessStateTransition.objects.filter(pk=completion.pk).update(audit_reference='missing:1'),
            'mainAuditAction':lambda:OrganizationOperatingAuditRecord.objects.filter(pk=audit.pk).update(action_code='unrelated.action'),
            'mainAuthorization':lambda:OrganizationOperatingAuditRecord.objects.filter(pk=audit.pk).update(
                after_snapshot={**audit.after_snapshot,'authorization':{'allowed':False}}),
            'mainActorChain':lambda:OrganizationOperatingAuditRecord.objects.filter(pk=audit.pk).update(
                after_snapshot={**audit.after_snapshot,'executionChain':{'account':'other'}}),
        }
        for name,mutate in changes.items():
            with self.subTest(name=name),transaction.atomic():
                mutate()
                with self.assertRaises(ManufacturingOutputError):
                    validate_selected_output(ProductManufacturingOutput.objects.get(pk=output.pk))
                transaction.set_rollback(True)

    def test_native_material_output_preserves_its_saved_resource_and_purpose_contract(self):
        from .manufacturing_output_generation_service import _saved_requirement_integrity
        requirement=self.order_bom_version.items.get().source_requirements.get().material_requirement
        detail=requirement.source_detail
        output={'canonicalName':detail.output_name,'resultDomain':'MATERIAL_REQUIREMENT',
            'materialId':requirement.material_id,'quantityBasis':requirement.quantity_basis,
            'itemRole':requirement.item_role,'requirementType':requirement.requirement_type,
            'supplyType':requirement.supply_type,'orderSpecification':requirement.order_specification}
        rule=EngineeringRuleDefinition(company=self.company,rule_code='RUNTIME-NATIVE-MATERIAL',
            rule_name='isolated original material output',version='V1',rule_kind='formula',
            specification={'outputs':[output]},status='released')
        rule._business_state_initialization_authorized=True;rule.save()
        detail.rule=rule;detail.output_value={'decimal':str(requirement.calculated_quantity)}
        detail.save(update_fields=['rule','output_value'])
        requirement.trace={};requirement.save(update_fields=['trace'])
        _saved_requirement_integrity(requirement)
        for key,value in (('materialId',requirement.material_id+1),('quantityBasis','PER_SALES_ITEM_UNIT'),
                ('itemRole','unproven'),('requirementType','unproven'),('supplyType','unproven'),
                ('orderSpecification',{'unproven':True}),('scrapRate','0.1')):
            with self.subTest(field=key),self.assertRaises(ValidationError):
                rule.specification={'outputs':[{**output,key:value}]}
                _saved_requirement_integrity(requirement)
            rule.specification={'outputs':[output]}

    def test_saved_output_missing_bom_provenance_and_changed_native_fingerprint_are_refused(self):
        output,_=self._generate();self._release(output,'proof-runtime-release')
        with transaction.atomic():
            BOMItemSourceRequirement.objects.filter(bom_item__bom_version=output.bom_version).delete()
            with self.assertRaises(ManufacturingOutputError):validate_selected_output(output)
            transaction.set_rollback(True)
        audit=OrganizationOperatingAuditRecord.objects.get(action_code=RELEASE_ACTION,target_type='ProductManufacturingOutput',target_id=output.pk)
        OrganizationOperatingAuditRecord.objects.filter(pk=audit.pk).update(after_snapshot={**audit.after_snapshot,'sourceFingerprint':'0'*64})
        with self.assertRaises(ManufacturingOutputError):validate_selected_output(output)

    def test_saved_output_still_requires_internal_document_stable_content_proof(self):
        output,_=self._generate();self._release(output,'document-runtime-release')
        # This fixture explicitly stubs the separate document review layer;
        # its negative authority is still mandatory to the output consumer.
        with patch(f'{MODULE}.project_release_content_integrity',return_value={'valid':False}):
            with self.assertRaises(ManufacturingOutputError):validate_selected_output(output)

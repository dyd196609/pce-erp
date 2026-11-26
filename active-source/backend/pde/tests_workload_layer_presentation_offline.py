"""SIMULATED_FOR_TEST: execute current reader code with metadata boundary doubles.

This suite proves the non-required presentation branch only; no Django import,
DB, HTTP, real source proof, quantity derivation or user acceptance is claimed.
"""
import ast
from copy import deepcopy
from contextlib import nullcontext
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import sqlite3
import sqlite3.dbapi2
import sys
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch


SOURCE = Path(os.environ.get('PCE_WORKLOAD_LAYER_SOURCE',
    Path(__file__).with_name('operation_workload_source_service.py'))).resolve()


class SourceError(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details or {}


class QueryCondition:
    def __init__(self, **filters):
        self.parts = [filters]

    def __or__(self, other):
        value = QueryCondition()
        value.parts = self.parts + other.parts
        return value


def reader_namespace():
    selected = {'_id', '_fail', '_reason', '_bucket', '_source_projection_key', 'read_for_plan',
                '_workload_requirement_rows', '_workload_persistence', '_formal_requirement_quantity_summary',
                '_workload_row_review', '_compact_workload_item', '_compact_workload_bucket',
                '_scope_proof_key', '_step_metadata_key', '_remember_step_metadata', '_read_step_metadata'}
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'), filename=str(SOURCE))
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in selected]
    assert {node.name for node in nodes} == selected
    for node in nodes:
        node.decorator_list = []  # Transaction behavior belongs to native integration tests.
    namespace = {'__package__': 'pde', 'deepcopy': deepcopy, 'CONTRACT': 'SIMULATED_READER_CONTRACT',
                 'OperationWorkloadSourceError': SourceError, 'ProductionFoundationError': SourceError,
                 'ValidationError': type('ValidationError', (Exception,), {}),
                 'DatabaseError': type('DatabaseError', (Exception,), {}),
                 'transaction': NS(atomic=nullcontext), 'Q': QueryCondition,
                 'Decimal':Decimal, 'InvalidOperation':InvalidOperation,
                 '_UNREAD_BUCKETS':{'NOT_READ','NOT_EVALUATED','READ_FAILED','PENDING','NOT_APPLICABLE'}}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), namespace)
    return namespace


class WorkloadIndependentLayerTests(unittest.TestCase):
    def setUp(self):
        self.connections = []
        for target in ('sqlite3.connect', 'sqlite3.dbapi2.connect',
                       'socket.create_connection', 'socket.socket.connect'):
            mock = self.enterContext(patch(target, side_effect=AssertionError('Offline boundary: ' + target)))
            self.connections.append(mock)
        self.ns = reader_namespace()
        self.user = NS(pk=47, company_id=23)
        self.plan = NS(pk=71)
        self.output = NS(pk=72, order_engineering_baseline_id=73,
                         order_engineering_baseline=NS(snapshot_hash='b'*64),
                         routing_version_id=74, routing_version=NS(routing_id=75))
        self.base = NS(pk=76, input_hash='c'*64, result_hash='d'*64,
                       source_record_id=120,engineering_instance_id=121)
        self.item, self.kind = NS(pk=77), NS(pk=78, code='SIM/LEGAL')
        self.step = NS(pk=79, operation_id=80, operation=NS(name='模拟合法工序'), sequence=2)
        self.applicability = {'result':'NOT_APPLICABLE', 'resultLabel':'本次不适用',
            'objectApplicability': {'complete':True, 'objects':[{
                'recordId':91, 'baselineItemId':92, 'designItemId':93, 'decision':'NOT_APPLICABLE',
                'auditId':94, 'basis':{'decisionReference':{'statement':'模拟精确对象依据'}}}]}}
        self.projection = {'statusCode':'CONFIGURED','statusLabel':'已配置正式作业量来源规则',
            'hasValidSourceConfiguration':True, 'sources':[{'ruleId':101,'ruleName':'模拟数量来源',
                'standardCapacityId':102,'uomLabel':'件'}], 'blockers':[]}
        self.capacity_facts = [{'id':102,'quantity':'17.000000','uomLabel':'件','timeUnitLabel':'天',
                                'timeBasisQuantity':'1.0000','factSource':'server'}]
        self.projection_read = Mock(side_effect=lambda *a, **k:deepcopy(self.projection))
        self.authorize = Mock()
        self.scope = Mock(side_effect=lambda *a, **k:(self.plan,self.output,self.item,self.base,
                                                    self.step,self.kind,self.applicability))
        self.queries = Mock()
        self.queries.filter.return_value.exists.return_value = False
        capacity_manager = Mock()
        capacity_manager.filter.return_value.select_related.return_value = []
        self.formal_persisted, self.allocation_persisted = [], []
        self.formal_manager, self.allocation_manager = Mock(), Mock()
        self.formal_manager.filter.return_value.order_by.return_value.values_list.side_effect = (
            lambda *a, **k:deepcopy(self.formal_persisted))
        self.allocation_manager.filter.return_value.order_by.return_value.values_list.side_effect = (
            lambda *a, **k:deepcopy(self.allocation_persisted))
        native = NS(VIEW='SIM_VIEW',PLAN_VIEW='SIM_PLAN_VIEW', DailyCapacityError=SourceError,
            _ReadOnlyProofCache=type('UnusedTypedCache', (dict,), {}),
            _source_read_cache=Mock(side_effect=lambda user, cache:{} if cache is None else cache),
            _read_once=Mock(side_effect=lambda cache,key,fn:deepcopy(cache.setdefault(key,fn()))),
            _today=lambda:date(2026,10,19))
        self.ns.update(_authorize=self.authorize,_scope_context=self.scope,native=native,
            _step_capacity_semantics=Mock(side_effect=lambda **k:({'meaningCode':'NOT_APPLICABLE'},
                                                                 deepcopy(self.capacity_facts))),
            EngineeringOperationRequirement=NS(objects=self.formal_manager),
            ProductionPlanOperationRequirementAllocation=NS(objects=self.allocation_manager),
            StandardCapacity=NS(objects=capacity_manager),operation_source_configuration=self.projection_read)
        modules = {}
        for name in ('pde','pde.models','pde.operation_input_preparation_service',
                     'pde.daily_capacity_service','pde.routing_step_applicability_service'):
            modules[name] = ModuleType(name)
        modules['pde.models'].OperationInputPreparationDraft = NS(objects=self.queries)
        modules['pde.operation_input_preparation_service'].read_preparation = Mock(
            side_effect=AssertionError('No existing preparation was declared'))
        modules['pde.daily_capacity_service'].capacity_source_rules = Mock(return_value={'status':'VALID'})
        modules['pde.routing_step_applicability_service'].RESULT_LABELS = {
            'REQUIRED':'本次必须执行','NOT_APPLICABLE':'本次不适用','PENDING':'待正式条件确认'}
        self.enterContext(patch.dict(sys.modules, modules))

    def tearDown(self):
        for mock in self.connections:
            mock.assert_not_called()

    def read(self, cache=None):
        return self.ns['read_for_plan'](user=self.user,production_plan_id=self.plan.pk,
                                        routing_step_id=self.step.pk,_read_cache=cache)

    def metadata_cache(self):
        """Run the real typed ownership/epoch gate with an offline connection."""
        connection = NS(alias='SIMULATED', in_atomic_block=True, atomic_blocks=[object()],
                        connection=NS(total_changes=0))
        tree = ast.parse(SOURCE.with_name('operation_requirement_service.py').read_text(encoding='utf-8'))
        names = {'_ReadOnlyProofCache', '_requirement_read_cache'}
        nodes = [node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.ClassDef))
                 and node.name in names]
        self.assertEqual({node.name for node in nodes}, names)
        namespace = {'transaction':NS(get_connection=lambda *args:connection),
                     '_CURRENT_CALL_ACTOR':object()}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'actual_native_cache','exec'),namespace)
        native = self.ns['native']
        native._ReadOnlyProofCache = namespace['_ReadOnlyProofCache']
        native._requirement_read_cache = namespace['_requirement_read_cache']
        native._digest = lambda value:sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()
        native._proof_record_hash = lambda row:native._digest(vars(row))
        self.plan.planning_requirement = NS(demand=NS(pk=401))
        self.base.source_record, self.base.engineering_instance = NS(pk=402),NS(pk=403)
        self.output.bom_version,self.output.engineering_document_version = NS(pk=404),NS(pk=405)
        self.output.routing_version.routing = NS(pk=75)
        context = (self.plan,self.output,self.item,self.base,self.step,self.kind,self.applicability)
        scope = {'companyId':23,'productionPlanId':71,'manufacturingOutputId':72,'mainCalculationId':76,
                 'salesOrderItemId':77,'baselineId':73,'routingVersionId':74,'routingStepId':79,
                 'operationId':80,'productTypeId':78}
        cache = native._ReadOnlyProofCache(self.user)
        return cache, context, scope, connection

    def test_same_atomic_metadata_is_read_once_but_returned_as_independent_json(self):
        cache,context,scope,_ = self.metadata_cache()
        read = lambda:self.ns['_read_step_metadata'](user=self.user,context=context,scope=scope,_read_cache=cache)
        first = read()
        first['standardCapacityFacts'][0]['quantity'] = '999'
        second = read()
        self.assertEqual(second['standardCapacityFacts'],self.capacity_facts)
        self.queries.filter.assert_called_once_with(company_id=23,production_plan_id=71,routing_step_id=79)
        sys.modules['pde.daily_capacity_service'].capacity_source_rules.assert_called_once()
        self.ns['_step_capacity_semantics'].assert_called_once()

    def test_overview_seed_reuses_preparation_and_semantics_without_reading_them_again(self):
        cache,context,scope,_ = self.metadata_cache()
        value = {'inputPreparation':{'recordId':501,'revision':7,'exactScope':scope},
                 'capacitySemantics':{'valid':False,'meaningCode':'UNPROVEN'},
                 'standardCapacityFacts':self.capacity_facts}
        self.ns['_remember_step_metadata'](self.user,cache,context,value,self.ns['native']._today())
        value['inputPreparation']['revision'] = 999
        result = self.ns['_read_step_metadata'](user=self.user,context=context,scope=scope,_read_cache=cache)
        self.assertEqual(result['inputPreparation']['revision'],7)
        self.assertFalse(result['capacitySemantics']['valid'])
        self.queries.filter.assert_not_called()
        self.ns['_step_capacity_semantics'].assert_not_called()

    def test_plain_foreign_actor_company_or_expired_atomic_cache_cannot_reuse_metadata(self):
        for change in ('plain','actor','company','atomic','connection'):
            with self.subTest(change=change):
                cache,context,scope,connection = self.metadata_cache()
                self.ns['_remember_step_metadata'](self.user,cache,context,
                    {'capacitySemantics':{'unexpected':'stale'}},self.ns['native']._today())
                if change=='plain': cache=dict(cache)
                elif change=='actor':cache.user_id = 999
                elif change=='company':cache.company_id = 999
                elif change=='atomic':connection.in_atomic_block = False
                else:connection.connection = NS(total_changes=0)
                value=self.ns['_read_step_metadata'](user=self.user,context=context,scope=scope,_read_cache=cache)
                self.assertNotIn('unexpected',value['capacitySemantics'])
        self.assertEqual(self.ns['_step_capacity_semantics'].call_count,5)

    def test_date_scope_and_same_connection_write_each_invalidate_metadata(self):
        for change in ('date','scope','epoch'):
            with self.subTest(change=change):
                cache,context,scope,connection=self.metadata_cache()
                old_date=self.ns['native']._today()
                self.ns['_remember_step_metadata'](self.user,cache,context,
                    {'capacitySemantics':{'unexpected':'stale'}},old_date)
                if change=='date':self.ns['native']._today=lambda:date(2026,10,20)
                elif change=='scope':self.base.result_hash='e'*64
                else:connection.connection.total_changes+=1
                value=self.ns['_read_step_metadata'](user=self.user,context=context,scope=scope,_read_cache=cache)
                self.assertNotIn('unexpected',value['capacitySemantics'])
                self.ns['native']._today=lambda:date(2026,10,19)
        self.assertEqual(self.ns['_step_capacity_semantics'].call_count,3)

    def test_mutated_metadata_and_failed_loader_never_supply_a_successful_cached_read(self):
        cache,context,scope,_=self.metadata_cache()
        self.ns['_remember_step_metadata'](self.user,cache,context,
            {'capacitySemantics':{'unexpected':'stale'}},self.ns['native']._today())
        key=self.ns['_step_metadata_key'](self.user,cache,context,self.ns['native']._today())
        cache[key]['metadata']['capacitySemantics']['unexpected']='mutated'
        value=self.ns['_read_step_metadata'](user=self.user,context=context,scope=scope,_read_cache=cache)
        self.assertNotIn('unexpected',value['capacitySemantics'])
        cache.clear()
        self.queries.filter.return_value.exists.return_value=True
        preparation=sys.modules['pde.operation_input_preparation_service'].read_preparation
        preparation.side_effect=SourceError('SIM_PREPARATION_FAILED','simulated')
        with self.assertRaises(SourceError):
            self.ns['_read_step_metadata'](user=self.user,context=context,scope=scope,_read_cache=cache)
        self.assertNotIn(key,cache)

    def test_metadata_read_crossing_midnight_does_not_publish_a_new_date_proof(self):
        cache,context,scope,_=self.metadata_cache()
        today=Mock(side_effect=[date(2026,10,19),date(2026,10,19),date(2026,10,19),date(2026,10,20)])
        self.ns['native']._today=today
        value=self.ns['_read_step_metadata'](user=self.user,context=context,scope=scope,_read_cache=cache)
        self.assertEqual(value['standardCapacityFacts'],self.capacity_facts)
        self.assertEqual(cache,{})

    def test_midnight_between_metadata_date_check_and_scope_key_never_publishes_old_metadata(self):
        cache,context,_,_=self.metadata_cache()
        self.ns['native']._today=Mock(side_effect=[date(2026,10,19),date(2026,10,20)])
        self.ns['_remember_step_metadata'](self.user,cache,context,
            {'capacitySemantics':{'unexpected':'old-day'}},date(2026,10,19))
        self.assertEqual(cache,{})

    def test_excluded_object_keeps_configuration_and_capacity_but_never_invents_quantity(self):
        value = self.read()
        self.assertEqual(value['sourceConfiguration']['sources'],self.projection['sources'])
        self.assertEqual(value['sourceConfiguration']['rules'],self.projection['sources'])
        self.assertEqual(value['sourceConfiguration']['statusCode'],'CONFIGURED')
        self.assertEqual(value['standardCapacityFacts'],self.capacity_facts)
        self.assertEqual(value['sourceCandidates']['statusCode'],'NOT_APPLICABLE')
        self.assertEqual(value['formalRequirements']['statusCode'],'NOT_APPLICABLE')
        self.assertEqual(value['savedAllocations']['statusCode'],'NOT_APPLICABLE')
        self.assertIsNone(value['savedAllocations']['quantity'])
        self.assertEqual(value['formalRequirements']['items'],[])
        self.assertEqual(value['businessWriteCount'],0)
        self.assertFalse(value['newEorRuleEvaluated'])
        self.assertFalse(value['generated'])
        self.assertFalse(value['allocationSaved'])

    def test_pending_object_keeps_independent_metadata_and_original_pending_blocker(self):
        self.applicability['result'] = 'PENDING'
        value = self.read()
        self.assertEqual(value['sourceConfiguration']['statusCode'],'CONFIGURED')
        self.assertEqual(value['standardCapacityFacts'],self.capacity_facts)
        self.assertEqual(value['savedAllocations']['statusCode'],'PENDING')
        self.assertEqual([row['code'] for row in value['blockers']],['WORKLOAD_SOURCE_APPLICABILITY_PENDING'])

    def test_invalid_configuration_stays_explicit_without_changing_exclusion(self):
        self.projection.update(statusCode='INVALID',hasValidSourceConfiguration=False,
            blockers=[{'code':'SIM_INVALID_SOURCE','statusLabel':'模拟配置无效'}])
        value = self.read()
        self.assertEqual(value['sourceConfiguration']['statusCode'],'INVALID')
        self.assertEqual(value['sourceConfiguration']['blockers'],self.projection['blockers'])
        self.assertEqual(value['applicability']['result'],'NOT_APPLICABLE')
        self.assertEqual(value['blockers'],[])

    def test_object_decision_labels_use_each_current_server_fact_and_do_not_mutate_proof(self):
        self.applicability['result'] = 'PENDING'
        objects = self.applicability['objectApplicability']['objects']
        objects.extend([{'effectiveDecision':'REQUIRED'},{'decision':'PENDING'},{'decision':'UNRECOGNIZED'}])
        before = deepcopy(self.applicability)
        rows = self.read()['applicability']['objectApplicability']['objects']
        self.assertEqual([row.get('decisionLabel') for row in rows],
                         ['本次不适用','本次必须执行','待正式条件确认',None])
        self.assertEqual(self.applicability,before)

    def test_projection_scope_and_existing_authorization_checks_remain_exact(self):
        self.read()
        self.assertEqual(self.authorize.call_args_list,
                         [unittest.mock.call(self.user,'SIM_VIEW'),unittest.mock.call(self.user,'SIM_PLAN_VIEW')])
        self.projection_read.assert_called_once_with(self.step.operation,self.kind.pk,
            routing_context={'routingId':75,'routingVersionId':74,'routingStepId':79})
        key = self.ns['native']._read_once.call_args.args[1]
        self.assertEqual(key,('workload_source_projection',23,71,72,76,'c'*64,'d'*64,73,'b'*64,74,79,78))

    def test_permission_denial_and_invalid_scope_do_not_read_configuration(self):
        self.authorize.side_effect = SourceError('SIM_PERMISSION_DENIED','模拟无读取资格')
        with self.assertRaises(SourceError):self.read()
        self.scope.assert_not_called()
        self.projection_read.assert_not_called()
        self.authorize.side_effect = None
        self.scope.side_effect = SourceError('SIM_CONTEXT_INVALID','模拟精确上下文失效')
        value = self.read()
        self.assertEqual(value['scope'],{})
        self.assertEqual(value['blockers'][0]['code'],'SIM_CONTEXT_INVALID')
        self.projection_read.assert_not_called()

    def test_route_capacity_metadata_reuses_same_native_labels_and_retains_quantity(self):
        tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
        route = next(node for node in tree.body if isinstance(node,ast.FunctionDef)
                     and node.name=='read_route_overview')
        loop = next(node for node in route.body if isinstance(node,ast.For)
                    and isinstance(node.target,ast.Name) and node.target.id=='step')
        nodes = [node for node in loop.body if isinstance(node,ast.Assign)
                 and isinstance(node.targets[0],ast.Name)
                 and node.targets[0].id in ('fact_by_id','candidates')]
        self.assertEqual(len(nodes),2)
        cap = NS(pk=108,code='SIM-CAP',name='模拟产能',operation_id=80,product_type_id=78,
                 work_center_id=109,work_center=NS(name='模拟工作中心'),uom_id=110,uom=NS(name='件'),
                 quantity='17.5',time_basis='day',time_basis_quantity='1',time_unit='DAY',
                 measurement_status='measured')
        native_fact = {'id':108,'productTypeCode':'SIM/LEGAL','productTypeName':'模拟产品',
                       'timeUnitLabel':'模拟正式时间单位','statusLabel':'模拟正式产能状态',
                       'capacitySemantics':{'sourceValue':'17.5'}}
        namespace = {'scoped_capacities':[cap],'capacity_facts':[native_fact],
                     'native':NS(_active=lambda value:True)}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),namespace)
        actual = namespace['candidates'][0]
        self.assertEqual(actual['timeUnitLabel'],native_fact['timeUnitLabel'])
        self.assertEqual(actual['productTypeCode'],native_fact['productTypeCode'])
        self.assertEqual(actual['productTypeName'],native_fact['productTypeName'])
        self.assertEqual(actual['workCenterName'],cap.work_center.name)
        self.assertEqual(actual['quantity'],'17.5')
        self.assertEqual(actual['statusLabel'],native_fact['statusLabel'])

    def test_exclusion_reports_zero_saved_records_without_becoming_zero_quantity(self):
        value = self.read()
        for key in ('formalRequirements','savedAllocations'):
            self.assertEqual(value[key]['persistence']['readStatus'],'loaded')
            self.assertEqual(value[key]['persistence']['recordCount'],0)
            self.assertEqual(value[key]['persistence']['recordIds'],[])
            self.assertEqual(value[key]['statusCode'],'NOT_APPLICABLE')
        self.assertIn('尚未保存分配',value['savedAllocations']['persistence']['statusLabel'])
        self.assertIsNone(value['savedAllocations']['quantity'])
        self.assertEqual(value['formalRequirements']['quantitySummary'],[])

    def test_positive_persistence_is_visible_without_promoting_an_excluded_load(self):
        self.formal_persisted[:]=[(201,80),(202,80)]
        self.allocation_persisted[:]=[(301,80)]
        value = self.read()
        self.assertEqual(value['formalRequirements']['persistence']['recordCount'],2)
        self.assertEqual(value['savedAllocations']['persistence']['recordIds'],[301])
        self.assertIn('本次有效性尚未核验',value['savedAllocations']['persistence']['statusLabel'])
        self.assertEqual(value['savedAllocations']['statusCode'],'NOT_APPLICABLE')
        self.assertIsNone(value['savedAllocations']['quantity'])
        self.assertEqual(value['savedAllocations']['items'],[])
        self.assertEqual(value['businessWriteCount'],0)

    def test_persistence_uses_the_exact_engineering_scope_and_does_not_filter_wrong_operation(self):
        self.allocation_persisted[:]=[(301,80),(302,999)]
        value = self.read()
        args,kwargs = self.formal_manager.filter.call_args
        self.assertEqual(args[0].parts,[{'source_calculation':self.base},
            {'source_calculation__origin_calculation':self.base,'source_calculation__scope':'fact_extension',
             'source_calculation__supersedes__isnull':True}])
        self.assertEqual(kwargs,{'calculation__company_id':23,'operation_id':80,
            'source_calculation__company_id':23,'source_calculation__status':'completed',
            'source_calculation__source_record_id':120,'source_calculation__sales_order_item_id':77,
            'source_calculation__engineering_instance_id':121})
        self.allocation_manager.filter.assert_called_once_with(company_id=23,
            production_plan_id=71,routing_step_id=79)
        saved = value['savedAllocations']
        self.assertEqual(saved['persistence']['recordCount'],2)
        self.assertEqual(saved['persistence']['operationMismatchRecordIds'],[302])
        self.assertIn('工序关联不一致',saved['persistence']['statusLabel'])
        self.assertIsNone(saved['quantity'])

    def test_failed_persistence_stays_unknown_and_exposes_a_read_failure(self):
        self.allocation_manager.filter.return_value.order_by.return_value.values_list.side_effect = (
            self.ns['DatabaseError']('SIMULATED_FOR_TEST read error'))
        value = self.read()
        failed = value['savedAllocations']['persistence']
        self.assertEqual(failed['readStatus'],'read_failed')
        self.assertIsNone(failed['recordCount'])
        self.assertIsNone(failed['recordIds'])
        self.assertIsNone(failed['operationMismatchRecordIds'])
        self.assertIn('WORKLOAD_PERSISTENCE_READ_FAILED',[row['code'] for row in value['blockers']])
        self.assertEqual(value['savedAllocations']['statusCode'],'NOT_APPLICABLE')
        self.assertIsNone(value['savedAllocations']['quantity'])

    def test_summary_is_decimal_grouped_by_formal_uom_without_mutating_valid_items(self):
        formal = {'statusCode':'EXISTS','items':[
            {'workloadQuantity':'0.100000','uomId':17,'uomLabel':'件'},
            {'workloadQuantity':'0.200000','uomId':17,'uomLabel':'件'},
            {'workloadQuantity':'2.000000','uomId':19,'uomLabel':'米'}]}
        before = deepcopy(formal)
        self.assertEqual(self.ns['_formal_requirement_quantity_summary'](formal),[
            {'quantity':'0.300000','uomId':17,'uomLabel':'件'},
            {'quantity':'2.000000','uomId':19,'uomLabel':'米'}])
        self.assertEqual(formal,before)
        formal['statusCode']='INVALID'
        self.assertEqual(self.ns['_formal_requirement_quantity_summary'](formal),[])

    def test_summary_rejects_missing_zero_or_nonfinite_quantity_and_unit_inconsistency(self):
        for invalid in (None,'0','NaN','Infinity','-1',''):
            with self.subTest(quantity=invalid), self.assertRaises(SourceError):
                self.ns['_formal_requirement_quantity_summary']({'statusCode':'EXISTS','items':[
                    {'workloadQuantity':invalid,'uomId':17,'uomLabel':'件'}]})
        for items in ([{'workloadQuantity':'1','uomId':None,'uomLabel':'件'}],
                      [{'workloadQuantity':'1','uomId':17,'uomLabel':'件'},
                       {'workloadQuantity':'1','uomId':17,'uomLabel':'套'}]):
            with self.assertRaises(SourceError):
                self.ns['_formal_requirement_quantity_summary']({'statusCode':'EXISTS','items':items})

    def test_route_compaction_and_review_reuse_the_same_independent_server_facts(self):
        value = self.read()
        formal,saved = value['formalRequirements'],value['savedAllocations']
        compact = self.ns['_compact_workload_bucket'](saved)
        self.assertEqual(compact['persistence'],saved['persistence'])
        compact['persistence']['recordCount']=999
        self.assertEqual(saved['persistence']['recordCount'],0)
        row={'sequence':2,'operationName':'模拟合法工序','applicability':value['applicability'],
             'sourceConfiguration':value['sourceConfiguration'],'formalRequirements':formal,
             'savedAllocations':saved,'capacitySemantics':{},'blockers':[]}
        review=self.ns['_workload_row_review'](row,coverage={'statusCode':'NOT_APPLICABLE','statusLabel':'本次不适用'})
        self.assertEqual(review['formalRequirementPersistenceLabel'],formal['persistence']['statusLabel'])
        self.assertEqual(review['allocationPersistenceLabel'],saved['persistence']['statusLabel'])
        self.assertEqual(review['formalRequirementQuantitySummary'],[])
        self.assertEqual(review['statusCode'],'NOT_APPLICABLE')
        self.assertIsNone(review['savedQuantity'])

    def test_failed_persistence_cannot_be_reported_as_a_complete_route_read(self):
        tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
        function=next(node for node in tree.body if isinstance(node,ast.FunctionDef)
                      and node.name=='_include_route_workloads')
        nodes=[node for node in function.body if isinstance(node,ast.Assign)
               and isinstance(node.targets[0],ast.Name)
               and node.targets[0].id in ('read_complete','business_complete')]
        self.assertEqual(len(nodes),2)
        bucket={'statusCode':'NOT_APPLICABLE','persistence':{'readStatus':'loaded'}}
        row={'routingStepId':79,'scope':{'routingStepId':79},'sourceCandidates':{'statusCode':'NOT_APPLICABLE'},
             'formalRequirements':deepcopy(bucket),'savedAllocations':deepcopy(bucket)}
        namespace={'result':{'rows':[row]},'reviews':[{'statusCode':'NOT_APPLICABLE'}],
                   'allocation_read':{'blockers':[]}}
        code=compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec')
        exec(code,namespace)
        self.assertTrue(namespace['read_complete'])
        self.assertTrue(namespace['business_complete'])
        row['savedAllocations']['persistence']['readStatus']='read_failed'
        exec(code,namespace)
        self.assertFalse(namespace['read_complete'])
        self.assertFalse(namespace['business_complete'])

    def test_required_reader_summarizes_valid_native_items_and_keeps_missing_allocation_unknown(self):
        self.applicability['result']='REQUIRED'
        self.projection.update(hasValidSourceConfiguration=False,statusCode='MISSING',sources=[])
        requirements=[]
        for pk,quantity in ((211,'1.250000'),(212,'2.750000')):
            fact={'operationRequirementId':pk,'workloadQuantity':quantity,'uomId':17}
            requirements.append(NS(pk=pk,fact=fact,uom=NS(name='件'),
                source_detail=NS(rule=NS(specification={'outputs':[{'productTypeId':78}]}))))
        self.formal_manager.filter.return_value.select_related.return_value=requirements
        native=self.ns['native']
        native.OperationRequirementError=SourceError
        native._prefetch_requirement_history=Mock()
        native._validate_requirement=Mock(return_value={})
        native._plan_source_consistency=Mock()
        native._requirement_fact=Mock(side_effect=lambda req,**kwargs:deepcopy(req.fact))
        native.process_demand_for_plan=Mock(return_value=None)
        module=ModuleType('pde.operation_requirement_correction_service')
        module.requirement_lifecycle=Mock(return_value={})
        module.require_effective_requirement=Mock()
        cache,_,_,_=self.metadata_cache()
        with patch.dict(sys.modules,{'pde.operation_requirement_correction_service':module}):
            value=self.read(cache)
            repeated=self.read(cache)
        self.assertEqual(repeated,value)
        self.assertEqual(value['formalRequirements']['statusCode'],'EXISTS')
        self.assertEqual(value['formalRequirements']['quantitySummary'],[
            {'quantity':'4.000000','uomId':17,'uomLabel':'件'}])
        self.assertEqual(native._validate_requirement.call_count,4)
        self.assertEqual(native._plan_source_consistency.call_count,4)
        self.assertEqual(self.scope.call_count,2)
        self.assertEqual(self.authorize.call_count,4)
        self.ns['_step_capacity_semantics'].assert_called_once()
        self.assertEqual(value['savedAllocations']['statusCode'],'MISSING')
        self.assertIn('尚未保存分配',value['savedAllocations']['statusLabel'])
        self.assertIsNone(value['savedAllocations']['quantity'])


if __name__ == '__main__':
    unittest.main(verbosity=2)

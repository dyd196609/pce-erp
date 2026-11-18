"""Isolated workbook/version capability tests, not formal source admission.

The existing continuation fixture supplies synthetic engineering objects and a
numeric adapter. This module uses real XLSX bytes, native Foundation create /
shared publication states, normalization and scope validation. Its method
reference is explicitly synthetic and never replaces the registered reference.
"""
from copy import deepcopy
from io import BytesIO
import os
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase,override_settings
from django.db import connection
from masterdata.models import UnitOfMeasure
from system.models import Permission,RolePermission
from workflow_runtime.models import BusinessStateTransition
from .models import EngineeringRuleDefinition,EngineeringSourceRecord,OrderEngineeringBaseline,ProductDesignItem
from .production_foundation_service import ProductionFoundationService as Foundation,EngineeringLifecycleService as Lifecycle,ProductionFoundationError
from .engineering_rule_foundation import specification_hash
from .source_format_mapping_service import normalize_source_payload,validate_mapping,SourceFormatMappingError
from .engineering_workbook_source_service import (BLOB_CONTRACT,FORMAT,WorkbookSourceError,
    store_workbook_bytes,resolve_workbook_source,restore_coordinates,audit_proof,workbook_source_facts,_parsed_rows)
from .tests_engineering_calculation_continuation import EngineeringCalculationContinuationTests as MainFixture
from .calculation_batch_reuse import VERSION

WORKBOOK_CONTRACT_READBACK={}
CONDITION_PREFLIGHT_READBACK={}


class EngineeringWorkbookSourceVersionTests(TestCase):
    _adopt=MainFixture._adopt
    args=MainFixture.args

    def numeric_fixture(self,keys,*,design_inputs,workbook_source_context=None):
        result=MainFixture.numeric_fixture(self,keys,design_inputs=design_inputs)
        if workbook_source_context:
            by_key={row['sourceKey']:row for row in workbook_source_context['sourceData']['realRows']}
            for row in result['rows']:
                row.update(deepcopy(by_key[row['sourceKey']]['coordinates']['Z']))
                row['workbookSource']={'workbookSourceRecordId':workbook_source_context['proof']['workbookSourceRecordId']}
        return result

    @classmethod
    def setUpTestData(cls):
        MainFixture.setUpTestData.__func__(cls)
        for code in ('production.engineering.rule.create','production.engineering.rule.maintain','production.engineering.rule.release'):
            permission,_=Permission.objects.get_or_create(code=code,defaults={'name':code,'module':'production'})
            RolePermission.objects.get_or_create(role=cls.role,permission=permission)

    def setUp(self):
        MainFixture.setUp(self)
        UnitOfMeasure.objects.create(company_id=self.company.pk,code='m',name='米',dimension='length')
        directory=Path(os.environ['PCE_ISOLATED_WORKBOOK_STORAGE'])
        self.settings_override=override_settings(PCE_ENGINEERING_SOURCE_STORAGE_ROOT=directory)
        self.settings_override.enable();self.addCleanup(self.settings_override.disable)
        _parsed_rows.cache_clear()
        self.rows=[d.pk for d in self.design_items]
        self.reference={'sourceFiles':[{'file':'isolated-predecessor.xlsx','sha256':'a'*64}],
            'realRows':[{'sheet':'FIXTURE','row':r,'cells':{
            f'H{r}':{'value':d.item_name,'formula':None},f'J{r}':{'value':1,'formula':None},
            f'Z{r}':{'value':2,'formula':f'=J{r}*2'}}} for d,r in zip(self.design_items,self.rows)]}
        self.reference_patch=patch('pde.engineering_workbook_source_service._reference',return_value=self.reference)
        self.reference_patch.start();self.addCleanup(self.reference_patch.stop)
        self.method_inputs=['H','J']
        self.input_contract_patch=patch('pde.calculation_batch_reuse.source_rows',side_effect=lambda source:
            [{'businessInputs':[{'adapterSlot':slot} for slot in self.method_inputs]} for row in source['realRows']])
        self.input_contract_patch.start();self.addCleanup(self.input_contract_patch.stop)
        self.config={'contractVersion':'PCE-SOURCE-FORMAT-MAPPING-V1','format':FORMAT,'adapterContract':VERSION,
            'sheets':[{'sheetName':'FIXTURE','sourceRows':self.rows,'fields':[
                {'rawField':'H','canonicalName':'H','headerCell':'H10','headerValue':'identity','valueType':'text',
                    'sourceType':'DESIGN','baselinePath':'designItem.itemName','identity':True,'blankPolicy':'ERROR'},
                {'rawField':'J','canonicalName':'J','headerCell':'J10','headerValue':'quantity','valueType':'decimal',
                    'sourceType':'ENGINEERING_INPUT','baselinePath':'designItem.physicalQuantity',
                    'designOverrideField':'physicalQuantity','blankPolicy':'ERROR','unitDimension':'dimensionless'},
                {'rawField':'AA','canonicalName':'Z','headerCell':'AA10','headerValue':'approved output','valueType':'decimal',
                    'sourceType':'ENGINEERING_DERIVED','unit':'m','unitDimension':'length','blankPolicy':'NULL'},
            ]}]}
        self.blob=self.make_blob()
        self.rule=self.publish_rule(self.config)
        baseline=OrderEngineeringBaseline.objects.get(pk=self.new_baseline_id)
        self.payload={'sourceFormatReference':{'ruleId':self.rule.pk,'ruleVersion':self.rule.version,
            'specificationHash':specification_hash(self.rule.specification)},'rawContent':self.blob,
            'sourceContext':{'objectSourceRecordId':self.source.pk,'baselineId':baseline.pk,
                'baselineSnapshotHash':baseline.snapshot_hash}}

    def make_blob(self,*,wrong_header=False,changed_input=False,changed_identity=False,changed_formula=False,styled=False,method_input=3,bool_cache=False,method_formula=0):
        from openpyxl import Workbook
        workbook=Workbook();sheet=workbook.active;sheet.title='FIXTURE'
        sheet['H10']='identity';sheet['J10']='quantity';sheet['K10']='method input';sheet['AA10']='wrong' if wrong_header else 'approved output'
        for d,r in zip(self.design_items,self.rows):
            sheet[f'H{r}']='other object' if changed_identity else d.item_name
            sheet[f'J{r}']=9 if changed_input else 1
            sheet[f'K{r}']=f'=J{r}+{method_formula}' if method_formula else method_input
            sheet[f'Z{r}']=987654321  # Actual old letter is deliberately unrelated.
            sheet[f'AA{r}']=f'=J{r}*3' if changed_formula else f'=J{r}*2'
        if styled:sheet['XFA20'].number_format='0.00'
        memory=BytesIO();workbook.save(memory);workbook.close()
        if bool_cache or method_formula:
            from zipfile import ZipFile
            from xml.etree import ElementTree as ET
            target=BytesIO();namespace='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
            with ZipFile(BytesIO(memory.getvalue())) as original,ZipFile(target,'w') as rewritten:
                for member in original.infolist():
                    content=original.read(member.filename)
                    if member.filename=='xl/worksheets/sheet1.xml':
                        root=ET.fromstring(content)
                        for cell in root.iter(namespace+'c'):
                            if bool_cache and cell.attrib['r'] in {f'AA{r}' for r in self.rows}:
                                cell.set('t','b');cell.find(namespace+'v').text='0'
                            if method_formula and cell.attrib['r'] in {f'K{r}' for r in self.rows}:
                                cell.set('t','n');cell.find(namespace+'v').text=str(method_input)
                        content=ET.tostring(root,encoding='utf-8')
                    rewritten.writestr(member,content)
            memory=target
        return store_workbook_bytes(memory.getvalue(),filename='isolated.xlsx',company_id=self.company.pk)

    def publish_rule(self,config,version='V1'):
        spec={'rulePackage':{'code':'WB-FIXTURE','version':version},'expression':'SOURCE_VALUE',
            'inputs':[{'canonicalName':'SOURCE_VALUE','valueType':'decimal','unitDimension':'dimensionless',
                'sourceType':'ENGINEERING_INPUT','required':True,'unitRequired':False}],
            'outputs':[{'canonicalName':'result','valueType':'decimal','unitDimension':'dimensionless','unit':None,'resultDomain':'DERIVED_FACT'}],
            'dependencies':[],'decimalPrecision':28,'outputScale':6,'roundingMode':'ROUND_HALF_UP',
            'sourceEvidence':{'reference':'isolated method mapping fixture'},'applicability':{},'sourceFormatMapping':deepcopy(config)}
        result=Foundation.write('engineering-rule-definitions',user=self.actor,idempotency_key=f'wb-rule-{version}',
            source_identity={'sourceSystem':'ISOLATED','sourceType':'WORKBOOK_MAPPING','sourceObjectType':'EngineeringRuleDefinition',
                'externalId':f'wb-rule-{version}'},payload={'company_id':self.company.pk,'rule_code':'WB-FIXTURE',
                'rule_name':'isolated workbook mapping','version':version,'rule_kind':'mapping','specification':spec,'reason':'isolated'})
        rule=EngineeringRuleDefinition.objects.get(pk=result['row']['id'])
        for target in ('reviewed','released'):
            Lifecycle.transition('engineering-rule-definitions',object_id=rule.pk,target_status=target,user=self.actor,reason='isolated mapping publication')
        rule.refresh_from_db();return rule

    def save_source(self,confirm=True):
        result=Foundation.write('engineering-source-records',user=self.actor,idempotency_key='wb-source-V1',
            source_identity={'sourceSystem':'ISOLATED','sourceType':'WORKBOOK_SOURCE','sourceObjectType':'EngineeringSourceRecord',
                'externalId':'wb-source-V1'},payload={'company_id':self.company.pk,'source_no':'WB-SOURCE',
                'source_name':'isolated workbook source','source_version':'V1','source_type':'controlled_import',
                'source_payload':deepcopy(self.payload),'reason':'isolated workbook source'})
        source=EngineeringSourceRecord.objects.get(pk=result['row']['id'])
        if confirm:
            Lifecycle.transition('engineering-source-records',object_id=source.pk,target_status='confirmed',user=self.actor,reason='isolated source confirmation')
            source.refresh_from_db()
        return source

    def error(self,code,call):
        with self.assertRaises((SourceFormatMappingError,ProductionFoundationError)) as caught:call()
        self.assertEqual(caught.exception.code,code)

    def test_01_real_xlsx_mapping_preserves_actual_coordinates_and_old_slot(self):
        normalized=normalize_source_payload(self.payload,company_id=self.company.pk)
        row=normalized['normalization']['rows'][0]
        self.assertEqual(row['coordinates']['Z']['sourceColumn'],'AA')
        self.assertEqual(row['coordinates']['Z']['sourceCell'],f'AA{self.rows[0]}')
        self.assertIsNone(row['canonicalInputs']['Z']['value'])
        self.assertEqual(row['cells'][f'Z{self.rows[0]}']['formula'],f'=J{self.rows[0]}*2')
        self.assertNotEqual(row['cells'][f'Z{self.rows[0]}']['value'],'987654321')

    def test_02_native_source_two_and_rule_three_states_prove_real_publication(self):
        source=self.save_source();ctx=resolve_workbook_source(source.pk,company_id=self.company.pk)
        self.assertEqual(len(audit_proof(self.rule)['stateTransitionIds']),3)
        self.assertEqual(len(audit_proof(source)['stateTransitionIds']),2)
        self.assertEqual(ctx['proof']['workbookSourceRecordId'],source.pk)
        self.assertEqual(ctx['proof']['sourceScope']['objectCount'],len(self.design_items))

    def test_03_unknown_new_input_is_blocked(self):
        payload={**self.payload,'rawContent':self.make_blob(changed_input=True)}
        self.error('WORKBOOK_OBJECT_INPUT_CHANGED',lambda:normalize_source_payload(payload,company_id=self.company.pk))

    def test_04_changed_object_identity_is_blocked(self):
        payload={**self.payload,'rawContent':self.make_blob(changed_identity=True)}
        self.error('WORKBOOK_OBJECT_INPUT_CHANGED',lambda:normalize_source_payload(payload,company_id=self.company.pk))

    def test_05_header_and_formula_changes_do_not_get_column_alias_permission(self):
        for changes,code in (({'wrong_header':True},'WORKBOOK_HEADER_MISMATCH'),({'changed_formula':True},'WORKBOOK_ADAPTER_FORMULA_CHANGED')):
            payload={**self.payload,'rawContent':self.make_blob(**changes)}
            self.error(code,lambda:normalize_source_payload(payload,company_id=self.company.pk))

    def test_06_parse_cache_never_skips_fresh_file_hash(self):
        normalize_source_payload(self.payload,company_id=self.company.pk)
        directory=Path(os.environ['PCE_ISOLATED_WORKBOOK_STORAGE']);path=directory/self.blob['storageKey']
        with path.open('ab') as target:target.write(b'fixture corruption')
        self.error('WORKBOOK_FILE_HASH_MISMATCH',lambda:normalize_source_payload(self.payload,company_id=self.company.pk))
        # Restore only this test-created file; no prior workspace source is edited.
        path.write_bytes(path.read_bytes()[:-len(b'fixture corruption')])

    def test_07_parse_cache_never_skips_current_design_or_proof(self):
        source=self.save_source();resolve_workbook_source(source.pk,company_id=self.company.pk)
        ProductDesignItem.objects.filter(pk=self.design_items[0].pk).update(version=999)
        self.error('WORKBOOK_OBJECT_SCOPE_MISMATCH',lambda:resolve_workbook_source(source.pk,company_id=self.company.pk))

    def test_08_cross_company_storage_reference_is_rejected(self):
        self.error('SOURCE_FORMAT_RULE_REFERENCE_MISMATCH',lambda:normalize_source_payload(self.payload,company_id=self.company.pk+100))

    def test_09_draft_is_not_execution_source_or_candidate(self):
        source=self.save_source(confirm=False)
        self.error('WORKBOOK_SOURCE_NOT_CONFIRMED',lambda:resolve_workbook_source(source.pk,company_id=self.company.pk))
        self.assertNotIn(source.pk,[row['id'] for row in workbook_source_facts(self.company.pk)])

    def test_10_source_and_mapping_status_without_audit_are_insufficient(self):
        source=self.save_source()
        BusinessStateTransition.objects.filter(object_type='EngineeringSourceRecord',object_id=source.pk).update(action_code='wrong')
        self.error('WORKBOOK_PUBLICATION_UNPROVEN',lambda:resolve_workbook_source(source.pk,company_id=self.company.pk))

    def test_11_actual_output_coordinates_do_not_relabel_canonical_slot(self):
        source=self.save_source();ctx=resolve_workbook_source(source.pk,company_id=self.company.pk)
        r=self.rows[0];row={'sourceKey':f'FIXTURE:{r}','column':'Z','id':f'FIXTURE:{r}:Z','sourceCell':f'Z{r}',
            'inputs':[{'sourceCell':f'J{r}','value':'1'}]}
        mapped=restore_coordinates([row],ctx)[0]
        self.assertEqual((mapped['id'],mapped['column'],mapped['adapterSlot']),(row['id'],'Z','Z'))
        self.assertEqual((mapped['sourceColumn'],mapped['sourceCell']),('AA',f'AA{r}'))
        self.assertEqual(row['sourceCell'],f'Z{r}')

    def test_12_configuration_is_generic_for_other_column_moves(self):
        config=deepcopy(self.config);config['sheets'][0]['fields'][2].update(rawField='AB',headerCell='AB10')
        validate_mapping(config)
        self.assertEqual(config['sheets'][0]['fields'][2]['canonicalName'],'Z')

    def test_13_full_scope_missing_and_duplicate_rows_are_rejected(self):
        for rows in (self.rows[:-1],self.rows+[self.rows[0]]):
            config=deepcopy(self.config);config['sheets'][0]['sourceRows']=rows
            if len(rows)!=len(set(rows)):
                self.error('WORKBOOK_MAPPING_INVALID',lambda:validate_mapping(config))
            else:
                rule=self.publish_rule(config,'V2')
                payload={**self.payload,'sourceFormatReference':{'ruleId':rule.pk,'ruleVersion':rule.version,'specificationHash':specification_hash(rule.specification)}}
                self.error('WORKBOOK_OBJECT_SCOPE_MISMATCH',lambda:normalize_source_payload(payload,company_id=self.company.pk))

    def test_14_style_only_xfa_dimension_is_not_scanned_as_business_scope(self):
        payload={**self.payload,'rawContent':self.make_blob(styled=True)}
        normalized=normalize_source_payload(payload,company_id=self.company.pk)
        self.assertEqual(normalized['normalization']['rowCount'],len(self.rows))

    def test_15_parse_results_are_copied_and_not_authority_cached(self):
        first=normalize_source_payload(self.payload,company_id=self.company.pk)
        first['normalization']['rows'][0]['canonicalInputs']['J']['value']='999'
        second=normalize_source_payload(self.payload,company_id=self.company.pk)
        self.assertEqual(second['normalization']['rows'][0]['canonicalInputs']['J']['value'],'1')

    def test_16_path_traversal_is_rejected_before_read(self):
        payload={**self.payload,'rawContent':{**self.blob,'storageKey':'../outside.xlsx'}}
        self.error('WORKBOOK_BLOB_INVALID',lambda:normalize_source_payload(payload,company_id=self.company.pk))

    def test_17_method_input_reference_checks_actual_new_file_without_filling(self):
        config=deepcopy(self.config)
        config['sheets'][0]['fields'].append({'rawField':'K','canonicalName':'K','headerCell':'K10','headerValue':'method input',
            'valueType':'decimal','sourceType':'RULE_PARAMETER','methodReference':True,'blankPolicy':'NULL'})
        for row in self.reference['realRows']:row['cells'][f"K{row['row']}"]={'value':3,'formula':None}
        rule=self.publish_rule(config,'V2')
        payload={**self.payload,'sourceFormatReference':{'ruleId':rule.pk,'ruleVersion':rule.version,'specificationHash':specification_hash(rule.specification)}}
        result=normalize_source_payload(payload,company_id=self.company.pk)
        self.assertEqual(result['canonicalInputs']['K']['value'],'3')
        self.assertTrue(result['normalization']['rows'][0]['methodReferenceComparisons'][0]['matchesApprovedMethod'])
        for value in (9,None,0):
            changed={**payload,'rawContent':self.make_blob(method_input=value)}
            self.error('WORKBOOK_METHOD_INPUT_CHANGED',lambda:normalize_source_payload(changed,company_id=self.company.pk))

    def test_18_method_reference_cannot_replace_object_identity_or_blend_authorities(self):
        for changes in ({'methodReference':True},{'methodReference':'true'}):
            config=deepcopy(self.config);config['sheets'][0]['fields'][1].update(changes)
            self.error('WORKBOOK_MAPPING_INVALID',lambda:validate_mapping(config))
        config=deepcopy(self.config);field=config['sheets'][0]['fields'][0]
        field.pop('baselinePath');field['methodReference']=True
        self.error('WORKBOOK_MAPPING_INVALID',lambda:validate_mapping(config))

    def test_19_selected_real_source_identity_reaches_native_continuation_readback(self):
        # Arithmetic remains the explicitly synthetic fixture, while workbook
        # normalization, qualification and native continuation commit are real.
        from .engineering_calculation_continuation_service import EngineeringCalculationContinuationService as Service,continuation_proof
        from .models import EngineeringCalculationContinuation,EngineeringCalculationRecord
        source=self.save_source()
        arguments={**self.args(),'workbook_source_record_id':source.pk}
        preview=Service.preview(**arguments)
        self.assertTrue(preview['ready'])
        self.assertEqual(preview['workbookSourceRecordId'],source.pk)
        result=Service.execute(**arguments,expected_context_hash=preview['expectedContextHash'],
            continuation_basis_hash=preview['continuationBasisHash'],idempotency_key='isolated-workbook-main',reason='isolated selected workbook')
        calc=EngineeringCalculationRecord.objects.get(pk=result['newCalculationId'])
        continuation=EngineeringCalculationContinuation.objects.get(pk=result['continuationId'])
        self.assertEqual(calc.trace['workbookSourceRecordId'],source.pk)
        self.assertEqual(calc.trace['workbookSource']['workbookSha256'],self.blob['sha256'])
        self.assertEqual(continuation_proof(continuation)['workbookSourceRecordId'],source.pk)
        self.assertEqual(result['calculation']['workbookSourceRecordId'],source.pk)
        self.assertTrue(all(fact.trace['sourceColumn']=='AA' for fact in calc.derived_facts.all()))
        facts=Service.facts(user=self.actor,sales_order_item_id=self.items[0].pk,engineering_instance_id=self.instances[0].pk,
            workbook_source_record_id=source.pk)
        self.assertEqual(facts['records'][0]['workbookSourceRecordId'],source.pk)

    def test_20_boolean_derived_cache_is_typed_evidence_never_numeric_zero(self):
        payload={**self.payload,'rawContent':self.make_blob(bool_cache=True)}
        result=normalize_source_payload(payload,company_id=self.company.pk)
        row=result['normalization']['rows'][0]
        self.assertIs(row['cells'][f'Z{self.rows[0]}']['rawValue'],False)
        self.assertIsNone(row['canonicalInputs']['Z']['value'])
        self.assertEqual(row['canonicalInputs']['Z']['cacheEvidence'],{'valueType':'boolean','value':False,'quantified':False})
        changed={**self.payload,'rawContent':self.make_blob(method_input=False)}
        config=deepcopy(self.config)
        config['sheets'][0]['fields'][1].update(rawField='K',headerCell='K10',headerValue='method input')
        rule=self.publish_rule(config,'V2')
        changed['sourceFormatReference']={'ruleId':rule.pk,'ruleVersion':rule.version,'specificationHash':specification_hash(rule.specification)}
        self.error('SOURCE_FORMAT_VALUE_INVALID',lambda:normalize_source_payload(changed,company_id=self.company.pk))

    def test_21_approved_formula_parameter_requires_same_formula_and_actual_cached_value(self):
        config=deepcopy(self.config)
        config['sheets'][0]['fields'].append({'rawField':'K','canonicalName':'K','headerCell':'K10','headerValue':'method input',
            'valueType':'decimal','sourceType':'RULE_PARAMETER','methodReference':True,'blankPolicy':'NULL'})
        for row in self.reference['realRows']:row['cells'][f"K{row['row']}"]={'value':3,'formula':f"=J{row['row']}+2"}
        rule=self.publish_rule(config,'V2')
        payload={**self.payload,'sourceFormatReference':{'ruleId':rule.pk,'ruleVersion':rule.version,'specificationHash':specification_hash(rule.specification)},
            'rawContent':self.make_blob(method_formula=2)}
        result=normalize_source_payload(payload,company_id=self.company.pk)
        comparison=result['normalization']['rows'][0]['methodReferenceComparisons'][0]
        self.assertEqual(comparison['valueAuthority'],'APPROVED_FORMULA_PARAMETER_CACHE')
        self.assertEqual(result['canonicalInputs']['K']['value'],'3')
        for changes,code in (({'method_formula':2,'method_input':9},'WORKBOOK_METHOD_INPUT_CHANGED'),
            ({'method_formula':3},'WORKBOOK_ADAPTER_FORMULA_CHANGED')):
            changed={**payload,'rawContent':self.make_blob(**changes)}
            self.error(code,lambda:normalize_source_payload(changed,company_id=self.company.pk))

    def test_22_original_http_source_and_selected_main_contract(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from rest_framework.test import APIClient
        from .engineering_calculation_continuation_service import normal
        client=APIClient();client.force_authenticate(self.actor)
        foundation='/api/pde/a1-foundation/engineering-source-records/'
        content=(Path(os.environ['PCE_ISOLATED_WORKBOOK_STORAGE'])/self.blob['storageKey']).read_bytes()
        upload=client.post(foundation,{'action':'upload-workbook','file':SimpleUploadedFile('isolated.xlsx',content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},format='multipart')
        self.assertEqual(upload.status_code,200,upload.data)
        payload={**self.payload,'rawContent':normal(upload.data['blob'])}
        projected=client.post(foundation,{'action':'sourceFormatPreview','sourcePayload':payload},format='json')
        self.assertEqual(projected.status_code,200,projected.data)
        self.assertEqual(projected.data['businessWriteCount'],0)
        saved=client.post(foundation,{'source_no':'WB-HTTP','source_name':'isolated HTTP workbook','source_version':'V1',
            'source_type':'controlled_import','source_payload':projected.data['normalizedPayload'],
            'idempotencyKey':'isolated-http-source','reason':'isolated HTTP source'},format='json')
        self.assertEqual(saved.status_code,201,saved.data);source_id=saved.data['row']['id']
        confirmed=client.post(f'/api/pde/a1-engineering/engineering-source-records/{source_id}/transition/',
            {'targetStatus':'confirmed','reason':'isolated HTTP confirmation'},format='json')
        self.assertEqual(confirmed.status_code,200,confirmed.data)
        # Only the acceptance-environment declaration is substituted: the actual
        # test connection remains physically restricted by the runner allowlist.
        with patch('pde.calculation_batch_reuse.verify_read_isolation',return_value={'verified':True,'boundary':'isolated fixture only'}):
            catalog=client.get('/api/pde/a1-engineering/calculations/batch-reuse/',{'action':'workbookSources'})
        self.assertEqual(catalog.status_code,200,catalog.data)
        self.assertIn(source_id,[row['id'] for row in catalog.data['workbookSources']])
        body={'salesOrderItemId':self.items[0].pk,'orderEngineeringInstanceId':self.instances[0].pk,
            'orderEngineeringBaselineId':self.new_baseline_id,'predecessorCalculationId':self.calculations[0].pk,
            'workbookSourceRecordId':source_id}
        path='/api/pde/a1-engineering/calculations/version-continuation/'
        preview=client.post(path+'preview/',body,format='json')
        self.assertEqual(preview.status_code,200,preview.data)
        body.update(expectedContextHash=preview.data['expectedContextHash'],continuationBasisHash=preview.data['continuationBasisHash'],
            idempotencyKey='isolated-http-workbook-main',reason='isolated HTTP selected source')
        executed=client.post(path+'execute/',body,format='json')
        self.assertEqual(executed.status_code,200,executed.data)
        self.assertEqual(executed.data['calculation']['workbookSourceRecordId'],source_id)
        facts=client.get('/api/pde/a1-engineering/calculations/formal-continuation/',
            {'orderNo':self.order.order_no,'workbookSourceRecordId':source_id})
        self.assertEqual(facts.status_code,200,facts.data)
        line=next(row for row in facts.data['lines'] if row['salesOrderItemId']==self.items[0].pk)
        self.assertEqual(line['calculationContinuation']['records'][0]['workbookSourceRecordId'],source_id)
        detail_response=client.get(f"/api/pde/a1-engineering/calculations/{executed.data['calculation']['id']}/")
        self.assertEqual(detail_response.status_code,200,detail_response.data);detail=detail_response.data
        self.assertEqual(detail['calculation']['trace']['workbookSourceRecordId'],source_id)
        WORKBOOK_CONTRACT_READBACK.update(boundary='ISOLATED SYNTHETIC CAPABILITY: numeric method and reference fixture; environment declaration stub only for catalog; real XLSX/Foundation/qualification/native continuation/audit/state',
            upload=normal(upload.data),formatPreview=normal(projected.data),sourceCreate=normal(saved.data),sourceConfirm=normal(confirmed.data),
            workbookSources=normal(catalog.data),mainPreview=normal(preview.data),mainExecute=normal(executed.data),factsAfter=normal(facts.data),calculationReadback=normal(detail))

    def test_23_future_design_revision_does_not_revoke_fixed_main_history(self):
        from .engineering_calculation_continuation_service import EngineeringCalculationContinuationService as Service,continuation_proof
        from .engineering_calculation_service import EngineeringCalculationService
        from .models import EngineeringCalculationContinuation
        source=self.save_source();arguments={**self.args(),'workbook_source_record_id':source.pk}
        preview=Service.preview(**arguments)
        result=Service.execute(**arguments,expected_context_hash=preview['expectedContextHash'],
            continuation_basis_hash=preview['continuationBasisHash'],idempotency_key='isolated-history-main',reason='isolated fixed main')
        row=EngineeringCalculationContinuation.objects.get(pk=result['continuationId']);frozen=continuation_proof(row)
        ProductDesignItem.objects.filter(pk=self.design_items[0].pk).update(version=999)
        self.assertEqual(continuation_proof(row),frozen)
        self.assertEqual(EngineeringCalculationService.get(user=self.actor,object_id=result['newCalculationId'])['trace']['workbookSourceRecordId'],source.pk)
        self.error('WORKBOOK_OBJECT_SCOPE_MISMATCH',lambda:resolve_workbook_source(source.pk,company_id=self.company.pk))

    def test_24_version_continuation_is_validated_against_real_reference_hash(self):
        from .semi_finished_configuration_preview import SOURCE_SHA
        claim={'predecessorAuthority':{'kind':'HASH_VERIFIED_FROZEN_WORKBOOK','sourceSnapshotSha256':SOURCE_SHA,
            'workbookSha256':'a'*64},'successorWorkbookSha256':self.blob['sha256'],'adapterContract':VERSION}
        payload={**self.payload,'sourceVersionContinuation':claim}
        result=normalize_source_payload(payload,company_id=self.company.pk)
        self.assertEqual(result['normalization']['adapterReference']['sourceFiles'][0]['sha256'],'a'*64)
        for key in ('workbookSha256','sourceSnapshotSha256'):
            changed=deepcopy(payload);changed['sourceVersionContinuation']['predecessorAuthority'][key]='b'*64
            self.error('WORKBOOK_VERSION_CONTINUATION_UNPROVEN',lambda:normalize_source_payload(changed,company_id=self.company.pk))

    def test_25_actual_adapter_input_cannot_be_misclassified_as_derived_or_omitted(self):
        config=deepcopy(self.config);field=config['sheets'][0]['fields'][1]
        field['sourceType']='ENGINEERING_DERIVED';field.pop('baselinePath');field.pop('designOverrideField')
        rule=self.publish_rule(config,'V2')
        payload={**self.payload,'rawContent':self.make_blob(changed_input=True),'sourceFormatReference':{
            'ruleId':rule.pk,'ruleVersion':rule.version,'specificationHash':specification_hash(rule.specification)}}
        self.error('WORKBOOK_ADAPTER_INPUT_AUTHORITY_REQUIRED',lambda:normalize_source_payload(payload,company_id=self.company.pk))
        config=deepcopy(self.config);config['sheets'][0]['fields'].pop(1)
        rule=self.publish_rule(config,'V3')
        payload['sourceFormatReference']={'ruleId':rule.pk,'ruleVersion':rule.version,'specificationHash':specification_hash(rule.specification)}
        self.error('WORKBOOK_ADAPTER_INPUT_MAPPING_REQUIRED',lambda:normalize_source_payload(payload,company_id=self.company.pk))

    def test_26_missing_baseline_path_is_not_a_formal_null(self):
        from .engineering_workbook_source_service import _path
        self.assertIsNone(_path({'present':None},'present'))
        self.error('WORKBOOK_BASELINE_FIELD_MISSING',lambda:_path({'present':None},'absent'))
        config=deepcopy(self.config)
        config['sheets'][0]['fields'].append({'rawField':'K','canonicalName':'K','headerCell':'K10','headerValue':'method input',
            'valueType':'decimal','sourceType':'ENGINEERING_INPUT','baselinePath':'source.rawValue.absent','blankPolicy':'NULL'})
        rule=self.publish_rule(config,'V2')
        payload={**self.payload,'rawContent':self.make_blob(method_input=None),'sourceFormatReference':{
            'ruleId':rule.pk,'ruleVersion':rule.version,'specificationHash':specification_hash(rule.specification)}}
        self.error('WORKBOOK_BASELINE_FIELD_MISSING',lambda:normalize_source_payload(payload,company_id=self.company.pk))

    def test_27_condition_preflight_api_uses_selected_source_and_exact_baseline(self):
        from rest_framework.test import APIClient
        from . import formal_engineering_continuation_service as native
        from .engineering_calculation_continuation_service import normal
        source=self.save_source();before=MainFixture.counts(self)
        client=APIClient();client.force_authenticate(self.actor)
        response=client.get('/api/pde/a1-engineering/order-calculation/condition-preflight/',
            {'orderNo':self.order.order_no,'sourceRecordId':self.source.pk,'workbookSourceRecordId':source.pk})
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['workbookSourceRecordId'],source.pk)
        self.assertEqual(response.data['businessWriteSideEffectCount'],0)
        self.assertEqual(before,MainFixture.counts(self))
        self.assertTrue(response.data['lines'])
        for line in response.data['lines']:
            self.assertEqual(line['confirmedBaseline']['id'],self.new_baseline_id)
            self.assertTrue(line['fullValidation']['ready'],line['fullValidation'])
            self.assertEqual(line['fullValidation']['selection']['workbookSourceRecordId'],source.pk)
            self.assertEqual(line['fullValidation']['selection']['baselineReference']['id'],self.new_baseline_id)
        self.assertTrue(native.run_batch.call_args_list)
        for call in native.run_batch.call_args_list:
            self.assertEqual(call.kwargs['workbook_source_context']['proof']['workbookSourceRecordId'],source.pk)
            self.assertNotIn('historical_read',call.kwargs)
        CONDITION_PREFLIGHT_READBACK.update(boundary='ISOLATED SYNTHETIC METHOD/REFERENCE/INPUT CONTRACT; real original condition-preflight API and native source qualification; no formal writes',
            selectedSource=normal(response.data))

    def test_28_condition_preflight_rejects_missing_source_and_wrong_object_scope(self):
        from rest_framework.test import APIClient
        source=self.save_source();client=APIClient();client.force_authenticate(self.actor)
        path='/api/pde/a1-engineering/order-calculation/condition-preflight/'
        before=MainFixture.counts(self)
        for changes,code in (({'workbookSourceRecordId':999999},'WORKBOOK_SOURCE_NOT_VISIBLE'),
            ({'workbookSourceRecordId':'not-an-id'},'WORKBOOK_SOURCE_ID_INVALID'),
            ({'sourceRecordId':self.source.pk+999},'PREFLIGHT_SOURCE_CONTEXT_MISMATCH')):
            query={'orderNo':self.order.order_no,'sourceRecordId':self.source.pk,'workbookSourceRecordId':source.pk,**changes}
            response=client.get(path,query)
            self.assertEqual(response.status_code,400,response.data);self.assertEqual(response.data['code'],code)
        self.assertEqual(before,MainFixture.counts(self))

    def test_29_condition_preflight_default_stays_strict_without_history_fallback(self):
        from rest_framework.test import APIClient
        from . import formal_engineering_continuation_service as native
        from .calculation_batch_reuse import run_batch
        from .engineering_calculation_continuation_service import normal
        client=APIClient();client.force_authenticate(self.actor);before=MainFixture.counts(self)
        with patch.object(native,'run_batch',side_effect=run_batch),patch('pde.calculation_batch_reuse.load_source',
            side_effect=FileNotFoundError('isolated missing registered original workbook')) as strict_loader:
            response=client.get('/api/pde/a1-engineering/order-calculation/condition-preflight/',
                {'orderNo':self.order.order_no,'sourceRecordId':self.source.pk})
        self.assertEqual(response.status_code,400,response.data)
        self.assertEqual(response.data['code'],'CONDITION_PREFLIGHT_SOURCE_READ_FAILED')
        self.assertEqual(response.data['businessWriteSideEffectCount'],0)
        self.assertEqual(before,MainFixture.counts(self));strict_loader.assert_called_once()
        CONDITION_PREFLIGHT_READBACK['unselectedOriginalUnavailable']=normal(response.data)

    def test_30_condition_preflight_rechecks_selected_file_and_draft_authority(self):
        from rest_framework.test import APIClient
        source=self.save_source(confirm=False);client=APIClient();client.force_authenticate(self.actor)
        path='/api/pde/a1-engineering/order-calculation/condition-preflight/'
        query={'orderNo':self.order.order_no,'sourceRecordId':self.source.pk,'workbookSourceRecordId':source.pk}
        response=client.get(path,query)
        self.assertEqual(response.status_code,400,response.data);self.assertEqual(response.data['code'],'WORKBOOK_SOURCE_NOT_CONFIRMED')
        Lifecycle.transition('engineering-source-records',object_id=source.pk,target_status='confirmed',user=self.actor,reason='isolated')
        before=MainFixture.counts(self);directory=Path(os.environ['PCE_ISOLATED_WORKBOOK_STORAGE']);file=directory/self.blob['storageKey']
        original=file.read_bytes()
        try:
            with file.open('ab') as target:target.write(b'isolated corruption')
            response=client.get(path,query)
            self.assertEqual(response.status_code,400,response.data);self.assertEqual(response.data['code'],'WORKBOOK_FILE_HASH_MISMATCH')
            self.assertEqual(before,MainFixture.counts(self))
        finally:file.write_bytes(original)

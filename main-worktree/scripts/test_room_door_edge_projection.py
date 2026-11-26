"""Real-source projection and production read-only API guards."""
import copy,os,sys,unittest
from unittest.mock import patch
from room_door_edge import ROOT,OUT,OLD,read,save,sha
sys.path.insert(0,str(ROOT/'backend'));sys.path.insert(0,str(ROOT/'backend/venv/Lib/site-packages'))
import test_semi_finished_role_layer_projection as legacy
from pde.semi_finished_configuration_validation import apply_validation
from pde.room_door_edge_preview import apply_room_door,load_evidence

class DoorProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        legacy.LayerProjectionTests.setUpClass();cls.base=apply_validation(legacy.LayerProjectionTests.base,formal=legacy.LayerProjectionTests.formal)
    def build(self):return apply_room_door(self.base)
    def door(self,p):return next(c for c in p['configurations'] if c['sourceCode']=='QSFB4601001')['layerPreview']
    def test_one_visible_fact(self):
        layer=self.door(self.build())
        for row in layer['components']:self.assertIs(row['visibleAreaFact'],next(v for v in layer['veneerRows'] if v['row']==row['row']))
    def test_8_rows_16_types(self):
        layer=self.door(self.build());self.assertEqual((len(layer['components']),len(layer['roomDoorRequirements'])),(8,16))
    def test_three_layer_frozen_only_two_configs(self):self.assertEqual(sum(c['roleLayerUserValidated'] for c in self.build()['configurations']),2)
    def test_new_manual_still_pending(self):self.assertEqual(self.build()['summary']['roomDoorManualRevalidation'],'PENDING')
    def test_board_veneer_and_tri_same(self):
        p=self.build()
        for key in ('board','veneer','edge'):self.assertEqual(p['roleLayerSummary'][key],self.base['roleLayerSummary'][key])
        tri=lambda p:next(c for c in p['configurations'] if c['sourceCode']=='BTKF2601001')['layerPreview']
        self.assertEqual(tri(p),tri(self.base))
    def test_no_gross_or_selected_material(self):
        for r in self.door(self.build())['roomDoorRequirements']:
            for k in ('quantity','materialId','grossLengthM','perEdgeAllowanceMm'):self.assertIsNone(r[k])
    def test_integrity_failclosed(self):
        with patch('pde.room_door_edge_preview.EVIDENCE_SHA','wrong'):
            with self.assertRaisesRegex(ValueError,'INTEGRITY_FAILED'):load_evidence()
    def test_owner_drift(self):
        e=load_evidence();e['roomDoorRequirements'][0]['componentId']=-1
        with self.assertRaisesRegex(ValueError,'OWNER_DRIFT'):apply_room_door(self.base,e)
    def test_visible_drift(self):
        e=load_evidence();e['visibleFacts'][0]['visibleAreaM2']='0'
        with self.assertRaisesRegex(ValueError,'VISIBLE_FACT_DRIFT'):apply_room_door(self.base,e)
    def test_source_not_mutated(self):b=copy.deepcopy(self.base);self.build();self.assertEqual(b,self.base)

suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(legacy.previous.ConfigurationProjectionTests),
    unittest.defaultTestLoader.loadTestsFromTestCase(legacy.LayerProjectionTests),unittest.defaultTestLoader.loadTestsFromTestCase(DoorProjectionTests)])
result=unittest.TextTestRunner(verbosity=1).run(suite);assert result.wasSuccessful()
DB=ROOT/'backend/db.sqlite3';before=sha(DB)
os.environ['DJANGO_SETTINGS_MODULE']='pce_backend.settings'
from django.conf import settings
settings.DATABASES['default']['NAME']=DB.as_uri()+'?mode=ro';settings.DATABASES['default']['OPTIONS']={'uri':True}
import django;django.setup()
from django.db import connection
from system.models import User
from rest_framework.test import APIRequestFactory,force_authenticate
from pde.views import EngineeringCalculationReadinessView
from pde.engineering_calculation_service import EngineeringCalculationError
connection.ensure_connection();connection.connection.execute('PRAGMA query_only=ON')
actor=User.objects.filter(is_superuser=True,company_id=1,is_active=True).defer('password').first();assert actor
factory=APIRequestFactory();view=EngineeringCalculationReadinessView.as_view();sql=[]
def guard(execute,statement,params,many,context):
    assert statement.lstrip().split()[0].upper() in {'SELECT','PRAGMA','EXPLAIN'},statement[:40]
    sql.append(statement.lstrip().split()[0].upper());return execute(statement,params,many,context)
def request(mode='semi-finished-structure',user=actor,method='get'):
    r=getattr(factory,method)('/api/pde/a1-engineering/calculations/readiness/',{'subview':mode})
    if user:force_authenticate(r,user)
    return view(r)
checks=[]
with connection.execute_wrapper(guard):
    r=request();assert r.status_code==200,str(r.data)
    assert r.data['semiFinishedConfiguration']==apply_room_door(DoorProjectionTests.base)
    assert all(r.data[k]==r.data['strictFacts'] for k in ('apiFacts','pageFacts','diagnosticFacts'))
    save('API_READONLY_EVIDENCE.json',r.data);checks.append('authorized same-source GET')
    assert request(user=None).status_code in (401,403);checks.append('anonymous denied')
    with patch('pde.engineering_calculation_service.EngineeringCalculationService._authorize',side_effect=EngineeringCalculationError('PERMISSION_DENIED','denied')):
        denied=request();assert denied.status_code==403 and denied.data['resultCount'] is None
    checks.append('insufficient permission denied')
    with patch('pde.room_door_edge_preview.EVIDENCE_SHA','wrong'):
        failed=request();assert failed.status_code==503 and failed.data['factLoadStatus']=='read_failed' and failed.data['resultCount'] is None
        assert all(k in failed.data for k in ('apiUrl','httpStatus','errorCode','errorMessage','loadedAt','tenantId','batchId'))
    checks.append('new evidence drift complete failure contract')
    assert request(mode='wrong').status_code==400;checks.append('unknown subview rejected')
    assert request(method='post').status_code==405;checks.append('POST rejected')
    old=request(mode='');assert old.status_code==200 and len(old.data['formalRules'])==4 and old.data['materialRuleDefinition']['sourceRowCount']==71
    checks.append('existing rules and 71 source rows unchanged')
connection.close();assert sha(DB)==before
save('API_TEST_RESULTS.json',{'status':'PASS','unitTests':result.testsRun,'apiChecks':checks,'sqlCount':len(sql),
    'dbMode':'mode=ro + query_only + statement guard','productionSHA':before,'productionBusinessWrite':0})
print('Projection',result.testsRun,'API',len(checks),'PASS')

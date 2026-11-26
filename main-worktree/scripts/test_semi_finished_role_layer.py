"""Isolated role constraints, FK provenance and NULL/geometry non-regression tests."""
import copy
import json
import unittest
from decimal import Decimal
from semi_finished_role_layer import bootstrap, read, save, OUT
bootstrap()
from django.db import transaction, IntegrityError, connection
from django.core.exceptions import ValidationError
from pde.models import (MaterialConfiguration, MaterialConfigurationSourceBinding, MaterialFamilyAllowedMaterial,
    TemplateMaterialRequirementSlot, ComponentMaterialRequirement, EngineeringBreakdownItem)
from pde.material_configuration_service import MaterialConfigurationService
from masterdata.models import Material, ExternalIdentity

class Tests(unittest.TestCase):
    def setUp(self):
        self.tx=transaction.atomic();self.tx.__enter__()
        self.config=MaterialConfiguration.objects.get(configuration_code='BTKF2601001')
        self.binding=self.config.source_bindings.order_by('source_row').first()
        self.req=ComponentMaterialRequirement.objects.order_by('id').first()
    def tearDown(self):
        transaction.set_rollback(True);self.tx.__exit__(None,None,None)
    def invalid(self,obj):
        with self.assertRaises(ValidationError):obj.full_clean()
    def test_two_frozen_identities(self):
        self.assertEqual(list(MaterialConfiguration.objects.order_by('configuration_code').values_list('configuration_code',flat=True)),['BTKF2601001','QSFB4601001'])
    def test_three_roles_each(self):
        for c in MaterialConfiguration.objects.all():
            self.assertEqual(set(c.composition_slots.values_list('slot_code',flat=True)),{'SUBSTRATE','VENEER','SURFACE_PAINT'})
            self.assertEqual(set(c.composition_slots.values_list('quantity_mode',flat=True)),{'CALCULATED'})
    def test_configuration_rejects_edge(self):
        s=self.config.composition_slots.first();s.slot_code='EDGE';self.invalid(s)
    def test_configuration_rejects_other_fixed(self):
        s=self.config.composition_slots.first();s.slot_code='OTHER_FIXED';self.invalid(s)
    def test_configuration_rejects_unknown_quantity_mode(self):
        s=self.config.composition_slots.first();s.quantity_mode='UNKNOWN';self.invalid(s)
    def test_configuration_rejects_manual_quantity_mode(self):
        s=self.config.composition_slots.first();s.quantity_mode='MANUAL';self.invalid(s)
    def test_configuration_role_db_constraint(self):
        with self.assertRaises(IntegrityError),transaction.atomic():
            self.config.composition_slots.filter(slot_code='VENEER').update(slot_code='EDGE')
    def test_surface_validated_rule_pending(self):
        result=MaterialConfigurationService.role_preview(self.config.composition_slots.get(slot_code='SURFACE_PAINT'))
        self.assertEqual((result['roleStatus'],result['quantityMode'],result['ruleReadiness']),('VALIDATED','CALCULATED','PENDING'))
        self.assertIsNone(result['quantity'])
    def test_source_components_not_fake_calculations(self):
        self.assertEqual(EngineeringBreakdownItem.objects.filter(source_binding__isnull=False,calculation=None).count(),71)
    def test_source_component_one_origin(self):
        c=self.req.breakdown_item;c.calculation_id=1;self.invalid(c)
    def test_source_component_unique_row(self):
        c=self.req.breakdown_item;c.pk=None;self.invalid(c)
    def test_no_fabricated_structure_parent(self):
        c=self.req.breakdown_item;c.parent_id=c.pk;self.invalid(c)
    def test_requirement_owner_is_component(self):
        self.assertEqual(ComponentMaterialRequirement.objects.filter(component=None,breakdown_item__isnull=False).count(),59)
    def test_requirement_owner_missing(self):
        self.req.breakdown_item=None;self.invalid(self.req)
    def test_noncomponent_rejected(self):
        c=self.req.breakdown_item;c.item_type='operation';self.req.breakdown_item=c;self.invalid(self.req)
    def test_duplicate_requirement(self):
        self.req.pk=None;self.invalid(self.req)
    def test_edge_quantity_mode(self):
        self.req.quantity_mode='MANUAL';self.invalid(self.req)
    def test_edge_no_zero(self):
        self.req.quantity=0;self.invalid(self.req)
    def test_edge_no_one_placeholder(self):
        self.req.quantity=1;self.invalid(self.req)
    def test_edge_no_gross_without_allowance(self):
        self.req.quantity=Decimal('1');self.req.quantity_status='calculated';self.invalid(self.req)
    def test_negative_allowance_rejected(self):
        self.req.per_edge_allowance_mm=-1;self.invalid(self.req)
    def test_edge_preview_nulls(self):
        r=MaterialConfigurationService.component_edge_preview(self.req)
        self.assertEqual(r['owner'],'ENGINEERING_COMPONENT');self.assertEqual(r['baseUom'],'m')
        for k in ('quantity','materialId','perEdgeAllowanceMm','grossLengthM'):self.assertIsNone(r[k])
    def test_thickness_user_input(self):
        self.assertEqual(MaterialConfigurationSourceBinding.objects.filter(thickness_semantic='BOARD_MATCH_INPUT').count(),63)
        self.assertEqual(self.binding.thickness_semantic,'BOARD_MATCH_INPUT')
    def test_door_wall_not_board(self):
        self.assertEqual(MaterialConfigurationSourceBinding.objects.filter(source_sheet='房门单',thickness_semantic='BOARD_MATCH_INPUT').count(),0)
    def test_thickness_requires_source_decision(self):
        self.binding.source_lineage.pop('thicknessAuthority');self.invalid(self.binding)
    def test_thickness_zero_rejected(self):
        self.binding.thickness_value=0;self.invalid(self.binding)
    def test_unknown_boolean_frozen(self):
        for a in self.config.attributes.filter(attribute_kind__in=['splice','skinFeel']):
            self.assertEqual(a.knowledge_state,'UNKNOWN');self.assertIsNone(a.canonical_value)
        q=MaterialConfiguration.objects.get(configuration_code='QSFB4601001')
        self.assertEqual(set(q.attributes.filter(attribute_kind__in=['splice','skinFeel']).values_list('knowledge_state',flat=True)),{'KNOWN_FALSE'})
    def test_family_blocks_not_thickness(self):
        result=MaterialConfigurationService.resolve_substrate(self.config,self.binding)
        self.assertIn('ALLOWED_MATERIAL_SPECIFICATION_SET_UNRESOLVED',result['blockers'])
        self.assertNotIn('THICKNESS_SEMANTIC_UNKNOWN',result['blockers'])
    def allowed(self,stock):
        # Synthetic allowance for a formal-source test member, rolled back; NOT business approval.
        member=MaterialFamilyAllowedMaterial(family=self.config.attributes.get(attribute_kind='substrate').material_family,
            material_id=stock['formal']['id'],source_identity_id=stock['identityEvidence'][0]['id'],
            length_mm=Decimal(stock['dimensions']['length']),width_mm=Decimal(stock['dimensions']['width']),thickness_mm=Decimal(stock['dimensions']['thickness']),
            source_validated=True,specification_validated=True,evidence={'scope':'SIMULATED_FOR_TEST_ROLLBACK'})
        member.save();return member
    def test_exact_match_when_allowance_explicit(self):
        stock=next(s for s in read('BOARD_MATCH_PREVIEW.json')['formalStocks'] if s['formalSpecificationMatched'] and s['dimensions'] and Decimal(s['dimensions']['thickness'])==self.binding.thickness_value)
        member=self.allowed(stock)
        result=MaterialConfigurationService.resolve_substrate(self.config,self.binding)
        self.assertEqual(result['materialId'],member.material_id);self.assertIsNone(result['quantity'])
    def test_nearest_thickness_never_used(self):
        stock=next(s for s in read('BOARD_MATCH_PREVIEW.json')['formalStocks'] if s['formalSpecificationMatched'] and s['dimensions'] and s['dimensions']['thickness']=='20')
        self.allowed(stock);self.binding.thickness_value=Decimal('22')
        result=MaterialConfigurationService.resolve_substrate(self.config,self.binding)
        self.assertIsNone(result['materialId']);self.assertIn('PROCUREMENT_MATERIAL_MASTER_DATA_GAP',result['blockers'])
    def test_equal_specs_no_first_material(self):
        stocks=[s for s in read('BOARD_MATCH_PREVIEW.json')['formalStocks'] if s['formalSpecificationMatched'] and s['dimensions']=={'length':'2440','width':'1220','thickness':'18'}]
        self.allowed(stocks[0]);self.allowed(stocks[1])
        result=MaterialConfigurationService.resolve_substrate(self.config,self.binding)
        self.assertIsNone(result['materialId']);self.assertIn('AMBIGUOUS_MINIMUM_SPEC',result['blockers'])
    def test_quantities_still_null(self):
        self.assertEqual(ComponentMaterialRequirement.objects.exclude(quantity=None).count(),0)
        self.assertEqual(TemplateMaterialRequirementSlot.objects.exclude(fixed_quantity=None).count(),0)
    def test_minimum_formal_spec_not_first_or_largest(self):
        stocks=read('BOARD_MATCH_PREVIEW.json')['formalStocks']
        small=next(s for s in stocks if s['dimensions']=={'length':'2440','width':'1220','thickness':'18'})
        large=next(s for s in stocks if s['dimensions']=={'length':'3200','width':'1220','thickness':'18'})
        self.allowed(large);member=self.allowed(small)
        result=MaterialConfigurationService.resolve_substrate(self.config,self.binding)
        self.assertEqual(result['materialId'],member.material_id)
    def test_geometry_exact_boundary_inclusive(self):
        stock=next(s for s in read('BOARD_MATCH_PREVIEW.json')['formalStocks'] if s['dimensions']=={'length':'2440','width':'1220','thickness':'18'})
        member=self.allowed(stock)
        self.binding.source_lineage['rawEngineeringRow'].update(length=2440,width=1220)
        self.assertEqual(MaterialConfigurationService.resolve_substrate(self.config,self.binding)['materialId'],member.material_id)
    def test_geometry_one_mm_over_blocks(self):
        stock=next(s for s in read('BOARD_MATCH_PREVIEW.json')['formalStocks'] if s['dimensions']=={'length':'2440','width':'1220','thickness':'18'})
        self.allowed(stock)
        self.binding.source_lineage['rawEngineeringRow'].update(length=2441,width=1220)
        result=MaterialConfigurationService.resolve_substrate(self.config,self.binding)
        self.assertIsNone(result['materialId']);self.assertIn('NO_EXACT_GEOMETRY_SPEC',result['blockers'])
    def test_rotation_not_implicitly_authorized(self):
        stock=next(s for s in read('BOARD_MATCH_PREVIEW.json')['formalStocks'] if s['dimensions']=={'length':'2440','width':'1220','thickness':'18'})
        self.allowed(stock)
        self.binding.source_lineage['rawEngineeringRow'].update(length=1200,width=2400)
        result=MaterialConfigurationService.resolve_substrate(self.config,self.binding)
        self.assertIsNone(result['materialId']);self.assertIn('ROTATION_PERMISSION_PENDING',result['blockers'])
    def test_resolved_material_identity_can_keep_quantity_pending(self):
        # Contract-only synthetic resolution; rolled back, not a real material choice.
        from system.models import User
        from django.utils import timezone
        material=Material.objects.filter(company_id=self.config.company_id,base_uom_id=self.req.uom_id).first()
        self.assertIsNotNone(material)
        self.req.material=material;self.req.identity_status='resolved';self.req.selection_status='resolved'
        self.req.resolved_by=User.objects.filter(company_id=self.config.company_id).first()
        self.req.resolved_at=timezone.now();self.req.identity_resolution_decision={'scope':'SIMULATED_FOR_TEST_ROLLBACK'}
        self.req.full_clean()
        self.assertIsNone(self.req.quantity);self.assertIsNone(self.req.normalized_base_quantity)
    def test_source_net_area_independent_procurement(self):
        v=read('VENEER_NET_PREVIEW.json');self.assertEqual(v['summary']['netPass'],70);self.assertEqual(v['summary']['netBlocked'],1)
        self.assertTrue(all(r['procurementMaterialId'] is None for r in v['rows']))
    def test_allocation_is_not_stock_quantity(self):
        b=read('BOARD_MATCH_PREVIEW.json')['summary'];self.assertEqual(b['exactThicknessMatch'],31);self.assertEqual(b['boardExactMatch'],0)
    def test_edge_only_explicit_rows(self):
        rows=read('EDGE_COMPONENT_PREVIEW.json')['rows'];self.assertEqual(len(rows),59)
        self.assertTrue(all(r['row'] not in {9,36,60,68} and r['sheet']=='三合一生产单' for r in rows))

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    save('ISOLATED_TESTS.json',{'testsRun':result.testsRun,'failures':[(str(t),s) for t,s in result.failures],
        'errors':[(str(t),s) for t,s in result.errors],'status':'PASS' if result.wasSuccessful() else 'FAIL',
        'syntheticAllowances':'SIMULATED_FOR_TEST; all transactions rolled back','productionBusinessWrite':0})
    with connection.cursor() as cur:cur.execute('PRAGMA foreign_key_check');assert not cur.fetchall()
    assert MaterialFamilyAllowedMaterial.objects.count()==0
    raise SystemExit(0 if result.wasSuccessful() else 1)

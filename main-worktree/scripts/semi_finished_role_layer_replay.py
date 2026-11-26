"""Two frozen configurations and explicit-edge source components, isolation only."""
import json
from decimal import Decimal
from semi_finished_role_layer import ROOT, OUT, OLD, ISO, bootstrap, read, save, sha, INSTRUCTION
bootstrap()
from django.apps import apps
from django.core import serializers
from django.db import transaction, connection
from pde.models import (MaterialConfiguration, MaterialConfigurationAttribute, MaterialConfigurationSourceBinding,
    TemplateMaterialRequirementSlot, ComponentMaterialRequirement, EngineeringBreakdownItem, MaterialFamilyAllowedMaterial)
from pde.material_configuration_service import MaterialConfigurationService
from pde.material_configuration_serializers import MaterialConfigurationSerializer
from semi_finished_model_closure_serialization import encoder

DECISION='USER_ATTACHMENT_65975ebd_SHA256_'+sha(INSTRUCTION)
previous=json.loads((OLD/'REAL_CASE_ROUNDTRIP_FIXTURE.json').read_text(encoding='utf-8'))
evidence=read('SOURCE_RECHECK.json')
edge_by_key={(r['sheet'],r['row']):r for r in read('EDGE_COMPONENT_PREVIEW.json')['rows']}
created=[]
with transaction.atomic():
    assert MaterialConfiguration.objects.count()==0
    # Preserve the two previously validated attribute sets byte-for-byte. This is
    # a fresh database, not deletion/modification of previous replay evidence.
    copied=[r for r in previous if r['model'] not in {'pde.templatematerialrequirementslot'}]
    for entry in copied:
        if entry['model']=='pde.materialconfigurationsourcebinding' and entry['fields']['source_sheet']=='三合一生产单':
            entry['fields']['thickness_semantic']='BOARD_MATCH_INPUT'
            entry['fields']['source_lineage']['thicknessAuthority']={'column':'L','userDecisionSha256':sha(INSTRUCTION),
                'semantic':'BOARD_MATCH_INPUT','scope':'三合一板材匹配；不推广至房门墙厚'}
        for obj in serializers.deserialize('json',json.dumps([entry]),ignorenonexistent=False):
            assert not type(obj.object).objects.filter(pk=obj.object.pk).exists(),entry['model']
            obj.object.full_clean()
            obj.save()
            created.append(obj.object)
    cases=[]
    for config in MaterialConfiguration.objects.order_by('configuration_code'):
        attrs={a.attribute_kind:a for a in config.attributes.all()}
        roles=[]
        for code,label,key in [('SUBSTRATE','坯板','substrate'),('VENEER','木皮','veneer'),('SURFACE_PAINT','表面 / 工艺耗材','paintKind')]:
            slot=TemplateMaterialRequirementSlot(material_configuration=config,configuration_attribute=attrs[key],slot_code=code,slot_name=label,
                material_category=attrs['substrate'].material_family if code=='SUBSTRATE' else None,
                quantity_mode='CALCULATED',composition_channel='CALCULATED_COMPOSITION',
                selection_constraints={'scope':'ISOLATED_REPLAY','roleStatus':'VALIDATED','ruleReadiness':'PENDING',
                    'userDecision':DECISION,'lossRate':None,'consumptionRate':None})
            slot.full_clean();slot.save();created.append(slot)
            roles.append(MaterialConfigurationService.role_preview(slot,config.source_bindings.first()))
        cases.append({'configurationCode':config.configuration_code,'configurationId':config.pk,'formalMaterialId':config.material_id,
            'sourceIdentityId':config.source_identity_id,'inheritedRows':config.source_bindings.count(),'sourceValidated':True,
            'canonicalConfiguration':MaterialConfigurationSerializer(config).data,'roles':roles,
            'replayStatus':'PASS','businessCalculationStatus':'BLOCKED'})
    from masterdata.models import UnitOfMeasure
    metre=UnitOfMeasure.objects.get(company_id=1,code='m',is_active=True)
    component_rows=[];edge_rows=[]
    for row in evidence['components']:
        binding=MaterialConfigurationSourceBinding.objects.get(source_sheet=row['sheet'],source_row=row['row'])
        edge=edge_by_key.get((row['sheet'],row['row']))
        component=EngineeringBreakdownItem(source_binding=binding,line_no=row['row'],item_type='component',
            item_code=f"SOURCE-COMPONENT-{binding.pk}",item_name=row['role'] or '来源组件名称未填',
            attributes={'scope':'ISOLATED_REPLAY_SOURCE_COMPONENT','geometry':{k:row[k] for k in ('length','width','thickness','quantity','dimensionSemantics')},
                'edgePreview':edge,'space':row['space'],'sourceRole':row['role'],'sourceSha256':row['sourceSha256'],
                'configurationReference':'source_binding.configuration','structureAuthority':'SOURCE_REFERENCE_ONLY_NOT_NUMERIC_OR_FORMULA_AUTHORITY'})
        component.full_clean();component.save();created.append(component)
        component_rows.append({'componentId':component.pk,'sourceBindingId':binding.pk,**{k:row[k] for k in ('sheet','row','configurationCode','role','space','productCategory','length','width','thickness','quantity','dimensionSemantics','visibleCondition','edgeMode')}})
        if edge and edge['edgeDimensionsMm']:
            requirement=ComponentMaterialRequirement(breakdown_item=component,line_no=1,requirement_kind='edge_banding',
                quantity_mode='CALCULATED',quantity_status='pending_calculation',quantity=None,
                quantity_basis='ORDER_TOTAL',uom=metre,uom_status='confirmed',source_uom_text='m',
                identity_status='unresolved',selection_status='insufficient_information',
                unresolved_requirement={'role':'EDGE_BANDING','materialSpecification':None,'sourceEdgeMode':edge['edgeMode']},
                source_lineage={'scope':'ISOLATED_REPLAY','sourceSha256':row['sourceSha256'],'sheet':row['sheet'],'row':row['row'],
                    'userDecision':DECISION,'netLengthEvidence':edge['netLengthM'],'quantityNotGenerated':True},
                order_specification={'material':None,'width':None,'thickness':None,'color':None},
                selection_constraints_snapshot={'perEdgeAllowance':None,'ruleReadiness':'PENDING','procurementIdentity':'UNRESOLVED'})
            requirement.full_clean();requirement.save();created.append(requirement)
            edge_rows.append(MaterialConfigurationService.component_edge_preview(requirement))
    assert len(cases)==2 and len(component_rows)==71 and len(edge_rows)==59
    assert TemplateMaterialRequirementSlot.objects.count()==6
    assert MaterialConfigurationSourceBinding.objects.filter(thickness_semantic='BOARD_MATCH_INPUT').count()==63
    assert ComponentMaterialRequirement.objects.exclude(quantity=None).count()==0
    with connection.cursor() as cur:
        cur.execute('PRAGMA foreign_key_check');assert not cur.fetchall()
    # Save in actual insertion order for deterministic FK-safe round-trip.
    fixture=serializers.serialize('json',created,indent=2,cls=encoder())
    (OUT/'REAL_CASE_ROUNDTRIP_FIXTURE.json').write_text(fixture+'\n',encoding='utf-8')
    save('ISOLATED_CREATED_OBJECTS.json',[{'model':o._meta.label,'table':o._meta.db_table,'pk':o.pk} for o in created])
report={'schemaVersion':'PCE-MATERIAL-ROLE-LAYER-ISOLATED-1','scope':'ISOLATED_REPLAY_NOT_PRODUCTION','status':'PASS',
    'userDecision':DECISION,'sourceBundleSha256':sha(ROOT/'backend/pde/semi_finished_configuration_source.json'),
    'sourceIdentityValidationFrozen':True,'roleLayerUserManualValidation':'PENDING','cases':cases,'components':component_rows,'edgeRequirements':edge_rows,
    'boardPreview':read('BOARD_MATCH_PREVIEW.json'),'veneerPreview':read('VENEER_NET_PREVIEW.json'),
    'edgeSummary':read('EDGE_COMPONENT_PREVIEW.json')['summary'],'structureAuthority':evidence['roughStructure'],
    'createdObjects':len(created),'configurationRoles':6,'sourceInheritedRows':71,'sourceComponentCount':71,'isolatedPendingComponentRequirements':59,
    'formalProcurementRequirementsGenerated':0,'actualConsumptionQuantityGenerated':0,'unknownQuantitiesPreserved':True,
    'unknownThicknessRows':0,'productionBusinessWrite':0,'productionMigrationApplied':False,'domainRuleFormalization':'NOT_ENTERED',
    'formalEvidenceFingerprint':sha(OUT/'FORMAL_BEFORE.json')}
save('ISOLATED_REPLAY.json',report)
print(json.dumps({k:report[k] for k in ('status','createdObjects','configurationRoles','sourceComponentCount','isolatedPendingComponentRequirements','formalProcurementRequirementsGenerated','unknownThicknessRows')},ensure_ascii=False))

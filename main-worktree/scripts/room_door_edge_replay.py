"""Minimal isolated schema and replay, original requirement carrier only."""
import json
import sys
from decimal import Decimal
from room_door_edge import ROOT,OUT,OLD,ISO,BACKEND,bootstrap,read,save,sha,INSTRUCTION

def migrate():
    bootstrap()
    from django.apps import apps
    from django.core.management import call_command
    from django.db import connection
    from django.db.migrations.autodetector import MigrationAutodetector
    from django.db.migrations.questioner import NonInteractiveMigrationQuestioner
    from django.db.migrations.state import ProjectState
    from django.db.migrations.writer import MigrationWriter
    from django.db.migrations.loader import MigrationLoader
    name='0027_component_net_and_loss_policy'
    assert not (BACKEND/f'pde/migrations/{name}.py').exists()
    baseline=MigrationLoader(connection).project_state([('pde','0026_material_role_layer_correction')])
    after=ProjectState.from_apps(apps);before=after.clone()
    before.models[('pde','componentmaterialrequirement')]=baseline.models[('pde','componentmaterialrequirement')].clone()
    del before.models[('pde','materiallosspolicy')]
    changes=MigrationAutodetector(before,after,NonInteractiveMigrationQuestioner())._detect_changes()
    assert set(changes)=={'pde'} and len(changes['pde'])==1
    migration=changes['pde'][0];migration.name=name
    migration.dependencies=[('pde','0026_material_role_layer_correction')]
    for op in migration.operations:
        assert (getattr(op,'model_name',None) or getattr(op,'name','')).lower() in {'componentmaterialrequirement','materiallosspolicy'}
    writer=MigrationWriter(migration)
    (BACKEND/'pde/migrations'/writer.filename).write_text(writer.as_string(),encoding='utf-8')
    call_command('migrate','pde',name,interactive=False,verbosity=1)
    call_command('check',verbosity=1)
    save('ISOLATED_MIGRATION.json',{'status':'PASS','migration':name,'operations':[op.describe() for op in migration.operations],
        'productionMigration':0,'database':str(ISO/'isolated.sqlite3'),
        'legacyBackfill':'Existing requirements default UNKNOWN/null; only 59 proven source edges receive isolated source-mode/net/trace/policy fields during replay; no guessed data migration'})

def replay():
    bootstrap()
    from django.db import transaction,connection
    from django.core import serializers
    from pde.models import MaterialLossPolicy,ComponentMaterialRequirement,EngineeringBreakdownItem
    from pde.material_configuration_service import MaterialConfigurationService
    from masterdata.models import UnitOfMeasure
    from semi_finished_model_closure_serialization import encoder
    old=read('ISOLATED_REPLAY.json',OLD);trace=read('ROOM_DOOR_EDGE_SEGMENT_TRACE.json');policies={}
    with transaction.atomic():
        assert MaterialLossPolicy.objects.count()==0 and ComponentMaterialRequirement.objects.count()==59
        before=json.loads(serializers.serialize('json',ComponentMaterialRequirement.objects.order_by('pk'),cls=encoder()))
        for source,name in [('STRUCTURE_EDGE_SOURCE','三合一组件封边'),('EDGE_BANDING_25_SOURCE','封边皮25'),('EDGE_BANDING_50_SOURCE','封边皮50')]:
            policy=MaterialLossPolicy(company_id=1,code=source,requirement_kind='edge_banding',source_material_identity=source,
                method='PER_EDGE_ALLOWANCE',source={'provenance':'USER_METHOD_DECISION_PARAMETER_PENDING','name':name,'instructionSha256':sha(INSTRUCTION)})
            policy.full_clean();policy.save();policies[source]=policy
        for requirement in ComponentMaterialRequirement.objects.all():
            component=requirement.breakdown_item;edge=component.attributes['edgePreview']
            requirement.requirement_source_mode='STRUCTURE_CALCULATED'
            requirement.net_quantity=Decimal(edge['netLengthM']);requirement.loss_policy=policies['STRUCTURE_EDGE_SOURCE']
            requirement.edge_trace_status='READY'
            requirement.edge_segment_trace=[{'segmentNo':i+1,'semantic':edge['edgeLabels'][i],
                'netSegmentLengthMm':str(length),'quantityMultiplier':edge['componentQuantity']}
                for i,length in enumerate(edge['edgeDimensionsMm'])]
            requirement.full_clean();requirement.save(update_fields=['requirement_source_mode','net_quantity','loss_policy','edge_trace_status','edge_segment_trace'])
        metre=UnitOfMeasure.objects.get(company_id=1,code='m',is_active=True)
        new=[]
        for edge in trace['rows']:
            component=EngineeringBreakdownItem.objects.get(source_binding__source_sheet='房门单',source_binding__source_row=edge['row'])
            requirement=ComponentMaterialRequirement(breakdown_item=component,line_no=1 if edge['sourceType']=='EDGE_BANDING_25_SOURCE' else 2,
                requirement_kind='edge_banding',requirement_source_mode='DIRECT_CALCULATED',quantity_mode='CALCULATED',
                quantity_basis='ORDER_TOTAL',net_quantity=Decimal(edge['netLengthM']),uom=metre,uom_status='confirmed',source_uom_text='m',
                edge_segment_trace=edge['segments'],edge_trace_status='READY',loss_policy=policies[edge['sourceType']],
                identity_status='unresolved',unresolved_requirement={'sourceIdentity':edge['sourceName'],'specification':None},
                source_lineage={'scope':'ISOLATED_REPLAY','sourceType':edge['sourceType'],'directNetEvidence':edge,
                    'sourceSha256':edge['sourceSha256'],'instructionSha256':sha(INSTRUCTION)})
            requirement.full_clean();requirement.save();new.append(MaterialConfigurationService.component_edge_preview(requirement))
        requirements=list(ComponentMaterialRequirement.objects.order_by('pk'))
        assert len(requirements)==75 and len(new)==16
        assert all(r.quantity is None and r.gross_quantity is None and r.total_allowance is None and r.per_edge_allowance_mm is None for r in requirements)
        after=json.loads(serializers.serialize('json',requirements[:59],cls=encoder()))
        allowed={'requirement_source_mode','net_quantity','loss_policy','edge_trace_status','edge_segment_trace'}
        assert [{**o,'fields':{k:v for k,v in o['fields'].items() if k not in allowed}} for o in before]==[{**o,'fields':{k:v for k,v in o['fields'].items() if k not in allowed}} for o in after]
        tri=[MaterialConfigurationService.component_edge_preview(r) for r in requirements[:59]]
        assert sum(Decimal(r['netLengthM']) for r in tri)==Decimal('296.062')
        with connection.cursor() as cur:cur.execute('PRAGMA foreign_key_check');assert not cur.fetchall()
        save('TARGET_REQUIREMENT_FIXTURE.json',json.loads(serializers.serialize('json',list(policies.values())+requirements,cls=encoder())))
        report={'schemaVersion':'PCE-ROOM-DOOR-NET-LOSS-ISOLATED-1','scope':'ISOLATED_REPLAY_NOT_PRODUCTION',
            'status':'PASS','userDecisionSha256':sha(INSTRUCTION),'previousReplaySha256':sha(OLD/'ISOLATED_REPLAY.json'),
            'formalInputFingerprint':old['formalInputFingerprint'],'sourceBundleSha256':old['sourceBundleSha256'],
            'summary':trace['summary'],'roomDoorRequirements':new,'visibleFacts':trace['visibleFacts'],
            'policies':json.loads(serializers.serialize('json',policies.values(),cls=encoder())),
            'threeInOneRequirements':tri,'threeInOneOriginalFactsPreserved':True,'productionBusinessWrite':0,
            'threeLayerUserValidated':True,'targetedUserRevalidation':'PENDING','domainRuleFormalization':'NOT_ENTERED'}
        save('ISOLATED_REPLAY.json',report)
    print(json.dumps({'status':'PASS','requirements':75,'newDoorRequirements':16,'policiesParameterPending':3,'summary':trace['summary']},ensure_ascii=False))
if __name__=='__main__':{'migrate':migrate,'replay':replay}[sys.argv[1]]()

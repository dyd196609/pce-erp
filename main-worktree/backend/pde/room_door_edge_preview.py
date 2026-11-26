"""Sealed, scoped source preview. No formal requirement or loss-policy writes."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json

EVIDENCE_PATH=Path(__file__).resolve().parents[2]/'docs/evidence/room_door_edge_20260909/ISOLATED_REPLAY.json'
EVIDENCE_SHA='4AFF0A95B6C810218FFF09415F592EE2170F6EE40AADF155ECC058B73F907967'

def load_evidence():
    raw=EVIDENCE_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest().upper()!=EVIDENCE_SHA:raise ValueError('ROOM_DOOR_EVIDENCE_INTEGRITY_FAILED')
    e=json.loads(raw)
    if e.get('schemaVersion')!='PCE-ROOM-DOOR-NET-LOSS-ISOLATED-1' or e.get('scope')!='ISOLATED_REPLAY_NOT_PRODUCTION':
        raise ValueError('ROOM_DOOR_EVIDENCE_SCHEMA_FAILED')
    return e

def apply_room_door(projection,evidence=None):
    data=deepcopy(projection);e=load_evidence() if evidence is None else deepcopy(evidence)
    if e['previousReplaySha256']!=data['isolationEvidence']['sha256']:raise ValueError('ROOM_DOOR_BASELINE_DRIFT')
    target=next(c for c in data['configurations'] if c['sourceCode']=='QSFB4601001')
    layer=target['layerPreview'];components=layer['components'];requirements=e['roomDoorRequirements']
    if len(components)!=8 or len(requirements)!=16:raise ValueError('ROOM_DOOR_SCOPE_DRIFT')
    for c in data['configurations']:
        if c['userValidated']:
            c['roleLayerUserValidated']=True
            c['layerUserValidationLabel']='三层模型已人工确认并冻结'
    for component in components:
        visible=next(v for v in layer['veneerRows'] if v['row']==component['row'])
        frozen=next(v for v in e['visibleFacts'] if v['row']==component['row'])
        if any(visible.get(k)!=v for k,v in frozen.items()):raise ValueError('ROOM_DOOR_VISIBLE_FACT_DRIFT')
        component['visibleAreaFact']=visible # Exactly the same source-derived object as veneer.
        component['edgeRequirements']=[r for r in requirements if r['row']==component['row']]
        if {r['sourceType'] for r in component['edgeRequirements']}!={'EDGE_BANDING_25_SOURCE','EDGE_BANDING_50_SOURCE'}:
            raise ValueError('ROOM_DOOR_EDGE_IDENTITY_DRIFT')
        if any(r['componentId']!=component['componentId'] or r['sourceBindingId']!=component['sourceBindingId'] for r in component['edgeRequirements']):
            raise ValueError('ROOM_DOOR_COMPONENT_OWNER_DRIFT')
    layer['roomDoorRequirements']=requirements
    layer['roomDoorSummary']=e['summary']
    layer['lossPolicies']=[p for p in e['policies'] if p['fields']['source_material_identity']!='STRUCTURE_EDGE_SOURCE']
    target['targetedUserRevalidation']='PENDING'
    data['summary'].update(threeLayerUserValidated=True,layerUserManualValidation='USER_VALIDATED_FROZEN',
        roomDoorManualRevalidation='PENDING',roomDoorSourceStatus='REMEDIATED',roomDoorVisiblePass=8,
        roomDoorVisibleTotalM2=e['summary']['visibleAreaTotalM2'],roomDoorEdge25NetTotalM=e['summary']['edge25NetTotalM'],
        roomDoorEdge50NetTotalM=e['summary']['edge50NetTotalM'],roomDoorEdge25NetPass=8,roomDoorEdge50NetPass=8,
        roomDoorEdgeSegmentCount=e['summary']['physicalEdgeCount'],roomDoorGrossQuantity=None,
        pendingEdgeRequirementCount=75,roomDoorPendingEdgeRequirementCount=16,roomDoorLossMethod='PER_EDGE_ALLOWANCE',roomDoorLossParameter=None)
    data['roleLayerSummary'].update(userManualValidation='USER_VALIDATED_FROZEN',userManualValidationLabel='三层模型已人工确认；仅房门6项待复验',
        pendingEdgeRequirementCount=75,roomDoor=e['summary'])
    data['boundaries'].update(roleLayerUserValidated=True,roomDoorUserRevalidated=False)
    data['roomDoorEvidence']={'sha256':EVIDENCE_SHA,'userDecisionSha256':e['userDecisionSha256'],
        'status':'ISOLATED_PREVIEW_NOT_PRODUCTION','sourceMode':'DIRECT_CALCULATED','lossPolicyProductionCount':0}
    data['isolationEvidence']['statusLabel']='三层模型已人工确认；房门净量与逐边损耗隔离预览待定向复验，生产未应用'
    data['version']='PCE-SEMI-FINISHED-CONFIGURATION-PREVIEW-4'
    return data

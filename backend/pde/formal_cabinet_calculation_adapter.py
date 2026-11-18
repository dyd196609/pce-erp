"""Approved explicit cabinet parts -> existing THREE_IN_ONE Decimal engine."""
import json
from decimal import Decimal
from .engineering_calculation_service import EngineeringCalculationError
CONTRACT='CABINET-PARTS-V1'
PRODUCTION_CONTRACT='CABINET-PARTS-V1'

def fail(message): raise EngineeringCalculationError('CABINET_INPUT_INVALID',message)

def normalize(value, frozen=False):
    from .native_design_calculation_adapter import _number
    from .calculation_batch_reuse import EDGE_BRANCHES
    from .engineering_condition_options import visible_condition_multiplier
    allowed={'contractVersion','ruleFamily','quantityBasis','components','provenance'}|({'unitProofs'} if frozen else set())
    if not isinstance(value,dict) or set(value)-allowed or value.get('contractVersion')!=CONTRACT or value.get('ruleFamily')!='THREE_IN_ONE' or value.get('quantityBasis')!='ORDER_COMPONENT_TOTAL': fail('柜体输入契约或订单总部件数量口径不正确。')
    parts=value.get('components')
    if not isinstance(parts,list) or not 1<=len(parts)<=200: fail('须明确1至200项测试部件，不自动拆柜。')
    keys=set()
    for part in parts:
        if not isinstance(part,dict) or set(part)!={'key','name','length','width','dimensionUomId','quantity','quantityUomId','visibleCondition','edgeMethod','basis'}: fail('部件字段不完整或包含未受控内容。')
        if not all(isinstance(part[k],str) and part[k].strip() for k in ('key','name','basis')) or part['key'] in keys: fail('部件标识必须唯一，名称和拆分依据必填。')
        keys.add(part['key'])
        for field in ('length','width','quantity'): _number(part[field],field,positive=True)
        if Decimal(str(part['quantity']))!=Decimal(str(part['quantity'])).to_integral_value(): fail('部件订单总数量须为整数，不乘柜体套数。')
        if type(part['dimensionUomId']) is not int or type(part['quantityUomId']) is not int: fail('尺寸和数量单位必须明确引用。')
        if visible_condition_multiplier(part['visibleCondition']) is None or part['edgeMethod'] not in EDGE_BRANCHES: fail('见光或封边须采用已有可计算枚举。')
    proof=value.get('provenance')
    if not isinstance(proof,dict) or proof.get('classification')!='DEVELOPMENT_TEST_ASSUMPTION' or not proof.get('reason') or not proof.get('references'): fail('测试清单须保留开发测试性质、拆分假设及来源引用。')
    return json.loads(json.dumps(value,ensure_ascii=False))

def freeze(value,company_id):
    from masterdata.models import UnitOfMeasure
    from .native_design_calculation_adapter import _unit_proof
    result=normalize(value)
    targets=list(UnitOfMeasure.objects.filter(company_id=company_id,code__iexact='mm',is_active=True))
    if len(targets)!=1: fail('公司必须有唯一有效毫米单位。')
    ids={targets[0].pk}|{p[k] for p in result['components'] for k in ('dimensionUomId','quantityUomId')}
    units={u.pk:u for u in UnitOfMeasure.objects.select_related('conversion_base').filter(company_id=company_id,pk__in=ids,is_active=True)}
    if set(units)!=ids: fail('部件单位缺失、跨公司或已失效。')
    proofs={str(k):_unit_proof(u) for k,u in units.items()}
    target=proofs[str(targets[0].pk)]
    for p in result['components']:
        dim=proofs[str(p['dimensionUomId'])];qty=proofs[str(p['quantityUomId'])]
        if dim['dimension']!='length' or dim['baseId']!=target['baseId'] or qty['dimension']!='count' or Decimal(qty['factor'])!=1: fail('尺寸须可受控转换为毫米，部件数量单位须为计数基准。')
    result['unitProofs']={'targetMmId':targets[0].pk,'units':proofs}
    return result

def calculate(item,identity):
    from masterdata.models import UnitOfMeasure
    from .native_design_calculation_adapter import _unit_proof,_mm
    from .calculation_batch_reuse import evaluate_row,VERSION
    value=normalize(item.content_snapshot['revision']['designData']['calculationInputs'],frozen=True)
    proof=value.get('unitProofs') or {};units=proof.get('units') or {}
    actual={str(u.pk):_unit_proof(u) for u in UnitOfMeasure.objects.select_related('conversion_base').filter(company_id=item.baseline.company_id,pk__in=units,is_active=True)}
    if actual!=units or not units: fail('当前单位与获准冻结单位证明不一致。')
    rows=[];inputs=[];totals={}
    for p in value['components']:
        length=_mm(p['length'],p['dimensionUomId'],proof,'length');width=_mm(p['width'],p['dimensionUomId'],proof,'width')
        mapped={'ruleFamily':'THREE_IN_ONE','sourceKey':identity['sourceKey']+':component:'+p['key'],'sourceIdentity':identity,
          'inputProof':{'baselineItemId':item.pk,'contentHash':item.content_hash,'component':p,'unitProofs':proof},
          'canonicalInputs':{'J':length,'K':width,'M':p['quantity'],'N':units[str(p['quantityUomId'])]['code'],'O':p['visibleCondition'],'P':p['edgeMethod'],'H':p['name']}}
        result=evaluate_row(mapped)
        for r in result:
            r.update(componentKey=p['key'],componentName=p['name'])
            if r.get('state')=='calculated': totals[r['column']]=totals.get(r['column'],Decimal(0))+Decimal(str(r['value']))
        rows.extend(result);inputs.append({'name':p['name'],'original':p,'dimensionUnit':units[str(p['dimensionUomId'])]['code'],'quantityUnit':units[str(p['quantityUomId'])]['code'],'lengthMm':length,'widthMm':width,'quantityUsedOnce':str(p['quantity'])})
    succeeded=bool(rows) and all(r.get('state')=='calculated' for r in rows)
    return {'statusLabel':'测试数字核算成功' if succeeded else '尚不可计算','inputComplete':True,'calculationSucceeded':succeeded,
      'rows':rows,'inputs':inputs,'summary':{k:str(v.quantize(Decimal('0.000001'))) for k,v in totals.items()},
      'ruleVersion':VERSION,'quantityBasis':'订单总部件数量，仅乘一次，不乘父级套数','blockers':[],'mapping':[]}

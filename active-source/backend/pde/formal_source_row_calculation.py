"""Approved source-row design parts -> existing Decimal formulas -> formal facts.

One design object's explicit component totals become four formal saved facts;
all component inputs and computed rows remain in the provenance. No Excel cells
or formal source identities are invented, and no TEST approval is consumed.
"""
from .engineering_calculation_service import EngineeringCalculationError

def preview(design_inputs):
    from .models import OrderEngineeringBaselineItem
    from .baseline_usage_service import validate_baseline
    from .baseline_source_identity import resolve_baseline_source_identity
    from .formal_cabinet_calculation_adapter import calculate,PRODUCTION_CONTRACT
    from .design_revision_approval_service import digest
    result=[];proofs=[]
    for row in design_inputs:
        item=OrderEngineeringBaselineItem.objects.select_related('baseline','design_revision','source_record','source_attribute','design_item__sales_order_item__sales_order').get(pk=row['baselineItemId'])
        validate_baseline(item.baseline,purpose='PRODUCTION_USE')
        identity=resolve_baseline_source_identity(item)
        value=item.content_snapshot['revision']['designData']['calculationInputs']
        if (identity['sourceKey']!=row['sourceKey'] or value.get('contractVersion')!=PRODUCTION_CONTRACT
            or item.content_hash!=row['baselineContentHash']):
            raise EngineeringCalculationError('FORMAL_SOURCE_ROW_INPUT_UNPROVEN','正式来源行、输入合同或准确基线Hash不一致。')
        computed=calculate(item,identity)
        if not computed['calculationSucceeded']:
            raise EngineeringCalculationError('FORMAL_SOURCE_ROW_CALCULATION_FAILED','获准部件输入未通过原Decimal规则计算。')
        for column,total in computed['summary'].items():
            parts=[r for r in computed['rows'] if r['column']==column]
            units={r['unit'] for r in parts}
            if len(units)!=1:raise EngineeringCalculationError('FORMAL_SOURCE_ROW_UNIT_MISMATCH','部件合计不能跨单位。')
            result.append({'sourceKey':identity['sourceKey'],'state':'calculated','column':column,
                'project':parts[0]['project'],'unit':next(iter(units)),'value':total,
                'expression':'SUM_OF_SAVED_EXPLICIT_COMPONENT_FORMULA_RESULTS','precision':6,'rounding':'ROUND_HALF_UP',
                'inputs':{'componentInputs':computed['inputs'],'componentResults':parts,'quantityBasis':'ORDER_COMPONENT_TOTAL'},
                'sourceCell':None,'sourceFormula':None,'resultScope':'original','sourceIdentity':identity,
                'expected':None,'difference':None,'matched':None,'statusLabel':'获准明确部件净量合计（保留各部件结果）'})
        proofs.append({'sourceKey':identity['sourceKey'],'contentHash':item.content_hash,'ruleVersion':computed['ruleVersion'],'inputs':computed['inputs']})
    return {'rows':result,'blockers':[],'batchFingerprint':digest({'proofs':proofs,'rows':result}),
        'inputRevisionHash':digest(proofs),'resultPositionCount':len(result),'factSource':'server'}

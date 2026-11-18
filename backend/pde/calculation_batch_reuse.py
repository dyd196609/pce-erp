from pde.baseline_usage_service import production_baselines, production_status
"""Read-only, non-production connection of approved historical engineering methods.

No new calculator: all numeric expressions go through engineering_rule_foundation.
Frozen source values are independent comparisons, never an output's own input.
Reference families not yet mapped to approved semantics remain inspectable only.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import hashlib
import json
import re
import uuid

from django.db.models import Count, Q

from .engineering_rule_foundation import evaluate_specification, EngineeringRuleError
from .semi_finished_configuration_preview import load_source, load_frozen_source_snapshot, cell_value, SOURCE_SHA
from .semi_finished_configuration_validation import load_evidence as role_evidence
from .room_door_edge_preview import load_evidence as door_evidence
from .engineering_work_context import normalize_draft_context, normalize_draft_row_references
from .engineering_condition_options import (
    VISIBLE_CONDITION_BY_NAME,
    visible_condition_multiplier,
)

ROOT = Path(__file__).resolve().parents[2]
VERSION = 'APPROVED-SOURCE-NET-ADAPTER-V2-LINEAR-CONTINUATION'
LINEAR_RULE_VERSION = 'SOURCE-LINEAR-CONTINUATION-V1'
ACCEPTED_DIFFERENCE_PROFILE_PATH = ROOT / 'docs/governance/evidence/PCE_SO202609180003_ENGINEERING_ACCEPTED_DIFFERENCES_V1.json'
CUT_LENGTH_TIERS_MM = tuple(Decimal(value) for value in ('2440', '2600', '2800', '3050', '3600'))
LABELS = {'J':'原始高度/长度', 'K':'原始宽度', 'L':'原始厚度/套深', 'M':'原始数量',
          'N':'门套高度', 'O':'门套宽度', 'P':'门套深度', 'Q':'门套数量',
          'R':'门扇高度', 'S':'门扇宽度', 'U':'门扇数量'}
EDGE_BRANCHES = {'一长':(1,0),'一宽':(0,1),'两长':(2,0),'两宽':(0,2),'一长一宽':(1,1),
                 '一长两宽':(1,2),'两长一宽':(2,1),'四边':(2,2),'白坯':(0,0)}
# Business catalogue is deliberately distinct from formula-family/technical output count.
CAPABILITIES = [
 ('dimensions','工程尺寸与尺寸派生','原始尺寸/结构→门套、门扇尺寸','A','当前正式服务及已确认来源', 'backend/pde/engineering_calculation_service.py'),
 ('quantity','部件数量及父项数量传播','单件/父项/订单总量，只乘一次','B','当前核心及历史来源方法','backend/pde/engineering_calculation_service.py'),
 ('net_area','部件工程净面积','长×宽×数量；不是原板采购量','B','已实现参考/来源方法','scripts/excel_parity/recovery_semantics.py:net_area'),
 ('visible','见光面积与木皮净量依据','单/双/白坯或门扇+门套见光→m²','B','已人工确认；采购身份独立','scripts/semi_finished_role_layer_sources.py'),
 ('edge','结构封边净长度','逐长/宽边×部件数量→m','B','已确认来源分支','scripts/semi_finished_role_layer_sources.py'),
 ('edge25','封边皮25净长度','门套尺寸及数量→m；25不是已确认规格','B','房门8行已验证，单行人工复核通过','scripts/room_door_edge_sources.py'),
 ('edge50','封边皮50净长度','结构分支及门套尺寸→m；真实零值保留','B','房门8行已验证，单行人工复核通过','scripts/room_door_edge_sources.py'),
 ('segments','逐边分解与部件归属','净长度→逐边来源及数量乘数','C','隔离候选已验证；本轮只读加载','backend/pde/room_door_edge_preview.py'),
 ('allowance','逐边加工预留与封边毛量','每边净长+每边预留→毛量','D','方法已确认，实际参数缺失','tools/semi-finished-model-closure/20260909-room-door/candidate/backend/pde/material_loss_policy_service.py'),
 ('loss','净量/损耗/毛量','基础净量、损耗政策分开，禁止重复加算','D','现有机制；真实损耗参数待维护','backend/pde/engineering_calculation_service.py'),
 ('aggregation','部件到来源/空间/材料角色汇总','同项目同单位汇总，不混合净/毛/采购数量','B','历史汇总机制复用','scripts/excel_parity/recovery_semantics.py'),
 ('configuration','配置角色、适用性及材料身份','配置→坯板/木皮/油漆/封边角色','C','三层配置已人工确认；生产未部署','backend/pde/semi_finished_configuration_validation.py'),
 ('stock','原板选料与规格约束','材料族允许成员+精确厚度+规格/方向','D','旧候选否定后已有受控参考；允许集缺失','scripts/excel_parity/recovery_semantics.py:resolve'),
 ('legacy_stock','被否定的旧36类选板候选','固定长度分档与真实材料语义不等价','F','历史保留，禁止恢复为正式算法','docs/evidence/NATIVE_EXCEL_GOLDEN_FINAL_CONSOLIDATED_20260909_NATIVE_R5.md'),
 ('requirements','需求/选料/结果/需求槽四类模型','已有历史契约及隔离恢复候选','C','未加载不等于未开发；不新增模型迁移','tools/semi-finished-model-closure/20260909/candidate/backend/pde/models.py'),
 ('hardware','五金、玻璃及其他外购构成','复用结构BOM固定构成和数量方式','D','非木制角色保留，当前来源未齐备正式构成','backend/pde/models.py:BOMItem'),
 ('bom','订单BOM草案、版本及追溯','经批准物料需求→现有BOM版本','A','当前服务存在；案例无材料需求不能生成','backend/pde/engineering_calculation_service.py:OrderEngineeringClosureService'),
 ('operations','工序工程量及产能接口','工程量/单位/来源/工艺版本；不是工时','D','工程量输出机制已存在；具体工艺事实不足','backend/pde/models.py:EngineeringOperationRequirement'),
 ('linear_components','横竖线条净长、开料长及条数','房门线条分支、加长及数量→线条工程量','B','六个未损坏来源公式族已接入非生产批量适配；不发布为正式损耗或材料政策','backend/pde/calculation_batch_reuse.py'),
 ('source_context','订单、客户、颜色和工艺来源字段','原来源查表/字段派生，不是材料耗用算法','C','参考登记保留；当前来源只读展示，不伪造正式订单关联','scripts/excel_parity/generated_reference.py'),
 ('reference_summary','来源材料汇总、领用量及计划参考','原表汇总与系数不直接成为正式损耗或产能','D','参考实现存在，正式政策/下游合同未齐备','scripts/excel_parity/generated_reference.py'),
 ('unresolved_reference','语义待核对及损坏来源公式','保留具体公式族、依赖和损坏证据','D','不能将参考技术一致或损坏输出视为业务成功','docs/evidence/excel_formula_parity/FORMULA_FAMILY_INVENTORY.json'),
]


def authorize(user, action_code='production.engineering.calculation.view'):
    from django.db import connections
    from .acceptance_isolation import verify_acceptance_connections
    from .engineering_calculation_service import EngineeringCalculationService, EngineeringCalculationError
    try:
        isolation = verify_acceptance_connections({a: connections[a].settings_dict for a in connections})
    except ValueError as exc:
        raise EngineeringCalculationError('NON_PRODUCTION_ISOLATION_REQUIRED', '未证明全部连接指向持久隔离验收库，已停止批量试算。', {'reason': str(exc)})
    EngineeringCalculationService._authorize(user=user, action_code=action_code, company_id=user.company_id)
    return isolation


def verify_read_isolation():
    """Verify the governed acceptance runtime without requiring execute permission.

    The catalogue and persisted source snapshots are read-only, company-scoped
    page facts.  Keeping them behind the calculation execute/view action made a
    legitimate PDE page reader receive 403 before the existing 71-row source
    could be restored.  Mutating and ad-hoc execution paths still call
    ``authorize`` with their explicit action codes.
    """
    from django.db import connections
    from .acceptance_isolation import verify_acceptance_connections
    from .engineering_calculation_service import EngineeringCalculationError
    try:
        return verify_acceptance_connections({a: connections[a].settings_dict for a in connections})
    except ValueError as exc:
        raise EngineeringCalculationError(
            'NON_PRODUCTION_ISOLATION_REQUIRED',
            '未证明全部连接指向持久隔离验收库，已停止读取工程来源成果。',
            {'reason': str(exc)},
        )


def authorize_read(user):
    """Authorize the business reader independently from runtime isolation.

    A valid non-production database proves only environment safety.  It never
    grants a user permission to view another company's engineering sources.
    """
    from .engineering_calculation_service import EngineeringCalculationService
    return EngineeringCalculationService._authorize(
        user=user,
        action_code='production.engineering.calculation.view',
        company_id=user.company_id,
    )


def family_catalog():
    path = ROOT/'docs/evidence/excel_formula_parity/FORMULA_FAMILY_INVENTORY.json'
    inv = json.loads(path.read_text(encoding='utf-8-sig'))
    return [{'id': f['family_id'], 'name': f.get('semantic_name') or f['semantic_output'],
             'sheet': f['sheet'], 'formula': f['source_formula'], 'cells': f['source_cells'],
             'inputDependencies': f['input_dependencies'], 'function': f.get('generated_reference_function'),
             'status': '来源损坏/旧候选待裁决，不执行' if f['broken'] else '历史参考实现；技术核对不代替业务批准',
             'broken': f['broken']} for f in inv['families']]


def source_rows(source):
    rows=[]
    for row in source['realRows']:
        tri=row['sheet']=='三合一生产单'
        fields={'J':'部件长度' if tri else '门洞高度','K':'部件宽度' if tri else '门洞宽度',
                'L':'板材匹配厚度' if tri else '来源洞深','M':'来源数量'}
        if tri: fields.update(O='见光条件',P='封边方式')
        else: fields.update(H='房门结构',I='油漆工艺',AO='横加',AP='竖加',AZ='线条单双')
        business_inputs=[{'name':name,'cell':row['cells'].get(f"{col}{row['row']}",{}).get('sourceCell',f"{col}{row['row']}"),
                          'adapterSlot':col,'rawValue':cell_value(row,col),
                          'unit':'mm' if col in {'J','K','L','AO','AP'} else cell_value(row,'N') if col=='M' and tri else None,
                          'sourceFormula':row['cells'].get(f"{col}{row['row']}",{}).get('formula'),
                          'sourceValueType':'来源派生值' if row['cells'].get(f"{col}{row['row']}",{}).get('formula') else '来源原始值'}
                         for col,name in fields.items()]
        rows.append({'key': f"{row['sheet']}:{row['row']}", 'sheet':row['sheet'], 'row':row['row'],
                     'space':cell_value(row,'F'), 'product':cell_value(row,'E'),
                     'component':cell_value(row,'G' if row['sheet']=='三合一生产单' else 'H'),
                     'configuration':cell_value(row,'B'), 'stableOrderLink':False,
                     'inputs':row['cells'],'businessInputs':business_inputs})
    return rows


def catalog(*, workbook_source_context=None):
    # The catalogue is a read, never the admission proof for a new calculation.
    source = workbook_source_context['sourceData'] if workbook_source_context is not None else load_frozen_source_snapshot()
    roles=role_evidence()
    doors=door_evidence()
    capabilities=[]
    for row in CAPABILITIES:
        item=dict(zip(('id','name','meaning','handling','implementation','code'), row))
        item.update(pageConnection='原页批量结果与过程' if row[3]=='B' else '原页既有办理入口' if row[3]=='A' else '原页历史详情/集中缺口',
                    runtimeStatus='现行服务' if row[3]=='A' else '非生产只读适配' if row[3]=='B' else '参考/隔离候选，未正式放行',
                    verification='适配回归与来源独立对账，实际运行记录另列' if row[3]=='B' else '现有订单闭环回归，实际运行记录另列' if row[3]=='A' else '历史参考/隔离候选测试与当前缺口分别记录',
                    manualConfirmation='沿用历史已确认业务含义；本轮整体页面体验未完成',
                    treatment='保留，不重复开发' if row[3]=='A' else '连接原方法，不另建计算核心' if row[3]=='B' else '不恢复被否定的选板算法' if row[3]=='F' else '保留原成果，展示已有值与缺口')
        capabilities.append(item)
    return {'version':VERSION, 'sourceSha256':workbook_source_context['proof']['workbookSha256'] if workbook_source_context is not None else SOURCE_SHA,
            'sourceReadMode': 'FORMAL_WORKBOOK_VERSION' if workbook_source_context is not None else 'HISTORICAL_FROZEN_SNAPSHOT',
            'workbookSource': deepcopy(workbook_source_context['proof']) if workbook_source_context is not None else None,
            'formalExecutionAdmitted': False, 'sources':source_rows(source),
            'capabilities':capabilities,
            'families':family_catalog(), 'sourceFiles':[{k:v for k,v in x.items() if k!='path'} for x in source['sourceFiles']],
            'history':{'label':'历史只读结果（2026-09-09隔离回放，非本次重新计算）',
                       'components':roles['components'], 'board':roles['boardPreview'],
                       'veneer':roles['veneerPreview'], 'edges':roles['edgeRequirements'],
                       'roomDoor':doors['roomDoorRequirements'], 'roomDoorSummary':doors['summary'],
                       'businessConfirmation':'已人工确认并冻结；不重复要求单项截图'},
            'gaps':[
                {'key':'identity','name':'采购身份及材料适用集合','reason':'木皮、封边材料与材料族允许采购成员未唯一建立；25/50不推定规格。'},
                {'key':'parameters','name':'预留、损耗与真实耗用量','reason':'逐边预留方法已确认，实际每边参数仍空；净面积/净长度不能冒充采购量。'},
                {'key':'source','name':'工程来源条件','reason':'缺少见光/封边条件的行单独提示；真实零值与缺失严格分开。'},
                {'key':'schema','name':'历史模型运行连接','reason':'四类模型及三层配置有隔离候选，当前未部署；本轮只读复用，不执行迁移。'},
                {'key':'order','name':'正式订单与BOM','reason':'来源案例无正式订单稳定键，当前无经批准材料需求，不生成空或伪完整BOM。'},
                {'key':'external','name':'五金、玻璃及工序工程量','reason':'既有BOM角色/数量机制保留；当前来源的完整固定构成及工艺输入不足。'},
            ], 'businessWriteSideEffectCount':0}


def _rule_value(row, column):
    if 'canonicalInputs' in row:
        return row['canonicalInputs'].get(column)
    return cell_value(row, column)


def _source_cell(row, column):
    return None if 'canonicalInputs' in row else f"{column}{row['row']}"


def _source_reference(row, column):
    return (f"{row['sourceKey']}:output:{column}" if 'canonicalInputs' in row
            else f"{row['sheet']}!{column}{row['row']}")


def evaluate_row(row):
    """Connect previously approved finite source branches to the existing unit-safe core."""
    tri=row.get('ruleFamily')=='THREE_IN_ONE' if 'canonicalInputs' in row else row['sheet']=='三合一生产单'
    v=lambda c: _rule_value(row,c)
    pool={c:{'value':str(v(c)) if isinstance(v(c),(int,float)) and not isinstance(v(c),bool) else v(c),
             'unit':'mm' if c in 'JKL' else (v('N') if tri else None),
             'unitDimension':'length' if c in 'JKL' else 'dimensionless'} for c in 'JKLM'}
    specs=[]
    gap_reasons={}
    def add(col,name,expression,dimension,unit):
        specs.append((col,name,expression,dimension,unit))
    if tri:
        add('quantity','部件数量','M','dimensionless',v('N'))
        add('S','部件工程净面积','J * K * M / 1000000','area','m2')
        visible_multiplier = visible_condition_multiplier(v('O'))
        if visible_multiplier is not None:
            count = visible_multiplier
            add('Q','见光面积',f'J * K * M * {count} / 1000000','area','m2')
        else:
            add('Q','见光面积',None,'area','m2')
        if v('P') in EDGE_BRANCHES:
            nl,nw=EDGE_BRANCHES[v('P')]
            add('R','结构封边净长度',f'(J * {nl} + K * {nw}) * M / 1000','length','m')
        else:
            add('R','结构封边净长度',None,'length','m')
    else:
        role=v('H')
        if role not in {'单开门','单面套'}:
            return [gap_result(row,'structure','结构分支','当前分支尚未完成受控服务适配；原参考与历史分支证据保留。')]
        casing=role=='单面套'
        paint_free=v('I')=='免漆'
        missing_paint=not casing and not v('I')
        add('N','门套高度','J' if casing else 'J - 10','length','mm')
        add('O','门套宽度','K' if casing else 'K - 20','length','mm')
        add('P','门套深度','L','length','mm')
        add('Q','门套数量','M','dimensionless',None)
        add('R','门扇高度',None if missing_paint else 'N * 0' if casing else f'N - {28 if paint_free else 33}','length','mm')
        add('S','门扇宽度',None if missing_paint else 'O * 0' if casing else f'O - {42 if paint_free else 52}','length','mm')
        if missing_paint: gap_reasons.update(R='缺少油漆工艺，不能选择尺寸扣减分支。', S='缺少油漆工艺，不能选择尺寸扣减分支。')
        add('U','来源部件数量','Q','dimensionless',v('V'))
        add('W','见光面积','(R * S * 2 * U + N * P * 2 * Q + O * P * Q) / 1000000','area','m2')
        add('X','门套净面积','(N * P * 2 * Q + O * P * Q) / 1000000','area','m2')
        add('Z','封边皮25净长度','(N * 4 + O * 2) * Q / 1000','length','m')
        add('AA','封边皮50净长度','N * 0' if casing else '(N * 2 + O * 2) * Q / 1000','length','m')
    results=[]
    for col,name,expression,dimension,unit in specs:
        if expression is None:
            results.append({**gap_result(row,col,name,gap_reasons.get(col,'来源未填写适用的见光/封边条件；不以零补齐。')), 'unit':unit})
            continue
        names=sorted(set(re.findall(r'\b[A-Za-z]+\b',expression)))
        if any(n not in pool or pool[n]['value'] is None or isinstance(pool[n]['value'],bool) for n in names):
            results.append({**gap_result(row,col,name,'必填原始输入或上游派生值缺失。'), 'unit':unit})
            continue
        try:
            for n in names:
                if Decimal(str(pool[n]['value'])) < 0:
                    raise EngineeringRuleError('NEGATIVE_GEOMETRY','尺寸/数量不得为负。')
            contracts=[{'canonicalName':n,'description':LABELS.get(n,n),'valueType':'decimal',
                        'unitDimension':pool[n]['unitDimension'],'unitRequired':bool(pool[n]['unit']),
                        'sourceType':'ENGINEERING_INPUT','required':True} for n in names]
            spec={'rulePackage':{'code':'APPROVED_SOURCE_NET','version':'V1'},'expression':expression,
                  'inputs':contracts, 'outputs':[{'canonicalName':'result','valueType':'decimal','unitDimension':dimension,
                   'unit':unit,'resultDomain':'DERIVED_FACT','description':name}], 'dependencies':[],
                  'decimalPrecision':28,'outputScale':6,'roundingMode':'ROUND_HALF_UP',
                  'sourceEvidence':{'reference':_source_reference(row,col)},
                  'applicability':{'sheet':row.get('sheet'),'structure':v('G' if tri else 'H')}}
            inputs={n:pool[n] for n in names}
            result=evaluate_specification(spec,inputs)
            source_cell=_source_cell(row,'M' if col=='quantity' else col)
            original=row.get('cells',{}).get(source_cell, {})
            # A published format mapping may normalize decimal inputs to text;
            # the workbook's actual typed cache remains independent comparison
            # evidence. Neither representation is used as a computed output.
            comparison_cell = row.get('cells',{}).get(_source_cell(row,'M'), {}) if col == 'quantity' else original
            expected = comparison_cell.get('rawValue', comparison_cell.get('value'))
            # Decimal output precision is explicit; original residual is also returned.
            # Frozen native/reference float residual rule remains 1e-11 (not widened).
            comparable=isinstance(expected,(int,float)) and not isinstance(expected,bool)
            actual=Decimal(result['value'])
            delta=actual-Decimal(str(expected)) if comparable else None
            match=comparable and abs(delta)<=Decimal('0.00000000001')
            pool[col]={'value':result['value'],'unit':unit,'unitDimension':dimension}
            confirmed_changes = row.get('_confirmedInputChanges') if isinstance(row.get('_confirmedInputChanges'), dict) else {}
            confirmed_change = confirmed_changes.get('visibleCondition') if col == 'Q' else confirmed_changes.get('edgeMode') if col == 'R' else None
            status_label = '用户确认条件已计算' if confirmed_change else '对账一致' if match else '发现差异' if comparable else '已计算，缺独立对照'
            results.append({**identity(row,col,name),'state':'calculated','statusLabel':status_label,
              'value':result['value'],'unit':unit,'expected':str(expected) if comparable else None,
              'difference':str(delta) if delta is not None else None,'matched':match,
              'expression':expression,'inputs':[{**inputs[n],'name':LABELS.get(n,n),'key':n} for n in names],
              'sourceFormula':original.get('formula'),'sourceCell':source_cell,
              'precision':28,'scale':6,'rounding':'ROUND_HALF_UP','ruleVersion':VERSION,
              'nature':'本次非生产试算；已确认业务方法，未正式发布',
              'gross':None,'allowance':None,'sourceBasis':'冻结原始来源/Native历史证据；未重跑Excel',
              'expectedResultsUsedAsInputs':False,
              **({'inputConfirmation': confirmed_change,
                   'comparisonBasis': 'USER_CONFIRMED_CURRENT_INPUT',
                   'sourceBasis': '原始工作簿对照与用户确认的当前输入分离；未覆盖原始工作簿'} if confirmed_change else {})})
        except (EngineeringRuleError, ArithmeticError, ValueError) as exc:
            results.append({**gap_result(row,col,name,getattr(exc,'message',str(exc))), 'unit':unit})
    return results


def identity(row,col,name,scope='original'):
    if 'canonicalInputs' in row:
        return {'id':f"{row['sourceKey']}:{col}", 'sourceKey':row['sourceKey'],
                'sheet':None,'row':None,'project':name,'column':col,
                'space':None,'product':None,'component':_rule_value(row,'H'),
                'configuration':None,'resultScope':scope,
                'resultScopeLabel':'原生设计工程净量' if scope=='original' else '原生设计线条续接',
                'sourceIdentity':row['sourceIdentity'],'inputProof':row['inputProof']}
    return {'id':f"{row['sheet']}:{row['row']}:{col}", 'sourceKey':f"{row['sheet']}:{row['row']}",
            'sheet':row['sheet'],'row':row['row'],'project':name,'column':col,
            'space':cell_value(row,'F'),'product':cell_value(row,'E'),
            'component':cell_value(row,'G' if row['sheet']=='三合一生产单' else 'H'),
            'configuration':cell_value(row,'B'), 'resultScope':scope,
            'resultScopeLabel':'原批量结果' if scope=='original' else '本轮线条续接'}


def gap_result(row,col,name,reason):
    return {**identity(row,col,name),'state':'missing','statusLabel':'缺少条件','reason':reason,'value':None,'unit':None,'gross':None,'allowance':None}


def _linear_gap(row, col, name, reason, *, unit=None, expression=None, family_id=None):
    source_cell=_source_cell(row,col)
    original=row.get('cells',{}).get(source_cell, {})
    return {**identity(row,col,name,'linear-continuation'), 'state':'missing', 'statusLabel':'缺少条件',
            'reason':reason, 'value':None, 'unit':unit, 'gross':None, 'allowance':None,
            'expression':expression, 'inputs':[], 'sourceFormula':original.get('formula'),
            'sourceCell':source_cell, 'precision':28, 'scale':6, 'rounding':'ROUND_HALF_UP',
            'ruleVersion':LINEAR_RULE_VERSION, 'sourceBasis':family_id,
            'nature':'本轮非生产线条续接；缺项未按0计入，未正式发布',
            'expectedResultsUsedAsInputs':False}


def _linear_value(row, col, name, expression, inputs, dimension, unit, family_id, *, process=None):
    """Evaluate one source-backed continuation without consuming its comparison result."""
    source_cell=_source_cell(row,col)
    original=row.get('cells',{}).get(source_cell, {})
    contracts=[]
    runtime_inputs={}
    display_inputs=[]
    for key, item in inputs.items():
        value=item.get('value')
        if value is None or value=='' or isinstance(value,bool):
            return _linear_gap(row,col,name,f"缺少{item['name']}；不能以0补齐。",unit=unit,expression=expression,family_id=family_id)
        try:
            numeric=Decimal(str(value))
        except (ArithmeticError, ValueError):
            return _linear_gap(row,col,name,f"{item['name']}不是有效数值。",unit=unit,expression=expression,family_id=family_id)
        if numeric < 0:
            return _linear_gap(row,col,name,f"{item['name']}不得为负。",unit=unit,expression=expression,family_id=family_id)
        input_dimension=item.get('dimension','dimensionless')
        input_unit=item.get('unit')
        contracts.append({'canonicalName':key,'description':item['name'],'valueType':'decimal',
                          'unitDimension':input_dimension,'unitRequired':bool(input_unit),
                          'sourceType':item.get('sourceType','ENGINEERING_INPUT'),'required':True})
        runtime_inputs[key]={'value':str(numeric),'unit':input_unit,'unitDimension':input_dimension}
        display_inputs.append({'key':key,'name':item['name'],'value':str(numeric),'unit':input_unit,
                               'sourceCell':item.get('sourceCell')})
    spec={'rulePackage':{'code':'SOURCE_LINEAR_CONTINUATION','version':'V1'},'expression':expression,
          'inputs':contracts,'outputs':[{'canonicalName':'result','valueType':'decimal','unitDimension':dimension,
          'unit':unit,'resultDomain':'DERIVED_FACT','description':name}], 'dependencies':[],
          'decimalPrecision':28,'outputScale':6,'roundingMode':'ROUND_HALF_UP',
          'sourceEvidence':{'reference':f"{family_id}:{_source_reference(row,col)}"},
          'applicability':{'sheet':row.get('sheet'),'structure':_rule_value(row,'H'),'nonProductionOnly':True}}
    try:
        evaluated=evaluate_specification(spec,runtime_inputs)
    except (EngineeringRuleError, ArithmeticError, ValueError) as exc:
        return _linear_gap(row,col,name,getattr(exc,'message',str(exc)),unit=unit,expression=expression,family_id=family_id)
    expected=original.get('rawValue', original.get('value'))
    comparable=isinstance(expected,(int,float)) and not isinstance(expected,bool)
    actual=Decimal(evaluated['value'])
    delta=actual-Decimal(str(expected)) if comparable else None
    matched=comparable and abs(delta)<=Decimal('0.00000000001')
    return {**identity(row,col,name,'linear-continuation'),'state':'calculated',
            'statusLabel':'对账一致' if matched else '发现差异' if comparable else '已计算，缺独立对照',
            'value':evaluated['value'],'unit':unit,'expected':str(expected) if comparable else None,
            'difference':str(delta) if delta is not None else None,'matched':matched,
            'expression':process or expression,'inputs':display_inputs,
            'sourceFormula':original.get('formula'),'sourceCell':source_cell,
            'precision':28,'scale':6,'rounding':'ROUND_HALF_UP','ruleVersion':LINEAR_RULE_VERSION,
            'nature':'本轮非生产线条续接；横加/竖加是来源工程参数，不作为批准损耗；未正式发布',
            'gross':None,'allowance':None,'sourceBasis':family_id,
            'expectedResultsUsedAsInputs':False}


def _cut_length(net_length):
    for tier in CUT_LENGTH_TIERS_MM:
        if net_length <= tier:
            return tier
    return None


def evaluate_linear_row(row):
    """Continue the six governed line-item outputs for applicable room-door rows."""
    if (row.get('ruleFamily')!='ROOM_DOOR' if 'canonicalInputs' in row else row['sheet']!='房门单'):
        return []
    v=lambda col: _rule_value(row,col)
    height_base=('J',v('J')) if v('J') not in (None,'',0) else ('N',v('N'))
    width_base=('K',v('K')) if v('K') not in (None,'',0) else ('O',v('O'))
    vertical=_linear_value(row,'AT','竖线净长','BASE_HEIGHT + VERTICAL_ADD',{
        'BASE_HEIGHT':{'name':'门洞/门套基准高度','value':height_base[1],'unit':'mm','dimension':'length','sourceCell':_source_cell(row,height_base[0])},
        'VERTICAL_ADD':{'name':'竖加','value':v('AP'),'unit':'mm','dimension':'length','sourceCell':_source_cell(row,'AP')},
    },'length','mm','FF_4412a3b79417')
    horizontal=_linear_value(row,'AU','横线净长','(BASE_WIDTH + HORIZONTAL_ADD) * 2',{
        'BASE_WIDTH':{'name':'门洞/门套基准宽度','value':width_base[1],'unit':'mm','dimension':'length','sourceCell':_source_cell(row,width_base[0])},
        'HORIZONTAL_ADD':{'name':'横加','value':v('AO'),'unit':'mm','dimension':'length','sourceCell':_source_cell(row,'AO')},
    },'length','mm','FF_56638d1b30f9')
    results=[vertical,horizontal]

    for net_result,col,name,family_id,basis_name,divisor in (
        (vertical,'AV','竖线开料长','FF_fc5f706a0412','系统竖线净长',Decimal('1')),
        (horizontal,'AX','横线开料长','FF_38be392bce2b','系统单边横线净长',Decimal('2')),
    ):
        if net_result['state']!='calculated':
            results.append(_linear_gap(row,col,name,f"{basis_name}未计算，开料档位不能选择。",unit='mm',family_id=family_id))
            continue
        basis=Decimal(net_result['value'])/divisor
        selected=_cut_length(basis)
        if selected is None:
            results.append(_linear_gap(row,col,name,f"{basis_name}{basis}mm超过当前来源方法最大档位3600mm。",unit='mm',family_id=family_id))
            continue
        results.append(_linear_value(row,col,name,'SELECTED_CUT_LENGTH',{
            'SELECTED_CUT_LENGTH':{'name':'来源方法选定开料档位','value':selected,'unit':'mm','dimension':'length','sourceType':'RULE_PARAMETER'},
        },'length','mm',family_id,process=f"按{basis_name}{basis}mm在2440/2600/2800/3050/3600mm中选择首个不小于净长的档位"))

    mode=v('AZ')
    if mode not in {'单','双'}:
        reason='线条单双缺失或不是“单/双”，条数不能使用来源公式的默认分支。'
        results.extend([_linear_gap(row,'AW','竖线条数',reason,unit='条',family_id='FF_6172b8a3a02a'),
                        _linear_gap(row,'AY','横线条数',reason,unit='条',family_id='FF_1e520fd1a320')])
        return results
    quantity=v('M')
    vertical_factor=4 if mode=='双' else 2
    vertical_count=_linear_value(row,'AW','竖线条数','LINE_FACTOR * SOURCE_QUANTITY',{
        'LINE_FACTOR':{'name':f'{mode}线竖线条数系数','value':vertical_factor,'dimension':'dimensionless','sourceType':'RULE_PARAMETER'},
        'SOURCE_QUANTITY':{'name':'来源数量（仅乘一次）','value':quantity,'dimension':'dimensionless','sourceCell':_source_cell(row,'M')},
    },'dimensionless','条','FF_6172b8a3a02a')
    results.append(vertical_count)
    if horizontal['state']!='calculated':
        results.append(_linear_gap(row,'AY','横线条数','系统横线净长未计算，不能判断单双条分支。',unit='条',family_id='FF_1e520fd1a320'))
    else:
        horizontal_factor=1 if mode=='单' or Decimal(horizontal['value'])<=Decimal('2440') else 2
        results.append(_linear_value(row,'AY','横线条数','LINE_FACTOR * SOURCE_QUANTITY',{
            'LINE_FACTOR':{'name':f'{mode}线横线条数系数','value':horizontal_factor,'dimension':'dimensionless','sourceType':'RULE_PARAMETER'},
            'SOURCE_QUANTITY':{'name':'来源数量（仅乘一次）','value':quantity,'dimension':'dimensionless','sourceCell':_source_cell(row,'M')},
        },'dimensionless','条','FF_1e520fd1a320',process='单线取1；双线按系统横线净长不大于2440mm取1，否则取2；再乘来源数量一次'))
    return results


def _draft_source_overrides(available, draft_rows):
    """Overlay only persisted O/P input changes on copied registered source rows."""
    if not isinstance(draft_rows, list):
        return available, []
    indexed = {
        f"{row.get('sourceSheet')}:{row.get('sourceRow')}": row
        for row in draft_rows if isinstance(row, dict) and row.get('sourceSheet') and row.get('sourceRow')
    }
    resolved = {}
    changes = []
    for key, source_row in available.items():
        draft_row = indexed.get(key)
        if not draft_row:
            resolved[key] = source_row
            continue
        current = deepcopy(source_row)
        row_changes = {}
        for field, column, allowed in (
            ('visibleCondition', 'O', set(VISIBLE_CONDITION_BY_NAME)),
            ('edgeMode', 'P', set(EDGE_BRANCHES)),
        ):
            after = draft_row.get(field)
            if after not in allowed:
                continue
            before = cell_value(source_row, column)
            if after == before:
                continue
            cell = f"{column}{source_row['row']}"
            current['cells'].setdefault(cell, {})['value'] = after
            change = {
                'stableRowId': draft_row.get('id'), 'sourceKey': key,
                'sheet': source_row['sheet'], 'sourceRow': source_row['row'],
                'field': field, 'sourceColumn': column,
                'before': before, 'after': after,
                'basis': 'USER_CONFIRMED_2026-09-15',
            }
            row_changes[field] = change
            changes.append(change)
        if row_changes:
            current['_confirmedInputChanges'] = row_changes
        resolved[key] = current
    return resolved, changes


def _design_source_overrides(available, design_inputs):
    """Adapt governed product-design facts to the existing calculation rows.

    The adapter changes a copied in-memory source only.  It neither mutates the
    accepted historical workbook baseline nor creates calculation records.
    """
    if not isinstance(design_inputs, list):
        return available, []
    resolved = {key: deepcopy(value) for key, value in available.items()}
    changes = []
    mapping = (
        ('designLength', 'J'), ('designWidth', 'K'),
        ('designThickness', 'L'), ('physicalQuantity', 'M'),
    )
    for item in design_inputs:
        if not isinstance(item, dict):
            continue
        key = str(item.get('sourceKey') or '')
        if key not in resolved:
            continue
        source_row = resolved[key]
        for field, column in mapping:
            after = item.get(field)
            if after in (None, ''):
                continue
            before = cell_value(source_row, column)
            cell = f"{column}{source_row['row']}"
            source_row['cells'].setdefault(cell, {})['value'] = after
            try:
                values_equal = Decimal(str(after)) == Decimal(str(before))
            except (ValueError, TypeError, ArithmeticError):
                values_equal = str(after) == str(before)
            if not values_equal:
                changes.append({
                    'designItemId': item.get('designItemId'),
                    'designItemNo': item.get('designItemNo'),
                    'sourceKey': key, 'field': field, 'sourceColumn': column,
                    'before': before, 'after': after,
                })
        if source_row['sheet'] == '三合一生产单':
            for field, column in (('visibleCondition', 'O'), ('edgeMethod', 'P')):
                after = item.get(field)
                if after in (None, ''):
                    continue
                before = cell_value(source_row, column)
                cell = f"{column}{source_row['row']}"
                source_row['cells'].setdefault(cell, {})['value'] = after
                if str(after) != str(before):
                    changes.append({
                        'designItemId': item.get('designItemId'),
                        'designItemNo': item.get('designItemNo'),
                        'sourceKey': key, 'field': field, 'sourceColumn': column,
                        'before': before, 'after': after,
                    })
    return resolved, changes


def _comparison_value_equal(left, right):
    if left is None or right is None:
        return left is right
    try:
        return Decimal(str(left)) == Decimal(str(right))
    except (ValueError, TypeError, ArithmeticError):
        return str(left) == str(right)


def _load_accepted_difference_profile(source_record, design_inputs):
    """Load the exact prior acceptance only for its original order/source/version."""
    if not ACCEPTED_DIFFERENCE_PROFILE_PATH.is_file() or not isinstance(design_inputs, list):
        return None
    profile = json.loads(ACCEPTED_DIFFERENCE_PROFILE_PATH.read_text(encoding='utf-8'))
    order_nos = {str(row.get('orderNo') or '') for row in design_inputs if isinstance(row, dict)} - {''}
    if order_nos != {profile.get('orderNo')}:
        return None
    if source_record.pk != profile.get('sourceRecordId') or source_record.source_version != profile.get('sourceVersion'):
        return None
    report_path = ROOT / str(profile.get('formalReportPath') or '')
    if not report_path.is_file():
        return None
    return profile


def _comparison_summary(rows):
    classifications = Counter(row.get('comparisonClassification') for row in rows)
    return {
        'total': len(rows),
        'numeric': sum(row.get('state') == 'calculated' and row.get('value') is not None for row in rows),
        'consistent': classifications['INDEPENDENT_COMPARISON_CONSISTENT'],
        'noIndependentComparison': classifications['NO_INDEPENDENT_COMPARISON'],
        'confirmedDesignChangeDifferences': classifications['SAME_CONFIRMED_DESIGN_CHANGE'],
        'unexplainedDifferences': classifications['NEW_UNEXPLAINED_DIFFERENCE'],
        'missing': classifications['MISSING_CONDITION'],
        'notApplicable': sum(row.get('state') == 'not_applicable' for row in rows),
        'errors': classifications['NEW_UNEXPLAINED_DIFFERENCE'] + sum(row.get('state') == 'error' for row in rows),
        'closureTotal': sum(classifications[key] for key in (
            'INDEPENDENT_COMPARISON_CONSISTENT', 'NO_INDEPENDENT_COMPARISON',
            'SAME_CONFIRMED_DESIGN_CHANGE', 'NEW_UNEXPLAINED_DIFFERENCE', 'MISSING_CONDITION',
        )),
    }


def _classify_current_comparison(rows, design_inputs, design_changes, acceptance_profile):
    """Classify current comparisons against an immutable, exact prior acceptance.

    A row is confirmed only when its identity, values, formula/rule and the
    upstream design change all match the historical evidence.  A count-only
    match never qualifies, and every non-matching comparable delta remains an
    unexplained difference.
    """
    current_inputs = {
        row.get('sourceKey'): row for row in design_inputs or []
        if isinstance(row, dict) and row.get('sourceKey')
    }
    current_changes = [row for row in design_changes or [] if isinstance(row, dict)]
    accepted_rows = {
        row.get('id'): row for row in (acceptance_profile or {}).get('confirmedDifferences', [])
        if isinstance(row, dict) and row.get('id')
    }
    matched_ids = []
    mismatched = []
    current_difference_ids = []
    for row in rows:
        if row.get('state') != 'calculated':
            row['comparisonClassification'] = 'MISSING_CONDITION'
            continue
        if row.get('expected') is None:
            row['comparisonClassification'] = 'NO_INDEPENDENT_COMPARISON'
            continue
        if row.get('matched') is True:
            row['comparisonClassification'] = 'INDEPENDENT_COMPARISON_CONSISTENT'
            continue
        row['comparisonClassification'] = 'NEW_UNEXPLAINED_DIFFERENCE'
        current_difference_ids.append(row.get('id'))
        accepted = accepted_rows.get(row.get('id'))
        if not accepted:
            continue
        design_input = current_inputs.get(row.get('sourceKey')) or {}
        accepted_change = accepted.get('designChange') or {}
        change_matches = any(
            change.get('designItemNo') == accepted.get('designItemNo')
            and change.get('sourceKey') == accepted.get('sourceKey')
            and change.get('field') == accepted_change.get('field')
            and _comparison_value_equal(change.get('before'), accepted_change.get('before'))
            and _comparison_value_equal(change.get('after'), accepted_change.get('after'))
            for change in current_changes
        )
        field_checks = {
            'designItemNo': design_input.get('designItemNo') == accepted.get('designItemNo'),
            'sourceKey': row.get('sourceKey') == accepted.get('sourceKey'),
            'project': row.get('project') == accepted.get('project'),
            'currentValue': _comparison_value_equal(row.get('value'), accepted.get('currentValue')),
            'independentValue': _comparison_value_equal(row.get('expected'), accepted.get('independentValue')),
            'difference': _comparison_value_equal(row.get('difference'), accepted.get('difference')),
            'unit': row.get('unit') == accepted.get('unit'),
            'sourceCell': row.get('sourceCell') == accepted.get('sourceCell'),
            'expression': row.get('expression') == accepted.get('expression'),
            'ruleVersion': row.get('ruleVersion') == accepted.get('ruleVersion'),
            'designChange': change_matches,
        }
        if all(field_checks.values()):
            row['comparisonClassification'] = 'SAME_CONFIRMED_DESIGN_CHANGE'
            row['statusLabel'] = '已确认设计变更差异'
            row['historicalAcceptance'] = {
                'evidenceId': acceptance_profile.get('evidenceId'),
                'formalReportPath': acceptance_profile.get('formalReportPath'),
                'acceptedAt': acceptance_profile.get('acceptedAt'),
                'acceptedBaselineNo': acceptance_profile.get('acceptedBaselineNo'),
                'designItemNo': accepted.get('designItemNo'),
                'designChange': accepted_change,
                'designChangeBasis': accepted.get('designChangeBasis'),
                'decision': 'SAME_CONFIRMED_DESIGN_CHANGE',
            }
            matched_ids.append(row.get('id'))
        else:
            mismatched.append({
                'id': row.get('id'),
                'failedChecks': sorted(key for key, value in field_checks.items() if not value),
            })
    summary = _comparison_summary(rows)
    accepted_ids = list(accepted_rows)
    missing_ids = sorted(set(accepted_ids) - set(current_difference_ids))
    new_ids = sorted(
        row.get('id') for row in rows
        if row.get('comparisonClassification') == 'NEW_UNEXPLAINED_DIFFERENCE'
    )
    accepted_counts = (acceptance_profile or {}).get('acceptedClassification') or {}
    count_match = all(summary.get(key) == accepted_counts.get(key) for key in (
        'total', 'consistent', 'noIndependentComparison',
        'confirmedDesignChangeDifferences', 'unexplainedDifferences', 'missing',
    )) if acceptance_profile else False
    exact_match = bool(acceptance_profile) and count_match and not missing_ids and not mismatched and not new_ids
    regression = {
        'statusCode': 'HISTORICAL_ACCEPTED_RESULT_MATCH' if exact_match else 'HISTORICAL_ACCEPTED_RESULT_MISMATCH',
        'statusLabel': '当前388项与历史正式验收结论逐项一致。' if exact_match else '当前结果未与历史正式验收结论完全一致；不得将未解释差异标记为已确认。',
        'match': exact_match,
        'evidenceId': (acceptance_profile or {}).get('evidenceId'),
        'formalReportPath': (acceptance_profile or {}).get('formalReportPath'),
        'acceptedBaselineNo': (acceptance_profile or {}).get('acceptedBaselineNo'),
        'acceptedClassification': accepted_counts,
        'currentClassification': summary,
        'matchedDifferenceIds': matched_ids,
        'missingAcceptedIds': missing_ids,
        'mismatchedAcceptedRows': mismatched,
        'newUnexplainedIds': new_ids,
        'databaseBusinessWrite': 0,
    }
    return summary, regression


def run_batch(keys, draft_rows=None, design_inputs=None, acceptance_profile=None, *,
              workbook_source_context=None, historical_read=False):
    from django.utils import timezone
    if workbook_source_context is not None and historical_read:
        raise ValueError('SOURCE_READ_CONTEXT_AMBIGUOUS')
    source = (workbook_source_context['sourceData'] if workbook_source_context is not None
              else load_frozen_source_snapshot() if historical_read else load_source())
    available={f"{r['sheet']}:{r['row']}":r for r in source['realRows']}
    if not isinstance(keys,list) or not keys or not all(isinstance(key,str) for key in keys) or len(keys)!=len(set(keys)) or set(keys)-set(available):
        raise ValueError('INVALID_OR_DUPLICATE_SOURCE_SCOPE')
    available, confirmed_changes = _draft_source_overrides(available, draft_rows)
    available, design_changes = _design_source_overrides(available, design_inputs)
    original_rows=[item for key in keys for item in evaluate_row(available[key])]
    linear_rows=[item for key in keys for item in evaluate_linear_row(available[key])]
    rows=original_rows+linear_rows
    comparison_summary, acceptance_regression = _classify_current_comparison(
        rows, design_inputs, design_changes, acceptance_profile,
    )
    if workbook_source_context is not None:
        from .engineering_workbook_source_service import restore_coordinates
        rows = restore_coordinates(rows, workbook_source_context)
        original_rows = [row for row in rows if row['resultScope'] == 'original']
        linear_rows = [row for row in rows if row['resultScope'] == 'linear-continuation']
    groups=defaultdict(list)
    for r in rows:
        groups[(r['resultScope'],r['resultScopeLabel'],r['sheet'],r['project'],r['unit'])].append(r)
    totals=[]
    for (result_scope,result_scope_label,sheet,project,unit),items in groups.items():
        known=[r for r in items if r['value'] is not None]
        # Dimensions themselves are not additive; expose detail instead of a meaningless total.
        additive=unit in {'m','m2','条'} or (project in {'部件数量','来源部件数量','门套数量'} and bool(unit))
        totals.append({'resultScope':result_scope,'resultScopeLabel':result_scope_label,'sheet':sheet,'project':project,'unit':unit,'known':len(known),'missing':len(items)-len(known),
                       'net':str(sum((Decimal(r['value']) for r in known),Decimal(0))) if known and additive else None,
                       'gross':None,'label':'已知净量小计' if additive else '来源未给出数量单位，暂不汇总' if not unit else '非可加尺寸，查看明细',
                       'ids':[r['id'] for r in items]})
    def segment(key,label,items):
        counts=Counter(row['statusLabel'] for row in items)
        return {'key':key,'label':label,'sourceCount':len({row['sourceKey'] for row in items}),
                'resultCount':len(items),'counts':dict(counts),'missingCount':sum(row['state']=='missing' for row in items)}
    design_snapshot_hash = hashlib.sha256(json.dumps(
        design_inputs or [], ensure_ascii=False, sort_keys=True, default=str,
    ).encode('utf-8')).hexdigest()
    input_revision_hash = hashlib.sha256(json.dumps({
        'confirmedDraftChanges': confirmed_changes,
        'designSnapshotHash': design_snapshot_hash if design_inputs is not None else None,
    }, ensure_ascii=False, sort_keys=True, default=str).encode('utf-8')).hexdigest()
    source_sha = workbook_source_context['proof']['workbookSha256'] if workbook_source_context is not None else SOURCE_SHA
    fingerprint_basis = {'source':source_sha,'keys':keys,'version':VERSION,'inputRevisionHash':input_revision_hash}
    if workbook_source_context is not None:
        fingerprint_basis['workbookSource'] = deepcopy(workbook_source_context['proof'])
    return {'version':VERSION,'completedAt':timezone.now().isoformat(),'sourceSha256':source_sha,'sourceCount':len(keys),
            'sourceReadMode': 'FORMAL_WORKBOOK_VERSION' if workbook_source_context is not None else 'HISTORICAL_FROZEN_SNAPSHOT' if historical_read else 'REGISTERED_ORIGINAL_FILES',
            'workbookSource': deepcopy(workbook_source_context['proof']) if workbook_source_context is not None else None,
            'rows':rows,'totals':totals,'counts':dict(Counter(r['statusLabel'] for r in rows)),
            'segments':[segment('original','原批量结果',original_rows),segment('linear-continuation','本轮线条续接',linear_rows)],
            'confirmedInputChanges':confirmed_changes,'confirmedInputChangeCount':len(confirmed_changes),
            'designInputChanges':design_changes,'designInputChangeCount':len(design_changes),
            'comparisonSummary':comparison_summary,
            'historicalAcceptanceRegression':acceptance_regression,
            'inputSnapshotVersion':'PRODUCT-DESIGN-CALCULATION-INPUT-V1' if design_inputs is not None else None,
            'inputSnapshotHash':design_snapshot_hash if design_inputs is not None else None,
            'inputAuthority':'ProductDesignItem/ProductDesignRevision' if design_inputs is not None else 'registered-source',
            'confirmedOutputCount':sum(row['statusLabel']=='用户确认条件已计算' for row in rows),
            'inputRevisionHash':input_revision_hash,
            'businessWriteSideEffectCount':0,'formalResultsCreated':False,'expectedResultsUsedAsInputs':False,
            'comparisonTolerance':'1e-11，沿用房门/来源原核对证据；实际差异始终显示',
            'batchFingerprint':hashlib.sha256(json.dumps(fingerprint_basis,sort_keys=True).encode()).hexdigest()}


def _calculation_input_applicability(*, source_sheet, product_category_name):
    """Describe which design fields the accepted source adapters actually use.

    The room-door adapter derives visible area and edge lengths from the door
    dimensions, structure and paint branch.  It does not consume the generic
    product-design ``visibleCondition`` or ``edgeMethod`` fields.  Three-in-one
    rows do consume both fields.  Keeping this contract next to ``evaluate_row``
    prevents the input page and work-order projection from inventing different
    applicability rules.
    """
    room_door = source_sheet == '房门单' or product_category_name == '房门'
    three_in_one = source_sheet == '三合一生产单'
    return {
        'designLength': {'classification': 'required', 'reason': '当前规则的尺寸输入。'},
        'designWidth': {'classification': 'required', 'reason': '当前规则的尺寸输入。'},
        'designThickness': {'classification': 'required', 'reason': '当前规则的尺寸输入。'},
        'visibleCondition': {
            'classification': 'not_applicable' if room_door else 'required' if three_in_one else 'undetermined',
            'reason': '房门规则由门扇与门套尺寸直接计算见光面积，不读取通用见光条件。' if room_door
            else '三合一见光面积规则直接读取该字段。' if three_in_one else '当前来源类型没有已确认的字段适用性。',
        },
        'edgeMethod': {
            'classification': 'not_applicable' if room_door else 'required' if three_in_one else 'undetermined',
            'reason': '房门规则按门套尺寸和结构分支计算封边皮25/50净长度，不读取通用封边方式。' if room_door
            else '三合一结构封边净长度规则直接读取该字段。' if three_in_one else '当前来源类型没有已确认的字段适用性。',
        },
        'hardware': {
            'classification': 'supplemental',
            'reason': '五金用于后续设计构成或材料需求；当前两个工程量规则包不读取该字段。',
        },
        'glass': {
            'classification': 'supplemental',
            'reason': '玻璃用于后续设计构成或材料需求；当前两个工程量规则包不读取该字段。',
        },
    }


def _product_design_inputs(company_id, source_record_id):
    """Build the single versioned calculation-input snapshot for one source."""
    from .models import ProductDesignItem
    items = ProductDesignItem.objects.filter(
        company_id=company_id, source_record_id=source_record_id,
    ).select_related(
        'sales_order_item__sales_order', 'physical_uom',
        'product_category', 'product_definition',
    ).prefetch_related(
        'design_revisions__design_uom', 'design_revisions__edge_method',
        'design_revisions__material', 'design_revisions__material__base_uom',
        'design_revisions__material_process_type', 'design_revisions__paint_process_type',
    ).order_by('sales_order_item__line_no', 'source_attribute_id', 'pk')
    result = []
    for item in items:
        existing = item.existing_design_data if isinstance(item.existing_design_data, dict) else {}
        revisions = list(item.design_revisions.all())
        latest = max(revisions, key=lambda value: value.revision) if revisions else None
        revision_data = latest.design_data if latest and isinstance(latest.design_data, dict) else {}
        match_results = item.match_results if isinstance(item.match_results, dict) else {}
        provenance = existing.get('provenance') if isinstance(existing.get('provenance'), dict) else {}
        sheet = str(provenance.get('sourceSheet') or '')
        source_row = provenance.get('sourceRow')
        effective = {**existing, **revision_data}
        for key, value in (
            ('designLength', latest.design_length if latest else None),
            ('designWidth', latest.design_width if latest else None),
            ('designThickness', latest.design_thickness if latest else None),
        ):
            if value is not None:
                effective[key] = value
        if latest and latest.edge_method_id:
            effective['edgeMethod'] = latest.edge_method.name
        source_material_code = str(effective.get('materialProcessCode') or '')
        source_routing_code = str(existing.get('routingProcessCode') or '')
        process_configuration_code = str(effective.get('processConfigurationCode') or source_routing_code)
        material = latest.material if latest and latest.material_id else None
        category = item.product_category
        product = item.product_definition
        sales_order = item.sales_order_item.sales_order
        is_room_door = '房门' in sheet or (category and category.name == '房门')
        source_key = f'{sheet}:{source_row}' if sheet and source_row is not None else ''
        applicability = _calculation_input_applicability(
            source_sheet=sheet, product_category_name=category.name if category else '',
        )
        required = [key for key, value in applicability.items() if value['classification'] == 'required']
        missing = [key for key in required if effective.get(key) in (None, '')]
        result.append({
            'designItemId': item.pk, 'designItemNo': item.item_no,
            'salesOrderItemId': item.sales_order_item_id,
            'orderNo': sales_order.order_no,
            'orderLineNo': item.sales_order_item.line_no,
            'projectReference': sales_order.project_reference or '',
            'sourceSheet': sheet, 'sourceRow': source_row, 'sourceKey': source_key,
            'revision': latest.revision if latest else None,
            'designLength': effective.get('designLength'),
            'designWidth': effective.get('designWidth'),
            'designThickness': effective.get('designThickness'),
            'designUom': latest.design_uom.name if latest and latest.design_uom_id else 'mm',
            'dimensionSemantics': [
                {'key': 'designLength', 'label': '门洞/门套高' if is_room_door else '设计长', 'value': effective.get('designLength')},
                {'key': 'designWidth', 'label': '门洞/门套宽' if is_room_door else '设计宽', 'value': effective.get('designWidth')},
                {'key': 'designThickness', 'label': '墙厚' if is_room_door else '部件厚', 'value': effective.get('designThickness')},
            ],
            'physicalQuantity': item.physical_quantity,
            'physicalUom': item.physical_uom_snapshot,
            'physicalUomId': item.physical_uom_id,
            'physicalUomCode': item.physical_uom.code if item.physical_uom_id else '',
            'physicalUomName': item.physical_uom.name if item.physical_uom_id else item.physical_uom_snapshot,
            'physicalUomMatchStatus': (match_results.get('physicalUom') or {}).get('status'),
            'itemName': item.item_name,
            'space': item.space_snapshot,
            'installationPosition': item.installation_position_snapshot,
            'productCategoryId': category.pk if category else None,
            'productCategoryCode': category.code if category else '',
            'productCategoryName': category.name if category else '',
            'productCode': product.product_code if product else '',
            'productName': product.product_name if product else '',
            'productSpecification': product.specification if product else '',
            'sourceMaterialCode': source_material_code,
            'materialId': material.pk if material else None,
            'materialCode': material.code if material else '',
            'materialName': material.name if material else '',
            'materialSpecification': material.specification if material else '',
            'materialMatchStatus': (match_results.get('material') or {}).get('status'),
            'materialProcessCode': latest.material_process_type.code if latest and latest.material_process_type_id else '',
            'materialProcessName': latest.material_process_type.name if latest and latest.material_process_type_id else '',
            'processConfigurationCode': process_configuration_code,
            'processConfigurationLabel': effective.get('processConfigurationLabel') or process_configuration_code,
            'sourceRoutingProcessCode': source_routing_code,
            'paintProcess': (latest.paint_process_type.name if latest and latest.paint_process_type_id else effective.get('paintProcess') or ''),
            'edgeMethod': effective.get('edgeMethod') or '',
            'visibleCondition': effective.get('visibleCondition') or '',
            'colorVersion': effective.get('finishOrColor') or '',
            'processingNote': effective.get('processingNote') or '',
            'hardware': effective.get('hardware') or '',
            'glass': effective.get('glass') or '',
            'inputAuthority': (
                f'ProductDesignRevision R{latest.revision} + 已有设计资料'
                if latest else 'ProductDesignItem 已有设计资料'
            ),
            'calculationReady': bool(source_key) and not missing,
            'missingCalculationFields': (["sourceKey"] if not source_key else []) + missing,
            'designGaps': [key for key in ('hardware', 'glass') if effective.get(key) in (None, '')],
            'fieldApplicability': applicability,
        })
    return result


def _work_order_rows(source_rows, design_inputs):
    """Project one read-only work-order view from the same product-design facts.

    This deliberately does not persist into the registered source draft.  It
    keeps imported evidence immutable while preventing the work-order page from
    falling back to older, sparsely matched draft fields.
    """
    designs = {row.get('sourceKey'): row for row in design_inputs or [] if row.get('sourceKey')}
    projected = []
    for source in source_rows or []:
        source_key = f"{source.get('sourceSheet')}:{source.get('sourceRow')}"
        design = designs.get(source_key)
        if not design:
            projected.append({
                **deepcopy(source), 'sourceKey': source_key,
                'projectionAuthority': '登记来源行（未找到关联产品设计项）',
                'remainingConfirmations': ['产品设计来源关联'],
            })
            continue
        applicability = design.get('fieldApplicability') or _calculation_input_applicability(
            source_sheet=str(design.get('sourceSheet') or ''),
            product_category_name=str(design.get('productCategoryName') or ''),
        )
        room_door = applicability.get('visibleCondition', {}).get('classification') == 'not_applicable'
        material_matched = bool(design.get('materialId'))
        source_material_code = design.get('sourceMaterialCode') or source.get('materialProcessCode') or ''
        source_unit = design.get('physicalUomName') or design.get('physicalUom') or source.get('unitName') or source.get('unit') or ''
        edge_value = design.get('edgeMethod') or ''
        visible_value = design.get('visibleCondition') or ''
        length_value = design.get('designLength') if design.get('designLength') not in (None, '') else source.get('length')
        width_value = design.get('designWidth') if design.get('designWidth') not in (None, '') else source.get('width')
        thickness_value = design.get('designThickness') if design.get('designThickness') not in (None, '') else source.get('thickness')
        dimension_semantics = [
            {'key': 'length', 'label': '门洞/门套高' if room_door else '设计长', 'value': length_value},
            {'key': 'width', 'label': '门洞/门套宽' if room_door else '设计宽', 'value': width_value},
            {'key': 'thickness', 'label': '墙厚' if room_door else '部件厚', 'value': thickness_value},
        ]
        confirmations = []
        if not material_matched:
            confirmations.append('来源材料编码尚未匹配正式材料主数据')
        if not design.get('edgeMethod') and applicability.get('edgeMethod', {}).get('classification') == 'required':
            confirmations.append('封边方式')
        if not design.get('visibleCondition') and applicability.get('visibleCondition', {}).get('classification') == 'required':
            confirmations.append('见光条件')
        if design.get('physicalUomMatchStatus') not in {'EXACT', None}:
            confirmations.append('来源单位尚未匹配正式单位主数据')
        projected.append({
            **deepcopy(source),
            'id': design.get('designItemNo') or source.get('id'),
            'sourceKey': source_key,
            'designItemId': design.get('designItemId'),
            'designItemNo': design.get('designItemNo'),
            'salesOrderItemId': design.get('salesOrderItemId'),
            'orderNo': design.get('orderNo') or '',
            'orderLineNo': design.get('orderLineNo'),
            'projectReference': design.get('projectReference') or '',
            'space': design.get('space') or source.get('space') or '',
            'installationPosition': design.get('installationPosition') or '',
            'product': design.get('productCategoryName') or source.get('product') or '',
            'productCategoryId': design.get('productCategoryId'),
            'productCategoryCode': design.get('productCategoryCode') or '',
            'productCategoryName': design.get('productCategoryName') or '',
            'component': design.get('productName') or design.get('itemName') or source.get('component') or '',
            'componentCode': design.get('productCode') or source.get('componentCode') or '',
            'quantity': design.get('physicalQuantity') if design.get('physicalQuantity') is not None else source.get('quantity'),
            'unit': source_unit,
            'unitId': design.get('physicalUomId'),
            'unitName': source_unit,
            'unitStatusLabel': '正式单位已匹配' if design.get('physicalUomMatchStatus') == 'EXACT' else '来源单位已保留，正式主数据待匹配',
            'length': length_value,
            'width': width_value,
            'thickness': thickness_value,
            'dimensionSemantics': dimension_semantics,
            'materialCode': design.get('materialCode') or source_material_code,
            'materialName': design.get('materialName') or '',
            'specification': design.get('materialSpecification') or '',
            'materialStatusLabel': '正式材料已匹配' if material_matched else ('来源材料编码已保留，正式材料待匹配' if source_material_code else '来源未提供材料身份'),
            'edgeMode': edge_value,
            'edgeStatusLabel': '本业务不适用' if applicability.get('edgeMethod', {}).get('classification') == 'not_applicable' and not edge_value else ('正式封边方式已匹配' if edge_value else '确需确认') + ('；当前核算未使用' if applicability.get('edgeMethod', {}).get('classification') == 'not_applicable' and edge_value else ''),
            'visibleCondition': visible_value,
            'visibleStatusLabel': '本业务不适用' if applicability.get('visibleCondition', {}).get('classification') == 'not_applicable' and not visible_value else ('当前设计要求已带入' if visible_value else '确需确认') + ('；当前核算未使用' if applicability.get('visibleCondition', {}).get('classification') == 'not_applicable' and visible_value else ''),
            'materialProcessCode': source_material_code,
            'routingProcessCode': design.get('processConfigurationCode') or design.get('sourceRoutingProcessCode') or source.get('routingProcessCode') or '',
            'processConfigurationLabel': design.get('processConfigurationLabel') or design.get('processConfigurationCode') or design.get('sourceRoutingProcessCode') or source.get('routingProcessCode') or '',
            'paintProcess': design.get('paintProcess') or '',
            'colorVersion': design.get('colorVersion') or '',
            'processingNote': design.get('processingNote') or source.get('processingNote') or '',
            'hardware': design.get('hardware') or '',
            'glass': design.get('glass') or '',
            'projectionAuthority': design.get('inputAuthority'),
            'remainingConfirmations': confirmations,
            'fieldApplicability': applicability,
        })
    return projected


def design_calculation_context(user, source_record_id=None, *, workbook_source_context=None):
    """Resolve the normal page from stable ProductDesignItem relationships."""
    from .models import EngineeringSourceRecord, ProductDesignItem
    candidates = ProductDesignItem.objects.filter(company_id=user.company_id)
    if workbook_source_context is not None:
        candidates = candidates.filter(source_record_id=workbook_source_context['proof']['objectSourceRecordId'])
    if source_record_id not in (None, ''):
        candidates = candidates.filter(source_record_id=source_record_id)
    source = EngineeringSourceRecord.objects.filter(
        company_id=user.company_id,
        pk__in=candidates.values('source_record_id'),
    ).annotate(design_item_count=Count('product_design_items')).order_by(
        '-design_item_count', '-updated_at', '-pk',
    ).first()
    if not source:
        raise ValueError('DESIGN_CALCULATION_CONTEXT_NOT_FOUND')
    if (workbook_source_context is not None
            and workbook_source_context['proof']['objectSourceRecordId'] != source.pk):
        raise ValueError('WORKBOOK_OBJECT_SOURCE_SCOPE_MISMATCH')
    snapshot = _draft_snapshot(source, include_design_calculation=False)
    design_inputs = _product_design_inputs(user.company_id, source.pk)
    scope = snapshot.get('registeredSourceScope') or {}
    keys = scope.get('sourceKeys') if isinstance(scope.get('sourceKeys'), list) else []
    if keys:
        acceptance_profile = _load_accepted_difference_profile(source, design_inputs)
        current = run_batch(
            keys, design_inputs=design_inputs, acceptance_profile=acceptance_profile,
            workbook_source_context=workbook_source_context,
            historical_read=workbook_source_context is None,
        )
        current['readStatusLabel'] = '当前产品设计输入核算；原核算基线独立保留'
        current['resultNature'] = 'CURRENT_PRODUCT_DESIGN_CALCULATION_PREVIEW'
        current['baselineRelationship'] = _calculation_baseline_relationship(user, snapshot)
        snapshot['currentInputCalculation'] = current
    snapshot['workbookSource'] = deepcopy(workbook_source_context['proof']) if workbook_source_context is not None else None
    snapshot['currentDesignInputs'] = design_inputs
    snapshot['workOrderRows'] = _work_order_rows(snapshot.get('rows'), design_inputs)
    snapshot['designInputReadiness'] = {
        'total': len(design_inputs),
        'calculationReady': sum(bool(row['calculationReady']) for row in design_inputs),
        'calculationBlocked': sum(not row['calculationReady'] for row in design_inputs),
        'designGapItemCount': sum(bool(row['designGaps']) for row in design_inputs),
        'snapshotVersion': 'PRODUCT-DESIGN-CALCULATION-INPUT-V1',
        'snapshotHash': hashlib.sha256(json.dumps(
            design_inputs, ensure_ascii=False, sort_keys=True, default=str,
        ).encode('utf-8')).hexdigest(),
    }
    return {
        'draft': snapshot, 'sourceRecordId': source.pk,
        'resolvedBy': 'ProductDesignItem.source_record + SalesOrderItem.sales_order',
        'candidateScope': 'tenant-and-view-permission-scoped',
        'businessWriteSideEffectCount': 0,
    }


def _baseline_relationship_from_facts(facts):
    """Describe a read-time input match without inventing a persisted calculation binding."""
    candidate = facts.get('candidateBaseline') or {}
    diff = facts.get('diffFacts') or {}
    saved = {row.get('baselineId'): row for row in facts.get('savedBaselines') or []}
    compared = saved.get(diff.get('comparedBaselineId')) or {}
    common = {
        'orderNo': candidate.get('orderNo') or '',
        'inputAuthority': 'ProductDesignItem/ProductDesignRevision',
        'candidateId': candidate.get('candidateId') or '',
        'baselineId': diff.get('comparedBaselineId'),
        'baselineNo': diff.get('comparedBaselineNo') or '',
        'baselineStatusLabel': compared.get('statusLabel') or '',
        'formalCalculationBaselineBound': False,
        'relationshipNature': 'READ_TIME_INPUT_SNAPSHOT_COMPARISON',
        'bindingStatusLabel': '只读预览未创建或变更正式核算记录；数值或哈希相同不等于历史核算记录已新增基线外键。',
    }
    if not compared:
        return {
            **common,
            'statusCode': 'NO_SAVED_BASELINE',
            'statusLabel': '当前输入按产品设计读取；尚无可比较的已保存工程基线。',
            'inputMatchesConfirmedBaseline': False,
        }
    matches = diff.get('statusCode') == 'NO_CHANGE' and candidate.get('candidateId') == compared.get('candidateId')
    confirmed = compared.get('statusCode') == 'confirmed'
    if matches and confirmed:
        return {
            **common,
            'statusCode': 'MATCHES_CONFIRMED_BASELINE',
            'statusLabel': f"当前{candidate.get('designItemCount') or 0}项核算输入与已确认基线{compared.get('baselineNo') or ''}内容一致。",
            'inputMatchesConfirmedBaseline': True,
        }
    if matches:
        return {
            **common,
            'statusCode': 'MATCHES_SAVED_DRAFT',
            'statusLabel': f"当前核算输入与已保存草稿{compared.get('baselineNo') or ''}内容一致；该草稿尚未确认。",
            'inputMatchesConfirmedBaseline': False,
        }
    return {
        **common,
        'statusCode': 'CURRENT_INPUT_CHANGED_AFTER_BASELINE',
        'statusLabel': f"当前核算输入与最近基线{compared.get('baselineNo') or ''}不同；按当前产品设计读取，旧基线保持不变。",
        'inputMatchesConfirmedBaseline': False,
        'changedItemNos': diff.get('changed') or [],
        'addedItemNos': diff.get('added') or [],
        'removedItemNos': diff.get('removed') or [],
    }


def _calculation_baseline_relationship(user, snapshot):
    linked_orders = snapshot.get('linkedOrders') or []
    if len(linked_orders) != 1:
        return {
            'statusCode': 'ORDER_SCOPE_NOT_UNIQUE',
            'statusLabel': '当前来源未唯一对应一个订单，不能声明核算输入与订单工程基线的关系。',
            'inputAuthority': 'ProductDesignItem/ProductDesignRevision',
            'formalCalculationBaselineBound': False,
            'relationshipNature': 'READ_TIME_INPUT_SNAPSHOT_COMPARISON',
            'bindingStatusLabel': '只读预览未创建或变更正式核算记录。',
            'inputMatchesConfirmedBaseline': False,
        }
    from .product_version_management_service import product_version_management_facts
    facts = product_version_management_facts(
        user.company_id, linked_orders[0].get('orderNo'), user=user,
    )
    return _baseline_relationship_from_facts(facts)


def _draft_snapshot(row, include_design_calculation=True):
    payload = row.source_payload if isinstance(row.source_payload, dict) else {}
    snapshot = {
        'id': row.pk,
        'sourceNo': row.source_no,
        'sourceName': row.source_name,
        'sourceVersion': row.source_version,
        'status': row.status,
        'orderEngineeringInstanceId': payload.get('orderEngineeringInstanceId'),
        'salesOrderItemId': payload.get('salesOrderItemId'),
        'rows': payload.get('engineeringRows') if isinstance(payload.get('engineeringRows'), list) else [],
        'responsibilityAssignments': payload.get('responsibilityAssignments') if isinstance(payload.get('responsibilityAssignments'), dict) else {},
        'packagingMethod': payload.get('packagingMethod') if isinstance(payload.get('packagingMethod'), dict) else {},
        'confirmedResponsibilityFacts': payload.get('confirmedResponsibilityFacts') if isinstance(payload.get('confirmedResponsibilityFacts'), dict) else {},
        'businessOrderReference': payload.get('businessOrderReference') if isinstance(payload.get('businessOrderReference'), dict) else {},
        'calculationRequired': bool(payload.get('calculationRequired', True)),
        'calculationImpact': payload.get('calculationImpact') or 'INPUT_CHANGE',
        'revisionReason': payload.get('revisionReason') or '',
        'createdAt': row.created_at.isoformat() if row.created_at else None,
        'contentHash': row.content_hash,
        'sourceScopeKey': payload.get('sourceScopeKey'),
        'registeredSourceScope': payload.get('registeredSourceScope') if isinstance(payload.get('registeredSourceScope'), dict) else None,
        'inputConfirmation': payload.get('inputConfirmation') if isinstance(payload.get('inputConfirmation'), dict) else None,
    }
    from .models import ProductDesignItem
    linked_items = ProductDesignItem.objects.filter(
        company_id=row.company_id, source_record_id=row.pk,
    ).select_related('sales_order_item__sales_order').order_by(
        'sales_order_item__sales_order_id', 'sales_order_item__line_no', 'pk',
    )
    linked_orders = {}
    for item in linked_items:
        sales_item = item.sales_order_item
        order = sales_item.sales_order
        order_snapshot = linked_orders.setdefault(order.pk, {
            'salesOrderId': order.pk,
            'orderNo': order.order_no,
            'sourceOrderNo': order.external_source_no or '',
            'designItemCount': 0,
            'lineScopes': {},
        })
        order_snapshot['designItemCount'] += 1
        line_key = str(sales_item.pk)
        line = order_snapshot['lineScopes'].setdefault(line_key, {
            'salesOrderItemId': sales_item.pk,
            'lineNo': sales_item.line_no,
            'designItemCount': 0,
        })
        line['designItemCount'] += 1
    snapshot['linkedOrders'] = [{
        **value, 'lineScopes': list(value['lineScopes'].values()),
    } for value in linked_orders.values()]
    scope = snapshot['registeredSourceScope']
    if scope and isinstance(scope.get('sourceKeys'), list):
        try:
            # Restore the accepted historical baseline first.  Confirmed input
            # changes belong to a newer comparison and must not silently turn
            # the original 383-consistent/5-missing result into a different
            # "all filled" result.
            snapshot['sourceCalculation'] = run_batch(scope['sourceKeys'], historical_read=True)
            snapshot['sourceCalculation']['readStatusLabel'] = '原核算基线只读重现；383项一致、5项缺失，缺项未补零'
            snapshot['sourceCalculation']['resultNature'] = 'HISTORICAL_APPROVED_SOURCE_PREVIEW'
            if snapshot['rows']:
                current = run_batch(scope['sourceKeys'], snapshot['rows'], historical_read=True)
                if current.get('confirmedInputChangeCount'):
                    current['readStatusLabel'] = '当前已确认输入修订的辅助对照；不替换原核算基线'
                    current['resultNature'] = 'CURRENT_INPUT_COMPARISON_PREVIEW'
                    snapshot['currentInputCalculation'] = current
        except (ValueError, OSError) as exc:
            snapshot['sourceCalculation'] = {
                'rows': [], 'totals': [], 'sourceCount': len(scope['sourceKeys']),
                'readStatusLabel': '保存的来源范围当前无法重新读取',
                'detail': str(exc), 'formalResultsCreated': False,
            }
    if include_design_calculation and linked_items.exists():
        design_inputs = _product_design_inputs(row.company_id, row.pk)
        snapshot['currentDesignInputs'] = design_inputs
        snapshot['workOrderRows'] = _work_order_rows(snapshot.get('rows'), design_inputs)
        if scope and isinstance(scope.get('sourceKeys'), list):
            acceptance_profile = _load_accepted_difference_profile(row, design_inputs)
            current = run_batch(
                scope['sourceKeys'], design_inputs=design_inputs,
                acceptance_profile=acceptance_profile,
                historical_read=True,
            )
            current['readStatusLabel'] = '当前产品设计输入核算；原核算基线独立保留'
            current['resultNature'] = 'CURRENT_PRODUCT_DESIGN_CALCULATION_PREVIEW'
            snapshot['currentInputCalculation'] = current
    return snapshot


def _registered_source_draft_row(user, source_row):
    """Map one registered workbook row without converting formulas into raw input."""
    from masterdata.models import UnitOfMeasure
    from .models import ProductCategory

    sheet = source_row['sheet']
    row_number = source_row['row']
    tri = sheet == '三合一生产单'
    value = lambda column: cell_value(source_row, column)
    unit_code = value('N') if tri else value('V')
    unit = UnitOfMeasure.objects.filter(
        company_id=user.company_id, is_active=True,
    ).filter(Q(code=unit_code) | Q(name=unit_code)).first() if unit_code else None
    category_name = value('E')
    category = ProductCategory.objects.filter(
        company_id=user.company_id, is_active=True, name=category_name,
    ).first() if category_name else None
    evidence = {}
    for column in ('B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'V', 'AD', 'AS'):
        cell = f'{column}{row_number}'
        source_cell = source_row['cells'].get(cell, {})
        if cell not in source_row['cells']:
            continue
        evidence[column] = {
            'cell': f'{sheet}!{cell}', 'value': value(column),
            'sourceValueType': '来源派生值' if source_cell.get('formula') else '来源原始值',
            'formula': source_cell.get('formula'),
        }
    notes = []
    if value('D') not in (None, ''):
        notes.append(f"门开/方向：{value('D')}")
    if value('H') not in (None, '') and tri:
        notes.append(f"结构：{value('H')}")
    if value('I') not in (None, ''):
        notes.append(f"油漆工艺：{value('I')}")
    if value('AD') not in (None, '', False):
        notes.append(f"饰面/颜色：{value('AD')}")
    if value('AS') not in (None, '', False):
        notes.append(f"线型规格：{value('AS')}")
    if value('V') not in (None, '') and tri:
        notes.append(f"来源备注：{value('V')}")
    return {
        'id': f"SOURCE-XLSX-{sheet}-{row_number}",
        'sourceType': '三合一单' if tri else '房门单',
        'space': value('F') or '', 'product': value('E') or '',
        'component': (value('G') if tri else value('H')) or '',
        'componentCode': '', 'quantity': value('M'),
        'unitId': unit.pk if unit else None,
        'unit': unit.code if unit else unit_code or '',
        'unitName': unit.name if unit else unit_code or '',
        'length': value('J'), 'width': value('K'), 'thickness': value('L'),
        'materialCode': '', 'materialName': '', 'specification': '',
        'edgeMode': value('P') if tri else '',
        'visibleCondition': value('O') if tri else '',
        'materialProcessCode': value('B') or '',
        'routingProcessCode': value('C') or '',
        'processingNote': '；'.join(notes),
        'sourceSheet': sheet, 'sourceRow': row_number,
        'productCategoryId': category.pk if category else None,
        'productCategoryCode': category.code if category else '',
        'productCategoryName': category.name if category else category_name or '',
        'sourceEvidence': evidence,
    }


def save_registered_source_draft(user, payload):
    """Persist the governed 71-row source as one stable, unbound acceptance scope."""
    from .models import EngineeringSourceRecord

    authorize(user, action_code='production.engineering.calculation.execute')
    source = load_source()
    available = {f"{row['sheet']}:{row['row']}": row for row in source['realRows']}
    requested = payload.get('sourceKeys')
    keys = requested if isinstance(requested, list) and requested else list(available)
    if len(keys) != len(set(keys)) or set(keys) - set(available):
        raise ValueError('INVALID_OR_DUPLICATE_SOURCE_SCOPE')
    source_fingerprint = hashlib.sha256(json.dumps({
        'registeredEvidenceSha256': SOURCE_SHA, 'sourceKeys': keys,
    }, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
    source_scope_key = f"REGISTERED-XLSX-{source_fingerprint[:16].upper()}"
    for record in EngineeringSourceRecord.objects.filter(
        company_id=user.company_id,
        source_no=f'PCE-ENGINEERING-DRAFT-{user.company_id}-{source_scope_key}',
    ).order_by('-pk'):
        existing = record.source_payload if isinstance(record.source_payload, dict) else {}
        if existing.get('registeredSourceScope', {}).get('fingerprint') == source_fingerprint:
            return {
                'draft': _draft_snapshot(record), 'auditId': None,
                'runtimeIsolation': {'verified': True},
                'businessWriteSideEffectCount': 0, 'formalCalculationCreated': False,
                'previousSourceOverwritten': False, 'idempotent': True,
            }
    rows = [_registered_source_draft_row(user, available[key]) for key in keys]
    result = save_draft(user, {
        'orderEngineeringInstanceId': None, 'salesOrderItemId': None,
        'sourceName': f'真实来源批量试录 · 房门8行＋三合一63行（{len(rows)}行）',
        'sourceScopeKey': source_scope_key,
        'revisionReason': str(payload.get('revisionReason') or '登记来源71行批量接入；缺项保留；未关联正式销售订单'),
        'responsibilityAssignments': {}, 'packagingMethod': {'id': None}, 'rows': rows,
    }, registered_source_scope={
        'sourceKeys': keys, 'sourceCount': len(keys), 'fingerprint': source_fingerprint,
        'registeredEvidenceSha256': SOURCE_SHA,
        'workbookSha256': '7ED132C13F6F7B13F5805F3872EC06528D9342A8E821A4D6F3D8B571243FB122',
        'formalSalesOrderCreated': False,
        'resultNature': 'NON_PRODUCTION_ENGINEERING_QUANTITY_PREVIEW',
    })
    result['idempotent'] = False
    return result


def draft_catalog(user, order_engineering_instance_id=None, *, workbook_source_context=None):
    """Read task-scoped engineering drafts without changing formal source facts."""
    from .models import EngineeringSourceRecord
    # This is the read side of the existing PDE page, not a calculation or
    # maintenance action.  Runtime isolation is verified by the API view and
    # the queryset below remains strictly tenant scoped.
    rows = EngineeringSourceRecord.objects.filter(
        company_id=user.company_id,
        source_no__startswith='PCE-ENGINEERING-DRAFT-',
    ).order_by('-pk')
    result = []
    for row in rows:
        if workbook_source_context is not None and row.pk != workbook_source_context['proof']['objectSourceRecordId']:
            continue
        snapshot = _draft_snapshot(row)
        if workbook_source_context is not None:
            context = design_calculation_context(user, row.pk, workbook_source_context=workbook_source_context)
            snapshot = context['draft']
        if order_engineering_instance_id == 'UNBOUND':
            if snapshot['orderEngineeringInstanceId'] is not None:
                continue
        elif order_engineering_instance_id and str(snapshot['orderEngineeringInstanceId']) != str(order_engineering_instance_id):
            continue
        result.append(snapshot)
    return {
        'drafts': result,
        'draftCount': len(result),
        'factSource': 'server',
        'businessWriteSideEffectCount': 0,
    }


def _workbook_source_identity(source_record_id):
    if source_record_id in (None, ''):
        return None
    if isinstance(source_record_id, bool):
        raise ValueError('WORKBOOK_SOURCE_ID_INVALID')
    try:
        selected = int(source_record_id)
    except (TypeError, ValueError):
        raise ValueError('WORKBOOK_SOURCE_ID_INVALID')
    if selected <= 0 or str(selected) != str(source_record_id):
        raise ValueError('WORKBOOK_SOURCE_ID_INVALID')
    return selected


def resolve_workbook_read_context(user, source_record_id):
    """Only a formal identity may cross the API boundary, never client proof."""
    selected = _workbook_source_identity(source_record_id)
    if selected is None:
        return None
    from .engineering_workbook_source_service import resolve_workbook_source
    return resolve_workbook_source(selected, company_id=user.company_id)


def workbook_source_metadata(user, source_record_id):
    """Describe a selected version; full file and baseline admission is separate."""
    selected = _workbook_source_identity(source_record_id)
    if selected is None:
        return None
    from .engineering_workbook_source_service import workbook_source_facts
    matches = [row for row in workbook_source_facts(user.company_id) if row['id'] == selected]
    if len(matches) != 1:
        raise ValueError('WORKBOOK_SOURCE_NOT_VISIBLE')
    return {**matches[0], 'proofReadStatus': 'metadata_only', 'formalExecutionAdmitted': False}


def workbook_source_catalog(user):
    """Current-company maintained source/context choices from formal records."""
    from .engineering_workbook_source_service import workbook_source_facts
    from .models import OrderEngineeringBaseline, EngineeringSourceRecord
    contexts = []
    baselines = production_baselines().filter(company_id=user.company_id, status='confirmed').select_related('sales_order')
    for baseline in baselines.order_by('sales_order_id', '-sequence', '-pk'):
        ids = set(baseline.items.values_list('source_record_id', flat=True))
        if len(ids) != 1:
            continue  # This workbook adapter requires one declared object source.
        source = EngineeringSourceRecord.objects.filter(pk=next(iter(ids)), company_id=user.company_id, status='confirmed').first()
        if source is None:
            continue
        contexts.append({'objectSourceRecordId': source.pk, 'baselineId': baseline.pk,
            'baselineSnapshotHash': baseline.snapshot_hash, 'baselineNo': baseline.baseline_no,
            'orderNo': baseline.sales_order.order_no, 'objectCount': baseline.items.count(),
            'label': f'{baseline.sales_order.order_no} / {baseline.baseline_no} / {source.source_no} / {baseline.items.count()}个对象'})
    return {'factSource': 'server', 'workbookSources': workbook_source_facts(user.company_id),
        'sourceContexts': contexts, 'businessWriteCount': 0, 'auditWriteCount': 0}


def save_draft(user, payload, registered_source_scope=None, ownership_correction=None, input_confirmation=None):
    """Append a draft revision. Existing source records and calculation results stay immutable."""
    from django.db import transaction
    from django.utils import timezone
    from .models import EngineeringSourceRecord, OrderEngineeringInstance, ProductDesignItem
    from system.models import OrganizationOperatingAuditRecord

    isolation = authorize(user, action_code='production.engineering.calculation.execute')
    rows = payload.get('rows')
    if not isinstance(rows, list) or not rows or len(rows) > 500:
        raise ValueError('ENGINEERING_DRAFT_ROWS_REQUIRED')
    normalized = []
    identities = set()
    allowed_fields = {
        'id', 'sourceType', 'space', 'product', 'component', 'componentCode', 'quantity',
        'unit', 'length', 'width', 'thickness', 'materialCode', 'materialName',
        'specification', 'edgeMode', 'visibleCondition', 'materialProcessCode',
        'routingProcessCode', 'processingNote', 'sourceSheet', 'sourceRow',
        'productCategoryId', 'productCategoryCode', 'productCategoryName',
        'unitId', 'unitName', 'sourceEvidence', 'drawingReference',
        'doorOpeningDirectionOptionId', 'doorOpeningDirectionOptionCode', 'doorOpeningDirectionOptionName',
        'lineStyleOptionId', 'lineStyleOptionCode', 'lineStyleOptionName',
        'edgeMethodOptionId', 'edgeMethodOptionCode', 'edgeMethodOptionName',
    }
    for index, value in enumerate(rows, start=1):
        if not isinstance(value, dict):
            raise ValueError(f'ENGINEERING_DRAFT_ROW_INVALID:{index}')
        item = {key: value.get(key) for key in allowed_fields if key in value}
        identity = str(item.get('id') or '').strip()
        if not identity:
            identity = f'DRAFT-{uuid.uuid4().hex}'
        if identity in identities:
            raise ValueError(f'ENGINEERING_DRAFT_ID_DUPLICATE:{identity}')
        identities.add(identity)
        item['id'] = identity
        item['sourceType'] = item.get('sourceType') if item.get('sourceType') in {'房门单', '三合一单'} else '未分类'
        item = normalize_draft_row_references(user, item, index)
        normalized.append(item)

    instance_id = payload.get('orderEngineeringInstanceId')
    sales_item_id = payload.get('salesOrderItemId')
    source_record_id = payload.get('sourceRecordId')
    design_scope = ProductDesignItem.objects.filter(company_id=user.company_id)
    if sales_item_id:
        design_scope = design_scope.filter(sales_order_item_id=sales_item_id)
    elif source_record_id:
        design_scope = design_scope.filter(source_record_id=source_record_id)
    else:
        design_scope = design_scope.none()
    if design_scope.exists():
        error = ValueError('ENGINEERING_DESIGN_FACT_READ_ONLY')
        error.code = 'ENGINEERING_DESIGN_FACT_READ_ONLY'
        error.message = '当前产品已由“产品设计管理”维护设计事实；工程数据录入只读消费，请返回产品设计修改。'
        error.details = {
            'salesOrderItemId': sales_item_id,
            'sourceRecordId': source_record_id,
            'factAuthority': 'ProductDesignItem/ProductDesignRevision',
            'suggestedAction': '返回产品设计修改',
            'route': '/pde/product-definitions',
        }
        raise error
    if instance_id:
        instance = OrderEngineeringInstance.objects.filter(pk=instance_id, company_id=user.company_id).first()
        if not instance or (sales_item_id and str(instance.sales_order_item_id) != str(sales_item_id)):
            raise ValueError('ENGINEERING_DRAFT_ORDER_SCOPE_INVALID')
    elif sales_item_id:
        raise ValueError('ENGINEERING_DRAFT_INSTANCE_REQUIRED')

    from .engineering_work_context import normalize_confirmed_business_facts
    draft_context = normalize_draft_context(user, payload)
    confirmed_business_facts = normalize_confirmed_business_facts(user, payload)
    metadata_only = bool(payload.get('metadataOnly'))
    source_payload = {
        'taskId': 'PCE-ENGINEERING-BREAKDOWN-BASE-AND-PLAN-20260914',
        'orderEngineeringInstanceId': instance_id,
        'salesOrderItemId': sales_item_id,
        'engineeringRows': normalized,
        **draft_context,
        **confirmed_business_facts,
        'revisionReason': str(payload.get('revisionReason') or '').strip()[:300],
        'sourceClassification': 'CONTROLLED_ENGINEERING_DRAFT',
        'formalSalesOrderCreated': False,
        'calculationRequired': not metadata_only,
        'calculationImpact': 'METADATA_ONLY' if metadata_only else 'INPUT_CHANGE',
        'sourceScopeKey': str(payload.get('sourceScopeKey') or instance_id or 'UNBOUND')[:100],
    }
    if registered_source_scope:
        source_payload['registeredSourceScope'] = registered_source_scope
    if ownership_correction:
        source_payload['companyOwnershipCorrection'] = dict(ownership_correction)
    if input_confirmation:
        source_payload['inputConfirmation'] = dict(input_confirmation)
    content_hash = hashlib.sha256(json.dumps(source_payload, ensure_ascii=False, sort_keys=True, default=str).encode('utf-8')).hexdigest()
    now = timezone.now()
    version = now.strftime('R%Y%m%d%H%M%S%f')
    source_no = f"PCE-ENGINEERING-DRAFT-{user.company_id}-{source_payload['sourceScopeKey']}"
    with transaction.atomic():
        record = EngineeringSourceRecord.objects.create(
            company_id=user.company_id,
            source_no=source_no,
            source_name=str(payload.get('sourceName') or '工程数据录入草稿')[:200],
            source_type='order_input' if instance_id else 'controlled_import',
            source_version=version,
            source_payload=source_payload,
            content_hash=content_hash,
            status='draft',
        )
        audit = OrganizationOperatingAuditRecord.objects.create(
            action_code='production.engineering.source.draft.save',
            actor=user,
            organization_id=user.company_id,
            target_type='EngineeringSourceRecord',
            target_id=record.pk,
            target_label=record.source_no[:200],
            reason=source_payload['revisionReason'] or '保存工程数据录入草稿',
            before_snapshot={},
            after_snapshot={
                'sourceRecordId': record.pk,
                'sourceVersion': version,
                'rowCount': len(normalized),
                'contentHash': content_hash,
                'calculationRequired': not metadata_only,
                'calculationImpact': 'METADATA_ONLY' if metadata_only else 'INPUT_CHANGE',
                'formalSalesOrderCreated': False,
            },
        )
    return {
        'draft': _draft_snapshot(record),
        'auditId': audit.pk,
        'runtimeIsolation': isolation,
        'businessWriteSideEffectCount': 1,
        'formalCalculationCreated': False,
        'previousSourceOverwritten': False,
    }

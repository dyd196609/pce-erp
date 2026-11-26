"""Audited decimal-boundary realization; never a fuzzy numeric comparator.

Frozen plans and captures remain immutable. A separate evaluation view binds
Reference to actual Native inputs, only when a sealed synthetic base +/- 0.1
exactly reconstructs the observed decimal value. Real business inputs, arbitrary
numeric drift and changed evaluated outputs remain fatal.
"""
import copy
import re
from decimal import Decimal
import package_support as p

CONTRACT = 'SEALED_SYNTHETIC_DECIMAL_BOUNDARY_REALIZATION_V1'


def realize(plan, golden, stocks):
    view = copy.deepcopy(plan)
    cases = {c['case_id']:c for c in view['cases']}
    stock_by_id = {str(s['material_id']):s for s in stocks}
    changes, exact = [], 0
    p.require(len(cases) == len(view['cases']), 'DUPLICATE PLAN CASE')
    p.require(len(golden['results']) == len(cases), 'REALIZATION NEEDS FULL CAPTURE')
    p.require([c['case_id'] for c in golden['results']] == [c['case_id'] for c in view['cases']], 'CAPTURE ORDER')
    for capture in golden['results']:
        c = cases[capture['case_id']]
        requested = {(x['sheet'],x['cell']):x for x in c['overrides']}
        p.require(len(requested) == len(c['overrides']) == len(capture['overrides']), 'INPUT SET')
        p.require({(a['sheet'],a['cell']) for a in capture['overrides']} == set(requested), 'INPUT KEYS')
        for a in capture['overrides']:
            e = requested[(a['sheet'],a['cell'])]
            typ = {'number':'number','text':'string','blank':'null','boolean':'boolean'}[e['type']]
            p.require(a['requested_type'] == e['type'] and p.type_matches(a['requested_value'],typ) and a['requested_value'] == e['value'], 'DECLARED REQUEST DRIFT')
            p.require(a['actual']['type'] == e['type'] and p.type_matches(a['actual']['value'],typ), 'ACTUAL INPUT TYPE DRIFT')
            if a['actual']['value'] == e['value']:
                exact += 1
                continue
            p.require(e['type'] == 'number', 'NONNUMERIC INPUT DRIFT')
            p.require(c.get('cohort') == 'R1_R3_R4_R5_R6_SYNTHETIC_BOUNDARIES' and c.get('data_provenance','').startswith('SIMULATED_FOR_TEST;'), 'REAL INPUT CANNOT BE NORMALIZED')
            match = re.fullmatch(r'U03_SYNTHETIC_(\d+)_([DEF])_(-?0\.1|0)', c['case_id'])
            p.require(match is not None, 'NO SEALED DECIMAL BOUNDARY RECIPE')
            material_id, col, delta = match.groups()
            p.require(material_id in stock_by_id and e['sheet'] == 'PCE_NATIVE_PROBES' and e['cell'] == col+'2300', 'BOUNDARY IDENTITY')
            field = {'D':'length','E':'width','F':'thickness'}[col]
            base = stock_by_id[material_id][field]
            p.require(e['value'] == base + float(delta), 'DECLARED INPUT != FROZEN GENERATOR')
            decimal_target = Decimal(str(base)) + Decimal(delta)
            p.require(a['actual']['value'] == float(decimal_target), 'ACTUAL INPUT != EXACT DECIMAL INTENT')
            # This is exact equality to one reconstructed input, not rounding,
            # epsilon, isclose or a relaxed formula-output tolerance.
            changes.append({'case_id':c['case_id'],'sheet':e['sheet'],'cell':e['cell'],
                'declared_value':e['value'],'native_value':a['actual']['value'],
                'stock_material_id':material_id,'dimension':field,'base':base,'delta':delta,
                'decimal_intent':str(decimal_target),'reason':'BINARY_ADDITION_TAIL_IN_SYNTHETIC_INPUT',
                'reference_binding':'ACTUAL_NATIVE_VALUE','source_or_capture_modified':False})
            e['value'] = a['actual']['value']
    evidence = {'contract':CONTRACT,'exact_input_count':exact,'realized_input_count':len(changes),
        'changes':changes,'frozen_plan_modified':False,'native_capture_modified':False,
        'formula_tolerance_changed':False,'case_output_invariance':'PENDING_CHECK'}
    return view, evidence


def verify_output_invariance(declared_rows, realized_rows, evidence):
    original = {(r['case_id'],r['cell']):r for r in declared_rows}
    actual = {(r['case_id'],r['cell']):r for r in realized_rows}
    p.require(set(original) == set(actual), 'REALIZED OUTPUT SET DRIFT')
    fields = ('formula_family','semantic_name','contract','reference_status','code_result')
    for k in original:
        p.require(all(original[k][f] == actual[k][f] for f in fields), 'DECIMAL REALIZATION CHANGED OUTPUT OR BRANCH: '+str(k))
    changed_ids = {c['case_id'] for c in evidence['changes']}
    affected = [r for r in realized_rows if r['case_id'] in changed_ids]
    evidence['case_output_invariance'] = 'PASS_TYPED_EXACT'
    evidence['affected_case_count'] = len(changed_ids)
    evidence['affected_output_count'] = len(affected)
    evidence['all_recomputed_output_count'] = len(actual)
    evidence['fit_minimum_selection_branch_output_count'] = sum(r['semantic_name'].startswith(('SYNTHETIC_SPEC_FIT_','SYNTHETIC_MINIMAL_SPEC_','SYNTHETIC_SELECTED_')) for r in affected)
    return evidence

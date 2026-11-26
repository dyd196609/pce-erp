"""One U03 recovery Native batch. Unsaved test copy only, no ERP rule changes."""
import collections
import copy
import itertools
from pathlib import Path
import package_support as p
from closure_batch import build as previous_build, qualified, SHEET
from formula_ast import Parser, SUPPORTED, functions as ast_functions
from workbook_source import SourceBook, coord, address
from u03_recovery_audit import OUT

COHORT = 'U03_RECOVERY_SINGLE_NATIVE_BATCH_R1'


def build(m):
    plan = previous_build(m)
    cases = plan['cases']
    family, frozen = p.assets(m)
    book = SourceBook(m['source'])
    audit = p.read(OUT / 'BOARD_STOCK_AND_REAL_ROW_AUDIT.json')
    stock = audit['stocks']
    probes = {v['cell']: v for v in plan['probe_sheet']['cells']}
    outputs_by_cell = {}
    seq = itertools.count(2000)

    def put(a, value, kind='formula', provenance='U03_RECOVERY_TEST_COPY_ONLY'):
        p.require(a not in probes, 'RECOVERY PROBE COLLISION')
        item = {'cell': a, 'type': kind, 'provenance': provenance}
        item['formula' if kind == 'formula' else 'value'] = value
        if kind == 'formula':
            tree = Parser().parse(value, allow_broken=True)
            p.require(set(ast_functions(tree)) <= SUPPORTED, 'UNSUPPORTED RECOVERY FORMULA')
            outputs_by_cell[a] = {'cell': SHEET + '!' + a, 'formula': value, 'formula_family': 'TECHNICAL_PROBE_' + a,
                'semantic_name': a, 'contract': {'comparison': 'TYPED_RAW_EXACT_NO_TOLERANCE'}, 'data_provenance': provenance}
        probes[a] = item
        return a

    def output(formula, name, provenance='U03_RECOVERY_TEST_COPY_ONLY'):
        a = put('B' + str(next(seq)), formula, provenance=provenance)
        outputs_by_cell[a]['semantic_name'] = name
        return a

    def case(name, addresses, cohort, changes=None, **extras):
        cases.append({'case_id': name, 'source_sha': p.EXPECTED_SHA, 'source_sheet': SHEET, 'source_row': None,
            'level': 'U03_RECOVERY', 'input_facts': {}, 'overrides': changes or [], 'derived_outputs': [copy.deepcopy(outputs_by_cell[a]) for a in addresses], 'cohort': cohort, **extras})

    # Complete unchanged baseline coverage, including all 456 existing boundaries.
    present = {c['case_id'] for c in cases}
    for c in frozen['cases']:
        if c['case_id'] in present:
            continue
        if c['level'] in (1, 4):
            cases.append(copy.deepcopy(c) | {'cohort': 'FROZEN_SOURCE_EXTRA_CASES_NOT_CURRENT_MIGRATION_APPROVAL'})
        elif c['level'] == 5:
            a = output(qualified(c['derived_outputs'][0]['formula'], c['source_sheet']), 'HISTORICAL_' + c['case_id'], 'HISTORICAL_SUMMARY_NOT_RECOVERED')
            case('HISTORICAL_' + c['case_id'], [a], 'HISTORICAL_MATERIAL_SUMMARY')
    # Source-only helper formulas outside the frozen target families. They are
    # not new recovered families and remain byte-checked before evaluation.
    for sn, cells in book.sheets.items():
        for a, cell in cells.items():
            f = cell['formula']
            key = sn + '!' + a
            if not f or '#REF!' in f or key in family['cell_to_family']:
                continue
            try:
                tree = Parser().parse(f)
            except Exception:
                continue
            if set(ast_functions(tree)) <= SUPPORTED:
                plan['technical_source_dependencies'][key] = f

    # Distinct geometric specs from actual formal material text, not 3x12 constants.
    specs = sorted({(s['length'], s['width'], s['thickness']) for s in stock})
    for i, dims in enumerate(specs, 1):
        for col, value in zip(('D', 'E', 'F'), dims):
            put(col + str(2000 + i), value, 'number', 'FORMAL_SPECIFICATION_SNAPSHOT')
    # For a row, test direct/rotated fit separately; unknown rotation is not
    # silently enabled. Formal material compatibility is deliberately unresolved.
    table_rows, real_rows = [], []
    for i, row in enumerate(audit['rows'], 1):
        r, t = row['row'], 2100 + i
        for col, src in zip(('D', 'E', 'F', 'G', 'H', 'I', 'J'), ('J', 'K', 'L', 'M', 'S', 'Q', 'R')):
            put(col + str(t), "='三合一生产单'!" + src + str(r), provenance='SOURCE_FORMULA_LINK_NOT_CACHE')
        put('K' + str(t), 'PENDING_MATERIAL_APPLICABILITY', 'text', 'MISSING_FORMAL_BINDING_NOT_FALSE_OR_ZERO')
        put('N' + str(t), f'=IF(\'三合一生产单\'!P{r}="","PENDING_EDGE_APPLICABILITY",\'三合一生产单\'!P{r})')
        fit, rotated = [], []
        for k, dims in enumerate(specs, 1):
            sr = 2000 + k
            a = output(f'=IF(AND(F{t}=F{sr},D{t}<=D{sr},E{t}<=E{sr},D{t}>0,E{t}>0,F{t}>0),1,0)', f'R3_GEOMETRY_ROW_{r}_SPEC_{k}')
            b = output(f'=IF(AND(F{t}=F{sr},E{t}<=D{sr},D{t}<=E{sr},D{t}>0,E{t}>0,F{t}>0),1,0)', f'R3_ROTATED_GEOMETRY_DIAGNOSTIC_ROW_{r}_SPEC_{k}')
            fit.append(a)
            rotated.append(b)
        mins = []
        for k, dims in enumerate(specs):
            dom = [fit[j] for j, other in enumerate(specs) if other[2] == dims[2] and other[0] <= dims[0] and other[1] <= dims[1] and other[:2] != dims[:2]]
            formula = f'=IF(AND({fit[k]}=1,SUM({",".join(dom) if dom else "0"})=0),1,0)'
            mins.append(output(formula, f'R3_MINIMUM_SPEC_ROW_{r}_{k+1}'))
        status = output(f'=IF(SUM({",".join(fit+rotated)})=0,"BLOCKED_NO_GEOMETRIC_SPEC",IF(K{t}="PENDING_MATERIAL_APPLICABILITY","BLOCKED_MATERIAL_APPLICABILITY","UNSUPPORTED_BINDING"))', f'R3_FORMAL_MATERIAL_ROW_{r}')
        put('L' + str(t), '=' + status)
        # Explicit unresolved identity, not a synthetic formal ID or a zero quantity.
        put('M' + str(t), f'=IF(L{t}="RESOLVED",K{t},"UNRESOLVED")')
        real_outputs = [c + str(t) for c in 'HIJ'] + [status] + fit + rotated + mins
        case(f'U03_REAL_TRI_{r}', real_outputs, 'R2_R3_REAL_ROW_RECOVERY', source_row_identity=f'三合一生产单!{r}')
        table_rows.append(t)
        real_rows.append(r)
    # Individual real row area outputs remain distinct from Material Requirements.
    def rows_sum(col):
        # This is a contiguous normalized 63-row table, not an arbitrary source
        # range. Range SUM preserves Excel's ignore-empty-text semantics.
        return f'SUM({col}{table_rows[0]}:{col}{table_rows[-1]})'
    net = output('=' + rows_sum('H'), 'ALL_TRI_PRODUCT_AREA_m2')
    veneer_net = output('=' + rows_sum('I'), 'VENEER_NET_VISIBLE_AREA_m2')
    veneer_gross = output('=' + veneer_net + '*1.2', 'AV30_RECOVERY_SOURCE_LOSS_FACTOR_1_20')
    edge_net = output('=' + rows_sum('J'), 'AV31_RECOVERY_NET_EDGE_LENGTH_m')
    unknown_visible = output('=COUNTIF(I2101:I2163,"")', 'VISIBLE_AREA_EMPTY_SOURCE_COUNT')
    unknown_edge = output('=COUNTIF(N2101:N2163,"PENDING_EDGE_APPLICABILITY")', 'EDGE_APPLICABILITY_MISSING_SOURCE_COUNT')
    case('U03_AGGREGATE_AREA_LEDGER', [net, veneer_net, veneer_gross, edge_net, unknown_visible, unknown_edge], 'R4_R5_R6_AGGREGATE_LEDGER')

    bucket_outputs = []
    unresolved = 'COUNTIF(M2101:M2163,"UNRESOLVED")'
    for s in stock:
        a = output(f'=IF({unresolved}>0,"BLOCKED_UNRESOLVED_REQUIREMENTS",SUMIFS(H2101:H2163,M2101:M2163,"{s["material_id"]}|{s["length"]}|{s["width"]}|{s["thickness"]}|m²"))', 'R4_FORMAL_BUCKET_' + str(s['material_id']))
        bucket_outputs.append(a)
    case('U03_ALL_FORMAL_MATERIAL_BUCKETS', bucket_outputs, 'R4_BOARD_AGGREGATION_WITH_BLOCKING')
    # A known net subtotal is not a complete gross/issue requirement.
    put('D2450', 'PENDING', 'text', 'MISSING_FORMAL_EDGE_ALLOWANCE_POLICY')
    edge_count_cells = []
    for r in real_rows:
        pattern = "'三合一生产单'!P" + str(r)
        multiplier = '0'
        for label, count in [('一长', 1), ('一宽', 1), ('两长', 2), ('两宽', 2), ('一长一宽', 2), ('一长两宽', 3), ('两长一宽', 3), ('四边', 4), ('白坯', 0)]:
            multiplier = f'IF({pattern}="{label}",{count},' + multiplier + ')'
        edge_count_cells.append(output(f'=IF({pattern}="","PENDING_EDGE_APPLICABILITY",({multiplier})*\'三合一生产单\'!M{r})', 'REAL_EDGE_COUNT_' + str(r)))
    edge_gross = output(f'=IF(D2450="PENDING","PENDING_EDGE_ALLOWANCE_POLICY",{edge_net}+SUM({",".join(edge_count_cells)})*D2450/1000)', 'REAL_EDGE_GROSS_POLICY_GATE')
    veneer_gate = output(f'=IF({unknown_visible}>0,"PARTIAL_VISIBLE_AREA_SOURCE","NET_BASIS_COMPLETE")', 'VENEER_SOURCE_COMPLETENESS_GATE')
    edge_gate = output(f'=IF({unknown_edge}>0,"PARTIAL_EDGE_APPLICABILITY_SOURCE","NET_BASIS_COMPLETE")', 'EDGE_SOURCE_COMPLETENESS_GATE')
    case('U03_REAL_EDGE_POLICY_AND_SCOPE', edge_count_cells + [edge_gross, veneer_gate, edge_gate], 'R5_R6_POLICY_AND_SCOPE_GATES')
    # Twelve damaged historical summary positions map one-to-many to actual
    # material/spec buckets. Missing source headings are not invented identities.
    projection = []
    broken_summary = [f for f in family['families'] if f['broken'] and any(family['cell_to_family'].get('三合一生产单!' + address(29, c)) == f['family_id'] for c in range(33, 45))]
    for f in broken_summary:
        projection.append({'family_id': f['family_id'], 'source_formula': f['source_formula'], 'replacement_semantic': 'GROUP_BY_FORMAL_MATERIAL_SPEC_UOM; one-to-many, no guessed cell-to-thickness binding', 'technical_bucket_cells': bucket_outputs, 'status': 'BLOCKED_FORMAL_MATERIAL_BINDING', 'native_validation': 'PENDING'})

    # All 36 original candidates are preserved as control expressions. Explicit
    # width/no-stock counterexamples prove why technical parity is not approval.
    candidate_cases = [c for c in cases if c.get('cohort') == 'RECOVERY_AREA_GUARD' and c['case_id'].endswith('_POSITIVE_CONTROL')]
    for c in candidate_cases:
        extra = copy.deepcopy(c)
        extra['case_id'] += '_WIDTH_TOO_WIDE'
        extra['cohort'] = 'R1_OLD_CANDIDATE_SEMANTIC_COUNTEREXAMPLE'
        for change in extra['overrides']:
            if change['sheet'] == '三合一生产单' and change['cell'].startswith('K'):
                change['type'], change['value'] = 'number', max(max(s['width'], s['length']) for s in stock) + 1
        extra['derived_outputs'] = extra['derived_outputs'][:1]
        cases.append(extra)

    # Reusable synthetic resolver cases with known eligibility and orientation.
    # Numeric IDs/specs are formal snapshots, but these assignments are TEST ONLY.
    representatives = [next(s for s in stock if (s['length'], s['width'], s['thickness']) == dims) for dims in specs]
    t = 2300
    for col, value in zip('DEFGHIJK', (100, 100, 18, 2, False, True, 0.2, 20)):
        put(col + str(t), value, 'boolean' if type(value) is bool else 'number', 'SIMULATED_FOR_TEST_NOT_FORMAL_POLICY')
    syn_fit, syn_min = [], []
    for k, s in enumerate(representatives, 1):
        sr = 2000 + k
        syn_fit.append(output(f'=IF(AND(F{t}=F{sr},OR(AND(D{t}<=D{sr},E{t}<=E{sr}),AND(H{t}=TRUE,E{t}<=D{sr},D{t}<=E{sr})),D{t}>0,E{t}>0,F{t}>0),1,0)', 'SYNTHETIC_SPEC_FIT_' + str(k)))
    for k, s in enumerate(representatives):
        dom = [syn_fit[j] for j, z in enumerate(representatives) if z['thickness'] == s['thickness'] and z['length'] <= s['length'] and z['width'] <= s['width'] and (z['length'], z['width']) != (s['length'], s['width'])]
        syn_min.append(output(f'=IF(AND({syn_fit[k]}=1,SUM({",".join(dom) if dom else "0"})=0),1,0)', 'SYNTHETIC_MINIMAL_SPEC_' + str(k)))
    selected = output(f'=IF(I{t}<>TRUE,"BLOCKED_APPLICABILITY",IF(SUM({",".join(syn_min)})=1,SUM(' + ','.join(f'IF({a}=1,{s["material_id"]},0)' for a, s in zip(syn_min, representatives)) + '),"BLOCKED_NO_OR_AMBIGUOUS_SPEC"))', 'SYNTHETIC_SELECTED_MATERIAL_ID')
    syn_area = output(f'=IF(OR(D{t}="",E{t}=""),"",D{t}*E{t}*G{t}/1000000)', 'SYNTHETIC_PRODUCT_AREA_m2')
    selected_key_expr = '"UNRESOLVED"'
    for s in representatives:
        key = '|'.join(str(s[k]) for k in ('material_id', 'length', 'width', 'thickness')) + '|m²'
        selected_key_expr = f'IF({selected}={s["material_id"]},"{key}",' + selected_key_expr + ')'
    selected_key = output('=' + selected_key_expr, 'SYNTHETIC_SELECTED_FULL_BUCKET_KEY')
    put('D2500', '=' + selected_key)
    put('D2501', '=' + selected_key)
    put('D2502', 'UNRELATED_MATERIAL_SPEC_KEY', 'text', 'SIMULATED_FOR_TEST_KEY')
    put('E2500', '=' + syn_area)
    put('E2501', '=' + syn_area + '*2')
    put('E2502', 999, 'number', 'SIMULATED_FOR_TEST_MUST_NOT_LEAK')
    chain_aggregate = output(f'=IF({selected_key}="UNRESOLVED","BLOCKED_UNRESOLVED_REQUIREMENTS",SUMIFS(E2500:E2502,D2500:D2502,{selected_key}))', 'SYNTHETIC_SELECTION_TO_NET_TO_BUCKET_AGGREGATE')
    syn_gross = output(f'=IF(J{t}="","PENDING_LOSS_RATE",{syn_area}*(1+J{t}))', 'SYNTHETIC_AREA_LOSS_PARAMETER')
    syn_edge = output(f'=IF(K{t}="","PENDING_EDGE_ALLOWANCE",((D{t}+K{t})*2+(E{t}+K{t})*2)*G{t}/1000)', 'SYNTHETIC_PER_EDGE_ALLOWANCE_m')
    # Aggregation uses a whole key, not only thickness; two same-key lines and
    # one unrelated key explicitly exercise no cross-material/spec mixing.
    for rr, k, n in [(2400, '11|2440|1220|18|m²', 0.2), (2401, '11|2440|1220|18|m²', 0.3), (2402, '12|2800|1220|18|m²', 0.9)]:
        put('D' + str(rr), k, 'text', 'SIMULATED_FOR_TEST_BUCKET_KEY')
        put('E' + str(rr), n, 'number', 'SIMULATED_FOR_TEST_NET_AREA')
    agg1 = output('=SUMIFS(E2400:E2402,D2400:D2402,D2400)', 'SYNTHETIC_SAME_BUCKET_ONLY')
    agg2 = output('=SUMIFS(E2400:E2402,D2400:D2402,D2402)', 'SYNTHETIC_OTHER_BUCKET_SEPARATE')
    for rr, key, value in [(2460, 'edge11|22mm|1mm|walnut|m', 1.04), (2461, 'edge11|22mm|1mm|walnut|m', 0.54), (2462, 'edge11|30mm|1mm|walnut|m', 2.04), (2463, 'edge12|22mm|1mm|oak|m', 3.04)]:
        put('D' + str(rr), key, 'text', 'SIMULATED_FOR_TEST_EDGE_KEY')
        put('E' + str(rr), value, 'number', 'SIMULATED_FOR_TEST_EDGE_LENGTH_m')
    edge_agg = [output(f'=SUMIFS(E2460:E2463,D2460:D2463,D{r})', 'SYNTHETIC_EDGE_BUCKET_' + str(r)) for r in (2460, 2462, 2463)]
    all_syn = syn_fit + syn_min + [selected, selected_key, syn_area, chain_aggregate, syn_gross, syn_edge, agg1, agg2] + edge_agg
    scenarios = []
    for s in representatives:
        for field, base in [('D', s['length']), ('E', s['width']), ('F', s['thickness'])]:
            for delta in (-0.1, 0, 0.1):
                facts = {'D': min(100, s['length']), 'E': min(100, s['width']), 'F': s['thickness'], 'G': 2, 'H': False, 'I': True, 'J': 0.2, 'K': 20}
                facts[field] = base + delta
                scenarios.append((f'{s["material_id"]}_{field}_{delta}', facts))
    for name, changes in [('ROTATED_ONLY', {'D': 1000, 'E': 2400, 'H': True}), ('ROTATION_FORBIDDEN', {'D': 1000, 'E': 2400, 'H': False}), ('AREA_ONLY_TRAP', {'D': 100, 'E': 1300, 'H': False}), ('UNKNOWN_APPLICABILITY', {'I': False}), ('NO_THICKNESS', {'F': 28}), ('NO_GEOMETRIC_FIT', {'D': 10000}), ('ZERO_QUANTITY', {'G': 0}), ('AREA_RATE_MISSING', {'J': ''}), ('EDGE_ALLOWANCE_MISSING', {'K': ''}), ('EDGE_ALLOWANCE_ZERO_EXPLICIT_TEST', {'K': 0}), ('AREA_RATE_ZERO_EXPLICIT_TEST', {'J': 0})]:
        scenarios.append((name, {'D': 100, 'E': 100, 'F': 18, 'G': 2, 'H': False, 'I': True, 'J': 0.2, 'K': 20} | changes))
    for name, facts in scenarios:
        overrides = [{'sheet': SHEET, 'cell': k + str(t), 'type': 'boolean' if type(v) is bool else 'text' if type(v) is str else 'number', 'value': v} for k, v in facts.items()]
        case('U03_SYNTHETIC_' + name, all_syn, 'R1_R3_R4_R5_R6_SYNTHETIC_BOUNDARIES', overrides, data_provenance='SIMULATED_FOR_TEST; NOT_REAL_MATERIAL_ASSIGNMENT_OR_POLICY')
    plan.update(cohort=COHORT, selected_case_count=len(cases), selected_output_count=sum(len(c['derived_outputs']) for c in cases),
        formula_recovery_applied=False, recovery_test_copy=True, recovery_source_sha=p.EXPECTED_SHA,
        formal_snapshot_sha=audit['formal_snapshot_sha'], board_business_status='BLOCKED_FORMAL_MATERIAL_APPLICABILITY_AND_SPEC_GAPS',
        real_source_rows=real_rows, summary_family_projections=projection, recovery_levels=['R1', 'R2', 'R3', 'R4', 'R5', 'R6'],
        recovery_acceptance='NATIVE_PARITY_PENDING; BUSINESS_BLOCKERS_NOT_HIDDEN_BY_EQUAL_BLOCKED_VALUES',
        legacy_scope='房门单 row >=39 historical only; frozen cases kept only as non-regression diagnostics')
    plan['probe_sheet']['cells'] = list(probes.values())
    p.require(len({c['case_id'] for c in cases}) == len(cases), 'DUPLICATE RECOVERY CASE ID')
    p.require(len(projection) == 12, 'MISSING AG29:AR29 FAMILY PROJECTION')
    return plan

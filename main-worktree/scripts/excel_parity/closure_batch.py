"""One supplemental native batch using the existing user-session runner.

All added formulas live ONLY on an unsaved technical sheet of the byte-identical
read-only copy. Source sheets/formulas are never patched, including candidates.
This is a test-plan adapter, not a second ERP/reference implementation.
"""
from __future__ import annotations
import copy
import itertools
import re
from pathlib import Path
from openpyxl.formula.tokenizer import Tokenizer
from openpyxl.formula.translate import Translator
import package_support as p
from formula_ast import Parser, functions as ast_functions, SUPPORTED
from workbook_source import SourceBook, coord

SHEET = 'PCE_NATIVE_PROBES'
COHORT = 'TECHNICAL_CLOSURE_NATIVE_SUPPLEMENT_R1'


def qualified(formula, sheet):
    tokens = Tokenizer(formula).items
    prefix = "'" + sheet.replace("'", "''") + "'!"
    return '=' + ''.join(prefix + t.value if t.type == 'OPERAND' and t.subtype == 'RANGE' and '!' not in t.value else t.value for t in tokens)


def build(m):
    family, manifest = p.assets(m)
    book = SourceBook(m['source'])
    from generated_reference import FUNCTIONS
    baseline_cases = p.select_cases(family, manifest, FUNCTIONS)
    baseline_ids = {c['case_id'] for c in baseline_cases}
    selected = [copy.deepcopy(c) | {'cohort': 'ORIGINAL_SOURCE_REMAINING_LEVEL1' if c['level'] == 1 else 'ORIGINAL_SOURCE_REAL_ROW'} for c in manifest['cases'] if (c['level'] == 1 and c['case_id'] not in baseline_ids) or c['level'] in (2, 3)]
    probes, probe_index = {}, {}
    sequence = itertools.count(100)

    def add(formula, label, provenance, contract=None):
        key = (formula, label)
        if key not in probe_index:
            address = 'B' + str(next(sequence))
            tree = Parser().parse(formula, allow_broken=True)
            p.require(set(ast_functions(tree)) <= SUPPORTED, 'UNSUPPORTED PROBE FUNCTION')
            probes[address] = {'cell': address, 'formula': formula, 'type': 'formula', 'provenance': provenance}
            probe_index[key] = address
        address = probe_index[key]
        return {'cell': SHEET + '!' + address, 'formula': formula, 'formula_family': 'TECHNICAL_PROBE_' + address, 'semantic_name': label, 'contract': contract or {'comparison': 'TYPED_EXACT'}, 'data_provenance': provenance}

    def case(case_id, outputs, overrides=None, cohort='MICRO_SEMANTICS', extra=None):
        return {'case_id': case_id, 'source_sha': p.EXPECTED_SHA, 'source_sheet': SHEET, 'source_row': None, 'level': 'TECHNICAL_SUPPLEMENT', 'input_facts': {}, 'overrides': overrides or [], 'derived_outputs': outputs, 'cohort': cohort} | (extra or {})

    # Physical blank (missing cell), formula empty string, zero and Boolean are
    # kept separate. No expected Excel result is baked into this native plan.
    for col in ('D', 'G'):
        probes[col + '2'] = {'cell': col + '2', 'type': 'formula', 'formula': '=""', 'provenance': 'SYNTHETIC_EMPTY_STRING'}
        probes[col + '3'] = {'cell': col + '3', 'type': 'number', 'value': 0, 'provenance': 'SYNTHETIC_ZERO'}
        probes[col + '4'] = {'cell': col + '4', 'type': 'boolean', 'value': False, 'provenance': 'SYNTHETIC_FALSE'}
    for row in range(1, 5):
        probes['H' + str(row)] = {'cell': 'H' + str(row), 'type': 'number', 'value': row * 11, 'provenance': 'SYNTHETIC_LOOKUP_RETURN_LABEL_NOT_ORACLE'}
    micro = []
    names = ['BLANK_CELL', 'EMPTY_STRING', 'ZERO', 'FALSE']
    for i, key in enumerate(names, 1):
        for j, target in enumerate(names, 1):
            for fn, formula in [('MATCH', f'=MATCH(D{i},G{j}:G{j},0)'), ('VLOOKUP', f'=VLOOKUP(D{i},G{j}:H{j},2,FALSE)')]:
                micro.append(add(formula, fn + '_' + key + '_TO_' + target, 'SYNTHETIC_MICRO_NATIVE_ORACLE_REQUIRED'))
        micro.append(add(f'=MATCH(D{i},G1:G4,0)', 'MIXED_MATCH_' + key, 'SYNTHETIC_MICRO_NATIVE_ORACLE_REQUIRED'))
        micro.append(add(f'=VLOOKUP(D{i},G1:H4,2,FALSE)', 'MIXED_VLOOKUP_' + key, 'SYNTHETIC_MICRO_NATIVE_ORACLE_REQUIRED'))
    for addr, typ, value in [('J1', 'formula', '=1/0'), ('J2', 'text', 'x'), ('K1', 'number', 71), ('K2', 'number', 9), ('L1', 'text', 'y'), ('L2', 'text', 'x'), ('M1', 'formula', '=1/0'), ('M2', 'number', 9), ('N1', 'text', 'x'), ('N2', 'text', 'x')]:
        probes[addr] = {'cell': addr, 'type': typ, 'formula' if typ == 'formula' else 'value': value, 'provenance': 'SYNTHETIC_SUMIFS_ERROR_PROBE'}
    for label, formula in {
        'SUMIFS_CRITERIA_ERROR': '=SUMIFS(K1:K2,J1:J2,"x")',
        'SUMIFS_UNMATCHED_SUM_ERROR': '=SUMIFS(M1:M2,L1:L2,"x")',
        'SUMIFS_MATCHED_SUM_ERROR': '=SUMIFS(M1:M2,N1:N2,"x")',
        'SUMIFS_ERROR_FIRST_CRITERION_SKIPPED_BY_SECOND': '=SUMIFS(K1:K2,J1:J2,"x",L1:L2,"x")',
        'SUMIFS_ERROR_SECOND_CRITERION_SKIPPED_BY_FIRST': '=SUMIFS(K1:K2,L1:L2,"x",J1:J2,"x")',
        'SUMIF_CRITERIA_ERROR': '=SUMIF(J1:J2,"x",K1:K2)',
        'SUMIFS_CRITERION_ARGUMENT_ERROR': '=SUMIFS(K1:K2,L1:L2,J1)',
        'BLANK_COMPARE_ZERO': '=D1=D3', 'BLANK_COMPARE_EMPTY': '=D1=D2',
        'IF_LAZY_ERROR': '=IF(FALSE,1/0,7)', 'IFERROR_ORDINARY_ERROR': '=IFERROR(1/0,7)',
        'AND_EAGER_ERROR': '=AND(FALSE,1/0)', 'OR_EAGER_ERROR': '=OR(TRUE,1/0)',
        'VLOOKUP_MATCHED_EMPTY_RETURN': '=VLOOKUP("x",N1:O2,2,FALSE)',
    }.items():
        micro.append(add(formula, label, 'SYNTHETIC_MICRO_NATIVE_ORACLE_REQUIRED'))
    selected.append(case('NATIVE_MICRO_LOOKUP_SUMIFS_LAZY_R1', micro))

    # Capture new source intermediates in the same ten old input cases plus S9.
    old = p.read(p.ROOT / 'runs/20260908T144733317Z-4c7dd106/DIFFERENTIAL_RESULTS.json')
    trace_ids = {r['case_id'] for r in old['results'] if r['classification'] == 'UNCLASSIFIED_DIFFERENCE' or r['cell'] == '房门单!S9'}
    trace_formulas = {
        'I6_SUMIFS_AW': '=SUMIFS(\'房门单\'!$AW:$AW,\'房门单\'!$AS:$AS,\'房门单\'!G6,\'房门单\'!$AV:$AV,\'房门单\'!H6)',
        'I6_SUMIFS_AY': '=SUMIFS(\'房门单\'!$AY:$AY,\'房门单\'!$AS:$AS,\'房门单\'!G6,\'房门单\'!$AV:$AV,\'房门单\'!H6)',
        'I6_SUMIFS_BC': '=SUMIFS(\'房门单\'!$BC:$BC,\'房门单\'!$BA:$BA,\'房门单\'!G6,\'房门单\'!$BB:$BB,\'房门单\'!H6)',
        'I39_W39_FIRST_MATCH': '=MATCH(\'房门单\'!X39,\'物料目录(设计)\'!G:G,0)',
        'I39_HEADER_MATCH': '=MATCH(\'房门单\'!I10,\'物料目录(设计)\'!A1:U1,0)',
    }
    intermediate_outputs = []
    for a in ['AT30', 'AV30', 'AW30', 'AY30', 'BC30', 'I39', 'M39', 'Q39', 'U39', 'AD39', 'W39', 'S9']:
        cell = book.sheets['房门单'].get(a)
        if cell and cell['formula']:
            intermediate_outputs.append({'cell': '房门单!' + a, 'formula': cell['formula'], 'formula_family': family['cell_to_family']['房门单!' + a], 'semantic_name': 'SOURCE_INTERMEDIATE_' + a, 'contract': {'comparison': 'TYPED_EXACT'}})
    intermediate_outputs += [add(f, name, 'UNCHANGED_SOURCE_SUBEXPRESSION_DIAGNOSTIC') for name, f in trace_formulas.items()]
    observation_cells = ['G6', 'H6', 'AS30', 'AZ30', 'J30', 'N30', 'AP30', 'Q30', 'G39', 'X39', 'I10', 'U10', 'AD10']
    for original in baseline_cases:
        if original['case_id'] in trace_ids:
            outputs = {o['cell']: copy.deepcopy(o) for o in original['derived_outputs'] + intermediate_outputs}
            selected.append(copy.deepcopy(original) | {'case_id': 'TRACE_' + original['case_id'], 'cohort': 'NATIVE_SOURCE_INTERMEDIATES', 'baseline_case_id': original['case_id'], 'derived_outputs': list(outputs.values()), 'observations': [{'sheet': '房门单', 'cell': a} for a in observation_cells]})

    candidates = p.read(Path(m['evidence_directory']) / 'CANDIDATE_FORMULA_RECONSTRUCTION.json')
    candidate_by_id = {c['family_id']: c for c in candidates}
    for original in manifest['cases']:
        if original['level'] not in (1, 2, 3):
            continue
        outputs = []
        for o in original['derived_outputs']:
            c = candidate_by_id.get(o['formula_family'])
            if c is None:
                continue
            source_sheet, address = o['cell'].rsplit('!', 1)
            origin = c['source_cells'][0].rsplit('!', 1)[1]
            candidate = Translator(c['candidate_formula'], origin=origin).translate_formula(address)
            original_broken = Translator(c['broken_formula'], origin=origin).translate_formula(address)
            p.require(original_broken == o['formula'], 'CANDIDATE SHIFT IDENTITY MISMATCH')
            output = add(qualified(candidate, source_sheet), 'CANDIDATE_' + o['cell'], 'RECOVERABLE_CANDIDATE_NOT_SOURCE_FORMULA', o['contract'])
            output.update(candidate_family=c['family_id'], candidate_source_cell=o['cell'], original_formula=o['formula'], candidate_formula=candidate)
            outputs.append(output)
        if outputs:
            selected.append(case('RECOVERY_' + original['case_id'], outputs, copy.deepcopy(original['overrides']), 'RECOVERY_CANDIDATE_ONLY', {'baseline_source_case_id': original['case_id'], 'real_source_row': original['source_row'] if original['level'] in (2, 3) else None}))

    # Additional paired area-guard tests: the candidate is NOT assumed equivalent
    # to homologous T. Native results may establish a real guard distinction.
    from reference_runtime import Context, truth
    from types import SimpleNamespace
    for c in candidates:
        source_sheet, origin = c['source_cells'][0].rsplit('!', 1)
        row = coord(origin)[0]
        candidate = c['candidate_formula']
        condition = Parser().parse(candidate)['arguments'][0]
        condition_book = SimpleNamespace(sheets={source_sheet: {}}, names=[])
        values = sorted({1, 18, 40, 1000} | {max(1, int(x) + d) for x in re.findall(r'(?<![A-Z])\b\d+\b', c['broken_formula']) for d in (-1, 0, 1)})
        positive = None
        for height, thickness in itertools.product(values, values):
            inputs = {(source_sheet, 'J' + str(row)): height, (source_sheet, 'K' + str(row)): 567, (source_sheet, 'L' + str(row)): thickness, (source_sheet, 'M' + str(row)): 2}
            ctx = Context(condition_book, {}, {}, inputs)
            if truth(ctx.source_ast(condition, source_sheet, row, coord(origin)[1])):
                positive = {'J': height, 'K': 567, 'L': thickness, 'M': 2}
                break
        p.require(positive is not None, 'NO SYNTHETIC TRUE BRANCH INPUT FOUND')
        scenarios = [('POSITIVE_CONTROL', None, None, None)] + [(field + '_' + kind, field, kind, value) for field in ('J', 'K', 'M') for kind, value in [('number', 0), ('blank', None), ('text', '')]]
        for label, field, typ, value in scenarios:
            changes = [{'sheet': source_sheet, 'cell': k + str(row), 'type': typ if k == field else 'number', 'value': value if k == field else v} for k, v in positive.items()]
            outputs = [add(qualified(candidate, source_sheet), 'AREA_GUARD_CANDIDATE_' + c['family_id'], 'RECOVERY_CANDIDATE_GUARD_PROBE')]
            for e in c['evidence']:
                hrow = coord(e['cell'])[0]
                for sf, hf in [('J', 'E'), ('K', 'F'), ('L', 'G'), ('M', 'H')]:
                    changes.append({'sheet': e['sheet'], 'cell': hf + str(hrow), 'type': typ if sf == field else 'number', 'value': value if sf == field else positive[sf]})
                p.require(book.sheets[e['sheet']][e['cell']]['formula'] == e['formula'], 'HOMOLOGOUS FORMULA CHANGED')
                # Alias on technical sheet keeps source family inventory immutable.
                outputs.append(add(qualified(e['formula'], e['sheet']), 'HOMOLOGOUS_' + e['sheet'] + '_' + c['family_id'], 'REAL_HOMOLOGOUS_FORMULA_WITH_SYNTHETIC_INPUTS_NOT_HISTORICAL_OUTPUT'))
            selected.append(case('AREA_GUARD_' + c['family_id'] + '_' + label, outputs, changes, 'RECOVERY_AREA_GUARD'))
    p.require(len({c['case_id'] for c in selected}) == len(selected), 'SUPPLEMENT CASE ID DUPLICATE')
    dependencies = {e['sheet'] + '!' + e['output_precedent']: e['precedent_formula'] for c in candidates for e in c['evidence']}
    return {'cohort': COHORT, 'cases': selected, 'probe_sheet': {'name': SHEET, 'cells': list(probes.values()), 'persistence': 'UNSAVED_ISOLATED_COPY_ONLY'}, 'technical_source_dependencies': dependencies, 'selected_case_count': len(selected), 'selected_output_count': sum(len(c['derived_outputs']) for c in selected), 'cached_values_are_oracle': False, 'original_formula_changes': 0, 'production_write': 0, 'formula_recovery_applied': False, 'candidate_formulas_tested_only_on_technical_sheet': True}


def context_assets(m, plan):
    """Extend the existing Context with per-plan technical expressions only."""
    modules = p.reference(m)
    family, _ = p.assets(m)
    book = SourceBook(plan['workbook_copy'])
    mapping = dict(family['cell_to_family'])
    functions = dict(modules['generated_reference'].FUNCTIONS)
    for source_cell, formula in plan.get('technical_source_dependencies', {}).items():
        sheet, addr = source_cell.rsplit('!', 1)
        p.require(book.sheets[sheet][addr]['formula'] == formula, 'TECHNICAL READ-ONLY DEPENDENCY DRIFT')
        p.require(source_cell not in mapping, 'DO NOT REPLACE AN INVENTORIED FAMILY')
        tree = Parser().parse(formula)
        fid = 'TECHNICAL_READONLY_DEPENDENCY_' + source_cell
        mapping[source_cell] = fid
        functions[fid] = lambda ctx, row, col, tree=tree, sheet=sheet: ctx.source_ast(tree, sheet, row, col)
    if 'probe_sheet' in plan:
        sheet = plan['probe_sheet']['name']
        p.require(sheet == SHEET and sheet not in book.sheets, 'PROBE SHEET MUST BE NEW AND TECHNICAL')
        book.sheets[sheet] = {}
        for definition in plan['probe_sheet']['cells']:
            addr = definition['cell']
            formula = definition.get('formula')
            book.sheets[sheet][addr] = {'formula': formula, 'value': definition.get('value'), 'type': 'n'}
            if formula:
                fid = 'TECHNICAL_PROBE_' + addr
                tree = Parser().parse(formula, allow_broken=True)
                mapping[sheet + '!' + addr] = fid
                functions[fid] = lambda ctx, row, col, tree=tree, sheet=sheet: ctx.source_ast(tree, sheet, row, col)
    return book, mapping, functions


def seal():
    from technical_closure import frozen, ARCHIVE, CLOSURE
    old = frozen()
    completed = sorted((CLOSURE / 'attempts').glob('*/SUMMARY.json'))
    p.require(completed, 'COMPLETED BASELINE RECOMPARISON AUDIT REQUIRED BEFORE RECOVERY BATCH')
    summary = p.read(completed[-1])
    p.require(summary['gates']['technical_fail'] == 0 and summary['gates']['current_eligible'] == summary['gates']['current_all_case_pass'], 'LEVEL 1A NOT CLOSED')
    dependencies = dict(old['frozen_files'])
    runtime = Path(old['reference_directory']) / 'reference_runtime.py'
    dependencies[str(runtime)] = p.digest(runtime)
    additions = ['technical_closure.py', 'closure_batch.py', 'test_technical_closure.py', 'test_closure_batch.py']
    for name in additions:
        path = Path(old['reference_directory']) / name
        dependencies[str(path)] = p.digest(path)
    for name in p.PACKAGE_FILES:
        path = p.ROOT / name
        if path.suffix == '.ps1':
            path.write_bytes(path.read_text('utf-8-sig').encode('utf-8-sig'))
        elif path.suffix == '.cmd':
            path.write_bytes(path.read_text('ascii').replace('\r\n', '\n').replace('\n', '\r\n').encode('ascii'))
    plan = build(old)
    import collections
    new = old | {'package_version': '1.2-technical-closure-r1', 'created_at': p.now(), 'files': {n: p.digest(p.ROOT / n) for n in p.PACKAGE_FILES}, 'frozen_files': dependencies, 'scope': COHORT, 'supplemental_batch': COHORT, 'native_execution': 'NOT_EXECUTED_FOR_NEW_BATCH', 'revision': {'old_manifest': str(ARCHIVE / 'RUNNER_MANIFEST.json'), 'old_manifest_sha': p.digest(ARCHIVE / 'RUNNER_MANIFEST.json'), 'runtime_before': old['frozen_files'][str(runtime)], 'runtime_after': p.digest(runtime), 'audit': str(completed[-1]), 'audit_sha': p.digest(completed[-1]), 'original_inventory_evidence_manifest_preserved': True, 'authorization': 'c91c7c1f sections 10,12,17,18; isolated native test extension; no source/production writes'}, 'batch_counts': {'cases': len(plan['cases']), 'outputs': plan['selected_output_count'], 'cohorts': dict(collections.Counter(c['cohort'] for c in plan['cases']))}}
    p.write(p.ROOT / 'RUNNER_MANIFEST.json', new)
    print(__import__('json').dumps(new['batch_counts'], ensure_ascii=False))

"""Append-only audit of the frozen native Run. No workbook or production writes."""
from __future__ import annotations
import collections
import importlib.util
import json
import sqlite3
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PACKAGE = REPO / 'tools/excel-golden-runner'
sys.path.insert(0, str(PACKAGE))
import package_support as p

EVIDENCE = REPO / 'docs/evidence/excel_formula_parity'
CLOSURE = EVIDENCE / 'closure-20260909'
ARCHIVE = CLOSURE / 'baseline-code'
BASELINE = PACKAGE / 'runs/20260908T144733317Z-4c7dd106'
RUN_MANIFEST_SHA = '38CF2AC205DDB077E97F1EA68B534103DC6D3208A7957F996DEE0C3C41433697'
DB_SHA = '9DADFB55D446DF052A4DCF6CF2EE552906939FD1B65D7D899C5FD8C1AC368F5C'


def frozen():
    p.require(p.digest(BASELINE / 'RUN_MANIFEST.json') == RUN_MANIFEST_SHA, 'BASELINE MANIFEST CHANGED')
    p.verify_hashes(p.read(BASELINE / 'RUN_MANIFEST.json')['files'], BASELINE)
    manifest = p.read(ARCHIVE / 'RUNNER_MANIFEST.json')
    p.require(p.digest(ARCHIVE / 'RUNNER_MANIFEST.json') == p.read(BASELINE / 'RUN_MANIFEST.json')['package_manifest_sha'], 'OLD PACKAGE MANIFEST CHANGED')
    p.verify_hashes(manifest['files'], ARCHIVE)
    for path, sha in manifest['frozen_files'].items():
        actual = ARCHIVE / 'reference_runtime.py' if Path(path).name == 'reference_runtime.py' else Path(path)
        p.require(p.digest(actual) == sha, 'FROZEN DEPENDENCY CHANGED: ' + path)
    p.require(p.digest(manifest['source']) == p.EXPECTED_SHA, 'SOURCE CHANGED')
    return manifest


def database_snapshot():
    path = REPO / 'backend/db.sqlite3'
    sha = p.digest(path)
    p.require(sha == DB_SHA, 'PRODUCTION DB HASH CHANGED; INVESTIGATE WITHOUT WRITING')
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as conn:
        conn.execute('PRAGMA query_only=ON')
        names = ['system_process', 'pde_routing', 'pde_routing_version', 'pde_routing_step', 'pde_engineering_rule_definition', 'pde_product_bom', 'pde_bom_item', 'pde_standard_capacity']
        counts = {name: conn.execute('SELECT COUNT(*) FROM "' + name + '"').fetchone()[0] for name in names}
    return {'sha256': sha, 'mode': 'READ_ONLY', 'counts': counts}


def compare_rows(rows, native):
    from differential import compare_result
    for row in rows:
        capture = native.get((row['case_id'], row['cell']))
        row['excel_raw_value'] = capture['excel_raw_value'] if capture else None
        row['native_capture_available'] = bool(capture)
        row['user_decision_requested'] = False
        if row['reference_status'] == 'BROKEN_DEPENDENCY':
            row['classification'] = 'BROKEN_SOURCE'
        elif row['reference_status'] == 'TECHNICAL_TRANSLATOR_DEFECT':
            row['classification'] = 'TECHNICAL_FAIL'
        elif capture:
            row['comparison'] = compare_result(row['code_result'], capture['excel_raw_value'], row['contract'])
            row['classification'] = 'PARITY_PASS' if row['comparison']['status'] == 'PASS' else 'TECHNICAL_FAIL'
        else:
            row['classification'] = None
            row['validation_status'] = 'NATIVE_CAPTURE_REQUIRED_NOT_PARITY_PASS'
    return rows


def trace_case(module, case, book, mapping, functions):
    """Observe the actual runtime; do not implement another evaluator."""
    class Trace(module.Context):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.stack, self.events = [], collections.deque(maxlen=240)
            self.cell_reads, self.errors, self.calls = collections.Counter(), collections.Counter(), collections.Counter()

        def cell(self, sheet, addr):
            key = sheet + '!' + addr
            self.cell_reads[key] += 1
            self.stack.append(key)
            try:
                return super().cell(sheet, addr)
            except Exception as exc:
                self.errors[type(exc).__name__ + ': ' + str(exc)] += 1
                if len(self.events) < 240 or addr in ('W39', 'I6', 'S9'):
                    self.events.append({'event': 'cell_error', 'path': list(self.stack), 'error': type(exc).__name__, 'message': str(exc)})
                raise
            finally:
                self.stack.pop()

        def call(self, name, args, **kw):
            self.calls[name] += 1
            try:
                result = super().call(name, args, **kw)
            except Exception as exc:
                if name in ('MATCH', 'VLOOKUP', 'SUMIFS', 'IFERROR', 'INDEX'):
                    self.events.append({'event': name, 'path': list(self.stack), 'error': type(exc).__name__, 'message': str(exc)})
                raise
            if name in ('MATCH', 'VLOOKUP', 'SUMIFS', 'IFERROR', 'INDEX'):
                if not isinstance(result, module.Range):
                    self.events.append({'event': name, 'path': list(self.stack), 'result': module.serialized(result)})
            return result

    overrides = {(x['sheet'], x['cell']): module.BLANK if x['type'] == 'blank' else x['value'] for x in case['overrides']}
    ctx = Trace(book, mapping, functions, overrides)
    outcomes = []
    for output in case['derived_outputs']:
        try:
            value = ctx.cell(*output['cell'].rsplit('!', 1))
            outcomes.append({'cell': output['cell'], 'value': module.serialized(value)})
        except Exception as exc:
            outcomes.append({'cell': output['cell'], 'error': type(exc).__name__, 'message': str(exc)})
    return {'outcomes': outcomes, 'calls': dict(ctx.calls), 'error_counts': dict(ctx.errors), 'cell_reads': dict(ctx.cell_reads), 'last_events': list(ctx.events), 'event_tail_limit': 240, 'native_intermediate_proof': 'NOT_CAPTURED_IN_BASELINE; INCLUDED_IN_SUPPLEMENT_BATCH'}


def recovery_register(family, candidates, book):
    by_id = {c['family_id']: c for c in candidates}
    rows = []
    for f in family['families']:
        if not f['broken']:
            continue
        row = {'family_id': f['family_id'], 'source_cells': f['source_cells'], 'formula': f['source_formula'], 'source_cell_count': len(f['source_cells']), 'source_write': 0, 'verified_recovery': False, 'user_decision_requested': False}
        if f['family_id'] in by_id:
            c = by_id[f['family_id']]
            p.require(c['source_cells'] == f['source_cells'], 'CANDIDATE IDENTITY MISMATCH')
            proof = []
            for e in c['evidence']:
                actual = book.sheets[e['sheet']][e['cell']]['formula']
                prior = book.sheets[e['sheet']][e['output_precedent']]['formula']
                p.require(actual == e['formula'] and prior == e['precedent_formula'], 'HOMOLOGOUS SOURCE DRIFT')
                proof.append({'sheet': e['sheet'], 'cell': e['cell'], 'formula': actual, 'output_precedent': e['output_precedent'], 'precedent_formula': prior})
            row.update(status='RECOVERABLE_SOURCE_CANDIDATE', candidate_formula=c['candidate_formula'], mapping=c['mapping'], source_evidence=proof, unresolved='S guarded area versus homologous T unguarded area; native synthetic/boundary and real-row candidate values required. Candidate native parity does NOT prove original business correctness.')
        else:
            row.update(status='SOURCE_RECOVERY_INVESTIGATION_OPEN', unresolved='No frozen reconstruction candidate. Inspect adjacent/homologous formulas, source headers and structural facts before any U01-U04 claim.')
        rows.append(row)
    return rows


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    m = frozen()
    db_before = database_snapshot()
    modules = p.reference(m)
    family, cases = p.assets(m)
    plan = p.read(BASELINE / 'RUN_CASE_PLAN.json')
    golden = p.read(BASELINE / 'EXCEL_NATIVE_GOLDEN.json')
    native = p.validate_native(p.read(BASELINE / 'NATIVE_EXCEL_RUN.json'), golden, plan, p.digest(BASELINE / 'RUN_CASE_PLAN.json'))
    historical = p.read(BASELINE / 'DIFFERENTIAL_RESULTS.json')
    old_rows = historical['results']
    out = CLOSURE / 'attempts' / (p.now().replace(':', '').replace('+', '_') + '-' + uuid.uuid4().hex[:8])
    out.mkdir(parents=True, exist_ok=False)
    p.write(out / 'CONTROL_SHEET.json', {'instruction': 'c91c7c1f-758d-4aae-8d0e-b5ab6f6fa686', 'continuation': True, 'baseline': str(BASELINE), 'baseline_manifest_sha': RUN_MANIFEST_SHA, 'production_before': db_before, 'allowed': ['generic reference semantics', 'dependency evaluator', 'pure technical tests', 'isolated native supplemental validation'], 'forbidden': ['original workbook changes', 'production writes', 'migration', 'cached-value oracle', 'relaxed comparator'], 'manual_business_decision': 'U01-U04 ONLY', 'overall': 'NOT_COMPLETED'})
    print('Recomparing frozen native 280...', flush=True)
    rows = compare_rows(p.evaluate_reference(m, plan), native)
    by_family = []
    for fid in sorted({r['formula_family'] for r in rows}):
        members = [r for r in rows if r['formula_family'] == fid]
        broken = any(r['classification'] == 'BROKEN_SOURCE' for r in members)
        passed = all(r['classification'] == 'PARITY_PASS' for r in members)
        by_family.append({'family_id': fid, 'case_count': len(members), 'counts': dict(collections.Counter(r['classification'] for r in members)), 'parity_eligible_for_captured_cases': not broken, 'all_case_pass': passed})
    eligible = [f for f in by_family if f['parity_eligible_for_captured_cases']]
    p.require(eligible and all(f['all_case_pass'] for f in eligible), 'LEVEL 1A HAS TECHNICAL FAIL; DO NOT START RECOVERY')
    old_diff = [r for r in old_rows if r['classification'] == 'UNCLASSIFIED_DIFFERENCE']
    old_broken = [r for r in old_rows if r['classification'] == 'BROKEN_DEPENDENCY']
    current_index = {(r['case_id'], r['cell']): r for r in rows}
    changes = []
    for old in old_diff:
        new = current_index[(old['case_id'], old['cell'])]
        p.require(new['classification'] == 'PARITY_PASS', 'ORIGINAL DIFFERENCE REMAINS')
        case = next(c for c in plan['cases'] if c['case_id'] == old['case_id'])
        cell = old['cell'].rsplit('!', 1)[1]
        root = 'SUMIFS_CRITERIA_ERROR_CELL_WAS_PROPAGATED_INSTEAD_OF_NONMATCH' if cell == 'I6' else 'EXACT_LOOKUP_BLANK_RANGE_ENTRY_WAS_FABRICATED_AS_MATCH; DOWNSTREAM_TYPE_PROPAGATION'
        changes.append({'case_id': old['case_id'], 'cell': old['cell'], 'formula': case['derived_outputs'][0]['formula'], 'source_input_facts': case['input_facts'], 'native_overrides': next(r['overrides'] for r in golden['results'] if r['case_id'] == old['case_id']), 'old_code': old['code_result'], 'native': new['excel_raw_value'], 'new_code': new['code_result'], 'classification': 'TECHNICAL_TRANSLATOR_DEFECT', 'resolution': new['classification'], 'root_cause': root, 'native_intermediate_semantics': 'SUPPLEMENTARY_CAPTURE_REQUIRED; ORIGINAL OUTPUT PARITY IS PROVEN', 'comparison': new['comparison']})
    book = modules['workbook_source'].SourceBook(plan['workbook_copy'])
    classified = []
    for old in old_broken:
        new = current_index[(old['case_id'], old['cell'])]
        sheet, addr = old['cell'].rsplit('!', 1)
        formula = book.sheets[sheet][addr]['formula']
        row = {'family_id': old['formula_family'], 'cell': old['cell'], 'formula': formula, 'native': new['excel_raw_value'], 'before_reason': old.get('reason'), 'after': new}
        if new['classification'] == 'PARITY_PASS':
            row.update(category='B_FALSE_DEPENDENCY_LAZY_EVALUATION_DEFECT', path='S9 -> SUM(W10:W1000) -> W39 -> first MATCH(X39,G:G,0) raises #N/A -> IFERROR empty; later MATCH(#REF!,headers,0) unvisited', branch_claim='REFERENCE_EXECUTION_TRACE; native numeric result establishes the old blanket dependency block was false')
        else:
            p.require(new['excel_raw_value'] == {'type': 'error', 'value': '#REF!'}, 'NATIVE SOURCE DAMAGE NOT ESTABLISHED')
            dependency = new.get('reason', '').removesuffix(' visited #REF!')
            ds, da = dependency.rsplit('!', 1)
            p.require(book.sheets[ds][da]['formula'] == '=#REF!' and da in formula, 'DIRECT DAMAGED PREDECESSOR NOT PROVEN')
            row.update(category='A_TRUE_SOURCE_DAMAGE', dependency_path=[old['cell'], dependency, '#REF!'], dependency_formula=book.sheets[ds][da]['formula'])
        classified.append(row)
    old_by_family = collections.defaultdict(list)
    for r in old_rows:
        old_by_family[r['formula_family']].append(r)
    old_eligible = [rs for rs in old_by_family.values() if not any(r['classification'] == 'BROKEN_DEPENDENCY' for r in rs)]
    gate = {'baseline_historical_counts': dict(collections.Counter(r['classification'] for r in old_rows)), 'text_intact_families': len(by_family), 'initial_eligible': len(old_eligible), 'initial_all_case_pass': sum(all(r['classification'] == 'PARITY_PASS' for r in rs) for rs in old_eligible), 'current_eligible': len(eligible), 'current_all_case_pass': sum(f['all_case_pass'] for f in eligible), 'technical_fail': sum(r['classification'] == 'TECHNICAL_FAIL' for r in rows), 'current_case_counts': dict(collections.Counter(r['classification'] for r in rows)), 'LEVEL_1A': 'PASS_FOR_FROZEN_NATIVE_CASES', 'LEVEL_1B': 'CLASSIFIED', 'denominator_change': 'S9 family reclassified from false dependency to eligible after visited-branch evaluation; not an ignored case.', 'broken_classification_counts': dict(collections.Counter(r['category'] for r in classified)), 'families': by_family, 'new_micro_semantics_proofs': 'PENDING_NATIVE_SUPPLEMENT; NO GLOBAL EXCEL_COMPATIBILITY CLAIM'}
    p.write(out / 'FROZEN_280_RECOMPARISON.json', {'results': rows, 'gates': gate})
    p.write(out / 'TEN_DIFFERENCE_RESOLUTIONS.json', changes)
    p.write(out / 'THIRTEEN_DEPENDENCY_CLASSIFICATIONS.json', classified)
    print(json.dumps(gate | {'families': 'omitted from console'}, ensure_ascii=False), flush=True)
    spec = importlib.util.spec_from_file_location('pce_frozen_runtime_before', ARCHIVE / 'reference_runtime.py')
    old_rt = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = old_rt
    spec.loader.exec_module(old_rt)
    trace_ids = {r['case_id'] for r in old_diff} | {r['case_id'] for r in old_broken if current_index[(r['case_id'], r['cell'])]['classification'] == 'PARITY_PASS'}
    for case in plan['cases']:
        if case['case_id'] in trace_ids:
            print('Trace ' + case['case_id'], flush=True)
            p.write(out / ('TRACE_' + case['case_id'] + '.json'), {'case': case, 'old': trace_case(old_rt, case, book, family['cell_to_family'], modules['generated_reference'].FUNCTIONS), 'new': trace_case(modules['reference_runtime'], case, book, family['cell_to_family'], modules['generated_reference'].FUNCTIONS)})
    real = [c for c in cases['cases'] if c['level'] in (2, 3)]
    # Frozen real-row cases, not arbitrary row ranges or a four-field subset.
    source_real = p.read(EVIDENCE / 'SOURCE_REAL_ROWS.json')
    p.require({(c['source_sheet'], c['source_row']) for c in real} == {(s, r) for s, rs in source_real.items() for r in rs}, 'REAL ROW CASE COVERAGE MISMATCH')
    base_captures = {}
    for c in plan['cases']:
        if not c['overrides']:
            for o in c['derived_outputs']:
                base_captures[o['cell']] = native[(c['case_id'], o['cell'])]
    real_native = {(c['case_id'], o['cell']): base_captures[o['cell']] for c in real for o in c['derived_outputs'] if o['cell'] in base_captures}
    print('Evaluating all real-row derived outputs...', flush=True)
    real_rows = compare_rows(p.evaluate_reference(m, plan | {'cases': real}), real_native)
    p.write(out / 'REAL_ROW_OUTPUT_MATRIX.json', {'row_count': len(real), 'source_rows_by_sheet': dict(collections.Counter(c['source_sheet'] for c in real)), 'output_count': len(real_rows), 'native_available': sum(r['native_capture_available'] for r in real_rows), 'counts': dict(collections.Counter(r['classification'] or 'PENDING_NATIVE' for r in real_rows)), 'results': real_rows, 'complete_native_validation': all(r['native_capture_available'] or r['classification'] == 'BROKEN_SOURCE' for r in real_rows)})
    boundaries = [c for c in cases['cases'] if c['level'] == 1 and c['overrides']]
    print('Evaluating existing branch/boundary cases...', flush=True)
    boundary_rows = compare_rows(p.evaluate_reference(m, plan | {'cases': boundaries}), native)
    p.write(out / 'BOUNDARY_OUTPUT_MATRIX.json', {'case_count': len(boundaries), 'counts': dict(collections.Counter(r['classification'] or 'PENDING_NATIVE' for r in boundary_rows)), 'results': boundary_rows})
    recovery = recovery_register(family, p.read(EVIDENCE / 'CANDIDATE_FORMULA_RECONSTRUCTION.json'), book)
    p.write(out / 'BROKEN_FAMILY_RECOVERY_REGISTER.json', recovery)
    db_after = database_snapshot()
    p.require(db_before == db_after, 'DATABASE CHANGED DURING AUDIT')
    frozen()
    summary = {'created_at': p.now(), 'baseline_unchanged': True, 'baseline_manifest_sha': RUN_MANIFEST_SHA, 'source_unchanged': True, 'production_after': db_after, 'production_write': 0, 'migration': 0, 'domain_formalization': 'NOT_ENTERED', 'gates': gate, 'real_rows': len(real), 'real_outputs': len(real_rows), 'real_native_available': len(real_native), 'real_counts': dict(collections.Counter(r['classification'] or 'PENDING_NATIVE' for r in real_rows)), 'boundary_counts': dict(collections.Counter(r['classification'] or 'PENDING_NATIVE' for r in boundary_rows)), 'recovery_families': len(recovery), 'recovery_candidates': sum(r['status'] == 'RECOVERABLE_SOURCE_CANDIDATE' for r in recovery), 'code_hashes': {str(path): p.digest(path) for path in Path(__file__).parent.glob('*.py')}, 'original_instruction_overall': 'NOT_COMPLETED', 'native_supplement_needed': True, 'manual_business_decisions': [], 'stop_condition_C': 'NOT_YET_SATISFIED_NATIVE_OUTPUT_COVERAGE_REQUIRED'}
    p.write(out / 'SUMMARY.json', summary)
    p.write(out / 'AUDIT_MANIFEST.json', {'files': {x.name: p.digest(x) for x in out.iterdir() if x.is_file()}, 'self_hash_excluded': True})
    print(json.dumps({'audit': str(out), 'real_counts': summary['real_counts'], 'boundary_counts': summary['boundary_counts'], 'recovery_families': len(recovery)}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()

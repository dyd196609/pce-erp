"""Append-only R2 audit of frozen Excel evidence. Never rewrites a Run."""
from __future__ import annotations
import collections
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / 'scripts/excel_parity'), str(REPO / 'tools/excel-golden-runner')]
import package_support as p
from technical_closure import frozen, database_snapshot, CLOSURE, BASELINE, recovery_register
from differential import compare_result
from workbook_source import SourceBook

ROOT = CLOSURE / 'native-supplement-r2'
ARCHIVE = ROOT / 'before-code'
RUN = p.ROOT / 'runs/20260909T010756709Z-772c0971'
RUN_SHA = '9A0AF062D4E8F6ACC64A57BF452F36935110783D238DA830FF76E2AC795E88E3'
ERRORS = {'#NULL!', '#DIV/0!', '#VALUE!', '#REF!', '#NAME?', '#NUM!', '#N/A', '#SPILL!', '#GETTING_DATA'}


def count(rows, key='classification'):
    return dict(collections.Counter(r[key] for r in rows))


def verify():
    old = frozen()
    p.require(p.digest(RUN / 'RUN_MANIFEST.json') == RUN_SHA, 'NEW NATIVE MANIFEST DRIFT')
    rm = p.read(RUN / 'RUN_MANIFEST.json')
    p.verify_hashes(rm['files'], RUN)
    m = p.read(ARCHIVE / 'RUNNER_MANIFEST.json')
    p.require(p.digest(ARCHIVE / 'RUNNER_MANIFEST.json') == rm['package_manifest_sha'], 'EXECUTED PACKAGE IDENTITY')
    p.verify_hashes(m['files'], ARCHIVE)
    for path, sha in m['frozen_files'].items():
        saved = ARCHIVE / Path(path).name
        p.require(p.digest(saved if saved.exists() else path) == sha, 'EXECUTED DEPENDENCY DRIFT ' + path)
    p.require(p.digest(m['source']) == p.EXPECTED_SHA, 'SOURCE DRIFT')
    # Read every JSON in the Run; the byte copy and complete log/JSON bytes are
    # all verified above. No mutation of historical validation_status=BLOCKED.
    documents = {f.name: p.read(f) for f in RUN.glob('*.json')}
    p.validate_output_files(RUN)
    plan = documents['RUN_CASE_PLAN.json']
    from closure_batch import build
    rebuilt = build(m)
    for field in ('cases', 'probe_sheet', 'technical_source_dependencies'):
        p.require(plan[field] == rebuilt[field], 'SOURCE PLAN REBUILD DRIFT: ' + field)
    native = p.validate_native(documents['NATIVE_EXCEL_RUN.json'], documents['EXCEL_NATIVE_GOLDEN.json'], plan, p.digest(RUN / 'RUN_CASE_PLAN.json'))
    identity = []
    for c in plan['cases']:
        for o in c['derived_outputs']:
            captured = native[(c['case_id'], o['cell'])]
            identity.append({'case_id': c['case_id'], 'cell': o['cell'], 'requested_formula': o['formula'], 'captured_formula': captured['formula'], 'identity': p.formula_identity(o['formula'], captured['formula'])})
    return old, m, plan, native, {'run_directory': str(RUN), 'run_manifest_sha': RUN_SHA, 'files_verified': len(rm['files']), 'json_documents_read': list(documents), 'output_schema': 'PASS', 'case_count': len(plan['cases']), 'output_count': len(native), 'native_execution': documents['NATIVE_EXCEL_RUN.json'], 'formula_identity_counts': count(identity, 'identity'), 'formula_identity': identity, 'historical_run_not_modified': True}


def compare(rows, native):
    for row in rows:
        capture = native.get((row['case_id'], row['cell']))
        row.update(excel_raw_value=capture['excel_raw_value'] if capture else None, native_capture_available=bool(capture))
        if row['reference_status'] == 'BROKEN_DEPENDENCY':
            row['classification'] = 'BROKEN_SOURCE'
        elif row['reference_status'] != 'EVALUATED_NOT_NATIVE_VERIFIED':
            row['classification'] = 'TECHNICAL_FAIL'
        elif capture is None:
            row['classification'] = 'NATIVE_CAPTURE_REQUIRED'
        elif capture['excel_raw_value']['type'] == 'error' and capture['excel_raw_value']['value'] not in ERRORS:
            row['classification'] = 'NATIVE_ERROR_CODE_UNAVAILABLE'
            row['reason'] = 'Frozen runner serialized displayed hashes, not the native CVError. Never infer the native code from reference output.'
        else:
            row['comparison'] = compare_result(row['code_result'], capture['excel_raw_value'], row['contract'])
            row['classification'] = 'PARITY_PASS' if row['comparison']['status'] == 'PASS' else 'TECHNICAL_FAIL'
    return rows


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    before = database_snapshot()
    old, m, plan, native, integrity = verify()
    out = ROOT / 'attempts' / (p.now().replace(':', '').replace('+', '_') + '-' + uuid.uuid4().hex[:8])
    out.mkdir(parents=True, exist_ok=False)
    p.write(out / 'RUN_INTEGRITY.json', integrity)
    print('AUDIT_DIRECTORY=' + str(out), flush=True)
    print('Fresh comparison of all 4487 native outputs...', flush=True)
    rows = compare(p.evaluate_reference(m, plan, progress=True), native)
    p.write(out / 'SUPPLEMENT_OUTPUT_MATRIX.json', {'counts': count(rows), 'cohorts': {k: count([r for r in rows if r['cohort'] == k]) for k in sorted({r['cohort'] for r in rows})}, 'results': rows})
    # Initial R2 differences are reconstructed from the sealed precheck, not
    # silently replaced by the fixed reference. Precheck is never a Golden.
    pre = p.ROOT / 'prechecks/20260908T215120299Z-74336b5b'
    p.verify_hashes(p.read(pre / 'RUN_MANIFEST.json')['files'], pre)
    p.require(p.read(pre / 'PACKAGE_PRECHECK.json')['package_manifest_sha'] == p.digest(ARCHIVE / 'RUNNER_MANIFEST.json'), 'PRECHECK PACKAGE DRIFT')
    p.require(p.read(pre / 'RUN_CASE_PLAN.json')['cases'] == plan['cases'], 'PRECHECK CASE DRIFT')
    prior = compare(p.read(pre / 'REFERENCE_PRECHECK.json')['results'], native)
    p.write(out / 'NEW_DIFFERENCE_RESOLUTION.json', {'before_counts': count(prior), 'after_counts': count(rows), 'changed': [{'before': a, 'after': b} for a, b in zip(prior, rows) if a['classification'] != b['classification'] or a['code_result'] != b['code_result']], 'capture_defects': [r for r in rows if r['classification'] == 'NATIVE_ERROR_CODE_UNAVAILABLE']})
    baseplan = p.read(BASELINE / 'RUN_CASE_PLAN.json')
    basenative = p.validate_native(p.read(BASELINE / 'NATIVE_EXCEL_RUN.json'), p.read(BASELINE / 'EXCEL_NATIVE_GOLDEN.json'), baseplan, p.digest(BASELINE / 'RUN_CASE_PLAN.json'))
    base = compare(p.evaluate_reference(old, baseplan, progress=True), basenative)
    p.write(out / 'FROZEN_280_RECOMPARISON.json', {'counts': count(base), 'results': base})
    family, manifest = p.assets(m)
    by_key = {(r['case_id'], r['cell']): r for r in base + rows}
    cases = manifest['cases']
    l1 = [by_key[(c['case_id'], o['cell'])] for c in cases if c['level'] == 1 for o in c['derived_outputs']]
    intact = {f['family_id'] for f in family['families'] if not f['broken']}
    families = []
    for fid in sorted(intact):
        members = [r for r in l1 if r['formula_family'] == fid]
        p.require(members, 'INTACT FAMILY HAS NO CASE')
        families.append({'family_id': fid, 'counts': count(members), 'eligible': not any(r['classification'] == 'BROKEN_SOURCE' for r in members), 'all_case_pass': all(r['classification'] == 'PARITY_PASS' for r in members)})
    eligible = [f for f in families if f['eligible']]
    p.require(all(f['all_case_pass'] for f in eligible), 'LEVEL 1A NOT CLOSED: RECOVERY FORBIDDEN')
    l1_report = {'all_source_families': len(family['families']), 'intact_families': len(intact), 'eligible_families': len(eligible), 'all_eligible_pass': all(f['all_case_pass'] for f in eligible), 'case_count': len(l1), 'counts': count(l1), 'families': families, 'results': l1}
    p.write(out / 'LEVEL1_COMPLETE_MATRIX.json', l1_report)
    original = p.read(BASELINE / 'DIFFERENTIAL_RESULTS.json')['results']
    ten = [{'historical': r, 'current': by_key[(r['case_id'], r['cell'])]} for r in original if r['classification'] == 'UNCLASSIFIED_DIFFERENCE']
    p.require(all(x['current']['classification'] == 'PARITY_PASS' for x in ten), 'ORIGINAL DIFFERENCE REGRESSION')
    thirteen = [{'historical': r, 'current': by_key[(r['case_id'], r['cell'])], 'category': 'A_TRUE_SOURCE_DAMAGE' if by_key[(r['case_id'], r['cell'])]['classification'] == 'BROKEN_SOURCE' else 'B_FALSE_DEPENDENCY_FIXED'} for r in original if r['classification'] == 'BROKEN_DEPENDENCY']
    p.write(out / 'ORIGINAL_10_AND_13.json', {'ten': ten, 'thirteen': thirteen})
    realcases = [c for c in cases if c['level'] in (2, 3)]
    source_real = p.read(p.EVIDENCE / 'SOURCE_REAL_ROWS.json') if hasattr(p, 'EVIDENCE') else p.read(CLOSURE.parent / 'SOURCE_REAL_ROWS.json')
    p.require({(c['source_sheet'], c['source_row']) for c in realcases} == {(s, r) for s, rr in source_real.items() for r in rr}, 'REAL ROW SET DRIFT')
    real = [by_key[(c['case_id'], o['cell'])] for c in realcases for o in c['derived_outputs']]
    boundary = [by_key[(c['case_id'], o['cell'])] for c in cases if c['level'] == 1 and c['overrides'] for o in c['derived_outputs']]
    p.write(out / 'REAL_ROW_OUTPUT_MATRIX.json', {'row_count': len(realcases), 'rows_by_sheet': dict(collections.Counter(c['source_sheet'] for c in realcases)), 'output_count': len(real), 'counts': count(real), 'row_summaries': [{'sheet': c['source_sheet'], 'row': c['source_row'], 'counts': count([by_key[(c['case_id'], o['cell'])] for o in c['derived_outputs']])} for c in realcases], 'results': real})
    p.write(out / 'BOUNDARY_OUTPUT_MATRIX.json', {'case_count': len(boundary), 'counts': count(boundary), 'results': boundary})
    p.require(all(r['classification'] in ('PARITY_PASS', 'BROKEN_SOURCE') for r in real + boundary), 'REAL/BOUNDARY VALIDATION INCOMPLETE')
    p.write(out / 'MICRO_NATIVE_PROOFS.json', [r for r in rows if r['cohort'] == 'MICRO_SEMANTICS'])
    p.write(out / 'SOURCE_INTERMEDIATE_PROOFS.json', [r for r in rows if r['cohort'] == 'NATIVE_SOURCE_INTERMEDIATES'])
    candidates = p.read(CLOSURE.parent / 'CANDIDATE_FORMULA_RECONSTRUCTION.json')
    register = recovery_register(family, candidates, SourceBook(m['source']))
    guards = []
    for c in plan['cases']:
        if c['cohort'] != 'RECOVERY_AREA_GUARD':
            continue
        values = [native[(c['case_id'], o['cell'])]['excel_raw_value'] for o in c['derived_outputs']]
        fid = next(x['family_id'] for x in candidates if c['case_id'].startswith('AREA_GUARD_' + x['family_id'] + '_'))
        pairs = [compare_result(values[0], v, {'comparison': 'TYPED_EXACT'}) for v in values[1:]]
        guards.append({'case_id': c['case_id'], 'family_id': fid, 'scenario': c['case_id'].removeprefix('AREA_GUARD_' + fid + '_'), 'inputs': c['overrides'], 'candidate_native': values[0], 'homologous_native': values[1:], 'pair_results': pairs, 'all_homologs_equal': all(x['status'] == 'PASS' for x in pairs)})
    p.write(out / 'RECOVERY_GUARD_NATIVE_COMPARISON.json', {'cases': len(guards), 'equal': sum(x['all_homologs_equal'] for x in guards), 'different': sum(not x['all_homologs_equal'] for x in guards), 'different_by_scenario': dict(collections.Counter(x['scenario'] for x in guards if not x['all_homologs_equal'])), 'results': guards})
    for item in register:
        fid = item['family_id']
        if item['status'] != 'RECOVERABLE_SOURCE_CANDIDATE':
            continue
        members = [r for r in rows if r['candidate_family'] == fid]
        fg = [g for g in guards if g['family_id'] == fid]
        item.update(candidate_native_reference_counts=count(members), guard_case_count=len(fg), guard_native_reference_counts=count([r for r in rows if r['case_id'].startswith('AREA_GUARD_' + fid + '_')]), positive_control_equal=all(g['all_homologs_equal'] for g in fg if g['scenario'] == 'POSITIVE_CONTROL'), guard_differences=[g['scenario'] for g in fg if not g['all_homologs_equal']], status='NATIVE_VERIFIED_CANDIDATE_NOT_BUSINESS_FORMALIZED', unresolved='Candidate/native parity proven; homologous guard differences documented, not evidence of disagreement with genuine historical business output. Original erased reference is not recoverable uniquely from parity alone.')
    p.write(out / 'BROKEN_FAMILY_RECOVERY_REGISTER.json', register)
    after = database_snapshot()
    p.require(before == after, 'PRODUCTION CHANGED')
    verify()
    summary = {'run_id': RUN.name, 'audit': str(out), 'timestamp': p.now(), 'supplement_counts': count(rows), 'baseline_counts': count(base), 'level1_counts': count(l1), 'level1_intact': len(intact), 'level1_eligible': len(eligible), 'level1_all_eligible_pass': True, 'real_rows': len(realcases), 'real_counts': count(real), 'boundary_counts': count(boundary), 'dependency_classifications': count(thirteen, 'category'), 'candidate_outputs': count([r for r in rows if r['cohort'].startswith('RECOVERY_')]), 'candidate_families': len(candidates), 'guard_equal': sum(g['all_homologs_equal'] for g in guards), 'guard_different': sum(not g['all_homologs_equal'] for g in guards), 'source_sha': p.digest(m['source']), 'production_after': after, 'production_write': 0, 'domain_formalization': 'NOT_ENTERED', 'original_instruction_overall': 'NOT_COMPLETED', 'code_hashes': {str(f): p.digest(f) for folder in [Path(__file__).parent, p.ROOT] for f in folder.glob('*') if f.suffix in ('.py', '.ps1', '.json', '.cmd') and f.is_file()}}
    p.write(out / 'SUMMARY.json', summary)
    p.write(out / 'AUDIT_MANIFEST.json', {'files': {f.name: p.digest(f) for f in out.iterdir() if f.is_file()}, 'self_hash_excluded': True})
    print(__import__('json').dumps(summary | {'code_hashes': 'see file'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()

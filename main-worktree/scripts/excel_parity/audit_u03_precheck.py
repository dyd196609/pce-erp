"""Cross-check recovery expressions against an independent Decimal/design model."""
import collections
import json
import sys
from decimal import Decimal
from pathlib import Path
from u03_recovery_audit import OUT, DB, DB_SHA, p
from recovery_semantics import resolve


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    pre = Path(sys.argv[1])
    m = p.load_manifest()
    report = p.read(pre / 'PACKAGE_PRECHECK.json')
    p.require(report['status'] == 'PASS', 'FULL PACKAGE PRECHECK REQUIRED')
    plan = p.read(pre / 'RUN_CASE_PLAN.json')
    results = p.read(pre / 'REFERENCE_PRECHECK.json')['results']
    audit = p.read(OUT / 'BOARD_STOCK_AND_REAL_ROW_AUDIT.json')
    stocks = audit['stocks']
    values = {(r['case_id'], r['semantic_name']): r['code_result'] for r in results}
    checks = []
    for r in audit['rows']:
        key = 'U03_REAL_TRI_' + str(r['row'])
        actual = values[(key, 'R3_FORMAL_MATERIAL_ROW_' + str(r['row']))]['value']
        p.require(actual == r['resolution']['status'], 'REAL ROW STATUS != INDEPENDENT RESOLVER')
        checks.append({'case_id': key, 'status': actual, 'independent_result': 'PASS', 'business_resolved': False})
    specs = sorted({(s['length'], s['width'], s['thickness']) for s in stocks})
    reps = [next(s for s in stocks if (s['length'], s['width'], s['thickness']) == dims) for dims in specs]
    for c in plan['cases']:
        if c['cohort'] != 'R1_R3_R4_R5_R6_SYNTHETIC_BOUNDARIES':
            continue
        facts = {o['cell'][0]: o['value'] for o in c['overrides']}
        expected = resolve([facts[k] for k in 'DEF'], reps, [s['material_id'] for s in reps] if facts['I'] else None, facts['H'])
        actual = values[(c['case_id'], 'SYNTHETIC_SELECTED_MATERIAL_ID')]['value']
        wanted = expected['material_id'] if expected['status'] == 'RESOLVED' else 'BLOCKED_APPLICABILITY' if not facts['I'] else 'BLOCKED_NO_OR_AMBIGUOUS_SPEC'
        p.require(actual == wanted, 'SYNTHETIC RESOLVER MISMATCH: ' + c['case_id'])
        chain = values[(c['case_id'], 'SYNTHETIC_SELECTION_TO_NET_TO_BUCKET_AGGREGATE')]['value']
        if expected['status'] == 'RESOLVED':
            # Independent exact Decimal arithmetic checks the chain's semantics;
            # raw Native parity still uses its unchanged strict comparator.
            desired = Decimal(str(facts['D'])) * Decimal(str(facts['E'])) * Decimal(str(facts['G'])) * 3 / 1000000
            p.require(abs(Decimal(str(chain)) - desired) < Decimal('0.000000001'), 'CHAIN SEMANTIC CROSSCHECK FAILED')
        else:
            p.require(chain == 'BLOCKED_UNRESOLVED_REQUIREMENTS', 'BLOCKED REQUIREMENT SILENTLY AGGREGATED')
        checks.append({'case_id': c['case_id'], 'independent_result': 'PASS', 'source_type': 'SIMULATED_FOR_TEST'})
    ledger = [r for r in results if r['cohort'] in ('R4_R5_R6_AGGREGATE_LEDGER', 'R5_R6_POLICY_AND_SCOPE_GATES') and not r['semantic_name'].startswith('REAL_EDGE_COUNT')]
    p.require(all(r['code_result']['type'] != 'error' for r in ledger), 'NEW RECOVERY LEDGER ERROR')
    p.require(p.read(pre / 'NATIVE_EXCEL_RUN.json')['mode'] == 'PACKAGE_PRECHECK', 'PRECHECK MUST NOT CLAIM NATIVE')
    p.require(p.digest(DB) == DB_SHA and p.digest(m['source']) == p.EXPECTED_SHA, 'PROTECTION DRIFT')
    for row in p.read(OUT / 'BEFORE_CODE_MANIFEST.json'):
        p.require(p.digest(row['archive']) == row['sha256'], 'ARCHIVE DRIFT')
    output = {'timestamp': p.now(), 'package_manifest_sha': p.digest(p.ROOT / 'RUNNER_MANIFEST.json'), 'precheck': str(pre),
        'native_executed': False, 'new_native_parity': 'PENDING', 'independent_checks': checks, 'ledger': ledger,
        'case_count': plan['selected_case_count'], 'output_count': plan['selected_output_count'],
        'reference_status_counts': dict(collections.Counter(r['reference_status'] for r in results)),
        'cohort_counts': dict(collections.Counter(c['cohort'] for c in plan['cases'])), 'python_tests': report['unit_test_count'],
        'source_sha': p.EXPECTED_SHA, 'db_sha': DB_SHA, 'production_write': 0, 'business_ready': False,
        'code_equals_package': True, 'domain_rule_formalization': 'NOT_ENTERED'}
    target = OUT / ('TECHNICAL_PRECHECK_AUDIT-' + pre.name + '.json')
    p.require(not target.exists(), 'APPEND ONLY AUDIT')
    p.write(target, output)
    print(json.dumps({k: v for k, v in output.items() if k not in ('independent_checks', 'ledger')}, ensure_ascii=False, indent=2))
    print('LEDGER', json.dumps([{k: r[k] for k in ('semantic_name','code_result')} for r in ledger], ensure_ascii=False))
    print('AUDIT', str(target))


if __name__ == '__main__':
    main()

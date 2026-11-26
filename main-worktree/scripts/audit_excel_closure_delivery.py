"""Read-only delivery audit; append-only technical evidence, never ERP writes."""
import collections
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / 'scripts/excel_parity'), str(REPO / 'tools/excel-golden-runner')]
import package_support as p
from technical_closure import frozen, database_snapshot, CLOSURE, BASELINE
from workbook_source import SourceBook


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    original = frozen()
    m = p.load_manifest()
    paths = sorted((p.ROOT / 'prechecks').glob('*/PACKAGE_PRECHECK.json'))
    precheck_path = paths[-1]
    precheck = p.read(precheck_path)
    p.require(precheck['status'] == 'PASS', 'LATEST FULL PACKAGE PRECHECK NOT PASS')
    p.require(precheck['package_manifest_sha'] == p.digest(p.ROOT / 'RUNNER_MANIFEST.json'), 'TESTED PACKAGE != DELIVERED PACKAGE')
    p.require(precheck['tested_files'] == m['files'], 'TESTED FILE SET MISMATCH')
    precheck_run = p.read(precheck_path.parent / 'NATIVE_EXCEL_RUN.json')
    p.require(precheck_run['mode'] == 'PACKAGE_PRECHECK' and precheck_run['execution_status'] == 'NOT_EXECUTED', 'PRECHECK MISREPRESENTED AS NATIVE')
    p.require(precheck_run['original_unchanged'] and precheck_run['run_copy_sha_after'] == p.EXPECTED_SHA, 'PRECHECK SOURCE PROTECTION FAILED')
    p.verify_hashes(p.read(precheck_path.parent / 'RUN_MANIFEST.json')['files'], precheck_path.parent)
    audit_path = Path(m['revision']['audit'])
    p.require(p.digest(audit_path) == m['revision']['audit_sha'], 'CLOSURE AUDIT DRIFT')
    audit = p.read(audit_path)
    rt_path = str(REPO / 'scripts/excel_parity/reference_runtime.py')
    p.require(audit['code_hashes'][rt_path] == p.digest(rt_path), 'PARITY-AUDITED RUNTIME != DELIVERED RUNTIME')
    db = database_snapshot()
    p.require(db == audit['production_after'], 'PRODUCTION DRIFT')
    book = SourceBook(m['source'])
    source_review = []

    def fact(sheet, addr):
        cell = book.sheets[sheet].get(addr, {})
        return {'sheet': sheet, 'cell': addr, 'formula': cell.get('formula'), 'constant_value': cell.get('value') if not cell.get('formula') else None, 'cached_value_used': False}

    source_review.append({'object': '房门单 W39:W520', 'family_count': 1, 'cell_count': 482, 'evidence': [fact('房门单', a) for a in ['W10', 'W38', 'V39', 'W39', 'X39']], 'conclusion': 'W39 index column selector is erased. Earlier W38 is geometric area, W39 is a different catalog lookup template; copying W38 down is NOT a proven recovery. Native S9 success proves only the damaged branch is unvisited for captured input.', 'next': 'Use new source intermediate/lookup probe capture and source template alignment; no invented header selector.'})
    source_review.append({'object': '三合一生产单 AG29:AR29', 'family_count': 12, 'evidence': [fact('三合一生产单', a) for a in ['AA5', 'AB5', 'AA7', 'AG29', 'AR29', 'AG30', 'AE29', 'AE30', 'AG31', 'AR31']], 'conclusion': 'Twelve erased direct references feed existing *1.2 issue quantities. Multiple source length/thickness buckets and header/formula column drift mean a simple guessed SUM is not established.', 'next': 'Reconstruct correct bucket/aggregation linkage only after candidate bucket outputs and source structure are checked; preserve erased originals.'})
    source_review.append({'object': '三合一生产单 AV30', 'family_count': 1, 'evidence': [fact('三合一生产单', a) for a in ['AS30', 'AV30', 'AW30', 'Q7', 'S7']], 'conclusion': 'Veneer issue label and *1.2 remain; the base reference was erased. Net area/paint area/sides cannot be inferred solely from label.', 'next': 'Search compatible source material-role and homologous veneer basis; no numeric authority from rough BOM.'})
    source_review.append({'object': '三合一生产单 AV31', 'family_count': 1, 'evidence': [fact('三合一生产单', a) for a in ['AS31', 'AV31', 'AW31', 'R7']], 'conclusion': 'Edge-use reference erased; source summary unit is ㎡. Do not silently equate it to the row perimeter or correct the source unit.', 'next': 'Check original role/unit/aggregation semantics; U03 not asserted before sources are exhausted.'})
    ref = p.read(precheck_path.parent / 'REFERENCE_PRECHECK.json')['results']
    pending_recovery = [r for r in ref if r['cohort'].startswith('RECOVERY_')]
    report = {
        'timestamp': p.now(), 'status': 'TECHNICAL_PACKAGE_PRECHECK_PASS_NEW_NATIVE_CAPTURE_REQUIRED',
        'original_instruction_overall': 'NOT_COMPLETED', 'package_version': m['package_version'],
        'package_manifest_sha': p.digest(p.ROOT / 'RUNNER_MANIFEST.json'), 'precheck': str(precheck_path.parent),
        'python_tests': precheck['unit_test_count'], 'powershell_contract_tests': precheck['powershell_contract_test_count'],
        'precheck_native_excel_executed': False, 'new_batch': m['batch_counts'],
        'reference_output_count': len(ref), 'reference_counts': dict(collections.Counter(r['reference_status'] for r in ref)),
        'recovery_reference_counts_not_native_proof': dict(collections.Counter(r['reference_status'] for r in pending_recovery)),
        'frozen_native_run': str(BASELINE), 'frozen_baseline_unchanged': True, 'original_manifest_archive': str(CLOSURE / 'baseline-code/RUNNER_MANIFEST.json'),
        'level1_gates': audit['gates'], 'real_output_matrix': str(audit_path.parent / 'REAL_ROW_OUTPUT_MATRIX.json'),
        'boundary_output_matrix': str(audit_path.parent / 'BOUNDARY_OUTPUT_MATRIX.json'),
        'recovery_register': str(audit_path.parent / 'BROKEN_FAMILY_RECOVERY_REGISTER.json'),
        'remaining_15_family_source_review': source_review, 'user_business_decisions_requested': [],
        'native_access_tool_observations_this_turn': {'sandbox_com_create_hresult': '0x80070520', 'sandbox_identity': 'PCE-FZG\\CodexSandboxOffline', 'connected_excel_sessions': 0, 'evidence_type': 'MAIN_AGENT_TOOL_OBSERVATION; NOT A NATIVE RUN', 'workbook_opened': False},
        'next_native_trigger': 'Instruction section 12: new capture ranges, new boundary/micro tests, candidate native validation; not a rerun required by translator-only changes.',
        'source_sha': p.digest(m['source']), 'source_unchanged': p.digest(m['source']) == p.EXPECTED_SHA,
        'production': db, 'writes': {'engineering_real_rule': 0, 'BOM': 0, 'capacity': 0, 'planning': 0, 'production_batch': 0, 'migration': 0},
        'domain_formalization': 'NOT_ENTERED', 'ui_navigation_changes': 0,
        'governance_hashes': {str(path): p.digest(path) for path in [REPO.parent / 'AGENTS.md', REPO / 'AGENTS.md', REPO / 'docs/governance/PCE CODEX开发指令规范管理V1.2.md']},
        'new_code_hashes': {str(path): p.digest(path) for path in [Path(__file__), REPO / 'scripts/excel_parity/technical_closure.py', REPO / 'scripts/excel_parity/closure_batch.py', REPO / 'scripts/excel_parity/reference_runtime.py', REPO / 'scripts/excel_parity/test_technical_closure.py', REPO / 'scripts/excel_parity/test_closure_batch.py']},
    }
    target = CLOSURE / ('DELIVERY_AUDIT_' + precheck_path.parent.name + '.json')
    p.require(not target.exists(), 'APPEND-ONLY DELIVERY AUDIT; NEVER OVERWRITE')
    p.write(target, report)
    print(json.dumps({'file': str(target), 'sha256': p.digest(target), 'tests': [report['python_tests'], report['powershell_contract_tests']], 'reference_counts': report['reference_counts'], 'new_batch': report['new_batch']}, ensure_ascii=False))


if __name__ == '__main__':
    main()

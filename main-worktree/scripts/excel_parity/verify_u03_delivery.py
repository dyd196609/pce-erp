"""Final append-only integrity audit. Never modifies native Runs or business DB."""
import json
import sys
from decimal import Decimal
from pathlib import Path
from u03_recovery_audit import OUT, DB, DB_SHA, REQUEST, REPO, p, snapshot, immutable
from workbook_source import SourceBook, SOURCE, coord


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    pre = Path(sys.argv[1]).resolve()
    m = p.load_manifest()
    technical = p.read(OUT / ('TECHNICAL_PRECHECK_AUDIT-' + pre.name + '.json'))
    current_sha = p.digest(p.ROOT / 'RUNNER_MANIFEST.json')
    p.require(technical['package_manifest_sha'] == current_sha, 'AUDITED CODE != DELIVERED CODE')
    check = p.read(pre / 'PACKAGE_PRECHECK.json')
    p.require(check['status'] == 'PASS' and check['package_manifest_sha'] == current_sha, 'PRECHECK PACKAGE NOT CURRENT')
    p.require(check['tested_files'] == m['files'], 'TESTED FILES NOT CURRENT')
    p.verify_hashes(p.read(pre / 'RUN_MANIFEST.json')['files'], pre)
    historical = []
    for run_id, sha in [('20260908T144733317Z-4c7dd106', '38CF2AC205DDB077E97F1EA68B534103DC6D3208A7957F996DEE0C3C41433697'), ('20260909T010756709Z-772c0971', '9A0AF062D4E8F6ACC64A57BF452F36935110783D238DA830FF76E2AC795E88E3')]:
        run = p.ROOT / 'runs' / run_id
        p.require(p.digest(run / 'RUN_MANIFEST.json') == sha, 'HISTORICAL MANIFEST DRIFT')
        manifest = p.read(run / 'RUN_MANIFEST.json')
        p.verify_hashes(manifest['files'], run)
        # Parse every historical JSON while preserving every byte.
        for file in run.glob('*.json'):
            p.read(file)
        historical.append({'run': str(run), 'manifest_sha': sha, 'verified_files': len(manifest['files']), 'writes': 0})
    old_report = REPO / 'docs/evidence/NATIVE_EXCEL_GOLDEN_FINAL_CONSOLIDATED_20260909_R2.md'
    p.require(p.digest(old_report) == '36D85577826CF02EAECF247A52BBC993773CCB28C9FD9D582A6CC9C12204307E', 'FROZEN REPORT DRIFT')
    book = SourceBook()
    policies = p.read(OUT / 'MATERIAL_LOSS_POLICY_CANDIDATES.json')
    p.require(book.sheets['三合一生产单']['AV30']['formula'] == '=#REF!*1.2', 'VENEER SOURCE LOSS FACTOR DRIFT')
    for c in policies['candidates']:
        p.require(c['current_formal_value'] is None and c['effective_version'] is None, 'POLICY MUST REMAIN PREVIEW')
        for cell in c.get('source_cells', []):
            sn, addr = cell.split('!')
            col = addr.rstrip('0123456789')
            p.require(book.sheets[sn][addr]['formula'] == '=' + col + '29*1.2', 'BOARD LOSS FACTOR SOURCE DRIFT')
    rows = p.read(OUT / 'REAL_ROW_SOURCE_FACTS.json')
    area, visible, edge = Decimal(0), Decimal(0), Decimal(0)
    missing_visible, missing_edge = [], []
    patterns = {'一长': (1, 0), '一宽': (0, 1), '两长': (2, 0), '两宽': (0, 2), '一长一宽': (1, 1), '一长两宽': (1, 2), '两长一宽': (2, 1), '四边': (2, 2), '白坯': (0, 0)}
    for row in rows:
        if row['sheet'] != '三合一生产单':
            continue
        r = row['row']
        fact = lambda col: row['source_cells'].get(col + str(r), {}).get('value')
        l, w, qty = [Decimal(str(fact(c))) for c in 'JKM']
        net = l * w * qty / 1000000
        area += net
        if fact('O') in ('单', '双'):
            visible += net * (1 if fact('O') == '单' else 2)
        elif fact('O') != '白坯':
            missing_visible.append(r)
        if fact('P') in patterns:
            lc, wc = patterns[fact('P')]
            edge += (l * lc + w * wc) * qty / 1000
        else:
            missing_edge.append(r)
    expected = {'ALL_TRI_PRODUCT_AREA_m2': area, 'VENEER_NET_VISIBLE_AREA_m2': visible, 'AV30_RECOVERY_SOURCE_LOSS_FACTOR_1_20': visible * Decimal('1.2'), 'AV31_RECOVERY_NET_EDGE_LENGTH_m': edge}
    by_name = {r['semantic_name']: r['code_result'] for r in technical['ledger']}
    for name, value in expected.items():
        p.require(by_name[name]['type'] == 'number', 'LEDGER NOT NUMERIC')
        # Dimensional Decimal crosscheck only; not a native acceptance tolerance.
        p.require(abs(Decimal(str(by_name[name]['value'])) - value) < Decimal('0.000000001'), 'INDEPENDENT SOURCE LEDGER MISMATCH')
    after = snapshot()
    p.require(after['db_sha'] == DB_SHA, 'PRODUCTION SHA DRIFT')
    inputs = set(m['frozen_files']) | {str(p.ROOT / n) for n in m['files']} | {str(SOURCE), str(REQUEST), str(DB)}
    inputs |= {str(SOURCE.parent / n) for n in ('05半成品板材.xlsx', '10采购物料.xlsx', '12木皮.xlsx', '13坯板.xlsx')}
    inputs |= {str(REPO.parent / 'AGENTS.md'), str(REPO / 'AGENTS.md'), str(REPO / 'docs/governance/PCE CODEX开发指令规范管理V1.2.md')}
    inputs |= {str(old_report), str(p.ROOT / 'RUNNER_MANIFEST.json')}
    output = {'timestamp': p.now(), 'package_version': m['package_version'], 'package_manifest_sha': current_sha, 'precheck': str(pre),
        'tests': {'python': check['unit_test_count'], 'powershell_contract': check['powershell_contract_test_count'], 'independent_whole_chain_cases': len(technical['independent_checks'])},
        'case_count': technical['case_count'], 'output_count': technical['output_count'], 'new_native_execution': 'NOT_EXECUTED',
        'historical_integrity': historical, 'frozen_report_sha': p.digest(old_report),
        'independent_decimal_ledger': {k: str(v) for k, v in expected.items()},
        'missing_visible_source_rows': missing_visible, 'missing_edge_applicability_rows': missing_edge,
        'production_counts': after['counts'], 'db_sha': DB_SHA, 'source_sha': p.EXPECTED_SHA,
        'production_write': 0, 'domain_rule_formalization': 'NOT_ENTERED', 'loss_policy_production_write': 0,
        'input_file_count_registered_scope': len(inputs), 'inputs': [{'path': path, 'sha': p.digest(path)} for path in sorted(inputs)],
        'delivery_artifacts': [{'path': str(f), 'sha': p.digest(f)} for f in sorted(OUT.glob('*.json'))] + [{'path': str(REPO / 'docs/evidence/ENGINEERING_MATERIAL_CALCULATION_TARGET_U03_20260909.md'), 'sha': p.digest(REPO / 'docs/evidence/ENGINEERING_MATERIAL_CALCULATION_TARGET_U03_20260909.md')}],
        'stop': 'ONE_PRECHECKED_NATIVE_PACKAGE_READY; BOARD_BUSINESS_RESOLUTION_BLOCKED; USER_SINGLE_DOUBLE_CLICK_REQUIRED',
        'ui_gate': 'N/A; UI untouched'}
    immutable('FINAL_DELIVERY_AUDIT.json', output)
    print(json.dumps({k: v for k, v in output.items() if k not in ('inputs', 'delivery_artifacts')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

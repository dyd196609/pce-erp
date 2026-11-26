"""Append-only U03 source/formal inventory. No ORM or production writes."""
import collections
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools/excel-golden-runner'))
import package_support as p
from workbook_source import SourceBook, SOURCE, coord

OUT = REPO / 'docs/evidence/excel_formula_parity/closure-20260909/recovery-u03'
DB = REPO / 'backend/db.sqlite3'
DB_SHA = '9DADFB55D446DF052A4DCF6CF2EE552906939FD1B65D7D899C5FD8C1AC368F5C'
REQUEST = Path(r'C:\Users\DAODA\.codex\attachments\3bf7a1eb-ff19-4d56-aa3b-62ae1cde5d56\pasted-text.txt')


def immutable(name, data):
    path = OUT / name
    p.require(not path.exists(), 'APPEND ONLY: ' + str(path))
    p.write(path, data)


def snapshot():
    p.require(p.digest(DB) == DB_SHA and p.digest(SOURCE) == p.EXPECTED_SHA, 'FROZEN DATA DRIFT')
    conn = sqlite3.connect(DB.as_uri() + '?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA query_only=ON')
    names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    scoped = [n for n in names if any(s in n for s in ('material', 'engineering', 'bom', 'external_identity'))]
    tables = {}
    for name in scoped:
        # Table identifiers originate only in SQLite's own schema.
        tables[name] = {'schema': [dict(r) for r in conn.execute('PRAGMA table_info("' + name + '")')],
                        'rows': [dict(r) for r in conn.execute('SELECT * FROM "' + name + '"')]}
    counts = {n: conn.execute('SELECT COUNT(*) FROM "' + n + '"').fetchone()[0] for n in ('system_process', 'pde_routing', 'pde_routing_version', 'pde_routing_step', 'pde_engineering_rule_definition')}
    conn.close()
    p.require(p.digest(DB) == DB_SHA, 'READ-ONLY DATABASE DRIFT')
    return {'db_sha': DB_SHA, 'counts': counts, 'tables': tables, 'query_only': True, 'production_write': 0}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    OUT.mkdir(parents=True, exist_ok=True)
    m = p.load_manifest()
    archive = OUT / 'before-code'
    p.require(not archive.exists(), 'ARCHIVE ALREADY EXISTS')
    archive.mkdir()
    files = {str(p.ROOT / n): h for n, h in m['files'].items()} | m['frozen_files']
    files[str(p.ROOT / 'RUNNER_MANIFEST.json')] = p.digest(p.ROOT / 'RUNNER_MANIFEST.json')
    mapping = []
    for i, (name, sha) in enumerate(files.items()):
        target = archive / (str(i).zfill(3) + '-' + Path(name).name)
        shutil.copyfile(name, target)
        p.require(p.digest(target) == sha, 'ARCHIVE HASH MISMATCH')
        mapping.append({'original': name, 'archive': str(target), 'sha256': sha})
    immutable('BEFORE_CODE_MANIFEST.json', mapping)
    control = {'created_at': p.now(), 'request': str(REQUEST), 'request_sha': p.digest(REQUEST),
               'governance': [{'path': str(f), 'sha': p.digest(f)} for f in [REPO.parent / 'AGENTS.md', REPO / 'AGENTS.md', REPO / 'docs/governance/PCE CODEX开发指令规范管理V1.2.md']],
               'effective_instruction_set': {'ACTIVE': ['U03 business adjudications; isolated recovery; one complete Native package; target design'],
                   'FROZEN': ['Native 280 baseline; 1123/4487 supplement; R2 evidence; Group 1/2/3A/3B; original XLSX and DB'],
                   'SUPERSEDED_IN_PART': ['U03-01 through U03-04 waiting for decision: now resolved by current attachment'],
                   'NOT_AUTHORIZED': ['Domain Rule Formalization', 'Migration', 'production writes', 'UI/navigation']},
               'control_sheet': {'original_goal': 'Excel reverse engineering and verifiable native reference parity', 'current_goal': 'apply U03, prepare recovery evidence and target design',
                   'stage': 'CONTROLLED EVIDENCE BUILD / PREPARATION; target design only for production domain',
                   'frozen_baseline': {'level1a': '100/100', 'real': '1510 PASS / 31 BROKEN_SOURCE', 'boundary': '434 PASS / 22 BROKEN_SOURCE', 'candidate': '2376 PASS; historical recovery 0'},
                   'user_path': 'N/A; existing ordinary-double-click runner only', 'stop': 'one complete prechecked native recovery package, or genuine new business adjudication',
                   'database': 'READ ONLY', 'review_level': 'C', 'scope_reevaluation': 'More than 10 dependency inputs; same original instruction explicitly requests one batch; no production implementation/deployment; preserve one consolidated report.'},
               'instruction_register': [{'id': 'EXCEL-NATIVE-U03-20260909', 'status': 'ACTIVE', 'decisions': ['W39 legacy excluded', 'exact geometry and thickness; product area per selected stock', 'visible-area veneer; loss candidate 20%', 'edge length m; per-edge allowance separate']}],
               'conflict_resolution': 'Latest user section 22 prohibits domain formalization even if parity later passes.'}
    immutable('INSTRUCTION_CONTROL.json', control)
    formal = snapshot()
    immutable('FORMAL_READONLY_SNAPSHOT.json', formal)
    book = SourceBook()
    family, cases = p.assets(m)
    rows = []
    for c in cases['cases']:
        if c['level'] in (2, 3):
            sn, r = c['source_sheet'], c['source_row']
            cells = {a: {k: v[k] for k in ('value', 'formula', 'type')} for a, v in book.sheets[sn].items() if coord(a)[0] == r}
            rows.append({'case_id': c['case_id'], 'sheet': sn, 'row': r, 'source_cells': cells})
    immutable('REAL_ROW_SOURCE_FACTS.json', rows)
    projected = []
    for f in family['families']:
        cells = f.get('source_cells', f.get('cells', []))
        # Inventory source_cells may be structured; use authoritative cell map.
        cells = [a for a, fid in family['cell_to_family'].items() if fid == f['family_id']]
        legacy = [a for a in cells if a.startswith('房门单!') and coord(a.split('!')[1])[0] >= 39]
        projected.append({'family_id': f['family_id'], 'broken': f['broken'], 'historical_cells': len(cells), 'excluded_legacy_cells': legacy, 'active_cells': [a for a in cells if a not in legacy], 'current_status': 'DEPRECATED_LEGACY_TEMPLATE' if len(legacy) == len(cells) else 'ACTIVE_OR_MIXED'})
    immutable('CURRENT_SCOPE_PROJECTION.json', {'historical_inventory_unchanged': True, 'families': projected,
        'summary': {'historical_families': len(projected), 'active_families': sum(bool(f['active_cells']) for f in projected), 'active_broken_families': sum(f['broken'] and bool(f['active_cells']) for f in projected), 'excluded_family_count': sum(not f['active_cells'] for f in projected), 'excluded_cells': sum(len(f['excluded_legacy_cells']) for f in projected)}})
    print(json.dumps({'out': str(OUT), 'counts': formal['counts'], 'tables': {n: len(t['rows']) for n, t in formal['tables'].items()}, 'real_rows': len(rows)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

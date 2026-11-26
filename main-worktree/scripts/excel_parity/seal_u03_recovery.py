"""Version 1.4 seal: new recovery tests only; previous manifests immutable."""
import collections
import sys
from pathlib import Path
from u03_recovery_audit import OUT, p
from recovery_batch import build, COHORT


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    archive = p.read(OUT / 'BEFORE_CODE_MANIFEST.json')
    saved_manifest = next(r for r in archive if r['original'] == str(p.ROOT / 'RUNNER_MANIFEST.json'))
    old = p.read(saved_manifest['archive'])
    for row in archive:
        p.require(p.digest(row['archive']) == row['sha256'], 'BEFORE ARCHIVE DRIFT')
    p.verify_hashes(old['frozen_files'])
    for name, sha in old['files'].items():
        if name not in ('package_support.py', 'README_FOR_USER.txt'):
            p.require(p.digest(p.ROOT / name) == sha, 'OUT-OF-SCOPE RUNNER CHANGE: ' + name)
    frozen = dict(old['frozen_files'])
    for name in ('u03_recovery_audit.py', 'recovery_semantics.py', 'recovery_batch.py', 'test_u03_recovery.py', 'seal_u03_recovery.py', 'audit_u03_precheck.py'):
        path = Path(__file__).parent / name
        frozen[str(path)] = p.digest(path)
    for name in ('FORMAL_READONLY_SNAPSHOT.json', 'BOARD_STOCK_AND_REAL_ROW_AUDIT.json', 'REAL_ROW_SOURCE_FACTS.json', 'CURRENT_SCOPE_PROJECTION.json', 'RECOVERY_REGISTER_U03.json', 'INSTRUCTION_CONTROL.json', 'BEFORE_CODE_MANIFEST.json'):
        frozen[str(OUT / name)] = p.digest(OUT / name)
    plan = build(old)
    current = old | {'package_version': '1.4-u03-recovery-r1', 'created_at': p.now(), 'files': {n: p.digest(p.ROOT/n) for n in p.PACKAGE_FILES},
        'frozen_files': frozen, 'scope': COHORT, 'supplemental_batch': COHORT, 'recovery_batch': COHORT,
        'native_execution': 'NOT_EXECUTED_FOR_U03_RECOVERY',
        'revision': {'old_manifest': saved_manifest['archive'], 'old_manifest_sha': saved_manifest['sha256'],
            'authorization': '3bf7a1eb U03 decisions; one isolated recovery batch; production writes=0', 'source_unchanged': True, 'production_unchanged': True},
        'batch_counts': {'cases': len(plan['cases']), 'outputs': plan['selected_output_count'], 'probe_cells': len(plan['probe_sheet']['cells']),
            'cohorts': dict(collections.Counter(c['cohort'] for c in plan['cases']))}}
    p.write(p.ROOT / 'RUNNER_MANIFEST.json', current)
    p.load_manifest()
    print(__import__('json').dumps(current['batch_counts'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

"""Seal only authorized R2 technical changes, preserving executed package 1.2."""
import sys
from pathlib import Path
from native_supplement_closure import p, ROOT, ARCHIVE, verify


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    _, old, plan, _, _ = verify()
    summary_path = Path(sys.argv[1])
    summary = p.read(summary_path)
    p.require(summary['level1_all_eligible_pass'], 'AUDITED PARITY REQUIRED')
    runtime = Path(old['reference_directory']) / 'reference_runtime.py'
    p.require(summary['code_hashes'][str(runtime)] == p.digest(runtime), 'AUDITED RUNTIME != PACKAGED RUNTIME')
    allowed_dependencies = {'reference_runtime.py', 'test_technical_closure.py'}
    frozen = dict(old['frozen_files'])
    delta = []
    for name, prior in frozen.items():
        current = p.digest(name)
        if current != prior:
            p.require(Path(name).name in allowed_dependencies, 'UNAUTHORIZED DEPENDENCY CHANGE: ' + name)
            delta.append({'path': name, 'before': prior, 'after': current})
            frozen[name] = current
    for name in ('test_native_supplement.py', 'native_supplement_closure.py', 'recovery_source_exhaustion.py', 'seal_native_r2_revision.py'):
        path = Path(__file__).parent / name
        frozen[str(path)] = p.digest(path)
    # Formatting only: keep PowerShell 5.1 Chinese strings UTF-8 BOM compatible.
    for name in p.PACKAGE_FILES:
        path = p.ROOT / name
        if path.suffix == '.ps1':
            path.write_bytes(path.read_text('utf-8-sig').encode('utf-8-sig'))
    result = old | {'package_version': '1.3-native-evidence-r2', 'created_at': p.now(), 'files': {n:p.digest(p.ROOT/n) for n in p.PACKAGE_FILES}, 'frozen_files': frozen, 'native_execution':'R2_FROZEN_CAPTURE_RECOMPARED; NEW_ERROR_CAPTURE_IMPLEMENTATION_NOT_NATIVE_EXECUTED', 'revision': {'old_manifest':str(ARCHIVE/'RUNNER_MANIFEST.json'),'old_manifest_sha':p.digest(ARCHIVE/'RUNNER_MANIFEST.json'),'audit':str(summary_path),'audit_sha':p.digest(summary_path),'authorized_dependency_delta':delta,'authorization':'Current continuation: formula identity, SUMIFS compatibility, error evidence capture, pure tests; source/production writes=0','case_plan_unchanged':True,'user_rerun_requested':False,'source_formula_recovery_applied':False}}
    p.write(p.ROOT/'RUNNER_MANIFEST.json',result)
    p.load_manifest()
    print(result['package_version'] + ' ' + p.digest(p.ROOT/'RUNNER_MANIFEST.json'))


if __name__ == '__main__':
    main()

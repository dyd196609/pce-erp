"""Read-only logical preservation fingerprints; no business table writes."""
import ast
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work' / 'manufacturing-eor-20261014'
DATABASE = Path(r'D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3')


def capture(path=DATABASE):
    con = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    tables = {}
    for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        quoted = '"' + name.replace('"', '""') + '"'
        rows = [json.dumps(row, ensure_ascii=False, default=str, separators=(',', ':'))
                for row in con.execute('SELECT * FROM ' + quoted)]
        tables[name] = {'count': len(rows), 'sha256': sha256('\n'.join(sorted(rows)).encode()).hexdigest()}
    schema = list(con.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"))
    con.close()
    return {'database': str(path), 'tables': tables,
            'schemaHash': sha256(json.dumps(schema, ensure_ascii=False).encode()).hexdigest()}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    name = sys.argv[1]
    data = capture()
    files = [*ROOT.joinpath('backend/pde').glob('*.py'),
             ROOT / 'backend/system/models.py', ROOT / 'backend/planning/models.py',
             ROOT / 'frontend/src/router/index.js', ROOT / 'frontend/src/api/pde.js',
             ROOT / 'frontend/src/meta/process/businessProcessRegistry.js']
    data['sourceHashes'] = {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest() for p in files}
    tree = ast.parse(ROOT.joinpath('backend/pde/models.py').read_text(encoding='utf-8-sig'))
    data['modelHashes'] = {node.name: sha256(ast.dump(node).encode()).hexdigest()
                           for node in tree.body if isinstance(node, ast.ClassDef)}
    data['timestamp'] = datetime.now(timezone(timedelta(hours=8))).isoformat()
    (OUT / f'{name}.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    if name == 'before':
        destination = OUT / 'isolated-manufacturing-eor.sqlite3'
        if destination.exists():
            raise SystemExit('ISOLATED_COPY_ALREADY_EXISTS; refusing overwrite')
        source = sqlite3.connect(DATABASE.as_uri() + '?mode=ro', uri=True)
        target = sqlite3.connect(destination)
        source.backup(target)
        source.close()
        target.close()
        for file in ('models.py', 'operation_requirement_service.py'):
            (OUT / f'before-{file}').write_bytes(ROOT.joinpath('backend/pde', file).read_bytes())
    print(json.dumps({'evidence': str(OUT / f'{name}.json'), 'tables': len(data['tables']),
                      'sourceFiles': len(files)}, ensure_ascii=False))


if __name__ == '__main__':
    main()

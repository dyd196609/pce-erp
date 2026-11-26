import csv
import json
from pathlib import Path
import sqlite3
import sys


database_path = Path(sys.argv[1]).resolve()
output_dir = Path(sys.argv[2]).resolve()
audit_id = int(sys.argv[3])
output_dir.mkdir(parents=True, exist_ok=True)

connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
connection.row_factory = sqlite3.Row
audit = connection.execute(
    "SELECT id, action_code, actor_id, organization_id, target_type, target_id, "
    "target_label, reason, before_snapshot, after_snapshot, created_at "
    "FROM system_organization_operating_audits WHERE id = ?",
    (audit_id,),
).fetchone()
if not audit:
    raise SystemExit(f"Audit {audit_id} not found")

before = json.loads(audit["before_snapshot"])
after = json.loads(audit["after_snapshot"])
evidence = {
    "databasePath": str(database_path),
    "audit": {
        "id": audit["id"], "actionCode": audit["action_code"],
        "actorId": audit["actor_id"], "organizationId": audit["organization_id"],
        "targetType": audit["target_type"], "targetId": audit["target_id"],
        "targetLabel": audit["target_label"], "reason": audit["reason"],
        "createdAt": audit["created_at"],
    },
    "before": before,
    "after": after,
    "summary": {
        "installationChangedCount": len(after.get("installationImpact", [])),
        "doorClassifiedCount": len(after.get("doorImpact", [])),
        "doorChangedCount": sum(1 for row in after.get("doorImpact", []) if row.get("changed")),
        "doorUnchangedCount": sum(1 for row in after.get("doorImpact", []) if not row.get("changed")),
    },
}
(output_dir / "写入差异与影响清单.json").write_text(
    json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8",
)

with (output_dir / "安装位置修复清单.csv").open("w", encoding="utf-8-sig", newline="") as handle:
    fields = [
        "designItemId", "itemNo", "sourceSheet", "sourceRow", "before", "after",
        "mergedRange", "topLeftCell",
    ]
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(after.get("installationImpact", []))

with (output_dir / "实际门类要求清单.csv").open("w", encoding="utf-8-sig", newline="") as handle:
    fields = [
        "designItemId", "itemNo", "sourceSheet", "sourceRow", "sourceProduct",
        "sourceComponent", "edgeBefore", "edgeAfter", "visibleBefore", "visibleAfter",
        "changed", "decisionBasis",
    ]
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(after.get("doorImpact", []))

print(json.dumps(evidence["summary"], ensure_ascii=False))

"""Build an isolated canonical backend candidate, never modify the running models."""
from pathlib import Path
import ast
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/evidence/semi_finished_model_closure_20260909"
ISO = ROOT / ".runtime/semi-finished-model-closure-20260909"
BACKEND = ISO / "backend"
RECOVER = (
    "StructureRole", "EngineeringRuleCategory", "ProductTemplateStructureNode",
    "TemplateNodeCalculationRuleBinding", "TemplateMaterialRequirementSlot",
    "OrderConfiguredProduct", "InstallationContext", "OrderProductComponent",
    "ComponentMaterialRequirement", "MaterialSelectionCandidate", "EngineeringMaterialCalculationResult",
)


def main():
    if BACKEND.exists():
        raise SystemExit("Isolated candidate already exists; do not overwrite")
    files = []
    for source in (ROOT / "backend").rglob("*"):
        relative = source.relative_to(ROOT / "backend")
        if set(relative.parts) & {"venv", ".venv", "__pycache__", "backups", "logs", "media", "node_modules", ".git"}:
            continue
        if not source.is_file() or source.suffix not in {".py", ".json"} or any(p.startswith(".") for p in relative.parts):
            continue
        target = BACKEND / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        files.append(str(relative))
    history = (OUT / "historical/models.py").read_text(encoding="utf-8")
    lines = history.splitlines(keepends=True)
    nodes = {n.name: "".join(lines[n.lineno-1:n.end_lineno]) for n in ast.parse(history).body if isinstance(n, (ast.ClassDef, ast.FunctionDef))}
    target = BACKEND / "pde/models.py"
    text = target.read_text(encoding="utf-8")
    text += "\n\n# Restored canonical contracts from wave26/27, isolated candidate only.\n"
    text += "\n\n".join(nodes[n] for n in ("_engineering_rule_is_test_only", *RECOVER)) + "\n"
    target.write_text(text, encoding="utf-8")
    shutil.copy2(OUT / "historical/order_engineered_product_service.py", BACKEND / "pde/order_engineered_product_service.py")
    (OUT / "ISOLATED_CANDIDATE_MANIFEST.json").write_text(json.dumps({
        "backend": str(BACKEND), "canonicalPaths": True, "deployment": "NOT_APPLIED",
        "sourceHead": json.loads((OUT / "BASELINE.json").read_text(encoding="utf-8"))["gitHead"],
        "restoredModels": RECOVER, "copiedFiles": files,
        "database": str(ISO / "isolated.sqlite3"),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"isolatedBackend": str(BACKEND), "fileCount": len(files), "restoredModels": RECOVER}, ensure_ascii=False))


if __name__ == "__main__":
    main()

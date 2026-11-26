# Excel compatibility reference adapter

This directory is an isolated migration/parity reference, not a production calculation engine. Nothing here imports Django or writes a business database. The existing Engineering Calculation Engine is unchanged.

## Current gate

Microsoft Excel COM activation fails in the current login session with `0x80070520`. There is no connected Excel document-control session. All native parity gates remain BLOCKED. Cached workbook values are preserved only as source evidence, never used as Golden values.

## Reproduce

Use the bundled Python executable returned by `load_workspace_dependencies` (this run: `C:\Users\DAODA\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`). Work in `D:\Dev-PCE\Source`.

1. `python scripts/excel_parity/workbook_source.py` freezes source identity and inventories the workbook without saving it.
2. `python scripts/excel_parity/analyze.py` creates ASTs, normalized families, provenance, dependencies, exceptions and `generated_reference.py`.
3. `python scripts/excel_parity/prepare_validation.py` prepares typed cases, source/master snapshots and candidate reconstruction evidence.
4. `python scripts/excel_parity/test_reference.py` runs technical adapter tests. This is not Excel parity.
5. In an automatable Microsoft Excel login session, run `powershell -File scripts/excel_parity/run_excel_golden.ps1 -Level 1`. Only a private copy is opened. Links, macros and events are disabled; auto-refresh connections are rejected; the original is never saved.
6. `python scripts/excel_parity/differential.py` compares only provenance-verified native outputs. No native output means UNSUPPORTED/BLOCKED, not PASS.
7. Only after the previous level is genuinely PASS may the native harness run the next level (2 through 5). Known broken families currently prevent full Level 1 PASS; no automatic exclusions or repairs are permitted.
8. `python scripts/excel_parity/verify_evidence.py` validates syntax, tests, dataset cardinality, source/DB protection and the package hash manifest.

Do not regenerate the case manifest between an Excel run and its comparison. The differential runner checks the exact case-manifest SHA and original workbook SHA. Native execution has not been validated beyond the current COM activation blocker.

## Boundaries and limitations

- Parser and generated functions are deterministic; unknown AST/function features fail explicitly. `IFERROR` cannot conceal adapter-unsupported or broken-source exceptions.
- Blank, omitted argument, zero, FALSE and empty text are distinct typed states. Excel coercion and numeric corner cases remain subject to native verification.
- Approximate lookups, INDEX array returns, implicit intersection, unrecognized TEXT formats and non-ASCII CHAR locale semantics are explicitly unsupported. Only the inventoried exact lookup mode and `00`/`000` TEXT patterns are implemented.
- Source header labels are provisional semantic names. Later blank door-template rows have shifted-column formulas; their names must not become domain fields automatically.
- Reconstruction candidates are never substituted into source, generated functions, golden inputs or production rules.
- The 722 case definitions and 2,192 per-output result rows are evidence preparation, not 722 passing cases.
- Domain migration to existing `EngineeringRuleDefinition`, `CalculationDetail` and `EngineeringDerivedFact` requires a separate authorized phase after the gates. No new model, API or navigation entry is introduced.

# Manual Latest Template Final Capability Validation Handoff

Run ID: `WAVE1-LATEST-TEMPLATE-FULL-CAPABILITY-20260911-001`

Use only `http://127.0.0.1:5174/` with the isolated manual database `D:\Dev-PCE\work\wave1_formal_import_manual_20260911.sqlite3`.

Login: `wave1_formal_import_gate` / `Wave1.Import#20260911`

Start counts: Customer 90, Supplier 122, Material 271, Workshop 4. Production must not be used.

## Customer

1. Open 企业基础资料 → 客户/经销商; optionally download the template and confirm its sheet/header/options are Chinese.
2. Click 导入数据 and choose `A-客户人工导入样例.xlsx`.
3. The preview must open automatically and show CREATE=1, MATCH=0, READY=1.
4. Click 确认导入. Search `W1-MANUAL-CUST-20260911`; total becomes 91.
5. Upload the same file again. Preview must show CREATE=0, MATCH=1. Confirming again must keep total at 91.

## Material

Repeat in 企业基础资料 → 物料档案 with `B-物料人工导入样例.xlsx`. First preview is CREATE=1/MATCH=0; search `W1-MANUAL-MT-20260911`; 271→272. Re-upload the same file: CREATE=0/MATCH=1; total remains 272.

## Workshop

Repeat in 企业基础资料 → 车间/生产区域 with `C-车间人工导入样例.xlsx`. First preview is CREATE=1/MATCH=0; search `W1-MAN-WS-20260911`; 4→5. Re-upload the same file: CREATE=0/MATCH=1; total remains 5.

## Supplier row selection

Open 企业基础资料 → 供应商. Select row 1: only row 1 is checked and count=1. Select row 2: count=2. Deselect row 1: only row 2 remains and count=1. Click the header checkbox: only then may the current visible page/scope be selected.

After validation, report PASS/FAIL for the three first imports, three replay previews/counts and Supplier selection. The temporary identity/session will be disabled and cleared only after acceptance is complete.

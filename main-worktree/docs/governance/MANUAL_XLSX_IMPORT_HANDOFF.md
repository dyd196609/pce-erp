# Manual XLSX Import Handoff

Status: `USER MANUAL FINAL IMPORT VALIDATION = FAIL/PENDING` until the user completes A2/B2/C2.

Runtime root: `http://127.0.0.1:5174/`  
Login: `wave1_formal_import_gate` / `Wave1.Import#20260911`

| Object | URL | Sample | Expected first import | Expected replay |
|---|---|---|---|---|
| Customer | `http://127.0.0.1:5174/#/master-data/customers` | `A2-客户人工导入样例.xlsx` | 90→91; 新建 1 / 匹配已有 0 | 91; 新建 0 / 匹配已有 1 |
| Material | `http://127.0.0.1:5174/#/foundation/master-data/materials` | `B2-物料人工导入样例.xlsx` | 271→272; 新建 1 / 匹配已有 0 | 272; 新建 0 / 匹配已有 1 |
| Workshop | `http://127.0.0.1:5174/#/foundation/master-data/workshops` | `C2-车间人工导入样例.xlsx` | 4→5; 新建 1 / 匹配已有 0 | 5; 新建 0 / 匹配已有 1 |

For each object: download the official template and confirm Chinese worksheet/header/values; click 导入数据 and select the matching A2/B2/C2 XLSX; verify the preview appears automatically; confirm the first import; upload the identical file again and confirm the MATCH replay does not increase the count.

All writes here target the isolated manual database. Keep the account/session available until user PASS, then disable it and clear its sessions.

`MANUAL XLSX IMPORT VALIDATION READY`

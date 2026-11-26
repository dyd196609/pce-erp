# Import User Preview Contract

The shared import toolbar implements one continuous user path:

`导入数据` → select `.xlsx`/legacy UTF-8 `.csv` → immediately open `导入预览` → visible validation → row decisions → explicit confirmation → result/readback → page refresh.

The preview must show file name, detected file type, XLSX worksheet name, total rows, READY, REVIEW, BLOCKED, CREATE, MATCH, errors and warnings. User-facing labels are Chinese-first: 可导入（READY）、需复核（REVIEW）、已阻断（BLOCKED）、新建（CREATE）、匹配已有（MATCH）. Each row must show source row number, business identity, localized key fields, validation state, identity decision, target action, errors and suggested action.

Before any write, the confirmation boundary repeats CREATE/MATCH/REVIEW/BLOCKED counts. `取消 / 返回` performs no write. `确认导入` is enabled only for a committable preview and requires the preview fingerprint plus an idempotency key. The result remains visible with created/matched totals and formal readback count.

Provider, authentication, export, filtering, sorting, pagination and process navigation authorities are unchanged.

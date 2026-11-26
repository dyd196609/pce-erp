# PCE-ERP 页面验收归档标准

版本：V1.14.2.8.4.20.7

## 目录规范

```text
test-results/page-acceptance/{version}/{moduleCode}/{pageCode}/{acceptanceRunId}/
├── manifest.json
├── acceptance.json
├── automatic-evidence.json
├── manual-acceptance.md
├── database-protection.json
├── screenshots/
├── traces/
└── hashes.json
```

## 必需内容

1. `manifest.json`：页面身份、模板版本、运行编号、执行时间、执行人、文件清单和 manifest Hash。
2. `acceptance.json`：全部检查项以及 PASS、FAIL、N/A、UNKNOWN 汇总。
3. `automatic-evidence.json`：规则、API、页面事实、性能和运行模式证据。
4. `manual-acceptance.md`：人工步骤、实际结果、验收人和结论。
5. `database-protection.json`：数据库前后 Hash、业务写入数和 `productionUserDataWritten`。
6. `screenshots/` 与 `traces/`：可视和交互证据；无证据时仍保留目录并在 manifest 说明。
7. `hashes.json`：归档内每个文件的 SHA-256。

## N/A归档规则

`N/A` 项不得删除、折叠或从总数中排除。每项必须记录 `naReason`、`confirmedBy` 和 `evidenceRefs`。缺少任一字段时归档校验失败。

## 不可变与版本

签署完成后设置 `immutable=true`。后续修正必须创建新的 `acceptanceRunId`，不得覆盖旧归档。模板升级必须保留原 `templateCode` 和 `templateVersion`，以便重放。

## 放行门禁

归档不等于验收通过。只有 `FAIL=0`、`UNKNOWN=0`、所有 N/A 原因完整、自动与人工均为 PASS、数据保护通过且 `archiveStatus=ARCHIVED` 时才允许放行。

# PCE-ERP 页面验收流程

版本：V1.14.2.8.4.20.7

## 1. 建立验收实例

从 `enterprise_page_master_template.json` 创建独立验收实例，填写页面身份、版本、执行人和唯一 `acceptanceRunId`。加载公共清单；SCM 页面还必须加载 SCM 扩展模板。验收范围必须是一页，禁止用其他页面证据替代。

## 2. 自动验收

采集路由、页面注册、API、五端服务端事实、企业列表契约、状态、按钮、对象关系、性能和数据库保护证据。自动接口按检查项编号返回 `PASS`、`FAIL`、`N/A` 或 `UNKNOWN`。

- `PASS`：证据完整且满足预期。
- `FAIL`：证据完整但不满足预期。
- `N/A`：检查项对当前页面不适用；检查项必须保留，并填写原因、确认人和证据。
- `UNKNOWN`：证据缺失、接口异常或无法判定；不得视为通过。

## 3. 人工验收

人工操作页面，确认页面名称、流程导航、查询筛选、列表与详情、按钮状态、异常提示、刷新保持及业务边界。人工结论必须引用截图、浏览器记录或明确的操作日志。

## 4. 结果复核

自动和人工结果合并时，必须保留母模板中的全部检查项。缺失检查项自动生成 `UNKNOWN`；`N/A` 不参与失败计数，但缺少原因时转换为 `FAIL`。任何 `FAIL` 或 `UNKNOWN` 均阻断页面放行。

## 5. 数据保护

记录正式数据库验收前后 Hash、业务写入数量和 `productionUserDataWritten`。只读验收必须满足业务写入为0；确需人工创建验收对象时，应使用明确的验收数据分类和独立归档，不得冒充自动通过证据。

## 6. 归档与放行

按归档标准生成清单、报告、证据、Hash 和签署记录。只有自动验收 PASS、人工验收 PASS、归档完成且数据保护通过时，`nextPageAllowed=true`。

## 自动验收接口

调用 `createEnterprisePageAcceptanceRun()` 创建完整运行实例，调用 `evaluateEnterprisePageAcceptance()` 合并检查结果。接口不读取业务缓存，不修改页面状态，不执行业务动作。返回结构包含：

```json
{
  "status": "PASS|FAIL|UNKNOWN",
  "summary": { "total": 0, "PASS": 0, "FAIL": 0, "N/A": 0, "UNKNOWN": 0 },
  "checks": [],
  "releaseGate": { "nextPageAllowed": false, "blockingReasons": [] }
}
```

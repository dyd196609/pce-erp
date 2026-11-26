# PCE真实运行验收治理体系建设验收报告

- 版本：`V1.14.2.8.4.27.2.36`
- 基于：`V1.14.2.8.4.27.2.35`
- 主题：PCE真实运行验收治理体系建设与CODEX执行标准升级
- 任务类型：治理-only
- 最终状态：`PCE_REAL_RUNTIME_ACCEPTANCE_GOVERNANCE_READY`

## 一、版本定位

本版本不开发业务功能，只建立真实浏览器验收、截图证据与READY三重门禁，并升级Codex任务执行格式。

## 二、治理文件读取

已完整读取：

1. `PCE-ERP智能化开发总纲.md`
2. `PCE-ERP开发治理总规范.md`
3. `页面真实运行验收规范.md`
4. `页面重构替换规范.md`
5. `Codex执行证据规范.md`

Governance Files Loaded: **PASS**

## 三、执行前扫描

现有规范已经声明源码和自动测试不能替代真实URL及用户动作，并已定义`AUTO_PASS_HUMAN_FAIL`。扫描发现的缺口是：

- 没有独立、统一的真实运行验收总规范；
- 截图、顶部/中部/底部、期望/实际结果尚未成为统一必填证据；
- Codex任务没有强制九段式模板；
- 最终READY没有统一、可检索的三项布尔判定公式。

## 四、允许修改范围

只修改`docs/governance`内的现行规范、验收报告、案例和版本截图证据。不修改业务模块、数据库、Runtime或Metadata。

## 五、实施内容

- 新增《真实运行验收规范》，建立`REAL-RUNTIME-ACCEPTANCE-001`。
- 在唯一总纲中新增真实运行验收优先原则与`CODEX-COMMAND-004`。
- 将Codex执行证据升级为强制九段式模板。
- 将URL、标题、区域、字段、按钮、期望、实际、截图设为逐页必填项。
- 新增`HUMAN-ACCEPTANCE-REQUIRED-001`、`PAGE-EVIDENCE-001`、`READY-GATE-001`。
- READY固定为自动验收、浏览器人工验收、Build三项全部PASS。

## 六、真实浏览器人工验收

### 页面验收记录

```text
页面URL：http://localhost:5173/#/foundation/erp/supplier-price-facts
页面标题：供应商价格事实 / 供应商价格事实
Route Component：SupplierPriceFactPage
验收区域：
  顶部区域：页面身份“供应商价格事实”；当前筛选结果405；服务端事实总数405；业务写入0
  中部区域：价格日期说明；单日日期=历史采购执行事实；日期区间=有效价格
  底部区域：价格事实列表；总记录数405；当前页1/21；操作列仅“查看”
检查字段：价格事实编号、供应商、物料、价格、币种、单位、税率、交货周期、来源类型、来源单据、生效日期、失效日期、状态
检查按钮：展开高级筛选；真实点击后按钮变为“收起高级筛选”，页面出现13个筛选控件；行操作仅“查看”
期望结果：真实URL可用，顶部/中部/底部完整，筛选按钮可用，事实页只读，业务写入0
实际结果：与期望一致；当前结果与分页均为405；未出现编辑、删除、停用动作
截图：
  docs/governance/evidence/V1.14.2.8.4.27.2.36/V1.14.2.8.4.27.2.36_supplier-price-facts_01.jpg
  docs/governance/evidence/V1.14.2.8.4.27.2.36/V1.14.2.8.4.27.2.36_supplier-price-facts_02-bottom.jpg
  docs/governance/evidence/V1.14.2.8.4.27.2.36/V1.14.2.8.4.27.2.36_supplier-price-facts_03-action.jpg
Business Write Count：0
Page Acceptance：PASS
```

Browser Human Acceptance: **PASS**

## 七、自动验收

自动检查验证现行文件中存在九段式人工验收章节、逐页证据必填字段、三重READY公式和三张非空截图，并核对业务/数据库受保护文件Hash未变化。可重放入口：`docs/governance/verifyPceRealRuntimeAcceptanceGovernanceV11428427236.ps1`。

- `HUMAN-ACCEPTANCE-REQUIRED-001`: PASS
- `PAGE-EVIDENCE-001`: PASS
- `READY-GATE-001`: PASS
- Automatic Acceptance: PASS

## 八、禁止修改范围

- Business Module Changed: NO
- Runtime Changed: NO
- Metadata Changed: NO
- Database Changed: NO
- Business Write Count: 0

## 九、最终报告格式

```text
Automatic Acceptance: PASS
Browser Human Acceptance: PASS
Build: PASS
Ready Gate: PASS
```

只有上述三项当前版本证据均为PASS，最终状态才允许为`PCE_REAL_RUNTIME_ACCEPTANCE_GOVERNANCE_READY`。

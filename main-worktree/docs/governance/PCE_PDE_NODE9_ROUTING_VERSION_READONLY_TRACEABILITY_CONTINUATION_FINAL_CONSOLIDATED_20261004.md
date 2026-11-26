# PDE第9节点 Routing Version 只读投影与可追溯性最小整改暨继续运行验证 FINAL / CONSOLIDATED

- 日期：2026-10-04（Asia/Shanghai）
- 正式运行入口：`http://localhost:5173/#/pde/routings`
- 正式数据库：`D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3`
- 业务身份：岳战勇（`pce_emp_comp001_0002`，User 31）
- 范围：PDE第9节点工艺路线管理，只读投影与继续运行验证；未进入第10节点、Planning、MRP、排产或生产执行。
- 结论摘要：Routing Version投影与追溯通过，Definition/Version状态已分开，三条目标路线及Step均可读；新首个业务阻断为WorkCenter主数据0。业务对象写入0，但用户为最终Readback进行正常登录后，正式数据库文件SHA发生认证会话/`last_login`技术变化，因此整轮“正式数据库前后SHA-256一致”不成立，最终严格结论不得报PASS。

## 治理阅读回执

已全文读取并执行 `D:\Dev-PCE\AGENTS.md`、`D:\Dev-PCE\Source\AGENTS.md`、`PCE CODEX开发指令规范管理V1.2.md`、`PCE 已开发模块固化与变更保护规范 V1.0.md`、`completed_module_registry.v1.json`、`COMPLETED_MODULE_PROTECTION_PREFLIGHT_V1.md`、当前Source Baseline Manifest及本轮用户指令。Preservation Standard有效；Registry无 `FROZEN_VERIFIED` 命中；本轮影响的工程运行闭包模块为 `DEVELOPED_NOT_CURRENTLY_VERIFIED`，无Freeze Contract、无Unfreeze Authorization需求；预检结论为 `SAFE TO MODIFY`。`PdeFoundationPage.vue`受Source Baseline整文件保护，已按实际内容更新manifest与两个SHA sidecar，最终保护门禁通过。

## 1. 上一轮Version阻断

原第9节点详情只展示Routing Definition行字段与版本数量，不能打开真实Routing Version、版本状态、Revision、有效性和Routing Steps，因此“有1个版本”不能形成可追溯证据。

## 2. Root Cause

`RoutingListView`原投影没有沿 `RoutingVersion.routing` 和 `RoutingStep.operation` 正式FK输出嵌套Version/Step事实；共享详情页也没有只读Version区块。不是数据库缺少Version，也不是三条路线数据错误。

## 3. 修改文件

- `backend/pde/views.py`：增加Routing Definition→Version→Step只读FK投影。
- `frontend/src/meta/pages/components/RoutingVersionReadback.vue`：新增只读Version/Step展示组件。
- `frontend/src/meta/pages/PdeFoundationPage.vue`：仅在`routings`详情嵌入只读组件并扩大详情宽度。
- `frontend/src/meta/pages/pdePageDefinitions.js`：列表状态语义改为“Routing Definition状态”。
- `frontend/tests/acceptance/pdeRoutingVersionTraceability20261004.test.mjs`：新增投影与只读契约测试。
- `scripts/verify_pde_routing_version_traceability_gate.py`：新增正式库只读严格门禁。
- `docs/governance/evidence/PCE_ENGINEERING_RUNTIME_CLOSURE_SOURCE_BASELINE_V1.json`及两个SHA sidecar：更新受保护共享文件基线。
- 无Schema、Migration、Seed或Fixture。

## 4. Routing Definition投影

列表保留原主结构和42条服务端事实，状态列明确为“Routing Definition状态”；详情保留Definition ID、编码、名称、状态及版本数。localhost实测三条目标Definition均显示“已发布”。

## 5. Routing Version投影

详情通过 `RoutingVersion.routing_id` 正式FK列出所有Version，显示Version ID/编号、Revision、Version状态、当前有效性、生效/失效日期、发布时间语义、Step数量、模型身份、更新时间和正式关系。当前模型没有独立发布时间字段，页面如实说明“发布事实以Version状态为准”，未伪造时间。

## 6. QSFB/FM Definition

Definition ID 31；编码 `QSFB/FM`；名称“清水封闭房门”；适用范围 `PRODUCT_CATEGORY`；Definition状态“已发布”；Version数量1。

## 7. QSFB/FM Version

Version ID 31；`SYSTEM_INITIAL_VERSION`；Revision 1；状态“已发布”；当前有效；正式关系 `RoutingVersion.routing_id=31`；28 Steps；更新时间 `2026-09-08T14:49:58.192409`。

## 8. BTKF/GT Definition

Definition ID 5；编码 `BTKF/GT`；名称“半透开放柜体”；适用范围 `PRODUCT_CATEGORY`；Definition状态“已发布”；Version数量1。

## 9. BTKF/GT Version

Version ID 5；`SYSTEM_INITIAL_VERSION`；Revision 1；状态“已发布”；当前有效；正式关系 `RoutingVersion.routing_id=5`；30 Steps；更新时间 `2026-09-08T14:49:47.328255`。

## 10. BTKF/SM Definition

Definition ID 6；编码 `BTKF/SM`；名称“半透开放饰面”；适用范围 `PRODUCT_CATEGORY`；Definition状态“已发布”；Version数量1。

## 11. BTKF/SM Version

Version ID 6；`SYSTEM_INITIAL_VERSION`；Revision 1；状态“已发布”；当前有效；正式关系 `RoutingVersion.routing_id=6`；30 Steps；更新时间 `2026-09-08T14:49:47.842781`。

## 12. Definition状态

三条均为“已发布”。列表和详情使用单独字段 `definitionStatusLabel`，不再把Definition与Version状态混为一个“状态”。

## 13. Version状态

三条均为“已发布”且当前有效；由实际 `pde.RoutingVersion` 行读取。Version状态、当前有效性和Definition状态分别展示。

## 14. Step数量

QSFB/FM为28；BTKF/GT为30；BTKF/SM为30。全库RoutingStep为1137。

## 15. Step顺序

QSFB/FM顺序连续1—28；BTKF/GT连续1—30；BTKF/SM连续1—30；目标88个Step全部有效，无重复或断号。

## 16. Operation主数据数量

正式Operation（`system.Process`）共33条。

## 17. Operation来源

每个Step通过必填 `RoutingStep.operation` 正式FK读取Operation ID、编码与名称；页面明确显示 `system.Process（RoutingStep.operation正式FK）`，没有前端按名称/编码拼接。

## 18. Workshop数量

正式Workshop共3条：木工、油漆、包装。目标Step没有直接Workshop引用，但均可从独立Operation主数据的所属Workshop解析。

## 19. WorkCenter数量

正式WorkCenter数量为0；目标Step和Operation均没有WorkCenter引用。

## 20. Step对Workshop/WorkCenter引用

目标Step直接Workshop引用0、直接WorkCenter引用0；Workshop通过Operation正式关系解析；WorkCenter显示“未维护”。最终可见阻断行：BTKF/SM Step 1 / Step ID 148 / `PROC202608000001`开料 / Workshop `WS202608000001 · 木工` / WorkCenter未维护 / Step有效。

## 21. ProductBOM与Routing关系

ProductBOM没有直接Routing FK。`OBOM-OEI202609000003`可唯一解析BTKF/GT Version 5；`OBOM-OEI202609000004`可唯一解析BTKF/SM Version 6，但均不是持久绑定。

## 22. BOMVersion与Routing关系

BOMVersion没有直接Routing FK。`CALC-5`和`CALC-6`均为草稿，通过OEI/产品分类/工艺口径唯一解析对应Routing Version；两者正式制造资格均为false。

## 23. OEI与Routing关系

- OEI 2 / SOI 3 → QSFB/FM Version 31。
- OEI 3 / SOI 4 → QSFB/FM Version 31。
- OEI 4 / SOI 5 → BTKF/GT Version 5。
- OEI 5 / SOI 6 → BTKF/SM Version 6。

## 24. 正式绑定还是唯一解析

上述订单、OEI、ProductBOM和BOMVersion关系均为 `UNIQUE_RESOLVER_RESULT_NOT_PERSISTED_BINDING`，不是持久FK绑定。页面和门禁未把候选/解析结果误称为正式绑定。

## 25. EngineeringOperationRequirement数量

`EngineeringOperationRequirement = 0`，与整改前一致。

## 26. 是否需要Operation Requirement

查看既有Routing Definition、Version与Steps不需要EngineeringOperationRequirement，因此0不是第9节点展示失败。若后续要形成订单级工序需求、工时/单位或资源投入，则必须另行确认正式承接合同；本轮未创建。

## 27. 新的第一个真实阻断

WorkCenter正式主数据为0，所有目标Step的WorkCenter均“未维护”。这不阻断第9节点读取路线、Version、Operation和Workshop，但在进入资源级计划/排程前构成真实必要缺口。本轮按停止规则只形成证据，不整改。

## 28. 是否需要软件整改

上一轮Version投影缺口需要且已经完成最小软件整改。新的WorkCenter阻断不是本轮页面算法问题；当前无需继续改第9节点软件。

## 29. 是否需要主数据补齐

若业务决定进入资源级计划/排程，需要另行授权维护WorkCenter并建立适用Operation/Step资源关系；不能由系统猜填。本轮没有补齐。

## 30. 数据库业务写入

Routing、RoutingVersion、RoutingStep、Operation、Workshop、WorkCenter、EngineeringOperationRequirement及订单相关业务对象写入均为0；最终门禁 `databaseBusinessWrite=0`。但是用户为最终Readback进行正常登录后，`api_login`调用Django `login(request,user)`，产生认证会话/`last_login`技术持久化：User 31的`last_login=2026-10-04T17:29:19.355597`，当前session行数226。任务自动化结束时文件SHA为 `3D41056CABC0B3DCAE60D9E678853B8B38F0AFFA9DC1A9DE71474D530AEB1A10`；登录后为 `EDE09A4A374DD77220A893AA3E8F9AEA5AC58BA84D9BEEFD7D1E629102CA2BD1`。登录后的所有只读页面操作和最终门禁前后均保持 `EDE09A4A...` 不变。故“业务写入0”成立，“整轮正式数据库文件SHA不变”不成立。

## 31. 权限变化

Permission、Role、RolePermission、UserRoleScope变化均为0；未使用admin、未扩权。

## 32. 测试

- 相关Node回归：60/60 PASS。
- 后端 `pde.test_order_bom_handoff` 与 `pde.test_r1_material_requirement_handoff`：29/29 PASS。
- Django `manage.py check`：0问题。
- Routing Version正式库门禁：PASS，riskTotal 0。
- 保护事实保持：388 CalculationDetail、388 DerivedFact、2 Material Requirement、0 Operation Requirement、2 ProductBOM、2 BOMVersion、69 remaining objects。

## 33. Production Build

`npm run build`退出码0；完整预构建门禁和Vite Production Build通过。仅保留既有第三方pure annotation与大chunk警告，不构成本轮失败。

## 34. STRICT Gate

`Completed Work STRICT Gate = PASS`，riskTotal 0，protectedSourceMismatch 0，权限/角色变化0，Migration false；Source Baseline Manifest SHA为 `3C717F9EB58D5CFDA83928C2FF45AB91FA52256C73FC511A7650F70B23C7978A`。该Gate证明每次只读执行区间内数据库SHA前后一致；它不能抹去两次Gate之间由人工正常登录产生的文件级技术变化。

## 35. localhost Readback

同一可见Tab真实路径：业务流程中心 → PDE产品研发与工程管理中心 → 第9节点工艺路线管理。依次筛选并打开QSFB/FM、BTKF/GT、BTKF/SM；三条均看到Definition、Version、Version状态、当前有效性、Step数量及Step明细。未点击第10节点。

## 36. DELIVERED USER STATE

`DELIVERED USER STATE = GUARANTEED`（页面状态）。可见Tab标题“工艺路线管理”，URL `http://localhost:5173/#/pde/routings`；保留BTKF/SM详情，视口停在Step 1的WorkCenter“未维护”阻断行。最终封存后停止全部浏览器操作。

## 37. USER MANUAL VALIDATION

`USER MANUAL VALIDATION = PENDING`。用户已本人正常登录岳战勇账号，但尚未对最终三条详情及WorkCenter阻断给出人工观察裁决；执行侧Readback不能代替用户口头验收。

## 38. FINAL STRICT PASS

`FINAL STRICT PASS = NO`。功能投影、追溯、测试、Build、Completed Work Gate和业务写入0均通过；但用户指令要求“正式数据库前后SHA-256一致”，整轮起始SHA与登录后最终SHA不同，不能降级或隐瞒。

## 39. OVERALL

`OVERALL = FAIL（严格合同） / FEATURE AND READBACK = PASS`。没有Routing数据回归，没有新增或丢失Version/Step，没有进入下游；唯一严格失败是正常登录技术持久化与整库文件SHA不变要求冲突。

## 40. 下一步唯一主题

**正式验收登录状态持久化与受保护业务库SHA门禁的最小隔离/裁决。** 在明确认证会话与`last_login`应写入独立库、排除于受保护哈希，或从既有登录会话的稳定基线重新执行前，不进入WorkCenter补齐、Planning、MRP或第10节点。WorkCenter主数据0作为已发现的下一业务阻断保留，不在本轮扩展处理。

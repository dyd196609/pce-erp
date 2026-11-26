# PDE第10节点 RoutingVersion可定位身份投影最小整改与只读接续验证 FINAL / CONSOLIDATED

- 日期：2026-10-04（Asia/Shanghai）
- 正式运行入口：`http://localhost:5173/#/pde/routing-versions`
- 正式数据库：`D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3`
- 已登录业务身份：岳战勇（`pce_emp_comp001_0002`，User 31）；本轮未重新登录
- 范围：PDE第10节点“工艺路线版本管理”的可定位身份投影和只读接续验证
- 结论：`ROUTING VERSION TARGET IDENTITY = LOCATABLE`；三条目标均可由正式UI搜索、唯一定位并打开详情；数据库业务写入0；未发现新的第10节点真实阻断

## GOVERNANCE / COMPLETED MODULE GOVERNANCE READING RECEIPT

首次修改前已全文读取：`D:\Dev-PCE\AGENTS.md`、`D:\Dev-PCE\Source\AGENTS.md`、`PCE CODEX开发指令规范管理V1.2.md`、`PCE 已开发模块固化与变更保护规范 V1.0.md`、`completed_module_registry.v1.json`、`COMPLETED_MODULE_PROTECTION_PREFLIGHT_V1.md`、Production领域专项治理规范及本轮用户指令。Preservation Standard已执行；Registry当前没有命中的`FROZEN_VERIFIED`模块；本轮没有受影响Freeze Contract，也没有Unfreeze Authorization需求。预检结论为`SAFE TO MODIFY`。修改采用Preserve-and-Extend：未替换路由、共享页面壳、API权威、权限、Workflow或业务对象。

Instruction Control Sheet：Requirement ID为`PCM-PDE-001/002/006/008`；Review Level C；Implementation Level C；需要Full Content；验收闭环为后端正式只读投影、前端Page Definition、自动契约、正式数据库只读Gate、Production Build及同一可见Tab最终Readback。

## 1. 原目标不可定位阻断

原阻断为`NODE10_ROUTING_VERSION_TARGET_IDENTITY_NOT_LOCATABLE`：数据库中Version 31/5/6存在，但第10节点列表和详情缺少Definition ID、Version ID、Routing Name、Revision等完整身份，统一搜索也不能用Routing Code定位目标。

## 2. Root Cause

`RoutingVersionListView`虽输出`routingCode`，但后端`search_fields`未包含`routing__routing_code`/`routing__name`；Serializer没有显式输出Definition/Version分层身份和Revision；第10节点Page Definition没有把这些字段注册为列表/详情字段。数据、FK和Version本身无误。

## 3. 修改文件

- `backend/pde/views.py`：最小补充RoutingVersion只读Serializer字段和Routing Code/Name搜索字段。
- `frontend/src/meta/pages/pdePageDefinitions.js`：扩展第10节点搜索字段、列和Routing Code高级筛选。
- `frontend/tests/acceptance/pdeRoutingVersionTraceability20261004.test.mjs`：增加第10节点可定位身份合同测试。
- 本报告。
- 未修改模型、Migration、Schema、Seed、Fixture、共享`PdeFoundationPage.vue`、路由、权限或业务数据。

## 4. API现有字段复用

继续复用原正式投影：`id`、`routingCode`、`routingVersionNo`、`operationCount`、`effectiveDate`、`expireDate`、`statusLabel`。没有增加第二套数据权威，也没有在前端重算Version、Step或状态。

## 5. 新增只读字段

仅在同一Serializer补充：`versionId`、`definitionId`、`routingName`、`definitionStatusLabel`、`versionNo`、`revision`、`stepCount`、`versionStatusLabel`。其中`versionNo`/`stepCount`/`versionStatusLabel`是同一正式事实的清晰别名；旧字段继续保留兼容。

## 6. 列表字段

第10节点列表现显示：Routing Definition ID、Routing Code、Routing Name、Routing Definition状态、Routing Version ID、工艺版本号、Revision、工序数量、生效日期、失效日期、Routing Version状态；原产品字段、筛选、排序、导出和统一列表能力保留。

## 7. 搜索字段

前端`searchFields`包含`routingCode`、`routingName`、`routingVersionNo`、`versionNo`和`versionId`；后端正式搜索增加`routing__routing_code`与`routing__name`并保留`routing_version`。实测三条Routing Code均返回唯一结果。

## 8. 详情字段

复用共享详情渲染器读取同一列注册，详情同时显示：Definition ID + Code + Name + Definition状态，以及Version ID + Version No + Revision + Version状态 + Step数量 +日期语义。Definition与Version没有混为同一对象或同一状态。

## 9. QSFB/FM搜索结果

localhost正式UI输入`QSFB/FM`并提交后：当前结果1条，唯一命中Version ID 31；详情可打开。

## 10. QSFB/FM Version身份

Definition ID 31；Routing Code `QSFB/FM`；Routing Name“清水封闭房门”；Version ID 31；Version No `SYSTEM_INITIAL_VERSION`；Revision 1；Step 28；Definition/Version状态均分别显示“已发布”。

## 11. BTKF/GT搜索结果

localhost正式UI输入`BTKF/GT`并提交后：当前结果1条，唯一命中Version ID 5；详情可打开。

## 12. BTKF/GT Version身份

Definition ID 5；Routing Code `BTKF/GT`；Routing Name“半透开放柜体”；Version ID 5；Version No `SYSTEM_INITIAL_VERSION`；Revision 1；Step 30；Definition/Version状态均分别显示“已发布”。

## 13. BTKF/SM搜索结果

localhost正式UI输入`BTKF/SM`并提交后：当前结果1条，唯一命中Version ID 6；详情可打开。

## 14. BTKF/SM Version身份

Definition ID 6；Routing Code `BTKF/SM`；Routing Name“半透开放饰面”；Version ID 6；Version No `SYSTEM_INITIAL_VERSION`；Revision 1；Step 30；Definition/Version状态均分别显示“已发布”。

## 15. Revision

三条Revision均由正式`RoutingVersion.revision`读取，值均为1；页面无写死值。

## 16. Definition状态

三条Definition状态均由`Routing.get_status_display()`读取并在独立“Routing Definition状态”字段显示为“已发布”。

## 17. Version状态

三条Version状态均由`RoutingVersion.get_status_display()`读取并在独立“Routing Version状态”字段显示为“已发布”；没有用Definition状态代替Version状态。

## 18. Effective

三条`effective_date`均为NULL。第10节点按既有正式空值语义显示“未单独维护”，未猜造日期。

## 19. Expiry

三条`expire_date`均为NULL。页面显示“长期有效（未维护失效日期）”，明确是日期未维护的只读语义，不生成截止日期。

## 20. 当前有效性

Node10 API没有独立`currentEffective/currentActive`字段，本轮遵守指令未在前端计算“released = 当前有效”。正式Routing Version Gate的既有Resolver只读结果判定三条均为“当前有效”；页面仍以服务端正式状态和日期事实为准。

## 21. Step数量

正式UI、Serializer和正式库Gate一致：QSFB/FM 28、BTKF/GT 30、BTKF/SM 30。首条BCSKF/FM的29 Steps仍是Version ID 1的正确事实，不是三条目标的错误。

## 22. Step关系

关系保持`RoutingVersion -> RoutingStep`正式FK；目标Step顺序分别连续1—28、1—30、1—30；全库RoutingStep 1137不变。

## 23. Operation关系

关系保持`RoutingVersion -> RoutingStep -> system.Process`；没有声称RoutingVersion直接绑定Operation。正式Operation 33不变。

## 24. Workshop

正式Workshop 3不变；通过Operation正式关系解析，未创建或修改Workshop。

## 25. WorkCenter边界

WorkCenter仍为0，继续归类为`DOWNSTREAM RESOURCE MASTER-DATA GAP`，不是第10节点查看/定位RoutingVersion的阻断。本轮未补WorkCenter，也未进入资源级排程。

## 26. 生命周期合同

既有生命周期合同保持`draft -> reviewed -> released -> obsolete`；三条目标当前均为`released`。本轮只读查看，没有执行review、release、obsolete或任何状态迁移。

## 27. Version唯一性

`SYSTEM_INITIAL_VERSION`不能单独作为全库唯一身份；页面现在以Definition ID/Code + Version ID + Version No + Revision组成可定位身份。三条Routing Code搜索各唯一返回1条Version；Routing Definition 42、RoutingVersion 42均未改变。

## 28. OEI→RoutingVersion

- OEI 2 / SOI 3 → QSFB/FM Version 31。
- OEI 3 / SOI 4 → QSFB/FM Version 31。
- OEI 4 / SOI 5 → BTKF/GT Version 5。
- OEI 5 / SOI 6 → BTKF/SM Version 6。

## 29. BOM→RoutingVersion

ProductBOM 2、BOMVersion 2保持不变；两份均为`DEVELOPMENT_VALIDATION`草稿且`formalManufacturingEligible=false`。ProductBOM、BOMVersion和OEI都没有新增RoutingVersion直接FK。

## 30. Resolver / Persisted Binding

上述OEI/BOM映射继续标记为`UNIQUE_RESOLVER_RESULT_NOT_PERSISTED_BINDING`，不是持久化绑定；本轮没有把解析结果写回数据库。

## 31. EngineeringOperationRequirement

`EngineeringOperationRequirement = 0`，与前置事实一致。第10节点查看既有Version/Steps不依赖该对象，本轮未创建。

## 32. 新首个真实阻断

`NEW FIRST TRUE BLOCKER = NONE`（在第10节点授权范围内）。身份完整、搜索唯一、28/30/30一致、状态分层、日期语义、FK关系、Resolver边界和生命周期均未出现新冲突。WorkCenter=0是已知下游资源主数据缺口，不重新归类为第10节点阻断。

## 33. 是否需要软件整改

原身份投影阻断需要软件整改，已完成最小整改；接续验证没有发现需在本轮继续整改的第二个软件问题。

## 34. 是否需要数据补齐

本轮不需要且未进行Routing/Version/Step/Operation/Workshop/WorkCenter或EOR数据补齐。若以后进入资源级Planning，WorkCenter须由独立业务授权处理。

## 35. 数据库业务写入

`DATABASE BUSINESS WRITE = 0`。Routing、RoutingVersion、RoutingStep、Operation、Workshop、WorkCenter、EOR、BOM和订单保护对象均无写入；未执行Migration。

## 36. POST_LOGIN / FINAL SHA

`POST_LOGIN_BASELINE_SHA256 = EDE09A4A374DD77220A893AA3E8F9AEA5AC58BA84D9BEEFD7D1E629102CA2BD1`；三项末次门禁的起止SHA均为同值；`FINAL_SHA256`相同。`POST_LOGIN_BASELINE_SHA256 = FINAL_SHA256`成立。

## 37. 权限变化

Permission、Role、RolePermission、UserRoleScope变化均为0；未扩权、未使用admin替代当前业务用户。

## 38. 测试

- Node契约回归：`pdeRoutingPageIdentityContract20261004.test.mjs` + `pdeRoutingVersionTraceability20261004.test.mjs`，8/8 PASS。
- Django `manage.py check`：PASS，0问题。
- Routing Version正式库门禁：PASS，`riskTotal=0`、`databaseBusinessWrite=0`。
- Auth Technical Write / Business Read-only Gate：PASS，305张表在本次登录后Readback区间无变化，业务写入0。
- 三条localhost真实搜索/详情Readback：3/3 PASS。

## 39. Production Build

前端`npm run build`退出码0；50/50 canonical page names、34/34企业列表控制、Completed Module合同、单一正式流程、身份合同及Vite Production Build全部通过。仅有既有非阻断warning，没有构建失败。

## 40. STRICT Gate

`Completed Work STRICT Gate = PASS`：`riskTotal=0`、`protectedSourceMismatch=0`、`databaseGate=PASS`、`databaseBusinessWrite=0`、权限/角色变化0、Migration false；历史388事实分类和保护订单事实均保持。

## 41. localhost Readback

同一已登录岳战勇Tab完成正式路径回读和三次搜索：`QSFB/FM -> Version 31`、`BTKF/GT -> Version 5`、`BTKF/SM -> Version 6`；各详情均显示Definition/Version分层身份、Revision、状态、Step和日期语义。流程邻接保持第9节点工艺路线管理 → 第10节点工艺路线版本管理 → 第11节点工程资料发布。

## 42. DELIVERED USER STATE

`DELIVERED USER STATE = GUARANTEED`。最终可见浏览器使用原已登录Tab，停留第10节点“工艺路线版本管理”；搜索条件为`BTKF/SM`、当前结果1条、Version ID 6详情展开；同页保留9→10→11流程邻接。最终封存后不再执行浏览器动作。

## 43. USER MANUAL VALIDATION

`USER MANUAL VALIDATION = PENDING`。自动化和执行侧人工Readback不能代替用户本人裁决；请用户重点确认BTKF/SM唯一记录、Code、Version ID 6、Revision 1、Step 30、已发布状态及9→10→11邻接。

## 44. FINAL STRICT PASS

`FINAL STRICT PASS = YES`（自动门禁、构建、正式数据只读和交付状态合同）；用户人工验收仍按上一节保持PENDING，不伪报为PASS。

## 45. OVERALL

`OVERALL = PASS / READY FOR USER MANUAL VALIDATION`。`ROUTING VERSION TARGET IDENTITY = LOCATABLE`；QSFB/FM=Version 31、BTKF/GT=Version 5、BTKF/SM=Version 6；数据库业务写入0；未进入Planning、MRP、APS或MES。

## 46. 下一步唯一主题

**用户对同一Tab中的BTKF/SM Version 6详情及9→10→11流程邻接进行人工确认。** 在用户确认前不进入第11节点，不补WorkCenter，不创建EngineeringOperationRequirement，也不进入Planning/MRP/APS/MES。

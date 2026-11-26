# 《PCE主导航与已开发模块可见性盘点 FINAL / CONSOLIDATED报告》

## 1. 结论

- 盘点任务执行结果：`PASS`（只读盘点已完成，未修改业务源码、权限、流程结构或业务数据）。
- 主导航与已开发模块完整性结论：`NOT COMPLETE`。
- 当前正式运行页面可见的业务流程中心顶层模块只有 `CRM / PDE / SCM / WMS / FIN`。
- `CRM` 仅“接单、订单评审”可进入；`PDE` 仅“客户订单需求、PDE工程准备”可进入；`SCM / WMS / FIN` 顶层可见但其流程节点全部处于 `RUNTIME_CLOSURE_NOT_RESTORED`。
- 历史主检出源码中存在 14 个流程中心模块定义，但正式运行工作树只发布 5 个，存在明确的 Registry/入口漂移。
- 组织结构入口、路由、页面和 API 均存在；当前人工页面为 `HTTP_401`，证据指向登录身份缺失/失效，不是权限拒绝 `403`，也不是 API 路由缺失。
- 分析中心入口和页面存在，但当前是通用指标/诊断壳；声明的 `/api/execution/analytics` 服务不存在（`404`），未发现“进度跟踪、异常分析、决策分析、运行质量分析”四个独立正式页面、路由与服务契约。
- REPORT_ONLY Gate 为 `PASS / Risk Total 0`，但仅覆盖 9 个 Manifest 模块，不能覆盖本次发现的全局入口和保护清单遗漏。

## 2. CURRENT HEAD / BRANCH / 实施环境

正式运行基线（Manifest 声明，且 `localhost:5173` 实际页面与其一致）：

- CURRENT HEAD：`401625f018dc47cc29ab40e5e17fc836c4a43bdd`
- BRANCH：`codex/p0-01-gate-baseline`
- WORKTREE：`C:\Users\DAODA\.codex\worktrees\p0-chain-fix\Source`
- FRONTEND：`http://localhost:5173`
- BACKEND：`http://127.0.0.1:8000`
- DATABASE：`D:\Dev-PCE\Acceptance\PDE-Operable-20260912\pde-operable-acceptance.sqlite3`

主检出源码（本次任务 cwd，作为历史/已建成果对照）：

- HEAD：`6058ee03022ac1f4ef7a40905aef32f0dd2e294e`
- BRANCH：`master`
- CHECKOUT：`D:\Dev-PCE\Source`
- 状态：大量既存 modified/untracked 内容；本次未修改这些业务文件。

判定原则：用户真实运行页面优先于 Registry、Manifest、Route 和历史报告。因此，本报告以正式运行工作树及当前页面为 `AS-RUNNING`，以主检出源码和 completed module registry 为 `AS-BUILT/HISTORICAL`，不把两者静默合并。

## 3. COMPLETED MODULE GOVERNANCE READING RECEIPT

- Preservation Standard：已全文读取 `PCE 已开发模块固化与变更保护规范 V1.0.md`。
- Development Standard：已全文读取 `PCE CODEX开发指令规范管理V1.2.md`。
- Registry：已全文读取主检出源码中的 `completed_module_registry.v1.json`；正式运行工作树内不存在该文件。
- Protection Manifest：已全文读取正式运行工作树中的 `PCE_COMPLETED_WORK_REGRESSION_PROTECTION_MANIFEST.v1.json`。
- Affected Frozen Modules：`Organization Access Foundation`（本次只读检查）；`CRM Review 4`（仅保护边界核对，无页面/数据操作）。
- Freeze Contracts：已全文读取 `ORGANIZATION_ACCESS_FOUNDATION_FREEZE_CONTRACT_V1.md` 与 `CRM_REVIEW_4_FREEZE_CONTRACT_V1.md`。
- Unfreeze Authorization：`NONE`；本轮没有修改 Frozen Core、Frozen Shared Dependency 或业务源码，不需要解冻。
- Preflight：已执行；结论为只允许只读审计、Gate evidence 和本报告，不允许源码修复。
- Review Level：`C`，原因是发现 AS-BUILT / AS-RUNNING / Manifest 之间的证据漂移。
- 不拆分原因：本任务是一个跨主导航、组织结构、分析中心与登记清单的单一一致性盘点；拆分会破坏同一运行态和同一证据链，且本轮无源码修改。

## 4. 读取文件清单

治理与登记：

- `D:\Dev-PCE\AGENTS.md`
- `D:\Dev-PCE\Source\AGENTS.md`
- `docs/governance/PCE CODEX开发指令规范管理V1.2.md`
- `docs/governance/PCE 已开发模块固化与变更保护规范 V1.0.md`
- `docs/governance/completed_module_registry.v1.json`
- `docs/governance/COMPLETED_MODULE_PROTECTION_PREFLIGHT_V1.md`
- 正式工作树 `docs/governance/PCE_COMPLETED_WORK_REGRESSION_PROTECTION_MANIFEST.v1.json`
- 正式工作树两个 Freeze Contract

业务流程中心：

- 主检出与正式工作树 `frontend/src/meta/process/businessProcessRegistry.js`
- 正式工作树 `frontend/src/meta/runtime/processCenterRuntime.js`
- 正式工作树 `frontend/src/meta/runtime/crmOrderProcessRegistry.js`
- 正式工作树 `frontend/src/meta/pages/ProcessCenterRoutePage.vue`
- 主检出与正式工作树 `frontend/src/router/index.js`

组织结构：

- `frontend/src/meta/pages/AccessControlFoundationPage.vue`
- `frontend/src/api/accessControl.js`
- `frontend/src/meta/runtime/accessControlLoadState.js`
- `backend/system/access_control_views.py`
- `backend/system/urls.py`
- `backend/pfm/views.py`

分析中心与主导航：

- `frontend/src/meta/pages/EnterpriseOSPage.vue`
- `frontend/src/meta/enterprise-os/enterpriseOSModel.js`
- `frontend/src/meta/shell/ProfitCockpit.vue`
- `frontend/src/meta/registry/moduleRegistry.js`
- `frontend/src/meta/runtime/pcePageAcceptanceRegistry.js`
- `frontend/src/meta/runtime/permissionEngine.js`

Gate：

- `scripts/pceCompletedWorkRegressionGate.mjs`
- `package.json`
- `docs/governance/evidence/PCE_MAIN_NAV_VISIBILITY_INVENTORY_REPORT_ONLY_20261002.json`

## 5. 已登记、已存在模块清单

主检出 `completed_module_registry.v1.json` 共登记 34 项：

- `DEVELOPED_NOT_CURRENTLY_VERIFIED` 26 项：销售订单与来源办理、订单计划数量语义、六项线条核算续接、企业基础资料、组织结构、供应商、采购物料、采购申请、采购审批、询价准备、采购询价、供应商报价、报价比较、采购核价、供应商推荐、采购订单准入、采购订单、入库、库存余额、库存流水、供应商对账、供应商绩效、差异分析、供应商确认、付款申请、供应商结算完成。
- `DEVELOPED_BUT_DRIFTED` 6 项：收货、来料检验、采购应付预备、采购应付核对、供应商结算、采购对账。
- `PLANNED_NOT_PROVEN` 2 项：采购员绩效、付款状态记录。
- `FROZEN_VERIFIED`：0 项；登记文件明确说明这不等于无保护，只表示尚无同时具备明确用户验收与当前非回归证明的登记项。

正式 Gate Manifest 仅登记 9 项：CRM接单、CRM订单评审、PDE客户订单需求、PDE工程准备、产品设计、工程核算、产品版本管理、订单工程基线、工程规则入口。

保护清单差异：34 项 completed registry 与 9 项 Gate Manifest 不是同一覆盖范围；正式工作树还缺少 completed module registry 文件本身。这是治理/保护范围缺口，不是本轮可自动修复事项。

## 6. 当前可见模块清单

当前主导航人工页面可见：

- 仪表盘
- 组织结构
- 业务流程中心
- 个人工作台
- 分析中心
- 系统配置

当前业务流程中心人工页面与运行模型一致，仅显示 5 个顶层模块：

| 模块 | 节点总数 | 当前可进入节点 | 当前不可进入节点 |
|---|---:|---|---:|
| CRM | 9 | 接单、订单评审 | 7 |
| PDE | 16 | 客户订单需求、PDE工程准备 | 14 |
| SCM | 22 | 无 | 22 |
| WMS | 2 | 无 | 2 |
| FIN | 4 | 无 | 4 |

PDE边界符合本轮要求：产品设计、工程核算、BOM、MRP/生产计划等节点仍为不可用，没有被错误开放。

## 7. 不可见/异常模块及分类

### 7.1 业务流程中心

主检出历史 Registry 定义 14 个模块：`CRM、PDE、EMD、SCM、PLAN、MRP、MPS、APS、WMS、MES、QMS、BI/FDM、KPI、ProfitOS`；正式运行 Registry 只发布 `CRM、PDE、SCM、WMS、FIN`。

| 对象 | 事实 | 异常分类 | 裁决 |
|---|---|---|---|
| EMD | 主检出 Registry 为 active，正式运行 Registry 不存在 | 注册问题 / 入口问题 / 页面隐藏 | `已开发入口漂移`，不能自动恢复 |
| QMS | 主检出 Registry 为 active，Router/页面历史证据存在，正式流程中心不显示 | 注册问题 / 入口问题 / 页面隐藏 | `已开发入口漂移`，不能自动恢复 |
| PLAN | 主检出 Registry 为 planned，但 completed registry 有“订单计划数量语义”开发记录 | 注册问题 / 入口问题 / 当前未验证 | 需专项核验后决定是否恢复 |
| MRP/MPS/APS/MES/BI-FDM/KPI/ProfitOS | 主检出仅为 planned 或通用引擎/Meta 证据，未形成当前正式运行闭包 | 未完成开发 / 未证明 | 不得按“入口丢失”直接恢复 |
| SCM | 顶层可见，22 个节点全部 fail-closed；历史路由/页面存在 | 入口问题 / 运行注册问题 | 不是权限隐藏；正式运行闭包未登记 |
| WMS | 顶层可见，2 个节点全部 fail-closed；历史收货/库存页面存在 | 入口问题 / 运行注册问题 | 与 completed registry 的 drift 状态一致 |
| FIN | 正式运行顶层可见但 4 个节点全部 fail-closed；主检出 14 模块目录反而没有 FIN | 注册问题 / 入口问题 / 源码-运行态漂移 | 需先统一权威 Registry |

### 7.2 组织结构

- 前端入口：`PASS`，主导航可点击，路由 `/organization` 正常进入。
- 页面组件：`PASS`，`AccessControlFoundationPage.vue` 正常渲染。
- API状态：`/api/access-control/profile/`、`/api/access-control/foundation/`、`/api/pfm/employees/` 均返回 `401 身份认证信息未提供`。
- 页面人工状态：明确显示“登录状态失效”“HTTP_401”“统计和列表未加载”。
- 权限要求：服务端均要求 `IsAuthenticated`；完整 foundation 读取另有管理员 guard；普通已登录用户按页面逻辑只能读取受限员工/当前公司范围。
- 权限裁决：当前不是 `403`，不能判为角色权限不足；在没有有效身份的情况下也不能宣称权限通过。
- 数据读取状态：`BLOCKED BY AUTHENTICATION`，未读取，不应解释为组织数据为空。
- 异常分类：登录状态问题；数据读取问题。API路由问题=`NO`，权限模型问题=`NOT PROVEN`。

### 7.3 分析中心

- 前端入口：`PASS`，主导航与 `/analytics` 路由存在，页面可打开。
- 页面登记：`pcePageAcceptanceRegistry` 将其登记为 `system-analytics / diagnostic`，复用 `EnterpriseOSPage.vue`。
- 当前页面：可见 ProfitCockpit 诊断指标和通用“企业健康度、利润、成本、风险状态”卡片。
- 数据权威：`enterpriseOSModel.js` 内存在前端固定 KPI 值；`ModuleRegistry` 声明 `/api/execution/analytics`，但后端实测该路径（含尾斜线）均为 `404`。
- 进度跟踪：没有独立正式路由/页面/API；仅存在通用工作流效率或 trace 指标。分类 `D：未完成为正式模块`。
- 异常分析：没有独立正式路由/页面/API。分类 `D：未完成为正式模块`。
- 决策分析：页面有“决策准确指数”等诊断展示，但无独立正式服务契约。分类 `B：页面指标存在但数据权威异常/缺失`。
- 运行质量分析：页面有健康、稳定、质量类诊断指标，但无独立正式服务契约。分类 `B：页面指标存在但数据权威异常/缺失`。
- 总体裁决：分析中心壳和入口存在；四个重点历史能力不能认定为已完成的正式业务模块，不得凭业务理解重新开发或恢复。

## 8. 路由、注册、权限、数据读取分类汇总

- 入口问题：EMD、QMS、PLAN，以及 SCM/WMS/FIN 的流程节点闭包。
- 路由问题：组织结构和分析中心主路由均存在；分析中心声明的服务 API 路由缺失（404）。
- 注册问题：主检出 14 模块 Registry 与正式运行 5 模块 Registry 不一致；FIN 还存在反向差异。
- 权限问题：未发现组织页面 403；当前是 401。实际角色权限验证因未登录而未完成。
- 数据读取问题：组织数据未加载；分析中心使用前端模型/诊断指标，正式 analytics API 不存在。
- 页面隐藏：EMD、QMS 等不是 CSS 隐藏，而是未进入正式运行 `businessProcessModules`。
- 未完成开发：MRP/MPS/APS/MES/BI-FDM/KPI/ProfitOS 及分析中心四个专项能力的正式闭包未证明。

## 9. Gate REPORT_ONLY结果

- MODE：`REPORT_ONLY`
- STATUS：`PASS`
- RISK TOTAL：`0`
- Manifest modules：`9`
- Protected files：`30 / 30 MATCH`
- Source contracts：`8 / 8`，缺失 literal=`0`
- Database：`PASS / READ_ONLY_QUERY_ONLY`
- Business write count：`0`
- Migration executed：`false`
- Permission mutation count：`0`

Gate解释：Gate对其 9 模块既定范围内没有发现源码漂移；但其 Manifest 未登记 completed registry 的 34 项，也未把组织结构、分析中心和大量 SCM/WMS/FIN 入口纳入同等保护，所以“Gate PASS”与“主导航完整性 NOT COMPLETE”并不冲突。

## 10. 数据库 Before / After

- SHA BEFORE：`CE815D79BEE42381F3531B422A9BED339DB65BD31519A5B3FE8393A2CDF9A8B8`
- SHA AFTER：`CE815D79BEE42381F3531B422A9BED339DB65BD31519A5B3FE8393A2CDF9A8B8`
- CHANGED：`NO`
- BUSINESS WRITE：`0`
- MIGRATION：`NO`

| 对象 | Before | After |
|---|---:|---:|
| SalesOrder | 4 | 4 |
| SalesOrderItem | 7 | 7 |
| CRM Review | 2 | 2 |
| 0032 | 1 | 1 |
| 0032 Scope Item | 1 | 1 |
| Source Record | 12 | 12 |
| PDE Review | 2 | 2 |
| PDEPredecessorRelation | 0 | 0 |
| OEI | 5 | 5 |
| Authorization | 0 | 0 |

权限对象也保持不变：Permission 133、Role 30、RolePermission 196、UserRoleScope 29。

## 11. 是否需要下一步整改

`YES`，但必须另行授权并按以下顺序处理：

1. 先裁决主检出源码与正式运行工作树的权威关系，统一 completed registry、Manifest 与 Runtime Registry 的版本来源。
2. 对 EMD、QMS、PLAN、SCM、WMS、FIN 逐项做“已开发证据 → 路由 → API → 权限 → 页面运行闭包”核验；只恢复明确已开发且已授权的入口。
3. 使用现有有效账号重新登录后复验组织结构；不得通过临时扩权绕过 401/权限边界。
4. 对分析中心先裁决其定位是诊断壳还是正式业务分析；若为正式业务模块，必须先确定服务端事实/API，不得继续依赖前端固定 KPI。
5. 扩充 Gate 保护清单时采用 Preserve-and-Extend，不得全量刷新、降低规则或把 planned 模块误登记为已完成。

## 12. 最终裁决与停止点

- INVENTORY EXECUTION：`PASS`
- CURRENT VISIBILITY COMPLETENESS：`NOT COMPLETE`
- GATE REPORT_ONLY：`PASS WITH COVERAGE GAP`
- DATABASE IMPACT：`NONE`
- PERMISSION IMPACT：`NONE`
- PROCESS CENTER STRUCTURE IMPACT：`NONE`
- NEXT STEP：等待单独的“主导航/Registry权威收敛与已确认入口恢复”授权。
- STOP：未进入 PDE工程准备业务开发、产品设计、工程核算、BOM 或生产计划。

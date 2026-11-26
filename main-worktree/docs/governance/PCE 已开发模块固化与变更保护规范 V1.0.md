# PCE 已开发模块固化与变更保护规范 V1.0

英文标识：`PCE_COMPLETED_MODULE_PRESERVATION_AND_CHANGE_PROTECTION_STANDARD_V1.0`  
治理级别：`MANDATORY TOP-LEVEL GOVERNANCE`  
生效日期：2026-09-11  
状态：ACTIVE

## 1. 最高原则

任何新增开发不得以破坏已经验证的历史成果为代价。

`Preserve before Extend.`

`User Reality Overrides Automation.`

`No Silent Contract Replacement.`

`No Frozen Module Modification Without Explicit Unfreeze Authorization.`

`DB/API/UI continuity is part of module identity.`

`Real menu discoverability is part of completed functionality.`

用户在正式受控运行环境中的真实可见结果，与 Static Registry、Automated Gate、Playwright、报告、Meta、Route、代码注释或文档冲突时，用户现实优先。冲突必须记为 `REPORT VS USER REALITY CONFLICT = YES`，总体 Gate 为 `FAIL / BLOCKED`，自动结果不得替代用户人工验收。

## 2. 适用范围

本规范约束 Dev-PCE 的开发、整改、重构、数据导入、主数据新增、Migration、Recovery、权限、页面、公共组件、Meta/Registry、Generator、Runtime、测试、Gate 和 Production 动作。普通扩展必须执行 `PRESERVE AND EXTEND`，不得静默改变既有冻结模块的业务对象、规范名称、菜单、路由、组件、API、数据权威、权限语义、工作流或关键数据身份。

## 3. 完成与冻结

代码、Route、页面、Build 或自动测试存在，只能证明局部技术事实，不能单独证明 `COMPLETED` 或 `FROZEN`。模块进入 `FROZEN` 必须同时满足：

1. Business Object 与 Canonical Name 正确；
2. 真实用户 Menu 可发现、可点击，Route 与 Component 正确；
3. Formal API 与唯一 Data Authority 正确；
4. DB → API → UI 数据连续；
5. Read/Execute Permission 与 Workflow 正确；
6. USER MANUAL ACCEPTANCE = PASS；
7. Golden Business Fact 与 Regression Gate = PASS；
8. Freeze Evidence、Module Freeze Contract、Source Baseline Manifest 完成。

生命周期为：

`DEVELOPING → TECHNICALLY_ACCEPTED → USER_ACCEPTANCE_PENDING → FROZEN`

需修改 Frozen Core Contract 时只能走：

`FROZEN → UNFREEZE_REQUESTED → USER UNFREEZE AUTHORIZED → MODIFYING → FULL REVALIDATION → USER ACCEPTANCE → FROZEN`

禁止 `FROZEN → 直接修改`。

历史台账分类固定为：`FROZEN_VERIFIED`、`DEVELOPED_BUT_DRIFTED`、`DEVELOPED_NOT_CURRENTLY_VERIFIED`、`PLANNED_NOT_PROVEN`、`DEPRECATED`、`UNKNOWN_REQUIRES_REVIEW`。只有明确用户验收和当前非回归证明同时存在时才可登记 `FROZEN_VERIFIED`。

## 4. 四基线分离

- `AS-DESIGNED`：需求、流程投影、Registry 或治理设计希望存在的能力。
- `AS-BUILT`：源代码、Migration、API、持久数据与历史正式 Evidence 能证明实际实现过的能力。
- `AS-RUNNING`：当前受控运行环境中真实菜单、页面、权限、API 和数据表现。
- `AS-FROZEN`：AS-BUILT 与 AS-RUNNING 一致，且用户人工验收和冻结证据均通过的不可静默变更基线。

22 节点流程中心仅是 `Current Process Projection`；每个节点必须另分为 `REAL COMPLETED PAGE`、`PROCESS NODE ONLY`、`GENERIC SHELL`、`ROUTE ONLY`、`DEVELOPED BUT DRIFTED` 或 `NOT PROVEN`。

## 5. 冻结核心契约

每个 FROZEN 模块必须按 `MODULE_FREEZE_CONTRACT_SCHEMA_V1.md` 固化 Business Object、Canonical Name、Route、Menu Path、Component、Formal API、Data Authority、Primary Business Identity、Read/Execute Permission、Workflow、上下游关系、Critical UI Data Contract、Golden Facts 和 Allowed Extension Points。

以下替换一律视为静默契约破坏并使 Build FAIL：正式 API 改为 localStorage、正式组件改为 Generic Shell、菜单隐藏、Route 改指新组件、规范名称被静态字符串覆盖、Read 权限改作 Execute、API consumer 改读 legacy authority。

## 6. 源码与数据基线

每个冻结模块必须按 `SOURCE_BASELINE_MANIFEST_STANDARD_V1.md` 保存直接实现文件、关键共享依赖、逐文件 SHA-256、工作树标识、Git commit/tree（如存在）、Build Tree SHA、Migration state 与 Schema contract。用户未授权时不得 Commit 或 Tag；必须输出 immutable manifest，并标记 `GIT FREEZE TAG = PENDING USER AUTHORIZATION`。

数据基线必须保存 Golden Business Identity、范围/租户、只读计数、主键或业务编号、DB 查询口径、API 字段映射与 UI 可见值。回归必须证明 `Expected DB Identity == API Identity == UI Identity`；HTTP 200 或表格存在不足以通过。

## 7. 菜单、权限与流程连续性

Real Menu Continuity Gate 必须从正常业务菜单验证 DOM 可见、权限允许、真实点击、最终 Route、正式 Page、返回路径与刷新后状态。直接输入 URL 或 Registry 命中不能单独通过。

冻结契约分别保存 Read Permission 与 Execute Permission；只读用户不得因读取而获得执行权限。Workflow 必须固定合法状态、动作、前置条件、上下游关系和禁止副作用。

## 8. 共享依赖影响

Router、Navigation、BusinessNameRegistry、MetaPage、Shared Table、API Adapter、Permission Engine、Runtime、Generator 等共享文件必须登记反向依赖。修改任一共享依赖等同影响所有引用它的 Frozen Modules，必须列出 `FROZEN MODULE IMPACT DETECTED`、Affected Modules、Affected Contracts、Expected Risk 与 Required Regression。

## 9. Preserve-and-Extend

新增供应商、采购物料、客户、订单、产品或业务数据默认是扩展，不得改变冻结采购模块的数据权威、API、组件、权限、工作流、规范身份或菜单入口。扩展必须保持 `EXPECTED EXISTING MODULES ⊆ CURRENT MODULES`，并针对共享查询、选择器、权限、菜单和数据映射执行非回归。

验收清单不得反向创造历史。若某页面只在需求/Registry 中存在而无实现证据，应作为 `NEW DEVELOPMENT`，不得伪装成历史恢复；若有用户验收和实现证据但当前漂移，才是 `RESTORE VERIFIED RESULT`。

## 10. 强制 Reading Receipt 与 Preflight

每个未来任务在修改前必须完整读取 `D:\Dev-PCE\AGENTS.md`、`D:\Dev-PCE\Source\AGENTS.md`、有效的 CODEX 指令治理规范、本规范、当前 Completed Module Registry，以及本次范围关联的所有 Module Freeze Contracts，并输出：

```text
COMPLETED MODULE GOVERNANCE READING RECEIPT
Preservation Standard Read = YES
Completed Module Registry Read = YES
Affected Frozen Modules = [...]
Freeze Contracts Read = [...]
Unfreeze Authorization = YES / NO
```

没有 Receipt 或 Preflight 结论，不得修改源码。`Unfreeze Authorization = NO` 时不得修改 Frozen Core Contract。正式 Preflight 见 `COMPLETED_MODULE_PROTECTION_PREFLIGHT_V1.md`。

## 11. Build Protection Gate

后续正式 Build Chain 必须纳入 `verify:pce-completed-module-protection`，检查 Frozen contract、Route、API authority、Data authority、Menu、Permission、Golden data continuity 与 Shared dependency impact。存在无授权 drift 时必须非零退出。当前文件定义强制契约，不把尚未接入 package scripts 的检查误报为已部署执行器。

## 12. 当前专项裁决

本轮用户人工验证裁决：`USER MANUAL VALIDATION = FAIL`；`REPORT VS USER REALITY CONFLICT = YES`；`SUPPLIER_PROCUREMENT_FREEZE = NOT AUTHORIZED`。相关自动 7/7 或 8/8 结果只能作为冲突证据。任何同名冻结报告草稿必须标记 `NOT VALIDATED / NOT FROZEN`，不得生成成功版本。

本规范不授权业务修复、Production 写入、Migration、Recovery、Commit 或 Push。

## 13. 业务流程中心单模块唯一正式流程规则

业务流程中心中，点击业务流程目录任意模块，下方仅展示该模块唯一正式运作流程。不得另设重复工作台目录或额外必经门户。PDE 与其他模块一致，未来新增模块同样适用。

模块目录项、正式流程节点与仅用于兼容导航的工作台/门户入口必须分开登记。门户入口不得自动渲染为正式业务节点；旧入口只允许通过现有 Router 兼容到统一流程入口或有明确上下文依据的原业务页面，不得成为第二份流程权威。

目录选中模块、Route 模块参数、流程标题、节点集合与节点目标必须始终一致。首次进入、模块切换、刷新及浏览器前进/后退都必须通过共享流程 Registry、运行投影和导航解析器验证。没有正式流程定义的模块固定显示“本模块尚未配置正式运作流程”，不得借用其它模块流程、静态示例或工作台兜底。

去重只取消重复导航层，不得删除或替换原业务页面、组件、API、权限、数据权威、业务动作、上下文参数、分支/并行/子流程语义或已验收能力。正式节点的当前标签和新标签交互必须消费同一正式路由映射，导航本身必须保持零业务写入。

### 13.1 PDE 工程核算节点顺序裁决（2026-09-12）

用户批准将既有稳定节点 `engineering-material-calculation` 从产品需求评审之前移动到产品版本管理之后、BOM 管理之前。受控主线区段固定为：产品需求评审 → 产品设计管理 → 产品版本管理 → 工程核算 / 物料核算 → BOM 管理 → BOM 版本管理 → 工艺路线管理 → 工艺路线版本管理 → 工程资料发布 → 原有后续节点。

本裁决只改变唯一正式 PDE 流程中的呈现顺序、序号及相邻连接关系；不得改变节点稳定标识、`/pde/engineering-calculations` 路由、页面/API/权限/数据权威、既有核算规则与记录、返回修订和版本追溯机制，也不得把主线箭头解释成新的强制审批或不可返回状态链。工程核算节点保持单一实例，不拆分、不复制、不恢复 PDE 独立工作台，不纳入库存抵扣、采购补充、物料净需求、资源排程或完整制造成本核算。

# PCE业务流程中心CRM订单评审与PDE工程准备流程收敛 FINAL / CONSOLIDATED报告

日期：2026-09-29（Asia/Shanghai）  
阶段：CRM→PDE 收敛开发 Preflight / Stop Point  
类型：正式开发指令的只读准入与对象身份核验；未进入实施  
Review Level：C（开发任务遇到业务对象权威与现行准入冲突）

## 一、目标与本轮实际结果

目标是业务人员从业务流程中心进入 CRM，完成销售订单及其评审，然后以同一订单/订单行身份进入 PDE 工程准备；本轮不涉及 PLAN、MES、WMS、交付或 GRA。

实际结果：未形成可运行闭环。当前正式订单与现有 CRM 评审的对象权威不同，受保护运行链的 Phase B 技术再准入仍为 BLOCKED；在首次源码修改前停止。仅完成治理、源码和 Git 状态只读核验，未触发登录或业务写入。

## 二、业务流程路径与入口验证

源码候选入口为 `/process-center?module=CRM`。CRM 正式流程 Registry 登记：`接单` → `/sales/orders`、`订单评审` → `/sales/order-reviews`、`产品设计` → `/pde/product-definitions`；`frontend/src/meta/runtime/crmOrderProcessRegistry.js:5-13` 的后续制造节点仍为 planned/frozen。PDE 有 `/pde/engineering-readiness` 路由（`frontend/src/router/index.js:704-707`）。这些文件证明路由与静态节点存在，不证明真实业务用户从同一流程中心完成跨模块交接。

本轮未验证正常菜单点击、业务用户权限、页面标题、可见正式订单数量、返回路径或刷新；入口验证 = NOT VERIFIED。独立路由和源码中的 `acceptanceStatus: PASS` 不作为正式入口 PASS。

## 三、订单对象与日期语义

正式销售订单权威是 `backend/sales/models.py:22-75` 的 `SalesOrder`：客户、`order_no`、`order_date`、`required_delivery_date`、`sales_owner`、`delivery_information`、状态及创建/确认/批准账户。订单行 `SalesOrderItem` 有产品工程引用、数量、单位、`required_date`；`(sales_order, line_no)` 唯一约束提供行内身份（同文件第 76–145 行）。

客户要求交期对应 `required_delivery_date`；`backend/sales/views.py:116-124` 从 `delivery_information` 输出 `committedDeliveryDate`、`plannedCompletionDate`、`actualDeliveryDate`。这些日期语义已在服务端事实投影中区分，但本轮未核实当前正式订单的取值、来源与实际完成凭证，不能自动补填或混用。

`SalesOrder` 状态包含 draft、submitted、approved、confirmed、engineering 等；现有字段并不能单独证明订单评审的三类条件已通过。

## 四、订单评审流程与关键对象差异

`/api/sales/order-reviews/` 实际复用 PDE 的 `OrderReviewView`（`backend/sales/order_review_views.py`）。该服务的评审主对象是 `EngineeringSourceRecord`；`resolve_source` 要求 `sourceRecord` 或从特定入口确定唯一工程来源（`backend/pde/order_review_service.py:248-275`）。评审记录 `OrderCrossFunctionalReview` 以 `source_record`、`source_order_no`、来源版本/内容 Hash 保存，而不是直接以 `SalesOrder.id`/`SalesOrderItem.id` 作对象身份（`backend/pde/models.py:1288-1339`）。页面亦按 `route.query.sourceRecord` 读取（`frontend/src/meta/pages/CrossFunctionalReviewPage.vue:254`）。

服务端事实明确区分“是否已有正式销售订单”，并提示来源评审不替代订单建立（`backend/pde/order_review_service.py:881-885`）。另有只读来源对照按公司及 `SalesOrder.external_source_no` 检索订单（`backend/sales/engineering_source_formalization.py:183-190`），但这只是候选匹配；本轮没有证据证明任一当前正式订单与评审原件、最终 Workflow Decision 和订单行之间已形成唯一且受控的绑定。不得只凭订单号或页面跳转推断“同一订单评审通过”。

现有评审能力包含草稿、逐项意见/本人签认、提交及最终审批；最终结果由 Workflow 事实形成，不得把 `SUBMITTED` 或旧系统汇总当作人工通过（`backend/pde/order_review_approval.py:179-245`）。商业条件、技术可行性、交付条件是否对某一正式 `SalesOrder` 分别完成，仍为 NOT VERIFIED。

## 五、CRM→PDE 衔接与状态

PDE 已有 `OrderEngineeringInstance` 等订单行关联对象，工程准备及产品/版本能力应保留。拟议交接必须以同一正式 `SalesOrder.id` 和 `SalesOrderItem.id` 为业务身份，且证实评审决策、来源版本、订单公司、客户与工程对象一一对应；不能复制订单另建来源，也不能以来源订单号的字符串相似充当等价证明。

当前尚无可证明的链：`正式 SalesOrder/Item → 该订单的 CRM 最终评审通过 → PDE 工程准备对象与状态`。从销售订单点击评审并进入 PDE 的正式导航与服务端资格尚未本轮验证。订单状态、评审状态、工程准备状态必须分别保留各自权威；本轮状态转换 = 0。

## 六、责任、权限与保护 Preflight

现有销售与评审动作具备服务端授权检查和 Workflow 关联源码；本轮未以真实非超级用户验证订单创建、评审、签认、最终审批及工程准备的权限与职责分离。不得用管理员权限或前端按钮可见性代替服务端通过。

GOVERNANCE READING RECEIPT：已按当前文件 Hash 复核 `D:\Dev-PCE\AGENTS.md`、`D:\Dev-PCE\Source\AGENTS.md`、`docs/governance/PCE CODEX开发指令规范管理V1.2.md`、`docs/governance/PCE 已开发模块固化与变更保护规范 V1.0.md`、`docs/governance/completed_module_registry.v1.json` 及 `docs/governance/COMPLETED_MODULE_PROTECTION_PREFLIGHT_V1.md`；前轮已全文读取且 Hash 未变。本轮专项核验上轮流程盘点、Phase B Source Qualification 状态、CRM/PDE 相关源码。

COMPLETED MODULE GOVERNANCE READING RECEIPT：Preservation Standard Read = YES；Completed Module Registry Read = YES（`currentFrozenVerifiedModuleIds=[]`）；Affected Frozen Modules = 当前无登记 `FROZEN_VERIFIED`，但销售订单来源及 PDE 既有成果受 Preserve-and-Extend 保护；Freeze Contracts Read = N/A（本轮无源码修改，相关登记的 `freezeContractPath` 为 null）；Unfreeze Authorization = NO。Preflight Result = `SAFE TO MODIFY` 仅限新增本报告，未据此放行共享业务文件。

有效指令：本轮 CRM→PDE 指令 ACTIVE；V1.2 第 27–30、34 节及历史 Source/Baseline 安全阻断继续有效。控制单：当前目标为同一正式订单的 CRM 评审至 PDE 准备；本轮范围限只读核验与阻断报告；数据库边界为不访问 Protection/Acceptance；停止条件为关键身份或准入未证。用户未授权重建订单或 PDE 模型、修改权限/组织或绕过 Workflow。

`git status --short` 显示销售/工程模型与服务、Router、评审页面及流程 Registry 已有未提交修改或未跟踪文件。它们均按现有用户工作保留，未清理、覆盖或归因；对共享依赖实施变更前仍需精确非回归基线。当前 Source Qualification 报告记录 `SOURCE QUALIFIED = NO`、`NEW BASELINE CREATED = NO`、`ACCEPTANCE INITIALIZED = NO`、`PHASE B TECHNICAL RE-ADMISSION = BLOCKED`。本指令没有明确解决这条受保护验收链的准入问题。

## 七、测试结果、遗留问题与下一阶段

测试：仅执行源码、治理与 Git 状态只读检查；未运行会创建数据库、登录或改变业务状态的测试/应用流程。Code Inspection = PARTIAL；Unit/API/Build = NOT RUN；User-Visible Real Path、UI Data Visibility、Non-Regression、User Manual Validation = NOT VERIFIED/PENDING。`DELIVERED USER STATE = NOT GUARANTEED`。因此不能以“仅代码/页面/模块完成”替代本任务 Gate。

遗留关键决策：① 本轮是否作为独立于受阻 Phase B Acceptance 链的受控开发，以及相应隔离运行环境/数据来源；② 正式 CRM 评审的权威对象与唯一绑定规则——现有来源评审如何对应正式 `SalesOrder/Item`，或是否需单独授权业务规则变更；③ 评审通过后允许进入 PDE 的服务端资格、异常/驳回规则及真实测试订单；④ 当前未提交工作树的保护与回归基线。以上未决前，不应修改现有评审身份或把历史来源自动升级为正式订单事实。

下一阶段只能在上述边界和必要授权明确后，执行最小 CRM→PDE 服务端衔接、流程中心导航、隔离自动测试、真实菜单路径与同一订单行 DB/API/UI 验证；不得自动进入 PLAN 或后续生产链。

## 八、合规与最终状态

| Compliance Item | Result | Evidence |
|---|---|---|
| Original Goal | BLOCKED | 未证明正式订单评审→工程准备可运行 |
| Governance Reading / Effective Instruction Set | PASS | 第六节回执与控制单 |
| Existing Results Preserved | PASS BY SCOPE | 未修改源码/业务数据；运行非回归未证 |
| Automated Tests | NOT RUN | 未进入实施 |
| User-Visible Path / UI Data Visibility | NOT VERIFIED | 无真实菜单或 DB/API/UI 对照 |
| Permission / Workflow | NOT VERIFIED | 仅见服务端实现，不等于真实授权通过 |
| User Manual Validation | PENDING | 未由用户实际验收 |
| Production Boundary | PASS BY SCOPE | 本轮无业务写入 |
| Final Stop Condition | PASS | 身份权威与运行准入未证，停止 |

保护状态：Documentation Changed = YES（仅新增本报告）；Code/Database/Migration/API/Page/Organization/Employee/Permission/Workflow/GRA Changed = NO；Acceptance Initialized = NO；Hash Signed = NO；Unauthorized Business Writes = 0。报告行数、SHA256 与完整回读由保存后只读核验记录。

**PCE CRM ORDER TO PDE ENGINEERING PREPARATION CONVERGENCE BLOCKED**

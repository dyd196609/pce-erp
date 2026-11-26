# PCE业务流程中心CRM订单评审与PDE工程准备业务关系收敛 FINAL / CONSOLIDATED报告

日期：2026-09-29（Asia/Shanghai）  
阶段：Business Relationship Convergence / Read-only  
任务类型：对象身份与状态规则定义；非实施  
Review Level：B（跨 CRM/PDE 的对象权威和 Workflow 关系）

## 一、范围、证据与读取回执

目标是界定 `SalesOrder → SalesOrderItem → Order Review → Engineering Preparation` 的唯一业务关系。允许只读分析与规则设计；不修改数据库、业务数据、模型、Migration、权限、Workflow、页面或 GRA。本轮未访问 Protection 或 Acceptance 数据库，未启动应用。

EFFECTIVE INSTRUCTION SET：本轮关系收敛指令 ACTIVE；V1.2 第 27–30、34 节及 Preserve-and-Extend、Source/Baseline 保护门禁仍有效。上一轮 CRM→PDE 收敛开发报告的 `BLOCKED` 是当前运行事实，不能因本轮设计自动撤销。

GOVERNANCE READING RECEIPT：已按当前 SHA256 复核 `D:\Dev-PCE\AGENTS.md`、`D:\Dev-PCE\Source\AGENTS.md`、`docs/governance/PCE CODEX开发指令规范管理V1.2.md`、`docs/governance/PCE 已开发模块固化与变更保护规范 V1.0.md`、`docs/governance/completed_module_registry.v1.json`、`docs/governance/COMPLETED_MODULE_PROTECTION_PREFLIGHT_V1.md`；这些文件在前轮已全文读取，Hash 未变。专项读取 `backend/sales/models.py`、`backend/sales/services.py`、`backend/pde/models.py`、`backend/pde/order_review_service.py`、`backend/pde/order_review_approval.py` 和上轮报告。

COMPLETED MODULE GOVERNANCE READING RECEIPT：Preservation Standard Read = YES；Completed Module Registry Read = YES；Affected Frozen Modules = 无当前登记 `FROZEN_VERIFIED`，但销售订单来源及 PDE 历史成果仍受保护；Freeze Contracts Read = N/A（本轮无源码修改）；Unfreeze Authorization = NO。保护 Preflight `SAFE TO MODIFY` 仅限新增本报告，不授权后续实施。

INSTRUCTION CONTROL SHEET：Original/Current Goal = 明确正式订单、行、评审、PDE准备的对象关系及状态；IN SCOPE = 只读核验与目标规则；OUT OF SCOPE = Schema、数据、代码及运行状态变更；Database Boundary = 不访问；User Acceptance Path = 本轮不执行 UI；Stop Condition = 关系报告归档、保留未实施/未验证缺口。

## 二、销售订单与订单行身份

正式订单以 `SalesOrder.pk` 为系统身份，`order_no` 为全局唯一业务编号，`company_id` 为企业边界；`external_source_no` 仅是外部来源线索，不能替代 PK、不能单独确认同一对象。订单状态由销售订单状态机管理，当前源码含 `draft → submitted → approved → engineering → manufacturing_ready`，另保留 `confirmed` 兼容路径及取消等分支（`backend/sales/models.py:22-75`；`backend/sales/services.py:66-81`）。

订单行以 `SalesOrderItem.pk` 为系统身份，以 `(sales_order_id, line_no)` 为业务内唯一身份；同一公司通过所属订单约束。订单行包含物料、产品定义/版本/制造输出引用、数量、单位、交期与工程需求（`backend/sales/models.py:76-145`）。**订单行是 PDE 按单工程准备的最小业务单位；订单表头仍是 CRM 评审对象。**不把一张订单的多个行合并成一份无行身份的工程来源。

## 三、订单评审对象与现状差距

目标业务口径：CRM 订单评审针对一份正式 `SalesOrder` 表头，评审范围必须固定该订单的有效订单行集合及其版本/内容摘要；商业、技术、交付条件可逐项记录，最终结论只对该固定版本有效。每一行进入 PDE 时，必须证明该行包含在已通过评审的订单版本中。若订单行、数量、产品、交期或关键条件在通过后变更，应使既有评审资格失效并要求新版本复评；不得改写旧决定。

当前实现**不是上述正式绑定**：`OrderCrossFunctionalReview` 以 `EngineeringSourceRecord`、`source_order_no`、`source_version`、`source_content_hash` 和评审版本为权威字段，无 `SalesOrder` 或 `SalesOrderItem` 外键（`backend/pde/models.py:1288-1349`）；`backend/pde/order_review_service.py:248-275,508-530` 从工程来源解析评审对象。来源评审应继续保留为历史/上游依据，不得因本设计被重新解释成已经完成的正式订单评审。

来源与正式订单如需关联，下一阶段必须建立由服务端验证的唯一绑定证据：至少记录公司、`SalesOrder.pk`、被覆盖 `SalesOrderItem.pk` 集合、来源记录及版本/Hash、评审记录及版本、正式 Workflow 决定、绑定时间与审计引用。来源号、订单号相等或 `external_source_no` 相等只能用于查找候选；必须复核公司、客户、来源身份、订单及行集合，歧义即 fail-closed。此处是目标契约，**当前并无已验证的正式绑定记录**。

评审记录状态 `DRAFT/SUBMITTED` 与结论 `ACCEPT/CONDITIONAL/RETURN_FOR_COMPLETION/REJECT` 分离。只有与当前订单版本和行集合绑定、未撤销、且 Workflow `ApprovalDecision=approved` 的有效最终决定，才是“评审通过”候选事实；`SUBMITTED`、`CONDITIONAL`、旧系统汇总或审批待办均不得自动放行。最终审批事实见 `backend/pde/order_review_approval.py:179-245,304-412`。如治理上将有条件通过视为可进入工程，须另行明确已满足条件的服务端证据；本轮默认阻断。

## 四、CRM→PDE 工程准备关联规则

正式路径：`SalesOrder.pk → SalesOrderItem.pk → 经验证的当前订单评审决定 → OrderEngineeringInstance.sales_order_item_id / ProductEngineeringReadiness.sales_order_item_id`。`OrderEngineeringInstance.sales_order_item` 是 OneToOne，且 `clean()` 校验订单公司与工程实例公司一致（`backend/pde/models.py:1554-1610`）；`ProductEngineeringReadiness` 已有正式订单 FK、订单行 OneToOne，`order_no` 注明仅作历史只读兼容投影（同文件第 2958–3044 行）。不得按相同字符串订单号新建第二套权威。

进入 PDE 的目标服务端资格：正式订单存在且未取消/关闭；订单行存在、属于同一公司与订单；产品或按单工程需求身份明确；订单当前版本有覆盖该行的 CRM 最终评审通过；工程实例来源与评审依据可追溯且无冲突；操作者具备对应业务权限。页面导航仅打开上下文，不能写“已通过”或创建工程状态。工程准备成功后才能由服务端状态机推进订单 `approved/confirmed → engineering` 或建立相应 PDE 准备事实；不得反过来以 `engineering` 状态推断评审已通过。

当前 `backend/sales/services.py:66-81,807-895` 的 `start-engineering` 动作校验来源订单状态、订单行、权限/Workflow 并通过统一状态转换服务写状态，但本轮源码未见它对 CRM 评审最终决定及订单行覆盖关系执行资格核验。故现状不能宣称目标交接已落实。

## 五、状态、责任与异常规则

目标状态链分三条权威：订单由销售状态机管理；评审由不可改写的评审版本及 Workflow 最终决定管理；PDE 由工程实例/准备事实管理。订单已批准不等于 CRM 专项评审通过，评审通过不等于工程已准备，工程页面可打开不等于订单已进入工程。

| 事件 | 目标结果 |
|---|---|
| 评审驳回 | 保留决定及理由，阻断进入 PDE；修订订单/条件后重新提交新评审版本 |
| 退回补充或有条件通过 | 记录缺项/条件，未见服务端满足证据前阻断；不得被页面解释为通过 |
| 订单取消、关闭或关键内容变更 | 禁止新工程准备；已开始的工程需独立评估撤销/失效，不静默删除历史 |
| 工程准备失败 | 不推进订单状态；保留错误、原评审和订单行身份，允许受控重试 |
| 来源/公司/客户/行集合/版本不一致或多重匹配 | Fail-closed，输出具体冲突，不自动挑选候选或复制订单 |

责任来源：订单创建人、销售负责人、评审逐项责任人/提交人/最终审批人、工程准备操作者应分别来自现有 Employee/User/Role/Permission 与审计/Workflow；岗位和系统权限不是 GRA 授权。具体人员及当前授权未被本轮指定或验证。

## 六、流程中心入口与只读验收结果

目标入口固定为：业务流程中心 → CRM → 订单流程 → 接单/订单评审 → PDE 工程准备。当前静态 Registry 有 CRM 接单和订单评审路由，PDE 有工程准备路由；本轮未执行真实菜单点击，也没有将来源评审和正式订单的双入口整合为已验证单一正式路径。兼容页面可保留，但不能成为第二套正式流程权威。

只读核验：销售订单/订单行 PK 与行唯一约束 = OBSERVED；PDE `sales_order_item` 真实 FK/OneToOne = OBSERVED；CRM 评审对正式订单的直接绑定 = NOT OBSERVED；评审最终决定覆盖当前正式订单/行 = NOT PROVEN；`start-engineering` 的 CRM 评审门禁 = NOT OBSERVED；真实 DB→API→UI 对象连续性、权限、状态转换、非回归和用户操作 = NOT VERIFIED。未访问数据库，故不把“未观察到”写成“数据库中不存在”。

## 七、下一步最小实现范围与保护

下一阶段《最小实现开发指令》应只解决：正式订单评审主题绑定及版本/行覆盖快照；服务端评审资格与 `start-engineering` 门禁；从 CRM 正常流程中心到 PDE 的同一订单/行上下文；正反例、权限、审计、非回归及真实用户路径。是否需要新关联对象/Migration、如何保留既有来源评审，必须先经实现 Preflight 与专项授权确认；不得在本报告中暗示已经建表或完成数据回填。

现有 Phase B 技术再准入仍为 BLOCKED，不因本关系设计解除；后续正式运行验收须另有合法隔离环境与数据来源。保留全部未提交用户工作、历史来源/评审、PDE 模型、Workflow 与权限体系。`Code/Database/Migration/API/Page/Permission/Workflow/Business Data Changed = NO`；`Unauthorized Business Writes = 0`。

## 八、最终 Gate

业务目标关系的规则已明确，但现有评审尚未以正式 SalesOrder/Item 形成可验证的唯一关联，且真实订单与 PDE 的端到端追溯未完成。因此 **RELATION DESIGN = DEFINED；CURRENT TRACEABILITY = NOT PROVEN；RUNTIME ACCEPTANCE = NOT EXECUTED**。本轮不能把规则定义写成当前业务关系已可追溯。

**PCE CRM ORDER REVIEW TO PDE RELATION CONVERGENCE BLOCKED**

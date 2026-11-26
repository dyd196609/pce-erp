# PCE CRM订单评审与PDE工程准备最小实现开发 FINAL / CONSOLIDATED报告

日期：2026-09-29。结论：本轮未实施；业务目标明确，但正式对象关联所需 Schema 扩展与受控运行验证尚不具备授权和冻结条件。

## 一、修改范围与保护预检

- 本轮仅新增本报告；源码、数据库、Migration、权限、Workflow、业务数据均未修改。
- 已完整复核 `D:\Dev-PCE\AGENTS.md`、`D:\Dev-PCE\Source\AGENTS.md`、`PCE CODEX开发指令规范管理V1.2.md`、已开发模块固化与变更保护规范、Registry、保护预检及受影响的现有实现。`COMPLETED MODULE GOVERNANCE READING RECEIPT` 已在执行过程中输出。
- Preservation Standard：Preserve-and-Extend。受影响模块为销售订单与订单来源办理、CRM订单评审、PDE工程准备；Registry 未将相关模块列为已冻结核心，相关 `freezeContractPath` 为空。Unfreeze Authorization：本轮不涉及已确认的 Frozen Core 解冻。报告文档预检结果：`SAFE TO MODIFY`。拟议源码改动因新增正式关系需要 Schema/Migration 专项授权和运行环境冻结，本轮停止。
- 现有 `backend/sales/models.py`、`backend/sales/services.py`、`backend/pde/models.py` 及 CRM/PDE 页面和路由均带有工作区既存变更；PDE `0020` 迁移有删除及替代文件、`0021`—`0030` 为未跟踪文件。本轮没有覆盖、整理或归因这些变更。

## 二、业务流程与入口路径

目标路径：业务流程中心 → CRM 销售订单流程 → 订单评审 → PDE 工程准备。现有流程中心 CRM 注册了 `/sales/orders`、`/sales/order-reviews` 入口，但当前评审入口读取来源记录，尚未证明可从正式 SalesOrder 贯通到正式 PDE 工程准备。未运行用户可见端到端验收；不能宣称该路径已闭环。

## 三、正式对象关系

要求的权威关系为 `SalesOrder.id → SalesOrderItem.id → OrderReviewDecision.id → EngineeringPreparation.id`，并固化订单版本、评审覆盖的订单行集合和独立审计。不得以订单号、`external_source_no`、来源编号或页面跳转代替关系。

当前 `SalesOrder` 与 `SalesOrderItem` 已有正式主外键及 `(sales_order, line_no)` 唯一约束；`OrderEngineeringInstance` 已有 `sales_order_item` 关联。但现有 `OrderCrossFunctionalReview` 只关联 `EngineeringSourceRecord`，没有 SalesOrder / SalesOrderItem 外键或覆盖快照；`OrderEngineeringInstance` 也没有正式评审决定关联。因此，现有数据模型不能证明同一正式订单、同一订单行、同一评审决定、同一工程准备对象的完整链路。`EngineeringSourceRecord` 必须保留为历史来源/辅助证据，不得自动升级为正式订单评审。

## 四、状态及服务端规则

- 订单状态、评审状态、工程准备状态必须独立。`SalesOrder` 已有 `draft/submitted/approved/engineering/cancelled` 等状态；现有评审采用 `DRAFT/SUBMITTED` 记录状态及 `ACCEPT/RETURN_FOR_COMPLETION/REJECT` 等结论，不能仅以 `SUBMITTED` 或页面显示推定最终通过。
- 拟实施的进入门禁须在服务端逐项检查：正式 SalesOrder 与 SalesOrderItem 存在且同属企业；订单未取消；正式决定最终通过且版本仍匹配；目标订单行在不可变覆盖范围内；产品、数量、交期及必要工程条件齐备；操作人具有既有服务端权限。
- 新增订单行、订单或行的实质变化不得继承旧评审覆盖；应形成新版本确认，不修改历史评审。待补充、驳回、取消、来源身份不一致、权限不足均应拒绝；工程准备失败应保留原因而不伪造成功状态。
- 当前 `backend/sales/services.py` 的 `start-engineering` 仅检查订单状态、至少一条明细及既有动作权限，未核验正式订单评审或行覆盖；不能作为本次门禁已经实现的证据。

## 五、入口、权限与测试结果

- 正式入口只应沿现有业务流程中心扩展，不创建第二套订单流程。组织、人员、Role、Permission 和 Workflow 保持现有事实权威；GRA 不作为本轮前置或产物。
- 本轮仅进行了源码、路由、Registry 和迁移工作树只读核验。没有执行 Migration、创建数据库、启动 Acceptance Runtime、写入业务数据或进行 UI 人工验收。
- 正向测试（创建正式订单、保存最终通过决定、按被覆盖订单行进入 PDE、同一 ID 追溯）及负向测试（待补充、驳回、取消、增行、版本变化、权限不足）均为 `NOT EXECUTED`，不得报告 PASS。
- `DELIVERED USER STATE = NOT GUARANTEED`：没有可用且获授权的同一可见浏览器 Tab 进行最终路径与 Readback。

## 六、阻断与下一阶段计划

1. 必须单独批准最小 Schema/Migration 范围：正式订单评审决定与 SalesOrder、SalesOrderItem 覆盖快照及工程准备的强关系；保持来源评审历史不可变，避免复制为第二套权威。按 V1.2 第10.2节，发现必需 Schema 扩展时停止申请新授权。
2. 明确受控开发/测试环境、分支与冻结代码、测试数据来源、允许文件及 Migration、网络隔离、写入计数和保留/销毁策略；不得使用 Protection、ABA/734F 历史库或 Acceptance Runtime 作为替代测试来源。现有 Phase B Source/Baseline 技术准入仍阻断，不能据此宣称正式验收环境就绪。
3. 在完成上述授权与迁移链核对后，以最小增量实现正式评审绑定、服务端 PDE 门禁、页面既有入口衔接及正反例自动化测试；再做同一可见 Tab 的业务人员路径验收与 Readback。非回归须覆盖既有销售订单、来源记录、PDE 工程对象、路由、权限与 Workflow。
4. 本阶段不进入 PLAN、MRP、MPS、APS、MES、WMS、交付或 GRA。仅在该闭环真实运行并验收后，才考虑 PDE 工程准备到计划需求的下一阶段。

## 七、最终 Gate

`PCE CRM ORDER REVIEW TO PDE ENGINEERING PREPARATION BLOCKED`

`SOURCE CODE CHANGED = NO`  
`DATABASE CHANGED = NO`  
`MIGRATION CREATED OR EXECUTED = NO`  
`BUSINESS END-TO-END VERIFIED = NO`  
`DELIVERED USER STATE = NOT GUARANTEED`

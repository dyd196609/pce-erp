# GRA Governance Decision Formal Record — 未签署模板

**状态：UNSIGNED TEMPLATE / NOT A GOVERNANCE DECISION。** 本文件供有权治理主体在独立原件上填写和签署；以下“候选方向”只是待核验提案，不是最终裁决。请勿直接编辑本模板冒充签署原件。签署后的独立工件应保留原始版本，不覆盖本模板。

## A. 基础身份与决策主体（由有权主体填写）

| 字段 | 待填写值 |
|---|---|
| Decision ID（由正式治理记录机制提供） | ____________________ |
| Decision Version | ____________________ |
| Proposal ID | `NCPSB-SP-A-20260929-001` |
| Logical Source ID | `PCE-NCPB-A-REBUILD-SOURCE-P01` |
| Related Design Version / Document Identity | ____________________ |
| Decision Type | GRA Governance Decision |
| Decision Maker / User ID / Employee Identity | ____________________ / ____________________ / ____________________ |
| Organization / Position / Role | ____________________ / ____________________ / ____________________ |
| Decision Authority Basis / Evidence Reference | ____________________ / ____________________ |
| Authority Effective Period | ____________________ |
| Decision Scope（适用企业、组织、对象、时间、排除项） | ____________________ |

Decision ID、User ID、签署人与授权依据不能由 Codex、开发人员、系统管理员身份或本模板自动推定。若一份原件覆盖多个 D 项，请对每项分别给出最终选择、理由、限制和有效范围。

## B. D-01～D-07 最终裁决（由有权主体勾选并说明）

### D-01 — GRA 定位

问题：是否采用 GRA 作为本双 ID 绑定的治理责任授权事实层，且不替代 Employee、Position、Organization、Role、Permission？  
候选方向（非最终）：`ACCEPT`。  
最终：□ ACCEPT　□ MODIFY　□ REJECT  
理由：____________________  
限制与适用范围：____________________

### D-02 — B+C+A 组合

问题：是否采用 B 治理授权语义 + C 原始证据登记 + A 受控 Workflow 过程？第一阶段是否排除复杂 Workflow 建设？  
候选方向（非最终）：`ACCEPT`。  
最终：□ ACCEPT　□ MODIFY　□ REJECT  
理由：____________________  
三层边界、关联及限制：____________________

### D-03 — 单一事实权威

问题：是否保持 Company/Department/OrganizationUnit 为组织事实，Employee/User 为身份事实，Role/Permission/UserRoleScopeAssignment 为系统权限与范围事实，GRA 与 Evidence Registry 为本 Proposal 的治理授权/原件事实，且不建设第二套组织权限？  
候选方向（非最终）：`ACCEPT`；`UserRoleScopeAssignment` 的范围口径须显式确认。  
最终：□ ACCEPT　□ MODIFY　□ REJECT  
理由：____________________  
权威及快照边界：____________________

### D-04 — 轻量 Workflow 边界

问题：第一阶段是否采用轻量责任验证，保持必要的正式审批关联且不建立平行审批？  
候选方向（非最终）：`MODIFY`。  
包含：□ 责任链验证　□ 必要审批关联  
排除：□ 复杂流程编排　□ 新审批平台　□ 全 Workflow 改造  
正式审批如存在，如何复用现有 Workflow/职责分离：____________________  
最终：□ ACCEPT　□ MODIFY　□ REJECT  
理由与限制：____________________

### D-05 — 双门禁

问题：业务动作是否须同时满足系统权限、有效治理授权、范围匹配、生命周期有效，并禁止 Superuser/Admin、前端隐藏及普通 Workflow 绕过？  
候选方向（非最终）：`ACCEPT`。  
最终：□ ACCEPT　□ MODIFY　□ REJECT  
理由与安全策略范围：____________________

### D-06 — 第一应用场景

候选方向（非最终）：`ACCEPT`；工程版本发布责任，单场景验证。  
正式业务对象/唯一身份：____________________  
涉及的版本类型：□ 产品工程版本　□ BOM 版本　□ 工程变更版本　□ 发布版本　□ 其他：________  
职责：□ 创建责任　□ 审核责任　□ 发布责任　□ 其他：________  
责任链、批准节点及数据权威：____________________  
与本 Proposal/Logical Source 的关系：____________________  
包含范围（企业/组织/数据/截止时点）：____________________  
排除范围（至少确认财务、采购审批、质量放行、全 ERP 权限、全 Workflow）：____________________  
对 BOM、生产、采购、财务的影响与单独评估要求：____________________  
最终：□ ACCEPT　□ MODIFY　□ REJECT  
理由：____________________

### D-07 — Implementation Authorization Assessment 入口

问题：是否仅允许进入数据模型、页面、API、Workflow、测试与实施边界的授权**评估**，而非开发、Migration 或实施批准？  
候选方向（非最终）：`ACCEPT`。  
最终：□ ACCEPT　□ MODIFY　□ REJECT  
理由、评估范围与有效期：____________________

## C. 签署与生效（由有权主体填写）

| 字段 | 待填写值 |
|---|---|
| 决策日期 / 签署时间 / 时区 | ____________________ / ____________________ / ____________________ |
| 生效时间 / 失效时间 | ____________________ / ____________________ |
| 签署主体、签署方式与授权依据引用 | ____________________ |
| 独立审查/会签主体及范围（若治理规则要求） | ____________________ |
| 原件版本与支持材料清单 | ____________________ |
| 签署 | ____________________ |

## D. 签署后接收与 Verification 输入（由独立接收/核验方登记；不预填）

| 字段 | 待核验值 |
|---|---|
| Original Document Location / Received Time / Provider | ____________________ |
| Signed Original File Version / Byte Length | ____________________ |
| Signed Original SHA256 | ____________________ |
| Verification ID / Reviewer / Verification Time | ____________________ |
| 来源、身份、事项权限、双 ID、范围、时间、版本、Hash 逐项结果 | ____________________ |
| Verification Result（VERIFIED / PENDING / REJECTED）与原因 | ____________________ |

SHA256 应在**签署原件形成后**按其实际字节只读计算，登记于独立接收/核验记录；不得在待签文件中伪填自身 Hash，也不得因文件已填写即认定 `DECIDED`。Verification ID、Decision ID 与未来 Authorization ID 互不等同。只有独立核验通过并按正式规则复核，才能讨论 Decision 状态转换；本模板本身永远不是签署原件。

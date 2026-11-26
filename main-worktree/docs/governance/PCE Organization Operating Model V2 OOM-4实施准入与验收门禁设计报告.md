# PCE Organization Operating Model V2 OOM-4 实施准入与验收门禁设计报告

日期：2026-08-18  
阶段：OOM-4 Implementation Readiness & Acceptance Gate Design（实施准入与验收门禁设计）  
类型：DESIGN ONLY（仅设计）  
实施授权：NOT AUTHORIZED（未授权实施）
## 1. 结论

本报告只定义 Organization Operating Model V2（企业组织运行模型 V2，OOM V2）进入实施前的准入、验收、回退和退出门禁，不提供实施方案，不创建 Schema、Migration、API、页面或数据。
门禁设计结论：

- OOM-4 实施必须经过 Gate-1 Architecture（架构）、Gate-2 Data（数据）、Gate-3 Governance（治理）、Gate-4 Technical（技术）、Gate-5 Business（业务）五项独立签发。
- Gate PASS 只表示可以提交实施授权评审，不等于自动获得实施授权。
- 任一 P0 阻断项、证据缺失或人工签发缺失，最终状态必须为 NOT READY。
- 未来实施完成后还必须通过组织、责任、员工任职、治理、安全、审计和采购保护验收，才能退出实施阶段。
- RRE-1（责任解析引擎第一实施阶段）和 Workflow Integration（流程集成）拥有独立门禁，不因 OOM 实施通过而自动开放。
- 当前准入评估为 NOT READY：数据结构尚未获 Migration 授权，实名治理责任尚未签发，技术实施/回退包尚未形成，业务验收尚未签字，且 OOM-3.3.1 归档正文缺失。
## 2. 已读取治理基线与判断

### 2.1 BAC-0 与 BAC-1

路径：

- `D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-0架构签发报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-1架构与契约定义设计报告.md`
用途：确认 Business Action Contract（业务动作契约，BAC）的权威位置，以及 `requiredResponsibility`、`requiredPermission` 边界。
关键原文：
> “本次批准代表架构规则批准，不代表代码实施批准。”
> “当前仓库尚未实施完整 Server Business Action Contract，尤其尚未建立 `requiredResponsibility` 字段。”
> “BAC-1 IMPLEMENTATION = NOT AUTHORIZED。”
判断：BAC 对接设计明确，但服务端完整契约尚未实施；OOM 不得以 BAC 设计批准推导 RRE 或 Workflow 实施授权。
### 2.2 OOM V2 与 BAC 对接设计

路径：`D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 与 Business Action Contract 对接设计报告.md`  
用途：确认 Organization、Position、Responsibility、PositionResponsibility、Employee 当前事实能力。
关键原文：
> “当前 `system.Responsibility` 已经是独立责任目录事实源。”
> “当前 `system.PositionResponsibility` 可以表达‘岗位承担责任’。”
> “当前 `pfm.Employee.position_ref` 只能表达员工的一个当前正式岗位，尚不能严谨表达多岗位、代理任职及历史时点任职。”
判断：现有模型可复用，但正式时态 Employee Assignment（员工任职关系）是实施前必须解决的缺口。
### 2.3 OOM-1 与 OOM-2

路径：

- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-1实施方案设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-2实施设计与Schema决策报告.md`
用途：确认实施阶段、模型复用、时态 Schema 和历史策略。
关键原文：
> “Schema Migration（数据结构迁移）= NOT AUTHORIZED。”
> “推荐新增 `pfm.EmployeePositionAssignment` 关系模型，需另行授权。”
> “统一使用 `[effective_from, effective_to)`，交接时点不重叠。”
判断：Schema 方向已经设计，但最终 Migration、备份、回退和数据转换仍需独立批准。
### 2.4 OOM-3、OOM-3.1 与 OOM-3.2

路径：

- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3数据治理与初始化方案设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.1主数据责任与治理矩阵设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.2组织主数据变更流程与治理闭环设计报告.md`
用途：确认数据初始化、Data Owner、Data Steward、Reviewer、Approver、Change Request 和唯一写入口。
关键原文：
> “初始化不是 Migration 默认数据，而是经过 Data Owner 与 Data Steward 确认的受控批次。”
> “同一自然人不得审批自己发起或维护的变更。”
> “保留现有 OrganizationOperatingService 作为未来‘执行已批准变更’的唯一组织写服务。”
判断：实施前必须把设计角色落实为实名授权，把即时保存收敛为获批申请执行，并明确初始化批次签发。
### 2.5 OOM-3.3.1～OOM-3.3.4

实际路径：

- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.3.1主数据对象与系统能力映射设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.3.2组织主数据变更管理能力边界设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.3.3治理权限与角色边界设计报告.md`
- `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-3.3.4人工智能数字孪生与控制能力边界设计报告.md`
用途：确认对象能力、变更能力、治理权限以及 AI/Digital Twin/Control 边界。
关键原文：
> “Change Request 需要成为独立治理对象。”
> “拥有 Permission 的用户不会因此自动成为责任人、Reviewer 或 Approver。”
> “Autonomous Execution 不得用于组织主数据变更。”
归档判断：OOM-3.3.2～3.3.4 内容完整；OOM-3.3.1 当前只有 5 行状态摘要，无可复核设计正文。该缺口必须在 Gate-1 前修复或由正式替代文档签发，本轮不越权修复。
## 3. 准入原则

### 3.1 Evidence First（证据优先）

每项门禁必须提供文件、版本、签发人、签发日期、检查结果和未决风险。口头确认、聊天记录或页面截图不能单独替代正式签发。
### 3.2 Five Gates, All Pass（五门全过）

五项 Gate 均 PASS 后，只能形成 `READY FOR IMPLEMENTATION AUTHORIZATION REVIEW`；还需新的人工实施授权指令才能开始代码或数据库工作。
### 3.3 No Implicit Expansion（禁止隐式扩权）

OOM 实施授权不包含 BAC-1 Implementation、RRE-1、Workflow Integration、采购流程切换、AI 自动执行或组织数据导入，除非授权逐项明确写出。
## 4. OOM-4 实施准入条件

### 4.1 架构条件

- OOM V2 对象、关系、时态、治理、权限、AI/Twin/Control 边界已冻结；
- BAC 是动作唯一事实来源，责任与权限字段不混用；
- Position、Responsibility、Role、Permission、Employee Assignment 语义分离；
- OrganizationOperatingService 是唯一正式写入口；
- Workflow 和 RRE 不创造企业事实；
- 所有设计文档完整、可读、版本一致并经人工签发。
### 4.2 数据结构条件

- EmployeePositionAssignment 的字段、约束、索引、状态、主岗/兼岗/代理语义最终确认；
- PositionResponsibility 有效期间、PRIMARY/SUPPORTING、历史终止语义最终确认；
- `[effective_from, effective_to)` 适用于所有时态关系；
- 跨公司、重复、重叠、空档、循环和孤儿引用规则冻结；
- 旧 `Employee.position_ref` 到新任职事实的兼容、候选、人工确认和退役策略批准；
- 历史查询和双时点记录策略批准。
### 4.3 治理条件

- 每类主数据的 Data Owner、Data Steward、Reviewer、Approver 实名明确；
- 提交、审核、批准的自然人隔离规则可执行；
- Change Request 生命周期、影响分析、Payload Hash、生效和归档规则冻结；
- 公司合并、组织调整、责任退役、岗位退役、员工调岗的审批链明确；
- superuser 不豁免职责分离；
- 初始化批次也必须经过治理签发。
### 4.4 系统能力条件

- 正式事实只有一个写入口和一个服务端读取事实；
- 页面不能绕过 Change Request 直接保存正式事实；
- AuthorizationService 提供动作、Permission、Scope 和证据；
- 审计覆盖申请、审核、批准、生效、Before/After、原因、回读；
- AI/Twin/Control 只能只读、建议、模拟、检测或阻断；
- 拒绝、失败和回退均固定零未授权写入。
## 5. Gate-1 Architecture（架构门禁）

| 检查项 | PASS 标准 | 阻断条件 |
|---|---|---|
| 设计冻结 | OOM-0～3.3 全部签发且正文完整 | 文档缺失、冲突或仅状态摘要 |
| BAC 边界 | 动作、责任、权限引用明确 | 前端/Workflow 自建动作或混用字段 |
| 事实来源 | 每对象唯一来源清单完成 | 第二组织树、第二责任目录、页面缓存补事实 |
| 服务边界 | 唯一写服务和只读消费者明确 | AI/RRE/Workflow 直接写事实 |
| 非目标边界 | RRE、Workflow、采购、AI 自动化隔离 | 实施包包含未授权范围 |
签发人：企业架构负责人 + OOM Data Owner 代表。  
必要证据：冻结文档索引、架构关系图、唯一事实来源矩阵、冲突扫描结果。
当前评估：BLOCKED。原因：OOM-3.3.1 正文缺失；BAC-1 仍是设计状态，但其与 OOM 的接口边界可保留为后续独立依赖。
## 6. Gate-2 Data（数据门禁）

| 检查项 | PASS 标准 | 阻断条件 |
|---|---|---|
| Schema 决策 | 最终字段、约束、索引、关系获批 | 仍有未决字段或平行 V2 模型 |
| 时态模型 | 左闭右开、历史和查询规则获批 | 覆盖历史或时间语义不一致 |
| 数据画像 | 当前数量、重复、孤儿、重叠报告完整 | 无基线或质量缺陷未处置 |
| 转换映射 | 每个旧事实映射到新事实且可追溯 | 自动把候选当正式任职 |
| 初始化 | 模板、批次、Owner/Steward 签发 | Migration 自动生成企业事实 |
签发人：数据架构负责人 + 人力/组织 Data Owner。  
必要证据：Schema 决策包、数据画像、映射清单、质量规则、初始化零自动生成声明。
当前评估：BLOCKED。原因：Migration 未授权，正式数据画像和人工转换批次尚未形成。
## 7. Gate-3 Governance（治理门禁）

| 检查项 | PASS 标准 | 阻断条件 |
|---|---|---|
| 实名责任 | Owner/Steward/Reviewer/Approver 名单签发 | 仅有抽象角色，无自然人 |
| 职责分离 | 自提自审自批被系统阻断 | superuser 或换 Role 可绕过 |
| Change Request | 状态机、指派、影响和批准证据完整 | 页面即时写正式事实 |
| 权限映射 | Submit/Review/Approve/Execute 分权 | 一个 manage 权限完成全部步骤 |
| 审计责任 | 证据保留期限和查阅责任明确 | 日志/Console 代替正式审计 |
签发人：数据治理负责人 + 权限治理负责人 + 业务代表。  
必要证据：实名 RACI、职责冲突矩阵、治理动作清单、拒绝测试设计、审计责任书。
当前评估：BLOCKED。原因：治理角色设计已完成，但实名授权、目标 Permission 和系统门禁尚未实施与签发。
## 8. Gate-4 Technical（技术门禁）

| 检查项 | PASS 标准 | 阻断条件 |
|---|---|---|
| Migration 方案 | 单一增量、顺序、锁定与耗时评估完整 | 未审 SQL、自动种业务数据、不可控锁表 |
| 备份与摘要 | 迁移前备份、SHA256、对象数量基线 | 无可验证恢复点 |
| 回退方案 | 结构、数据、应用版本可恢复并演练 | 仅写“可回退”无脚本/时限/责任人 |
| 测试方案 | 单元、集成、权限、时态、并发、回归 | 缺 P0 失败测试 |
| 可观测性 | 迁移、写入、拒绝、审计和漂移可观察 | 只能靠页面判断成功 |
| 环境隔离 | 测试演练不触碰生产和采购业务 | 使用真实流程/业务写入试验 |
签发人：技术负责人 + DBA/数据保管人 + 测试负责人。  
必要证据：Migration 草案、备份恢复演练、测试清单、性能预算、部署/回退 Runbook。
当前评估：BLOCKED。原因：本阶段禁止实施，尚无获批 Migration、部署和回退包。
## 9. Gate-5 Business（业务门禁）

| 检查项 | PASS 标准 | 阻断条件 |
|---|---|---|
| 业务范围 | 公司、组织、岗位、责任、员工任职范围签字 | 边界不清或默认全量上线 |
| 责任定义 | 首批责任由业务 Owner 人工确认 | 根据岗位名自动生成 |
| 验收标准 | H01～Hxx 场景、预期、证据和签字人明确 | 只有技术测试无业务验收 |
| 切换窗口 | 维护冻结、上线、验证、回退时限明确 | 业务高峰无回退窗口 |
| 培训与操作 | Steward/Reviewer/Approver 能完成真实闭环 | 管理员仍使用即时保存思维 |
签发人：组织/人力负责人 + 首批业务领域负责人 + 最终验收负责人。  
必要证据：业务范围签发、首批数据清单、人工验收脚本、培训记录、上线窗口确认。
当前评估：BLOCKED。原因：尚未形成正式业务签发、验收人员和上线窗口。
## 10. Gate 汇总与裁决规则

| Gate | 当前状态 | 是否允许豁免 |
|---|---|---|
| Gate-1 Architecture | BLOCKED | 不允许 |
| Gate-2 Data | BLOCKED | 不允许 |
| Gate-3 Governance | BLOCKED | 不允许 |
| Gate-4 Technical | BLOCKED | 不允许 |
| Gate-5 Business | BLOCKED | 不允许 |
最终裁决：`OOM-4 Implementation Readiness = NOT READY`。  
即使未来五项全部 PASS，仍需 Human Implementation Authorization（人工实施授权）才能执行。
## 11. 未来实施验收设计

### 11.1 Organization（组织）验收

- Company 创建/查看/停用/历史保持同一服务端事实；
- Organization Unit 层级无循环、跨公司或孤儿节点；
- Department 与 Organization Unit 映射一致；
- Position 归属、父岗位、状态和有效期正确；
- Job Family 与 Job Level 为独立分类维度，不自动产生责任/权限；
- 刷新、API、综合模型和审计读取同一事实。
### 11.2 Responsibility（责任）验收

- Responsibility 目录为唯一事实源，编码唯一；
- 页面、岗位、AI、RRE、Workflow 不自动创建责任；
- PositionResponsibility 只能引用已有有效责任和岗位；
- PRIMARY/SUPPORTING 记录正确但不自动选人或授权；
- 有效区间按左闭右开校验，历史不可覆盖；
- 暂停/退役责任的 BAC 和关系引用被阻断或受控迁移。
### 11.3 Employee Assignment（员工任职）验收

- 支持主岗、兼岗、代理、调岗、离岗；
- 调岗在同一时点结束旧任职并建立新任职，不重叠；
- 可按历史时点查询员工岗位；
- 员工变化不修改 BAC、Responsibility、Role、Permission 或 Workflow；
- 多岗位产生真实多候选时不静默选择；
- `Employee.position_ref` 兼容结果与正式任职关系一致且可追溯。
### 11.4 Governance（治理）验收

- 正式变更必须有 Change Request；
- Requester、Reviewer、Approver 为不同自然人；
- 无权限、未指派、Scope 不符均返回拒绝且写入为 0；
- 批准后 Payload 修改导致重新审核；
- 未到生效时间或 Before Snapshot 漂移不得执行；
- 成功执行记录 Before、After、Operator、Reviewer、Approver、Reason、时间和回读。
### 11.5 Control 与安全验收

- AI/Twin/Control 调用组织写入口被拒绝；
- `AUTO_APPROVE` 和 unattended mode 对 OOM 强制无效；
- RRE 无候选/多候选只报告，不修复；
- Workflow 不创建责任或修改任职；
- 页面缓存、Fixture、Twin Snapshot 不作为第二事实源；
- Unauthorized Business Writes（未授权业务写入）始终为 0。
## 12. 验收测试目录

| 编号 | 场景 | PASS 条件 |
|---|---|---|
| OOM4-A01 | Company/Organization Unit 唯一事实读取 | 页面/API/回读一致 |
| OOM4-A02 | 组织循环与跨公司关系 | 服务端拒绝，写入 0 |
| OOM4-A03 | Position 生命周期 | 创建、暂停、退役保留历史 |
| OOM4-A04 | Job Family/Level 变化 | 不改变责任或权限 |
| OOM4-A05 | Responsibility 创建与退役 | 人工治理、引用门禁通过 |
| OOM4-A06 | PositionResponsibility 时态 | PRIMARY/SUPPORTING 与区间正确 |
| OOM4-A07 | Employee 调岗 | 左闭右开、历史一致 |
| OOM4-A08 | 兼岗/代理 | 范围、期限、多候选真实 |
| OOM4-A09 | 自提自审自批 | 按自然人拒绝 |
| OOM4-A10 | 无 Permission/Scope | HTTP 403、写入 0 |
| OOM4-A11 | 批准后内容漂移 | 批准失效、重新审核 |
| OOM4-A12 | 审计与回读 | 全证据且服务端一致 |
| OOM4-A13 | AI/Twin/Control 写入 | 全部拒绝 |
| OOM4-A14 | Migration 回退演练 | 规定时间内恢复且审计保留 |
| OOM4-A15 | 采购保护 | PurchaseOrder/SupplierMaterialPrice 无变化 |
## 13. 回退门禁

### 13.1 实施前必须具备

- 已验证数据库备份和 SHA256；
- Company、OrganizationUnit、Position、Responsibility、PositionResponsibility、Employee、Assignment、Audit 数量基线；
- 应用版本、Migration 顺序和依赖锁定；
- 结构回退、数据恢复、应用回退三套步骤；
- 明确回退负责人、批准人、最长恢复时间和业务通知方案；
- 在隔离副本上至少一次完整恢复演练。
### 13.2 强制停止触发器

- Migration 非预期创建或修改业务数据；
- 正式对象数量出现无法解释的变化；
- 时态重叠、历史丢失或跨公司关系出现；
- AuthorizationService、审计或唯一写入口被绕过；
- 采购订单、供应商价格、流程任务等保护对象变化；
- 回读与数据库正式事实不一致；
- P0 验收失败或 Unauthorized Business Writes > 0。
### 13.3 回退原则

立即停止后续步骤，封存日志和审计；按批准 Runbook 恢复应用和数据库；保留失败 Migration、操作者、时间和原因；不得删除失败证据或以人工 SQL 静默修正；恢复后重新执行数据基线和保护检查。
## 14. 实施退出条件

未来 OOM 实施只有同时满足以下条件才能标记 COMPLETE：

1. 获批范围内代码、Schema、Migration 和页面全部完成；
2. OOM4-A01～A15 全部 PASS；
3. 数据迁移数量、映射和历史追溯一致；
4. 五类 Gate 签发人完成最终复核；
5. 人工浏览器验收和服务端回读通过；
6. 采购及其他非目标模块保护通过；
7. 未授权业务写入为 0；
8. 遗留风险均有 Owner、截止日期和不影响上线的证明；
9. 最终实施报告和回退结果归档；
10. Human Acceptance（人工验收）正式签字。
未满足时状态只能是 PARTIAL、FAILED 或 ROLLED BACK，不得声明 PASS。
## 15. RRE-1 前置门禁

RRE-1 另行授权前必须满足：

- 服务端 BAC 已提供 `actionCode`、`objectType`、`requiredResponsibility`、`requiredPermission` 和 scopeDimensions；
- Company、Organization Unit、Position、Responsibility 可从正式服务端读取；
- PositionResponsibility 有效期查询可靠；
- Employee Assignment 可按解析时点读取主岗、兼岗和代理；
- 无候选、多候选、无员工等异常有稳定状态码；
- Resolution Evidence 包含来源、时点、关系和授权预检证据；
- 只读验证 `writeCount = 0`；
- OOM 数据质量和历史查询验收通过。
禁止 RRE 创建、补齐、修改或修复组织数据；禁止按管理员、主管、Role、Permission 或最小 ID 兜底。
当前状态：`RRE-1 = NOT AUTHORIZED`。
## 16. Workflow Integration 前置门禁

Workflow 接入前必须满足：

- OOM 实施和人工验收 COMPLETE；
- BAC 服务端契约已实施并稳定；
- Responsibility 和 PositionResponsibility 首批数据已由业务签发；
- RRE 只读解析与权限预检验证完成；
- Workflow Node 只引用已有 actionCode/requiredResponsibility；
- `ApprovalTask.required_role_code` 继续保持 Role 语义，不写 Responsibility Code；
- Shadow Mode、真实任务切换和回退分别获得授权；
- Workflow 不拥有组织事实写权限。
当前状态：`Workflow Integration = NOT AUTHORIZED`。
## 17. 准入签发模板

| Gate | Owner | Evidence Version | Result | Open Risks | Signature/Date |
|---|---|---|---|---|---|
| Gate-1 Architecture | 待实名 | 待填写 | BLOCKED | OOM-3.3.1 正文缺失 | 待签发 |
| Gate-2 Data | 待实名 | 待填写 | BLOCKED | Schema/Migration 未批准 | 待签发 |
| Gate-3 Governance | 待实名 | 待填写 | BLOCKED | 实名治理链未建立 | 待签发 |
| Gate-4 Technical | 待实名 | 待填写 | BLOCKED | 实施/回退包未形成 | 待签发 |
| Gate-5 Business | 待实名 | 待填写 | BLOCKED | 业务验收未签字 | 待签发 |
最终签发意见：`NOT READY FOR IMPLEMENTATION AUTHORIZATION`。
## 18. 保护确认

本轮只新增本设计报告，没有实施 OOM-4、Schema、Migration、API、页面、数据导入、RRE 或 Workflow 集成。
`Documentation Changed = YES`。  
`Code Changed = NO`；`Database Changed = NO`；`Migration Created = NO`；`API Created = NO`；`Page Created = NO`。  
`Organization Data Changed = NO`；`Responsibility Data Changed = NO`；`Employee Data Changed = NO`。  
`Permission Model Changed = NO`；`Workflow Runtime Changed = NO`；`ApprovalTask Changed = NO`。  
`RRE Started = NO`；`Unauthorized Business Writes = 0`。
## 19. 最终状态

`OOM-4 Implementation Readiness & Acceptance Gate Design = COMPLETE`。  
`OOM-4 Implementation Readiness = NOT READY`。  
`Organization Model Implementation = NOT AUTHORIZED`。  
`Schema Migration = NOT AUTHORIZED`；`RRE-1 = NOT AUTHORIZED`；`Workflow Integration = NOT AUTHORIZED`。
本报告完成后停止，等待人工架构、数据、治理、技术和业务门禁决策。

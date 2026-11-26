# PCE CODEX 开发指令规范管理 V1.1

日期：2026-08-19  
版本：V1.1  
阶段：PCE CODEX Development Instruction Governance Standard V1.1（PCE CODEX 开发指令治理规范 V1.1）  
类型：GOVERNANCE DOCUMENT DESIGN ONLY（治理规范文档设计，仅编制不实施）  
适用范围：Dev-PCE 后续全部 CODEX 设计、评审、准备、证据构建和实施指令  
规范权威：本文件是 PCE CODEX 指令结构、边界、归档和回读要求的唯一规范来源  
实施授权：NOT APPLICABLE；本文件不授权任何业务或技术实施  
升级来源：V1.0 完整母版；V1.1 新增上下文、分层基线、规模控制、输出拆分、网络稳定性和质量指标规则  
## 1. 文档目的

本规范统一 PCE 项目中 CODEX 指令的生成、执行、验证、归档、回读和审查方法，防止指令依赖临时记忆、个人习惯或聊天上下文。 目标：
1. 保证开发质量、设计质量以及架构与治理基线一致；
2. 保证每个任务只有一个核心目标，授权范围可判断、可阻断；
3. 保证输出完整、可追溯、可回读，并可由 ChatGPT 和人工负责人直接审查；
4. 保证实施、数据写入和外部副作用均需明确授权，失败或未完成不得包装为 PASS。
## 2. 规范权威与适用原则

### 2.1 唯一规范来源

后续 PCE CODEX 指令必须引用本文件：
```text
D:\Dev-PCE\Source\docs\governance\PCE CODEX开发指令规范管理V1.1.md
```
聊天记录、个人模板、旧任务文本和模型记忆只能作为上下文，不能替代本规范。 发生冲突时优先级为：
```text
用户明确授权 → AGENTS.md/安全边界 → PCE 架构与专项规范 → 本规范 → 任务补充 → 历史聊天/个人习惯
```
更高层规则不能被本规范降低；当前任务也不能隐式扩大已冻结的业务或安全边界。
### 2.2 证据优先

任何“存在、完成、通过、未修改”判断必须基于文件、代码、数据库只读结果、测试或签发证据。禁止只根据文件名、聊天摘要或预期设计下结论。
### 2.3 授权显式

没有明确授权即视为不允许。Design Complete（设计完成）、Preparation Complete（准备完成）、Gate PASS（门禁通过）均不自动等于 Implementation Authorized（实施已授权）。
## 3. 已读取治理基线与经验来源

### 3.1 架构治理基线

| 实际路径 | 文件用途 | 关键原文 | 固化规则 |
|---|---|---|---|
| `D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-0架构签发报告.md` | 架构基线和实施授权边界 | “架构规则批准，不代表代码实施批准” | 架构签发与实施授权分离 |
| `D:\Dev-PCE\Source\docs\governance\PCE Business Action Contract V1 BAC-1架构与契约定义设计报告.md` | 设计任务和真实仓库证据 | `BAC-1 IMPLEMENTATION = NOT AUTHORIZED` | 设计报告不得实施模型/API |
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4实施准入与验收门禁设计报告.md` | Gate 管理 | “任一 P0、证据或人工签发缺失，最终状态必须为 NOT READY” | Gate 必须证据化且不可豁免 |
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 OOM-4 Gate重新评估报告.md` | 文档修复后的重新评估 | “修复仅解除 Gate-1 的文档完整性阻断” | 单项修复不得自动扩展结论 |
### 3.2 CODEX 使用过程经验

| 过程文件 | 观察 | 固化经验 |
|---|---|---|
| `PCE Organization Operating Model V2 OOM-3.3.1主数据对象与系统能力映射设计报告.md` | 正式正文曾被 5 行状态摘要替代 | 禁止摘要覆盖正文；保存后必须完整回读 |
| `PCE Organization Operating Model V2 OOM-4.1.1组织模型Schema实施包设计报告.md` | 设计了 Schema/Migration，但保持未授权 | 设计包只定义未来实施，不创建 Migration |
| `PCE Organization Operating Model V2 OOM-4.1.2组织服务能力实施包设计报告.md` | 报告规模较大且包含多个能力面 | 长任务应拆分；行数上限是硬门禁 |
| `PCE Organization Operating Model V2 OOM-4.1.3组织管理页面实施包设计报告.md` | 页面依赖 Schema 和服务，当前 Gate FAIL | 前置条件不满足时必须停止，不用页面假实现补齐 |
| `PCE Organization Operating Model V2 OOM-4.1.4组织数据初始化与验收实施包设计报告.md` | 候选数据与正式事实严格分离 | 分析、候选、模拟不得写成正式业务事实 |
| Gate-2/3/4/5 解除准备报告 | Preparation Design 均 COMPLETE，但 Gate 均 BLOCKED | 准备完成不等于证据建立或门禁通过 |
| OOM-4 Gate 综合路线图 | Gate 要求实施证据，但正式实施未授权 | 使用 Controlled Evidence Build 解决授权闭环，不降低 Gate 标准 |
| `PCE Organization Operating Model V2 Controlled Evidence Build Authorization设计报告.md` | `Controlled Evidence Build Authorization = NOT GRANTED` | 只读取当前任务所需章节；执行与设计必须独立授权 |
| `PCE Organization Operating Model V2 Controlled Evidence Build Authorization评审与授权申请设计报告.md` | `Controlled Evidence Build Authorization Request Instance = NOT CREATED` | 单次指令只处理一个状态阶段，避免全链同时执行 |
| `PCE Organization Operating Model V2 OOM-4 Gate综合状态评估与解除路线图报告.md` | `Gate-2 Data = BLOCKED`；其余治理、技术、业务 Gate 同为 BLOCKED | Gate 评估应按门禁拆分，综合报告只消费冻结结论 |
## 4. CODEX 指令生命周期

完整生命周期：
```text
需求提出
↓
任务澄清与边界识别
↓
大任务拆解
↓
CODEX 指令生成
↓
基线文件读取与 Preflight（实施前检查）
↓
CODEX 受控执行
↓
结果验证与保护检查
↓
文档归档
↓
归档原文回读
↓
ChatGPT / 人工审查
↓
下一阶段决策或停止
```
任何阶段发现缺少授权、关键基线、输入文件或可恢复路径时，必须停止在当前阶段并输出 BLOCKED，不得跳到下一阶段。
### 4.1 生命周期状态

| 状态 | 含义 | 是否允许下一阶段 |
|---|---|---|
| DRAFT | 指令或报告未冻结 | 否 |
| READY FOR EXECUTION | 输入、边界和授权已确认 | 仅允许当前阶段 |
| IN PROGRESS | 当前任务执行中 | 否 |
| BLOCKED | 存在授权、证据或依赖阻断 | 否 |
| COMPLETE | 当前任务目标和验证完成 | 等待人工决定 |
| PASS | 指定 Gate 或验收通过 | 仅按规则申请下一阶段 |
| NOT AUTHORIZED | 未获实施权限 | 否 |
## 5. 标准 CODEX 指令结构

所有正式指令必须按以下顺序编写：
| 顺序 | 章节 | 强制内容 |
|---:|---|---|
| 1 | 任务名称 | 系统、模块、阶段、唯一目标；禁止“继续处理”等模糊名称 |
| 2 | 任务性质 | Stage、Type、当前允许状态、明确不是哪些阶段 |
| 3 | 背景与事实基线 | 当前任务所需已确认事实；不能替代真实文件读取 |
| 4 | 唯一目标 | 一个核心问题和一个主要结果；支撑章节不能变成多个实施阶段 |
| 5 | 必须读取文件 | 路径、文件名、用途、需要确认的事实 |
| 6 | 允许范围 | 本阶段可执行动作；未列明的高影响动作默认禁止 |
| 7 | 禁止事项 | 代码、数据库、Migration、API、页面、权限、Workflow、数据、副作用、下一阶段 |
| 8 | 核心任务 | 每项输入、判断、输出和停止条件 |
| 9 | 输出要求 | 文件名、绝对路径、格式、行数、必含章节、正文回传要求 |
| 10 | 保护要求 | 第 14 节统一模板和专项保护对象 |
| 11 | 结束状态 | COMPLETE/PASS/BLOCKED、保持不变的 Gate、未授权阶段、立即停止 |
## 6. 基线阅读管理规范

### 6.1 核心基线

每个任务按适用范围读取：
| 基线类别 | 典型文件 | 适用条件 |
|---|---|---|
| 架构 | BAC、OOM、ERP 架构与运行边界 | 所有架构、服务和跨模块任务 |
| Runtime | Runtime 职责规范、运行层文件职责规范 | Provider、Runtime、页面、流程任务 |
| Permission | PCE-BUSINESS-ACTION-PERMISSION、AuthorizationService 报告 | 任何读写动作或权限展示 |
| Schema | Schema 规范、目标模型报告、Migration 设计 | 数据结构或模型任务 |
| Workflow | Workflow Runtime 和流程治理规范 | 审核、批准、任务、状态任务 |
| Acceptance | 真实运行验收规范、Gate 报告 | 任何 COMPLETE/PASS 判断 |
| Module | 采购、SCM、Finance 等专项保护报告 | 涉及相邻业务对象时 |
### 6.2 当前任务基线

在核心基线之外，只增加直接支撑当前目标的设计、实施、整改、验收和保护报告。
禁止为了减少时间随意删除关键基线，也禁止无差别读取全部历史文件造成判断污染。
### 6.3 阅读证据

正式报告必须列出：实际读取路径、文件用途、关键原文或结构化摘录、判断依据。
仅写“已检查”“已读取”不合格。
### 6.4 文件缺失或命名不一致

必须先使用仓库文件搜索确认真实路径。找不到时输出 MISSING 和影响，不得凭历史聊天重建原文或假定文件存在。
### 6.5 Context Management（上下文管理）

CODEX 任务必须主动控制读取、推理和输出规模。标准路径：
```text
任务目标明确
↓
读取最小必要基线
↓
完成单一任务
↓
验证与归档
```
禁止无目的读取全部历史文件、重复加载已经冻结但与当前判断无关的报告，或把整个项目历史作为默认上下文。
已经读取的文件只有在内容可能变化、任务要求重新核验或需要精确原文时才重新读取；历史聊天摘要不能替代当前活动基线。
### 6.6 基线文件分层

| 层级 | 定义 | 读取规则 |
|---|---|---|
| Level 0 | CODEX 核心规范基线 | 每个正式 CODEX 任务必须读取当前活动版本 `PCE CODEX开发指令规范管理V1.1.md` |
| Level 1 | 阶段基线 | 只读取当前阶段最新冻结文件；OOM 读取 OOM 冻结基线，Controlled Evidence 读取相应冻结基线 |
| Level 2 | 专项基线 | 只读取当前目标直接依赖的模型、服务、页面、数据、Gate 或保护文件 |
规则：没有明确依赖，不读取。旧版本只在版本差异、追溯或修复任务中读取，不能与活动版本并列作为权威来源。
### 6.7 输入文件数量控制

出现任一条件必须在 Preflight 重新评估拆分：
- 单次输入文件超过 10 个；目标报告预计超过 500 行；
- 涉及超过 3 个系统模块。
如仍决定不拆分，指令必须记录不可拆分原因、上下文控制办法和输出分阶段方案；没有说明不得执行。
## 7. 小步快走规则

一个任务必须遵循：
```text
一个主题
+ 一个核心目标
+ 一个主要报告或一个受控实现包
+ 一个冻结点
= 一个可审查任务
```
禁止一个 CODEX 指令同时包含多个实施阶段。
推荐拆分示例：
```text
Schema Design
→ Service Design
→ UI Design
→ Initialization Design
→ Authorization Review
→ Controlled Evidence Build
→ Production Implementation
```
每步完成后停止，等待人工决定下一步。
## 8. 设计、准备、证据构建与实施分离

| 阶段 | 允许 | 禁止/边界 | 合法输出 |
|---|---|---|---|
| Design（设计） | 架构、模型、字段、规则、接口概念、测试和路线 | 修改代码、数据库、API、页面和正式数据 | Design Complete |
| Preparation（准备） | 实施包、证据清单、Runbook 草案、候选模板和准入条件 | 把草案当执行证据或 Gate PASS | Preparation Complete |
| Controlled Evidence Build（受控证据构建） | 独立授权的隔离实现与演练 | 生产实施和正式数据写入 | 隔离证据状态 |
| Implementation（正式实施） | 明确授权的对象、环境、代码/Schema/Data、测试和回退 | 隐式扩展授权 | Implementation 状态 |
状态等式：
```text
Design Complete ≠ Preparation Complete
Preparation Complete ≠ Evidence Established
Evidence Established ≠ Gate PASS
Gate PASS ≠ Implementation Authorized
Implementation Complete ≠ Human Acceptance PASS
```
## 9. Controlled Evidence Build 规范

### 9.1 目的

用于解决 Gate 需要真实实施、测试和恢复证据，但生产实施尚未授权的治理闭环。
### 9.2 必须单独授权

受控证据构建不是默认能力。授权指令必须明确：环境、分支、数据来源、允许文件、允许 Migration、测试范围、网络隔离、写入计数和销毁/保留策略。
### 9.3 允许

- 严格隔离的开发或测试环境；非生产数据库副本；
- 匿名化、合成或明确授权的测试数据；候选代码、Migration 和 API 实现；
- 单元、集成、安全、并发和回退演练；生成 Gate 所需技术证据。
### 9.4 禁止

- 生产代码部署或生产数据库修改；正式业务数据写入或企业数据导入；
- 生产密钥、证书、网络端点或外部副作用；自动切换业务状态、Workflow、RRE 或采购流程；
- 把隔离环境 PASS 声明为生产验收 PASS；未授权扩大文件、模块或数据范围。
### 9.5 证据要求

必须记录环境清单、代码提交、Migration 标识、数据摘要、执行者、时间、测试结果、失败日志、恢复结果、SHA256 和销毁/保留决定。
### 9.6 结束状态

```text
Controlled Evidence Build = COMPLETE / FAILED / BLOCKED
Production Implementation = NOT AUTHORIZED
Unauthorized Business Writes = 0
```
## 10. 执行控制规范

### 10.1 Preflight（执行前检查）

CODEX 必须确认：
1. 当前工作目录和 AGENTS.md；
2. 指定输入文件真实存在；
3. 当前任务是设计、准备、证据构建还是实施；
4. 允许和禁止范围无冲突；
5. 目标文件是否已存在；
6. 工作区已有变更属于谁；
7. 是否需要备份、数据库摘要或保护数量；
8. 输出行数和原文回传要求。
9. 任务是否只有一个核心目标；
10. 每个输入文件是否直接必要，并已按 Level 0/1/2 分类；
11. 是否触发“超过 10 个文件、500 行、3 个模块”的拆分复评；
12. 指令是否包含明确实施授权，或应保持 Design/Preparation；
13. 生成、归档回读和正文传输是否需要分阶段。
### 10.2 执行中

- 只修改目标范围内文件；
- 不清理、不覆盖、不归因用户已有改动；
- 发现必须扩展 Schema、权限或模块时停止并申请新授权；
- 工具执行超过合理时间时提供简短进度；
- 输出中断后从完整章节重新开始，不以半句续写归档。
### 10.3 验证

按风险验证文件、语法、测试、数据库摘要、业务数量、保护对象和最终状态。设计任务至少验证文件完整性、行数、围栏配对、异常字符和 SHA256。
## 11. 文档归档与可审查规范

### 11.1 强制归档闭环

完成报告后必须依次执行：
1. 保存正式 Markdown 文件；
2. 确认目标路径和文件名完全一致；
3. 重新读取刚生成的完整文件；
4. 验证标题、章节、表格、代码围栏和最终状态；
5. 计算实际行数；
6. 计算 SHA256；
7. 将回读内容与预期目标比对；
8. 向用户提供完整文件路径；
9. 提供完整正文，或在界面限制下分成连续、标号明确且无缺失的正文块；
10. 明确等待 ChatGPT / 人工审查。
### 11.2 强制状态

```text
Documentation Archived = YES
Archive Content Readback = YES
ChatGPT Reviewable = YES
```
任何一项不是 YES，文档任务不得声明归档完成。
### 11.3 禁止的交付方式

禁止只返回：
- 本地路径；
- 行数；
- SHA256；
- COMPLETE 状态；
- 摘要而没有正文；
- 被截断的开头或结尾。
路径、行数和 SHA256 是完整性元数据，不能替代可审查正文。
### 11.4 正文过长

优先在任务设计阶段拆分报告。确需长文时：先完整落盘和回读，再按 `Part 1/N` 至 `Part N/N` 返回；每部分必须标明连续章节，最后提供全文 Hash。
长报告的交付必须分为两个可恢复阶段：
```text
阶段 A：生成并验证文件
输出：文件路径、行数、SHA256
↓
阶段 B：归档回读与可审查交付
输出：Archive Content Readback、ChatGPT Reviewable、连续正文块
```
禁止在同一次长响应中同时承担超长正文生成、完整回读和全量传输；文件落盘与校验完成后，即使连接中断也应复用同一归档正文，不得重新生成不同版本。
## 12. 文件完整性规范

归档前必须检查：
- 标题完整且与任务一致；
- 文件名和路径完全匹配；
- 日期、版本、阶段、类型存在；
- 所有必含章节存在；
- 表格列数一致；
- Markdown 代码围栏成对；
- 无零宽字符、乱码或异常编码；
- 无半句、截断标题、未完成列表或占位符；
- 保护状态完整；
- 最终状态与正文判断一致；
- 行数在指令范围内；
- SHA256 基于最终保存内容重新计算。
若检查失败，必须先修复并重新完整回读，再交付。
### 12.1 报告规模分级

| 任务类型 | 建议规模 | 控制规则 |
|---|---:|---|
| Small Design（小设计） | 200–400 行 | 单一对象、单一决策或单一模板 |
| Medium Governance（中型治理） | 300–500 行 | 一个治理主题及其证据、风险和状态 |
| Large Report（大型报告） | 超过 500 行 | 必须拆分为独立小报告，不得直接生成 |
任务另有更小上限时执行更严格限制。不得用压缩可读性、删除证据或合并不相干目标的方式规避行数门禁。
## 13. 报告证据规范

所有正式报告至少包含：
1. 日期；
2. 版本或阶段；
3. 任务类型；
4. 目标与非目标；
5. 实际输入文件路径；
6. 文件用途；
7. 关键原文、代码片段或结构化事实；
8. 判断依据；
9. 当前状态与差距；
10. 风险及优先级；
11. 保护状态；
12. 最终状态；
13. 归档行数和 SHA256；
14. 回读及可审查状态。
引用代码或模型时必须提供真实路径；不能只写“仓库中存在”。
## 14. 保护状态统一模板

每个指令按实际授权填写 YES/NO，不得先写结论后忽略实际变更。
```text
Documentation Changed = YES/NO
Code Changed = YES/NO
Database Changed = YES/NO
Migration Created = YES/NO
API Created = YES/NO
Page Created = YES/NO
Organization Data Changed = YES/NO
Responsibility Data Changed = YES/NO
Employee Data Changed = YES/NO
Permission Model Changed = YES/NO
Workflow Runtime Changed = YES/NO
ApprovalTask Changed = YES/NO
RRE Started = YES/NO
Unauthorized Business Writes = 0
```
专项任务必须增加对应保护，例如 PurchaseOrder 数量、SupplierMaterialPrice 数量、外部网络调用、银行发送、生产密钥和业务状态写入。
`Unauthorized Business Writes` 只允许为 0；若大于 0，立即停止、保留证据并报告 FAILED/BLOCKED。
## 15. 大任务拆分规则
满足任一条件必须评估拆分：
- 涉及多个模块；
- 涉及 Schema、服务、页面、数据等多个层；
- 同时包含设计和实施；
- 包含多个 Migration 或业务数据批次；
- 预计报告超过指定上限；
- 需要不同签发人或不同 Gate；
- 一个失败点会阻断其他独立工作。
- 输入文件超过 10 个；
- 预计正文超过 500 行；
- 涉及超过 3 个系统模块。
标准拆分：
```text
大问题
↓
小任务 1 → 小报告 1 → 冻结点 1
↓
小任务 2 → 小报告 2 → 冻结点 2
↓
综合评估
↓
下一阶段授权
```
每个子任务独立声明输入、输出、保护和停止状态。禁止在完成子任务后自动进入下一子任务。
大任务的标准治理链为：
```text
大问题
↓
阶段任务
↓
单个目标
↓
单份报告
↓
冻结
↓
下一阶段
```
禁止一个 CODEX 指令同时包含设计、实施、测试和部署；即使它们属于同一业务主题，也必须按授权阶段拆分。
## 16. 指令质量门禁
发送给 CODEX 前，指令编制人必须检查：
| 编号 | 检查 | FAIL 条件 |
|---|---|---|
| IQ-01 | 任务名称唯一 | 无模块/阶段/目标 |
| IQ-02 | 任务类型明确 | 设计与实施混用 |
| IQ-03 | 唯一目标 | 两个以上独立结果 |
| IQ-04 | 基线完整 | 缺核心架构/权限/Runtime 文件 |
| IQ-05 | 允许范围明确 | 只能从禁止项反推允许项 |
| IQ-06 | 禁止范围完整 | 未覆盖代码/数据/下一阶段 |
| IQ-07 | 输出可定位 | 缺文件名、路径或格式 |
| IQ-08 | 报告规模可控 | 无行数范围或明显超载 |
| IQ-09 | 保护模板完整 | 缺未授权写入状态 |
| IQ-10 | 归档可审查 | 未要求回读和正文 |
| IQ-11 | 结束状态明确 | 完成后可能自动继续 |
| IQ-12 | 授权依赖无闭环 | PASS 需要被禁止的证据却无受控阶段 |
| IQ-13 | Context Scope | 无最小必要基线或无目的读取历史文件 |
| IQ-14 | Input Files | 超过 10 个但未复评拆分 |
| IQ-15 | Module Scope | 超过 3 个模块但未复评拆分 |
| IQ-16 | Output Size | 超过 500 行但未拆分 |
任一 P0 项 FAIL，指令不得执行。
## 17. 标准指令模板
```markdown
# Codex 指令

## 任务名称

[系统 / 模块 / 阶段 / 唯一目标]
## 一、任务性质

阶段：...
类型：DESIGN / PREPARATION / CONTROLLED EVIDENCE BUILD / IMPLEMENTATION
本轮只解决：...
完成后立即停止。
## 二、必须读取治理基线

1. 路径、文件、用途、确认事项
2. 当前任务专项文件
## 三、允许范围

- ...
## 四、禁止事项

- 代码 / 数据库 / Migration / API / 页面 / 数据 / 权限 / Workflow / 下一阶段
## 五、唯一目标

生成或完成：...
## 六、核心任务

1. 输入、判断、输出
2. 风险和停止条件
## 七、输出要求

文件名：...
路径：...
格式：Markdown
行数：... 至 ...
## 八、原文可见性与归档

- 保存
- 完整回读
- 行数
- SHA256
- 完整正文或连续分块正文
## 九、保护要求

[统一模板 + 专项保护]
## 十、结束状态

[当前 COMPLETE/PASS/BLOCKED]
[下一阶段 NOT STARTED / NOT AUTHORIZED]
执行完成后停止。
```
## 18. 归档、版本与修订管理
### 18.1 文件命名
使用稳定的系统、模块、版本、阶段和主题。禁止同一正式报告存在多个仅空格或标点不同的文件名。
### 18.2 修订
修订正式文档时：
- 保留原文件名，除非正式升级版本；
- 不用状态摘要覆盖完整正文；
- 记录修订原因、前后状态和影响；
- 修订后重新计算行数和 SHA256；
- 重新执行完整回读；
- 如影响 Gate，发起独立重评，不能自动改 Gate。
### 18.3 版本升级
规则语义变化使用 V1.1、V2.0 等新版本，并提供替代关系。旧文件可归档，但不能与新版本同时作为活动唯一规范。
### 18.4 V1.1 替代关系

V1.1 自归档完成后替代 V1.0 成为活动唯一规范。V1.0 作为历史母版保留，只用于审计、差异比较和历史任务解释。
后续正式指令必须引用：
```text
D:\Dev-PCE\Source\docs\governance\PCE CODEX开发指令规范管理V1.1.md
```
## 19. 异常、阻断与恢复
### 19.1 输出中断
文件已完整落盘但聊天输出中断：先回读确认文件，随后从完整章节或标号分块重新发送，不重新生成不同正文。
### 19.2 文件写入失败
不得声明 COMPLETE。报告错误、目标路径、已有临时结果和是否发生其他变更。
### 19.3 基线冲突
停止并列出冲突文件、原文、影响和需要人工裁决的问题，不自行选择对自己最方便的规则。
### 19.4 发现越权需求
只输出设计说明或授权缺口；不得“顺便”修改 Schema、Permission、Workflow 或业务数据。
### 19.5 网络与流稳定性保护

出现以下任一错误时，不得无限重复“继续”：
- `stream disconnected`；`Transport error`；
- `response body decoding error`。
处理顺序：
```text
停止当前连接尝试
↓
确认文件是否已完整落盘
↓
检查输入、上下文和输出规模
↓
拆分生成、回读和正文传输阶段
↓
从最后一个已验证冻结点恢复
```
禁止因传输失败重新执行已经完成的代码、数据库或业务写入。不得在未核验落盘状态时重复生成同名报告。
### 19.6 恢复点要求

长任务必须在“输入确认、文件落盘、完整性验证、归档回读”形成可识别恢复点。恢复时复用最终文件和 SHA256，不依赖模型记忆续写半句。
## 20. 本规范的验收清单
| 编号 | 验收项 | 结果 |
|---|---|---|
| CGS-01 | 唯一规范来源声明 | PASS |
| CGS-02 | 指令生命周期 | PASS |
| CGS-03 | 标准指令结构 | PASS |
| CGS-04 | 基线阅读规范 | PASS |
| CGS-05 | 小步快走与拆分 | PASS |
| CGS-06 | Design/Preparation/Evidence/Implementation 分离 | PASS |
| CGS-07 | Controlled Evidence Build | PASS |
| CGS-08 | 归档完整回读 | PASS |
| CGS-09 | ChatGPT 可审查正文 | PASS |
| CGS-10 | 文件完整性 | PASS |
| CGS-11 | 报告证据 | PASS |
| CGS-12 | 保护模板 | PASS |
| CGS-13 | Context Management | PASS |
| CGS-14 | Level 0/1/2 基线分层 | PASS |
| CGS-15 | 输入文件、报告行数和模块数量门禁 | PASS |
| CGS-16 | 生成与归档回读阶段拆分 | PASS |
| CGS-17 | 网络错误停止与恢复 | PASS |
| CGS-18 | CODEX 执行质量指标 | PASS |
### 20.1 CODEX 执行质量指标

每个正式任务必须在最终状态附近报告：
```text
Context Scope = CONTROLLED
Input Files = [实际数量]
Task Scope = SINGLE
Output Size = [实际行数 / 指令上限]
Archive Readback = YES
ChatGPT Reviewable = YES
```
任一指标无法确认时不得声明完整归档；数值必须来自最终文件和实际输入，不得预填。
## 21. 本轮保护确认
```text
Documentation Changed = YES
Code Changed = NO
Database Changed = NO
Migration Created = NO
API Created = NO
Page Created = NO
Organization Data Changed = NO
Responsibility Data Changed = NO
Employee Data Changed = NO
Permission Model Changed = NO
Workflow Runtime Changed = NO
ApprovalTask Changed = NO
RRE Started = NO
Unauthorized Business Writes = 0
```
## 22. 最终状态
```text
PCE CODEX Development Instruction Governance Standard V1.1 = COMPLETE
Context Scope = CONTROLLED
Input Files = 4
Task Scope = SINGLE
Output Size = WITHIN 300-600 LINES
Documentation Archived = YES
Archive Content Readback = YES
ChatGPT Reviewable = YES
Source Excerpts Verified = YES
No Code Change
No Database Change
No Migration
No API
No Business Data Change
```
本规范编制与归档完成后立即停止，不进入任何 CODEX 实际开发、OOM 实施、Schema、Migration、API、页面或数据导入任务。

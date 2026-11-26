# PCE CODEX 开发指令规范管理 V1.2

日期：2026-08-19  
最近原位合并修订：2026-09-08  
本次原位增补：2026-09-29，新增第 34 节“业务流程中心优先开发原则”；保留 V1.2 既有正文和保护门禁。  
版本：V1.2（持续生效；未建立并行版本）  
阶段：PCE CODEX Development Instruction Governance Standard V1.2（PCE CODEX 开发指令治理规范 V1.2）  
类型：GOVERNANCE DOCUMENT UPDATE ONLY（治理规范更新，仅修改规范文件）  
适用范围：Dev-PCE 后续全部 CODEX 设计、评审、准备、证据构建和实施指令  
规范权威：本文件是 PCE CODEX 指令结构、边界、归档和回读要求的唯一规范来源  
实施授权：NOT APPLICABLE；本文件不授权任何业务或技术实施  
升级来源：V1.1 完整母版；V1.2 新增 Risk-Based Review（风险分级审查）、自动升级触发、分级正文交付和审查质量指标；2026-09-08 原位合并《CODEX INSTRUCTION CONTROL & USER-VISIBLE ACCEPTANCE CONTRACT V1.0》  
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
D:\Dev-PCE\Source\docs\governance\PCE CODEX开发指令规范管理V1.2.md
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
### 3.3 V1.2 升级直接依据

| 实际路径 | 关键原文/事实 | V1.2 判断 |
|---|---|---|
| `D:\Dev-PCE\Source\docs\governance\PCE CODEX开发指令规范管理V1.1.md` | “禁止在同一次长响应中同时承担超长正文生成、完整回读和全量传输” | 保留归档回读，正文交付按风险分级 |
| `D:\Dev-PCE\Source\docs\governance\PCE Organization Operating Model V2 Controlled Evidence Build Authorization评审与授权申请设计报告.md` | “APPROVED 不表示证据构建已经 ACTIVE（执行中）” | 授权、Gate 和实施节点使用高等级审查 |
| `D:\Dev-PCE\Source\docs\governance\PCE Controlled Evidence Build Authorization Request Template设计报告.md` | 468 行；`Review Level` 尚未成为交付字段 | 长模板设计无需默认全文回传，但必须完整归档回读 |
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
| Level 0 | CODEX 核心规范基线 | 每个正式 CODEX 任务必须读取当前活动版本 `PCE CODEX开发指令规范管理V1.2.md` |
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
14. 初始 Review Level 是 A、B 还是 C，是否存在自动升级触发条件；
15. `Full Content Review Required` 是否与 Review Level 一致。
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
9. 按 Review Level（审查等级）提供摘要、关键章节或完整正文；Level C 必须提供完整正文或连续、标号明确且无缺失的正文块；
10. 明确等待 ChatGPT / 人工审查。
### 11.2 强制状态
```text
Documentation Archived = YES
Archive Content Readback = YES
ChatGPT Reviewable = YES
Review Level = A / B / C
Full Content Review Required = YES / NO
```
前三项任何一项不是 YES，文档任务不得声明归档完成。Review Level 和全文要求必须与任务实际风险一致。
### 11.3 禁止的交付方式

禁止只返回本地路径、行数、SHA256 或 COMPLETE 状态；禁止返回与 Review Level 不匹配的证据；禁止返回被截断的开头或结尾。
路径、行数和 SHA256 是完整性元数据，不能单独替代可审查内容。Level A 必须提供关键结论和保护状态；Level B 必须提供关键章节、判断依据和风险；Level C 必须提供完整正文。
### 11.4 正文过长

优先在任务设计阶段拆分报告。只有 Review Level C 或人工明确要求全文时，长文才按 `Part 1/N` 至 `Part N/N` 返回；每部分必须标明连续章节，最后提供全文 Hash。Level A/B 不得为了形式要求无风险地重复传输全文。
长报告的交付必须分为两个可恢复阶段：
```text
阶段 A：生成并验证文件
输出：文件路径、行数、SHA256
↓
阶段 B：归档回读与可审查交付
输出：Archive Content Readback、ChatGPT Reviewable、按 Review Level 提供摘要、关键章节或连续正文块
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
### 12.2 Risk-Based Review（风险分级审查规范）

风险分级审查用于在保持关键节点深度审查的同时，避免普通设计任务重复传输超长正文。审查等级决定对话中的交付深度，不降低文件归档、完整回读、证据真实性、授权边界或保护要求。
#### 12.2.1 Level A：快速治理审查

适用范围：

- 普通 Design（设计）文档、模板设计、治理流程设计和状态确认；无代码、数据库、Migration、API、页面、权限、Workflow 或正式业务数据变化；不作架构冻结、Gate 裁决、实施授权或生产决定。

交付要求：

- 文件路径、行数、SHA256 和归档回读状态；任务状态、关键结论、保护状态和必要章节摘要；实际输入文件数量及关键证据核验结果。

Level A 不强制在对话中传输全文。需要全文时应通过已回读归档文件提供，或由人工明确升级审查。
#### 12.2.2 Level B：重点审查

适用范围：

- 架构设计、Gate 评估、Schema 设计、Service 设计、权限设计、Workflow 设计和数据模型设计；涉及多个模块、事实来源、权限边界、运行边界或重要兼容决策；核心治理规范的新版本升级。

交付要求：

- Level A 的全部元数据和状态；关键章节、关键判断依据、风险点、边界和最终状态；对直接支撑结论的原文或结构化证据进行核验。

Level B 默认不强制全文传输；审查人认为关键上下文不足、结论存在争议或文件不可直接读取时，可以要求全文或指定章节。
#### 12.2.3 Level C：强制全文审查

以下任务必须使用 Level C：

- Implementation（正式实施）、Migration、数据导入或业务数据切换；
- Permission（权限）变更、Workflow 上线、RRE 启动或生产外部副作用；
- Gate PASS 裁决、OOM-4.2 Implementation Authorization Review（实施授权评审）；
- 发现异常、冲突、未授权写入、关键证据不一致或回退失败。

Level C 要求：
```text
Documentation Archived = YES
Archive Content Readback = YES
ChatGPT Reviewable = YES
Full Content Review Required = YES
```

完整正文必须可直接审查；正文过长时使用连续分块，不得只提供摘要、路径或 Hash。
#### 12.2.4 默认审查策略
```text
设计任务 = Level A
架构任务 = Level B
实施任务 = Level C
```

任务同时符合多个等级时采用最高等级。核心治理规范升级至少为 Level B，不得因“只修改文档”降为 Level A。
#### 12.2.5 自动升级触发规则

Level A 自动升级为 Level B 的条件：

- 发现架构影响；涉及多个模块；涉及权限、数据、组织事实或运行边界；
- 需要冻结模型、契约、治理规则或兼容决策；
- 摘要不足以支撑关键判断。

Level B 自动升级为 Level C 的条件：

- 代码、数据库、Migration、API、页面或正式业务数据发生变化；
- 发生权限变更、Workflow 上线、RRE 启动或生产副作用；
- 作出实施授权、Gate PASS 或生产放行裁决；
- 发现异常、冲突、证据漂移、未授权写入或无法证明回退。

升级后不得继续使用较低等级的交付规则。审查等级只能因范围和风险变化上调；任务完成前不得为了缩短输出而下调。
#### 12.2.6 ChatGPT Reviewable（可审查）定义

`ChatGPT Reviewable = YES` 表示已按当前 Review Level 提供充分材料，不再等同于所有任务都已在对话中传输全文：
| Review Level | 可审查材料 |
|---|---|
| A | 摘要、状态、关键证据和保护状态足以判断 |
| B | 关键章节、判断依据、风险、边界和状态足以判断 |
| C | 完整正文可直接审查，必要时连续分块 |

无论等级如何，`Archive Content Readback = YES` 都要求 CODEX 实际重新读取完整归档文件，而不是只检查文件存在。
#### 12.2.7 上下文控制升级

- 禁止为满足形式上的全文要求，对无代码、无数据、无授权裁决的低风险任务重复传输超长正文；
- 优先交付归档文件、SHA256、Review Level、关键章节和保护状态；
- 已验证的活动基线不因全文传输要求而重复加载；没有明确依赖的历史文件不得读取；
- 若对话连接不稳定，先保全最终归档文件和 Hash，再按当前等级恢复交付；不得重新执行已完成写入。
#### 12.2.8 Review Level 决策记录

Preflight 必须记录初始等级、触发依据和是否要求全文。执行中触发升级时，必须记录升级原因。最终状态必须使用实际最终等级。
```text
Review Level = A / B / C
Full Content Review Required = YES / NO
```

Level A/B 的 `Full Content Review Required = NO` 不代表正文缺失；正文仍必须完整归档并完成回读。
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
15. Review Level、等级依据和是否要求全文。
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
| IQ-10 | 归档可审查 | 未要求完整回读，或可审查材料与 Review Level 不匹配 |
| IQ-11 | 结束状态明确 | 完成后可能自动继续 |
| IQ-12 | 授权依赖无闭环 | PASS 需要被禁止的证据却无受控阶段 |
| IQ-13 | Context Scope | 无最小必要基线或无目的读取历史文件 |
| IQ-14 | Input Files | 超过 10 个但未复评拆分 |
| IQ-15 | Module Scope | 超过 3 个模块但未复评拆分 |
| IQ-16 | Output Size | 超过 500 行但未拆分 |
| IQ-17 | Review Level | 未分级、等级低于实际风险或未处理升级触发 |
| IQ-18 | Full Content Review | Level C 未要求全文，或 Level A/B 无理由强制超长全文 |
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
## 二-A、Completed Module Protection（强制，不得删除）

COMPLETED MODULE GOVERNANCE READING RECEIPT

Preservation Standard Read = YES / NO

Completed Module Registry Read = YES / NO

Affected Frozen Modules = [...]

Freeze Contracts Read = [...]

Unfreeze Authorization = YES / NO

Preserve-and-Extend Analysis = ...

Non-Regression Plan = ...

User Reality Conflict Rule = USER REALITY OVERRIDES AUTOMATION

Preflight Result = SAFE TO MODIFY / UNFREEZE AUTHORIZATION REQUIRED

以上字段缺失、读取为 NO、或 Preflight 未通过时，指令不得执行源码修改。无用户明确授权不得修改 Frozen Core Contract。
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
- Review Level A：摘要、状态、关键证据
- Review Level B：关键章节、判断依据、风险和状态
- Review Level C：完整正文或连续分块正文
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
规则语义变化使用 V1.2、V2.0 等新版本，并提供替代关系。旧文件可归档，但不能与新版本同时作为活动唯一规范。
### 18.4 V1.2 替代关系

V1.2 自归档完成后替代 V1.1 成为活动唯一规范。V1.1 及 V1.0 作为历史母版保留，只用于审计、差异比较和历史任务解释。
后续正式指令必须引用：
```text
D:\Dev-PCE\Source\docs\governance\PCE CODEX开发指令规范管理V1.2.md
```
## 19. 异常、阻断与恢复
### 19.1 输出中断
文件已完整落盘但聊天输出中断：先回读确认文件，随后按 Review Level 从完整章节、关键章节或标号分块恢复发送，不重新生成不同正文。
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
| CGS-19 | Risk-Based Review 三级审查 | PASS |
| CGS-20 | 自动升级触发规则 | PASS |
| CGS-21 | 分级 ChatGPT Reviewable 定义 | PASS |
| CGS-22 | Level C 强制全文审查 | PASS |
### 20.1 CODEX 执行质量指标

每个正式任务必须在最终状态附近报告：
```text
Context Scope = CONTROLLED
Input Files = [实际数量]
Task Scope = SINGLE
Output Size = [实际行数 / 指令上限]
Review Level = A / B / C
Full Content Review Required = YES / NO
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
PCE CODEX Development Instruction Governance Standard V1.2 = COMPLETE
Context Scope = CONTROLLED
Input Files = 3
Task Scope = SINGLE
Output Size = WITHIN 300-700 LINES
Review Level = B
Full Content Review Required = NO
Documentation Archived = YES
Archive Content Readback = YES
ChatGPT Reviewable = YES
Source Excerpts Verified = YES
No Implementation / No Code Change / No Database Change
No Migration / No API
No Business Data Change
```
本规范编制与归档完成后立即停止，不进入任何 CODEX 实际开发、OOM 实施、Schema、Migration、API、页面或数据导入任务。

## 23. CODEX 指令控制与用户可见验收合同

### 23.1 合同地位

自 2026-09-08 起，《CODEX INSTRUCTION CONTROL & USER-VISIBLE ACCEPTANCE CONTRACT V1.0》的全部有效约束原位合并到本文件。本文件继续作为唯一正式治理归宿，不建立 `V2`、`WholeHouse` 或其它平行治理文件。

本次合并不替换第 1–22 节，而是 `PRESERVE + EXTEND`。如旧条款与本节相比约束较弱，以本节更严格的控制、非回归和用户可见验收要求为准；更高层安全与用户明确授权仍优先。

项目级自动读取入口 `D:\Dev-PCE\AGENTS.md` 只登记核心强制规则和本文件路径，不承担第二份完整规范的职责。

### 23.2 长文档例外

本文件在合并前已超过 500 行。因用户明确要求唯一正式治理位置并禁止重复治理文件，本次允许继续原位合并。后续通过稳定章节编号、控制模板、登记表和按需回读控制上下文；不得以行数为由拆出内容重叠的平行规范。

## 24. EFFECTIVE INSTRUCTION SET 与 INSTRUCTION REGISTER

### 24.1 有效指令集

每个多轮任务必须维护 `EFFECTIVE INSTRUCTION SET`，至少包含：

1. 当前用户已明确发出的 ACTIVE 指令；
2. 未被明确取代且仍有效的历史约束；
3. 用户已经作出的人工裁决；
4. 已冻结范围、停止点、数据写入边界和非回归基线；
5. 适用的 `AGENTS.md` 与正式治理规范。

只处理最后一条消息、遗忘前轮仍有效约束或将聊天摘要当成完整指令集，均属于指令控制失败。

`NOT YET SENT ≠ ACTIVE`。用户尚未发送、仅被预告、推测或模型自行扩展的后续指令不得进入 ACTIVE 状态，也不得据此开始实施。

### 24.2 指令状态

| 状态 | 含义 |
|---|---|
| ACTIVE | 当前必须执行且尚未被取代的指令 |
| SUPERSEDED | 已被用户后续明确指令全部取代；必须记录取代者 |
| FROZEN | 结果或边界已冻结，后续任务不得擅自改动或重跑 |
| COMPLETED | 指令工作已完成，但其中标注为持续有效的约束仍进入有效指令集 |

不得因状态为 `COMPLETED` 就删除长期约束；不得将部分变化误报为整条指令 `SUPERSEDED`。

### 24.3 指令登记表模板

每个正式多轮任务开始时建立并持续更新下表：

| ID | 日期 | 目的 | 状态 | Superseded By | 仍有效约束 | 用户裁决 |
|---|---|---|---|---|---|---|
| `[任务-ID]` | `YYYY-MM-DD` | `[单一目标]` | `ACTIVE/SUPERSEDED/FROZEN/COMPLETED` | `[ID/NONE]` | `[范围/边界/停止点]` | `[明确裁决/NONE]` |

登记表可以位于当前正式任务文档或最终合并报告中；不得另建与本规范竞争的治理总表。

### 24.4 当前合同登记

| ID | 日期 | 目的 | 状态 | Superseded By | 仍有效约束 | 用户裁决 |
|---|---|---|---|---|---|---|
| CIC-20260908-001 | 2026-09-08 | 建立指令控制、非回归、用户可见真实路径与最终合并报告合同 | ACTIVE | NONE | 全部第 23–32 节；不进入业务开发 | 用户真实页面优先；人工验收独立且只由用户授予 |
| BPC-20260929-001 | 2026-09-29 | 确立业务流程中心优先开发主线 | ACTIVE | NONE | 第 34 节；不降低既有保护与授权门禁 | 用户明确要求以后所有 PCE 开发指令遵循业务流程中心优先原则 |

## 25. PRE-DEVELOPMENT GOVERNANCE READ

### 25.1 强制读取顺序

任何设计、修改、实施、测试或状态判定前必须：

1. 从所在目录向上读取全部适用 `AGENTS.md`；
2. 完整读取本文件；
3. 读取与任务范围直接相关的专项治理、架构和验收规范；
4. 建立有效指令集、指令登记表和控制单；
5. 在首次修改前输出治理读取回执。

### 25.2 GOVERNANCE READING RECEIPT 模板

```text
GOVERNANCE READING RECEIPT
Project Instruction Entry = [path]
Formal Governance Location = [path]
Applicable Specialized Standards = [paths / NONE]
Governance Files / Versions = [{path, version/current status}]
Key Applicable Rules = [本任务直接适用条款]
Current Task Constraints = [范围、数据、权限、验收与停止约束]
Effective Instruction Set Built = YES / NO
Instruction Register Updated = YES / NO
Conflicts Found = [NONE / description]
Resolution = [rule / user decision]
Authorized Scope = [scope]
Stop Condition = [condition]
```

没有该回执，不得开始修改。读取文件名但未读取正文不算完成。

## 26. INSTRUCTION CONTROL SHEET

每个正式开发任务必须在首次修改前填写以下控制单：

```text
INSTRUCTION CONTROL SHEET
Original Goal = [最初目标]
Current Goal = [当前经合法变更后的目标]
IN SCOPE = [允许事项]
OUT OF SCOPE = [禁止事项]
User Decisions = [已明确裁决]
Frozen Facts / Functions = [不得重跑或改变的事实与功能]
Non-Regression Baseline = [修改前可见模块、路由、数据与能力]
Database Boundary = [只读/允许的受控写入/禁止写入]
User Acceptance Path = [正常菜单点击路径；非 UI 任务填 N/A]
Required Evidence = [代码/API/UI/截图/计数]
Stop Condition = [第一停止点]
```

范围改变时必须更新 `Current Goal`、登记关联指令 ID 并重新检查授权；不得静默扩大范围。

## 27. PCE NON-REGRESSION GATE

### 27.1 强制原则

```text
NEW FUNCTION = PASS
EXISTING FUNCTION REGRESSION = 0
OVERALL = PASS
```

只要新功能存在但任何未经授权的旧功能减少、消失、不可见、不可进入或事实退化，`OVERALL = FAIL`。

### 27.2 修改前冻结

修改 Navigation、Router、Registry、页面组合、API 合同或数据投影前，必须以只读证据冻结：

- 现有模块、菜单、路由和页面集合；
- 当前用户真实点击路径；
- 页面标题、默认选中项和可见记录总数；
- 权限动作与维护入口；
- 当前正式数据源和关键事实计数。

Navigation 任务还必须保护左侧主菜单、系统配置、组织结构、业务流程中心、个人工作台、分析中心及所有修改前已存在的系统配置模块。企业基础资料等既有页面的“物料与供应、产品工程、制造资源、仓储基础”等页内结构必须保持；新增验收能力只能增强模块操作，不得提升成平行目录或破坏原页面布局。

Navigation 专项门禁固定表达为：

```text
EXPECTED_EXISTING_NAVIGATION ⊆ CURRENT_NAVIGATION
```

禁止全局回滚。发现缺陷时必须 `fix current scope only`，保留其它已完成且有效的修改。

### 27.3 Gate 模板

| Gate | 修改前基线 | 修改后结果 | 判定 | 证据 |
|---|---|---|---|---|
| Expected Existing Modules ⊆ Current Modules | `[set]` | `[set]` | PASS/FAIL | `[registry/menu]` |
| Existing Routes Reachable | `[routes]` | `[routes]` | PASS/FAIL | `[click trace]` |
| Existing Page Responsibilities Unchanged | `[mapping]` | `[mapping]` | PASS/FAIL | `[title/source]` |
| Existing Visible Data Not Reduced | `[count]` | `[count]` | PASS/FAIL | `[UI/API/DB]` |
| Existing Authorized Actions Preserved | `[actions]` | `[actions]` | PASS/FAIL | `[permission UI]` |
| Unauthorized Business Writes | `0` | `[count]` | PASS/FAIL | `[write evidence]` |

所有适用项 PASS 才能声明非回归门禁 PASS。

## 28. USER-VISIBLE REAL-PATH 与 UI DATA VISIBILITY GATE

### 28.1 用户可见验收原则

用户可见结果必须从业务用户正常入口实际点击验证。手工输入内部 URL、组件测试、Router 测试、API 数量或直接打开技术 Route 均不能单独证明用户可见 PASS。

每次 UI 验收至少记录：

```text
USER_CLICK_PATH = [逐级中文点击路径]
FINAL_URL = [最终 URL]
FINAL_PAGE_TITLE = [用户实际看到的标题]
VISIBLE_MODULES = [用户实际可见模块]
VISIBLE_RECORD_COUNT = [列表实际可见总数]
VISIBLE_PRIMARY_ACTIONS = [用户实际可见操作]
EXPECTED = [预期结果]
ACTUAL = [实际结果]
RESULT = [PASS/FAIL]
RETURN_PATH = [面包屑/返回入口]
REFRESH_RESULT = [PASS/FAIL]
PERMISSION_RESULT = [PASS/FAIL]
SCREENSHOT_EVIDENCE = [artifact/path]
```

必须保留最终页面供用户检查；除非用户要求，不得在取证后自动跳离。

用户提供的截图、实际操作结果和业务判断属于正式 Acceptance Evidence。截图证明页面为空、菜单丢失、数据错误或入口错误时，不得继续引用旧的自动化 PASS 否定用户结果。

### 28.2 页面职责不得混用

不同正式对象的页面、Route、默认选中状态与数据源必须一一对应。相关对象可以导航互通，但不得用另一个对象页面或另一个对象的计数冒充当前对象可见。

### 28.3 UI DATA VISIBILITY GATE 模板

当 DB 或 API 正式记录数大于 0 时，正式页面必须显示相同业务范围的记录总数和真实记录；加载失败不得伪装为 0。

| 层级 | 数据源/端点 | 期望记录数 | 实际记录数 | 业务范围一致 | 判定 |
|---|---|---:|---:|---|---|
| Database | `[formal model]` | `[n]` | `[n]` | YES/NO | PASS/FAIL |
| API | `[formal endpoint]` | `[n]` | `[n]` | YES/NO | PASS/FAIL |
| Formal UI | `[normal user path]` | `[n]` | `[visible total]` | YES/NO | PASS/FAIL |

`DB/API > 0` 且 `Formal UI = 0/unknown/wrong object` 时，本 Gate 必须 FAIL。

## 29. 事实来源与验证等级分离

### 29.1 数据来源标签

来源事实、正式数据、Preview、模拟补充和系统派生必须显式分开：

```text
SOURCE / FORMAL / PREVIEW / SIMULATED_FOR_TEST / SYSTEM_DERIVED
```

不得用 Preview 或模拟数据制造正式数据 READY；不得覆盖来源真实值；系统生成技术标识不得冒充用户历史事实。

### 29.2 三状态独立

每个模块必须分别报告：

```text
DEVELOPED = TRUE/FALSE
DATA PRESENT = TRUE/FALSE
USER VALIDATED = TRUE/FALSE
```

页面存在不等于数据存在；数据存在不等于用户已验收。

### 29.3 验证层级独立

以下状态必须分别给出，不得互相替代：

```text
Code Inspection
Unit Test
API / Contract Test
Build
Codex Self-Validation
User-Visible Real-Path Validation
User Manual Validation
```

`USER VALIDATED = TRUE` 只能来自用户明确的人工裁决。Codex、测试、截图、API 或数据库计数都无权自动授予。

Codex 负责代码、Schema、API、事务、Migration、权限、审计与自动测试的专业技术验证；用户负责客户、物料、工艺、产能、计划真实性以及页面操作习惯的业务人工验证。不得要求用户代替 Codex 验证技术内部对象。

正式开发顺序必须为：

```text
READ GOVERNANCE
→ READ ORIGINAL / CURRENT CODE
→ INSTRUCTION CONTROL SHEET
→ IMPLEMENT
→ AUTOMATED TEST
→ SELF VALIDATION
→ USER-VISIBLE REAL PATH VALIDATION
→ NON-REGRESSION VALIDATION
→ PACKAGE / PAGE READY
→ USER MANUAL VALIDATION
```

自行验证必须使用最终封包内容，并证明：

```text
tested-code == delivered-code
tested-route == delivered-route
tested-config == delivered-config
tested-page == delivered-page
```

每个关键 PASS 必须绑定对象、验证位置、进入方式、可见内容、记录数量、预期、实际和 Evidence；任一项无法回答时不得 PASS。

## 30. REPORT ≠ USER REALITY 冲突规则

一旦用户截图、真实点击结果或明确观察与 Codex 报告不一致，必须立即：

1. 撤销相关 PASS，状态改为 FAIL 或 NOT READY；
2. 冻结下一阶段，禁止继续后续 Group、模块或业务流程；
3. 分类根因并比较 Codex 测试路径与用户真实路径；
4. 记录用户实际路径、最终 URL、页面标题和可见数量；
5. 只整改当前缺陷，不做全局回滚，不重跑已冻结业务数据；
6. 重新从正常菜单路径验证；
7. 等待用户人工确认。

用户真实页面是 UI 验收的最高事实来源。Codex 自动化报告不能覆盖用户实际观察。

Blocker 整改固定遵循：

```text
CURRENT BLOCKER → MINIMAL REMEDIATION → TARGETED RETEST
```

已经冻结的 PASS 不得为解决无关 Blocker 而重跑。

### 30.1 DELIVERED USER STATE CONTRACT

所有需要用户人工验收的 UI 任务，最终交付必须同时满足并分别记录：

```text
TESTED USER PATH = PASS
FINAL DELIVERED BROWSER STATE = PASS / NOT GUARANTEED
USER TAKES OVER SAME STATE = GUARANTEED / NOT GUARANTEED
USER MANUAL VALIDATION = PENDING
```

“测试过程中到达过页面”不等于“已经把同一页面状态交付给用户”。最终回复前必须在全部自动测试、构建和非退化检查完成之后，再使用用户实际可见的同一浏览器上下文与同一 Tab 执行最后一次正常业务路径，并采集 `FINAL_DELIVERED_USER_SCREEN_EVIDENCE`。

最终交付证据必须记录：

```text
DELIVERED_BROWSER_TAB = [同一实际应用浏览器与Tab标识]
DELIVERED_URL = [最后一次浏览器操作后的URL]
DELIVERED_PAGE_TITLE = [最后一次浏览器操作后的页面标题]
DELIVERED_ACTIVE_MODULE = [当前业务模块]
DELIVERED_ACTIVE_MODE = [当前查看/维护/来源对照/人工验收模式]
DELIVERED_VISIBLE_PRIMARY_CONTENT = [用户接手时直接可见的主要内容]
DELIVERED_TIMESTAMP = [带时区的采集时间]
```

最后一次交付取证完成后必须 `STOP ALL BROWSER ACTIONS`。不得再切换 Tab、导航、刷新、重启前端、运行会操作浏览器的测试或访问其它页面；否则当前交付证据立即失效，必须重新执行最后交付路径和取证。

最终回复前必须重新读取当前可见浏览器状态，不得依赖内存、旧截图、测试阶段页面、隐藏 Tab 或其它 Browser Context。只有 URL、页面标题、活动模块、活动模式和主要验收内容全部仍符合时，才能报告 `DELIVERED USER STATE = PASS`。

如果工具不能证明用户接手的是同一实际可见浏览器上下文与同一 Tab，必须报告：

```text
TESTED USER PATH = PASS / FAIL
DELIVERED USER STATE = NOT GUARANTEED
USER NAVIGATION REQUIRED = [正常中文点击路径]
```

不得在无法保证时声称“浏览器已停在验收页面”。用户随后提供的截图或实际观察仍是最高交付事实；如与报告冲突，立即按本章撤销 PASS。

## 31. FINAL CONSOLIDATED REPORT 与 COMPLIANCE MATRIX

### 31.1 最终报告规则

每轮正式任务只在工作真实结束或到达停止点后提交一份 `FINAL / CONSOLIDATED` 报告。中间更新不得包装为最终完成。

最终报告至少包含：目标、实际变更、未变更边界、证据、非回归结果、用户可见路径结果、数据可见性结果、人工验收状态、剩余阻断和停止点。

### 31.2 最终合规矩阵模板

| Compliance Item | Result | Evidence / Note |
|---|---|---|
| Original Goal | PASS/FAIL | `[原始目标与最终交付]` |
| Governance Reading Receipt | PASS/FAIL | `[receipt]` |
| Effective Instruction Set | PASS/FAIL | `[register IDs]` |
| Scope / Stop Condition | PASS/FAIL | `[control sheet]` |
| Existing Results Preserved | PASS/FAIL | `[baseline comparison]` |
| Automated Tests | PASS/FAIL/N/A | `[code/unit/API/build results]` |
| User-Visible Real Path | PASS/FAIL/N/A | `[click trace]` |
| UI Data Visibility | PASS/FAIL/N/A | `[DB/API/UI count]` |
| Non-Regression | PASS/FAIL | `[gate evidence]` |
| User Manual Validation | PASS/FAIL/PENDING/N/A | `[explicit user decision]` |
| Production Boundary | PASS/FAIL | `[write count / prohibited scope]` |
| Report vs User Reality Conflict | NONE/RESOLVED/BLOCKED | `[note]` |
| Final Stop Condition | PASS/FAIL | `[stop evidence]` |

任何 FAIL 不得在总状态中写成 PASS；`PENDING` 的用户人工验收不得由 Codex 改写为完成。

## 32. 本次合同建立的停止边界

本次工作只允许：治理现实检查、唯一正式位置确认、合同原位合并、指令登记表、控制单、非回归门禁、用户可见验收门禁和最终合规矩阵的建立。

明确禁止进入：GROUP 3B、BOM、Routing、GROUP 4、Planning、订单流程以及任何生产业务数据写入。

本次合并完成后状态为：

```text
CODEX INSTRUCTION CONTROL CONTRACT = ESTABLISHED
INSTRUCTION REGISTER = ACTIVE
PRE-DEVELOPMENT GOVERNANCE READ = MANDATORY
NON-REGRESSION GATE = MANDATORY
USER-VISIBLE REAL-PATH VALIDATION = MANDATORY
UI DATA VISIBILITY GATE = MANDATORY
USER MANUAL VALIDATION = SEPARATE / REQUIRED
FINAL CONSOLIDATED REPORT = MANDATORY
REPORT ≠ USER REALITY CONFLICT RULE = ACTIVE
```

到达本节停止点后立即停止，不进入任何业务开发。

## 33. PCE 前端页面身份单一事实源合同

### 33.1 单模块单身份

```text
ONE BUSINESS MODULE = ONE CANONICAL IDENTITY
```

每个业务模块只能有一个 canonical module identity。模块身份至少统一声明：业务域、模块标识、导航键、页面键、Route 名称、Route 路径、页面组件、正式数据源、API、权限和可用模式。导航、Router、页面注册和页面组件不得各自维护一份可决定业务对象的平行映射。

### 33.2 页面模式不是业务模块

```text
PAGE MODE != BUSINESS MODULE
```

`view / maintain / source_compare / acceptance` 只是同一模块的页面模式。切换模式必须保留 canonical module identity、正式数据源和页面上下文，不得以“人工验收页”“来源对照页”为名创建第二个业务模块。

### 33.3 Route 必须确定性表达页面状态

```text
ROUTE MUST EXPRESS MODULE + MODE
```

URL 和 Route meta 必须共同、确定性地解析为 `module + mode + recordId + filters/subview`。刷新、Deep Link 和同模块操作切换后必须得到相同状态。除应用根入口外，未知或冲突 Route 禁止静默回退到任意默认业务模块。

### 33.4 导航与 Router 只消费 canonical registry

```text
NAVIGATION / ROUTER MUST CONSUME CANONICAL REGISTRY
```

左侧导航、企业基础资料页内分组、人工验收中心、Route binding、页面标题和正式数据适配必须由同一个 canonical registry 派生。兼容旧入口只能重定向到 canonical route，不能继续成为页面身份 authority。

### 33.5 已测试前端必须等于实际服务前端

```text
TESTED FRONTEND = SERVED FRONTEND
```

构建或开发服务必须暴露可核对的运行身份，至少包含 Router、canonical registry、页面组件的内容哈希以及构建/运行标识。最终 PASS 必须证明测试读取的哈希与当前服务实例返回的哈希逐项一致；不一致时不得使用旧测试结论。

### 33.6 页面身份冲突必须失败

```text
PAGE IDENTITY MISMATCH = FAIL
```

Route 路径、Route meta、组件输入、canonical module、组件实现或数据适配器任一不一致时，必须显示可见诊断并停止加载，不得静默展示其它模块。前端验收 Gate 必须包含 canonical 唯一性、全模式解析、冲突注入、Golden Case、正常菜单真实路径与非回归检查。

## 34. PCE 业务流程中心优先开发原则

### 34.1 地位与建设顺序

自 2026-09-29 起，`BUSINESS PROCESS CENTER FIRST` 是 PCE 后续模块、流程、功能、数据模型、权限及支撑能力建设的最高业务主线。业务建设顺序固定为：

```text
企业业务流程 → 业务节点 → 业务对象 → 责任关系 → 权限控制 → 数据模型 → 软件实现
```

不得先建设孤立技术能力，再寻找业务用途。本原则决定开发目标与优先级，不豁免既有安全、人工授权、数据库保护、Frozen Core、Source/Baseline Gate 或非回归门禁；发生保护冲突时先停止并按既有规则处理。

### 34.2 业务流程中心与模块定位

业务流程中心是 PCE 正式业务的统一入口。正式业务应能从业务流程中心进入相应模块唯一正式流程；模块目录用于业务分类，不是第二套流程权威、重复工作台或额外必经门户。适用域包括 CRM、PDE、EMD、SCM、PLAN、MRP、MPS、APS、WMS、MES、QMS、BI/FDM、KPI、ProfitOS、FIN 等，但目录存在、流程节点存在、页面存在和用户可操作分别是不同事实，不能互相冒充。

新增或整合流程须遵守第 27–30、33 节以及《PCE 已开发模块固化与变更保护规范 V1.0》第 13 节：保留已验收菜单、路由、页面、API、数据权威、权限、Workflow、上下游关系与真实用户路径，优先连接、整合和完善，不为重画流程推翻已有成果。

### 34.3 开发入口问题与支撑能力约束

每个后续开发任务在设计或实施前必须回答：服务哪个业务流程；流程起点与终点；涉及哪些节点、对象和上下游；谁负责、谁操作、谁审核；业务人员从流程中心如何进入及完成。缺少这些信息时，任务可继续做有限的流程定义或必要保护整改，但不得把独立技术模块长期推进为正式业务交付。

组织、员工、权限、主数据、GRA、Workflow、审计和基础配置属于支撑能力。它们须说明所服务的流程节点和业务结果；GRA仅增强“谁负责”的治理证据，不替代流程、组织、岗位或系统权限。支撑能力的范围讨论不得无期限占用业务流程主线；但正式保护、授权或安全 Gate 未满足时，仍必须阻断受影响的实施动作，不得以“流程优先”绕过。

### 34.4 验收与后续指令

开发完成不能仅由代码、页面或 Build 证明。正式验收应从业务流程中心正常入口验证：入口、实际流程路径、操作步骤、服务端数据结果、业务规则、异常处理与返回路径；用户人工验收仍独立于 Codex 自动验证。任务报告须分别声明流程定义、技术实现、实际可见运行与人工验收状态，不得用流程图或模块目录推断业务已可操作。

后续 PCE 开发指令必须记录本节的流程定位、起止、对象、责任、入口和验收路径。与本原则冲突的拟议开发应先重新评估；本节仅建立开发规范，不授权任何 Phase B Source/Baseline、GRA、Migration、数据写入或开发实施。

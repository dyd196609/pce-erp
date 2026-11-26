# Codex执行证据规范

- 规则编号：`CODEX-EVIDENCE-001`
- 生效版本：`V1.14.2.8.4.27.2.36`
- 适用范围：Codex执行的页面开发、修复、重构与验收任务
- 状态：长期有效

## 1. 禁止无证据PASS

验收报告不得只输出`XXX PASS`。每个关键结论必须绑定可重放的静态证据、真实URL证据或用户操作证据，并记录证据位置。

## 2. 页面运行证据格式

```text
Runtime Evidence:
URL: <真实运行URL>
Page Title: <浏览器和页面标题>
区域: PASS/FAIL + <稳定区域标识>
字段: PASS/FAIL + <字段和值来源>
按钮: PASS/FAIL + <按钮名称和Handler>
Action Result: PASS/FAIL + <可观察结果>
验收区域: <顶部/中部/底部 + 稳定标识>
检查字段: <用户可见字段名称>
检查按钮: <用户可见按钮名称>
期望结果: <需求声明结果>
实际结果: <浏览器实际结果>
Screenshot: <本次会话截图路径>
```

刷新类动作还必须输出刷新前后URL、对象业务键、Provider Reload计数、UI更新时间和业务写入数。打印类动作必须输出打印入口、预览区域、设置项及预览模型来源。

## 3. 证据层级

- 静态证据：文件、路由、组件、契约和测试；
- 运行证据：真实URL、页面标题、DOM区域、字段和值；
- 操作证据：点击、输入、处理链和结果；
- 边界证据：禁改资产哈希、业务写入计数和数据库哈希。

构建PASS只能作为工程证据，不能替代运行或操作证据。真实页面未达到需求时，必须执行`CODEX-COMMAND-002`并阻断READY。

## 4. 归档与判定

自动报告和真实页面证据归档到`frontend/test-results`；治理-only版本的示范证据可归档到`docs/governance/evidence/<version>`。扫描报告记录当前Renderer和迁移结果。证据缺失为UNKNOWN；证据与结论冲突时以真实运行结果为准。

## 5. Codex强制九段式执行模板

以后所有开发任务必须按以下顺序执行和报告；任务无页面时第六段可以标记`N/A`并说明不存在可运行入口，禁止直接省略：

```text
一、版本定位
二、治理文件读取
三、执行前扫描
四、允许修改范围
五、实施内容
六、真实浏览器人工验收
七、自动验收
八、禁止修改范围
九、最终报告格式
```

第六段必须按页面逐项填写URL、页面标题、顶部/中部/底部区域、字段名称、按钮名称、期望结果、实际结果和截图路径。第七段必须给出可重放命令或检查入口，不得以人工观察代替自动验收。

## 6. 最终状态与READY门禁

最终报告必须显式包含：

```text
Automatic Acceptance: PASS/FAIL
Browser Human Acceptance: PASS/FAIL/N/A
Build: PASS/FAIL
Ready Gate: PASS/FAIL
```

包含页面或可运行入口时，只有前三项全部为PASS，`Ready Gate`才能为PASS。任一项为FAIL或UNKNOWN时禁止输出任何`*_READY`状态；自动PASS、人工FAIL固定输出`AUTO_PASS_HUMAN_FAIL`。报告中的状态必须与证据逐项一致。

## 7. 自动治理检查

- `HUMAN-ACCEPTANCE-REQUIRED-001`：版本报告存在“真实浏览器人工验收”章节，并按目标页面逐页记录；缺失为FAIL。
- `PAGE-EVIDENCE-001`：每页至少记录URL、页面标题、验收区域、字段名称、按钮名称、期望结果、实际结果和截图路径；任一必填项缺失为FAIL。
- `READY-GATE-001`：READY必须同时满足`Automatic Acceptance=PASS`、`Browser Human Acceptance=PASS`、`Build=PASS`；门禁不得被脚本、人工说明或历史版本结果覆盖。

## 8. 对象级证据、写入口径与运行优先规则

- `SAME-OBJECT-ACCEPTANCE-001`：证据必须逐条列出 Automatic Test、Runtime、API、Page、Clicked Object 与归档对象来源 ID。不得只给成功数、截图总数或业务编号近似匹配；任一 ID 缺失或不一致即 FAIL。
- `HUMAN-ACCEPTANCE-AUTHORITY-001`：最终报告使用 `Browser Automatic Acceptance`、`Real Browser Evidence`、`Human Acceptance` 三字段。Codex 自动浏览器不得签发人工 PASS；用户未明确确认时固定为 `WAITING`。
- `AUTHORIZED-BUSINESS-WRITE-001`：分别报告授权与未授权写入计数。授权写入台账至少包含 Object Type、Object ID、Write Count、Write Reason、Source Version、Test Fact/Formal Business Fact、Rollback Capability。
- `RUNTIME-BEFORE-TEST-001`：真实页面失败后的第一份证据必须覆盖 `Browser Page -> API -> Runtime -> Service -> Database`，并说明 QuerySet、过滤、分页、缓存、Session Memory、数据库环境、事务、Fixture 与 Mock。先补测试数据或直调内部服务形成的 PASS 不得作为修复证据。

旧报告若把自动浏览器结果写为人工 PASS，后续治理报告必须明确标注口径错误及替代状态，不能静默沿用。

## 9. 价格持久化对账证据（V1.14.2.8.4.27.2.45.9）

价格持久化报告必须列出数据库路径与表名、正式/有效/停用数、Runtime 数、API 数、浏览器数和至少三个共同价格编号。数据库或 Runtime 有数据但页面为零时禁止 PASS；必须精确定位契约字段、过滤、租户、状态、缓存、数据库环境或事务中的真实根因。

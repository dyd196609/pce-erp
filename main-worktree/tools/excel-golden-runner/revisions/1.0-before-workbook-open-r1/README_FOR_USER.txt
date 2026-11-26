PCE Microsoft Excel 原生验证

只需普通双击同目录的 RUN_EXCEL_GOLDEN_VALIDATION.cmd。
不需要管理员权限，不输入命令、不选文件、不填写路径，不修改任何系统设置。
请保留此文件夹的位置及现有 scripts/excel_parity、docs/evidence/excel_formula_parity 文件。

程序会显示中文进度。计算期间无需操作 Excel，也不需要关闭你已打开的 Excel。
它只创建自己的 Excel 实例，仅打开隔离副本；禁用宏、事件、链接更新，不保存工作簿。
原始 Excel 在运行前后都核对 SHA-256。不会连接或写入 PCE 业务数据库。

结果自动保存在本文件夹 runs 下的新运行目录。
固定输出为 NATIVE_EXCEL_RUN.json、EXCEL_NATIVE_GOLDEN.json、DIFFERENTIAL_RESULTS.json、
SESSION_DIAGNOSTIC.json、RUN_LOG.txt、RUN_MANIFEST.json。保留这些文件即可，下一轮 Codex 会读取。
程序结束后窗口约 15 秒自动关闭；无需按键。结果路径同时写入 LAST_RUN.txt。

PASS 只表示本次 112 个完整公式族的 280 个冻结案例输出均通过原生差分。
REVIEW_REQUIRED 表示原生结果已经留存，仍有差异或损坏依赖，由 Codex 先分析技术问题。
BLOCKED 表示不能完成原生计算或证据保护/完整性检查；诊断自动保存，不要修改 DCOM 或注册表。
程序包预检通过不等于 Excel 原生验证通过，也不等于业务人工验收通过。

本包复用冻结的 163 个公式族、112 个函数和 722 个案例定义，不重新生成公式清单。
首批选择其中 112 个完整公式族对应的 280 个单元/边界案例；其余 442 个案例暂不执行。
51 个直接损坏公式族不进入本批，不阻断完整公式族；完整公式的损坏依赖单独标记。
单纯数值不一致先标记 UNCLASSIFIED_DIFFERENCE，由 Codex 追踪；不会直接要求你裁决业务。
生产写入、Migration、公式恢复、业务规则正式化以及后续验证层级均未启动。

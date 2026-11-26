半成品 Schema 用户会话隔离演练环境

当前状态：READY_FOR_USER_AUTHORIZED_REHEARSAL

用途：
1. 从 backend\db.sqlite3 实时复制新的只读基线副本；
2. 仅在副本上应用 pde 0024、0025、0026、0027；
3. 启动隔离 Backend 127.0.0.1:8001；
4. 启动隔离 Frontend 127.0.0.1:5183；
5. 不停止、不占用现有 8000 / 5173 服务。

只有在 REHEARSAL_MANIFEST.json 的 packageStatus 精确等于
READY_FOR_USER_AUTHORIZED_REHEARSAL、PACKAGE_STATUS_CONTRACT.json 有效且 HASH_LOCK.json
完整匹配时，START_SCHEMA_REHEARSAL.cmd 才能进入隔离演练。包状态只表示等待明确用户授权，
不会自行启动；每次演练仍须具有独立的用户授权。

正式放行后，用户操作只有：普通双击 START_SCHEMA_REHEARSAL.cmd。
停止时普通双击 STOP_SCHEMA_REHEARSAL.cmd；每个 owned process 会记录非空绝对 executable、
PID、parent PID、command line、start time、run owner、host、working directory 与 listener port。
Manifest 写入后立即 round-trip parse/schema validation。STOP 会先校验整份 Manifest，再要求
PID、启动时间、可执行文件和端口 ownership 全部匹配；无效 metadata 会报告
RUN_MANIFEST_PROCESS_IDENTITY_INVALID，并且不会扩大清理范围。

本包不执行生产 Migration，不写生产数据库，不创建正式业务事实。

Python 运行时使用本机 Codex 随附解释器，并显式加载项目 venv 的依赖目录；
预检会同时核验两者存在且可完成 Django 导入。

Launcher 使用 Windows PowerShell 5.1 系统自带的 System.Net.Http 程序集。共享 bootstrap
会在进程启动和预检时 fail-closed 验证程序集加载、HttpClient 类型解析与真实实例化；
不会安装全局组件，也不会把 Framework DLL 复制进包。

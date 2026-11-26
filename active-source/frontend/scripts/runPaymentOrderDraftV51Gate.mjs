import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.51'
const CHECKPOINT = 'payment_order_draft_reviewed_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(frontend, '..', 'backend')
const database = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(backend, 'db.sqlite3')
const resultRoot = path.join(frontend, 'test-results', 'payment-order-draft-v51')
const checkpointRoot = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const python = process.env.PCE_PYTHON_EXECUTABLE
  || 'C:\\Users\\DAODA\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe'
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const developmentHashBefore = digest(developmentDatabase)
const persistentHashAtRunnerStart = digest(database)
const protectedIds = [
  'payment_order_prepare_validated_ready',
  'payment_order_prepare_standard_list_ready',
  'pce_web_acceptance_v11_strict_pages_ready',
]
const coreNames = ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const checkpointHashes = id => Object.fromEntries(coreNames.map(name => [
  name,
  digest(path.join(checkpointRoot, id, name)),
]))
const protectedBefore = Object.fromEntries(protectedIds.map(id => [id, checkpointHashes(id)]))
const env = {
  ...process.env,
  PYTHONUTF8: '1',
  PYTHONPATH: path.join(backend, 'venv', 'Lib', 'site-packages'),
  DJANGO_SETTINGS_MODULE: 'pce_backend.canary_demo_settings',
  PCE_CANARY_DATABASE_PATH: database,
}
const steps = []
const run = (label, executable, args, options = {}) => {
  console.log(`\n[${VERSION}] ${label}`)
  const npm = process.platform === 'win32' && executable === 'npm.cmd'
  execFileSync(
    npm ? (process.env.ComSpec || 'C:\\Windows\\System32\\cmd.exe') : executable,
    npm ? ['/d', '/s', '/c', ['npm.cmd', ...args].join(' ')] : args,
    { cwd: options.cwd || frontend, env: options.env || process.env, stdio: 'inherit' },
  )
  steps.push({ label, result: 'passed' })
}

console.log(`当前版本：${VERSION}\n正式付款单草稿服务端持久化、最终草稿复核与正式付款单放行闭环 Runner 启动`)
for (const id of protectedIds) {
  const manifest = JSON.parse(fs.readFileSync(path.join(checkpointRoot, id, 'manifest.json'), 'utf8'))
  if (manifest.result !== 'passed' || manifest.immutable !== true) throw new Error(`Prerequisite checkpoint failed: ${id}`)
}
steps.push({ label: '输入检查点不可变基线', result: 'passed' })
run('changed-only 页面门禁', 'npm.cmd', ['run', 'gate:web-acceptance:changed'])
run('Migration', python, ['manage.py', 'migrate', 'payment_order_draft', '--noinput'], { cwd: backend, env })
run('持久金丝雀 ensure', python, ['manage.py', 'ensure_payment_order_draft_canary'], { cwd: backend, env })
const stableHash = digest(database)
run('重复 ensure', python, ['manage.py', 'ensure_payment_order_draft_canary'], { cwd: backend, env })
if (digest(database) !== stableHash) throw new Error('Repeated V51 ensure changed persistent database')
fs.mkdirSync(resultRoot, { recursive: true })
run('服务端报告与 A-Z 矩阵', python, ['manage.py', 'report_payment_order_draft_v51', '--output-dir', resultRoot], { cwd: backend, env })

const clone = path.join(os.tmpdir(), `pce-v51-regression-${process.pid}.sqlite3`)
fs.copyFileSync(database, clone)
const cloneEnv = { ...env, PCE_CANARY_DATABASE_PATH: clone }
run('隔离克隆硬约束与幂等恢复', python, ['manage.py', 'verify_payment_order_draft_constraints'], { cwd: backend, env: cloneEnv })
fs.rmSync(clone)
if (digest(database) !== stableHash) throw new Error('Regression clone gate modified persistent database')
run('静态及运行时守卫', 'npm.cmd', ['run', 'verify:payment-order-draft:v51-guards'])
run('真实 Chrome 页面及十二页回归', 'npm.cmd', ['run', 'gate:payment-order-draft:v51-page'])
if (digest(database) !== stableHash) throw new Error('Browser acceptance modified persistent database')
run('Django check', python, ['manage.py', 'check'], { cwd: backend, env })
run('Python compileall', python, ['-m', 'compileall', '-q', 'payment_order_draft'], { cwd: backend, env })
run('完整 Vite 生产构建', 'npm.cmd', ['run', 'build'])
if (digest(database) !== stableHash) throw new Error('Build gate modified persistent database')
run('报告、检查点与外部归档', 'npm.cmd', ['run', 'finalize:payment-order-draft:v51'])
run('跨进程检查点恢复', 'npm.cmd', ['run', 'verify:pce-golden-checkpoint-restore', '--', CHECKPOINT])
if (digest(database) !== stableHash) throw new Error('Checkpoint recovery modified persistent database')
if (digest(developmentDatabase) !== developmentHashBefore) throw new Error('Development database changed')
const protectedAfter = Object.fromEntries(protectedIds.map(id => [id, checkpointHashes(id)]))
if (JSON.stringify(protectedBefore) !== JSON.stringify(protectedAfter)) throw new Error('V51 modified a protected input checkpoint')
console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  runnerVersion: VERSION,
  checkpointVersion: VERSION,
  checkpointId: CHECKPOINT,
  steps,
  persistentDatabaseHashAtRunnerStart: persistentHashAtRunnerStart,
  persistentDatabaseStableHash: stableHash,
  persistentDatabaseSha256: digest(database),
  developmentDatabaseSha256: digest(developmentDatabase),
  protectedInputCheckpointsImmutable: true,
  productionRolloutEnabled: false,
  productionUserDataWritten: false,
  nextModuleObjectCreated: false,
  formalPaymentOrderCreated: false,
  formalPaymentInstructionCreated: false,
  paymentExecuted: false,
}, null, 2))

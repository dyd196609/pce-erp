import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.50'
const CHECKPOINT = 'payment_order_prepare_validated_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(frontend, '..', 'backend')
const database = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(backend, 'db.sqlite3')
const checkpointRoot = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const python = process.env.PCE_PYTHON_EXECUTABLE
  || 'C:\\Users\\DAODA\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe'
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const developmentHashBefore = digest(developmentDatabase)
const protectedIds = [
  'payment_instruction_prepare_validated_ready',
  'payment_instruction_prepare_observability_ready',
  'payment_request_approved_ready',
]
const coreNames = ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const inputHashesBefore = Object.fromEntries(protectedIds.map(id => [
  id,
  Object.fromEntries(coreNames.map(name => [name, digest(path.join(checkpointRoot, id, name))])),
]))
const env = {
  ...process.env, PYTHONUTF8: '1',
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

console.log(`当前版本：${VERSION}\n正式付款单预备服务端持久化、资金与签署能力校验及下一阶段放行闭环 Runner 启动`)
for (const id of protectedIds) {
  const manifest = JSON.parse(fs.readFileSync(path.join(checkpointRoot, id, 'manifest.json'), 'utf8'))
  if (manifest.result !== 'passed' || manifest.immutable !== true) throw new Error(`Prerequisite checkpoint failed: ${id}`)
}
steps.push({ label: '前置检查点', result: 'passed' })
run('前置检查点恢复', 'npm.cmd', ['run', 'verify:pce-golden-checkpoint-restore', '--', 'payment_instruction_prepare_observability_ready'])
run('Migration', python, ['manage.py', 'migrate', 'payment_order_prepare', '--noinput'], { cwd: backend, env })
run('持久金丝雀 ensure', python, ['manage.py', 'ensure_payment_order_prepare_canary'], { cwd: backend, env })
const databaseHashAfterFirstEnsure = digest(database)
run('重复 ensure', python, ['manage.py', 'ensure_payment_order_prepare_canary'], { cwd: backend, env })
if (digest(database) !== databaseHashAfterFirstEnsure) throw new Error('Repeated V50 ensure changed persistent database')
run('服务端报告', python, ['manage.py', 'report_payment_order_prepare_v50', '--output-dir', path.join(frontend, 'test-results', 'payment-order-prepare-v50')], { cwd: backend, env })
run('隔离故障矩阵与硬约束', 'npm.cmd', ['run', 'verify:payment-order-prepare:v50-fault-matrix'])
run('静态与运行时守卫', 'npm.cmd', ['run', 'verify:payment-order-prepare:v50-guards'])
run('Playwright 十一页验收', 'npm.cmd', ['run', 'gate:payment-order-prepare:v50-page'])
run('Django check', python, ['manage.py', 'check'], { cwd: backend, env })
run('Python compileall', python, ['-m', 'compileall', '-q', 'payment_order_prepare'], { cwd: backend, env })
run('完整生产构建', 'npm.cmd', ['run', 'build'])
run('报告与检查点', 'npm.cmd', ['run', 'finalize:payment-order-prepare:v50'])
run('跨进程检查点恢复', 'npm.cmd', ['run', 'verify:pce-golden-checkpoint-restore', '--', CHECKPOINT])
if (digest(developmentDatabase) !== developmentHashBefore) throw new Error('Development database changed')
const inputHashesAfter = Object.fromEntries(protectedIds.map(id => [
  id,
  Object.fromEntries(coreNames.map(name => [name, digest(path.join(checkpointRoot, id, name))])),
]))
if (JSON.stringify(inputHashesBefore) !== JSON.stringify(inputHashesAfter)) throw new Error('V50 modified a protected input checkpoint')
console.log(JSON.stringify({
  result: 'passed', version: VERSION, runnerVersion: VERSION,
  checkpointVersion: VERSION, checkpointId: CHECKPOINT, steps,
  persistentDatabaseSha256: digest(database),
  developmentDatabaseSha256: digest(developmentDatabase),
  protectedInputCheckpointsImmutable: true,
  productionRolloutEnabled: false, productionUserDataWritten: false,
  nextModuleObjectCreated: false, formalPaymentOrderCreated: false,
  formalPaymentInstructionCreated: false, paymentExecuted: false,
}, null, 2))

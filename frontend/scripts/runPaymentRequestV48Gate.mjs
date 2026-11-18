import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.48'
const CHECKPOINT = 'payment_request_approved_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const source = path.resolve(frontend, '..')
const backend = path.join(source, 'backend')
const database = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(backend, 'db.sqlite3')
const checkpointRoot = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const python = process.env.PCE_PYTHON_EXECUTABLE
  || 'C:\\Users\\DAODA\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe'
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const developmentHashBefore = digest(developmentDatabase)
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

console.log(`${VERSION}\n付款申请审批闭环统一门禁 Runner 启动`)
for (const id of [
  'payment_request_prepare_validated_ready',
  'payment_request_prepare_page_semantics_consistent_ready',
  'payment_request_prepare_page_structure_consistent_ready',
]) {
  const manifest = JSON.parse(fs.readFileSync(path.join(checkpointRoot, id, 'manifest.json'), 'utf8'))
  if (manifest.result !== 'passed' || manifest.immutable !== true) {
    throw new Error(`prerequisite checkpoint failed: ${id}`)
  }
}
steps.push({ label: '前置检查点', result: 'passed' })
run('Migration', python, ['manage.py', 'migrate'], { cwd: backend, env })
const databaseHashBeforeEnsure = digest(database)
run('持久金丝雀 ensure', python, ['manage.py', 'ensure_payment_request_canary'], { cwd: backend, env })
run('重复 ensure', python, ['manage.py', 'ensure_payment_request_canary'], { cwd: backend, env })
if (digest(database) !== databaseHashBeforeEnsure) throw new Error('repeated ensure changed persistent database')
run('审批及故障矩阵报告', python, [
  'manage.py', 'report_payment_request_v48',
  '--output-dir', path.join(frontend, 'test-results', 'payment-request-v48'),
], { cwd: backend, env })
run('参数化故障注入矩阵', 'npm.cmd', ['run', 'verify:payment-request:v48-fault-matrix'])
run('静态守卫', 'npm.cmd', ['run', 'verify:payment-request:v48-guards'])
run('Playwright 九页与服务端读模型', 'npm.cmd', ['run', 'gate:payment-request:v48-page'])
run('Django check', python, ['manage.py', 'check'], { cwd: backend, env })
run('Python compileall', python, ['-m', 'compileall', '-q', 'payment_request', 'workflow_runtime'], { cwd: backend, env })
run('完整生产构建', 'npm.cmd', ['run', 'build'])
run('报告与检查点', 'npm.cmd', ['run', 'finalize:payment-request:v48'])
run('跨进程检查点恢复', 'npm.cmd', ['run', 'verify:pce-golden-checkpoint-restore', '--', CHECKPOINT])
if (digest(developmentDatabase) !== developmentHashBefore) throw new Error('development database changed')

console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  runnerVersion: VERSION,
  checkpointVersion: VERSION,
  checkpointId: CHECKPOINT,
  steps,
  persistentDatabaseSha256: digest(database),
  developmentDatabaseSha256: digest(developmentDatabase),
  productionRolloutEnabled: false,
  productionUserDataWritten: false,
  paymentInstructionPrepareCreated: false,
}, null, 2))

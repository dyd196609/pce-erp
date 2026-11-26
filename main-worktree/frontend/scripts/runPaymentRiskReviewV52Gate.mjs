import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.52'
const CHECKPOINT = 'payment_risk_review_validated_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(frontend, '..', 'backend')
const persistentDatabase = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(backend, 'db.sqlite3')
const expectedPersistentHash = 'ae801464c27d4ff687aa1a35327790a7e9186de433f47c99563b26b85ce757a6'
const expectedDevelopmentHash = 'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'
const checkpointBase = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const protectedIds = [
  'payment_order_prepare_validated_ready',
  'payment_order_prepare_standard_list_ready',
  'payment_order_draft_reviewed_ready',
  'payment_order_draft_fact_consistency_ready',
]
const coreNames = ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const checkpointHashes = id => Object.fromEntries(coreNames.map(name => [name, digest(path.join(checkpointBase, id, name))]))
const protectedBefore = Object.fromEntries(protectedIds.map(id => [id, checkpointHashes(id)]))
const assertProtected = () => {
  if (digest(persistentDatabase) !== expectedPersistentHash) throw new Error('V52 persistent database drifted')
  if (digest(developmentDatabase) !== expectedDevelopmentHash) throw new Error('Development database changed')
  const after = Object.fromEntries(protectedIds.map(id => [id, checkpointHashes(id)]))
  if (JSON.stringify(after) !== JSON.stringify(protectedBefore)) throw new Error('Protected V50/V51 checkpoint changed')
}
const python = process.env.PCE_PYTHON_EXECUTABLE
  || 'C:\\Users\\DAODA\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe'
const env = {
  ...process.env,
  PYTHONUTF8: '1',
  PYTHONPATH: path.join(backend, 'venv', 'Lib', 'site-packages'),
  DJANGO_SETTINGS_MODULE: 'pce_backend.canary_demo_settings',
  PCE_CANARY_DATABASE_PATH: persistentDatabase,
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
  assertProtected()
  steps.push({ label, result: 'passed' })
}

console.log(`当前版本：${VERSION}`)
assertProtected()
run('迁移状态只读核验', python, ['manage.py', 'showmigrations', 'payment_risk_review'], { cwd: backend, env })
run('持久金丝雀幂等确认', python, ['manage.py', 'ensure_payment_risk_review_canary'], { cwd: backend, env })
run('服务端报告与阻断矩阵', python, [
  'manage.py', 'report_payment_risk_review_v52',
  '--output-dir', path.join(frontend, 'test-results', 'payment-risk-review-v52'),
], { cwd: backend, env })
const clone = path.join(backend, 'canary-data', `v52-regression-${process.pid}.sqlite3`)
if (fs.existsSync(clone)) throw new Error(`Unexpected regression clone: ${clone}`)
fs.copyFileSync(persistentDatabase, clone)
try {
  run(
    '克隆库唯一约束与幂等验证',
    python,
    ['manage.py', 'verify_payment_risk_review_constraints'],
    { cwd: backend, env: { ...env, PCE_CANARY_DATABASE_PATH: clone } },
  )
} finally {
  if (fs.existsSync(clone)) fs.unlinkSync(clone)
}
run('后端契约测试', python, ['manage.py', 'test', 'payment_risk_review', '--verbosity', '2'], {
  cwd: backend,
  env: { ...env, DJANGO_SETTINGS_MODULE: 'pce_backend.test_settings', PCE_CANARY_DATABASE_PATH: '' },
})
run('V52 静态及运行时守卫', 'npm.cmd', ['run', 'verify:payment-risk-review:v52-guards'])
run('真实 Chrome 页面验收', 'npm.cmd', ['run', 'gate:payment-risk-review:v52-page'])
run('Django 系统检查', python, ['manage.py', 'check'], { cwd: backend, env })
run('完整 Vite 生产构建', 'npm.cmd', ['run', 'build'])
run('报告、检查点与外部归档', 'npm.cmd', ['run', 'finalize:payment-risk-review:v52'])
run('新检查点跨进程恢复', 'npm.cmd', ['run', 'verify:pce-golden-checkpoint-restore', '--', CHECKPOINT])
console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT,
  steps,
  persistentDatabaseSha256: digest(persistentDatabase),
  developmentDatabaseSha256: digest(developmentDatabase),
  protectedCheckpointsImmutable: true,
  productionUserDataWritten: false,
  formalPaymentOrderCreated: false,
  paymentExecuted: false,
}, null, 2))


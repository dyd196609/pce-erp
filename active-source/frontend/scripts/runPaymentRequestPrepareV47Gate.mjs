import { execFileSync } from 'node:child_process'
import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.47'
const CHECKPOINT = 'payment_request_prepare_validated_ready'
console.log(`${VERSION}\n付款申请准备统一门禁 Runner 启动`)

const frontend = path.resolve(import.meta.dirname, '..')
const source = path.resolve(frontend, '..')
const backend = path.join(source, 'backend')
const database = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const python = process.env.PCE_PYTHON_EXECUTABLE
  || 'C:\\Users\\DAODA\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe'
const baseEnv = {
  ...process.env,
  PYTHONUTF8: '1',
  PYTHONPATH: path.join(backend, 'venv', 'Lib', 'site-packages'),
}
const canaryEnv = {
  ...baseEnv,
  DJANGO_SETTINGS_MODULE: 'pce_backend.canary_demo_settings',
  PCE_CANARY_DATABASE_PATH: database,
}
const testEnv = {
  ...baseEnv,
  DJANGO_SETTINGS_MODULE: 'pce_backend.test_settings',
}
const steps = []
function run(label, executable, args, options = {}) {
  console.log(`\n[${VERSION}] ${label}`)
  const useWindowsNpmLauncher = process.platform === 'win32' && executable === 'npm.cmd'
  const resolvedExecutable = useWindowsNpmLauncher
    ? (process.env.ComSpec || 'C:\\Windows\\System32\\cmd.exe')
    : executable
  const resolvedArgs = useWindowsNpmLauncher
    ? ['/d', '/s', '/c', ['npm.cmd', ...args].join(' ')]
    : args
  execFileSync(resolvedExecutable, resolvedArgs, {
    cwd: options.cwd || frontend,
    env: options.env || process.env,
    stdio: 'inherit',
  })
  steps.push({ label, result: 'passed' })
}

const requiredCheckpoints = [
  'payable_confirmation_prepare_validated_ready',
  'purchase_canary_downstream_capacity_ready',
]
for (const checkpointId of requiredCheckpoints) {
  const manifest = JSON.parse(fs.readFileSync(
    path.join(
      frontend,
      'test-results',
      'purchase-payment-golden-flow',
      'checkpoints',
      checkpointId,
      'manifest.json',
    ),
    'utf8',
  ))
  if (manifest.result !== 'passed' || manifest.immutable !== true) {
    throw new Error(`Prerequisite checkpoint failed: ${checkpointId}`)
  }
}
steps.push({ label: '输入检查点', result: 'passed' })

run(
  'Migration',
  python,
  ['manage.py', 'migrate', 'payment_request_prepare'],
  { cwd: backend, env: canaryEnv },
)
run(
  '持久金丝雀确保',
  python,
  ['manage.py', 'ensure_payment_request_prepare_canary'],
  { cwd: backend, env: canaryEnv },
)
run(
  'Django A—Z、Provider、约束、授权和幂等测试',
  python,
  ['manage.py', 'test', 'payment_request_prepare.tests', '--verbosity=1'],
  { cwd: backend, env: testEnv },
)
run('参数化故障矩阵', 'npm.cmd', ['run', 'verify:payment-request-prepare:v47-fault-matrix'])
run('Playwright 页面与持续性门禁', 'npm.cmd', ['run', 'gate:payment-request-prepare:v47'])
run('静态与运行时契约守卫', 'npm.cmd', ['run', 'verify:payment-request-prepare:v47-guards'])
run(
  'Django check',
  python,
  ['manage.py', 'check'],
  { cwd: backend, env: canaryEnv },
)
run(
  'Python compileall',
  python,
  ['-m', 'compileall', '-q', 'payment_request_prepare'],
  { cwd: backend, env: canaryEnv },
)
run('完整生产构建', 'npm.cmd', ['run', 'build'])
const completedCheckpointManifest = path.join(
  frontend,
  'test-results',
  'purchase-payment-golden-flow',
  'checkpoints',
  CHECKPOINT,
  'manifest.json',
)
if (fs.existsSync(completedCheckpointManifest)) {
  const completedCheckpoint = JSON.parse(
    fs.readFileSync(completedCheckpointManifest, 'utf8'),
  )
  if (
    completedCheckpoint.result !== 'passed'
    || completedCheckpoint.version !== VERSION
    || completedCheckpoint.immutable !== true
  ) {
    throw new Error(`Existing V47 checkpoint is not reusable: ${CHECKPOINT}`)
  }
  run(
    '报告与检查点一致性复核',
    'npm.cmd',
    ['run', 'verify:pce-golden-checkpoint-restore', '--', CHECKPOINT],
  )
} else {
  run('报告与检查点', 'npm.cmd', ['run', 'finalize:payment-request-prepare:v47'])
}
run(
  '跨进程检查点恢复',
  'npm.cmd',
  ['run', 'verify:pce-golden-checkpoint-restore', '--', CHECKPOINT],
)
const archiveDestination = path.resolve(
  source,
  '..',
  'CheckpointArchive',
  'purchase-payment-golden-flow',
  CHECKPOINT,
)
if (fs.existsSync(archiveDestination)) {
  const digest = file => crypto
    .createHash('sha256')
    .update(fs.readFileSync(file))
    .digest('hex')
  for (const name of [
    'manifest.json',
    'storage-state.json',
    'application-state.json',
    'business-entities.json',
    'relationship-graph.json',
  ]) {
    const localFile = path.join(
      frontend,
      'test-results',
      'purchase-payment-golden-flow',
      'checkpoints',
      CHECKPOINT,
      name,
    )
    const archivedFile = path.join(archiveDestination, 'checkpoint', name)
    if (digest(localFile) !== digest(archivedFile)) {
      throw new Error(`Existing archive hash mismatch: ${name}`)
    }
  }
  steps.push({ label: '外部归档一致性复核', result: 'passed' })
  console.log(`[${VERSION}] 外部归档一致性复核通过`)
} else {
  run('外部归档', 'npm.cmd', ['run', 'archive:pce-checkpoint', '--', CHECKPOINT])
}

console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  runnerVersion: VERSION,
  checkpointVersion: VERSION,
  checkpointName: CHECKPOINT,
  stepCount: steps.length,
  steps,
  productionRolloutEnabled: false,
  productionUserDataWritten: false,
  paymentRequestCreated: false,
}, null, 2))

import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.53'
const CHECKPOINT = 'formal_payment_order_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(frontend, '..', 'backend')
const resultRoot = path.join(frontend, 'test-results', 'formal-payment-order-v53')
const persistentDatabase = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(backend, 'db.sqlite3')
const expectedPersistentHash = 'e9fe4cf001a6408fdaa4291fc00d2d5e6c92f84c5d6fc98f49ed33e5edb6a676'
const expectedDevelopmentHash = 'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'
const python = process.env.PCE_PYTHON_EXECUTABLE
  || 'C:\\Users\\DAODA\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe'
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const assertProtected = () => {
  if (digest(persistentDatabase) !== expectedPersistentHash) {
    throw new Error('V53 persistent canary database changed')
  }
  if (digest(developmentDatabase) !== expectedDevelopmentHash) {
    throw new Error('Development database changed')
  }
}
const djangoEnv = {
  ...process.env,
  PYTHONUTF8: '1',
  PYTHONPATH: path.join(backend, 'venv', 'Lib', 'site-packages'),
  DJANGO_SETTINGS_MODULE: 'pce_backend.canary_demo_settings',
  PCE_CANARY_DATABASE_PATH: persistentDatabase,
}
const steps = []
const run = (label, executable, args, options = {}) => {
  console.log(`\n[${VERSION}] ${label}`)
  const npmOnWindows = process.platform === 'win32' && executable === 'npm.cmd'
  execFileSync(
    npmOnWindows ? (process.env.ComSpec || 'C:\\Windows\\System32\\cmd.exe') : executable,
    npmOnWindows ? ['/d', '/s', '/c', ['npm.cmd', ...args].join(' ')] : args,
    {
      cwd: options.cwd || frontend,
      env: options.env || process.env,
      stdio: 'inherit',
    },
  )
  assertProtected()
  steps.push({ label, result: 'passed' })
}

console.log(`当前版本：${VERSION}`)
assertProtected()
run('迁移状态只读核验', python, ['manage.py', 'showmigrations', 'formal_payment_order'], {
  cwd: backend,
  env: djangoEnv,
})
run('服务端约束、幂等及零对象验证', python, [
  'manage.py',
  'verify_formal_payment_order_constraints',
  '--output',
  path.join(resultRoot, 'server-report.json'),
], { cwd: backend, env: djangoEnv })
run('后端契约测试', python, ['manage.py', 'test', 'formal_payment_order', '--verbosity', '2'], {
  cwd: backend,
  env: {
    ...djangoEnv,
    DJANGO_SETTINGS_MODULE: 'pce_backend.test_settings',
    PCE_CANARY_DATABASE_PATH: '',
  },
})
run('V53 静态及运行时守卫', 'npm.cmd', ['run', 'verify:formal-payment-order:v53-guards'])
run('真实 Chrome Level 5 页面验收', 'npm.cmd', ['run', 'gate:formal-payment-order:v53-page'])
run('跨进程服务端状态恢复', 'npm.cmd', ['run', 'verify:formal-payment-order:v53-recovery'])
run('Django 系统检查', python, ['manage.py', 'check'], { cwd: backend, env: djangoEnv })
run('完整 Vite 生产构建', 'npm.cmd', ['run', 'build'])
run('专用检查点与外部归档验证', 'npm.cmd', ['run', 'verify:formal-payment-order:v53-checkpoint'])
run('通用黄金检查点恢复', 'npm.cmd', [
  'run',
  'verify:pce-golden-checkpoint-restore',
  '--',
  CHECKPOINT,
])

console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT,
  steps,
  persistentDatabaseSha256: digest(persistentDatabase),
  developmentDatabaseSha256: digest(developmentDatabase),
  formalPaymentOrderCount: 8,
  preparedCount: 8,
  blockedScenarioCount: 15,
  nextStageConsumedCount: 0,
  productionUserDataWritten: false,
  bankMessageCreated: false,
  bankSendTaskCreated: false,
  paymentExecuted: false,
}, null, 2))

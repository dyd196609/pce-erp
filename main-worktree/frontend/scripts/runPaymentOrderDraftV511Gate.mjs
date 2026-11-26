import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.51.1'
const CHECKPOINT = 'payment_order_draft_fact_consistency_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(frontend, '..', 'backend')
const persistentDatabase = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(backend, 'db.sqlite3')
const priorCheckpoint = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints', 'payment_order_draft_reviewed_ready')
const expectedPersistentHash = '150221238105f9451cb80a03ee748eed0732a443137c6bbc3553553859421a17'
const expectedDevelopmentHash = 'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'
const expectedPriorHashes = {
  'manifest.json': '0f77c69daf722d960a3121e04291e7abd1ea189d50f0803df1af5b2f79d48a13',
  'storage-state.json': '8fc36561d0bc7ff473395e7a810739c1228ffe8df47449b5a53f1f48fa88a242',
  'application-state.json': '2089484bb1ac063fc63e20f907d50e067e24b839840ee9d45a612dd3856ba4f2',
  'business-entities.json': '2ec9637d55f15cf42dfe8e329225e30899014788076a1c8bbef031f9b4fc4809',
  'relationship-graph.json': 'ccbd404a1211110c635e8c9ab8b8471f1b70d38e866b70f9cec6925cde0e8540',
}
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const priorHashes = () => Object.fromEntries(Object.keys(expectedPriorHashes).map(name => [name, digest(path.join(priorCheckpoint, name))]))
const assertProtected = () => {
  if (digest(persistentDatabase) !== expectedPersistentHash) throw new Error('Persistent canary database changed')
  if (digest(developmentDatabase) !== expectedDevelopmentHash) throw new Error('Development database changed')
  if (JSON.stringify(priorHashes()) !== JSON.stringify(expectedPriorHashes)) throw new Error('V51 checkpoint changed')
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
steps.push({ label: '数据库与 V51 检查点只读基线', result: 'passed' })
run('静态及运行时守卫', 'npm.cmd', ['run', 'verify:payment-order-draft:v51-guards'])
run('真实 Chrome 页面、诊断一致性及十二页回归', 'npm.cmd', ['run', 'gate:payment-order-draft:v51-page'])
run('Django 系统检查', python, ['manage.py', 'check'], { cwd: backend, env })
run('完整 Vite 生产构建', 'npm.cmd', ['run', 'build'])
run('报告、检查点与外部归档', 'npm.cmd', ['run', 'finalize:payment-order-draft:v511'])
run('新检查点恢复', 'npm.cmd', ['run', 'verify:pce-golden-checkpoint-restore', '--', CHECKPOINT])
console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT,
  steps,
  persistentDatabaseSha256: digest(persistentDatabase),
  developmentDatabaseSha256: digest(developmentDatabase),
  priorCheckpointHashes: priorHashes(),
  persistentDatabaseUnchanged: true,
  developmentDatabaseUnchanged: true,
  productionUserDataWritten: false,
  nextModuleObjectCreated: false,
}, null, 2))

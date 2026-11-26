import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { PAYMENT_REQUEST_PREPARE_VERSION } from '../src/meta/runtime/paymentRequestPrepareRuntime.js'

const VERSION = PAYMENT_REQUEST_PREPARE_VERSION
const CHECKPOINT = 'payment_request_prepare_page_semantics_consistent_ready'
console.log(`${VERSION}\n付款申请准备页面语义统一门禁 Runner 启动`)
const frontend = path.resolve(import.meta.dirname, '..')
const source = path.resolve(frontend, '..')
const database = path.join(source, 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(source, 'backend', 'db.sqlite3')
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const before = { persistent: digest(database), development: digest(developmentDatabase) }
const run = (label, args) => {
  console.log(`\n[${VERSION}] ${label}`)
  execFileSync(process.env.ComSpec || 'C:\\Windows\\System32\\cmd.exe', ['/d', '/s', '/c', ['npm.cmd', ...args].join(' ')], {
    cwd: frontend,
    stdio: 'inherit',
  })
}
run('静态守卫', ['run', 'verify:payment-request-prepare:v471-guards'])
run('Chrome 全页 Playwright', ['run', 'gate:payment-request-prepare:v471'])
run('完整生产构建', ['run', 'build'])
const manifest = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints', CHECKPOINT, 'manifest.json')
if (fs.existsSync(manifest)) {
  run('检查点恢复', ['run', 'verify:pce-golden-checkpoint-restore', '--', CHECKPOINT])
} else {
  run('报告与检查点', ['run', 'finalize:payment-request-prepare:v471'])
  run('检查点恢复', ['run', 'verify:pce-golden-checkpoint-restore', '--', CHECKPOINT])
}
const after = { persistent: digest(database), development: digest(developmentDatabase) }
if (JSON.stringify(before) !== JSON.stringify(after)) {
  throw new Error(`V47.1 zero-write database hash mismatch: ${JSON.stringify({ before, after })}`)
}
run('外部归档', ['run', 'archive:pce-checkpoint', '--', CHECKPOINT])
console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT,
  persistentDatabaseUnchanged: true,
  developmentDatabaseUnchanged: true,
  productionUserDataWritten: false,
}, null, 2))

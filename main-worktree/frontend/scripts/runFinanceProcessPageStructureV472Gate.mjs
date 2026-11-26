import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { FINANCE_PROCESS_STRUCTURE_VERSION } from '../src/meta/process/financeProcessPageRegistry.js'

const VERSION = FINANCE_PROCESS_STRUCTURE_VERSION
const CHECKPOINT = 'payment_request_prepare_page_structure_consistent_ready'
console.log(`${VERSION}\n付款申请准备统一页面结构 Runner 启动`)
const frontend = path.resolve(import.meta.dirname, '..')
const source = path.resolve(frontend, '..')
const persistent = path.join(source, 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const development = path.join(source, 'backend', 'db.sqlite3')
const checkpoint = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints', CHECKPOINT)
const archive = path.resolve(source, '..', 'CheckpointArchive', 'purchase-payment-golden-flow', CHECKPOINT)
const coreFiles = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const before = { persistent: sha256(persistent), development: sha256(development) }
const run = (label, args) => {
  console.log(`\n[${VERSION}] ${label}`)
  execFileSync(process.env.ComSpec || 'C:\\Windows\\System32\\cmd.exe', ['/d', '/s', '/c', ['npm.cmd', ...args].join(' ')], {
    cwd: frontend,
    stdio: 'inherit',
  })
}
run('公共结构静态与运行时守卫', ['run', 'verify:finance-process-structure:v472-guards'])
run('八页 Chrome 全页结构对比', ['run', 'gate:finance-process-structure:v472'])
run('完整生产构建', ['run', 'build'])
const manifest = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints', CHECKPOINT, 'manifest.json')
if (!fs.existsSync(manifest)) run('报告与检查点', ['run', 'finalize:finance-process-structure:v472'])
run('检查点恢复', ['run', 'verify:pce-golden-checkpoint-restore', '--', CHECKPOINT])
const after = { persistent: sha256(persistent), development: sha256(development) }
if (JSON.stringify(before) !== JSON.stringify(after)) throw new Error('V47.2 database hash changed')
if (!fs.existsSync(archive)) {
  run('外部归档', ['run', 'archive:pce-checkpoint', '--', CHECKPOINT])
} else {
  const archiveCheckpoint = path.join(archive, 'checkpoint')
  for (const file of coreFiles) {
    if (sha256(path.join(checkpoint, file)) !== sha256(path.join(archiveCheckpoint, file))) {
      throw new Error(`V47.2 archived checkpoint hash mismatch: ${file}`)
    }
  }
  console.log(`\n[${VERSION}] 外部归档已存在且五项核心哈希一致`)
}
console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT,
  persistentDatabaseUnchanged: true,
  developmentDatabaseUnchanged: true,
  productionUserDataWritten: false,
}, null, 2))

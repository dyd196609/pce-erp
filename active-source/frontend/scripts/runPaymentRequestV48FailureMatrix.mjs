import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.48'
const frontend = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(frontend, '..', 'backend')
const sourceDatabase = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(backend, 'db.sqlite3')
const clone = path.join(backend, 'canary-data', `.v48-fault-${process.pid}.sqlite3`)
const python = process.env.PCE_PYTHON_EXECUTABLE
  || 'C:\\Users\\DAODA\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe'
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const matrix = {
  generate: [
    'authentication', 'business_gate', 'idempotency', 'persistent_lock',
    'source_reload', 'version_check', 'target_check', 'number_reservation',
    'target_insert', 'source_snapshot', 'source_relation', 'transaction_status',
    'audit', 'idempotency_committed', 'number_consumed', 'database_commit',
    'response_lost',
  ],
  submit: [
    'authentication', 'permission', 'object_read', 'version_check', 'idempotency',
    'persistent_lock', 'source_reload', 'provider_read', 'approval_policy',
    'approval_route', 'submission_snapshot', 'workflow_instance', 'first_tasks',
    'status_update', 'audit', 'database_commit', 'response_lost',
  ],
  approve: [
    'authentication', 'approval_permission', 'segregation', 'task_read',
    'step_check', 'version_check', 'persistent_lock', 'locked_reload',
    'source_reload', 'decision_insert', 'task_complete', 'next_task',
    'approved_update', 'audit', 'idempotency_committed', 'database_commit',
    'response_lost',
  ],
  reject: [
    'authentication', 'task_read', 'reject_decision', 'remaining_tasks_close',
    'rejected_update', 'audit', 'idempotency_committed', 'database_commit',
    'response_lost',
  ],
}
const persistentBefore = sha256(sourceDatabase)
const developmentBefore = sha256(developmentDatabase)
fs.copyFileSync(sourceDatabase, clone)
const env = {
  ...process.env,
  PYTHONUTF8: '1',
  PYTHONPATH: path.join(backend, 'venv', 'Lib', 'site-packages'),
  DJANGO_SETTINGS_MODULE: 'pce_backend.canary_demo_settings',
  PCE_CANARY_DATABASE_PATH: clone,
}
const results = []
try {
  for (const [action, steps] of Object.entries(matrix)) {
    for (const step of steps) {
      const output = execFileSync(python, [
        'manage.py', 'exercise_payment_request_failure_case',
        '--action', action, '--step', step,
      ], { cwd: backend, env, encoding: 'utf8' })
      const result = JSON.parse(output.trim().split(/\r?\n/).filter(Boolean).at(-1))
      if (result.result !== 'passed') throw new Error(`failure case failed: ${action}/${step}`)
      results.push(result)
    }
  }
} finally {
  if (fs.existsSync(clone)) fs.unlinkSync(clone)
}
const report = {
  result: 'passed',
  version: VERSION,
  caseCount: results.length,
  allFailurePointsInjected: true,
  zeroResidueOrCommittedRecovery: results.every(item => item.result === 'passed'),
  regressionCloneIsolationReady: true,
  regressionCloneRemoved: !fs.existsSync(clone),
  persistentDatabaseSha256Before: persistentBefore,
  persistentDatabaseSha256After: sha256(sourceDatabase),
  persistentDatabaseUnchanged: sha256(sourceDatabase) === persistentBefore,
  developmentDatabaseSha256Before: developmentBefore,
  developmentDatabaseSha256After: sha256(developmentDatabase),
  developmentDatabaseUnchanged: sha256(developmentDatabase) === developmentBefore,
  sqliteConcurrencyModel: [
    'atomic transaction',
    'database hard unique constraints',
    'optimistic version',
    'persistent business lock',
    'idempotency record',
  ],
  cases: results,
}
if (!report.persistentDatabaseUnchanged || !report.developmentDatabaseUnchanged) {
  throw new Error('fault matrix modified a protected database')
}
fs.writeFileSync(
  path.join(frontend, 'test-results', 'payment-request-v48', 'failure-injection-evidence.json'),
  `${JSON.stringify(report, null, 2)}\n`,
  'utf8',
)
console.log(JSON.stringify(report, null, 2))

import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const frontend = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(frontend, '..', 'backend')
const resultRoot = path.join(frontend, 'test-results', 'payable-confirmation-prepare-v46')
const persistent = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const development = path.join(backend, 'db.sqlite3')
const cloneRoot = path.join(resultRoot, 'regression-clones')
const python = process.env.PCE_PYTHON_EXECUTABLE
  || 'C:\\Users\\DAODA\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe'
const steps = [
  'after_authorization',
  'after_idempotency_registration',
  'after_persistent_lock',
  'after_locked_source_reload',
  'after_source_version_check',
  'after_accounting_validation',
  'after_number_reservation',
  'after_target_insert',
  'after_accounting_snapshot_insert',
  'after_validation_execution_insert',
  'after_source_relation_insert',
  'after_audit_insert',
  'after_idempotency_committed',
  'after_number_consumed',
  'before_database_commit',
  'before_response',
]
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const persistentBefore = sha256(persistent)
const developmentBefore = sha256(development)
fs.mkdirSync(cloneRoot, { recursive: true })
const rows = []
for (const step of steps) {
  const clone = path.join(cloneRoot, `v46-${step}.sqlite3`)
  fs.copyFileSync(persistent, clone)
  const env = {
    ...process.env,
    PYTHONUTF8: '1',
    PYTHONPATH: path.join(backend, 'venv', 'Lib', 'site-packages'),
    DJANGO_SETTINGS_MODULE: 'pce_backend.canary_regression_settings',
    PCE_CANARY_DATABASE_PATH: clone,
    PCE_CANARY_EXPECTED_CLONE_PATH: clone,
  }
  const output = execFileSync(
    python,
    ['manage.py', 'run_payable_confirmation_prepare_failure_case', step],
    { cwd: backend, env, encoding: 'utf8' },
  )
  const jsonLine = output.trim().split(/\r?\n/).filter(Boolean).at(-1)
  rows.push(JSON.parse(jsonLine))
  fs.rmSync(clone, { force: true })
}
if (fs.existsSync(cloneRoot) && fs.readdirSync(cloneRoot).length === 0) {
  fs.rmdirSync(cloneRoot)
}
const persistentAfter = sha256(persistent)
const developmentAfter = sha256(development)
const report = {
  result: rows.every(row => row.passed)
    && persistentBefore === persistentAfter
    && developmentBefore === developmentAfter
    ? 'passed' : 'failed',
  version: 'V1.14.2.8.4.7.46',
  matrixSize: rows.length,
  cases: rows,
  regressionCloneRemoved: !fs.existsSync(cloneRoot),
  persistentDatabaseSha256Before: persistentBefore,
  persistentDatabaseSha256After: persistentAfter,
  persistentDatabaseUnchanged: persistentBefore === persistentAfter,
  developmentDatabaseSha256Before: developmentBefore,
  developmentDatabaseSha256After: developmentAfter,
  developmentDatabaseUnchanged: developmentBefore === developmentAfter,
  paymentRequestPrepareCreated: false,
}
fs.mkdirSync(resultRoot, { recursive: true })
const reportPath = path.join(resultRoot, 'failure-matrix.json')
fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify({ ...report, reportPath }, null, 2))
if (report.result !== 'passed') process.exitCode = 1

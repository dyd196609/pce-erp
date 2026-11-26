import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.47'
console.log(`${VERSION}\n付款申请准备参数化故障矩阵启动`)

const frontend = path.resolve(import.meta.dirname, '..')
const source = path.resolve(frontend, '..')
const backend = path.join(source, 'backend')
const resultRoot = path.join(frontend, 'test-results', 'payment-request-prepare-v47')
const cloneRoot = path.join(resultRoot, 'failure-clones')
const persistentDatabase = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(backend, 'db.sqlite3')
const python = process.env.PCE_PYTHON_EXECUTABLE
  || 'C:\\Users\\DAODA\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe'
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const generationSteps = [
  'after_authorization',
  'after_business_gate',
  'after_idempotency_registration',
  'after_persistent_lock',
  'after_source_reload',
  'after_version_check',
  'after_target_check',
  'after_number_reservation',
  'after_target_insert',
  'after_source_snapshot_insert',
  'after_source_relation_insert',
  'after_audit_insert',
  'after_idempotency_committed',
  'after_number_consumed',
  'before_database_commit',
  'before_response',
]
const saveSteps = [
  'after_authorization',
  'after_idempotency_registration',
  'after_persistent_lock',
  'after_prepare_reload',
  'after_provider_read',
  'after_version_check',
  'after_payment_data_snapshot_insert',
  'after_prepare_update',
  'after_audit_insert',
  'after_idempotency_committed',
  'before_database_commit',
  'before_response',
]
const validationSteps = [
  'after_authorization',
  'after_idempotency_registration',
  'after_persistent_lock',
  'after_prepare_reload',
  'after_payment_data_reload',
  'after_source_reload',
  'after_provider_read',
  'after_version_check',
  'after_validation_execution_insert',
  'after_issue_insert',
  'after_prepared_update',
  'after_audit_insert',
  'after_idempotency_committed',
  'before_database_commit',
  'before_response',
]
const cases = [
  ...generationSteps.map(failureStep => ({ action: 'generate', failureStep })),
  ...saveSteps.map(failureStep => ({ action: 'save', failureStep })),
  ...validationSteps.map(failureStep => ({ action: 'validate', failureStep })),
]
fs.mkdirSync(cloneRoot, { recursive: true })
const persistentHashBefore = sha256(persistentDatabase)
const developmentHashBefore = sha256(developmentDatabase)
const results = []
for (const [index, item] of cases.entries()) {
  const clone = path.join(
    cloneRoot,
    `${String(index + 1).padStart(2, '0')}-${item.action}-${item.failureStep}.sqlite3`,
  )
  fs.copyFileSync(persistentDatabase, clone)
  const env = {
    ...process.env,
    PYTHONUTF8: '1',
    PYTHONPATH: path.join(backend, 'venv', 'Lib', 'site-packages'),
    DJANGO_SETTINGS_MODULE: 'pce_backend.canary_regression_settings',
    PCE_CANARY_DATABASE_PATH: clone,
    PCE_CANARY_EXPECTED_CLONE_PATH: clone,
  }
  try {
    const output = execFileSync(
      python,
      ['manage.py', 'run_payment_request_prepare_failure_case', item.action, item.failureStep],
      { cwd: backend, env, encoding: 'utf8' },
    )
    const payload = JSON.parse(
      output.trim().split(/\r?\n/).filter(Boolean).at(-1),
    )
    results.push({ ...item, ...payload, cloneRemoved: true })
  } catch (error) {
    results.push({
      ...item,
      result: 'failed',
      error: String(error.stderr || error.stdout || error.message),
      cloneRemoved: true,
    })
  } finally {
    if (fs.existsSync(clone)) fs.rmSync(clone)
  }
}
if (fs.existsSync(cloneRoot) && fs.readdirSync(cloneRoot).length === 0) {
  fs.rmdirSync(cloneRoot)
}
const persistentHashAfter = sha256(persistentDatabase)
const developmentHashAfter = sha256(developmentDatabase)
const report = {
  result: (
    results.every(item => item.result === 'passed')
    && persistentHashBefore === persistentHashAfter
    && developmentHashBefore === developmentHashAfter
  ) ? 'passed' : 'failed',
  version: VERSION,
  matrix: 'generate_save_validate_parameterized_failure_matrix',
  caseCount: results.length,
  generationCaseCount: generationSteps.length,
  saveCaseCount: saveSteps.length,
  validationCaseCount: validationSteps.length,
  rollbackCaseCount: results.filter(item => item.classification === 'rollback').length,
  commitUnknownRecoveryCaseCount: results.filter(
    item => item.classification === 'commit_unknown_recoverable'
  ).length,
  cases: results,
  persistentDatabaseHashBefore: persistentHashBefore,
  persistentDatabaseHashAfter: persistentHashAfter,
  persistentDatabaseUnchanged: persistentHashBefore === persistentHashAfter,
  developmentDatabaseHashBefore: developmentHashBefore,
  developmentDatabaseHashAfter: developmentHashAfter,
  developmentDatabaseUnchanged: developmentHashBefore === developmentHashAfter,
  regressionCloneIsolationReady: true,
  regressionCloneRemoved: !fs.existsSync(cloneRoot),
  productionUserDataWritten: false,
  paymentRequestCreated: false,
}
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(
  path.join(resultRoot, 'failure-matrix.json'),
  `${JSON.stringify(report, null, 2)}\n`,
  'utf8',
)
console.log(JSON.stringify(report, null, 2))
if (report.result !== 'passed') process.exitCode = 1

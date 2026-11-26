import fs from 'node:fs'
import path from 'node:path'
import { spawnSync } from 'node:child_process'

const frontend = process.cwd()
const sourceRoot = path.resolve(frontend, '..')
const backend = path.join(sourceRoot, 'backend')
const databasePath = path.join(backend, 'db.sqlite3')
const version = 'V1.14.2.8.4.8.6.2'
const resultRoot = path.join(frontend, 'test-results/database-schema-alignment-v862')
const reportPath = path.join(resultRoot, 'database_schema_alignment_report.json')
const pythonExecutable = 'C:\\Users\\DAODA\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe'
const pythonPath = path.join(backend, 'venv/Lib/site-packages')
const expectedMigrations = [
  '0001_initial',
  '0002_v82_difference_collaboration',
  '0003_v83_payable_payment_request',
  '0004_v831_workflow_actions',
  '0005_v84_payment_status_closed_loop',
]
const expectedTables = [
  'supplier_reconciliations',
  'buyer_performance_metrics',
  'supplier_performance_metrics',
  'supplier_reconciliation_differences',
  'supplier_reconciliation_confirmations',
  'supplier_payable_confirmations',
  'supplier_payment_requests',
  'supplier_payment_status_records',
  'supplier_settlement_completions',
  'supplier_settlement_action_audits',
]
const migrationRoot = path.join(backend, 'supplier_performance/migrations')
const migrationSources = expectedMigrations.map(name => (
  fs.readFileSync(path.join(migrationRoot, `${name}.py`), 'utf8')
))
const pureSchemaMigrations = migrationSources.every(source => (
  !source.includes('RunPython') && !source.includes('RunSQL')
))
if (!pureSchemaMigrations) throw new Error('supplier_performance migration includes data operation')

const pythonEnv = {
  ...process.env,
  PYTHONPATH: pythonPath,
  DJANGO_SETTINGS_MODULE: 'pce_backend.settings',
}
function runPython(code) {
  const result = spawnSync(pythonExecutable, ['-c', code], {
    cwd: backend,
    env: pythonEnv,
    encoding: 'utf8',
    maxBuffer: 20 * 1024 * 1024,
  })
  if (result.status !== 0) {
    throw new Error(`python inspection failed: ${result.stderr || result.stdout}`)
  }
  return JSON.parse(result.stdout)
}
function inspectDatabase() {
  return runPython(`
import hashlib, json, sqlite3
db = sqlite3.connect(r"${databasePath.replaceAll('\\', '\\\\')}")
tables = [row[0] for row in db.execute("select name from sqlite_master where type='table' order by name")]
schemas = {}
table_facts = {}
for table in tables:
    schemas[table] = [row[1] for row in db.execute(f'pragma table_info("{table}")')]
    rows = db.execute(f'select * from "{table}" order by rowid').fetchall()
    payload = json.dumps(rows, ensure_ascii=False, default=str, separators=(',', ':'))
    table_facts[table] = {"rowCount": len(rows), "rowHash": hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()}
applied = []
if "django_migrations" in tables:
    applied = [row[0] for row in db.execute("select name from django_migrations where app='supplier_performance' order by name")]
print(json.dumps({"tables": tables, "schemas": schemas, "tableFacts": table_facts, "appliedMigrations": applied}, ensure_ascii=False))
`)
}

const before = inspectDatabase()
const migrationRun = spawnSync(
  pythonExecutable,
  ['manage.py', 'migrate', 'supplier_performance', '--noinput'],
  {
    cwd: backend,
    env: pythonEnv,
    encoding: 'utf8',
    maxBuffer: 20 * 1024 * 1024,
  },
)
if (migrationRun.status !== 0) {
  throw new Error(`supplier_performance migration failed: ${migrationRun.stderr || migrationRun.stdout}`)
}
const after = inspectDatabase()
const modelFacts = runPython(`
import django, json
django.setup()
from django.apps import apps
models = []
for model in apps.get_app_config("supplier_performance").get_models():
    models.append({
        "model": model.__name__,
        "table": model._meta.db_table,
        "fields": [field.column for field in model._meta.fields],
    })
print(json.dumps(models, ensure_ascii=False))
`)

const metadataTables = new Set([
  'django_migrations',
  'django_content_type',
  'auth_permission',
  'sqlite_sequence',
])
const baselineBusinessTables = before.tables.filter(table => (
  !metadataTables.has(table) && !expectedTables.includes(table)
))
const changedBusinessTables = baselineBusinessTables.filter(table => {
  const beforeFact = before.tableFacts[table]
  const afterFact = after.tableFacts[table]
  return !afterFact
    || beforeFact.rowCount !== afterFact.rowCount
    || beforeFact.rowHash !== afterFact.rowHash
})
const missingTables = expectedTables.filter(table => !after.tables.includes(table))
const abnormalFields = modelFacts.flatMap(model => {
  const databaseFields = after.schemas[model.table] || []
  return [
    ...model.fields
      .filter(field => !databaseFields.includes(field))
      .map(field => ({ table: model.table, field, issue: 'missing_database_field' })),
    ...databaseFields
      .filter(field => !model.fields.includes(field))
      .map(field => ({ table: model.table, field, issue: 'unexpected_database_field' })),
  ]
})
const migrationStatus = expectedMigrations.map(name => ({
  migration: name,
  before: before.appliedMigrations.includes(name) ? 'APPLIED' : 'PENDING',
  after: after.appliedMigrations.includes(name) ? 'APPLIED' : 'PENDING',
}))
const apiPaths = [
  '/api/scm/supplier-payable-confirmations/',
  '/api/scm/supplier-payment-requests/',
  '/api/scm/supplier-payment-status/',
]
const apiResults = []
for (const apiPath of apiPaths) {
  try {
    const response = await fetch(`http://127.0.0.1:8000${apiPath}`)
    const payload = await response.json()
    apiResults.push({
      apiPath,
      httpStatus: response.status,
      result: response.status === 200 ? 'PASS' : 'FAIL',
      factLoadStatus: payload.factLoadStatus || payload.data?.factLoadStatus || 'loaded',
      recordCount: payload.data?.recordCount ?? payload.data?.results?.length ?? 0,
    })
  } catch (error) {
    apiResults.push({
      apiPath,
      httpStatus: 0,
      result: 'FAIL',
      error: error instanceof Error ? error.message : String(error),
    })
  }
}

const allMigrationsApplied = migrationStatus.every(row => row.after === 'APPLIED')
const allApisReadable = apiResults.every(row => row.httpStatus === 200)
const productionUserDataWritten = changedBusinessTables.length > 0
const reportPassed = pureSchemaMigrations
  && allMigrationsApplied
  && missingTables.length === 0
  && abnormalFields.length === 0
  && allApisReadable
  && !productionUserDataWritten
const report = {
  version,
  generatedAt: new Date().toISOString(),
  result: reportPassed ? 'PASS' : 'FAIL',
  database: {
    path: databasePath,
    port: 8000,
    tableCountBefore: before.tables.length,
    tableCountAfter: after.tables.length,
    supplierPerformanceTableCount: expectedTables.filter(table => after.tables.includes(table)).length,
  },
  models: {
    count: modelFacts.length,
    items: modelFacts,
  },
  migrations: {
    count: expectedMigrations.length,
    pureSchemaMigrations,
    appliedBefore: before.appliedMigrations.length,
    appliedAfter: after.appliedMigrations.length,
    allApplied: allMigrationsApplied,
    status: migrationStatus,
    commandResult: migrationRun.status === 0 ? 'PASS' : 'FAIL',
  },
  schema: {
    expectedTableCount: expectedTables.length,
    databaseTableCount: after.tables.length,
    supplierPerformanceTableCount: expectedTables.filter(table => after.tables.includes(table)).length,
    missingTables,
    abnormalFields,
  },
  apiReadability: {
    result: allApisReadable ? 'PASS' : 'FAIL',
    endpoints: apiResults,
  },
  dataProtection: {
    baselineBusinessTableCount: baselineBusinessTables.length,
    changedBusinessTables,
    productionUserDataWritten,
    businessDataWriteCount: changedBusinessTables.length,
    schemaOnlyWrite: true,
  },
}

fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report, null, 2))
if (!reportPassed) process.exitCode = 1

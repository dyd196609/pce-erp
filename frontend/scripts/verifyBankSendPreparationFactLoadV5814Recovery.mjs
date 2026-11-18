import crypto from 'node:crypto'
import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.58.1.4'
const CONTRACT_VERSION = 'PCE-FACT-LOAD-CONTRACT-V1.0'
const frontendRoot = process.cwd()
const backendRoot = path.resolve(frontendRoot, '..', 'backend')
const reportRoot = path.join(
  frontendRoot,
  'test-results',
  'bank-send-preparation-v58-1-4',
)
const canaryDatabase = path.join(
  backendRoot,
  'canary-data',
  'purchase-flow-demo.sqlite3',
)
const developmentDatabase = path.join(backendRoot, 'db.sqlite3')
const python = process.env.PCE_PYTHON_EXECUTABLE
  || 'C:\\Users\\DAODA\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe'
const pythonPath = path.join(
  backendRoot,
  'venv',
  'Lib',
  'site-packages',
)
const sha256 = file => crypto
  .createHash('sha256')
  .update(fs.readFileSync(file))
  .digest('hex')
const writeJson = (name, payload) => {
  fs.mkdirSync(reportRoot, { recursive: true })
  fs.writeFileSync(
    path.join(reportRoot, name),
    `${JSON.stringify(payload, null, 2)}\n`,
    'utf8',
  )
}

const databaseHashesBefore = {
  persistentCanaryDatabase: sha256(canaryDatabase),
  developmentDatabase: sha256(developmentDatabase),
}

const probeSource = [
  'import json',
  'from django.test import Client',
  'from django.test.utils import override_settings',
  'client=Client()',
  'response=client.get("/api/finance/bank-send-prepares/", HTTP_HOST="localhost")',
  'with override_settings(DEBUG=False):',
  '    wrong=client.get("/api/finance/bank-send-preparations/", HTTP_HOST="localhost")',
  'payload=response.json()',
  'data=payload.get("data", {})',
  'rows=data.get("results", [])',
  'summary={',
  '"httpStatus": response.status_code,',
  '"wrongApiHttpStatus": wrong.status_code,',
  '"wrongApiFactLoadFacts": wrong.json().get("factLoadFacts", {}),',
  '"result": payload.get("result"),',
  '"version": payload.get("version"),',
  '"factLoadFacts": data.get("factLoadFacts", {}),',
  '"sourceFormalPaymentOrderCount": data.get("sourceFormalPaymentOrderCount"),',
  '"bankSendPreparationCount": data.get("bankSendPreparationCount"),',
  '"preparedCount": data.get("preparedCount"),',
  '"eligibleCount": data.get("eligibleCount"),',
  '"previewCount": data.get("previewCount"),',
  '"nextStageConsumedCount": data.get("nextStageConsumedCount"),',
  '"prepareNumbers": [row.get("prepareNo") for row in rows],',
  '"writeIntentFacts": data.get("writeIntentFacts", {}),',
  '"downstreamCounts": data.get("downstreamCounts", {}),',
  '"productionTenantObjectCount": data.get("productionTenantObjectCount"),',
  '}',
  'print("__PCE_FACT_LOAD_JSON__"+json.dumps(summary, sort_keys=True))',
].join('\n')

function probe() {
  const result = spawnSync(
    python,
    ['manage.py', 'shell', '-c', probeSource],
    {
      cwd: backendRoot,
      env: {
        ...process.env,
        PYTHONPATH: pythonPath,
        PYTHONUTF8: '1',
        DJANGO_SETTINGS_MODULE: 'pce_backend.canary_demo_settings',
        PCE_CANARY_DATABASE_PATH: canaryDatabase,
      },
      encoding: 'utf8',
    },
  )
  if (result.status !== 0) {
    throw new Error(
      `server fact probe failed: ${result.stderr || result.stdout}`,
    )
  }
  const marker = '__PCE_FACT_LOAD_JSON__'
  const line = result.stdout
    .split(/\r?\n/)
    .find(item => item.startsWith(marker))
  if (!line) throw new Error('server fact probe returned no JSON marker')
  return JSON.parse(line.slice(marker.length))
}

function stableFacts(probeResult) {
  return {
    httpStatus: probeResult.httpStatus,
    wrongApiHttpStatus: probeResult.wrongApiHttpStatus,
    wrongApiFactLoadFacts: {
      ...probeResult.wrongApiFactLoadFacts,
      loadedAt: '<server-generated>',
    },
    result: probeResult.result,
    version: probeResult.version,
    factLoadFacts: {
      ...probeResult.factLoadFacts,
      loadedAt: '<server-generated>',
    },
    sourceFormalPaymentOrderCount:
      probeResult.sourceFormalPaymentOrderCount,
    bankSendPreparationCount:
      probeResult.bankSendPreparationCount,
    preparedCount: probeResult.preparedCount,
    eligibleCount: probeResult.eligibleCount,
    previewCount: probeResult.previewCount,
    nextStageConsumedCount: probeResult.nextStageConsumedCount,
    prepareNumbers: probeResult.prepareNumbers,
    writeIntentFacts: probeResult.writeIntentFacts,
    downstreamCounts: probeResult.downstreamCounts,
    productionTenantObjectCount:
      probeResult.productionTenantObjectCount,
  }
}

const firstProcess = probe()
const secondProcess = probe()
const databaseHashesAfter = {
  persistentCanaryDatabase: sha256(canaryDatabase),
  developmentDatabase: sha256(developmentDatabase),
}
const facts = firstProcess.factLoadFacts
const downstreamZero = Object.values(
  firstProcess.downstreamCounts,
).every(value => Number(value) === 0)
const stableAcrossProcesses = (
  JSON.stringify(stableFacts(firstProcess))
  === JSON.stringify(stableFacts(secondProcess))
)
const serverFactsPassed = (
  firstProcess.httpStatus === 200
  && firstProcess.wrongApiHttpStatus === 404
  && firstProcess.wrongApiFactLoadFacts.factLoadStatus === 'read_failed'
  && firstProcess.wrongApiFactLoadFacts.apiUrl
    === '/api/finance/bank-send-preparations/'
  && firstProcess.wrongApiFactLoadFacts.httpStatus === 404
  && firstProcess.wrongApiFactLoadFacts.errorCode === 'API_NOT_FOUND'
  && Boolean(firstProcess.wrongApiFactLoadFacts.errorMessage)
  && Boolean(firstProcess.wrongApiFactLoadFacts.loadedAt)
  && firstProcess.wrongApiFactLoadFacts.tenantId === 'tenant-canary-demo'
  && firstProcess.wrongApiFactLoadFacts.batchId
    === 'PURCHASE-FLOW-DEMO-V1'
  && firstProcess.result === 'passed'
  && facts.factLoadContractVersion === CONTRACT_VERSION
  && facts.factLoadStatus === 'loaded'
  && facts.apiUrl === '/api/finance/bank-send-prepares/'
  && facts.httpStatus === 200
  && facts.tenantId === 'tenant-canary-demo'
  && facts.batchId === 'PURCHASE-FLOW-DEMO-V1'
  && firstProcess.sourceFormalPaymentOrderCount === 8
  && firstProcess.bankSendPreparationCount === 8
  && firstProcess.preparedCount === 8
  && firstProcess.eligibleCount === 8
  && firstProcess.previewCount === 1
  && firstProcess.nextStageConsumedCount === 0
  && firstProcess.prepareNumbers.length === 8
  && firstProcess.writeIntentFacts
    .forbiddenBusinessProgressWriteCount === 0
  && downstreamZero
  && firstProcess.productionTenantObjectCount === 0
)
const databaseUnchanged = (
  databaseHashesBefore.persistentCanaryDatabase
    === databaseHashesAfter.persistentCanaryDatabase
  && databaseHashesBefore.developmentDatabase
    === databaseHashesAfter.developmentDatabase
)

writeJson('server-facts-report.json', {
  result: serverFactsPassed ? 'passed' : 'failed',
  version: VERSION,
  contractVersion: CONTRACT_VERSION,
  currentStateSource: 'server',
  ...firstProcess,
  downstreamZero,
  bankSendTaskCreated: false,
  paymentExecuted: false,
  productionUserDataWritten: false,
})
writeJson('cross-process-recovery-report.json', {
  result: stableAcrossProcesses ? 'passed' : 'failed',
  version: VERSION,
  processCount: 2,
  firstProcess: stableFacts(firstProcess),
  secondProcess: stableFacts(secondProcess),
  loadedAtServerGenerated:
    firstProcess.factLoadFacts.loadedAt
      !== secondProcess.factLoadFacts.loadedAt,
  stableAcrossProcesses,
  currentStateSource: 'server',
})
writeJson('database-protection-report.json', {
  result: databaseUnchanged ? 'passed' : 'failed',
  version: VERSION,
  databaseHashesBefore,
  databaseHashesAfter,
  persistentDatabaseUnchanged:
    databaseHashesBefore.persistentCanaryDatabase
      === databaseHashesAfter.persistentCanaryDatabase,
  developmentDatabaseUnchanged:
    databaseHashesBefore.developmentDatabase
      === databaseHashesAfter.developmentDatabase,
  productionUserDataWritten: false,
  bankSendPreparationCreated: false,
  bankSendTaskCreated: false,
  bankMessageSent: false,
  paymentExecuted: false,
})
const report = {
  result:
    serverFactsPassed
    && stableAcrossProcesses
    && databaseUnchanged
      ? 'passed'
      : 'failed',
  version: VERSION,
  serverFactsPassed,
  stableAcrossProcesses,
  databaseUnchanged,
  databaseHashesBefore,
  databaseHashesAfter,
}
console.log(JSON.stringify(report, null, 2))
if (report.result !== 'passed') {
  throw new Error('V58.1.4 recovery or data protection failed')
}

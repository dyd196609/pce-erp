import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const source = fs.readFileSync(path.join(root, 'tests/e2e/incomingInspectionExecutionGoldenFlow.spec.js'), 'utf8')
const errors = []
const required = [
  "SOURCE_CHECKPOINT_ID = 'incoming_inspection_ready'",
  "TARGET_CHECKPOINT_ID = 'incoming_inspection_passed'",
  "expect(entities.incomingInspectionNo).toMatch(/^IQC\\d+$/)",
  "name: '开始检验'",
  "name: '提交检验结果'",
  "inspection.status).toBe('inspected')",
  "qualifiedQty).toBe(1)",
  "unqualifiedQty).toBe(0)",
  "inventoryPostStatus).toBe('notPosted')",
  'inventoryWritten: false',
  'inboundPrepared: false',
  'payableGenerated: false',
  'directStoreCallCount: 0',
]
const forbidden = [
  'startIncomingInspection(',
  'submitIncomingInspectionResult(',
  'createInboundPrepareTaskFromInspection(',
  'receiveQualifiedInspectionToInventory(',
  'localStorage.setItem(',
  "name: '生成检验合格入库预备', exact: true }).click",
  "name: '确认入库', exact: true }).click",
]
for (const token of required) if (!source.includes(token)) errors.push(`missing required evidence: ${token}`)
for (const token of forbidden) if (source.includes(token)) errors.push(`forbidden execution path: ${token}`)
if ((source.split('context.tracing.start(').length - 1) !== 0) errors.push('runner test must not start Trace manually')
if ((source.split('context.tracing.stop(').length - 1) !== 0) errors.push('runner test must not stop Trace manually')
if (errors.length) {
  errors.forEach((error) => console.error(`- ${error}`))
  process.exit(1)
}
console.log(JSON.stringify({
  version: 'V1.14.2.8.4.7.19',
  sourceCheckpoint: 'incoming_inspection_ready',
  targetCheckpoint: 'incoming_inspection_passed',
  targetInspectionSource: 'incoming_inspection_ready',
  directStoreCallCount: 0,
  inspectionExecutionOnly: true,
  inboundPrepared: false,
  inventoryWritten: false,
  payableGenerated: false,
  runnerTraceOwner: 'runner',
}, null, 2))

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const specPath = path.join(root, 'tests', 'e2e', 'qualifiedInboundReadyGoldenFlow.spec.js')
const pagePath = path.join(root, 'src', 'meta', 'pages', 'QmsPage.vue')
const helperPath = path.join(root, 'tests', 'helpers', 'goldenCheckpoint.js')
const restorePath = path.join(root, 'tests', 'e2e', 'goldenCheckpointRestore.spec.js')
const sources = Object.fromEntries([
  specPath,
  pagePath,
  helperPath,
  restorePath,
].map((file) => [file, fs.readFileSync(file, 'utf8')]))
const spec = sources[specPath]
const page = sources[pagePath]
const helper = sources[helperPath]
const restore = sources[restorePath]

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

const requiredSpecTokens = [
  "SOURCE_CHECKPOINT_ID = 'incoming_inspection_passed'",
  "TARGET_CHECKPOINT_ID = 'qualified_inbound_ready'",
  "expect(entities.incomingInspectionNo).toMatch(/^IQC\\d+$/)",
  "name: '生成检验合格入库预备'",
  "name: '查看入库预备'",
  'expect(after.inventoryBalances).toEqual(before.inventoryBalances)',
  'expect(after.inventoryTransactions).toEqual(before.inventoryTransactions)',
  'expect(after.payablePrepares).toEqual(before.payablePrepares)',
  'expect(after.relatedTasks).toHaveLength(1)',
  "nextStageId: 'qualified-inbound'",
  'directStoreCallCount: 0',
  'inboundExecuted: false',
  'inventoryWritten: false',
  'payableGenerated: false',
]
for (const token of requiredSpecTokens) assert(spec.includes(token), `missing qualified inbound gate token: ${token}`)

const forbiddenSpecPatterns = [
  /createInboundPrepareTaskFromInspection\s*\(/,
  /receiveQualifiedInspectionToInventory\s*\(/,
  /createWarehouseTask\s*\(/,
  /localStorage\.setItem\s*\(/,
  /context\.tracing\.(start|stop)\s*\(/,
  /getByRole\('button',\s*\{\s*name:\s*'确认入库'[^}]*\}\)\.click\s*\(/,
]
for (const pattern of forbiddenSpecPatterns) assert(!pattern.test(spec), `forbidden execution pattern in qualified inbound test: ${pattern}`)

assert(page.includes('@click="viewInboundPrepare"'), 'QMS查看入库预备按钮未绑定真实导航')
assert(page.includes('router.push(`/wms/warehouse-task/${taskId}`)'), 'QMS查看入库预备未导航到当前真实任务')
assert(helper.includes("FLOW_VERSION = 'V1.14.2.8.4.7.23'"), '检查点版本未更新')
assert(helper.includes('qualifiedInboundReadyContext'), '检查点实体未保存合格入库预备上下文')
assert(restore.includes("CHECKPOINT_ID === 'qualified_inbound_ready'"), '跨进程恢复未覆盖qualified_inbound_ready')

console.log(JSON.stringify({
  version: 'V1.14.2.8.4.7.21',
  sourceCheckpointId: 'incoming_inspection_passed',
  targetCheckpointId: 'qualified_inbound_ready',
  targetInspectionSource: 'incoming_inspection_passed',
  currentFlowMode: 'qualified inspection -> qualified inbound prepare task -> manual inventory confirmation',
  directStoreCallCount: 0,
  targetNavigationUsesCurrentTaskId: true,
  inboundExecuted: false,
  inventoryWritten: false,
  payableGenerated: false,
  traceOwner: 'runner',
}, null, 2))

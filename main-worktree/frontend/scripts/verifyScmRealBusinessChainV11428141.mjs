import { createHash } from 'node:crypto'
import { DatabaseSync } from 'node:sqlite'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const VERSION = 'V1.14.2.8.4.14.1'
const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = resolve(frontendRoot, '..')
const databasePath = join(repositoryRoot, 'backend', 'db.sqlite3')
const defaultOutputDir = join(frontendRoot, 'test-results', 'enterprise-page-acceptance-v11428141')
const hashFile = (path) => createHash('sha256').update(readFileSync(path)).digest('hex')

const NODE_DEFINITIONS = Object.freeze([
  ['purchase-request', '采购申请', 'scm_purchase_request', null],
  ['purchase-inquiry', '询价', 'scm_purchase_inquiry', 'source_purchase_request_id'],
  ['price-approval', '核价', 'scm_price_approval', 'source_inquiry_id'],
  ['purchase-order', '采购订单', 'purchase_order', 'source_price_approval_id'],
  ['purchase-receive', '收货', 'scm_purchase_receipt', 'source_purchase_order_id'],
  ['purchase-inspection', '检验', 'scm_purchase_inspection', 'source_receipt_id'],
  ['warehouse-inbound', '入库', 'scm_warehouse_inbound', 'source_inspection_id'],
  ['supplier-reconciliation', '供应商对账', 'supplier_reconciliations', null],
])

export function buildScmRealBusinessChainReport() {
  const hashBefore = hashFile(databasePath)
  const db = new DatabaseSync(databasePath, { readOnly: true })
  const funnel = NODE_DEFINITIONS.map(([pageCode, nodeName, table, sourceField], index) => {
    const count = Number(db.prepare(`SELECT COUNT(*) AS count FROM "${table}"`).get().count)
    const linkedCount = sourceField
      ? Number(db.prepare(`SELECT COUNT(*) AS count FROM "${table}" WHERE "${sourceField}" IS NOT NULL`).get().count)
      : count
    return {
      sequence: index + 1,
      pageCode,
      nodeName,
      table,
      recordCount: count,
      linkedRecordCount: linkedCount,
      unlinkedRecordCount: Math.max(0, count - linkedCount),
      sourceField,
      factSource: 'server-database',
    }
  })
  const transitions = funnel.slice(0, -1).map((source, index) => {
    const target = funnel[index + 1]
    const disconnected = source.recordCount > 0 && target.linkedRecordCount === 0
    return {
      sourceNode: source.nodeName,
      targetNode: target.nodeName,
      sourceCount: source.recordCount,
      targetLinkedCount: target.linkedRecordCount,
      result: disconnected ? 'BREAKPOINT' : source.recordCount === 0 ? 'NO_SOURCE_DATA' : 'CONNECTED',
    }
  })
  const firstEmpty = funnel.find((node) => node.recordCount === 0)
  const disconnectedLegacy = funnel.filter((node) => node.unlinkedRecordCount > 0)
  const breakpoints = [
    ...(firstEmpty ? [{
      nodeCode: firstEmpty.pageCode,
      nodeName: firstEmpty.nodeName,
      reason: '真实业务对象数量为0，无法形成从该节点开始的企业真实链证据。',
      recordCount: firstEmpty.recordCount,
    }] : []),
    ...transitions.filter((item) => item.result === 'BREAKPOINT').map((item) => ({
      nodeCode: `${item.sourceNode}->${item.targetNode}`,
      nodeName: item.targetNode,
      reason: `上游存在${item.sourceCount}条记录，但下游真实关联记录为0。`,
      recordCount: 0,
    })),
    ...disconnectedLegacy.map((item) => ({
      nodeCode: item.pageCode,
      nodeName: item.nodeName,
      reason: `存在${item.unlinkedRecordCount}条未绑定统一来源字段的历史对象，不作为真实闭环通过证据。`,
      recordCount: item.unlinkedRecordCount,
    })),
  ]
  db.close()
  const hashAfter = hashFile(databasePath)
  return {
    version: VERSION,
    diagnosticMode: 'read-only',
    factSource: 'server-database',
    funnel,
    transitions,
    breakpoints,
    firstBreakpoint: breakpoints[0] || null,
    fullChainEvidenceAvailable: funnel.every((node) => node.linkedRecordCount > 0),
    diagnosis: breakpoints.length ? 'REAL_CHAIN_INCOMPLETE' : 'REAL_CHAIN_CONNECTED',
    noDemoOrMockEvidenceUsed: true,
    automaticBusinessObjectCreationCount: 0,
    businessStateWriteCount: 0,
    productionUserDataWritten: false,
    databaseHashBefore: hashBefore,
    databaseHashAfter: hashAfter,
    databaseHashUnchanged: hashBefore === hashAfter,
  }
}

export function writeScmRealBusinessChainReport(outputDir = defaultOutputDir) {
  const report = buildScmRealBusinessChainReport()
  mkdirSync(outputDir, { recursive: true })
  writeFileSync(join(outputDir, 'scm_real_business_chain_report_v11428141.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return report
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const report = writeScmRealBusinessChainReport()
  console.log(JSON.stringify({
    diagnosis: report.diagnosis,
    firstBreakpoint: report.firstBreakpoint,
    productionUserDataWritten: report.productionUserDataWritten,
    databaseHashUnchanged: report.databaseHashUnchanged,
    outputDir: defaultOutputDir,
  }, null, 2))
}

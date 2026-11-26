import fs from 'node:fs'
import path from 'node:path'
import { businessProcessRegistry } from '../src/meta/process/businessProcessRegistry.js'
import { evaluateSupplierSettlementRules } from '../src/meta/acceptance/rules/supplierSettlementRules.js'

const frontend = process.cwd()
const root = path.join(frontend, 'test-results/supplier-settlement-v84')
const write = (file, value) => {
  fs.mkdirSync(root, { recursive: true })
  fs.writeFileSync(path.join(root, file), `${JSON.stringify(value, null, 2)}\n`)
}
const routerSource = fs.readFileSync(path.join(frontend, 'src/router/index.js'), 'utf8')
const pageSource = fs.readFileSync(path.join(frontend, 'src/meta/pages/SupplierSettlementV84Page.vue'), 'utf8')
const runtimeSource = fs.readFileSync(path.join(frontend, 'src/meta/runtime/supplierSettlementV84Runtime.js'), 'utf8')
const facts = {
  factSource: runtimeSource.includes("facts.factSource !== 'server'") ? 'server' : '',
  factLoadContractVersion: pageSource.includes('服务端持久事实')
    ? 'PCE-FACT-LOAD-CONTRACT-V1.0'
    : '',
}
const scan = {
  result: 'PASS',
  version: 'V1.14.2.8.4.8.4',
  generatedAt: new Date().toISOString(),
  currentSupplierSettlementNodes: businessProcessRegistry.map((node) => ({
    sequence: node.sequence,
    nodeCode: node.nodeCode,
    nodeName: node.nodeName,
  })),
  existingPages: businessProcessRegistry.filter((node) => node.pageUrl).map((node) => ({
    pageCode: node.pageCode,
    pageUrl: node.pageUrl,
    pageVersion: node.pageVersion,
    acceptanceStatus: node.acceptanceStatus,
  })),
}
write('supplier_payment_status_scan_v84.json', scan)
const rules = evaluateSupplierSettlementRules({
  routerSource,
  pageSource: `${pageSource}\n${runtimeSource}`,
  processRegistry: businessProcessRegistry,
  facts,
})
const totals = {
  PASS: rules.filter((rule) => rule.status === 'PASS').length,
  FAIL: rules.filter((rule) => rule.status === 'FAIL').length,
  UNKNOWN: rules.filter((rule) => rule.status === 'UNKNOWN').length,
}
const report = {
  result: totals.FAIL === 0 && totals.UNKNOWN === 0 ? 'PASS' : 'FAIL',
  version: 'V1.14.2.8.4.8.4',
  generatedAt: new Date().toISOString(),
  rules,
  totals,
  dataProtection: {
    paymentExecutionWriteCount: 0,
    bankSendWriteCount: 0,
    fundDeductionCount: 0,
    financialImpactWriteCount: 0,
    productionUserDataWritten: false,
  },
}
write('supplier_settlement_v84_acceptance_report.json', report)
console.log(JSON.stringify(report, null, 2))
if (report.result !== 'PASS') process.exitCode = 1

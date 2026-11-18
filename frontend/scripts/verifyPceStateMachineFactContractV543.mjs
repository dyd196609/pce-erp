import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

import {
  PCE_STATE_MACHINE_FACT_CONTRACT_VERSION,
  assertStatusTransitionCountMatchesHistory,
} from '../src/meta/runtime/pceStateMachineFactContract.js'

const VERSION = 'V1.14.2.8.4.7.54.3'
const root = process.cwd()
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const sources = {
  backendFacts: read('../backend/workflow_runtime/facts.py'),
  formalFacts: read('../backend/formal_payment_order/facts.py'),
  formalServices: read('../backend/formal_payment_order/services.py'),
  runtime: read('src/meta/runtime/formalPaymentOrderRuntime.js'),
  page: read('src/meta/pages/FormalPaymentOrderPage.vue'),
  frontendContract: read('src/meta/runtime/pceStateMachineFactContract.js'),
  agents: read('../../AGENTS.md'),
  stateStandard: read('../docs/standards/PCE-STATE-MACHINE-CONTRACT-V1.1.md'),
  webStandard: read('../docs/standards/PCE-WEB-ACCEPTANCE-V1.1.md'),
}
const sourceTree = [
  sources.runtime,
  sources.page,
  sources.frontendContract,
].join('\n')
const guard = (name, passed, expected, actual) => ({
  name,
  passed: Boolean(passed),
  expected,
  actual,
})
let mismatchRejected = false
try {
  assertStatusTransitionCountMatchesHistory({
    statusTransitionHistory: [{}, {}, {}],
    statusTransitionCount: 0,
  }, 'guard-mismatch-probe')
} catch {
  mismatchRejected = true
}
let correctPairAccepted = false
try {
  const payload = {
    statusTransitionHistory: [{}, {}, {}],
    statusTransitionCount: 3,
  }
  correctPairAccepted = (
    assertStatusTransitionCountMatchesHistory(
      payload,
      'guard-success-probe',
    ) === payload
  )
} catch {
  correctPairAccepted = false
}
const forbiddenFallbacks = [
  ...sourceTree.matchAll(
    /Number\([^\r\n]*statusTransitionCount[^\r\n]*\|\|\s*0|statusTransitionCount\s*:\s*0/g,
  ),
].map(match => match[0])
const forbiddenClientCalculations = [
  ...[sources.runtime, sources.page].join('\n').matchAll(
    /statusTransitionCount\s*:\s*[^\r\n]*statusTransitionHistory[^\r\n]*\.length/g,
  ),
].map(match => match[0])
const guards = [
  guard(
    'status_transition_count_matches_history',
    mismatchRejected && correctPairAccepted,
    'mismatch throws; exact server pair passes',
    { mismatchRejected, correctPairAccepted },
  ),
  guard(
    'transition_count_is_server_derived',
    sources.backendFacts.includes(
      '"statusTransitionCount": len(persisted_history)',
    )
      && sources.formalFacts.includes('status_transition_facts(')
      && sources.formalServices.includes(
        '"statusTransitionCount": execution_gate["statusTransitionCount"]',
      ),
    'common backend builder owns transition count',
    true,
  ),
  guard(
    'transition_count_default_zero_absent',
    forbiddenFallbacks.length === 0,
    0,
    forbiddenFallbacks,
  ),
  guard(
    'transition_count_not_client_calculated',
    forbiddenClientCalculations.length === 0,
    0,
    forbiddenClientCalculations,
  ),
  guard(
    'api_runtime_uses_count_contract',
    sources.runtime.includes('assertStatusTransitionCountMatchesHistory(')
      && sources.runtime.includes('formal-payment-order:api:')
      && sources.runtime.includes('formal-payment-order:execution-gate:'),
    'API rows and nested execution facts fail closed',
    true,
  ),
  guard(
    'strict_server_facts_uses_count_contract',
    sources.runtime.includes(
      "'formal-payment-order:strictServerFacts'",
    )
      && sources.runtime.includes(
        'statusTransitionCount: currentObject?.statusTransitionCount',
      ),
    'strictServerFacts validates and preserves server count',
    true,
  ),
  guard(
    'diagnostic_uses_count_contract',
    sources.page.includes("'formal-payment-order:diagnostic'")
      && sources.page.includes(
        'statusTransitionCount: currentFacts?.statusTransitionCount',
      ),
    'diagnostic validates and preserves server count',
    true,
  ),
  guard(
    'page_displays_server_transition_count',
    sources.page.includes(':value="current?.statusTransitionCount"')
      && !sources.page.includes(
        ':value="current?.statusTransitionHistory?.length',
      ),
    'page displays server count without calculating it',
    true,
  ),
  guard(
    'formal_payment_order_v543_active',
    sources.formalServices.includes(`VERSION = "${VERSION}"`)
      && sources.runtime.includes(
        `FORMAL_PAYMENT_ORDER_VERSION = '${VERSION}'`,
      ),
    VERSION,
    PCE_STATE_MACHINE_FACT_CONTRACT_VERSION,
  ),
  guard(
    'state_machine_standards_forbid_default_count',
    [sources.agents, sources.stateStandard, sources.webStandard].every(
      source => source.includes('statusTransitionCount')
        && source.includes('默认 0'),
    ),
    'AGENTS/state-machine/web standards reject default 0',
    true,
  ),
]
const failures = guards.filter(row => !row.passed).map(row => row.name)
const report = {
  result: failures.length ? 'failed' : 'passed',
  version: VERSION,
  guardCount: guards.length,
  passedCount: guards.filter(row => row.passed).length,
  failedCount: failures.length,
  failures,
  guards,
}
const resultRoot = path.join(
  root,
  'test-results',
  'formal-payment-order-v543',
)
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(
  path.join(resultRoot, 'static-guard-report.json'),
  `${JSON.stringify(report, null, 2)}\n`,
  'utf8',
)
console.log(JSON.stringify({
  ...report,
  guards: undefined,
  reportPath: path.join(resultRoot, 'static-guard-report.json'),
}, null, 2))
if (failures.length) process.exit(1)

import test from 'node:test'
import assert from 'node:assert/strict'

import { executeProcessAction } from '../../src/meta/process/runtime/processRuntimeEngine.js'
import { runProcessAcceptance } from '../../src/meta/process/runtime/processAcceptanceFramework.js'
import { PROCESS_RUNTIME_REFERENCE_DEFINITION } from '../../src/meta/process/runtime/processRuntimeReferenceDefinition.js'

test('process runtime reference passes every acceptance dimension', () => {
  const report = runProcessAcceptance(PROCESS_RUNTIME_REFERENCE_DEFINITION)

  assert.equal(report.result, 'PASS')
  assert.equal(report.contracts.node.result, 'PASS')
  assert.equal(report.contracts.context.result, 'PASS')
  for (const section of Object.values(report.sections)) assert.equal(section.result, 'PASS', section.name)
})

test('runtime action closes state transition and creates the declared handoff', () => {
  const result = executeProcessAction(
    PROCESS_RUNTIME_REFERENCE_DEFINITION,
    PROCESS_RUNTIME_REFERENCE_DEFINITION.contexts[0],
    'COMPLETE_PREPARATION',
  )

  assert.deepEqual(result.transition, { actionCode: 'COMPLETE_PREPARATION', from: 'draft', to: 'prepared' })
  assert.equal(result.context.state, 'prepared')
  assert.equal(result.handoff.fromNode, 'work-item-prepare')
  assert.equal(result.handoff.toNode, 'work-item-review')
  assert.equal(result.handoff.objectType, 'GenericWorkItem')
})

test('RULE-001 rejects a page button without an Action Contract', () => {
  const definition = {
    ...PROCESS_RUNTIME_REFERENCE_DEFINITION,
    pages: [{ pageCode: 'broken-page', nodeCode: 'work-item-prepare', buttonBindings: [{ buttonCode: 'orphan-button', actionCode: 'ORPHAN_ACTION' }] }],
  }
  const report = runProcessAcceptance(definition)

  assert.equal(report.result, 'FAIL')
  assert.equal(report.sections.page.result, 'FAIL')
  assert.ok(report.sections.page.checks.some(check => check.ruleId === 'RULE-001' && check.result === 'FAIL'))
})

test('RULE-004 and RULE-005 reject a missing handoff and missing regression', () => {
  const definition = {
    ...PROCESS_RUNTIME_REFERENCE_DEFINITION,
    handoffs: [],
    regressions: [],
  }
  const report = runProcessAcceptance(definition)

  assert.equal(report.sections.handoff.result, 'FAIL')
  assert.equal(report.sections.regression.result, 'FAIL')
  assert.ok(report.sections.runtime.checks.some(check => check.ruleId === 'RULE-004' && check.result === 'FAIL'))
})

test('runtime refuses an action from an undeclared state', () => {
  const context = { ...PROCESS_RUNTIME_REFERENCE_DEFINITION.contexts[0], state: 'prepared' }
  assert.throws(
    () => executeProcessAction(PROCESS_RUNTIME_REFERENCE_DEFINITION, context, 'COMPLETE_PREPARATION'),
    /ACTION_STATE_NOT_ALLOWED:prepared/,
  )
})

test('Context Contract must bind to a declared node state and object model', () => {
  const definition = {
    ...PROCESS_RUNTIME_REFERENCE_DEFINITION,
    contexts: [{ ...PROCESS_RUNTIME_REFERENCE_DEFINITION.contexts[0], objectType: 'UnrelatedObject' }],
  }
  const report = runProcessAcceptance(definition)

  assert.equal(report.contracts.context.result, 'FAIL')
  assert.ok(report.contracts.context.checks.some(check => check.evidence.endsWith('RUNTIME_BINDING_INVALID')))
})

test('PROCESS-006 requires an executed End-to-End Business Walkthrough', () => {
  const { businessWalkthrough, ...definition } = PROCESS_RUNTIME_REFERENCE_DEFINITION
  assert.ok(businessWalkthrough)
  const report = runProcessAcceptance(definition)

  assert.equal(report.result, 'FAIL')
  assert.equal(report.sections.process006.result, 'FAIL')
  assert.equal(report.sections.process006.checks[0].ruleId, 'PROCESS-006')
})

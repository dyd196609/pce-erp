import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const page = readFileSync(resolve(root, 'src/meta/pages/PdeFoundationPage.vue'), 'utf8')
const component = readFileSync(
  resolve(root, 'src/meta/pages/components/BomVersionReleasePreflightReadback.vue'),
  'utf8',
)
const definitions = readFileSync(resolve(root, 'src/meta/pages/pdePageDefinitions.js'), 'utf8')
const api = readFileSync(resolve(root, 'src/api/pde.js'), 'utf8')

assert.match(page, /BomVersionReleasePreflightReadback/)
assert.match(page, /props\.pageKind === 'bomVersions'/)
assert.match(component, /data-acceptance-id="pde-bom-version-control-chain-readiness"/)
assert.match(component, /Workflow Runtime/)
assert.match(component, /BusinessStateTransition/)
assert.match(component, /Request Idempotency/)
assert.match(component, /职责分离/)
assert.match(component, /等待正式评审授权/)
assert.match(component, /pde-bom-version-formal-review-action/)
assert.match(component, /pde-bom-version-formal-review-readback/)
assert.match(component, /formalReviewDecision/)
assert.match(component, /actor__real_name/)
assert.match(component, /completed_at/)
assert.match(component, /pde-bom-version-submit-review/)
assert.match(component, /canSubmitReview/)
assert.match(component, /accessControlApi\.profile/)
assert.match(component, /transitionEngineering\(/)
assert.match(component, /'bom-versions'.*'reviewed'/s)
assert.match(component, /'pde\.bom_version\.review'/)
assert.match(component, /requestIdentity/)
assert.match(component, /pde-bom-version-formal-release-action/)
assert.match(component, /pde-bom-version-formal-release-readback/)
assert.match(component, /pde-bom-version-submit-release/)
assert.match(component, /canSubmitRelease/)
assert.match(component, /formalReleaseCompleted/)
assert.match(component, /'bom-versions'.*'released'/s)
assert.match(component, /'pde\.bom_version\.release'/)
assert.match(component, /releaseRequestIdentity/)
assert.match(component, /相同版本禁止重复发布/)
assert.match(definitions, /title: 'BOM版本管理'/)
assert.match(definitions, /控制链已接入，现有Workflow配置阻断/)
assert.match(definitions, /独立合法发布人在正式评审完成后发布同一版本/)
assert.match(api, /transitionEngineering\(entity, objectId, targetStatus, reason = '', idempotencyKey = '', action = ''\)/)
assert.match(api, /'Idempotency-Key': idempotencyKey/)

console.log(JSON.stringify({
  gate: 'PDE-NODE8-BOM-VERSION-CONTROL-CHAIN-FRONTEND',
  status: 'PASS',
  checks: 34,
  writeActionCount: 1,
  releaseActionCount: 1,
}, null, 2))

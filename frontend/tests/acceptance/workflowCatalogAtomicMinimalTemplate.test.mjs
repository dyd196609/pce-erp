import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '../..')
const api = readFileSync(path.join(root, 'src/api/workflowDefinitions.js'), 'utf8')
const page = readFileSync(path.join(root, 'src/meta/pages/ProcessDesignerPage.vue'), 'utf8')

const checks = [
  ['atomic API stays in the formal workflow catalog namespace',
    api.includes("url: '/api/workflow/definitions/atomic-minimal-template/'")],
  ['atomic API sends the server-required Idempotency-Key',
    api.includes("'Idempotency-Key': idempotencyKey")],
  ['atomic API declares the existing catalog permission',
    api.includes("permissionCode: 'system.organization.workflow_responsibility.manage'")],
  ['new minimal template submits through the atomic API',
    page.includes('createAtomicMinimalWorkflowTemplate({')],
  ['one dialog owns one stable request identity',
    page.includes("const atomicRequestIdentity = ref('')")
      && page.includes('atomicRequestIdentity.value = createRequestIdentity()')
      && page.includes('}, atomicRequestIdentity.value)')],
  ['retry does not allocate a new key inside submitDefinition',
    !/async function submitDefinition\([\s\S]*createRequestIdentity\(\)[\s\S]*\n}/.test(page)],
  ['new create sends definition and initial node in one request',
    page.includes('node: { ...atomicNodeForm }')
      && page.includes("原子创建Template")],
  ['existing definition maintenance remains preserved',
    page.includes('response = await saveWorkflowDefinition({ ...definitionForm })')],
  ['workflow actions render in a dedicated in-flow region below the page title',
    page.includes('data-acceptance-id="process-designer-actions"')
      && page.indexOf('</header>') < page.indexOf('data-acceptance-id="process-designer-actions"')],
  ['create entry stays visible but fails closed when catalog permission is unavailable',
    page.includes('data-acceptance-id="create-workflow-definition-button"')
      && page.includes(':disabled="catalogAccess !== \'allowed\'"')
      && page.includes('system.organization.workflow_responsibility.manage')],
  ['server-returned definition identity drives readback',
    page.includes('await selectDefinition(response.data.definition)')],
  ['409 is shown as an explicit configuration conflict',
    page.includes("response.meta?.status === 409 ? '配置冲突：'")],
  ['failed requests never show the success message',
    page.indexOf('if (!response.success)') < page.indexOf("ElMessage.success(editing")],
  ['no BOMVersion production sample is hard-coded in the generic capability',
    !page.includes('BOMVersion') && !page.includes('SO202609180003') && !page.includes('CALC-3')
      && !api.includes('BOMVersion') && !api.includes('SO202609180003') && !api.includes('CALC-3')],
]

for (const [name, passed] of checks) {
  assert.equal(passed, true, name)
}

console.log(`workflowCatalogAtomicMinimalTemplate: ${checks.length}/${checks.length} checks passed`)

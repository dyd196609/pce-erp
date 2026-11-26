import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..', '..')
const governance = readFileSync(resolve(root, 'docs', 'governance', 'PCE CODEX开发指令规范管理V1.2.md'), 'utf8')
const agents = readFileSync(resolve(root, 'AGENTS.md'), 'utf8')

const requiredGovernanceTerms = [
  'DELIVERED USER STATE CONTRACT',
  'TESTED USER PATH = PASS',
  'FINAL DELIVERED BROWSER STATE = PASS / NOT GUARANTEED',
  'USER TAKES OVER SAME STATE = GUARANTEED / NOT GUARANTEED',
  'FINAL_DELIVERED_USER_SCREEN_EVIDENCE',
  'DELIVERED_BROWSER_TAB',
  'DELIVERED_URL',
  'DELIVERED_PAGE_TITLE',
  'DELIVERED_ACTIVE_MODULE',
  'DELIVERED_ACTIVE_MODE',
  'DELIVERED_VISIBLE_PRIMARY_CONTENT',
  'DELIVERED_TIMESTAMP',
  'STOP ALL BROWSER ACTIONS',
  'DELIVERED USER STATE = NOT GUARANTEED',
]

const checks = {
  governanceContractComplete: requiredGovernanceTerms.every((term) => governance.includes(term)),
  finalReadbackRequired: governance.includes('最终回复前必须重新读取当前可见浏览器状态'),
  sameContextRequired: governance.includes('同一浏览器上下文与同一 Tab'),
  reportRealityConflictPreserved: governance.includes('用户随后提供的截图或实际观察仍是最高交付事实'),
  projectAutoReadEntry: agents.includes('全文读取 `docs/governance/PCE CODEX开发指令规范管理V1.2.md`')
    && agents.includes('DELIVERED USER STATE CONTRACT'),
}

if (Object.values(checks).some((value) => !value)) {
  console.error(JSON.stringify({ result: 'failed', checks }, null, 2))
  process.exit(1)
}

console.log(JSON.stringify({ result: 'passed', checks, requiredTermCount: requiredGovernanceTerms.length }, null, 2))

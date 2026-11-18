import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const root = new URL('../../', import.meta.url)
const panel = await readFile(new URL('src/meta/components/EngineeringCalculationBatchPanel.vue', root), 'utf8')
const api = await readFile(new URL('src/api/pde.js', root), 'utf8')

test('批量入口继续使用受控业务动作与原批量接口', () => {
  assert.match(panel, /pceBusinessActionLabel\('batch-trial-engineering-sources'\)/)
  assert.match(api, /\/api\/pde\/a1-engineering\/calculations\/batch-reuse\//)
  assert.match(api, /method: 'GET'.*\/api\/pde\/a1-engineering\/calculations\/batch-reuse\//)
  assert.match(api, /method: 'POST'.*\/api\/pde\/a1-engineering\/calculations\/batch-reuse\//)
})

test('响应先校验再替换旧结果，并保留范围过期保护', () => {
  const validateAt = panel.indexOf("const next=readBatchResponse(await pdeApi.calculateSourceBatch(selected,workbookSourceId !== '' && workbookSourceId != null ? { workbookSourceRecordId:Number(workbookSourceId) } : {}),'result')")
  const replaceAt = panel.indexOf('result.value=next')
  assert.ok(validateAt >= 0)
  assert.ok(replaceAt > validateAt)
  assert.match(panel, /resultStale=ref\(false\)/)
  assert.match(panel, /resultStale\.value/)
})

test('新增结果范围进入展示、筛选、排序、下钻和导出合同', () => {
  assert.match(panel, /resultScopeLabel/)
  assert.match(panel, /result\.segments/)
  assert.match(panel, /结果范围/)
  assert.match(panel, /updateFilter\('resultScopeLabel'/)
  assert.match(panel, /exportColumns:/)
  assert.match(panel, /exportCurrent/)
})

test('批量响应继续拒绝不完整总计与分段结构', () => {
  assert.match(panel, /requireList\(data\.totals,'result\.totals'/)
  assert.match(panel, /requireList\(data\.segments,'result\.segments'/)
  assert.match(panel, /!==segment\.resultCount/)
})

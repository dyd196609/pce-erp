import assert from 'node:assert/strict'
import test from 'node:test'
import { ref } from 'vue'
import { usePceEnterpriseListRuntime } from '../../src/meta/runtime/pceEnterpriseListContract.js'

test('shared export runtime uses filtered rows and dispatches one connected-anchor download', () => {
  const stages = []
  const appended = []
  const removed = []
  const revoked = []
  const originalDocument = globalThis.document
  const originalWindow = globalThis.window
  const originalCreateObjectURL = URL.createObjectURL
  const originalRevokeObjectURL = URL.revokeObjectURL
  const anchor = {
    hidden: false,
    href: '',
    download: '',
    clickCount: 0,
    click() { this.clickCount += 1 },
    remove() { removed.push(this) },
  }
  globalThis.document = {
    createElement(name) { assert.equal(name, 'a'); return anchor },
    body: { appendChild(node) { appended.push(node) } },
  }
  globalThis.window = { setTimeout(callback) { callback(); return 1 } }
  URL.createObjectURL = () => 'blob:pce-export-test'
  URL.revokeObjectURL = value => revoked.push(value)
  try {
    const rows = ref([
      { id: 1, project: '竖线净长', unit: 'mm', state: 'calculated', value: '2205.000000' },
      { id: 2, project: '结构封边净长度', unit: 'm', state: 'missing', value: null },
    ])
    const runtime = usePceEnterpriseListRuntime({
      rows,
      filterSchema: [{ field: 'project', label: '核算项目', filterType: 'text' }],
      searchFields: ['project'],
      exportColumns: [{ field: 'project', label: '核算项目' }, { field: 'value', label: '数值' }],
      exportFileName: '工程核算批量结果.csv',
      onExportStage(event) { stages.push(event) },
    })
    runtime.updateFilter('project', '竖线净长')
    const result = runtime.exportCurrent()
    assert.equal(result.rowCount, 1)
    assert.equal(result.columnCount, 2)
    assert.match(result.csv, /"竖线净长","2205\.000000"/)
    assert.doesNotMatch(result.csv, /结构封边净长度/)
    assert.equal(anchor.clickCount, 1)
    assert.deepEqual(appended, [anchor])
    assert.deepEqual(removed, [anchor])
    assert.deepEqual(revoked, ['blob:pce-export-test'])
    assert.deepEqual(stages.map(item => item.stage), ['runtime-received', 'csv-prepared', 'blob-url-created', 'download-click-dispatched'])
  } finally {
    globalThis.document = originalDocument
    globalThis.window = originalWindow
    URL.createObjectURL = originalCreateObjectURL
    URL.revokeObjectURL = originalRevokeObjectURL
  }
})

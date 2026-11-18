import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { ref } from 'vue'
import { usePceEnterpriseListRuntime } from '../../src/meta/runtime/pceEnterpriseListContract.js'

const root = path.resolve(import.meta.dirname, '..', '..', '..')
const page = fs.readFileSync(
  path.join(root, 'frontend/src/meta/components/ProductionFoundationMaintenance.vue'),
  'utf8',
)
const model = fs.readFileSync(path.join(root, 'backend/pde/models.py'), 'utf8')
const service = fs.readFileSync(path.join(root, 'backend/pde/production_foundation_service.py'), 'utf8')
const runtime = fs.readFileSync(
  path.join(root, 'frontend/src/meta/runtime/pceEnterpriseListContract.js'),
  'utf8',
)

test('工程规则唯一业务编码来自服务端rule_code而不是主键或通用code', () => {
  assert.match(model, /rule_code = models\.CharField\("规则编码", max_length=80\)/)
  assert.match(model, /fields=\("company", "rule_code", "version"\)/)
  assert.match(service, /for field in instance\._meta\.concrete_fields/)
  assert.match(page, /selectedEntity\.value === 'engineering-rule-definitions'\) return 'rule_code'/)
  assert.match(page, /selectedEntity\.value === 'engineering-rule-definitions'\) return '规则编码'/)
  assert.doesNotMatch(page, /code\s*\|\|\s*rule_code|rule_code\s*\|\|\s*id/)
})

test('工程规则列表主列完整可读且查询筛选排序导出复用实体列合同', () => {
  assert.match(page, /:primary-width="wave1PrimaryWidth"/)
  assert.match(page, /'engineering-rule-definitions' \? 260 : 220/)
  assert.match(page, /column\.key !== wave1PrimaryField\.value/)
  assert.match(page, /field: 'rule_code', label: '规则编码', filterType: 'text'/)
  assert.match(page, /searchFields: \(\) => currentDefinition\.value\.columns\.map/)
  assert.match(page, /exportColumns: \(\) => currentDefinition\.value\.columns\.map/)
  assert.match(runtime, /resolveRuntimeOption\(options\.searchFields, \[\]\)/)
  assert.match(runtime, /resolveRuntimeOption\(options\.exportColumns, \[\]\)/)
})

test('运行时按当前工程规则列合同搜索完整rule_code', () => {
  const columns = [
    { key: 'rule_code', label: '规则编码' },
    { key: 'rule_name', label: '规则名称' },
    { key: 'version', label: '版本' },
  ]
  const runtimeContract = usePceEnterpriseListRuntime({
    rows: ref([
      { id: 1, rule_code: 'G1-CASING-HEIGHT', rule_name: 'G1门套高', version: 'V1.0' },
      { id: 2, rule_code: 'G1-DOOR-WIDTH', rule_name: 'G1门宽', version: 'V1.0' },
    ]),
    filterSchema: [{ field: 'rule_code', label: '规则编码', filterType: 'text' }],
    searchFields: () => columns.map(column => column.key),
    exportColumns: () => columns.map(column => ({ field: column.key, label: column.label })),
  })

  runtimeContract.quickSearch.value = 'G1-CASING-HEIGHT'
  runtimeContract.applySearch()
  assert.deepEqual(runtimeContract.filteredRows.value.map(row => row.id), [1])
  runtimeContract.clearFilters()
  assert.deepEqual(runtimeContract.filteredRows.value.map(row => row.id), [1, 2])
})

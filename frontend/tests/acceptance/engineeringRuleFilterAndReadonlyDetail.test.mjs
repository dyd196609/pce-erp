import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { ref } from 'vue'
import {
  ENGINEERING_RULE_FILTER_SCHEMA,
  ENGINEERING_RULE_STATUS_OPTIONS,
  canEditEngineeringRule,
  canTransitionEngineeringRule,
} from '../../src/meta/runtime/engineeringRuleListPresentation.js'
import { resolveListFilterOptions } from '../../src/meta/runtime/listFilterRuntime.js'
import { usePceEnterpriseListRuntime } from '../../src/meta/runtime/pceEnterpriseListContract.js'

const root = path.resolve(import.meta.dirname, '..', '..', '..')
const page = fs.readFileSync(
  path.join(root, 'frontend/src/meta/components/ProductionFoundationMaintenance.vue'),
  'utf8',
)
const field = fs.readFileSync(
  path.join(root, 'frontend/src/meta/components/PceAdvancedFilterField.vue'),
  'utf8',
)

const formalRows = [
  { id: 1, rule_code: 'G1-CASING-HEIGHT', rule_name: 'G1门套高', version: 'V1.0', status: 'released' },
  { id: 2, rule_code: 'G1-DOOR-WIDTH', rule_name: 'G1门宽', version: 'V1.0', status: 'released' },
  { id: 3, rule_code: 'G2-DOOR-WIDTH', rule_name: 'G2门宽', version: 'V2.0', status: 'draft' },
]

test('工程规则高级筛选只保留实体正式字段并由授权正式行生成选项', () => {
  assert.deepEqual(ENGINEERING_RULE_FILTER_SCHEMA.map(item => item.field), [
    'rule_code', 'rule_name', 'version', 'status',
  ])
  const withCandidate = [...formalRows, {
    ruleCode: 'APPROVED_SOURCE_NET', version: 'V1', registrationStatus: 'candidate',
  }]
  const codeOptions = resolveListFilterOptions(ENGINEERING_RULE_FILTER_SCHEMA[0], withCandidate)
  assert.deepEqual(codeOptions.map(option => option.value), [
    'G1-CASING-HEIGHT', 'G1-DOOR-WIDTH', 'G2-DOOR-WIDTH',
  ])
  assert.match(codeOptions[0].label, /G1-CASING-HEIGHT · G1门套高/)
  const versionOptions = resolveListFilterOptions(ENGINEERING_RULE_FILTER_SCHEMA[2], withCandidate)
  assert.deepEqual(versionOptions.map(option => option.value), ['V1.0', 'V2.0'])
  assert.deepEqual(ENGINEERING_RULE_STATUS_OPTIONS.map(option => option.label), [
    '草稿', '已评审', '已发布', '已失效',
  ])
})

test('编码和名称下拉允许关键词并保持清空恢复', () => {
  const runtime = usePceEnterpriseListRuntime({
    rows: ref(formalRows),
    filterSchema: ENGINEERING_RULE_FILTER_SCHEMA,
    searchFields: () => ['rule_code', 'rule_name', 'version', 'status'],
    exportColumns: () => [],
  })
  runtime.updateFilter('rule_code', 'door-width')
  assert.deepEqual(runtime.filteredRows.value.map(row => row.id), [2, 3])
  runtime.updateFilter('rule_name', 'G1')
  assert.deepEqual(runtime.filteredRows.value.map(row => row.id), [2])
  runtime.clearFilters()
  assert.deepEqual(runtime.filteredRows.value.map(row => row.id), [1, 2, 3])
  assert.match(field, /:allow-create="Boolean\(field\.allowCustomValue\)"/)
  assert.match(field, /没有匹配项，可继续输入关键词/)
})

test('已发布规则始终可查看且只允许合法草稿编辑或生命周期维护', () => {
  const updateDraft = { 'production.engineering.rule.update_draft': { allowed: true } }
  const release = { 'production.engineering.rule.release': { allowed: true } }
  assert.equal(canEditEngineeringRule({ status: 'draft' }, updateDraft), true)
  assert.equal(canEditEngineeringRule({ status: 'released' }, updateDraft), false)
  assert.equal(canEditEngineeringRule({ status: 'draft' }, release), false)
  assert.equal(canTransitionEngineeringRule({ status: 'released' }, release), true)
  assert.match(page, /@click="viewEngineeringRule\(row\)">查看</)
  assert.match(page, /当前版本已发布，不可直接修改/)
  assert.match(page, /displayValue\(row\[column\.key\], column\)/)
  assert.match(page, /关闭并返回规则列表/)
  assert.match(page, /规则定义正式内容/)
  assert.match(page, /if \(!canSaveCurrentForm\.value\) throw new Error/)
  assert.doesNotMatch(page, /viewEngineeringRule[\s\S]{0,500}saveProductionFoundation/)
})

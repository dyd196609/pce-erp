import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { ref } from 'vue'

import { usePceEnterpriseListRuntime } from '../../src/meta/runtime/pceEnterpriseListContract.js'


const root = path.resolve(import.meta.dirname, '..', '..', '..')
const page = fs.readFileSync(
  path.join(root, 'frontend/src/meta/pages/AccessControlFoundationPage.vue'),
  'utf8',
)
const dialog = fs.readFileSync(
  path.join(root, 'frontend/src/meta/components/OrganizationOperatingAdminDialog.vue'),
  'utf8',
)
const service = fs.readFileSync(
  path.join(root, 'backend/system/organization_operating.py'),
  'utf8',
)

test('员工维护按主键读取历史档案并继续阻断跨公司维护', () => {
  assert.match(service, /select_related\("department_ref", "position_ref"\)/)
  assert.match(service, /\.filter\(pk=row_id\)/)
  assert.match(service, /CROSS_COMPANY_WRITE_FORBIDDEN/)
  assert.doesNotMatch(
    service,
    /Employee\.objects\.select_for_update\(\)\.filter\(\s*pk=row_id, department_ref__company_id=user\.company_id/,
  )
})

test('岗位和主管候选只消费正式有效事实且空候选给出中文原因', () => {
  assert.match(dialog, /employeePositionOptions/)
  assert.match(dialog, /row\.isActive!==false/)
  assert.match(dialog, /formalCandidateBaseEligible/)
  assert.match(dialog, /employeeCompanyId/)
  assert.match(dialog, /row\.companyId===employeeCompanyId\.value/)
  assert.match(dialog, /员工正式公司/)
  assert.match(dialog, /当前操作公司/)
  assert.match(dialog, /未关联正式公司/)
  assert.match(dialog, /未建立正式公司关系时不生成主管候选/)
  assert.doesNotMatch(dialog, /employeeFormalDepartment\.value\?\.companyId\|\|props\.facts\.operatingCompany/)
  assert.match(dialog, /所选部门当前没有已启用正式岗位/)
  assert.match(dialog, /所选正式公司当前没有符合任职规则的主管候选/)
  assert.match(dialog, /不能虚构岗位/)
})

test('组织页标签切换清理排序和选择时不会把表格事件递归回运行时', () => {
  assert.match(page, /@clear-sort="handleTableClearSort"/)
  assert.match(page, /@clear-selection="handleTableClearSelection"/)
  assert.match(page, /handleSort,clearSort:clearTableSort/)
  assert.match(page, /handleSelectionChange,clearSelection:clearTableSelection/)
  assert.match(page, /function handleTableClearSort\(\)\{handleSort\(\)\}/)
  assert.match(page, /function handleTableClearSelection\(\)\{handleSelectionChange\(\[\]\)\}/)
  assert.match(page, /watch\(activeTab,[^\n]*clearFilters\(\);clearTableSort\(\);clearTableSelection\(\)/)
  assert.doesNotMatch(page, /@clear-sort="clearSort"/)
  assert.doesNotMatch(page, /@clear-selection="clearSelection"/)
})

test('员工高级筛选字段与当前列表事实一致并支持可见值查询', () => {
  for (const field of [
    'employeeNo', 'fullName', 'departmentId', 'legacyDepartmentName',
    'positionId', 'legacyPositionName', 'directManagerId',
    'functionalManagerId', 'organizationComplete', 'status',
  ]) {
    assert.match(page, new RegExp(`field:'${field}'`))
  }
  assert.match(page, /watch\(activeTab,[^\n]*clearFilters\(\);clearTableSort\(\);clearTableSelection\(\)/)

  const rows = ref([
    {
      id: 54,
      employeeNo: 'EMP054',
      fullName: '历史身份待确认',
      departmentId: null,
      legacyDepartmentName: '人事部',
      positionId: null,
      legacyPositionName: '人事专员',
      directManagerId: null,
      functionalManagerId: null,
      organizationComplete: false,
      status: 'active',
    },
    {
      id: 6,
      employeeNo: 'EMP006',
      fullName: '正式员工',
      departmentId: 14,
      legacyDepartmentName: '',
      positionId: 27,
      legacyPositionName: '',
      directManagerId: 8,
      functionalManagerId: 9,
      organizationComplete: true,
      status: 'active',
    },
  ])
  const schema = [
    { field: 'employeeNo', label: '员工编号', filterType: 'text' },
    { field: 'fullName', label: '姓名', filterType: 'text' },
    { field: 'legacyDepartmentName', label: '历史部门文字', filterType: 'select', optionsSource: 'current_result' },
    { field: 'organizationComplete', label: '组织数据状态', filterType: 'select', options: [
      { label: '完整', value: true }, { label: '待维护', value: false },
    ] },
  ]
  const runtime = usePceEnterpriseListRuntime({
    rows,
    filterSchema: schema,
    searchFields: ['employeeNo', 'fullName'],
  })

  runtime.updateFilter('employeeNo', 'EMP054')
  assert.deepEqual(runtime.filteredRows.value.map(row => row.id), [54])
  runtime.clearFilters()
  runtime.updateFilter('legacyDepartmentName', '人事部')
  assert.deepEqual(runtime.filteredRows.value.map(row => row.id), [54])
  runtime.clearFilters()
  runtime.updateFilter('organizationComplete', false)
  assert.deepEqual(runtime.filteredRows.value.map(row => row.id), [54])
  runtime.clearFilters()
  runtime.quickSearch.value = '正式员工'
  runtime.applySearch()
  assert.deepEqual(runtime.filteredRows.value.map(row => row.id), [6])
})


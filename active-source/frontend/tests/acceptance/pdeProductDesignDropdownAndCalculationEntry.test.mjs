import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const root = new URL('../../', import.meta.url)
const designPage = await readFile(new URL('src/meta/pages/PdeProductDesignPage.vue', root), 'utf8')
const calculationPage = await readFile(new URL('src/meta/pages/PdeOrderEngineeringCalculationPage.vue', root), 'utf8')
const designService = await readFile(new URL('../backend/pde/product_design_service.py', root), 'utf8')
const requestAdapter = await readFile(new URL('src/api/request.js', root), 'utf8')
const businessNameRegistry = await readFile(new URL('src/meta/governance/businessNameRegistry.js', root), 'utf8')
const pdePageDefinitions = await readFile(new URL('src/meta/pages/pdePageDefinitions.js', root), 'utf8')

test('产品设计列表提供本行可操作下拉并统一颜色版号口径', () => {
  assert.match(designPage, /编辑当前设计/)
  assert.match(designPage, /rowDesignForm\.productCategoryId/)
  assert.match(designPage, /rowDesignForm\.productDefinitionId/)
  assert.match(designPage, /rowDesignForm\.materialId/)
  assert.match(designPage, /rowDesignForm\.visibleConditionCode/)
  assert.match(designPage, /rowDesignForm\.colorVersionOptionId/)
  assert.match(designPage, /颜色\/版号/)
  assert.doesNotMatch(designPage, /颜色\/饰面/)
  assert.match(designPage, /rowDesignBaseline/)
  assert.match(designPage, /rowDesignPatch/)
  assert.match(designPage, /尚未修改本行设计字段/)
  assert.match(designPage, /option\.selectable === false/)
  assert.match(designPage, /rowProcessConfigurationNotice/)
})

test('工程录入与施工单由各自真实表格内部滚动并冻结表头、序号和识别列', () => {
  assert.match(calculationPage, /data-scroll-owner="engineering-input-table"/)
  assert.match(calculationPage, /data-scroll-owner="work-order-table"/)
  assert.equal((calculationPage.match(/<th class="sticky-sequence">序号<\/th>/g) || []).length, 2)
  assert.match(calculationPage, /\.table-wrap thead th\{position:sticky;top:0/)
  assert.match(calculationPage, /\.governed-scroll-table\{max-height:[^}]+overflow:auto/)
  assert.match(calculationPage, /\.governed-scroll-table \.sticky-identity\{position:sticky;left:64px/)
})

test('封边与见光保持两个独立受治理字段', () => {
  assert.match(designPage, /label="封边方式"/)
  assert.match(designPage, /label="见光条件"/)
  assert.match(designService, /"key": "edgeMethod", "label": "封边方式"/)
  assert.match(designService, /"key": "visibleCondition", "label": "见光条件"/)
  assert.doesNotMatch(designPage, /label: '封边方式\/见光条件'/)
  assert.match(calculationPage, /visibleConditions/)
  assert.match(calculationPage, /applyVisibleCondition/)
  assert.match(calculationPage, /edgeModeOriginal/)
})

test('工程核算只把401视为认证失效，403保持页面与登录态', () => {
  assert.match(calculationPage, /const isAuthenticationFailure = error => Number\(error\?\.response\?\.status \|\| 0\) === 401/)
  assert.match(calculationPage, /if \(status === 403\)/)
  assert.match(calculationPage, /auxiliaryReadNotice\.value/)
  assert.match(calculationPage, /当前账号无查看权限/)
  assert.doesNotMatch(calculationPage, /\[401, 403\]\.includes/)
})

test('未指定订单时保持待选择且显式选择后仍消费当前设计事实', () => {
  assert.match(calculationPage, /selection\.salesOrderItemId = null/)
  assert.doesNotMatch(calculationPage, /find\(row => row\.linkedDesignItemCount > 0\)/)
  assert.match(calculationPage, /请选择订单或工程来源/)
  assert.match(calculationPage, /currentDesignInputs/)
  assert.match(calculationPage, /row\.inputAuthority/)
})

test('工程录入对已有产品设计的对象只读消费并返回源头修改', () => {
  assert.match(calculationPage, /designSourceOwned/)
  assert.match(calculationPage, /设计事实唯一来源：产品设计管理/)
  assert.match(calculationPage, /返回产品设计修改/)
  assert.match(calculationPage, /selectedOrder && !designSourceOwned/)
})

test('产品设计批量编辑显式选字段并通过服务端导出Excel', () => {
  assert.match(designPage, /batchSelectedFields/)
  assert.match(designPage, /1 选择一个或多个产品设计项/)
  assert.match(designPage, /影响设计项数量：\{\{ selectedRows\.length \}\}/)
  assert.match(designPage, /影响订单行：\{\{ selectedOrderLines\.join\('、'\) \}\}/)
  assert.match(designPage, /4 确认保存/)
  assert.match(designPage, /exportProductDesignExcel/)
  assert.match(designPage, /\.xlsx/)
  assert.doesNotMatch(designPage, /@export-current="exportCurrent"/)
  assert.match(designPage, /来源已有，正式主数据未匹配/)
  assert.match(designPage, /batchChangePreview/)
  assert.match(designPage, /原值 \{\{ change\.before \}\} → 新值 \{\{ change\.after \}\}/)
  assert.match(designPage, /signature\[0\] !== 0x50 \|\| signature\[1\] !== 0x4B/)
  assert.match(designPage, /if \(response\?\.success === false\)/)
  assert.doesNotMatch(designPage, /new Blob\(\[response\]/)
  assert.match(designPage, /加入批量/)
  assert.match(designPage, /tableRef\.value\?\.toggleRowSelection\?\./)
  assert.match(designPage, /Object\.hasOwn\(source, key\)/)
})

test('产品设计主列表、服务端事实、Excel与导入模板共享同一服务端字段契约', () => {
  const labels = [
    '产品标识', '所属订单行', '设计分组', '来源名称', '空间/安装位置', '来源位置',
    '实物数量', '商业数量', '实物单位', '产品分类', '正式产品定义', '工程对象状态', '材料编码', '材料名称', '物料规格',
    'Routing编码', 'Routing名称', '油漆工艺编码', '油漆工艺名称', '封边方式',
    '见光条件', '颜色/版号', '设计长度', '设计宽度', '第三尺寸', '第三尺寸语义', '设计尺寸单位',
    '配置说明', '设计说明', '五金要求', '玻璃要求', '资料引用', '设计资料性质', '当前修订原因', '设计负责人', '设计状态',
    '设计修订号', '完成状态',
  ]
  for (const label of labels) assert.match(designService, new RegExp(`"label": "${label}"`))
  assert.equal((designService.match(/"label": "/g) || []).filter(Boolean).length >= 38, true)
  assert.match(designPage, /standardListColumns/)
  assert.match(designPage, /listFieldContract\.value\.slice\(1\)/)
  assert.match(designPage, /displayListValue\(row, field\.key\)/)
  assert.doesNotMatch(designPage, /exportFileName: '产品设计计划、内容与完成记录\.csv'/)
  assert.doesNotMatch(designPage, /材料\/工艺编码/)
  assert.doesNotMatch(designPage, /label="设计尺寸"/)
  assert.match(designPage, /label="二、产品设计"/)
  assert.doesNotMatch(designPage, /列表式设计内容/)
  assert.match(designPage, /产品设计当前结果-/)
  assert.match(businessNameRegistry, /'PdeProductDefinitions','product-design-management','产品设计'/)
  assert.match(pdePageDefinitions, /title: '产品设计'/)
  assert.match(designService, /businessMeaning/)
})

test('编辑页面拆分材料、Routing与油漆编码名称并保留未匹配来源值', () => {
  for (const label of ['物料编码', '物料名称', '物料规格', 'Routing编码', 'Routing名称', '油漆工艺编码', '油漆工艺名称']) {
    assert.match(designPage, new RegExp(`label="${label}"`))
  }
  assert.match(designPage, /`\$\{option\.code\} · \$\{option\.name\}`/)
  assert.match(designPage, /未匹配正式工艺路线，保留来源值/)
})

test('单行保存显式提交页面显示的三个尺寸且与批量选择状态隔离', () => {
  assert.match(designPage, /for \(const key of \['designLength', 'designWidth', 'designThickness'\]\) data\[key\] = rowDesignForm\[key\]/)
  const openRowDesign = designPage.match(/function openRowDesign\(row\) \{([\s\S]*?)\n\}/)?.[1] || ''
  assert.doesNotMatch(openRowDesign, /\bcurrent\./)
  assert.match(openRowDesign, /currentValue\('designUomId'\)/)
  assert.match(openRowDesign, /currentValue\('finishOrColor'\)/)
  assert.match(designPage, /invalidPositiveNumber\(rowDesignForm\)/)
  assert.match(designPage, /designItemIds: \[row\.id\]/)
  assert.doesNotMatch(designPage, /saveRowDesign[\s\S]{0,800}selectedRows\.value/)
})

test('首次正式修订提交完整可见表单快照而后续正式修订仍只提交差异', () => {
  assert.match(designPage, /rowDesignRequiresFullSnapshot = computed\(\(\) => Boolean\(rowDesignItem\.value\) && rowDesignItem\.value\.designRevision\?\.designNature !== 'FORMAL'\)/)
  assert.match(designPage, /!rowDesignRequiresFullSnapshot\.value && !Object\.keys\(rowDesignPatch\.value\)\.length/)
  assert.match(designPage, /const requiresFullSnapshot = row\.designRevision\?\.designNature !== 'FORMAL'/)
  assert.match(designPage, /requiresFullSnapshot \? structuredClone\(rowDesignForm\) : nonEmptyDesignPatch\(rowDesignPatch\.value\)/)
})

test('产品设计计划按DES分组选择、校验并保存回读', () => {
  assert.match(designPage, /v-model="selectedDesignGroups"/)
  assert.match(designPage, /group\.designGroup/)
  assert.match(designPage, /DES-01|group\.designGroup/)
  assert.match(designPage, /当前计划影响：\{\{ plannedImpactCount \}\} 个设计项/)
  assert.match(designPage, /请选择需要安排计划的产品设计分组/)
  assert.match(designPage, /保存该设计分组计划/)
  assert.match(designPage, /product-design-plan-register/)
  assert.match(designPage, /planStatusLabel/)
  assert.match(designPage, /计划开始日期/)
  assert.match(designPage, /计划完成日期/)
  assert.match(designPage, /designGroups, \.\.\.planForm/)
  assert.match(designPage, /设计计划保存成功并已从服务端回读/)
  assert.match(designPage, /lastPlanSaveSummary/)
  assert.match(designPage, /最近保存：已安排/)
  assert.doesNotMatch(designPage, /未选择产品。[^\n]*planSaveBlocker/)
  assert.doesNotMatch(designPage, /安排单项产品设计计划/)
  assert.doesNotMatch(designPage, /product-design-row-plan-/)
})

test('工艺配置来自已发布有效Routing且油漆工艺保持独立字段', () => {
  assert.match(designService, /def _formal_routing_queryset/)
  assert.match(designService, /status="released"/)
  assert.match(designService, /"source": "pde\.Routing"/)
  assert.match(designService, /"compatibleItemIds": compatible_ids/)
  assert.match(designService, /NO_FORMAL_ROUTING/)
  assert.match(designPage, /processConfigurationId/)
  assert.match(designPage, /paintProcessTypeId/)
})

test('Customer Engineering不按来源名称自动认定正式产品且无产品仍可编辑', () => {
  assert.match(designService, /"category_id"/)
  assert.match(designService, /status="released"/)
  assert.match(designService, /productDefinitionBindingSource/)
  assert.match(designService, /SOURCE_IDENTITY_ONLY/)
  assert.match(designService, /SOURCE_PRODUCT_UNFORMALIZED/)
  assert.match(designService, /CUSTOMER_ENGINEERING/)
  assert.match(designService, /FORMAL_PRODUCT_LINKED/)
  assert.match(designPage, /rowProductOptions/)
  assert.match(designPage, /当前分类暂无正式产品定义；可继续完成客户订单工程设计/)
  assert.match(designPage, /来源名称不会自动认定为 ProductDefinition/)
  assert.match(designPage, /customer-engineering-identity/)
  assert.match(designPage, /正式产品定义（可选）/)
  assert.doesNotMatch(designPage, /row\.matchResults\?\.productDefinition\?\.matchedId/)
  assert.doesNotMatch(designPage, /rowDesignSaveBlocker[^\n]*!rowDesignForm\.productDefinitionId/)
})

test('统一请求错误保留字段级服务端详情', () => {
  assert.match(requestAdapter, /res\.data\?\.error\?\.details/)
})

test('商业数量与实物数量定义分离且工程端只读消费设计事实', () => {
  assert.match(designPage, /商业数量：<\/b>销售合同数量/)
  assert.match(designPage, /实物数量：<\/b>实际设计、生产对象数量/)
  assert.match(designPage, /柜门 6 件、侧板 2 件、层板 3 件/)
  assert.match(designPage, /禁止混算/)
  assert.match(designPage, /工程数据录入只负责转换、核算、校验和输出/)
})

import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { buildBomMaterialDetailReadback } from '../../src/meta/runtime/bomMaterialDetailReadback.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const projectRoot = path.resolve(frontendRoot, '..')
const readFrontend = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const readProject = relative => fs.readFileSync(path.join(projectRoot, relative), 'utf8')

function formalShape() {
  const rows = Array.from({ length: 5 }, (_, itemIndex) => {
    const bomItemId = 100 + itemIndex
    const uomCode = ['PCS', 'M', 'M2', 'M', 'M'][itemIndex]
    const sourceRequirements = Array.from({ length: 5 }, (_, sourceIndex) => {
      const requirementId = 1000 + itemIndex * 5 + sourceIndex
      return {
        requirementId,
        designItemId: 2000 + sourceIndex,
        designItemNo: `DES-TEST-${sourceIndex + 1}`,
        materialId: 3000 + itemIndex,
        materialCode: `TEST-MAT-${itemIndex + 1}`,
        materialName: `测试物料${itemIndex + 1}`,
        quantity: '1.000000',
        uomCode,
        uomDisplay: uomCode,
        structuralRole: `ROLE-${itemIndex + 1}`,
        calculationId: 4000,
        calculationNo: 'CALC-TEST',
        sourceDetailId: 5000 + requirementId,
        sourceDetailName: `测试来源${sourceIndex + 1}`,
        sourceFactId: 6000 + requirementId,
        mappingRuleId: 7000 + requirementId,
        mappingRuleCode: `RULE-TEST-${requirementId}`,
        relationStatusCode: 'LINKED',
        relationStatusLabel: '已建立正式来源关系',
        companyId: 1,
        orderNo: 'SO-TEST',
        orderLineNo: 1,
        bomItemId,
      }
    })
    return {
      bomItemId,
      lineNo: itemIndex + 1,
      materialId: 3000 + itemIndex,
      materialCode: `TEST-MAT-${itemIndex + 1}`,
      materialName: `测试物料${itemIndex + 1}`,
      materialSpecification: itemIndex === 1 ? '' : `规格${itemIndex + 1}`,
      materialSpecificationLabel: itemIndex === 1 ? '未维护' : `规格${itemIndex + 1}`,
      quantity: '5.000000',
      uomCode,
      uomDisplay: uomCode,
      sourceRequirementCount: 5,
      sourceRequirements,
    }
  })
  return {
    id: 3,
    companyId: 1,
    orderNo: 'SO-TEST',
    orderLineNo: 1,
    sourceCalculationId: 4000,
    latestMaterialCount: 5,
    sourceRequirementCount: 25,
    bomMaterialDetails: rows,
  }
}

test('01 服务端五个BOMItem按原顺序形成五行物料明细', () => {
  const readback = buildBomMaterialDetailReadback(formalShape())
  assert.equal(readback.result, 'PASS')
  assert.equal(readback.rows.length, 5)
  assert.deepEqual(readback.rows.map(row => row.lineNo), [1, 2, 3, 4, 5])
})

test('02 二十五条Requirement只存在于所属BOMItem分组', () => {
  const readback = buildBomMaterialDetailReadback(formalShape())
  assert.equal(readback.sourceRequirementCount, 25)
  assert.deepEqual(readback.rows.map(row => row.sourceRequirements.length), [5, 5, 5, 5, 5])
})

test('03 Requirement身份全局不重复', () => {
  const readback = buildBomMaterialDetailReadback(formalShape())
  const ids = readback.rows.flatMap(row => row.sourceRequirements.map(source => source.requirementId))
  assert.equal(new Set(ids).size, 25)
})

test('04 物料编码名称数量和单位均保留服务端投影', () => {
  const row = buildBomMaterialDetailReadback(formalShape()).rows[0]
  assert.deepEqual(
    [row.materialCode, row.materialName, row.quantity, row.uomCode],
    ['TEST-MAT-1', '测试物料1', '5.000000', 'PCS'],
  )
})

test('05 规格缺失明确显示未维护且不猜值', () => {
  const row = buildBomMaterialDetailReadback(formalShape()).rows[1]
  assert.equal(row.materialSpecification, '')
  assert.equal(row.materialSpecificationLabel, '未维护')
})

test('06 公司越界立即FAIL_CLOSED', () => {
  const detail = formalShape()
  detail.bomMaterialDetails[0].sourceRequirements[0].companyId = 2
  assert.equal(buildBomMaterialDetailReadback(detail).result, 'FAIL_CLOSED')
})

test('07 订单越界立即FAIL_CLOSED', () => {
  const detail = formalShape()
  detail.bomMaterialDetails[0].sourceRequirements[0].orderNo = 'SO-OTHER'
  assert.equal(buildBomMaterialDetailReadback(detail).result, 'FAIL_CLOSED')
})

test('08 订单行越界立即FAIL_CLOSED', () => {
  const detail = formalShape()
  detail.bomMaterialDetails[0].sourceRequirements[0].orderLineNo = 2
  assert.equal(buildBomMaterialDetailReadback(detail).result, 'FAIL_CLOSED')
})

test('09 核算越界立即FAIL_CLOSED', () => {
  const detail = formalShape()
  detail.bomMaterialDetails[0].sourceRequirements[0].calculationId = 9999
  assert.equal(buildBomMaterialDetailReadback(detail).result, 'FAIL_CLOSED')
})

test('10 物料或单位错配立即FAIL_CLOSED', () => {
  const detail = formalShape()
  detail.bomMaterialDetails[0].sourceRequirements[0].uomCode = 'KG'
  assert.equal(buildBomMaterialDetailReadback(detail).result, 'FAIL_CLOSED')
})

test('11 非正式关联状态立即FAIL_CLOSED', () => {
  const detail = formalShape()
  detail.bomMaterialDetails[0].sourceRequirements[0].relationStatusCode = 'UNLINKED'
  assert.equal(buildBomMaterialDetailReadback(detail).result, 'FAIL_CLOSED')
})

test('12 重复Requirement立即FAIL_CLOSED', () => {
  const detail = formalShape()
  detail.bomMaterialDetails[1].sourceRequirements[0].requirementId = 1000
  assert.equal(buildBomMaterialDetailReadback(detail).result, 'FAIL_CLOSED')
})

test('13 前端在既有BOM及BOM版本详情弹窗复用同一只读明细', () => {
  const page = readFrontend('src/meta/pages/PdeFoundationPage.vue')
  // The existing BOM-version extension shares this exact component; requiring
  // the older BOM-only condition would reject the preserved formal contract.
  assert.match(page, /<BomMaterialDetailReadback\s+v-if="\['boms', 'bomVersions'\]\.includes\(props\.pageKind\) && detailRow"/)
  assert.match(page, /:detail="detailRow"/)
  assert.match(page, /min\(1320px, 96vw\)/)
})

test('14 BOM明细提供查看来源且不提供生成编辑删除发布动作', () => {
  const component = readFrontend('src/meta/pages/components/BomMaterialDetailReadback.vue')
  assert.match(component, /'查看来源'/)
  assert.match(component, /data-write-action-count="0"/)
  assert.doesNotMatch(component, />\s*(生成BOM|编辑|删除|发布)\s*</)
})

test('15 Requirement展开区显示用户要求的完整追溯字段', () => {
  const component = readFrontend('src/meta/pages/components/BomMaterialDetailReadback.vue')
  for (const label of ['Requirement ID', '设计对象', '物料', '数量 / 单位', '结构角色', '核算', '来源明细', '映射规则', '关系状态']) {
    assert.match(component, new RegExp(label))
  }
})

test('16 两层表格都由自身横向滚动容器承担窄屏可用性', () => {
  const component = readFrontend('src/meta/pages/components/BomMaterialDetailReadback.vue')
  assert.match(component, /\.material-table-scroll,\.source-table-scroll \{ width:100%; overflow-x:auto; \}/)
  assert.match(component, /@media \(max-width: 760px\)/)
})

test('17 后端沿正式关系只读投影且既有列表端点不引入生成调用', () => {
  const projection = readProject('backend/pde/product_bom_detail_projection.py')
  const views = readProject('backend/pde/views.py')
  const block = views.slice(views.indexOf('class ProductBomListView'), views.indexOf('class RoutingListView'))
  assert.match(projection, /BOMItemSourceRequirement\.objects\.select_related/)
  assert.match(projection, /material_requirement__source_detail/)
  assert.match(projection, /material_requirement__calculation__sales_order_item__sales_order/)
  assert.match(block, /project_product_bom_material_detail/)
  assert.doesNotMatch(block, /generate_bom\(/)
  assert.doesNotMatch(block, /\.create\(/)
  assert.doesNotMatch(block, /\.save\(/)
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

import {
  PRODUCT_DESIGN_INPUT_FIELDS,
  productDesignSelectionKey,
  summarizeProductDesignSelection,
} from '../../src/meta/runtime/productDesignComprehensiveRuntime.js'

const root = new URL('../../', import.meta.url)
const page = await readFile(new URL('src/meta/pages/PdeProductDesignPage.vue', root), 'utf8')
const service = await readFile(new URL('../backend/pde/product_design_service.py', root), 'utf8')
const importer = await readFile(new URL('../backend/pde/product_design_import_service.py', root), 'utf8')

const row = (overrides = {}) => ({
  id: 3, productCategoryId: 7, productDefinitionId: null, physicalUomId: 11,
  matchResults: { material: { matchedId: 21 }, processConfiguration: { matchedId: '31' }, paintProcess: { matchedId: 41 }, edgeMethod: { matchedId: 51 } },
  existingDesign: { designLength: '2300', designWidth: '940', designThickness: '18', designUomId: 12, designNotes: '原说明' },
  designRevision: null,
  ...overrides,
})

test('单项完整回填并明确区分实物单位与设计尺寸单位', () => {
  const result = summarizeProductDesignSelection([row()])
  assert.equal(result.form.physicalUomId, 11)
  assert.equal(result.form.designUomId, 12)
  assert.equal(result.form.designWidth, '940')
  assert.deepEqual(result.mixedFields, [])
})

test('多项一致值回填、混合值只显示状态且不会成为业务值', () => {
  const result = summarizeProductDesignSelection([
    row(), row({ id: 4, existingDesign: { ...row().existingDesign, designWidth: '800' } }),
  ])
  assert.equal(result.form.designLength, '2300')
  assert.equal(result.form.designWidth, null)
  assert.ok(result.mixedFields.includes('designWidth'))
  assert.notEqual(result.form.designWidth, '多个值')
  assert.equal(productDesignSelectionKey([{ id: 4 }, { id: 3 }]), '3|4')
})

test('综合区、单行弹窗、字段契约与导入兼容均使用受控实现', () => {
  assert.equal(PRODUCT_DESIGN_INPUT_FIELDS.length, 18)
  assert.match(page, /产品综合设计区/)
  assert.match(page, /product-design-comprehensive-targets/)
  assert.match(page, /designForm\.designUomId/)
  assert.match(page, /comprehensiveDrafts/)
  assert.match(page, /handleDesignSelectionChange/)
  assert.match(page, /rowDesignForm\.designUomId/)
  assert.match(service, /"key": "physicalUnit", "label": "实物单位"/)
  assert.match(service, /"key": "designDimensionUnit", "label": "设计尺寸单位"/)
  assert.match(service, /DESIGN_UOM_CONVERSION_UNAVAILABLE/)
  assert.match(service, /DESIGN_DIMENSION_SEMANTIC_MIXED/)
  assert.match(importer, /LEGACY_HEADERS/)
  assert.match(importer, /source\["实物单位"\] = source\.pop\("单位"/)
})

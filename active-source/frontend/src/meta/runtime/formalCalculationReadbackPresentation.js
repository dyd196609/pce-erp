// Formatting only: values and saved-state labels must come from server facts.
export const FORMAL_READBACK_CONTRACT = 'PDE-FORMAL-CALCULATION-READBACK-V1'

export function formalSavedState(state, failed = false) {
  if (!failed && state?.contractVersion === FORMAL_READBACK_CONTRACT) return state
  return {
    label: failed ? '正式核算保存状态读取失败' : '正式核算保存状态待读取',
    explanation: failed ? '当前读取失败，不使用旧状态代替。' : '等待服务端持久化状态读回；不以预检或实例状态推断。',
  }
}

// The list deliberately omits trace. Read the existing detail endpoint and
// reject stale selection responses or mismatched identities before presenting it.
export async function readSelectedCalculationDetail(row, read, isCurrent) {
  const detail = await read(row.id)
  if (!isCurrent()) return null
  for (const field of ['id', 'companyId', 'salesOrderItemId', 'orderEngineeringInstanceId', 'sourceRecordId']) {
    if (detail?.[field] !== row[field]) throw new Error('正式记录详情身份与当前选择不一致，已停止展示。')
  }
  if (detail.savedPageContext) {
    for (const field of ['companyId', 'salesOrderItemId', 'orderEngineeringInstanceId', 'sourceRecordId']) {
      if (detail.savedPageContext.readStatus !== 'read_failed' && detail.savedPageContext[field] !== detail[field]) throw new Error('冻结页面资料与核算记录范围不一致，已停止展示。')
    }
    if (detail.savedPageContext.calculationId !== detail.id) throw new Error('冻结页面资料不属于所选核算记录。')
  }
  return detail
}

export function savedPageContextForSelection(calculation, line) {
  const context = calculation?.savedPageContext
  if (!context || context.contractVersion !== 'PDE-SAVED-CALCULATION-CONTEXT-V1'
      || context.readStatus !== 'loaded' || context.calculationId !== calculation.id
      || context.salesOrderItemId !== line?.salesOrderItemId
      || context.companyId !== calculation.companyId || context.sourceRecordId !== calculation.sourceRecordId
      || context.orderEngineeringInstanceId !== calculation.orderEngineeringInstanceId) return null
  return context
}

const labels = {
  object: '已确认基线对象', ruleInputs: '实际计算输入', sourceCell: '来源单元格', sourceFormula: '来源公式',
  baselineItemId: '基线项ID', baselineContentHash: '基线项内容指纹', designItemId: '设计对象ID',
  designItemNo: '设计对象编号', sourceAttributeId: '来源属性ID', sourceRecordId: '来源ID',
  sourceSheet: '来源工作表', sourceRow: '来源行', sourceKey: '来源位置', revision: '设计修订',
  designLength: '设计长度／高度', designWidth: '设计宽度', designThickness: '设计厚度',
  designUomId: '尺寸单位ID', physicalQuantity: '实物数量', physicalUomId: '实物单位ID', physicalUom: '实物单位',
  productCategoryId: '产品分类ID', productDefinitionId: '产品定义ID', materialId: '材料ID',
  materialProcessTypeId: '材料工艺ID', paintProcessTypeId: '油漆工艺ID', edgeMethodId: '封边方式ID',
  edgeMethod: '封边方式', visibleCondition: '见光条件', finishOrColor: '饰面／颜色', paintProcess: '油漆工艺',
  routingProcessCode: '工艺路线', processConfigurationCode: '工艺配置', inputAuthority: '输入依据',
  sourceVersion: '来源版本', sourceContentHash: '来源内容指纹',
  opening_height: '门洞高度', opening_width: '门洞宽度', casing_height: '门套高度', casing_width: '门套宽度',
  door_height: '门扇高度', door_width: '门扇宽度', order_quantity: '订单数量',
  name: '名称', key: '字段', value: '值', unit: '单位', unitDimension: '量纲',
}

function display(value) {
  if (value === null || value === undefined || value === '') return '未提供'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (Array.isArray(value)) return value.length ? value.map(display).join('；') : '无'
  if (typeof value === 'object') {
    if (Object.hasOwn(value, 'decimal')) return display(value.decimal)
    if (Object.hasOwn(value, 'value')) return `${display(value.value)}${value.unit ? ` ${value.unit}` : ''}`
    return Object.entries(value).map(([key, item]) => `${labels[key] || key}：${display(item)}`).join('；') || '无'
  }
  return value === 'CONFIRMED_ORDER_ENGINEERING_BASELINE_ITEM' ? '已确认整单工程基线项' : String(value)
}

export function calculationInputLines(snapshot) {
  if (!snapshot || !Object.keys(snapshot).length) return ['无输入快照']
  return Object.entries(snapshot).flatMap(([key, value]) => {
    if (key === 'object' && value && typeof value === 'object') {
      const native = value.sourceIdentity?.type === 'NATIVE_DESIGN_REVISION'
      return Object.entries(value).map(([field, item]) => `${labels[field] || field}：${native && ['sourceSheet', 'sourceRow'].includes(field) ? '不适用／原生设计来源' : display(item)}`)
    }
    if (key === 'ruleInputs' && Array.isArray(value)) {
      return value.length ? value.map(item => `实际计算输入 · ${item.name || item.key || '未命名字段'}${item.name && item.key ? `（${item.key}）` : ''}：${display(item)}${item.sourceCell ? `；来源单元格：${item.sourceCell}` : ''}`) : ['实际计算输入：无']
    }
    const native = snapshot.object?.sourceIdentity?.type === 'NATIVE_DESIGN_REVISION'
    return [`${labels[key] || key}：${native && ['sourceCell', 'sourceFormula'].includes(key) ? '不适用／原生设计来源' : display(value)}`]
  })
}

export function calculationTraceRows(calculation) {
  const trace = calculation?.trace || {}, source = trace.sourceReference, baseline = trace.baselineReference
  if (!source && !baseline) return [] // Preserve legacy records; do not invent a formal baseline.
  return [
    { label: '订单／订单行／实例', value: `${display(baseline?.orderNo)}；订单行ID ${display(calculation.salesOrderItemId)}；实例ID ${display(calculation.orderEngineeringInstanceId)}` },
    { label: '工程来源', value: `ID ${display(source?.id)}；版本 ${display(source?.sourceVersion)}` },
    { label: '已验证基线', value: `${display(baseline?.baselineNo)}（ID ${display(baseline?.id)}）；本记录对象 ${display(baseline?.selectedItemCount)} 项` },
    { label: '对象／修订范围', value: (trace.objectInputSnapshot || []).map(item => `${display(item.designItemNo)}／R${display(item.input?.revision)}（基线项 ${display(item.baselineItemId)}；${display(item.sourceKey)}）`).join('；') || '未提供' },
    { label: '正式规则', value: (trace.ruleGraphSnapshot || []).map(item => `${display(item.ruleCode)}@${display(item.version)}（ID ${display(item.id)}）`).join('；') || '未提供' },
  ]
}



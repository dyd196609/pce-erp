import {
  addOperationLog,
  getFoundationState,
  resetFoundationState,
  saveFoundationState,
} from './manufacturingFoundationStore.js'

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function today() {
  return new Date().toISOString().slice(0, 10)
}

function code(prefix, index) {
  return `${prefix}-${String(index).padStart(6, '0')}`
}

function ensureCount(collection, target, factory) {
  const next = [...(collection || [])]
  for (let index = next.length; index < target; index += 1) {
    next.push(factory(index + 1))
  }
  return next
}

function markGenerated(state) {
  const parameters = state.systemParameters || []
  const existing = parameters.find((item) => item.key === 'sampleDataGenerated')
  if (existing) {
    existing.value = 'true'
    existing.updatedAt = new Date().toISOString()
  } else {
    parameters.push({
      id: 'param-sample-data-generated',
      key: 'sampleDataGenerated',
      name: '制造业样例数据已生成',
      value: 'true',
      status: 'enabled',
    })
  }
  state.systemParameters = parameters
}

function generated(state) {
  return (state.systemParameters || []).some((item) => item.key === 'sampleDataGenerated' && String(item.value) === 'true')
}

function buildLocations(warehouseIndex, count) {
  return Array.from({ length: count }, (_, index) => ({
    id: `loc-sample-${warehouseIndex}-${index + 1}`,
    code: code('LOC', (warehouseIndex - 1) * count + index + 1),
    name: `样例库位${warehouseIndex}-${index + 1}`,
    status: 'enabled',
  }))
}

function calcWorkYears(hireDate, leaveDate) {
  const start = new Date(hireDate)
  const end = leaveDate ? new Date(leaveDate) : new Date()
  return Number(((end.getTime() - start.getTime()) / (365.25 * 24 * 60 * 60 * 1000)).toFixed(1))
}

export function buildManufacturingSampleState(baseState = getFoundationState()) {
  const state = clone(baseState)
  const departments = ['生产部', '采购部', '销售部', '仓储部', '质量部', '计划部', '财务部', '管理部', '印刷事业部', '整木事业部']
  const roles = ['生产操作员', '采购员', '销售专员', '仓管员', '质量检验员', '计划员', '财务专员', '车间主管', '印刷机长', '木工技师']
  const shifts = ['shift-day', 'shift-night', 'shift-flex']
  const materialCategories = [
    '纸张', '油墨', '胶水', '覆膜材料', '包装材料', '印刷半成品', '印刷成品',
    '板材', '木皮', '五金', '油漆', '胶黏剂', '封边条', '门板', '柜体', '线条', '成品家具',
    '辅料', '备品备件', '工装耗材',
  ]
  const supplierTypes = ['纸张', '油墨', '板材', '五金', '油漆', '胶水', '包装', '设备维护', '物流', '辅料']
  const workCenterNames = [
    '设计制版', '切纸', '印刷', '覆膜', '烫金', '模切', '糊盒', '印刷包装', '印刷质检',
    '开料', '封边', 'CNC', '钻孔', '砂光', '涂装', '木皮压贴', '组装', '整木包装', '整木质检',
    '备料', '来料检验', '成品检验', '设备维护', '返工处理', '试制中心', '计划排程', '外协处理', '仓储拣配', '出库复核', '安全库存',
  ]
  const processNames = [
    '印前制版', '切纸', '四色印刷', '专色印刷', '覆膜', '烫金', '模切', '糊盒', '印刷包装', '印刷质检',
    '开料', '封边', 'CNC加工', '钻孔', '砂光', '底漆', '面漆', '木皮压贴', '柜体组装', '门板装配',
    '备料', '来料检验', '成品检验', '包装', '设备点检', '返修', '外协检验', '入库复核', '拣配', '出库复核',
  ]

  state.departments = ensureCount(state.departments, departments.length, (index) => ({
    id: `dept-sample-${index}`,
    name: departments[index - 1],
    owner: `负责人${index}`,
    duty: `${departments[index - 1]}基础职责`,
  }))
  state.employees = ensureCount(state.employees, 200, (index) => {
    const hireDate = `202${index % 5}-0${(index % 9) + 1}-15`
    const leaveDate = index % 23 === 0 ? `2025-12-${String((index % 20) + 1).padStart(2, '0')}` : ''
    const status = leaveDate ? 'resigned' : ['active', 'leave', 'borrowed'][index % 3]
    return {
      id: `emp-sample-${index}`,
      employeeNo: code('EMP', index),
      name: `样例员工${index}`,
      idCardNo: `110101199${index % 10}0101${String(index).padStart(4, '0')}`,
      nativePlace: ['江苏苏州', '浙江杭州', '广东佛山', '山东青岛'][index % 4],
      department: departments[index % departments.length],
      role: roles[index % roles.length],
      jobGrade: `G${(index % 6) + 1}`,
      jobLevel: `L${(index % 4) + 1}`,
      status,
      phone: `13810${String(index).padStart(6, '0')}`,
      email: `employee${index}@example.com`,
      hireDate,
      leaveDate,
      workYears: calcWorkYears(hireDate, leaveDate),
      skills: [roles[index % roles.length]],
      certificates: [],
      shiftId: shifts[index % shifts.length],
      remark: index % 2 ? '印刷行业样例岗位' : '全屋定制/整木样例岗位',
    }
  })
  state.customers = ensureCount(state.customers, 100, (index) => ({
    id: `cus-sample-${index}`,
    code: code('CUS', index),
    name: `${index % 2 ? '印刷包装客户' : '家居定制客户'}${index}`,
    contact: `客户经理${index}`,
    phone: `13930${String(index).padStart(6, '0')}`,
    creditLevel: ['A', 'B', 'C'][index % 3],
    creditLimit: 100000 + index * 5000,
    status: 'enabled',
  }))
  state.suppliers = ensureCount(state.suppliers, 100, (index) => ({
    id: `sup-sample-${index}`,
    code: code('SUP', index),
    name: `${supplierTypes[index % supplierTypes.length]}供应商${index}`,
    contact: `供应商联系人${index}`,
    phone: `13920${String(index).padStart(6, '0')}`,
    grade: ['A', 'B', 'C'][index % 3],
    onTimeRate: 85 + (index % 15),
    leadTimeDays: 3 + (index % 15),
    status: 'enabled',
  }))
  state.workCenters = ensureCount(state.workCenters, 30, (index) => ({
    id: `wc-sample-${index}`,
    code: code('WC', index),
    name: workCenterNames[(index - 1) % workCenterNames.length],
    department: index <= 9 ? '印刷事业部' : index <= 19 ? '整木事业部' : '生产部',
    capacity: 60 + (index % 12) * 10,
    standardLaborCapacity: 6 + (index % 10),
    machineHours: 40 + (index % 20),
    laborCost: 35 + (index % 30),
    status: 'enabled',
  }))
  state.warehouses = ensureCount(state.warehouses, 10, (index) => ({
    id: `wh-sample-${index}`,
    code: code('WH', index),
    name: `样例仓库${index}`,
    owner: `仓库负责人${index}`,
    status: 'enabled',
    locations: buildLocations(index, 10),
  })).map((warehouse, index) => ({
    ...warehouse,
    code: warehouse.code?.startsWith('WH-') ? warehouse.code : code('WH', index + 1),
    status: 'enabled',
    locations: ensureCount(warehouse.locations || [], 10, (locationIndex) => ({
      id: `loc-sample-${index + 1}-${locationIndex}`,
      code: code('LOC', index * 10 + locationIndex),
      name: `样例库位${index + 1}-${locationIndex}`,
      status: 'enabled',
    })),
  }))
  state.productCategories = ensureCount(state.productCategories, 40, (index) => ({
    id: `pc-sample-${index}`,
    categoryCode: code('CAT', index),
    categoryName: materialCategories[index % materialCategories.length],
    industryType: index % 3 === 0 ? 'printing' : index % 3 === 1 ? 'wholeHouseWood' : 'general',
    parentId: '',
    status: 'enabled',
    remark: '样例产品类别',
  }))
  state.materials = ensureCount(state.materials, 300, (index) => {
    const safetyStock = 50 + (index % 80)
    const warehouse = state.warehouses[index % state.warehouses.length]
    const location = warehouse?.locations?.[index % (warehouse.locations.length || 1)]
    const category = materialCategories[index % materialCategories.length]
    return {
      id: `mat-sample-${index}`,
      code: code('MAT', index),
      name: `${category}物料${index}`,
      specification: `SP-${String(index).padStart(4, '0')}`,
      materialType: index % 5 === 0 ? '成品' : index % 3 === 0 ? '半成品' : '原材料',
      category,
      productCategory: state.productCategories[index % state.productCategories.length]?.categoryName || category,
      baseUnit: index % 3 === 0 ? '张' : index % 3 === 1 ? '件' : '米',
      purchaseUnit: index % 3 === 0 ? '令' : index % 3 === 1 ? '件' : '米',
      stockUnit: index % 3 === 0 ? '张' : index % 3 === 1 ? '件' : '米',
      unit: index % 3 === 0 ? '张' : index % 3 === 1 ? '件' : '米',
      safetyStock,
      maxStock: safetyStock + 300 + (index % 100),
      defaultWarehouseId: warehouse?.id || '',
      defaultLocationId: location?.id || '',
      mrpEnabled: index % 4 !== 0,
      status: 'enabled',
    }
  })
  state.processes = ensureCount(state.processes, 80, (index) => ({
    id: `proc-sample-${index}`,
    processCode: code('PROC', index),
    processName: `${processNames[index % processNames.length]}${index}`,
    industryType: index % 3 === 0 ? 'printing' : index % 3 === 1 ? 'wholeHouseWood' : 'general',
    workCenterId: state.workCenters[index % state.workCenters.length]?.id,
    standardHours: Number((0.5 + (index % 12) * 0.25).toFixed(2)),
    skillRequired: processNames[index % processNames.length],
    qualityCheckRequired: index % 4 === 0,
    status: 'enabled',
    remark: '样例工序',
  }))
  state.routings = ensureCount(state.routings, 30, (index) => ({
    id: `routing-sample-${index}`,
    routingCode: code('ROUTE', index),
    routingName: `${index <= 15 ? '印刷' : '整木'}标准工艺路线${index}`,
    industryType: index <= 15 ? 'printing' : 'wholeHouseWood',
    productCategory: state.productCategories[index % state.productCategories.length]?.categoryName || '',
    materialId: state.materials[index % state.materials.length]?.id || '',
    version: 'V1',
    status: 'enabled',
    remark: '样例工艺路线',
  }))
  const requiredSteps = []
  state.routings.forEach((routing, routingIndex) => {
    for (let step = 1; step <= 6; step += 1) {
      requiredSteps.push({
        id: `rstep-sample-${routingIndex + 1}-${step}`,
        routingId: routing.id,
        stepNo: step * 10,
        processId: state.processes[(routingIndex + step) % state.processes.length]?.id,
        workCenterId: state.workCenters[(routingIndex + step) % state.workCenters.length]?.id,
        standardHours: Number((0.5 + step * 0.35).toFixed(2)),
        setupHours: 0.2,
        transferHours: 0.1,
        qualityCheckPoint: step === 1 || step === 6,
        remark: '样例工艺步骤',
      })
    }
  })
  const existingStepIds = new Set((state.routingSteps || []).map((item) => item.id))
  state.routingSteps = [...(state.routingSteps || []), ...requiredSteps.filter((item) => !existingStepIds.has(item.id))]
  state.equipment = ensureCount(state.equipment, 80, (index) => ({
    id: `eq-sample-${index}`,
    equipmentCode: code('EQP', index),
    equipmentName: `${index % 3 === 0 ? '印刷设备' : index % 3 === 1 ? '木工设备' : '通用设备'}${index}`,
    industryType: index % 3 === 0 ? 'printing' : index % 3 === 1 ? 'wholeHouseWood' : 'general',
    workCenterId: state.workCenters[index % state.workCenters.length]?.id,
    equipmentType: index % 3 === 0 ? '印刷设备' : index % 3 === 1 ? '木工设备' : '通用设备',
    status: 'enabled',
    capacityPerHour: 50 + (index % 20) * 10,
    remark: '样例设备',
  }))
  state.warningRules = ensureCount(state.warningRules, 30, (index) => ({
    id: `warn-sample-${index}`,
    name: `样例预警规则${index}`,
    target: ['SCM', 'WMS', 'MRP', 'MES', 'QMS', 'CRM', 'KPI'][index % 7],
    condition: '超过阈值',
    level: ['低', '中', '高'][index % 3],
    status: 'enabled',
  }))

  state.materialSupplierRelations = ensureCount(state.materialSupplierRelations, Math.max(500, state.materials.length), (index) => ({
    id: `msr-sample-${index}`,
    relationCode: code('MSR', index),
    materialId: state.materials[(index - 1) % state.materials.length]?.id,
    supplierId: state.suppliers[(index - 1) % state.suppliers.length]?.id,
    priority: (index % 3) + 1,
    isPrimary: true,
    leadTimeDays: 3 + (index % 15),
    qualityLevel: ['A', 'B', 'C'][index % 3],
    onTimeRate: 85 + (index % 15),
    status: 'enabled',
    remark: '样例供应关系',
  }))
  const primarySeen = new Set()
  state.materialSupplierRelations = state.materialSupplierRelations.map((relation) => {
    if (primarySeen.has(relation.materialId)) return { ...relation, isPrimary: false }
    primarySeen.add(relation.materialId)
    return { ...relation, isPrimary: true }
  })
  state.supplierMaterialPrices = ensureCount(state.supplierMaterialPrices, 500, (index) => {
    const relation = state.materialSupplierRelations[(index - 1) % state.materialSupplierRelations.length]
    return {
      id: `smp-sample-${index}`,
      supplierMaterialCode: code('SMP', index),
      supplierId: relation?.supplierId,
      materialId: relation?.materialId,
      minOrderQty: 1 + (index % 20),
      price: Number((8 + (index % 200) * 1.37).toFixed(2)),
      taxRate: 13,
      currency: 'CNY',
      deliveryDays: relation?.leadTimeDays || 7,
      paymentTerms: index % 2 ? '月结30天' : '月结45天',
      effectiveDate: today(),
      expiryDate: '2027-12-31',
      isDefault: relation?.isPrimary || false,
      status: 'enabled',
      remark: '样例供应商物料价格',
    }
  })

  state.codeSequences = {
    employee: state.employees.length,
    material: state.materials.length,
    customer: state.customers.length,
    supplier: state.suppliers.length,
    workCenter: state.workCenters.length,
    warehouse: state.warehouses.length,
    location: state.warehouses.reduce((sum, warehouse) => sum + (warehouse.locations?.length || 0), 0),
    process: state.processes.length,
    routing: state.routings.length,
    equipment: state.equipment.length,
    productCategory: state.productCategories.length,
    supplierMaterialPrice: state.supplierMaterialPrices.length,
    materialSupplierRelation: state.materialSupplierRelations.length,
  }

  markGenerated(state)
  return state
}

export function generateManufacturingSampleData() {
  const current = getFoundationState()
  if (generated(current)) {
    return { generated: false, state: current, message: '样例数据已经生成，无需重复生成。' }
  }
  const next = buildManufacturingSampleState(current)
  saveFoundationState(next)
  addOperationLog({ action: '生成制造业样例数据', targetType: 'sampleData', targetId: 'manufacturing', summary: '生成印刷与全屋定制/整木行业样例数据' })
  return { generated: true, state: getFoundationState(), message: '制造业样例数据已生成。' }
}

export function resetAndGenerateSampleData() {
  resetFoundationState()
  const next = buildManufacturingSampleState(getFoundationState())
  saveFoundationState(next)
  addOperationLog({ action: '重置并生成制造业样例数据', targetType: 'sampleData', targetId: 'manufacturing', summary: '重置基础资料后重新生成样例数据' })
  return { generated: true, state: getFoundationState(), message: '制造业样例数据已重置并重新生成。' }
}


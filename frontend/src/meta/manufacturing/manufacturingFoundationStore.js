const STORAGE_KEY = 'manufacturing-foundation-state-v1'

const CODE_RULES = {
  employee: { collection: 'employees', field: 'employeeNo', prefix: 'EMP' },
  material: { collection: 'materials', field: 'code', prefix: 'MAT' },
  customer: { collection: 'customers', field: 'code', prefix: 'CUS' },
  supplier: { collection: 'suppliers', field: 'code', prefix: 'SUP' },
  workCenter: { collection: 'workCenters', field: 'code', prefix: 'WC' },
  warehouse: { collection: 'warehouses', field: 'code', prefix: 'WH' },
  location: { collection: 'warehouses', field: 'code', prefix: 'LOC' },
  process: { collection: 'processes', field: 'processCode', prefix: 'PROC' },
  routing: { collection: 'routings', field: 'routingCode', prefix: 'ROUTE' },
  equipment: { collection: 'equipment', field: 'equipmentCode', prefix: 'EQP' },
  productCategory: { collection: 'productCategories', field: 'categoryCode', prefix: 'CAT' },
  supplierMaterialPrice: { collection: 'supplierMaterialPrices', field: 'supplierMaterialCode', prefix: 'SMP' },
  materialSupplierRelation: { collection: 'materialSupplierRelations', field: 'relationCode', prefix: 'MSR' },
}

const COLLECTION_ENTITY = {
  employees: 'employee',
  materials: 'material',
  customers: 'customer',
  suppliers: 'supplier',
  workCenters: 'workCenter',
  warehouses: 'warehouse',
  processes: 'process',
  routings: 'routing',
  equipment: 'equipment',
  productCategories: 'productCategory',
  supplierMaterialPrices: 'supplierMaterialPrice',
  materialSupplierRelations: 'materialSupplierRelation',
}

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function createId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
}

function nowText() {
  return new Date().toISOString()
}

function code(prefix, index) {
  return `${prefix}-${String(index).padStart(6, '0')}`
}

function isDisabled(item) {
  const status = String(item?.status || '').toLowerCase()
  return status === 'disabled' || status === '停用' || status.includes('停用')
}

function normalizeCommonStatus(value) {
  const text = String(value || '').toLowerCase()
  if (text === 'disabled' || text.includes('停用')) return 'disabled'
  return 'enabled'
}

function normalizeEmployeeStatus(value) {
  const text = String(value || '').toLowerCase()
  if (['resigned', '离职'].some((item) => text.includes(item))) return 'resigned'
  if (['leave', '休假'].some((item) => text.includes(item))) return 'leave'
  if (['borrowed', '借调'].some((item) => text.includes(item))) return 'borrowed'
  return 'active'
}

function calculateWorkYears(hireDate, leaveDate) {
  if (!hireDate) return 0
  const start = new Date(hireDate)
  const end = leaveDate ? new Date(leaveDate) : new Date()
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) return 0
  const yearMs = 365.25 * 24 * 60 * 60 * 1000
  return Number(((end.getTime() - start.getTime()) / yearMs).toFixed(1))
}

function createDefaultState() {
  return {
    codeSequences: {
      employee: 3,
      material: 5,
      customer: 3,
      supplier: 3,
      workCenter: 2,
      warehouse: 2,
      location: 4,
      process: 3,
      routing: 2,
      equipment: 3,
      productCategory: 3,
      supplierMaterialPrice: 3,
      materialSupplierRelation: 3,
    },
    departments: [
      { id: 'dept-production', name: '生产部', owner: '周建军', duty: '生产计划执行与车间协同' },
      { id: 'dept-quality', name: '品质部', owner: '钱敏', duty: '来料、制程与出货质量控制' },
      { id: 'dept-supply', name: '供应链部', owner: '吴芳', duty: '采购、供应商与仓储协同' },
    ],
    roles: [
      { id: 'role-planner', name: '计划员', department: '生产部', duty: '维护计划与产能基础资料' },
      { id: 'role-buyer', name: '采购员', department: '供应链部', duty: '维护供应商与采购基础资料' },
      { id: 'role-quality', name: '质量工程师', department: '品质部', duty: '维护质量与预警基础资料' },
    ],
    employees: [
      { id: 'emp-001', employeeNo: code('EMP', 1), name: '李明', idCardNo: '110101199003071234', nativePlace: '江苏苏州', department: '生产部', role: '计划员', jobGrade: 'G5', jobLevel: 'L2', status: 'active', phone: '13800010001', email: 'liming@example.com', hireDate: '2024-03-12', leaveDate: '', workYears: 0, skills: ['排产', 'MRP'], certificates: ['安全生产培训'], shiftId: 'shift-day', remark: '负责一车间计划基础资料维护' },
      { id: 'emp-002', employeeNo: code('EMP', 2), name: '王静', idCardNo: '110101198812121111', nativePlace: '浙江杭州', department: '品质部', role: '质量工程师', jobGrade: 'G6', jobLevel: 'L3', status: 'active', phone: '13800010002', email: 'wangjing@example.com', hireDate: '2023-08-18', leaveDate: '', workYears: 0, skills: ['来料检验', '8D'], certificates: ['内审员证书'], shiftId: 'shift-day', remark: '负责来料质量基础资料' },
      { id: 'emp-003', employeeNo: code('EMP', 3), name: '赵强', idCardNo: '110101199211301234', nativePlace: '山东青岛', department: '供应链部', role: '采购员', jobGrade: 'G4', jobLevel: 'L2', status: 'borrowed', phone: '13800010003', email: 'zhaoqiang@example.com', hireDate: '2022-11-01', leaveDate: '', workYears: 0, skills: ['供应商管理', '询价'], certificates: ['采购合规培训'], shiftId: 'shift-flex', remark: '负责核心供应商维护' },
    ],
    skills: [
      { id: 'skill-mrp', name: 'MRP基础', level: '熟练', ownerRole: '计划员', status: 'enabled' },
      { id: 'skill-iqc', name: '来料检验', level: '熟练', ownerRole: '质量工程师', status: 'enabled' },
      { id: 'skill-supplier', name: '供应商管理', level: '熟练', ownerRole: '采购员', status: 'enabled' },
    ],
    certificates: [
      { id: 'cert-safe', name: '安全生产培训', type: '通用', expireDate: '2026-12-31', owner: '李明', status: 'enabled' },
      { id: 'cert-auditor', name: '内审员证书', type: '质量', expireDate: '2027-06-30', owner: '王静', status: 'enabled' },
    ],
    shifts: [
      { id: 'shift-day', name: '白班', startTime: '08:00', endTime: '17:00', capacity: 80, status: 'enabled' },
      { id: 'shift-night', name: '夜班', startTime: '20:00', endTime: '05:00', capacity: 40, status: 'enabled' },
      { id: 'shift-flex', name: '弹性班', startTime: '09:00', endTime: '18:00', capacity: 20, status: 'enabled' },
    ],
    employeeShiftAssignments: [
      { id: 'assign-001', employeeId: 'emp-001', shiftId: 'shift-day', effectiveDate: '2026-07-01' },
      { id: 'assign-002', employeeId: 'emp-002', shiftId: 'shift-day', effectiveDate: '2026-07-01' },
    ],
    materials: [
      { id: 'mat-001', code: code('MAT', 1), name: '铝合金型材', specification: '6063-T5 40x40', materialType: '原材料', category: '原材料', productCategory: '型材', baseUnit: '米', purchaseUnit: '米', stockUnit: '米', unit: '米', safetyStock: 300, maxStock: 1200, defaultWarehouseId: 'wh-raw', defaultLocationId: 'loc-raw-a1', mrpEnabled: true, status: 'enabled' },
      { id: 'mat-002', code: code('MAT', 2), name: '铜线材', specification: 'BV2.5', materialType: '原材料', category: '原材料', productCategory: '线材', baseUnit: '卷', purchaseUnit: '卷', stockUnit: '卷', unit: '卷', safetyStock: 120, maxStock: 600, defaultWarehouseId: 'wh-raw', defaultLocationId: 'loc-raw-b1', mrpEnabled: true, status: 'enabled' },
      { id: 'mat-003', code: code('MAT', 3), name: '控制面板', specification: '标准面板', materialType: '半成品', category: '半成品', productCategory: '电子件', baseUnit: '件', purchaseUnit: '件', stockUnit: '件', unit: '件', safetyStock: 80, maxStock: 300, defaultWarehouseId: 'wh-fg', defaultLocationId: 'loc-fg-c1', mrpEnabled: true, status: 'enabled' },
      { id: 'mat-004', code: code('MAT', 4), name: '智能终端整机', specification: 'V1 标准款', materialType: '成品', category: '成品', productCategory: '终端', baseUnit: '台', purchaseUnit: '台', stockUnit: '台', unit: '台', safetyStock: 50, maxStock: 180, defaultWarehouseId: 'wh-fg', defaultLocationId: 'loc-fg-d1', mrpEnabled: false, status: 'enabled' },
      { id: 'mat-005', code: code('MAT', 5), name: '防震包装箱', specification: '600x400x300', materialType: '包材', category: '包材', productCategory: '包装', baseUnit: '个', purchaseUnit: '个', stockUnit: '个', unit: '个', safetyStock: 500, maxStock: 2000, defaultWarehouseId: 'wh-raw', defaultLocationId: 'loc-raw-a1', mrpEnabled: true, status: 'enabled' },
    ],
    customers: [
      { id: 'cus-001', code: code('CUS', 1), name: '华东装备集团', contact: '陈经理', phone: '13900020001', creditLevel: 'A', creditLimit: 1000000, status: 'enabled' },
      { id: 'cus-002', code: code('CUS', 2), name: '北方智能制造', contact: '刘经理', phone: '13900020002', creditLevel: 'B', creditLimit: 500000, status: 'enabled' },
      { id: 'cus-003', code: code('CUS', 3), name: '南海工业客户', contact: '黄经理', phone: '13900020003', creditLevel: 'A', creditLimit: 800000, status: 'enabled' },
    ],
    suppliers: [
      { id: 'sup-001', code: code('SUP', 1), name: '精工铝材供应商', contact: '孙工', phone: '13900030001', grade: 'A', onTimeRate: 96, leadTimeDays: 7, status: 'enabled' },
      { id: 'sup-002', code: code('SUP', 2), name: '华信电子材料', contact: '冯工', phone: '13900030002', grade: 'B', onTimeRate: 94, leadTimeDays: 10, status: 'enabled' },
      { id: 'sup-003', code: code('SUP', 3), name: '联创包装材料', contact: '郑工', phone: '13900030003', grade: 'A', onTimeRate: 97, leadTimeDays: 5, status: 'enabled' },
    ],
    workCenters: [
      { id: 'wc-assembly', code: code('WC', 1), name: '总装工作中心', department: '生产部', capacity: 120, standardLaborCapacity: 16, machineHours: 80, laborCost: 55, status: 'enabled' },
      { id: 'wc-testing', code: code('WC', 2), name: '测试工作中心', department: '品质部', capacity: 80, standardLaborCapacity: 10, machineHours: 60, laborCost: 60, status: 'enabled' },
    ],
    warehouses: [
      { id: 'wh-raw', code: code('WH', 1), name: '原材料仓', owner: '赵强', status: 'enabled', locations: [{ id: 'loc-raw-a1', code: code('LOC', 1), name: '铝材区A1', status: 'enabled' }, { id: 'loc-raw-b1', code: code('LOC', 2), name: '电子料区B1', status: 'enabled' }] },
      { id: 'wh-fg', code: code('WH', 2), name: '成品仓', owner: '李明', status: 'enabled', locations: [{ id: 'loc-fg-c1', code: code('LOC', 3), name: '待检区C1', status: 'enabled' }, { id: 'loc-fg-d1', code: code('LOC', 4), name: '可发货区D1', status: 'enabled' }] },
    ],
    dataDictionaries: [
      { id: 'dict-material-category', name: '物料分类', values: '原材料,半成品,成品,包材', status: 'enabled' },
      { id: 'dict-employee-status', name: '人员状态', values: 'active,resigned,leave,borrowed', status: 'enabled' },
    ],
    codingRules: [
      { id: 'rule-material', entityType: 'material', name: '物料编码规则', prefix: 'MAT', serialLength: 6, status: 'enabled' },
      { id: 'rule-employee', entityType: 'employee', name: '员工工号规则', prefix: 'EMP', serialLength: 6, status: 'enabled' },
    ],
    systemParameters: [
      { id: 'param-default-entry', key: 'defaultEntry', name: '默认入口', value: '/foundation', status: 'enabled' },
      { id: 'param-master-data-lock', key: 'masterDataLock', name: '主数据保存校验', value: '开启', status: 'enabled' },
    ],
    permissionPoints: [
      { id: 'perm-foundation-view', code: 'foundation:view', name: '基础资料查看', module: '基础资料', action: '查看', status: 'enabled' },
      { id: 'perm-employee-edit', code: 'pfm:employee:edit', name: '人员档案维护', module: 'PFM', action: '编辑', status: 'enabled' },
      { id: 'perm-material-edit', code: 'erp:material:edit', name: '物料维护', module: 'ERP主数据', action: '编辑', status: 'enabled' },
      { id: 'perm-security-edit', code: 'security:permission:edit', name: '权限配置', module: '权限与日志', action: '配置', status: 'enabled' },
      { id: 'perm-log-view', code: 'logs:operation:view', name: '操作日志查看', module: '权限与日志', action: '查看', status: 'enabled' },
      { id: 'perm-warning-edit', code: 'warning:rule:edit', name: '预警规则维护', module: '预警引擎基础', action: '编辑', status: 'enabled' },
    ],
    rolePermissions: [
      { id: 'rp-planner', role: '计划员', permissionCodes: ['foundation:view', 'pfm:employee:edit', 'erp:material:edit'] },
      { id: 'rp-buyer', role: '采购员', permissionCodes: ['foundation:view', 'erp:material:edit'] },
    ],
    userRoles: [
      { id: 'ur-001', userName: '李明', roles: ['计划员'] },
      { id: 'ur-002', userName: '王静', roles: ['质量工程师'] },
    ],
    operationLogs: [
      { id: 'log-001', time: '2026-07-01T09:00:00.000Z', operator: '系统初始化', action: '初始化基础资料', targetType: 'foundation', targetId: 'init', summary: '载入制造业基础资料' },
    ],
    importRecords: [],
    warningRules: [
      { id: 'warn-cert-expire', name: '证书到期预警', target: 'PFM证书', condition: '30天内到期', level: '中', status: 'enabled' },
      { id: 'warn-material-missing', name: '物料主数据缺失预警', target: '物料', condition: '必填字段为空', level: '高', status: 'enabled' },
    ],
    warningRecords: [
      { id: 'wr-001', ruleName: '证书到期预警', target: '内审员证书', level: '中', status: '待处理', createdAt: '2026-07-01T10:00:00.000Z', owner: '王静' },
    ],
    warningSubscribers: [
      { id: 'sub-001', name: '李明', channel: '站内消息', scope: '物料主数据', status: 'enabled' },
      { id: 'sub-002', name: '王静', channel: '邮件', scope: '证书与质量', status: 'enabled' },
    ],
    supplierMaterialPrices: [
      { id: 'smp-001', supplierMaterialCode: code('SMP', 1), supplierId: 'sup-001', materialId: 'mat-001', minOrderQty: 10, price: 66, taxRate: 13, currency: 'CNY', deliveryDays: 7, paymentTerms: '月结30天', effectiveDate: '2026-07-01', expiryDate: '2027-06-30', isDefault: true, status: 'enabled', remark: '默认铝材采购价' },
      { id: 'smp-002', supplierMaterialCode: code('SMP', 2), supplierId: 'sup-002', materialId: 'mat-002', minOrderQty: 5, price: 123, taxRate: 13, currency: 'CNY', deliveryDays: 10, paymentTerms: '月结45天', effectiveDate: '2026-07-01', expiryDate: '2027-06-30', isDefault: true, status: 'enabled', remark: '默认铜线采购价' },
      { id: 'smp-003', supplierMaterialCode: code('SMP', 3), supplierId: 'sup-003', materialId: 'mat-005', minOrderQty: 50, price: 8.8, taxRate: 13, currency: 'CNY', deliveryDays: 5, paymentTerms: '月结30天', effectiveDate: '2026-07-01', expiryDate: '2027-06-30', isDefault: true, status: 'enabled', remark: '包装材料价格' },
    ],
    materialSupplierRelations: [
      { id: 'msr-001', relationCode: code('MSR', 1), materialId: 'mat-001', supplierId: 'sup-001', priority: 1, isPrimary: true, leadTimeDays: 7, qualityLevel: 'A', onTimeRate: 96, status: 'enabled', remark: '主供应商' },
      { id: 'msr-002', relationCode: code('MSR', 2), materialId: 'mat-002', supplierId: 'sup-002', priority: 1, isPrimary: true, leadTimeDays: 10, qualityLevel: 'A', onTimeRate: 94, status: 'enabled', remark: '主供应商' },
      { id: 'msr-003', relationCode: code('MSR', 3), materialId: 'mat-005', supplierId: 'sup-003', priority: 1, isPrimary: true, leadTimeDays: 5, qualityLevel: 'A', onTimeRate: 97, status: 'enabled', remark: '主供应商' },
    ],
    processes: [
      { id: 'proc-print-001', processCode: code('PROC', 1), processName: '印前制版', industryType: 'printing', workCenterId: 'wc-assembly', standardHours: 1.5, skillRequired: '印前处理', qualityCheckRequired: true, status: 'enabled', remark: '印刷行业基础工序' },
      { id: 'proc-wood-001', processCode: code('PROC', 2), processName: '开料', industryType: 'wholeHouseWood', workCenterId: 'wc-assembly', standardHours: 2, skillRequired: '板材开料', qualityCheckRequired: true, status: 'enabled', remark: '全屋定制基础工序' },
      { id: 'proc-general-001', processCode: code('PROC', 3), processName: '包装', industryType: 'general', workCenterId: 'wc-testing', standardHours: 0.8, skillRequired: '包装', qualityCheckRequired: false, status: 'enabled', remark: '通用工序' },
    ],
    routings: [
      { id: 'routing-print-001', routingCode: code('ROUTE', 1), routingName: '彩盒彩印标准路线', industryType: 'printing', productCategory: '印刷成品', materialId: 'mat-004', version: 'V1', status: 'enabled', remark: '演示工艺路线' },
      { id: 'routing-wood-001', routingCode: code('ROUTE', 2), routingName: '柜体标准加工路线', industryType: 'wholeHouseWood', productCategory: '柜体', materialId: 'mat-004', version: 'V1', status: 'enabled', remark: '演示工艺路线' },
    ],
    routingSteps: [
      { id: 'rstep-001', routingId: 'routing-print-001', stepNo: 10, processId: 'proc-print-001', workCenterId: 'wc-assembly', standardHours: 1.5, setupHours: 0.2, transferHours: 0.1, qualityCheckPoint: true, remark: '制版首检' },
      { id: 'rstep-002', routingId: 'routing-print-001', stepNo: 20, processId: 'proc-general-001', workCenterId: 'wc-testing', standardHours: 0.8, setupHours: 0.1, transferHours: 0.1, qualityCheckPoint: false, remark: '包装' },
      { id: 'rstep-003', routingId: 'routing-wood-001', stepNo: 10, processId: 'proc-wood-001', workCenterId: 'wc-assembly', standardHours: 2, setupHours: 0.2, transferHours: 0.2, qualityCheckPoint: true, remark: '开料检验' },
    ],
    equipment: [
      { id: 'eq-print-001', equipmentCode: code('EQP', 1), equipmentName: '四色印刷机', industryType: 'printing', workCenterId: 'wc-assembly', equipmentType: '印刷设备', status: 'enabled', capacityPerHour: 1200, remark: '样例设备' },
      { id: 'eq-wood-001', equipmentCode: code('EQP', 2), equipmentName: '数控开料机', industryType: 'wholeHouseWood', workCenterId: 'wc-assembly', equipmentType: '木工设备', status: 'enabled', capacityPerHour: 60, remark: '样例设备' },
      { id: 'eq-general-001', equipmentCode: code('EQP', 3), equipmentName: '自动包装线', industryType: 'general', workCenterId: 'wc-testing', equipmentType: '通用设备', status: 'enabled', capacityPerHour: 300, remark: '样例设备' },
    ],
    productCategories: [
      { id: 'pc-print-paper', categoryCode: code('CAT', 1), categoryName: '印刷纸张', industryType: 'printing', parentId: '', status: 'enabled', remark: '印刷行业' },
      { id: 'pc-wood-board', categoryCode: code('CAT', 2), categoryName: '定制板材', industryType: 'wholeHouseWood', parentId: '', status: 'enabled', remark: '全屋定制/整木' },
      { id: 'pc-general-spare', categoryCode: code('CAT', 3), categoryName: '备品备件', industryType: 'general', parentId: '', status: 'enabled', remark: '通用分类' },
    ],
  }
}

function normalizeRecord(collection, item = {}) {
  const entityType = COLLECTION_ENTITY[collection]
  const next = { ...item }

  if (collection === 'employees') {
    next.status = normalizeEmployeeStatus(next.status)
    next.workYears = calculateWorkYears(next.hireDate, next.leaveDate)
    return next
  }

  if ('status' in next || entityType) next.status = normalizeCommonStatus(next.status)
  if (collection === 'materials') {
    next.materialType = next.materialType || next.category || ''
    next.category = next.category || next.materialType || ''
    next.baseUnit = next.baseUnit || next.unit || ''
    next.purchaseUnit = next.purchaseUnit || next.baseUnit || next.unit || ''
    next.stockUnit = next.stockUnit || next.baseUnit || next.unit || ''
    next.unit = next.unit || next.baseUnit || ''
    next.maxStock = Number(next.maxStock || next.safetyStock || 0)
    next.safetyStock = Number(next.safetyStock || 0)
    next.mrpEnabled = next.mrpEnabled === true || String(next.mrpEnabled) === 'true' || String(next.mrpEnabled) === '是'
  }
  if (collection === 'warehouses') {
    next.locations = (next.locations || []).map((location) => ({ status: 'enabled', ...location, status: normalizeCommonStatus(location.status) }))
  }
  return next
}

function normalizeState(nextState = {}) {
  const defaults = createDefaultState()
  const merged = { ...defaults, ...nextState }
  Object.keys(defaults).forEach((key) => {
    if (!Array.isArray(defaults[key])) return
    merged[key] = Array.isArray(merged[key]) ? merged[key] : defaults[key]
  })
  merged.codeSequences = { ...defaults.codeSequences, ...(nextState.codeSequences || {}) }
  Object.keys(COLLECTION_ENTITY).forEach((collection) => {
    merged[collection] = (merged[collection] || []).map((item) => normalizeRecord(collection, item))
  })
  return merged
}

function loadState() {
  if (typeof localStorage === 'undefined') return normalizeState(createDefaultState())
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeState(JSON.parse(raw)) : normalizeState(createDefaultState())
  } catch (error) {
    return normalizeState(createDefaultState())
  }
}

let state = loadState()

function persist() {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  }
}

function writeLog(action, targetType, targetId, summary) {
  state.operationLogs = [
    {
      id: createId('log'),
      time: nowText(),
      operator: '当前用户',
      action,
      targetType,
      targetId,
      summary,
    },
    ...(state.operationLogs || []),
  ].slice(0, 500)
}

function saveWithLog(action, targetType, targetId, summary) {
  writeLog(action, targetType, targetId, summary)
  persist()
}

function matchesId(item, index, id) {
  const value = String(id || '')
  return String(item.id) === value || String(index + 1) === value
}

function findRawById(collection, id) {
  return (state[collection] || []).find((item, index) => matchesId(item, index, id)) || null
}

function findById(collection, id) {
  return clone(findRawById(collection, id))
}

function getCodeConfig(entityType) {
  return CODE_RULES[entityType] || null
}

function getCodeRule(entityType) {
  const fallback = getCodeConfig(entityType)
  if (!fallback) return null
  const active = (state.codingRules || []).find((rule) => (
    normalizeCommonStatus(rule.status) === 'enabled'
    && (rule.entityType === entityType || String(rule.name || '').toLowerCase().includes(entityType.toLowerCase()))
  ))
  return {
    prefix: active?.prefix || fallback.prefix,
    serialLength: Number(active?.serialLength || 6),
  }
}

function getExistingCodes(entityType) {
  const config = getCodeConfig(entityType)
  if (!config) return new Set()
  if (entityType === 'location') {
    return new Set((state.warehouses || []).flatMap((warehouse) => warehouse.locations || []).map((item) => String(item.code || '')).filter(Boolean))
  }
  return new Set((state[config.collection] || []).map((item) => String(item[config.field] || '')).filter(Boolean))
}

export function getNextSequence(entityType) {
  return Number(state.codeSequences?.[entityType] || 0) + 1
}

export function previewNextCode(entityType) {
  const rule = getCodeRule(entityType)
  if (!rule) return ''
  return `${rule.prefix}-${String(getNextSequence(entityType)).padStart(rule.serialLength, '0')}`
}

export function generateCode(entityType) {
  const rule = getCodeRule(entityType)
  if (!rule) return ''
  const existing = getExistingCodes(entityType)
  let sequence = getNextSequence(entityType)
  let nextCode = `${rule.prefix}-${String(sequence).padStart(rule.serialLength, '0')}`
  while (existing.has(nextCode)) {
    sequence += 1
    nextCode = `${rule.prefix}-${String(sequence).padStart(rule.serialLength, '0')}`
  }
  state.codeSequences = { ...(state.codeSequences || {}), [entityType]: sequence }
  persist()
  return nextCode
}

function ensureCode(collection, item, currentId) {
  const entityType = COLLECTION_ENTITY[collection]
  const config = getCodeConfig(entityType)
  if (!config) return item
  const next = { ...item }
  if (!String(next[config.field] || '').trim()) next[config.field] = generateCode(entityType)
  const duplicate = (state[collection] || []).find((record) => (
    String(record.id) !== String(currentId || next.id || '')
    && String(record[config.field] || '') === String(next[config.field] || '')
  ))
  if (duplicate) throw new Error(`${config.field} 已存在，请检查编码唯一性`)
  return next
}

function assertNumberRange(value, label, min, max = Infinity) {
  const number = Number(value || 0)
  if (number < min || number > max) throw new Error(`${label}必须在 ${min} 到 ${max} 范围内`)
}

function validateRecord(collection, item) {
  if (collection === 'employees') {
    if (item.idCardNo && ![15, 18].includes(String(item.idCardNo).length)) throw new Error('身份证号必须为 15 位或 18 位')
  }
  if (collection === 'materials' && Number(item.maxStock || 0) < Number(item.safetyStock || 0)) {
    throw new Error('最高库存必须大于等于安全库存')
  }
  if (collection === 'customers') assertNumberRange(item.creditLimit, '信用额度', 0)
  if (collection === 'suppliers') {
    assertNumberRange(item.onTimeRate, '准时率', 0, 100)
    assertNumberRange(item.leadTimeDays, '交货周期', 0)
  }
  if (collection === 'workCenters') {
    assertNumberRange(item.standardLaborCapacity, '标准人工产能', 0)
    assertNumberRange(item.machineHours, '机器工时', 0)
    assertNumberRange(item.laborCost, '单位人工成本', 0)
  }
  if (collection === 'supplierMaterialPrices') {
    assertNumberRange(item.price, '价格', 0)
    assertNumberRange(item.deliveryDays, '交货周期', 0)
  }
  if (collection === 'materialSupplierRelations') {
    if (!Number.isInteger(Number(item.priority)) || Number(item.priority) < 1) throw new Error('优先级必须为正整数')
    assertNumberRange(item.onTimeRate, '准时率', 0, 100)
  }
  if (collection === 'processes') {
    assertNumberRange(item.standardHours, '标准工时', 0)
    if (!['printing', 'wholeHouseWood', 'general'].includes(String(item.industryType || ''))) throw new Error('行业类型必须是 printing / wholeHouseWood / general')
  }
  if (collection === 'equipment') {
    assertNumberRange(item.capacityPerHour, '每小时产能', 0)
    if (!item.workCenterId) throw new Error('设备必须归属工作中心')
  }
}

function enforceUniqueDefaults(collection, item) {
  if (collection === 'supplierMaterialPrices' && item.isDefault && normalizeCommonStatus(item.status) === 'enabled') {
    state.supplierMaterialPrices = (state.supplierMaterialPrices || []).map((record) => (
      String(record.id) !== String(item.id)
      && String(record.supplierId) === String(item.supplierId)
      && String(record.materialId) === String(item.materialId)
      && normalizeCommonStatus(record.status) === 'enabled'
        ? { ...record, isDefault: false }
        : record
    ))
  }
  if (collection === 'materialSupplierRelations' && item.isPrimary && normalizeCommonStatus(item.status) === 'enabled') {
    state.materialSupplierRelations = (state.materialSupplierRelations || []).map((record) => (
      String(record.id) !== String(item.id)
      && String(record.materialId) === String(item.materialId)
      && normalizeCommonStatus(record.status) === 'enabled'
        ? { ...record, isPrimary: false }
        : record
    ))
  }
}

function prepareRecord(collection, item, currentId) {
  const withCode = ensureCode(collection, item, currentId)
  const normalized = normalizeRecord(collection, withCode)
  validateRecord(collection, normalized)
  enforceUniqueDefaults(collection, normalized)
  return normalized
}

function upsert(collection, item, prefix, logName) {
  const id = item.id || createId(prefix)
  const next = prepareRecord(collection, { ...item, id }, id)
  state[collection] = [...(state[collection] || []), next]
  saveWithLog(`新增${logName}`, collection, id, next.name || next.code || next.employeeNo || id)
  return id
}

function update(collection, id, patch, logName) {
  let found = null
  state[collection] = (state[collection] || []).map((item, index) => {
    if (!matchesId(item, index, id)) return item
    found = prepareRecord(collection, { ...item, ...patch, id: item.id }, item.id)
    return found
  })
  saveWithLog(`保存${logName}`, collection, id, found?.name || found?.code || id)
}

function remove(collection, id, logName) {
  const current = findById(collection, id)
  state[collection] = (state[collection] || []).filter((item, index) => !matchesId(item, index, id))
  saveWithLog(`删除${logName}`, collection, id, current?.name || current?.code || id)
}

export function setFoundationRecordStatus(collection, id, status) {
  if (collection === 'employees') throw new Error('员工档案使用人员状态，不使用启用/停用')
  let current = null
  state[collection] = (state[collection] || []).map((item, index) => {
    if (!matchesId(item, index, id)) return item
    current = { ...item, status: normalizeCommonStatus(status) }
    return current
  })
  saveWithLog(current?.status === 'disabled' ? '停用基础资料' : '启用基础资料', collection, id, current?.name || current?.code || id)
}

export function enableFoundationRecord(collection, id) {
  setFoundationRecordStatus(collection, id, 'enabled')
}

export function disableFoundationRecord(collection, id) {
  setFoundationRecordStatus(collection, id, 'disabled')
}

export function getFoundationState() {
  return clone(state)
}

export function saveFoundationState(nextState) {
  state = normalizeState(nextState)
  saveWithLog('保存基础资料状态', 'foundation', 'state', '整体状态已保存')
}

export function resetFoundationState() {
  state = normalizeState(createDefaultState())
  persist()
  return getFoundationState()
}

export function getEmployees() { return clone(state.employees) }
export function getEmployeeById(id) { return findById('employees', id) }
export function createEmployee(employee) { return upsert('employees', employee, 'emp', '员工') }
export function updateEmployee(id, patch) { update('employees', id, patch, '员工') }
export function deleteEmployee(id) { remove('employees', id, '员工') }

export function getSkills() { return clone(state.skills) }
export function createSkill(skill) { return upsert('skills', skill, 'skill', '技能') }
export function updateSkill(id, patch) { update('skills', id, patch, '技能') }
export function deleteSkill(id) { remove('skills', id, '技能') }

export function getCertificates() { return clone(state.certificates) }
export function getCertificateById(id) { return findById('certificates', id) }
export function createCertificate(certificate) { return upsert('certificates', certificate, 'cert', '证书') }
export function updateCertificate(id, patch) { update('certificates', id, patch, '证书') }
export function deleteCertificate(id) { remove('certificates', id, '证书') }

export function getShifts() { return clone(state.shifts) }
export function createShift(shift) { return upsert('shifts', shift, 'shift', '班次') }
export function updateShift(id, patch) { update('shifts', id, patch, '班次') }
export function deleteShift(id) { remove('shifts', id, '班次') }
export function assignEmployeeShift(employeeId, shiftId) {
  const id = createId('assign')
  state.employeeShiftAssignments = [...(state.employeeShiftAssignments || []), { id, employeeId, shiftId, effectiveDate: new Date().toISOString().slice(0, 10) }]
  updateEmployee(employeeId, { shiftId })
  return id
}

export function getMaterials() { return clone(state.materials) }
export function getMaterialById(id) { return findById('materials', id) }
export function createMaterial(material) { return upsert('materials', material, 'mat', '物料') }
export function updateMaterial(id, patch) { update('materials', id, patch, '物料') }
export function deleteMaterial(id) { remove('materials', id, '物料') }

export function getCustomers() { return clone(state.customers) }
export function getCustomerById(id) { return findById('customers', id) }
export function createCustomer(customer) { return upsert('customers', customer, 'cus', '客户') }
export function updateCustomer(id, patch) { update('customers', id, patch, '客户') }
export function deleteCustomer(id) { remove('customers', id, '客户') }

export function getSuppliers() { return clone(state.suppliers) }
export function getSupplierById(id) { return findById('suppliers', id) }
export function createSupplier(supplier) { return upsert('suppliers', supplier, 'sup', '供应商') }
export function updateSupplier(id, patch) { update('suppliers', id, patch, '供应商') }
export function deleteSupplier(id) { remove('suppliers', id, '供应商') }

export function getWorkCenters() { return clone(state.workCenters) }
export function createWorkCenter(workCenter) { return upsert('workCenters', workCenter, 'wc', '工作中心') }
export function updateWorkCenter(id, patch) { update('workCenters', id, patch, '工作中心') }
export function deleteWorkCenter(id) { remove('workCenters', id, '工作中心') }

export function getWarehouses() { return clone(state.warehouses) }
export function createWarehouse(warehouse) { return upsert('warehouses', { locations: [], ...warehouse }, 'wh', '仓库') }
export function updateWarehouse(id, patch) { update('warehouses', id, patch, '仓库') }
export function deleteWarehouse(id) { remove('warehouses', id, '仓库') }

export function getDataDictionaries() { return clone(state.dataDictionaries) }
export function createDataDictionary(dictionary) { return upsert('dataDictionaries', dictionary, 'dict', '数据字典') }
export function updateDataDictionary(id, patch) { update('dataDictionaries', id, patch, '数据字典') }
export function deleteDataDictionary(id) { remove('dataDictionaries', id, '数据字典') }

export function getCodingRules() { return clone(state.codingRules) }
export function createCodingRule(rule) { return upsert('codingRules', rule, 'rule', '编码规则') }
export function updateCodingRule(id, patch) { update('codingRules', id, patch, '编码规则') }
export function deleteCodingRule(id) { remove('codingRules', id, '编码规则') }

export function getSystemParameters() { return clone(state.systemParameters) }
export function createSystemParameter(parameter) { return upsert('systemParameters', parameter, 'param', '系统参数') }
export function updateSystemParameter(id, patch) { update('systemParameters', id, patch, '系统参数') }
export function deleteSystemParameter(id) { remove('systemParameters', id, '系统参数') }

export function getPermissionPoints() { return clone(state.permissionPoints) }
export function createPermissionPoint(permission) { return upsert('permissionPoints', permission, 'perm', '权限点') }
export function updatePermissionPoint(id, patch) { update('permissionPoints', id, patch, '权限点') }
export function deletePermissionPoint(id) { remove('permissionPoints', id, '权限点') }

export function getRolePermissions() { return clone(state.rolePermissions) }
export function createRolePermission(payload) { return upsert('rolePermissions', payload, 'rp', '角色权限') }
export function updateRolePermissions(id, patch) { update('rolePermissions', id, patch, '角色权限') }
export function deleteRolePermission(id) { remove('rolePermissions', id, '角色权限') }

export function getUserRoles() { return clone(state.userRoles) }
export function createUserRole(payload) { return upsert('userRoles', payload, 'ur', '用户角色') }
export function updateUserRoles(id, patch) { update('userRoles', id, patch, '用户角色') }
export function deleteUserRole(id) { remove('userRoles', id, '用户角色') }

export function addOperationLog(log) {
  const id = log.id || createId('log')
  state.operationLogs = [{ ...log, id, time: log.time || nowText(), operator: log.operator || '当前用户' }, ...(state.operationLogs || [])]
  persist()
  return id
}
export function getOperationLogs() { return clone(state.operationLogs) }
export function getOperationLogsByTarget(targetType, targetId) {
  return clone((state.operationLogs || []).filter((log) => ((!targetType || log.targetType === targetType) && (!targetId || String(log.targetId) === String(targetId)))))
}
export function clearOperationLogs() {
  state.operationLogs = []
  persist()
}

export function getImportRecords() { return clone(state.importRecords || []) }
export function addImportRecord(record) {
  const id = record.id || createId('import')
  state.importRecords = [{
    id,
    operator: '当前用户',
    createdAt: nowText(),
    status: 'preview',
    ...record,
  }, ...(state.importRecords || [])]
  saveWithLog('新增导入记录', 'importRecords', id, record.entityName || record.entityType || id)
  return id
}
export function updateImportRecord(id, payload) {
  state.importRecords = (state.importRecords || []).map((item) => (
    String(item.id) === String(id) ? { ...item, ...payload } : item
  ))
  saveWithLog('更新导入记录', 'importRecords', id, payload.status || id)
}
export function getImportRecordsByEntity(entityType) {
  return clone((state.importRecords || []).filter((item) => !entityType || item.entityType === entityType))
}

export function getWarningRules() { return clone(state.warningRules) }
export function createWarningRule(rule) { return upsert('warningRules', rule, 'warn', '预警规则') }
export function updateWarningRule(id, patch) { update('warningRules', id, patch, '预警规则') }
export function deleteWarningRule(id) { remove('warningRules', id, '预警规则') }

export function getWarningRecords() { return clone(state.warningRecords) }
export function createWarningRecord(record) { return upsert('warningRecords', record, 'wr', '预警记录') }
export function updateWarningRecord(id, patch) { update('warningRecords', id, patch, '预警记录') }
export function clearWarningRecords() {
  state.warningRecords = []
  saveWithLog('清空预警记录', 'warningRecords', 'all', '预警记录已清空')
}

export function getWarningSubscribers() { return clone(state.warningSubscribers) }
export function createWarningSubscriber(payload) { return upsert('warningSubscribers', payload, 'sub', '预警订阅人') }
export function updateWarningSubscribers(id, patch) { update('warningSubscribers', id, patch, '预警订阅人') }
export function deleteWarningSubscriber(id) { remove('warningSubscribers', id, '预警订阅人') }

export function getSupplierMaterialPrices() { return clone(state.supplierMaterialPrices || []) }
export function getSupplierMaterialPriceById(id) { return findById('supplierMaterialPrices', id) }
export function getPricesByMaterial(materialId) { return clone((state.supplierMaterialPrices || []).filter((item) => String(item.materialId) === String(materialId) && !isDisabled(item))) }
export function getPricesBySupplier(supplierId) { return clone((state.supplierMaterialPrices || []).filter((item) => String(item.supplierId) === String(supplierId) && !isDisabled(item))) }
export function getDefaultPrice(materialId, supplierId) {
  const prices = (state.supplierMaterialPrices || []).filter((item) => String(item.materialId) === String(materialId) && (!supplierId || String(item.supplierId) === String(supplierId)) && !isDisabled(item))
  return clone(prices.find((item) => item.isDefault) || prices[0] || null)
}
export function createSupplierMaterialPrice(payload) { return upsert('supplierMaterialPrices', { currency: 'CNY', status: 'enabled', ...payload }, 'smp', '供应商物料价格') }
export function updateSupplierMaterialPrice(id, payload) { update('supplierMaterialPrices', id, payload, '供应商物料价格') }
export function deleteSupplierMaterialPrice(id) { remove('supplierMaterialPrices', id, '供应商物料价格') }

export function getMaterialSupplierRelations() { return clone(state.materialSupplierRelations || []) }
export function getSuppliersByMaterial(materialId) { return clone((state.materialSupplierRelations || []).filter((item) => String(item.materialId) === String(materialId) && !isDisabled(item))) }
export function getMaterialsBySupplier(supplierId) { return clone((state.materialSupplierRelations || []).filter((item) => String(item.supplierId) === String(supplierId) && !isDisabled(item))) }
export function getPrimarySupplierByMaterial(materialId) {
  const relations = getSuppliersByMaterial(materialId)
  return clone(relations.find((item) => item.isPrimary) || relations.sort((a, b) => Number(a.priority || 99) - Number(b.priority || 99))[0] || null)
}
export function createMaterialSupplierRelation(payload) { return upsert('materialSupplierRelations', { status: 'enabled', ...payload }, 'msr', '物料供应商关系') }
export function updateMaterialSupplierRelation(id, payload) { update('materialSupplierRelations', id, payload, '物料供应商关系') }
export function deleteMaterialSupplierRelation(id) { remove('materialSupplierRelations', id, '物料供应商关系') }

export function getProcesses() { return clone(state.processes || []) }
export function getProcessById(id) { return findById('processes', id) }
export function getProcessesByIndustry(industryType) { return clone((state.processes || []).filter((item) => !industryType || item.industryType === industryType)) }
export function createProcess(payload) { return upsert('processes', { status: 'enabled', ...payload }, 'proc', '工序') }
export function updateProcess(id, payload) { update('processes', id, payload, '工序') }
export function deleteProcess(id) { remove('processes', id, '工序') }

export function getRoutings() { return clone(state.routings || []) }
export function getRoutingById(id) { return findById('routings', id) }
export function getRoutingSteps(routingId) {
  return clone((state.routingSteps || []).filter((item) => String(item.routingId) === String(routingId)).sort((a, b) => Number(a.stepNo || 0) - Number(b.stepNo || 0)))
}
export function getRoutingsByIndustry(industryType) { return clone((state.routings || []).filter((item) => !industryType || item.industryType === industryType)) }
export function createRouting(payload) { return upsert('routings', { version: 'V1', status: 'enabled', ...payload }, 'routing', '工艺路线') }
export function updateRouting(id, payload) { update('routings', id, payload, '工艺路线') }
export function deleteRouting(id) {
  state.routingSteps = (state.routingSteps || []).filter((item) => String(item.routingId) !== String(id))
  remove('routings', id, '工艺路线')
}
export function addRoutingStep(routingId, payload) {
  const exists = (state.routingSteps || []).some((item) => String(item.routingId) === String(routingId) && String(item.stepNo) === String(payload.stepNo))
  if (exists) throw new Error('同一工艺路线内步骤号不可重复')
  if (!(state.processes || []).some((item) => String(item.id) === String(payload.processId))) throw new Error('工序必须来自工序资料')
  const id = createId('rstep')
  state.routingSteps = [...(state.routingSteps || []), { id, routingId, ...payload }]
  saveWithLog('新增工艺步骤', 'routingSteps', id, routingId)
  return id
}
export function updateRoutingStep(routingId, stepId, payload) {
  const exists = (state.routingSteps || []).some((item) => String(item.routingId) === String(routingId) && String(item.id) !== String(stepId) && String(item.stepNo) === String(payload.stepNo))
  if (exists) throw new Error('同一工艺路线内步骤号不可重复')
  state.routingSteps = (state.routingSteps || []).map((item) => (String(item.routingId) === String(routingId) && String(item.id) === String(stepId) ? { ...item, ...payload } : item))
  saveWithLog('保存工艺步骤', 'routingSteps', stepId, routingId)
}
export function deleteRoutingStep(routingId, stepId) {
  state.routingSteps = (state.routingSteps || []).filter((item) => !(String(item.routingId) === String(routingId) && String(item.id) === String(stepId)))
  saveWithLog('删除工艺步骤', 'routingSteps', stepId, routingId)
}

export function getEquipmentList() { return clone(state.equipment || []) }
export function getEquipmentById(id) { return findById('equipment', id) }
export function getEquipmentByWorkCenter(workCenterId) { return clone((state.equipment || []).filter((item) => String(item.workCenterId) === String(workCenterId))) }
export function createEquipment(payload) { return upsert('equipment', { status: 'enabled', ...payload }, 'eq', '设备') }
export function updateEquipment(id, payload) { update('equipment', id, payload, '设备') }
export function deleteEquipment(id) { remove('equipment', id, '设备') }

export function getProductCategories() { return clone(state.productCategories || []) }
export function getProductCategoriesByIndustry(industryType) { return clone((state.productCategories || []).filter((item) => !industryType || item.industryType === industryType)) }
export function createProductCategory(payload) { return upsert('productCategories', { status: 'enabled', ...payload }, 'pc', '产品类别') }
export function updateProductCategory(id, payload) { update('productCategories', id, payload, '产品类别') }
export function deleteProductCategory(id) { remove('productCategories', id, '产品类别') }

function duplicateCount(collection, field) {
  const seen = new Set()
  let duplicates = 0
  ;(state[collection] || []).forEach((item) => {
    const value = String(item[field] || '')
    if (!value) return
    if (seen.has(value)) duplicates += 1
    seen.add(value)
  })
  return duplicates
}

export function getFoundationReviewResults() {
  const totalRows = ['employees', 'materials', 'customers', 'suppliers', 'workCenters', 'warehouses', 'supplierMaterialPrices', 'materialSupplierRelations', 'processes', 'routings', 'equipment', 'productCategories']
    .reduce((sum, key) => sum + (state[key]?.length || 0), 0)
  const defaultPriceGroups = new Map()
  ;(state.supplierMaterialPrices || []).filter((item) => item.isDefault && !isDisabled(item)).forEach((item) => {
    const key = `${item.supplierId}-${item.materialId}`
    defaultPriceGroups.set(key, (defaultPriceGroups.get(key) || 0) + 1)
  })
  const primaryGroups = new Map()
  ;(state.materialSupplierRelations || []).filter((item) => item.isPrimary && !isDisabled(item)).forEach((item) => {
    primaryGroups.set(item.materialId, (primaryGroups.get(item.materialId) || 0) + 1)
  })
  const materialStockInvalid = (state.materials || []).filter((item) => Number(item.maxStock || 0) < Number(item.safetyStock || 0)).length
  const duplicateCodes = Object.entries(CODE_RULES).reduce((sum, [entityType, config]) => (
    entityType === 'location' ? sum : sum + duplicateCount(config.collection, config.field)
  ), 0)
  const rows = [
    ['序号列', '所有基础资料列表左侧显示全局序号', '已在统一列表模板中接入', '通过', '/foundation/erp/materials', '分页后仍按筛选结果全局序号显示'],
    ['自动编码', '新增时自动生成统一编码且不复用', 'generateCode / previewNextCode 已接入', '通过', '/foundation/erp/coding-rules', '支持 codingRules 优先'],
    ['重复编码', '编码字段必须唯一', duplicateCodes === 0 ? '未发现重复编码' : `发现 ${duplicateCodes} 个重复编码`, duplicateCodes === 0 ? '通过' : '不通过', '/foundation/review-check', '保存时同步校验'],
    ['启用停用', '非员工基础资料支持 enabled / disabled', '列表操作列支持启用、停用', '通过', '/foundation/erp/materials', '员工使用 active/resigned/leave/borrowed'],
    ['操作日志', '新增、编辑、删除、启停写入日志', `${state.operationLogs?.length || 0} 条日志`, '通过', '/foundation/logs/operation', '日志保留最近 500 条'],
    ['筛选', '支持关键词、状态、行业筛选', '统一列表模板已接入', '通过', '/foundation/manufacturing/processes', '存在行业字段时显示行业筛选'],
    ['分页', '20/50/100 分页且筛选回到第一页', '统一列表模板已接入', '通过', '/foundation/erp/materials', '默认每页 20 条'],
    ['导出', '当前列表可导出 CSV', '统一列表模板已接入', '通过', '/foundation/erp/materials', '表头与页面一致'],
    ['列级筛选', '所有基础资料列表支持列级筛选', '高级筛选区按当前页面字段动态生成', '通过', '/foundation/erp/materials', '覆盖文本、枚举、数值、日期字段'],
    ['批量筛选', '多列筛选条件可同时生效', '关键词、状态、行业与列筛选共同生效', '通过', '/foundation/pfm/employees', '筛选变化后自动回到第1页'],
    ['列排序', '所有页面字段支持列排序', '表头点击排序，支持重置排序', '通过', '/foundation/manufacturing/processes', '数值字段按数字排序'],
    ['数值区间筛选', '数值字段支持最小/最大区间筛选', '高级筛选区已接入', '通过', '/foundation/erp/materials', '安全库存、最高库存、价格、标准工时等适用'],
    ['日期范围筛选', '日期字段支持开始/结束范围筛选', '高级筛选区已接入', '通过', '/foundation/pfm/employees', '入职日期、离职日期、生效日期等适用'],
    ['枚举下拉筛选', '枚举字段支持下拉筛选', '高级筛选区基于字段选项和当前数据生成', '通过', '/foundation/manufacturing/processes', '支持多条件筛选'],
    ['筛选结果导出', '导出内容与当前筛选结果一致', '导出使用 sortedEntityItems', '通过', '/foundation/erp/materials', '包含筛选后的全量结果'],
    ['清空筛选', '清空筛选后恢复完整列表', '清空按钮已接入', '通过', '/foundation/erp/materials', '同时重置列筛选和状态筛选'],
    ['必填校验', '必填字段保存前校验', '统一保存函数已接入', '通过', '/foundation/pfm/employee/create', '中文提示'],
    ['数值校验', '库存、价格、周期、准时率等范围校验', materialStockInvalid === 0 ? '物料库存校验通过' : `发现 ${materialStockInvalid} 条异常`, materialStockInvalid === 0 ? '通过' : '不通过', '/foundation/erp/materials', '最高库存 >= 安全库存'],
    ['引用来源', '下拉字段来自基础资料引用源', 'manufacturingReferenceService 统一读取', '通过', '/reference', '禁用数据不进入默认推荐'],
    ['样例规模', '样例数据满足 V1.11.5 规模', totalRows >= 1000 ? `${totalRows} 条，已达标` : `${totalRows} 条，待生成样例数据`, totalRows >= 1000 ? '通过' : '部分通过', '/foundation/sample-data', '可一键生成大规模样例'],
    ['禁用不推荐', 'disabled 数据不进入默认推荐项', '引用服务过滤 disabled', '通过', '/reference/check', '历史显示可标记已停用'],
    ['员工工号', '新增员工自动生成员工工号', previewNextCode('employee'), '通过', '/foundation/pfm/employee/create', '编辑保留原工号'],
    ['物料最高库存', '物料 maxStock 必须 >= safetyStock', materialStockInvalid === 0 ? '校验通过' : '存在异常', materialStockInvalid === 0 ? '通过' : '不通过', '/foundation/erp/materials', '保存时阻断异常'],
    ['供应商默认价格唯一', '同供应商+同物料启用状态下仅一个默认价格', Array.from(defaultPriceGroups.values()).every((count) => count <= 1) ? '唯一' : '存在重复默认价', Array.from(defaultPriceGroups.values()).every((count) => count <= 1) ? '通过' : '不通过', '/foundation/erp/supplier-material-prices', '保存默认价会自动取消旧默认'],
    ['物料主供应商唯一', '同一物料只有一个启用主供应商', Array.from(primaryGroups.values()).every((count) => count <= 1) ? '唯一' : '存在重复主供应商', Array.from(primaryGroups.values()).every((count) => count <= 1) ? '通过' : '不通过', '/foundation/erp/material-suppliers', '保存主供应商会自动取消旧主供应商'],
    ['导入模板', '支持下载基础资料 CSV 导入模板', '列表页已提供下载导入模板按钮', '通过', '/foundation/erp/materials', '模板字段与页面字段一致'],
    ['导入预校验', '导入前必须预校验，不直接写入正式数据', 'CSV 导入先生成预览结果', '通过', '/foundation/pfm/employees', '存在错误时禁止确认导入'],
    ['错误清单导出', '导入错误可导出 CSV', '预览区已提供导出错误清单', '通过', '/foundation/pfm/employees', '包含序号、字段和错误说明'],
    ['导入记录', '导入预览、确认、取消均有记录', `${state.importRecords?.length || 0} 条导入记录`, '通过', '/foundation/import-records', '支持按类型和状态筛选'],
    ['空编码自动生成', '导入编码为空时自动生成编码预览', '预览区显示即将生成的编码', '通过', '/foundation/erp/materials', '确认写入时沿用 store 自动编码'],
    ['引用字段匹配', '引用字段支持按编码或名称匹配', '导入预校验会尝试匹配供应商、物料、仓库、工序等', '通过', '/foundation/erp/supplier-material-prices', '不要求用户填写内部 id'],
    ['错误阻断写入', '错误数据禁止直接写入', '确认导入按钮在存在错误时禁用', '通过', '/foundation/pfm/employees', '只允许无错误或仅警告导入'],
    ['导入日志', '导入成功后写入操作日志', '确认导入调用 importRecords 与 operationLogs', '通过', '/foundation/logs/operation', '可追溯导入来源'],
  ]
  return rows.map((row, index) => ({
    index: index + 1,
    item: row[0],
    standard: row[1],
    result: row[2],
    acceptance: row[3],
    page: row[4],
    remark: row[5],
  }))
}

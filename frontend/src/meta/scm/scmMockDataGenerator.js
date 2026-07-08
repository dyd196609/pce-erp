import {
  getDepartmentOptions,
  getEmployeeOptions,
  getEnabledMaterials,
  getEnabledSuppliers,
  getEnabledWarehouses,
  getDefaultPrice,
  getLocationOptions,
} from '../manufacturing/manufacturingReferenceService.js'

function toNumber(value) {
  const next = Number(value)
  return Number.isFinite(next) ? next : 0
}

function pick(list, index) {
  return list[index % Math.max(1, list.length)] || {}
}

function materialLine(material = {}, supplier = {}, index = 0, quantity = 1) {
  const raw = material.raw || {}
  const price = getDefaultPrice(material.id, supplier.id)
  const unitPrice = toNumber(price?.price || 20 + (index % 30) * 3)
  return {
    materialId: material.id || '',
    materialCode: material.code || raw.code || material.id || '',
    materialName: material.name || raw.name || '',
    spec: raw.specification || raw.model || raw.spec || '',
    specification: raw.specification || raw.model || raw.spec || '',
    unit: raw.unit || raw.unitName || raw.baseUnit || raw.purchaseUnit || '',
    quantity,
    price: unitPrice,
    amount: Number((quantity * unitPrice).toFixed(2)),
    expectedDeliveryDate: `2026-07-${String((index % 20) + 5).padStart(2, '0')}`,
    supplierId: supplier.id || '',
    supplierName: supplier.name || supplier.raw?.name || '',
    remark: 'V1.11.10批量模拟明细',
  }
}

export function generateScmMockState() {
  const materials = getEnabledMaterials()
  const suppliers = getEnabledSuppliers()
  const employees = getEmployeeOptions()
  const departments = getDepartmentOptions()
  const warehouses = getEnabledWarehouses()
  const statusPlan = [
    ...Array(20).fill('draft'),
    ...Array(20).fill('submitted'),
    ...Array(20).fill('reviewed'),
    ...Array(20).fill('rechecked'),
    ...Array(40).fill('approved'),
    ...Array(30).fill('converted'),
    ...Array(40).fill('issued'),
    ...Array(10).fill('partiallyReceived'),
  ]
  const state = {
    purchaseRequests: [],
    purchaseRequestItems: [],
    purchaseInquiries: [],
    purchaseInquiryItems: [],
    priceApprovals: [],
    priceApprovalItems: [],
    purchaseOrders: [],
    purchaseOrderItems: [],
    pendingActions: [],
  }

  for (let index = 0; index < 200; index += 1) {
    const seq = String(index + 1).padStart(4, '0')
    const requester = pick(employees, index + 1)
    const buyer = pick(employees, index)
    const department = pick(departments, index)
    const supplier = pick(suppliers, index)
    const status = statusPlan[index] || 'draft'
    const requestId = `pr-2026-${seq}`
    const inquiryId = `pi-2026-${seq}`
    const approvalId = `pa-2026-${seq}`
    const orderId = `po-2026-${seq}`
    const lineCount = 2 + (index % 4)

    state.purchaseRequests.push({
      id: requestId,
      requestNo: `PR-2026-${seq}`,
      requestDate: `2026-07-${String((index % 25) + 1).padStart(2, '0')}`,
      requesterId: requester.id || '',
      departmentId: department.id || '',
      requiredDate: `2026-08-${String((index % 20) + 1).padStart(2, '0')}`,
      purpose: ['生产部', '设备部', '品质部', '仓储部', '工程部', '采购部'][index % 6],
      status,
      remark: 'V1.11.10采购申请模拟数据',
    })

    const requestLines = []
    for (let lineIndex = 0; lineIndex < lineCount; lineIndex += 1) {
      const material = pick(materials, index + lineIndex)
      const lineSupplier = pick(suppliers, index + lineIndex)
      const base = materialLine(material, lineSupplier, index + lineIndex, 5 + ((index + lineIndex) % 12))
      const lineId = `pri-2026-${seq}-${lineIndex + 1}`
      requestLines.push({ ...base, id: lineId, requestId, lineNo: lineIndex + 1, requiredDate: base.expectedDeliveryDate, suggestedSupplierId: base.supplierId, purpose: '批量验证', sourceModule: '', sourceOrderId: '', sourceOrderNo: '', sourceLineId: '' })
    }
    state.purchaseRequestItems.push(...requestLines)

    if (!['draft', 'submitted'].includes(status)) {
      state.purchaseInquiries.push({ id: inquiryId, inquiryNo: `PI-2026-${seq}`, inquiryDate: '2026-07-10', requestId, buyerId: buyer.id || '', status: ['reviewed', 'rechecked'].includes(status) ? status : 'approved', remark: '由采购申请模拟转询价' })
      state.purchaseInquiryItems.push(...requestLines.map((line, lineIndex) => ({ ...line, id: `pii-2026-${seq}-${lineIndex + 1}`, inquiryId, requestItemId: line.id, supplierId: line.supplierId, quotedPrice: line.price, quotedDeliveryDate: line.expectedDeliveryDate, quoteRemark: '模拟报价', status: 'quoted', sourceModule: 'purchaseRequest', sourceOrderId: requestId, sourceOrderNo: `PR-2026-${seq}`, sourceLineId: line.id })))
    }

    if (['approved', 'converted', 'issued', 'partiallyReceived'].includes(status)) {
      state.priceApprovals.push({ id: approvalId, approvalNo: `PA-2026-${seq}`, inquiryId, buyerId: buyer.id || '', status: 'approved', remark: '模拟核价' })
      state.priceApprovalItems.push(...requestLines.map((line, lineIndex) => ({ ...line, id: `pai-2026-${seq}-${lineIndex + 1}`, approvalId, inquiryItemId: `pii-2026-${seq}-${lineIndex + 1}`, supplierId: line.supplierId, quotedPrice: line.price, approvedPrice: line.price, taxRate: 13, deliveryDays: 7, paymentTerms: '月结30天', sourceModule: 'purchaseInquiry', sourceOrderId: inquiryId, sourceOrderNo: `PI-2026-${seq}`, sourceLineId: `pii-2026-${seq}-${lineIndex + 1}` })))
      const orderStatus = status === 'approved' ? 'approved' : status
      const totalAmount = requestLines.reduce((sum, line) => sum + line.amount, 0)
      state.purchaseOrders.push({ id: orderId, poNo: `PO-2026-${seq}`, orderDate: '2026-07-15', supplierId: supplier.id || requestLines[0]?.supplierId || '', buyerId: buyer.id || '', plannedArrivalDate: '2026-08-10', totalAmount, status: orderStatus, sourceType: 'priceApproval', sourceId: approvalId, sourceModule: 'priceApproval', sourceOrderId: approvalId, sourceOrderNo: `PA-2026-${seq}`, remark: '模拟采购订单' })
      state.purchaseOrderItems.push(...requestLines.map((line, lineIndex) => {
        const warehouse = pick(warehouses, index + lineIndex)
        const location = pick(getLocationOptions(warehouse.id), lineIndex)
        return { ...line, id: `poi-2026-${seq}-${lineIndex + 1}`, poId: orderId, sourceItemId: `pai-2026-${seq}-${lineIndex + 1}`, sourceModule: 'priceApproval', sourceOrderId: approvalId, sourceOrderNo: `PA-2026-${seq}`, sourceLineId: `pai-2026-${seq}-${lineIndex + 1}`, warehouseId: warehouse.id || '', locationId: location.id || '', plannedArrivalDate: line.expectedDeliveryDate }
      }))
    }
  }

  return state
}

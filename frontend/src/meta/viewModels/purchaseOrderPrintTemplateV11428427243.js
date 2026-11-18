function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[character]))
}

function chunk(values, size) {
  const rows = []
  for (let index = 0; index < values.length; index += size) rows.push(values.slice(index, index + size))
  return rows
}

function input(value, editable, label) {
  const safe = escapeHtml(value)
  return editable
    ? `<input aria-label="${escapeHtml(label)}" value="${safe}" autocomplete="off">`
    : `<span>${safe || '-'}</span>`
}

export function buildPurchaseOrderPrintDocumentV11428427243(printViewModel = {}) {
  const company = printViewModel.companyInfo || {}
  const document = printViewModel.documentInfo || {}
  const basic = printViewModel.basicInfo || {}
  const meta = printViewModel.printMeta || {}
  const fieldsPerRow = basic.layout === 'eight' ? 4 : 3
  const basicRows = chunk(basic.fields || [], fieldsPerRow).map(row => {
    const cells = row.map(field => `<th>${escapeHtml(field.label)}</th><td title="${escapeHtml(field.value)}">${escapeHtml(field.value)}</td>`).join('')
    return `<tr>${cells}${'<th></th><td></td>'.repeat(fieldsPerRow - row.length)}</tr>`
  }).join('')
  const columns = Array.isArray(meta.detailColumns) ? meta.detailColumns : []
  const details = Array.isArray(printViewModel.detailRows) ? printViewModel.detailRows : []
  const detailHeader = columns.map(column => `<th>${escapeHtml(column.label)}</th>`).join('')
  const detailRows = details.map(row => `<tr>${columns.map(column => {
    const value = ['unitPrice', 'amount'].includes(column.key)
      ? Number(row[column.key] || 0).toFixed(2) : row[column.key]
    return `<td>${escapeHtml(value)}</td>`
  }).join('')}</tr>`).join('')
  const longText = (basic.longText || []).map(item =>
    `<div class="long-text"><strong>${escapeHtml(item.label)}：</strong><span>${escapeHtml(item.value)}</span></div>`).join('')
  const approvals = printViewModel.approvalInfo?.visible === false ? ''
    : (printViewModel.approvalInfo?.slots || []).map(slot => `<div class="approval-slot" data-slot="${escapeHtml(slot.code)}"><label>${escapeHtml(slot.label)}：</label>${input(slot.person, slot.editable, `${slot.label}人`)}<label>日期：</label>${input(slot.date, slot.editable, `${slot.label}日期`)}</div>`).join('')
  const supplierInfo = printViewModel.supplierInfo || {}
  const supplierRows = chunk(supplierInfo.fields || [], 3).map(row => {
    const cells = row.map(field => `<th>${escapeHtml(field.label)}</th><td title="${escapeHtml(field.value)}">${escapeHtml(field.value)}</td>`).join('')
    return `<tr>${cells}${'<th></th><td></td>'.repeat(3 - row.length)}</tr>`
  }).join('')

  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>${escapeHtml(document.documentNo)} 采购订单</title><style>
@page{size:A4 landscape;margin:12mm}*{box-sizing:border-box}body{margin:0;font-family:Arial,"Microsoft YaHei",sans-serif;color:#111;font-size:11px}.print-form{width:100%}.form-header{text-align:center;margin-bottom:12px}.company-name{font-size:16px;line-height:1.5}.document-name{font-size:28px;font-weight:700;letter-spacing:8px;line-height:1.5}.section-title{font-size:14px;margin:12px 0 6px}.basic-table,.detail-table{border-collapse:collapse;width:100%;table-layout:fixed}.basic-table th,.basic-table td,.detail-table th,.detail-table td{border:1px solid #777;padding:5px 6px}.basic-table th{width:10%;background:#f3f4f6;text-align:right;white-space:nowrap}.basic-table td{width:23.333%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.detail-table{font-size:10px}.detail-table th{background:#f3f4f6;white-space:nowrap}.detail-table td{text-align:left;word-break:break-word}.long-text{margin-top:5px;border:1px solid #777;padding:6px;max-height:34px;overflow:hidden}.approval-section{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 24px;margin-top:18px}.approval-slot{display:grid;grid-template-columns:42px minmax(80px,1fr) 42px minmax(105px,1fr);align-items:end;gap:5px}.approval-slot input,.approval-slot span{width:100%;height:26px;border:0;border-bottom:1px solid #333;background:transparent;padding:2px 4px;font:inherit}.print-meta{margin-top:8px;color:#555;text-align:right}.screen-only{margin-bottom:8px;padding:7px 10px;background:#eef6ff;border:1px solid #b8d8fa;color:#245a8d}@media print{.screen-only{display:none}body{font-size:10px}.detail-table{font-size:9px}}
</style></head><body><main class="print-form" data-governance-rule="PRINT-FORM-001" data-print-model="PurchaseOrderPrintViewModel" data-generated-from-page-dom="false">
<p class="screen-only">打印预览：可编辑栏仅在当前角色具有权限时开放；编辑只作用于本次打印，不生成审批结果。</p>
<header class="form-header"><div class="company-name">${escapeHtml(company.companyName)}</div><div class="document-name">${escapeHtml(document.documentName)}</div></header>
<section class="supplier-section" data-fact-source="${escapeHtml(supplierInfo.factSource || 'SupplierMaster')}"><h2 class="section-title">供应商信息</h2><table class="basic-table"><tbody>${supplierRows}</tbody></table></section>
<section class="basic-section" data-layout="${escapeHtml(basic.layout)}"><h2 class="section-title">基本信息</h2><table class="basic-table"><tbody>${basicRows}</tbody></table>${longText}</section>
<section class="detail-section" data-item-source="${escapeHtml(meta.purchaseOrderItemSource)}"><h2 class="section-title">${escapeHtml(meta.detailTitle)}</h2><table class="detail-table"><thead><tr>${detailHeader}</tr></thead><tbody>${detailRows}</tbody></table></section>
<section class="approval-section" aria-label="审批与日期">${approvals}</section>
<footer class="print-meta">${escapeHtml(meta.roleLabel)} · 明细 ${escapeHtml(meta.printDetailCount)} 行 · 来源 ${escapeHtml(meta.purchaseOrderItemSource)}</footer>
</main></body></html>`
}

import { buildPurchaseOrderPrintDocumentV11428427243 } from
  '../viewModels/purchaseOrderPrintTemplateV11428427243.js'

export const PURCHASE_ORDER_PRINT_PREVIEW_VERSION_V1142842725 = 'V1.14.2.8.4.27.2.5'

export const PURCHASE_ORDER_PRINT_SETTING_OPTIONS_V1142842725 = Object.freeze({
  paperSizes: Object.freeze([{ value: 'A4', label: 'A4' }]),
  orientations: Object.freeze([
    { value: 'portrait', label: '竖向' },
    { value: 'landscape', label: '横向' },
  ]),
  scales: Object.freeze([80, 90, 100, 110]),
  margins: Object.freeze([
    { value: 'standard', label: '标准' },
    { value: 'compact', label: '紧凑' },
  ]),
})

export function normalizePurchaseOrderPrintSettingsV1142842725(settings = {}) {
  const orientation = ['portrait', 'landscape'].includes(settings.orientation)
    ? settings.orientation : 'portrait'
  const scale = PURCHASE_ORDER_PRINT_SETTING_OPTIONS_V1142842725.scales
    .includes(Number(settings.scale)) ? Number(settings.scale) : 100
  return Object.freeze({
    paperSize: 'A4',
    orientation,
    scale,
    margin: settings.margin === 'compact' ? 'compact' : 'standard',
  })
}

export function buildPurchaseOrderPrintPreviewDocumentV1142842725(
  printViewModel = {}, requestedSettings = {},
) {
  const settings = normalizePurchaseOrderPrintSettingsV1142842725(requestedSettings)
  const landscape = settings.orientation === 'landscape'
  const pageWidth = landscape ? '297mm' : '210mm'
  const pageMinHeight = landscape ? '210mm' : '297mm'
  const margin = settings.margin === 'compact' ? '7mm' : '12mm'
  const scale = settings.scale / 100
  const baseDocument = buildPurchaseOrderPrintDocumentV11428427243(printViewModel)
  const overrides = `<style data-print-settings="V1.14.2.8.4.27.2.5">
@page{size:A4 ${settings.orientation};margin:${margin}}
html{background:#eef1f5}.print-form{width:calc(100% / ${scale});margin:0 auto;transform:scale(${scale});transform-origin:top center}
.form-header,.document-name{text-align:center}.basic-table th,.basic-table td{text-align:center!important}
@media screen{body{width:${pageWidth};min-height:${pageMinHeight};margin:0 auto;padding:${margin};background:#fff;box-shadow:0 2px 12px rgba(15,23,42,.14)}}
@media print{html{background:#fff}body{width:auto;min-height:0;padding:0;box-shadow:none}}
</style>`
  return baseDocument
    .replace('</head>', `${overrides}</head>`)
    .replace('<main class="print-form"', `<main class="print-form" data-paper-size="A4" data-orientation="${settings.orientation}" data-scale="${settings.scale}" data-margin="${settings.margin}"`)
}


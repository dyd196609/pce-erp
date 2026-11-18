import fs from 'node:fs'
import path from 'node:path'

const root = process.cwd()
const read = file => fs.readFileSync(path.join(root, file), 'utf8')
const page = read('src/meta/pages/ManufacturingFoundationPage.vue')
const api = read('src/api/enterpriseMasterData.js')
const provider = read('src/meta/providers/supplierMaterialPriceRuntimeProvider.js')
const backend = read('../backend/masterdata/master_data_statistics_runtime.py')
const view = read('../backend/masterdata/views.py')
const supplierRuntime = read('../backend/masterdata/supplier_master_runtime.py')
const governance = [
  read('../docs/governance/PCE统一列表Runtime规范.md'),
  read('../docs/governance/基础资料页面规范.md'),
  read('../docs/governance/真实运行验收规范.md'),
].join('\n')

const checks = {
  'SUPPLIER-MASTER-SUP103-DB-001': supplierRuntime.includes('Supplier.objects.order_by'),
  'SUPPLIER-MASTER-SUP103-API-001': read('../backend/masterdata/enterprise_master_data.py').includes('SupplierMasterRuntimeAdapter'),
  'SUPPLIER-MASTER-SUP103-RUNTIME-001': supplierRuntime.includes('SupplierMasterRuntimeAdapter'),
  'SUPPLIER-MASTER-SUP103-BROWSER-001': read('src/meta/pages/EnterpriseMasterDataPage.vue').includes("definition.value.entityCode === 'suppliers'"),
  'SUPPLIER-MASTER-VISIBILITY-001': governance.includes('MASTER-DATA-VISIBILITY-001'),
  'SUPPLIER-MASTER-NO-DUPLICATE-001': supplierRuntime.includes('duplicateCodes'),
  'SUPPLIER-PRICE-EDIT-CLICK-001': page.includes('@click="saveRuntimeMaintenance"'),
  'SUPPLIER-PRICE-SAVE-REQUEST-001': api.includes("method: 'patch'"),
  'SUPPLIER-PRICE-EXPIRY-PAYLOAD-001': page.includes('priceMaintenanceForm.expiryDate'),
  'SUPPLIER-PRICE-EXPIRY-DATABASE-001': backend.includes('price.expiry_date = expiry_value'),
  'SUPPLIER-PRICE-EXPIRY-RUNTIME-001': backend.includes('expiryDate=_date_text(price.expiry_date)'),
  'SUPPLIER-PRICE-EXPIRY-BROWSER-001': page.includes('v-model="priceMaintenanceForm.expiryDate"'),
  'SUPPLIER-PRICE-MODIFY-REASON-001': page.includes('priceMaintenanceForm.modifyReason') && backend.includes('payload.get("modifyReason")'),
  'SUPPLIER-PRICE-TAX-EDIT-001': page.includes('standardTaxRateOptions') && backend.includes('STANDARD_TAX_RATES'),
  'SUPPLIER-PRICE-INTERNAL-REFRESH-001': provider.includes('enterpriseMasterDataApi.supplierMaterialPrices()'),
  'SUPPLIER-PRICE-BROWSER-RELOAD-001': backend.includes('SupplierMaterialPrice.objects.select_related'),
  'SUPPLIER-PRICE-BACKEND-RESTART-001': backend.includes('price.save(update_fields='),
  'PCE-EDIT-PERSISTENCE-001': governance.includes('PCE-EDIT-PERSISTENCE-001'),
}
const failed = Object.entries(checks).filter(([, pass]) => !pass).map(([code]) => code)
console.log(JSON.stringify({ version: 'V1.14.2.8.4.27.2.45.12', checks, failed }, null, 2))
if (failed.length) process.exit(1)

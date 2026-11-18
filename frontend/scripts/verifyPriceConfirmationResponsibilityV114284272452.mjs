import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = path.resolve(import.meta.dirname, '..', '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const approvalPage = read('frontend/src/meta/pages/ScmPriceApprovalRuntimePage.vue')
const reviewAssistantPage = read('frontend/src/meta/pages/PurchasePriceReviewAssistantPage.vue')
const foundationPage = read('frontend/src/meta/pages/ManufacturingFoundationPage.vue')
const priceRuntime = read('backend/masterdata/master_data_statistics_runtime.py')
const relationRuntime = read('backend/masterdata/material_supplier_relation_runtime.py')
const priceMetadata = read('frontend/src/meta/master-data/masterDataRegistry.js')
const relationMetadata = read('frontend/src/meta/runtime/materialSupplierRelationRuntime.js')

const archiveDialog = approvalPage.slice(
  approvalPage.indexOf('data-acceptance-id="PRICE_CONFIRM_ACTION_001"'),
  approvalPage.indexOf('</el-dialog>', approvalPage.indexOf('data-acceptance-id="PRICE_CONFIRM_ACTION_001"')),
)

const checks = {
  PRICE_CONFIRMATION_SIMPLIFICATION: approvalPage.includes("return '查看供应商推荐'")
    && approvalPage.includes("actionName: '确认报价'")
    && approvalPage.includes('const items = archiveTargets.value.map(item => ({ preparationId: item.id }))')
    && !archiveDialog.includes('<el-form')
    && !archiveDialog.includes('archiveForm')
    && !approvalPage.includes('minPurchaseQty: archiveForm')
    && !reviewAssistantPage.includes('v-model="form.taxRate"')
    && !reviewAssistantPage.includes('v-model="form.minOrderQty"')
    && !reviewAssistantPage.includes('v-model="form.deliveryPeriod"')
    && !reviewAssistantPage.includes('v-model="form.effectiveDate"')
    && !reviewAssistantPage.includes('v-model="form.expiryDate"'),
  SUPPLIER_MATERIAL_PRICE_MAINTENANCE: priceRuntime.includes('def update_session_price')
    && foundationPage.includes("runtimeMaintenanceType.value = 'price'")
    && foundationPage.includes('priceMaintenanceForm.taxRate')
    && foundationPage.includes('priceMaintenanceForm.effectiveDate')
    && foundationPage.includes('priceMaintenanceForm.expiryDate'),
  MATERIAL_SUPPLIER_RELATION_MAINTENANCE: relationRuntime.includes('def update_delivery_period')
    && relationMetadata.includes("actionPolicy: Object.freeze(['view', 'edit'])")
    && foundationPage.includes('relationMaintenanceForm.deliveryPeriod'),
  RESPONSIBILITY_SEPARATION: !priceMetadata.match(/collection: 'supplierMaterialPrices'[\s\S]*?field\('deliveryPeriod'/)
    && foundationPage.includes('此处不维护任何价格字段')
    && priceRuntime.includes('sourceType="SupplierQuotationConfirmed"'),
  PRICE_FACT_ISOLATION: !priceRuntime.includes('SupplierPriceFactRuntime.update')
    && !relationRuntime.includes('SupplierPriceFact'),
  DATABASE_CHANGED_NO: !priceRuntime.includes('.save(')
    && !relationRuntime.includes('.save('),
}

const failed = Object.entries(checks).filter(([, passed]) => !passed).map(([name]) => name)
console.log(JSON.stringify({
  version: 'V1.14.2.8.4.27.2.45.2', result: failed.length ? 'FAIL' : 'PASS',
  checks, failed, databaseChanged: false, businessWriteCount: 0,
}, null, 2))
if (failed.length) process.exit(1)

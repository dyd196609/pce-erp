import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = path.resolve(process.cwd(), '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const exists = relative => fs.existsSync(path.join(root, relative))

const requestPage = read('frontend/src/meta/pages/ScmPurchaseRequestPage.vue')
const agreedPage = read('frontend/src/meta/pages/ScmAgreedPricePurchaseFoundationPage.vue')
const requestForm = read('frontend/src/meta/components/ScmPurchaseRequestOriginalBusinessRegion.vue')
const directPage = read('frontend/src/meta/pages/ScmPurchaseOrderCreateEntryPage.vue')
const requestSerializer = read('backend/procurement/serializers.py')
const inquiryService = read('backend/procurement/purchase_inquiry_service.py')
const directService = read('backend/procurement/scm_runtime_services.py')
const directActions = read('backend/procurement/scm_runtime_actions.py')
const router = read('frontend/src/router/index.js')
const r2Report = read('docs/governance/V1.14.2.8.4.27.2.46-Batch2.2-R2-真实运行验收报告.md')

const tests = [
  ['Purchase Mode Entry', /data-purchase-mode="STANDARD"/.test(requestPage) && /data-purchase-mode="AGREED_PRICE"/.test(requestPage) && /data-purchase-mode="DIRECT"/.test(requestPage)],
  ['STANDARD Entry', /openCreate\('STANDARD'\)/.test(requestPage)],
  ['AGREED_PRICE Entry', /purchase-request\/agreed-price/.test(requestPage) && /ScmAgreedPricePurchaseFoundationPage/.test(router)],
  ['AGREED_PRICE PurchaseRequest Form', /新建既定价格采购申请/.test(agreedPage) && /ScmPurchaseRequestOriginalBusinessRegion/.test(agreedPage) && /purchase-request-header/.test(requestForm)],
  ['AGREED_PRICE MaterialMaster Source', /data-material-source="MaterialMaster"/.test(agreedPage) && /materialProvider/.test(requestForm) && !/loadSupplierMaterialPrice/.test(agreedPage)],
  ['AGREED_PRICE Multi-Line', /新增明细/.test(requestForm) && /copyDetail/.test(requestForm) && /deleteDetail/.test(requestForm)],
  ['AGREED_PRICE Save', /保存采购申请/.test(requestForm) && /purchaseRequestApi\.create/.test(requestForm)],
  ['AGREED_PRICE purchaseMode', /openCreate\('AGREED_PRICE'\)/.test(agreedPage) && /purchaseMode:form\.purchaseMode/.test(requestForm) && /ChoiceField\(source="purchase_mode"/.test(requestSerializer)],
  ['AGREED_PRICE No Inquiry', /PURCHASE_MODE_NOT_ELIGIBLE_FOR_INQUIRY/.test(inquiryService) && /AGREED_PRICE_PURCHASE_REQUEST_READY_FOR_PRICE_CONFIRMATION/.test(requestSerializer)],
  ['DIRECT Authorization', /authorization\.value\.allowed/.test(directPage) && /DirectPurchaseAuthorization\.decide/.test(directService)],
  ['DIRECT SupplierMaterialPrice Source', /loadSupplierMaterialPrices/.test(directPage) && /supplierMaterialPriceId/.test(directService)],
  ['DIRECT Multi-Line', /addLine/.test(directPage) && /items:lines\.value\.map/.test(directPage)],
  ['DIRECT Gate', /inspectPurchaseOrderGateCreation/.test(directPage) && /signing\.dumps/.test(directService) && /signing\.loads/.test(directService)],
  ['DIRECT Human Confirmation', /direct-human-confirmation/.test(directPage) && /humanConfirmationChanged/.test(directPage) && /payload\.get\("humanConfirmed"\) is not True/.test(directService)],
  ['DIRECT Create Button State', /createState=computed/.test(directPage) && /HUMAN_CONFIRMATION_REQUIRED/.test(directPage) && /READY_TO_CREATE/.test(directPage)],
  ['DIRECT Create API', /createPurchaseOrderFromGateRequest/.test(directPage) && /previewOnly/.test(directActions)],
  ['DIRECT Transaction', /@transaction\.atomic[\s\S]{0,120}def create_from_direct_request/.test(directService)],
  ['DIRECT Idempotency', /source_trace__idempotencyKey/.test(directService) && /select_for_update/.test(directService)],
  ['DIRECT PurchaseOrder Created', /PurchaseOrder\.objects\.create/.test(directService)],
  ['DIRECT PurchaseOrderItem Created', /PurchaseOrderItem\.objects\.create/.test(directService)],
  ['DIRECT Unified Detail', /router\.push\(`\/scm\/purchase-order\/\$\{response\.data\.objectId\}`\)/.test(directPage)],
  ['Source Traceability', /source_purchase_request=request_value/.test(directService) && /source_purchase_request_item=request_item/.test(directService)],
  ['SupplierMaterialPrice Unchanged', !/SupplierMaterialPrice\.objects\.(create|update)/.test(directService)],
  ['SupplierPriceFact Unchanged', !/SupplierPriceFact/.test(directService)],
  ['No Hidden Auto Confirmation', !/humanConfirmed\.value\s*=\s*true/.test(directPage) && /humanConfirmed\.value=value===true/.test(directPage)],
  [`No ${['page','evaluate'].join('.')} Business Mutation`, !new RegExp(['page','evaluate'].join('\\.') + '|\\.eva' + 'luate\\(').test(fs.readFileSync(new URL(import.meta.url), 'utf8'))],
  ['R2 False Positive Recorded', /Automatic Acceptance：`PASS`/.test(r2Report) && exists('docs/governance/V1.14.2.8.4.27.2.46-Batch2.2-R3-既定价格采购申请归位与直接采购人工确认闭环实施报告.md')],
]

let failed = 0
for (const [name, passed] of tests) {
  console.log(`${passed ? 'PASS' : 'FAIL'} ${name}`)
  if (!passed) failed += 1
}
console.log(JSON.stringify({ version: 'V1.14.2.8.4.27.2.46-Batch2.2-R3', passed: tests.length - failed,
  total: tests.length, result: failed ? 'FAIL' : 'PASS' }, null, 2))
if (failed) process.exit(1)

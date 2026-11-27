<template>
  <section aria-label="订单交付凭证" class="delivery-evidence">
    <h4>订单交付凭证</h4>
    <template v-if="order">
      <dl class="delivery-fields" aria-label="交付日期与延期">
        <div><dt>承诺交期</dt><dd>{{ facts.promisedDate || '未提供' }}</dd></div>
        <div><dt>实际交付日期</dt><dd>{{ facts.actualDeliveryDate || '未提供' }}</dd></div>
        <div><dt>延期天数</dt><dd>{{ facts.delayDays == null ? '待核' : facts.delayDays + ' 天' }}</dd></div>
      </dl>
      <p>{{ facts.statusLabel }}。{{ facts.reason }}</p>
    </template>
    <p>批次凭证 {{ facts.batchDocumentLabel }}。<template v-if="facts.wholeOrderAcceptanceRequired">合同约定整单验收。</template></p>
    <p v-if="facts.contractPolicy">
      合同 {{ facts.contractPolicy.contractNo }} · 条款 {{ facts.contractPolicy.contractClause }} · 核对人 {{ facts.contractPolicy.verifiedBy }}
    </p>
    <p v-if="facts.wholeOrderAcceptanceRequired && facts.allLinesFulfilledDate">
      各行已足额 {{ facts.allLinesFulfilledDate }}
    </p>
    <p v-if="facts.orderAcceptance">
      整单验收单 {{ facts.orderAcceptance.sourceNo }} · 验收日期 {{ facts.orderAcceptance.businessDate }} · 核对人 {{ facts.orderAcceptance.verifiedBy }}
    </p>
    <article v-for="line in facts.lines" :key="line.salesOrderItemId" class="delivery-line">
      <h5>第 {{ line.lineNo }} 行 · {{ line.materialName }}</h5>
      <dl class="delivery-fields">
        <div><dt>应交</dt><dd>{{ line.orderedQty }} {{ line.uomLabel }}</dd></div>
        <div><dt>有效已交</dt><dd>{{ line.deliveredQty }} {{ line.uomLabel }}</dd></div>
        <div><dt>剩余</dt><dd>{{ line.remainingQty }} {{ line.uomLabel }}</dd></div>
        <div><dt>超交</dt><dd>{{ line.overDeliveredQty }} {{ line.uomLabel }}</dd></div>
        <div><dt>历史登记量（未核验）</dt><dd>{{ line.historicalUnverifiedQty }} {{ line.uomLabel }}</dd></div>
        <div><dt>首次足额日期</dt><dd>{{ line.fulfilledDate || '尚未足额' }}</dd></div>
      </dl>
      <details v-if="line.batches.length">
        <summary>查看原交付凭证（{{ line.batches.length }} 笔）</summary>
        <ul>
          <li v-for="batch in line.batches" :key="batch.deliveryAuditId">
            {{ facts.batchDocumentLabel }} {{ batch.sourceNo }} · {{ batch.businessDate }} ·
            {{ batch.quantity }} {{ line.uomLabel }} · 核对人 {{ batch.verifiedBy }} · 审计 {{ batch.deliveryAuditId }}
          </li>
        </ul>
      </details>
      <details v-if="line.historicalBatches?.length">
        <summary>查看未核验历史登记（{{ line.historicalBatches.length }} 笔）</summary>
        <ul>
          <li v-for="batch in line.historicalBatches" :key="batch.id">
            {{ batch.batchNo }} · {{ batch.actualDeliveryDate }} · {{ batch.quantity }} {{ line.uomLabel }}
          </li>
        </ul>
      </details>
    </article>
    <template v-if="order?.deliveryEvidenceAction">
      <el-button v-if="!editing" native-type="button" type="primary" @click="openRegistration">
        {{ order.deliveryEvidenceAction.label }}
      </el-button>
      <el-alert v-if="message" :type="messageType" :title="message" :closable="false" />
      <div v-if="editing" class="delivery-form-controls">
        <form
          ref="registrationForm"
          class="evidence-form evidence-subform delivery-registration-form"
          aria-label="登记交付凭证"
          tabindex="-1"
          @submit.prevent="submit"
        >
          <label class="evidence-field evidence-field--choice">登记事项
            <select v-model="form.recordKind" :disabled="busy">
              <option value="batch">分批交付凭证</option>
              <option v-if="canEnterPolicy" value="policy">合同交付约定</option>
              <option v-if="facts.wholeOrderAcceptanceRequired && facts.allLinesFulfilledDate && !facts.orderAcceptance" value="acceptance">
                整单验收单
              </option>
            </select>
          </label>
          <template v-if="form.recordKind === 'policy'">
            <label class="evidence-field evidence-field--choice">合同约定的批次凭证
              <select v-model="form.documentType" required>
                <option value="customer_receipt">客户签收单</option>
                <option value="carrier_delivery">承运人妥投凭证</option>
                <option value="installation_acceptance">安装验收单</option>
                <option value="specified_dispatch">合同约定发运凭证</option>
              </select>
            </label>
            <label class="evidence-field evidence-field--wide">原合同 {{ order.contractReference }} 的条款依据
              <textarea v-model.trim="form.contractClause" required maxlength="300" rows="2"></textarea>
            </label>
            <el-checkbox v-model="form.wholeOrderAcceptance">合同约定整单验收</el-checkbox>
          </template>
          <template v-else>
            <label v-if="form.recordKind === 'batch'" class="evidence-field delivery-order-line">交付订单行
              <select v-model="form.salesOrderItemId" required>
                <option value="" disabled>请选择</option>
                <option v-for="line in facts.lines" :key="line.salesOrderItemId" :value="line.salesOrderItemId">
                  第 {{ line.lineNo }} 行 · {{ line.materialName }}（{{ line.uomLabel }}）
                </option>
              </select>
            </label>
            <label class="evidence-field delivery-source-number">来源单号
              <input v-model.trim="form.sourceNo" required maxlength="120">
            </label>
            <label class="evidence-field delivery-business-date">凭证业务日期
              <input v-model="form.businessDate" type="date" required>
            </label>
            <label v-if="form.recordKind === 'batch'" class="evidence-field delivery-quantity">
              <span>本批有效交付数量</span>
              <input v-model="form.quantity" type="number" min="0.0001" step="0.0001" required>
              <span v-if="selectedUnit" class="delivery-quantity-unit">{{ selectedUnit }}</span>
            </label>
          </template>
          <div class="delivery-form-actions">
            <el-button native-type="submit" type="primary" :loading="busy" :disabled="busy">确认登记</el-button>
            <el-button native-type="button" :disabled="busy" @click="editing = false">取消</el-button>
          </div>
        </form>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, nextTick, reactive, ref } from 'vue'
import { evidenceWrite } from '@/api/enterpriseEvidence'
import '@/styles/evidenceControls.css'

const props = defineProps({ facts: { type: Object, required: true }, order: { type: Object, default: null } })
const emit = defineEmits(['registered'])
const editing = ref(false)
const registrationForm = ref(null)
const busy = ref(false)
const message = ref('')
const messageType = ref('success')
const form = reactive({
  recordKind: 'batch', documentType: 'customer_receipt', sourceNo: '', businessDate: '',
  salesOrderItemId: '', quantity: '', contractClause: '', wholeOrderAcceptance: false,
})
const selectedUnit = computed(() => props.facts.lines.find(line => line.salesOrderItemId === form.salesOrderItemId)?.uomLabel)
const canEnterPolicy = computed(() => props.order.deliveryEvidenceAction.canRegisterContract
  && !props.facts.contractPolicy && props.facts.lines.every(line => !line.batches.length))

async function openRegistration() {
  editing.value = true
  await nextTick()
  registrationForm.value?.focus({ preventScroll: true })
  registrationForm.value?.scrollIntoView({ block: 'nearest' })
}

async function submit() {
  const { recordKind } = form
  const payload = { recordKind, expectedVersion: props.order.version }
  if (recordKind === 'policy') {
    Object.assign(payload, {
      documentType: form.documentType, contractClause: form.contractClause,
      wholeOrderAcceptance: form.wholeOrderAcceptance,
    })
  } else {
    Object.assign(payload, { sourceNo: form.sourceNo, businessDate: form.businessDate })
    if (recordKind === 'batch') Object.assign(payload, {
      documentType: props.facts.batchDocumentType, salesOrderItemId: form.salesOrderItemId,
      quantity: form.quantity,
    })
  }
  busy.value = true
  try {
    const result = await evidenceWrite('/api/sales/orders/' + encodeURIComponent(props.order.id) + '/delivery-evidence/', payload)
    messageType.value = result.success ? 'success' : 'error'
    message.value = result.success ? '凭证已登记。' : result.error?.message || '登记结果待核，请重读原订单。'
    if (!result.success) return
    editing.value = false
    Object.assign(form, { recordKind: 'batch', sourceNo: '', businessDate: '', quantity: '' })
    emit('registered', result.data)
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.delivery-evidence { display: grid; gap: 12px; padding-block: 12px; }
.delivery-evidence > h4, .delivery-evidence p, .delivery-evidence h5 { margin: 0; }
.delivery-evidence > .el-button { justify-self: start; }
.delivery-line { padding: 12px; border: 1px solid #d6e0ee; border-radius: 8px; }
.delivery-fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(125px, 1fr)); gap: 10px; }
.delivery-fields dd { margin: 4px 0 0; font-weight: 600; }
.delivery-form-controls { min-width: 0; }
.delivery-registration-form { margin-block: 0; }
.delivery-form-actions {
  display: flex;
  flex: 1 0 100%;
  flex-wrap: wrap;
  gap: var(--evidence-gap);
}
.delivery-quantity {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  column-gap: 0;
}
.delivery-quantity > :first-child { grid-column: 1 / -1; }
.delivery-quantity-unit { margin-inline-start: 8px; }

@media (min-width: 641px) {
  .delivery-registration-form > .evidence-field--choice {
    flex-basis: 12rem;
    min-width: min(100%, 12rem);
  }
  .delivery-registration-form > .delivery-order-line {
    flex: 2 1 20rem;
    min-width: min(100%, 20rem);
  }
  .delivery-registration-form > .delivery-source-number {
    flex: 2 1 15rem;
    min-width: min(100%, 15rem);
  }
  .delivery-registration-form > :is(.delivery-business-date, .delivery-quantity) {
    flex: 0 1 11rem;
    min-width: min(100%, 11rem);
  }
  .delivery-form-actions { justify-content: flex-end; }
}
</style>
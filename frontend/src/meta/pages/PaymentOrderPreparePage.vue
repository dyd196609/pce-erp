<template>
  <main class="payment-prepare-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.12.7 正式付款单预备</p>
        <h1>{{ detail ? '正式付款单预备详情' : '正式付款单预备' }}</h1>
        <p>本页只做付款执行前检查和正式付款单预备，不执行真实付款，不生成银行支付，不生成财务凭证、总账或成本记录。</p>
        <p class="finance-current-module-badge">当前操作模块：正式付款单预备</p>
      </section>
      <nav class="page-tabs finance-flow-nav" aria-label="财务前置流程导航">
        <span class="finance-nav-title">财务前置流程导航</span>
        <router-link class="finance-nav-button" to="/finance/payable-prepares">应付预备</router-link>
        <router-link class="finance-nav-button" to="/finance/payable-checks">应付核对</router-link>
        <router-link class="finance-nav-button" to="/finance/invoice-prepares">发票预备</router-link>
        <router-link class="finance-nav-button" to="/finance/ap-drafts">应付账款草稿</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-drafts">供应商付款草稿</router-link>
        <router-link class="finance-nav-button finance-nav-button-active" to="/finance/payment-prepares">正式付款单预备 <span class="finance-current-tag">当前</span></router-link>
        <router-link class="finance-nav-button" to="/finance/payment-order-drafts">正式付款单草稿</router-link>
      </nav>
    </header>

    <el-alert v-if="message" :title="message" :type="messageType" show-icon :closable="false" />

    <section v-if="detail" class="operation-shell">
      <section class="plain-flow-guide">
        <strong>正式付款单预备流程：供应商付款草稿 -> 付款执行前检查 -> 标记可进入正式付款 -> 后续正式付款单</strong>
        <div class="plain-flow-grid">
          <span><b>当前步骤</b>对已进入可付款的供应商付款草稿做付款执行前检查。</span>
          <span><b>本页做什么</b>检查供应商、金额、发票、应付、审批、防重复付款和银行信息。</span>
          <span><b>下一步做什么</b>检查通过后标记“可进入正式付款”，留给后续 V1.12.8 生成正式付款单。</span>
          <span><b>本页不做什么</b>不真实付款、不银行支付、不生成凭证、不写总账、不做成本核算。</span>
        </div>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>{{ detail.paymentPrepareNo }}</h2>
              <span>{{ detail.sourcePaymentDraftNo || '-' }} / {{ detail.supplierName || '-' }}</span>
            </div>
            <div class="button-row">
              <el-button @click="router.push('/finance/payment-prepares')">返回列表</el-button>
              <el-button @click="router.push(`/finance/payment-draft/${detail.sourcePaymentDraftId}`)">查看供应商付款草稿</el-button>
              <el-button @click="router.push('/finance/payment-order-drafts')">查看正式付款单草稿</el-button>
              <el-button v-if="canOperate(detail)" type="primary" @click="checkPrepare(detail)">执行付款前检查</el-button>
              <el-button v-if="canOperate(detail)" type="success" :disabled="isBlockedPrepare(detail)" @click="checkedPrepare(detail)">标记已检查</el-button>
              <el-button v-if="canReady(detail)" type="warning" :disabled="isBlockedPrepare(detail)" @click="readyPrepare(detail)">标记可进入正式付款</el-button>
              <el-button v-if="canCancel(detail)" type="danger" @click="cancelPrepare(detail)">取消预备</el-button>
            </div>
          </div>
        </template>
        <el-alert v-if="isBlockedPrepare(detail)" title="付款前检查未通过，请先补正问题并重新检查。" type="error" show-icon :closable="false" />
        <div class="info-grid">
          <article v-for="item in detailFields" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>付款执行前检查项</h2></template>
        <el-table :data="detail.preCheckItems || []" border stripe height="360">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="label" label="检查项" min-width="180" />
          <el-table-column prop="passed" label="结果" width="120">
            <template #default="{ row }">
              <el-tag :type="row.passed ? 'success' : (row.severity === 'warning' ? 'warning' : 'danger')">
                {{ row.passed ? '通过' : (row.severity === 'warning' ? '警告' : '阻断') }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="severity" label="严重程度" width="120">
            <template #default="{ row }">{{ severityLabel(row.severity) }}</template>
          </el-table-column>
          <el-table-column prop="message" label="失败原因" min-width="260" />
          <el-table-column prop="suggestion" label="处理建议" min-width="300" />
          <el-table-column label="操作" :width="getActionColumnWidth(['处理'])" fixed="right">
            <template #default="{ row }">
              <el-button v-if="!row.passed && canEditCorrection(detail)" size="small" type="primary" @click="startCorrection">去补正</el-button>
              <span v-else>-</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>付款信息补正区</h2>
              <span>当前银行信息可手工补正或使用模拟数据进行流程测试；后续正式版本应从供应商档案和企业付款账户主数据中读取银行信息。</span>
            </div>
            <div class="button-row">
              <el-button v-if="!correctionEditing" :disabled="!canEditCorrection(detail)" type="primary" @click="startCorrection">编辑付款信息</el-button>
              <el-button :disabled="!canEditCorrection(detail)" type="success" @click="fillSupplierBankFromProfile">从供应商档案带出银行信息</el-button>
              <el-button :disabled="!canEditCorrection(detail)" type="success" @click="fillCompanyDefaultBank">从企业默认账户带出付款账户</el-button>
              <el-button :disabled="!canEditCorrection(detail)" type="warning" @click="fillMockBankInfo">一键填入模拟银行信息</el-button>
              <el-button @click="router.push('/foundation/suppliers')">维护供应商档案</el-button>
              <el-button v-if="correctionEditing" type="success" @click="saveCorrection">保存付款信息</el-button>
              <el-button v-if="correctionEditing" @click="cancelCorrection">取消编辑</el-button>
              <el-button type="warning" @click="checkPrepare(detail)">重新执行付款前检查</el-button>
            </div>
          </div>
        </template>
        <el-alert v-if="correctionNotice" :title="correctionNotice" type="warning" show-icon :closable="false" />
        <el-alert v-if="detail.bankInfoMocked || correctionForm.bankInfoMocked || supplierProfileForDetail?.bankInfoMocked" title="供应商银行信息为系统自动补齐模拟数据，仅用于流程验证，请后续维护真实资料。" type="warning" show-icon :closable="false" />
        <el-form class="correction-form" label-width="130px">
          <el-form-item label="付款方式">
            <el-select v-model="correctionForm.paymentMethod" :disabled="!correctionEditing">
              <el-option label="银行转账" value="bankTransfer" />
              <el-option label="现金" value="cash" />
              <el-option label="承兑" value="acceptance" />
              <el-option label="其他" value="other" />
            </el-select>
          </el-form-item>
          <el-form-item label="付款账户"><el-input v-model="correctionForm.paymentAccount" :disabled="!correctionEditing" /></el-form-item>
          <el-form-item label="付款账户名称"><el-input v-model="correctionForm.paymentAccountName" :disabled="!correctionEditing" /></el-form-item>
          <el-form-item label="付款银行"><el-input v-model="correctionForm.paymentBankName" :disabled="!correctionEditing" /></el-form-item>
          <el-form-item label="供应商开户行"><el-input v-model="correctionForm.supplierBankName" :disabled="!correctionEditing" /></el-form-item>
          <el-form-item label="供应商银行账号"><el-input v-model="correctionForm.supplierBankAccount" :disabled="!correctionEditing" /></el-form-item>
          <el-form-item label="供应商账户名称"><el-input v-model="correctionForm.supplierBankAccountName" :disabled="!correctionEditing" /></el-form-item>
          <el-form-item label="批准付款金额"><el-input-number v-model="correctionForm.approvedPayAmount" :disabled="!correctionEditing" :min="0" :precision="2" /></el-form-item>
          <el-form-item label="预备付款金额"><el-input-number v-model="correctionForm.preparePayAmount" :disabled="!correctionEditing" :min="0" :precision="2" /></el-form-item>
          <el-form-item label="预计付款日期"><el-date-picker v-model="correctionForm.expectedPayDate" :disabled="!correctionEditing" type="date" value-format="YYYY-MM-DD" /></el-form-item>
          <el-form-item label="备注"><el-input v-model="correctionForm.remark" :disabled="!correctionEditing" type="textarea" /></el-form-item>
          <el-form-item label="模拟数据说明"><el-input v-model="correctionForm.bankInfoMockRemark" disabled /></el-form-item>
        </el-form>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>检查结果详情</h2></template>
        <el-table :data="detail.preCheckItems || []" border stripe height="360">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="label" label="检查项" min-width="180" />
          <el-table-column prop="passed" label="结果" width="120">
            <template #default="{ row }">
              <el-tag :type="row.passed ? 'success' : (row.severity === 'warning' ? 'warning' : 'danger')">
                {{ row.passed ? '通过' : (row.severity === 'warning' ? '警告' : '阻断') }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="severity" label="级别" width="110" fixed="right">
            <template #default="{ row }">{{ severityLabel(row.severity) }}</template>
          </el-table-column>
          <el-table-column prop="message" label="原因" min-width="260" />
          <el-table-column prop="suggestion" label="处理建议" min-width="300" />
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>正式付款单预备明细</h2></template>
        <el-table :data="detail.lines || []" border stripe height="500">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="materialCode" label="物料编码" min-width="130" />
          <el-table-column prop="materialName" label="物料名称" min-width="160" />
          <el-table-column prop="spec" label="规格型号" min-width="120" />
          <el-table-column prop="unit" label="单位" width="90" />
          <el-table-column prop="payableAmount" label="应付金额" width="120" />
          <el-table-column prop="paidAmount" label="已付金额" width="120" />
          <el-table-column prop="unpaidAmount" label="未付金额" width="120" />
          <el-table-column prop="applyPayAmount" label="申请付款金额" width="140" />
          <el-table-column prop="approvedPayAmount" label="批准付款金额" width="140" />
          <el-table-column prop="preparePayAmount" label="预备付款金额" width="140" />
          <el-table-column prop="sourcePurchaseOrderNo" label="采购订单" min-width="150" />
          <el-table-column prop="sourceReceiveNo" label="收货单" min-width="150" />
          <el-table-column prop="sourceInspectionNo" label="检验单" min-width="150" />
          <el-table-column prop="sourceInventoryTransactionNo" label="库存流水" min-width="150" />
          <el-table-column prop="rootRequestNo" label="原始请购单" min-width="150" />
          <el-table-column prop="remark" label="备注" min-width="180" fixed="right" />
        </el-table>
      </el-card>
    </section>

    <section v-else class="operation-shell">
      <section class="plain-flow-guide">
        <strong>正式付款单预备流程：供应商付款草稿 -> 付款执行前检查 -> 标记可进入正式付款 -> 后续正式付款单</strong>
        <div class="plain-flow-grid">
          <span><b>当前步骤</b>从 paymentReady / approved 的供应商付款草稿生成正式付款单预备。</span>
          <span><b>本页做什么</b>生成预备单、批量付款前检查、标记已检查、标记可进入正式付款。</span>
          <span><b>下一步做什么</b>后续阶段再生成正式付款单和付款执行，不在本页完成。</span>
          <span><b>本页不做什么</b>不真实付款、不银行支付、不生成凭证、不写总账、不做成本核算。</span>
        </div>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>来源供应商付款草稿</h2>
              <span>只允许 approved / paymentReady 且未重复生成的供应商付款草稿进入本页。</span>
            </div>
            <div class="button-row">
              <el-button type="primary" @click="refresh">刷新来源</el-button>
              <el-button @click="router.push('/finance/payment-drafts')">查看供应商付款草稿</el-button>
              <el-button @click="router.push('/finance/payment-order-drafts')">查看正式付款单草稿</el-button>
            </div>
          </div>
        </template>
        <div class="batch-bar">
          <span>已选择 {{ selectedSourceRows.length }} 条</span>
          <span>可生成 {{ sourceBatchCounts.create }} 条</span>
          <span>跳过 {{ selectedSourceRows.length - sourceBatchCounts.create }} 条</span>
          <span class="sort-help">{{ sourceSortText }}</span>
          <el-button size="small" @click="resetSourceSorting">清除排序</el-button>
          <el-button size="small" @click="clearSourceSelection">清空选择</el-button>
          <span class="batch-action-title">当前模块操作（立即生效）</span>
          <span class="batch-action-tip">以下按钮会立即修改所选记录状态，请确认选择无误后再执行。</span>
          <el-button size="small" type="success" :disabled="!sourceBatchCounts.create" @click="runBatchCreatePrepares">批量生成正式付款单预备</el-button>
        </div>
        <BatchResult v-if="sourceBatchResult" :result="sourceBatchResult" :type="sourceBatchResultType" @close="sourceBatchResult = null" />
        <el-table ref="sourceTableRef" :data="sortedSourceRows" border stripe height="460" @selection-change="handleSourceSelectionChange" @sort-change="handleSourceSortChange">
          <el-table-column type="selection" width="48" fixed="left" :selectable="sourceSelectable" />
          <el-table-column type="expand" width="44" fixed="left">
            <template #default="{ row }">{{ row.sourceRejectReason || '可生成正式付款单预备；生成后会自动执行付款前检查。' }}</template>
          </el-table-column>
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="paymentDraftNo" label="付款草稿单号" min-width="170" sortable="custom" />
          <el-table-column prop="sourceApDraftNo" label="应付账款草稿" min-width="170" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" sortable="custom" />
          <el-table-column prop="sourcePurchaseOrderNo" label="采购订单" min-width="150" sortable="custom" />
          <el-table-column prop="sourceReceiveNo" label="收货单" min-width="150" />
          <el-table-column prop="sourceInspectionNo" label="检验单" min-width="150" />
          <el-table-column prop="sourceInventoryTransactionNos" label="库存流水" min-width="150">
            <template #default="{ row }">{{ sourceInventoryText(row) }}</template>
          </el-table-column>
          <el-table-column prop="rootRequestNo" label="原始请购单" min-width="150" />
          <el-table-column prop="unpaidAmount" label="未付金额" width="120" sortable="custom" />
          <el-table-column prop="applyPayAmount" label="申请付款金额" width="140" sortable="custom" />
          <el-table-column prop="paymentDraftStatus" label="付款草稿状态" width="150" sortable="custom">
            <template #default="{ row }"><el-tag :type="paymentDraftStatusType(row.paymentDraftStatus)">{{ paymentDraftStatusLabel(row.paymentDraftStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="是否已生成付款预备" width="170">
            <template #default="{ row }"><el-tag :type="row.paymentPrepareGenerated ? 'success' : 'info'">{{ row.paymentPrepareGeneratedText }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="getActionColumnWidth(['查看付款草稿', '生成付款预备'])">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button size="small" class="app-action-button-md" @click="router.push(`/finance/payment-draft/${row.id}`)">查看付款草稿</el-button>
                <el-button v-if="!row.paymentPrepareGenerated" size="small" class="app-action-button-md" type="success" :disabled="!row.canCreatePaymentPrepare" @click="createPrepare(row)">生成付款预备</el-button>
                <el-button v-else size="small" class="app-action-button-md" type="success" @click="viewPaymentPrepareFromSource(row)">查看付款预备</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>正式付款单预备列表</h2></template>
        <div class="batch-bar">
          <span>已选择 {{ selectedPrepareRows.length }} 条</span>
          <span class="sort-help">{{ prepareSortText }}</span>
          <el-button size="small" @click="resetPrepareSorting">清除排序</el-button>
          <el-button size="small" @click="clearPrepareSelection">清空选择</el-button>
          <span class="batch-action-title">当前模块操作（立即生效）</span>
          <span class="batch-action-tip">以下按钮会立即修改所选记录状态，请确认选择无误后再执行。</span>
          <el-button size="small" type="primary" :disabled="!selectedPrepareRows.length" @click="runBatchChecks">批量执行付款前检查</el-button>
          <el-button size="small" type="success" :disabled="!selectedPrepareRows.length" @click="runBatchChecked">批量标记已检查</el-button>
          <el-button size="small" type="warning" :disabled="!selectedPrepareRows.length" @click="runBatchReady">批量标记可进入正式付款</el-button>
          <el-button size="small" type="danger" :disabled="!selectedPrepareRows.length" @click="runBatchCancel">批量取消预备</el-button>
        </div>
        <BatchResult v-if="prepareBatchResult" :result="prepareBatchResult" :type="prepareBatchResultType" @close="prepareBatchResult = null" />
        <el-table ref="prepareTableRef" :data="sortedPrepareRows" border stripe height="520" @selection-change="handlePrepareSelectionChange" @sort-change="handlePrepareSortChange">
          <el-table-column type="selection" width="48" fixed="left" />
          <el-table-column type="expand" width="44" fixed="left">
            <template #default="{ row }">
              <div class="check-detail-panel">
                <strong>检查结果详情：{{ row.preCheckResult || '尚未执行付款前检查。' }}</strong>
                <el-table :data="row.preCheckItems || []" border size="small">
                  <el-table-column prop="label" label="检查项" min-width="160" />
                  <el-table-column prop="passed" label="结果" width="100">
                    <template #default="{ row: item }">
                      <el-tag :type="item.passed ? 'success' : (item.severity === 'warning' ? 'warning' : 'danger')">
                        {{ item.passed ? '通过' : (item.severity === 'warning' ? '警告' : '阻断') }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="severity" label="严重程度" width="110" />
                  <el-table-column prop="message" label="原因" min-width="220" />
                  <el-table-column prop="suggestion" label="处理建议" min-width="260" />
                </el-table>
              </div>
            </template>
          </el-table-column>
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="paymentPrepareNo" label="付款预备单号" min-width="170" sortable="custom" />
          <el-table-column prop="sourcePaymentDraftNo" label="来源付款草稿" min-width="170" sortable="custom" />
          <el-table-column prop="sourceApDraftNo" label="来源应付草稿" min-width="170" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" sortable="custom" />
          <el-table-column prop="preparePayAmount" label="预备付款金额" width="140" sortable="custom" />
          <el-table-column prop="expectedPayDate" label="预计付款日期" width="130" sortable="custom" />
          <el-table-column prop="paymentMethod" label="付款方式" width="130">
            <template #default="{ row }">{{ paymentMethodLabel(row.paymentMethod) }}</template>
          </el-table-column>
          <el-table-column prop="preCheckStatus" label="前置检查" width="140" sortable="custom">
            <template #default="{ row }"><el-tag :type="preCheckStatusType(row.preCheckStatus)">{{ preCheckStatusLabel(row.preCheckStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="riskLevel" label="风险级别" width="120" sortable="custom">
            <template #default="{ row }">{{ riskLevelLabel(row.riskLevel) }}</template>
          </el-table-column>
          <el-table-column prop="paymentPrepareStatus" label="预备状态" width="150" sortable="custom">
            <template #default="{ row }"><el-tag :type="paymentPrepareStatusType(row.paymentPrepareStatus)">{{ paymentPrepareStatusLabel(row.paymentPrepareStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="prepareActionColumnWidth">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button size="small" class="app-action-button-sm" @click="router.push(`/finance/payment-prepare/${row.id}`)">查看详情</el-button>
                <el-button v-if="canOperate(row)" size="small" class="app-action-button-sm" type="primary" @click="checkPrepare(row)">执行检查</el-button>
                <el-button v-if="canOperate(row)" size="small" class="app-action-button-md" type="success" :disabled="isBlockedPrepare(row)" @click="checkedPrepare(row)">标记已检查</el-button>
                <el-button v-if="canReady(row)" size="small" class="app-action-button-lg" type="warning" :disabled="isBlockedPrepare(row)" @click="readyPrepare(row)">可进入正式付款</el-button>
                <el-button v-if="canCancel(row)" size="small" class="app-action-button-sm" type="danger" @click="cancelPrepare(row)">取消</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </section>
  </main>
</template>

<script setup>
import { computed, defineComponent, h, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  buildPaymentPrepareSupplierBankFields,
  getDefaultCompanyBankAccount,
  getSupplierProfileByIdentity,
  normalizePaymentMethod,
  writeBusinessPartnerLog,
} from '../foundation/businessPartnerStore.js'
import {
  batchCancelPaymentPrepares,
  batchCreatePaymentPreparesFromPaymentDrafts,
  batchMarkPaymentPrepareChecked,
  batchMarkPaymentPrepareReady,
  batchRunPaymentPreChecks,
  cancelPaymentPrepare,
  createPaymentPrepareFromPaymentDraft,
  getPaymentOrderPrepareById,
  getPaymentPrepareSourcesFromPaymentDrafts,
  listPaymentOrderPrepares,
  markPaymentPrepareChecked,
  markPaymentPrepareReady,
  markPaymentPrepareChecking,
  updatePaymentPrepare,
  writePaymentPrepareLog,
} from '../finance/paymentOrderPrepareStore.js'
import { getActionColumnWidth, getActionColumnWidthForRows } from '../runtime/tableActionColumnEngine.js'
import { sortRecords } from '../runtime/tableSortEngine.js'

const BatchResult = defineComponent({
  props: { result: { type: Object, required: true }, type: { type: String, default: 'success' } },
  emits: ['close'],
  setup(props, { emit }) {
    return () => h('div', { class: ['batch-result', props.type] }, [
      h('button', { type: 'button', onClick: () => emit('close') }, '关闭'),
      h('strong', '批量操作完成'),
      h('span', `操作名称：${props.result.operationName}`),
      h('span', `已选择：${props.result.total} 条`),
      h('span', `成功：${props.result.successCount} 条`),
      h('span', `失败/跳过：${props.result.failedCount} 条`),
      props.result.failedReason?.length ? h('ol', props.result.failedReason.map((reason) => h('li', { key: reason }, reason))) : null,
      props.result.nextSuggestion ? h('span', `下一步建议：${props.result.nextSuggestion}`) : null,
    ])
  },
})

const route = useRoute()
const router = useRouter()
const sourceRows = ref([])
const prepareRows = ref([])
const selectedSourceRows = ref([])
const selectedPrepareRows = ref([])
const sourceSortState = ref({ key: '', direction: 'asc' })
const prepareSortState = ref({ key: '', direction: 'asc' })
const sourceTableRef = ref(null)
const prepareTableRef = ref(null)
const message = ref('')
const messageType = ref('success')
const sourceBatchResult = ref(null)
const sourceBatchResultType = ref('success')
const prepareBatchResult = ref(null)
const prepareBatchResultType = ref('success')
const correctionEditing = ref(false)
const correctionNotice = ref('')
const correctionForm = ref(defaultCorrectionForm())
const detailVersion = ref(0)

const detail = computed(() => {
  detailVersion.value
  return route.params.id ? getPaymentOrderPrepareById(route.params.id) : null
})
const supplierProfileForDetail = computed(() => detail.value ? getSupplierProfileByIdentity({
  supplierId: detail.value.supplierId,
  supplierName: detail.value.supplierName,
}) : null)
const sourceIds = computed(() => selectedSourceRows.value.map((row) => row.id).filter(Boolean))
const prepareIds = computed(() => selectedPrepareRows.value.map((row) => row.id).filter(Boolean))
const sourceSortColumns = [
  { key: 'paymentDraftNo', sortType: 'string' },
  { key: 'sourceApDraftNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'sourcePurchaseOrderNo', sortType: 'string' },
  { key: 'unpaidAmount', sortType: 'amount' },
  { key: 'applyPayAmount', sortType: 'amount' },
  { key: 'paymentDraftStatus', sortType: 'status' },
]
const prepareSortColumns = [
  { key: 'paymentPrepareNo', sortType: 'string' },
  { key: 'sourcePaymentDraftNo', sortType: 'string' },
  { key: 'sourceApDraftNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'preparePayAmount', sortType: 'amount' },
  { key: 'expectedPayDate', sortType: 'date' },
  { key: 'preCheckStatus', sortType: 'status' },
  { key: 'riskLevel', sortType: 'status' },
  { key: 'paymentPrepareStatus', sortType: 'status' },
]
const sortedSourceRows = computed(() => sortRecords(sourceRows.value, sourceSortState.value, sourceSortColumns))
const sortedPrepareRows = computed(() => sortRecords(prepareRows.value, prepareSortState.value, prepareSortColumns))
const sourceBatchCounts = computed(() => ({ create: selectedSourceRows.value.filter((row) => row.canCreatePaymentPrepare).length }))
const prepareActionColumnWidth = computed(() => getActionColumnWidthForRows(sortedPrepareRows.value, prepareRowActions, ['查看详情']))
const sourceSortText = computed(() => currentSortText(sourceSortState.value, {
  paymentDraftNo: '付款草稿单号',
  sourceApDraftNo: '应付账款草稿',
  supplierName: '供应商',
  sourcePurchaseOrderNo: '采购订单',
  unpaidAmount: '未付金额',
  applyPayAmount: '申请付款金额',
  paymentDraftStatus: '付款草稿状态',
}))
const prepareSortText = computed(() => currentSortText(prepareSortState.value, {
  paymentPrepareNo: '付款预备单号',
  sourcePaymentDraftNo: '来源付款草稿',
  sourceApDraftNo: '来源应付草稿',
  supplierName: '供应商',
  preparePayAmount: '预备付款金额',
  expectedPayDate: '预计付款日期',
  preCheckStatus: '前置检查',
  riskLevel: '风险级别',
  paymentPrepareStatus: '预备状态',
}))
const detailFields = computed(() => detail.value ? [
  { label: '付款预备单号', value: detail.value.paymentPrepareNo },
  { label: '来源付款草稿', value: detail.value.sourcePaymentDraftNo || '-' },
  { label: '来源应付账款草稿', value: detail.value.sourceApDraftNo || '-' },
  { label: '来源发票预备', value: detail.value.sourceInvoicePrepareNo || '-' },
  { label: '来源应付核对', value: detail.value.sourcePayableCheckNo || '-' },
  { label: '来源应付预备', value: detail.value.sourcePayablePrepareNo || '-' },
  { label: '供应商', value: detail.value.supplierName || '-' },
  { label: '采购订单', value: detail.value.sourcePurchaseOrderNo || '-' },
  { label: '收货单', value: detail.value.sourceReceiveNo || '-' },
  { label: '检验单', value: detail.value.sourceInspectionNo || '-' },
  { label: '库存流水', value: sourceInventoryText(detail.value) },
  { label: '原始请购单', value: detail.value.rootRequestNo || '-' },
  { label: '应付金额', value: detail.value.totalPayableAmount },
  { label: '已付金额', value: detail.value.paidAmount },
  { label: '未付金额', value: detail.value.unpaidAmount },
  { label: '申请付款金额', value: detail.value.applyPayAmount },
  { label: '批准付款金额', value: detail.value.approvedPayAmount },
  { label: '预备付款金额', value: detail.value.preparePayAmount },
  { label: '预计付款日期', value: detail.value.expectedPayDate || '-' },
  { label: '付款方式', value: paymentMethodLabel(detail.value.paymentMethod) },
  { label: '付款账户', value: detail.value.paymentAccount || '-' },
  { label: '供应商开户行', value: detail.value.supplierBankName || '-' },
  { label: '供应商银行账号', value: detail.value.supplierBankAccount || '-' },
  { label: '前置检查', value: preCheckStatusLabel(detail.value.preCheckStatus) },
  { label: '风险级别', value: riskLevelLabel(detail.value.riskLevel) },
  { label: '预备状态', value: paymentPrepareStatusLabel(detail.value.paymentPrepareStatus) },
  { label: '真实付款状态', value: realPaymentStatusLabel(detail.value.realPaymentStatus) },
  { label: '凭证状态', value: voucherStatusLabel(detail.value.voucherStatus) },
] : [])

function defaultCorrectionForm() {
  return {
    paymentMethod: 'bankTransfer',
    paymentAccount: '',
    paymentAccountName: '',
    paymentBankName: '',
    supplierBankName: '',
    supplierBankAccount: '',
    supplierBankAccountName: '',
    approvedPayAmount: 0,
    preparePayAmount: 0,
    expectedPayDate: '',
    remark: '',
    bankInfoMocked: false,
    bankInfoMockedAt: '',
    bankInfoMockRemark: '',
  }
}

function syncCorrectionForm(record = detail.value) {
  correctionForm.value = {
    paymentMethod: record?.paymentMethod || 'bankTransfer',
    paymentAccount: record?.paymentAccount || '',
    paymentAccountName: record?.paymentAccountName || '',
    paymentBankName: record?.paymentBankName || '',
    supplierBankName: record?.supplierBankName || '',
    supplierBankAccount: record?.supplierBankAccount || '',
    supplierBankAccountName: record?.supplierBankAccountName || '',
    approvedPayAmount: Number(record?.approvedPayAmount || 0),
    preparePayAmount: Number(record?.preparePayAmount || 0),
    expectedPayDate: record?.expectedPayDate || '',
    remark: record?.remark || '',
    bankInfoMocked: record?.bankInfoMocked ?? false,
    bankInfoMockedAt: record?.bankInfoMockedAt || '',
    bankInfoMockRemark: record?.bankInfoMockRemark || '',
  }
}

function refresh() {
  sourceRows.value = getPaymentPrepareSourcesFromPaymentDrafts()
  prepareRows.value = listPaymentOrderPrepares()
  detailVersion.value += 1
}

function notify(text, type = 'success') {
  message.value = text
  messageType.value = type
  window.clearTimeout(notify.timer)
  notify.timer = window.setTimeout(() => { message.value = '' }, 2400)
}

function currentSortText(state = {}, labels = {}) {
  if (!state.key) return '当前排序：默认顺序。表格支持点击表头排序，左侧序号冻结，右侧操作冻结。'
  return `当前排序：${labels[state.key] || state.key} / ${state.direction === 'desc' ? '降序' : '升序'}`
}

function handleSourceSelectionChange(rows) { selectedSourceRows.value = rows || [] }
function handlePrepareSelectionChange(rows) { selectedPrepareRows.value = rows || [] }
function clearSourceSelection() { selectedSourceRows.value = []; sourceTableRef.value?.clearSelection?.() }
function clearPrepareSelection() { selectedPrepareRows.value = []; prepareTableRef.value?.clearSelection?.() }
function sourceSelectable(row) { return row.canCreatePaymentPrepare }

function prepareRowActions(row = {}) {
  return [
    '查看详情',
    { label: '执行检查', visible: canOperate(row) },
    { label: '标记已检查', visible: canOperate(row) },
    { label: '可进入正式付款', visible: canReady(row) },
    { label: '取消', visible: canCancel(row) },
  ]
}

function handleSourceSortChange({ prop, order }) {
  sourceSortState.value = { key: prop || '', direction: order === 'descending' ? 'desc' : 'asc' }
  clearSourceSelection()
}

function handlePrepareSortChange({ prop, order }) {
  prepareSortState.value = { key: prop || '', direction: order === 'descending' ? 'desc' : 'asc' }
  clearPrepareSelection()
}

function resetSourceSorting() { sourceSortState.value = { key: '', direction: 'asc' }; clearSourceSelection() }
function resetPrepareSorting() { prepareSortState.value = { key: '', direction: 'asc' }; clearPrepareSelection() }

function nextBatchSuggestion(reasons = []) {
  const text = reasons.join('；')
  if (text.includes('重复') || text.includes('已生成')) return '建议查看已生成的付款预备；若原预备已取消，可重新生成。'
  if (text.includes('approved') || text.includes('paymentReady') || text.includes('审批')) return '建议先在供应商付款草稿中完成审批或标记可付款。'
  if (text.includes('金额') || text.includes('未付款')) return '建议检查未付金额、申请付款金额和预备付款金额。'
  if (text.includes('银行') || text.includes('账户')) return '建议补充付款账户和供应商收款账户后重新检查。'
  if (text.includes('检查')) return '建议处理阻断项后重新执行付款前检查。'
  return '请按失败原因处理后重新执行。'
}

function normalizeBatchResult(result = {}, operationName = '批量操作') {
  const failedReason = result.failedReason || []
  return {
    operationName,
    total: result.total ?? 0,
    successCount: result.successCount || 0,
    failedCount: result.failedCount || 0,
    failedReason,
    nextSuggestion: nextBatchSuggestion(failedReason),
  }
}

function showSourceBatchResult(result, operationName) {
  refresh()
  clearSourceSelection()
  sourceBatchResult.value = normalizeBatchResult(result, operationName)
  sourceBatchResultType.value = result?.failedCount ? (result.successCount ? 'warning' : 'error') : 'success'
}

function showPrepareBatchResult(result, operationName) {
  refresh()
  clearPrepareSelection()
  prepareBatchResult.value = normalizeBatchResult(result, operationName)
  prepareBatchResultType.value = result?.failedCount ? (result.successCount ? 'warning' : 'error') : 'success'
}

function runBatchCreatePrepares() {
  if (!sourceIds.value.length) return notify('请先选择可生成正式付款单预备的供应商付款草稿。', 'warning')
  showSourceBatchResult(batchCreatePaymentPreparesFromPaymentDrafts(sourceIds.value), '批量生成正式付款单预备')
}

function runBatchChecks() {
  if (!prepareIds.value.length) return notify('请先选择正式付款单预备。', 'warning')
  showPrepareBatchResult(batchRunPaymentPreChecks(prepareIds.value), '批量执行付款前检查')
}

function runBatchChecked() {
  if (!prepareIds.value.length) return notify('请先选择正式付款单预备。', 'warning')
  showPrepareBatchResult(batchMarkPaymentPrepareChecked(prepareIds.value), '批量标记已检查')
}

function runBatchReady() {
  if (!prepareIds.value.length) return notify('请先选择正式付款单预备。', 'warning')
  showPrepareBatchResult(batchMarkPaymentPrepareReady(prepareIds.value), '批量标记可进入正式付款')
}

function runBatchCancel() {
  if (!prepareIds.value.length) return notify('请先选择正式付款单预备。', 'warning')
  showPrepareBatchResult(batchCancelPaymentPrepares(prepareIds.value), '批量取消正式付款单预备')
}

function createPrepare(row) {
  const outcome = createPaymentPrepareFromPaymentDraft(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify(`已生成正式付款单预备 ${outcome.paymentPrepareNo}`)
}

function viewPaymentPrepareFromSource(row = {}) {
  if (row.targetPaymentPrepareId) return router.push(`/finance/payment-prepare/${row.targetPaymentPrepareId}`)
  notify(row.targetPaymentPrepareNo ? `已生成正式付款单预备 ${row.targetPaymentPrepareNo}，请在列表中查看。` : '已生成正式付款单预备，请在列表中查看。', 'warning')
  return router.push('/finance/payment-prepares')
}

function checkPrepare(row) {
  const outcome = markPaymentPrepareChecking(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify(outcome.paymentOrderPrepare.preCheckStatus === 'blocked' ? '付款前检查存在阻断项。' : '付款前检查已执行。', outcome.paymentOrderPrepare.preCheckStatus === 'blocked' ? 'warning' : 'success')
}

function checkedPrepare(row) {
  if (isBlockedPrepare(row)) {
    notify('付款前检查未通过，请先补正问题并重新检查。', 'warning')
    return
  }
  const outcome = markPaymentPrepareChecked(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify(outcome.paymentOrderPrepare.preCheckStatus === 'blocked' ? '付款前检查未通过，已标记阻断。' : '已标记付款前检查完成。', outcome.paymentOrderPrepare.preCheckStatus === 'blocked' ? 'warning' : 'success')
}

function readyPrepare(row) {
  if (isBlockedPrepare(row)) {
    notify('付款前检查未通过，请先补正问题并重新检查。', 'warning')
    return
  }
  const outcome = markPaymentPrepareReady(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify('已标记可进入正式付款；本轮不执行真实付款。')
}

function cancelPrepare(row) {
  const outcome = cancelPaymentPrepare(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify('正式付款单预备已取消。')
}

function canOperate(row = {}) {
  return !['ready', 'cancelled', 'closed'].includes(row.paymentPrepareStatus)
}

function canReady(row = {}) {
  return ['draft', 'checking', 'checked'].includes(row.paymentPrepareStatus)
}

function isBlockedPrepare(row = {}) {
  return row.preCheckStatus === 'blocked' || row.riskLevel === 'high'
}

function canEditCorrection(row = {}) {
  return ['blocked', 'draft', 'checking'].includes(row.paymentPrepareStatus)
}

function startCorrection() {
  if (!canEditCorrection(detail.value)) return notify('当前状态不允许编辑付款信息。', 'warning')
  syncCorrectionForm()
  correctionEditing.value = true
  correctionNotice.value = ''
  writePaymentPrepareLog('编辑付款信息', { targetId: detail.value.id, targetNo: detail.value.paymentPrepareNo })
}

function ensureCorrectionEditing() {
  if (!canEditCorrection(detail.value)) {
    notify('当前状态不允许编辑付款信息。', 'warning')
    return false
  }
  if (!correctionEditing.value) {
    syncCorrectionForm()
    correctionEditing.value = true
  }
  return true
}

function fillSupplierBankFromProfile() {
  if (!ensureCorrectionEditing()) return
  const supplier = getSupplierProfileByIdentity({
    supplierId: detail.value?.supplierId,
    supplierName: detail.value?.supplierName,
  })
  if (!supplier) {
    notify('未找到供应商档案，请先维护供应商档案或执行“归集历史供应商”。', 'warning')
    return
  }
  const supplierBankFields = buildPaymentPrepareSupplierBankFields(supplier)
  const patch = {
    ...supplierBankFields,
    bankInfoMocked: Boolean(supplier.bankInfoMocked),
    bankInfoMockedAt: supplier.bankInfoMockedAt || '',
    bankInfoMockRemark: supplier.bankInfoMocked ? '供应商银行信息为系统自动补齐模拟数据，仅用于流程验证，请后续维护真实资料。' : '',
  }
  correctionForm.value = {
    ...correctionForm.value,
    ...patch,
  }
  const outcome = updatePaymentPrepare(detail.value.id, patch)
  if (!outcome.success) return notify(outcome.error, 'warning')
  correctionNotice.value = supplier.bankInfoMocked
    ? '已从供应商档案带出收款银行信息并保存；当前供应商银行信息为系统自动补齐模拟数据，仅用于流程测试。请重新执行付款前检查。'
    : '已从供应商档案带出收款银行信息并保存，请重新执行付款前检查。'
  writePaymentPrepareLog('从供应商档案带出银行信息', { targetId: detail.value.id, targetNo: detail.value.paymentPrepareNo, result: supplier.supplierName })
  writeBusinessPartnerLog('从供应商档案带出银行信息', { targetType: 'paymentOrderPrepare', targetId: detail.value.id, targetNo: detail.value.paymentPrepareNo, detail: supplier.supplierName })
  refresh()
  notify('已从供应商档案带出收款银行信息并保存，请重新执行付款前检查。', supplier.bankInfoMocked ? 'warning' : 'success')
}

function fillCompanyDefaultBank() {
  if (!ensureCorrectionEditing()) return
  const account = getDefaultCompanyBankAccount()
  if (!account) {
    notify('未找到启用的企业银行账户，请先维护企业银行账户。', 'warning')
    return
  }
  const patch = {
    paymentAccount: account.bankAccount || '',
    paymentAccountName: account.accountName || '',
    paymentBankName: account.bankName || '',
    paymentMethod: normalizePaymentMethod(correctionForm.value.paymentMethod || detail.value?.paymentMethod || 'bankTransfer'),
  }
  correctionForm.value = {
    ...correctionForm.value,
    ...patch,
  }
  const outcome = updatePaymentPrepare(detail.value.id, patch)
  if (!outcome.success) return notify(outcome.error, 'warning')
  correctionNotice.value = '已从企业默认账户带出付款账户并保存，请重新执行付款前检查。'
  writePaymentPrepareLog('从企业银行账户带出付款账户', { targetId: detail.value.id, targetNo: detail.value.paymentPrepareNo, result: account.accountCode })
  writeBusinessPartnerLog('从企业银行账户带出付款账户', { targetType: 'paymentOrderPrepare', targetId: detail.value.id, targetNo: detail.value.paymentPrepareNo, detail: account.accountCode })
  refresh()
  notify('已从企业默认账户带出付款账户并保存，请重新执行付款前检查。')
}

function fillMockBankInfo() {
  if (!ensureCorrectionEditing()) return
  const patch = {
    paymentMethod: 'bankTransfer',
    paymentBankName: '中国工商银行深圳科技园支行',
    paymentAccountName: '广东智造科技有限公司',
    paymentAccount: '6222020200008888666',
    supplierBankName: '中国建设银行东莞制造业支行',
    supplierBankAccountName: detail.value?.supplierName || '模拟供应商账户',
    supplierBankAccount: '6217000000008888999',
    bankInfoMocked: true,
    bankInfoMockedAt: new Date().toISOString(),
    bankInfoMockRemark: '模拟银行信息，仅用于本地流程验证',
  }
  correctionForm.value = {
    ...correctionForm.value,
    ...patch,
  }
  const outcome = updatePaymentPrepare(detail.value.id, patch)
  if (!outcome.success) return notify(outcome.error, 'warning')
  correctionNotice.value = '已填入模拟银行信息并保存，仅用于本地业务流程验证，不代表真实银行账户。建议优先维护供应商档案。'
  writePaymentPrepareLog('一键填入模拟银行信息', { targetId: detail.value.id, targetNo: detail.value.paymentPrepareNo, result: '模拟银行信息，仅用于本地流程验证' })
  refresh()
  notify('已填入模拟银行信息并保存，仅用于本地业务流程验证，不代表真实银行账户。', 'warning')
}

function cancelCorrection() {
  syncCorrectionForm()
  correctionEditing.value = false
  correctionNotice.value = ''
}

function saveCorrection() {
  if (!detail.value) return
  const outcome = updatePaymentPrepare(detail.value.id, correctionForm.value)
  if (!outcome.success) return notify(outcome.error, 'warning')
  correctionEditing.value = false
  correctionNotice.value = '付款信息已修改，请重新执行付款前检查。'
  refresh()
  notify('付款信息已保存，请重新执行付款前检查。', 'warning')
}

function canCancel(row = {}) {
  return ['draft', 'checking', 'checked', 'blocked'].includes(row.paymentPrepareStatus)
}

function paymentDraftStatusLabel(status) {
  return { draft: '草稿', submitted: '已提交', approved: '已审批', paymentReady: '可付款', cancelled: '取消', closed: '关闭' }[status] || status || '-'
}
function paymentDraftStatusType(status) {
  return { draft: 'info', submitted: 'primary', approved: 'success', paymentReady: 'warning', cancelled: 'info', closed: 'info' }[status] || 'info'
}
function paymentPrepareStatusLabel(status) {
  return { draft: '草稿', checking: '检查中', checked: '已检查', ready: '可进入正式付款', blocked: '检查未通过', cancelled: '取消', closed: '关闭' }[status] || status || '-'
}
function paymentPrepareStatusType(status) {
  return { draft: 'info', checking: 'primary', checked: 'success', ready: 'warning', blocked: 'danger', cancelled: 'info', closed: 'info' }[status] || 'info'
}
function preCheckStatusLabel(status) {
  return { notChecked: '未检查', pending: '需要重新检查', passed: '通过', warning: '有警告', blocked: '阻断' }[status] || status || '-'
}
function preCheckStatusType(status) {
  return { notChecked: 'info', pending: 'warning', passed: 'success', warning: 'warning', blocked: 'danger' }[status] || 'info'
}
function riskLevelLabel(level) {
  return { none: '未检查', low: '低风险', medium: '中风险', high: '高风险' }[level] || level || '-'
}
function paymentMethodLabel(method) {
  return { bankTransfer: '银行转账', cash: '现金', acceptance: '承兑', other: '其他' }[method] || method || '-'
}
function realPaymentStatusLabel(status) {
  return { notPaid: '未付款', paymentPrepared: '已预备，未付款', partial: '部分付款', paid: '已付款' }[status] || status || '-'
}
function voucherStatusLabel(status) {
  return { notGenerated: '未生成凭证', voucherReady: '可生成凭证', generated: '已生成凭证' }[status] || status || '-'
}
function severityLabel(severity) {
  return { info: '提示', warning: '警告', error: '阻断' }[severity] || severity || '-'
}
function sourceInventoryText(row = {}) {
  const nos = row.sourceInventoryTransactionNos || row.sourceInventoryTransactionNo || ''
  if (Array.isArray(nos)) return nos.filter(Boolean).join('、') || '-'
  return nos || '-'
}

watch(() => route.fullPath, refresh, { immediate: true })
watch(detail, (record) => {
  if (record) syncCorrectionForm(record)
  correctionEditing.value = false
  correctionNotice.value = ''
}, { immediate: true })
</script>

<style scoped>
.payment-prepare-page { display: flex; flex-direction: column; gap: 16px; min-height: 100%; padding: 22px; background: #f5f7fb; color: #172033; }
.page-header, .card-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.page-header p { margin: 6px 0 0; color: #475467; line-height: 1.5; }
.eyebrow, .card-header span, .info-grid span { color: #64748b; font-size: 13px; }
h1, h2 { margin: 0; }
.page-tabs, .button-row, .batch-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.finance-flow-nav { align-items: stretch; border: 1px solid #dbeafe; border-radius: 8px; padding: 10px; background: #f8fbff; }
.finance-nav-title { display: flex; align-items: center; color: #475467; font-size: 13px; font-weight: 700; margin-right: 4px; }
.page-tabs a, .finance-nav-button { border: 1px solid #bfdbfe; border-radius: 6px; padding: 8px 12px; background: #fff; color: #1d4ed8; font-weight: 700; text-decoration: none; white-space: nowrap; }
.page-tabs a.finance-nav-button-active { border-color: #0f766e; background: #0f766e; color: #fff; box-shadow: 0 6px 14px rgba(15, 118, 110, 0.18); }
.finance-current-tag { display: inline-flex; align-items: center; margin-left: 6px; border-radius: 999px; padding: 2px 7px; background: rgba(255, 255, 255, 0.22); color: inherit; font-size: 12px; }
.finance-current-module-badge { display: inline-flex; width: fit-content; border: 1px solid #99f6e4; border-radius: 999px; padding: 5px 10px; background: #ecfdf5; color: #0f766e !important; font-weight: 800; }
.operation-shell { display: flex; flex-direction: column; gap: 16px; }
.plain-flow-guide { display: grid; gap: 10px; border: 1px solid #a7f3d0; border-radius: 8px; padding: 14px; background: #ecfdf5; color: #064e3b; line-height: 1.6; }
.plain-flow-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.plain-flow-grid span { display: grid; gap: 4px; border: 1px solid rgba(6, 78, 59, 0.14); border-radius: 8px; padding: 10px; background: #fff; }
.info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin-top: 14px; }
.info-grid article { border: 1px solid #dbe3ef; border-radius: 8px; padding: 12px; background: #fff; }
.info-grid strong { display: block; margin-top: 4px; }
.correction-form { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 2px 12px; }
.check-detail-panel { display: grid; gap: 10px; padding: 8px; }
.batch-bar { border: 1px solid #dbe3ef; border-radius: 8px; padding: 10px; margin-bottom: 12px; background: #f8fafc; }
.button-row .el-button, .batch-bar .el-button { min-width: 96px; white-space: nowrap; }
.button-row .el-button--small, .batch-bar .el-button--small { min-width: 86px; }
.button-row .el-button--primary, .button-row .el-button--success, .button-row .el-button--warning,
.batch-bar .el-button--primary, .batch-bar .el-button--success, .batch-bar .el-button--warning { min-width: 132px; }
.button-row .el-button--danger, .batch-bar .el-button--danger { min-width: 86px; }
.sort-help { color: #64748b; font-size: 13px; }
.batch-result { position: relative; display: grid; gap: 6px; margin-bottom: 12px; border-radius: 8px; padding: 12px; background: #ecfdf5; color: #065f46; }
.batch-result.warning { background: #fffbeb; color: #92400e; }
.batch-result.error { background: #fef2f2; color: #991b1b; }
.batch-result button { position: absolute; top: 8px; right: 8px; border: 0; background: transparent; color: inherit; cursor: pointer; }
@media (max-width: 900px) {
  .page-header { align-items: flex-start; flex-direction: column; }
  .plain-flow-grid { grid-template-columns: 1fr; }
}
</style>

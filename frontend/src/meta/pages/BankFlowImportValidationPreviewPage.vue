<template>
  <main class="bank-flow-import-validation-preview-page app-page-shell">
    <section class="app-hero-section">
      <div>
        <p class="app-eyebrow">V1.13.49 · Finance</p>
        <h1>银行流水导入校验预览</h1>
        <p class="app-hero-copy">
          本页用于银行流水只读对象数据来源适配、导入校验预览和来源缺失提示加固。
          本轮不上传文件，不读取 Excel / CSV，不导入银行流水，不创建导入批次，不进入待匹配，不核销，不写总账。
        </p>
      </div>
      <div class="page-actions">
        <router-link class="app-nav-button" to="/finance/settlement-boundary-overview">查看企业结算边界总览</router-link>
        <router-link class="app-nav-button" :to="`/finance/payment-voucher-prepare-preview/${routePaymentExecutionPrepareNoText}`">查看付款凭证准备只读预览</router-link>
        <router-link class="app-nav-button" to="/finance/payment-execution-prepares">返回付款执行准备页</router-link>
        <el-button type="primary" plain @click="copyDiagnosticData">复制诊断数据</el-button>
      </div>
    </section>

    <section v-if="!paymentExecutionPrepareFound" class="warning-card">
      <h2>未找到付款执行准备单</h2>
      <p>当前路径参数：{{ routePaymentExecutionPrepareNoText }}</p>
      <p>未找到原因：{{ notFoundReason }}</p>
      <ul>
        <li>本轮未上传文件。</li>
        <li>本轮未读取 Excel / CSV。</li>
        <li>本轮未导入银行流水。</li>
        <li>本轮未创建导入批次。</li>
        <li>本轮未生成银行流水。</li>
        <li>本轮未核销。</li>
        <li>本轮未写总账。</li>
      </ul>
    </section>

    <section class="boundary-card">
      <strong>本轮统一保护结论：</strong>
      上传文件、读取 Excel、读取 CSV、新增正式银行流水对象、新增导入按钮、创建导入批次、执行导入校验、执行重复拦截、进入待匹配、
      关联付款执行单、自动匹配、人工确认匹配、写正式银行流水审计日志、生成付款凭证、核销、写总账、过账，全部为“否”。
    </section>

    <section class="summary-grid">
      <article class="summary-card">
        <span>付款执行准备单号</span>
        <strong>{{ paymentExecutionPrepareNoText }}</strong>
        <small>{{ paymentExecutionPrepareFound ? '已找到付款执行准备对象' : '未找到付款执行准备对象' }}</small>
      </article>
      <article class="summary-card">
        <span>预览页版本</span>
        <strong>V1.13.49</strong>
        <small>稳定检查与来源缺失提示加固</small>
      </article>
      <article class="summary-card">
        <span>来源缺失数量</span>
        <strong>{{ missingSourceItems.length }}</strong>
        <small>缺失来源只提示，不创建数据</small>
      </article>
      <article class="summary-card">
        <span>字段缺失数量</span>
        <strong>{{ missingFieldItems.length }}</strong>
        <small>缺失字段只提示，不写正式银行流水</small>
      </article>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>数据来源适配总览</h2>
        <span>每项来源均显示状态、缺失影响和是否读取为正式银行流水</span>
      </div>
      <el-table :data="sourceAdaptationItems" border stripe>
        <el-table-column prop="sourceName" label="数据来源" min-width="170" />
        <el-table-column prop="sourcePage" label="来源页面" min-width="210" />
        <el-table-column prop="sourceStatus" label="来源状态" min-width="150" />
        <el-table-column prop="missingImpact" label="缺失影响" min-width="360" />
        <el-table-column prop="readAsFormalBankFlowThisRound" label="本轮是否读取为正式银行流水" min-width="220" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>银行流水只读对象字段来源适配</h2>
        <span>字段缺失时显示中文业务提示，不显示技术字段错误</span>
      </div>
      <el-table :data="fieldAdaptationItems" border stripe>
        <el-table-column prop="fieldName" label="字段" min-width="170" />
        <el-table-column prop="currentValue" label="当前预览值" min-width="220" />
        <el-table-column prop="source" label="来源" min-width="260" />
        <el-table-column prop="sourceStatus" label="来源状态" min-width="150" />
        <el-table-column prop="missingMessage" label="缺失提示" min-width="360" />
        <el-table-column prop="canEnterFormalBankFlow" label="本轮是否进入正式银行流水" min-width="220" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>导入校验预览缺失提示</h2>
        <span>只展示未来校验口径，本轮不执行校验</span>
      </div>
      <el-table :data="importValidationPreviewItems" border stripe>
        <el-table-column prop="item" label="校验项" min-width="190" />
        <el-table-column prop="previewResult" label="预览结果" min-width="380" />
        <el-table-column prop="validationExecutedThisRound" label="本轮是否执行校验" min-width="190" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>重复流水拦截预览缺失提示</h2>
        <span>只展示未来拦截规则，本轮不执行拦截</span>
      </div>
      <el-table :data="duplicateBlockPreviewItems" border stripe>
        <el-table-column prop="rule" label="拦截规则" min-width="230" />
        <el-table-column prop="previewResult" label="预览结果" min-width="390" />
        <el-table-column prop="blockExecutedThisRound" label="本轮是否执行拦截" min-width="190" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>错误清单预览</h2>
        <span>当前均不触发真实错误，仅提供后续处理建议</span>
      </div>
      <el-table :data="errorPreviewItems" border stripe>
        <el-table-column prop="errorType" label="错误类型" min-width="220" />
        <el-table-column prop="triggeredRealErrorThisRound" label="当前是否触发真实错误" min-width="210" />
        <el-table-column prop="reason" label="原因" min-width="330" />
        <el-table-column prop="suggestion" label="处理建议" min-width="360" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>待匹配状态预览</h2>
        <span>不进入待匹配状态，仅预留状态口径</span>
      </div>
      <el-table :data="pendingMatchPreviewItems" border stripe>
        <el-table-column prop="status" label="预览状态" min-width="190" />
        <el-table-column prop="meaning" label="含义" min-width="330" />
        <el-table-column prop="enteredThisRound" label="本轮是否进入该状态" min-width="200" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>审计日志预览</h2>
        <span>不写正式银行流水审计日志</span>
      </div>
      <el-table :data="auditLogPreviewItems" border stripe>
        <el-table-column prop="auditItem" label="审计项" min-width="210" />
        <el-table-column prop="previewText" label="预览说明" min-width="360" />
        <el-table-column prop="writeFormalAuditLogThisRound" label="本轮是否写正式审计日志" min-width="230" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>本轮统一保护结论</h2>
        <span>全部为否，只读预览</span>
      </div>
      <div class="protection-grid">
        <article v-for="item in unifiedProtectionConclusion" :key="item.item">
          <span>{{ item.item }}</span>
          <strong>{{ item.result }}</strong>
        </article>
      </div>
    </section>

    <section class="table-card bank-account-design-entry-card">
      <div class="table-title">
        <div>
          <h2>银行账户档案前置设计</h2>
          <p class="helper-text">
            当前企业银行账户档案和供应商银行档案尚未建立，先查看前置设计。只读设计，不录入真实银行账号。
          </p>
        </div>
        <router-link class="app-nav-button primary" to="/finance/bank-account-master-design">
          查看银行账户档案前置设计
        </router-link>
      </div>
      <el-alert
        title="当前仍不录入真实银行账号"
        description="本入口仅用于查看企业银行账户档案与供应商银行档案的未来字段、状态、校验、权限和审计规则，不上传文件，不导入银行流水。"
        type="info"
        show-icon
        :closable="false"
      />
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>下一步开发建议</h2>
        <span>本轮不开发正式导入能力</span>
      </div>
      <ol class="next-step-list">
        <li v-for="item in recommendedNextStepItems" :key="item">{{ item }}</li>
      </ol>
    </section>
  </main>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getPaymentExecutionPrepareSourcesFromPaymentOrderPrepares,
  listPaymentExecutionPrepares,
} from '@/meta/finance/paymentExecutionPrepareStore'

const route = useRoute()

const routePaymentExecutionPrepareNo = computed(() => String(route.params.paymentExecutionPrepareNo || '').trim())
const routePaymentExecutionPrepareNoText = computed(() => routePaymentExecutionPrepareNo.value || '未提供付款执行准备单号')
const executionPrepareRows = computed(() => listPaymentExecutionPrepares())
const sourceRows = computed(() => getPaymentExecutionPrepareSourcesFromPaymentOrderPrepares())
const currentRow = computed(() => (
  executionPrepareRows.value.find((item) => item.paymentExecutionPrepareNo === routePaymentExecutionPrepareNo.value)
  || sourceRows.value.find((item) => item.linkedPaymentExecutionPrepareNo === routePaymentExecutionPrepareNo.value)
  || null
))
const paymentExecutionPrepareFound = computed(() => Boolean(routePaymentExecutionPrepareNo.value && currentRow.value))
const paymentExecutionPrepareNoText = computed(() => (
  paymentExecutionPrepareFound.value ? routePaymentExecutionPrepareNo.value : '未找到付款执行准备单'
))
const notFoundReason = computed(() => {
  if (!routePaymentExecutionPrepareNo.value) return '当前路由未提供付款执行准备单号。'
  return '当前浏览器会话中没有找到与该单号对应的付款执行准备对象。'
})

function no() {
  return '否'
}

function safeValue(value, fallback = '来源暂缺') {
  if (value === null || value === undefined || value === '') return fallback
  const text = String(value)
  if (['undefined', 'null', 'NaN'].includes(text)) return fallback
  return text
}

function amountValue(row) {
  if (!row) return 0
  const value = Number(row.executionAmount ?? row.orderAmount ?? row.paymentAmount ?? row.settlementAmount ?? 0)
  return Number.isFinite(value) ? value : 0
}

function formatAmount(value) {
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue) || numberValue <= 0) return '金额来源暂缺'
  return numberValue.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function sourceStatus(hasSource) {
  if (!paymentExecutionPrepareFound.value) return '未找到'
  return hasSource ? '可追溯' : '来源缺失'
}

const row = computed(() => currentRow.value || {})

const unifiedProtectionConclusion = computed(() => [
  '上传文件',
  '读取 Excel',
  '读取 CSV',
  '新增正式银行流水对象',
  '新增正式银行流水列表',
  '新增银行流水导入按钮',
  '新增上传控件',
  '创建导入批次',
  '执行导入校验',
  '执行重复拦截',
  '进入待匹配',
  '关联付款执行单',
  '自动匹配',
  '人工确认匹配',
  '写正式银行流水审计日志',
  '生成付款凭证',
  '核销',
  '写总账',
  '过账',
].map((item) => ({ item, result: no() })))

const sourceAdaptationItems = computed(() => [
  {
    sourceName: '付款执行准备对象',
    sourcePage: '/finance/payment-execution-prepares',
    sourceStatus: paymentExecutionPrepareFound.value ? '已找到' : '未找到',
    missingImpact: paymentExecutionPrepareFound.value ? '可展示付款执行准备单号、执行金额、付款方式、收款方和计划付款日期。' : '无法读取付款执行准备来源，只能展示异常路由保护提示。',
    readAsFormalBankFlowThisRound: no(),
  },
  {
    sourceName: '付款指令准备对象',
    sourcePage: '/finance/payment-order-prepares',
    sourceStatus: sourceStatus(row.value.sourcePaymentOrderPrepareNo),
    missingImpact: row.value.sourcePaymentOrderPrepareNo ? '可追溯来源付款指令准备。' : '无法追溯付款指令准备，只能展示只读预览。',
    readAsFormalBankFlowThisRound: no(),
  },
  {
    sourceName: '付款申请对象',
    sourcePage: '/finance/payment-applications',
    sourceStatus: sourceStatus(row.value.sourcePaymentApplicationNo),
    missingImpact: row.value.sourcePaymentApplicationNo ? '可追溯来源付款申请。' : '无法追溯付款申请，只能展示只读预览。',
    readAsFormalBankFlowThisRound: no(),
  },
  {
    sourceName: '应付确认对象',
    sourcePage: '/finance/account-payable-confirms',
    sourceStatus: sourceStatus(row.value.sourcePayableConfirmNo),
    missingImpact: row.value.sourcePayableConfirmNo ? '可追溯来源应付确认。' : '无法追溯应付确认，只能展示只读预览。',
    readAsFormalBankFlowThisRound: no(),
  },
  {
    sourceName: '采购发票准备对象',
    sourcePage: '/finance/purchase-invoice-prepares',
    sourceStatus: sourceStatus(row.value.sourceInvoicePrepareNo),
    missingImpact: row.value.sourceInvoicePrepareNo ? '可追溯来源采购发票准备。' : '无法追溯采购发票准备，只能展示只读预览。',
    readAsFormalBankFlowThisRound: no(),
  },
  {
    sourceName: '供应商结算对象',
    sourcePage: '/scm/supplier-settlements',
    sourceStatus: sourceStatus(row.value.sourceSettlementNo),
    missingImpact: row.value.sourceSettlementNo ? '可追溯来源供应商结算。' : '无法追溯供应商结算，只能展示只读预览。',
    readAsFormalBankFlowThisRound: no(),
  },
  {
    sourceName: '供应商银行档案',
    sourcePage: '当前未建立正式档案页',
    sourceStatus: '当前未建立正式档案页 / 来源暂缺',
    missingImpact: '暂不能校验收款银行账号，只能展示只读预览。',
    readAsFormalBankFlowThisRound: no(),
  },
  {
    sourceName: '企业银行账户档案',
    sourcePage: '当前未建立正式档案页',
    sourceStatus: '当前未建立正式档案页 / 来源暂缺',
    missingImpact: '暂不能校验企业付款账户，只能展示只读预览。',
    readAsFormalBankFlowThisRound: no(),
  },
  {
    sourceName: '银行流水文件',
    sourcePage: '未来 Excel / CSV / 银行文件',
    sourceStatus: '本轮未上传、未读取',
    missingImpact: '不能校验真实银行流水号、交易日期、交易金额和交易方向。',
    readAsFormalBankFlowThisRound: no(),
  },
  {
    sourceName: '银企直联接口',
    sourcePage: '未来 API',
    sourceStatus: '当前未接入',
    missingImpact: '不能获取银行回传流水号和交易状态。',
    readAsFormalBankFlowThisRound: no(),
  },
])

const missingSourceItems = computed(() => sourceAdaptationItems.value.filter((item) => (
  ['来源缺失', '未找到'].includes(item.sourceStatus)
  || item.sourceStatus.includes('暂缺')
  || item.sourceStatus.includes('未上传')
  || item.sourceStatus.includes('未接入')
)))

const fieldAdaptationItems = computed(() => {
  const current = row.value
  const items = [
    ['预览对象编号', paymentExecutionPrepareFound.value ? `BF-PREVIEW-${routePaymentExecutionPrepareNo.value}` : '未找到付款执行准备单，未生成预览编号', '本页只读预览', paymentExecutionPrepareFound.value ? '已生成预览' : '来源缺失', '未找到付款执行准备单时，不自动创建预览对象。'],
    ['付款执行准备单号', paymentExecutionPrepareFound.value ? routePaymentExecutionPrepareNo.value : routePaymentExecutionPrepareNoText.value, '路由参数 / 付款执行准备对象', paymentExecutionPrepareFound.value ? '已找到' : '未找到', '当前浏览器会话未找到对应付款执行准备单。'],
    ['交易金额', formatAmount(amountValue(current)), '付款执行准备对象的执行准备金额', amountValue(current) > 0 ? '已找到' : '来源暂缺', '付款执行准备未提供有效执行金额。'],
    ['付款方式', safeValue(current.paymentMethod), '付款执行准备对象的付款方式', current.paymentMethod ? '已找到' : '来源暂缺', '付款执行准备未提供付款方式。'],
    ['收款方', safeValue(current.payeeName || current.supplierName), '付款执行准备对象的收款方或供应商', current.payeeName || current.supplierName ? '已找到' : '来源暂缺', '付款执行准备未提供收款方或供应商。'],
    ['收款银行', safeValue(current.payeeBankName), '供应商银行档案或付款执行准备对象', current.payeeBankName ? '已找到' : '来源暂缺', '来源暂缺：供应商银行档案或付款执行准备未提供收款银行。'],
    ['计划付款日期', safeValue(current.plannedPaymentDate), '付款执行准备对象', current.plannedPaymentDate ? '已找到' : '来源暂缺', '来源暂缺：付款执行准备未提供计划付款日期。'],
    ['企业付款银行账号', safeValue(current.payerBankAccount), '企业银行账户档案或付款执行准备对象', current.payerBankAccount ? '已找到' : '来源暂缺', '来源暂缺：企业银行账户档案未建立。'],
    ['银行流水号', '未读取：本轮未上传银行流水文件，也未接入银企直联。', '银行流水文件或银企直联接口', '未读取', '未读取：本轮未上传银行流水文件，也未接入银企直联。'],
    ['银行交易号 / 回单号', '未读取：本轮未上传银行流水文件，也未接入银企直联。', '银行流水文件或银企直联接口', '未读取', '未读取：本轮未上传银行流水文件，也未接入银企直联。'],
    ['交易日期', '未读取：本轮未读取银行流水文件。', '银行流水文件或银企直联接口', '未读取', '未读取：本轮未读取银行流水文件。'],
    ['交易金额', '未读取：本轮未读取银行流水文件。', '银行流水文件或银企直联接口', '未读取', '未读取：本轮未读取银行流水文件。'],
    ['交易方向', '未读取：本轮未读取银行流水文件。', '银行流水文件或银企直联接口', '未读取', '未读取：本轮未读取银行流水文件。'],
    ['匹配状态', '未进入待匹配', '本页只读预览', '未进入', '本轮不进入待匹配。'],
    ['审计状态', '未写正式银行流水审计日志', '本页只读预览', '未写入', '本轮不写正式银行流水审计日志。'],
  ]
  return items.map(([fieldName, currentValue, source, sourceStatusText, missingMessage]) => ({
    fieldName,
    currentValue,
    source,
    sourceStatus: sourceStatusText,
    missingMessage,
    canEnterFormalBankFlow: no(),
  }))
})

const missingFieldItems = computed(() => fieldAdaptationItems.value.filter((item) => (
  item.sourceStatus !== '已找到' && item.sourceStatus !== '已生成预览'
)))

const importValidationPreviewItems = computed(() => [
  ['文件存在性校验', '未上传文件。'],
  ['Excel 读取校验', '未读取 Excel。'],
  ['CSV 读取校验', '未读取 CSV。'],
  ['必填字段校验', '未读取银行流水字段，不能做正式字段完整性校验。'],
  ['企业银行账户校验', '企业银行账户档案未建立，不能做正式校验。'],
  ['供应商银行账号校验', '供应商银行档案未建立，不能做正式校验。'],
  ['银行流水号唯一性校验', '未读取银行流水号，不能做重复校验。'],
  ['交易金额校验', '未读取银行交易金额。'],
  ['交易方向校验', '未读取交易方向。'],
  ['权限与审计校验', '未执行正式权限校验，未写正式审计日志。'],
].map(([item, previewResult]) => ({ item, previewResult, validationExecutedThisRound: no() })))

const duplicateBlockPreviewItems = computed(() => [
  ['银行流水号重复拦截', '未读取银行流水号，暂不判断。'],
  ['银行交易号重复拦截', '未读取银行交易号，暂不判断。'],
  ['同账号同日同金额重复预警', '未读取银行账号、交易日期和交易金额，暂不判断。'],
  ['同一导入批次内重复拦截', '未创建导入批次，暂不判断。'],
  ['已关联付款执行单重复导入拦截', '未关联付款执行单，暂不判断。'],
  ['冲正流水覆盖原流水拦截', '未读取冲正流水，暂不判断。'],
  ['手续费流水误判拦截', '未读取手续费流水，暂不判断。'],
].map(([rule, previewResult]) => ({ rule, previewResult, blockExecutedThisRound: no() })))

const errorPreviewItems = computed(() => [
  ['未上传文件', '本轮不上传文件，因此不触发真实错误。', '后续正式导入页开发时再处理。'],
  ['未读取 Excel', '本轮不读取 Excel，因此不触发真实错误。', '后续正式导入页开发时再处理。'],
  ['未读取 CSV', '本轮不读取 CSV，因此不触发真实错误。', '后续正式导入页开发时再处理。'],
  ['文件格式不支持', '本轮不读取文件，因此不触发真实错误。', '后续正式导入页开发时再处理。'],
  ['必填字段缺失', '本轮不执行字段校验，因此不触发真实错误。', '后续正式导入校验时再处理。'],
  ['银行流水号为空', '本轮无导入数据，因此不触发真实错误。', '后续正式导入校验时再处理。'],
  ['银行流水号重复', '本轮不执行重复拦截，因此不触发真实错误。', '后续正式导入校验时再处理。'],
  ['企业银行账户档案未建立', '当前仅提示来源缺失，不触发真实错误。', '后续应先建立企业银行账户档案，再做正式银行流水导入校验。'],
  ['供应商银行档案未建立', '当前仅提示来源缺失，不触发真实错误。', '后续应先建立供应商银行信息，再做收款方账号校验。'],
  ['交易金额为 0', '本轮不读取银行流水金额，因此不触发真实错误。', '后续读取真实银行流水后再处理。'],
  ['交易金额与付款金额不一致', '本轮不执行金额校验，因此不触发真实错误。', '后续正式导入校验时再处理。'],
  ['交易方向错误', '本轮不读取交易方向，因此不触发真实错误。', '后续正式导入校验时再处理。'],
  ['付款执行准备不存在', paymentExecutionPrepareFound.value ? '当前付款执行准备已找到。' : '当前路由参数未匹配到付款执行准备对象。', '返回付款执行准备页选择有效记录。'],
  ['付款执行准备已付款', '本轮不修改付款执行真实状态。', '后续真实付款前再处理。'],
  ['付款凭证已生成', '本轮不生成付款凭证。', '后续凭证流程开发时再处理。'],
  ['已核销', '本轮不核销。', '后续核销流程开发时再处理。'],
  ['已写总账或已过账', '本轮不写总账，不过账。', '后续总账流程开发时再处理。'],
].map(([errorType, reason, suggestion]) => ({
  errorType,
  triggeredRealErrorThisRound: no(),
  reason,
  suggestion,
})))

const pendingMatchPreviewItems = computed(() => [
  ['not_uploaded', '尚未上传银行流水文件。'],
  ['uploaded_not_read', '文件已上传但尚未读取。'],
  ['validated_not_imported', '字段校验通过但未创建正式流水。'],
  ['pending_match', '流水等待与付款执行准备匹配。'],
  ['matched_preview', '匹配预览通过但未确认。'],
  ['match_confirmed', '人工确认匹配。'],
].map(([status, meaning]) => ({ status, meaning, enteredThisRound: no() })))

const auditLogPreviewItems = computed(() => [
  ['打开预览页', '仅用于页面诊断，不写正式审计日志。'],
  ['查看字段来源', '仅展示来源适配，不写正式审计日志。'],
  ['查看导入校验口径', '仅展示校验预览，不写正式审计日志。'],
  ['查看重复拦截口径', '仅展示拦截预览，不写正式审计日志。'],
  ['复制诊断数据', '复制页面诊断 JSON，不写正式审计日志。'],
  ['未来导入动作', '未来如启用导入，需要写正式审计日志；本轮不写。'],
].map(([auditItem, previewText]) => ({ auditItem, previewText, writeFormalAuditLogThisRound: no() })))

const recommendedNextStepItems = [
  '先补齐企业银行账户档案与供应商银行档案，再考虑正式读取银行文件。',
  '正式导入前应设计文件模板、权限校验、审计日志、重复拦截和回滚策略。',
  '银行流水进入待匹配前，必须明确不会自动付款、不会自动核销、不会自动写总账。',
  '后续如接入银企直联，应单独设计接口安全、回执状态和异常补偿机制。',
]

const routeStabilityCheck = computed(() => ({
  routePaymentExecutionPrepareNo: routePaymentExecutionPrepareNoText.value,
  paymentExecutionPrepareFound: paymentExecutionPrepareFound.value,
  fallbackMessage: paymentExecutionPrepareFound.value ? '正常路径已找到付款执行准备单。' : '未找到付款执行准备单，页面已进入中文保护提示，不崩溃，不自动生成数据。',
}))

const protectionFlags = computed(() => ({
  uploadFile: false,
  readExcel: false,
  readCsv: false,
  createFormalBankFlowObject: false,
  createFormalBankFlowList: false,
  addImportButton: false,
  addUploadControl: false,
  createImportBatch: false,
  executeImportValidation: false,
  executeDuplicateBlock: false,
  enterPendingMatch: false,
  linkPaymentExecutionPrepare: false,
  autoMatch: false,
  manualConfirmMatch: false,
  writeFormalAuditLog: false,
  generatePaymentVoucher: false,
  writeOffPayment: false,
  writeLedger: false,
  postLedger: false,
  modifyPaymentExecutionStatus: false,
}))

const bankFlowSourceAdaptationPreviewSummary = computed(() => ({
  page: 'BankFlowImportValidationPreviewPage',
  version: 'V1.13.49',
  routePaymentExecutionPrepareNo: routePaymentExecutionPrepareNoText.value,
  paymentExecutionPrepareFound: paymentExecutionPrepareFound.value,
  paymentExecutionPrepareNo: paymentExecutionPrepareFound.value ? routePaymentExecutionPrepareNo.value : '',
  sourceAdaptationItems: sourceAdaptationItems.value,
  missingSourceItems: missingSourceItems.value,
  fieldAdaptationItems: fieldAdaptationItems.value,
  missingFieldItems: missingFieldItems.value,
  importValidationPreviewItems: importValidationPreviewItems.value,
  duplicateBlockPreviewItems: duplicateBlockPreviewItems.value,
  errorPreviewItems: errorPreviewItems.value,
  pendingMatchPreviewItems: pendingMatchPreviewItems.value,
  auditLogPreviewItems: auditLogPreviewItems.value,
  routeStabilityCheck: routeStabilityCheck.value,
  fallbackMessage: routeStabilityCheck.value.fallbackMessage,
  unifiedProtectionConclusion: unifiedProtectionConclusion.value,
  protectionFlags: protectionFlags.value,
  recommendedNextStep: recommendedNextStepItems.join('；'),
  timestamp: new Date().toISOString(),
}))

const diagnosticData = computed(() => ({
  page: 'BankFlowImportValidationPreviewPage',
  version: 'V1.13.49',
  bankFlowSourceAdaptationPreviewSummary: bankFlowSourceAdaptationPreviewSummary.value,
  diagnosticChineseSummary: {
    页面名称: '银行流水导入校验预览',
    页面版本: 'V1.13.49',
    付款执行准备单是否找到: paymentExecutionPrepareFound.value ? '是' : '否',
    来源缺失数量: missingSourceItems.value.length,
    字段缺失数量: missingFieldItems.value.length,
    本轮是否上传文件: no(),
    本轮是否读取Excel: no(),
    本轮是否读取CSV: no(),
    本轮是否新增正式银行流水对象: no(),
    本轮是否新增导入按钮: no(),
    本轮是否创建导入批次: no(),
    本轮是否执行导入校验: no(),
    本轮是否执行重复拦截: no(),
    本轮是否进入待匹配: no(),
    本轮是否写正式审计日志: no(),
    本轮是否核销: no(),
    本轮是否写总账: no(),
    本轮是否过账: no(),
  },
}))

async function copyDiagnosticData() {
  const text = JSON.stringify(diagnosticData.value, null, 2)
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('诊断数据已复制。')
  } catch (error) {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    ElMessage.success('诊断数据已复制。')
  }
}
</script>

<style scoped>
.bank-flow-import-validation-preview-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.page-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.boundary-card,
.warning-card,
.table-card {
  padding: 16px;
  border: 1px solid var(--app-border, #d8dee8);
  border-radius: 8px;
  background: #fff;
  overflow-x: auto;
}

.warning-card {
  border-color: #f59e0b;
  background: #fffbeb;
}

.warning-card h2 {
  margin: 0 0 8px;
}

.warning-card p {
  margin: 4px 0;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 12px;
}

.summary-card {
  display: grid;
  gap: 6px;
  padding: 14px;
  border: 1px solid var(--app-border, #d8dee8);
  border-radius: 8px;
  background: #fff;
}

.summary-card strong {
  font-size: 22px;
}

.summary-card small,
.table-title span {
  color: #667085;
}

.helper-text {
  margin: 4px 0 0;
  color: #667085;
  line-height: 1.7;
}

.table-title {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
}

.protection-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 10px;
}

.protection-grid article {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid #d8dee8;
  border-radius: 8px;
  background: #f8fafc;
}

.protection-grid strong {
  color: #b42318;
}

.next-step-list {
  margin: 0;
  padding-left: 20px;
  line-height: 1.8;
}
</style>

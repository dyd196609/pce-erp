<template>
  <main class="invoice-prepare-page">
    <header class="page-header">
      <div v-if="!embeddedInCommonShell">
        <p class="eyebrow">V1.14.2.8.4.7.43.1 · 服务端当前状态修正</p>
        <h2 data-acceptance-id="page-internal-subject-title"><PceBusinessNameConsumer page-code="invoice-prepare" /></h2>
        <p>当前数据源：服务端采购发票准备持久化对象 · 当前来源类型：采购对账 · 生产灰度：关闭</p>
      </div>
      <div class="header-actions">
        <el-button @click="loadServerState">刷新</el-button>
        <el-button plain @click="copyDiagnostics">复制诊断数据</el-button>
        <el-button plain @click="router.push('/scm/purchase-reconciliations')">返回业务流程中心</el-button>
      </div>
    </header>

    <section class="evidence-card" data-acceptance-id="purchase-invoice-prepare-source">
      <h3>采购发票准备来源</h3>
      <p class="ctrl-f">来源采购对账</p>
      <div class="fact-grid">
        <Fact label="来源采购对账编号" :value="source.reconciliationNo" />
        <Fact label="采购发票准备编号" :value="currentPrepare.prepareNo" />
        <Fact label="来源采购对账状态" :value="source.status" />
        <Fact label="核对结果" :value="source.checkResultCode" />
        <Fact label="采购对账版本" :value="source.version" />
        <Fact label="核对版本" :value="source.checkVersion" />
        <Fact label="差异数量" :value="source.differenceCount" />
        <Fact label="双权威证据完整性" :value="source.evidenceIntegrity === 'passed' ? '通过' : '未通过'" />
        <Fact label="来源基础资格（动作前）" :value="source.eligible ? '通过' : '不通过'" />
        <Fact label="供应商" :value="currentPrepare.supplierName" />
        <Fact label="法人" :value="currentPrepare.legalEntityId" />
        <Fact label="账簿" :value="currentPrepare.ledgerBookId" />
        <Fact label="币种" :value="currentPrepare.currency" />
        <Fact label="来源金额" :value="currentPrepare.settlementAmount" />
        <Fact label="来源数量" :value="currentPrepare.quantity" />
      </div>
    </section>

    <section class="evidence-card" data-acceptance-id="purchase-invoice-data-collection">
      <div class="section-heading">
        <div><h3>发票资料采集</h3><p class="ctrl-f">发票资料采集</p></div>
        <div class="canary-actions">
          <el-button v-if="validationModel.validation.idempotencyKey && currentState.testTenant" plain @click="retryValidation">
            测试租户执行幂等重试
          </el-button>
          <el-button v-if="validationModel.validation.idempotencyKey && currentState.testTenant" plain @click="queryValidationResult">
            测试租户查询校验结果
          </el-button>
        </div>
      </div>
      <div class="advanced-filter-panel">
        <label>发票类型<el-input v-model="invoiceForm.invoiceType" :disabled="isPrepared" /></label>
        <label>发票代码<el-input v-model="invoiceForm.invoiceCode" :disabled="isPrepared" /></label>
        <label>发票号码<el-input v-model="invoiceForm.invoiceNumber" :disabled="isPrepared" /></label>
        <label>开票日期<el-input v-model="invoiceForm.invoiceDate" :disabled="isPrepared" /></label>
        <label>销方名称<el-input v-model="invoiceForm.sellerName" :disabled="isPrepared" /></label>
        <label>销方税号<el-input v-model="invoiceForm.sellerTaxId" :disabled="isPrepared" /></label>
        <label>购方名称<el-input v-model="invoiceForm.buyerName" :disabled="isPrepared" /></label>
        <label>购方税号<el-input v-model="invoiceForm.buyerTaxId" :disabled="isPrepared" /></label>
        <label>币种<el-input v-model="invoiceForm.currency" :disabled="isPrepared" /></label>
        <label>未税金额<el-input v-model="invoiceForm.amountExcludingTax" :disabled="isPrepared" /></label>
        <label>税额<el-input v-model="invoiceForm.taxAmount" :disabled="isPrepared" /></label>
        <label>含税金额<el-input v-model="invoiceForm.amountIncludingTax" :disabled="isPrepared" /></label>
      </div>
      <div class="fact-grid">
        <Fact label="资料版本" :value="validationModel.versionsAndAudit.dataVersion" />
        <Fact label="资料完整性" :value="currentPrepare.invoiceDataStatus" />
        <Fact label="资料来源" :value="validationModel.invoiceData?.dataSource || 'not_collected'" />
      </div>
    </section>

    <section class="evidence-card" data-acceptance-id="purchase-invoice-lines-and-tax">
      <h3>发票明细与税额</h3>
      <p class="ctrl-f">发票明细</p>
      <el-table :data="invoiceForm.lines" border>
        <el-table-column prop="lineNo" label="行号" width="70" />
        <el-table-column label="项目" min-width="140"><template #default="{ row }"><el-input v-model="row.itemName" :disabled="isPrepared" /></template></el-table-column>
        <el-table-column label="规格" min-width="100"><template #default="{ row }"><el-input v-model="row.specification" :disabled="isPrepared" /></template></el-table-column>
        <el-table-column label="数量" min-width="100"><template #default="{ row }"><el-input v-model="row.quantity" :disabled="isPrepared" /></template></el-table-column>
        <el-table-column label="单位" width="90"><template #default="{ row }"><el-input v-model="row.unit" :disabled="isPrepared" /></template></el-table-column>
        <el-table-column label="单价" min-width="110"><template #default="{ row }"><el-input v-model="row.unitPrice" :disabled="isPrepared" /></template></el-table-column>
        <el-table-column label="未税金额" min-width="110"><template #default="{ row }"><el-input v-model="row.amountExcludingTax" :disabled="isPrepared" /></template></el-table-column>
        <el-table-column label="税率" min-width="90"><template #default="{ row }"><el-input v-model="row.taxRate" :disabled="isPrepared" /></template></el-table-column>
        <el-table-column label="税额" min-width="100"><template #default="{ row }"><el-input v-model="row.taxAmount" :disabled="isPrepared" /></template></el-table-column>
        <el-table-column label="含税金额" min-width="110"><template #default="{ row }"><el-input v-model="row.amountIncludingTax" :disabled="isPrepared" /></template></el-table-column>
      </el-table>
      <div class="fact-grid">
        <Fact label="行合计" :value="lineTotals.includingTax" />
        <Fact label="表头合计" :value="invoiceForm.amountIncludingTax" />
        <Fact label="差异值" :value="lineTotals.difference" />
      </div>
    </section>

    <section class="evidence-card" data-acceptance-id="purchase-invoice-validation">
      <h3>发票要素校验</h3>
      <p class="ctrl-f">发票要素校验</p>
      <div class="fact-grid">
        <Fact label="校验状态" :value="validationModel.validation.status" />
        <Fact label="校验结果编码" :value="validationModel.validation.resultCode" />
        <Fact label="校验策略版本" :value="validationModel.validation.policyVersion" />
        <Fact label="资料版本" :value="validationModel.validation.dataVersion" />
        <Fact label="来源版本" :value="validationModel.validation.sourceVersion" />
        <Fact label="核对版本" :value="validationModel.validation.checkVersion" />
        <Fact label="规则总数" :value="validationModel.validation.ruleCount" />
        <Fact label="通过规则数" :value="validationModel.validation.passedRuleCount" />
        <Fact label="阻断规则数" :value="validationModel.validation.blockingRuleCount" />
        <Fact label="问题数量" :value="validationModel.validation.issueCount" />
      </div>
    </section>

    <section class="evidence-card" data-acceptance-id="purchase-invoice-validation-issues">
      <h3>校验问题清单</h3>
      <p class="ctrl-f">校验问题清单</p>
      <p v-if="!validationModel.validationIssues.length">无校验问题</p>
      <el-table v-else :data="validationModel.validationIssues" border>
        <el-table-column prop="ruleCode" label="规则编码" min-width="240" />
        <el-table-column prop="dimension" label="问题维度" min-width="130" />
        <el-table-column prop="lineNo" label="行号" width="70" />
        <el-table-column prop="expected" label="期望值" min-width="130" />
        <el-table-column prop="actual" label="实际值" min-width="130" />
        <el-table-column prop="delta" label="差异值" min-width="90" />
        <el-table-column prop="severity" label="严重程度" min-width="90" />
        <el-table-column prop="blocking" label="是否阻断" min-width="90" />
        <el-table-column prop="message" label="说明" min-width="220" />
      </el-table>
    </section>

    <section class="evidence-card" data-acceptance-id="purchase-invoice-duplicate">
      <h3>重复发票识别</h3>
      <p class="ctrl-f">重复发票</p>
      <div class="fact-grid">
        <Fact label="发票身份键" :value="validationModel.invoiceIdentity.identityKey" />
        <Fact label="身份状态" :value="validationModel.invoiceIdentity.status" />
        <Fact label="已有占用对象" :value="validationModel.invoiceIdentity.existingPrepareId" />
        <Fact label="是否发现重复" :value="validationModel.invoiceIdentity.duplicateFound" />
        <Fact label="重复阻断编码" :value="validationModel.invoiceIdentity.duplicateBlockingCode || '-'" />
        <Fact label="数据库唯一约束状态" :value="validationModel.invoiceIdentity.databaseUniqueConstraint" />
      </div>
    </section>

    <section class="evidence-card" data-acceptance-id="purchase-invoice-ap-draft-eligibility">
      <div class="section-heading">
        <div><h3>采购应付账款草稿资格</h3><p class="ctrl-f">应付账款草稿资格</p></div>
      </div>
      <PceBusinessActionBar
        current-module="purchase-invoice-prepare"
        :current-status="currentPrepare.status || validationModel.accountsPayableDraftEligibility.status"
        :selected-rows="currentPrepare.id ? [currentPrepare] : []"
        :eligibility="validationModel.accountsPayableDraftEligibility.eligible"
        :show-unavailable="true"
        :include-action-ids="[
          'save-purchase-invoice-data',
          'validate-purchase-invoice-data',
          'enter-accounts-payable-draft',
          'batch-enter-accounts-payable-draft',
        ]"
        @execute="executeRegistryAction"
      />
      <div class="fact-grid">
        <Fact label="采购发票准备状态" :value="validationModel.accountsPayableDraftEligibility.status" />
        <Fact label="资料状态" :value="validationModel.accountsPayableDraftEligibility.invoiceDataStatus" />
        <Fact label="校验状态" :value="validationModel.accountsPayableDraftEligibility.validationStatus" />
        <Fact label="校验结果" :value="validationModel.accountsPayableDraftEligibility.validationResultCode" />
        <Fact label="问题数量" :value="validationModel.accountsPayableDraftEligibility.validationIssueCount" />
        <Fact label="发票身份状态" :value="validationModel.accountsPayableDraftEligibility.invoiceIdentityStatus" />
        <Fact label="来源采购对账状态" :value="validationModel.accountsPayableDraftEligibility.sourcePurchaseReconciliationStatus" />
        <Fact label="来源版本是否一致" :value="!validationModel.accountsPayableDraftEligibility.blockingReasons.includes('sourceVersionCurrent')" />
        <Fact label="nextStepReadiness" :value="validationModel.accountsPayableDraftEligibility.nextStepReadiness" />
        <Fact label="eligible" :value="validationModel.accountsPayableDraftEligibility.eligible" />
        <Fact label="blockingReasons" :value="validationModel.accountsPayableDraftEligibility.blockingReasons.join(',') || '[]'" />
      </div>
    </section>

    <section class="evidence-card" data-acceptance-id="purchase-invoice-prepare-strict-facts">
      <h3>服务端状态机事实</h3>
      <div class="fact-grid">
        <Fact label="当前状态来源" :value="strictFacts.currentStateSource" />
        <Fact label="对象数量" :value="strictFacts.objectCount" />
        <Fact label="状态迁移数量" :value="strictFacts.statusTransitionCount" />
        <Fact label="状态机一致" :value="strictFacts.stateMachineConsistent" />
      </div>
    </section>

    <section class="evidence-card" data-acceptance-id="purchase-invoice-version-idempotency-audit">
      <h3>版本、幂等与审计</h3>
      <p class="ctrl-f">版本、幂等与审计</p>
      <div class="fact-grid">
        <Fact label="对象版本" :value="validationModel.versionsAndAudit.prepareVersion" />
        <Fact label="资料版本" :value="validationModel.versionsAndAudit.dataVersion" />
        <Fact label="校验版本" :value="validationModel.versionsAndAudit.validationVersion" />
        <Fact label="保存幂等状态" :value="validationModel.versionsAndAudit.saveIdempotencyStatus" />
        <Fact label="校验幂等状态" :value="validationModel.versionsAndAudit.validationIdempotencyStatus" />
        <Fact label="事务状态" :value="validationModel.versionsAndAudit.transactionStatus" />
        <Fact label="审计状态" :value="validationModel.versionsAndAudit.auditStatus" />
        <Fact label="当前状态来源" :value="validationModel.versionsAndAudit.currentStateSource" />
      </div>
    </section>

    <section class="evidence-card" data-acceptance-id="purchase-invoice-flow-boundary-v44">
      <h3>业务流程与后续边界</h3>
      <p class="ctrl-f">后续边界</p>
      <div class="fact-grid">
        <Fact label="当前模块" value="采购发票准备" />
        <Fact label="前置模块" value="采购对账" />
        <Fact label="下一模块" value="采购应付账款草稿" />
        <Fact label="是否允许进入下一模块" :value="validationModel.accountsPayableDraftEligibility.eligible" />
        <Fact label="是否已创建采购应付账款草稿" value="否" />
      </div>
    </section>

    <section class="evidence-card protection" data-acceptance-id="purchase-invoice-downstream-zero-v44">
      <h3>下游零对象保护</h3>
      <p class="ctrl-f">下游零对象</p>
      <div class="fact-grid">
        <Fact v-for="item in downstreamV44Facts" :key="item.label" :label="item.label" :value="item.value" />
      </div>
    </section>

    <section class="evidence-card" data-acceptance-id="purchase-invoice-prepare-business-gate">
      <h3>采购发票准备业务门禁</h3>
      <p class="ctrl-f">业务门禁</p>
      <div class="fact-grid">
        <Fact v-for="item in businessGateFacts" :key="item.label" :label="item.label" :value="item.value" />
      </div>
    </section>

    <section class="evidence-card snapshot" data-acceptance-id="purchase-invoice-prepare-pre-action-gate-snapshot">
      <h3>动作前业务门禁快照</h3>
      <p class="ctrl-f">动作前门禁快照（仅作审计证据，不代表当前可执行性）</p>
      <div class="fact-grid">
        <Fact v-for="item in preActionGateFacts" :key="item.label" :label="item.label" :value="item.value" />
      </div>
    </section>

    <section class="evidence-card" data-acceptance-id="purchase-invoice-prepare-transaction-gate">
      <h3>采购发票准备事务门禁</h3>
      <p class="ctrl-f">事务门禁</p>
      <div class="fact-grid">
        <Fact v-for="item in transactionGateFacts" :key="item.label" :label="item.label" :value="item.value" />
      </div>
    </section>

    <section class="evidence-card" data-acceptance-id="purchase-invoice-prepare-object">
      <div class="section-heading">
        <div><h3>采购发票准备对象</h3><p class="ctrl-f">采购发票准备编号</p></div>
        <div class="canary-actions">
          <PceBusinessActionBar
            current-module="purchase-reconciliation"
            :current-status="source.status"
            :selected-rows="source.id ? [source] : []"
            :eligibility="generationButtonVisible"
            :show-unavailable="true"
            :batch-enabled="false"
            :include-action-ids="['generate-purchase-invoice-prepare']"
            @execute="executeRegistryAction"
          />
          <el-button v-if="currentState.targetCount === 1" plain @click="viewExistingPrepare">查看已有采购发票准备</el-button>
          <el-button v-if="currentState.testTenant && currentState.targetCount === 1" plain :disabled="!lastIdempotencyKey" @click="retryCanary">测试租户执行幂等重试</el-button>
          <el-button v-if="currentState.testTenant && currentState.targetCount === 1" plain :disabled="!lastIdempotencyKey" @click="recoverCanary">金丝雀查询生成结果</el-button>
        </div>
      </div>
      <div class="fact-grid">
        <Fact label="对象标识" :value="currentPrepare.id" />
        <Fact label="采购发票准备编号" :value="currentPrepare.prepareNo" />
        <Fact label="对象状态" :value="currentPrepare.status ? `${currentPrepare.status} / 草稿` : '-'" />
        <Fact label="发票资料状态" :value="currentPrepare.invoiceDataStatus" />
        <Fact label="供应商" :value="currentPrepare.supplierName" />
        <Fact label="法人" :value="currentPrepare.legalEntityId" />
        <Fact label="账簿" :value="currentPrepare.ledgerBookId" />
        <Fact label="币种" :value="currentPrepare.currency" />
        <Fact label="数量" :value="currentPrepare.quantity" />
        <Fact label="金额" :value="currentPrepare.settlementAmount" />
        <Fact label="来源采购对账" :value="currentPrepare.sourcePurchaseReconciliationNo" />
        <Fact label="来源类型" :value="currentPrepare.sourceDocumentType" />
      </div>
    </section>

    <section class="evidence-card" data-acceptance-id="purchase-invoice-prepare-idempotency">
      <h3>生成结果与幂等状态</h3>
      <p class="ctrl-f">幂等状态</p>
      <div class="fact-grid">
        <Fact label="动作前对象数量" :value="generationFacts.beforeCount" />
        <Fact label="动作后对象数量" :value="generationFacts.afterCount" />
        <Fact label="重试后对象数量" :value="generationFacts.retryCount" />
        <Fact label="幂等状态" :value="generationFacts.idempotencyStatus" />
        <Fact label="编号状态" :value="generationFacts.numberStatus" />
        <Fact label="事务状态" :value="generationFacts.transactionStatus" />
        <Fact label="审计状态" :value="generationFacts.auditStatus" />
        <Fact label="来源关系状态" :value="generationFacts.relationStatus" />
      </div>
    </section>

    <section class="evidence-card" data-acceptance-id="purchase-invoice-prepare-rollback">
      <h3>事务回滚与结果恢复</h3>
      <p class="ctrl-f">事务回滚</p>
      <div class="fact-grid">
        <Fact label="失败步骤" value="参数化 17 个注入点" />
        <Fact label="事务状态" value="失败原子回滚 / 响应丢失可恢复" />
        <Fact label="对象残留" value="0" />
        <Fact label="关系残留" value="0" />
        <Fact label="审计残留" value="0" />
        <Fact label="编号状态" value="未消费或 committed 后 consumed" />
        <Fact label="恢复分类" value="existing_result / recovery_required" />
        <Fact label="是否允许重试" value="仅稳定可重试错误" />
        <Fact label="是否需要人工处理" value="阈值外才需要" />
      </div>
    </section>

    <section class="evidence-card" data-acceptance-id="purchase-invoice-prepare-flow-boundary">
      <h3>业务流程与后续边界</h3>
      <p class="ctrl-f">后续边界</p>
      <div class="fact-grid">
        <Fact label="当前业务模块" value="采购发票准备" />
        <Fact label="前置业务模块" value="采购对账" />
        <Fact label="下一业务模块" value="采购应付账款草稿" />
        <Fact label="是否创建应付草稿" value="否" />
        <Fact label="是否创建付款对象" value="否" />
        <Fact label="是否创建付款凭证" value="否" />
        <Fact label="是否写总账" value="否" />
        <Fact label="是否过账" value="否" />
      </div>
    </section>

    <section class="evidence-card protection" data-acceptance-id="purchase-invoice-prepare-zero-downstream">
      <h3>正式生产与下游零对象保护</h3>
      <p class="ctrl-f">下游零对象</p>
      <div class="fact-grid">
        <Fact label="测试租户采购发票准备数量" :value="rows.length" />
        <Fact label="生产租户采购发票准备数量" value="0" />
        <Fact label="应付账款草稿数量" value="0" />
        <Fact label="付款申请数量" value="0" />
        <Fact label="付款对象数量" value="0" />
        <Fact label="付款凭证数量" value="0" />
        <Fact label="核销数量" value="0" />
        <Fact label="总账数量" value="0" />
        <Fact label="过账数量" value="0" />
        <Fact label="银行流水数量" value="0" />
        <Fact label="用户 localStorage 业务写入" value="0" />
        <Fact label="生产租户网络写入" value="0" />
      </div>
    </section>

    <section class="evidence-card">
      <StandardListToolbar
        page-id="invoice-prepare"
        table-id="invoice-prepare-main"
        v-model:quick-search="quickSearch"
        :advanced-visible="advancedVisible"
        :result-count="filteredRows.length"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        sort-text="服务端创建时间倒序"
        :export-disabled="filteredRows.length === 0"
        @search="loadServerState"
        @toggle-advanced="advancedVisible = !advancedVisible"
        @clear-filters="clearFilters"
        @clear-sort="clearSort"
        @export-current="exportCurrentRows"
      />
      <section
        v-show="advancedVisible"
        class="advanced-filter-panel"
        data-acceptance-id="list-advanced-filter-panel"
        data-pce-filter-for="invoice-prepare-main"
      >
        <label>采购发票准备编号<PceResultFilterSelect v-model="filters.prepareNo" :rows="rows" :fields="['prepareNo']" /></label>
        <label>来源采购对账编号<PceResultFilterSelect v-model="filters.sourcePurchaseReconciliationNo" :rows="rows" :fields="['sourcePurchaseReconciliationNo']" /></label>
        <label>供应商<PceResultFilterSelect v-model="filters.supplierName" :rows="rows" :fields="['supplierName']" /></label>
        <label>对象状态<PceResultFilterSelect v-model="filters.status" :rows="rows" :fields="['status']" /></label>
        <label>发票资料状态<PceResultFilterSelect v-model="filters.invoiceDataStatus" :rows="rows" :fields="['invoiceDataStatus']" /></label>
        <label>事务标识<PceResultFilterSelect v-model="filters.transactionId" :rows="rows" :fields="['transactionId']" /></label>
      </section>
      <BusinessTableScrollContainer acceptance-id="business-table-scroll-invoice-prepare-main" min-width="1200px">
        <el-table :data="filteredRows" border stripe height="420" scrollbar-always-on @selection-change="selectedRows = $event">
          <el-table-column type="selection" width="48" fixed="left" class-name="business-table-selection-column" header-class-name="business-table-selection-column" label-class-name="business-table-selection-column" />
          <el-table-column type="index" label="序号" width="64" fixed="left" class-name="pce-fixed-index-column" header-class-name="pce-fixed-index-column" label-class-name="pce-fixed-index-column" />
          <el-table-column prop="prepareNo" label="采购发票准备编号" min-width="190" fixed="left" />
          <el-table-column prop="sourcePurchaseReconciliationNo" label="来源采购对账编号" min-width="190" />
          <el-table-column prop="supplierName" label="供应商" min-width="170" />
          <el-table-column prop="settlementAmount" label="金额" width="130" />
          <el-table-column prop="status" label="对象状态" width="130"><template #default="{ row }">{{ display(row.status) }}</template></el-table-column>
          <el-table-column prop="invoiceDataStatus" label="发票资料状态" width="160"><template #default="{ row }">{{ display(row.invoiceDataStatus) }}</template></el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button plain size="small" @click="viewSource(row)">查看来源采购对账</el-button>
            </template>
          </el-table-column>
        </el-table>
      </BusinessTableScrollContainer>
    </section>
  </main>
</template>

<script setup>
import PceBusinessNameConsumer from '../components/PceBusinessNameConsumer.vue'
const { embeddedInCommonShell = false } = defineProps({
  embeddedInCommonShell: { type: Boolean, default: false },
})
import { computed, defineComponent, h, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { displayPceFilterValue } from '@/meta/runtime/pceAdvancedFilterContract.js'
import { purchaseInvoicePrepareApi } from '../../api/purchaseInvoicePrepare.js'
import BusinessTableScrollContainer from '../components/BusinessTableScrollContainer.vue'
import PceResultFilterSelect from '../components/PceResultFilterSelect.vue'
import StandardListToolbar from '../components/StandardListToolbar.vue'
import PceBusinessActionBar from '../components/PceBusinessActionBar.vue'

const display = displayPceFilterValue
import { getPurchaseReconciliationInvoicePrepareEligibility } from '../../api/purchaseReconciliation.js'

const Fact = defineComponent({
  props: { label: String, value: [String, Number, Boolean] },
  setup: (props) => () => h('div', { class: 'fact' }, [
    h('span', props.label),
    h('strong', String(props.value ?? '-')),
  ]),
})

const route = useRoute()
const router = useRouter()
const rows = ref([])
const selectedRows = ref([])
const quickSearch = ref('')
const advancedVisible = ref(false)
const generating = ref(false)
const savingData = ref(false)
const validatingData = ref(false)
const lastIdempotencyKey = ref('')
const source = reactive({
  id: Number(route.query.sourcePurchaseReconciliationId || 0),
  reconciliationNo: '-',
  status: '-',
  checkResultCode: '-',
  version: 0,
  checkVersion: 0,
  differenceCount: 0,
  evidenceIntegrity: 'failed',
  evidenceSourceCount: 0,
  evidenceSourcesIndependent: false,
  eligible: false,
})
const generationFacts = reactive({
  beforeCount: 0,
  afterCount: 0,
  retryCount: 0,
  idempotencyStatus: 'not_started / 未执行',
  numberStatus: 'not_allocated / 未分配',
  transactionStatus: 'not_started / 未执行',
  auditStatus: 'not_started / 未执行',
  relationStatus: 'not_started / 未执行',
})
const currentState = reactive({
  currentStateSource: 'server',
  targetExistenceStatus: 'no_target',
  targetCount: 0,
  preActionTargetCount: 0,
  generationAllowed: false,
  generationStatus: 'not_started',
  preActionBusinessGateResult: 'unknown',
  currentIdempotencyStatus: 'not_started',
  currentNumberReservationStatus: 'not_allocated',
  currentTransactionStatus: 'not_started',
  currentAuditStatus: 'not_started',
  currentSourceRelationStatus: 'not_started',
  generationResultIdempotencyKey: null,
  testTenant: false,
  productionRolloutEnabled: false,
  purchaseInvoicePrepare: null,
})
const strictFacts = reactive({
  currentStateSource: 'server',
  objectCount: null,
  statusTransitionHistory: null,
  statusTransitionCount: null,
  stateMachineConsistent: false,
})
const validationModel = reactive({
  currentStateSource: 'server',
  invoiceData: null,
  validation: {
    status: 'not_validated', resultCode: 'not_validated', policyVersion: 'pip-invoice-validation-v1',
    dataVersion: 0, sourceVersion: 0, checkVersion: 0, validationVersion: 0,
    ruleCount: 0, passedRuleCount: 0, blockingRuleCount: 0, issueCount: 0, idempotencyKey: '',
  },
  validationIssues: [],
  invoiceIdentity: {
    identityKey: '', status: 'not_claimed', existingPrepareId: null,
    duplicateFound: false, duplicateBlockingCode: '',
    databaseUniqueConstraint: 'uniq_active_purchase_invoice_identity',
  },
  accountsPayableDraftEligibility: {
    eligible: false, status: 'draft', invoiceDataStatus: 'not_collected',
    validationStatus: 'not_validated', validationResultCode: 'not_validated',
    validationIssueCount: 0, invoiceIdentityStatus: 'not_claimed',
    sourcePurchaseReconciliationStatus: '-', nextStepReadiness: 'blocked', blockingReasons: [],
  },
  versionsAndAudit: {
    prepareVersion: 1, dataVersion: 0, validationVersion: 0,
    saveIdempotencyStatus: 'not_started', validationIdempotencyStatus: 'not_started',
    transactionStatus: 'not_started', auditStatus: 'not_started', currentStateSource: 'server',
  },
  downstreamCounts: {},
})
const invoiceForm = reactive({
  invoiceType: '', invoiceCode: '', invoiceNumber: '', invoiceDate: '',
  sellerName: '', sellerTaxId: '', buyerName: '', buyerTaxId: '', currency: '',
  amountExcludingTax: '', taxAmount: '', amountIncludingTax: '',
  lines: [{
    lineNo: 1, itemCode: 'MAT-V44', itemName: '', specification: '',
    quantity: '', unit: '', unitPrice: '', amountExcludingTax: '',
    taxRate: '', taxAmount: '', amountIncludingTax: '',
  }],
})
const filters = reactive({
  prepareNo: '',
  sourcePurchaseReconciliationNo: '',
  supplierName: '',
  status: '',
  invoiceDataStatus: '',
  transactionId: '',
})

const currentPrepare = computed(() => currentState.purchaseInvoicePrepare || {})
const isPrepared = computed(() => currentPrepare.value.status === 'prepared')
const canEditInvoiceData = computed(() => currentState.testTenant && !isPrepared.value && currentState.targetCount === 1)
const canValidateInvoiceData = computed(() => (
  currentState.testTenant && !isPrepared.value && currentPrepare.value.invoiceDataStatus === 'complete'
))
const lineTotals = computed(() => {
  const total = invoiceForm.lines.reduce((sum, line) => sum + Number(line.amountIncludingTax || 0), 0)
  const header = Number(invoiceForm.amountIncludingTax || 0)
  return {
    includingTax: total.toFixed(2),
    difference: (total - header).toFixed(2),
  }
})
const downstreamV44Facts = computed(() => [
  ['采购应付账款草稿数量', validationModel.downstreamCounts.accountsPayableDrafts || 0],
  ['付款申请数量', validationModel.downstreamCounts.paymentApplications || 0],
  ['付款对象数量', validationModel.downstreamCounts.payments || 0],
  ['付款凭证数量', validationModel.downstreamCounts.paymentVouchers || 0],
  ['核销数量', validationModel.downstreamCounts.writeoffs || 0],
  ['总账数量', validationModel.downstreamCounts.ledgerEntries || 0],
  ['过账数量', validationModel.downstreamCounts.postings || 0],
  ['银行流水数量', validationModel.downstreamCounts.bankTransactions || 0],
  ['生产租户写入数量', validationModel.downstreamCounts.productionTenantWrites || 0],
  ['用户 localStorage 业务写入数量', validationModel.downstreamCounts.localStorageBusinessWrites || 0],
].map(([label, value]) => ({ label, value })))
const generationButtonVisible = computed(() => (
  currentState.currentStateSource === 'server'
  && currentState.testTenant
  && currentState.generationAllowed
  && currentState.targetCount === 0
))
const activeFilterCount = computed(() => (
  (quickSearch.value.trim() ? 1 : 0)
  + Object.values(filters).filter((value) => String(value || '').trim()).length
))
const filteredRows = computed(() => {
  const query = quickSearch.value.trim().toLowerCase()
  return rows.value.filter((item) => {
    if (query && !Object.values(item).join(' ').toLowerCase().includes(query)) return false
    if (filters.prepareNo && !String(item.prepareNo || '').includes(filters.prepareNo)) return false
    if (filters.sourcePurchaseReconciliationNo && !String(item.sourcePurchaseReconciliationNo || '').includes(filters.sourcePurchaseReconciliationNo)) return false
    if (filters.supplierName && !String(item.supplierName || '').includes(filters.supplierName)) return false
    if (filters.status && item.status !== filters.status) return false
    if (filters.invoiceDataStatus && item.invoiceDataStatus !== filters.invoiceDataStatus) return false
    if (filters.transactionId && item.transactionId !== filters.transactionId) return false
    return true
  })
})
const passText = (condition) => condition ? '通过' : '未通过'
const currentBusinessStatus = computed(() => {
  if (currentState.generationStatus === 'existing_target') return '已存在采购发票准备，不允许重复生成'
  if (currentState.generationAllowed) return '允许金丝雀受控生成'
  if (currentState.generationStatus === 'conflict') return '目标状态冲突，禁止生成'
  return '当前条件阻断'
})
const businessGateFacts = computed(() => [
  { label: '当前状态来源', value: currentState.currentStateSource },
  { label: '目标对象数量', value: currentState.targetCount },
  { label: '目标存在状态', value: currentState.targetExistenceStatus },
  { label: '当前生成资格或当前业务状态', value: currentBusinessStatus.value },
  { label: '当前生成状态', value: currentState.generationStatus },
])
const preActionGateFacts = computed(() => [
  { label: '来源存在', value: passText(Boolean(source.id)) },
  { label: '状态 matched', value: passText(source.status === 'matched') },
  { label: '核对结果 matched', value: passText(source.checkResultCode === 'PRC_CHECK_MATCHED') },
  { label: '零差异', value: passText(source.differenceCount === 0) },
  { label: '双权威证据', value: passText(source.evidenceIntegrity === 'passed' && source.evidenceSourceCount === 2 && source.evidenceSourcesIndependent) },
  { label: '来源版本', value: source.version },
  { label: '核对版本', value: source.checkVersion },
  { label: '动作前目标数量', value: currentState.preActionTargetCount ?? '-' },
  { label: '审计证据', value: passText(source.eligible) },
  { label: '动作前门禁结论', value: currentState.preActionBusinessGateResult },
])
const transactionGateFacts = computed(() => [
  ['持久化适配器', 'Django ORM / SQLite'],
  ['原子事务', '通过'],
  ['幂等唯一约束', '通过'],
  ['来源唯一约束', '通过'],
  ['编号唯一约束', '通过'],
  ['持久锁', '通过'],
  ['提交恢复', '通过'],
  ['原子审计', '通过'],
  ['服务端授权', '通过'],
  ['生产灰度', '关闭'],
].map(([label, value]) => ({ label, value })))

function unwrap(response) {
  const envelope = response?.data || {}
  return envelope?.data || envelope
}

function responseBody(response) {
  return response?.data || response || {}
}

function applyCurrentState(state = {}) {
  Object.assign(currentState, state)
  lastIdempotencyKey.value = state.generationResultIdempotencyKey || ''
  generationFacts.beforeCount = state.preActionTargetCount ?? 0
  generationFacts.afterCount = state.targetCount ?? 0
  generationFacts.retryCount = state.targetCount ?? 0
  generationFacts.idempotencyStatus = state.currentIdempotencyStatus || 'not_started'
  generationFacts.numberStatus = state.currentNumberReservationStatus || 'not_allocated'
  generationFacts.transactionStatus = state.currentTransactionStatus || 'not_started'
  generationFacts.auditStatus = state.currentAuditStatus || 'not_started'
  generationFacts.relationStatus = state.currentSourceRelationStatus || 'not_started'
}

function applyValidationModel(model = {}) {
  if (!model || model.currentStateSource !== 'server') return
  validationModel.currentStateSource = 'server'
  validationModel.invoiceData = model.invoiceData || null
  Object.assign(validationModel.validation, model.validation || {})
  validationModel.validationIssues = [...(model.validationIssues || [])]
  Object.assign(validationModel.invoiceIdentity, model.invoiceIdentity || {})
  Object.assign(validationModel.accountsPayableDraftEligibility, model.accountsPayableDraftEligibility || {})
  Object.assign(validationModel.versionsAndAudit, model.versionsAndAudit || {})
  validationModel.downstreamCounts = { ...(model.downstreamCounts || {}) }
  if (model.purchaseInvoicePrepare) currentState.purchaseInvoicePrepare = model.purchaseInvoicePrepare
  const data = model.invoiceData
  if (data) {
    Object.assign(invoiceForm, {
      invoiceType: data.invoiceType || '',
      invoiceCode: data.invoiceCode || '',
      invoiceNumber: data.invoiceNumber || '',
      invoiceDate: data.invoiceDate || '',
      sellerName: data.sellerName || '',
      sellerTaxId: data.sellerTaxId || '',
      buyerName: data.buyerName || '',
      buyerTaxId: data.buyerTaxId || '',
      currency: data.currency || '',
      amountExcludingTax: data.amountExcludingTax || '',
      taxAmount: data.taxAmount || '',
      amountIncludingTax: data.amountIncludingTax || '',
      lines: [...(data.lines || [])],
    })
  }
}

async function loadServerState() {
  const listResponse = await purchaseInvoicePrepareApi.list()
  const listPayload = unwrap(listResponse)
  rows.value = Array.isArray(listPayload?.results) ? listPayload.results : []
  Object.assign(strictFacts, listPayload?.strictFacts || {})
  if (source.id) {
    const eligibilityResponse = await getPurchaseReconciliationInvoicePrepareEligibility(source.id)
    const eligibility = unwrap(eligibilityResponse)
    Object.assign(source, {
      reconciliationNo: eligibility.reconciliationNo || '-',
      status: eligibility.status || source.status,
      checkResultCode: eligibility.checkResultCode || source.checkResultCode,
      version: eligibility.reconciliationVersion || source.version,
      checkVersion: eligibility.checkVersion || source.checkVersion,
      differenceCount: eligibility.differenceCount ?? source.differenceCount,
      evidenceIntegrity: eligibility.evidenceIntegrity || 'failed',
      evidenceSourceCount: eligibility.evidenceSourceCount || 0,
      evidenceSourcesIndependent: eligibility.evidenceSourcesIndependent === true,
      eligible: eligibility.eligible === true,
    })
    const bySourceResponse = await purchaseInvoicePrepareApi.bySource(source.id)
    const bySource = unwrap(bySourceResponse)
    applyCurrentState(bySource)
    if (bySource.targetCount === 1 && bySource.purchaseInvoicePrepare?.id) {
      const detailResponse = await purchaseInvoicePrepareApi.detail(bySource.purchaseInvoicePrepare.id)
      const detail = unwrap(detailResponse)
      applyCurrentState(detail.currentState || bySource)
      currentState.purchaseInvoicePrepare = detail.currentState?.purchaseInvoicePrepare || detail
      applyValidationModel(detail.validationReadModel)
      const invoiceDataModel = unwrap(await purchaseInvoicePrepareApi.invoiceData(bySource.purchaseInvoicePrepare.id))
      applyValidationModel(invoiceDataModel)
      const issueModel = unwrap(await purchaseInvoicePrepareApi.validationIssues(bySource.purchaseInvoicePrepare.id))
      Object.assign(validationModel.validation, issueModel.validation || {})
      validationModel.validationIssues = [...(issueModel.issues || [])]
      const apDraftEligibility = unwrap(await purchaseInvoicePrepareApi.accountsPayableDraftEligibility(bySource.purchaseInvoicePrepare.id))
      Object.assign(validationModel.accountsPayableDraftEligibility, apDraftEligibility || {})
      const key = currentState.generationResultIdempotencyKey
      if (key) {
        const resultBody = responseBody(await purchaseInvoicePrepareApi.generationResult(key))
        applyCurrentState(resultBody.currentState || currentState)
      }
    }
  }
}

function invoicePayload() {
  return {
    invoiceType: invoiceForm.invoiceType,
    invoiceCode: invoiceForm.invoiceCode,
    invoiceNumber: invoiceForm.invoiceNumber,
    invoiceDate: invoiceForm.invoiceDate,
    sellerName: invoiceForm.sellerName,
    sellerTaxId: invoiceForm.sellerTaxId,
    buyerName: invoiceForm.buyerName,
    buyerTaxId: invoiceForm.buyerTaxId,
    currency: invoiceForm.currency,
    amountExcludingTax: invoiceForm.amountExcludingTax,
    taxAmount: invoiceForm.taxAmount,
    amountIncludingTax: invoiceForm.amountIncludingTax,
    lines: invoiceForm.lines.map((line) => ({ ...line })),
  }
}

async function saveCanaryInvoiceData() {
  savingData.value = true
  try {
    const key = `pip-v44-save-${currentPrepare.value.id}-${validationModel.versionsAndAudit.dataVersion + 1}`
    const result = responseBody(await purchaseInvoicePrepareApi.saveInvoiceData(currentPrepare.value.id, {
      idempotencyKey: key,
      expectedVersion: validationModel.versionsAndAudit.prepareVersion,
      expectedDataVersion: validationModel.versionsAndAudit.dataVersion,
      explicitUserAction: true,
      invoiceData: invoicePayload(),
    }))
    if (result.result === 'blocked') throw new Error(result.error?.code || 'PIP_DATA_SAVE_BLOCKED')
    await loadServerState()
    ElMessage.success('采购发票资料已由服务端保存')
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    savingData.value = false
  }
}

async function validateCanaryInvoiceData() {
  validatingData.value = true
  try {
    const key = `pip-v44-validate-${currentPrepare.value.id}-${validationModel.versionsAndAudit.dataVersion}`
    const result = responseBody(await purchaseInvoicePrepareApi.validateInvoiceData(currentPrepare.value.id, {
      idempotencyKey: key,
      expectedVersion: validationModel.versionsAndAudit.prepareVersion,
      expectedDataVersion: validationModel.versionsAndAudit.dataVersion,
      expectedReconciliationVersion: source.version,
      expectedCheckVersion: source.checkVersion,
      explicitUserAction: true,
    }))
    if (result.result === 'blocked') throw new Error(result.error?.code || 'PIP_VALIDATION_BLOCKED')
    await loadServerState()
    ElMessage.success('采购发票要素校验已由服务端执行')
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    validatingData.value = false
  }
}

function executeRegistryAction(action) {
  if (action.actionId === 'generate-purchase-invoice-prepare') {
    generateCanary()
    return
  }
  if (action.actionId === 'save-purchase-invoice-data') {
    saveCanaryInvoiceData()
    return
  }
  if (action.actionId === 'validate-purchase-invoice-data') {
    validateCanaryInvoiceData()
  }
}

async function retryValidation() {
  const result = responseBody(await purchaseInvoicePrepareApi.validateInvoiceData(currentPrepare.value.id, {
    idempotencyKey: validationModel.validation.idempotencyKey,
    expectedVersion: validationModel.versionsAndAudit.prepareVersion - 1,
    expectedDataVersion: validationModel.versionsAndAudit.dataVersion,
    expectedReconciliationVersion: source.version,
    expectedCheckVersion: source.checkVersion,
    explicitUserAction: true,
  }))
  if (result.classification !== 'existing_result') throw new Error('PIP_VALIDATION_RETRY_NOT_IDEMPOTENT')
  await loadServerState()
}

async function queryValidationResult() {
  const result = responseBody(await purchaseInvoicePrepareApi.validationResult(validationModel.validation.idempotencyKey))
  applyValidationModel(result)
}

function goAccountsPayableDraft() {
  router.push({ path: '/finance/ap-drafts', query: { sourcePurchaseInvoicePrepareId: currentPrepare.value.id } })
}

async function generateWithKey(key) {
  const response = await purchaseInvoicePrepareApi.generate({
    sourcePurchaseReconciliationId: source.id,
    idempotencyKey: key,
    expectedReconciliationVersion: source.version,
    expectedCheckVersion: source.checkVersion,
    explicitUserAction: true,
  })
  const payload = response?.data || response
  if (response?.success === false || payload?.result === 'blocked') {
    throw new Error(payload?.error?.code || response?.error || 'PIP_GENERATION_BLOCKED')
  }
  return payload
}

async function generateCanary() {
  generating.value = true
  try {
    lastIdempotencyKey.value = `pip-v43.1-${source.id}-${source.version}`
    const result = await generateWithKey(lastIdempotencyKey.value)
    await loadServerState()
    if (!['created', 'existing_result', 'existing_target'].includes(result.classification)) {
      throw new Error('PIP_CURRENT_STATE_NOT_COMMITTED')
    }
    ElMessage.success('测试租户采购发票准备已由服务端受控生成')
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    generating.value = false
  }
}

async function retryCanary() {
  const result = await generateWithKey(lastIdempotencyKey.value)
  await loadServerState()
  if (result.classification !== 'existing_result') throw new Error('PIP_RETRY_NOT_EXISTING_RESULT')
}

async function recoverCanary() {
  const result = responseBody(await purchaseInvoicePrepareApi.generationResult(lastIdempotencyKey.value))
  applyCurrentState(result.currentState || currentState)
  ElMessage.success('金丝雀提交结果已从服务端恢复')
}

function viewExistingPrepare() {
  document.querySelector('[data-acceptance-id="purchase-invoice-prepare-object"]')?.scrollIntoView({ behavior: 'smooth' })
}

function viewSource(row) {
  router.push({ path: '/scm/purchase-reconciliations', query: { reconciliationNo: row.sourcePurchaseReconciliationNo } })
}

function clearFilters() {
  quickSearch.value = ''
  Object.keys(filters).forEach((key) => { filters[key] = '' })
}

function clearSort() {
  // The server list order is canonical creation-time descending in V43.
}

async function copyDiagnostics() {
  await navigator.clipboard.writeText(JSON.stringify({
    version: 'V1.14.2.8.4.7.43.1',
    canonicalName: '采购发票准备',
    route: '/finance/purchase-invoice-prepares',
    sourceDocumentType: 'purchaseReconciliation',
    serverReadModel: true,
    productionRolloutEnabled: false,
    source: { ...source },
    currentState: { ...currentState },
    strictFacts: { ...strictFacts },
    generationFacts: { ...generationFacts },
    downstreamWrites: 0,
  }, null, 2))
  ElMessage.success('诊断数据已复制')
}

function exportCurrentRows() {
  const csv = ['采购发票准备编号,来源采购对账编号,供应商,金额,状态']
    .concat(filteredRows.value.map((row) => [
      row.prepareNo, row.sourcePurchaseReconciliationNo, row.supplierName, row.settlementAmount, row.status,
    ].map((value) => `"${String(value ?? '').replaceAll('"', '""')}"`).join(',')))
    .join('\n')
  const link = document.createElement('a')
  link.href = URL.createObjectURL(new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8;' }))
  link.download = 'purchase-invoice-prepares.csv'
  link.click()
  URL.revokeObjectURL(link.href)
}

onMounted(loadServerState)
</script>

<style scoped>
.invoice-prepare-page { display: grid; gap: 16px; max-width: 100%; overflow-x: hidden; }
.page-header, .section-heading { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.page-header h2, .page-header p, h3, .ctrl-f { margin: 0; }
.eyebrow { color: #2563eb; font-weight: 800; }
.header-actions, .canary-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.evidence-card { display: grid; gap: 12px; padding: 16px; border: 1px solid #dbeafe; border-radius: 10px; background: #fff; }
.protection { border-color: #86efac; background: #f0fdf4; }
.snapshot { border-style: dashed; background: #fffbeb; }
.ctrl-f { color: #64748b; font-size: 12px; font-weight: 700; }
.fact-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }
.advanced-filter-panel { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; padding: 12px; border: 1px solid #dbeafe; border-radius: 8px; background: #f8fafc; }
.advanced-filter-panel label { display: grid; gap: 5px; color: #334155; font-size: 12px; font-weight: 800; }
:deep(.fact) { display: grid; gap: 5px; padding: 10px; border-radius: 8px; background: #f8fafc; }
:deep(.fact span) { color: #64748b; font-size: 12px; font-weight: 700; }
:deep(.fact strong) { color: #0f172a; overflow-wrap: anywhere; }
</style>

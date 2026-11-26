<template>
  <main class="settlement-boundary-overview-page app-page-shell">
    <section class="app-hero-section">
      <div>
        <p class="app-eyebrow">V1.13.52 · Finance</p>
        <h1>企业结算类型边界总览</h1>
        <p class="app-hero-copy">
          本页面只用于说明企业结算类型、当前应付结算开发范围和未来扩展边界，不新增结算业务，不改变任何业务状态。
          当前阶段锁定采购到付款的应付结算链路，不建设统一大结算平台。
        </p>
      </div>
      <div class="page-actions">
        <router-link class="app-nav-button" to="/finance/payment-execution-prepares">返回付款执行准备页</router-link>
        <router-link class="app-nav-button" to="/finance/bank-account-master-design">返回银行账户档案前置设计页</router-link>
        <router-link class="app-nav-button" to="/finance/bank-flow-import-validation-preview/PEP2026071311191257">返回银行流水导入校验预览页</router-link>
        <router-link class="app-nav-button" to="/finance/payment-voucher-prepare-preview/PEP2026071311191257">查看付款凭证准备只读预览</router-link>
        <el-button type="primary" plain @click="copyDiagnosticData">复制诊断数据</el-button>
      </div>
    </section>

    <section class="boundary-card">
      <strong>本轮统一保护结论：</strong>
      本轮不新增正式结算模块，不新增统一结算中心，不开发应收、工资、费用报销、税费、预收预付、内部往来、项目、资产购置或资金调拨结算；
      不真实付款，不生成或导入银行流水，不生成付款凭证，不核销，不写总账，不过账，不修改任何业务金额。
    </section>

    <section class="protection-grid">
      <article v-for="item in unifiedProtectionConclusion" :key="item.item">
        <span>{{ item.item }}</span>
        <strong>{{ item.result }}</strong>
      </article>
    </section>

    <section class="table-card">
      <div class="table-title">
        <div>
          <h2>企业结算类型总览</h2>
          <p class="helper-text">展示企业中可能存在的结算类型。本轮仅锁定应付结算链路，其它类型仅列为未来边界。</p>
        </div>
      </div>
      <el-table :data="settlementTypeItems" border stripe>
        <el-table-column prop="typeName" label="结算类型" min-width="170" />
        <el-table-column prop="businessObjects" label="业务对象" min-width="460" />
        <el-table-column prop="currentStatus" label="当前状态" min-width="170" />
        <el-table-column prop="developedThisRound" label="本轮是否新增业务功能" min-width="190" />
      </el-table>
    </section>

    <section class="table-card highlight-card">
      <div class="table-title">
        <div>
          <h2>当前应付结算链路范围</h2>
          <p class="helper-text">当前开发范围仅围绕采购到付款的应付结算链路，不扩展到应收、工资、费用、税费等其它结算。</p>
        </div>
      </div>
      <div class="chain-flow">
        <span v-for="item in currentScopeItems" :key="item">{{ item }}</span>
      </div>
      <div class="readonly-note-grid">
        <article v-for="item in currentScopeProtectionItems" :key="item">
          {{ item }}
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <div>
          <h2>第一阶段锁定范围</h2>
          <p class="helper-text">第一阶段只保证应付结算链路可追踪、可准备、可模拟、可检查，但不进入真实付款、凭证、核销和总账。</p>
        </div>
      </div>
      <div class="two-column-list">
        <article>
          <h3>第一阶段目标</h3>
          <ul>
            <li v-for="item in lockedScopeItems" :key="item">{{ item }}</li>
          </ul>
        </article>
        <article>
          <h3>第一阶段不做</h3>
          <ul>
            <li v-for="item in lockedOutItems" :key="item">{{ item }}</li>
          </ul>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <div>
          <h2>暂不展开的结算类型</h2>
          <p class="helper-text">以下结算类型不在当前版本展开，不提供入口，不生成业务数据。</p>
        </div>
      </div>
      <el-table :data="deferredSettlementItems" border stripe>
        <el-table-column prop="typeName" label="结算类型" min-width="170" />
        <el-table-column prop="deferReason" label="暂不展开原因" min-width="420" />
        <el-table-column prop="futureTrigger" label="未来触发条件" min-width="420" />
        <el-table-column prop="developedThisRound" label="本轮是否开发" min-width="160" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <div>
          <h2>未来共享能力边界</h2>
          <p class="helper-text">银行账户、银行流水、凭证、核销、总账等能力未来可复用，但当前只为应付结算做前置设计。</p>
        </div>
      </div>
      <el-table :data="sharedCapabilityItems" border stripe>
        <el-table-column prop="capability" label="共享能力" min-width="210" />
        <el-table-column prop="futureUse" label="未来用途" min-width="420" />
        <el-table-column prop="currentBoundary" label="当前边界" min-width="420" />
      </el-table>
    </section>

    <section class="table-card warning-panel">
      <div class="table-title">
        <div>
          <h2>不做“大结算平台”的边界说明</h2>
          <p class="helper-text">PCE-ERP 是企业管理软件，不是完整财务套件；结算能力按业务链路逐步建设，不一次性堆成复杂平台。</p>
        </div>
      </div>
      <ol class="number-list">
        <li v-for="item in notBigSettlementPlatformItems" :key="item">{{ item }}</li>
      </ol>
    </section>

    <section class="table-card">
      <div class="table-title">
        <div>
          <h2>当前缺口与后续建议</h2>
          <p class="helper-text">继续完成应付结算链路，暂不启动应收、工资、费用、税费等新结算线。</p>
        </div>
      </div>
      <div class="two-column-list">
        <article>
          <h3>当前缺口</h3>
          <ul>
            <li v-for="item in currentGapItems" :key="item">{{ item }}</li>
          </ul>
        </article>
        <article>
          <h3>后续建议</h3>
          <ul>
            <li v-for="item in recommendedNextStepItems" :key="item">{{ item }}</li>
          </ul>
        </article>
      </div>
    </section>
  </main>
</template>

<script setup>
import { computed } from 'vue'
import { ElMessage } from 'element-plus'

const no = () => '否'

const unifiedProtectionConclusion = [
  '本轮是否新增正式结算模块',
  '本轮是否新增统一结算中心',
  '本轮是否开发应收结算',
  '本轮是否开发工资结算',
  '本轮是否开发费用报销结算',
  '本轮是否开发税费结算',
  '本轮是否开发预收预付结算',
  '本轮是否开发内部往来结算',
  '本轮是否开发项目结算',
  '本轮是否开发资产购置结算',
  '本轮是否真实付款',
  '本轮是否生成银行流水',
  '本轮是否导入银行流水',
  '本轮是否生成付款凭证',
  '本轮是否核销',
  '本轮是否写总账',
  '本轮是否过账',
  '本轮是否修改业务金额',
  '本轮是否修改采购、收货、检验、库存',
].map((item) => ({ item, result: no() }))

const settlementTypeItems = [
  {
    typeName: '应付结算',
    businessObjects: '供应商、采购订单、收货、检验、入库、供应商结算、采购发票、应付确认、付款申请、付款指令、付款执行、银行流水、核销、凭证',
    currentStatus: '当前正在开发',
    developedThisRound: no(),
  },
  {
    typeName: '应收结算',
    businessObjects: '客户、销售订单、出货、销售发票、应收确认、收款、银行流水、核销、凭证',
    currentStatus: '未来开发，当前不展开',
    developedThisRound: no(),
  },
  {
    typeName: '工资结算',
    businessObjects: '员工、考勤、工资表、社保、公积金、个税、实发工资、工资付款、凭证',
    currentStatus: '未来开发，当前不展开',
    developedThisRound: no(),
  },
  {
    typeName: '费用报销结算',
    businessObjects: '员工报销、费用申请、费用审核、付款、发票、凭证',
    currentStatus: '未来开发，当前不展开',
    developedThisRound: no(),
  },
  {
    typeName: '预付款 / 预收款结算',
    businessObjects: '供应商预付款、客户预收款、后续采购或销售核销',
    currentStatus: '未来开发，当前不展开',
    developedThisRound: no(),
  },
  {
    typeName: '税费结算',
    businessObjects: '增值税、附加税、企业所得税、个税、应交税费、税费缴纳、凭证',
    currentStatus: '未来开发，当前不展开',
    developedThisRound: no(),
  },
  {
    typeName: '内部往来结算',
    businessObjects: '集团内部公司、部门、内部交易、内部往来款、内部核销',
    currentStatus: '后续扩展，当前不展开',
    developedThisRound: no(),
  },
  {
    typeName: '项目结算',
    businessObjects: '项目合同、项目成本、项目收入、项目收付款、项目结算单',
    currentStatus: '后续扩展，当前不展开',
    developedThisRound: no(),
  },
  {
    typeName: '资产购置结算',
    businessObjects: '固定资产采购、资产验收、资产发票、付款、折旧前置',
    currentStatus: '后续扩展，当前不展开',
    developedThisRound: no(),
  },
  {
    typeName: '资金调拨 / 银行资金结算',
    businessObjects: '企业银行账户、内部资金调拨、银行流水、资金余额、资金预测',
    currentStatus: '后续扩展，当前不展开',
    developedThisRound: no(),
  },
]

const currentScopeItems = [
  '供应商结算',
  '采购发票准备',
  '应付确认准备',
  '付款申请准备',
  '付款指令准备',
  '付款执行准备',
  '付款执行前安全检查',
  '付款执行模拟',
  '正式付款执行入口预览',
  '真实付款前最终评审',
  '真实付款状态影响设计',
  '银行流水生成 / 导入边界设计',
  '银行流水真实对象与导入校验设计',
  '银行流水只读对象与导入校验预览',
  '银行流水导入校验预览页',
  '银行账户档案前置设计',
  '银行账户档案只读样例与脱敏规则设计',
  '付款凭证准备前置边界与只读预览设计',
]

const currentScopeProtectionItems = [
  '当前仍未真实付款',
  '当前仍未生成银行流水',
  '当前仍未导入银行流水',
  '当前仍未生成付款凭证',
  '当前仍未核销',
  '当前仍未写总账',
  '当前仍未过账',
]

const lockedScopeItems = [
  '能从供应商结算走到付款执行准备',
  '能做付款前风险检查',
  '能做付款执行模拟',
  '能设计银行流水前置边界',
  '能设计银行账户前置边界',
  '能保证不误付款',
  '能保证不误生成凭证',
  '能保证不误核销',
  '能保证不误写总账',
]

const lockedOutItems = [
  '应收结算',
  '工资结算',
  '费用报销结算',
  '税费结算',
  '预收预付结算',
  '内部往来结算',
  '项目结算',
  '资产购置结算',
  '资金调拨结算',
  '完整财务报表',
  '完整总账系统',
  '真实银企直连',
]

const deferredSettlementItems = [
  ['应收结算', '当前采购到付款链路尚未进入真实付款与核销，先不引入销售回款链路。', '销售订单、出货、销售发票和客户收款链路启动后再进入。'],
  ['工资结算', '工资涉及人事、考勤、社保、公积金和个税，当前基础链路尚未启动。', 'HR 薪酬链路和付款审批制度明确后再进入。'],
  ['费用报销结算', '费用报销涉及员工申请、票据、审批和预算控制，当前不混入 P2P 应付链路。', '费用申请、费用审核和报销付款链路启动后再进入。'],
  ['税费结算', '税费需要税务口径、申报规则和正式凭证配套，当前不展开。', '税务模块和正式财务制度确认后再进入。'],
  ['预付款 / 预收款结算', '预收预付涉及后续核销与跨期间管理，当前不进入。', '预收预付业务场景和核销规则明确后再进入。'],
  ['内部往来结算', '内部往来需要组织、公司间交易和内部抵消规则，当前不展开。', '集团组织和内部交易规则明确后再进入。'],
  ['项目结算', '项目结算依赖项目合同、成本、收入和收付款链路，当前不展开。', '项目管理链路启动后再进入。'],
  ['资产购置结算', '资产购置涉及验收、付款和折旧前置，当前不展开。', '固定资产链路启动后再进入。'],
  ['资金调拨 / 银行资金结算', '资金调拨涉及银行账户余额、内部资金计划和审批，当前不展开。', '资金管理和银行账户正式档案建立后再进入。'],
].map(([typeName, deferReason, futureTrigger]) => ({
  typeName,
  deferReason,
  futureTrigger,
  developedThisRound: no(),
}))

const sharedCapabilityItems = [
  ['企业银行账户档案', '未来可服务付款、收款、资金调拨和银行流水匹配。', '当前只为应付结算做前置设计。'],
  ['供应商 / 客户银行账户档案', '未来可服务供应商付款和客户收款。', '当前仅设计供应商银行账户样例与脱敏规则。'],
  ['银行流水', '未来可服务付款、收款、核销和资金对账。', '当前不生成、不导入，只做只读预览和边界说明。'],
  ['付款 / 收款执行', '未来可区分付款执行和收款确认。', '当前只围绕付款执行准备与模拟。'],
  ['核销规则', '未来可服务应付、应收、预收预付等链路。', '当前不核销，只做边界说明。'],
  ['凭证准备', '未来可服务多类结算的凭证前置。', '当前不生成付款凭证和正式凭证。'],
  ['正式凭证', '未来可服务正式财务结果。', '当前不进入正式凭证。'],
  ['总账前置检查', '未来可作为正式总账写入前校验。', '当前不写总账，不过账。'],
  ['审计日志', '未来可记录敏感操作。', '当前仅做诊断和说明。'],
  ['权限控制', '未来可控制付款、账号查看和凭证处理。', '当前不启用正式权限流程。'],
  ['账号脱敏', '未来可服务银行账户、流水和付款页面。', '当前只做只读样例设计。'],
  ['风险预警', '未来可服务跨链路风险识别。', '当前只服务应付结算边界说明。'],
  ['业务追踪', '未来可服务 P2P / O2C / MFG 等链路。', '当前以 P2P 为样板。'],
  ['P2P / O2C 验证中心', '未来可扩展到销售收款链路。', '当前不启动 O2C 结算。'],
].map(([capability, futureUse, currentBoundary]) => ({ capability, futureUse, currentBoundary }))

const notBigSettlementPlatformItems = [
  'PCE-ERP 当前不是完整财务套件。',
  '当前不做统一大结算平台。',
  '当前不把应付、应收、工资、费用、税费全部塞进一个大模块。',
  '当前结算能力按业务链路逐步建设。',
  '当前先做采购到付款的应付结算。',
  '后续应收结算应从销售到收款链路进入。',
  '后续工资结算应从人事薪酬链路进入。',
  '后续费用结算应从费用报销链路进入。',
  '后续税费结算应从税务 / 财务链路进入。',
  '银行流水、账户档案、凭证、核销是可复用能力，但不能提前做成复杂平台。',
]

const currentGapItems = [
  '应付结算尚未进入真实付款。',
  '银行流水尚未正式导入。',
  '银行账户档案仍为只读设计。',
  '付款凭证准备尚未正式开发。',
  '核销尚未正式开发。',
  '总账写入尚未正式开发。',
  '应收结算暂未启动。',
  '工资结算暂未启动。',
  '税费结算暂未启动。',
]

const recommendedNextStepItems = [
  '继续完成应付结算链路。',
  '下一步优先设计付款凭证准备前置边界。',
  '再做付款凭证准备只读对象与分录预览稳定检查。',
  '再做核销前置设计。',
  '再做总账前置设计。',
  '应收、工资、费用、税费暂时不启动。',
  '不要新增统一大结算中心。',
]

const protectionFlags = {
  createFormalSettlementModule: false,
  createUnifiedSettlementCenter: false,
  developReceivableSettlement: false,
  developSalarySettlement: false,
  developExpenseSettlement: false,
  developTaxSettlement: false,
  developPrepaymentSettlement: false,
  developInternalSettlement: false,
  developProjectSettlement: false,
  developAssetSettlement: false,
  executeRealPayment: false,
  generateBankFlow: false,
  importBankFlow: false,
  generatePaymentVoucher: false,
  writeOffPayment: false,
  writeLedger: false,
  postLedger: false,
  modifyBusinessAmount: false,
  modifyPurchaseReceiptInspectionInventory: false,
}

const settlementBoundaryOverviewSummary = computed(() => ({
  page: '企业结算类型边界总览',
  version: 'V1.13.52',
  settlementTypeItems,
  currentScopeItems,
  lockedScopeItems,
  deferredSettlementItems,
  sharedCapabilityItems,
  notBigSettlementPlatformItems,
  currentGapItems,
  recommendedNextStepItems,
  unifiedProtectionConclusion,
  protectionFlags,
  timestamp: new Date().toISOString(),
}))

const diagnosticData = computed(() => ({
  settlementBoundaryOverviewSummary: settlementBoundaryOverviewSummary.value,
  diagnosticChineseSummary: {
    页面名称: '企业结算类型边界总览',
    页面版本: 'V1.13.52',
    当前锁定范围: '应付结算链路',
    本轮是否新增正式结算模块: no(),
    本轮是否新增统一结算中心: no(),
    本轮是否开发应收结算: no(),
    本轮是否开发工资结算: no(),
    本轮是否开发费用报销结算: no(),
    本轮是否开发税费结算: no(),
    本轮是否开发预收预付结算: no(),
    本轮是否真实付款: no(),
    本轮是否生成银行流水: no(),
    本轮是否生成付款凭证: no(),
    本轮是否核销: no(),
    本轮是否写总账: no(),
    本轮是否过账: no(),
  },
}))

const copyDiagnosticData = async () => {
  try {
    await navigator.clipboard.writeText(JSON.stringify(diagnosticData.value, null, 2))
    ElMessage.success('诊断数据已复制')
  } catch (error) {
    console.error(error)
    ElMessage.error('复制失败，请稍后重试')
  }
}
</script>

<style scoped>
.settlement-boundary-overview-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.page-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}

.boundary-card,
.table-card,
.summary-card,
.protection-grid article,
.two-column-list article {
  border: 1px solid #d8e0ea;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
}

.boundary-card {
  padding: 16px 18px;
  line-height: 1.8;
  color: #334155;
  background: #f8fbff;
}

.protection-grid,
.summary-grid,
.readonly-note-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 12px;
}

.protection-grid article,
.summary-card,
.readonly-note-grid article {
  padding: 14px;
}

.protection-grid span,
.summary-card span {
  display: block;
  color: #64748b;
  font-size: 13px;
}

.protection-grid strong,
.summary-card strong {
  display: block;
  margin-top: 6px;
  color: #0f766e;
  font-size: 20px;
}

.table-card {
  padding: 18px;
}

.highlight-card {
  border-color: #bae6fd;
  background: #f0f9ff;
}

.warning-panel {
  border-color: #fed7aa;
  background: #fff7ed;
}

.table-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.table-title h2 {
  margin: 0;
  color: #0f172a;
  font-size: 20px;
}

.helper-text {
  margin: 6px 0 0;
  color: #64748b;
  line-height: 1.7;
}

.chain-flow {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 12px 0 16px;
}

.chain-flow span {
  position: relative;
  padding: 8px 12px;
  border-radius: 999px;
  background: #e0f2fe;
  color: #075985;
  font-weight: 700;
}

.chain-flow span:not(:last-child)::after {
  content: '→';
  margin-left: 10px;
  color: #0284c7;
}

.readonly-note-grid article {
  color: #0f766e;
  font-weight: 700;
  background: #ecfdf5;
}

.two-column-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 14px;
}

.two-column-list article {
  padding: 16px;
}

.two-column-list h3 {
  margin: 0 0 10px;
  color: #0f172a;
}

.two-column-list ul,
.number-list {
  margin: 0;
  padding-left: 20px;
  color: #334155;
  line-height: 1.8;
}
</style>

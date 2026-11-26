<template>
  <main class="bank-account-master-design-page app-page-shell">
    <section class="app-hero-section">
      <div>
        <p class="app-eyebrow">V1.13.51 · Finance</p>
        <h1>银行账户档案前置设计</h1>
        <p class="app-hero-copy">
          本页面用于银行账户档案只读样例与脱敏规则设计。页面中的账号均为样例、脱敏账号或占位符，不是真实完整银行账号，不可用于付款、导入银行流水、核销或总账。
        </p>
      </div>
      <div class="page-actions">
        <router-link class="app-nav-button" to="/finance/settlement-boundary-overview">查看企业结算边界总览</router-link>
        <router-link class="app-nav-button" to="/finance/payment-execution-prepares">返回付款执行准备页</router-link>
        <router-link class="app-nav-button" to="/finance/bank-flow-import-validation-preview/PEP2026071311191257">返回银行流水导入校验预览页</router-link>
        <el-button type="primary" plain @click="copyDiagnosticData">复制诊断数据</el-button>
      </div>
    </section>

    <section class="boundary-card">
      <strong>本轮统一保护结论：</strong>
      本轮不录入企业真实银行账号，不录入供应商真实银行账号，不显示真实完整银行账号，不新增正式银行账户档案，不新增正式供应商银行档案，
      不新增查看完整账号、编辑、保存、删除、上传、导入、导出按钮，不上传文件，不读取 Excel / CSV，不导入银行流水，不生成银行流水，
      不生成付款凭证，不核销，不写总账，不过账。
    </section>

    <section class="protection-grid">
      <article v-for="item in unifiedProtectionConclusion" :key="item.item">
        <span>{{ item.item }}</span>
        <strong>{{ item.result }}</strong>
      </article>
    </section>

    <section class="table-card highlight-card">
      <div class="table-title">
        <div>
          <h2>银行账户档案只读样例与脱敏规则</h2>
          <p class="helper-text">
            本区域是 V1.13.51 主区域，只展示样例账号、脱敏规则、完整账号查看权限、查看审计规则和风险提示。所有账号均非真实完整账号。
          </p>
        </div>
      </div>
      <div class="sample-summary-grid">
        <article>
          <span>企业银行账户样例</span>
          <strong>脱敏显示</strong>
          <small>6222 **** **** 1234</small>
        </article>
        <article>
          <span>供应商银行账户样例</span>
          <strong>脱敏显示</strong>
          <small>6222 **** **** 5678</small>
        </article>
        <article>
          <span>完整账号展示</span>
          <strong>不显示</strong>
          <small>本轮不新增查看完整账号按钮</small>
        </article>
        <article>
          <span>正式档案写入</span>
          <strong>否</strong>
          <small>只读样例，不写业务数据</small>
        </article>
      </div>
    </section>

    <section class="table-card">
      <div class="table-title">
        <div>
          <h2>企业银行账户只读样例</h2>
          <p class="helper-text">以下数据仅为样例，不是真实银行账户，不可用于付款、导入银行流水、核销或总账。</p>
        </div>
      </div>
      <el-table :data="enterpriseReadonlySampleItems" border stripe>
        <el-table-column prop="fieldName" label="样例字段" min-width="180" />
        <el-table-column prop="sampleValue" label="示例值" min-width="260" />
        <el-table-column prop="isRealAccount" label="是否真实账号" min-width="150" />
        <el-table-column prop="writeFormalMasterThisRound" label="本轮是否写入正式档案" min-width="210" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <div>
          <h2>供应商银行账户只读样例</h2>
          <p class="helper-text">以下数据仅为样例，不是真实供应商银行账户，不可用于付款、导入银行流水、核销或总账。</p>
        </div>
      </div>
      <el-table :data="supplierReadonlySampleItems" border stripe>
        <el-table-column prop="fieldName" label="样例字段" min-width="180" />
        <el-table-column prop="sampleValue" label="示例值" min-width="260" />
        <el-table-column prop="isRealAccount" label="是否真实账号" min-width="150" />
        <el-table-column prop="writeFormalMasterThisRound" label="本轮是否写入正式档案" min-width="210" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>银行账号脱敏规则设计</h2>
        <span>只做规则设计，不执行真实脱敏，不输出真实完整账号</span>
      </div>
      <el-table :data="maskingRuleItems" border stripe>
        <el-table-column prop="ruleName" label="脱敏规则" min-width="230" />
        <el-table-column prop="description" label="规则说明" min-width="420" />
        <el-table-column prop="executedThisRound" label="本轮是否执行真实脱敏" min-width="210" />
        <el-table-column prop="showFullAccountThisRound" label="本轮是否显示完整账号" min-width="210" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>完整账号查看权限设计</h2>
        <span>本轮不启用权限控制，不允许查看完整账号</span>
      </div>
      <el-table :data="fullAccountPermissionItems" border stripe>
        <el-table-column prop="permissionItem" label="权限项" min-width="250" />
        <el-table-column prop="description" label="未来控制说明" min-width="420" />
        <el-table-column prop="enabledThisRound" label="本轮是否启用权限控制" min-width="210" />
        <el-table-column prop="allowViewFullAccountThisRound" label="本轮是否允许查看完整账号" min-width="230" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>完整账号查看审计规则设计</h2>
        <span>本轮不写正式审计日志</span>
      </div>
      <el-table :data="fullAccountAuditRuleItems" border stripe>
        <el-table-column prop="auditItem" label="审计项" min-width="210" />
        <el-table-column prop="description" label="未来记录内容" min-width="430" />
        <el-table-column prop="writeFormalAuditLogThisRound" label="本轮是否写正式审计日志" min-width="230" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>账号脱敏风险提示</h2>
        <span>只做风险提示，不处理真实风险</span>
      </div>
      <el-table :data="maskingRiskItems" border stripe>
        <el-table-column prop="riskName" label="风险项" min-width="250" />
        <el-table-column prop="description" label="风险说明" min-width="430" />
        <el-table-column prop="triggeredRealRiskThisRound" label="本轮是否触发真实风险" min-width="210" />
        <el-table-column prop="handlingThisRound" label="本轮处理方式" min-width="250" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>与后续正式维护流程关系</h2>
        <span>本轮只读样例与脱敏规则先行</span>
      </div>
      <ol class="relation-list">
        <li v-for="item in maintenanceFlowRelationItems" :key="item">{{ item }}</li>
      </ol>
    </section>

    <section class="table-card">
      <div class="table-title">
        <div>
          <h2>企业银行账户档案设计</h2>
          <p class="helper-text">
            企业银行账户档案用于记录企业可用于付款、收款、退款和银行流水匹配的银行账户。未来正式付款和银行流水导入时，必须先确认企业银行账户是否合法、启用、币种正确、权限允许。
          </p>
        </div>
      </div>
      <el-table :data="enterpriseBankAccountDesignItems" border stripe>
        <el-table-column prop="fieldName" label="字段名称" min-width="180" />
        <el-table-column prop="meaning" label="字段含义" min-width="330" />
        <el-table-column prop="required" label="是否必填" min-width="120" />
        <el-table-column prop="source" label="来源" min-width="180" />
        <el-table-column prop="writeFormalMasterThisRound" label="本轮是否写入正式档案" min-width="210" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <div>
          <h2>供应商银行档案设计</h2>
          <p class="helper-text">
            供应商银行档案用于记录供应商收款账户。未来付款执行、银行流水匹配、付款核销前，必须确认供应商收款账户有效、已复核、未停用，并与付款申请中的供应商一致。
          </p>
        </div>
      </div>
      <el-table :data="supplierBankAccountDesignItems" border stripe>
        <el-table-column prop="fieldName" label="字段名称" min-width="180" />
        <el-table-column prop="meaning" label="字段含义" min-width="330" />
        <el-table-column prop="required" label="是否必填" min-width="120" />
        <el-table-column prop="source" label="来源" min-width="180" />
        <el-table-column prop="writeFormalMasterThisRound" label="本轮是否写入正式档案" min-width="210" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>银行账户状态规则设计</h2>
        <span>本轮不创建、不改变任何账户状态</span>
      </div>
      <el-table :data="accountStatusRuleItems" border stripe>
        <el-table-column prop="accountType" label="账户类型" min-width="180" />
        <el-table-column prop="statusName" label="状态" min-width="150" />
        <el-table-column prop="description" label="说明" min-width="360" />
        <el-table-column prop="createdOrChangedThisRound" label="本轮是否创建或变更" min-width="210" />
      </el-table>
      <p class="helper-text status-note">
        未来只有“启用 + 已复核 + 未冻结 + 未失效”的账户，才允许进入付款和银行流水匹配流程。本轮不改变任何账户状态。
      </p>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>银行账户校验规则设计</h2>
        <span>只设计校验规则，本轮不执行校验</span>
      </div>
      <el-table :data="validationRuleItems" border stripe>
        <el-table-column prop="ruleScope" label="规则范围" min-width="180" />
        <el-table-column prop="ruleName" label="校验规则" min-width="300" />
        <el-table-column prop="purpose" label="校验目的" min-width="340" />
        <el-table-column prop="executedThisRound" label="本轮是否执行校验" min-width="190" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>权限与审计规则设计</h2>
        <span>只设计权限和审计口径，本轮不执行、不写正式审计日志</span>
      </div>
      <el-table :data="permissionAuditRuleItems" border stripe>
        <el-table-column prop="ruleType" label="规则类型" min-width="150" />
        <el-table-column prop="ruleName" label="规则名称" min-width="310" />
        <el-table-column prop="description" label="说明" min-width="360" />
        <el-table-column prop="executedThisRound" label="本轮是否执行" min-width="150" />
        <el-table-column prop="writeFormalAuditLogThisRound" label="本轮是否写正式审计日志" min-width="230" />
      </el-table>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>与银行流水导入校验预览页的关系</h2>
        <span>两类档案是未来正式银行流水导入校验的前置条件</span>
      </div>
      <ol class="relation-list">
        <li v-for="item in bankFlowPreviewRelationItems" :key="item">{{ item }}</li>
      </ol>
    </section>

    <section class="table-card">
      <div class="table-title">
        <h2>当前缺口与后续建议</h2>
        <span>本轮只备案，不开发正式维护流程</span>
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

function no() {
  return '否'
}

function designItem(fieldName, meaning, required, source) {
  return { fieldName, meaning, required, source, writeFormalMasterThisRound: no() }
}

function sampleItem(fieldName, sampleValue) {
  return { fieldName, sampleValue, isRealAccount: no(), writeFormalMasterThisRound: no() }
}

const unifiedProtectionConclusion = computed(() => [
  '本轮是否录入企业真实银行账号',
  '本轮是否录入供应商真实银行账号',
  '本轮是否显示真实完整银行账号',
  '本轮是否新增正式银行账户档案',
  '本轮是否新增正式供应商银行档案',
  '本轮是否新增查看完整账号按钮',
  '本轮是否新增编辑按钮',
  '本轮是否新增保存按钮',
  '本轮是否新增删除按钮',
  '本轮是否新增上传按钮',
  '本轮是否新增导入按钮',
  '本轮是否新增导出按钮',
  '本轮是否写正式账号查看审计日志',
  '本轮是否导入银行流水',
  '本轮是否生成银行流水',
  '本轮是否生成付款凭证',
  '本轮是否核销',
  '本轮是否写总账',
  '本轮是否过账',
].map((item) => ({ item, result: no() })))

const enterpriseReadonlySampleItems = [
  sampleItem('样例账户编号', 'EBA-SAMPLE-001'),
  sampleItem('账户名称', '企业付款专户样例'),
  sampleItem('开户主体', '样例制造公司'),
  sampleItem('脱敏银行账号', '6222 **** **** 1234'),
  sampleItem('完整银行账号', '不显示'),
  sampleItem('开户银行', '样例银行'),
  sampleItem('币种', 'CNY'),
  sampleItem('账户用途', '付款'),
  sampleItem('账户状态', '启用样例'),
  sampleItem('是否默认付款账户', '否'),
  sampleItem('单笔付款限额', '仅示意，不生效'),
  sampleItem('日累计付款限额', '仅示意，不生效'),
  sampleItem('银企直联状态', '未接入'),
  sampleItem('脱敏规则', '仅显示前 4 位和后 4 位，中间用星号隐藏'),
  sampleItem('审计提示', '本轮不写正式审计日志'),
]

const supplierReadonlySampleItems = [
  sampleItem('样例供应商银行档案编号', 'SBA-SAMPLE-001'),
  sampleItem('供应商编号', 'SUP-SAMPLE-001'),
  sampleItem('供应商名称', '样例供应商'),
  sampleItem('收款户名', '样例供应商收款户名'),
  sampleItem('脱敏收款账号', '6222 **** **** 5678'),
  sampleItem('完整收款账号', '不显示'),
  sampleItem('收款银行', '样例银行'),
  sampleItem('币种', 'CNY'),
  sampleItem('是否默认收款账户', '否'),
  sampleItem('账户状态', '启用样例'),
  sampleItem('复核状态', '已复核样例'),
  sampleItem('生效日期', '样例日期'),
  sampleItem('失效日期', '无'),
  sampleItem('脱敏规则', '仅显示前 4 位和后 4 位，中间用星号隐藏'),
  sampleItem('审计提示', '本轮不写正式审计日志'),
]

const maskingRuleItems = [
  ['默认列表显示脱敏账号', '默认只显示前 4 位和后 4 位。', '否，仅设计。', '否'],
  ['详情页默认展示脱敏账号', '详情页也不直接显示完整账号。', '否，仅设计。', '否'],
  ['完整账号默认不显示', '完整账号必须通过权限和审计后才允许查看。', '否，仅设计。', '否'],
  ['导出时默认导出脱敏账号', '导出完整账号必须单独审批。', '否，仅设计。', '否'],
  ['复制账号默认禁止', '复制完整账号必须被审计。', '否，仅设计。', '否'],
  ['打印页面默认脱敏', '打印或截图场景默认不能显示完整账号。', '否，仅设计。', '否'],
  ['日志中不得记录完整账号', '正式日志中不得明文记录完整银行账号。', '否，仅设计。', '否'],
  ['诊断数据中不得包含完整账号', '复制诊断数据只能包含脱敏账号或样例账号。', '否，仅设计。', '否'],
].map(([ruleName, description, executedThisRound, showFullAccountThisRound]) => ({
  ruleName,
  description,
  executedThisRound,
  showFullAccountThisRound,
}))

const fullAccountPermissionItems = [
  '谁可以申请查看完整账号',
  '谁可以审批查看完整账号',
  '谁可以临时查看完整账号',
  '谁可以查看企业完整银行账号',
  '谁可以查看供应商完整银行账号',
  '谁可以导出完整账号',
  '谁可以复制完整账号',
  '谁可以查看账号变更历史',
  '谁可以查看账号审计日志',
  '谁可以解除账号冻结',
].map((permissionItem) => ({
  permissionItem,
  description: '未来需要通过权限、审批和审计控制。',
  enabledThisRound: no(),
  allowViewFullAccountThisRound: no(),
}))

const fullAccountAuditRuleItems = [
  '查看人',
  '查看时间',
  '查看账号类型',
  '查看对象',
  '查看原因',
  '审批人',
  '审批时间',
  '查看方式',
  '是否导出',
  '是否复制',
  '是否截图提示',
  '是否超时关闭',
  '是否异常查看',
  '是否触发风险预警',
  '是否写入正式审计日志',
].map((auditItem) => ({
  auditItem,
  description: '未来完整账号查看必须记录该审计项。',
  writeFormalAuditLogThisRound: no(),
}))

const maskingRiskItems = [
  '完整账号泄露风险',
  '错误收款账号导致误付款风险',
  '供应商账号被篡改风险',
  '未复核账号用于付款风险',
  '离职人员查看账号风险',
  '导出文件泄露风险',
  '截图传播风险',
  '诊断数据包含敏感账号风险',
  '银企直联接口返回账号明文风险',
  '日志记录完整账号风险',
].map((riskName) => ({
  riskName,
  description: '未来正式流程必须通过脱敏、权限、审计和复核控制。',
  triggeredRealRiskThisRound: no(),
  handlingThisRound: '仅做风险提示，不处理真实风险。',
}))

const maintenanceFlowRelationItems = [
  '本轮只做只读样例和脱敏规则。',
  '下一阶段可以做企业银行账户档案维护流程设计。',
  '再下一阶段可以做供应商银行档案维护流程设计。',
  '维护流程完成后才能考虑正式银行流水导入。',
  '正式银行流水导入前必须有账号脱敏、权限、审计、复核和变更控制。',
  '没有银行账户档案，不允许正式付款。',
  '没有供应商银行档案，不允许正式付款。',
  '没有账号审计，不允许查看完整账号。',
]

const enterpriseBankAccountDesignItems = [
  designItem('企业银行账户档案编号', '系统内部档案编号。', '是', '系统生成'),
  designItem('账户名称', '企业内部账户名称，例如基本户、一般户、付款专户。', '是', '人工维护'),
  designItem('开户主体', '企业法人主体或分支机构。', '是', '企业组织档案'),
  designItem('银行账号', '企业银行账号。', '是', '银行开户资料'),
  designItem('开户银行', '开户银行名称。', '是', '银行开户资料'),
  designItem('开户行联行号', '银行联行号。', '建议必填', '银行资料'),
  designItem('币种', '账户币种。', '是', '银行开户资料'),
  designItem('账户用途', '付款、收款、工资、税费、保证金、备用金等。', '是', '财务配置'),
  designItem('账户状态', '草稿、启用、停用、冻结、注销。', '是', '账户维护流程'),
  designItem('是否默认付款账户', '付款时默认带出的企业账户。', '否', '财务配置'),
  designItem('付款权限范围', '哪些组织、岗位、用户可以使用该账户付款。', '是', '权限配置'),
  designItem('单笔付款限额', '单笔付款金额上限。', '建议必填', '财务控制策略'),
  designItem('日累计付款限额', '每日累计付款金额上限。', '建议必填', '财务控制策略'),
  designItem('银企直联状态', '未接入、测试中、已接入、停用。', '是', '接口配置'),
  designItem('审计状态', '未审计、已审计、变更待复核。', '是', '审计流程'),
]

const supplierBankAccountDesignItems = [
  designItem('供应商银行档案编号', '系统内部档案编号。', '是', '系统生成'),
  designItem('供应商编号', '供应商主数据编号。', '是', '供应商档案'),
  designItem('供应商名称', '供应商名称。', '是', '供应商档案'),
  designItem('收款户名', '银行账户户名。', '是', '供应商提供资料'),
  designItem('收款账号', '供应商收款银行账号。', '是', '供应商提供资料'),
  designItem('收款银行', '供应商开户银行。', '是', '供应商提供资料'),
  designItem('开户行联行号', '收款银行联行号。', '建议必填', '供应商提供资料'),
  designItem('币种', '账户币种。', '是', '供应商资料'),
  designItem('是否默认收款账户', '该供应商默认收款账户。', '否', '供应商银行档案维护'),
  designItem('账户状态', '草稿、待复核、启用、停用、冻结、失效。', '是', '供应商银行档案流程'),
  designItem('复核状态', '未复核、已复核、变更待复核。', '是', '供应商银行档案复核流程'),
  designItem('生效日期', '账户生效日期。', '建议必填', '供应商资料'),
  designItem('失效日期', '账户失效日期。', '否', '供应商资料'),
  designItem('变更原因', '银行账户变更原因。', '变更时必填', '供应商资料或人工维护'),
  designItem('审计状态', '未审计、已审计、变更待复核。', '是', '审计流程'),
]

const accountStatusRuleItems = [
  ['企业银行账户', '草稿', '账户尚未启用，未来不能用于付款或流水匹配。'],
  ['企业银行账户', '启用', '账户可作为未来付款账户候选。'],
  ['企业银行账户', '停用', '账户不能用于付款或流水匹配。'],
  ['企业银行账户', '冻结', '账户被冻结，不能用于付款或流水匹配。'],
  ['企业银行账户', '注销', '账户已注销，不能用于付款或流水匹配。'],
  ['供应商银行账户', '草稿', '账户尚未提交复核。'],
  ['供应商银行账户', '待复核', '账户等待复核，不能直接付款。'],
  ['供应商银行账户', '启用', '账户已启用，未来可作为收款账户候选。'],
  ['供应商银行账户', '停用', '账户不能用于付款。'],
  ['供应商银行账户', '冻结', '账户被冻结，不能用于付款。'],
  ['供应商银行账户', '失效', '账户已失效，不能用于付款。'],
  ['供应商银行账户', '变更待复核', '账户变更后等待复核，不能直接付款。'],
].map(([accountType, statusName, description]) => ({
  accountType,
  statusName,
  description,
  createdOrChangedThisRound: no(),
}))

const validationRuleItems = [
  ['企业银行账户', '企业付款账户是否存在', '确认付款账户档案已建立。'],
  ['企业银行账户', '企业付款账户是否启用', '确认账户可用于付款。'],
  ['企业银行账户', '企业付款账户是否冻结', '冻结账户不得付款。'],
  ['企业银行账户', '企业付款账户币种是否匹配', '避免币种不一致导致付款失败。'],
  ['企业银行账户', '企业付款账户是否有付款权限', '确认当前组织或岗位允许使用账户。'],
  ['企业银行账户', '单笔付款是否超过限额', '控制单笔付款风险。'],
  ['企业银行账户', '日累计付款是否超过限额', '控制日累计付款风险。'],
  ['企业银行账户', '银企直联状态是否允许付款', '确认接口状态可用。'],
  ['企业银行账户', '是否已审计', '确认账户信息已审计。'],
  ['企业银行账户', '是否存在重复银行账号', '避免账户重复维护。'],
  ['供应商银行账户', '供应商收款账户是否存在', '确认供应商收款账户档案已建立。'],
  ['供应商银行账户', '供应商收款账户是否启用', '确认账户可收款。'],
  ['供应商银行账户', '供应商收款账户是否已复核', '未复核账户不得付款。'],
  ['供应商银行账户', '供应商收款账户是否冻结', '冻结账户不得付款。'],
  ['供应商银行账户', '供应商收款账户是否失效', '失效账户不得付款。'],
  ['供应商银行账户', '收款户名是否与供应商一致', '避免收款方错误。'],
  ['供应商银行账户', '收款账号是否重复', '避免供应商账户重复维护。'],
  ['供应商银行账户', '币种是否匹配', '避免付款币种错误。'],
  ['供应商银行账户', '生效日期是否有效', '确认账户处于有效期。'],
  ['供应商银行账户', '是否存在变更待复核', '变更未复核账户不得付款。'],
].map(([ruleScope, ruleName, purpose]) => ({
  ruleScope,
  ruleName,
  purpose,
  executedThisRound: no(),
}))

const permissionAuditRuleItems = [
  ['权限', '谁可以新增企业银行账户', '未来必须控制新增权限。'],
  ['权限', '谁可以编辑企业银行账户', '未来必须控制编辑权限。'],
  ['权限', '谁可以停用企业银行账户', '未来必须控制停用权限。'],
  ['权限', '谁可以新增供应商银行账户', '未来必须控制供应商账户新增权限。'],
  ['权限', '谁可以编辑供应商银行账户', '未来必须控制供应商账户编辑权限。'],
  ['权限', '谁可以复核供应商银行账户', '未来必须控制复核权限。'],
  ['权限', '谁可以查看脱敏银行账号', '未来默认展示脱敏账号。'],
  ['权限', '谁可以查看完整银行账号', '未来完整账号查看必须受控。'],
  ['权限', '谁可以导出银行账户档案', '未来导出必须审批或审计。'],
  ['权限', '谁可以在付款时选择账户', '未来付款账户选择必须受控。'],
  ['权限', '谁可以维护付款限额', '未来付款限额维护必须受控。'],
  ['权限', '谁可以接入银企直联', '未来接口接入必须受控。'],
  ['审计', '新增银行账户', '未来必须记录新增动作。'],
  ['审计', '编辑银行账户', '未来必须记录编辑动作。'],
  ['审计', '停用银行账户', '未来必须记录停用动作。'],
  ['审计', '启用银行账户', '未来必须记录启用动作。'],
  ['审计', '冻结银行账户', '未来必须记录冻结动作。'],
  ['审计', '修改默认账户', '未来必须记录默认账户变更。'],
  ['审计', '修改付款限额', '未来必须记录限额变更。'],
  ['审计', '查看完整账号', '未来必须记录完整账号查看。'],
  ['审计', '导出银行账户', '未来必须记录导出动作。'],
  ['审计', '复核供应商银行账户', '未来必须记录复核动作。'],
].map(([ruleType, ruleName, description]) => ({
  ruleType,
  ruleName,
  description,
  executedThisRound: no(),
  writeFormalAuditLogThisRound: no(),
}))

const bankFlowPreviewRelationItems = [
  '企业银行账户档案用于校验银行流水中的企业付款账户。',
  '供应商银行档案用于校验银行流水中的收款方账户。',
  '如果企业银行账户档案缺失，银行流水导入校验页只能提示来源缺失。',
  '如果供应商银行档案缺失，银行流水导入校验页只能提示来源缺失。',
  '只有两个档案都建立、启用、复核后，未来才可以进入正式银行流水导入校验。',
  '本轮仍不读取银行流水文件。',
  '本轮仍不进入待匹配。',
  '本轮仍不核销。',
  '本轮仍不写总账。',
]

const currentGapItems = [
  '企业银行账户档案尚未建立。',
  '供应商银行档案尚未建立。',
  '企业付款账户不能正式校验。',
  '供应商收款账户不能正式校验。',
  '银企直联状态不能判断。',
  '银行账号权限与脱敏规则未设计为正式流程。',
  '银行账户变更复核流程未设计为正式流程。',
  '银行账户审计日志未设计为正式流程。',
]

const recommendedNextStepItems = [
  '下一阶段可以做企业银行账户档案维护流程设计。',
  '再下一阶段可以做供应商银行档案维护流程设计。',
  '维护流程完成后再考虑正式银行流水导入。',
  '正式银行流水导入前必须有账号脱敏、权限、审计、复核和变更控制。',
]

const protectionFlags = computed(() => ({
  inputEnterpriseRealBankAccount: false,
  inputSupplierRealBankAccount: false,
  showRealFullBankAccount: false,
  createFormalBankAccountMaster: false,
  createFormalSupplierBankMaster: false,
  addViewFullAccountButton: false,
  addEditButton: false,
  addSaveButton: false,
  addDeleteButton: false,
  addUploadControl: false,
  uploadFile: false,
  readExcel: false,
  readCsv: false,
  importBankFlow: false,
  generateBankFlow: false,
  executeBankFlowMatch: false,
  linkPaymentExecutionPrepare: false,
  generatePaymentVoucher: false,
  writeOffPayment: false,
  writeLedger: false,
  postLedger: false,
}))

const bankAccountMaskingDesignSummary = computed(() => ({
  page: 'BankAccountMasterDesignPage',
  version: 'V1.13.51',
  enterpriseReadonlySampleItems,
  supplierReadonlySampleItems,
  maskingRuleItems,
  fullAccountPermissionItems,
  fullAccountAuditRuleItems,
  maskingRiskItems,
  maintenanceFlowRelationItems,
  unifiedProtectionConclusion: unifiedProtectionConclusion.value,
  protectionFlags: protectionFlags.value,
  timestamp: new Date().toISOString(),
}))

const bankAccountMasterDesignSummary = computed(() => ({
  page: 'BankAccountMasterDesignPage',
  version: 'V1.13.51',
  enterpriseBankAccountDesignItems,
  supplierBankAccountDesignItems,
  accountStatusRuleItems,
  validationRuleItems,
  permissionAuditRuleItems,
  bankFlowPreviewRelationItems,
  currentGapItems,
  recommendedNextStepItems,
  unifiedProtectionConclusion: unifiedProtectionConclusion.value,
  protectionFlags: protectionFlags.value,
  timestamp: new Date().toISOString(),
}))

const diagnosticData = computed(() => ({
  page: 'BankAccountMasterDesignPage',
  version: 'V1.13.51',
  bankAccountMaskingDesignSummary: bankAccountMaskingDesignSummary.value,
  bankAccountMasterDesignSummary: bankAccountMasterDesignSummary.value,
  diagnosticChineseSummary: {
    页面名称: '银行账户档案前置设计',
    页面版本: 'V1.13.51',
    本轮是否录入企业真实银行账号: no(),
    本轮是否录入供应商真实银行账号: no(),
    本轮是否显示真实完整银行账号: no(),
    本轮是否新增正式银行账户档案: no(),
    本轮是否新增正式供应商银行档案: no(),
    本轮是否新增查看完整账号按钮: no(),
    本轮是否新增编辑按钮: no(),
    本轮是否新增保存按钮: no(),
    本轮是否新增删除按钮: no(),
    本轮是否上传文件: no(),
    本轮是否读取Excel: no(),
    本轮是否读取CSV: no(),
    本轮是否导入银行流水: no(),
    本轮是否生成银行流水: no(),
    本轮是否生成付款凭证: no(),
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
.bank-account-master-design-page {
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
.table-card {
  padding: 16px;
  border: 1px solid var(--app-border, #d8dee8);
  border-radius: 8px;
  background: #fff;
  overflow-x: auto;
}

.highlight-card {
  border-color: #9bb6f0;
  background: #f8fbff;
}

.protection-grid,
.sample-summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}

.protection-grid article,
.sample-summary-grid article {
  display: grid;
  gap: 5px;
  padding: 10px 12px;
  border: 1px solid #d8dee8;
  border-radius: 8px;
  background: #f8fafc;
}

.protection-grid strong {
  color: #b42318;
}

.sample-summary-grid strong {
  font-size: 18px;
}

.sample-summary-grid small {
  color: #667085;
}

.table-title {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
}

.helper-text {
  margin: 4px 0 0;
  color: #667085;
  line-height: 1.7;
}

.status-note {
  margin-top: 12px;
}

.relation-list {
  margin: 0;
  padding-left: 20px;
  line-height: 1.9;
}

.two-column-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 14px;
}

.two-column-list article {
  padding: 12px;
  border: 1px solid #d8dee8;
  border-radius: 8px;
  background: #f8fafc;
}

.two-column-list h3 {
  margin: 0 0 8px;
}

.two-column-list ul {
  margin: 0;
  padding-left: 18px;
  line-height: 1.8;
}
</style>

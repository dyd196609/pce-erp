<template>
  <section class="purchase-order-operation-guide"
    data-acceptance-id="purchase-order-operation-guide"
    data-version="V1.14.2.8.4.27.2.1">
    <el-card shadow="never">
      <template #header>
        <div class="guide-heading">
          <div>
            <h2>采购订单操作流程说明</h2>
            <span>采购人员按以下顺序完成人工核对；页面进入和查看不会推进采购订单状态。</span>
          </div>
          <el-tag type="info">人工操作指引</el-tag>
        </div>
      </template>
      <p class="flow-summary">
        采购申请 → 询价 → 报价比较 → 核价 → 供应商推荐 → Gate → 采购订单 → 审批 → 下达
      </p>
      <ol class="guide-steps">
        <li>
          <strong>步骤1：采购需求准备</strong>
          <span>来源：采购申请 → 询价 → 报价比较 → 核价 → 供应商推荐 → Gate准入。</span>
        </li>
        <li><strong>步骤2：创建采购订单草稿</strong><span>操作：新增采购订单。</span></li>
        <li>
          <strong>步骤3：人工确认采购信息</strong>
          <span>确认：供应商、物料、数量、价格、交期、备注。</span>
        </li>
        <li><strong>步骤4：创建正式采购订单</strong><span>仅由受保护的显式人工动作创建。</span></li>
        <li><strong>步骤5：提交审批</strong><span>草稿确认完成后进入审批承接。</span></li>
        <li><strong>步骤6：审批通过后下达供应商</strong><span>审批通过不等于已经下达。</span></li>
      </ol>
    </el-card>
  </section>
</template>

<style scoped>
.purchase-order-operation-guide { width: 100%; max-width: 100%; min-width: 0; }
.guide-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.guide-heading h2 { margin: 0 0 4px; }
.guide-heading span { color: #64748b; }
.flow-summary { margin: 0 0 16px; padding: 14px; border-radius: 8px; background: #eff6ff; color: #1e3a8a; font-weight: 700; }
.guide-steps { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 0; padding: 0; list-style: none; }
.guide-steps li { display: grid; gap: 7px; padding: 14px; border: 1px solid #dbe4ee; border-radius: 9px; background: #fff; }
.guide-steps span { color: #475569; line-height: 1.6; }
@media (max-width: 900px) { .guide-steps { grid-template-columns: 1fr; } .guide-heading { align-items: flex-start; flex-direction: column; } }
</style>

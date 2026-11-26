<template>
  <main class="purchase-reconciliation-page">
    <section class="page-heading">
      <div v-if="!embeddedInCommonShell">
        <p class="eyebrow">{{ VERSION }} · SCM</p>
        <h1>{{ productionPersistenceMode ? '采购对账生产持久化能力验收' : controlledGenerationMode ? '采购对账正式生成受控执行' : transactionDesignMode ? '采购对账正式生成事务设计' : finalReviewMode ? '采购对账最终评审' : simulationMode ? '采购对账模拟生成状态机' : preGenerationMode ? '采购对账生成前设计' : '采购对账' }}</h1>
        <p class="page-note">
          本页是独立的采购对账只读入口，用于从供应商结算查看采购订单、应付核对、结算金额和差异状态的来源关系。
          当前不新建对账对象、不修改供应商结算、不付款、不写总账、不核销、不生成银行流水。
        </p>
      </div>
      <el-button plain @click="copyDiagnostics">复制诊断数据</el-button>
    </section>

    <section v-if="productionPersistenceMode" class="table-card pre-generation-design" data-acceptance-id="purchase-reconciliation-production-persistence-readiness">
      <section class="design-panel" data-acceptance-id="persistence-overview"><h3>生产持久化能力总览</h3><span>原子事务：是</span><span>幂等唯一约束：是</span><span>来源唯一约束：是</span><span>编号唯一约束：是</span><span>持久来源锁：是</span><span>提交结果恢复：是</span><span>审计原子性：是</span><span>服务端授权：是</span><span>生产灰度开关：关闭</span></section>
      <section class="design-panel" data-acceptance-id="persistence-business-gate"><h3>服务端业务动作门禁</h3><span>最终评审：review_passed / approved</span><span>来源新鲜度：有效</span><span>模拟完整性：有效</span><span>主体一致性：是</span><span>金额和币种：一致</span><span>当前目标数量：0</span><span>致命风险：0</span><span>门禁结论：通过</span></section>
      <section class="design-panel" data-acceptance-id="persistence-transaction-gate"><h3>服务端事务能力门禁</h3><span>数据库类型：SQLite 隔离测试库</span><span>事务模式：Django atomic</span><span>唯一约束：数据库硬约束</span><span>锁模式：数据库持久锁</span><span>编号服务：服务端受控编号</span><span>审计事务：同事务</span><span>恢复接口：已启用</span><span>服务端授权：已启用</span><span>门禁结论：通过</span></section>
      <section class="design-panel" data-acceptance-id="persistence-result"><h3>正式采购对账持久化结果</h3><span>测试租户：{{ productionReadiness.tenantId }}</span><span>正式对象标识：{{ productionReadiness.targetId }}</span><span>采购对账编号：{{ productionReadiness.reconciliationNo }}</span><span>状态：draft</span><span>供应商：SUP-41</span><span>数量：10.0000</span><span>金额：100.00 CNY</span><span>来源供应商结算：PCE-REG-concurrent</span><span>来源应付核对：PAYABLE-concurrent</span><span>幂等键：idem-concurrent</span><span>事务标识：{{ productionReadiness.transactionId }}</span></section>
      <section class="design-panel" data-acceptance-id="persistence-constraints"><h3>硬唯一约束验证</h3><span>幂等唯一约束：通过</span><span>来源唯一约束：通过</span><span>编号唯一约束：通过</span><span>数据库错误编码：IntegrityError</span><span>冲突返回结果：blocked</span><span>重复对象数量：0</span></section>
      <section class="design-panel" data-acceptance-id="persistence-authorization"><h3>服务端授权与灰度边界</h3><span>认证状态：已认证</span><span>权限编码：reconciliation.generate_purchase_reconciliation</span><span>组织范围：company_id=41</span><span>测试租户白名单：tenant-v41</span><span>服务端 Feature Flag：开启</span><span>用户正式租户开关：关闭</span><span>越权调用结果：PRC_AUTH_SCOPE_DENIED</span></section>
      <section class="design-panel" data-acceptance-id="persistence-failure-recovery"><h3>事务、回滚与提交恢复</h3><span>事务状态：{{ productionReadiness.transactionState }}</span><span>失败步骤：15</span><span>数据库回滚：完整</span><span>提交结果：committed</span><span>恢复分类：committed</span><span>目标残留：0</span><span>关系残留：0</span><span>审计残留：0</span><span>是否允许重试：仅明确未提交</span></section>
      <section class="design-panel" data-acceptance-id="persistence-canaries"><h3>金丝雀群与并发结果</h3><span>批次编号：{{ productionReadiness.canaryBatchId }}</span><span>场景总数：23</span><span>并发请求数：2</span><span>成功创建数：1</span><span>幂等复用数：1</span><span>唯一约束阻断数：3</span><span>失败场景数：15</span><span>恢复场景数：2</span></section>
      <section class="design-panel" data-acceptance-id="persistence-protection"><h3>生产灰度与下游保护</h3><span>测试数据库对象数量：1</span><span>用户正式租户对象数量：0</span><span>生产灰度开关：关闭</span><span>付款对象数量：0</span><span>付款凭证数量：0</span><span>核销记录数量：0</span><span>总账记录数量：0</span><span>过账记录数量：0</span><span>银行流水数量：0</span><span>用户 localStorage 业务写入：0</span><span>生产正式租户网络写入：0</span></section>
      <div class="row-actions" data-acceptance-id="persistence-readonly-actions"><el-button plain @click="viewFinalReview">查看最终评审</el-button><el-button plain @click="goSourceSupplierSettlement">查看来源供应商结算</el-button><el-button plain @click="reloadProductionPersistence">重新读取服务端结果</el-button><el-button plain @click="returnPurchaseReconciliation">返回采购对账</el-button></div>
    </section>

    <section v-else-if="controlledGenerationMode" class="table-card pre-generation-design" data-acceptance-id="purchase-reconciliation-controlled-generation">
      <section class="design-panel" data-acceptance-id="controlled-dual-gate-overview">
        <h3>双门禁总览</h3>
        <span>当前环境：金丝雀隔离环境</span><span>用户正式业务环境：未执行</span><span>正式生产开关：关闭</span>
        <span>业务动作门禁：{{ controlledResult.businessGateResult?.passed ? '通过' : '阻断' }}</span>
        <span>事务能力门禁：{{ controlledResult.transactionGateResult?.passed ? '通过' : '阻断' }}</span>
        <span>可信执行上下文：{{ controlledResult.authorizationResult?.trustedExecutionContext ? '是' : '否' }}</span>
        <span>运行时开关：{{ controlledResult.authorizationResult?.runtimeSwitchEnabled ? '隔离金丝雀已开启' : '关闭' }}</span>
        <span>用户明确动作：{{ controlledResult.authorizationResult?.explicitUserAction ? '是' : '否' }}</span>
        <span>最终授权结果：{{ controlledResult.authorizationResult?.allowed ? '仅允许金丝雀受控执行' : '阻断' }}</span>
        <span>阻断编码：{{ controlledResult.denialCodes?.join('、') || '-' }}</span>
      </section>
      <section class="design-panel" data-acceptance-id="controlled-business-gate">
        <h3>业务动作门禁</h3>
        <span>最终评审状态：{{ controlledResult.businessGateResult?.reviewState || '-' }}</span><span>最终评审决策：{{ controlledResult.businessGateResult?.reviewDecision || '-' }}</span>
        <span>来源新鲜度：{{ controlledResult.businessGateResult?.sourceFreshnessValid ? '有效' : '无效' }}</span><span>模拟完整性：{{ controlledResult.businessGateResult?.simulationIntegrityValid ? '有效' : '无效' }}</span>
        <span>审计证据：{{ controlledResult.businessGateResult?.auditEvidenceComplete ? '完整' : '不完整' }}</span><span>目标数量：{{ controlledResult.businessGateResult?.targetCount ?? 0 }}</span>
        <span>致命风险：{{ controlledResult.businessGateResult?.fatalRiskCount ?? 0 }}</span><span>门禁哈希：{{ controlledResult.businessGateResult?.gateHash || '-' }}</span>
      </section>
      <section class="design-panel" data-acceptance-id="controlled-transaction-gate">
        <h3>事务执行门禁</h3>
        <span>持久化适配器：{{ controlledResult.transactionGateResult?.persistenceAdapterType || '-' }}</span><span>原子事务能力：{{ controlledResult.transactionGateResult?.atomicTransactionSupported ? '是' : '否' }}</span>
        <span>幂等唯一约束：{{ controlledResult.transactionGateResult?.idempotencyConstraintSupported ? '是' : '否' }}</span><span>来源唯一约束：{{ controlledResult.transactionGateResult?.sourceUniqueConstraintSupported ? '是' : '否' }}</span>
        <span>编号唯一约束：{{ controlledResult.transactionGateResult?.documentNumberUniqueConstraintSupported ? '是' : '否' }}</span><span>来源锁：{{ controlledResult.transactionGateResult?.sourceLockSupported ? '是' : '否' }}</span>
        <span>提交恢复：{{ controlledResult.transactionGateResult?.commitRecoverySupported ? '是' : '否' }}</span><span>审计原子性：{{ controlledResult.transactionGateResult?.auditAtomicitySupported ? '是' : '否' }}</span>
        <span>服务端授权：{{ controlledResult.transactionGateResult?.serverAuthorizationSupported ? '是' : '否' }}</span><span>门禁结论：{{ controlledResult.transactionGateResult?.passed ? '通过（金丝雀）' : '阻断' }}</span>
        <span>生产适配器能力：不满足；productionTransactionCapabilityGate=false</span>
      </section>
      <section class="design-panel" data-acceptance-id="controlled-command">
        <h3>正式生成命令</h3>
        <span>命令标识：{{ controlledResult.commandId || '-' }}</span><span>来源唯一键：{{ controlledObject?.sourceKey || '-' }}</span>
        <span>幂等键：{{ controlledResult.idempotencyKey || '-' }}</span><span>事务锁键：{{ controlledScenario?.transactionLockKey || '-' }}</span>
        <span>评审标识：{{ controlledScenario?.reviewId || '-' }}</span><span>正式执行模式：金丝雀隔离受控</span><span>正式生产权限：关闭</span>
      </section>
      <section class="design-panel" data-acceptance-id="controlled-formal-object">
        <h3>采购对账正式结构对象</h3>
        <span>隔离对象标识：{{ controlledObject?.id || '-' }}</span><span>隔离采购对账编号：{{ controlledObject?.reconciliationNo || '-' }}</span>
        <span>对象状态：{{ controlledObject?.status || '-' }} / 草稿</span><span>供应商：{{ controlledObject?.supplierName || '-' }}</span>
        <span>数量：{{ controlledObject?.quantity ?? '-' }}</span><span>金额：{{ controlledObject?.settlementAmount ?? '-' }}</span><span>币种：{{ controlledObject?.currency || '-' }}</span>
        <span>来源供应商结算：{{ controlledObject?.sourceSupplierSettlementNo || '-' }}</span><span>正式生产对象是否存在：否</span>
      </section>
      <section class="design-panel" data-acceptance-id="controlled-result">
        <h3>受控执行结果</h3>
        <span>执行状态：{{ controlledResult.transactionState || '-' }}</span><span>执行结果：{{ controlledResult.outcome || '-' }}</span>
        <span>动作前对象数量：{{ controlledResult.formalEquivalentObjectCountBefore ?? 0 }}</span><span>动作后对象数量：{{ controlledResult.formalEquivalentObjectCountAfter ?? 0 }}</span>
        <span>幂等重试后数量：{{ controlledScenario?.retryResult?.formalEquivalentObjectCountAfterRetry ?? controlledResult.formalEquivalentObjectCountAfterRetry ?? 0 }}</span>
        <span>是否提交：{{ controlledResult.commitStatus === 'committed' ? '是' : '否' }}</span><span>是否回滚：{{ controlledResult.commitStatus === 'rolled_back' ? '是' : '否' }}</span>
        <span>是否需要恢复：{{ controlledResult.requiresRecovery ? '是' : '否' }}</span><span>是否需要人工处理：{{ controlledResult.requiresManualIntervention ? '是' : '否' }}</span><span>结果哈希：{{ controlledResult.executionHash || '-' }}</span>
      </section>
      <section class="design-panel" data-acceptance-id="controlled-number-idempotency">
        <h3>编号、幂等与并发结果</h3>
        <span>编号预留状态：{{ controlledResult.numberReservationStatus || '-' }}</span><span>编号消费状态：{{ controlledResult.numberReservationStatus || '-' }}</span><span>失败编号是否可复用：否</span>
        <span>幂等状态：{{ controlledResult.idempotencyStatus || '-' }}</span><span>来源锁状态：{{ controlledResult.lockAcquireCount ? '已获取' : '未获取' }}</span>
        <span>并发请求结果：{{ controlledScenario?.retryResult?.outcome || '-' }}</span><span>重复对象数量：0</span>
      </section>
      <section class="design-panel" data-acceptance-id="controlled-relations-audit">
        <h3>来源关系与审计结果</h3>
        <span>来源—目标关系：{{ controlledCounts.sourceTargetRelations }}</span><span>来源反向关系：{{ controlledCounts.sourceBackReferences }}</span>
        <span>供应商结算生命周期状态：reconciling → reconciling</span><span>审计记录：{{ controlledCounts.auditRecords }}</span>
        <span>评审引用：{{ controlledScenario?.reviewId || '-' }}</span><span>事务引用：{{ controlledScenario?.transactionPlanId || '-' }}</span>
      </section>
      <section class="design-panel" data-acceptance-id="controlled-recovery">
        <h3>回滚与提交结果恢复</h3>
        <span>失败步骤：{{ controlledResult.failedStepCode || '-' }}</span><span>回滚状态：{{ controlledResult.commitStatus || '-' }}</span>
        <span>补偿步骤：{{ controlledResult.compensationResults?.map(item => item.compensationCode).join('、') || '-' }}</span>
        <span>残留数量：{{ (controlledResult.residualObjectCount || 0) + (controlledResult.residualRelationCount || 0) + (controlledResult.residualAuditCount || 0) }}</span>
        <span>恢复分类：{{ controlledScenario?.recoveryResult?.classification || controlledResult.recoveryStatus || '-' }}</span><span>是否允许安全重试：{{ controlledResult.safeToRetry ? '是' : '否' }}</span><span>是否需要人工处理：{{ controlledResult.requiresManualIntervention ? '是' : '否' }}</span>
      </section>
      <section class="design-panel" data-acceptance-id="controlled-protection">
        <h3>正式业务保护与下游零对象</h3>
        <span>金丝雀正式结构对象数量：{{ controlledCounts.formalObjects }}</span><span>用户正式采购对账对象数量：0</span><span>正式编号分配次数：0</span>
        <span>供应商结算生命周期修改次数：0</span><span>付款对象数量：0</span><span>付款凭证数量：0</span><span>核销记录数量：0</span><span>总账记录数量：0</span><span>过账记录数量：0</span><span>银行流水数量：0</span>
        <span>用户localStorage业务写入次数：0</span><span>生产网络写请求次数：0</span>
      </section>
      <div class="row-actions" data-acceptance-id="controlled-actions"><el-button plain @click="viewFinalReview">查看最终评审</el-button><el-button plain @click="goSourceSupplierSettlement">查看来源供应商结算</el-button><el-button plain @click="reloadControlledArtifact">重新读取执行结果</el-button><el-button plain @click="returnPurchaseReconciliation">返回采购对账</el-button></div>
    </section>

    <section v-else-if="transactionDesignMode" class="table-card pre-generation-design" data-acceptance-id="purchase-reconciliation-transaction-design">
      <section class="design-panel" data-acceptance-id="purchase-reconciliation-transaction-command">
        <h3>正式生成命令上下文</h3>
        <span>来源供应商结算编号：{{ transactionResult.command.sourceSupplierSettlementNo || '-' }}</span>
        <span>候选对象标识：{{ transactionResult.command.sourceCandidateId || '-' }}</span>
        <span>最终评审标识：{{ transactionResult.command.reviewId || '-' }}</span>
        <span>最终评审状态：{{ transactionScenario?.review?.reviewState || '-' }}</span>
        <span>最终评审决策：{{ transactionScenario?.review?.reviewDecision || '-' }}</span>
        <span>命令标识：{{ transactionResult.command.commandId || '-' }}</span>
        <span>正式执行权限：否</span>
      </section>

      <section class="design-panel" data-acceptance-id="purchase-reconciliation-transaction-plan">
        <h3>事务计划</h3>
        <span>事务计划标识：{{ transactionResult.transactionPlan.transactionPlanId || '-' }}</span>
        <span>事务策略版本：{{ transactionResult.transactionPlan.transactionPolicyVersion || '-' }}</span>
        <span>来源唯一键：{{ transactionResult.command.sourceKey || '-' }}</span>
        <span>幂等键：{{ transactionResult.command.idempotencyKey || '-' }}</span>
        <span>事务锁键：{{ transactionResult.command.transactionLockKey || '-' }}</span>
        <span>预期来源哈希：{{ transactionResult.command.expectedSourceSnapshotHash || '-' }}</span>
        <span>预期目标数量：{{ transactionResult.command.expectedTargetCount }}</span>
        <span>步骤数量：{{ transactionResult.transactionPlan.transactionSteps.length }}</span>
        <span>补偿步骤数量：{{ transactionResult.transactionPlan.compensationSteps.length }}</span>
      </section>

      <section class="design-panel" data-acceptance-id="purchase-reconciliation-transaction-numbering">
        <h3>正式编号策略</h3>
        <span>单据类型：{{ transactionNumberPlan.numberScope.documentType || '-' }}</span>
        <span>编号策略版本：{{ transactionNumberPlan.numberPolicyVersion || '-' }}</span>
        <span>编号作用域：{{ transactionNumberScope }}</span>
        <span>编号预留键：{{ transactionNumberPlan.numberReservationKey || '-' }}</span>
        <span>隔离模拟编号：{{ transactionResult.simulatedFormalTargetNo || transactionNumberPlan.simulatedReservationResult || '-' }}</span>
        <span>正式编号是否分配：否</span>
        <span>失败编号是否可复用：否</span>
      </section>

      <section class="design-panel" data-acceptance-id="purchase-reconciliation-transaction-idempotency">
        <h3>幂等与并发控制</h3>
        <span>幂等键：{{ transactionResult.command.idempotencyKey || '-' }}</span>
        <span>幂等状态：{{ transactionResult.idempotencyStatus }}</span>
        <span>来源锁键：{{ transactionResult.command.transactionLockKey || '-' }}</span>
        <span>锁状态：{{ transactionResult.lockStatus }}</span>
        <span>相同请求处理方式：复用同一事务身份和隔离编号预留</span>
        <span>相同来源不同请求处理方式：锁内重新检查目标并阻断第二事务</span>
        <span>目标唯一约束：sourceKey 唯一目标</span>
      </section>

      <section class="design-panel design-table" data-acceptance-id="purchase-reconciliation-transaction-steps">
        <h3>事务执行步骤</h3>
        <el-table :data="transactionResult.executedSteps" border size="small">
          <el-table-column prop="sequence" label="顺序" width="80" />
          <el-table-column prop="stepCode" label="步骤编码" min-width="280" />
          <el-table-column prop="phase" label="阶段" width="120" />
          <el-table-column prop="status" label="执行状态" width="130" />
          <el-table-column prop="inputHash" label="输入哈希" min-width="130" />
          <el-table-column prop="outputHash" label="输出哈希" min-width="130" />
          <el-table-column prop="failureCode" label="失败编码" min-width="260" />
          <el-table-column prop="formalWriteCount" label="正式写入数量" width="130" />
        </el-table>
      </section>

      <section class="design-panel design-table" data-acceptance-id="purchase-reconciliation-transaction-rollback">
        <h3>失败回滚与补偿计划</h3>
        <span v-if="transactionResult.compensationResults.length === 0">无需执行补偿</span>
        <el-table v-else :data="transactionResult.compensationResults" border size="small">
          <el-table-column prop="originalStepCode" label="原失败或已完成步骤" min-width="280" />
          <el-table-column prop="compensationCode" label="补偿步骤" min-width="300" />
          <el-table-column prop="sequence" label="补偿顺序" width="100" />
          <el-table-column prop="status" label="补偿状态" width="150" />
          <el-table-column prop="residualCount" label="残留数量" width="110" />
        </el-table>
        <span>是否需要人工处理：{{ transactionResult.requiresManualIntervention ? '是' : '否' }}</span>
      </section>

      <section class="design-panel" data-acceptance-id="purchase-reconciliation-transaction-result">
        <h3>隔离事务结果</h3>
        <span>事务状态：{{ transactionResult.transactionState }}</span>
        <span>事务结果：{{ transactionResult.outcome }}</span>
        <span>是否提交：{{ transactionResult.committed ? '是' : '否' }}</span>
        <span>是否回滚：{{ transactionResult.rolledBack ? '是' : '否' }}</span>
        <span>是否提交结果不确定：{{ transactionResult.commitUnknown ? '是' : '否' }}</span>
        <span>是否需要恢复：{{ transactionResult.requiresRecovery ? '是' : '否' }}</span>
        <span>是否需要人工处理：{{ transactionResult.requiresManualIntervention ? '是' : '否' }}</span>
        <span>事务结果哈希：{{ transactionResult.transactionResultHash || '-' }}</span>
      </section>

      <section class="design-panel" data-acceptance-id="purchase-reconciliation-transaction-recovery">
        <h3>提交结果恢复</h3>
        <span>恢复分类：{{ transactionRecovery.classification }}</span>
        <span>幂等记录状态：{{ transactionResult.idempotencyStatus }}</span>
        <span>目标存在状态：{{ transactionResult.existingTargetNos.length ? 'existing' : 'not_found' }}</span>
        <span>目标编号：{{ transactionResult.existingTargetNos.join('、') || transactionResult.simulatedFormalTargetNo || '-' }}</span>
        <span>编号预留状态：{{ transactionResult.numberReservationStatus }}</span>
        <span>来源关系状态：{{ transactionRecovery.sourceTargetRelationStatus || '隔离证据' }}</span>
        <span>审计状态：{{ transactionRecovery.auditStatus || '隔离证据' }}</span>
        <span>是否允许安全重试：{{ transactionRecovery.safeToRetry ? '是' : '否' }}</span>
      </section>

      <section class="design-panel" data-acceptance-id="purchase-reconciliation-transaction-artifacts">
        <h3>事务产物与零正式写入</h3>
        <span>隔离事务计划数量：{{ transactionArtifacts.isolatedTransactionPlanCount }}</span>
        <span>隔离幂等记录数量：{{ transactionArtifacts.isolatedIdempotencyRecordCount }}</span>
        <span>隔离编号预留数量：{{ transactionArtifacts.isolatedNumberReservationCount }}</span>
        <span>隔离暂存对象数量：{{ transactionArtifacts.isolatedStagedObjectCount }}</span>
        <span>隔离回滚记录数量：{{ transactionArtifacts.isolatedRollbackRecordCount }}</span>
        <span>正式采购对账对象数量：0</span>
        <span>正式编号分配次数：0</span>
        <span>供应商结算状态修改次数：0</span>
        <span>付款对象数量：0</span>
        <span>用户localStorage业务写入次数：0</span>
        <span>网络写请求次数：0</span>
      </section>

      <section class="design-panel" data-acceptance-id="purchase-reconciliation-transaction-protection">
        <h3>事务风险与正式执行保护</h3>
        <span>正式执行权限：关闭</span>
        <span>越权执行阻断编码：BUSINESS_ACTION_FORMAL_EXECUTION_DISABLED</span>
        <span>并发风险：由 sourceKey 锁和目标唯一约束保护</span>
        <span>编号风险：隔离编号不进入正式编号序列</span>
        <span>部分提交风险：commit_unknown 必须显式恢复</span>
        <span>回滚失败风险：rollback_failed 需要人工处理</span>
        <span>当前未解决风险：{{ transactionResult.requiresManualIntervention ? transactionResult.blockingReasonCodes.join('、') : '无' }}</span>
        <span>进入正式生成前仍需满足事项：正式执行授权、后端原子事务及硬唯一约束</span>
      </section>

      <div class="row-actions" data-acceptance-id="purchase-reconciliation-transaction-actions">
        <el-button plain @click="viewFinalReview">查看最终评审</el-button>
        <el-button plain @click="goSourceSupplierSettlement">查看来源供应商结算</el-button>
        <el-button plain @click="reloadTransactionArtifact">重新读取事务结果</el-button>
        <el-button plain @click="returnPurchaseReconciliation">返回采购对账</el-button>
      </div>
    </section>

    <section v-else-if="finalReviewMode" class="table-card pre-generation-design" data-acceptance-id="purchase-reconciliation-final-review">
      <section class="design-panel" data-acceptance-id="purchase-reconciliation-final-review-context">
        <h3>最终评审上下文</h3>
        <span>候选对象标识：{{ finalReview.sourceCandidateId || '-' }}</span>
        <span>来源供应商结算编号：{{ finalReview.sourceSupplierSettlementNo || '-' }}</span>
        <span>模拟请求标识：{{ finalReview.simulationRequestId || '-' }}</span>
        <span>模拟结果标识：{{ finalReview.simulationResultId || '-' }}</span>
        <span>模拟最终状态：{{ finalReview.simulationFinalState || '-' }}</span>
        <span>模拟结果完整性：{{ finalReview.integrityResult }}</span>
        <span>评审标识：{{ finalReview.reviewId || '-' }}</span>
        <span>评审策略版本：{{ finalReview.reviewPolicyVersion || '-' }}</span>
      </section>

      <section class="design-panel" data-acceptance-id="purchase-reconciliation-final-review-decision">
        <h3>最终评审结论</h3>
        <span>评审状态：{{ finalReview.reviewState }}</span>
        <span>评审决策：{{ finalReview.reviewDecision }}</span>
        <span>业务条件是否满足：{{ finalReview.reviewDecision === 'approved' ? '是' : '否' }}</span>
        <span>是否达到未来正式生成条件：{{ finalReview.generationReadiness === 'ready' ? '是' : '否' }}</span>
        <span>本版本是否允许正式生成：否</span>
        <span>当前未满足条件数量：{{ finalReview.unmetConditions.length }}</span>
        <span>致命风险数量：{{ fatalReviewRisks.length }}</span>
      </section>

      <section class="design-panel design-table" data-acceptance-id="purchase-reconciliation-final-review-conditions">
        <h3>正式生成放行条件总表</h3>
        <el-table :data="finalReview.conditionResults" border size="small">
          <el-table-column prop="code" label="条件编码" min-width="280" />
          <el-table-column prop="category" label="条件分类" width="140" />
          <el-table-column prop="name" label="条件名称" min-width="210" />
          <el-table-column prop="status" label="检查结果" width="110" />
          <el-table-column prop="actual" label="实际值" min-width="180" />
          <el-table-column prop="expected" label="期望值" min-width="160" />
          <el-table-column label="是否阻断" width="100"><template #default="{ row }">{{ row.blocking ? '是' : '否' }}</template></el-table-column>
        </el-table>
      </section>

      <section class="design-panel design-table" data-acceptance-id="purchase-reconciliation-final-review-unmet">
        <h3>当前未满足条件清单</h3>
        <span v-if="finalReview.unmetConditions.length === 0">无未满足条件</span>
        <el-table v-else :data="finalReview.unmetConditions" border size="small">
          <el-table-column prop="code" label="条件编码" min-width="280" />
          <el-table-column prop="actual" label="实际值" min-width="180" />
          <el-table-column prop="expected" label="期望值" min-width="160" />
          <el-table-column prop="message" label="阻断原因" min-width="260" />
        </el-table>
      </section>

      <section class="design-panel" data-acceptance-id="purchase-reconciliation-final-review-freshness">
        <h3>来源新鲜度与唯一性复核</h3>
        <span>模拟来源快照哈希：{{ finalReview.sourceSnapshotHash || '-' }}</span>
        <span>当前来源快照哈希：{{ finalReview.currentSourceSnapshotHash || '-' }}</span>
        <span>来源是否变化：{{ finalReview.freshnessResult.status === 'stale' ? '是' : '否' }}</span>
        <span>变化字段：{{ finalReview.freshnessResult.changedFields.join('、') || '-' }}</span>
        <span>模拟金额：{{ formatAmount(finalReview.simulationAmount) }}</span>
        <span>当前金额：{{ formatAmount(finalReview.currentAmount) }}</span>
        <span>金额差异：{{ formatAmount(finalReview.amountDifference) }}</span>
        <span>模拟币种/当前币种：{{ finalReview.simulationCurrency || '-' }} / {{ finalReview.currentCurrency || '-' }}</span>
        <span>目标存在状态：{{ finalReview.targetExistenceStatus }}</span>
        <span>当前目标数量：{{ finalReview.currentTargetCount }}</span>
        <span>当前目标编号：{{ finalReview.existingTargetNos.join('、') || '-' }}</span>
        <span>是否存在唯一性冲突：{{ finalReview.targetExistenceStatus === 'multiple_targets' ? '是' : '否' }}</span>
      </section>

      <section class="design-panel" data-acceptance-id="purchase-reconciliation-final-review-forbidden-actions">
        <h3>绝对禁止自动推进事项</h3>
        <span v-for="action in finalReview.forbiddenAutoAdvanceActions" :key="action">{{ action }}：禁止</span>
      </section>

      <section class="design-panel design-table" data-acceptance-id="purchase-reconciliation-final-review-audit">
        <h3>正式生成前审计要求</h3>
        <el-table :data="finalReview.auditRequirements" border size="small">
          <el-table-column prop="field" label="审计字段" min-width="260" />
          <el-table-column label="是否必需" width="100"><template #default="{ row }">{{ row.required ? '是' : '否' }}</template></el-table-column>
          <el-table-column label="当前具备" width="100"><template #default="{ row }">{{ row.present ? '是' : '否' }}</template></el-table-column>
        </el-table>
      </section>

      <section class="design-panel" data-acceptance-id="purchase-reconciliation-final-review-reassessment">
        <h3>回滚、作废与重新评审边界</h3>
        <span v-for="boundary in reassessmentBoundaries" :key="boundary">{{ boundary }}</span>
      </section>

      <section class="design-panel" data-acceptance-id="purchase-reconciliation-final-review-artifacts">
        <h3>模拟与评审产物分类</h3>
        <span>模拟请求产物数量：{{ finalReview.artifactClassification.simulationRequestArtifactCount }}</span>
        <span>模拟结果产物数量：{{ finalReview.artifactClassification.simulationResultArtifactCount }}</span>
        <span>状态检查点数量：{{ finalReview.artifactClassification.simulationStateCheckpointCount }}</span>
        <span>评审产物数量：{{ finalReview.artifactClassification.reviewArtifactCount }}</span>
        <span>跨进程恢复副本数量：{{ finalReview.artifactClassification.crossProcessRecoveryCopyCount }}</span>
        <span>幂等复用次数：{{ finalReview.artifactClassification.idempotentReuseCount }}</span>
        <span>完整性拒绝副本数量：{{ finalReview.artifactClassification.rejectedIntegrityCopyCount }}</span>
        <span>正式业务写入数量：{{ finalReview.formalBusinessWriteCount }}</span>
      </section>

      <section class="design-panel" data-acceptance-id="purchase-reconciliation-final-review-risks">
        <h3>最终风险清单与零写入保护</h3>
        <span>致命风险：{{ fatalReviewRisks.map((item) => item.code).join('、') || '无' }}</span>
        <span>非致命风险：{{ nonFatalReviewRisks.map((item) => item.code).join('、') || '无' }}</span>
        <span>正式采购对账对象数量：0</span>
        <span>正式编号分配次数：{{ finalReview.formalNumberAllocationCount }}</span>
        <span>供应商结算状态修改次数：{{ finalReview.supplierSettlementWriteCount }}</span>
        <span>付款对象数量：{{ finalReview.paymentObjectWriteCount }}</span>
        <span>用户localStorage业务写入次数：{{ finalReview.localStorageBusinessWriteCount }}</span>
        <span>网络写请求次数：{{ finalReview.networkWriteRequestCount }}</span>
      </section>

      <div class="row-actions" data-acceptance-id="purchase-reconciliation-final-review-actions">
        <el-button plain @click="goSourceSupplierSettlement">查看来源供应商结算</el-button>
        <el-button plain @click="focusReviewRegion('purchase-reconciliation-final-review-context')">查看模拟请求</el-button>
        <el-button plain @click="focusReviewRegion('purchase-reconciliation-final-review-decision')">查看模拟结果</el-button>
        <el-button plain @click="returnPurchaseReconciliation">返回采购对账</el-button>
        <el-button plain @click="reloadReviewArtifact">重新读取评审结果</el-button>
      </div>
    </section>

    <section v-else-if="simulationMode" class="table-card pre-generation-design" data-acceptance-id="purchase-reconciliation-simulation-state-machine">
      <section class="design-panel" data-acceptance-id="purchase-reconciliation-simulation-candidate-context">
        <h3>采购对账候选上下文</h3>
        <span>候选对象标识：{{ precheck.candidate.candidateId || '-' }}</span>
        <span>唯一来源键：{{ precheck.candidate.sourceKey || '-' }}</span>
        <span>来源供应商结算编号：{{ precheck.candidate.sourceSupplierSettlementNo || '-' }}</span>
        <span>业务资格：{{ precheck.businessEligibility }}</span>
        <span>目标存在状态：{{ precheck.targetExistenceStatus }}</span>
        <span>运行时模拟权限：{{ simulationAuthorization.simulationExecutionAllowed ? '是' : '否' }}</span>
        <span>正式生成权限：否</span>
        <span>现有目标编号：{{ precheck.targetNos.join('、') || '-' }}</span>
      </section>

      <section class="design-panel" data-acceptance-id="purchase-reconciliation-simulation-request">
        <h3>模拟请求对象</h3>
        <span>模拟请求标识：{{ simulationRequest.simulationRequestId || '-' }}</span>
        <span>模拟策略版本：{{ simulationRequest.simulationPolicyVersion }}</span>
        <span>输入快照哈希：{{ simulationRequest.inputSnapshotHash }}</span>
        <span>预检查结果哈希：{{ simulationRequest.precheckResultHash }}</span>
        <span>请求唯一键：{{ simulationRequest.requestUniquenessKey || '-' }}</span>
        <span>运行模式：{{ simulationRequest.runtimeMode }}</span>
      </section>

      <section class="design-panel" data-acceptance-id="purchase-reconciliation-simulation-status">
        <h3>模拟状态机运行状态</h3>
        <span>初始状态：not_created</span>
        <span>当前状态：{{ simulationView.finalState }}</span>
        <span>最终状态：{{ simulationView.finalState }}</span>
        <span>是否终态：{{ simulationView.terminal ? '是' : '否' }}</span>
        <span>模拟结果：{{ simulationView.outcome }}</span>
        <span>状态转换次数：{{ simulationView.stateHistory.length }}</span>
        <span>非法转换次数：{{ simulationScenario?.testKind === 'illegal_transition' ? 1 : 0 }}</span>
      </section>

      <section class="design-panel design-table" data-acceptance-id="purchase-reconciliation-simulation-history">
        <h3>状态转换历史</h3>
        <el-table :data="simulationView.stateHistory" border size="small">
          <el-table-column prop="sequence" label="顺序" width="80" />
          <el-table-column prop="fromState" label="原状态" min-width="160" />
          <el-table-column prop="eventCode" label="事件编码" min-width="270" />
          <el-table-column prop="toState" label="目标状态" min-width="180" />
          <el-table-column prop="reasonCode" label="原因编码" min-width="250" />
          <el-table-column label="是否终态" width="100"><template #default="{ row }">{{ row.terminal ? '是' : '否' }}</template></el-table-column>
        </el-table>
      </section>

      <section class="design-panel" data-acceptance-id="purchase-reconciliation-simulation-result">
        <h3>模拟结果对象</h3>
        <span>模拟结果标识：{{ simulationResult.simulationResultId || '-' }}</span>
        <span>结果类型：{{ simulationView.outcome }}</span>
        <span>结果哈希：{{ simulationResult.resultHash }}</span>
        <span>阻断原因：{{ simulationResult.blockingReasonCodes.join('、') || '-' }}</span>
        <span>失败原因：{{ simulationResult.failureReasonCodes.join('、') || '-' }}</span>
        <span>结果完整性：{{ simulationIntegrity.integrityValid ? '有效' : '无效' }}</span>
        <span v-if="!simulationIntegrity.integrityValid">完整性错误编码：{{ simulationIntegrity.errorCode }}</span>
        <span>拟生成对象快照：{{ simulationView.proposedPurchaseReconciliationSnapshot ? '已形成只读快照' : '未形成' }}</span>
        <span>正式采购对账编号：未分配</span>
      </section>

      <section class="design-panel" data-acceptance-id="purchase-reconciliation-simulation-write-protection">
        <h3>模拟写入与正式业务保护</h3>
        <span>模拟测试产物写入数量：1</span>
        <span>正式业务写入数量：0</span>
        <span>正式采购对账对象数量：0</span>
        <span>正式编号分配次数：0</span>
        <span>供应商结算状态修改次数：0</span>
        <span>付款对象写入数量：0</span>
        <span>用户localStorage写入次数：0</span>
        <span>网络写请求次数：0</span>
      </section>

      <div class="row-actions" data-acceptance-id="purchase-reconciliation-simulation-readonly-actions">
        <el-button plain @click="goSourceSupplierSettlement">查看来源供应商结算</el-button>
        <el-button plain :disabled="!precheck.candidate.sourcePayableCheckNo" @click="goSourcePayableCheck">查看来源采购应付核对</el-button>
        <el-button plain @click="goSourceSupplierSettlement">返回供应商结算</el-button>
      </div>
    </section>

    <section v-else-if="preGenerationMode" class="table-card pre-generation-design" data-acceptance-id="purchase-reconciliation-pre-generation-design">
      <section class="design-panel" data-acceptance-id="purchase-reconciliation-candidate-source">
        <h3>采购对账候选来源</h3>
        <span>来源供应商结算编号：{{ precheck.candidate.sourceSupplierSettlementNo || '-' }}</span>
        <span>来源采购应付核对编号：{{ precheck.candidate.sourcePayableCheckNo || '-' }}</span>
        <span>来源应付预备编号：{{ precheck.candidate.sourcePayablePrepareNo || '-' }}</span>
        <span>来源采购订单编号：{{ precheck.candidate.purchaseOrderNo || '-' }}</span>
        <span>供应商编号：{{ precheck.candidate.supplierId || '-' }}</span>
        <span>供应商名称：{{ precheck.candidate.supplierName || '-' }}</span>
        <span>来源上下文状态：{{ candidateInput.contextState || '-' }}</span>
        <span>供应商结算状态：{{ candidateInput.sourceSettlement?.settlementStatus || '-' }}</span>
      </section>

      <section class="design-panel" data-acceptance-id="purchase-reconciliation-domain-model">
        <h3>采购对账领域模型</h3>
        <span>候选对象标识：{{ precheck.candidate.candidateId || '-' }}</span>
        <span>来源类型：{{ precheck.candidate.sourceType }}</span>
        <span>唯一来源键：{{ precheck.candidate.sourceKey || '-' }}</span>
        <span>法人：{{ precheck.candidate.legalEntityId || '生成前必须补齐' }} {{ precheck.candidate.legalEntityName }}</span>
        <span>账套：{{ precheck.candidate.ledgerBookId || '生成前必须补齐' }} {{ precheck.candidate.ledgerBookName }}</span>
        <span>币种：{{ precheck.candidate.currency || '生成前必须补齐' }}</span>
        <span>数量：{{ precheck.candidate.quantity }}</span>
        <span>单位：{{ precheck.candidate.unit || '-' }}</span>
        <span>金额口径：结算金额</span>
        <span>金额：{{ formatAmount(precheck.candidate.amount) }}</span>
        <span>来源金额：{{ formatAmount(precheck.amountComparison.sourceAmount) }}</span>
        <span>目标候选金额：{{ formatAmount(precheck.amountComparison.candidateAmount) }}</span>
        <span>差异值：{{ formatAmount(precheck.amountComparison.difference) }}</span>
      </section>

      <section class="design-panel" data-acceptance-id="purchase-reconciliation-uniqueness-decision">
        <h3>唯一性决策</h3>
        <span>目标存在状态：{{ precheck.targetExistenceStatus }}</span>
        <span>现有采购对账目标数量：{{ precheck.targetCount }}</span>
        <span>现有目标编号：{{ precheck.targetNos.join('、') || '-' }}</span>
        <span>是否存在唯一性冲突：{{ precheck.targetExistenceStatus === 'multiple_targets' ? '是' : '否' }}</span>
        <span>业务资格：{{ precheck.businessEligibility }}</span>
      </section>

      <section class="design-panel design-table" data-acceptance-id="purchase-reconciliation-source-mapping">
        <h3>来源字段映射</h3>
        <el-table :data="precheck.mapping" border size="small">
          <el-table-column prop="targetField" label="目标字段" min-width="180" />
          <el-table-column prop="sourceObject" label="来源对象" min-width="210" />
          <el-table-column prop="sourceField" label="来源字段" min-width="220" />
          <el-table-column prop="actual" label="实际值" min-width="190" />
          <el-table-column label="是否必填" width="100"><template #default="{ row }">{{ row.required ? '是' : '否' }}</template></el-table-column>
          <el-table-column prop="mappingResult" label="映射结果" width="120" />
        </el-table>
      </section>

      <section class="design-panel design-table" data-acceptance-id="purchase-reconciliation-precheck-rules">
        <h3>生成前预检查</h3>
        <el-table :data="precheck.rules" border size="small">
          <el-table-column prop="code" label="规则编码" min-width="250" />
          <el-table-column prop="message" label="规则名称" min-width="260" />
          <el-table-column prop="status" label="检查结果" width="110" />
          <el-table-column prop="actual" label="实际值" min-width="180" />
          <el-table-column prop="expected" label="期望值" min-width="160" />
          <el-table-column label="阻断原因" min-width="220"><template #default="{ row }">{{ row.status === 'blocked' ? row.message : '-' }}</template></el-table-column>
        </el-table>
      </section>

      <section class="design-panel" data-acceptance-id="purchase-reconciliation-zero-write-protection">
        <h3>零写入与运行时保护</h3>
        <span>业务条件是否满足：{{ precheck.businessEligibility === 'eligible' ? '是' : '否' }}</span>
        <span>本版本是否允许生成：否</span>
        <span>是否分配正式采购对账编号：否</span>
        <span>采购对账对象写入数量：{{ precheck.writeMetrics.purchaseReconciliationWrites }}</span>
        <span>供应商结算状态修改数量：{{ precheck.writeMetrics.supplierSettlementStatusWrites }}</span>
        <span>付款对象写入数量：{{ precheck.writeMetrics.paymentObjectWrites }}</span>
        <span>localStorage写入次数：{{ precheck.writeMetrics.localStorageWrites }}</span>
        <span>网络写请求次数：{{ precheck.writeMetrics.networkWriteRequests }}</span>
      </section>

      <div class="row-actions" data-acceptance-id="purchase-reconciliation-design-actions">
        <el-button plain @click="goSourceSupplierSettlement">查看来源供应商结算</el-button>
        <el-button plain :disabled="!precheck.candidate.sourcePayableCheckNo" @click="goSourcePayableCheck">查看来源采购应付核对</el-button>
        <el-button plain @click="goSourceSupplierSettlement">返回供应商结算</el-button>
      </div>
    </section>

    <section v-else class="table-card">
      <el-alert
        v-if="sourceSettlementNo"
        data-acceptance-id="purchase-reconciliation-source-context"
        :title="`当前服务端来源供应商结算：${sourceSettlementNo}`"
        description="正式采购对账状态、差异和下一步资格均由服务端返回。"
        type="info"
        :closable="false"
      />
      <PceBusinessActionBar
        current-module="purchase-reconciliation"
        :current-status="selectedRows[0]?.status || selectedRows[0]?.reconciliationStatus || ''"
        :selected-rows="selectedRows"
        :eligibility="selectedRows[0]?.invoicePrepareEligibility?.eligible ?? null"
        :show-unavailable="selectedRows.length === 0"
        @execute="executeRegistryAction"
      />
      <div class="facts" data-acceptance-id="purchase-reconciliation-strict-facts">
        <div><span>当前状态来源</span><strong>{{ strictFacts.currentStateSource }}</strong></div>
        <div><span>对象数量</span><strong>{{ strictFacts.objectCount }}</strong></div>
        <div><span>状态迁移数量</span><strong>{{ strictFacts.statusTransitionCount }}</strong></div>
        <div><span>状态机一致</span><strong>{{ strictFacts.stateMachineConsistent }}</strong></div>
      </div>
      <div class="standard-list-toolbar" data-acceptance-id="standard-list-toolbar" data-pce-page-id="purchase-reconciliation" data-pce-toolbar-for="purchase-reconciliation-main">
        <span class="toolbar-search-wrapper" data-acceptance-id="list-fuzzy-search-input">
        <el-input
          v-model="quickSearch"
          class="toolbar-search"
          clearable
          placeholder="输入编号、来源单号、供应商或关键字"
          @keyup.enter="clearSelection"
          @clear="clearSelection"
        />
        </span>
        <el-button plain data-acceptance-id="list-advanced-filter-toggle" data-pce-filter-toggle-for="purchase-reconciliation-main" :aria-expanded="String(advancedFilterVisible)" @click="advancedFilterVisible = !advancedFilterVisible">
          {{ advancedFilterVisible ? '收起高级筛选' : '展开高级筛选' }}
        </el-button>
        <el-button type="primary" plain data-acceptance-id="list-fuzzy-search-button" @click="clearSelection">
          搜索
        </el-button>
        <el-button plain data-acceptance-id="list-clear-filter-button" @click="clearFilters">清空筛选</el-button>
        <el-button plain data-acceptance-id="list-clear-sort-button" @click="clearSort">清除排序</el-button>
        <el-button type="primary" plain data-acceptance-id="list-export-current-result-button" data-pce-export-for="purchase-reconciliation-main" :disabled="filteredSortedRows.length === 0" @click="exportCurrentRows">
          导出当前结果
        </el-button>
        <span data-acceptance-id="list-result-count-visible">当前结果 {{ filteredSortedRows.length }} 条</span>
        <span data-acceptance-id="business-flow-selected-count">已选择 {{ selectedRows.length }} 条</span>
        <el-button plain :disabled="selectedRows.length === 0" @click="clearSelection">清空选择</el-button>
      </div>

      <section v-show="advancedFilterVisible" class="advanced-filter-panel" data-acceptance-id="list-advanced-filter-panel" data-pce-filter-for="purchase-reconciliation-main">
        <label>采购对账编号<el-select v-model="filters.reconciliationNo" filterable clearable placeholder="请选择或搜索">
          <el-option v-for="option in reconciliationNoOptions" :key="option" :label="option" :value="option" />
        </el-select></label>
        <label>来源供应商结算单号<el-select v-model="filters.sourceSettlementNo" filterable clearable placeholder="请选择或搜索">
          <el-option v-for="option in sourceSettlementNoOptions" :key="option" :label="option" :value="option" />
        </el-select></label>
        <label>采购对账状态<el-select v-model="filters.reconciliationStatus" clearable placeholder="全部">
          <el-option v-for="option in reconciliationStatusOptions" :key="option.value" :label="option.label" :value="option.value" />
        </el-select></label>
        <label>供应商<el-select v-model="filters.supplierName" filterable clearable placeholder="请选择或搜索">
          <el-option v-for="option in supplierOptions" :key="option" :label="option" :value="option" />
        </el-select></label>
        <label>采购订单号<el-select v-model="filters.purchaseOrderNo" filterable clearable placeholder="请选择或搜索">
          <el-option v-for="option in purchaseOrderNoOptions" :key="option" :label="option" :value="option" />
        </el-select></label>
      </section>

      <h3 data-acceptance-id="page-internal-subject-title"><PceBusinessNameConsumer page-code="purchase-reconciliation" /></h3>
      <BusinessTableScrollContainer
        class="pce-baseline-table-shell"
        acceptance-id="business-table-scroll-purchase-reconciliation-main"
        page-id="purchase-reconciliation"
        table-id="purchase-reconciliation-main"
        min-width="2600px"
      >
        <el-table
          ref="tableRef"
          class="pce-baseline-table-shell global-sort-arrow"
          :data="filteredSortedRows"
          border
          stripe
          height="500"
          scrollbar-always-on
          row-key="reconciliationNo"
          @selection-change="selectedRows = $event"
          @sort-change="handleSortChange"
        >
          <el-table-column type="selection" width="52" fixed="left" class-name="business-table-selection-column" header-class-name="business-table-selection-column" label-class-name="business-table-selection-column" />
          <el-table-column type="index" label="序号" width="70" fixed="left" class-name="pce-fixed-index-column" header-class-name="pce-fixed-index-column" label-class-name="pce-fixed-index-column" />
          <el-table-column prop="reconciliationNo" label="采购对账编号" width="220" fixed="left" sortable="custom" class-name="pce-fixed-primary-no-column" header-class-name="pce-fixed-primary-no-column" label-class-name="pce-fixed-primary-no-column" />
          <el-table-column prop="sourceSettlementNo" label="来源供应商结算单号" width="210" sortable="custom" />
          <el-table-column prop="sourcePayableCheckNo" label="来源应付核对单号" width="200" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商" width="180" sortable="custom" />
          <el-table-column prop="purchaseOrderNo" label="采购订单号" width="180" sortable="custom" />
          <el-table-column prop="settlementAmount" label="结算金额" width="140" sortable="custom">
            <template #default="{ row }">{{ formatAmount(row.settlementAmount) }}</template>
          </el-table-column>
          <el-table-column prop="differenceAmount" label="差异金额" width="140" sortable="custom">
            <template #default="{ row }">{{ formatAmount(row.differenceAmount) }}</template>
          </el-table-column>
          <el-table-column prop="statusText" label="采购对账状态" width="160" sortable="custom" />
          <el-table-column prop="boundaryText" label="当前能力边界" width="240" />
          <el-table-column label="操作" width="260" fixed="right" class-name="payment-fixed-action-column" header-class-name="payment-fixed-action-column" label-class-name="payment-fixed-action-column">
            <template #default="{ row }">
              <div class="row-actions">
                <el-button size="small" plain @click="goSupplierSettlement(row)">查看来源供应商结算</el-button>
                <el-button size="small" plain @click="showServerResult(row)">查看采购对账结果</el-button>
                <el-button
                  size="small"
                  type="success"
                  :disabled="row.status !== 'draft'"
                  data-acceptance-id="complete-purchase-reconciliation-check"
                  @click="completeCheck(row)"
                >{{ pceBusinessActionLabel('complete-purchase-reconciliation') }}</el-button>
                <el-button
                  size="small"
                  type="primary"
                  :disabled="!invoicePrepareNavigation(row).allowed"
                  :title="invoicePrepareNavigation(row).reason"
                  data-acceptance-id="purchase-reconciliation-go-invoice-prepare-row"
                  @click="goPurchaseInvoicePrepare(row)"
                >{{ pceBusinessActionLabel('enter-purchase-invoice-prepare') }}</el-button>
                <small v-if="invoicePrepareNavigation(row).reason" class="blocked-reason">{{ invoicePrepareNavigation(row).reason }}</small>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </BusinessTableScrollContainer>

      <footer class="table-footer">
        <span>当前页码：1</span>
        <span>每页数量：{{ filteredSortedRows.length }}</span>
        <span>当前结果总数：{{ filteredSortedRows.length }}</span>
        <span>已选择数量：{{ selectedRows.length }}</span>
      </footer>
    </section>
  </main>
</template>

<script setup>
import PceBusinessNameConsumer from '../components/PceBusinessNameConsumer.vue'
const { embeddedInCommonShell = false } = defineProps({
  embeddedInCommonShell: { type: Boolean, default: false },
})
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import BusinessTableScrollContainer from '../components/BusinessTableScrollContainer.vue'
import PceBusinessActionBar from '../components/PceBusinessActionBar.vue'
import { pceBusinessActionLabel } from '../runtime/pceBusinessActionRegistry.js'
import {
  completePurchaseReconciliationCheck,
  listPurchaseReconciliations,
} from '../../api/purchaseReconciliation.js'
import {
  buildPurchaseInvoicePrepareRoute,
  evaluatePurchaseInvoicePrepareNavigation,
  getPurchaseReconciliationStatusLabel,
} from '../process/purchaseInvoicePrepareNavigation.js'
import { buildPurchaseReconciliationPrecheckResult } from '../scm/purchaseReconciliationCandidate.js'
import {
  buildPurchaseReconciliationSimulationRequest,
  buildPurchaseReconciliationSimulationResult,
  evaluatePurchaseReconciliationSimulationAuthorization,
  transitionPurchaseReconciliationSimulationState,
  validatePurchaseReconciliationSimulationIntegrity,
} from '../scm/purchaseReconciliationSimulation.js'

const VERSION = 'V1.14.2.8.4.7.42'
const router = useRouter()
const route = useRoute()
const sourceSettlementNo = computed(() => String(route.query.sourceSettlementNo || route.query.settlementNo || '').trim())
const sourceSettlementId = computed(() => String(route.query.sourceSettlementId || '').trim())
const preGenerationMode = computed(() => String(route.query.designMode || '') === 'pre_generation')
const simulationMode = computed(() => String(route.query.designMode || '') === 'simulation_state_machine')
const finalReviewMode = computed(() => String(route.query.designMode || '') === 'final_review')
const transactionDesignMode = computed(() => String(route.query.designMode || '') === 'formal_generation_transaction_design')
const controlledGenerationMode = computed(() => String(route.query.designMode || '') === 'controlled_formal_generation')
const productionPersistenceMode = computed(() => String(route.query.designMode || '') === 'production_persistence_readiness')
const productionReadiness = computed(() => globalThis.__PCE_PRODUCTION_PERSISTENCE_ACCEPTANCE__ || {
  environment: 'production-rollout-disabled', tenantId: '-', transactionState: 'not-executed',
  reconciliationNo: '-', sourceKey: '-', targetId: '-', transactionId: '-', canaryBatchId: '-', failureInjectionCount: 15,
})
const candidateScenarioCode = computed(() => String(route.query.scenarioCode || '').trim())
const tableRef = ref(null)
const quickSearch = ref('')
const advancedFilterVisible = ref(false)
const selectedRows = ref([])
const sortState = ref({ prop: '', order: '' })
const reviewReloadNonce = ref(0)
const transactionReloadNonce = ref(0)
const controlledReloadNonce = ref(0)
const productionReloadNonce = ref(0)
const serverRows = ref([])
const serverReadError = ref('')
const strictFacts = reactive({
  currentStateSource: 'server',
  objectCount: null,
  statusTransitionHistory: null,
  statusTransitionCount: null,
  stateMachineConsistent: false,
})
const filters = reactive({
  reconciliationNo: '',
  sourceSettlementNo: '',
  reconciliationStatus: '',
  supplierName: '',
  purchaseOrderNo: '',
})

function readCandidateCanaries() {
  try {
    return JSON.parse(localStorage.getItem('pce-purchase-reconciliation-candidate-canaries-v1') || '{}').scenarios || []
  } catch {
    return []
  }
}

function readSimulationCanaries() {
  try {
    return JSON.parse(localStorage.getItem('pce-purchase-reconciliation-simulation-canaries-v1') || '{}').scenarios || []
  } catch {
    return []
  }
}

function readFinalReviewCanaries() {
  reviewReloadNonce.value
  try {
    return JSON.parse(localStorage.getItem('pce-purchase-reconciliation-final-review-canaries-v1') || '{}').scenarios || []
  } catch {
    return []
  }
}

function readTransactionCanaries() {
  transactionReloadNonce.value
  try {
    return JSON.parse(localStorage.getItem('pce-purchase-reconciliation-transaction-canaries-v1') || '{}').scenarios || []
  } catch {
    return []
  }
}

function readControlledGenerationCanaries() {
  controlledReloadNonce.value
  try {
    return JSON.parse(localStorage.getItem('pce-purchase-reconciliation-controlled-generation-canaries-v1') || '{}').scenarios || []
  } catch {
    return []
  }
}

const emptyControlledResult = { businessGateResult: {}, transactionGateResult: {}, authorizationResult: {}, denialCodes: [], compensationResults: [], transactionState: 'not_created', outcome: 'not_created', idempotencyKey: '', numberReservationStatus: 'not_reserved', idempotencyStatus: 'not_found', commitStatus: 'not_started', recoveryStatus: 'not_required', formalEquivalentObjectCountBefore: 0, formalEquivalentObjectCountAfter: 0, formalEquivalentObjectCountAfterRetry: 0, lockAcquireCount: 0, residualObjectCount: 0, residualRelationCount: 0, residualAuditCount: 0, requiresRecovery: false, requiresManualIntervention: false, safeToRetry: false }
const controlledScenario = computed(() => readControlledGenerationCanaries().find((item) => item.scenarioCode === candidateScenarioCode.value) || null)
const controlledResult = computed(() => controlledScenario.value?.controlledResult || emptyControlledResult)
const controlledObject = computed(() => controlledScenario.value?.formalEquivalentObject || null)
const controlledCounts = computed(() => controlledScenario.value?.isolatedCounts || { formalObjects: 0, idempotencyRecords: 0, numberReservations: 0, sourceTargetRelations: 0, sourceBackReferences: 0, auditRecords: 0, commitRecords: 0, rollbackRecords: 0, recoveryRecords: 0 })

const emptyTransactionPlan = { transactionPlanId: '', transactionPolicyVersion: '', transactionSteps: [], compensationSteps: [], numberReservationPlan: { numberScope: {} } }
const emptyTransactionResult = { command: {}, transactionPlan: emptyTransactionPlan, transactionState: 'not_created', outcome: 'not_created', committed: false, rolledBack: false, commitUnknown: false, requiresRecovery: false, requiresManualIntervention: false, blockingReasonCodes: [], existingTargetNos: [], executedSteps: [], compensationResults: [], residualBusinessEntityCount: 0, numberReservationStatus: 'not_reserved', simulatedFormalTargetNo: '', idempotencyStatus: 'not_found', lockStatus: 'not_acquired', transactionResultHash: '' }
const transactionScenario = computed(() => readTransactionCanaries().find((item) => item.scenarioCode === candidateScenarioCode.value) || null)
const transactionResult = computed(() => transactionScenario.value?.transactionResult || emptyTransactionResult)
const transactionNumberPlan = computed(() => transactionResult.value.transactionPlan.numberReservationPlan || { numberScope: {} })
const transactionNumberScope = computed(() => Object.entries(transactionNumberPlan.value.numberScope || {}).map(([key, value]) => `${key}=${value}`).join('；') || '-')
const transactionRecovery = computed(() => transactionScenario.value?.recoveryResult || { classification: transactionResult.value.commitUnknown ? 'recovery_required' : 'not_required', safeToRetry: false })
const transactionArtifacts = computed(() => transactionScenario.value?.artifactClassification || { isolatedCommandCount: 1, isolatedTransactionPlanCount: 1, isolatedIdempotencyRecordCount: 1, isolatedNumberReservationCount: transactionResult.value.numberReservationStatus === 'not_reserved' ? 0 : 1, isolatedStagedObjectCount: transactionResult.value.committed ? 1 : 0, isolatedCommitRecordCount: transactionResult.value.committed ? 1 : 0, isolatedRollbackRecordCount: transactionResult.value.rolledBack ? 1 : 0, isolatedRecoveryRecordCount: transactionScenario.value?.recoveryResult ? 1 : 0, formalBusinessWriteCount: 0 })

const emptyArtifactClassification = { simulationRequestArtifactCount: 0, simulationResultArtifactCount: 0, simulationStateCheckpointCount: 0, reviewArtifactCount: 0, crossProcessRecoveryCopyCount: 0, idempotentReuseCount: 0, rejectedIntegrityCopyCount: 0, formalBusinessWriteCount: 0 }
const emptyFinalReview = { sourceCandidateId: '', sourceSupplierSettlementNo: '', simulationRequestId: '', simulationResultId: '', simulationFinalState: '', integrityResult: 'invalid', reviewId: '', reviewPolicyVersion: '', reviewState: 'not_created', reviewDecision: 'blocked', generationReadiness: 'not_ready', unmetConditions: [], conditionResults: [], riskItems: [], auditRequirements: [], freshnessResult: { status: 'stale', changedFields: [] }, sourceSnapshotHash: '', currentSourceSnapshotHash: '', simulationAmount: null, currentAmount: null, amountDifference: 0, simulationCurrency: '', currentCurrency: '', targetExistenceStatus: 'read_failed', currentTargetCount: 0, existingTargetNos: [], forbiddenAutoAdvanceActions: [], artifactClassification: emptyArtifactClassification, formalBusinessWriteCount: 0, formalNumberAllocationCount: 0, supplierSettlementWriteCount: 0, paymentObjectWriteCount: 0, localStorageBusinessWriteCount: 0, networkWriteRequestCount: 0 }
const finalReviewScenario = computed(() => readFinalReviewCanaries().find((item) => item.scenarioCode === candidateScenarioCode.value) || null)
const finalReview = computed(() => finalReviewScenario.value?.review || emptyFinalReview)
const fatalReviewRisks = computed(() => finalReview.value.riskItems.filter((item) => item.severity === 'fatal'))
const nonFatalReviewRisks = computed(() => finalReview.value.riskItems.filter((item) => item.severity !== 'fatal'))
const reassessmentBoundaries = [
  '评审结果不是正式对象，不使用正式作废动作。', '来源变化后标记为 stale 并保留原证据。',
  '完整性失败时拒绝恢复且不覆盖原证据。', '新输入生成新 reviewId，相同输入复用原 reviewId。',
  'blocked、stale 和 failed 不得自动变成 passed。', '未来重新评审必须保留与旧评审结果的关系。',
  '正式对象形成后必须使用未来专门的取消、作废和恢复策略。', '不得删除旧目标来恢复可生成状态。',
]

const simulationScenario = computed(() => readSimulationCanaries().find((item) => item.scenarioCode === candidateScenarioCode.value) || null)

const candidateInput = computed(() => {
  if (simulationScenario.value?.candidateInput) return simulationScenario.value.candidateInput
  const canary = readCandidateCanaries().find((item) => item.scenarioCode === candidateScenarioCode.value)
  if (canary) return canary
  return {
    sourceType: 'supplier_settlement', contextState: 'invalid_source', sourceSettlement: null,
    upstreamEvidence: {},
    targetEvidence: [], writeMetrics: { purchaseReconciliationWrites: 0, supplierSettlementStatusWrites: 0, paymentObjectWrites: 0, formalNumberAllocations: 0, localStorageWrites: 0, networkWriteRequests: 0 },
  }
})
const precheck = computed(() => buildPurchaseReconciliationPrecheckResult(candidateInput.value))
const simulationRequest = computed(() => buildPurchaseReconciliationSimulationRequest({ candidate: precheck.value.candidate, precheckResult: precheck.value }))
const simulationAuthorization = computed(() => evaluatePurchaseReconciliationSimulationAuthorization({ precheckResult: precheck.value, runtimeMode: simulationRequest.value.runtimeMode, origin: simulationScenario.value?.origin || 'non_canary' }))
const simulationResult = computed(() => buildPurchaseReconciliationSimulationResult({
  request: simulationRequest.value, candidate: precheck.value.candidate, precheckResult: precheck.value,
  origin: simulationScenario.value?.origin || 'non_canary', failureInjectionCode: simulationScenario.value?.failureInjectionCode || '',
}))
const illegalSimulationTransition = computed(() => transitionPurchaseReconciliationSimulationState({ currentState: 'not_created', eventCode: 'PRC_SIMULATION_SUCCEEDED' }))
const simulationView = computed(() => simulationScenario.value?.testKind === 'illegal_transition' ? {
  ...simulationResult.value, finalState: illegalSimulationTransition.value.currentState, outcome: 'blocked', terminal: false,
  stateHistory: illegalSimulationTransition.value.stateHistory, proposedPurchaseReconciliationSnapshot: null,
} : simulationResult.value)
const simulationIntegrity = computed(() => {
  const value = simulationScenario.value?.testKind === 'integrity_tamper' ? { ...simulationResult.value, finalState: 'simulation_failed' } : simulationResult.value
  return validatePurchaseReconciliationSimulationIntegrity(value)
})

function focusReviewRegion(acceptanceId) {
  document.querySelector(`[data-acceptance-id="${acceptanceId}"]`)?.scrollIntoView?.({ block: 'start' })
}

function returnPurchaseReconciliation() {
  router.push('/scm/purchase-reconciliations')
}

function reloadReviewArtifact() {
  reviewReloadNonce.value += 1
}

function reloadTransactionArtifact() {
  transactionReloadNonce.value += 1
}

function reloadControlledArtifact() {
  controlledReloadNonce.value += 1
}

function reloadProductionPersistence() {
  productionReloadNonce.value += 1
  ElMessage.success('已重新读取服务端持久化验收结果')
}

function viewFinalReview() {
  router.push({ path: '/scm/purchase-reconciliations', query: { ...route.query, designMode: 'final_review' } })
}

const distinctOptions = (key) => [...new Set(rows.value.map((item) => String(item[key] || '').trim()).filter(Boolean))]
const reconciliationNoOptions = computed(() => distinctOptions('reconciliationNo'))
const sourceSettlementNoOptions = computed(() => distinctOptions('sourceSettlementNo'))
const supplierOptions = computed(() => distinctOptions('supplierName'))
const purchaseOrderNoOptions = computed(() => distinctOptions('purchaseOrderNo'))

const rows = computed(() => serverRows.value.filter((item) => {
  if (sourceSettlementId.value && String(item.id) !== sourceSettlementId.value) return false
  if (sourceSettlementNo.value && String(item.sourceSettlementNo) !== sourceSettlementNo.value) return false
  return true
}).map((item) => {
  const status = item.status || 'draft'
  return {
    id: item.id,
    sourceSettlementId: item.sourceSettlementId || '',
    reconciliationNo: item.reconciliationNo,
    sourceSettlementNo: item.sourceSettlementNo || '',
    sourcePayableCheckNo: item.sourcePayableCheckNo || '-',
    supplierName: item.supplierName || '-',
    purchaseOrderNo: item.purchaseOrderNo || '',
    settlementAmount: item.settlementAmount || 0,
    differenceAmount: item.differenceAmount || 0,
    reconciliationStatus: status,
    statusText: getPurchaseReconciliationStatusLabel(status),
    nextStepReadiness: item.nextStepReadiness || '',
    invoicePrepareEligibility: item.invoicePrepareEligibility || { eligible: false, blockingReasons: ['PRC_ELIGIBILITY_MISSING'] },
    version: item.version,
    differenceCount: item.differenceCount || 0,
    checkResultCode: item.checkResultCode || '',
    boundaryText: item.invoicePrepareEligibility?.eligible
      ? '服务端核对一致，仅具备进入采购发票准备的导航资格。'
      : '服务端核对未放行，不创建采购发票准备对象。',
  }
}))

async function loadServerRows() {
  const response = await listPurchaseReconciliations()
  const envelope = response?.data || {}
  const payload = envelope?.data || envelope
  if (response?.success === false || !Array.isArray(payload?.results)) {
    serverRows.value = []
    serverReadError.value = response?.error || 'PRC_SERVER_READ_MODEL_UNAVAILABLE'
    return
  }
  serverRows.value = payload.results
  Object.assign(strictFacts, payload.strictFacts || {})
  serverReadError.value = ''
}

async function completeCheck(row) {
  const response = await completePurchaseReconciliationCheck(row.id, {
    idempotencyKey: `prc-check-${row.id}-${row.version}`,
    expectedVersion: row.version,
    explicitUserAction: true,
  })
  if (response?.success === false) {
    ElMessage.error(response.error || '采购对账核对失败')
    return
  }
  await loadServerRows()
  ElMessage.success('采购对账核对结果已由服务端持久化')
}

onMounted(loadServerRows)

const reconciliationStatusOptions = computed(() => [...new Set(rows.value.map((row) => row.reconciliationStatus).filter(Boolean))]
  .map((value) => ({ value, label: getPurchaseReconciliationStatusLabel(value) })))

const selectedInvoicePrepareNavigation = computed(() => {
  if (selectedRows.value.length !== 1) {
    return { allowed: false, reason: selectedRows.value.length ? '只能选择一条采购对账记录。' : '请先选择一条采购对账记录。' }
  }
  return evaluatePurchaseInvoicePrepareNavigation(selectedRows.value[0])
})

const filteredRows = computed(() => rows.value.filter((row) => {
  const q = quickSearch.value.trim().toLowerCase()
  if (q && ![
    row.reconciliationNo,
    row.sourceSettlementNo,
    row.sourcePayableCheckNo,
    row.supplierName,
    row.purchaseOrderNo,
    row.statusText,
  ].join(' ').toLowerCase().includes(q)) return false
  if (filters.reconciliationNo && row.reconciliationNo !== filters.reconciliationNo) return false
  if (filters.sourceSettlementNo && row.sourceSettlementNo !== filters.sourceSettlementNo) return false
  if (filters.reconciliationStatus && row.reconciliationStatus !== filters.reconciliationStatus) return false
  if (filters.supplierName && !row.supplierName.toLowerCase().includes(filters.supplierName.toLowerCase())) return false
  if (filters.purchaseOrderNo && !row.purchaseOrderNo.toLowerCase().includes(filters.purchaseOrderNo.toLowerCase())) return false
  return true
}))

const filteredSortedRows = computed(() => {
  const list = [...filteredRows.value]
  if (!sortState.value.prop || !sortState.value.order) return list
  const factor = sortState.value.order === 'ascending' ? 1 : -1
  return list.sort((a, b) => String(a[sortState.value.prop] ?? '').localeCompare(String(b[sortState.value.prop] ?? ''), 'zh-CN') * factor)
})

function handleSortChange({ prop, order }) {
  sortState.value = { prop: prop || '', order: order || '' }
}

function clearSort() {
  sortState.value = { prop: '', order: '' }
  tableRef.value?.clearSort?.()
}

function clearSelection() {
  tableRef.value?.clearSelection?.()
  selectedRows.value = []
}

function clearFilters() {
  quickSearch.value = ''
  Object.keys(filters).forEach((key) => {
    filters[key] = ''
  })
  clearSelection()
}

function formatAmount(value) {
  const amount = Number(value)
  return Number.isFinite(amount) ? amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '0.00'
}

function csvEscape(value) {
  return `"${String(value ?? '').replaceAll('"', '""')}"`
}

function exportCurrentRows() {
  const headers = ['采购对账编号', '来源供应商结算单号', '来源应付核对单号', '供应商', '采购订单号', '结算金额', '差异金额', '采购对账状态', '当前能力边界']
  const csv = [headers.join(',')]
    .concat(filteredSortedRows.value.map((row) => headers.map((header) => {
      const map = {
        采购对账编号: row.reconciliationNo,
        来源供应商结算单号: row.sourceSettlementNo,
        来源应付核对单号: row.sourcePayableCheckNo,
        供应商: row.supplierName,
        采购订单号: row.purchaseOrderNo,
        结算金额: row.settlementAmount,
        差异金额: row.differenceAmount,
        采购对账状态: row.statusText,
        当前能力边界: row.boundaryText,
      }
      return csvEscape(map[header])
    }).join(',')))
    .join('\n')
  const blob = new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  const date = new Date().toISOString().slice(0, 10).replaceAll('-', '')
  link.href = URL.createObjectURL(blob)
  link.download = `purchase-reconciliations-${date}.csv`
  link.click()
  URL.revokeObjectURL(link.href)
}

function goSupplierSettlement(row) {
  router.push({ path: '/scm/supplier-settlements', query: { settlementNo: row.sourceSettlementNo } })
}

function goSourceSupplierSettlement() {
  router.push({ path: '/scm/supplier-settlements', query: { settlementNo: precheck.value.candidate.sourceSupplierSettlementNo } })
}

function goSourcePayableCheck() {
  router.push({ path: '/finance/payable-checks', query: { sourcePayableCheckNo: precheck.value.candidate.sourcePayableCheckNo } })
}

function showServerResult(row) {
  ElMessage.info(`服务端采购对账：${row.reconciliationNo}，状态：${row.statusText}，差异：${row.differenceCount}`)
}

function executeRegistryAction(action) {
  if (action.actionId === 'complete-purchase-reconciliation') {
    completeCheck(action.selectedRows[0])
    return
  }
  if (action.actionId === 'batch-complete-purchase-reconciliation') {
    Promise.all(action.selectedRows.map(row => completeCheck(row)))
  }
}

function invoicePrepareNavigation(row) {
  return evaluatePurchaseInvoicePrepareNavigation(row)
}

function goPurchaseInvoicePrepare(row) {
  const navigation = evaluatePurchaseInvoicePrepareNavigation(row)
  if (!navigation.allowed) {
    ElMessage.warning(navigation.reason)
    return
  }
  router.push(buildPurchaseInvoicePrepareRoute(row))
}

async function copyDiagnostics() {
  const diagnostics = {
    page: 'PurchaseReconciliationPage',
    version: VERSION,
    routePath: '/scm/purchase-reconciliations',
    source: 'server_purchase_reconciliation_api',
    resultCount: filteredSortedRows.value.length,
    selectedCount: selectedRows.value.length,
    filterState: { quickSearch: quickSearch.value, ...filters },
    sortState: { ...sortState.value },
    operationMode: 'server_read_model',
    strictFacts: { ...strictFacts },
    rawReconciliationStatuses: rows.value.map((row) => ({
      reconciliationNo: row.reconciliationNo,
      reconciliationStatus: row.reconciliationStatus,
      nextStepReadiness: row.nextStepReadiness,
      eligibility: row.invoicePrepareEligibility,
    })),
    purchaseInvoicePrepareNavigation: selectedRows.value.length === 1
      ? { ...selectedInvoicePrepareNavigation.value, route: buildPurchaseInvoicePrepareRoute(selectedRows.value[0]) }
      : { ...selectedInvoicePrepareNavigation.value },
    protectionFlags: {
      writeBusinessData: false,
      modifySupplierSettlement: false,
      modifyPayableCheck: false,
      generateInvoicePrepare: false,
      writeLedger: false,
      writeOffPayment: false,
      generateBankFlow: false,
    },
    timestamp: new Date().toISOString(),
  }
  await navigator.clipboard.writeText(JSON.stringify(diagnostics, null, 2))
  ElMessage.success('诊断数据已复制')
}
</script>

<style scoped>
.purchase-reconciliation-page {
  display: grid;
  gap: 12px;
  max-width: 100%;
  overflow-x: hidden;
}

.page-heading,
.table-card {
  border: 1px solid #d8e0ea;
  border-radius: 8px;
  background: #fff;
  padding: 14px;
}

.pre-generation-design {
  display: grid;
  gap: 12px;
}

.design-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
  padding: 12px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fbff;
}

.design-panel h3 {
  width: 100%;
  margin: 0 0 4px;
}

.design-table {
  display: block;
}

.page-heading {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.page-heading h2,
.page-heading p {
  margin: 0;
}

.eyebrow {
  color: #2563eb;
  font-size: 13px;
  font-weight: 800;
}

.page-note {
  margin-top: 6px;
  color: #475569;
  font-size: 13px;
  line-height: 1.6;
}

.table-card {
  display: grid;
  gap: 10px;
}

.standard-list-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  padding: 10px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fbff;
}

.toolbar-search-wrapper,
.toolbar-search {
  width: min(360px, 100%);
}

.advanced-filter-panel {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.advanced-filter-panel label {
  display: grid;
  gap: 5px;
  color: #334155;
  font-size: 12px;
  font-weight: 800;
}

.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.table-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: #475569;
  font-size: 13px;
}
</style>

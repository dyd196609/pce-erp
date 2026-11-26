<template>
  <main class="review-page" :data-review-type="reviewType" :data-fact-source="facts?.factSource || 'unavailable'">
    <el-alert :title="`${title}与${otherTitle}分别记录`" description="本表记录逐项意见和本人签认；正式提交只锁定送审版本，最终通过或不通过只由具备本模块最终审批权限的人独立决定。" type="info" :closable="false" show-icon />

    <section v-if="!isCrmReview && loadState === REVIEW_LOAD_STATES.SUCCESS" class="card" data-acceptance-id="pde-formal-order-identity">
      <template v-if="formalOrderReady">
        <h2>正式销售订单 {{ facts.orderContext.salesOrderNo }}</h2>
        <div class="fact-grid">
          <article><small>订单状态及版本</small><strong>{{ facts.orderContext.salesOrderStatusLabel }} · 版本 {{ facts.orderContext.salesOrderVersion }}</strong></article>
          <article><small>CRM来源编号</small><strong>{{ facts.orderContext.sourceOrderNo }}</strong></article>
          <article><small>来源及依据版本</small><strong>来源 {{ facts.orderContext.sourceRecordId }}／版本 {{ facts.orderContext.sourceVersion }}</strong></article>
          <article><small>当前PDE草稿</small><strong>{{ facts.review.draft ? `草稿 ${facts.review.draft.id}／评审 V${facts.review.draft.reviewVersion}` : '尚未保存草稿' }}</strong></article>
        </div>
        <el-table :data="facts.orderContext.applicableOrderItems" aria-label="本次评审适用的正式订单明细">
          <el-table-column prop="lineNo" label="订单行" width="90" />
          <el-table-column prop="materialCode" label="物料编码" min-width="180" />
          <el-table-column prop="materialName" label="物料名称" min-width="240" />
          <el-table-column prop="quantity" label="数量" width="120" />
          <el-table-column prop="unit" label="单位" width="90" />
        </el-table>
      </template>
      <el-alert v-else title="正式订单身份读取不完整，已停止保存。请重新读取并核对订单、来源和适用明细。" type="error" :closable="false" show-icon />
    </section>

    <section class="card guide-card" data-acceptance-id="review-operation-guide">
      <el-collapse>
        <el-collapse-item title="操作说明" name="operation-guide">
          <div class="guide-grid">
            <article><h3>本页用途</h3><p>{{ pagePurpose }}</p></article>
            <article><h3>开始条件</h3><p>从“业务流程中心”进入本节点，确认订单、客户、项目、工程来源及依据版本正确；系统按既有正式角色、事项权限、员工、账号和范围生成责任安排，普通参与人取得本人责任分配后才能维护和签认本人事项。</p></article>
            <article><h3>操作顺序</h3><ol><li>先核对系统自动责任安排；固定九项唯一合格人员会自动带入，不需要逐项重选。</li><li>新增其它评审事项无需先保存即可选择合法责任候选；选择只是准备，点击“保存草稿”后才形成本次责任和对象授权。</li><li>只处理“责任人待确定”或“缺少责任配置”的异常事项；需要补充依据时点击该行“补充说明”。</li><li>各责任人填写并保存本人意见后本人签认；准备人不能代替责任人签认，全部项目有效签认后再由有权人员正式提交。</li></ol></article>
            <article><h3>保存、签认、提交</h3><p>“保存草稿”只保存内容；选择“不同意”后须填写原因并先保存本人意见，随后可以本人签认。签认只确认当前账号关联员工本人负责的意见，不代表改成同意；“正式提交”锁定版本并进入待审批，不按同意人数、比例或是否存在不同意自动形成最终结论。</p></article>
            <article><h3>责任人办理</h3><p>有权准备人员保存责任人后，系统按评审对象和版本形成本人办理授权。普通参与人只可维护、保存和签认本人负责行；其他行保持只读。签认不同意意见不代表改成同意。</p></article>
            <article><h3>首次登录准备</h3><p>{{ facts?.submissionProcess?.firstLoginSetup?.statement }}如账号仍无可用密码，由账户管理员按“{{ facts?.submissionProcess?.firstLoginSetup?.administratorPath }}”办理；不得共享密码或由他人代登录。{{ facts?.submissionProcess?.firstLoginSetup?.completionRule }}</p></article>
            <article><h3>记录与后续</h3><p>已提交版本仍在本页完整显示。最终决定由具备本模块专门审批权限及合法范围的角色通过本页既有业务主线作出；未配置审批人时保持“待配置审批人／待审批”，系统不会自动选择管理员或其他人员。</p></article>
            <article><h3>条件不足</h3><p>页面下方“当前进度与下一步”会列出未完成项目、责任人账号衔接缺口和当前可执行动作。按钮不可用或操作失败时，以该区域的具体原因处理，页面不会清空已保存草稿。</p></article>
          </div>
        </el-collapse-item>
      </el-collapse>
    </section>

    <section v-if="loadState !== REVIEW_LOAD_STATES.SUCCESS" class="card load-state" data-acceptance-id="review-load-state">
      <h2>{{ loadPresentation.title }}</h2>
      <p>{{ loadPresentation.description }}</p>
      <div class="load-summary">
        <article><small>来源与订单</small><strong>{{ loadState === REVIEW_LOAD_STATES.LOADING ? '读取中' : '未取得' }}</strong></article>
        <article><small>固定评审项目</small><strong>—</strong></article>
        <article><small>历史与权限</small><strong>{{ loadState === REVIEW_LOAD_STATES.LOADING ? '读取中' : '未取得' }}</strong></article>
      </div>
      <p v-if="loadErrorCode" class="error-code">状态代码：{{ loadErrorCode }}</p>
      <div class="load-actions">
        <el-button :loading="loadState === REVIEW_LOAD_STATES.LOADING" @click="refresh">重新读取</el-button>
        <el-button v-if="loadState === REVIEW_LOAD_STATES.UNAUTHENTICATED" type="primary" @click="goToLogin">正常登录入口</el-button>
      </div>
    </section>

    <template v-if="loadState === REVIEW_LOAD_STATES.SUCCESS">

    <el-alert v-if="facts?.reviewAvailability?.statusCode === 'FORMAL_REVIEW_NOT_ESTABLISHED'" class="condition" type="warning" :closable="false" show-icon :title="facts.reviewAvailability.statusLabel" :description="facts.reviewAvailability.nextStep" />

    <section class="card" data-acceptance-id="review-source-context">
      <div class="heading"><div><h2>{{ title }}</h2><p>{{ facts?.review?.purpose }}</p></div><el-tag>{{ facts?.review?.template?.title }} · {{ facts?.review?.template?.version }}</el-tag></div>
      <div class="fact-grid">
        <article><small>{{ isCrmReview ? '来源订单' : 'CRM来源编号' }}</small><strong>{{ facts?.orderContext?.sourceOrderNo || '-' }}</strong></article>
        <article><small>客户</small><strong>{{ facts?.orderContext?.customer || '-' }}</strong></article>
        <article><small>项目</small><strong>{{ facts?.orderContext?.project || '-' }}</strong></article>
        <article><small>工程来源</small><strong>{{ facts?.source?.sourceName || '-' }}（{{ facts?.source?.sourceRowCount ?? '-' }}行）</strong></article>
        <article><small>依据版本</small><strong>{{ facts?.source?.sourceVersion || '-' }}</strong></article>
        <article><small>本类状态</small><strong>{{ facts?.review?.draft ? '草稿，评审未完成' : (facts?.approval?.statusLabel || facts?.review?.latest?.conclusionLabel || '尚无真实评审记录') }}</strong></article>
      </div>
      <el-table v-if="facts?.intakeSourceRows?.length" :data="facts.intakeSourceRows" aria-label="接单来源明细">
        <el-table-column prop="product" label="产品" />
        <el-table-column prop="component" label="部件" />
        <el-table-column prop="quantity" label="数量" />
        <el-table-column prop="unit" label="单位" />
      </el-table>
      <el-alert class="condition" :title="facts?.orderContext?.formalSalesOrderCondition || '正在读取正式订单条件'" type="warning" :closable="false" />
    </section>

    <section class="card progress-card" data-acceptance-id="review-progress-and-next-step">
      <div class="heading"><div><h2>当前进度与下一步</h2><p>以下状态来自服务端当前评审记录，不把责任人选择、汇总数字或按钮点击当作已经签认或提交。</p></div><el-tag :type="facts?.review?.latest && !facts?.review?.draft ? 'success' : 'warning'">{{ currentStatusLabel }}</el-tag></div>
      <el-alert v-if="errorMessage" :title="`操作未成功：${errorMessage}`" type="error" :closable="false" show-icon />
      <el-alert v-if="actionSuccessMessage" :title="actionSuccessMessage" type="success" :closable="false" show-icon />
      <div v-if="facts?.review?.latest && !facts?.review?.draft" class="submission-receipt">
        <strong>提交回执：评审记录 #{{ facts.review.latest.id }} · 版本 {{ facts.review.latest.reviewVersion }}</strong>
        <span>{{ facts.review.latest.statusLabel }}；{{ facts?.approval?.statusLabel || facts.review.latest.conclusionLabel }}；提交时间 {{ formatDateTime(facts.review.latest.executedAt) }}</span>
        <span>{{ facts?.submissionProcess?.postSubmitResult }}</span>
      </div>
      <template v-else>
        <p><strong>未完成事项：</strong>{{ serverIncompleteReasons.length ? serverIncompleteReasons.join('；') : '当前服务端没有未完成项。' }}</p>
        <p><strong>当前账号可签认：</strong>{{ currentUserSignableRows.length ? currentUserSignableRows.map(row => `${row.itemCode} ${row.itemText}`).join('；') : '没有本人负责且待签认的项目。' }}</p>
        <p><strong>责任人办理入口：</strong>{{ facts?.submissionProcess?.signatureEntry }}</p>
        <p v-if="blockedSignatureRows.length" class="denied"><strong>签认衔接缺口：</strong>{{ blockedSignatureRows.map(row => `${row.itemCode} ${row.responsibleEmployee?.name || '未指定责任人'}（${row.responsibleEmployee?.signatureRoutingBlock || '签认入口未就绪'}）`).join('；') }}。请按下方办理准备状态中的“仍缺条件”完成本人登录准备。</p>
        <p><strong>综合审批：</strong>{{ facts?.submissionProcess?.comprehensiveApprovalLabel }}。{{ facts?.submissionProcess?.postSubmitResult }}</p>
        <p v-if="facts?.submissionProcess?.legalSubmitterAvailable"><strong>正式提交人：</strong>{{ facts.submissionProcess.eligibleSubmitters.map(row => `${row.name}（${row.employeeNo}）／${row.username}`).join('；') }}。全部必要签认完成后，由上述合法提交人点击“正式提交评审”。</p>
        <p v-else class="denied"><strong>正式提交人：</strong>{{ facts?.submissionProcess?.submitterGap }} {{ facts?.submissionProcess?.minimumFutureApproval }}</p>
        <el-table v-if="(facts?.responsibleReadiness || []).length" :data="responsibleReadinessRows" row-key="employeeId" border class="readiness-table">
          <el-table-column v-if="isCrmReview" type="index" label="序号" width="72" />
          <el-table-column label="责任人" min-width="150"><template #default="{ row }">{{ row.name }}（{{ row.employeeNo }}）</template></el-table-column>
          <el-table-column prop="username" label="账号" min-width="170" />
          <el-table-column v-if="isCrmReview" prop="position" label="职务" min-width="140" />
          <el-table-column prop="loginPreparationStatusLabel" label="登录准备状态" min-width="240" />
          <el-table-column label="查看本评审" width="115"><template #default="{ row }">{{ row.canViewReview ? '可以' : '不可以' }}</template></el-table-column>
          <el-table-column label="本人意见" width="115"><template #default="{ row }">{{ row.canMaintainOwnOpinion ? '可以维护' : '不可维护' }}</template></el-table-column>
          <el-table-column label="本人签认" width="115"><template #default="{ row }">{{ row.canSignOwnItems ? '具备资格' : '不具备' }}</template></el-table-column>
          <el-table-column label="负责项目" min-width="130"><template #default="{ row }">{{ row.assignedItemCodes.join('、') }}</template></el-table-column>
          <el-table-column label="真实签认" width="105"><template #default="{ row }">{{ row.signedItemCount }}项</template></el-table-column>
          <el-table-column prop="identityNote" label="身份说明" min-width="300" />
          <el-table-column prop="remainingCondition" label="仍缺条件" min-width="220" />
        </el-table>
      </template>
    </section>

    <section v-if="facts?.review?.latest" class="card approval-card" data-acceptance-id="review-final-approval">
      <div class="heading"><div><h2>{{ title }}最终审批</h2><p>意见数量仅供参考；最终结果只来自具备专门动作权限和公司范围的审批人动作。当前登录：{{ facts?.currentActor?.employee?.name || facts?.currentActor?.username || '未识别' }}（{{ facts?.currentActor?.username || '未识别' }}）。</p></div><el-tag :type="facts?.approval?.finalDecision ? 'success' : 'warning'">{{ facts?.approval?.statusLabel }}</el-tag></div>
      <div class="fact-grid">
        <article><small>送审版本</small><strong>评审 V{{ facts.review.latest.reviewVersion }}／依据 {{ facts.review.latest.sourceVersion }}</strong></article>
        <article><small>意见统计</small><strong>{{ facts.review.latest.opinionSummaryLabel }}</strong></article>
        <article><small>已配置审批人</small><strong>{{ facts?.approval?.configuredApproverCount || 0 }} 人</strong></article>
        <article><small>当前审批人</small><strong>{{ (facts?.approval?.configuredApprovers || []).map(row => row.name || row.username).join('、') || '待配置' }}</strong></article>
        <article><small>最终决定</small><strong>{{ facts?.approval?.finalDecision?.decisionLabel || '尚无最终审批结论' }}</strong></article>
      </div>
      <p v-if="!facts?.approval?.configuredApproverCount" class="denied">尚未配置最终审批人。请由管理员在“组织结构 → 角色权限”把“{{ title }}—最终审批”授予经批准的正式角色，再在“用户账户”维护该角色及公司范围；系统不会自动授权管理员、提交人或参与人。</p>
      <div v-if="facts?.approval?.finalDecision" class="approval-receipt">
        <strong>{{ facts.approval.finalDecision.decisionLabel }} · {{ facts.approval.finalDecision.approver.name || facts.approval.finalDecision.approver.username }}</strong>
        <span>{{ formatDateTime(facts.approval.finalDecision.approvedAt) }}；审批意见：{{ facts.approval.finalDecision.approvalOpinion }}</span>
        <span v-if="facts.approval.finalDecision.riskHandling">风险处理：{{ facts.approval.finalDecision.riskHandling }}</span>
      </div>
      <div v-else-if="facts?.approval?.canCurrentUserApprove" class="approval-form">
        <el-input v-model="approvalOpinion" type="textarea" :rows="3" placeholder="请填写最终审批意见" />
        <el-input v-model="riskHandling" type="textarea" :rows="3" placeholder="决定与评审意见不一致时必须填写风险处理说明" />
        <div class="row-actions"><el-button type="success" :loading="saving" @click="finalApprove('APPROVE')">最终审批通过</el-button><el-button type="danger" :loading="saving" @click="finalApprove('REJECT')">最终审批不通过</el-button></div>
      </div>
      <p v-else-if="facts?.approval?.configuredApproverCount" class="muted">当前账号没有本版本最终审批资格；普通参与、本人签认或提交资格不会自动产生审批权。</p>
    </section>

    <section class="card" data-acceptance-id="itemized-review-table">
      <div class="heading"><div><h2>固定评审项目</h2><p>一行一个事项；判定初始为“请选择”，固定项目文字由服务端正式模板提供且不能删除或改写。</p></div></div>
      <div class="summary-grid">
        <article><small>总项目数</small><strong>{{ displaySummary.total }}</strong></article><article><small>同意数</small><strong>{{ displaySummary.agree }}</strong></article>
        <article><small>不同意数</small><strong>{{ displaySummary.disagree }}</strong></article><article><small>待判定数</small><strong>{{ displaySummary.pending }}</strong></article>
        <article><small>已签认数</small><strong>{{ displaySummary.signed }}</strong></article><article><small>意见状态</small><strong>{{ summaryLabel }}</strong></article>
      </div>
      <div v-if="facts?.responsibilityPlan?.visible" class="responsibility-plan" data-acceptance-id="pde-responsibility-plan">
        <div class="heading"><div><h3>系统责任安排</h3><p>保存前为“待保存”预览；正式保存后才形成当前评审版本的责任记录和对象授权。多候选或无候选只影响对应事项。</p></div><el-tag type="info">服务端正式配置匹配</el-tag></div>
        <div class="summary-grid">
          <article><small>自动确定</small><strong>{{ facts.responsibilityPlan.summary.automatic }}项</strong></article>
          <article><small>已有责任保留</small><strong>{{ facts.responsibilityPlan.summary.preserved }}项</strong></article>
          <article><small>多人待确定</small><strong>{{ facts.responsibilityPlan.summary.pendingMultiple }}项</strong></article>
          <article><small>缺少配置</small><strong>{{ facts.responsibilityPlan.summary.missing }}项</strong></article>
        </div>
      </div>
      <BusinessTableScrollContainer acceptance-id="business-table-scroll-order-review-fixed" :page-id="route.meta.pageCode" table-id="order-review-fixed-items" min-width="1500px">
        <PceResizableTable :data="fixedRows" row-key="stableKey" border class="review-table"
          :user-key="facts?.currentActor?.userId" :page-id="route.meta.pageCode" table-id="order-review-fixed-items">
          <el-table-column column-key="item-code" prop="itemCode" label="序号" width="76" fixed="left" />
          <el-table-column column-key="review-item" prop="itemText" label="评审事项" min-width="320" />
          <el-table-column column-key="decision" label="判定" width="180">
            <template #default="{ row }"><el-select v-model="row.decision" placeholder="请选择" :disabled="!canEditRow(row)"><el-option label="同意" value="AGREE"/><el-option label="不同意" value="DISAGREE"/></el-select></template>
          </el-table-column>
          <el-table-column column-key="disagreement-reason" label="不同意原因" min-width="280">
            <template #default="{ row }"><template v-if="row.decision === 'DISAGREE'"><el-select v-model="row.disagreementReasonCode" placeholder="请选择原因" :disabled="!canEditRow(row)"><el-option v-for="reason in reasonOptions" :key="reason" :label="reason" :value="reason"/></el-select><el-input v-if="row.disagreementReasonCode === '其它'" v-model="row.disagreementReasonText" placeholder="请填写具体说明" :disabled="!canEditRow(row)"/></template><span v-else class="muted">不适用</span></template>
          </el-table-column>
          <el-table-column column-key="responsible-employee" label="责任人" min-width="330">
            <template #default="{ row }"><div class="responsibility-cell">
              <employee-select v-model="row.responsibleEmployeeId" :employees="eligibleEmployeesFor(row)" :disabled="!canFullDraftEdit" />
              <strong v-if="isCrmReview && row.responsibleEmployee">{{ row.responsibleEmployee.name }}</strong>
              <small v-if="row.responsibilityMatch?.statusLabel"><strong>{{ row.responsibilityMatch.statusLabel }}</strong>；{{ row.responsibilityMatch.matchBasis }}</small>
              <small v-if="row.responsibilityMatch?.selected">{{ row.responsibilityMatch.selected.position }}；账号 {{ row.responsibilityMatch.selected.username || '未关联' }}</small>
              <el-input v-if="responsibilityChanged(row)" v-model="row.responsibilityChangeReason" placeholder="已有责任人调整原因（必填）" />
            </div></template>
          </el-table-column>
          <el-table-column column-key="signature-date" label="签认状态与日期" width="190"><template #default="{ row }"><signature-cell :row="row" /></template></el-table-column>
          <el-table-column column-key="actions" label="操作" width="230" fixed="right" class-name="payment-fixed-action-column" label-class-name="payment-fixed-action-column">
            <template #default="{ row }">
              <div class="row-actions">
                <el-popover placement="left" :width="380" trigger="click">
                  <template #reference><el-button link type="primary">补充说明</el-button></template>
                  <div class="evidence-popover"><strong>补充说明</strong><p>可引用合同、工程、成本或资源依据；留空不影响草稿保存。</p><el-input v-model="row.evidenceNote" type="textarea" :rows="4" placeholder="按需填写或引用依据" :disabled="!canEditRow(row)" /></div>
                </el-popover>
                <div class="sign-action"><el-checkbox v-model="row.selectedForSign" :disabled="!canActorSignRow(row)">选择本次签认</el-checkbox><small v-if="!canActorSignRow(row)">{{ signDisabledReason(row) }}</small></div>
              </div>
            </template>
          </el-table-column>
        </PceResizableTable>
      </BusinessTableScrollContainer>
    </section>

    <section class="card" data-acceptance-id="other-review-items">
      <div class="heading"><div><h2>其它评审事项</h2><p>默认没有必填空行；新增项无需先保存即可选择合法责任候选，正式保存后才形成本次责任与对象授权。</p></div><el-button type="primary" plain :disabled="!canFullDraftEdit" @click="addOther">添加其它评审项</el-button></div>
      <el-empty v-if="!otherRows.length" description="没有其它评审事项时，无需填写“无”或额外签认" />
      <BusinessTableScrollContainer v-else acceptance-id="business-table-scroll-order-review-other" :page-id="route.meta.pageCode" table-id="order-review-other-items" min-width="1560px">
        <PceResizableTable :data="otherRows" row-key="stableKey" border class="review-table"
          :user-key="facts?.currentActor?.userId" :page-id="route.meta.pageCode" table-id="order-review-other-items">
          <el-table-column column-key="item-code" label="序号" width="76" fixed="left"><template #default="{ $index }">{{ $index + 1 }}</template></el-table-column>
          <el-table-column column-key="review-item" label="具体评审内容" min-width="340"><template #default="{ row }"><el-input v-model="row.itemText" placeholder="一行填写一个可以单独判断的事项" :disabled="!canFullDraftEdit" /></template></el-table-column>
          <el-table-column column-key="decision" label="判定" width="180"><template #default="{ row }"><el-select v-model="row.decision" placeholder="请选择" :disabled="!canEditRow(row)"><el-option label="同意" value="AGREE"/><el-option label="不同意" value="DISAGREE"/></el-select></template></el-table-column>
          <el-table-column column-key="disagreement-reason" label="不同意原因" min-width="280"><template #default="{ row }"><template v-if="row.decision === 'DISAGREE'"><el-select v-model="row.disagreementReasonCode" placeholder="请选择原因" :disabled="!canEditRow(row)"><el-option v-for="reason in reasonOptions" :key="reason" :label="reason" :value="reason"/></el-select><el-input v-if="row.disagreementReasonCode === '其它'" v-model="row.disagreementReasonText" placeholder="请填写具体说明" :disabled="!canEditRow(row)"/></template><span v-else class="muted">不适用</span></template></el-table-column>
          <el-table-column column-key="responsible-employee" label="责任人" min-width="420"><template #default="{ row }"><div class="responsibility-cell"><employee-select v-model="row.responsibleEmployeeId" :employees="eligibleEmployeesFor(row)" :empty-text="responsibilityCandidateEmptyText(row)" :disabled="!canFullDraftEdit" /><small :class="responsibilityCandidateState(row).statusCode === 'AVAILABLE' ? 'candidate-ready' : 'candidate-blocked'">{{ responsibilityCandidateState(row).statusLabel }}</small><el-input v-if="responsibilityChanged(row)" v-model="row.responsibilityChangeReason" placeholder="已有责任人调整原因（必填）" /></div></template></el-table-column>
          <el-table-column column-key="signature-date" label="签认状态与日期" width="190"><template #default="{ row }"><signature-cell :row="row" /></template></el-table-column>
          <el-table-column column-key="actions" label="操作" width="240" fixed="right" class-name="payment-fixed-action-column" label-class-name="payment-fixed-action-column">
            <template #default="{ row, $index }"><div class="row-actions">
              <el-popover placement="left" :width="380" trigger="click"><template #reference><el-button link type="primary">补充说明</el-button></template><div class="evidence-popover"><strong>补充说明</strong><p>按需填写或引用依据；留空不影响草稿保存。</p><el-input v-model="row.evidenceNote" type="textarea" :rows="4" placeholder="按需填写或引用依据" :disabled="!canEditRow(row)" /></div></el-popover>
              <div class="sign-action"><el-checkbox v-model="row.selectedForSign" :disabled="!canActorSignRow(row)">选择本次签认</el-checkbox><small v-if="!canActorSignRow(row)">{{ signDisabledReason(row) }}</small></div><el-button link type="danger" :disabled="!canFullDraftEdit" @click="removeOther($index)">移除</el-button>
            </div></template>
          </el-table-column>
        </PceResizableTable>
      </BusinessTableScrollContainer>
    </section>

    <el-alert class="condition" type="info" :closable="false" title="办理顺序：填写判定及说明 → 保存草稿 → 服务端保存回读成功 → 选择本次签认 → 确认签认 → 回读签认结果；日常办理无需手动刷新。" />
    <div v-if="readbackPending" class="card"><el-alert :title="errorMessage" type="warning" :closable="false" /><el-button :loading="saving" @click="retryActionReadback">只读重试状态回读</el-button></div>
    <section class="card actions" data-acceptance-id="review-actions">
      <el-button :type="isCrmReview ? 'primary' : 'default'" :loading="saving" :disabled="!canWrite" @click="saveDraft">保存草稿</el-button>
      <el-button type="primary" plain :loading="saving" :disabled="saving || confirmingSign || readbackPending || !selectedSignableCount" @click="signSelected">确认签认所选项目</el-button>
      <el-button type="primary" :loading="saving" :disabled="!canSubmit" @click="submitReview">正式提交评审</el-button>
      <p v-if="!canWrite && !canSign" class="denied">当前身份不可维护本人意见或签认：{{ facts?.authorization?.saveReason }}</p>
      <p v-else-if="!canSubmit" class="denied">“正式提交评审”暂不可执行：{{ submitDisabledReason }}</p>
      <p v-else class="muted">全部项目已有效签认；正式提交将锁定本版本意见快照并进入待审批，不自动产生最终结论。</p>
    </section>

    <section class="card" data-acceptance-id="independent-review-history"><h2>{{ title }}历史</h2>
      <el-collapse>
        <el-collapse-item :title="`历史记录（${(facts?.review?.history || []).length}）`" name="history">
          <el-empty v-if="!(facts?.review?.history || []).length" description="尚无更早的已提交版本" />
          <el-table v-else :data="facts.review.history" row-key="id"><el-table-column prop="reviewVersion" label="版本" width="80"/><el-table-column prop="opinionSummaryLabel" label="意见统计" width="180"/><el-table-column prop="approval.statusLabel" label="审批状态／最终决定" min-width="210"/><el-table-column prop="reviewer.name" label="提交人" width="120"/><el-table-column prop="executedAt" label="提交时间" width="210"/><el-table-column prop="sourceVersion" label="依据版本"/><el-table-column prop="templateVersion" label="模板版本" width="120"/></el-table>
        </el-collapse-item>
      </el-collapse>
      <div class="cross-feedback"><h3>{{ otherTitle }}反馈（只读）</h3><p v-if="facts?.crossReviewFeedback">{{ facts.crossReviewFeedback.conclusionLabel }}；不会改变本页状态。</p><p v-else>尚无另一类已提交评审结论；本页不会代填或推断。</p></div>
    </section>
    </template>
  </main>
</template>

<script setup>
import { computed, defineComponent, h, inject, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElButton, ElMessage, ElMessageBox, ElOption, ElSelect } from 'element-plus'
import { salesApi } from '@/api/sales.js'; import { pdeApi } from '@/api/pde.js'
import BusinessTableScrollContainer from '@/meta/components/BusinessTableScrollContainer.vue'
import PceResizableTable from '@/meta/components/PceResizableTable.vue'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { REVIEW_LOAD_STATES, classifyOrderReviewFailure, reviewLoadPresentation, validateOrderReviewFacts } from '@/meta/runtime/orderReviewLoadState.js'
import { normalizeResponsibleEmployeeId } from '@/meta/runtime/orderReviewDraftControls.js'
import { createReviewOperation } from '@/meta/runtime/orderReviewOperation.js'

const EmployeeSelect = defineComponent({ props: { modelValue: [Number,String], employees: Array, disabled: Boolean, emptyText: String }, emits: ['update:modelValue'], setup(props,{emit}) { const update=value=>emit('update:modelValue',normalizeResponsibleEmployeeId(value)); return () => h('div',{class:'employee-select-control'},[h(ElSelect,{modelValue:props.modelValue,placeholder:'请选择正式员工',noDataText:props.emptyText||'未找到符合条件的责任人',filterable:true,clearable:true,disabled:props.disabled,onClear:()=>update(null),'onUpdate:modelValue':update},()=> (props.employees||[]).map(e=>h(ElOption,{label:`${e.name}（${e.employeeNo}；${e.department}／${e.position}）`,value:e.id,key:e.id}))),props.modelValue!==null&&props.modelValue!==undefined&&props.modelValue!==''?h(ElButton,{link:true,type:'primary',title:'清空',disabled:props.disabled,onClick:()=>update(null)},()=> '清空'):null]) } })
const SignatureCell = defineComponent({ props:{row:Object}, setup(props){return()=>h('div',{class:'signature'},[h('strong',props.row.signatureStatusLabel||'未签认'),props.row.signedEmployee?h('small',`${props.row.signedEmployee.name}（${props.row.signedEmployee.employeeNo}）`):null,props.row.signedAt?h('small',new Date(props.row.signedAt).toLocaleString()):null])} })
const emit = defineEmits(['reviewOrderContext'])
const route=useRoute(); const router=useRouter(); const reviewType=computed(()=>route.meta.reviewType); const title=computed(()=>reviewType.value==='CRM_ORDER_REVIEW'?'订单评审':'生产可行性评审'); const otherTitle=computed(()=>reviewType.value==='CRM_ORDER_REVIEW'?'生产可行性评审':'订单评审')
const facts=ref(null), fixedRows=ref([]), otherRows=ref([]), errorMessage=ref(''), actionSuccessMessage=ref(''), saving=ref(false), approvalOpinion=ref(''), riskHandling=ref(''); const observability=inject(PAGE_OBSERVABILITY_ACTIONS_KEY,null)
const loadState=ref(REVIEW_LOAD_STATES.IDLE), loadErrorCode=ref(''), loadMessage=ref(''); let requestSequence=0
const readbackPending=ref(false), confirmingSign=ref(false)
const selectedSignableCount=computed(()=>allRows.value.filter(row=>row.selectedForSign && canActorSignRow(row)).length)
const loadPresentation=computed(()=>reviewLoadPresentation(loadState.value,loadMessage.value))
const reasonOptions=computed(()=>facts.value?.reasonOptions||[])
const formalOrderReady=computed(()=>{
  const context=facts.value?.orderContext
  return context?.formalContextResolved===true && Boolean(context.salesOrderId && context.crmOrderRelationId && context.salesOrderNo && context.salesOrderVersion && context.applicableOrderItems?.length)
})
const identityAllowsWrite=computed(()=>isCrmReview.value || formalOrderReady.value)
const canWrite=computed(()=>!saving.value && !readbackPending.value && identityAllowsWrite.value && facts.value?.authorization?.draftEdit?.executable===true)
const canFullDraftEdit=computed(()=>!saving.value && !readbackPending.value && identityAllowsWrite.value && facts.value?.authorization?.fullDraftEdit?.executable===true)
const canSign=computed(()=>facts.value?.authorization?.sign?.executable===true)
const pagePurpose=computed(()=>reviewType.value==='CRM_ORDER_REVIEW'?'记录客户要求、报价、成本效益、交期与履约风险等逐项意见和本人签认；本表不按票数自动形成最终结论。':'核对实现计划、工艺、材料、人员技能、设备与资源条件，形成当前能否实现及需补齐哪些条件的独立结论。')
const allRows=computed(()=>[...fixedRows.value,...otherRows.value.filter(r=>String(r.itemText||'').trim())])
const displaySummary=computed(()=>({total:allRows.value.length,agree:allRows.value.filter(r=>r.decision==='AGREE').length,disagree:allRows.value.filter(r=>r.decision==='DISAGREE').length,pending:allRows.value.filter(r=>!r.decision).length,signed:allRows.value.filter(r=>r.signatureStatus==='SIGNED').length}))
const summaryLabel=computed(()=>displaySummary.value.pending?'意见未完成':(displaySummary.value.disagree?'含不同意意见，仅供最终审批参考':'意见已完整，仅供最终审批参考'))
const serverIncompleteReasons=computed(()=>facts.value?.review?.draftSummary?.incompleteReasons||['尚未保存草稿'])
const serverDraftRows=computed(()=>facts.value?.review?.draftItems||[])
const isCrmReview = computed(() => route.meta.pageCode === 'crm-order-reviews')
const responsibleReadinessRows = computed(() => {
  const rows = facts.value?.responsibleReadiness || []
  if (!isCrmReview.value) return rows

  const itemOrder = new Map(serverDraftRows.value.map((item, index) => [item.itemCode, index]))
  const rank = code => itemOrder.get(code) ?? Infinity
  return rows
    .map(row => ({
      ...row,
      position: facts.value?.employees?.find(employee => employee.id === row.employeeId)?.position || "—",
      assignedItemCodes: [...row.assignedItemCodes].sort((a, b) => rank(a) - rank(b)),
    }))
    .sort((a, b) => rank(a.assignedItemCodes[0]) - rank(b.assignedItemCodes[0]))
})
const currentUserSignableRows=computed(()=>serverDraftRows.value.filter(row=>row.signingReadiness?.executable&&row.signatureStatus!=='SIGNED'))
const blockedSignatureRows=computed(()=>serverDraftRows.value.filter(row=>row.signatureStatus!=='SIGNED'&&row.responsibleEmployee&&!row.responsibleEmployee.signatureEntryReady))
const currentStatusLabel=computed(()=>facts.value?.review?.draft?'草稿，尚未提交':(facts.value?.review?.latest?`${facts.value.review.latest.statusLabel} · ${facts.value?.approval?.statusLabel || facts.value.review.latest.conclusionLabel}`:'尚无真实评审记录'))
const canSubmit=computed(()=>facts.value?.authorization?.submit?.executable===true&&Boolean(facts.value?.review?.draft)&&facts.value?.review?.draftSummary?.complete===true)
const submitDisabledReason=computed(()=>{if(!facts.value?.review?.draft)return facts.value?.review?.latest?'当前版本已经提交，请在最终审批区办理；不得重复保存或提交。':'尚无可提交草稿';const reasons=serverIncompleteReasons.value;if(reasons.length)return reasons.slice(0,5).join('；');return'服务端尚未确认全部项目有效签认'})
function opinionFingerprint(row){return JSON.stringify([row.evidenceNote||'',row.decision||'',row.disagreementReasonCode||'',row.disagreementReasonText||''])}
function normalize(row){return {...row,selectedForSign:false,reasonOptions:row.reasonOptions||reasonOptions.value,originalResponsibleEmployeeId:row.responsibleEmployeeId??null,persistedOpinionFingerprint:opinionFingerprint(row),responsibilityChangeReason:''}}
function canEditRow(row){return canFullDraftEdit.value||(canWrite.value&&row.canCurrentUserEdit===true)}
function responsibilityChanged(row){return row.id&&Number(row.originalResponsibleEmployeeId||0)!==Number(row.responsibleEmployeeId||0)}
function rowHasUnsavedOpinion(row){return Boolean(row.id)&&row.persistedOpinionFingerprint!==opinionFingerprint(row)}
function canActorSignRow(row){return !saving.value&&!readbackPending.value&&canSign.value&&row?.signingReadiness?.executable===true&&!rowHasUnsavedOpinion(row)&&row.signatureStatus!=='SIGNED'}
function signDisabledReason(row){if(rowHasUnsavedOpinion(row))return row.decision==='DISAGREE'?'请先填写不同意原因并保存本人意见；保存后可签认不同意意见。':'请先保存本人意见。';if(!row.id)return'请先保存为正式评审项目。';return row?.signingReadiness?.disabledReason||facts.value?.authorization?.sign?.disabledReason||'当前评审或版本不允许签认。'}
function responsibilityCandidateState(row){if(reviewType.value!=='PDE_PRODUCTION_FEASIBILITY')return{statusCode:'AVAILABLE',statusLabel:'按当前模块既有责任规则选择'};if(row.itemKind==='OTHER'&&!row.id){const state=facts.value?.otherResponsibilityCandidates;if(!state)return{statusCode:'READ_FAILED',statusLabel:'责任人候选读取失败'};if(state.statusCode==='NO_ELIGIBLE_CANDIDATES'&&state.noCandidateReason)return{...state,statusLabel:`未找到符合条件的责任人：${state.noCandidateReason}`};if(state.statusCode==='SELECTION_PERMISSION_DENIED'&&state.disabledReason)return{...state,statusLabel:state.disabledReason};return state}const count=(row.eligibleEmployeeIds||[]).length;return count?{statusCode:'AVAILABLE',statusLabel:`已取得 ${count} 名符合条件的正式责任候选`}:{statusCode:'NO_ELIGIBLE_CANDIDATES',statusLabel:'未找到符合条件的责任人'}}
function responsibilityCandidateEmptyText(row){const state=responsibilityCandidateState(row);if(state.statusCode==='SELECTION_PERMISSION_DENIED')return'当前身份没有责任选择资格';if(state.statusCode==='READ_FAILED')return'责任人候选读取失败';return'未找到符合条件的责任人'}
function eligibleEmployeesFor(row){const all=facts.value?.employees||[];if(reviewType.value!=='PDE_PRODUCTION_FEASIBILITY')return all;const sourceIds=row.itemKind==='OTHER'&&!row.id?(facts.value?.otherResponsibilityCandidates?.eligibleEmployeeIds||[]):(row.eligibleEmployeeIds||[]);const allowed=new Set(sourceIds.map(Number));if(row.responsibleEmployeeId)allowed.add(Number(row.responsibleEmployeeId));return all.filter(employee=>allowed.has(Number(employee.id)))}
function formatDateTime(value){return value?new Date(value).toLocaleString():'—'}
function bindRows(){const displayed=facts.value?.review?.displayItems||[]; const source=displayed.length?displayed:facts.value?.review?.templateItems||[]; fixedRows.value=source.filter(r=>r.itemKind==='FIXED').map(normalize); otherRows.value=source.filter(r=>r.itemKind==='OTHER').map(normalize)}
function diagnostics(){return {canonicalName:title.value,moduleCode:route.meta.moduleCode,factSource:facts.value?.factSource||'unavailable',reviewType:reviewType.value,loadState:loadState.value,loadErrorCode:loadErrorCode.value,currentActor:facts.value?.currentActor||null,source:facts.value?.source||null,orderContext:facts.value?.orderContext||null,currentDraft:facts.value?.review?.draft||null,template:facts.value?.review?.template||null,draftSummary:facts.value?.review?.draftSummary||null,latestOwnReview:facts.value?.review?.latest||null,approval:facts.value?.approval||null,crossReviewFeedback:facts.value?.crossReviewFeedback||null,separationFacts:facts.value?.separationFacts||null}}
function publish(){if(isCrmReview.value)emit('reviewOrderContext',facts.value?.orderContext?.formalSalesOrderNo || facts.value?.orderContext?.sourceOrderNo || '');window.__PCE_BUSINESS_PAGE_ACCEPTANCE__={pageCode:route.meta.pageCode,moduleCode:route.meta.moduleCode,factSource:facts.value?.factSource||'unavailable',strictFacts:diagnostics(),pageAssertions:[{rule:'REVIEW-LOAD-STATE-EXPLICIT',passed:loadState.value!==REVIEW_LOAD_STATES.IDLE},{rule:'REVIEW-SERVER-TEMPLATE',passed:loadState.value===REVIEW_LOAD_STATES.SUCCESS&&facts.value?.separationFacts?.serverTemplateAuthority===true},{rule:'REVIEW-NO-AUTO-DECISION',passed:loadState.value===REVIEW_LOAD_STATES.SUCCESS&&facts.value?.separationFacts?.noAutomaticDecision===true},{rule:'REVIEW-OTHER-SECTION',passed:loadState.value===REVIEW_LOAD_STATES.SUCCESS}]}}
function clearLoadedFacts(){facts.value=null;fixedRows.value=[];otherRows.value=[]}
async function refresh(){
  if(saving.value || readbackPending.value)return
  if(allRows.value.some(rowHasUnsavedOpinion)){
    try{await ElMessageBox.confirm('有尚未保存的输入。重新读取会丢弃这些输入，请先复制需要保留的内容。是否继续？','核对未保存内容',{type:'warning'})}catch{return}
  }
  const sequence=++requestSequence; clearLoadedFacts(); errorMessage.value=''; actionSuccessMessage.value=''; loadErrorCode.value=''; loadMessage.value=''; loadState.value=REVIEW_LOAD_STATES.LOADING; publish()
  let response
  try { response=reviewType.value==='CRM_ORDER_REVIEW'?await salesApi.orderReview(route.query.sourceRecord||undefined):await pdeApi.productionFeasibilityReview(route.query.sourceRecord||undefined, { salesOrderId: route.query.salesOrderId, crmOrderRelationId: route.query.crmOrderRelationId }) }
  catch(error){ response={success:false,error:{code:error?.code||'REVIEW_READ_FAILED',message:error?.message||`${title.value}服务端事实读取失败`}} }
  if(sequence!==requestSequence)return
  if(!response?.success){const failure=classifyOrderReviewFailure(response);loadState.value=failure.state;loadErrorCode.value=failure.code;loadMessage.value=failure.message;publish();return}
  const schemaError=validateOrderReviewFacts(response.data)
  if(schemaError){loadState.value=REVIEW_LOAD_STATES.RESPONSE_ERROR;loadErrorCode.value='REVIEW_RESPONSE_INVALID';loadMessage.value=schemaError;publish();return}
  facts.value=response.data;bindRows();loadState.value=REVIEW_LOAD_STATES.SUCCESS;publish()
}
function goToLogin(){router.push({path:'/system-login',query:{redirect:route.fullPath,reason:'review-read-required'}})}
function addOther(){otherRows.value.push(normalize({stableKey:`OTHER-NEW-${Date.now()}-${otherRows.value.length}`,itemKind:'OTHER',itemCode:'',itemText:'',evidenceNote:'',decision:'',disagreementReasonCode:'',disagreementReasonText:'',responsibleEmployeeId:null,signatureStatus:'UNSIGNED',signatureStatusLabel:'未签认',signingReadiness:{statusCode:'UNSAVED_ITEM',statusLabel:'尚未保存',executable:false,disabledReason:'请先保存为正式评审项目。'},signedAt:null}))}
async function removeOther(index){const row=otherRows.value[index]; if(row.id&&(row.decision==='DISAGREE'||row.signatureStatus==='SIGNED')) await ElMessageBox.confirm('该项目已有负面判定或签认，移除后服务端仍保留变更历史。是否继续？','保留历史的移除',{type:'warning'}); otherRows.value.splice(index,1)}
function basePayload(action){return {action,sourceRecord:facts.value.source.id,reviewId:facts.value.review.draft?.id||null,expectedSourceVersion:facts.value.source.sourceVersion,expectedContentHash:facts.value.source.contentHash,expectedTemplateVersion:facts.value.review.template.version}}
function validateActionReadback(data,payload){
  const schemaError=validateOrderReviewFacts(data);if(schemaError)return schemaError
  if(payload.action==='saveDraft'){
    const saved=data.review?.draftItems||[]
    const fields=['evidenceNote','decision','disagreementReasonCode','disagreementReasonText']
    if((payload.reviewId && Number(data.review?.draft?.id)!==Number(payload.reviewId)) || !(payload.items||[]).every(row=>{const persisted=saved.find(item=>item.stableKey===row.stableKey);return persisted && fields.every(field=>String(persisted[field]||'').trim()===String(row[field]||'').trim())}))return '保存内容与服务端回读不一致，请重新核对'
  }
  if(payload.action==='signItems' && !(payload.itemIds||[]).every(id=>data.review?.draftItems?.some(row=>row.id===id && row.signatureStatus==='SIGNED' && row.signedAt)))return '本次签认记录未完整读回'
  return ''
}
async function readActionFacts(payload){
  return reviewType.value==='CRM_ORDER_REVIEW'?salesApi.orderReview(payload.sourceRecord):pdeApi.productionFeasibilityReview(payload.sourceRecord,{salesOrderId:payload.salesOrderId,crmOrderRelationId:payload.crmOrderRelationId})
}
const operation=createReviewOperation({
  write:payload=>{const key=`${reviewType.value}-${payload.action}-${Date.now()}`;return reviewType.value==='CRM_ORDER_REVIEW'?salesApi.orderReviewAction(payload,key):pdeApi.productionFeasibilityReviewAction(payload,key)},
  read:readActionFacts,validate:validateActionReadback,
  onBusy:value=>{saving.value=value},onPending:value=>{readbackPending.value=Boolean(value)},onError:message=>{errorMessage.value=message},
  onReadback:(data,payload)=>{facts.value=data;bindRows();loadState.value=REVIEW_LOAD_STATES.SUCCESS;errorMessage.value='';actionSuccessMessage.value=payload.action==='signItems'?'本人所选项目签认成功，签认人、时间及汇总已回读':'保存成功，服务端内容及办理资格已回读';publish()},
})
async function act(payload){
  if(saving.value || readbackPending.value)return false
  if(!identityAllowsWrite.value){errorMessage.value='正式订单身份未确认，已停止保存。';return false}
  if(reviewType.value==='PDE_PRODUCTION_FEASIBILITY')payload={...payload,salesOrderId:facts.value.orderContext.salesOrderId,crmOrderRelationId:facts.value.orderContext.crmOrderRelationId}
  ++requestSequence;errorMessage.value='';actionSuccessMessage.value=''
  return operation.run(payload)
}
async function retryActionReadback(){await operation.retryReadback()}
async function saveDraft(){
  const ownOnly=!canFullDraftEdit.value
  const selected=ownOnly?allRows.value.filter(row=>row.canCurrentUserEdit===true):allRows.value
  const items=selected.map(({selectedForSign,reasonOptions,originalResponsibleEmployeeId,persistedOpinionFingerprint,...r})=>r)
  const ok=await act({...basePayload('saveDraft'),ownOpinionOnly:ownOnly,items})
  if(ok){actionSuccessMessage.value=ownOnly?'本人意见已保存并完成服务端回读；未自动签认':'草稿、责任安排及精确对象授权已保存并完成服务端回读；未自动评审或签认';ElMessage.success(actionSuccessMessage.value)}
}
async function signSelected(){
  if(saving.value || confirmingSign.value || readbackPending.value)return
  const selected=allRows.value.filter(row=>row.selectedForSign && row.id && canActorSignRow(row))
  if(!selected.length){errorMessage.value='请先保存本人判定，再选择本次签认项目。';return}
  confirmingSign.value=true
  try{await ElMessageBox.confirm(`确认以本人身份签认 ${selected.map(row=>row.itemCode).join('、')} 项？签认记录将保存本人姓名和服务端时间。`,'确认本人签认',{type:'warning'})}catch{return}finally{confirmingSign.value=false}
  const ok=await act({...basePayload('signItems'),itemIds:selected.map(row=>row.id),expectedItemRevisions:Object.fromEntries(selected.map(row=>[row.id,row.contentRevision]))})
  if(ok)ElMessage.success('本人所选项目已签认，签认人、时间及汇总已回读')
}
async function submitReview(){await ElMessageBox.confirm('正式提交后本版本不可原地修改；提交只锁定意见快照并进入待审批，不自动形成最终结论。','确认正式提交',{type:'warning'});const ok=await act(basePayload('submitReview'));if(ok){const latest=facts.value?.review?.latest;actionSuccessMessage.value=latest?`提交成功：评审记录 #${latest.id}，版本 ${latest.reviewVersion}，状态“${facts.value?.approval?.statusLabel || '待审批'}”。`:'评审已提交，待审批。';ElMessage.success('评审已提交，待审批')}}
async function finalApprove(decision){const label=decision==='APPROVE'?'通过':'不通过';await ElMessageBox.confirm(`确认对当前明确版本作出最终“${label}”决定？原始评审意见和签认不会被改写。`,'确认最终审批',{type:'warning'});const latest=facts.value?.review?.latest;const prefix=reviewType.value==='CRM_ORDER_REVIEW'?'CRM-OR':'PDE-PFR';const ok=await act({action:'finalApprove',sourceRecord:facts.value.source.id,reviewId:latest.id,expectedReviewVersion:latest.reviewVersion,expectedSourceVersion:latest.sourceVersion,decision,approvalOpinion:approvalOpinion.value,riskHandling:riskHandling.value,actionId:`${prefix}-FINAL-${latest.id}-V${latest.reviewVersion}-${Date.now()}`});if(ok){actionSuccessMessage.value=`最终审批已记录为“${label}”；原始意见与签认保持不变。`;ElMessage.success(`最终审批：${label}`)}}
function handleAuthenticationChanged(event){
  requestSequence+=1;operation.invalidate();clearLoadedFacts();approvalOpinion.value='';riskHandling.value=''
  if(!event?.detail?.authenticated){loadState.value=REVIEW_LOAD_STATES.UNAUTHENTICATED;loadErrorCode.value='AUTH_REQUIRED';loadMessage.value='当前标签页已退出登录，请重新登录。';publish();return}
  refresh()
}
watch(()=>route.fullPath,()=>{++requestSequence;operation.invalidate();refresh()})
let provider;onMounted(async()=>{window.addEventListener('pce:authentication-changed',handleAuthenticationChanged);provider={factOwner:route.meta.pageCode,refresh,buildDiagnostics:diagnostics};observability?.register?.(provider);await refresh();observability?.register?.(provider)});onBeforeUnmount(()=>{requestSequence+=1;operation.invalidate();window.removeEventListener('pce:authentication-changed',handleAuthenticationChanged);observability?.unregister?.(provider)})
</script>
<style scoped>
.review-page{display:grid;gap:18px;padding:20px;background:#f4f7fb;min-width:0}.card{padding:20px;border:1px solid #dce4ed;border-radius:12px;background:#fff;min-width:0}.card h2{margin:0 0 6px}.heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.heading p{margin:4px 0 14px;color:#64748b}.fact-grid,.summary-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}.fact-grid article,.summary-grid article{display:grid;gap:5px;padding:12px;border-radius:9px;background:#f5f8fb}.fact-grid small,.summary-grid small,.signature small{color:#64748b}.condition{margin-top:14px}.review-table{width:100%}.review-table :deep(.el-select){width:100%}.review-table :deep(.el-input){margin-bottom:6px}.signature{display:grid;gap:4px;min-width:140px}.employee-select-control{display:flex;align-items:center;gap:6px;min-width:300px}.employee-select-control :deep(.el-select){min-width:235px}.row-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.evidence-popover{display:grid;gap:8px}.evidence-popover p{margin:0;color:#64748b}.actions{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.denied{color:#b45309}.muted{color:#64748b}.cross-feedback{margin-top:18px;padding:14px;border-left:4px solid #60a5fa;background:#eff6ff}
.load-state p{margin:8px 0 16px;color:#475569}.load-summary{display:grid;grid-template-columns:repeat(3,minmax(150px,1fr));gap:10px}.load-summary article{display:grid;gap:5px;padding:12px;border-radius:9px;background:#f5f8fb}.load-summary small{color:#64748b}.load-actions{display:flex;gap:10px;margin-top:16px}.error-code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;color:#991b1b!important}
.guide-card :deep(.el-collapse){border:0}.guide-card :deep(.el-collapse-item__header){height:auto;min-height:42px;font-size:18px;font-weight:700;border:0}.guide-card :deep(.el-collapse-item__wrap){border:0}.guide-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}.guide-grid article{padding:14px;border-radius:9px;background:#f5f8fb}.guide-grid h3{margin:0 0 8px}.guide-grid p,.guide-grid ol{margin:0;color:#475569;line-height:1.7}.guide-grid ol{padding-left:20px}.progress-card{display:grid;gap:10px}.progress-card p{margin:0;line-height:1.65}.submission-receipt{display:grid;gap:6px;padding:14px;border-radius:9px;background:#ecfdf5;color:#166534}.approval-card,.approval-form,.approval-receipt{display:grid;gap:12px}.approval-receipt{padding:14px;border-radius:9px;background:#ecfdf5;color:#166534}
.responsibility-plan{display:grid;gap:10px;margin:14px 0;padding:14px;border-radius:9px;background:#eff6ff}.responsibility-cell{display:grid;gap:6px}.responsibility-cell small{color:#475569;line-height:1.5}.candidate-ready{color:#166534!important}.candidate-blocked{color:#b45309!important}.sign-action{display:grid;gap:2px;max-width:155px}.sign-action small{color:#64748b;line-height:1.35}
</style>

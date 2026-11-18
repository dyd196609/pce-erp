<template>
  <main class="planning-page" :data-fact-load-status="factLoadStatus">
    <FormalProductionSchedulingPanel v-if="route.query.section === 'formal-scheduling'" :plans="productionPlanOptions" :parent-loading="loading || !factsAvailable" />
    <ProductionWorkOrderReceptionPanel v-if="route.query.section === 'work-order-reception'" :plans="productionPlanOptions" :parent-loading="loading || !factsAvailable" :planning-read-denied="planningReadDenied" />
    <section class="planning-hero">
      <div>
        <p class="eyebrow">ORDER PLANNING CHAIN / V1</p>
        <h1>订单计划工作台</h1>
        <p>订单 → 制造准备 → 计划需求 → 主生产计划建议 → 物料需求建议。</p>
      </div>
      <div class="hero-actions">
        <el-button @click="$router.push('/process-center')">返回业务流程中心</el-button>
        <el-button :loading="loading" @click="loadFacts">刷新</el-button>
        <el-button v-if="capabilities.canGenerateMps" type="primary" :loading="runningMps" @click="generateMps">生成 MPS 建议</el-button>
        <el-button v-if="capabilities.canPlan" type="primary" @click="dialogVisible = true">新增人工计划需求</el-button>
      </div>
    </section>

    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      show-icon
      :closable="false"
      class="block"
    />
    <el-alert
      v-if="planningSchema.status && !planningSchema.deployed"
      :title="`订单计划扩展 Schema：${planningSchema.status}；缺失表：${planningSchema.missingTables?.join('、') || '状态读取失败'}`"
      type="warning"
      show-icon
      :closable="false"
      class="block"
    />

    <section class="fact-grid block">
      <article><span>需求总数</span><strong>{{ factCount(demands.length) }}</strong></article>
      <article><span>已计算计划需求</span><strong>{{ factCount(requirements.length) }}</strong></article>
      <article><span>已生成供应计划</span><strong>{{ factCount(plannedCount) }}</strong></article>
      <article><span>MPS 建议批次</span><strong>{{ planningSchema.deployed ? factCount(mpsRuns.length) : '未部署' }}</strong></article>
      <article><span>MRP 建议批次</span><strong>{{ planningSchema.deployed ? factCount(mrpRuns.length) : '未部署' }}</strong></article>
      <article><span>库存写入</span><strong>{{ factCount(apiFacts.inventoryWriteCount) }}</strong></article>
    </section>

    <section v-if="!factsAvailable" class="panel block unavailable-facts" data-fact-load-result="unavailable">
      <strong>未取得计划数据</strong>
      <p>需求、计划和审计数量均为未知；下方空表不能解释为权威数据源确实为 0 条。</p>
    </section>

    <ProductionMaterialDemandPanel :plans="productionPlanOptions" :demands="demands" :parent-loading="loading || !factsAvailable" @refresh="loadFacts" />

    <section class="panel block">
      <div class="panel-heading">
        <div><h2>订单计划需求</h2><p>仅显示来自正式销售订单且保留订单行、客户、交期、工程模式和制造准备血缘的需求。</p><small v-if="route.query.orderNo">当前订单：{{ route.query.orderNo }}；共 {{ orderDemands.length }} 条有效需求</small></div>
      </div>
      <el-table :data="orderDemands" border empty-text="暂无已生成的订单计划需求">
        <el-table-column prop="demandNo" label="需求编号" min-width="150" fixed>
          <template #default="{ row }">
            <span>{{ row.demandNo }}</span><br />
            <button v-if="row.salesOrderItemId" type="button" class="m09-line-button" @click="openM09Line(row)">查看批次与范围</button>
          </template>
        </el-table-column>
        <el-table-column prop="salesOrderNo" label="销售订单编号" min-width="155">
          <template #default="scope"><el-button link type="primary" @click="openOrder(scope.row)">{{ scope.row.salesOrderNo }}</el-button></template>
        </el-table-column>
        <el-table-column prop="salesOrderItemId" label="订单行ID" width="100" />
        <el-table-column prop="customerName" label="客户" min-width="140" />
        <el-table-column prop="materialCode" label="物料编码" min-width="130" />
        <el-table-column prop="requiredQty" label="需求数量" width="105" />
        <el-table-column prop="uomCode" label="计量单位" width="80" />
        <el-table-column prop="effectivePlanQty" label="有效计划量" width="110" />
        <el-table-column prop="pendingNetPlanQty" label="净需求待计划" width="115" />
        <el-table-column label="订单未覆盖" width="115"><template #default="scope">{{ scope.row.uncoveredDemandQty ?? '未确认' }}</template></el-table-column>
        <el-table-column label="数量校验" width="125"><template #default="scope">{{ planningQuantityText(scope.row) }}</template></el-table-column>
        <el-table-column prop="customerRequiredDate" label="客户要求交期" width="135" />
        <el-table-column label="企业承诺交期" width="135"><template #default="scope">{{ scope.row.committedDeliveryDate || '未维护' }}</template></el-table-column>
        <el-table-column label="计划完成时间" width="135"><template #default="scope">{{ scope.row.plannedCompletionDate || '尚无法预测' }}</template></el-table-column>
        <el-table-column prop="engineeringMode" label="工程模式" min-width="155" />
        <el-table-column prop="engineeringReadinessStatus" label="制造准备" width="110" />
        <el-table-column prop="planStatusLabel" label="供应计划状态" width="110" />
        <el-table-column prop="statusLabel" label="需求状态" width="100" />
      </el-table>
    </section>

    <el-dialog :model-value="Boolean(m09LineId)" title="订单行制造批次与计划范围"
      width="min(860px, calc(100% - 24px))" @update:model-value="visible => { if (!visible) closeM09Line() }">
      <section v-if="m09Selected" class="m09-range-panel" aria-label="订单行制造批次与计划范围">
        <h3>{{ m09Selected.salesOrderNo }} · {{ m09Facts.line?.lineNo ? `第 ${m09Facts.line.lineNo} 行` : `订单行 ID ${m09Selected.salesOrderItemId}` }}</h3>
        <p>{{ m09Selected.materialName }} · {{ m09Selected.uomCode || '单位未提供' }}</p>
        <p v-if="m09Loading" role="status">正在读取本订单行的计划范围、制造版本及完成依据。</p>
        <dl class="m09-range-fields">
          <div><dt>计划制造范围量</dt><dd>{{ m09Quantity(m09Facts.coverage?.plannedManufacturingScopeQuantity, m09Facts.coverage?.uomLabel) }}</dd></div>
          <div><dt>实际制造完成量</dt><dd>{{ m09Quantity(m09Facts.coverage?.manufacturingCompletedQuantity, m09Facts.coverage?.uomLabel) }}</dd></div>
          <div><dt>当前库存覆盖量</dt><dd>{{ m09Quantity(m09Facts.coverage?.confirmedStockCoverageQuantity, m09Facts.coverage?.uomLabel) }}</dd></div>
          <div><dt>订单完成条件</dt><dd>{{ m09Readiness(m09Facts.completion?.ready) }}</dd></div>
        </dl>
        <p v-if="m09Facts.completionError" role="alert">完成依据未取得：{{ m09Facts.completionError }}</p>
        <template v-if="m09Facts.line">
          <p>本行供给覆盖：{{ m09Facts.line.completionStatus === 'SOURCE_UNKNOWN' ? '供应来源待核' : m09Facts.coverage?.supplyCoverageStatusLabel || '未提供' }}</p>
          <ul v-if="m09Facts.line.blockingReasons?.length">
            <li v-for="(reason, index) in m09Facts.line.blockingReasons" :key="index">{{ reason.message }}</li>
          </ul>
          <ul v-if="m09Facts.completion.blockingReasons?.some(reason => reason.scope === 'ORDER')">
            <li v-for="(reason, index) in m09Facts.completion.blockingReasons.filter(reason => reason.scope === 'ORDER')" :key="index">{{ reason.message }}</li>
          </ul>
        </template>
        <p v-if="m09Facts.outputError" role="alert">制造输出版本未取得：{{ m09Facts.outputError }}</p>
        <article v-for="entry in m09Rows" :key="entry.row.id" class="m09-batch" :data-demand-id="entry.row.id">
          <h4>{{ entry.batch?.batchKey ? `制造批次 ${entry.batch.batchKey}` : '计划需求' }} · {{ entry.row.demandNo }}</h4>
          <dl class="m09-range-fields">
            <div><dt>生产计划</dt><dd><router-link v-if="entry.row.planType === 'ProductionPlan' && entry.row.planId" :to="m09PlanLink(entry.row)">{{ entry.row.planNo }}</router-link><template v-else>未提供</template></dd></div>
            <div><dt>原计划量</dt><dd>{{ m09Quantity(entry.plan?.planQty, entry.row.uomCode) }}</dd></div>
            <div><dt>制造输出</dt><dd>{{ fieldText(entry.row.manufacturingOutputId) }}</dd></div>
            <div><dt>制造输出修订</dt><dd>{{ entry.output?.revision != null ? `修订 ${entry.output.revision}` : '未提供' }}</dd></div>
            <div><dt>批次起止范围</dt><dd>{{ entry.batch?.batchKey ? m09Range(entry.batch.rangeStart, entry.batch.rangeEnd, m09Facts.coverage?.uomLabel) : '未提供' }}</dd></div>
            <div><dt>批次数量</dt><dd>{{ m09Quantity(entry.batch?.batchKey ? entry.batch.quantity : null, m09Facts.coverage?.uomLabel) }}</dd></div>
            <div><dt>本计划批准范围</dt><dd>{{ m09Range(entry.scope?.approvedRangeStart, entry.scope?.approvedRangeEnd, entry.scope?.productionUomCode) }}</dd></div>
            <div><dt>本批制造闭合</dt><dd>{{ entry.batch?.batchKey && typeof entry.batch.manufacturingCompleted === 'boolean' ? (entry.batch.manufacturingCompleted ? '已闭合' : '尚未闭合') : '未提供' }}</dd></div>
          </dl>
          <p v-if="entry.rangeError">批准范围待核：{{ entry.rangeError }}</p>
          <p v-if="m09Facts.outputs && entry.row.manufacturingOutputId && !entry.output">本需求关联的制造输出未在当前可读版本中取得。</p>
          <p v-if="!m09Loading && !entry.batch?.batchKey">{{ entry.batch ? '原服务保留该需求的范围依据，未登记独立制造批次。' : '尚未取得该需求的正式制造批次关联。' }}</p>
        </article>
        <p v-for="allocation in m09ReleasedStock" :key="allocation.allocationId">库存分配 {{ allocation.allocationId }} 已释放，服务端已将其排除在当前覆盖量之外。</p>
      </section>
      <p v-else role="status">{{ loading ? '正在读取计划记录。' : '当前授权的订单计划需求中未取得该订单行。' }}</p>
      <template #footer><el-button @click="closeM09Line">返回订单计划需求</el-button></template>
    </el-dialog>

    <section class="panel block">
      <div class="panel-heading">
        <div><h2>主生产计划建议（MPS）</h2><p>按产品、需求日期、数量与工程模式形成可解释建议，并保留每一笔 Demand 分配。</p></div>
      </div>
      <el-table :data="mpsLines" border empty-text="暂无 MPS 建议">
        <el-table-column prop="runNo" label="MPS批次" min-width="165" fixed />
        <el-table-column prop="lineNo" label="行号" width="75" />
        <el-table-column prop="productCode" label="产品编码" min-width="120" />
        <el-table-column prop="materialCode" label="物料编码" min-width="130" />
        <el-table-column prop="totalQty" label="计划数量" width="105" />
        <el-table-column prop="uomCode" label="计量单位" width="80" />
        <el-table-column prop="requiredDate" label="需求日期" width="120" />
        <el-table-column prop="engineeringMode" label="工程模式" min-width="150" />
        <el-table-column label="来源订单" min-width="190"><template #default="scope">{{ scope.row.demands?.map(item => item.salesOrderNo).join('、') }}</template></el-table-column>
        <el-table-column label="动作" width="145" fixed="right">
          <template #default="scope"><el-button v-if="capabilities.canGenerateMrp" size="small" type="success" :disabled="Boolean(scope.row.mrpRunId)" @click="generateMrp(scope.row)">运行 MRP</el-button></template>
        </el-table-column>
      </el-table>
    </section>

    <section class="panel block">
      <div class="panel-heading">
        <div><h2>物料需求建议（MRP）</h2><p>直接展开 PDE 已发布 BOM；MAKE、BUY 与 UNRESOLVED 明确分流，不生成采购单或生产任务。</p></div>
      </div>
      <el-table :data="mrpProposals" border empty-text="暂无 MRP 建议">
        <el-table-column prop="runNo" label="MRP批次" min-width="165" fixed />
        <el-table-column prop="salesOrderNo" label="销售订单编号" min-width="155"><template #default="scope"><el-button link type="primary" @click="openOrder(scope.row)">{{ scope.row.salesOrderNo }}</el-button></template></el-table-column>
        <el-table-column prop="demandNo" label="需求编号" min-width="150" />
        <el-table-column prop="materialCode" label="物料编码" min-width="120" />
        <el-table-column prop="requiredQty" label="毛需求" width="100" />
        <el-table-column prop="currentInventory" label="当前库存" width="105"><template #default="scope">{{ scope.row.currentInventory ?? 'INVENTORY NOT YET INTEGRATED' }}</template></el-table-column>
        <el-table-column prop="netRequirement" label="净需求" width="100" />
        <el-table-column prop="supplyTypeLabel" label="供应方式" width="100" />
        <el-table-column prop="suggestedAction" label="建议动作" min-width="180" />
        <el-table-column prop="blockReason" label="阻断原因" min-width="220"><template #default="scope">{{ scope.row.blockReason || '-' }}</template></el-table-column>
        <el-table-column prop="sourceBomVersionId" label="来源BOM版本ID" width="135" />
      </el-table>
    </section>

    <section class="panel block">
      <div class="panel-heading">
        <div>
          <h2>人工计划需求</h2>
          <p>来源类别、来源对象类型、对象ID及单据编号分别来自原需求；订单明细来源的对象ID是订单行，单据编号是父订单。类型可识别不表示来源审核或办理资格通过。</p>
        </div>
      </div>
      <div v-if="compactPlanningViewport" class="planning-table-tools"><span>按住表头蓝色↔边界左右拖动调列宽；表格内横滑查看其他列。</span><el-button size="small" @click="planningInteraction.reset('demand')">恢复默认列宽</el-button></div>
      <el-table ref="demandTableRef" data-planning-table="demand" @header-dragend="(width,oldWidth,column)=>planningInteraction.dragend('demand',width,oldWidth,column)" :style="{'--planning-action-readable-width': `${Math.max(44, planningViewportWidths.demand - planningColumnWidths.demandLeft - 8)}px`}" :data="demands" :data-planning-right-fixed="String(demandActionsFixed)" border empty-text="暂无正式需求">
        <el-table-column prop="demandNo" label="需求编号" min-width="155" fixed />
        <el-table-column prop="sourceTypeLabel" label="需求来源类别" min-width="120" />
        <el-table-column label="来源对象类型" min-width="205"><template #default="{row}">{{ sourceDocumentTypeText(row) }}</template></el-table-column>
        <el-table-column prop="sourceDocumentId" label="来源对象ID（订单行等）" min-width="200"><template #default="{row}">{{ fieldText(row.sourceDocumentId) }}</template></el-table-column>
        <el-table-column prop="sourceDocumentNo" label="来源单据编号（父订单等）" min-width="205"><template #default="{row}">{{ fieldText(row.sourceDocumentNo) }}</template></el-table-column>
        <el-table-column prop="materialCode" label="物料编码" min-width="110" />
        <el-table-column prop="materialName" label="物料名称" min-width="150" />
        <el-table-column prop="requiredQty" label="需求数量" min-width="110" />
        <el-table-column prop="requiredDate" label="需求日期" min-width="120" />
        <el-table-column prop="departmentName" label="需求部门" min-width="130" />
        <el-table-column prop="statusLabel" label="需求状态" min-width="90" />
        <el-table-column v-if="capabilities.canPlan" label="业务动作" min-width="150" :fixed="demandActionsFixed" class-name="planning-responsive-actions">
          <template #default="scope">
            <el-button
              size="small"
              type="primary"
              :disabled="Boolean(scope.row.requirementId)"
              @click="calculate(scope.row)"
            >计算净需求</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="panel block">
      <div class="panel-heading">
        <div>
          <h2>计划需求与分流结果</h2>
          <p>库存计算快照、净需求和供应类型全部来自服务端；库存快照不等于订单库存分配，页面不重新计算。</p>
        </div>
      </div>
      <div v-if="compactPlanningViewport" class="planning-table-tools"><span>按住表头蓝色↔边界左右拖动调列宽；表格内横滑查看其他列。</span><el-button size="small" @click="planningInteraction.reset('requirement')">恢复默认列宽</el-button></div>
      <el-table ref="requirementTableRef" data-planning-table="requirement" @header-dragend="(width,oldWidth,column)=>planningInteraction.dragend('requirement',width,oldWidth,column)" :style="{'--planning-action-readable-width': `${Math.max(44, planningViewportWidths.requirement - planningColumnWidths.requirementLeft - 8)}px`}" :data="requirements" :data-planning-right-fixed="String(requirementActionsFixed)" border empty-text="暂无计划需求">
        <el-table-column prop="requirementNo" label="计划需求编号" min-width="165" fixed />
        <el-table-column prop="demandNo" label="需求编号" min-width="155" />
        <el-table-column prop="sourceTypeLabel" label="需求来源类别" min-width="150" />
        <el-table-column label="来源对象类型" min-width="205"><template #default="{row}">{{ sourceDocumentTypeText(row) }}</template></el-table-column>
        <el-table-column prop="sourceDocumentId" label="来源对象ID（订单行等）" min-width="200"><template #default="{row}">{{ fieldText(row.sourceDocumentId) }}</template></el-table-column>
        <el-table-column prop="sourceDocumentNo" label="来源单据编号（父订单等）" min-width="205"><template #default="{row}">{{ fieldText(row.sourceDocumentNo) }}</template></el-table-column>
        <el-table-column prop="materialCode" label="物料编码" min-width="110" />
        <el-table-column prop="demandQty" label="需求数量" min-width="100" />
        <el-table-column prop="inventorySnapshotQty" label="库存计算快照（未分配）" min-width="170" />
        <el-table-column label="订单库存覆盖" min-width="125"><template #default="scope">{{ scope.row.effectiveInventoryCoverageQty ?? '未确认' }}</template></el-table-column>
        <el-table-column prop="netRequiredQty" label="净需求" min-width="100" />
        <el-table-column prop="supplyTypeLabel" label="供应类型" min-width="100" />
        <el-table-column prop="planType" label="供应计划类型" min-width="130"><template #default="scope">{{ supplyPlanTypeText(scope.row) }}</template></el-table-column>
        <el-table-column prop="planNo" label="供应计划编号" min-width="205"><template #default="{row}">{{ supplyPlanNumberText(row) }}</template></el-table-column>
        <el-table-column prop="planQty" label="计划数量" min-width="100" />
        <el-table-column prop="planStatusLabel" label="供应计划状态" min-width="100" />
        <el-table-column prop="purchaseRequestNo" label="采购申请编号" min-width="155" />
        <el-table-column prop="purchaseRequestQty" label="申请数量" min-width="100" />
        <el-table-column prop="purchaseRequestStatusLabel" label="采购申请状态" min-width="100" />
        <el-table-column label="采购订单" min-width="165">
          <template #default="scope">{{ scope.row.purchaseOrders?.map(item => item.poNo).join('、') || '-' }}</template>
        </el-table-column>
        <el-table-column label="业务动作" min-width="320" :fixed="requirementActionsFixed" class-name="planning-responsive-actions">
          <template #default="scope">
            <el-button
              v-if="capabilities.canPlan"
              size="small"
              type="success"
              :disabled="Boolean(scope.row.planId) || scope.row.supplyType === 'ambiguous' || Number(scope.row.netRequiredQty) <= 0"
              @click="confirmPlan(scope.row)"
            >确认供应计划</el-button>
            <el-button
              v-if="capabilities.canConvertPurchasePlan"
              size="small"
              type="primary"
              :disabled="scope.row.planType !== 'PurchasePlan' || scope.row.planStatus !== 'confirmed' || Boolean(scope.row.purchaseRequestId)"
              @click="convertPlan(scope.row)"
            >承接采购申请</el-button>
            <el-button v-if="scope.row.purchaseRequestId" size="small" @click="openRequest(scope.row)">打开采购申请</el-button>
            <el-button v-if="scope.row.purchaseRequestStatus === 'approved' && !scope.row.purchaseOrders?.length" size="small" @click="openGate(scope.row)">进入订单准入</el-button>
            <el-button size="small" @click="validate(scope.row)">只读验证</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section v-if="selectedTrace" class="panel trace-panel block">
      <div class="panel-heading">
        <div>
          <h2>业务链追踪与只读验证</h2>
          <p>同一组服务端关系同时支持从需求查看计划、从计划回看需求。</p>
        </div>
      </div>
      <div class="trace-flow">
        <span>{{ selectedTrace.source?.no || '-' }}</span><b>↓</b>
        <span>{{ selectedTrace.demand?.no || '-' }}</span><b>↓</b>
        <span>{{ selectedTrace.requirement?.no || '-' }}</span><b>↓</b>
        <span>{{ selectedTrace.plan?.no || '尚未生成计划' }}</span><b>↓</b>
        <span>{{ selectedTrace.purchaseRequest?.no || '尚未生成采购申请' }}</span><b>↓</b>
        <span>{{ selectedTrace.purchaseOrders?.map(item => item.no).join('、') || '尚未生成采购订单' }}</span>
      </div>
      <div v-if="validationResult" class="validation-grid">
        <article v-for="item in validationItems" :key="item.key">
          <span>{{ item.label }}</span>
          <strong :class="validationResult[item.key] ? 'pass' : 'fail'">
            {{ validationResult[item.key] ? 'PASS' : 'FAIL' }}
          </strong>
        </article>
      </div>
    </section>

    <section class="panel block">
      <div class="panel-heading">
        <div>
          <h2>正式审计</h2>
          <p>显示最近 30 条计划业务动作审计。</p>
        </div>
      </div>
      <el-table :data="audits" border empty-text="暂无计划审计">
        <el-table-column prop="id" label="审计ID" width="90" />
        <el-table-column prop="actionCode" label="业务动作" min-width="220" />
        <el-table-column prop="targetType" label="对象类型" min-width="150" />
        <el-table-column prop="targetLabel" label="对象编号" min-width="170" />
        <el-table-column prop="actor" label="执行账户" min-width="130" />
        <el-table-column prop="createdAt" label="执行时间" min-width="210" />
      </el-table>
    </section>

    <el-dialog v-model="dialogVisible" title="新增人工计划需求" width="560px">
      <el-form label-width="110px">
        <el-form-item label="正式物料">
          <el-select v-model="form.materialId" filterable style="width: 100%">
            <el-option
              v-for="item in materials"
              :key="item.id"
              :label="`${item.code} / ${item.name}`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="需求部门">
          <el-select v-model="form.departmentId" filterable style="width: 100%">
            <el-option
              v-for="item in departments"
              :key="item.id"
              :label="`${item.code} / ${item.name}`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="需求数量"><el-input-number v-model="form.requiredQty" :min="0.0001" :precision="4" /></el-form-item>
        <el-form-item label="需求日期"><el-date-picker v-model="form.requiredDate" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="需求原因"><el-input v-model="form.reason" maxlength="300" /></el-form-item>
        <el-form-item label="验收标识"><el-input v-model="form.acceptanceMarker" maxlength="120" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="createDemand">保存正式需求</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup>
import {fieldText,sourceDocumentTypeText,supplyPlanTypeText,supplyPlanNumberText} from '@/meta/runtime/authoritativeFieldPresentation.js'
import ProductionMaterialDemandPanel from '@/meta/components/ProductionMaterialDemandPanel.vue'
import FormalProductionSchedulingPanel from '@/meta/components/FormalProductionSchedulingPanel.vue'
import ProductionWorkOrderReceptionPanel from '@/meta/components/ProductionWorkOrderReceptionPanel.vue'
import { computed, onMounted, onBeforeUnmount, reactive, ref, watch } from 'vue'
import {usePlanningTableInteraction} from '@/meta/runtime/usePlanningTableInteraction.js'
import {useCompactViewport} from '@/meta/runtime/useCompactViewport.js'
import {planningRightActionFixed} from '@/meta/runtime/planningNarrowFixedPolicy.js'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { planningApi } from '@/api/planning'
import request from '@/api/request.js'
import { getTabAuthEpoch } from '@/meta/runtime/tabAuthenticationContext.js'
import { createReadFailedFactLoad } from '@/meta/runtime/pceFactLoadContract.js'

const demandTableRef = ref(null), requirementTableRef = ref(null)
const planningViewportWidths = reactive({ demand: 0, requirement: 0 })
const planningColumnWidths = reactive({ demandLeft:155, demandRight:150, requirementLeft:165, requirementRight:320 })
const compactPlanningViewport = useCompactViewport()
const demandActionsFixed = computed(() => planningRightActionFixed(compactPlanningViewport.value, planningViewportWidths.demand, planningColumnWidths.demandLeft, planningColumnWidths.demandRight))
const requirementActionsFixed = computed(() => planningRightActionFixed(compactPlanningViewport.value, planningViewportWidths.requirement, planningColumnWidths.requirementLeft, planningColumnWidths.requirementRight))
let planningViewportObserver = null
let planningViewportFrame = 0
const planningInteraction=usePlanningTableInteraction({demand:demandTableRef,requirement:requirementTableRef},compactPlanningViewport,syncPlanningViewportWidths)
function syncPlanningViewportWidths() {
  for (const [key, table] of [['demand', demandTableRef], ['requirement', requirementTableRef]]) {
    const headers = [...(table.value?.$el?.querySelectorAll('thead th') || [])]
    const action = headers.find(header => header.innerText.trim() === '业务动作')
    if (headers[0]) planningColumnWidths[key+'Left'] = headers[0].getBoundingClientRect().width
    if (action) planningColumnWidths[key+'Right'] = action.getBoundingClientRect().width
  }
  planningViewportWidths.demand = demandTableRef.value?.$el?.querySelector('.el-table__body-wrapper .el-scrollbar__wrap')?.clientWidth || 0
  planningViewportWidths.requirement = requirementTableRef.value?.$el?.querySelector('.el-table__body-wrapper .el-scrollbar__wrap')?.clientWidth || 0
  planningInteraction.sync()
}
onMounted(() => {
  syncPlanningViewportWidths()
  if (globalThis.ResizeObserver) {
    planningViewportObserver = new ResizeObserver(() => {cancelAnimationFrame(planningViewportFrame);planningViewportFrame=requestAnimationFrame(syncPlanningViewportWidths)})
    for (const table of [demandTableRef, requirementTableRef]) if (table.value?.$el) planningViewportObserver.observe(table.value.$el)
  }
  globalThis.addEventListener?.('resize', syncPlanningViewportWidths)
})
onBeforeUnmount(() => {
  planningViewportObserver?.disconnect()
  cancelAnimationFrame(planningViewportFrame)
  globalThis.removeEventListener?.('resize', syncPlanningViewportWidths)
})
const loading = ref(false)
const saving = ref(false)
const errorMessage = ref('')
const factLoadFacts = ref(null)
const dialogVisible = ref(false)
const demands = ref([])
const requirements = ref([])
const mpsRuns = ref([])
const mrpRuns = ref([])
const materials = ref([])
const departments = ref([])
const audits = ref([])
const apiFacts = ref({})
const planningSchema = ref({ status: '', deployed: false, missingTables: [] })
const selectedTrace = ref(null)
const validationResult = ref(null)
const capabilities = ref({ canPlan: false, canConvertPurchasePlan: false })
const factLoadStatus = computed(() => factLoadFacts.value?.factLoadStatus || 'loading')
const factsAvailable = computed(() => ['loaded', 'empty_valid', 'success'].includes(factLoadStatus.value))
const planningReadDenied = computed(() => factLoadStatus.value === 'read_failed')
const productionPlanOptions = computed(() => [...new Map(requirements.value.filter(item => item.planType === 'ProductionPlan' && Number.isSafeInteger(item.planId) && item.planId > 0 && item.planNo).map(item => [item.planId,{id:item.planId,label:item.planNo}])).values()])
const runningMps = ref(false)
const router = useRouter()
const route = useRoute()
const form = reactive({
  materialId: null,
  departmentId: null,
  requiredQty: 5,
  requiredDate: '2026-09-15',
  reason: '系统流程验收数据',
  acceptanceMarker: 'PCE-PLAN-V1.0',
})
const plannedCount = computed(() => requirements.value.filter(item => item.planId).length)
const factCount = value => factsAvailable.value ? Number(value ?? 0) : '未取得'
const planningQuantityText = row => row.planningQuantityStatus === 'OVER_PLANNED'
  ? `超计划 ${row.overPlannedQty}`
  : (row.planningQuantityStatus === 'NET_REQUIREMENT_FULLY_PLANNED' ? '净需求已足额计划'
    : (row.planningQuantityStatus === 'NOT_CALCULATED' ? '尚未计算' : '净需求仍待计划'))
function readFailureMessage(response) {
  const facts = response?.factLoadFacts || response?.data?.factLoadFacts || {}
  const code = String(response?.error?.code || facts.errorCode || 'FACT_READ_FAILED')
  const detail = String(response?.error?.message || facts.errorMessage || '服务端事实读取失败')
  const httpStatus = Number(facts.httpStatus || response?.meta?.status || 0)
  if (code === 'not_authenticated' || httpStatus === 401) return '未取得数据：当前未登录或会话已失效。请从正式系统登录入口登录后重试。'
  if (httpStatus === 403 || code.toLowerCase().includes('denied')) return `未取得数据：当前合法身份没有计划只读权限。${detail}`
  return `未取得数据：订单计划读取失败。${detail}`
}
const orderDemands = computed(() => demands.value.filter(item => item.sourceType === 'sales_order' && (!route.query.orderNo || item.salesOrderNo === route.query.orderNo)))
const m09LineId = computed(() => typeof route.query.m09Line === 'string' ? route.query.m09Line : '')
const m09Selected = computed(() => factsAvailable.value ? orderDemands.value.find(row => String(row.salesOrderItemId) === m09LineId.value) : null)
const m09LineDemands = computed(() => m09Selected.value ? orderDemands.value.filter(row =>
  row.salesOrderId === m09Selected.value.salesOrderId && row.salesOrderItemId === m09Selected.value.salesOrderItemId) : [])
const m09Facts = ref({})
const m09Loading = ref(false)
let m09ReadCycle = 0
const m09Rows = computed(() => m09LineDemands.value.map(row => ({
  row,
  plan: requirements.value.find(plan => plan.demandId === row.id && plan.planId === row.planId && plan.planType === 'ProductionPlan'),
  batch: m09Facts.value.coverage?.batches?.find(batch => batch.demandId === row.id && batch.manufacturingOutputId === row.manufacturingOutputId),
  output: m09Facts.value.outputs?.find(output => output.manufacturingOutputId === row.manufacturingOutputId),
  scope: m09Facts.value.scopes?.get(row.planId)?.facts,
  rangeError: row.planType === 'ProductionPlan' ? m09Facts.value.scopes?.get(row.planId)?.error : '',
})))
const m09ReleasedStock = computed(() => m09Facts.value.coverage?.stockAllocationHistory?.filter(row => row.active === false && row.status === 'released') || [])
const m09Readiness = value => value === true ? '已满足' : value === false ? '未满足' : '未提供'
const m09Quantity = (value, unit) => value == null || value === '' ? '未提供' : `${value} ${unit || '（单位未提供）'}`
const m09Range = (start, end, unit) => start == null || end == null || start === '' || end === '' ? '未提供' : `[${start}, ${end}) ${unit || '（单位未提供）'}`

function openM09Line(row) {
  router.push({ query: { ...route.query, m09Line: String(row.salesOrderItemId) } })
}
function closeM09Line() {
  router.replace({ query: { ...route.query, m09Line: undefined } })
}
function m09PlanLink(row) {
  return { path: '/planning/requirements', query: { ...route.query, m09Line: undefined, orderNo: row.salesOrderNo, section: 'formal-scheduling', productionPlanId: row.planId } }
}
function m09Read(url, module, params) {
  return request({ url, params, meta: { module, readOnly: true, factLoad: true } }).catch(() => null)
}
function m09Error(response, fallback) {
  return response?.error?.message || response?.factLoadFacts?.errorMessage || fallback
}
async function readM09Line() {
  const cycle = ++m09ReadCycle
  const epoch = getTabAuthEpoch()
  const row = m09Selected.value
  m09Facts.value = {}
  m09Loading.value = false
  if (!row || loading.value) return
  m09Loading.value = true
  const plans = m09LineDemands.value.filter(entry => entry.planType === 'ProductionPlan' && entry.planId)
  const [sales, outputs, scopes] = await Promise.all([
    m09Read(`/api/sales/orders/${encodeURIComponent(row.salesOrderId)}/`, 'SALES', { includeCompletionFacts: '1' }),
    m09Read('/api/pde/manufacturing-outputs/', 'PDE', { q: row.salesOrderNo }),
    Promise.all(plans.map(async plan => {
      const response = await m09Read('/api/planning/demands/', 'PLAN', { sourceCandidates: '1', productionPlanId: plan.planId })
      const facts = response?.data
      const matches = response?.success && facts?.contractVersion === 'PCE-PRODUCTION-MATERIAL-SOURCE-CATALOGUE-V1' &&
        facts.readMode === 'APPROVED_RANGE_CONTEXT' && facts.productionPlanId === plan.planId && facts.productionPlanNo === plan.planNo &&
        facts.productionUomId === plan.uomId && facts.factLoadStatus === 'loaded'
      return [plan.planId, matches ? { facts } : { error: m09Error(response, '原服务未提供本计划的批准范围。') }]
    })),
  ])
  if (cycle !== m09ReadCycle) return
  m09Loading.value = false
  if (epoch !== getTabAuthEpoch()) return
  const order = sales?.data?.order
  const completion = order?.mesCompletionFacts
  const line = sales?.success && order?.id === row.salesOrderId && order.orderNo === row.salesOrderNo &&
    completion?.contractVersion === 'PCE-ORDER-MES-COMPLETION-V1' && completion.salesOrderId === order.id && completion.factLoadStatus === 'loaded'
    ? completion.lines?.find(line => line.salesOrderItemId === row.salesOrderItemId) : null
  const supplied = line?.supplyCoverage
  const coverage = supplied?.contractVersion === 'PCE-ORDER-SUPPLY-COVERAGE-V1' && supplied.uomId === row.uomId ? supplied : null
  const outputRows = outputs?.success && Array.isArray(outputs.data?.rows) ? outputs.data.rows : null
  m09Facts.value = {
    completion: line ? completion : null, line, coverage, scopes: new Map(scopes), outputs: outputRows,
    completionError: line ? '' : m09Error(sales, '原服务未提供本订单行的完成依据。'),
    outputError: outputRows ? '' : m09Error(outputs, '原服务未提供制造输出。'),
  }
}
watch([m09Selected, loading], readM09Line, { immediate: true, flush: 'sync' })
onBeforeUnmount(() => { m09ReadCycle++ })
const mpsLines = computed(() => mpsRuns.value.flatMap(run => (run.lines || []).map(line => ({ ...line, runId: run.id, runNo: run.runNo, mrpRunId: mrpRuns.value.find(item => item.mpsRunId === run.id)?.id || null }))))
const mrpProposals = computed(() => mrpRuns.value.flatMap(run => (run.proposals || []).map(item => ({ ...item, runNo: run.runNo }))))
const validationItems = [
  ['sourceComplete', '来源完整'], ['materialValid', '物料有效'], ['inventoryRead', '库存读取'],
  ['netRequirementCorrect', '净需求计算'], ['supplyTypeValid', '供应类型'],
  ['planQuantityCorrect', '计划数量'], ['sourceTraceComplete', '来源追踪'],
  ['purchaseRequestExists', '采购申请存在'], ['purchaseOrderExists', '采购订单存在'],
  ['purchaseRequestSourceComplete', 'PP→PR来源'], ['quantityRelationCorrect', '数量关系'],
  ['materialConsistent', '物料一致'], ['statusRelationCorrect', '状态关系'],
  ['priceAdmissionValid', '价格准入'], ['amountCorrect', '金额'],
  ['duplicateExecutionProtected', '重复执行保护'], ['inventoryUnchanged', '库存不变'],
].map(([key, label]) => ({ key, label }))

async function loadFacts() {
  loading.value = true
  errorMessage.value = ''
  factLoadFacts.value = null
  const response = await planningApi.facts()
  loading.value = false
  if (!response.success) {
    factLoadFacts.value = response.factLoadFacts || response.data?.factLoadFacts || createReadFailedFactLoad({
      apiUrl: '/api/planning/facts/', httpStatus: response.meta?.status,
      errorCode: response.error?.code, errorMessage: response.error?.message,
    })
    errorMessage.value = readFailureMessage(response)
    demands.value = []
    requirements.value = []
    mpsRuns.value = []
    mrpRuns.value = []
    capabilities.value = { canPlan: false, canConvertPurchasePlan: false, canGenerateMps: false, canGenerateMrp: false }
    return
  }
  const data = response.data || {}
  factLoadFacts.value = data.factLoadFacts || data.strictFacts?.factLoadFacts || null
  if (!factLoadFacts.value) {
    factLoadFacts.value = createReadFailedFactLoad({
      apiUrl: '/api/planning/facts/', httpStatus: response.meta?.status,
      errorCode: 'FACT_LOAD_CONTRACT_INCOMPLETE', errorMessage: '计划接口未返回完整事实加载合同',
    })
    errorMessage.value = readFailureMessage({ factLoadFacts: factLoadFacts.value, error: { message: factLoadFacts.value.errorMessage } })
    demands.value = []
    requirements.value = []
    mpsRuns.value = []
    mrpRuns.value = []
    return
  }
  demands.value = data.demands || []
  requirements.value = data.requirements || []
  mpsRuns.value = data.mpsRuns || []
  mrpRuns.value = data.mrpRuns || []
  materials.value = data.materials || []
  departments.value = data.departments || []
  audits.value = data.audits || []
  apiFacts.value = data.apiFacts || {}
  planningSchema.value = data.apiFacts?.orderPlanningSchema || { status: 'READ_FAILED', deployed: false, missingTables: null }
  capabilities.value = data.capabilities || { canPlan: false, canConvertPurchasePlan: false, canGenerateMps: false, canGenerateMrp: false }
  if (!form.departmentId) {
    form.departmentId = departments.value.find(item => item.code === 'JHWKB')?.id || departments.value[0]?.id || null
  }
  if (!form.materialId) {
    form.materialId = materials.value.find(item => item.code === 'MT004')?.id || materials.value[0]?.id || null
  }
}

function requestFacts(prefix) {
  const value = `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`
  return { requestId: value, idempotencyKey: value }
}

async function generateMps() {
  runningMps.value = true
  const response = await planningApi.generateMps(requestFacts('MPS'))
  runningMps.value = false
  if (!response.success) return ElMessage.error(response.error?.message || 'MPS建议生成失败。')
  ElMessage.success(`主生产计划建议 ${response.data.mpsRun.runNo} 已生成`)
  await loadFacts()
}

async function generateMrp(row) {
  const response = await planningApi.generateMrp(row.runId, requestFacts('MRP'))
  if (!response.success) return ElMessage.error(response.error?.message || 'MRP建议生成失败。')
  ElMessage.success(`物料需求建议 ${response.data.mrpRun.runNo} 已生成`)
  await loadFacts()
}

function openOrder(row) {
  router.push({ path: '/sales/orders', query: { search: row.salesOrderNo } })
}

async function createDemand() {
  saving.value = true
  const response = await planningApi.createDemand({ ...form })
  saving.value = false
  if (!response.success) return ElMessage.error(response.error?.message || '需求创建失败。')
  dialogVisible.value = false
  ElMessage.success(`正式需求 ${response.data.demand.demandNo} 已创建`)
  await loadFacts()
}

async function calculate(row) {
  const response = await planningApi.calculateDemand(row.id)
  if (!response.success) return ElMessage.error(response.error?.message || '净需求计算失败。')
  ElMessage.success(`计划需求 ${response.data.requirement.requirementNo} 已生成`)
  await loadFacts()
}

async function confirmPlan(row) {
  const response = await planningApi.confirmPlan(row.id)
  if (!response.success) return ElMessage.error(response.error?.message || '供应计划确认失败。')
  ElMessage.success(`${response.data.plan.planNo} 已确认`)
  await loadFacts()
  await showTrace(response.data.plan.planNo)
}

async function convertPlan(row) {
  const response = await planningApi.convertPurchasePlan(row.planId)
  if (!response.success) return ElMessage.error(response.error?.message || '采购计划承接失败。')
  ElMessage.success(`采购计划已生成 ${response.data.purchaseRequest.requestNo}`)
  await loadFacts()
  await showTrace(response.data.purchaseRequest.requestNo)
}

function openRequest(row) {
  router.push({ path: '/scm/purchase-request', query: { search: row.purchaseRequestNo } })
}

function openGate(row) {
  router.push({ path: '/scm/purchase-order-gate', query: { purchaseRequestId: row.purchaseRequestId } })
}

async function validate(row) {
  const [validationResponse] = await Promise.all([
    planningApi.validate(row.id),
    showTrace(row.planNo || row.requirementNo),
  ])
  if (!validationResponse.success) return ElMessage.error(validationResponse.error?.message || '只读验证失败。')
  validationResult.value = validationResponse.data.validation
}

async function showTrace(reference) {
  const response = await planningApi.trace(reference)
  if (!response.success) return
  selectedTrace.value = response.data.traces?.[0] || null
}

onMounted(loadFacts)
</script>

<style scoped>
.planning-page { padding: 24px; background: #f3f6fb; min-height: 100vh; color: #17233d; }
.planning-hero, .panel { background: #fff; border: 1px solid #dfe6f2; border-radius: 16px; padding: 22px; }
.unavailable-facts { border-color: #f3c3c3; background: #fff7f7; color: #9f1d1d; }
.unavailable-facts p { color: #9f1d1d; }
.planning-hero { display: flex; justify-content: space-between; gap: 24px; align-items: center; }
.planning-hero h1, .panel h2 { margin: 0; }
.planning-hero p, .panel p { margin: 8px 0 0; color: #667085; }
.eyebrow { color: #3157c7 !important; font-size: 12px; font-weight: 700; letter-spacing: .08em; }
.hero-actions { display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
.block { margin-top: 18px; }
.fact-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 14px; }
.fact-grid article { background: #fff; border: 1px solid #dfe6f2; border-radius: 14px; padding: 18px; }
.fact-grid span { display: block; color: #667085; font-size: 13px; }
.fact-grid strong { display: block; margin-top: 8px; font-size: 28px; }
.panel-heading { display: flex; justify-content: space-between; margin-bottom: 16px; }
.trace-panel { background: #fbfdff; }
.trace-flow { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.trace-flow span { background: #eef4ff; border: 1px solid #cbd9ff; border-radius: 10px; padding: 10px 14px; font-weight: 700; }
.trace-flow b { color: #3157c7; }
.validation-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 18px; }
.validation-grid article { background: #fff; border: 1px solid #dfe6f2; border-radius: 10px; padding: 12px; }
.validation-grid span { display: block; color: #667085; font-size: 12px; }
.validation-grid strong { display: block; margin-top: 5px; }
.pass { color: #14804a; } .fail { color: #c43232; }
@media (max-width: 980px) { .planning-hero { align-items: flex-start; flex-direction: column; } .fact-grid, .validation-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }

/* Only these two tables release their right actions when compact space is insufficient. */
.planning-page :deep(.el-table[data-planning-right-fixed='false'] th.planning-responsive-actions .cell) { text-align: right; padding-right: 4px; }
.planning-page :deep(.el-table[data-planning-right-fixed='false'] td.planning-responsive-actions .cell) {
  display: flex; flex-direction: column; align-items: flex-end; gap: 8px; padding-left: 4px; padding-right: 4px;
}
.planning-page :deep(.el-table[data-planning-right-fixed='false'] td.planning-responsive-actions .el-button) {
  width: min(100%, var(--planning-action-readable-width)); min-width: 44px; min-height: 44px; height: auto;
  margin-left: 0; padding: 8px 4px; white-space: normal;
}
.planning-page :deep(.el-table[data-planning-right-fixed='false'] td.planning-responsive-actions .el-button > span) {
  white-space: normal; overflow-wrap: anywhere;
}

/* Local to this original page and its two adapted tables; no global table policy. */
@media(max-width:900px) {
  :global(.pce-list-page-shell:has(.planning-page)), :global(.pce-list-page-content:has(> .planning-page)) { overflow-x: clip; overflow-y: visible; }
  .planning-page :deep(.el-table[data-planning-table]), .planning-page :deep(.el-table[data-planning-table] .el-table__inner-wrapper) { overflow: visible; }
  .planning-page :deep(.el-table[data-planning-table] .el-table__header-wrapper) { position: sticky; top: calc(var(--pce-account-bookmark-height,52px) + var(--pce-system-bar-height,48px) + 8px); z-index: 12; background:#f8fafc; box-shadow:0 2px 3px #173f6920; }
  .planning-page :deep(.el-table[data-planning-table] th .cell) { min-height:44px; padding-right:28px; display:flex; align-items:center; white-space:normal; overflow-wrap:anywhere; }
  .planning-page :deep(.el-table[data-planning-table] th.planning-responsive-actions .cell) { justify-content:flex-end; }
  .planning-page :deep(.planning-column-resize-handle) { position:absolute; right:0; top:0; bottom:0; width:24px; min-height:44px; padding:0; margin:0; border:0; border-right:2px solid #3973c8; border-radius:4px; background:#e1edfc; color:#1757a1; cursor:col-resize; touch-action:none; user-select:none; z-index:3; font-size:12px; }
  .planning-page :deep(.planning-column-resize-handle:focus-visible) { outline:2px solid #1757a1; outline-offset:-2px; }
  .planning-table-tools { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-bottom:8px; color:#526780; font-size:13px; }
  .planning-table-tools .el-button { min-height:44px; }
}

.m09-line-button{min-height:44px;padding:4px 2px;border:0;background:none;color:#1757a1;text-decoration:underline;cursor:pointer}
.m09-line-button:focus-visible{outline:2px solid #1757a1;outline-offset:-2px}
.m09-range-panel{min-width:0;overflow-wrap:anywhere}
.m09-batch{margin-top:12px;padding:12px;border:1px solid #d6e0ee;border-radius:8px}
.m09-batch h4{margin:0 0 8px}
.m09-range-fields{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:8px 0}
.m09-range-fields dd{margin:0;font-weight:600;font-variant-numeric:tabular-nums}
@media(max-width:600px){.m09-range-fields{grid-template-columns:repeat(2,minmax(0,1fr))}.m09-batch{padding:8px}}
</style>

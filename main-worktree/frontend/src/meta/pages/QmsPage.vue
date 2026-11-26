<template>
  <main class="qms-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.11.9 QMS来料检验预备</p>
        <h1>{{ currentQmsPageName }}</h1>
        <p>本页登记来料检验结果，并只将合格与让步接收数量推送到 WMS 入库。</p>
        <p class="app-current-module-badge">当前操作模块：{{ currentQmsModuleName }}</p>
      </section>
      <nav class="page-tabs app-module-nav-zone">
        <span class="app-nav-zone-title">QMS检验流程导航</span>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': isQmsNavActive('home') }" to="/qms">
          QMS首页
          <span v-if="isQmsNavActive('home')" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': isQmsNavActive('inspection') }" to="/qms/incoming-inspections">
          来料检验
          <span v-if="isQmsNavActive('inspection')" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" to="/wms/purchase-receives">采购收货预备</router-link>
      </nav>
    </header>

    <el-alert v-if="message" :title="message" :type="messageType" show-icon :closable="false" />

    <section v-if="detail" class="operation-shell">
      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>{{ detail.inspectionNo }}</h2>
              <span>来源收货单号：{{ detail.sourceReceiveNo || '-' }}</span>
            </div>
            <div class="button-row">
              <el-button v-if="!detail.formalAuthority && detail.status === 'pending'" type="primary" @click="startInspection">开始检验</el-button>
              <el-button v-if="!detail.formalAuthority && detail.status === 'inspecting'" type="success" @click="saveResult">保存检验结果</el-button>
              <el-button v-if="!detail.formalAuthority && detail.status === 'inspecting'" type="warning" @click="submitResult">提交检验结果</el-button>
              <el-button v-if="!detail.formalAuthority && detail.status === 'inspected'" type="primary" @click="prepareInbound">生成检验合格入库预备</el-button>
              <el-button v-if="detail.status === 'inboundPrepared'" @click="viewInboundPrepare">查看入库预备</el-button>
              <el-button v-if="detail.status === 'rejected'" @click="notify('退货、报废、返工已记录，不进入库存。')">查看不合格处理</el-button>
              <el-button v-if="detail.status === 'inventoryPosted'" @click="viewInventoryTransactions">查看库存流水</el-button>
              <el-button v-if="detail.status === 'inventoryPosted'" @click="viewInventoryBalances">查看库存余额</el-button>
              <el-button @click="goList(router, 'qms', 'incomingInspections')">返回列表</el-button>
              <el-button @click="goParent(router, 'qms')">返回上级</el-button>
              <el-button v-if="detail.sourceReceiveId" @click="goSource(router, receiveSourceRecord, notify)">查看来源收货单</el-button>
              <el-button v-if="detail.sourceOrderId" @click="goSource(router, orderSourceRecord, notify)">查看来源采购订单</el-button>
            </div>
          </div>
        </template>
        <div class="info-grid">
          <article v-for="item in detailFields" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>
        <div class="flow-box">
          <strong>来料检验流程：待检 → 开始检验 → 填写检验结果 → 提交检验 → 生成入库预备 → 确认入库</strong>
          <span>当前流程位置：{{ flowPosition.current }}，下一步：{{ flowPosition.next }}。</span>
        </div>
      </el-card>

      <el-card v-if="detail.status === 'inspecting'" shadow="never">
        <template #header><h2>检验头信息</h2></template>
        <div class="edit-grid">
          <label>
            <span>检验员</span>
            <el-select v-model="editDraft.inspectorId" filterable @change="syncInspectorName">
              <el-option v-for="item in employeeOptions" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
          </label>
          <label>
            <span>实际检验日期</span>
            <el-date-picker v-model="editDraft.actualInspectDate" type="date" value-format="YYYY-MM-DD" />
          </label>
          <label>
            <span>备注</span>
            <el-input v-model="editDraft.remark" />
          </label>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>检验结果明细</h2></template>
        <el-table :data="detailLines" border stripe height="520" class="qms-inspection-table">
          <el-table-column prop="lineNo" label="序号" width="70" fixed="left" />
          <el-table-column prop="materialCode" label="物料编码" min-width="140" fixed />
          <el-table-column prop="materialName" label="物料名称" min-width="180" fixed />
          <el-table-column prop="spec" label="规格型号" min-width="150" />
          <el-table-column prop="unit" label="单位" width="80" />
          <el-table-column prop="batchNo" label="批号" min-width="130" />
          <el-table-column prop="warehouseName" label="仓库" min-width="110" />
          <el-table-column prop="locationName" label="库位" min-width="110" />
          <el-table-column prop="receivedQty" label="收货数量" width="100" />
          <el-table-column prop="pendingInspectQty" label="待检数量" width="100" />
          <el-table-column prop="qualifiedQty" label="合格数量" min-width="150">
            <template #default="{ row }">
              <el-input-number v-if="detail.status === 'inspecting'" v-model="row.qualifiedQty" class="qms-number-input" :min="0" :precision="2" @change="recalculateLine(row)" />
              <span v-else>{{ row.qualifiedQty }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="unqualifiedQty" label="不合格数量" min-width="150">
            <template #default="{ row }">
              <el-input-number v-if="detail.status === 'inspecting'" v-model="row.unqualifiedQty" class="qms-number-input" :min="0" :precision="2" @change="recalculateLine(row)" />
              <span v-else>{{ row.unqualifiedQty }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="concessionQty" label="让步接收数量" min-width="160">
            <template #default="{ row }">
              <el-input-number v-if="detail.status === 'inspecting'" v-model="row.concessionQty" class="qms-number-input" :min="0" :precision="2" @change="recalculateLine(row)" />
              <span v-else>{{ row.concessionQty }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="returnQty" label="退货数量" min-width="150">
            <template #default="{ row }">
              <el-input-number v-if="detail.status === 'inspecting'" v-model="row.returnQty" class="qms-number-input" :min="0" :precision="2" @change="recalculateLine(row)" />
              <span v-else>{{ row.returnQty }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="scrapQty" label="报废数量" min-width="150">
            <template #default="{ row }">
              <el-input-number v-if="detail.status === 'inspecting'" v-model="row.scrapQty" class="qms-number-input" :min="0" :precision="2" @change="recalculateLine(row)" />
              <span v-else>{{ row.scrapQty }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="reworkQty" label="返工数量" min-width="150">
            <template #default="{ row }">
              <el-input-number v-if="detail.status === 'inspecting'" v-model="row.reworkQty" class="qms-number-input" :min="0" :precision="2" @change="recalculateLine(row)" />
              <span v-else>{{ row.reworkQty }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="inspectResult" label="检验结果" min-width="170">
            <template #default="{ row }">
              <el-select v-if="detail.status === 'inspecting'" v-model="row.inspectResult">
                <el-option label="待检" value="pending" />
                <el-option label="合格" value="qualified" />
                <el-option label="不合格" value="unqualified" />
                <el-option label="部分合格" value="partial" />
              </el-select>
              <span v-else>{{ inspectResultLabel(row.inspectResult) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="dispositionType" label="处理方式" min-width="170">
            <template #default="{ row }">
              <el-select v-if="detail.status === 'inspecting'" v-model="row.dispositionType">
                <el-option label="合格" value="qualified" />
                <el-option label="让步接收" value="concession" />
                <el-option label="退货" value="return" />
                <el-option label="报废" value="scrap" />
                <el-option label="返工" value="rework" />
                <el-option label="混合处理" value="mixed" />
                <el-option label="待处理" value="pending" />
              </el-select>
              <span v-else>{{ dispositionLabel(row.dispositionType) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="defectReason" label="不良原因" min-width="160">
            <template #default="{ row }">
              <el-input v-if="detail.status === 'inspecting'" v-model="row.defectReason" />
              <span v-else>{{ row.defectReason || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="inspectorName" label="检验员" min-width="110" />
          <el-table-column prop="actualInspectDate" label="实际检验日期" min-width="130" />
          <el-table-column prop="inventoryPosted" label="是否已入库" min-width="110">
            <template #default="{ row }">{{ row.inventoryPosted ? '是' : '否' }}</template>
          </el-table-column>
          <el-table-column prop="inventoryPostedQty" label="入库数量" width="100" />
          <el-table-column prop="qualityStatus" label="质量状态" min-width="120">
            <template #default="{ row }">{{ qualityStatusLabel(row.qualityStatus) }}</template>
          </el-table-column>
          <el-table-column prop="remark" label="备注" min-width="160">
            <template #default="{ row }">
              <el-input v-if="detail.status === 'inspecting'" v-model="row.remark" />
              <span v-else>{{ row.remark || '-' }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card v-if="['inboundPrepared', 'inventoryPosted'].includes(detail.status)" shadow="never">
        <template #header><h2>检验合格入库预备</h2></template>
        <el-table :data="inboundPrepareLines" border stripe height="360">
          <el-table-column prop="lineNo" label="序号" width="70" fixed="left" />
          <el-table-column prop="materialCode" label="物料编码" min-width="130" />
          <el-table-column prop="materialName" label="物料名称" min-width="160" />
          <el-table-column prop="batchNo" label="批号" min-width="130" />
          <el-table-column prop="warehouseName" label="仓库" min-width="120" />
          <el-table-column prop="locationName" label="库位" min-width="120" />
          <el-table-column prop="qualifiedQty" label="合格数量" width="110" />
          <el-table-column prop="concessionQty" label="让步接收数量" width="130" />
          <el-table-column prop="inboundPreparedQty" label="预备入库数量" width="130" />
          <el-table-column prop="inventoryPostedQty" label="已入库数量" width="120" />
          <el-table-column label="状态" width="120">
            <template #default="{ row }">{{ row.inventoryPosted ? '已入库' : '待确认入库' }}</template>
          </el-table-column>
        </el-table>
      </el-card>
    </section>

    <section v-else class="operation-shell">
      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>QMS首页</h2>
              <span>从采购收货预备单生成来料检验单</span>
            </div>
            <el-button type="primary" @click="createFromFirstReceive">从采购收货预备单生成来料检验</el-button>
          </div>
        </template>
        <div class="summary-grid">
          <article>
            <span>来料检验单</span>
            <strong>{{ inspections.length }}</strong>
            <p>支持检验结果和入库</p>
          </article>
          <article>
            <span>可生成来源单</span>
            <strong>{{ candidateReceives.length }}</strong>
            <p>采购收货预备单</p>
          </article>
          <article>
            <span>待检数量</span>
            <strong>{{ inspections.filter((item) => item.status === 'pending').length }}</strong>
            <p>等待检验动作</p>
          </article>
          <article>
            <span>已入库检验单</span>
            <strong>{{ inspections.filter((item) => item.inventoryPosted).length }}</strong>
            <p>已推送 WMS 库存</p>
          </article>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2 data-acceptance-id="page-internal-subject-title">{{ currentQmsPageName }}</h2></template>
        <div class="toolbar">
          <el-button @click="quickSearchVisible = !quickSearchVisible">
            {{ quickSearchVisible ? '收起快速搜索' : '展开快速搜索' }}
          </el-button>
          <span class="sort-help">快速搜索用于跨字段临时查找；精准查询请使用高级筛选。</span>
        </div>
        <div
          v-if="quickSearchVisible"
          class="toolbar"
          data-acceptance-id="standard-list-toolbar"
          data-pce-page-id="incoming-inspection"
          data-pce-toolbar-for="incoming-inspections-main"
        >
          <span data-acceptance-id="list-fuzzy-search-input">
            <el-autocomplete
              v-model="keyword"
              :fetch-suggestions="querySearchSuggestions"
              placeholder="搜索检验单、收货单、供应商、物料、状态"
              clearable
              @select="handleSuggestionSelect"
            />
          </span>
          <el-button data-acceptance-id="list-fuzzy-search-button" @click="clearSelection">搜索</el-button>
          <el-button
            data-acceptance-id="list-advanced-filter-toggle"
            data-pce-filter-toggle-for="incoming-inspections-main"
            :aria-expanded="String(showAdvancedFilters)"
            @click="showAdvancedFilters = !showAdvancedFilters"
          >
            {{ showAdvancedFilters ? '收起高级筛选' : '展开高级筛选' }}
          </el-button>
          <el-button data-acceptance-id="list-clear-filter-button" @click="resetFilters">清空筛选</el-button>
          <el-button data-acceptance-id="list-clear-sort-button" @click="resetSorting">清除排序</el-button>
          <el-button
            type="success"
            data-acceptance-id="list-export-current-result-button"
            data-pce-export-for="incoming-inspections-main"
            @click="exportCurrentResults"
          >
            导出当前结果
          </el-button>
          <span data-acceptance-id="list-result-count-visible">当前结果 {{ sortedInspections.length }} 条</span>
          <span data-acceptance-id="business-flow-selected-count">已选择 {{ selectedRows.length }} 条</span>
          <el-button @click="resetFilters">重置</el-button>
        </div>
        <div
          class="toolbar advanced-filter-toolbar"
          data-pce-page-id="incoming-inspection"
        >
          <strong>高级筛选</strong>
          <el-button @click="resetFilters">清空筛选</el-button>
          <el-button @click="resetSorting">清除排序</el-button>
          <el-button
            type="success"
            data-acceptance-id="list-export-current-result-button"
            data-pce-export-for="incoming-inspections-main"
            @click="exportCurrentResults"
          >
            导出当前结果
          </el-button>
          <el-button type="primary" plain @click="copyDiagnosticData">复制诊断数据</el-button>
          <span class="sort-help">排序：点击表格表头字段可升序/降序排序；点击“清除排序”恢复默认顺序。</span>
          <span class="sort-help">{{ currentSortText }}</span>
        </div>
        <div
          v-show="showAdvancedFilters"
          class="advanced-filter-panel"
          data-acceptance-id="list-advanced-filter-panel"
          data-pce-filter-for="incoming-inspections-main"
        >
          <label>
            <span>检验单号</span>
            <PceResultFilterSelect v-model="advancedFilters.inspectionNo" :rows="inspections" :fields="['inspectionNo']" />
          </label>
          <label>
            <span>来源收货单号</span>
            <PceResultFilterSelect v-model="advancedFilters.sourceReceiveNo" :rows="inspections" :fields="['sourceReceiveNo']" />
          </label>
          <label>
            <span>来源采购订单号</span>
            <PceResultFilterSelect v-model="advancedFilters.sourcePurchaseOrderNo" :rows="inspections" :fields="['sourcePurchaseOrderNo']" />
          </label>
          <label>
            <span>原始请购单号</span>
            <PceResultFilterSelect v-model="advancedFilters.rootRequestNo" :rows="inspections" :fields="['rootRequestNo']" />
          </label>
          <label>
            <span>供应商</span>
            <PceResultFilterSelect v-model="advancedFilters.supplierName" :rows="inspections" :fields="['supplierName']" />
          </label>
          <label>
            <span>仓库</span>
            <PceResultFilterSelect v-model="advancedFilters.warehouseName" :rows="inspections" :fields="['warehouseName']" />
          </label>
          <label>
            <span>物料编码</span>
            <PceResultFilterSelect v-model="advancedFilters.materialCode" :rows="inspections" :fields="['materialCode']" />
          </label>
          <label>
            <span>物料名称</span>
            <PceResultFilterSelect v-model="advancedFilters.materialName" :rows="inspections" :fields="['materialName']" />
          </label>
          <label>
            <span>检验状态</span>
            <el-select v-model="advancedFilters.status" clearable>
              <el-option v-for="item in inspectionStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </label>
          <label>
            <span>质量状态</span>
            <el-select v-model="advancedFilters.qualityStatus" clearable>
              <el-option v-for="item in qualityStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </label>
          <label>
            <span>入库状态</span>
            <el-select v-model="advancedFilters.inventoryPostStatus" clearable>
              <el-option label="未入库" value="notPosted" />
              <el-option label="已生成入库预备" value="inboundPrepared" />
              <el-option label="已入库" value="posted" />
            </el-select>
          </label>
          <label>
            <span>检验员</span>
            <PceResultFilterSelect v-model="advancedFilters.inspectorName" :rows="inspections" :fields="['inspectorName']" />
          </label>
          <label>
            <span>计划检验日期起</span>
            <el-date-picker v-model="advancedFilters.plannedInspectDateStart" type="date" value-format="YYYY-MM-DD" />
          </label>
          <label>
            <span>计划检验日期止</span>
            <el-date-picker v-model="advancedFilters.plannedInspectDateEnd" type="date" value-format="YYYY-MM-DD" />
          </label>
          <label>
            <span>实际检验日期起</span>
            <el-date-picker v-model="advancedFilters.actualInspectDateStart" type="date" value-format="YYYY-MM-DD" />
          </label>
          <label>
            <span>实际检验日期止</span>
            <el-date-picker v-model="advancedFilters.actualInspectDateEnd" type="date" value-format="YYYY-MM-DD" />
          </label>
          <label>
            <span>已生成入库预备</span>
            <el-select v-model="advancedFilters.inboundPrepared" clearable>
              <el-option label="是" :value="true" />
              <el-option label="否" :value="false" />
            </el-select>
          </label>
          <label>
            <span>已入库</span>
            <el-select v-model="advancedFilters.inventoryPosted" clearable>
              <el-option label="是" :value="true" />
              <el-option label="否" :value="false" />
            </el-select>
          </label>
        </div>
        <el-alert
          title="来料检验流程：待检 → 开始检验 → 填写检验结果 → 提交检验 → 生成检验合格入库预备 → 确认入库。确认入库前不改变库存，不生成应付。"
          type="info"
          show-icon
          :closable="false"
        />
        <div class="batch-bar" data-pce-section="incoming-inspection-batch-actions">
          <span>已选择 {{ selectedRows.length }} 条</span>
          <span>可开始 {{ qmsBatchCounts.start }} 条</span>
          <span>可提交 {{ qmsBatchCounts.submit }} 条</span>
          <span>可生成入库预备 {{ qmsBatchCounts.prepare }} 条</span>
          <span>待仓库确认入库 {{ qmsBatchCounts.post }} 条</span>
          <el-button size="small" @click="clearSelection">清空选择</el-button>
          <el-button size="small" type="primary" data-pce-action-id="start-incoming-inspections" :disabled="!qmsBatchCounts.start" :title="qmsBatchCounts.start ? '' : '所选记录没有待检单据。'" @click="runBatchStart">批量开始检验</el-button>
          <el-button size="small" type="warning" data-pce-action-id="submit-incoming-inspection-results" :disabled="!qmsBatchCounts.submit" :title="qmsBatchCounts.submit ? '' : '所选记录没有可提交的检验结果。'" @click="runBatchSubmit">批量提交检验结果</el-button>
          <el-button size="small" type="success" data-pce-action-id="create-qualified-inbound-prepares" :disabled="!qmsBatchCounts.prepare" :title="qmsBatchCounts.prepare ? '' : '所选记录没有可生成入库预备的检验单。'" @click="runBatchPrepareInbound">批量生成检验合格入库预备</el-button>
        </div>
        <div v-if="batchResult" class="batch-result" :class="batchMessageType">
          <button type="button" @click="batchResult = null">关闭</button>
          <strong>批量操作完成：</strong>
          <span>操作名称：{{ batchResult.operationName }}</span>
          <span>已选择：{{ batchResult.total }} 条</span>
          <span>成功：{{ batchResult.successCount }} 条</span>
          <span>失败/跳过：{{ batchResult.failedCount }} 条</span>
          <template v-if="batchResult.failedReason?.length">
            <span>失败原因：</span>
            <ol>
              <li v-for="reason in batchResult.failedReason" :key="reason">{{ reason }}</li>
            </ol>
            <span>下一步建议：{{ batchResult.nextSuggestion }}</span>
          </template>
        </div>
        <BusinessTableScrollContainer
          class="pce-baseline-table-shell"
          acceptance-id="business-table-scroll-incoming-inspections-main"
          page-id="incoming-inspection"
          table-id="incoming-inspections-main"
        >
        <el-table ref="listTableRef" :data="sortedInspections" border stripe height="520" class="global-sort-arrow" scrollbar-always-on @selection-change="handleSelectionChange" @sort-change="handleSortChange">
          <el-table-column type="selection" :selectable="(row) => !row.formalAuthority" width="48" fixed="left" class-name="business-table-selection-column" header-class-name="business-table-selection-column" />
          <el-table-column type="index" label="序号" width="70" fixed="left" class-name="pce-fixed-index-column" header-class-name="pce-fixed-index-column" />
          <el-table-column prop="inspectionNo" label="检验单号" min-width="170" sortable="custom" fixed="left" class-name="pce-fixed-primary-no-column" header-class-name="pce-fixed-primary-no-column" />
          <el-table-column prop="sourceReceiveNo" label="来源收货单号" min-width="150" sortable="custom" />
          <el-table-column prop="sourceOrderNo" label="来源采购订单号" min-width="150" sortable="custom" />
          <el-table-column prop="rootRequestNo" label="原始请购单号" min-width="150" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商" sortable="custom" />
          <el-table-column prop="warehouseName" label="仓库" sortable="custom" />
          <el-table-column prop="inspectorName" label="检验员" sortable="custom" />
          <el-table-column prop="plannedInspectDate" label="计划检验日期" sortable="custom" />
          <el-table-column prop="actualInspectDate" label="实际检验日期" sortable="custom" />
          <el-table-column prop="status" label="状态" sortable="custom">
            <template #default="{ row }"><el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="inventoryPostStatus" label="入库状态" min-width="130" sortable="custom">
            <template #default="{ row }">{{ inventoryPostStatusLabel(row.inventoryPostStatus, row) }}</template>
          </el-table-column>
          <el-table-column prop="inventoryPostMessage" label="入库结果" min-width="180" sortable="custom" />
          <el-table-column prop="remark" label="备注" min-width="180" sortable="custom" />
          <el-table-column label="操作" fixed="right" :width="getActionColumnWidth(['详情', '生成检验合格入库预备'])" class-name="payment-fixed-action-column" header-class-name="payment-fixed-action-column">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button size="small" class="app-action-button-sm" @click="router.push(`/qms/incoming-inspection/${row.id}`)">详情</el-button>
                <el-button v-if="!row.formalAuthority && row.status === 'pending'" size="small" class="app-action-button-sm" type="primary" @click="startInspectionFromList(row)">开始检验</el-button>
                <el-button v-if="!row.formalAuthority && row.status === 'inspecting'" size="small" class="app-action-button-md" type="primary" @click="router.push(`/qms/incoming-inspection/${row.id}`)">填写检验结果</el-button>
                <el-button v-if="!row.formalAuthority && row.status === 'inspected' && hasInboundQty(row)" size="small" class="app-action-button-lg" type="success" @click="prepareInboundFromList(row)">生成检验合格入库预备</el-button>
                <el-button v-if="row.status === 'inboundPrepared'" size="small" class="app-action-button-lg" type="success" @click="viewInboundPrepareFromList(row)">查看入库预备</el-button>
                <el-button v-if="row.status === 'inventoryPosted'" size="small" class="app-action-button-sm" @click="viewInventoryTransactions">查看库存</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
        </BusinessTableScrollContainer>
      </el-card>
    </section>
  </main>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import PceResultFilterSelect from '../components/PceResultFilterSelect.vue'
import { useRoute, useRouter } from 'vue-router'
import { createInspectionPreviewFromPurchaseReceive, listPurchaseReceives } from '../wms/purchaseReceiveStore.js'
import {
  createInboundPrepareTaskFromInspection,
} from '../wms/wmsStore.js'
import { getEmployeeOptions } from '../manufacturing/manufacturingReferenceService.js'
import {
  batchStartInspections,
  batchSubmitInspectionResults,
  cancelIncomingInspection,
  getIncomingInspectionById,
  listIncomingInspections,
  saveIncomingInspectionResult,
  startIncomingInspection,
  submitIncomingInspectionResult,
  writeQmsLog,
} from '../qms/qmsStore.js'
import { buildMultiFieldSuggestions, filterSuggestions } from '../runtime/filterSuggestionEngine.js'
import BusinessTableScrollContainer from '../components/BusinessTableScrollContainer.vue'
import { getActionColumnWidth } from '../runtime/tableActionColumnEngine.js'
import { sortRecords } from '../runtime/tableSortEngine.js'
import { resolvePageNameConsumption } from '../governance/pageNameConsumer.js'
import { exportRowsToCsv as exportRowsToCsvUtil } from '../manufacturing/foundationTableUtils.js'
import { formalExecutionApi } from '@/api/formalExecution.js'
import {
  goList,
  goParent,
  goSource,
} from '../runtime/navigationRules.js'

const route = useRoute()
const router = useRouter()
const incomingInspectionName = resolvePageNameConsumption({ pageCode: 'incoming-inspection', route: '/qms/incoming-inspections' })
const currentQmsPageName = computed(() => route.path.startsWith('/qms/incoming-inspection')
  ? incomingInspectionName.pageTitle
  : 'QMS首页')
const currentQmsModuleName = computed(() => currentQmsPageName.value)

function isQmsNavActive(type) {
  if (type === 'inspection') return route.path.startsWith('/qms/incoming-inspection')
  return route.path === '/qms'
}
const inspections = ref([])
const keyword = ref('')
const quickSearchVisible = ref(true)
const showAdvancedFilters = ref(false)
const advancedFilters = ref(defaultAdvancedFilters())
const message = ref('')
const messageType = ref('success')
const sortState = ref({ key: '', direction: 'asc' })
const selectedRows = ref([])
const listTableRef = ref(null)
const copyStatus = ref('')
const batchResult = ref(null)
const batchMessageType = ref('success')
const editDraft = ref({ lines: [] })
const detail = computed(() => {
  if (!route.params.id) return null
  return inspections.value.find((item) => String(item.id) === String(route.params.id)) || getIncomingInspectionById(route.params.id)
})
const detailLines = computed(() => detail.value?.status === 'inspecting' ? editDraft.value.lines || [] : detail.value?.lines || [])
const inboundPrepareLines = computed(() => (detail.value?.lines || []).filter((line) => Number(line.qualifiedQty || 0) + Number(line.concessionQty || 0) > 0))
const employeeOptions = computed(() => getEmployeeOptions())
const receiveSourceRecord = computed(() => detail.value ? {
  sourceType: 'purchaseReceive',
  sourceReceiveId: detail.value.sourceReceiveId,
  sourceReceiveNo: detail.value.sourceReceiveNo,
} : {})
const orderSourceRecord = computed(() => detail.value ? {
  sourceType: 'scmPurchaseOrder',
  sourceOrderId: detail.value.sourceOrderId,
  sourceOrderNo: detail.value.sourceOrderNo,
} : {})
const candidateReceives = computed(() => listPurchaseReceives().filter((item) => !['cancelled', 'inspectionPrepared'].includes(item.status)))
const filteredInspections = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  return inspections.value.filter((row) => {
    const keywordMatched = !text || `${JSON.stringify(row)} ${statusLabel(row.status)} ${qualityStatusLabel(row.qualityStatus)}`.toLowerCase().includes(text)
    return keywordMatched && matchesAdvancedFilters(row)
  })
})
const inspectionStatusOptions = [
  { label: '待检', value: 'pending' },
  { label: '检验中', value: 'inspecting' },
  { label: '已检验', value: 'inspected' },
  { label: '已生成入库预备', value: 'inboundPrepared' },
  { label: '已入库', value: 'inventoryPosted' },
  { label: '已拒收', value: 'rejected' },
  { label: '已取消', value: 'cancelled' },
]
const qualityStatusOptions = [
  { label: '合格', value: 'qualified' },
  { label: '让步接收', value: 'concession' },
  { label: '拒收', value: 'rejected' },
  { label: '退货待处理', value: 'returnPending' },
  { label: '已报废', value: 'scrapped' },
  { label: '返工待处理', value: 'reworkPending' },
]
const inspectionSortColumns = [
  { key: 'inspectionNo', sortType: 'string' },
  { key: 'sourceReceiveNo', sortType: 'string' },
  { key: 'sourceOrderNo', sortType: 'string' },
  { key: 'rootRequestNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'warehouseName', sortType: 'string' },
  { key: 'inspectorName', sortType: 'string' },
  { key: 'plannedInspectDate', sortType: 'date' },
  { key: 'actualInspectDate', sortType: 'date' },
  { key: 'status', sortType: 'status' },
  { key: 'inventoryPostStatus', sortType: 'status' },
  { key: 'inventoryPostMessage', sortType: 'string' },
  { key: 'remark', sortType: 'string' },
]
const sortedInspections = computed(() => sortRecords(filteredInspections.value, sortState.value, inspectionSortColumns))
const currentSortText = computed(() => {
  if (!sortState.value.key) return '当前排序：默认顺序'
  const labels = {
    inspectionNo: '检验单号',
    sourceReceiveNo: '来源收货单号',
    sourceOrderNo: '来源采购订单号',
    rootRequestNo: '原始请购单号',
    supplierName: '供应商',
    warehouseName: '仓库',
    inspectorName: '检验员',
    plannedInspectDate: '计划检验日期',
    actualInspectDate: '实际检验日期',
    status: '状态',
    inventoryPostStatus: '入库状态',
    inventoryPostMessage: '入库结果',
    remark: '备注',
  }
  return `当前排序：${labels[sortState.value.key] || sortState.value.key} / ${sortState.value.direction === 'desc' ? '降序' : '升序'}`
})
const selectedIds = computed(() => selectedRows.value.map((row) => row.id).filter(Boolean))
const sortableColumns = inspectionSortColumns.map((item) => item.key)
const exportColumns = [
  { key: 'inspectionNo', label: '检验单号' },
  { key: 'sourceReceiveNo', label: '来源收货单号' },
  { key: 'sourceOrderNo', label: '来源采购订单号' },
  { key: 'rootRequestNo', label: '原始请购单号' },
  { key: 'supplierName', label: '供应商' },
  { key: 'warehouseName', label: '仓库' },
  { key: 'inspectorName', label: '检验员' },
  { key: 'plannedInspectDate', label: '计划检验日期' },
  { key: 'actualInspectDate', label: '实际检验日期' },
  { key: 'statusText', label: '状态' },
  { key: 'inventoryPostStatusText', label: '入库状态' },
  { key: 'inventoryPostMessage', label: '入库结果' },
  { key: 'remark', label: '备注' },
]
const exportRows = computed(() => sortedInspections.value.map((row) => ({
  ...row,
  statusText: statusLabel(row.status),
  inventoryPostStatusText: inventoryPostStatusLabel(row.inventoryPostStatus, row),
})))
const diagnosticData = computed(() => ({
  page: 'incoming-inspections',
  version: 'V1.13.29.3.2',
  quickSearch: keyword.value,
  advancedFilterState: { ...advancedFilters.value },
  sortState: { ...sortState.value },
  resultCount: sortedInspections.value.length,
  selectedCount: selectedRows.value.length,
  exportEnabled: true,
  sortableColumns,
  sortArrowStyle: 'no-tail-bold-arrow',
  sortArrowShape: 'upright-triangle',
  timestamp: new Date().toISOString(),
}))
const qmsBatchCounts = computed(() => ({
  start: selectedRows.value.filter((row) => row.status === 'pending').length,
  submit: selectedRows.value.filter((row) => row.status === 'inspecting' && hasInspectionResultQty(row)).length,
  prepare: selectedRows.value.filter((row) => row.status === 'inspected' && canPrepareInbound(row)).length,
  post: selectedRows.value.filter((row) => row.status === 'inboundPrepared').length,
}))
const detailFields = computed(() => detail.value ? [
  { label: '检验单号', value: detail.value.inspectionNo },
  { label: '来源收货单号', value: detail.value.sourceReceiveNo || '-' },
  { label: '来源采购订单号', value: detail.value.sourceOrderNo || '-' },
  { label: '来源核价单号', value: detail.value.sourcePriceApprovalNo || '-' },
  { label: '原始请购单号', value: detail.value.rootRequestNo || '-' },
  { label: '供应商', value: detail.value.supplierName || '-' },
  { label: '仓库', value: detail.value.warehouseName || '-' },
  { label: '检验员', value: detail.value.inspectorName || '-' },
  { label: '计划检验日期', value: detail.value.plannedInspectDate || '-' },
  { label: '实际检验日期', value: detail.value.actualInspectDate || '-' },
  { label: '入库状态', value: detail.value.inventoryPostStatus || 'notPosted' },
  { label: '入库结果', value: detail.value.inventoryPostMessage || '-' },
  { label: '状态', value: statusLabel(detail.value.status) },
  { label: '备注', value: detail.value.remark || '-' },
] : [])
const flowPosition = computed(() => {
  const status = detail.value?.status || 'pending'
  return {
    pending: { current: '待检', next: '开始检验' },
    inspecting: { current: '检验中', next: '填写并提交检验结果' },
    inspected: { current: '已检验', next: '生成检验合格入库预备' },
    inboundPrepared: { current: '已生成入库预备', next: '确认入库' },
    inventoryPosted: { current: '已入库', next: '流程完成' },
    rejected: { current: '已拒收', next: '查看不合格处理' },
    cancelled: { current: '已取消', next: '流程终止' },
  }[status] || { current: status, next: '-' }
})

function adaptFormalInspection(row = {}) {
  const items = Array.isArray(row.items) ? row.items : []
  return {
    ...row,
    sourceReceiveNo: row.receiptNo || '',
    sourceOrderNo: row.purchaseOrderNo || '',
    actualInspectDate: row.inspectionDate || '',
    qualityStatus: row.status === 'qualified' ? 'qualified' : (row.status === 'rejected' ? 'rejected' : 'pending'),
    status: row.status === 'qualified' ? 'inspected' : row.status,
    lines: items,
    formalAuthority: true,
    authoritySource: 'procurement.PurchaseInspection',
  }
}

async function refresh() {
  const response = await formalExecutionApi.qualityFacts()
  if (!response?.success) {
    inspections.value = []
    notify(response?.error?.message || '正式来料检验事实读取失败', 'error')
    return
  }
  inspections.value = (response.data?.inspections || []).map(adaptFormalInspection)
}

function notify(text, type = 'success') {
  message.value = text
  messageType.value = type
  window.clearTimeout(notify.timer)
  notify.timer = window.setTimeout(() => {
    message.value = ''
  }, 2400)
}

function defaultAdvancedFilters() {
  return {
    inspectionNo: '',
    sourceReceiveNo: '',
    sourcePurchaseOrderNo: '',
    rootRequestNo: '',
    supplierName: '',
    warehouseName: '',
    materialCode: '',
    materialName: '',
    status: '',
    qualityStatus: '',
    inventoryPostStatus: '',
    inspectorName: '',
    plannedInspectDateStart: '',
    plannedInspectDateEnd: '',
    actualInspectDateStart: '',
    actualInspectDateEnd: '',
    inboundPrepared: '',
    inventoryPosted: '',
  }
}

function fuzzyMatch(value, query) {
  if (!query) return true
  return String(value || '').toLowerCase().includes(String(query).trim().toLowerCase())
}

function rowHasLineMatch(row, field, query) {
  if (!query) return true
  return (row.lines || []).some((line) => fuzzyMatch(line[field], query))
}

function dateInRange(value, start, end) {
  if (!start && !end) return true
  const date = String(value || '')
  if (!date) return false
  if (start && date < start) return false
  if (end && date > end) return false
  return true
}

function rowHasQualityStatus(row, qualityStatus) {
  if (!qualityStatus) return true
  return row.qualityStatus === qualityStatus || (row.lines || []).some((line) => line.qualityStatus === qualityStatus)
}

function matchesAdvancedFilters(row) {
  const filters = advancedFilters.value
  return fuzzyMatch(row.inspectionNo, filters.inspectionNo)
    && fuzzyMatch(row.sourceReceiveNo, filters.sourceReceiveNo)
    && fuzzyMatch(row.sourceOrderNo || row.sourcePurchaseOrderNo, filters.sourcePurchaseOrderNo)
    && fuzzyMatch(row.rootRequestNo, filters.rootRequestNo)
    && fuzzyMatch(row.supplierName, filters.supplierName)
    && fuzzyMatch(row.warehouseName, filters.warehouseName)
    && rowHasLineMatch(row, 'materialCode', filters.materialCode)
    && rowHasLineMatch(row, 'materialName', filters.materialName)
    && (!filters.status || row.status === filters.status)
    && rowHasQualityStatus(row, filters.qualityStatus)
    && (!filters.inventoryPostStatus || normalizeInventoryPostStatus(row) === filters.inventoryPostStatus)
    && fuzzyMatch(row.inspectorName, filters.inspectorName)
    && dateInRange(row.plannedInspectDate, filters.plannedInspectDateStart, filters.plannedInspectDateEnd)
    && dateInRange(row.actualInspectDate, filters.actualInspectDateStart, filters.actualInspectDateEnd)
    && (filters.inboundPrepared === '' || Boolean(row.inboundPrepared || row.status === 'inboundPrepared' || row.inboundPrepareTaskIds?.length) === filters.inboundPrepared)
    && (filters.inventoryPosted === '' || Boolean(row.inventoryPosted || row.status === 'inventoryPosted') === filters.inventoryPosted)
}

function resetFilters() {
  keyword.value = ''
  advancedFilters.value = defaultAdvancedFilters()
  clearSelection()
}

function handleSelectionChange(rows) {
  selectedRows.value = rows || []
}

function clearSelection() {
  selectedRows.value = []
  listTableRef.value?.clearSelection?.()
}

function resetSorting() {
  sortState.value = { key: '', direction: 'asc' }
  clearSelection()
}

function handleSortChange({ prop, order }) {
  sortState.value = { key: prop || '', direction: order === 'descending' ? 'desc' : 'asc' }
  clearSelection()
}

function nextBatchSuggestion(reasons = []) {
  const text = reasons.join('；')
  if (text.includes('请先提交收货预备')) return '建议先点击“批量提交收货预备”。'
  if (text.includes('已生成')) return '建议点击对应行查看已生成单据。'
  if (text.includes('状态')) return '建议检查当前状态后再执行批量操作。'
  return '请按失败原因处理后重新执行。'
}

function normalizeBatchResult(result = {}, operationName = '批量操作') {
  const failedReason = result.failedReason || []
  return {
    operationName,
    total: result.total ?? selectedIds.value.length,
    successCount: result.successCount || 0,
    failedCount: result.failedCount || 0,
    failedReason,
    nextSuggestion: nextBatchSuggestion(failedReason),
  }
}

function showBatchResult(result, operationName) {
  refresh()
  clearSelection()
  batchResult.value = normalizeBatchResult(result || {}, operationName)
  batchMessageType.value = result?.failedCount ? (result.successCount ? 'warning' : 'error') : 'success'
}

function buildPageBatchResult(ids, handler, label) {
  const result = {
    total: ids.length,
    successCount: 0,
    failedCount: 0,
    successItems: [],
    failedItems: [],
    failedReason: [],
  }
  ids.forEach((id) => {
    const item = getIncomingInspectionById(id)
    const no = item?.inspectionNo || id
    const outcome = handler(id, item)
    if (outcome?.success === false) {
      const reason = outcome.error || outcome.message || '当前状态不满足批量操作条件。'
      result.failedCount += 1
      result.failedItems.push({ id, no, reason })
      result.failedReason.push(`${no}：${reason}`)
      return
    }
    result.successCount += 1
    result.successItems.push({ id, no })
  })
  writeQmsLog(label, { result: `成功 ${result.successCount} 条，失败 ${result.failedCount} 条；${result.failedReason.join('；')}` })
  if (result.failedCount) writeQmsLog('批量操作失败原因', { result: result.failedReason.join('；') })
  return result
}

function runBatchStart() {
  if (!selectedIds.value.length) return notify('请先选择要批量处理的来料检验单', 'warning')
  if (!qmsBatchCounts.value.start) return notify('所选记录没有待检单据。', 'warning')
  showBatchResult(batchStartInspections(selectedIds.value), '批量开始检验')
}

function runBatchSubmit() {
  if (!selectedIds.value.length) return notify('请先选择要批量处理的来料检验单', 'warning')
  if (!qmsBatchCounts.value.submit) return notify('所选记录没有可提交的检验结果。', 'warning')
  showBatchResult(batchSubmitInspectionResults(selectedIds.value), '批量提交检验结果')
}

function runBatchPrepareInbound() {
  if (!selectedIds.value.length) return notify('请先选择要批量处理的来料检验单', 'warning')
  if (!qmsBatchCounts.value.prepare) return notify('所选记录没有可生成入库预备的检验单。', 'warning')
  showBatchResult(buildPageBatchResult(selectedIds.value, (id) => createInboundPrepareTaskFromInspection(id), '批量生成检验合格入库预备'), '批量生成检验合格入库预备')
}

function statusLabel(status) {
  return {
    pending: '待检',
    inspecting: '检验中',
    inspected: '已检验',
    inboundPrepared: '已生成入库预备',
    released: '已放行',
    partiallyReleased: '部分放行',
    rejected: '已拒收',
    inventoryPosted: '已入库',
    cancelled: '取消',
  }[status] || status || '-'
}

function statusType(status) {
  return {
    pending: 'warning',
    inspecting: 'primary',
    inspected: 'success',
    inboundPrepared: 'warning',
    released: 'success',
    partiallyReleased: 'warning',
    inventoryPosted: 'success',
    rejected: 'danger',
    cancelled: 'info',
  }[status] || 'info'
}

function inspectResultLabel(result) {
  return {
    pending: '待检',
    qualified: '合格',
    unqualified: '不合格',
    partial: '部分合格',
  }[result] || result || '-'
}

function dispositionLabel(type) {
  return {
    qualified: '合格',
    concession: '让步接收',
    return: '退货',
    scrap: '报废',
    rework: '返工',
    mixed: '混合处理',
    pending: '待处理',
  }[type] || type || '-'
}

function qualityStatusLabel(status) {
  return {
    pending: '待检',
    qualified: '合格',
    unqualified: '不合格',
    concession: '让步接收',
    returnPending: '退货待处理',
    scrapped: '已报废',
    reworkPending: '返工待处理',
  }[status] || status || '-'
}

function normalizeInventoryPostStatus(row = {}) {
  if (row.inventoryPosted || row.status === 'inventoryPosted' || row.inventoryPostStatus === 'posted') return 'posted'
  if (row.inboundPrepared || row.status === 'inboundPrepared' || row.inventoryPostStatus === 'inboundPrepared' || row.inboundPrepareTaskIds?.length) return 'inboundPrepared'
  return row.inventoryPostStatus || 'notPosted'
}

function inventoryPostStatusLabel(status, row = {}) {
  const normalized = normalizeInventoryPostStatus({ ...row, inventoryPostStatus: status || row.inventoryPostStatus })
  return {
    notPosted: '未入库',
    inboundPrepared: '已生成入库预备',
    posted: '已入库',
  }[normalized] || normalized || '-'
}

function cloneDraft(value) {
  return JSON.parse(JSON.stringify(value || { lines: [] }))
}

function syncDraft() {
  editDraft.value = cloneDraft(detail.value)
}

function syncInspectorName() {
  const employee = employeeOptions.value.find((item) => item.id === editDraft.value.inspectorId)
  editDraft.value.inspectorName = employee?.name || employee?.raw?.name || ''
  ;(editDraft.value.lines || []).forEach((line) => {
    line.inspectorId = editDraft.value.inspectorId
    line.inspectorName = editDraft.value.inspectorName
  })
}

function recalculateLine(row) {
  const qualified = Number(row.qualifiedQty) || 0
  const unqualified = Number(row.unqualifiedQty) || 0
  const concession = Number(row.concessionQty) || 0
  const returnQty = Number(row.returnQty) || 0
  const scrap = Number(row.scrapQty) || 0
  const rework = Number(row.reworkQty) || 0
  if (qualified > 0 && unqualified > 0) row.inspectResult = 'partial'
  else if (qualified > 0) row.inspectResult = 'qualified'
  else if (unqualified > 0) row.inspectResult = 'unqualified'
  row.dispositionType = concession > 0 && (returnQty > 0 || scrap > 0 || rework > 0) ? 'mixed'
    : concession > 0 ? 'concession'
      : returnQty > 0 ? 'return'
        : scrap > 0 ? 'scrap'
          : rework > 0 ? 'rework'
            : qualified > 0 && unqualified === 0 ? 'qualified'
              : row.dispositionType || 'pending'
}

function buildDraftPayload() {
  syncInspectorName()
  return {
    ...editDraft.value,
    lines: (editDraft.value.lines || []).map((line) => {
      recalculateLine(line)
      line.actualInspectDate = line.actualInspectDate || editDraft.value.actualInspectDate
      return line
    }),
  }
}

function querySearchSuggestions(queryString, callback) {
  const records = inspections.value.flatMap((row) => [
    {
      inspectionNo: row.inspectionNo,
      sourceReceiveNo: row.sourceReceiveNo,
      sourceOrderNo: row.sourceOrderNo,
      supplierName: row.supplierName,
      warehouseName: row.warehouseName,
      inspectorName: row.inspectorName,
      status: statusLabel(row.status),
    },
    ...(row.lines || []).map((line) => ({
      materialCode: line.materialCode,
      materialName: line.materialName,
      batchNo: line.batchNo,
      inspectResult: inspectResultLabel(line.inspectResult),
    })),
  ])
  const suggestions = buildMultiFieldSuggestions(records, ['inspectionNo', 'sourceReceiveNo', 'sourceOrderNo', 'supplierName', 'warehouseName', 'inspectorName', 'status', 'materialCode', 'materialName', 'batchNo', 'inspectResult'])
  callback(filterSuggestions(queryString, suggestions))
}

function handleSuggestionSelect(item) {
  keyword.value = item.value
}

function todayStamp() {
  return new Date().toISOString().slice(0, 10).replaceAll('-', '')
}

function exportCurrentResults() {
  exportRowsToCsvUtil(exportRows.value, exportColumns, `incoming-inspections-${todayStamp()}.csv`)
  notify(`已导出当前筛选结果 ${exportRows.value.length} 条`)
}

async function copyDiagnosticData() {
  const text = JSON.stringify(diagnosticData.value, null, 2)
  try {
    if (navigator?.clipboard?.writeText) await navigator.clipboard.writeText(text)
    else fallbackCopy(text)
    copyStatus.value = '已复制诊断数据'
    notify('已复制诊断数据')
  } catch (error) {
    try {
      fallbackCopy(text)
      copyStatus.value = '已复制诊断数据'
      notify('已复制诊断数据')
    } catch (fallbackError) {
      copyStatus.value = '复制失败，请重试'
      notify('复制失败，请重试', 'warning')
    }
  }
}

function fallbackCopy(text) {
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', 'readonly')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  document.body.appendChild(textarea)
  textarea.select()
  document.execCommand('copy')
  document.body.removeChild(textarea)
}

function createFromFirstReceive() {
  const receive = candidateReceives.value[0]
  if (!receive) return notify('暂无可用采购收货预备单', 'warning')
  const outcome = createInspectionPreviewFromPurchaseReceive(receive.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify(`${outcome.existed ? '已存在' : '已生成'}来料检验预备单 ${outcome.inspectionNo}，库存余额不变`)
}

function hasInboundQty(row) {
  return (row.lines || []).some((line) => Number(line.qualifiedQty || 0) + Number(line.concessionQty || 0) > 0 && !line.inventoryPosted && !line.inboundPrepared)
}

function hasInspectionResultQty(row) {
  return (row.lines || []).some((line) => (
    Number(line.qualifiedQty || 0)
    + Number(line.unqualifiedQty || 0)
    + Number(line.concessionQty || 0)
    + Number(line.returnQty || 0)
    + Number(line.scrapQty || 0)
    + Number(line.reworkQty || 0)
  ) > 0)
}

function canPrepareInbound(row) {
  return hasInboundQty(row)
}

function startInspection() {
  if (!detail.value) return
  const outcome = startIncomingInspection(detail.value.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  editDraft.value = cloneDraft(outcome.inspection)
  notify('已开始检验')
}

function startInspectionFromList(row) {
  const outcome = startIncomingInspection(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  router.push(`/qms/incoming-inspection/${row.id}`)
  notify('已开始检验')
}

function saveResult() {
  if (!detail.value) return
  const outcome = saveIncomingInspectionResult(detail.value.id, buildDraftPayload())
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  editDraft.value = cloneDraft(outcome.inspection)
  notify('检验结果已保存')
}

function submitResult() {
  if (!detail.value) return
  const outcome = submitIncomingInspectionResult(detail.value.id, buildDraftPayload())
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  editDraft.value = cloneDraft(outcome.inspection)
  notify('检验结果已提交')
}

function prepareInbound() {
  if (!detail.value) return
  const outcome = createInboundPrepareTaskFromInspection(detail.value.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify(`已生成检验合格入库预备 ${outcome.taskIds?.length || 0} 条`)
}

function viewInboundPrepare() {
  const taskId = detail.value?.inboundPrepareTaskIds?.[0]
  if (!taskId) return notify('未找到当前检验单关联的检验合格入库预备。', 'warning')
  router.push(`/wms/warehouse-task/${taskId}`)
}

function viewInboundPrepareFromList(row) {
  const taskId = row?.inboundPrepareTaskIds?.[0]
  if (!taskId) return notify('未找到当前检验单关联的检验合格入库预备。', 'warning')
  router.push(`/wms/warehouse-task/${taskId}`)
}

function prepareInboundFromList(row) {
  const outcome = createInboundPrepareTaskFromInspection(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  router.push(`/qms/incoming-inspection/${row.id}`)
  notify(`已生成检验合格入库预备 ${outcome.taskIds?.length || 0} 条`)
}

function viewInventoryTransactions() {
  notify('已切换到 WMS 库存流水，可按检验单号搜索入库结果。')
  router.push('/wms/inventory-transactions')
}

function viewInventoryBalances() {
  notify('已切换到 WMS 库存余额，可按物料或批号搜索入库结果。')
  router.push('/wms/inventory-balances')
}

function cancelInspection(row) {
  const outcome = cancelIncomingInspection(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify('来料检验预备单已取消')
}

watch([keyword, advancedFilters], () => {
  clearSelection()
}, { deep: true })

watch(() => route.fullPath, () => {
  refresh()
  syncDraft()
  quickSearchVisible.value = true
}, { immediate: true })

watch(detail, syncDraft)
</script>

<style scoped>
.qms-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  min-height: 100%;
  padding: 22px;
  background: #f4f7fb;
  color: #172033;
}

.page-header,
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.eyebrow,
.summary-grid span,
.info-grid span,
.card-header span {
  color: #64748b;
  font-size: 13px;
}

h1,
h2 {
  margin: 0;
}

.page-tabs,
.button-row,
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.toolbar {
  margin-bottom: 12px;
}

.advanced-filter-toolbar {
  padding: 10px 12px;
  border: 1px solid #d9e4f2;
  border-radius: 8px;
  background: #f8fbff;
}

.batch-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: 12px 0;
  padding: 10px 12px;
  border: 1px solid #d9e4f2;
  border-radius: 8px;
  background: #f8fbff;
}

.advanced-filter-panel {
  display: grid;
  grid-template-columns: repeat(4, minmax(180px, 1fr));
  gap: 10px;
  margin: 0 0 12px;
  padding: 12px;
  border: 1px solid #d9e4f2;
  border-radius: 8px;
  background: #fff;
}

.advanced-filter-panel label {
  min-width: 0;
}

.advanced-filter-panel span {
  display: block;
  margin-bottom: 6px;
  color: #64748b;
  font-size: 13px;
}

.batch-result {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 12px 0;
  padding: 12px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #eff6ff;
  color: #172033;
  line-height: 1.6;
}

.batch-result.warning {
  border-color: #fde68a;
  background: #fffbeb;
}

.batch-result.error {
  border-color: #fecaca;
  background: #fef2f2;
}

.batch-result button {
  align-self: flex-end;
  border: 0;
  background: transparent;
  color: #2563eb;
  cursor: pointer;
}

.page-tabs a {
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  padding: 7px 12px;
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 700;
  text-decoration: none;
}

.operation-shell {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.summary-grid,
.info-grid,
.edit-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-grid article,
.info-grid article,
.edit-grid label {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  padding: 12px;
}

.edit-grid label span {
  display: block;
  margin-bottom: 6px;
  color: #64748b;
  font-size: 13px;
}

.flow-box {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 12px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #eff6ff;
  padding: 12px;
  color: #1e3a8a;
}

.qms-inspection-table {
  width: 100%;
}

.qms-number-input {
  width: 132px;
}

.qms-inspection-table :deep(.el-input-number) {
  width: 132px;
}

.qms-inspection-table :deep(.el-input-number__decrease),
.qms-inspection-table :deep(.el-input-number__increase) {
  width: 28px;
}

.summary-grid strong,
.info-grid strong {
  display: block;
  margin-top: 6px;
  font-size: 18px;
}

@media (max-width: 900px) {
  .page-header,
  .card-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .summary-grid,
  .info-grid,
  .edit-grid,
  .advanced-filter-panel {
    grid-template-columns: 1fr;
  }
}
</style>

<template>
  <main class="g2-page" data-acceptance-id="group2-comparison-preview" data-read-only="true">
    <FoundationBreadcrumb group="第2组 物料与产品工程" :module="title" show-return />
    <section class="hero">
      <div><p>企业基础资料 · 第2组</p><h1>{{ title }}真实数据对照 / 人工验收准备</h1><small>来源 → 当前正式数据 → 差异 → 预览 → 用户验收</small></div>
      <span>只读 · 正式新增为0</span>
    </section>

    <nav class="tabs" aria-label="Group 2 对照页">
      <router-link v-for="tab in tabs" :key="tab.entity" :to="`/foundation/group2-comparison/${tab.entity}`">{{ tab.label }}</router-link>
    </nav>

    <section v-if="loading" class="panel">正在读取来源快照和正式模型……</section>
    <section v-else-if="error" class="panel error">{{ error }}</section>
    <template v-else>
      <section class="state panel">
        <div><span>正式模型</span><strong>{{ facts.formalModel }}</strong></div>
        <div><span>已开发</span><strong>{{ developedLabel }}</strong></div>
        <div><span>数据存在</span><strong>{{ enumLabel(dataPresentLabel) }}</strong></div>
        <div><span>用户已验收</span><strong>等待定向复验</strong></div>
        <div><span>就绪状态</span><strong>{{ enumLabel(readyLabel) }}</strong></div>
      </section>

      <section v-if="entity !== 'product-versions-configurations'" class="summary">
        <article><span>来源记录</span><strong>{{ facts.sourceRecordCount }}</strong></article>
        <article v-if="facts.validSourceCount !== undefined"><span>有效来源</span><strong>{{ facts.validSourceCount }}</strong></article>
        <article v-if="facts.distinctSourceCandidateCount !== undefined"><span>去重产品候选</span><strong>{{ facts.distinctSourceCandidateCount }}</strong></article>
        <article><span>正式记录</span><strong>{{ facts.formalRecordCount }}</strong></article>
        <article class="good"><span>{{ entity === 'materials' ? '业务属性匹配' : '精确匹配' }}</span><strong>{{ entity === 'materials' ? facts.matchCount : facts.exactMatchCount }}</strong></article>
        <article v-if="entity === 'materials'"><span>来源编码精确一致</span><strong>{{ facts.sourceCodeExactMatchCount }}</strong></article>
        <article class="blue"><span>拟映射</span><strong>{{ facts.proposedMappingCount }}</strong></article>
        <article class="warn"><span>缺失/无效来源</span><strong>{{ facts.missingSourceCount }}</strong></article>
        <article class="danger"><span>冲突</span><strong>{{ facts.conflictCount }}</strong></article>
        <article><span>历史测试</span><strong>{{ facts.testHistoricalCount }}</strong></article>
        <article><span>正式库非当前来源</span><strong>{{ facts.formalOutsideCurrentSourceCount }}</strong></article>
      </section>

      <template v-if="entity === 'materials'">
        <DataPanel title="自制半成品板材计量单位定向复验" :count="facts.targetedRemediation?.targetCount" note="精确目标集由来源文件、来源类型、自制属性及正式来源身份共同限定；本页只读回显正式写入结果。">
          <div class="chips"><span>通过 {{ facts.targetedRemediation?.passCount }} / {{ facts.targetedRemediation?.targetCount }}</span><span>正式计量单位：平方米</span><span>用户状态：等待定向复验</span><span>正式物料新增：0</span></div>
          <table><thead><tr><th>来源行</th><th>来源编码</th><th>正式物料ID</th><th>正式编码</th><th>正式名称</th><th>当前计量单位</th><th>目标计量单位</th><th>自制/采购</th><th>物料类型</th><th>结果</th><th>数据来源</th></tr></thead>
          <tbody><tr v-for="row in facts.targetedRemediation?.rows" :key="row.materialId"><td>{{ row.sourceRow }}</td><td>{{ row.sourceCode }}</td><td>{{ row.materialId }}</td><td>{{ row.formalCode }}</td><td><strong>{{ row.formalName }}</strong></td><td>{{ row.currentUom }}</td><td>{{ row.proposedUom }}</td><td>{{ enumLabel(row.makeBuy) }}</td><td>{{ enumLabel(row.materialType) }}</td><td><StatusPill :value="row.result" /></td><td class="provenance-cell">{{ row.dataProvenance }}</td></tr></tbody></table>
        </DataPanel>
        <DataPanel title="用户排除的不完整来源" :count="facts.targetedRemediation?.excludedRows?.length" note="保留来源证据，不创建、不删除正式物料，也不进入计划。">
          <table><thead><tr><th>来源行</th><th>来源编码</th><th>来源名称</th><th>裁决状态</th><th>允许导入</th><th>允许进入计划</th><th>正式物料新增</th></tr></thead><tbody><tr v-for="row in facts.targetedRemediation?.excludedRows" :key="row.sourceCode"><td>{{ row.sourceRow }}</td><td>{{ row.sourceCode }}</td><td>{{ row.sourceName }}</td><td>{{ enumLabel(row.sourceDecisionStatus) }}</td><td>{{ row.importEligible ? '是' : '否' }}</td><td>{{ row.planningEligible ? '是' : '否' }}</td><td>{{ row.formalMaterialCreate }}</td></tr></tbody></table>
        </DataPanel>
        <section class="panel acceptance-console">
          <header><div><h2>物料人工验收工作台</h2><p>一次筛选整批检查；所有事实来自同一服务端只读响应。</p></div><strong>193 来源 / 190 匹配 / 3 阻断 / 270 正式 / 80 非当前来源</strong></header>
          <div class="quick-views"><button @click="setMaterialView('matched')">190 条真实匹配</button><button @click="setMaterialView('blocked')">3 条身份阻断</button><button @click="setMaterialView('outside')">80 条非当前来源正式物料</button><button @click="setMaterialView('all')">全部</button></div>
          <div class="filters"><input v-model.trim="materialSearch" placeholder="搜索编码、名称、规格"><select v-model="sourceFileFilter"><option value="">全部来源文件</option><option v-for="group in facts.sourceFileGroups" :key="group.sourceFile" :value="group.sourceFile">{{ group.sourceFile }}（{{ group.rowCount }}）</option></select><select v-model="materialStatusFilter"><option value="">全部状态</option><option value="MATCHED">真实匹配</option><option value="BLOCKED">身份阻断</option><option value="TEST_HISTORICAL">历史/测试</option><option value="POSSIBLE_REAL_OUTSIDE_SOURCE">可能真实的其它来源</option><option value="UNKNOWN_OUTSIDE_SOURCE">来源未知</option></select></div>
          <div class="chips"><span>明确历史/测试：{{ facts.testHistoricalCount }}</span><span>可能真实其它来源：{{ facts.possibleRealOutsideSourceCount }}</span><span>未知来源：{{ facts.unknownOutsideSourceCount }}</span><span>冲突：{{ facts.conflictCount }}</span></div>
        </section>
        <DataPanel title="A. 真实整木物料代表项" :count="facts.representativeRows?.length" note="按实际来源挑选板材、木皮、玻璃/镜面、五金/型材及其它采购件代表；全部来自已匹配来源，不把组成物料当成销售产品。">
          <table><thead><tr><th>代表类别</th><th>来源编码</th><th>来源名称</th><th>正式编码</th><th>正式名称</th><th>规格</th><th>计量单位</th><th>自制/采购</th><th>数据来源</th><th>匹配状态</th></tr></thead>
          <tbody><tr v-for="row in facts.representativeRows" :key="`${row.sourceFile}-${row.sourceRow}`"><td><strong>{{ row.representativeGroup }}</strong></td><td>{{ row.sourceCode }}</td><td>{{ row.sourceName }}</td><td>{{ row.formalMatch?.formalCode }}</td><td>{{ row.formalMatch?.formalName }}</td><td>{{ row.specification || '-' }}</td><td>{{ row.sourceUom || row.formalMatch?.uom || '待维护' }}</td><td>{{ enumLabel(row.makeBuy) }}</td><td class="provenance-cell">{{ row.dataProvenance }}</td><td><StatusPill :value="row.matchStatus" /></td></tr></tbody></table>
        </DataPanel>
        <DataPanel title="C. 用户排除的来源物料" :count="facts.missingSourceRows?.length" note="3条来源占位数据经用户裁决不再进入主数据建立流程；保留来源证据。">
          <table><thead><tr><th>来源编码</th><th>来源名称</th><th>正式编码</th><th>正式名称</th><th>规格</th><th>计量单位</th><th>自制/采购</th><th>数据来源</th><th>匹配状态</th></tr></thead>
          <tbody><tr v-for="row in facts.missingSourceRows" :key="row.sourceCode"><td>{{ row.sourceCode }}</td><td><strong>{{ row.sourceName }}</strong></td><td>-</td><td>-</td><td>{{ row.specification || '-' }}</td><td>{{ row.sourceUom || '来源未提供' }}</td><td>{{ enumLabel(row.makeBuy) }}</td><td class="provenance-cell">{{ row.dataProvenance }}</td><td><StatusPill :value="row.matchStatus" /></td></tr></tbody></table>
        </DataPanel>
        <DataPanel title="B. 测试/历史物料隔离摘要" :count="facts.testHistoricalCount" note="80条正式历史/测试记录不参与整木业务验收，不删除；MT004 / 无线鼠标单独置于代表项首位。">
          <div class="chips"><span v-for="item in facts.historicalSummary" :key="item.materialType">{{ item.materialType }}：{{ item.count }}</span></div>
          <table><thead><tr><th>来源编码</th><th>来源名称</th><th>正式编码</th><th>正式名称</th><th>规格</th><th>计量单位</th><th>自制/采购</th><th>数据来源</th><th>匹配状态</th></tr></thead>
          <tbody><tr v-for="row in facts.historicalExamples" :key="row.id" class="historical"><td>-</td><td>不属于当前整木来源</td><td>{{ row.formalCode }}</td><td><strong>{{ row.formalName }}</strong></td><td>{{ row.specification || '-' }}</td><td>{{ row.uom || '待维护' }}</td><td>{{ enumLabel(row.makeBuy) }}</td><td>正式库历史记录 / masterdata.Material</td><td><StatusPill value="TEST_HISTORICAL" /></td></tr></tbody></table>
        </DataPanel>
        <DataPanel title="来源物料逐条映射" :count="facts.sourceRows?.length" note="193条物理来源中，3条‘待定’占位不进入有效候选；不执行自动新增。">
          <table><thead><tr><th>来源</th><th>来源编码</th><th>名称 / 规格</th><th>类型</th><th>计量单位</th><th>自制/采购</th><th>正式匹配</th><th>编码关系</th><th>状态</th><th>冲突/拟处理</th></tr></thead>
          <tbody><tr v-for="row in filteredSourceRows" :key="`${row.sourceFile}-${row.sourceRow}`"><td>{{ row.sourceFile }} #{{ row.sourceRow }}</td><td>{{ row.sourceCode }}</td><td><strong>{{ row.sourceName }}</strong><br>{{ row.specification || '-' }}</td><td>{{ enumLabel(row.materialType) }}</td><td>{{ row.sourceUom || '来源未提供' }}</td><td>{{ enumLabel(row.makeBuy) }}<br><small>{{ row.supplyEvidence }}</small></td><td>{{ row.formalMatch ? `${row.formalMatch.formalCode} / ${row.formalMatch.formalName}` : '-' }}</td><td>{{ row.codeComparison || '-' }}</td><td><StatusPill :value="row.matchStatus" /></td><td>{{ row.conflicts?.join('；') || actionLabel(row.proposedAction) }}<br><small>{{ row.matchBasis }}</small></td></tr></tbody></table>
        </DataPanel>
        <DataPanel title="当前正式物料分类" :count="facts.formalRows?.length" note="每条正式记录明确分类；MT004 / 无线鼠标保留并隔离为测试/历史物料。">
          <table><thead><tr><th>正式编码</th><th>名称 / 规格</th><th>物料类型</th><th>计量单位</th><th>自制/采购</th><th>启用</th><th>业务分类</th><th>分类依据</th></tr></thead>
          <tbody><tr v-for="row in filteredFormalRows" :key="row.id" :class="{ historical: row.classification === 'TEST_HISTORICAL' }"><td>{{ row.formalCode }}</td><td><strong>{{ row.formalName }}</strong><br>{{ row.specification || '-' }}</td><td>{{ enumLabel(row.materialType) }}</td><td>{{ row.uom || '待维护' }}</td><td>{{ enumLabel(row.makeBuy) }}</td><td>{{ row.enabled ? '启用' : '停用' }}</td><td><StatusPill :value="row.classification" /></td><td>{{ row.classificationEvidence }}<br><small>生产引用 {{ row.productionReferenceTotal }}：{{ referenceText(row.productionReferenceCounts) }} / {{ enumLabel(row.productionReferenceStatus) }}</small></td></tr></tbody></table>
        </DataPanel>
        <DataPanel title="木皮 / 坯板属性目录参考" :count="facts.referenceCatalogRows?.length" note="仅作为物料属性和工程结构证据，不反向创建销售产品。">
          <table><thead><tr><th>来源</th><th>目录语义</th><th>实际名称</th><th>分类</th></tr></thead><tbody><tr v-for="row in facts.referenceCatalogRows" :key="`${row.sourceFile}-${row.sourceRow}`"><td>{{ row.sourceFile }} #{{ row.sourceRow }}</td><td>{{ row.catalogSemantic }}</td><td>{{ row.sourceName }}</td><td>{{ row.classification }}</td></tr></tbody></table>
        </DataPanel>
      </template>

      <template v-else-if="entity === 'products'">
        <section class="identity-gate panel"><h2>{{ facts.productIdentityConclusion }}</h2><p>当前闸门：<strong>{{ facts.identityGate }}</strong>。产品候选不等于正式产品；以下全部为只读 Preview。</p></section>
        <DataPanel title="正式承载模型 / 当前生产事实" :count="facts.formalRealityRows?.length" note="继续复用现有唯一正式模型，不建立 ProductV2 / WholeHouseProduct。">
          <table><thead><tr><th>业务对象</th><th>唯一正式模型</th><th>正式生产记录数</th><th>状态</th></tr></thead><tbody><tr v-for="row in facts.formalRealityRows" :key="row.object"><td><strong>{{ row.object }}</strong></td><td>{{ row.formalModel }}</td><td>{{ row.formalCount }}</td><td><StatusPill :value="row.status" /></td></tr></tbody></table>
        </DataPanel>
        <DataPanel title="A. 来源产品候选 / SOURCE PRODUCT NORMALIZATION PREVIEW" :count="facts.sourceRows?.length" note="逐行展示08排产的真实字段；原表没有具体产品名称、型号、尺寸和安装空间，因此明确显示‘未提供’。">
          <table><thead><tr><th>来源行</th><th>订单</th><th>产品原始名称</th><th>产品类别</th><th>规格 / 尺寸</th><th>空间</th><th>其它身份区分字段</th><th>拟正式 Product identity</th><th>是否唯一</th><th>需用户确认</th></tr></thead>
          <tbody><tr v-for="row in facts.sourceRows" :key="row.sourceRow"><td>{{ row.sourceFile }} #{{ row.sourceRow }}</td><td>{{ row.salesOrderNo }}<br><strong>{{ row.salesOrderItemNo }}</strong></td><td>{{ row.rawProductName }}</td><td><strong>{{ row.productCategory }}</strong></td><td>{{ row.specification }} / {{ row.dimensionsText }}</td><td>{{ row.space }}</td><td>{{ row.distinguishingFields }}</td><td>{{ row.proposedFormalIdentity }}</td><td>{{ row.isUnique }}</td><td>{{ row.needsUserConfirmation }}</td></tr></tbody></table>
        </DataPanel>
        <DataPanel title="37 条来源如何归并" :count="facts.normalizationGroups?.length" note="三种原值是产品类型/分类候选，不直接等于三个长期 ProductDefinition。">
          <table><thead><tr><th>来源产品类型</th><th>来源行数</th><th>主订单数</th><th>唯一子订单数</th><th>拟分类数</th><th>拟长期 ProductDefinition</th><th>拟按单工程实例</th><th>身份无法判断</th></tr></thead><tbody><tr v-for="row in facts.normalizationGroups" :key="row.sourceCategory"><td><strong>{{ row.sourceCategory }}</strong></td><td>{{ row.sourceRowCount }}</td><td>{{ row.uniqueOrderCount }}</td><td>{{ row.uniqueSubOrderCount }}</td><td>{{ row.proposedCategoryCount }}</td><td>{{ row.proposedProductDefinitionCount }}</td><td>{{ row.proposedOrderEngineeredInstanceCount }}</td><td>{{ row.unableToDetermineCount }}</td></tr></tbody></table>
        </DataPanel>
        <DataPanel title="B. 拟产品分类 / Product Category Preview" :count="facts.categoryPreviewRows?.length" note="原表列名为‘产品类型’；工程拆单表又把‘产品类别’与‘产品名称’分列，因此本层只提出分类候选。">
          <table><thead><tr><th>来源类型</th><th>来源行数 / 行号</th><th>拟分类名称</th><th>正式分类当前状态</th><th>语义依据</th><th>人工裁决</th></tr></thead><tbody><tr v-for="row in facts.categoryPreviewRows" :key="row.sourceCategory"><td><strong>{{ row.sourceCategory }}</strong></td><td>{{ row.sourceRowCount }} 行<br>#{{ row.sourceRowNumbers.join('、#') }}</td><td>{{ row.proposedCategoryName }}</td><td><StatusPill :value="row.formalStatus" /></td><td>{{ row.semanticEvidence }}</td><td>{{ row.decisionNote }}</td></tr></tbody></table>
        </DataPanel>
        <DataPanel title="C1. 拟正式 ProductDefinition 清单" :count="facts.productDefinitionPreviewRows?.length" note="来源证据不足时保持空清单，不用‘房门/饰面/柜体’三个类别词制造虚假产品。">
          <p v-if="!facts.productDefinitionPreviewRows?.length" class="empty-result"><strong>0 条。</strong> 08来源缺少具体产品名称、型号/规格、尺寸与安装空间；目前不能确认任何长期 ProductDefinition。</p>
        </DataPanel>
        <DataPanel title="C2. 拟 Order-Engineered 产品清单" :count="facts.orderEngineeredPreviewRows?.length" note="37个子订单仅形成按单工程来源实例候选；现有正式 OrderEngineeringInstance 仍要求已确认的 ProductDefinition / ProductVersion，所以本轮不写入。">
          <table><thead><tr><th>来源行</th><th>主/子订单</th><th>来源类别</th><th>拟身份</th><th>业务边界</th><th>正式写入</th></tr></thead><tbody><tr v-for="row in facts.orderEngineeredPreviewRows" :key="row.sourceRow"><td>#{{ row.sourceRow }}</td><td>{{ row.salesOrderNo }}<br><strong>{{ row.salesOrderItemNo }}</strong></td><td>{{ row.productCategory }}</td><td>{{ row.proposedFormalIdentity }}</td><td>{{ row.boundaryDecision }}</td><td>{{ row.formalWriteStatus }}</td></tr></tbody></table>
        </DataPanel>
        <DataPanel title="无法判断项" :count="facts.unableToDetermineRows?.length" note="所有37行都只能确认类别和订单上下文，不能确认‘这到底是什么长期产品’。">
          <table><thead><tr><th>来源类别</th><th>受影响行数 / 行号</th><th>缺失身份字段</th><th>无法判断原因</th></tr></thead><tbody><tr v-for="row in facts.unableToDetermineSummaryRows" :key="row.sourceCategory"><td><strong>{{ row.sourceCategory }}</strong></td><td>{{ row.affectedRowCount }} 行<br>#{{ row.sourceRowNumbers.join('、#') }}</td><td>{{ row.missingIdentityFields.join('、') }}</td><td>{{ row.reason }}</td></tr></tbody></table>
        </DataPanel>
        <DataPanel title="工程拆单身份字段参考（不可拼接到08的37行）" :count="facts.engineeringIdentityEvidence?.recordCount" :note="facts.engineeringIdentityEvidence?.reason">
          <p class="evidence-warning">关联结论：<strong>{{ facts.engineeringIdentityEvidence?.linkageTo08 }}</strong>。下表仅证明工程资料能够承载产品类别、产品名称、型号、尺寸和安装区域，不作为37行的身份补值。</p>
          <table><thead><tr><th>来源</th><th>产品类别</th><th>产品名称</th><th>型号</th><th>安装空间</th><th>尺寸</th><th>关联到08</th></tr></thead><tbody><tr v-for="row in facts.engineeringIdentityEvidence?.exampleRows" :key="`${row.sourceSheet}-${row.sourceRow}`"><td>{{ row.sourceSheet }} #{{ row.sourceRow }}</td><td>{{ row.productCategory }}</td><td><strong>{{ row.productName }}</strong></td><td>{{ row.model || '-' }}</td><td>{{ row.space || '-' }}</td><td>{{ row.dimensions.height || '-' }} × {{ row.dimensions.width || '-' }} × {{ row.dimensions.thickness || '-' }}</td><td>{{ row.linkageToSchedulingSource }}</td></tr></tbody></table>
        </DataPanel>
      </template>

      <template v-else>
        <section class="summary">
          <article><span>有效订单产品行</span><strong>{{ facts.sourceRecordCount }}</strong></article><article><span>产品候选</span><strong>{{ facts.distinctSourceCandidateCount }}</strong></article><article><span>工程物料编码</span><strong>{{ facts.engineeredMaterialCodeCount }}</strong></article><article><span>Production write</span><strong>0</strong></article>
        </section>
        <section class="two-col">
          <article class="panel"><h2>Product Version</h2><dl><dt>正式模型</dt><dd>{{ facts.productVersion?.formalModel }}</dd><dt>正式记录</dt><dd>{{ facts.productVersion?.formalRecordCount }}</dd><dt>DEVELOPED</dt><dd>YES</dd><dt>DATA PRESENT</dt><dd>{{ facts.productVersion?.dataPresent }}</dd><dt>USER VALIDATED</dt><dd>NO</dd><dt>READY</dt><dd>{{ facts.productVersion?.ready }}</dd></dl><p>{{ facts.productVersion?.status }}</p></article>
          <article class="panel"><h2>Product Configuration</h2><dl><dt>正式模型</dt><dd>{{ facts.productConfiguration?.formalModel }}</dd><dt>模板 / 配置记录</dt><dd>{{ facts.productConfiguration?.templateRecordCount }} / {{ facts.productConfiguration?.formalRecordCount }}</dd><dt>DEVELOPED</dt><dd>YES</dd><dt>DATA PRESENT</dt><dd>{{ facts.productConfiguration?.dataPresent }}</dd><dt>USER VALIDATED</dt><dd>NO</dd><dt>READY</dt><dd>{{ facts.productConfiguration?.ready }}</dd></dl><p>{{ facts.productConfiguration?.status }}</p></article>
        </section>
        <DataPanel title="VERSION READINESS PREVIEW" :count="facts.versionReadinessRows?.length" note="来源没有版本事实。仅建议产品验收后建立初始版本容器，本轮不创建正式版本。">
          <table><thead><tr><th>产品候选</th><th>来源行</th><th>来源版本事实</th><th>正式版本</th><th>初始版本容器建议</th><th>必须由用户填写/批准的真实制造事实</th><th>可由系统生成的技术标识</th></tr></thead><tbody><tr v-for="row in facts.versionReadinessRows" :key="row.productCandidate"><td><strong>{{ row.productCandidate }}</strong></td><td>{{ row.sourceRowCount }}行：#{{ row.sourceRowNumbers.join('、#') }}</td><td>{{ row.sourceVersionFactPresent ? '存在' : '不存在' }}</td><td>{{ row.formalVersionRecordCount }}</td><td>{{ row.recommendation }}</td><td>{{ row.realManufacturingFields.join('、') }}</td><td>{{ row.systemGeneratedFields.join('、') }}</td></tr></tbody></table>
        </DataPanel>
        <DataPanel title="Product Configuration 暂停" :count="facts.configurationReadinessRows?.length" note="Product identity 未通过人工确认前，不要求选择 STANDARD / TEMPLATE_ASSISTED / ORDER_ENGINEERED。">
          <table><thead><tr><th>来源分类候选</th><th>来源行数量</th><th>当前状态</th><th>暂停原因</th></tr></thead><tbody><tr v-for="row in facts.configurationReadinessRows" :key="row.productCandidate"><td><strong>{{ row.productCandidate }}</strong></td><td>{{ row.sourceRowCount }}</td><td>{{ row.currentSelection }}</td><td>{{ row.blockedReason }}</td></tr></tbody></table>
        </DataPanel>
      </template>

      <section class="panel provenance"><h2>DATA PROVENANCE</h2><ul><li v-for="item in facts.dataProvenance" :key="item.fileName"><strong>{{ item.fileName }}</strong><code>{{ item.sha256 }}</code></li></ul></section>
      <section class="boundary panel"><strong>Group 2 manual validation preview ready；Group 3 未进入</strong><span>Production business write: {{ facts.productionBusinessWriteCount }}</span></section>
    </template>
  </main>
</template>

<script setup>
import { computed, defineComponent, h, ref, watch } from 'vue'
import { enterpriseMasterDataApi } from '@/api/enterpriseMasterData.js'
import { businessUiEnumLabel } from '@/meta/governance/businessNameRegistry.js'
import FoundationBreadcrumb from '@/meta/components/FoundationBreadcrumb.vue'

const props = defineProps({ entity: { type: String, required: true } })
const tabs = [{ entity: 'materials', label: '物料对照 / 验收' }, { entity: 'products', label: '产品对照 / 验收' }, { entity: 'product-versions-configurations', label: '产品版本 / 配置对照' }]
const facts = ref({}); const loading = ref(false); const error = ref('')
const materialSearch = ref(''); const sourceFileFilter = ref(''); const materialStatusFilter = ref('')
const title = computed(() => tabs.find(item => item.entity === props.entity)?.label || props.entity)
const developedLabel = computed(() => props.entity === 'product-versions-configurations' ? 'YES / YES' : (facts.value.developed ? 'YES' : 'NO'))
const dataPresentLabel = computed(() => props.entity === 'product-versions-configurations' ? `${facts.value.productVersion?.dataPresent || '-'} / ${facts.value.productConfiguration?.dataPresent || '-'}` : facts.value.dataPresent)
const readyLabel = computed(() => props.entity === 'product-versions-configurations' ? `${facts.value.productVersion?.ready || '-'} / ${facts.value.productConfiguration?.ready || '-'}` : facts.value.ready)
const labels = { PROPOSED_MAPPING: '拟映射待确认' }
const enumLabel = value => labels[value] || businessUiEnumLabel(value)
const StatusPill = defineComponent({ props: { value: String }, setup(p) { return () => h('span', { class: ['pill', String(p.value || '').toLowerCase()] }, enumLabel(p.value)) } })
const DataPanel = defineComponent({ props: { title: String, count: Number, note: String }, setup(p, { slots }) { return () => h('section', { class: 'panel' }, [h('header', [h('div', [h('h2', p.title), h('p', p.note)]), h('span', `${p.count || 0} 条`)]), h('div', { class: 'table-wrap' }, slots.default?.())]) } })
const actionLabel = value => ({ REUSE_EXISTING: '拟复用', MANUAL_CONFLICT_REVIEW: '人工冲突复核', MANUAL_MATCH_OR_MAINTENANCE_PREVIEW: '人工匹配/维护预览', SOURCE_CORRECTION_REQUIRED: '修正来源' }[value] || value)
const quantityText = value => Object.entries(value || {}).filter(([, v]) => v && v !== '0').map(([k, v]) => `${k}=${v}`).join('；') || '-'
const matchesSearch = row => !materialSearch.value || JSON.stringify(row).toLowerCase().includes(materialSearch.value.toLowerCase())
const filteredSourceRows = computed(() => (facts.value.sourceRows || []).filter(row => matchesSearch(row) && (!sourceFileFilter.value || row.sourceFile === sourceFileFilter.value) && (!materialStatusFilter.value || (materialStatusFilter.value === 'MATCHED' && ['EXACT_MATCH','ATTRIBUTE_MATCH'].includes(row.matchStatus)) || (materialStatusFilter.value === 'BLOCKED' && ['NO_MATCH','INVALID_SOURCE','USER_EXCLUDED_INCOMPLETE_SOURCE','CONFLICT'].includes(row.matchStatus)))))
const filteredFormalRows = computed(() => (facts.value.formalRows || []).filter(row => matchesSearch(row) && (!materialStatusFilter.value || row.classification === materialStatusFilter.value || (materialStatusFilter.value === 'MATCHED' && row.classification === 'REAL_WHOLE_HOUSE_MATERIAL'))))
function setMaterialView(view){sourceFileFilter.value='';materialStatusFilter.value=({matched:'MATCHED',blocked:'BLOCKED',outside:'TEST_HISTORICAL',all:''})[view]||''}
const referenceText = counts => Object.entries(counts || {}).filter(([,value]) => value).map(([key,value]) => `${key}=${value}`).join('；') || '无'
async function load() { loading.value = true; error.value = ''; try { const response = await enterpriseMasterDataApi.group2Comparison(props.entity); facts.value = response?.data ?? response } catch (e) { error.value = e?.message || 'Group 2 对照事实读取失败' } finally { loading.value = false } }
watch(() => props.entity, load, { immediate: true })
</script>

<style scoped>
.g2-page{padding:24px;color:#17223a;box-sizing:border-box}.hero,.panel{background:#fff;border:1px solid #dce4ef;border-radius:16px;padding:20px 22px;margin-bottom:18px}.hero{display:flex;justify-content:space-between;align-items:center;gap:18px;color:#fff;background:linear-gradient(135deg,#143b69,#315bcf)}.hero p,.hero h1,.hero small,.panel h2,.panel p{margin:0}.hero h1{margin:5px 0 8px}.hero>span{border:1px solid #a8c5ff;padding:9px 12px;border-radius:999px;white-space:nowrap}.tabs{display:flex;gap:10px;margin-bottom:18px}.tabs a{padding:10px 15px;border-radius:10px;background:#edf2ff;color:#244a9b;text-decoration:none}.tabs a.router-link-active{background:#315bcf;color:#fff}.state,.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}.state div,.summary article{display:grid;gap:5px;padding:13px;border-radius:10px;background:#f5f8fc;border-left:4px solid #315bcf}.state span,.summary span{font-size:12px;color:#637189}.summary{margin-bottom:18px}.summary strong{font-size:22px}.summary .good{border-color:#168357}.summary .warn{border-color:#d48600}.summary .danger{border-color:#c5362d}.panel header{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-bottom:12px}.table-wrap{overflow:auto;max-height:620px;border:1px solid #e1e7f0;border-radius:10px}table{border-collapse:collapse;width:100%;font-size:12px}th,td{padding:9px;border-bottom:1px solid #e8edf5;text-align:left;vertical-align:top;min-width:90px}th{position:sticky;top:0;background:#edf2f8;z-index:1;white-space:nowrap}td:nth-last-child(1){min-width:180px}.historical{background:#fff7e8}.pill{display:inline-block;padding:3px 7px;border-radius:999px;white-space:nowrap;background:#edf1f7}.pill.exact_match,.pill.real_whole_house_material{background:#e5f6ee;color:#126b45}.pill.test_historical,.pill.invalid_source{background:#fff0d8;color:#8b5900}.pill.no_match,.pill.unmatched,.pill.conflict{background:#feeceb;color:#a6241c}.pill.proposed_mapping{background:#e8efff;color:#284da0}.two-col{display:grid;grid-template-columns:1fr 1fr;gap:18px}.two-col dl{display:grid;grid-template-columns:150px 1fr}.two-col dt,.two-col dd{margin:0;padding:9px;border-bottom:1px solid #e8edf5}.provenance ul{padding-left:20px}.provenance li{display:grid;grid-template-columns:minmax(180px,320px) 1fr;gap:10px;margin:7px 0}.provenance code{font-size:10px;word-break:break-all}.boundary{display:flex;justify-content:space-between;background:#fff8e6}.error{color:#a6241c}@media(max-width:800px){.g2-page{padding:12px}.hero,.boundary,.panel header{align-items:flex-start;flex-direction:column}.two-col{grid-template-columns:1fr}}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}.chips span{padding:7px 10px;border-radius:999px;background:#fff0d8;color:#7d5200}.provenance-cell{min-width:280px;font-size:10px;word-break:break-all}.option-definitions{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:14px}.option-definitions p{padding:12px;border:1px solid #dce4ef;border-radius:10px;background:#f6f8fc}.option-definitions strong{display:block;color:#244a9b;margin-bottom:4px}select{min-width:190px;padding:8px;border:1px solid #b8c4d6;border-radius:8px;background:#fff}.pill.attribute_match,.pill.present{background:#e5f6ee;color:#126b45}.pill.missing{background:#feeceb;color:#a6241c}@media(max-width:800px){.option-definitions{grid-template-columns:1fr}}
.identity-gate{border-left:5px solid #d48600}.empty-result,.evidence-warning{padding:14px;background:#fff8e6;border-radius:9px;margin:0!important}.evidence-warning{margin-bottom:12px!important}.identity-gate strong,.evidence-warning strong{color:#9a5b00}
.quick-views,.filters{display:flex;flex-wrap:wrap;gap:9px;margin:12px 0}.quick-views button{padding:8px 12px;border:1px solid #9eb3df;border-radius:9px;background:#edf2ff;color:#244a9b;cursor:pointer}.filters input,.filters select{padding:9px;border:1px solid #b8c4d6;border-radius:8px;background:#fff;min-width:210px}.acceptance-console{border-left:5px solid #315bcf}.pill.possible_real_outside_source{background:#e8efff;color:#284da0}.pill.unknown_outside_source{background:#edf1f7;color:#536176}
</style>

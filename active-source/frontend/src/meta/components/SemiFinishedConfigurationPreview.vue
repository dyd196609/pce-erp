<template>
  <section class="configuration-preview" data-subview="semi-finished-structure" data-business-write-count="0">
    <header class="config-hero">
      <div><p>只读预览 · 按配置验收一次，工程行引用同一身份</p><h2>半成品物料结构</h2><p>先回答“是什么材料结构”，再计算“这一单需要多少”。不逐行选采购板，不写正式 BOM 或核算规则。</p></div>
      <strong>隔离模型验证 / 只读预览<br>生产业务写入 0</strong>
    </header>
    <p v-if="loading" role="status">正在读取来源证据及当前正式身份…</p>
    <div v-else-if="error" class="error" role="alert"><h3>配置证据读取失败</h3><p>{{ error }}</p><p>记录数未知，不代表空数据；请使用页面“刷新”重试。</p></div>
    <template v-else-if="preview">
      <div class="config-summary">
        <article><b>{{ preview.summary.source05Count }}</b><span>05 来源编码</span></article>
        <article><b>{{ preview.summary.formal05Matched }}</b><span>已匹配正式物料身份</span></article>
        <article><b>{{ preview.summary.userExcludedSourceCount }}</b><span>已人工排除，继续保留</span></article>
        <article><b>{{ preview.summary.threeInOneMapped }} / {{ preview.summary.threeInOneCount }}</b><span>三合一来源行精确对应 05</span></article>
        <article><b>{{ preview.summary.activeConfigurationCount }}</b><span>71 行当前配置组（三合一 1 组）</span></article>
        <article><b>{{ preview.summary.userValidatedConfigurationCount }}</b><span>来源配置已人工确认，其余56有效配置未验收</span></article>
      </div>
      <p class="warning">三层模型及两个配置身份已人工确认并冻结；本轮只复验 QSFB4601001 房门的见光、封边皮25/50净长度、边段、每边预留方式与毛需求待定六项。BTKF、板材、木皮架构和表面耗材不重新验收。生产关系尚未部署，不生成正式耗用。</p>
      <div class="layer-guide" aria-label="三个业务层级">
        <article><h3>制造配置</h3><p>组件使用什么板材制造体系：坯板、木皮、颜色、表面工艺等。</p></article>
        <article><h3>工程组件材料需求</h3><p>组件提供几何、数量、封边方式和结构位置。封边、五金、玻璃属于这一层。</p></article>
        <article><h3>工程结构 / 粗略 BOM</h3><p>成品 → 部件 → 子部件。继续只作结构参考，不是数量或公式权威，不复制到配置。</p></article>
      </div>
      <div class="config-selection">
        <label>筛选编码 / 名称<input v-model="search" placeholder="输入半成品编码或名称" type="search"></label>
        <label>选择半成品板材编码<select v-model="selectedId" aria-label="选择半成品板材编码"><option v-for="row in options" :key="row.groupId" :value="row.groupId">{{ row.sourceCode }} · {{ row.name }} · {{ row.realRowCount }} 条工程引用{{ row.identity.excludedByUser ? ' · 已人工排除' : '' }}</option></select></label>
        <span>筛选结果 {{ options.length }} / {{ preview.summary.source05Count }}</span>
      </div>
      <template v-if="selected">
        <section class="config-card" aria-label="当前半成品身份">
          <h3>A. 制造配置 · {{ selected.sourceCode }}</h3><p>{{ selected.name }} · {{ selected.layerUserValidationLabel }}</p>
          <dl class="identity-grid">
            <div><dt>来源</dt><dd>{{ selected.sourceFile }} / 半成品板材 / 第 {{ selected.sourceRow }} 行</dd></div>
            <div><dt>正式物料身份</dt><dd>{{ targetText(selected.identity.formal) }}</dd></div>
            <div><dt>匹配依据</dt><dd>{{ selected.identity.reason }}</dd></div>
            <div><dt>产品类别 / 结构角色</dt><dd>{{ selected.productCategories.join('、') || '未提供' }} / {{ selected.structureRoles.join('、') || '当前71行无引用' }}</dd></div>
            <div><dt>工程行归并</dt><dd>{{ selected.realRowCount }} 条 → 1 个配置组；不按尺寸拆成 {{ selected.realRowCount }} 个物料</dd></div>
            <div><dt>来源 / 正式 / 人工验收</dt><dd>{{ selected.userValidationLabel }}；{{ selected.identity.status === 'MATCHED' ? '正式物料身份存在' : '无可用正式物料身份' }}。{{ selected.productionConfigurationLabel || '生产配置关系未建立' }}</dd></div>
          </dl>
          <p v-if="selected.identity.excludedByUser" class="warning">该记录已被用户排除，不作为待补建物料，本轮不重开既有裁决。</p>
          <details><summary>{{ selected.userValidated ? '查看已冻结的制造属性、来源与正式身份' : '查看制造属性、来源与正式身份（尚未人工确认）' }}</summary><div class="attribute-table-wrap"><table aria-label="半成品制造属性来源与正式身份"><thead><tr><th>制造属性</th><th>来源真实值 / 位置</th><th>标准业务值 / 受控状态</th><th>当前生产身份</th><th>人工确认 / 身份状态</th><th>关系及缺口</th></tr></thead><tbody>
            <tr v-for="field in selected.attributes" :key="field.key"><th>{{ field.label }}</th><td><b>{{ field.sourceValue ?? '来源未填写' }}</b><small>{{ field.sourceCell }}</small><small v-for="trace in field.sourceTrace" :key="`${trace.fileSheet}-${trace.row}`">{{ trace.fileSheet }} · 行 {{ trace.row }}</small></td><td>{{ field.knowledgeLabel || field.canonicalValue || '未确定' }}</td><td>{{ field.formalTargets.map(targetText).join('；') || '尚未解析' }}</td><td><b>{{ field.sourceValidationLabel }}</b><small>{{ field.formalStatusLabel }}</small></td><td><b>{{ field.relationshipStatus === 'EXISTING_FORMAL_LINK' ? '既有正式关联，保持不变' : field.relationshipStatus === 'SOURCE_EXPLICIT_NONE' ? '来源明确不适用' : '生产配置关系尚未部署' }}</b><small>{{ field.note }}</small></td></tr>
          </tbody></table></div></details>
        </section>
        <section v-if="selected.isolatedReplay" class="config-card" aria-label="制造配置三个材料角色">
          <h3>制造配置的三个材料角色</h3>
          <p>本配置在隔离库建立一次，{{ selected.isolatedReplay.inheritedRows }} 条工程行共同继承。来源业务关系已确认，不代表采购身份或用量已确定。</p>
          <div class="attribute-table-wrap"><table aria-label="隔离材料组成角色明细"><thead><tr><th>组成角色</th><th>来源业务身份</th><th>正式采购物料身份</th><th>数量方式 / 状态</th><th>阻断原因</th></tr></thead><tbody>
            <tr v-for="role in selected.isolatedReplay.roles" :key="role.roleCode"><th>{{ role.roleLabel }}<small>{{ role.roleStatusLabel }}</small></th><td>{{ role.sourceBusinessIdentity || '具体耗材待确定' }}<small v-if="role.formalFamilyId">隔离材料族：实木多层板；不是已选采购规格</small></td><td>{{ role.formalMaterialId || '尚未唯一解析' }}</td><td>{{ role.quantityModeLabel }}<small>{{ role.ruleReadinessLabel }}；数量未生成</small></td><td><span v-for="reason in role.blockerLabels" :key="reason" class="blocker-line">{{ reason }}</span></td></tr>
          </tbody></table></div>
          <p class="layer-note">封边属于组件，不是半成品板材组成。其它固定组成留在工程结构 / BOM，不在这里复制。</p>
          <p>颜色 / 色板、油漆工艺是配置属性。表面 / 工艺耗材角色已确认，数量方式为规则计算；具体油漆、胶水、耗用系数与规则待定义。数量保持未生成，不猜涂布率或道数。</p>
        </section>
        <section v-else class="config-card"><h3>预计展开的材料组成</h3><p>“由什么组成”与“需要多少”分开；下表不是已保存的 BOM。组成数量全部保持未生成。</p>
          <div class="attribute-table-wrap"><table aria-label="预计材料组成"><thead><tr><th>材料角色</th><th>来源关系</th><th>正式目标</th><th>数量基数 / 状态</th></tr></thead><tbody><tr v-for="row in selected.composition" :key="row.role"><th>{{ row.role }}</th><td>{{ row.sourceValue ?? '来源未提供' }}</td><td>{{ row.formalTargets.map(targetText).join('；') || '待解析' }}</td><td>{{ row.basis }}<small>{{ statusLabel(row.status) }}；不生成用量</small></td></tr></tbody></table></div>
          <p>固定组成：确定材料身份；计算组成：引用已批准派生事实计算数量。工程人工指定、临时追加、客户特殊要求使用独立来源通道，不伪造公式。</p>
        </section>
        <section v-if="selected.layerPreview" class="config-card" aria-label="工程组件层">
          <h3>B. 工程组件 · {{ selected.layerPreview.components.length }} 条真实来源</h3>
          <p>每条组件通过来源行引用 {{ selected.sourceCode }}，继承坯板族、木皮、颜色与工艺。组件自身提供几何、数量、封边方式及结构位置；没有创建正式订单或伪造计算成功记录。</p>
          <template v-if="selected.layerPreview.roomDoorSummary">
            <p class="result-line">8行见光均可判定，合计 {{ selected.layerPreview.roomDoorSummary.visibleAreaTotalM2 }} m²，与木皮净面积同源。</p>
            <p>封边皮25：{{ selected.layerPreview.roomDoorSummary.edge25NetTotalM }} m；封边皮50：{{ selected.layerPreview.roomDoorSummary.edge50NetTotalM }} m。共 {{ selected.layerPreview.roomDoorSummary.physicalEdgeCount }} 条边。均为净长度，不含损耗。</p>
            <div class="door-components" aria-label="房门八行定向复验">
              <article v-for="row in selected.layerPreview.components" :key="row.componentId" class="door-component">
                <h4>房门单第{{ row.row }}行 · {{ row.role }}</h4>
                <p>{{ row.space }} · {{ row.configurationCode }}<br>门洞 {{ row.length }} × {{ row.width }} mm；数量 {{ row.quantity }}</p>
                <strong>见光面积 {{ row.visibleAreaFact.visibleAreaM2 }} m²</strong>
                <small>{{ row.visibleAreaFact.basisCell }} · 木皮净面积使用同一个见光派生事实</small>
                <RoomDoorEdgeRequirementPreview v-for="edge in row.edgeRequirements" :key="edge.requirementId" :requirement="edge" />
              </article>
            </div>
          </template>
          <div v-else class="attribute-table-wrap source-list"><table aria-label="工程组件引用链"><thead><tr><th>来源行 / 组件</th><th>配置引用</th><th>空间 / 位置</th><th>来源几何与数量</th><th>见光 / 封边</th></tr></thead><tbody>
            <tr v-for="row in selected.layerPreview.components" :key="row.componentId"><th>{{ row.sheet }} / {{ row.row }}<small>{{ row.role }}</small></th><td>{{ row.configurationCode }}</td><td>{{ row.space || '本行未填，不猜位置' }}<small>{{ row.productCategory || '来源未填' }}</small></td><td>{{ row.length }} × {{ row.width }}<small>{{ row.dimensionSemantics === 'BOARD_COMPONENT' ? `厚 ${row.thickness}（L列）` : '门洞尺寸；墙厚不作为板厚' }}；数量 {{ row.quantity }}</small></td><td>{{ row.visibleCondition || '未提供' }} / {{ row.edgeMode || '未提供，不按无封边处理' }}</td></tr>
          </tbody></table></div>
        </section>
        <section v-if="selected.layerPreview" class="config-card" aria-label="材料需求层">
          <h3>C. 材料需求 · 净量预览与正式需求分开</h3>
          <article class="demand-block" aria-label="板材精确匹配预览"><h4>板材精确匹配</h4>
            <template v-if="selected.layerPreview.boardRows.length">
              <p>厚度输入：三合一 L 列，{{ selected.layerPreview.boardRows.length }} 行已确认。18 / 22 / 24 / 25 / 28 按原值精确匹配，禁止 22→20、24→25、28→30。</p>
              <p class="result-line">同厚度诊断 {{ preview.roleLayerSummary.board.exactThicknessMatch }} 行 · 材料族允许集匹配 {{ preview.roleLayerSummary.board.materialFamilyMatch }} 行 · 合法规格匹配 {{ preview.roleLayerSummary.board.specMatch }} 行 · 已选板材 {{ preview.roleLayerSummary.board.boardExactMatch }} 行 · 阻断 {{ preview.roleLayerSummary.board.blocked }} 行</p>
              <p>顺序：配置 → 实木多层板族 → L 列厚度 → 允许采购物料 → 正式长宽厚 → 几何适配 → 最小合法规格。31 行仅有同厚度目录候选，不等于材质适用；32 行缺少精确采购厚度。未证明叠层关系，不自动归为组合板。</p>
              <details><summary>查看全部 {{ selected.layerPreview.boardRows.length }} 行板材匹配与缺口</summary><div class="attribute-table-wrap source-list"><table aria-label="板材匹配明细"><thead><tr><th>来源行 / 组件</th><th>厚度输入</th><th>同厚度正式物料数</th><th>合法规格匹配数</th><th>当前阻断</th></tr></thead><tbody><tr v-for="row in selected.layerPreview.boardRows" :key="row.row"><th>{{ row.row }} / {{ row.role }}</th><td>{{ row.thickness }} mm<small>{{ row.thicknessCell }}</small></td><td>{{ row.exactThicknessMaterialIds.length }}<small>仅诊断，不是已选物料</small></td><td>{{ row.specMatchIds.length }}</td><td><span v-for="reason in row.blockerLabels" :key="reason" class="blocker-line">{{ reason }}</span></td></tr></tbody></table></div></details>
            </template><p v-else>房门单 8 行不适用三合一 L 列板厚合同；没有将门洞、墙厚强行匹配为采购板。</p>
          </article>
          <article class="demand-block" aria-label="木皮净面积预览"><h4>木皮净面积</h4>
            <p class="result-line">已知净面积小计 {{ selected.layerPreview.veneerSummary.knownSubtotalM2 }} m² · {{ selected.layerPreview.veneerSummary.blockedRows.length ? `第 ${selected.layerPreview.veneerSummary.blockedRows.join('、')} 行缺见光条件，完整总量未知` : '本配置全部来源行可判定' }}</p>
            <p>工程组件 → 配置木皮身份 → 见光面积 → 净木皮需求。木皮自身厚度仅为物料属性，不参与当前用量计算；无固定长宽不阻断净面积。采购木皮身份未解析，只阻断正式采购需求，不阻断已知净面积。</p>
            <details><summary>查看全部 {{ selected.layerPreview.veneerRows.length }} 行木皮净面积与来源</summary><div class="attribute-table-wrap source-list"><table aria-label="木皮净面积明细"><thead><tr><th>来源行</th><th>配置木皮 / 厚度属性</th><th>见光面积依据</th><th>净面积 m²</th><th>正式采购需求</th></tr></thead><tbody><tr v-for="row in selected.layerPreview.veneerRows" :key="row.row"><th>{{ row.sheet }} / {{ row.row }}</th><td>{{ row.veneerSourceIdentity }}<small>名称原文保留；厚度不参与当前计算</small></td><td>{{ row.basisCell }}<small>{{ row.netStatusLabel }}</small></td><td>{{ row.netRequirementM2 ?? '未知，未补0' }}</td><td>采购身份未解析；毛量未生成<small>没有应用20%损耗</small></td></tr></tbody></table></div></details>
          </article>
          <article class="demand-block" aria-label="组件级封边预览"><h4>组件级封边</h4>
            <p class="layer-note">封边属于组件，不是半成品板材组成。</p>
            <template v-if="selected.layerPreview.roomDoorRequirements">
              <p>房门原公式直接计算净长度 → 同一逐边损耗策略 → 毛需求待参数。16条来源需求分开保留封边皮25/50；材料身份未解析不隐藏净量。</p>
              <details><summary>查看16条房门封边净需求与损耗状态</summary><RoomDoorEdgeRequirementPreview v-for="edge in selected.layerPreview.roomDoorRequirements" :key="edge.requirementId" :requirement="edge" /></details>
              <details><summary>查看企业损耗参数维护目标（隔离预览，不可保存）</summary>
                <article v-for="policy in selected.layerPreview.lossPolicies" :key="policy.pk">
                  <h5>{{ policy.fields.source.name }}</h5>
                  <p>需求类型：封边；方式：每边预留；单位：mm。<br>建议值：待定；正式值：待定；版本：{{ policy.fields.version }}；状态：参数待确认。<br>来源：用户只确认方法，尚未提供参数；修改人：未正式指定；隔离记录时间：{{ policy.fields.modified_at }}。</p>
                </article>
                <p>两种房门材料与三合一使用同一机制、独立参数身份。不以面积损耗率替代逐边预留；没有真实参数不生成毛需求。</p>
              </details>
            </template>
            <template v-else-if="selected.layerPreview.edgeRows.length">
              <p>本配置 {{ selected.layerPreview.edgeRows.length }} 行有明确封边方式，已在隔离库接入原组件材料需求载体。数量方式：规则计算；基础单位 m。已知净长小计 {{ preview.roleLayerSummary.edge.knownNetSubtotalM }} m。</p>
              <p>封哪条边 → 各边实际长度 → 每边预留 → 毛边长 → 正式封边条 → 按规格 / 单位汇总。实际封边条与每边余量未知，毛量保持未生成；第9、36、60、68行不猜封边方式。</p>
              <details><summary>查看 {{ selected.layerPreview.edgeRows.length }} 条组件级封边需求</summary><div class="attribute-table-wrap source-list"><table aria-label="组件封边需求明细"><thead><tr><th>组件 / 来源行</th><th>封边方式 / 边长 mm</th><th>净长 m</th><th>封边条规格</th><th>每边余量 / 毛量</th></tr></thead><tbody><tr v-for="row in selected.layerPreview.edgeRows" :key="row.requirementId"><th>{{ row.role }} / {{ row.row }}<small>{{ row.configurationCode }}</small></th><td>{{ row.edgeMode }}<small>{{ row.edgeDimensionsMm.join(' + ') }}；组件数量 {{ row.componentQuantity }}</small></td><td>{{ row.netLengthM }}</td><td>材质、宽度、厚度、颜色待明确</td><td>余量未知；毛量未生成<small>规则未发布，未用0/1占位</small></td></tr></tbody></table></div></details>
            </template><p v-else>当前来源没有可判定的封边需求，保持未知，不根据产品名称推断。</p>
          </article>
          <article class="demand-block"><h4>表面 / 工艺耗材</h4><p>角色已确认 · 数量方式：规则计算 · 规则待定义/发布 · 具体物料身份未解析。油漆工艺是配置，油漆/胶水消耗是材料需求，两者不混用。本轮耗用系数、涂布率、道数及真实耗用量全部未填写。</p></article>
        </section>
        <section class="config-card"><h3>仍阻断业务计算的事实</h3><p>已确认的来源配置不重开；本轮不提供保存、导入或规则发布动作。</p><ul><li v-for="issue in gap?.issues || []" :key="issue">{{ issue }}</li></ul><p v-if="!gap">当前71行未使用本来源；本轮不启动额外人工裁决。</p><p>配置属性、BOM半成品主体、数量模式及旧需求表契约已在隔离环境验证。生产模型未应用，不把隔离通过标记成生产就绪。</p></section>
        <details class="config-card"><summary>查看本配置全部 {{ selected.realRowCount }} 条工程来源行</summary><div class="attribute-table-wrap"><table aria-label="工程引用行"><thead><tr><th>Sheet / 行</th><th>类别 / 角色</th><th>空间 / 型号</th><th>来源尺寸（保留原字段语义）</th><th>来源数量 / 工程行单位</th><th>单双 / 封边</th></tr></thead><tbody><tr v-for="row in selected.engineeringRows" :key="`${row.sheet}-${row.row}`"><td>{{ row.sheet }} / {{ row.row }}</td><td>{{ row.productCategory }} / {{ row.role || '未提供' }}</td><td>{{ row.space || '本行未填' }} / {{ row.model || '本行未填' }}</td><td>{{ row.dimensionText }}</td><td>{{ row.quantityLabel }} {{ row.quantity }} / {{ row.rowUom || '本行未填' }}</td><td>{{ row.visibleSides || '未提供' }} / {{ row.edgeMode || '未提供' }}</td></tr></tbody></table></div></details>
        <details class="config-card"><summary>来源版本、冲突与身份依据（技术诊断）</summary><p v-for="source in preview.sourceFiles" :key="source.file">{{ source.file }}<small>SHA256 {{ source.sha256 }}</small></p><pre>{{ JSON.stringify({ isolation: preview.isolationEvidence, externalIdentity: selected.identity.evidence, designCatalogRows: selected.designCatalogRows, attributeConflicts: selected.attributeConflicts, paintInputs: selected.paintInputs }, null, 2) }}</pre><p>08仅为派生参考，本视图未读取。三合一25、26、72行是冻结71行范围外的来源记录；只在审计中保留，不扩大既有Native验算范围。</p></details>
      </template>
      <p v-else>没有符合筛选条件的配置；清除筛选可以恢复原列表。</p>
      <footer>三层模型已人工确认并冻结；仅QSFB房门六项待定向复验。净需求源自Excel；毛需求须待企业逐边预留参数。生产迁移未应用，生产业务写入0。</footer>
    </template>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import RoomDoorEdgeRequirementPreview from './RoomDoorEdgeRequirementPreview.vue'
const props = defineProps({ preview: { type: Object, default: null }, loading: Boolean, error: { type: String, default: '' } })
const search = ref('')
const selectedId = ref('')
const options = computed(() => [...(props.preview?.configurations || [])].filter(row => `${row.sourceCode} ${row.name}`.toLowerCase().includes(search.value.trim().toLowerCase())).sort((a, b) => b.realRowCount - a.realRowCount))
const selected = computed(() => options.value.find(row => row.groupId === selectedId.value))
const gap = computed(() => (props.preview?.gaps || []).find(row => row.sourceCode === selected.value?.sourceCode))
watch(options, rows => { if (!rows.some(row => row.groupId === selectedId.value)) selectedId.value = rows[0]?.groupId || '' }, { immediate: true })
const targetText = item => item ? `${item.code} / ${item.name}（ID ${item.id}）` : '尚未解析'
const statusLabel = value => ({ MATCHED: '身份已匹配', UNRESOLVED: '待解析', NOT_APPLICABLE: '不适用' })[value] || value
</script>

<style scoped>
.door-components{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,360px),1fr));gap:12px}.door-component{border:1px solid #cadce4;border-radius:8px;padding:14px;min-width:0}.door-component h4{margin:0 0 8px;font-size:16px}.door-component p{margin:7px 0}
.layer-guide{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.layer-guide article{border:1px solid #cadce4;padding:14px;background:#f3f8fa;border-radius:8px}.layer-guide h3{font-size:16px;margin:0 0 8px}.layer-guide p{margin:0;line-height:1.7}.layer-note{border-left:4px solid #17676c;padding:10px 14px;background:#eaf5f3;font-weight:700}.source-list{max-height:310px}.source-list thead{position:sticky;top:0;z-index:1}.demand-block{padding:12px 0;border-top:1px solid #dce6eb}.demand-block h4{font-size:17px;margin:10px 0}.result-line{font-weight:700;color:#17545d}@media(max-width:780px){.layer-guide{grid-template-columns:1fr}}
.blocker-line{display:block;margin-bottom:5px}
.configuration-preview{min-width:0;color:#1b3045}.config-hero{display:flex;justify-content:space-between;gap:20px;background:#123d51;color:#fff;padding:22px;border-radius:12px}.config-hero h2{font-size:25px;margin:5px 0 12px}.config-hero p{margin:0 0 5px;line-height:1.7}.config-hero>strong{white-space:nowrap;line-height:1.8;color:#bdece3}.config-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:10px;margin:16px 0}.config-summary article{display:grid;gap:7px;border:1px solid #c9dce2;border-radius:9px;padding:13px;background:white}.config-summary b{font-size:25px;color:#17676c}.config-summary span{font-size:13px}.warning{padding:13px 16px;background:#fff4da;border-left:4px solid #ce942c;line-height:1.7}.config-selection{display:flex;gap:18px;align-items:end;flex-wrap:wrap;margin:16px 0}.config-selection label{display:grid;gap:8px;max-width:100%;font-weight:700}.config-selection input,.config-selection select{padding:10px;border:1px solid #9bb8c3;border-radius:7px;font:inherit;max-width:100%;background:white}.config-card{background:white;border:1px solid #cadce4;border-radius:10px;padding:20px;margin:15px 0;min-width:0}.config-card h3{margin:0 0 14px;font-size:18px}.config-card p{line-height:1.8}.identity-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:0 0 18px}.identity-grid div{background:#f3f8fa;padding:12px}.identity-grid dt{color:#5a6f7d;font-size:13px}.identity-grid dd{margin:6px 0 0;line-height:1.7;overflow-wrap:anywhere}.attribute-table-wrap{overflow:auto;border:1px solid #dce6eb;border-radius:6px}table{border-collapse:collapse;width:100%;min-width:780px}th,td{padding:12px;text-align:left;vertical-align:top;border-bottom:1px solid #dce6eb;line-height:1.65}thead th{background:#eaf2f5;white-space:nowrap}tbody th{min-width:85px}td{max-width:340px;overflow-wrap:anywhere}small{display:block;color:#5d7181;font-size:12px;line-height:1.7;overflow-wrap:anywhere}.state{display:inline-block;padding:3px 9px;border-radius:5px;white-space:nowrap}.matched{background:#dff3e9;color:#145638}.unresolved{background:#fff0d9;color:#865300}.not_applicable{background:#edf0f4;color:#435366}.error{padding:20px;background:#fff1f1;border:1px solid #c77575}.config-card summary{cursor:pointer;font-weight:700}.config-card li{margin:8px 0;line-height:1.6}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}footer{padding:18px;background:#e8f0f5;line-height:1.7}@media(max-width:780px){.identity-grid{grid-template-columns:1fr}.config-hero{flex-direction:column}.config-card{padding:12px}}
</style>



<template>
  <section
    class="bom-material-readback"
    data-acceptance-id="pde-bom-material-detail-readback"
    data-projection-source="server-formal-fk"
    data-write-action-count="0"
  >
    <header class="readback-header">
      <div>
        <h3>BOM物料明细</h3><p class="material-name-source">物料名称为当前物料档案参考名称，非保存时冻结名称。</p>
        <p>“查看详情”读取当前BOM版本的物料构成；“查看来源”展开该BOMItem已持久化的Requirement追溯关系。</p>
      </div>
      <div class="readback-counts" aria-label="BOM明细统计">
        <strong>{{ readback.rows.length }}</strong><span>项物料</span>
        <strong>{{ readback.sourceRequirementCount }}</strong><span>条来源</span>
      </div>
    </header>

    <el-alert v-if="detail.controlledDraftLabel" type="warning" :closable="false" show-icon
      :title="detail.controlledDraftLabel"
      :description="`${detail.quantityBasisLabel}；${detail.frozenDesignRevisionLabel}；基线${detail.frozenBaselineNo}。损耗、毛量未维护，当前数量不代表采购或投料毛量。`" />

    <el-alert
      v-if="readback.result !== 'PASS'"
      title="BOM来源追溯一致性校验未通过，已停止展示关系明细"
      :description="readback.issues.join('；')"
      type="error"
      :closable="false"
      show-icon
      data-acceptance-id="pde-bom-material-detail-fail-closed"
    />

    <div v-else class="material-table-scroll">
      <table class="material-table" data-acceptance-id="pde-bom-material-detail-table">
        <thead>
          <tr>
            <th>序号</th><th>物料编码</th><th>物料名称</th><th>规格</th>
            <th>结构角色</th><th>数量</th><th>数量口径</th><th>单位</th><th>损耗率</th><th>毛量</th><th>来源Requirement数</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="row in readback.rows" :key="row.bomItemId">
            <tr :data-bom-item-id="row.bomItemId">
              <td>{{ row.lineNo }}</td>
              <td class="identity">{{ row.materialCode }}</td>
              <td>{{ row.materialName }}</td>
              <td>{{ row.materialSpecificationLabel }}</td>
              <td>{{ row.structuralRoleLabel }}</td>
              <td class="number">{{ row.quantity }}</td>
              <td>{{ row.quantityBasisLabel }}</td>
              <td>{{ row.uomDisplay }}</td>
              <td>{{ row.scrapRateLabel }}</td>
              <td>{{ row.grossQuantityLabel }}</td>
              <td class="number">{{ row.sourceRequirementCount }}</td>
              <td>
                <el-button
                  size="small"
                  plain
                  :aria-expanded="expandedItemIds.includes(row.bomItemId)"
                  @click="toggle(row.bomItemId)"
                >{{ expandedItemIds.includes(row.bomItemId) ? '收起来源' : '查看来源' }}</el-button>
              </td>
            </tr>
            <tr v-if="expandedItemIds.includes(row.bomItemId)" class="source-row">
              <td colspan="12">
                <div class="source-panel" :data-source-bom-item-id="row.bomItemId">
                  <h4>{{ row.materialCode }} · Requirement来源</h4><p class="material-name-source">物料名称为当前物料档案参考名称，非保存时冻结名称。</p>
                  <div class="source-table-scroll">
                    <table class="source-table">
                      <thead>
                        <tr>
                          <th>Requirement ID</th><th>设计对象</th><th>物料</th><th>数量 / 单位</th>
                          <th>结构角色</th><th>核算</th><th>来源明细</th><th>映射规则</th><th>关系状态</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="source in row.sourceRequirements" :key="source.requirementId" :data-requirement-id="source.requirementId">
                          <td class="identity">{{ source.requirementId }}</td>
                          <td>{{ source.designItemNo }}<small v-if="source.designItemId">ID {{ source.designItemId }}</small></td>
                          <td>{{ source.materialCode }}<small>{{ source.materialName }}</small></td>
                          <td>{{ source.quantity }} / {{ source.uomDisplay }}</td>
                          <td>{{ source.structuralRoleLabel }}</td>
                          <td>{{ source.calculationNo }}<small>ID {{ source.calculationId }}</small></td>
                          <td>{{ source.sourceDetailName }}<small>ID {{ source.sourceDetailId }} · Fact {{ source.sourceFactId ?? '未提供' }}</small></td>
                          <td>{{ source.mappingRuleCode }}<small>ID {{ source.mappingRuleId ?? '未提供' }}</small></td>
                          <td><PceBusinessStatus :status-label="source.relationStatusLabel" source="server" /></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import { buildBomMaterialDetailReadback } from '@/meta/runtime/bomMaterialDetailReadback.js'

const props = defineProps({ detail: { type: Object, required: true } })
const expandedItemIds = ref([])
const readback = computed(() => buildBomMaterialDetailReadback(props.detail))

function toggle(id) {
  expandedItemIds.value = expandedItemIds.value.includes(id)
    ? expandedItemIds.value.filter(value => value !== id)
    : [...expandedItemIds.value, id]
}

watch(() => props.detail?.id, () => { expandedItemIds.value = [] })
</script>

<style scoped>
.bom-material-readback { margin-top:18px; padding-top:16px; border-top:1px solid #dce4ed; }
.readback-header { display:flex; justify-content:space-between; gap:18px; align-items:flex-start; margin-bottom:14px; }
.readback-header h3,.source-panel h4 { margin:0; color:#193a50; }
.readback-header p { margin:6px 0 0; color:#60758a; line-height:1.6; }
.readback-counts { display:grid; grid-template-columns:auto auto; align-items:baseline; gap:2px 7px; min-width:128px; padding:9px 12px; border-radius:9px; background:#eef6f8; }
.readback-counts strong { color:#126b78; font-size:18px; text-align:right; }
.readback-counts span { color:#60758a; font-size:12px; }
.material-table-scroll,.source-table-scroll { width:100%; overflow-x:auto; }
.material-table,.source-table { width:100%; border-collapse:collapse; color:#263b4b; }
.material-table { min-width:920px; }
.source-table { min-width:1320px; margin-top:10px; }
th,td { padding:10px 11px; border:1px solid #dce4ed; text-align:left; vertical-align:top; }
th { background:#f4f8fb; color:#3c5263; font-size:13px; white-space:nowrap; }
td { font-size:13px; }
.identity { font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-weight:600; }
.number { text-align:right; font-variant-numeric:tabular-nums; }
.source-row > td { padding:0; background:#f8fbfd; }
.source-panel { padding:16px; border-left:4px solid #2b7a87; }
.source-table td small { display:block; margin-top:4px; color:#718293; font-family:inherit; font-weight:400; }
@media (max-width: 760px) {
  .readback-header { flex-direction:column; }
  .readback-counts { width:100%; box-sizing:border-box; grid-template-columns:auto 1fr auto 1fr; }
}
</style>

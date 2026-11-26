<template>
  <div class="door-edge" :aria-label="`${requirement.sourceName}第${requirement.row}行`">
    <strong>{{ requirement.sourceName }} · 净长度 {{ requirement.netLengthM }} m</strong>
    <p>{{ requirement.edgeCount }} 条边 · 损耗方式：每边预留</p>
    <p>每边预留：待企业参数（mm）<br>总余量：待定 · 毛需求：待定（不是净量，也不是0）</p>
    <p>来源净量：可判定 · 材料身份：待解析 · 损耗参数：待定</p>
    <small>{{ requirement.sheet }}!{{ requirement.sourceCell }} · {{ requirement.formulaBranch }}分支 · 原生核对一致</small>
    <details>
      <summary>查看{{ requirement.sourceName }}的{{ requirement.edgeCount }}条边及原公式</summary>
      <ul v-if="requirement.segments.length"><li v-for="segment in requirement.segments" :key="segment.segmentNo">第{{ segment.segmentNo }}段：{{ segment.semantic }} {{ segment.netSegmentLengthMm }} mm × {{ segment.quantityMultiplier }}（{{ segment.dimensionCell }}；数量 {{ segment.quantityCell }}）</li></ul>
      <p v-else>本分支原公式结果为0，解析为0条边；不是用0填补未知值。未给真实预留参数，毛需求仍待定。</p>
      <p>长度依据是原公式引用的门套尺寸，不擅自替换成门扇高宽。</p>
      <code>{{ requirement.sourceFormula }}</code>
      <small>公式族 {{ requirement.formulaFamily }}<br>来源身份 {{ requirement.sourceType }}<br>来源公式直接计算净长度；单位m。25/50不擅自解释为宽度。</small>
    </details>
  </div>
</template>
<script setup>
defineProps({ requirement: { type: Object, required: true } })
</script>
<style scoped>
.door-edge{border-left:3px solid #17676c;padding:10px 12px;background:#f4f8fa;min-width:0;margin:10px 0}.door-edge p{margin:6px 0;line-height:1.65}.door-edge strong{font-size:15px}.door-edge small{display:block;color:#506573;line-height:1.6;overflow-wrap:anywhere}.door-edge summary{cursor:pointer;font-weight:600;line-height:1.7}.door-edge code{display:block;white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}.door-edge li{line-height:1.7}
</style>



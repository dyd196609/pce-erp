<template>
<section v-if="reasons.length" class="mes-action-restrictions" role="note" aria-label="当前办理限制" data-ui-revision="THREE-PAGE-PROMPTS-R3">
<h3>当前不能办理的原因</h3><ul><li v-for="row in reasons.slice(0, 3)" :key="row.text">{{ row.text }}</li></ul>
<p>请先核对当前所选对象及下列原服务条件；可使用本页已有的刷新、选择和原记录入口查看，不会绕过限制。</p>
<p v-if="reasons.length > 3">另有 {{ reasons.length - 3 }} 项动作限制，仍禁止办理；请展开下方完整核验信息查看。</p><details><summary>展开全部限制、原始核验信息与动作对应</summary><section v-for="group in groups" :key="group.label"><strong>{{ group.label }}</strong><p v-for="(item,index) in group.items || []" :key="index">{{ label(item) }}</p></section></details>
</section>
</template>
<script setup>
import {computed} from 'vue'
const props=defineProps({groups:{type:Array,default:()=>[]}})
const label=item=>typeof item==='string'?item:item?.statusLabel || item?.message || '原服务阻断项'
const reasons=computed(()=>{const map=new Map();for(const group of props.groups)for(const item of group.items || [])for(const text of label(item).split(/[；;]/).map(s=>s.trim()).filter(Boolean)){if(!map.has(text))map.set(text,{text,scopes:[]});const row=map.get(text);if(group.label&&!row.scopes.includes(group.label))row.scopes.push(group.label)}return [...map.values()]})
</script>
<style scoped>
.mes-action-restrictions{background:#fff7e6;color:#744b0a;border-radius:6px;padding:12px;min-width:0}.mes-action-restrictions h3{margin:0 0 8px}.mes-action-restrictions p,.mes-action-restrictions li{line-height:1.65;overflow-wrap:anywhere}.mes-action-restrictions small{font-size:inherit}.mes-action-restrictions summary{cursor:pointer;min-height:44px;display:list-item;padding:10px 0}.mes-action-restrictions ul{padding-left:22px}
</style>

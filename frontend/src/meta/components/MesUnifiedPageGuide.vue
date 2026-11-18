<template>
<section class="mes-unified-guide" data-ui-revision="THREE-PAGE-UI-20261114-R1">
<nav aria-label="业务查看与返回"><router-link to="/process-center">返回业务流程中心</router-link><router-link :to="listLocation">返回本页列表</router-link></nav>
<details><summary>操作说明 · {{ title }}</summary>
<dl><div><dt>用途</dt><dd>{{ purpose }}</dd></div><div><dt>适用人员</dt><dd>{{ people }}</dd></div><div><dt>前置条件</dt><dd>使用本人账户；先选择有权业务对象并读取最新事实，核对页面所列具体条件。读取失败、无权限和等待条件未满足时不能提交。</dd></div><div><dt>操作步骤</dt><dd>定位任务或交接单 → 核对工单、工序、数量和单位 → 查看当前资格 → 由责任人本人操作。完整业务口径及原记录保留在本页下方。</dd></div><div><dt>结果</dt><dd>以正式回查结果为准。成功后查看原记录；失败按原错误处理；结果待确认时只重新读取，不重复提交。未提供的计划或实际日期保持未知，不使用更新时间替代。</dd></div></dl>
</details>
</section>
</template>
<script setup>
import {computed} from 'vue'
import {useRoute} from 'vue-router'
const props=defineProps({title:String,purpose:String,people:String})
const route=useRoute()
const listLocation=computed(()=>({path:route.path,query:route.query.workOrderId ? {workOrderId:route.query.workOrderId} : {}}))
</script>
<style scoped>
.mes-unified-guide{min-width:0;border:1px solid #dbe3ef;border-radius:10px;background:#fff;padding:12px 16px}.mes-unified-guide nav{display:flex;gap:10px;flex-wrap:wrap}.mes-unified-guide a{display:inline-flex;align-items:center;min-height:44px;padding:0 10px;border:1px solid #b8cce2;border-radius:6px;color:#185b97;text-decoration:none;box-sizing:border-box;overflow-wrap:anywhere}.mes-unified-guide summary{cursor:pointer;min-height:44px;display:flex;align-items:center;font-weight:600;color:#193e5e}.mes-unified-guide dl{margin:0;display:grid;gap:12px}.mes-unified-guide dt{font-weight:600;color:#193e5e}.mes-unified-guide dd{margin:4px 0 0;line-height:1.6;color:#52677b;overflow-wrap:anywhere}.mes-unified-guide :focus-visible{outline:3px solid #2563eb;outline-offset:2px}@media(max-width:650px){.mes-unified-guide{padding:10px;font-size:14px}.mes-unified-guide nav{gap:6px}.mes-unified-guide a{padding:0 8px}}
</style>


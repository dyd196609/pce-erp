<template>
  <main class="page">
    <section class="hero"><div><p>企业基础资料 · 已验收事实正式化</p><h1>Group 1 + 产品分类最小正式写入</h1></div><strong>物料 / ProductDefinition / 版本 / 配置 / 订单 WRITE 0</strong></section>
    <section v-if="error" class="panel error">{{ error }}</section>
    <section v-if="facts.counts" class="panel">
      <h2>生产库写前 / 当前回读</h2><p class="hash">DB SHA-256：{{ facts.databaseSha256 }}</p>
      <div class="cards"><article v-for="(value,key) in facts.counts" :key="key"><span>{{ key }}</span><strong>{{ value }}</strong></article></div>
    </section>
    <section class="panel"><h2>明确授权范围</h2><ul><li>客户/经销商 88 条：按07经销商真实名称创建或匹配</li><li>供应商 18 条有效名称：创建或匹配；2条空名称阻断</li><li>UOM：10项既有映射；平方→m²；面积→calculation_basis=AREA，不创建UOM</li><li>产品分类：房门、柜体、饰面；ProductDefinition保持0</li></ul><button :disabled="working" @click="execute">{{ working ? '正在执行并回读……' : '执行已验证事实最小正式化' }}</button></section>
    <section v-if="result.after" class="panel success" data-acceptance-id="validated-fact-readback"><h2>正式写入已完成并回读</h2><p class="hash">Before：{{ result.before.databaseSha256 }}<br>After：{{ result.after.databaseSha256 }}</p><pre>{{ JSON.stringify(result.results, null, 2) }}</pre><p><strong>Material write {{ result.materialWriteCount }} · Order write {{ result.productionBusinessOrderWriteCount }}</strong></p></section>
    <nav class="links"><router-link to="/foundation/base-data-comparison/customers">客户对照</router-link><router-link to="/foundation/base-data-comparison/suppliers">供应商对照</router-link><router-link to="/foundation/master-data/product-categories">正式产品分类</router-link><router-link to="/foundation/group2-comparison/materials">物料人工验收</router-link></nav>
  </main>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { enterpriseMasterDataApi } from '@/api/enterpriseMasterData.js'
const facts=ref({}); const result=ref({}); const working=ref(false); const error=ref('')
async function load(){try{const r=await enterpriseMasterDataApi.validatedFactFormalization('GET');facts.value=r?.data??r}catch(e){error.value=e?.response?.data?.errorMessage||e?.message||'读取失败'}}
async function execute(){working.value=true;error.value='';try{const r=await enterpriseMasterDataApi.validatedFactFormalization('POST');if(r?.success===false)throw new Error(r?.error?.message||'正式化失败');result.value=r?.data??r;await load()}catch(e){error.value=e?.response?.data?.errorMessage||e?.message||'正式化失败'}finally{working.value=false}}
onMounted(load)
</script>
<style scoped>.page{padding:24px;color:#17223a}.hero,.panel{padding:20px 22px;margin-bottom:18px;border:1px solid #dce4ef;border-radius:16px;background:#fff}.hero{display:flex;justify-content:space-between;gap:20px;color:#fff;background:linear-gradient(135deg,#143b69,#315bcf)}.hero p,.hero h1{margin:0}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}.cards article{display:grid;padding:12px;border-left:4px solid #315bcf;background:#f5f8fc}.cards span{font-size:12px;color:#637189}.cards strong{font-size:22px}button{padding:11px 18px;border:0;border-radius:9px;color:#fff;background:#315bcf;cursor:pointer}.hash{word-break:break-all;font-family:monospace}.success{border-left:5px solid #168357}.error{color:#a6241c}.links{display:flex;flex-wrap:wrap;gap:10px}.links a{padding:10px 14px;border-radius:9px;background:#e8efff;text-decoration:none;color:#284da0}pre{overflow:auto;max-height:480px;background:#f6f8fc;padding:14px}</style>

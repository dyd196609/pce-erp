<template>
  <nav class="foundation-breadcrumb" aria-label="企业基础资料导航" data-acceptance-id="foundation-breadcrumb">
    <router-link :to="routes.enterpriseFoundation">企业基础资料</router-link><template v-if="showAcceptanceCenter"><span>›</span><router-link :to="routes.acceptanceCenter">基础数据人工验收中心</router-link></template>
    <template v-if="group"><span>›</span><span>{{ group }}</span></template><template v-if="module"><span>›</span><span>{{ module }}</span></template>
    <router-link v-if="showReturn" class="return-link" :to="returnTo || routes.acceptanceCenter">{{ returnLabel }}</router-link>
  </nav>
</template>
<script setup>
import { FOUNDATION_ROUTES } from '@/meta/master-data/foundationNavigationRegistry.js'
defineProps({
  group: { type: String, default: '' }, module: { type: String, default: '' },
  showReturn: { type: Boolean, default: false }, showAcceptanceCenter: { type: Boolean, default: true },
  returnTo: { type: String, default: '' }, returnLabel: { type: String, default: '返回基础数据人工验收中心' },
})
const routes = FOUNDATION_ROUTES
</script>
<style scoped>
.foundation-breadcrumb{display:flex;align-items:center;gap:8px;min-height:36px;margin:0 0 14px;padding:8px 12px;border:1px solid #dbe3ef;border-radius:10px;background:#f7f9fc;color:#53627a;font-size:13px}.foundation-breadcrumb a{color:#2457ba;font-weight:700;text-decoration:none}.foundation-breadcrumb .return-link{margin-left:auto;padding:6px 10px;border-radius:8px;background:#e8efff}@media(max-width:760px){.foundation-breadcrumb{align-items:flex-start;flex-wrap:wrap}.foundation-breadcrumb .return-link{margin-left:0;width:100%}}
</style>

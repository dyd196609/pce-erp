<template>
  <section>
    <h2>新建接单来源</h2>
    <router-link to="/sales/orders">返回接单</router-link>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="source">
      <p v-if="source.confirmation">
        确认人 {{ source.confirmation.actorName }} · 确认时间 {{ formatConfirmationTime(source.confirmation.confirmedAt) }}
      </p>
      <p>{{ source.sourceNo }} · 版本 {{ source.sourceVersion }} · {{ source.statusLabel }}</p>
      <p>{{ source.payload.businessOrderReference.projectName }} · {{ source.payload.businessOrderReference.customerName }}</p>
      <ul><li v-for="row in source.payload.engineeringRows" :key="row.sourceRowId">
        {{ row.product }} / {{ row.component }} · {{ row.quantity }} {{ row.unit }}
      </li></ul>
      <section v-if="source.formalScope">
        <h3>正式订单行范围</h3>
        <router-link :to="{ path: '/sales/orders', query: { linkedSource: source.id } }">关联创建销售订单</router-link>
        <p>登记账号 {{ source.formalScope.registeredBy }} · 登记时间 {{ formatConfirmationTime(source.formalScope.registeredAt) }}</p>
        <ul><li v-for="row in source.formalScope.items" :key="row.key">
          来源行 {{ row.key }} · {{ row.materialName }} · {{ row.quantity }} {{ row.unit }}
        </li></ul>
      </section>
      <form v-if="source.canRegisterScope" @submit.prevent="registerScope">
        <h3>登记正式订单行范围</h3>
        <fieldset v-for="(row, index) in scopeRows" :key="row.sourceRowId">
          <legend>{{ source.payload.engineeringRows[index].product }}／{{ source.payload.engineeringRows[index].component }}</legend>
          <label>正式物料
            <select v-model="row.materialId" required>
              <option value="" disabled>请选择物料</option>
              <option v-for="item in source.scopeOptions.materials" :key="item.id" :value="item.id">{{ item.code }} {{ item.name }}</option>
            </select>
          </label>
          <label>销售单位
            <select v-model="row.uomId" required>
              <option value="" disabled>请选择单位</option>
              <option v-for="unit in source.scopeOptions.units" :key="unit.id" :value="unit.id">{{ unit.name }}</option>
            </select>
          </label>
          <label>数量 <input v-model="row.quantity" required type="number" min="0.0001" step="0.0001"></label>
        </fieldset>
        <button :disabled="busy">登记正式订单行范围</button>
      </form>
      <template v-if="source.canConfirm">
        <p>请核对当前版本及适用明细。确认后保留该来源版本和内容。</p>
        <el-button :loading="busy" @click="confirmSource">确认来源</el-button>
      </template>
      <router-link :to="{ path: '/sales/order-reviews', query: { sourceRecord: source.id } }">进入订单评审</router-link>
    </template>
    <form v-else-if="scope && !route.query.sourceRecord" @submit.prevent="save">
      <label>项目 <input v-model.trim="form.projectName" required maxlength="180"></label>
      <label>客户 <input v-model.trim="form.customerName" required maxlength="120"></label>
      <fieldset v-for="(row, index) in form.rows" :key="index">
        <legend>适用明细 {{ index + 1 }}</legend>
        <label>产品 <input v-model.trim="row.product" required maxlength="120"></label>
        <label>部件 <input v-model.trim="row.component" required maxlength="120"></label>
        <label>数量 <input v-model="row.quantity" required type="number" min="0.0001" step="0.0001"></label>
        <label>单位 <input v-model.trim="row.unit" required maxlength="40"></label>
        <button v-if="form.rows.length > 1" type="button" @click="form.rows.splice(index, 1)">删除</button>
      </fieldset>
      <button type="button" :disabled="form.rows.length >= 200" @click="form.rows.push(blankRow())">新增明细</button>
      <button :disabled="busy">保存来源</button>
    </form>
  </section>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { salesApi } from '@/api/sales'

const route = useRoute()
const router = useRouter()
const source = ref(null)
const scope = ref(null)
const scopeRows = ref([])
const error = ref('')
const busy = ref(false)
const formatConfirmationTime = value => new Date(value).toLocaleString('zh-CN')
const blankRow = () => ({ product: '', component: '', quantity: '', unit: '' })
const form = reactive({ projectName: '', customerName: '', rows: [blankRow()] })

watch(() => route.query.sourceRecord, async id => {
  source.value = null
  error.value = ''
  try {
    const result = await salesApi.newOrderSource(id)
    if (route.query.sourceRecord !== id) return
    if (!result.success) throw new Error(result.error?.message)
    if (id) {
      source.value = result.data
      scopeRows.value = result.data.payload.engineeringRows.map(row => ({
        sourceRowId: row.sourceRowId, materialId: '', uomId: '', quantity: row.quantity,
      }))
    } else scope.value = result.data
  } catch (cause) {
    error.value = cause.message || '接单来源读取失败'
  }
}, { immediate: true })

async function registerScope() {
  const { id, sourceVersion, contentHash } = source.value
  busy.value = true
  error.value = ''
  try {
    const result = await salesApi.registerOrderSourceScope(id, { sourceVersion, contentHash, items: scopeRows.value })
    if (!result.success) throw new Error(result.error?.message)
    const readback = await salesApi.newOrderSource(id)
    if (!readback.success) throw new Error(readback.error?.message)
    if (source.value?.id === id) source.value = readback.data
  } catch (cause) {
    error.value = cause.message || '范围登记失败'
  } finally {
    busy.value = false
  }
}

async function confirmSource() {
  const { id, sourceVersion, contentHash } = source.value
  busy.value = true
  error.value = ''
  try {
    const result = await salesApi.confirmNewOrderSource(id, { sourceVersion, contentHash })
    if (!result.success) throw new Error(result.error?.message)
    const readback = await salesApi.newOrderSource(id)
    if (!readback.success) throw new Error(readback.error?.message)
    source.value = readback.data
  } catch (cause) {
    error.value = cause.message || '来源确认失败'
  } finally {
    busy.value = false
  }
}

async function save() {
  busy.value = true
  error.value = ''
  try {
    const result = await salesApi.saveNewOrderSource({ ...form, departmentId: scope.value.departmentId })
    if (!result.success) throw new Error(result.error?.message)
    await router.replace({ query: { mode: 'new-order-source', sourceRecord: result.data.id } })
  } catch (cause) {
    error.value = cause.message || '接单来源保存失败'
  } finally {
    busy.value = false
  }
}
</script>

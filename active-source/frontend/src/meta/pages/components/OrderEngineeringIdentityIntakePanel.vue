<template>
  <section v-if="facts?.controlledIdentityCarryEnabled || error" class="card" data-acceptance-id="order-engineering-identity-intake">
    <h2>订单行按单工程身份承接</h2>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <template v-if="facts?.controlledIdentityCarryEnabled">
      <p>{{ facts.identity.salesOrderNo }}／版本 {{ facts.orderVersion }}／行 {{ facts.identity.lineNo }}；来源 {{ facts.source.sourceRecordId }}／版本 {{ facts.source.sourceVersion }}</p>
      <p>PDE评审 {{ facts.admission.pdeReviewId }}／V{{ facts.admission.pdeReviewVersion }}；前序关系 {{ facts.admission.predecessorRelationId }}；授权 {{ facts.admission.authorizationId }}</p>
      <p>当前模式：{{ facts.identity.engineeringModeLabel }}；{{ facts.identity.materialCode }} {{ facts.identity.materialName }}</p>
      <el-alert title="本操作只确认工程身份，不改客户、物料、数量、价格或交期，不清除CRM原交期异议；补拟测试资料不是正式工程参数。原MAKE快照及审批历史保留，服务端追加受控承接证明。" type="info" :closable="false" />
      <p v-if="facts.oei">已建立工程实例：{{ facts.oei.instanceNo }}（{{ facts.oei.statusLabel }}）；分类 {{ facts.identity.productCategoryName }}；工艺 {{ facts.identity.selectedProcessTypeName }}。</p>
      <p v-if="facts.oei"><router-link :to="{ path: '/pde/product-definitions', query: { companyId: facts.authorizationDecision.organizationId, orderNo: facts.identity.salesOrderNo, salesOrderId: facts.identity.salesOrderId, salesOrderItemId: facts.identity.salesOrderItemId, orderEngineeringInstanceId: facts.oei.id, sourceRecordId: facts.source.sourceRecordId, sourceVersion: facts.source.sourceVersion, authorizationId: facts.admission.authorizationId } }">办理本单产品设计（首次准备、填写保存、刷新核对）</router-link></p>
      <el-form v-if="!facts.oei" label-width="140px">
        <el-form-item label="客户产品名称"><el-input v-model="form.customerProductName" :disabled="busy || !facts.canCreate" placeholder="按已确认资料填写，不自动采用补拟测试内容" /></el-form-item>
        <el-form-item label="产品分类"><el-select v-model="form.productCategoryId" :disabled="busy || !facts.canCreate" placeholder="选择有效产品分类"><el-option v-for="row in facts.productCategories" :key="row.id" :label="`${row.name}（${row.code}）`" :value="row.id" /></el-select></el-form-item>
        <el-form-item label="工艺类型"><el-select v-model="form.selectedProcessTypeId" :disabled="busy || !facts.canCreate" placeholder="选择经业务确认的有效工艺"><el-option v-for="row in facts.processTypes" :key="row.id" :label="`${row.name}（${row.code}）`" :value="row.id" /></el-select></el-form-item>
        <el-form-item label="办理依据"><el-input v-model="form.reason" type="textarea" :disabled="busy || !facts.canCreate" maxlength="300" placeholder="说明本次工程身份承接依据；原CRM风险仍须跟进" /></el-form-item>
        <el-button type="primary" :loading="busy" :disabled="!facts.canCreate || !complete" :data-action-code="facts.actionCode" @click="confirm">{{ facts.confirmActionLabel }}</el-button>
        <p v-if="!facts.permissionAllowed">{{ facts.authorizationDecision.reason }}</p>
      </el-form>
      <p v-if="receipt">{{ receipt }}</p>
      <el-button :loading="busy" @click="load">只读回查身份</el-button>
    </template>
  </section>
</template>
<script setup>
import {computed,onMounted,ref,watch} from 'vue'
import {ElMessageBox} from 'element-plus'
import {pdeApi} from '@/api/pde.js'
const props=defineProps({salesOrderItemId:{type:[Number,String],required:true}})
const emit=defineEmits(['facts','saved'])
const facts=ref(null),error=ref(''),busy=ref(false),receipt=ref('')
const form=ref({customerProductName:'',productCategoryId:null,selectedProcessTypeId:null,reason:''})
const complete=computed(()=>form.value.customerProductName.trim() && form.value.productCategoryId && form.value.selectedProcessTypeId && form.value.reason.trim().length>=2)
let sequence=0
async function load(){const own=++sequence;error.value='';try{const r=await pdeApi.orderEngineeringIntake(props.salesOrderItemId);if(own!==sequence)return;if(!r.success)throw new Error(r.error?.message||'工程身份读取失败');facts.value=r.data;emit('facts',r.data)}catch(e){if(own===sequence)error.value=e.message}}
async function confirm(){
 if(busy.value||!complete.value||!facts.value?.canCreate)return
 busy.value=true
 try{
  await ElMessageBox.confirm('确认依据已审批PDE授权建立本订单行按单工程身份？不会创建BOM、排产或执行生产。','确认工程身份',{type:'warning'})
  const result=await pdeApi.confirmOrderEngineeringIntake({...form.value,salesOrderItemId:facts.value.identity.salesOrderItemId,sourceRecordId:facts.value.source.sourceRecordId,authorizationId:facts.value.admission.authorizationId,expectedOrderVersion:facts.value.orderVersion,expectedSourceContentHash:facts.value.source.sourceContentHash},`engineering-intake-${Date.now()}`)
  if(!result.success)throw new Error(result.error?.message||'工程身份保存失败')
  receipt.value=`工程身份已保存；承接证明 ${result.data.engineeringIdentityCarryProofId || '未返回'}。`
  await load()
  emit('saved')
 }catch(e){if(e!=='cancel'&&e!=='close')error.value=e.message||'操作未完成；输入保留'}finally{busy.value=false}
}
onMounted(load)
watch(()=>props.salesOrderItemId,()=>{facts.value=null;receipt.value='';load()})
</script>

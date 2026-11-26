<template>
  <el-form label-width="130px" class="catalog-form">
    <el-form-item :label="selectLabel"><el-select v-model="form.id" clearable filterable @change="load"><el-option v-for="row in rows" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
    <el-form-item :label="kind==='responsibility'?'责任编码':'编码'" required><el-input v-model="form.code" :disabled="kind==='responsibility'&&!!form.id&&form.status!=='DRAFT'" /></el-form-item>
    <el-form-item :label="kind==='responsibility'?'责任名称':'名称'" required><el-input v-model="form.name" /></el-form-item>
    <el-form-item v-if="kind==='level'" label="等级顺序"><el-input-number v-model="form.rank" :min="1" /></el-form-item>
    <el-form-item v-if="kind==='responsibility'" label="业务领域"><el-input v-model="form.businessDomain" placeholder="例如：采购、供应商、财务" /></el-form-item>
    <el-form-item :label="kind==='responsibility'?'责任说明':'说明'"><el-input v-model="form.description" type="textarea" /></el-form-item>
    <template v-if="kind==='responsibility'">
      <el-form-item label="状态" required><el-select v-model="form.status"><el-option v-for="item in responsibilityStatuses" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
      <el-form-item label="有效期"><div class="date-pair"><el-date-picker v-model="form.effectiveFrom" value-format="YYYY-MM-DD" placeholder="生效日期" /><el-date-picker v-model="form.effectiveTo" value-format="YYYY-MM-DD" placeholder="失效日期" /></div></el-form-item>
      <el-alert title="责任必须先以草稿创建；生效后编码不可修改，失效后不可恢复生效。历史责任不提供删除操作。" type="info" :closable="false" show-icon />
    </template>
    <el-form-item v-else label="状态"><el-switch v-model="form.active" /></el-form-item>
    <el-form-item label="修改原因" required><el-input v-model="form.reason" type="textarea" /></el-form-item>
    <el-form-item><el-button type="primary" :loading="saving" @click="$emit('save',action,form)">保存并回读</el-button></el-form-item>
  </el-form>
</template>
<script setup>
import { computed, reactive, watch } from 'vue'
const props=defineProps({kind:{type:String,required:true},facts:{type:Object,required:true},saving:Boolean,initialRow:{type:Object,default:()=>({})}})
defineEmits(['save'])
const responsibilityStatuses=[{value:'DRAFT',label:'草稿'},{value:'ACTIVE',label:'生效'},{value:'SUSPENDED',label:'暂停'},{value:'EXPIRED',label:'失效'}]
const emptyForm=()=>({id:null,code:'',name:'',rank:1,businessDomain:'',description:'',active:true,status:'DRAFT',effectiveFrom:'',effectiveTo:'',reason:''})
const form=reactive(emptyForm())
const rows=computed(()=>props.kind==='family'?props.facts.jobFamilies:props.kind==='level'?props.facts.jobLevels:props.facts.responsibilities)
const action=computed(()=>props.kind==='family'?'SAVE_JOB_FAMILY':props.kind==='level'?'SAVE_JOB_LEVEL':'SAVE_RESPONSIBILITY')
const selectLabel=computed(()=>props.kind==='family'?'选择岗位族':props.kind==='level'?'选择岗位等级':'选择职责')
function load(id){const row=rows.value?.find(item=>item.id===id);Object.assign(form,row?{...emptyForm(),...row,businessDomain:row.businessDomain||row.category||'',active:row.isActive!==false,reason:''}:emptyForm())}
watch(()=>props.initialRow,row=>{if(props.kind==='responsibility')Object.assign(form,row?.id?{...emptyForm(),...row,businessDomain:row.businessDomain||row.category||'',active:row.isActive!==false,reason:''}:emptyForm())},{immediate:true})
</script>
<style scoped>.catalog-form{max-width:840px;margin:16px auto 0}.catalog-form :deep(.el-select),.catalog-form :deep(.el-input),.catalog-form :deep(.el-textarea){width:100%}.date-pair{display:flex;gap:10px;width:100%}.date-pair>*{flex:1}</style>

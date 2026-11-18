<template>
  <section aria-label="柜体结构化测试部件">
    <h3>柜体结构化测试部件</h3>
    <p>手工明确测试拆分，不自动拆柜。数量为订单总部件数量，仅乘一次；不会修改已确认基线。保存后仍须重新提交批准及另存新基线。</p>
    <el-button @click="load">读取当前部件与有效选项</el-button>
    <p v-if="error">{{ error }}</p>
    <template v-if="options">
      <el-table :data="parts">
        <el-table-column label="部件名称"><template #default="{row}"><el-input v-model="row.name" /></template></el-table-column>
        <el-table-column label="长度"><template #default="{row}"><el-input v-model="row.length" /></template></el-table-column>
        <el-table-column label="宽度"><template #default="{row}"><el-input v-model="row.width" /></template></el-table-column>
        <el-table-column label="尺寸单位"><template #default="{row}"><el-select v-model="row.dimensionUomId"><el-option v-for="u in options.units.filter(x=>x.dimension==='length')" :key="u.id" :value="u.id" :label="u.code" /></el-select></template></el-table-column>
        <el-table-column label="订单总部件数量"><template #default="{row}"><el-input v-model="row.quantity" /></template></el-table-column>
        <el-table-column label="数量单位"><template #default="{row}"><el-select v-model="row.quantityUomId"><el-option v-for="u in options.units.filter(x=>x.dimension==='count')" :key="u.id" :value="u.id" :label="u.code" /></el-select></template></el-table-column>
        <el-table-column label="见光"><template #default="{row}"><el-select v-model="row.visibleCondition"><el-option v-for="v in options.visibleConditions" :key="v" :value="v" :label="v" /></el-select></template></el-table-column>
        <el-table-column label="封边"><template #default="{row}"><el-select v-model="row.edgeMethod"><el-option v-for="v in options.edgeMethods" :key="v" :value="v" :label="v" /></el-select></template></el-table-column>
        <el-table-column label="部件依据"><template #default="{row}"><el-input v-model="row.basis" /></template></el-table-column>
        <el-table-column label="操作"><template #default="{$index}"><el-button @click="parts.splice($index,1)">移除未保存行</el-button></template></el-table-column>
      </el-table>
      <el-button @click="addPart">增加测试部件</el-button>
      <el-input v-model="reason" placeholder="本次测试拆分假设及新修订原因（必填）" />
      <el-button :disabled="!parts.length || !reason.trim()" @click="save">保存所选项测试部件新修订</el-button>
    </template>
  </section>
</template>
<script setup>
import {ref,watch} from 'vue'
import {pdeApi} from '@/api/pde.js'
const props=defineProps({current:Object}),emit=defineEmits(['save'])
const options=ref(null),parts=ref([]),reason=ref(''),error=ref('')
watch(()=>props.current,()=>{options.value=null;parts.value=[];reason.value=''})
async function load(){try{const r=await pdeApi.testCalculationPreview({mode:'options'});options.value=r.data??r;parts.value=JSON.parse(JSON.stringify(props.current?.components||[]));error.value=''}catch(e){error.value=e?.response?.data?.message||e.message}}
function save(){emit('save',{contractVersion:'CABINET-PARTS-TEST-V1',ruleFamily:'THREE_IN_ONE',quantityBasis:'ORDER_COMPONENT_TOTAL',components:parts.value,provenance:{classification:'DEVELOPMENT_TEST_ASSUMPTION',reason:reason.value,references:['人工补拟测试清单；保留本项原来源与批准沿革']}},reason.value)}
function addPart(){parts.value.push({key:crypto.randomUUID(),name:'',length:'',width:'',quantity:'',dimensionUomId:null,quantityUomId:null,visibleCondition:'',edgeMethod:'',basis:''})}
</script>


<template>
  <el-dialog v-model="visible" :title="dialogTitle" width="min(980px, 95vw)" destroy-on-close>
    <el-alert title="唯一正式维护入口：所有保存都经过独立写权限、AuthorizationService、事务和组织运作审计。" type="success" :closable="false" show-icon />

    <el-tabs v-if="section==='departments'" v-model="tab">
      <el-tab-pane label="部门信息与关系" name="department">
        <el-form label-width="130px" class="form-grid">
          <el-form-item label="部门编码"><el-input :model-value="departmentForm.departmentId ? departmentForm.code : '系统自动生成'" disabled /><small class="code-hint">新增时统一发号；编辑不重新编号。</small></el-form-item>
          <el-form-item label="部门名称" required><el-input v-model="departmentForm.name" /></el-form-item>
          <el-form-item label="所属公司"><el-input :model-value="companyName" disabled /></el-form-item>
          <el-form-item label="部门类型" required><el-select v-model="departmentForm.departmentType"><el-option v-for="item in departmentTypes" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
          <el-form-item label="所属组织单元"><el-select v-model="departmentForm.organizationUnitId" clearable filterable><el-option v-for="row in facts.organizationUnits" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
          <el-form-item label="上级部门"><el-select v-model="departmentForm.parentId" clearable filterable><el-option v-for="row in facts.departments.filter(item=>item.id!==departmentForm.departmentId)" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
          <el-form-item label="责任岗位"><el-select v-model="departmentForm.responsiblePositionId" clearable filterable><el-option v-for="row in facts.positions" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
          <el-form-item label="有效期"><div class="date-pair"><el-date-picker v-model="departmentForm.effectiveFrom" value-format="YYYY-MM-DD" placeholder="生效日期" /><el-date-picker v-model="departmentForm.effectiveTo" value-format="YYYY-MM-DD" placeholder="失效日期" /></div></el-form-item>
          <el-form-item label="状态"><el-switch v-model="departmentForm.active" active-text="启用" inactive-text="停用" /></el-form-item>
          <el-form-item label="修改原因" required><el-input v-model="departmentForm.reason" type="textarea" placeholder="必填，写入正式审计" /></el-form-item>
          <el-form-item><el-button type="primary" :loading="saving" @click="save('SAVE_DEPARTMENT',departmentForm)">保存部门并回读</el-button></el-form-item>
        </el-form>
        <el-divider>实际负责人（Employee，与责任岗位严格分离）</el-divider>
        <el-form label-width="130px" class="form-grid">
          <el-form-item label="实际负责人"><el-select v-model="leaderForm.leaderEmployeeId" clearable filterable><el-option v-for="row in formalEmployeeOptions" :key="row.id" :label="`${row.employeeNo} · ${row.fullName}`" :value="row.id" /></el-select></el-form-item>
          <el-form-item label="有效期"><div class="date-pair"><el-date-picker v-model="leaderForm.effectiveFrom" value-format="YYYY-MM-DD" placeholder="生效日期" /><el-date-picker v-model="leaderForm.effectiveTo" value-format="YYYY-MM-DD" placeholder="失效日期" /></div></el-form-item>
          <el-form-item label="修改原因" required><el-input v-model="leaderForm.reason" type="textarea" placeholder="必填，写入正式审计" /></el-form-item>
          <el-form-item><el-button type="primary" :disabled="!leaderForm.departmentId" :loading="saving" @click="save('SAVE_DEPARTMENT_LEADER',leaderForm)">保存实际负责人并回读</el-button></el-form-item>
        </el-form>
      </el-tab-pane>
      <el-tab-pane label="组织单元维护" name="organization-unit">
        <el-form label-width="130px" class="form-grid">
          <el-form-item label="选择组织单元"><el-select v-model="unitForm.id" clearable filterable @change="loadUnit"><el-option v-for="row in facts.organizationUnits" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
          <el-form-item label="组织单元编码"><el-input :model-value="unitForm.id ? unitForm.code : '系统自动生成'" disabled /><small class="code-hint">新增时统一发号；编辑不重新编号。</small></el-form-item>
          <el-form-item label="组织单元名称" required><el-input v-model="unitForm.name" /></el-form-item>
          <el-form-item label="组织类型" required><el-select v-model="unitForm.unitType"><el-option v-for="item in unitTypes" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
          <el-form-item label="上级组织单元"><el-select v-model="unitForm.parentId" clearable filterable><el-option v-for="row in facts.organizationUnits.filter(item=>item.id!==unitForm.id)" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
          <el-form-item label="有效期"><div class="date-pair"><el-date-picker v-model="unitForm.effectiveFrom" value-format="YYYY-MM-DD" placeholder="生效日期" /><el-date-picker v-model="unitForm.effectiveTo" value-format="YYYY-MM-DD" placeholder="失效日期" /></div></el-form-item>
          <el-form-item label="状态"><el-switch v-model="unitForm.active" /></el-form-item>
          <el-form-item label="修改原因" required><el-input v-model="unitForm.reason" type="textarea" /></el-form-item>
          <el-form-item><el-button type="primary" :loading="saving" @click="save('SAVE_ORGANIZATION_UNIT',unitForm)">保存组织单元并回读</el-button></el-form-item>
        </el-form>
      </el-tab-pane>
    </el-tabs>

    <el-tabs v-else-if="section==='positions'" v-model="tab">
      <el-tab-pane v-if="!responsibilityAssignmentOnly" label="岗位信息与关系" name="position">
        <el-form label-width="130px" class="form-grid">
          <el-form-item label="岗位编码"><el-input :model-value="positionForm.positionId ? positionForm.code : '系统自动生成'" disabled /><small class="code-hint">新增时统一发号；编辑不重新编号。</small></el-form-item>
          <el-form-item label="岗位名称" required><el-input v-model="positionForm.name" /></el-form-item>
          <el-form-item label="所属公司"><el-input :model-value="companyName" disabled /></el-form-item>
          <el-form-item label="所属部门" required><el-select v-model="positionForm.departmentId" filterable><el-option v-for="row in facts.departments" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
          <el-form-item label="岗位族"><el-select v-model="positionForm.jobFamilyId" clearable filterable><el-option v-for="row in facts.jobFamilies" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
          <el-form-item label="岗位等级"><el-select v-model="positionForm.jobLevelId" clearable filterable><el-option v-for="row in facts.jobLevels" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
          <el-form-item label="上级岗位"><el-select v-model="positionForm.parentPositionId" clearable filterable><el-option v-for="row in facts.positions.filter(item=>item.id!==positionForm.positionId)" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
          <el-form-item label="默认角色"><el-select v-model="positionForm.defaultRoleId" clearable filterable><el-option v-for="row in facts.roles" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
          <el-form-item label="岗位说明"><el-input v-model="positionForm.description" type="textarea" /></el-form-item>
          <el-form-item label="职责摘要"><el-input v-model="positionForm.responsibilitySummary" type="textarea" /></el-form-item>
          <el-form-item label="有效期"><div class="date-pair"><el-date-picker v-model="positionForm.effectiveFrom" value-format="YYYY-MM-DD" placeholder="生效日期" /><el-date-picker v-model="positionForm.effectiveTo" value-format="YYYY-MM-DD" placeholder="失效日期" /></div></el-form-item>
          <el-form-item label="状态"><el-switch v-model="positionForm.active" /></el-form-item>
          <el-form-item label="修改原因" required><el-input v-model="positionForm.reason" type="textarea" /></el-form-item>
          <el-form-item><el-button type="primary" :loading="saving" @click="save('SAVE_POSITION',positionForm)">保存岗位并回读</el-button></el-form-item>
        </el-form>
      </el-tab-pane>
      <el-tab-pane v-if="!responsibilityAssignmentOnly" label="岗位族" name="job-family"><CatalogForm kind="family" :facts="facts" :saving="saving" @save="save" /></el-tab-pane>
      <el-tab-pane v-if="!responsibilityAssignmentOnly" label="岗位等级" name="job-level"><CatalogForm kind="level" :facts="facts" :saving="saving" @save="save" /></el-tab-pane>
      <el-tab-pane label="职责分配" name="assignment">
        <el-alert title="岗位只能从责任目录选择已有责任；新责任必须在组织页面顶层“责任管理”中独立创建。" type="info" :closable="false" show-icon />
        <el-form label-width="130px" class="form-grid"><el-form-item label="岗位"><el-select v-model="assignmentForm.positionId" filterable><el-option v-for="row in facts.positions" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item><el-form-item label="职责"><div class="responsibility-source-field"><el-select v-model="assignmentForm.responsibilityId" filterable><el-option v-for="row in responsibilityOptions" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select><small>数据来源：Responsibility API · system.Responsibility</small></div></el-form-item><el-form-item label="承担类型"><el-select v-model="assignmentForm.responsibilityType"><el-option label="主责" value="PRIMARY" /><el-option label="协助" value="SUPPORTING" /></el-select></el-form-item><el-form-item label="状态"><el-switch v-model="assignmentForm.active" active-text="有效" inactive-text="停用" /></el-form-item><el-form-item label="修改原因" required><el-input v-model="assignmentForm.reason" type="textarea" /></el-form-item><el-form-item><el-button type="primary" :loading="saving" @click="save('SAVE_POSITION_RESPONSIBILITY',assignmentForm)">保存职责分配并回读</el-button></el-form-item></el-form>
      </el-tab-pane>
      <el-tab-pane v-if="!responsibilityAssignmentOnly" label="流程责任" name="workflow">
        <el-form label-width="130px" class="form-grid"><el-form-item label="现有流程责任"><el-select v-model="workflowForm.id" clearable filterable @change="loadWorkflow"><el-option v-for="row in facts.workflowResponsibilities" :key="row.id" :label="`${row.positionName} · ${row.workflowCode}/${row.nodeCode}`" :value="row.id" /></el-select></el-form-item><el-form-item label="责任岗位"><el-select v-model="workflowForm.positionId" filterable><el-option v-for="row in facts.positions" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item><el-form-item label="关联职责"><el-select v-model="workflowForm.responsibilityId" clearable filterable><el-option v-for="row in facts.responsibilities" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item><el-form-item label="正式流程节点" required><el-select v-model="workflowForm.workflowNodeId" filterable><el-option v-for="row in facts.workflowNodes" :key="row.id" :label="`${row.workflowCode}/${row.nodeCode} · ${row.nodeName} · ${row.businessActionCode}`" :value="row.id" /></el-select></el-form-item><el-form-item label="责任类型"><el-select v-model="workflowForm.ownershipType"><el-option v-for="item in ownershipTypes" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item><el-form-item label="有效期"><div class="date-pair"><el-date-picker v-model="workflowForm.effectiveFrom" value-format="YYYY-MM-DD" /><el-date-picker v-model="workflowForm.effectiveTo" value-format="YYYY-MM-DD" /></div></el-form-item><el-form-item label="状态"><el-switch v-model="workflowForm.active" /></el-form-item><el-form-item label="修改原因" required><el-input v-model="workflowForm.reason" type="textarea" /></el-form-item><el-form-item><el-button type="primary" :loading="saving" @click="save('SAVE_WORKFLOW_RESPONSIBILITY',workflowForm)">保存流程责任</el-button></el-form-item></el-form>
      </el-tab-pane>
    </el-tabs>

    <section v-else-if="section==='responsibilities'" class="responsibility-catalog">
      <el-alert title="责任目录独立定义企业应承担的责任；岗位不是责任创建者，只能在岗位管理中选择已有责任。" type="success" :closable="false" show-icon />
      <CatalogForm kind="responsibility" :facts="facts" :saving="saving" :initial-row="responsibilityInitialRow" @save="save" />
    </section>

    <el-tabs v-else v-model="tab">
      <el-tab-pane label="员工档案" name="employee">
        <el-alert title="直属主管和职能主管都必须从正式员工档案选择；岗位、角色、部门和用户账户不能作为人员选项。" type="info" :closable="false" show-icon />
        <el-form label-width="180px" class="form-grid">
          <el-form-item label="员工编号"><el-input :model-value="employeeForm.employeeId ? employeeForm.employeeNo : '系统自动生成'" disabled /><small class="code-hint">新增时统一发号；调岗、改名或编辑资料不会重新编号。</small></el-form-item>
          <el-form-item label="姓名" required><el-input v-model="employeeForm.fullName" /></el-form-item>
          <el-form-item label="员工正式公司"><el-input :model-value="employeeFormalCompanyName" disabled /><small class="code-hint">由所选正式部门确定；未选择正式部门时不推定为当前操作公司。</small></el-form-item>
          <el-form-item label="当前操作公司"><el-input :model-value="companyName" disabled /><small class="code-hint">仅表示本次维护所在公司上下文，不等于员工已建立正式任职关系。</small></el-form-item>
          <el-form-item label="正式部门" required><el-select v-model="employeeForm.departmentId" filterable><el-option v-for="row in facts.departments" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
          <el-form-item label="正式岗位" required><div class="reporting-field"><el-select v-model="employeeForm.positionId" filterable :disabled="!employeeForm.departmentId" :no-data-text="positionCandidateMessage"><el-option v-for="row in employeePositionOptions" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select><small>{{ positionCandidateMessage }}</small></div></el-form-item>
          <el-form-item label="直属主管"><div class="reporting-field"><el-select v-model="employeeForm.directManagerId" clearable filterable placeholder="选择员工" :no-data-text="managerCandidateMessage"><el-option v-for="row in reportingManagerOptions" :key="row.id" :label="employeeManagerLabel(row)" :value="row.id" /></el-select><small>员工日常汇报对象，负责日常工作安排和管理。{{ managerCandidateMessage }}</small></div></el-form-item>
          <el-form-item label="直属主管有效期"><div class="date-pair"><el-date-picker v-model="employeeForm.directManagerEffectiveFrom" value-format="YYYY-MM-DD" placeholder="生效日期" /><el-date-picker v-model="employeeForm.directManagerEffectiveTo" value-format="YYYY-MM-DD" placeholder="失效日期" /></div></el-form-item>
          <el-form-item label="职能主管"><div class="reporting-field"><el-select v-model="employeeForm.functionalManagerId" clearable filterable placeholder="选择员工" :no-data-text="managerCandidateMessage"><el-option v-for="row in reportingManagerOptions" :key="row.id" :label="employeeManagerLabel(row)" :value="row.id" /></el-select><small>员工专业领域负责人，负责专业指导和业务规范管理。{{ managerCandidateMessage }}</small><el-button type="primary" plain :disabled="!employeeForm.employeeId||!employeeForm.functionalManagerId" @click="openFunctionalManagerMaintenance">继续填写有效期并保存</el-button></div></el-form-item>
          <el-form-item label="联系电话"><el-input v-model="employeeForm.phone" /></el-form-item>
          <el-form-item label="状态"><el-select v-model="employeeForm.status"><el-option label="在职" value="active" /><el-option label="停用" value="inactive" /><el-option label="休假" value="leave" /><el-option label="离职" value="quit" /></el-select></el-form-item>
          <el-form-item label="修改原因" required><el-input v-model="employeeForm.reason" type="textarea" placeholder="必填；员工及汇报关系 Before/After 写入正式审计" /></el-form-item>
          <el-form-item><el-button type="primary" :loading="saving" @click="save('SAVE_EMPLOYEE',employeeForm)">保存员工及直属主管并回读</el-button></el-form-item>
        </el-form>
      </el-tab-pane>
      <el-tab-pane label="关联登录账户" name="account">
        <el-alert title="这里只建立 Employee 与既有 User 的正式关联；用户名、密码、安全和账号启停仍在“用户账户”维护。" type="info" :closable="false" />
        <el-alert :title="employeeAccountContext?.message||'账户关联范围事实未读取，请关闭后刷新服务端事实。'" :type="employeeAccountContext?.eligible?'info':'warning'" :closable="false" show-icon />
        <el-form label-width="130px" class="form-grid"><el-form-item label="员工"><el-input :model-value="employeeLabel" disabled /></el-form-item><el-form-item label="当前关联账户"><el-input :model-value="employeeAccountContext?(employeeAccountContext.linkedUsername||'未关联登录账户'):'未读取'" disabled /><small class="code-hint">当前绑定来自服务端；选择候选不会自动保存或解除已有绑定。</small></el-form-item><el-form-item label="关联账户"><el-select v-model="accountForm.userId" clearable filterable><el-option v-for="row in availableAccounts" :key="row.id" :label="`${row.username} · ${row.realName}`" :value="row.id" /></el-select><small class="code-hint">已关联其他员工的账户不可重复关联；当前员工原有关联保留显示。</small></el-form-item><el-form-item label="修改原因" required><el-input v-model="accountForm.reason" type="textarea" /></el-form-item><el-form-item><el-button type="primary" :disabled="!accountForm.employeeId||!employeeAccountContext?.eligible" :loading="saving" @click="save('SAVE_EMPLOYEE_ACCOUNT',accountForm)">保存/解除账户关联</el-button></el-form-item></el-form>
      </el-tab-pane>
      <el-tab-pane label="汇报关系详细维护" name="reporting">
        <el-alert :title="reportingForm.relationType==='DIRECT'?'直属主管：员工日常汇报对象，负责日常工作安排和管理。':'职能主管：员工专业领域负责人，负责专业指导和业务规范管理。'" type="info" :closable="false" show-icon />
        <el-form label-width="130px" class="form-grid"><el-form-item label="员工"><el-input :model-value="employeeLabel" disabled /></el-form-item><el-form-item label="汇报类型"><el-select v-model="reportingForm.relationType"><el-option label="直属主管" value="DIRECT" /><el-option label="职能主管" value="FUNCTIONAL" /></el-select></el-form-item><el-form-item :label="reportingForm.relationType==='DIRECT'?'直属主管':'职能主管'"><div class="reporting-field"><el-select v-model="reportingForm.managerId" filterable placeholder="选择员工" :no-data-text="managerCandidateMessage"><el-option v-for="row in reportingManagerOptions" :key="row.id" :label="employeeManagerLabel(row)" :value="row.id" /></el-select><small>{{ managerCandidateMessage }}</small></div></el-form-item><el-form-item label="有效期"><div class="date-pair"><el-date-picker v-model="reportingForm.effectiveFrom" value-format="YYYY-MM-DD" /><el-date-picker v-model="reportingForm.effectiveTo" value-format="YYYY-MM-DD" /></div></el-form-item><el-form-item label="状态"><el-switch v-model="reportingForm.active" /></el-form-item><el-form-item label="修改原因" required><el-input v-model="reportingForm.reason" type="textarea" /></el-form-item><el-form-item><el-button type="primary" :disabled="!reportingForm.employeeId||!reportingForm.managerId" :loading="saving" @click="save('SAVE_REPORTING_RELATION',reportingForm)">保存汇报关系</el-button></el-form-item></el-form>
      </el-tab-pane>
    </el-tabs>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { accessControlApi } from '@/api/accessControl.js'
import CatalogForm from './OrganizationOperatingCatalogForm.vue'

const props=defineProps({facts:{type:Object,required:true},responsibilityOptions:{type:Array,default:()=>[]},responsibilityAssignmentOnly:Boolean})
const emit=defineEmits(['saved'])
const visible=ref(false),saving=ref(false),section=ref('departments'),tab=ref('department'),responsibilityInitialRow=ref({})
const departmentTypes=[{value:'FUNCTIONAL',label:'职能部门'},{value:'BUSINESS',label:'业务部门'},{value:'PRODUCTION',label:'生产部门'},{value:'SUPPORT',label:'支持部门'},{value:'TEAM',label:'团队/班组'}]
const unitTypes=[{value:'COMPANY',label:'公司'},{value:'BUSINESS_UNIT',label:'事业部'},{value:'CENTER',label:'中心'},{value:'DEPARTMENT',label:'部门'},{value:'TEAM',label:'团队/班组'}]
const ownershipTypes=[{value:'OWNER',label:'OWNER（负责）'},{value:'APPROVER',label:'APPROVER（审批）'},{value:'REVIEWER',label:'REVIEWER（审核/复核）'},{value:'EXECUTOR',label:'EXECUTOR（执行）'}]
const departmentForm=reactive({departmentId:null,code:'',name:'',departmentType:'FUNCTIONAL',organizationUnitId:null,parentId:null,responsiblePositionId:null,effectiveFrom:'',effectiveTo:'',active:true,reason:''})
const leaderForm=reactive({departmentId:null,leaderEmployeeId:null,effectiveFrom:'',effectiveTo:'',reason:''})
const unitForm=reactive({id:null,code:'',name:'',unitType:'DEPARTMENT',parentId:null,effectiveFrom:'',effectiveTo:'',active:true,reason:''})
const positionForm=reactive({positionId:null,code:'',name:'',departmentId:null,jobFamilyId:null,jobLevelId:null,parentPositionId:null,defaultRoleId:null,description:'',responsibilitySummary:'',effectiveFrom:'',effectiveTo:'',active:true,reason:''})
const assignmentForm=reactive({positionId:null,responsibilityId:null,responsibilityType:'PRIMARY',active:true,reason:''})
const workflowForm=reactive({id:null,positionId:null,responsibilityId:null,workflowNodeId:null,ownershipType:'OWNER',effectiveFrom:'',effectiveTo:'',active:true,reason:''})
const employeeForm=reactive({employeeId:null,employeeNo:'',fullName:'',departmentId:null,positionId:null,directManagerId:null,directManagerEffectiveFrom:'',directManagerEffectiveTo:'',functionalManagerId:null,phone:'',status:'active',reason:''})
const accountForm=reactive({employeeId:null,userId:null,reason:''})
const reportingForm=reactive({employeeId:null,managerId:null,relationType:'DIRECT',effectiveFrom:'',effectiveTo:'',active:true,reason:''})
const companyName=computed(()=>props.facts.companies?.find(row=>row.id===props.facts.currentUser?.organizationId)?.name||props.facts.companies?.[0]?.name||'当前公司')
const dialogTitle=computed(()=>section.value==='departments'?'部门与组织单元正式维护':section.value==='positions'?'岗位及已有责任分配正式维护':section.value==='responsibilities'?'责任目录正式维护':'员工、账户与汇报关系正式维护')
const employeeLabel=computed(()=>{const row=props.facts.employees?.find(item=>item.id===employeeForm.employeeId);return row?`${row.employeeNo} · ${row.fullName}`:'请先选择或保存员工'})
const employeeAccountContext=computed(()=>props.facts.employees?.find(row=>row.id===accountForm.employeeId)?.accountAssociationContext||null)
const availableAccounts=computed(()=>props.facts.users?.filter(row=>!row.employee||row.employee.id===accountForm.employeeId)||[])
const formalEmployeeOptions=computed(()=>(props.facts.employees||[]).filter(row=>row.formalCandidateBaseEligible))
const employeePositionOptions=computed(()=>employeeForm.departmentId?(props.facts.positions||[]).filter(row=>row.isActive!==false&&row.departmentId===employeeForm.departmentId):[])
const employeeFormalDepartment=computed(()=>props.facts.departments?.find(row=>row.id===employeeForm.departmentId)||null)
const employeeCompanyId=computed(()=>employeeFormalDepartment.value?.companyId||null)
const employeeFormalCompanyName=computed(()=>props.facts.companies?.find(row=>row.id===employeeCompanyId.value)?.name||'未关联正式公司')
const reportingManagerOptions=computed(()=>employeeCompanyId.value?formalEmployeeOptions.value.filter(row=>row.id!==employeeForm.employeeId&&row.companyId===employeeCompanyId.value):[])
const positionCandidateMessage=computed(()=>{
  if(!employeeForm.departmentId)return '请先选择正式部门，再从该部门已启用岗位中选择。'
  return employeePositionOptions.value.length?'候选仅包含所选部门中已启用的正式岗位。':'所选部门当前没有已启用正式岗位；请由用户核对组织事实，不能虚构岗位。'
})
const managerCandidateMessage=computed(()=>{
  if(!employeeForm.departmentId)return '请先选择正式部门；未建立正式公司关系时不生成主管候选。'
  return reportingManagerOptions.value.length?'候选仅包含员工正式公司内在职且正式部门、岗位关系完整的员工。':'所选正式公司当前没有符合任职规则的主管候选；允许按业务规则留空，请由用户决定维护真实员工任职。'
})
function employeeManagerLabel(row){return `${row.fullName}（${row.positionName||'岗位待维护'}）· ${row.employeeNo}`}
function active(row){return row?.isActive!==false&&row?.statusLabel!=='停用'}
function open(target,row={}){
  section.value=target;visible.value=true;tab.value=target==='departments'?'department':target==='positions'?(props.responsibilityAssignmentOnly?'assignment':'position'):'employee'
  if(target==='departments'){
    Object.assign(departmentForm,{departmentId:row.id||null,code:row.code||'',name:row.name||'',departmentType:row.departmentType||'FUNCTIONAL',organizationUnitId:row.organizationUnitId||null,parentId:row.parentId||null,responsiblePositionId:row.responsiblePositionId||null,effectiveFrom:row.effectiveFrom||'',effectiveTo:row.effectiveTo||'',active:active(row),reason:''})
    Object.assign(leaderForm,{departmentId:row.id||null,leaderEmployeeId:row.leaderEmployeeId||null,effectiveFrom:'',effectiveTo:'',reason:''})
  }else if(target==='positions'){
    Object.assign(positionForm,{positionId:row.id||null,code:row.code||'',name:row.name||'',departmentId:row.departmentId||null,jobFamilyId:row.jobFamilyId||null,jobLevelId:row.jobLevelId||null,parentPositionId:row.parentPositionId||null,defaultRoleId:row.defaultRoleId||null,description:row.description||'',responsibilitySummary:row.responsibilitySummary||'',effectiveFrom:row.effectiveFrom||'',effectiveTo:row.effectiveTo||'',active:active(row),reason:''})
    assignmentForm.positionId=row.id||null;workflowForm.positionId=row.id||null
  }else if(target==='responsibilities'){
    responsibilityInitialRow.value={...row}
  }else{
    Object.assign(employeeForm,{employeeId:row.id||null,employeeNo:row.employeeNo||'',fullName:row.fullName||'',departmentId:row.departmentId||null,positionId:row.positionId||null,directManagerId:row.directManagerId||null,directManagerEffectiveFrom:row.directManagerEffectiveFrom||'',directManagerEffectiveTo:row.directManagerEffectiveTo||'',functionalManagerId:row.functionalManagerId||null,phone:row.phone||'',status:row.status||'active',reason:''})
    Object.assign(accountForm,{employeeId:row.id||null,userId:row.userId||null,reason:''})
    Object.assign(reportingForm,{employeeId:row.id||null,managerId:row.directManagerId||null,relationType:'DIRECT',effectiveFrom:'',effectiveTo:'',active:true,reason:''})
  }
}
function loadUnit(id){const row=props.facts.organizationUnits?.find(item=>item.id===id);Object.assign(unitForm,row?{id:row.id,code:row.code,name:row.name,unitType:row.unitType,parentId:row.parentId,effectiveFrom:row.effectiveFrom||'',effectiveTo:row.effectiveTo||'',active:active(row),reason:''}:{id:null,code:'',name:'',unitType:'DEPARTMENT',parentId:null,effectiveFrom:'',effectiveTo:'',active:true,reason:''})}
function loadWorkflow(id){const row=props.facts.workflowResponsibilities?.find(item=>item.id===id);if(row)Object.assign(workflowForm,{id:row.id,positionId:row.positionId,responsibilityId:props.facts.responsibilities?.find(item=>item.code===row.responsibilityCode)?.id||null,workflowNodeId:row.workflowNodeId||null,ownershipType:row.ownershipType,effectiveFrom:row.effectiveFrom||'',effectiveTo:row.effectiveTo||'',active:active(row),reason:''})}
async function save(action,payload){saving.value=true;try{const requestPayload={...payload};if(action==='SAVE_POSITION_RESPONSIBILITY')requestPayload.isPrimary=requestPayload.responsibilityType==='PRIMARY';const response=await accessControlApi.saveEnterpriseOrganizationModel(action,requestPayload);if(!response?.success)throw new Error(response?.error?.message||'保存失败');ElMessage.success('正式组织事实已保存并生成审计');await emit('saved',response.data)}catch(error){const responseError=error?.response?.data?.error;const conflictPrefix=error?.response?.status===409&&responseError?.code?`请求冲突（${responseError.code}）：`:'';ElMessage.error(`${conflictPrefix}${responseError?.message||error?.message||String(error)}`)}finally{saving.value=false}}
function openFunctionalManagerMaintenance(){Object.assign(reportingForm,{employeeId:employeeForm.employeeId,managerId:employeeForm.functionalManagerId,relationType:'FUNCTIONAL',reason:employeeForm.reason});tab.value='reporting'}
defineExpose({open})
</script>

<style scoped>
.form-grid{max-width:840px;margin:16px auto 0}.form-grid :deep(.el-select),.form-grid :deep(.el-input),.form-grid :deep(.el-textarea){width:100%}.date-pair{display:flex;gap:10px;width:100%}.date-pair>*{flex:1}.reporting-field,.responsibility-source-field{display:grid;gap:6px;width:100%}.reporting-field small,.responsibility-source-field small,.code-hint{color:#606266;line-height:1.5}.reporting-field .el-button{justify-self:start}.responsibility-catalog{margin-top:16px}
</style>

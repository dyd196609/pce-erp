<template>
  <main class="enterprise-os-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">{{ t('Enterprise OS') }}</p>
        <h1>{{ currentTitle }}</h1>
        <p class="app-current-module-badge">当前操作模块：{{ currentTitle }}</p>
      </section>
      <nav class="page-tabs app-module-nav-zone">
        <span class="app-nav-zone-title">企业操作模块导航</span>
        <router-link class="app-nav-button" to="/home">本人首页</router-link>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': isEnterpriseNavActive('/work-center') }" to="/work-center">
          {{ t('Work Center') }}
          <span v-if="isEnterpriseNavActive('/work-center')" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': isEnterpriseNavActive('/process-center') }" to="/process-center">
          {{ t('Process Center') }}
          <span v-if="isEnterpriseNavActive('/process-center')" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" to="/process-designer">流程设计中心</router-link>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': isEnterpriseNavActive('/organization') }" to="/organization">
          {{ t('Organization') }}
          <span v-if="isEnterpriseNavActive('/organization')" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': isEnterpriseNavActive('/dashboard') }" to="/dashboard">
          {{ t('Dashboard') }}
          <span v-if="isEnterpriseNavActive('/dashboard')" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': isEnterpriseNavActive('/analytics') }" to="/analytics">
          {{ t('Analytics') }}
          <span v-if="isEnterpriseNavActive('/analytics')" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': isEnterpriseNavActive('/admin') }" to="/admin">
          {{ t('Admin') }}
          <span v-if="isEnterpriseNavActive('/admin')" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" to="/manufacturing/modules">PCE制造数字化能力地图</router-link>
        <router-link class="app-nav-button" to="/foundation">基础资料维护</router-link>
        <router-link class="app-nav-button" to="/reference">数据引用中心</router-link>
        <router-link class="app-nav-button" to="/admin/approval-flow-config">审批流配置</router-link>
      </nav>
    </header>

    <section v-if="message" class="notice">{{ message }}</section>

    <section v-if="isActionPage" class="operation-shell">
      <section class="panel primary-panel">
        <header>
          <div>
            <h2>{{ actionTitle }}</h2>
            <span>{{ actionSubtitle }}</span>
          </div>
          <button type="button" @click="goBack">{{ backLabel }}</button>
        </header>

        <div v-if="route.name === 'WorkTaskAction'" class="detail-layout">
          <section class="info-box">
            <h3>基础信息</h3>
            <p>任务详情：{{ selectedTask?.title || '任务不存在' }}</p>
            <p>任务状态：{{ selectedTask?.status || '-' }}</p>
            <p>负责人：{{ selectedTask?.owner || '-' }}</p>
          </section>
          <label>处理意见<textarea v-model="taskForm.opinion" /></label>
          <div class="button-row">
            <button type="button" @click="saveTask">保存</button>
            <button type="button" @click="finishTaskAction">完成</button>
            <button type="button" @click="goBack">取消</button>
          </div>
        </div>

        <div v-else-if="route.name === 'ApprovalAction'" class="detail-layout">
          <section class="info-box">
            <h3>审批单详情</h3>
            <p>审批事项：{{ selectedApproval?.title || '审批单不存在' }}</p>
            <p>申请人：{{ selectedApproval?.applicant || '-' }}</p>
            <p>金额：{{ selectedApproval?.amount || '-' }}</p>
            <p>状态：{{ selectedApproval?.status || '-' }}</p>
          </section>
          <label>审批意见<textarea v-model="approvalForm.opinion" /></label>
          <div class="button-row">
            <button type="button" @click="approveCurrentApproval">审批通过</button>
            <button type="button" @click="rejectCurrentApproval">驳回</button>
            <button type="button" @click="goBack">返回个人工作台</button>
          </div>
        </div>

        <div v-else-if="route.name === 'ExecutionAction'" class="detail-layout">
          <section class="info-box">
            <h3>执行任务详情</h3>
            <p>任务：{{ selectedExecutionTask?.title || '执行任务不存在' }}</p>
            <p>当前执行步骤：{{ selectedExecutionTask?.status || '-' }}</p>
            <p>负责人：{{ selectedExecutionTask?.owner || '-' }}</p>
          </section>
          <label>执行结果<textarea v-model="executionForm.result" /></label>
          <div class="button-row">
            <button type="button" @click="finishExecution">完成执行</button>
            <button type="button" @click="goBack">返回个人工作台</button>
          </div>
        </div>

        <div v-else-if="organizationActionType" class="detail-layout">
          <section class="info-box">
            <h3>基础信息</h3>
            <p>{{ actionTitle }}，保存后返回组织结构。</p>
          </section>
          <div class="form-grid">
            <label v-for="field in organizationFields" :key="field.key">
              {{ field.label }}
              <input v-model="organizationForm[field.key]" :type="field.type || 'text'" />
            </label>
          </div>
          <div class="button-row">
            <button type="button" @click="saveOrganizationAction">保存</button>
            <button type="button" @click="goBack">返回组织结构</button>
          </div>
        </div>

        <div v-else-if="adminActionPage" class="detail-layout">
          <section class="info-box">
            <h3>{{ actionTitle }}</h3>
            <p>基础信息与处理区。</p>
          </section>
          <div class="form-grid">
            <label>配置名称<input v-model="adminActionForm.name" /></label>
            <label>配置值<input v-model="adminActionForm.value" /></label>
            <label>备注<textarea v-model="adminActionForm.remark" /></label>
          </div>
          <div class="button-row">
            <button type="button" @click="saveAdminAction">保存</button>
            <button type="button" @click="goBack">返回系统配置</button>
          </div>
        </div>
      </section>
    </section>

    <section v-else-if="currentPath === '/work-center'" class="operation-shell">
      <section class="action-bar">
        <strong>快捷操作</strong>
        <button
          v-for="action in state.quickActions"
          :key="action.id"
          type="button"
          @click="createQuickActionTask(action.name)"
        >
          {{ action.name }}
        </button>
      </section>

      <section class="panel primary-panel">
        <header>
          <h2>我的待办任务</h2>
          <span>{{ pendingTasks.length }} 项</span>
        </header>
        <div class="task-table">
          <article v-for="task in pendingTasks" :key="task.id">
            <strong>{{ task.title }}</strong>
            <span>{{ task.process }}</span>
            <span>{{ task.owner }}</span>
            <span>{{ task.due }}</span>
            <div class="button-row">
              <button type="button" @click="router.push(`/work-center/task/${task.id}`)">查看</button>
              <button type="button" @click="router.push(`/work-center/task/${task.id}`)">处理</button>
              <button type="button" @click="finishTask(task.id)">完成</button>
            </div>
          </article>
        </div>
      </section>

      <section class="two-column">
        <section class="panel">
          <header>
            <h2>我的审批</h2>
            <span>{{ state.approvals.length }} 项</span>
          </header>
          <article v-for="approval in state.approvals" :key="approval.id" class="list-row">
            <div>
              <strong>{{ approval.title }}</strong>
              <p>{{ approval.applicant }} / {{ approval.amount }} / {{ approval.status }}</p>
            </div>
            <div class="button-row">
              <button type="button" @click="router.push(`/work-center/approval/${approval.id}`)">审批</button>
              <button type="button" @click="router.push(`/work-center/approval/${approval.id}`)">驳回</button>
            </div>
          </article>
        </section>

        <section class="panel">
          <header>
            <h2>我的执行任务</h2>
            <span>{{ executionTasks.length }} 项</span>
          </header>
          <article v-for="task in executionTasks" :key="task.id" class="list-row">
            <div>
              <strong>{{ task.title }}</strong>
              <p>{{ task.process }} / {{ task.owner }} / {{ task.status }}</p>
            </div>
            <div class="button-row">
              <button type="button" @click="router.push(`/work-center/execution/${task.id}`)">查看</button>
              <button type="button" @click="router.push(`/work-center/execution/${task.id}`)">执行</button>
              <button type="button" @click="finishTask(task.id)">完成</button>
            </div>
          </article>
        </section>
      </section>

      <section class="panel">
        <header>
          <h2>我的流程</h2>
          <span>基于岗位的流程执行</span>
        </header>
        <div class="card-grid">
          <article v-for="workflow in state.workflows" :key="workflow.id" class="business-card">
            <span>{{ workflow.name }}</span>
            <strong>{{ workflow.currentStep }}</strong>
            <p>{{ workflow.progress }}</p>
            <div class="button-row">
              <button type="button" @click="router.push('/process-center')">查看流程</button>
              <button type="button" @click="createWorkflowTask(workflow)">处理任务</button>
            </div>
          </article>
        </div>
      </section>
    </section>

    <section
      v-else-if="currentPath === '/process-center'"
      class="operation-shell"
      data-acceptance-id="pce-business-process-center"
      data-page-version="V1.14.2.8.4.8.5.2"
      data-page-name="业务流程中心"
      data-page-module="Business Process Center"
      data-fact-source="ProcessCenterRuntime"
      data-runtime-code="ProcessCenterRuntime"
      data-runtime-model="ProcessCenterRuntimeModel"
      data-danger-action-count="0"
      data-detail-display-mode="process-node-track"
      data-master-data-maintenance="false"
      data-isolated-business-shortcut-count="0"
      data-navigation-hierarchy="module-process-node-page"
      data-acceptance-status="PASS"
    >
      <section class="panel primary-panel">
        <header>
          <div>
            <h2>业务流程中心</h2>
            <span>企业业务流程导航与页面质量状态</span>
          </div>
        </header>
        <p class="platform-note">本中心只显示企业业务流程；主数据维护、引用关系分析和产品能力架构分别由对应中心负责。</p>
        <section
          class="process-catalog"
          data-acceptance-id="business-process-center-v1"
          data-process-registry-version="V1.14.2.8.4.10.4"
          :data-process-count="enterpriseProcesses.length"
        >
          <header class="process-catalog-header">
            <div>
              <h3>企业业务流程目录</h3>
              <p>按业务模块查看流程、节点、页面版本与自动验收状态。</p>
            </div>
            <span class="registry-badge">统一流程 {{ enterpriseProcesses.length }} 个</span>
          </header>

          <nav class="process-module-navigation" aria-label="业务模块导航" data-acceptance-id="business-module-navigation">
            <button
              v-for="module in processCenterModules"
              :key="module.moduleCode"
              type="button"
              class="process-module-button"
              :class="{ active: selectedProcessModule === module.moduleCode }"
              :data-process-module="module.moduleCode"
              @click="selectProcessModule(module.moduleCode)"
            >
              <strong>{{ module.moduleCode }}</strong>
              <span>{{ module.moduleName }}</span>
            </button>
          </nav>

          <section
            v-if="selectedFormalProcess"
            class="scm-purchase-process"
            data-acceptance-id="selected-module-formal-process"
            data-process-visual-contract="PROCESS-VISUAL-001"
            :data-process-module="selectedProcessModule"
            :data-process-code="selectedFormalProcess.processCode"
            :data-formal-root-count="selectedModuleProcesses.length"
          >
            <header>
              <div>
                <h3>{{ selectedFormalProcess.processName }}</h3>
                <p><strong>{{ selectedModuleName }}</strong></p>
                <p>共 {{ selectedFormalProcessNodes.length }} 个节点，已挂接 {{ selectedBoundPageCount }} 个业务页面。</p>
              </div>
              <span class="registry-badge success">{{ selectedFormalProcess.processCode === 'MES_TEST_PRODUCTION_EXECUTION' ? '按正式与TEST原生来源分别核验 · 待人工验收' : '唯一正式流程' }}</span>
            </header>
            <div
              class="process-node-track"
              data-process-layout="card-flow"
              data-horizontal-scroll-owner="process-region"
            >
              <template v-for="(node, index) in selectedFormalProcessNodes" :key="node.nodeCode">
                <ProcessNodeNavigation
                  :node="node"
                  :selected="selectedProcessNode?.nodeCode === node.nodeCode"
                  @inspect="inspectProcessNode"
                  @opened="handleProcessNodeOpened"
                />
                <span v-if="index < selectedFormalProcessNodes.length - 1" class="process-arrow" aria-hidden="true">→</span>
              </template>
            </div>
            <p v-if="selectedProcessModule === 'PDE' && pdeScmRelationship" class="platform-note">
              {{ pdeScmRelationship.businessChain.join(' → ') }}
            </p>
          </section>

          <section v-else class="process-module-empty" data-acceptance-id="module-formal-process-empty">
            <strong>{{ selectedProcessModule }}</strong>
            <p>本模块尚未配置正式运作流程</p>
          </section>

          <aside
            v-if="selectedProcessNode"
            class="process-node-inspector"
            data-acceptance-id="process-node-inspector"
          >
            <div>
              <span>当前查看节点</span>
              <strong>{{ selectedProcessNode.nodeName }}</strong>
            </div>
            <dl>
              <div><dt>模块</dt><dd>{{ selectedProcessNode.moduleCode }}</dd></div>
              <div><dt>页面编码</dt><dd>{{ selectedProcessNode.pageCode }}</dd></div>
              <div><dt>页面地址</dt><dd>{{ selectedProcessNode.pageRoute || selectedProcessNode.pageUrl }}</dd></div>
              <div><dt>状态说明</dt><dd>{{ selectedProcessNode.statusDescription }}</dd></div>
              <div><dt>导航方式</dt><dd>新标签打开，流程中心保持</dd></div>
            </dl>
          </aside>
        </section>
      </section>
    </section>

    <section v-else-if="currentPath === '/organization'" class="operation-shell">
      <section class="panel primary-panel">
        <header>
          <div>
            <h2>组织结构</h2>
            <span>{{ state.company.name }}</span>
          </div>
          <button type="button" @click="saveCompany">保存公司信息</button>
        </header>
        <div class="org-summary">
          <label>公司<input v-model="companyForm.name" /></label>
          <label>法人主体<input v-model="companyForm.legalEntity" /></label>
          <label>业务单元<input v-model="companyForm.businessUnit" /></label>
          <article>
            <span>流程责任人</span>
            <strong>{{ state.departments.length }} 个部门已绑定流程</strong>
            <p>角色权限 / 流程责任人在此处维护。</p>
          </article>
        </div>
      </section>

      <section class="three-column">
        <EditableList
          title="部门"
          add-label="新增部门"
          edit-label="编辑部门"
          delete-label="删除部门"
          :items="state.departments"
          :fields="departmentFields"
          @add="startCreate('department')"
          @edit="router.push(`/organization/department/${$event.id}`)"
          @delete="removeItem('department', $event)"
        />
        <EditableList
          title="岗位"
          add-label="新增岗位"
          edit-label="编辑岗位"
          delete-label="删除岗位"
          :items="state.roles"
          :fields="roleFields"
          @add="startCreate('role')"
          @edit="router.push(`/organization/role/${$event.id}`)"
          @delete="removeItem('role', $event)"
        />
        <EditableList
          title="人员"
          add-label="新增人员"
          edit-label="编辑人员"
          delete-label="删除人员"
          :items="state.users"
          :fields="userFields"
          @add="startCreate('user')"
          @edit="router.push(`/organization/user/${$event.id}`)"
          @delete="removeItem('user', $event)"
        />
      </section>

      <section class="panel">
        <header>
          <h2>权限配置</h2>
          <button type="button" @click="startCreate('permission')">配置权限</button>
        </header>
        <article v-for="permission in state.permissions" :key="permission.id" class="list-row">
          <div>
            <strong>{{ permission.name }}</strong>
            <p>{{ permission.role }} / {{ permission.scope }}</p>
          </div>
          <div class="button-row">
            <button type="button" @click="router.push(`/organization/permission/${permission.id}`)">编辑权限</button>
            <button type="button" @click="removeItem('permission', permission)">删除权限</button>
          </div>
        </article>
      </section>

      <section v-if="entityFormOpen" class="panel editor-panel">
        <header>
          <h2>{{ entityFormTitle }}</h2>
          <button type="button" @click="closeForms">取消</button>
        </header>
        <div class="form-grid">
          <label v-for="field in activeFields" :key="field.key">
            {{ field.label }}
            <input v-model="entityForm[field.key]" :type="field.type || 'text'" />
          </label>
        </div>
        <button type="button" @click="saveEntity">保存</button>
      </section>
    </section>

    <section v-else-if="currentPath === '/dashboard' || currentPath === '/analytics'" class="operation-shell">
      <section class="panel primary-panel">
        <header>
          <h2>{{ currentPath === '/dashboard' ? '仪表盘' : '分析中心' }}</h2>
          <span>指标与分析只在此处展示</span>
        </header>
        <div class="metric-grid">
          <article>
            <span>企业健康度</span>
            <strong>{{ model.dashboard.kpis.health }}/100</strong>
            <p>系统健康指标属于仪表盘和分析中心。</p>
          </article>
          <article>
            <span>利润</span>
            <strong>{{ model.dashboard.kpis.profit }}</strong>
            <p>经营指标总览。</p>
          </article>
          <article>
            <span>成本</span>
            <strong>{{ model.dashboard.kpis.cost }}</strong>
            <p>成本与产能分析。</p>
          </article>
          <article>
            <span>风险状态</span>
            <strong>{{ model.dashboard.kpis.riskIndex }}</strong>
            <p>风险指标不进入操作页主区域。</p>
          </article>
        </div>
      </section>
    </section>

    <section v-if="currentPath === '/analytics'" class="operation-shell">
      <section class="panel primary-panel">
        <header>
          <div>
            <h2>企业数据智能分析平台</h2>
            <span>用于业务链追踪、数据一致性验证、风险闭环和后续经营分析。</span>
          </div>
        </header>
        <p class="platform-relation-note">业务链追踪 → 数据一致性验证 → 风险闭环处理，当前 P2P 验证与闭环在同一页面完成。</p>
        <p class="platform-relation-note">当前平台已进入数据健康评分模型设计阶段，评分仅用于管理分析，不作为正式 KPI。</p>
        <p class="platform-relation-note">企业数据智能分析平台是平台级管理辅助能力；财务执行页面保留在 Finance / ERP 导航中，不作为分析中心主入口。</p>
        <div class="metric-grid">
          <article>
            <span>企业业务追踪中心</span>
            <strong>业务链追踪</strong>
            <p>从请购、采购订单、收货、检验、库存、应付、付款等业务节点追踪完整业务链。</p>
            <button type="button" @click="router.push('/business-trace')">进入业务追踪中心</button>
          </article>
          <article>
            <span>P2P业务数据验证与闭环中心</span>
            <strong>只读验证 + 风险闭环</strong>
            <p>检查 P2P 业务链数据是否完整，发现数据断点、一致性问题和金额核对问题；风险确认、处理、解决、关闭和历史追踪均在本中心内完成。</p>
            <button type="button" @click="router.push('/finance/p2p-validation-center')">进入验证与闭环中心</button>
          </article>
        </div>
      </section>
    </section>

    <section v-else-if="currentPath === '/admin'" class="operation-shell">
      <section class="panel primary-panel">
        <header>
          <div>
            <h2>系统配置</h2>
            <span>角色权限、菜单配置、流程模板、租户参数</span>
          </div>
          <button type="button" @click="saveAdminConfig">保存配置</button>
        </header>
        <div class="metric-grid">
          <article>
            <span>企业操作系统模式</span>
            <strong>{{ statusLabel(state.config.enterpriseOSMode) }}</strong>
            <p>系统配置在此处管理。</p>
          </article>
          <article>
            <span>模块界面</span>
            <strong>{{ statusLabel(state.config.moduleUI) }}</strong>
            <p>旧模块已作为流程节点管理。</p>
          </article>
          <article>
            <span>流程界面</span>
            <select v-model="adminForm.processUI">
              <option value="ACTIVE">已启用</option>
              <option value="DISABLED">已停用</option>
            </select>
            <p>企业业务从业务流程中心开始。</p>
          </article>
          <article>
            <span>组织界面</span>
            <select v-model="adminForm.organizationUI">
              <option value="ACTIVE">已启用</option>
              <option value="DISABLED">已停用</option>
            </select>
            <p>角色、用户和权限在此处管理。</p>
          </article>
          <article>
            <span>默认入口</span>
            <select v-model="adminForm.defaultEntry">
              <option value="/process-center">业务流程中心</option>
              <option value="/work-center">个人工作台</option>
              <option value="/organization">组织结构</option>
              <option value="/dashboard">仪表盘</option>
            </select>
            <p>配置企业用户进入系统后的默认页面。</p>
          </article>
          <article>
            <span>角色权限</span>
            <input v-model="adminForm.rolePermissionMode" />
            <button type="button" @click="router.push('/admin/role-permission')">进入配置</button>
          </article>
          <article>
            <span>菜单配置</span>
            <strong>已启用</strong>
            <button type="button" @click="router.push('/admin/config/menu')">进入配置</button>
          </article>
          <article>
            <span>流程模板</span>
            <strong>{{ state.processes.length }} 个</strong>
            <button type="button" @click="router.push('/admin/process-template')">进入配置</button>
          </article>
          <article>
            <span>租户参数</span>
            <strong>已保存</strong>
            <button type="button" @click="router.push('/admin/tenant-setting')">进入配置</button>
          </article>
          <article data-system-config-module="enterprise-foundation">
            <span>企业基础资料</span>
            <strong>正式维护与人工验收</strong>
            <p>保留原系统配置模块，在原页面内增加企业基础资料入口。</p>
            <button type="button" @click="router.push('/foundation')">进入企业基础资料</button>
          </article>
        </div>
      </section>
    </section>
  </main>
</template>

<script setup>
import { computed, defineComponent, h, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ProcessNodeNavigation from '../components/ProcessNodeNavigation.vue'
import { getEnterpriseOSModel } from '../enterprise-os/enterpriseOSModel.js'
import {
  addDepartment,
  addPermission,
  addRole,
  addTask,
  addUser,
  approveTask,
  completeTask,
  deleteDepartment,
  deletePermission,
  deleteRole,
  deleteUser,
  getApprovalById,
  getDepartmentById,
  getEnterpriseOperationState,
  getExecutionTaskById,
  getPermissionById,
  getRoleById,
  getTaskById,
  getUserById,
  rejectTask,
  updateApproval,
  updateCompany,
  updateConfig,
  updateDepartment,
  updatePermission,
  updateRole,
  updateTask,
  updateUser,
} from '../enterprise-os/enterpriseOperationStore.js'
import { translate } from '../runtime/i18nEngine.js'
import { loadProcessCenterRuntimeModel } from '../runtime/processCenterRuntime.js'

const processCenterRuntimeModel = loadProcessCenterRuntimeModel()
const processCenterModules = processCenterRuntimeModel.modules
const enterpriseProcesses = processCenterRuntimeModel.processes
const pdeScmRelationship = processCenterRuntimeModel.relationships[0]

const EditableList = defineComponent({
  props: {
    title: { type: String, required: true },
    addLabel: { type: String, required: true },
    editLabel: { type: String, required: true },
    deleteLabel: { type: String, required: true },
    items: { type: Array, required: true },
    fields: { type: Array, required: true },
  },
  emits: ['add', 'edit', 'delete'],
  setup(props, { emit }) {
    return () => h('section', { class: 'panel' }, [
      h('header', [
        h('h2', props.title),
        h('button', { type: 'button', onClick: () => emit('add') }, props.addLabel),
      ]),
      ...props.items.map((item) => h('article', { class: 'list-row', key: item.id }, [
        h('div', [
          h('strong', item.name),
          h('p', props.fields
            .filter((field) => field.key !== 'name')
            .map((field) => item[field.key])
            .filter(Boolean)
            .join(' / ')),
        ]),
        h('div', { class: 'button-row' }, [
          h('button', { type: 'button', onClick: () => emit('edit', item) }, props.editLabel),
          h('button', { type: 'button', onClick: () => emit('delete', item) }, props.deleteLabel),
        ]),
      ])),
    ])
  },
})

const route = useRoute()
const router = useRouter()
const canonicalProcessModuleCode = (value) => {
  const normalized = String(value || '').trim().toUpperCase()
  return processCenterModules.find(module => module.moduleCode.toUpperCase() === normalized)?.moduleCode || ''
}
const requestedProcessModule = canonicalProcessModuleCode(route.query.module)
const selectedProcessModule = ref(
  requestedProcessModule || 'SCM',
)
function selectProcessModule(moduleCode) {
  const canonical = canonicalProcessModuleCode(moduleCode)
  if (!canonical) return
  selectedProcessModule.value = canonical
  selectedProcessNode.value = null
  if (route.path.startsWith('/process-center') && route.query.module !== canonical) {
    router.push({
      path: '/process-center',
      query: { ...route.query, module: canonical },
    })
  }
}
watch(
  () => route.query.module,
  (moduleCode) => {
    const canonical = canonicalProcessModuleCode(moduleCode) || 'SCM'
    if (selectedProcessModule.value !== canonical) {
      selectedProcessModule.value = canonical
      selectedProcessNode.value = null
    }
  },
)
const selectedModuleProcesses = computed(() => (
  enterpriseProcesses.filter(process => process.moduleCode === selectedProcessModule.value)
))
const selectedFormalProcess = computed(() => selectedModuleProcesses.value[0] || null)
const selectedFormalProcessNodes = computed(() => selectedFormalProcess.value?.nodes || [])
const selectedBoundPageCount = computed(() => selectedFormalProcessNodes.value.filter(node => node.pageUrl).length)
const selectedModuleName = computed(() => (
  processCenterModules.find(module => module.moduleCode === selectedProcessModule.value)?.moduleName
  || selectedFormalProcess.value?.moduleName
  || selectedProcessModule.value
))
const model = computed(() => getEnterpriseOSModel())
const state = ref(getEnterpriseOperationState())
const message = ref('')
const selectedProcessNode = ref(null)

function inspectProcessNode(node) {
  selectedProcessNode.value = node
  message.value = `${node.nodeName}节点信息已显示；流程中心保持打开。`
}

function handleProcessNodeOpened(result) {
  if (result.opened) {
    message.value = result.target === '_self' ? `${result.node.nodeName}已在当前标签页打开。` : `${result.node.nodeName}已在新标签打开；流程中心保持打开。`
    return
  }
  message.value = `${result.node.nodeName}新标签打开失败，请检查浏览器弹窗权限。`
}

const pageMap = {
  '/dashboard': '仪表盘',
  '/organization': '组织结构',
  '/process-center': '业务流程中心',
  '/work-center': '个人工作台',
  '/analytics': '分析中心',
  '/admin': '系统配置',
}
const currentPath = computed(() => {
  if (route.path.startsWith('/work-center')) return '/work-center'
  if (route.path.startsWith('/process-center')) return '/process-center'
  if (route.path.startsWith('/organization')) return '/organization'
  if (route.path.startsWith('/admin')) return '/admin'
  if (route.path === '/dashboard') return '/dashboard'
  if (route.path === '/analytics') return '/analytics'
  return '/process-center'
})
const currentTitle = computed(() => actionTitle.value || pageMap[currentPath.value] || '业务流程中心')
function isEnterpriseNavActive(path) {
  if (path === '/admin') return currentPath.value === '/admin'
  return currentPath.value === path
}
const isActionPage = computed(() => !Object.keys(pageMap).includes(route.path))
const adminActionPage = computed(() => route.path.startsWith('/admin/') && route.path !== '/admin')
const organizationActionType = computed(() => {
  if (route.path.startsWith('/organization/department/')) return 'department'
  if (route.path.startsWith('/organization/role/')) return 'role'
  if (route.path.startsWith('/organization/user/')) return 'user'
  if (route.path.startsWith('/organization/permission/')) return 'permission'
  return ''
})
const pendingTasks = computed(() => state.value.tasks.filter((task) => task.type === 'pending' && !task.completed))
const executionTasks = computed(() => state.value.tasks.filter((task) => task.type === 'execution' && !task.completed))
const selectedTask = computed(() => getTaskById(route.params.id))
const selectedApproval = computed(() => getApprovalById(route.params.id))
const selectedExecutionTask = computed(() => getExecutionTaskById(route.params.id))
const workTaskPage = computed(() => route.name === 'WorkTaskAction')
const approvalPage = computed(() => route.name === 'ApprovalAction')
const executionPage = computed(() => route.name === 'ExecutionAction')

const departmentFields = [
  { key: 'name', label: '部门名称' },
  { key: 'parent', label: '上级部门' },
  { key: 'owner', label: '负责人' },
  { key: 'people', label: '人数', type: 'number' },
  { key: 'processOwner', label: '流程责任' },
]
const roleFields = [
  { key: 'name', label: '岗位名称' },
  { key: 'department', label: '所属部门' },
  { key: 'responsibility', label: '岗位职责' },
]
const userFields = [
  { key: 'name', label: '姓名' },
  { key: 'department', label: '部门' },
  { key: 'role', label: '岗位' },
  { key: 'status', label: '状态' },
]
const permissionFields = [
  { key: 'name', label: '角色' },
  { key: 'role', label: '可访问页面' },
  { key: 'scope', label: '可执行动作' },
]
const entityMap = {
  department: {
    title: '部门',
    fields: departmentFields,
    defaults: { name: '新部门', parent: '总部', owner: '负责人', people: 1, processOwner: '流程责任人' },
    add: addDepartment,
    update: updateDepartment,
    delete: deleteDepartment,
    get: getDepartmentById,
  },
  role: {
    title: '岗位',
    fields: roleFields,
    defaults: { name: '新岗位', department: '部门', responsibility: '岗位职责' },
    add: addRole,
    update: updateRole,
    delete: deleteRole,
    get: getRoleById,
  },
  user: {
    title: '人员',
    fields: userFields,
    defaults: { name: '新人员', department: '部门', role: '岗位', status: '在职' },
    add: addUser,
    update: updateUser,
    delete: deleteUser,
    get: getUserById,
  },
  permission: {
    title: '权限',
    fields: permissionFields,
    defaults: { name: '新权限', role: '业务流程中心', scope: '查看 / 编辑 / 保存' },
    add: addPermission,
    update: updatePermission,
    delete: deletePermission,
    get: getPermissionById,
  },
}

const companyForm = reactive({})
const adminForm = reactive({})
const entityForm = reactive({})
const taskForm = reactive({ opinion: '' })
const approvalForm = reactive({ opinion: '' })
const executionForm = reactive({ result: '' })
const organizationForm = reactive({})
const adminActionForm = reactive({})
const entityFormOpen = ref(false)
const editingEntity = ref({ type: '', id: '' })

const activeFields = computed(() => entityMap[editingEntity.value.type]?.fields || [])
const entityFormTitle = computed(() => {
  const name = entityMap[editingEntity.value.type]?.title || '项目'
  return editingEntity.value.id ? `编辑${name}` : `新增${name}`
})
const organizationFields = computed(() => entityMap[organizationActionType.value]?.fields || [])
const actionTitle = computed(() => {
  const titleMap = {
    WorkTaskAction: '任务处理页',
    ApprovalAction: '审批处理页',
    ExecutionAction: '执行任务页',
    AdminRolePermission: '角色权限配置',
    AdminProcessTemplate: '流程模板配置',
    AdminTenantSetting: '租户参数配置',
    AdminConfig: '系统配置页',
  }
  if (organizationActionType.value) return `${entityMap[organizationActionType.value].title}编辑表单`
  return titleMap[route.name] || ''
})
const actionSubtitle = computed(() => {
  if (route.path.startsWith('/work-center')) return '个人工作台操作闭环'
  if (route.path.startsWith('/process-center')) return '业务流程操作闭环'
  if (route.path.startsWith('/organization')) return '组织结构操作闭环'
  if (route.path.startsWith('/admin')) return '系统配置操作闭环'
  return ''
})
const backLabel = computed(() => {
  if (route.path.startsWith('/work-center')) return '返回个人工作台'
  if (route.path.startsWith('/process-center')) return '返回流程中心'
  if (route.path.startsWith('/organization')) return '返回组织结构'
  return '返回系统配置'
})

function t(key) {
  return translate(key)
}

function refresh() {
  state.value = getEnterpriseOperationState()
  resetObject(companyForm, state.value.company)
  resetObject(adminForm, state.value.config)
}

function notify(text) {
  message.value = text
  window.setTimeout(() => {
    message.value = ''
  }, 1800)
}

function resetObject(target, source = {}) {
  Object.keys(target).forEach((key) => delete target[key])
  Object.assign(target, source)
}

function statusLabel(value) {
  return ({
    ACTIVE: '已启用',
    DISABLED: '已禁用',
    ON: '已开启',
    OFF: '已关闭',
  })[value] || value
}

function goBack() {
  if (route.path.startsWith('/work-center')) router.push('/work-center')
  else if (route.path.startsWith('/process-center')) router.push('/process-center')
  else if (route.path.startsWith('/organization')) router.push('/organization')
  else router.push('/admin')
}

function closeForms() {
  entityFormOpen.value = false
  editingEntity.value = { type: '', id: '' }
}

function startCreate(type) {
  closeForms()
  editingEntity.value = { type, id: '' }
  resetObject(entityForm, entityMap[type].defaults)
  entityFormOpen.value = true
}

function saveEntity() {
  const config = entityMap[editingEntity.value.type]
  if (!config) return

  if (editingEntity.value.id) {
    config.update(editingEntity.value.id, { ...entityForm })
    notify(`${config.title}已保存`)
  } else {
    config.add({ ...entityForm })
    notify(`${config.title}已新增`)
  }

  closeForms()
  refresh()
}

function removeItem(type, item) {
  entityMap[type].delete(item.id ? item.id : item)
  notify(`${entityMap[type].title}已删除`)
  refresh()
}

function saveCompany() {
  updateCompany({ ...companyForm })
  refresh()
  notify('公司信息已保存')
}

function finishTask(id) {
  completeTask(id, '列表快速完成')
  refresh()
  notify('任务已完成')
}

function saveTask() {
  updateTask(route.params.id, { opinion: taskForm.opinion, status: '处理中' })
  refresh()
  notify('任务已保存')
  goBack()
}

function finishTaskAction() {
  completeTask(route.params.id, taskForm.opinion || '处理完成')
  refresh()
  notify('任务已完成')
  goBack()
}

function approveCurrentApproval() {
  updateApproval(route.params.id, { status: '已审批', opinion: approvalForm.opinion })
  approveTask(route.params.id, approvalForm.opinion)
  refresh()
  notify('审批通过')
  goBack()
}

function rejectCurrentApproval() {
  updateApproval(route.params.id, { status: '已驳回', opinion: approvalForm.opinion })
  rejectTask(route.params.id, approvalForm.opinion)
  refresh()
  notify('已驳回')
  goBack()
}

function finishExecution() {
  completeTask(route.params.id, executionForm.result || '执行完成')
  refresh()
  notify('执行已完成')
  goBack()
}

function saveOrganizationAction() {
  const config = entityMap[organizationActionType.value]
  if (!config) return
  config.update(route.params.id, { ...organizationForm })
  refresh()
  notify(`${config.title}已保存`)
  goBack()
}

function saveAdminAction() {
  updateConfig({
    [`admin.${route.name || route.params.key}`]: { ...adminActionForm },
  })
  refresh()
  notify('配置已保存')
  goBack()
}

function saveAdminConfig() {
  updateConfig({ ...adminForm })
  refresh()
  notify('系统配置已保存')
}

function createQuickActionTask(name) {
  addTask({
    title: name,
    process: name.replace('新建', ''),
    owner: '当前岗位',
    status: '待处理',
    type: 'pending',
  })
  refresh()
  notify(`${name}已创建`)
}

function createWorkflowTask(workflow) {
  addTask({
    title: `处理${workflow.name}`,
    process: workflow.name,
    owner: '当前岗位',
    status: '待处理',
    type: 'pending',
  })
  refresh()
  notify('流程任务已创建')
}

function syncActionForms() {
  resetObject(taskForm, { opinion: selectedTask.value?.opinion || '' })
  resetObject(approvalForm, { opinion: selectedApproval.value?.opinion || '' })
  resetObject(executionForm, { result: selectedExecutionTask.value?.result || '' })
  const orgConfig = entityMap[organizationActionType.value]
  resetObject(organizationForm, orgConfig?.get(route.params.id) || orgConfig?.defaults || {})
  resetObject(adminActionForm, {
    name: actionTitle.value || '系统配置',
    value: route.params.key || route.name || '',
    remark: '',
  })
}

watch(() => route.fullPath, () => {
  refresh()
  syncActionForms()
}, { immediate: true })
</script>

<style scoped>
.enterprise-os-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
  padding: 22px;
  background: #f4f7fb;
  color: #172033;
}

.page-header,
.panel header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page-header {
  flex-wrap: wrap;
}

.eyebrow {
  margin: 0 0 4px;
  color: #64748b;
  font-size: 13px;
}

h1,
h2,
h3 {
  margin: 0;
}

h1 {
  font-size: 28px;
}

h2 {
  font-size: 18px;
}

h3 {
  font-size: 16px;
}

.page-tabs,
.button-row,
.action-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.page-tabs a,
button {
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  padding: 7px 12px;
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
}

button {
  border-color: #0f766e;
  background: #f0fdfa;
  color: #0f766e;
}

input,
select,
textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 8px 10px;
  background: #fff;
  color: #172033;
}

textarea {
  min-height: 96px;
  resize: vertical;
}

label {
  display: grid;
  gap: 6px;
  color: #334155;
  font-weight: 700;
}

.notice {
  border: 1px solid #99f6e4;
  border-radius: 8px;
  padding: 10px 12px;
  background: #f0fdfa;
  color: #0f766e;
  font-weight: 700;
}

.platform-note {
  margin-bottom: 14px;
  color: #475467;
  line-height: 1.6;
}

.process-catalog {
  box-sizing: border-box;
  display: grid;
  gap: 16px;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  margin: 0 0 20px;
  padding: 18px;
  border: 1px solid #c7d7fe;
  border-radius: 12px;
  background:
    linear-gradient(135deg, rgb(239 246 255 / 92%), rgb(255 255 255 / 98%) 58%),
    #fff;
}

.process-catalog-header,
.scm-purchase-process > header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.page-header > section {
  flex: 1 1 180px;
  min-width: 0;
}

.page-header > section h1 {
  white-space: normal;
  overflow-wrap: anywhere;
}

.page-header > .page-tabs {
  flex: 1 1 auto;
  min-width: 0;
  justify-content: flex-start;
}

.process-catalog h3 {
  margin: 0;
  color: #172554;
}

.registry-badge {
  flex: 0 0 auto;
  padding: 5px 9px;
  border: 1px solid #93c5fd;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.registry-badge.success {
  border-color: #86efac;
  background: #f0fdf4;
  color: #15803d;
}

.process-module-navigation {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
  gap: 8px;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  overflow-x: hidden;
  padding-bottom: 6px;
}

.process-module-button {
  display: grid;
  min-height: 66px;
  padding: 9px 10px;
  border: 1px solid #dbeafe;
  border-radius: 9px;
  background: #fff;
  color: #334155;
  text-align: left;
}

.process-module-button strong {
  color: #1e3a8a;
  font-size: 14px;
}

.process-module-button span {
  font-size: 12px;
}

.process-module-button.active {
  border-color: #2563eb;
  background: #dbeafe;
  box-shadow: inset 0 0 0 1px #2563eb;
}

.scm-purchase-process {
  box-sizing: border-box;
  display: grid;
  gap: 14px;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  overflow-x: hidden;
  padding: 16px;
  border: 1px solid #bfdbfe;
  border-radius: 10px;
  background: #fff;
}

.process-node-track {
  box-sizing: border-box;
  display: flex;
  align-items: stretch;
  gap: 8px;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  overscroll-behavior-inline: contain;
  padding: 3px 3px 12px;
  scrollbar-gutter: stable;
}

.pde-primary-entry {
  display: flex;
  padding: 14px;
  border: 1px solid #93c5fd;
  border-radius: 10px;
  background: linear-gradient(135deg, #eff6ff, #f8fbff);
}

.process-arrow {
  display: grid;
  flex: 0 0 20px;
  place-items: center;
  color: #2563eb;
  font-size: 20px;
  font-weight: 800;
}

.process-node-inspector {
  display: grid;
  gap: 12px;
  padding: 14px;
  border: 1px solid #93c5fd;
  border-radius: 10px;
  background: #f8fbff;
}

.process-node-inspector > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.process-node-inspector span,
.process-node-inspector dt {
  color: #64748b;
  font-size: 12px;
}

.process-node-inspector dl {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin: 0;
}

.process-node-inspector dl > div {
  display: grid;
  gap: 4px;
  padding: 8px;
  border-radius: 7px;
  background: #fff;
}

.process-node-inspector dd {
  margin: 0;
  color: #0f172a;
  font-size: 12px;
  overflow-wrap: anywhere;
}

@media (max-width: 900px) {
  .process-node-inspector dl {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.process-module-empty {
  padding: 18px;
  border: 1px dashed #cbd5e1;
  border-radius: 9px;
  background: #fff;
}

.operation-shell,
.detail-layout {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
  max-width: 100%;
  overflow-x: hidden;
}

.panel {
  border: 1px solid #dce5f2;
  border-radius: 8px;
  background: #fff;
  padding: 16px;
}

.primary-panel {
  border-color: #bfdbfe;
  min-width: 0;
  max-width: 100%;
  overflow-x: hidden;
}

.panel header {
  margin-bottom: 14px;
}

.panel header span,
.business-card span,
.task-table span,
.metric-grid span,
.org-summary span {
  color: #64748b;
  font-size: 12px;
}

.card-grid,
.process-grid,
.metric-grid,
.org-summary,
.form-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.two-column {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.three-column {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.task-table {
  display: grid;
  gap: 10px;
}

.task-table article,
.business-card,
.metric-grid article,
.org-summary article,
.list-row,
.info-box {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  padding: 12px;
}

.task-table article {
  display: grid;
  grid-template-columns: 1.3fr 1fr 1fr 0.7fr 1.5fr;
  align-items: center;
  gap: 10px;
}

.business-card,
.metric-grid article,
.org-summary article {
  min-height: 128px;
}

.list-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.editor-panel {
  border-color: #0f766e;
}

strong {
  display: block;
  color: #101828;
  font-size: 17px;
}

p {
  margin: 8px 0 0;
  color: #475467;
  font-size: 13px;
  line-height: 1.5;
}

@media (max-width: 1100px) {
  .process-module-navigation {
    grid-template-columns: repeat(4, minmax(120px, 1fr));
  }

  .card-grid,
  .process-grid,
  .metric-grid,
  .org-summary,
  .form-grid,
  .two-column,
  .three-column {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .task-table article {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .page-header,
  .panel header,
  .list-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .card-grid,
  .process-grid,
  .metric-grid,
  .org-summary,
  .form-grid,
  .two-column,
  .three-column {
    grid-template-columns: 1fr;
  }

  .process-module-navigation {
    grid-template-columns: repeat(2, minmax(120px, 1fr));
  }

  .process-catalog-header,
  .scm-purchase-process > header {
    flex-direction: column;
  }
}
</style>

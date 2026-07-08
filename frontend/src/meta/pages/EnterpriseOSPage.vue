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
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': isEnterpriseNavActive('/work-center') }" to="/work-center">
          {{ t('Work Center') }}
          <span v-if="isEnterpriseNavActive('/work-center')" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': isEnterpriseNavActive('/process-center') }" to="/process-center">
          {{ t('Process Center') }}
          <span v-if="isEnterpriseNavActive('/process-center')" class="app-current-tag">当前</span>
        </router-link>
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
        <router-link class="app-nav-button" to="/manufacturing/modules">制造业13大核心模块</router-link>
        <router-link class="app-nav-button" to="/foundation">第一期基础资料</router-link>
        <router-link class="app-nav-button" to="/foundation/business-partners">业务伙伴档案</router-link>
        <router-link class="app-nav-button" to="/reference">数据引用中心</router-link>
        <router-link class="app-nav-button" to="/scm">SCM采购管理</router-link>
        <router-link class="app-nav-button" to="/wms">WMS库存管理</router-link>
        <router-link class="app-nav-button" to="/qms">QMS来料检验</router-link>
        <router-link class="app-nav-button" to="/finance/payable-prepares">采购应付预备</router-link>
        <router-link class="app-nav-button" to="/finance/payable-checks">采购应付核对</router-link>
        <router-link class="app-nav-button" to="/finance/invoice-prepares">采购发票预备</router-link>
        <router-link class="app-nav-button" to="/finance/ap-drafts">采购应付账款草稿</router-link>
        <router-link class="app-nav-button" to="/finance/payment-drafts">供应商付款草稿</router-link>
        <router-link class="app-nav-button" to="/finance/payment-prepares">正式付款单预备</router-link>
        <router-link class="app-nav-button" to="/finance/payment-order-drafts">正式付款单草稿</router-link>
        <router-link class="app-nav-button" to="/finance/payment-risk-reviews">真实付款风险评审</router-link>
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

        <div v-else-if="route.name === 'ProcessDetail'" class="detail-layout">
          <section class="info-box">
            <h3>流程信息</h3>
            <p>流程详情：{{ selectedProcess?.name || '流程不存在' }}</p>
            <p>流程步骤：提交 / 审批 / 执行 / 完成</p>
            <p>当前状态：{{ selectedProcess?.status || '-' }}</p>
            <p>负责人：{{ selectedProcess?.owner || '-' }}</p>
            <p>关联任务：{{ relatedTasks.length }} 项</p>
          </section>
          <div class="button-row">
            <button type="button" @click="router.push(`/process-center/process/${route.params.id}/create`)">新建业务单</button>
            <button type="button" @click="router.push(`/process-center/process/${route.params.id}/edit`)">编辑流程</button>
            <button type="button" @click="router.push(`/process-center/process/${route.params.id}/execute`)">执行流程</button>
            <button type="button" @click="goBack">返回流程中心</button>
          </div>
        </div>

        <div v-else-if="route.name === 'ProcessCreate'" class="detail-layout">
          <section class="info-box">
            <h3>新建业务单表单</h3>
            <p>所属流程：{{ selectedProcess?.name || route.params.id }}</p>
          </section>
          <div class="form-grid">
            <label>名称<input v-model="businessForm.name" /></label>
            <label>类型<input v-model="businessForm.type" /></label>
            <label>负责人<input v-model="businessForm.owner" /></label>
            <label>计划日期<input v-model="businessForm.planDate" type="date" /></label>
            <label>备注<textarea v-model="businessForm.remark" /></label>
          </div>
          <div class="button-row">
            <button type="button" @click="saveBusinessRecord">保存</button>
            <button type="button" @click="goBack">取消</button>
          </div>
        </div>

        <div v-else-if="route.name === 'ProcessEdit'" class="detail-layout">
          <section class="info-box">
            <h3>编辑流程表单</h3>
            <p>流程信息保存后返回业务流程中心。</p>
          </section>
          <div class="form-grid">
            <label>流程名称<input v-model="processForm.name" /></label>
            <label>所属分类<select v-model="processForm.category">
              <option v-for="group in processGroups" :key="group.key" :value="group.key">{{ group.title }}</option>
            </select></label>
            <label>负责人岗位<input v-model="processForm.owner" /></label>
            <label>当前状态<input v-model="processForm.status" /></label>
            <label>待处理数量<input v-model.number="processForm.pending" type="number" min="0" /></label>
          </div>
          <div class="button-row">
            <button type="button" @click="saveProcessEdit">保存</button>
            <button type="button" @click="goBack">取消</button>
          </div>
        </div>

        <div v-else-if="route.name === 'ProcessExecute'" class="detail-layout">
          <section class="info-box">
            <h3>流程执行页面</h3>
            <p>流程：{{ selectedProcess?.name || route.params.id }}</p>
            <p>当前状态：{{ selectedProcess?.status || '-' }}</p>
          </section>
          <label>执行动作<input v-model="processExecuteForm.action" /></label>
          <label>执行结果<textarea v-model="processExecuteForm.result" /></label>
          <div class="button-row">
            <button type="button" @click="confirmProcessExecution">确认执行</button>
            <button type="button" @click="goBack">返回流程中心</button>
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

    <section v-else-if="currentPath === '/process-center'" class="operation-shell">
      <section class="panel primary-panel">
        <header>
          <div>
            <h2>业务流程中心</h2>
            <span>操作优先</span>
          </div>
          <div class="button-row">
            <button type="button" @click="router.push('/manufacturing/modules')">掌云智造模块蓝图</button>
            <button type="button" @click="router.push('/foundation')">第一期基础资料</button>
            <button type="button" @click="router.push('/foundation/business-partners')">业务伙伴档案</button>
            <button type="button" @click="router.push('/foundation/suppliers')">供应商档案</button>
            <button type="button" @click="router.push('/foundation/company-bank-accounts')">企业银行账户</button>
            <button type="button" @click="router.push('/foundation/sample-data')">样例数据管理</button>
            <button type="button" @click="router.push('/foundation/erp/supplier-material-prices')">供应商物料价格</button>
            <button type="button" @click="router.push('/foundation/erp/material-suppliers')">物料供应商关系</button>
            <button type="button" @click="router.push('/foundation/manufacturing/processes')">工序资料</button>
            <button type="button" @click="router.push('/foundation/manufacturing/routings')">工艺路线</button>
            <button type="button" @click="router.push('/foundation/manufacturing/equipment')">设备资料</button>
            <button type="button" @click="router.push('/foundation/pfm/employees')">PFM人员档案</button>
            <button type="button" @click="router.push('/foundation/erp/materials')">ERP主数据</button>
            <button type="button" @click="router.push('/foundation/security/permissions')">权限与日志</button>
            <button type="button" @click="router.push('/foundation/warnings/rules')">预警引擎基础</button>
            <button type="button" @click="router.push('/reference')">数据引用中心</button>
            <button type="button" @click="router.push('/reference/check')">基础资料检查</button>
            <button type="button" @click="router.push('/foundation/review-check')">基础资料评审检查</button>
            <button type="button" @click="router.push('/foundation/import-records')">基础资料导入记录</button>
            <button type="button" @click="router.push('/scm')">SCM采购管理</button>
            <button type="button" @click="router.push('/scm')">SCM待处理流程</button>
            <button type="button" @click="router.push('/wms')">WMS库存管理</button>
            <button type="button" @click="router.push('/wms/inventory-balances')">库存余额</button>
            <button type="button" @click="router.push('/wms/inventory-transactions')">库存流水</button>
            <button type="button" @click="router.push('/wms/warehouse-tasks')">仓库任务</button>
            <button type="button" @click="router.push('/wms/stock-warnings')">库存预警</button>
            <button type="button" @click="router.push('/wms/purchase-receive-preview')">采购到货预备</button>
            <button type="button" @click="router.push('/wms/purchase-receives')">采购收货预备</button>
            <button type="button" @click="router.push('/qms')">QMS来料检验预备</button>
            <button type="button" @click="router.push('/finance/payable-prepares')">采购应付预备</button>
            <button type="button" @click="router.push('/finance/payable-checks')">采购应付核对</button>
            <button type="button" @click="router.push('/finance/invoice-prepares')">采购发票预备</button>
            <button type="button" @click="router.push('/finance/ap-drafts')">采购应付账款草稿</button>
            <button type="button" @click="router.push('/finance/payment-drafts')">供应商付款草稿</button>
            <button type="button" @click="router.push('/finance/payment-prepares')">正式付款单预备</button>
            <button type="button" @click="router.push('/finance/payment-order-drafts')">正式付款单草稿</button>
            <button type="button" @click="router.push('/admin/approval-flow-config')">审批流配置</button>
            <button type="button" @click="startCreateProcess">新建流程</button>
          </div>
        </header>
        <p class="platform-note">
          当前软件定位为制造企业数字化集成平台，V1.11.0 已接入 ERP、CRM、SCM、WMS、MRP、MPS、APS、MES、QMS、BI、FDM、PFM、KPI 13 大模块蓝图。
        </p>
        <div class="process-grid">
          <article v-for="process in state.processes" :key="process.id" class="business-card">
            <span>{{ categoryLabel(process.category) }}</span>
            <strong>{{ process.name }}</strong>
            <p>当前状态：{{ process.status }}</p>
            <p>负责人/岗位：{{ process.owner }}</p>
            <p>待处理数量：{{ process.pending }}</p>
            <p>状态：{{ process.enabled ? '已启用' : '已停用' }}</p>
            <div class="button-row">
              <button type="button" @click="router.push(`/process-center/process/${process.id}`)">查看</button>
              <button type="button" @click="router.push(`/process-center/process/${process.id}/create`)">新建</button>
              <button type="button" @click="router.push(`/process-center/process/${process.id}/edit`)">编辑</button>
              <button type="button" @click="router.push(`/process-center/process/${process.id}/execute`)">执行</button>
              <button type="button" @click="router.push(`/process-center/process/${process.id}`)">查看流程</button>
              <button type="button" @click="toggleProcess(process)">
                {{ process.enabled ? '停用' : '启用' }}
              </button>
            </div>
          </article>
        </div>
      </section>

      <section v-if="processFormOpen" class="panel editor-panel">
        <header>
          <h2>{{ editingProcessId ? '编辑流程' : '新增流程' }}</h2>
          <button type="button" @click="closeForms">取消</button>
        </header>
        <div class="form-grid">
          <label>流程名称<input v-model="processForm.name" /></label>
          <label>所属分类<select v-model="processForm.category">
            <option v-for="group in processGroups" :key="group.key" :value="group.key">{{ group.title }}</option>
          </select></label>
          <label>负责人岗位<input v-model="processForm.owner" /></label>
          <label>当前状态<input v-model="processForm.status" /></label>
          <label>待处理数量<input v-model.number="processForm.pending" type="number" min="0" /></label>
        </div>
        <button type="button" @click="saveProcess">保存流程</button>
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
          <span>指标与分析只在此处显示</span>
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
              <option value="DISABLED">已禁用</option>
            </select>
            <p>企业业务从业务流程中心开始。</p>
          </article>
          <article>
            <span>组织界面</span>
            <select v-model="adminForm.organizationUI">
              <option value="ACTIVE">已启用</option>
              <option value="DISABLED">已禁用</option>
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
        </div>
      </section>
    </section>
  </main>
</template>

<script setup>
import { computed, defineComponent, h, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getEnterpriseOSModel } from '../enterprise-os/enterpriseOSModel.js'
import { processGroups } from '../enterprise-os/enterpriseOperationModel.js'
import {
  addDepartment,
  addPermission,
  addProcess,
  addRole,
  addTask,
  addUser,
  approveTask,
  completeTask,
  createBusinessRecord,
  deleteDepartment,
  deletePermission,
  deleteRole,
  deleteUser,
  executeProcess as storeExecuteProcess,
  getApprovalById,
  getDepartmentById,
  getEnterpriseOperationState,
  getExecutionTaskById,
  getPermissionById,
  getProcessById,
  getRoleById,
  getTaskById,
  getUserById,
  rejectTask,
  updateApproval,
  updateCompany,
  updateConfig,
  updateDepartment,
  updatePermission,
  updateProcess,
  updateRole,
  updateTask,
  updateUser,
} from '../enterprise-os/enterpriseOperationStore.js'
import { translate } from '../runtime/i18nEngine.js'

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
const model = computed(() => getEnterpriseOSModel())
const state = ref(getEnterpriseOperationState())
const message = ref('')

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
const selectedProcess = computed(() => getProcessById(route.params.id))
const relatedTasks = computed(() => state.value.tasks.filter((task) => task.process === selectedProcess.value?.name))
const workTaskPage = computed(() => route.name === 'WorkTaskAction')
const approvalPage = computed(() => route.name === 'ApprovalAction')
const executionPage = computed(() => route.name === 'ExecutionAction')
const processDetailPage = computed(() => route.name === 'ProcessDetail')
const processCreatePage = computed(() => route.name === 'ProcessCreate')
const processEditPage = computed(() => route.name === 'ProcessEdit')
const processExecutePage = computed(() => route.name === 'ProcessExecute')

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
const processForm = reactive({})
const taskForm = reactive({ opinion: '' })
const approvalForm = reactive({ opinion: '' })
const executionForm = reactive({ result: '' })
const businessForm = reactive({})
const processExecuteForm = reactive({})
const organizationForm = reactive({})
const adminActionForm = reactive({})
const entityFormOpen = ref(false)
const processFormOpen = ref(false)
const editingEntity = ref({ type: '', id: '' })
const editingProcessId = ref('')

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
    ProcessDetail: '流程详情',
    ProcessCreate: '新建业务单',
    ProcessEdit: '编辑流程',
    ProcessExecute: '流程执行',
    AdminRolePermission: '角色权限配置',
    AdminProcessTemplate: '流程模板配置',
    AdminTenantSetting: '租户参数配置',
    AdminConfig: '系统配置项',
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

function categoryLabel(key) {
  return processGroups.find((group) => group.key === key)?.title || key
}

function goBack() {
  if (route.path.startsWith('/work-center')) router.push('/work-center')
  else if (route.path.startsWith('/process-center')) router.push('/process-center')
  else if (route.path.startsWith('/organization')) router.push('/organization')
  else router.push('/admin')
}

function closeForms() {
  entityFormOpen.value = false
  processFormOpen.value = false
  editingEntity.value = { type: '', id: '' }
  editingProcessId.value = ''
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

function startCreateProcess() {
  closeForms()
  editingProcessId.value = ''
  resetObject(processForm, {
    name: '新流程',
    category: 'purchase',
    owner: '负责人岗位',
    status: '待处理',
    pending: 0,
  })
  processFormOpen.value = true
}

function saveProcess() {
  addProcess({
    ...processForm,
    pending: Number(processForm.pending || 0),
    categoryName: categoryLabel(processForm.category),
  })
  closeForms()
  refresh()
  notify('流程已新增')
}

function toggleProcess(process) {
  updateProcess(process.id, { enabled: !process.enabled })
  refresh()
  notify(process.enabled ? '流程已停用' : '流程已启用')
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

function saveBusinessRecord() {
  createBusinessRecord(route.params.id, { ...businessForm })
  refresh()
  notify('业务单已保存')
  goBack()
}

function saveProcessEdit() {
  const process = selectedProcess.value
  if (!process) return
  updateProcess(process.id, {
    ...processForm,
    pending: Number(processForm.pending || 0),
    categoryName: categoryLabel(processForm.category),
  })
  refresh()
  notify('流程已保存')
  goBack()
}

function confirmProcessExecution() {
  storeExecuteProcess(route.params.id, { ...processExecuteForm })
  refresh()
  notify('流程已执行')
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
  resetObject(businessForm, {
    name: `${selectedProcess.value?.name || '业务'}单据`,
    type: selectedProcess.value?.categoryName || '业务单',
    owner: selectedProcess.value?.owner || '负责人',
    planDate: '',
    remark: '',
  })
  resetObject(processForm, selectedProcess.value || {
    name: '新流程',
    category: 'purchase',
    owner: '负责人岗位',
    status: '待处理',
    pending: 0,
  })
  resetObject(processExecuteForm, {
    action: '确认执行',
    result: selectedProcess.value?.executionResult || '',
  })
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

.operation-shell,
.detail-layout {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.panel {
  border: 1px solid #dce5f2;
  border-radius: 8px;
  background: #fff;
  padding: 16px;
}

.primary-panel {
  border-color: #bfdbfe;
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
}
</style>

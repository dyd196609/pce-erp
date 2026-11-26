<template>
  <main class="access-page" data-page-code="erp-access-control-foundation">
    <header class="page-heading">
      <div>
        <p>ERP 组织与权限基础</p>
        <h1>公司、组织、人员、岗位、账户、角色与权限</h1>
        <span>全部记录来自服务端正式模型；岗位不等于角色，账户不代替员工档案。</span>
      </div>
      <PceBusinessStatus status-code="SERVER_FACT" :status-label="loadStatusLabel" source="server" />
    </header>

    <el-alert v-if="loadState==='loading'" title="正在读取组织与权限正式数据，请稍候。" type="info" :closable="false" show-icon />
    <el-alert v-else-if="loadState==='auth_expired'" :title="loadError" type="warning" :closable="false" show-icon />
    <el-alert v-else-if="loadState==='permission_denied'" :title="loadError" type="warning" :closable="false" show-icon />
    <el-alert v-else-if="loadState==='read_failed'" :title="loadError" type="error" :closable="false" show-icon />
    <el-alert v-else-if="responsibilityScopedView" title="当前账号已获得岗位职责维护权限；本页面仅开放责任目录与岗位职责分配正式动作。"
      type="success" :closable="false" show-icon />
    <el-alert v-else-if="restrictedEmployeeView" title="当前账号可查看本人及授权范围内员工；组织、岗位、职责和员工维护需按正式权限办理。"
      type="info" :closable="false" show-icon />
    <el-alert v-else title="正式关系：公司 → 部门 → 岗位 → 员工 → 登录账户 → 系统角色 → 业务动作权限 → 数据范围"
      type="success" :closable="false" show-icon />

    <el-alert v-if="responsibilityLocatorError" :title="responsibilityLocatorError" type="warning" :closable="false" show-icon data-m02-responsibility-locator-error />
    <el-alert v-if="companyLocatorError" :title="companyLocatorError" type="warning" :closable="false" show-icon data-m02-company-locator-error />
    <el-alert v-if="positionAssociationLocatorError" :title="positionAssociationLocatorError" type="warning" :closable="false" show-icon data-m02-position-association-error />
    <nav class="access-tabs" aria-label="组织与权限管理导航">
      <el-button v-for="item in visibleTabs" :key="item.key" :type="activeTab===item.key?'primary':'default'"
        :data-acceptance-id="`access-tab-${item.key}`" @click="selectTab(item.key)">{{ item.label }}</el-button>
    </nav>

    <section v-if="restrictedEmployeeView&&factsReadable" class="summary-grid restricted-summary">
      <article><span>当前可见员工</span><strong>{{ facts.employees.length }}</strong></article>
      <article><span>数据范围</span><strong>{{ accessScopeLabel }}</strong></article>
      <article><span>维护权限</span><strong>无</strong></article>
    </section>
    <section v-else-if="responsibilityScopedView&&factsReadable" class="summary-grid restricted-summary">
      <article class="operating-company-card"><span>当前经营公司</span><strong>{{ operatingCompanyDisplay }}</strong><small>{{ operatingCompanyDetail }}</small></article>
      <article><span>责任</span><strong>{{ summaryCount(facts.responsibilities) }}</strong></article>
      <article><span>可维护岗位</span><strong>{{ summaryCount(facts.positions) }}</strong></article>
      <article><span>数据范围</span><strong>{{ accessScopeLabel }}</strong></article>
      <article><span>维护权限</span><strong>岗位职责维护</strong></article>
    </section>
    <section v-else class="summary-grid">
      <article class="operating-company-card"><span>当前经营公司</span><strong>{{ operatingCompanyDisplay }}</strong><small>{{ operatingCompanyDetail }}</small></article>
      <article><span>有效 / 历史公司</span><strong>{{ summaryPair(facts.companyScopeSummary.activeOperatingCompanyCount, facts.companyScopeSummary.historicalInactiveCompanyCount) }}</strong></article>
      <article><span>当前公司部门</span><strong>{{ summaryCount(facts.departments) }}</strong></article>
      <article><span>当前公司岗位</span><strong>{{ summaryCount(facts.positions) }}</strong></article>
      <article><span>责任</span><strong>{{ summaryCount(facts.responsibilities) }}</strong></article>
      <article><span>员工档案</span><strong>{{ summaryCount(facts.employees) }}</strong></article>
      <article><span>正式业务基础候选</span><strong>{{ summaryValue(facts.employeeArchiveSummary.formalCandidateBaseCount) }}</strong></article>
      <article><span>组织关系待维护</span><strong>{{ summaryValue(facts.employeeArchiveSummary.organizationIncompleteCount) }}</strong></article>
      <article><span>非在职 / 历史</span><strong>{{ summaryValue(facts.employeeArchiveSummary.inactiveHistoryCount) }}</strong></article>
      <article><span>账户</span><strong>{{ summaryCount(facts.users) }}</strong></article>
      <article><span>角色 / 权限</span><strong>{{ summaryPair(facts.roles.length, facts.permissions.length) }}</strong></article>
    </section>

    <section v-if="!factsReadable" class="list-card load-state-card" :data-load-state="loadState">
      <h2>{{ loadState==='loading' ? '正在读取正式数据' : '本次读取未完成' }}</h2>
      <p>{{ loadStateDescription }}</p>
      <p v-if="loadFailure.errorCode" class="load-error-code">错误代码：{{ loadFailure.errorCode }}；HTTP：{{ loadFailure.httpStatus||'未取得' }}</p>
      <el-button v-if="loadState!=='loading'" :loading="loading" @click="refresh">重新读取</el-button>
    </section>
    <section v-else-if="activeTab==='job-families'" class="list-card">
      <JobFamilyManagementPanel :facts="facts" :loading="loading" @refresh="refresh" @view-positions="viewFamilyPositions" />
    </section>
    <section v-else-if="activeTab==='job-levels'" class="list-card">
      <JobLevelManagementPanel :facts="facts" :loading="loading" @refresh="refresh" @view-positions="viewLevelPositions" />
    </section>
    <section v-else-if="!positionAssociationLocatorError" class="list-card">
      <header class="section-heading">
        <div><h2>{{ currentTab.label }}</h2><p>{{ currentTab.note }}</p></div>
        <div class="heading-actions">
          <el-button v-if="canEditActiveTab&&!loadError&&editableTabs.includes(activeTab)" type="primary" @click="openEditor()">{{ organizationTabs.includes(activeTab)?'新增/维护':'新增' }}{{ currentTab.itemName }}</el-button>
          <el-button v-if="canMaintain&&!loadError&&activeTab==='roles'" type="success" @click="openPermissionEditor()">角色权限配置</el-button>
          <el-button v-if="canMaintain&&!loadError&&activeTab==='users'" type="success" @click="openAuthorityEditor()">用户角色分配</el-button>
          <el-button :loading="loading" @click="refresh">刷新</el-button>
        </div>
      </header>

      <p v-if="activeTab==='roles'" data-field-contract="role-state">{{ ROLE_STATE_NOTICE }}</p>
      <PceEnterpriseListTable
        :key="`${route.query.tab}:${activeTab}`"
        :presentation-sort="['responsibilities','companies','departments','positions','employees','users','roles','permissions','review-grants'].includes(activeTab)?runtime.sortState:undefined"
        @sort-change="['responsibilities','companies','departments','positions','employees','users','roles','permissions','review-grants'].includes(activeTab)&&handleSort($event)"
        ref="tableRef" :contract="enterpriseListContract" page-id="erp-access-control"
        :table-id="`erp-access-${activeTab}-table`" :rows="currentRows" :table-rows="filteredRows"
        :preference-user-key="facts.currentUser.userId"
        :filter-schema="currentFilterSchema" :filters="filters" :quick-search="quickSearch"
        :advanced-visible="advancedVisible" :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount" :sort-text="sortText"
        :primary-field="currentTab.primaryField" :primary-label="currentTab.primaryLabel" :primary-width="210"
        min-width="1320px" :show-refresh="true" :refreshing="loading" action-width="180"
        @update:quick-search="quickSearch=$event" @search="appliedSearch=quickSearch"
        @toggle-advanced="advancedVisible=!advancedVisible" @clear-filters="clearFilters"
        @clear-sort="handleTableClearSort" @export-current="exportCurrent" @clear-selection="handleTableClearSelection"
        @update-filter="updateFilter" @selection-change="selectedRows=$event" @refresh="refresh"
      >
        <template #toolbar-extension>
          <LatestBaseDataImportToolbarExtension
            v-if="canMaintain&&!loadError&&organizationImportTabs.includes(activeTab)"
            :entity="activeTab" :entity-name="currentTab.itemName" provider="organization" :xlsx-only="true"
            @import-committed="refresh"
          />
        </template>
        <template #columns>
          <template v-if="activeTab==='companies'">
            <el-table-column prop="name" label="完整公司名称" min-width="240" />
            <el-table-column prop="statusLabel" label="公司状态" width="140" />
            <el-table-column prop="operatingPurposeLabel" label="当前用途" width="150" />
            <el-table-column prop="address" label="地址" min-width="190" />
            <el-table-column prop="departmentCount" label="部门" width="80" />
            <el-table-column prop="positionCount" label="岗位" width="80" />
            <el-table-column prop="employeeCount" label="员工" width="80" />
            <el-table-column prop="salesOrderCount" label="订单" width="80" />
            <el-table-column prop="engineeringSourceCount" label="工程来源" width="100" />
          </template>
          <template v-else-if="activeTab==='departments'">
            <el-table-column prop="name" label="部门名称" width="180" />
            <el-table-column prop="companyName" label="所属公司" width="220" />
            <el-table-column prop="organizationUnitName" label="所属组织单元" width="190" />
            <el-table-column prop="parentName" label="上级部门" width="170" />
            <el-table-column prop="responsiblePositionName" label="责任岗位" width="170" />
            <el-table-column prop="leaderEmployeeName" label="实际负责人" width="170" />
            <el-table-column prop="statusLabel" label="部门状态" width="100" />
          </template>
          <template v-else-if="activeTab==='positions'">
            <el-table-column prop="name" label="岗位名称" width="180" />
            <el-table-column prop="departmentName" label="所属部门" width="180" />
            <el-table-column prop="jobFamilyName" label="岗位族" width="160" />
            <el-table-column prop="jobLevelName" label="岗位等级" width="140" />
            <el-table-column prop="parentPositionName" label="上级岗位" width="170" />
            <el-table-column prop="defaultRoleName" label="默认角色" width="170" />
            <el-table-column prop="responsibilityText" label="已关联岗位职责" min-width="360" />
            <el-table-column prop="employeeCount" label="任职人数" width="110" />
            <el-table-column prop="statusLabel" label="岗位启用状态" width="100" />
          </template>
          <template v-else-if="activeTab==='responsibilities'">
            <el-table-column prop="name" label="责任名称" width="210" />
            <el-table-column prop="businessDomain" label="业务领域" width="150" />
            <el-table-column prop="statusLabel" label="责任状态" width="100" />
            <el-table-column prop="effectiveFrom" label="生效日期" width="120" />
            <el-table-column prop="effectiveTo" label="失效日期" width="120" />
            <el-table-column prop="positionCount" label="关联岗位数量" width="130" />
            <el-table-column label="最后更新时间" min-width="190"><template #default="{row}">{{ formatDateTime(row.lastModifiedAt) }}</template></el-table-column>
          </template>
          <template v-else-if="activeTab==='employees'">
            <el-table-column prop="fullName" label="员工姓名" width="150" />
            <el-table-column prop="companyName" label="所属公司" width="190" />
            <el-table-column prop="departmentName" label="正式部门" width="170" />
            <el-table-column prop="legacyDepartmentName" label="历史部门文字" width="170" />
            <el-table-column prop="positionName" label="正式岗位" width="180" />
            <el-table-column prop="legacyPositionName" label="历史岗位文字" width="180" />
            <el-table-column prop="organizationStatusLabel" label="组织数据状态" width="170" />
            <el-table-column prop="businessCandidateStatusLabel" label="业务候选说明" min-width="260" />
            <el-table-column prop="directManagerDisplay" label="直属主管" width="220" />
            <el-table-column prop="functionalManagerDisplay" label="职能主管" width="220" />
            <el-table-column label="关联登录账户" width="190"><template #default="{row}">{{ row.username||'未建立账号' }}</template></el-table-column>
            <el-table-column prop="statusLabel" label="员工状态" width="100" />
          </template>
          <template v-else-if="activeTab==='users'">
            <el-table-column column-key="real-name" prop="realName" label="账号显示姓名" width="160" />
            <el-table-column column-key="linked-employee" label="关联员工" min-width="260"><template #default="{row}">{{ employeeSummary(row.employee) }}</template></el-table-column>
            <el-table-column column-key="system-roles" label="系统角色" min-width="260"><template #default="{row}">{{ authorityRoles(row) }}</template></el-table-column>
            <el-table-column column-key="data-scope" label="数据范围" width="160"><template #default="{row}">{{ authorityScopes(row) }}</template></el-table-column>
            <el-table-column column-key="credential-state" label="凭证状态" width="150"><template #default="{row}">{{ row.credentialState==='PENDING_SECURE_INITIALIZATION'?'待设置初始密码':'可正常认证' }}</template></el-table-column>
            <el-table-column column-key="account-state" label="账号启用状态" width="100"><template #default="{row}">{{ row.isActive?'启用':'禁用' }}</template></el-table-column>
          </template>
          <template v-else-if="activeTab==='roles'">
            <el-table-column prop="name" label="角色名称" width="190" />
            <el-table-column prop="description" label="角色说明" min-width="300" />
            <el-table-column label="权限数量" width="120"><template #default="{row}">{{ row.permissionCodes.length }}</template></el-table-column>
            <el-table-column label="权限摘要" min-width="360"><template #default="{row}">{{ row.permissionCodes.join('、')||'未配置' }}</template></el-table-column>
          </template>
          <template v-else-if="activeTab==='review-grants'">
            <el-table-column prop="moduleName" label="评审模块" width="190" />
            <el-table-column prop="sourceOrderNo" label="业务订单" width="180" />
            <el-table-column label="评审对象" min-width="210"><template #default="{row}">#{{ row.reviewId }} · V{{ row.reviewVersion }}</template></el-table-column>
            <el-table-column label="参与账户" min-width="220"><template #default="{row}">{{ row.employeeNo }} / {{ row.employeeName }} / {{ row.username }}</template></el-table-column>
            <el-table-column label="对象能力" min-width="300"><template #default="{row}">{{ row.capabilityLabels.join('、')||'无' }}</template></el-table-column>
            <el-table-column prop="requiredRoleCode" label="所需角色" min-width="260" />
            <el-table-column prop="statusLabel" label="评审授权状态" width="100" />
          </template>
          <template v-else>
            <el-table-column prop="name" label="权限名称" width="240" />
            <el-table-column prop="module" label="所属模块" width="150" />
            <el-table-column label="业务动作" min-width="360"><template #default="{row}">{{ row.code }}</template></el-table-column>
            <el-table-column prop="roleNames" label="已授权角色" min-width="260" />
          </template>
        </template>
        <template #actions="{row}">
          <el-button v-if="activeTab==='companies'" link type="primary" @click="openCompanyDetail(row)">查看公司资料</el-button>
          <el-button v-if="canMaintainResponsibility&&!loadError&&activeTab==='responsibilities'" link type="success" @click="openResponsibilityDetail(row)">查看详情</el-button>
          <el-button v-if="responsibilityScopedView&&!loadError&&activeTab==='positions'" link type="primary" @click="openPositionResponsibilityEditor(row)">维护职责分配</el-button>
          <el-button v-if="canEditActiveTab&&!loadError&&editableTabs.includes(activeTab)" link type="primary" @click="openEditor(row)">编辑</el-button>
          <el-button v-if="canMaintain&&!loadError&&activeTab==='roles'" link type="success" @click="openPermissionEditor(row)">配置权限</el-button>
          <el-button v-if="canMaintain&&!loadError&&activeTab==='users'&&!row.isSuperuser" link type="success" @click="openAuthorityEditor(row)">分配角色</el-button>
          <el-button v-if="canMaintain&&!loadError&&activeTab==='review-grants'" link type="primary" @click="openReviewGrantEditor(row)">维护对象授权</el-button>
          <span v-if="restrictedEmployeeView&&activeTab==='employees'">仅查看</span>
          <span v-if="activeTab==='permissions'">权限点由业务动作代码、治理迁移或受控初始化登记；管理员只向角色分配</span>
        </template>
      </PceEnterpriseListTable>
    </section>

    <section v-if="canEditActiveTab&&organizationTabs.includes(activeTab)" class="governance-note">
      <strong>正式维护闭环</strong>
      <span>此入口与组织模型综合页读取同一服务端事实。成功保存必须填写原因并生成 OrganizationOperatingAuditRecord；综合页只负责查看、树展示与诊断。</span>
    </section>

    <section v-if="facts.audits.length" class="audit-card">
      <h2>最近组织维护审计</h2>
      <article v-for="row in facts.audits.slice(0,8)" :key="row.id"><strong>{{ row.actionCode }}</strong><span>{{ row.targetLabel }} · {{ row.actorName }} · {{ row.reason }}<small v-if="row.sourceLabel">来源：{{ row.sourceLabel }}</small></span><small>{{ row.createdAt }}</small></article>
    </section>
    <details v-if="facts.sourceAuditEvents?.length || activeTab==='roles'" class="audit-card" data-source-audit-events>
      <summary>{{ activeTab==='roles' ? '查看角色说明与来源依据' : '查看承接来源审计' }}（{{ facts.sourceAuditEvents.length }}）</summary><p v-if="activeTab==='roles'">{{ ROLE_STATE_TRACE }}</p>
      <p>按原来源和原审计身份追溯；原始记录及最近组织维护审计保持独立。</p>
      <article v-for="row in facts.sourceAuditEvents" :key="row.sourceEventIdentity">
        <strong>{{ row.actionCode }}</strong><span>{{ row.targetLabel }} · {{ row.actorName }} · {{ row.reason }}<small>来源：{{ row.sourceLabel }}</small></span><small>{{ row.createdAt }}</small>
      </article>
    </details>

    <OrganizationOperatingAdminDialog ref="maintenanceRef" :facts="facts" :responsibility-options="responsibilityOptions" :responsibility-assignment-only="responsibilityScopedView" @saved="refresh" />

    <el-dialog :model-value="companyDetailVisible" @update:model-value="value=>{if(!value)closeCompanyDetail()}" title="公司资料" width="min(860px, 95vw)">
      <el-alert :title="companyDetail.isActive?'当前唯一有效经营主体':'历史归档记录：只供追溯，不可用于新增业务'" :type="companyDetail.isActive?'success':'warning'" :closable="false" show-icon />
      <el-descriptions :column="2" border class="detail-section">
        <el-descriptions-item label="公司ID">{{ companyDetail.id }}</el-descriptions-item>
        <el-descriptions-item label="公司编码">{{ companyDetail.code }}</el-descriptions-item>
        <el-descriptions-item label="完整公司名称" :span="2">{{ companyDetail.name }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ companyDetail.statusLabel }}</el-descriptions-item>
        <el-descriptions-item label="用途">{{ companyDetail.operatingPurposeLabel }}</el-descriptions-item>
        <el-descriptions-item label="地址" :span="2">{{ companyDetail.address||'未填写' }}</el-descriptions-item>
        <el-descriptions-item label="联系人">{{ companyDetail.contact||'未填写' }}</el-descriptions-item>
        <el-descriptions-item label="联系电话">{{ companyDetail.phone||'未填写' }}</el-descriptions-item>
        <el-descriptions-item label="组织范围">部门 {{ companyDetail.departmentCount }} · 岗位 {{ companyDetail.positionCount }} · 员工 {{ companyDetail.employeeCount }}</el-descriptions-item>
        <el-descriptions-item label="业务关联">订单 {{ companyDetail.salesOrderCount }} · 工程来源 {{ companyDetail.engineeringSourceCount }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <el-dialog :model-value="responsibilityDetailVisible" title="责任详情" width="min(920px, 95vw)" @update:model-value="value=>{if(!value)closeResponsibilityDetail()}">
      <el-skeleton v-if="responsibilityDetailLoading" :rows="8" animated />
      <template v-else-if="responsibilityDetail.id">
        <el-alert title="事实来源：Responsibility API · system.Responsibility；岗位关系与审计只作为详情证据，不生成责任目录。" type="info" :closable="false" show-icon />
        <el-descriptions title="基础信息" :column="2" border class="detail-section">
          <el-descriptions-item label="责任编码">{{ responsibilityDetail.code }}</el-descriptions-item>
          <el-descriptions-item label="责任名称">{{ responsibilityDetail.name }}</el-descriptions-item>
          <el-descriptions-item label="业务领域">{{ responsibilityDetail.businessDomain||'未填写' }}</el-descriptions-item>
          <el-descriptions-item label="说明">{{ responsibilityDetail.description||'未填写' }}</el-descriptions-item>
        </el-descriptions>
        <el-descriptions title="生命周期" :column="3" border class="detail-section">
          <el-descriptions-item label="状态">{{ responsibilityDetail.statusLabel }}</el-descriptions-item>
          <el-descriptions-item label="生效日期">{{ responsibilityDetail.effectiveFrom||'未填写' }}</el-descriptions-item>
          <el-descriptions-item label="失效日期">{{ responsibilityDetail.effectiveTo||'未填写' }}</el-descriptions-item>
        </el-descriptions>
        <section class="detail-section"><h3>关联岗位（{{ responsibilityDetail.positionCount }}）</h3><el-table :data="responsibilityDetail.positions" empty-text="暂无关联岗位"><el-table-column prop="positionCode" label="岗位编码" width="170" /><el-table-column prop="positionName" label="岗位名称" min-width="180" /><el-table-column prop="departmentName" label="部门" min-width="160" /><el-table-column prop="companyName" label="公司" min-width="180" /><el-table-column prop="responsibilityType" label="承担类型" width="120" /></el-table></section>
        <el-descriptions title="审计信息" :column="2" border class="detail-section">
          <el-descriptions-item label="创建人">{{ responsibilityDetail.audit?.createdBy||'暂无审计' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDateTime(responsibilityDetail.audit?.createdTime) }}</el-descriptions-item>
          <el-descriptions-item label="最后修改人">{{ responsibilityDetail.audit?.lastModifiedBy||'暂无审计' }}</el-descriptions-item>
          <el-descriptions-item label="最后修改时间">{{ formatDateTime(responsibilityDetail.audit?.lastModifiedTime) }}</el-descriptions-item>
          <el-descriptions-item label="修改原因" :span="2">{{ responsibilityDetail.audit?.reason||'暂无审计' }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-dialog>

    <el-dialog v-model="editorVisible" :title="`${editorForm.id?'编辑':'新增'}${currentTab.itemName}`" width="620px">
      <el-form label-width="110px">
        <template v-if="activeTab==='users'">
          <el-form-item label="关联员工" required><el-select v-model="editorForm.employeeId" :disabled="Boolean(editorForm.id)" clearable filterable @change="syncNewAccountEmployee"><el-option v-for="row in availableAccountEmployees" :key="row.id" :label="accountEmployeeOptionLabel(row)" :value="row.id" /></el-select></el-form-item>
          <el-alert v-if="editorForm.id" title="已有账户的关联员工在此处只读" description="请到“员工档案 → 编辑 → 关联登录账户”维护。先核对真实员工编号和当前关联；不会自动选择、解除或改绑员工。" type="info" :closable="false" show-icon />
          <el-form-item v-if="editorForm.id"><el-button plain @click="goToEmployeeAccountMaintenance">前往员工档案关联</el-button></el-form-item>
          <el-form-item label="员工身份"><el-input :model-value="selectedAccountEmployee?accountEmployeeOptionLabel(selectedAccountEmployee):'请选择员工档案中的在职未开户员工'" disabled /></el-form-item>
          <el-alert v-if="!editorForm.id&&selectedAccountEmployee" :title="selectedAccountEmployee.accountProvisioningStatusLabel" :description="accountProvisioningDescription" :type="selectedAccountEmployee.accountProvisioningEligible?'warning':'error'" :closable="false" show-icon />
          <el-form-item label="登录账号"><el-input :model-value="editorForm.id?editorForm.username:(selectedAccountEmployee?.suggestedUsername||'选择员工后由系统自动生成')" disabled /><small class="form-hint">登录账号由统一正式开户服务按员工编号生成；员工改名或调岗不会重算。</small></el-form-item>
          <el-form-item label="真实姓名"><el-input v-model="editorForm.realName" :disabled="!editorForm.id" /></el-form-item>
          <el-form-item label="所属公司" required><el-select v-model="editorForm.companyId" disabled><el-option v-for="row in facts.companies" :key="row.id" :label="row.name" :value="row.id" /></el-select></el-form-item>
          <el-form-item v-if="editorForm.id" label="重置密码"><el-switch v-model="editorForm.passwordChangeRequested" active-text="本次明确重置" inactive-text="保持原密码" /></el-form-item>
          <el-alert v-if="!editorForm.id" title="新账户将建立为“待设置初始密码”；本次不写入密码。保存后由账户管理员通过现有受控入口明确设置。" type="info" :closable="false" show-icon />
          <template v-if="editorForm.id&&editorForm.passwordChangeRequested">
            <el-alert title="密码只在本次明确重置时写入；普通资料、角色和范围修改不会改变密码。" type="warning" :closable="false" show-icon />
            <el-form-item :label="editorForm.id?'新密码':'初始密码'" required><el-input v-model="editorForm.password" type="password" show-password autocomplete="new-password" /></el-form-item>
            <el-form-item label="确认密码" required><el-input v-model="editorForm.passwordConfirm" type="password" show-password autocomplete="new-password" /></el-form-item>
          </template>
          <el-form-item label="账户状态"><el-switch v-model="editorForm.isActive" active-text="启用" inactive-text="禁用" /></el-form-item>
          <el-form-item label="修改原因" required><el-input v-model="editorForm.reason" type="textarea" /></el-form-item>
        </template>
        <template v-else-if="activeTab==='roles'">
          <el-form-item label="角色编码">
            <el-input v-if="editorForm.id" v-model="editorForm.code" disabled />
            <el-input v-else model-value="系统自动生成" disabled />
            <small class="form-hint">新增时由统一正式编码服务生成；编辑既有角色不会重新编号。</small>
          </el-form-item>
          <el-form-item label="角色名称" required><el-input v-model="editorForm.name" /></el-form-item>
          <el-form-item label="角色说明"><el-input v-model="editorForm.description" type="textarea" /></el-form-item>
        </template>
      </el-form>
      <template #footer><el-button @click="editorVisible=false">取消</el-button><el-button type="primary" :loading="saving" :disabled="editorSaveDisabled" @click="saveEditor">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="permissionVisible" title="角色权限配置" width="760px">
      <el-form label-width="88px" class="permission-form"><el-form-item label="系统角色"><el-select v-model="permissionRoleId" @change="syncPermissionSelection"><el-option v-for="row in facts.roles" :key="row.id" :label="`${row.code} / ${row.name}`" :value="row.id" /></el-select></el-form-item><el-form-item label="权限筛选"><el-input v-model="permissionSearch" clearable placeholder="按权限编码或名称筛选" /></el-form-item><el-form-item label="修改原因" required><el-input v-model="permissionReason" /></el-form-item></el-form>
      <el-alert title="事项权限决定可承担哪一项；操作权限决定可执行查看、本人意见、本人签认、完整草稿或提交；具体评审仍须另有对象、版本和本人责任关系。" type="info" :closable="false" show-icon />
      <el-checkbox-group :key="permissionSearch" v-model="selectedPermissionCodes" class="permission-groups">
        <section v-for="group in groupedPermissions" :key="group.label" class="permission-group">
          <h3>{{ group.label }}</h3>
          <div class="permission-grid"><el-checkbox v-for="row in group.rows" :key="row.code" :value="row.code" :label="row.code"><strong>{{ row.name }}</strong><small>{{ row.code }}</small></el-checkbox></div>
        </section>
      </el-checkbox-group>
      <template #footer><el-button @click="permissionVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="savePermissions">保存角色权限</el-button></template>
    </el-dialog>

    <el-dialog v-model="authorityVisible" title="用户角色与数据范围" width="760px">
      <el-form label-width="100px"><el-form-item label="登录账户"><el-select v-model="authorityUserId" @change="syncAuthorityRows"><el-option v-for="row in nonAdminUsers" :key="row.id" :label="`${row.username} / ${row.realName}`" :value="row.id" /></el-select></el-form-item><el-form-item label="修改原因" required><el-input v-model="authorityReason" /></el-form-item></el-form>
      <div v-for="(row,index) in authorityRows" :key="index" class="authority-row">
        <el-select v-model="row.roleCode" placeholder="角色"><el-option v-for="role in facts.roles.filter(item=>item.code!=='superadmin')" :key="role.code" :label="role.name" :value="role.code" /></el-select>
        <el-select v-model="row.scopeCode" placeholder="数据范围"><el-option v-for="scope in facts.scopeOptions" :key="scope.code" :label="scope.name" :value="scope.code" /></el-select>
        <el-select v-if="row.scopeCode==='DEPARTMENT'" v-model="row.departmentId" placeholder="部门"><el-option v-for="department in facts.departments" :key="department.id" :label="department.name" :value="department.id" /></el-select>
        <el-button type="danger" plain @click="authorityRows.splice(index,1)">移除</el-button>
      </div>
      <el-button plain @click="authorityRows.push(defaultAuthority())">添加角色</el-button>
      <template #footer><el-button @click="authorityVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="saveAuthorities">保存用户角色</el-button></template>
    </el-dialog>

    <el-dialog v-model="reviewGrantVisible" title="评审对象授权" width="760px">
      <el-alert title="双重门禁：系统角色权限与当前评审对象授权必须同时有效；本入口不授予正式提交权限。" type="warning" :closable="false" show-icon />
      <el-descriptions :column="2" border class="detail-section">
        <el-descriptions-item label="评审模块">{{ reviewGrantForm.moduleName }}</el-descriptions-item>
        <el-descriptions-item label="评审对象">#{{ reviewGrantForm.reviewId }} · V{{ reviewGrantForm.reviewVersion }}</el-descriptions-item>
        <el-descriptions-item label="参与账户" :span="2">{{ reviewGrantForm.employeeNo }} / {{ reviewGrantForm.employeeName }} / {{ reviewGrantForm.username }}</el-descriptions-item>
        <el-descriptions-item label="所需角色" :span="2">{{ reviewGrantForm.requiredRoleCode }}</el-descriptions-item>
        <el-descriptions-item label="所需权限" :span="2">{{ (reviewGrantForm.requiredPermissionCodes||[]).join('、') }}</el-descriptions-item>
        <el-descriptions-item label="对象范围" :span="2">{{ reviewGrantForm.scopeLabel }}</el-descriptions-item>
      </el-descriptions>
      <el-form label-width="150px" class="detail-section">
        <el-form-item label="授权状态"><el-switch v-model="reviewGrantForm.active" active-text="有效" inactive-text="撤销" /></el-form-item>
        <el-form-item label="查看本评审"><el-switch v-model="reviewGrantForm.canView" /></el-form-item>
        <el-form-item label="维护本人意见"><el-switch v-model="reviewGrantForm.canMaintainOwnOpinion" /></el-form-item>
        <el-form-item label="签认本人项目"><el-switch v-model="reviewGrantForm.canSignOwnItems" /></el-form-item>
        <el-form-item label="修改原因" required><el-input v-model="reviewGrantForm.reason" type="textarea" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="reviewGrantVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="saveReviewGrant">保存对象授权</el-button></template>
    </el-dialog>
  </main>
</template>

<script setup>
import {ROLE_STATE_NOTICE,ROLE_STATE_TRACE} from '@/meta/runtime/authoritativeFieldPresentation.js'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { accessControlApi } from '@/api/accessControl.js'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import OrganizationOperatingAdminDialog from '@/meta/components/OrganizationOperatingAdminDialog.vue'
import JobFamilyManagementPanel from '@/meta/components/JobFamilyManagementPanel.vue'
import JobLevelManagementPanel from '@/meta/components/JobLevelManagementPanel.vue'
import LatestBaseDataImportToolbarExtension from '@/meta/components/LatestBaseDataImportToolbarExtension.vue'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { JOB_FAMILY_LOAD_STATUS, loadJobFamilyOptions, mapJobFamilyResponse } from '@/meta/runtime/jobFamilyRuntimeLoad.js'
import { ACCESS_CONTROL_LOAD_STATE, classifyAccessControlFailure, loadStateMessage } from '@/meta/runtime/accessControlLoadState.js'

const route=useRoute(),router=useRouter(),loading=ref(false),saving=ref(false),loadError=ref('')
const loadState=ref(ACCESS_CONTROL_LOAD_STATE.LOADING)
const loadFailure=reactive({errorCode:'',httpStatus:0,apiUrl:''})
const jobFamilyLoadStatus=ref('NOT_LOADED')
const tabs=[
  {key:'companies',label:'公司资料',itemName:'公司',note:'正式 Company 只读资料；区分当前经营主体与历史归档记录',primaryField:'code',primaryLabel:'公司编码'},
  {key:'departments',label:'部门管理',itemName:'部门',note:'正式 Department 主档及所属公司',primaryField:'code',primaryLabel:'部门编码'},
  {key:'positions',label:'岗位管理',itemName:'岗位',note:'正式 Position 主档；岗位属于组织，不等于系统角色',primaryField:'code',primaryLabel:'岗位编码'},
  {key:'job-families',label:'岗位族管理',itemName:'岗位族',note:'正式 JobFamily 目录及关联岗位事实',primaryField:'code',primaryLabel:'岗位族编码'},
  {key:'job-levels',label:'岗位等级管理',itemName:'岗位等级',note:'正式 JobLevel 目录及关联岗位事实',primaryField:'code',primaryLabel:'岗位等级编码'},
  {key:'responsibilities',label:'责任管理',itemName:'责任',note:'独立 Responsibility 目录；先定义责任，再由岗位选择并承担',primaryField:'code',primaryLabel:'责任编码'},
  {key:'employees',label:'员工档案',itemName:'员工',note:'正式 Employee 档案及部门、岗位、账户关系',primaryField:'employeeNo',primaryLabel:'员工编号'},
  {key:'users',label:'用户账户',itemName:'账户',note:'登录账户必须明确关联员工，角色允许多选',primaryField:'username',primaryLabel:'登录账号'},
  {key:'roles',label:'角色管理',itemName:'角色',note:'系统角色是权限集合，不等于岗位',primaryField:'code',primaryLabel:'角色编码'},
  {key:'permissions',label:'权限管理',itemName:'权限',note:'业务动作权限点及模块归属',primaryField:'code',primaryLabel:'权限编码'},
  {key:'review-grants',label:'评审对象授权',itemName:'评审对象授权',note:'角色权限与评审对象/版本授权双重门禁；不在此授予正式提交',primaryField:'grantCode',primaryLabel:'授权编码'},
]
const activeTab=ref(tabs.some(item=>item.key===route.query.tab)?route.query.tab:'departments')
const RESPONSIBILITY_MANAGE_PERMISSION='system.organization.responsibility.manage'
const canMaintain=ref(false),canMaintainResponsibility=ref(false)
const responsibilityScopedView=computed(()=>!canMaintain.value&&canMaintainResponsibility.value)
const restrictedEmployeeView=computed(()=>!canMaintain.value&&!canMaintainResponsibility.value)
const visibleTabs=computed(()=>canMaintain.value?tabs:responsibilityScopedView.value?tabs.filter(item=>['positions','responsibilities'].includes(item.key)):tabs.filter(item=>item.key==='employees'))
const canEditActiveTab=computed(()=>canMaintain.value||(canMaintainResponsibility.value&&activeTab.value==='responsibilities'))
const accessScopeCodes=ref([])
const accessScopeLabel=computed(()=>accessScopeCodes.value.map(code=>({SELF:'本人',DEPARTMENT:'本部门',ORGANIZATION:'当前组织',ALL:'全部'}[code]||'授权范围')).join('、')||'本人')
const currentTab=computed(()=>tabs.find(item=>item.key===activeTab.value)||tabs[0])
const facts=reactive({companies:[],operatingCompany:null,companyScopeSummary:{},employeeArchiveSummary:{},organizationUnits:[],departments:[],positions:[],employees:[],accountLinkEmployees:[],users:[],roles:[],permissions:[],reviewGrants:[],scopeOptions:[],jobFamilies:[],jobLevels:[],responsibilities:[],workflowResponsibilities:[],workflowNodes:[],audits:[],sourceAuditEvents:[],currentUser:{}})
const operatingCompany=computed(()=>facts.operatingCompany||facts.companies.find(row=>row.isActive)||null)
const factsReadable=computed(()=>[ACCESS_CONTROL_LOAD_STATE.LOADED,ACCESS_CONTROL_LOAD_STATE.EMPTY_VALID].includes(loadState.value))
const loadStatusLabel=computed(()=>({loading:'正在读取',loaded:'服务端正式数据',empty_valid:'读取成功（无记录）',permission_denied:'无访问权限',auth_expired:'登录状态失效',read_failed:'服务器读取失败'}[loadState.value]||'未读取'))
const operatingCompanyDisplay=computed(()=>factsReadable.value?(operatingCompany.value?.name||'未确定'):(loadState.value===ACCESS_CONTROL_LOAD_STATE.LOADING?'正在读取':'—'))
const operatingCompanyDetail=computed(()=>factsReadable.value?(operatingCompany.value?`${operatingCompany.value.code} · ID ${operatingCompany.value.id}`:'读取成功，但服务端未返回唯一经营主体'):'尚未取得可信的服务端公司事实')
const loadStateDescription=computed(()=>loadStateMessage(loadState.value))
const responsibilityOptions=ref([])
const currentRows=computed(()=>activeTab.value==='review-grants'?facts.reviewGrants:(facts[activeTab.value]||[]))
const organizationTabs=['departments','positions','responsibilities','employees']
const organizationImportTabs=['departments','positions','employees']
const editableTabs=[...organizationTabs,'users','roles']
const filterSchemas={
  companies:[{field:'code',label:'公司编码',filterType:'text'},{field:'name',label:'完整公司名称',filterType:'text'},{field:'operatingPurpose',label:'当前用途',filterType:'select',options:[{label:'当前经营主体',value:'OPERATING'},{label:'仅供历史追溯',value:'HISTORICAL_ARCHIVE'}]}],
  departments:[{field:'code',label:'部门编码',filterType:'text'},{field:'name',label:'部门名称',filterType:'text'},{field:'companyName',label:'所属公司',filterType:'text'}],
  positions:[{field:'code',label:'岗位编码',filterType:'text'},{field:'name',label:'岗位名称',filterType:'text'},{field:'departmentId',label:'所属部门',filterType:'select',optionsSource:()=>facts.departments.map(row=>({label:`${row.code} · ${row.name}`,value:row.id}))},{field:'jobFamilyId',label:'岗位族',filterType:'select',optionsSource:()=>facts.jobFamilies.map(row=>({label:`${row.code} · ${row.name}`,value:row.id}))},{field:'jobLevelId',label:'岗位等级',filterType:'select',optionsSource:()=>facts.jobLevels.map(row=>({label:`${row.code} · ${row.name}`,value:row.id}))},{field:'isActive',label:'岗位启用状态',filterType:'select',options:[{label:'启用',value:true},{label:'停用',value:false}]}],
  responsibilities:[{field:'code',label:'责任编码',filterType:'text'},{field:'name',label:'责任名称',filterType:'text'},{field:'businessDomain',label:'业务领域',filterType:'text'},{field:'status',label:'责任状态',filterType:'select',options:[{label:'草稿',value:'DRAFT'},{label:'生效',value:'ACTIVE'},{label:'暂停',value:'SUSPENDED'},{label:'失效',value:'EXPIRED'}]}],
  employees:[
    {field:'employeeNo',label:'员工编号',filterType:'text'},
    {field:'fullName',label:'员工姓名',filterType:'text'},
    {field:'departmentId',label:'正式部门',filterType:'select',optionsSource:()=>facts.departments.map(row=>({label:`${row.code} · ${row.name}`,value:row.id}))},
    {field:'legacyDepartmentName',label:'历史部门文字',filterType:'select',optionsSource:'current_result'},
    {field:'positionId',label:'正式岗位',filterType:'select',optionsSource:()=>facts.positions.filter(row=>row.isActive!==false).map(row=>({label:`${row.code} · ${row.name}`,value:row.id}))},
    {field:'legacyPositionName',label:'历史岗位文字',filterType:'select',optionsSource:'current_result'},
    {field:'directManagerId',label:'直属主管',filterType:'select',optionsSource:()=>facts.employees.filter(row=>row.formalCandidateBaseEligible).map(row=>({label:`${row.employeeNo} · ${row.fullName}`,value:row.id}))},
    {field:'functionalManagerId',label:'职能主管',filterType:'select',optionsSource:()=>facts.employees.filter(row=>row.formalCandidateBaseEligible).map(row=>({label:`${row.employeeNo} · ${row.fullName}`,value:row.id}))},
    {field:'organizationComplete',label:'组织数据状态',filterType:'select',options:[{label:'正式组织链完整',value:true},{label:'组织关系待维护',value:false}]},
    {field:'status',label:'员工状态',filterType:'select',options:[{label:'在职',value:'active'},{label:'停用',value:'inactive'},{label:'休假',value:'leave'},{label:'离职',value:'quit'}]},
  ],
  users:[{field:'username',label:'登录账号',filterType:'text'},{field:'realName',label:'账号显示姓名',filterType:'text'},{field:'credentialState',label:'凭证状态',filterType:'select',options:[{label:'待设置初始密码',value:'PENDING_SECURE_INITIALIZATION'},{label:'可正常认证',value:'ACTIVE'}]},{field:'isActive',label:'账号启用状态',filterType:'select',options:[{label:'启用',value:true},{label:'禁用',value:false}]}],
  roles:[{field:'code',label:'角色编码',filterType:'text'},{field:'name',label:'角色名称',filterType:'text'},{field:'description',label:'说明',filterType:'text'}],
  permissions:[{field:'code',label:'权限编码',filterType:'text'},{field:'name',label:'权限名称',filterType:'text'},{field:'module',label:'所属模块',filterType:'text'}],
  'review-grants':[{field:'moduleName',label:'评审模块',filterType:'text'},{field:'username',label:'登录账号',filterType:'text'},{field:'employeeName',label:'员工姓名',filterType:'text'},{field:'active',label:'评审授权状态',filterType:'select',options:[{label:'有效',value:true},{label:'已撤销',value:false}]}],
}
const currentFilterSchema=computed(()=>filterSchemas[activeTab.value])
const allFilterSchema=Object.values(filterSchemas).flat().filter((field,index,rows)=>rows.findIndex(item=>item.field===field.field)===index)
const enterpriseListContract=computed(()=>createPceEnterpriseListContract({pageCode:`erp-access-${activeTab.value}`,pageType:'list',title:currentTab.value.label,moduleCode:'SYSTEM'}))
const rowsProxy=computed(()=>currentRows.value)
const exportNameColumns={companies:{field:'name',label:'完整公司名称'},departments:{field:'name',label:'部门名称'},positions:{field:'name',label:'岗位名称'},responsibilities:{field:'name',label:'责任名称'},employees:{field:'fullName',label:'员工姓名'},users:{field:'realName',label:'账号显示姓名'},roles:{field:'name',label:'角色名称'},permissions:{field:'name',label:'权限名称'},'review-grants':{field:'moduleName',label:'评审模块'}}
function currentExportColumns(){const name=exportNameColumns[activeTab.value];if(!name)throw new Error('当前对象导出字段尚未核定');return [{field:currentTab.value.primaryField,label:currentTab.value.primaryLabel},name]}
const runtime=usePceEnterpriseListRuntime({presentationScope:()=>route.fullPath,rows:rowsProxy,filterSchema:allFilterSchema,pageCode:'erp-access-control',searchFields:['code','name','employeeNo','fullName','username','realName','employeeName','sourceOrderNo','module','moduleName','departmentName','legacyDepartmentName','positionName','legacyPositionName','directManagerDisplay','functionalManagerDisplay','statusLabel','description','businessDomain'],exportFileName:'erp-access-control.csv',exportColumns:currentExportColumns})
const {selectedRows,quickSearch,appliedSearch,advancedVisible,filters,tableRef,activeFilterCount,sortText,filteredRows,clearFilters,handleSort,clearSort:clearTableSort,handleSelectionChange,clearSelection:clearTableSelection,exportCurrent}=runtime
function updateFilter(field,value){filters[field]=value}
function handleTableClearSort(){handleSort()}
function handleTableClearSelection(){handleSelectionChange([])}
// Save against the current organization route before the outer menu commits its destination.
onBeforeRouteLeave(()=>{runtime.savePresentation()})
function selectTab(tab){if(!visibleTabs.value.some(item=>item.key===tab))return;runtime.savePresentation();router.replace({path:'/organization',query:{tab}})}
function viewFamilyPositions(id){runtime.savePresentation();clearFilters();clearTableSort();clearTableSelection();router.replace({path:'/organization',query:{tab:'positions',jobFamilyId:String(id)}})}
function viewLevelPositions(id){runtime.savePresentation();clearFilters();clearTableSort();clearTableSelection();router.replace({path:'/organization',query:{tab:'positions',jobLevelId:String(id)}})}
watch(()=>route.query.tab,value=>{if(tabs.some(item=>item.key===value))activeTab.value=value})
watch(activeTab,(value,previous)=>{if(value===previous)return;clearFilters();clearTableSort();clearTableSelection();if(route.query.tab===value)runtime.restorePresentation()})
// Read-only record locator from the existing home; switching tabs still clears unrelated filters.
watch(()=>[route.query.tab,route.query.search],()=>{if(['responsibilities','companies','departments','positions','employees','users','roles','permissions','review-grants'].includes(route.query.tab)&&route.query.search===undefined)return;quickSearch.value=String(route.query.search||'');appliedSearch.value=quickSearch.value},{immediate:true,flush:'post'})
// Original association links are explicit display locators, never action authority.
const positionAssociationLocatorError=ref('')
watch(()=>[route.query.tab,route.query.jobFamilyId,route.query.jobLevelId,factsReadable.value],()=>{
  positionAssociationLocatorError.value=''
  if(route.query.tab!=='positions'||!factsReadable.value)return
  for(const [field,catalog] of [['jobFamilyId','jobFamilies'],['jobLevelId','jobLevels']]){
    const raw=route.query[field];if(raw===undefined)continue
    const id=Number(raw),known=Number.isSafeInteger(id)&&id>0&&facts[catalog].some(row=>Number(row.id)===id)
    filters[field]=known?id:'__invalid_association_locator__'
    if(!known)positionAssociationLocatorError.value='所选岗位族或岗位等级不在本次可读目录中，请返回原目录重新选择；当前未定位关联岗位。'
  }
},{immediate:true,flush:'post'})
function resetFacts(){Object.keys(facts).forEach(key=>{facts[key]=key==='currentUser'?{}:key==='operatingCompany'?null:['companyScopeSummary','employeeArchiveSummary'].includes(key)?{}:[]})}
function summaryCount(rows){return factsReadable.value?rows.length:'—'}
function summaryValue(value){return factsReadable.value?(value??0):'—'}
function summaryPair(left,right){return factsReadable.value?`${left??0} / ${right??0}`:'— / —'}
function applyLoadFailure(response,fallback){const failure=classifyAccessControlFailure(response);loadState.value=failure.state;loadError.value=failure.message||fallback;loadFailure.errorCode=failure.errorCode;loadFailure.httpStatus=failure.httpStatus;loadFailure.apiUrl=failure.apiUrl;resetFacts();responsibilityOptions.value=[]}
function mapScopedEmployee(row){const organizationComplete=Boolean(row.department_ref&&row.position_ref);return{id:row.id,employeeNo:row.employee_no,fullName:row.full_name,companyName:row.formal_department_name?'当前登录组织':'未关联正式公司',departmentName:row.formal_department_name||'未维护',legacyDepartmentName:row.department_name||'—',positionName:row.formal_position_name||'未维护',legacyPositionName:row.position||'—',organizationComplete,organizationStatusLabel:organizationComplete?'组织关系已关联':'组织关系待维护',formalCandidateBaseEligible:false,businessCandidateStatusLabel:'业务资格由服务端正式候选规则另行判断',directManagerDisplay:'未维护',functionalManagerDisplay:'未维护',username:row.user_name||'',status:row.status,statusLabel:row.status==='active'?'在职':'非在职'}}
async function refresh(){loading.value=true;loadState.value=ACCESS_CONTROL_LOAD_STATE.LOADING;loadError.value='';Object.assign(loadFailure,{errorCode:'',httpStatus:0,apiUrl:''});resetFacts();responsibilityOptions.value=[];try{const profileResponse=await accessControlApi.profile();if(!profileResponse.success){applyLoadFailure(profileResponse,'当前账号读取失败');return}const profile=profileResponse.data||{};const permissionCodes=profile.permissionCodes||[];canMaintain.value=permissionCodes.includes('*')||profile.roles?.includes('superadmin');canMaintainResponsibility.value=canMaintain.value||permissionCodes.includes(RESPONSIBILITY_MANAGE_PERMISSION);accessScopeCodes.value=profile.scopeCodes||[];facts.currentUser=profile;if(responsibilityScopedView.value){if(!['positions','responsibilities'].includes(activeTab.value))activeTab.value='responsibilities';const catalogResponse=await accessControlApi.responsibilities({assignmentContext:'1'});if(!catalogResponse.success){applyLoadFailure(catalogResponse,'责任目录读取失败');return}const organization=profile.organization||{};const company=organization.id?{id:organization.id,code:organization.code||'',name:organization.name||'',isActive:true}:null;const assignmentContext=catalogResponse.data?.assignmentContext||{};facts.companies=company?[company]:[];facts.operatingCompany=company;facts.departments=assignmentContext.departments||[];facts.positions=assignmentContext.positions||[];responsibilityOptions.value=catalogResponse.data?.items||[];facts.responsibilities=responsibilityOptions.value;loadState.value=facts.responsibilities.length||facts.positions.length?ACCESS_CONTROL_LOAD_STATE.LOADED:ACCESS_CONTROL_LOAD_STATE.EMPTY_VALID;return}if(restrictedEmployeeView.value){activeTab.value='employees';const employeeResponse=await accessControlApi.scopedEmployees({page_size:100});if(!employeeResponse.success){applyLoadFailure(employeeResponse,'员工档案读取失败');return}facts.employees=(employeeResponse.data?.results||[]).map(mapScopedEmployee);loadState.value=facts.employees.length?ACCESS_CONTROL_LOAD_STATE.LOADED:ACCESS_CONTROL_LOAD_STATE.EMPTY_VALID;return}const [response,organizationResponse,catalogResponse]=await Promise.all([accessControlApi.foundation(),accessControlApi.enterpriseOrganizationModel(),accessControlApi.responsibilities()]);if(!response.success){applyLoadFailure(response,'组织与权限正式数据读取失败');return}if(!organizationResponse.success){applyLoadFailure(organizationResponse,'企业组织模型读取失败');return}if(!catalogResponse.success){applyLoadFailure(catalogResponse,'责任目录读取失败');return}const jobFamilyResult=mapJobFamilyResponse(organizationResponse);jobFamilyLoadStatus.value=jobFamilyResult.status;if(jobFamilyResult.status===JOB_FAMILY_LOAD_STATUS.READ_FAILED){applyLoadFailure({error:{code:'ORGANIZATION_MODEL_CONTRACT_INVALID',message:jobFamilyResult.error},meta:{status:200}},jobFamilyResult.error);return}Object.keys(facts).forEach(key=>facts[key]=key==='currentUser'?(response.data?.[key]||profile):(response.data?.[key]??facts[key]));facts.jobFamilies=jobFamilyResult.options;facts.jobLevels=organizationResponse.data?.jobLevels||[];facts.sourceAuditEvents=organizationResponse.data?.sourceAuditEvents;responsibilityOptions.value=catalogResponse.data?.items||[];facts.responsibilities=responsibilityOptions.value;loadState.value=facts.companies.length||facts.departments.length||facts.positions.length||facts.employees.length||facts.users.length||facts.roles.length||facts.permissions.length?ACCESS_CONTROL_LOAD_STATE.LOADED:ACCESS_CONTROL_LOAD_STATE.EMPTY_VALID}catch(error){applyLoadFailure({error:{code:'UNEXPECTED_READ_FAILURE',message:error.message||String(error)}},'组织与权限正式数据读取失败')}finally{loading.value=false}}
const responsibilityDetailVisible=ref(false),responsibilityDetailLoading=ref(false),responsibilityDetail=reactive({})
const responsibilityLocatorError=ref('')
let responsibilityReadSequence=0, responsibilityReadingId=null
const companyDetailVisible=ref(false),companyDetail=reactive({})
const companyLocatorError=ref('')
// Same original foundation company row; URL is only a lookup hint, never authority.
async function openCompanyDetail(row){
  if(!factsReadable.value||activeTab.value!=='companies'||!visibleTabs.value.some(tab=>tab.key==='companies'))return
  const current=facts.companies.find(item=>Number(item.id)===Number(row.id));if(!current)return
  if(String(route.query.companyId||'')!==String(current.id)){await router.replace({path:route.path,query:{...route.query,companyId:String(current.id)}});return}
  resetObject(companyDetail,current);companyDetailVisible.value=true
}
function closeCompanyDetail(){
  companyDetailVisible.value=false
  if(route.query.companyId!==undefined){const query={...route.query};delete query.companyId;router.replace({path:route.path,query})}
}
watch(()=>[route.query.companyId,activeTab.value,factsReadable.value],()=>{
  companyLocatorError.value='';companyDetailVisible.value=false;resetObject(companyDetail,{})
  if(route.query.companyId===undefined||activeTab.value!=='companies'||!factsReadable.value)return
  if(!visibleTabs.value.some(tab=>tab.key==='companies')){companyLocatorError.value='当前账号不可查看公司资料。';return}
  const id=Number(route.query.companyId),row=Number.isSafeInteger(id)&&id>0&&facts.companies.find(item=>Number(item.id)===id)
  if(!row){companyLocatorError.value='定位的公司不在当前可读取目录中，请核对链接或返回公司资料列表选择。';return}
  openCompanyDetail(row)
},{flush:'post'})
function formatDateTime(value){return value?new Date(value).toLocaleString('zh-CN',{hour12:false}):'暂无记录'}
// The URL is a read locator only. Refresh always reloads qualification and the scoped catalog first.
async function openResponsibilityDetail(row){
  if(!factsReadable.value||!canMaintainResponsibility.value||activeTab.value!=='responsibilities'||!facts.responsibilities.some(item=>Number(item.id)===Number(row.id)))return
  if(String(route.query.responsibilityId||'')!==String(row.id)){
    await router.replace({path:route.path,query:{...route.query,responsibilityId:String(row.id)}})
    return
  }
  if(responsibilityReadingId===Number(row.id)||(responsibilityDetailVisible.value&&Number(responsibilityDetail.id)===Number(row.id)))return
  const sequence=++responsibilityReadSequence
  responsibilityReadingId=Number(row.id);responsibilityLocatorError.value='';responsibilityDetailVisible.value=true;responsibilityDetailLoading.value=true;resetObject(responsibilityDetail,{})
  try{
    const response=await accessControlApi.responsibilities({id:row.id})
    if(sequence!==responsibilityReadSequence)return
    if(!response.success)throw new Error(response.error?.message||'责任详情读取失败')
    if(Number(response.data?.item?.id)!==Number(row.id))throw new Error('责任详情返回对象与定位记录不一致，请重新读取。')
    resetObject(responsibilityDetail,response.data.item)
  }catch(error){if(sequence===responsibilityReadSequence){responsibilityLocatorError.value=error.message||String(error);responsibilityDetailVisible.value=false}}
  finally{if(sequence===responsibilityReadSequence){responsibilityDetailLoading.value=false;responsibilityReadingId=null}}
}
function closeResponsibilityDetail(){
  ++responsibilityReadSequence;responsibilityReadingId=null;responsibilityDetailLoading.value=false;responsibilityDetailVisible.value=false
  if(route.query.responsibilityId!==undefined&&!responsibilityLocatorError.value){const query={...route.query};delete query.responsibilityId;router.replace({path:route.path,query})}
}
watch(()=>[route.query.responsibilityId,activeTab.value,factsReadable.value,canMaintainResponsibility.value],()=>{
  responsibilityLocatorError.value=''
  const locator=route.query.responsibilityId
  if(locator===undefined||activeTab.value!=='responsibilities'||!factsReadable.value){++responsibilityReadSequence;responsibilityReadingId=null;responsibilityDetailLoading.value=false;responsibilityDetailVisible.value=false;return}
  if(!canMaintainResponsibility.value){++responsibilityReadSequence;responsibilityReadingId=null;responsibilityDetailLoading.value=false;responsibilityDetailVisible.value=false;responsibilityLocatorError.value='当前账号没有责任详情读取资格。';return}
  const id=Number(locator),row=Number.isSafeInteger(id)&&id>0&&facts.responsibilities.find(item=>Number(item.id)===id)
  if(!row){++responsibilityReadSequence;responsibilityReadingId=null;responsibilityDetailLoading.value=false;responsibilityDetailVisible.value=false;responsibilityLocatorError.value='定位的责任记录不在当前可读取目录中，请核对链接或返回目录选择。';return}
  openResponsibilityDetail(row)
},{flush:'post'})
function openPositionResponsibilityEditor(row){maintenanceRef.value?.open('positions',row)}
function employeeSummary(employee){return employee?`${employee.employeeNo} / ${employee.fullName} / ${employee.departmentName} / ${employee.positionName}`:'未关联员工'}
function authorityRoles(user){return user.isSuperuser?'系统管理员（ALL）':(user.authorities||[]).map(item=>facts.roles.find(role=>role.code===item.roleCode)?.name||item.roleCode).join('、')||'未分配'}
function authorityScopes(user){return user.isSuperuser?'全部数据':(user.authorities||[]).map(item=>facts.scopeOptions.find(scope=>scope.code===item.scopeCode)?.name||item.scopeCode).join('、')||'未分配'}

const editorVisible=ref(false),editorForm=reactive({}),editorActor=ref(null),maintenanceRef=ref(null)
const actionByTab={users:'SAVE_USER',roles:'SAVE_ROLE'}
const availableAccountEmployees=computed(()=>{if(!editorForm.id)return facts.accountLinkEmployees;const currentId=Number(editorForm.employee?.id||editorForm.employeeId);return facts.employees.filter(row=>Number(row.id)===currentId)})
const selectedAccountEmployee=computed(()=>facts.accountLinkEmployees.find(row=>Number(row.id)===Number(editorForm.employeeId))||facts.employees.find(row=>Number(row.id)===Number(editorForm.employeeId))||editorForm.employee||null)
function historicalOrganizationLabel(formalName,legacyName){if(formalName&&formalName!=='未维护')return formalName;if(legacyName&&legacyName!=='—')return `${legacyName}（历史）`;return '未维护'}
function accountEmployeeOptionLabel(row){if(!row)return '未选择员工';return [row.employeeNo,row.fullName,historicalOrganizationLabel(row.formalDepartmentName||row.departmentName,row.legacyDepartmentName),historicalOrganizationLabel(row.formalPositionName||row.positionName,row.legacyPositionName),row.statusLabel,row.organizationStatusLabel,row.accountLinkStatusLabel].filter(Boolean).join(' / ')}
const accountProvisioningDescription=computed(()=>{const row=selectedAccountEmployee.value;if(!row)return '';const organizationNote=row.organizationComplete?'正式组织链完整。':'组织关系待维护；历史部门/岗位仅用于识别，不作为正式组织事实。';return `${organizationNote}${row.accountProvisioningMessage||''}`})
const editorSaveDisabled=computed(()=>activeTab.value==='users'&&!editorForm.id&&(!selectedAccountEmployee.value||!selectedAccountEmployee.value.accountProvisioningEligible))
function resetObject(target,value){Object.keys(target).forEach(key=>delete target[key]);Object.assign(target,value)}
function currentActor(profile=facts.currentUser){const identity=profile?.identity||{};return{userId:Number(identity.userId??profile?.userId??0),username:String(identity.username||'')}}
function clearSensitiveEditor(){editorForm.password='';editorForm.passwordConfirm='';editorForm.passwordChangeRequested=false}
function goToEmployeeAccountMaintenance(){clearSensitiveEditor();editorVisible.value=false;selectTab('employees')}
async function invalidateEditorForIdentityChange(){if(!editorVisible.value)return;clearSensitiveEditor();editorVisible.value=false;ElMessage.warning('当前登录身份已变化，已清除未保存密码并关闭编辑窗口；请按当前身份重新进入。');await refresh()}
async function openEditor(row={}){if(organizationTabs.includes(activeTab.value)){if(activeTab.value==='positions'){const result=await loadJobFamilyOptions(()=>accessControlApi.enterpriseOrganizationModel());jobFamilyLoadStatus.value=result.status;if(result.status===JOB_FAMILY_LOAD_STATUS.READ_FAILED){facts.jobFamilies=[];loadError.value=result.error;ElMessage.error(result.error);return}facts.jobFamilies=result.options;loadError.value=''}maintenanceRef.value?.open(activeTab.value,row);return}const companyId=row.companyId||facts.companies[0]?.id||null;resetObject(editorForm,{...row,companyId,isActive:row.isActive!==false,password:'',passwordConfirm:'',passwordChangeRequested:false,reason:'',employeeId:row.employee?.id||null});editorActor.value=currentActor();editorVisible.value=true}
function syncNewAccountEmployee(){if(editorForm.id)return;const employee=selectedAccountEmployee.value;editorForm.realName=employee?.fullName||'';editorForm.companyId=operatingCompany.value?.id||null;editorForm.username=employee?.suggestedUsername||''}
async function saveEditor(){if(activeTab.value==='users'){if(!String(editorForm.reason||'').trim())return ElMessage.warning('请填写修改原因');if(!editorForm.id&&!editorForm.employeeId)return ElMessage.warning('请选择需要开户的员工');if(!editorForm.id&&!selectedAccountEmployee.value?.accountProvisioningEligible)return ElMessage.warning(selectedAccountEmployee.value?.accountProvisioningMessage||'该员工当前不满足账户建立条件');if(editorForm.id&&editorForm.passwordChangeRequested&&editorForm.password!==editorForm.passwordConfirm)return ElMessage.warning('两次输入的密码不一致')}saving.value=true;try{const profileResponse=await accessControlApi.profile();const actual=profileResponse.success?currentActor(profileResponse.data):null;if(!actual||actual.userId!==editorActor.value?.userId||actual.username!==editorActor.value?.username){clearSensitiveEditor();editorVisible.value=false;throw new Error('当前登录身份已变化，未执行保存；未保存密码已清除，请按当前身份重新进入。')}const response=await accessControlApi.action(actionByTab[activeTab.value],{...editorForm,expectedActorId:editorActor.value.userId});if(!response.success)throw new Error(response.error?.message||'保存失败');const saved=response.data?.result;if(activeTab.value==='users'&&editorForm.id&&editorForm.passwordChangeRequested&&saved?.credentialVerification!=='PERSISTED_AND_VERIFIED')throw new Error('服务端未返回密码持久化回读校验，不能确认重置成功。请勿登录，联系管理员核对运行版本。');if(activeTab.value==='roles')ElMessage.success(`角色已保存，正式编码：${saved?.code||'已由系统生成'}`);else if(!editorForm.id)ElMessage.success(`账户已创建：${saved?.username||'请刷新查看'}；当前为待设置初始密码`);else ElMessage.success(editorForm.passwordChangeRequested?'密码已写入并通过服务端回读校验；账户资料已保存':'账户资料已保存，原密码保持不变');editorVisible.value=false;await refresh()}catch(error){ElMessage.error(error.message||String(error))}finally{saving.value=false}}

const permissionVisible=ref(false),permissionRoleId=ref(null),selectedPermissionCodes=ref([]),permissionReason=ref(''),permissionSearch=ref('')
const filteredPermissions=computed(()=>{const query=permissionSearch.value.trim().toLowerCase();return query?facts.permissions.filter(row=>`${row.code} ${row.name} ${row.module}`.toLowerCase().includes(query)):facts.permissions})
const groupedPermissions=computed(()=>{const ordered=['生产可行性评审—评审事项权限','生产可行性评审—操作权限','其他权限'];return ordered.map(label=>({label,rows:filteredPermissions.value.filter(row=>(row.permissionGroupLabel||'其他权限')===label)})).filter(group=>group.rows.length)})
function openPermissionEditor(role){permissionRoleId.value=role?.id||facts.roles.find(item=>item.code==='direct_purchase_authorized')?.id||facts.roles[0]?.id||null;permissionReason.value='';permissionSearch.value='';syncPermissionSelection();permissionVisible.value=true}
function syncPermissionSelection(){selectedPermissionCodes.value=[...(facts.roles.find(row=>row.id===permissionRoleId.value)?.permissionCodes||[])]}
async function savePermissions(){saving.value=true;try{const response=await accessControlApi.action('SET_ROLE_PERMISSIONS',{roleId:permissionRoleId.value,permissionCodes:selectedPermissionCodes.value,reason:permissionReason.value});if(!response.success)throw new Error(response.error?.message||'保存失败');ElMessage.success('角色权限已保存并形成审计');permissionVisible.value=false;await refresh()}catch(error){ElMessage.error(error.message||String(error))}finally{saving.value=false}}

const authorityVisible=ref(false),authorityUserId=ref(null),authorityRows=ref([]),authorityReason=ref(''),nonAdminUsers=computed(()=>facts.users.filter(row=>!row.isSuperuser))
function defaultAuthority() {
  const user = facts.users.find(row => row.id === authorityUserId.value)
  return { roleCode: 'buyer', scopeCode: 'SELF', departmentId: null, legalEntityId: String(user?.companyId ?? '') }
}
function openAuthorityEditor(user){authorityUserId.value=user?.id||nonAdminUsers.value[0]?.id||null;authorityReason.value='';syncAuthorityRows();authorityVisible.value=true}
function syncAuthorityRows(){const user=facts.users.find(row=>row.id===authorityUserId.value);authorityRows.value=(user?.authorities||[]).map(row=>({...row,departmentId:['SELF','ALL',''].includes(String(row.departmentId))?null:Number(row.departmentId)}));if(!authorityRows.value.length)authorityRows.value=[defaultAuthority()]}
async function saveAuthorities(){saving.value=true;try{const response=await accessControlApi.action('SET_USER_AUTHORITIES',{userId:authorityUserId.value,authorities:authorityRows.value,reason:authorityReason.value});if(!response.success)throw new Error(response.error?.message||'保存失败');ElMessage.success('用户角色与数据范围已保存并形成审计');authorityVisible.value=false;await refresh()}catch(error){ElMessage.error(error.message||String(error))}finally{saving.value=false}}

const reviewGrantVisible=ref(false),reviewGrantForm=reactive({})
function openReviewGrantEditor(row){resetObject(reviewGrantForm,{...row,reason:''});reviewGrantVisible.value=true}
async function saveReviewGrant(){if(!String(reviewGrantForm.reason||'').trim())return ElMessage.warning('请填写修改原因');saving.value=true;try{const response=await accessControlApi.action('SET_REVIEW_PARTICIPANT_GRANT',{grantId:reviewGrantForm.id,active:reviewGrantForm.active,canView:reviewGrantForm.canView,canMaintainOwnOpinion:reviewGrantForm.canMaintainOwnOpinion,canSignOwnItems:reviewGrantForm.canSignOwnItems,reason:reviewGrantForm.reason});if(!response.success)throw new Error(response.error?.message||'保存失败');ElMessage.success('评审对象授权已保存并形成审计');reviewGrantVisible.value=false;await refresh()}catch(error){ElMessage.error(error.message||String(error))}finally{saving.value=false}}

function onAuthenticationChanged(){invalidateEditorForIdentityChange()}
function onAuthenticationStorage(event){if(event.key==='token'||event.key==='pce_current_identity_v1')invalidateEditorForIdentityChange()}
onMounted(()=>{window.addEventListener('pce:authentication-changed',onAuthenticationChanged);window.addEventListener('storage',onAuthenticationStorage);refresh()})
onBeforeUnmount(()=>{window.removeEventListener('pce:authentication-changed',onAuthenticationChanged);window.removeEventListener('storage',onAuthenticationStorage)})
</script>

<style scoped>
.access-page{display:grid;gap:18px;padding:22px;background:#f4f7fb;min-width:0}.page-heading,.section-heading{display:flex;align-items:center;justify-content:space-between;gap:16px}.page-heading p,.page-heading h1,.page-heading span,.section-heading h2,.section-heading p{margin:0}.page-heading p{color:#2563eb;font-weight:800}.page-heading h1{margin:5px 0;font-size:28px}.page-heading span,.section-heading p{color:#64748b}.access-tabs,.heading-actions{display:flex;flex-wrap:wrap;gap:8px}.summary-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.summary-grid article,.list-card{padding:16px;border:1px solid #dce5ef;border-radius:10px;background:#fff}.summary-grid span,.summary-grid small{display:block;color:#64748b}.summary-grid strong{font-size:24px}.summary-grid .operating-company-card{grid-column:span 2;border-color:#86efac;background:#f0fdf4}.summary-grid .operating-company-card strong{font-size:19px}.list-card{display:grid;gap:14px}.permission-form{display:grid;grid-template-columns:1fr 1fr 1.4fr;gap:10px}.permission-form :deep(.el-form-item){margin-bottom:8px}.permission-groups{display:grid;gap:14px;max-height:48vh;overflow:auto;margin-top:12px}.permission-group{display:grid;gap:8px}.permission-group h3{margin:0;color:#334155}.permission-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.permission-grid :deep(.el-checkbox){height:auto;align-items:flex-start}.permission-grid small{display:block;color:#64748b}.authority-row{display:grid;grid-template-columns:1.2fr 1fr 1fr auto;gap:10px;margin-bottom:10px}@media(max-width:1100px){.summary-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:720px){.page-heading,.section-heading{align-items:flex-start;flex-direction:column}.summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.summary-grid .operating-company-card{grid-column:span 2}.permission-form,.permission-grid,.authority-row{grid-template-columns:1fr}}
.governance-note,.audit-card{padding:16px;border:1px solid #dce5ef;border-radius:10px;background:#fff}.governance-note{display:grid;gap:5px;border-color:#86efac;background:#f0fdf4}.governance-note span,.audit-card span,.audit-card small{color:#64748b}.audit-card{display:grid;gap:9px}.audit-card h2{margin:0}.audit-card article{display:grid;grid-template-columns:220px 1fr auto;gap:12px;padding:10px;background:#f8fafc;border-radius:8px}@media(max-width:720px){.audit-card article{grid-template-columns:1fr}}
.detail-section{margin-top:18px}.detail-section h3{margin:0 0 10px}
.restricted-summary{grid-template-columns:repeat(3,minmax(0,1fr))}.restricted-summary strong{font-size:18px}
.load-state-card{justify-items:start;border-color:#fca5a5;background:#fff7f7}.load-state-card h2,.load-state-card p{margin:0}.load-state-card p{color:#475569}.load-error-code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:13px}
</style>

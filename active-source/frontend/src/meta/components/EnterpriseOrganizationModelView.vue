<template>
  <main class="enterprise-organization-model" :data-page-code="definition.pageCode"
    :data-action-code="ACTION_CODE" data-fact-source="server">
    <header class="model-heading" data-acceptance-id="organization-model-heading">
      <div>
        <p>PCE Enterprise Organization Model V1 · ERP 组织经营基础</p>
        <h1>{{ definition.title }}</h1>
        <span>{{ definition.description }}</span>
      </div>
      <PceBusinessStatus status-code="READ_ONLY" status-label="综合查看与诊断" source="server" />
    </header>

    <nav class="model-navigation" aria-label="组织经营模型页面导航">
      <button v-for="item in navigation" :key="item.route" type="button"
        :class="{ active: item.view === view }" @click="router.push(item.route)">{{ item.label }}</button>
    </nav>

    <el-alert v-if="loadError" :title="loadError" type="error" :closable="false" show-icon />
    <el-alert v-else-if="!permissionFact.executable" :title="permissionFact.disabledReason"
      type="warning" :closable="false" show-icon />
    <el-alert v-else title="统一授权已通过；本页只展示服务端组织事实、关系树与诊断。正式维护统一进入“组织与权限基础”。"
      type="success" :closable="false" show-icon />

    <section class="scope-context" data-acceptance-id="organization-model-scope-context">
      <span>当前角色：<strong>{{ profile.roles?.join('、') || '无' }}</strong></span>
      <span>数据范围：<strong>{{ profile.scopeCodes?.join('、') || '无' }}</strong></span>
      <span>授权决定：<strong>{{ model.authorization?.allowed ? 'ALLOW' : 'DENY' }}</strong></span>
      <span>事实来源：<strong>AuthorizationService / Server</strong></span>
    </section>

    <section class="model-summary" data-acceptance-id="organization-model-summary">
      <article><span>组织单元</span><strong>{{ strictFacts.organizationUnitCount ?? 0 }}</strong></article>
      <article><span>部门</span><strong>{{ strictFacts.departmentCount ?? 0 }}</strong></article>
      <article><span>岗位</span><strong>{{ strictFacts.positionCount ?? 0 }}</strong></article>
      <article><span>员工</span><strong>{{ strictFacts.employeeCount ?? 0 }}</strong></article>
      <article><span>流程责任</span><strong>{{ strictFacts.workflowResponsibilityCount ?? 0 }}</strong></article>
      <article><span>业务写入</span><strong>{{ strictFacts.authorizedBusinessWriteCount ?? 0 }}</strong></article>
    </section>

    <section class="maintenance-entry" data-acceptance-id="organization-operating-maintenance-entry">
      <div>
        <h2>唯一正式管理员入口</h2>
        <p>本页不再写入组织事实。部门、岗位、员工、职责与流程责任统一在“组织与权限基础”维护。</p>
      </div>
      <div class="permission-tags">
        <span v-for="item in visibleManageActions" :key="item.code"
          :class="{ allowed: item.allowed }">{{ item.label }} · {{ item.allowed ? 'ALLOW' : 'DENY' }}</span>
      </div>
      <el-button type="primary" :disabled="!hasAnyManagePermission" @click="router.push({path:'/organization',query:{tab:view==='department'?'departments':view==='position'?'positions':'departments'}})">
        {{ hasAnyManagePermission ? '前往唯一正式维护入口' : '当前身份只读' }}
      </el-button>
    </section>

    <section class="hierarchy-region" data-acceptance-id="organization-hierarchy-tree">
      <div class="section-title">
        <div><h2>{{ definition.treeTitle }}</h2><p>{{ definition.treeDescription }}</p></div>
        <span>{{ model.contractVersion || 'PCE-ENTERPRISE-ORGANIZATION-MODEL-V1' }}</span>
      </div>
      <div v-if="treeRows.length" class="hierarchy-tree">
        <article v-for="row in treeRows" :key="`${view}-${row.id}`"
          class="hierarchy-node" :style="{ '--tree-depth': row.depth || 0 }">
          <strong>{{ row.name }}</strong>
          <span>{{ row.treeMeta }}</span>
          <small>{{ row.pathText || row.parentName || '顶层' }}</small>
        </article>
      </div>
      <p v-else class="empty-state">当前权限范围内暂无可显示的层级事实。</p>
    </section>

    <section class="model-list" :data-acceptance-id="`${definition.pageCode}-list`">
      <PceEnterpriseListTable
        ref="tableRef" :contract="enterpriseListContract" :page-id="definition.pageCode"
        :table-id="`${definition.pageCode}-table`" :rows="rows" :table-rows="filteredRows"
        :filter-schema="filterSchema" :filters="filters" :quick-search="quickSearch"
        :advanced-visible="advancedVisible" :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount" :sort-text="sortText"
        primary-field="code" :primary-label="definition.primaryLabel" primary-width="190"
        min-width="1560px" :show-refresh="true" :refreshing="loading" :show-actions="false"
        @update:quick-search="quickSearch=$event" @search="appliedSearch=quickSearch"
        @toggle-advanced="advancedVisible=!advancedVisible" @clear-filters="clearFilters"
        @clear-sort="clearSort" @export-current="exportCurrent" @clear-selection="clearSelection"
        @update-filter="updateFilter" @selection-change="selectedRows=$event" @refresh="refresh"
      >
        <template #columns>
          <el-table-column v-for="column in definition.columns" :key="column.field"
            :prop="column.field" :label="column.label" :width="column.width"
            show-overflow-tooltip />
        </template>
      </PceEnterpriseListTable>
    </section>

    <section v-if="view === 'organization'" class="evidence-region"
      data-acceptance-id="employee-reporting-evidence">
      <div class="section-title"><div><h2>员工组织归属与汇报关系</h2><p>直属主管负责日常工作安排和管理；职能主管负责专业指导和业务规范管理。两类关系均来自正式员工汇报关系。</p></div></div>
      <div class="evidence-grid">
        <article v-for="employee in employeeEvidenceRows" :key="employee.id">
          <strong>{{ employee.employeeNo }} · {{ employee.fullName }}</strong>
          <span>部门：{{ employee.departmentName }}</span>
          <span>岗位：{{ employee.positionName }}</span>
          <span>直属主管：{{ employee.directManagerDisplay }}</span>
          <span>职能主管：{{ employee.functionalManagerDisplay }}</span>
        </article>
      </div>
      <p v-if="!employeeEvidenceRows.length" class="empty-state">当前权限范围内暂无员工归属事实。</p>
    </section>

    <section v-if="view === 'position'" class="evidence-region"
      data-acceptance-id="workflow-responsibility-evidence">
      <div class="section-title"><div><h2>岗位流程责任接口</h2><p>流程按岗位责任解析候选人员；本页面不执行审批或状态推进。</p></div></div>
      <div class="evidence-grid">
        <article v-for="mapping in workflowEvidenceRows" :key="mapping.id">
          <strong>{{ mapping.positionName }} · {{ mapping.ownershipTypeLabel }}</strong>
          <span>流程：{{ mapping.workflowCode }}</span>
          <span>节点：{{ mapping.nodeCode }}</span>
          <span>职责：{{ mapping.responsibilityName || '未关联具体职责' }}</span>
        </article>
      </div>
      <p v-if="!workflowEvidenceRows.length" class="empty-state">接口已经建立，当前正式数据尚未维护流程责任映射。</p>
    </section>

    <section class="audit-region" data-acceptance-id="organization-operating-audit-list">
      <div class="section-title"><div><h2>最近维护审计</h2><p>正式保存产生的操作者、时间、对象和修改原因来自服务端审计事实。</p></div></div>
      <div class="audit-list">
        <article v-for="audit in (model.audits || []).slice(0, 10)" :key="audit.id">
          <strong>{{ audit.targetLabel }}</strong>
          <span>{{ audit.actionCode }} · {{ audit.actorName }} · {{ formatTime(audit.createdAt) }}</span>
          <small>修改原因：{{ audit.reason }}</small>
        </article>
      </div>
      <p v-if="!model.audits?.length" class="empty-state">当前尚无组织运作维护审计。</p>
    </section>

    <el-dialog v-if="false" v-model="maintenanceVisible" title="已停用：请使用 /organization 正式管理员入口" width="min(980px, 94vw)"
      destroy-on-close data-acceptance-id="organization-operating-maintenance-dialog">
      <el-alert v-if="saveError" :title="saveError" type="error" :closable="false" show-icon />
      <el-alert v-if="writeResult" :title="writeResult" type="success" :closable="false" show-icon />

      <el-tabs v-if="view === 'organization'" v-model="maintenanceTab">
        <el-tab-pane label="组织单元" name="organization-unit">
          <el-form label-width="130px" class="maintenance-form">
            <el-form-item label="选择现有组织单元"><el-select v-model="organizationForm.id" clearable filterable @change="loadOrganizationForm">
              <el-option v-for="row in model.organizationUnits" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" />
            </el-select></el-form-item>
            <el-form-item label="组织单元编码"><el-input :model-value="organizationForm.id ? organizationForm.code : '系统自动生成'" disabled /></el-form-item>
            <el-form-item label="组织单元名称"><el-input v-model="organizationForm.name" /></el-form-item>
            <el-form-item label="组织单元类型"><el-select v-model="organizationForm.unitType"><el-option v-for="item in unitTypes" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
            <el-form-item label="上级组织单元"><el-select v-model="organizationForm.parentId" clearable filterable><el-option v-for="row in model.organizationUnits.filter(item => item.id !== organizationForm.id)" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
            <el-form-item label="所属公司"><el-input :model-value="model.company?.name" disabled /></el-form-item>
            <el-form-item label="有效期"><div class="date-pair"><el-date-picker v-model="organizationForm.effectiveFrom" value-format="YYYY-MM-DD" placeholder="生效日期" /><el-date-picker v-model="organizationForm.effectiveTo" value-format="YYYY-MM-DD" placeholder="失效日期" /></div></el-form-item>
            <el-form-item label="启用"><el-switch v-model="organizationForm.active" /></el-form-item>
            <el-form-item label="修改原因"><el-input v-model="organizationForm.reason" type="textarea" placeholder="必填，进入正式审计" /></el-form-item>
            <el-form-item><el-button type="primary" :loading="saving" @click="saveAction('SAVE_ORGANIZATION_UNIT', organizationForm)">保存并回读</el-button></el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <el-tabs v-else-if="view === 'department'" v-model="maintenanceTab">
        <el-tab-pane label="部门关系与责任岗位" name="department">
          <el-form label-width="130px" class="maintenance-form">
            <el-form-item label="部门"><el-select v-model="departmentForm.departmentId" filterable @change="loadDepartmentForm"><el-option v-for="row in model.departments" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
            <el-form-item label="部门编码"><el-input :model-value="departmentForm.departmentId ? departmentForm.code : '系统自动生成'" disabled /></el-form-item>
            <el-form-item label="部门名称"><el-input v-model="departmentForm.name" /></el-form-item>
            <el-form-item label="上级部门"><el-select v-model="departmentForm.parentId" clearable filterable><el-option v-for="row in model.departments.filter(item => item.id !== departmentForm.departmentId)" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
            <el-form-item label="部门类型"><el-select v-model="departmentForm.departmentType"><el-option v-for="item in departmentTypes" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
            <el-form-item label="组织单元"><el-select v-model="departmentForm.organizationUnitId" clearable filterable><el-option v-for="row in model.organizationUnits" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
            <el-form-item label="责任岗位"><el-select v-model="departmentForm.responsiblePositionId" clearable filterable><el-option v-for="row in model.positions" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
            <el-form-item label="有效期"><div class="date-pair"><el-date-picker v-model="departmentForm.effectiveFrom" value-format="YYYY-MM-DD" placeholder="生效日期" /><el-date-picker v-model="departmentForm.effectiveTo" value-format="YYYY-MM-DD" placeholder="失效日期" /></div></el-form-item>
            <el-form-item label="启用"><el-switch v-model="departmentForm.active" /></el-form-item>
            <el-form-item label="修改原因"><el-input v-model="departmentForm.reason" type="textarea" placeholder="必填，进入正式审计" /></el-form-item>
            <el-form-item><el-button type="primary" :loading="saving" @click="saveAction('SAVE_DEPARTMENT', departmentForm)">保存部门关系并回读</el-button></el-form-item>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="部门实际负责人" name="department-leader">
          <el-form label-width="130px" class="maintenance-form">
            <el-form-item label="部门"><el-select v-model="leaderForm.departmentId" filterable @change="loadLeaderForm"><el-option v-for="row in model.departments" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
            <el-form-item label="实际负责人"><el-select v-model="leaderForm.leaderEmployeeId" clearable filterable><el-option v-for="row in model.employees" :key="row.id" :label="`${row.employeeNo} · ${row.fullName}`" :value="row.id" /></el-select></el-form-item>
            <el-form-item label="有效期"><div class="date-pair"><el-date-picker v-model="leaderForm.effectiveFrom" value-format="YYYY-MM-DD" placeholder="生效日期" /><el-date-picker v-model="leaderForm.effectiveTo" value-format="YYYY-MM-DD" placeholder="失效日期" /></div></el-form-item>
            <el-form-item label="修改原因"><el-input v-model="leaderForm.reason" type="textarea" placeholder="必填，进入正式审计" /></el-form-item>
            <el-form-item><el-button type="primary" :loading="saving" @click="saveAction('SAVE_DEPARTMENT_LEADER', leaderForm)">保存实际负责人并回读</el-button></el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <el-tabs v-else v-model="maintenanceTab">
        <el-tab-pane label="岗位层级与默认角色" name="position">
          <el-form label-width="130px" class="maintenance-form">
            <el-form-item label="岗位"><el-select v-model="positionForm.positionId" filterable @change="loadPositionForm"><el-option v-for="row in model.positions" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
            <el-form-item label="岗位编码"><el-input :model-value="positionForm.positionId ? positionForm.code : '系统自动生成'" disabled /></el-form-item><el-form-item label="岗位名称"><el-input v-model="positionForm.name" /></el-form-item>
            <el-form-item label="岗位族"><el-select v-model="positionForm.jobFamilyId" clearable filterable><el-option v-for="row in model.jobFamilies" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
            <el-form-item label="岗位等级"><el-select v-model="positionForm.jobLevelId" clearable filterable><el-option v-for="row in model.jobLevels" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
            <el-form-item label="上级岗位"><el-select v-model="positionForm.parentPositionId" clearable filterable><el-option v-for="row in model.positions.filter(item => item.id !== positionForm.positionId)" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
            <el-form-item label="默认系统角色"><el-select v-model="positionForm.defaultRoleId" clearable filterable><el-option v-for="row in model.roles" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
            <el-form-item label="岗位说明"><el-input v-model="positionForm.description" type="textarea" /></el-form-item>
            <el-form-item label="职责摘要"><el-input v-model="positionForm.responsibilitySummary" type="textarea" /></el-form-item>
            <el-form-item label="启用"><el-switch v-model="positionForm.active" /></el-form-item>
            <el-form-item label="修改原因"><el-input v-model="positionForm.reason" type="textarea" placeholder="必填，进入正式审计" /></el-form-item>
            <el-form-item><el-button type="primary" :loading="saving" @click="saveAction('SAVE_POSITION', positionForm)">保存岗位并回读</el-button></el-form-item>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="岗位族" name="job-family">
          <el-form label-width="130px" class="maintenance-form"><el-form-item label="选择现有岗位族"><el-select v-model="jobFamilyForm.id" clearable filterable @change="loadJobFamilyForm"><el-option v-for="row in model.jobFamilies" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item><el-form-item label="岗位族编码"><el-input :model-value="jobFamilyForm.id ? jobFamilyForm.code : '系统自动生成'" disabled /></el-form-item><el-form-item label="岗位族名称"><el-input v-model="jobFamilyForm.name" /></el-form-item><el-form-item label="说明"><el-input v-model="jobFamilyForm.description" type="textarea" /></el-form-item><el-form-item label="启用"><el-switch v-model="jobFamilyForm.active" /></el-form-item><el-form-item label="修改原因"><el-input v-model="jobFamilyForm.reason" type="textarea" placeholder="必填，进入正式审计" /></el-form-item><el-form-item><el-button type="primary" :loading="saving" @click="saveAction('SAVE_JOB_FAMILY', jobFamilyForm)">保存岗位族</el-button></el-form-item></el-form>
        </el-tab-pane>
        <el-tab-pane label="岗位等级" name="job-level">
          <el-form label-width="130px" class="maintenance-form"><el-form-item label="选择现有等级"><el-select v-model="jobLevelForm.id" clearable filterable @change="loadJobLevelForm"><el-option v-for="row in model.jobLevels" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item>
            <el-form-item label="等级编码"><el-input :model-value="jobLevelForm.id ? jobLevelForm.code : '系统自动生成'" disabled /></el-form-item><el-form-item label="等级名称"><el-input v-model="jobLevelForm.name" /></el-form-item><el-form-item label="等级顺序"><el-input-number v-model="jobLevelForm.rank" :min="1" /></el-form-item><el-form-item label="说明"><el-input v-model="jobLevelForm.description" type="textarea" /></el-form-item><el-form-item label="启用"><el-switch v-model="jobLevelForm.active" /></el-form-item><el-form-item label="修改原因"><el-input v-model="jobLevelForm.reason" type="textarea" placeholder="必填，进入正式审计" /></el-form-item><el-form-item><el-button type="primary" :loading="saving" @click="saveAction('SAVE_JOB_LEVEL', jobLevelForm)">保存岗位等级</el-button></el-form-item></el-form>
        </el-tab-pane>
        <el-tab-pane label="责任查看" name="responsibility">
          <el-alert title="此处只显示服务端责任事实；正式维护请进入“组织与权限基础 → 岗位 → 责任管理”。" type="info" :closable="false" show-icon />
          <el-table :data="model.responsibilities" style="width:100%;margin-top:16px"><el-table-column prop="code" label="责任编码" min-width="210" /><el-table-column prop="name" label="责任名称" min-width="180" /><el-table-column prop="businessDomain" label="业务领域" min-width="130" /><el-table-column prop="statusLabel" label="责任状态" width="100" /><el-table-column prop="effectiveFrom" label="生效日期" width="120" /><el-table-column prop="effectiveTo" label="失效日期" width="120" /></el-table>
        </el-tab-pane>
        <el-tab-pane label="岗位责任查看" name="position-responsibility">
          <el-alert title="岗位责任只在正式组织入口维护；此处沿用同一服务端投影进行综合查看。" type="info" :closable="false" show-icon />
          <el-table :data="model.positions" style="width:100%;margin-top:16px"><el-table-column prop="code" label="岗位编码" min-width="160" /><el-table-column prop="name" label="岗位名称" min-width="160" /><el-table-column prop="responsibilityText" label="岗位责任" min-width="320" /></el-table>
        </el-tab-pane>
        <el-tab-pane label="员工汇报" name="reporting">
          <el-alert :title="reportingForm.relationType==='DIRECT'?'直属主管：员工日常汇报对象，负责日常工作安排和管理。':'职能主管：员工专业领域负责人，负责专业指导和业务规范管理。'" type="info" :closable="false" show-icon />
          <el-form label-width="130px" class="maintenance-form"><el-form-item label="员工"><el-select v-model="reportingForm.employeeId" filterable><el-option v-for="row in model.employees" :key="row.id" :label="employeeManagerLabel(row)" :value="row.id" /></el-select></el-form-item><el-form-item label="汇报类型"><el-select v-model="reportingForm.relationType"><el-option label="直属主管" value="DIRECT" /><el-option label="职能主管" value="FUNCTIONAL" /></el-select></el-form-item><el-form-item :label="reportingForm.relationType==='DIRECT'?'直属主管':'职能主管'"><el-select v-model="reportingForm.managerId" filterable placeholder="选择员工"><el-option v-for="row in model.employees.filter(item => item.id !== reportingForm.employeeId)" :key="row.id" :label="employeeManagerLabel(row)" :value="row.id" /></el-select></el-form-item><el-form-item label="有效期"><div class="date-pair"><el-date-picker v-model="reportingForm.effectiveFrom" value-format="YYYY-MM-DD" placeholder="生效日期" /><el-date-picker v-model="reportingForm.effectiveTo" value-format="YYYY-MM-DD" placeholder="失效日期" /></div></el-form-item><el-form-item label="启用"><el-switch v-model="reportingForm.active" /></el-form-item><el-form-item label="修改原因"><el-input v-model="reportingForm.reason" type="textarea" placeholder="必填，进入正式审计" /></el-form-item><el-form-item><el-button type="primary" :loading="saving" @click="saveAction('SAVE_REPORTING_RELATION', reportingForm)">保存汇报关系</el-button></el-form-item></el-form>
        </el-tab-pane>
        <el-tab-pane label="流程责任" name="workflow">
          <el-form label-width="130px" class="maintenance-form"><el-form-item label="选择现有映射"><el-select v-model="workflowForm.id" clearable filterable @change="loadWorkflowForm"><el-option v-for="row in model.workflowResponsibilities" :key="row.id" :label="`${row.positionName} · ${row.workflowCode}/${row.nodeCode}`" :value="row.id" /></el-select></el-form-item><el-form-item label="责任岗位"><el-select v-model="workflowForm.positionId" filterable><el-option v-for="row in model.positions" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item><el-form-item label="关联职责"><el-select v-model="workflowForm.responsibilityId" clearable filterable><el-option v-for="row in model.responsibilities" :key="row.id" :label="`${row.code} · ${row.name}`" :value="row.id" /></el-select></el-form-item><el-form-item label="正式流程节点"><el-select v-model="workflowForm.workflowNodeId" filterable><el-option v-for="row in model.workflowNodes" :key="row.id" :label="`${row.workflowCode}/${row.nodeCode} · ${row.nodeName} · ${row.businessActionCode}`" :value="row.id" /></el-select></el-form-item><el-form-item label="责任类型"><el-select v-model="workflowForm.ownershipType"><el-option v-for="item in ownershipTypes" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item><el-form-item label="有效期"><div class="date-pair"><el-date-picker v-model="workflowForm.effectiveFrom" value-format="YYYY-MM-DD" placeholder="生效日期" /><el-date-picker v-model="workflowForm.effectiveTo" value-format="YYYY-MM-DD" placeholder="失效日期" /></div></el-form-item><el-form-item label="启用"><el-switch v-model="workflowForm.active" /></el-form-item><el-form-item label="修改原因"><el-input v-model="workflowForm.reason" type="textarea" placeholder="必填，进入正式审计" /></el-form-item><el-form-item><el-button type="primary" :loading="saving" @click="saveAction('SAVE_WORKFLOW_RESPONSIBILITY', workflowForm)">保存流程责任</el-button></el-form-item></el-form>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>

    <details class="diagnostic-region" data-acceptance-id="organization-model-diagnostics">
      <summary>查看诊断信息</summary>
      <pre>{{ diagnostics }}</pre>
    </details>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { accessControlApi } from '@/api/accessControl.js'
import {
  loadPermissionProfile,
  resolvePermissionFact,
} from '@/meta/runtime/permissionProfileRuntime.js'
import {
  createPceEnterpriseListContract,
  usePceEnterpriseListRuntime,
} from '@/meta/runtime/pceEnterpriseListContract.js'

const props = defineProps({ view: { type: String, required: true } })
const view = props.view
const ACTION_CODE = 'system.organization_directory.view'
const MANAGE_ACTIONS = Object.freeze([
  { code: 'system.organization.structure.manage', label: '组织单元维护', views: ['organization'] },
  { code: 'system.organization.department.manage', label: '部门关系维护', views: ['department'] },
  { code: 'system.organization.position.manage', label: '岗位体系维护', views: ['position'] },
  { code: 'system.organization.responsibility.manage', label: '岗位职责维护', views: ['position'] },
  { code: 'system.organization.reporting.manage', label: '员工汇报维护', views: ['position'] },
  { code: 'system.organization.workflow_responsibility.manage', label: '流程责任维护', views: ['position'] },
])
const unitTypes = Object.freeze([{ value: 'COMPANY', label: '公司' }, { value: 'BUSINESS_UNIT', label: '事业部' }, { value: 'CENTER', label: '管理中心/组织中心' }, { value: 'DEPARTMENT', label: '部门' }, { value: 'TEAM', label: '团队/班组' }])
const departmentTypes = Object.freeze([{ value: 'FUNCTIONAL', label: '职能部门' }, { value: 'BUSINESS', label: '业务部门' }, { value: 'PRODUCTION', label: '生产部门' }, { value: 'SUPPORT', label: '支持部门' }, { value: 'TEAM', label: '团队/班组' }])
const ownershipTypes = Object.freeze([{ value: 'OWNER', label: '负责' }, { value: 'APPROVER', label: '审批' }, { value: 'REVIEWER', label: '审核/复核' }, { value: 'EXECUTOR', label: '执行' }])
const router = useRouter()
const navigation = [
  { view: 'organization', label: '组织层级', route: '/organization-model' },
  { view: 'department', label: '部门体系', route: '/organization-model/departments' },
  { view: 'position', label: '岗位与职责', route: '/organization-model/positions' },
]
const definitions = {
  organization: {
    pageCode: 'enterprise-organization-model-v1', title: '企业组织经营模型',
    description: '统一展示 Company、Organization Unit、Department、Employee 与经营归属基础。',
    treeTitle: '组织层级树', treeDescription: 'Company → Organization Unit → Department → Team。',
    source: 'organizationUnits', primaryLabel: '组织单元编码', exportFile: 'enterprise-organization-units.csv',
    filters: [
      { field: 'code', label: '组织编码', filterType: 'text' },
      { field: 'name', label: '组织名称', filterType: 'text' },
      { field: 'unitTypeLabel', label: '组织类型', filterType: 'text' },
      { field: 'leaderEmployeeName', label: '组织实际负责人', filterType: 'text' },
    ],
    searchFields: ['code', 'name', 'unitTypeLabel', 'pathText', 'leaderEmployeeName'],
    columns: [
      { field: 'name', label: '组织名称', width: 200 }, { field: 'unitTypeLabel', label: '组织类型', width: 140 },
      { field: 'pathText', label: '组织路径', width: 360 }, { field: 'leaderEmployeeName', label: '组织实际负责人', width: 180 },
      { field: 'effectiveFrom', label: '生效日期', width: 140 }, { field: 'effectiveTo', label: '失效日期', width: 140 },
      { field: 'statusLabel', label: '组织状态', width: 110 },
    ],
  },
  department: {
    pageCode: 'enterprise-department-model-v1', title: '部门体系',
    description: '综合展示正式部门层级、责任岗位、实际负责人和组织单元。',
    treeTitle: '部门层级树', treeDescription: '部门父子关系直接来自 system.Department。',
    source: 'departments', primaryLabel: '部门编码', exportFile: 'enterprise-departments.csv',
    filters: [
      { field: 'code', label: '部门编码', filterType: 'text' },
      { field: 'name', label: '部门名称', filterType: 'text' },
      { field: 'departmentTypeLabel', label: '部门类型', filterType: 'text' },
      { field: 'leaderEmployeeName', label: '负责人', filterType: 'text' },
    ],
    searchFields: ['code', 'name', 'parentName', 'departmentTypeLabel', 'responsiblePositionName', 'leaderEmployeeName'],
    columns: [
      { field: 'name', label: '部门名称', width: 180 }, { field: 'parentName', label: '上级部门', width: 170 },
      { field: 'departmentTypeLabel', label: '部门类型', width: 140 }, { field: 'organizationUnitName', label: '组织单元', width: 190 },
      { field: 'responsiblePositionName', label: '责任岗位', width: 170 }, { field: 'leaderEmployeeName', label: '实际负责人', width: 170 },
      { field: 'employeeCount', label: '员工数', width: 100 }, { field: 'positionCount', label: '岗位数', width: 100 },
      { field: 'statusLabel', label: '部门状态', width: 100 },
    ],
  },
  position: {
    pageCode: 'enterprise-position-model-v1', title: '岗位与职责体系',
    description: 'Position、Job Family、Job Level、Responsibility、Default Role 与流程责任保持分层。',
    treeTitle: '岗位层级树', treeDescription: '岗位上级、岗位族与岗位等级来自正式模型。',
    source: 'positions', primaryLabel: '岗位编码', exportFile: 'enterprise-positions.csv',
    filters: [
      { field: 'code', label: '岗位编码', filterType: 'text' },
      { field: 'name', label: '岗位名称', filterType: 'text' },
      { field: 'departmentName', label: '所属部门', filterType: 'text' },
      { field: 'jobFamilyName', label: '岗位族', filterType: 'text' },
    ],
    searchFields: ['code', 'name', 'departmentName', 'jobFamilyName', 'jobLevelName', 'responsibilityText'],
    columns: [
      { field: 'name', label: '岗位名称', width: 180 }, { field: 'departmentName', label: '所属部门', width: 170 },
      { field: 'jobFamilyName', label: '岗位族', width: 170 }, { field: 'jobLevelName', label: '岗位等级', width: 140 },
      { field: 'parentPositionName', label: '上级岗位', width: 170 }, { field: 'defaultRoleName', label: '默认角色', width: 180 },
      { field: 'responsibilityText', label: '岗位职责', width: 260 }, { field: 'workflowResponsibilityText', label: '流程责任', width: 300 },
      { field: 'employeeCount', label: '任职人数', width: 110 }, { field: 'statusLabel', label: '岗位启用状态', width: 100 },
    ],
  },
}
const definition = definitions[view]
const loading = ref(false)
const loadError = ref('')
const rows = ref([])
const model = reactive({ company: {}, organizationUnits: [], departments: [], positions: [], employees: [], workflowResponsibilities: [], workflowNodes: [], jobFamilies: [], jobLevels: [], responsibilities: [], roles: [], audits: [] })
const strictFacts = reactive({})
const profile = reactive({ roles: [], scopeCodes: [], permissionCodes: [], actionFacts: {} })
const permissionFact = computed(() => resolvePermissionFact(profile, ACTION_CODE))
const visibleManageActions = computed(() => MANAGE_ACTIONS.filter(item => item.views.includes(view)).map(item => ({ ...item, allowed: resolvePermissionFact(profile, item.code).executable })))
const hasAnyManagePermission = computed(() => MANAGE_ACTIONS.some(item => resolvePermissionFact(profile, item.code).executable))
const viewManageAllowed = computed(() => visibleManageActions.value.some(item => item.allowed))
const maintenanceVisible = ref(false)
const maintenanceTab = ref(view === 'organization' ? 'organization-unit' : view === 'department' ? 'department' : 'position')
const saving = ref(false)
const saveError = ref('')
const writeResult = ref('')
const organizationForm = reactive({ id: null, code: '', name: '', unitType: 'DEPARTMENT', parentId: null, effectiveFrom: '', effectiveTo: '', active: true, reason: '' })
const departmentForm = reactive({ departmentId: null, code: '', name: '', parentId: null, departmentType: 'FUNCTIONAL', organizationUnitId: null, responsiblePositionId: null, effectiveFrom: '', effectiveTo: '', active: true, reason: '' })
const leaderForm = reactive({ departmentId: null, leaderEmployeeId: null, effectiveFrom: '', effectiveTo: '', reason: '' })
const positionForm = reactive({ positionId: null, code: '', name: '', jobFamilyId: null, jobLevelId: null, parentPositionId: null, defaultRoleId: null, description: '', responsibilitySummary: '', active: true, reason: '' })
const jobFamilyForm = reactive({ id: null, code: '', name: '', description: '', active: true, reason: '' })
const jobLevelForm = reactive({ id: null, code: '', name: '', rank: 1, description: '', active: true, reason: '' })
const responsibilityForm = reactive({ id: null, code: '', name: '', category: '', description: '', active: true, reason: '' })
const positionResponsibilityForm = reactive({ positionId: null, responsibilityId: null, isPrimary: false, active: true, reason: '' })
const reportingForm = reactive({ employeeId: null, managerId: null, relationType: 'DIRECT', effectiveFrom: '', effectiveTo: '', active: true, reason: '' })
const workflowForm = reactive({ id: null, positionId: null, responsibilityId: null, workflowNodeId: null, ownershipType: 'OWNER', effectiveFrom: '', effectiveTo: '', active: true, reason: '' })
const filterSchema = definition.filters
const enterpriseListContract = createPceEnterpriseListContract({
  pageCode: definition.pageCode, pageType: 'list', title: definition.title, moduleCode: 'SYSTEM',
})
const listRuntime = usePceEnterpriseListRuntime({
  rows, filterSchema, pageCode: definition.pageCode,
  searchFields: definition.searchFields, exportFileName: definition.exportFile,
  exportColumns: [{ field: 'code', label: definition.primaryLabel }, ...definition.columns],
})
const {
  selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef,
  activeFilterCount, sortText, filteredRows, clearFilters, clearSort, clearSelection, exportCurrent,
} = listRuntime
function updateFilter(field, value) { filters[field] = value }

const treeRows = computed(() => {
  if (view === 'organization') return (model.organizationUnits || []).map(row => ({
    ...row, treeMeta: `${row.unitTypeLabel} · ${row.leaderEmployeeName}`,
  }))
  if (view === 'department') {
    const byId = Object.fromEntries((model.departments || []).map(row => [row.id, row]))
    const depth = row => {
      let count = 0; let current = row; const seen = new Set([row.id])
      while (current.parentId && byId[current.parentId] && !seen.has(current.parentId)) {
        current = byId[current.parentId]; seen.add(current.id); count += 1
      }
      return count
    }
    return (model.departments || []).map(row => ({
      ...row, depth: depth(row), pathText: row.parentName ? `${row.parentName} / ${row.name}` : row.name,
      treeMeta: `${row.departmentTypeLabel} · 责任岗位 ${row.responsiblePositionName} · 实际负责人 ${row.leaderEmployeeName}`,
    }))
  }
  const byId = Object.fromEntries((model.positions || []).map(row => [row.id, row]))
  const positionPath = row => {
    const names = [row.name]; let current = row; const seen = new Set([row.id])
    while (current.parentPositionId && byId[current.parentPositionId] && !seen.has(current.parentPositionId)) {
      current = byId[current.parentPositionId]; seen.add(current.id); names.unshift(current.name)
    }
    return names
  }
  return (model.positions || []).map(row => ({
    ...row, depth: positionPath(row).length - 1,
    pathText: positionPath(row).join(' / '),
    treeMeta: `${row.jobFamilyName} · ${row.jobLevelName}`,
  }))
})
const employeeEvidenceRows = computed(() => (model.employees || []).slice(0, 8))
const workflowEvidenceRows = computed(() => (model.workflowResponsibilities || []).slice(0, 8))
const diagnostics = computed(() => JSON.stringify({
  pageCode: definition.pageCode, actionCode: ACTION_CODE,
  factSource: strictFacts.factSource, factLoadStatus: strictFacts.factLoadStatus,
  resultCount: rows.value.length, strictFacts,
}, null, 2))

function isActive(row) { return row?.statusLabel === '启用' }
function formatTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '' }
function employeeManagerLabel(row) { return `${row.fullName}（${row.positionName || '岗位待维护'}）· ${row.employeeNo}` }
function openMaintenance() {
  saveError.value = ''
  writeResult.value = ''
  maintenanceTab.value = view === 'organization' ? 'organization-unit' : view === 'department' ? 'department' : 'position'
  maintenanceVisible.value = true
  if (view === 'organization' && !organizationForm.id && model.organizationUnits[0]) { organizationForm.id = model.organizationUnits[0].id; loadOrganizationForm(organizationForm.id) }
  if (view === 'department' && !departmentForm.departmentId && model.departments[0]) { departmentForm.departmentId = model.departments[0].id; loadDepartmentForm(departmentForm.departmentId); leaderForm.departmentId = departmentForm.departmentId; loadLeaderForm(leaderForm.departmentId) }
  if (view === 'position' && !positionForm.positionId && model.positions[0]) { positionForm.positionId = model.positions[0].id; loadPositionForm(positionForm.positionId) }
}
function loadOrganizationForm(id) {
  if (!id) { Object.assign(organizationForm, { id: null, code: '', name: '', unitType: 'DEPARTMENT', parentId: null, effectiveFrom: '', effectiveTo: '', active: true }); return }
  const row = model.organizationUnits.find(item => item.id === id); if (!row) return
  Object.assign(organizationForm, { id: row.id, code: row.code, name: row.name, unitType: row.unitType, parentId: row.parentId, effectiveFrom: row.effectiveFrom || '', effectiveTo: row.effectiveTo || '', active: isActive(row) })
}
function loadDepartmentForm(id) {
  const row = model.departments.find(item => item.id === id); if (!row) return
  Object.assign(departmentForm, { departmentId: row.id, code: row.code, name: row.name, parentId: row.parentId, departmentType: row.departmentType, organizationUnitId: row.organizationUnitId, responsiblePositionId: row.responsiblePositionId, effectiveFrom: row.effectiveFrom || '', effectiveTo: row.effectiveTo || '', active: isActive(row) })
}
function loadLeaderForm(id) {
  const row = model.departments.find(item => item.id === id); if (!row) return
  Object.assign(leaderForm, { departmentId: row.id, leaderEmployeeId: row.leaderEmployeeId, effectiveFrom: '', effectiveTo: '' })
}
function loadPositionForm(id) {
  const row = model.positions.find(item => item.id === id); if (!row) return
  Object.assign(positionForm, { positionId: row.id, code: row.code, name: row.name, jobFamilyId: row.jobFamilyId, jobLevelId: row.jobLevelId, parentPositionId: row.parentPositionId, defaultRoleId: row.defaultRoleId, description: row.description || '', responsibilitySummary: row.responsibilitySummary || '', active: isActive(row) })
}
function loadJobFamilyForm(id) { const row = model.jobFamilies.find(item => item.id === id); if (row) Object.assign(jobFamilyForm, { ...row, active: isActive(row) }); else Object.assign(jobFamilyForm, { id: null, code: '', name: '', description: '', active: true }) }
function loadJobLevelForm(id) { const row = model.jobLevels.find(item => item.id === id); if (row) Object.assign(jobLevelForm, { ...row, active: isActive(row) }); else Object.assign(jobLevelForm, { id: null, code: '', name: '', rank: 1, description: '', active: true }) }
function loadResponsibilityForm(id) { const row = model.responsibilities.find(item => item.id === id); if (row) Object.assign(responsibilityForm, { ...row, active: isActive(row) }); else Object.assign(responsibilityForm, { id: null, code: '', name: '', category: '', description: '', active: true }) }
function loadWorkflowForm(id) {
  const row = model.workflowResponsibilities.find(item => item.id === id); if (!row) { Object.assign(workflowForm, { id: null, positionId: null, responsibilityId: null, workflowNodeId: null, ownershipType: 'OWNER', effectiveFrom: '', effectiveTo: '', active: true }); return }
  Object.assign(workflowForm, { id: row.id, positionId: row.positionId, responsibilityId: model.responsibilities.find(item => item.code === row.responsibilityCode)?.id || null, workflowNodeId: row.workflowNodeId || null, ownershipType: row.ownershipType, effectiveFrom: row.effectiveFrom || '', effectiveTo: row.effectiveTo || '', active: isActive(row) })
}
async function saveAction(action, form) {
  saving.value = true; saveError.value = ''; writeResult.value = ''
  try {
    const response = await accessControlApi.saveEnterpriseOrganizationModel(action, { ...form })
    if (!response?.success) throw new Error(response?.error?.message || '组织运作维护保存失败。')
    writeResult.value = `保存成功；审计记录 #${response.data?.auditId}，服务端写入计数 ${response.data?.writeCount ?? 0}。`
    await refresh()
  } catch (error) {
    const responseError = error?.response?.data?.error
    const conflictPrefix = error?.response?.status === 409 && responseError?.code
      ? `请求冲突（${responseError.code}）：`
      : ''
    saveError.value = `${conflictPrefix}${responseError?.message || error?.message || String(error)}`
  } finally { saving.value = false }
}

async function refresh() {
  loading.value = true
  loadError.value = ''
  rows.value = []
  try {
    const loadedProfile = await loadPermissionProfile({ force: true })
    Object.assign(profile, loadedProfile)
    if (!permissionFact.value.executable) return
    const response = await accessControlApi.enterpriseOrganizationModel()
    if (!response?.success) throw new Error(response?.error?.message || '企业组织经营模型读取失败。')
    Object.assign(model, response.data || {})
    Object.assign(strictFacts, response.data?.strictFacts || {})
    rows.value = response.data?.[definition.source] || []
  } catch (error) {
    loadError.value = error?.message || String(error)
  } finally {
    loading.value = false
  }
}

onMounted(refresh)
</script>

<style scoped>
.enterprise-organization-model{display:grid;gap:16px;padding:22px;background:#f4f7fb;min-width:0;max-width:100%;overflow-x:hidden}
.model-heading,.scope-context,.hierarchy-region,.model-list,.evidence-region,.maintenance-entry,.audit-region,.diagnostic-region{padding:18px;background:#fff;border:1px solid #dce5ef;border-radius:12px;min-width:0}
.model-heading{display:flex;justify-content:space-between;align-items:center;gap:18px}.model-heading p,.model-heading h1,.model-heading span,.section-title h2,.section-title p{margin:0}.model-heading p{color:#2563eb;font-weight:800}.model-heading h1{margin:7px 0;font-size:30px}.model-heading span,.section-title p{color:#64748b}
.model-navigation{display:flex;gap:10px;flex-wrap:wrap}.model-navigation button{border:1px solid #cbd5e1;border-radius:8px;background:#fff;padding:9px 15px;color:#334155;cursor:pointer}.model-navigation button.active{background:#1d4ed8;border-color:#1d4ed8;color:#fff}
.scope-context{display:flex;gap:12px;flex-wrap:wrap}.scope-context span{padding:8px 10px;background:#f8fafc;border-radius:8px;color:#475569}.scope-context strong{color:#0f172a}.model-summary{display:grid;grid-template-columns:repeat(6,minmax(120px,1fr));gap:12px}.model-summary article{display:grid;gap:4px;padding:14px;background:#fff;border:1px solid #dce5ef;border-radius:10px}.model-summary span{color:#64748b}.model-summary strong{font-size:24px;color:#0f172a}
.section-title{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:14px}.section-title>span{color:#2563eb;font-weight:700}.hierarchy-tree{display:grid;gap:8px}.hierarchy-node{display:grid;grid-template-columns:minmax(180px,1fr) minmax(180px,1fr) minmax(260px,2fr);gap:12px;align-items:center;margin-left:calc(var(--tree-depth) * 24px);padding:10px 12px;border-left:4px solid #60a5fa;background:#f8fafc;border-radius:8px}.hierarchy-node span,.hierarchy-node small{color:#64748b}.empty-state{margin:0;color:#64748b}
.evidence-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px}.evidence-grid article{display:grid;gap:5px;padding:13px;border:1px solid #dbeafe;background:#eff6ff;border-radius:9px}.evidence-grid span{color:#475569}.diagnostic-region summary{cursor:pointer;font-weight:700}.diagnostic-region pre{white-space:pre-wrap;overflow:auto;background:#0f172a;color:#dbeafe;padding:12px;border-radius:8px}
.maintenance-entry{display:grid;grid-template-columns:minmax(260px,1fr) minmax(320px,2fr) auto;gap:16px;align-items:center}.maintenance-entry h2,.maintenance-entry p{margin:0}.maintenance-entry p{margin-top:5px;color:#64748b}.permission-tags{display:flex;gap:8px;flex-wrap:wrap}.permission-tags span{padding:7px 9px;border-radius:8px;background:#fff7ed;color:#9a3412;font-size:13px}.permission-tags span.allowed{background:#ecfdf5;color:#047857}.maintenance-form{max-width:800px;margin:12px auto 0}.maintenance-form :deep(.el-select),.maintenance-form :deep(.el-input),.maintenance-form :deep(.el-textarea){width:100%}.date-pair{display:flex;gap:10px;width:100%}.date-pair>*{flex:1}.audit-list{display:grid;gap:8px}.audit-list article{display:grid;grid-template-columns:minmax(180px,1fr) minmax(320px,2fr);gap:5px 16px;padding:11px 13px;background:#f8fafc;border-radius:8px}.audit-list span,.audit-list small{color:#64748b}.audit-list small{grid-column:1/-1}
@media(max-width:1000px){.model-summary{grid-template-columns:repeat(3,1fr)}.hierarchy-node{grid-template-columns:1fr;margin-left:calc(var(--tree-depth) * 12px)}}
@media(max-width:900px){.maintenance-entry{grid-template-columns:1fr}.audit-list article{grid-template-columns:1fr}}
@media(max-width:720px){.model-heading{align-items:flex-start;flex-direction:column}.model-summary{grid-template-columns:repeat(2,1fr)}.date-pair{flex-direction:column}}
</style>

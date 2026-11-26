<template>
  <section
    class="pce-business-action-bar"
    :data-pce-business-action-module="currentModule"
    :data-pce-business-action-contract="resolved.contractVersion"
    :data-pce-action-permission-contract="permissionState.contractVersion"
    :data-pce-action-permission-source="permissionState.currentStateSource"
  >
    <div class="action-summary">
      <strong>当前业务操作</strong>
      <span>{{ resolved.currentModule }} / {{ currentStatusLabel || resolved.currentStatus || '状态加载中' }}</span>
      <span>已选择 {{ resolved.selectedCount }} 条</span>
      <span>下一模块：{{ resolved.nextModule }}</span>
      <span data-acceptance-id="action-permission-server-source">
        权限来源：{{ permissionState.currentStateSource }}
      </span>
      <span data-acceptance-id="action-permission-granted-count">
        服务端授权 {{ permissionState.grantedPermissionCodes.length }} 项
      </span>
    </div>
    <div class="action-buttons" data-acceptance-id="business-action-registry-buttons">
      <el-button
        v-for="action in displayedActions"
        :key="action.actionId"
        :type="action.scope === 'batch' ? 'success' : 'primary'"
        :plain="action.scope !== 'batch'"
        :data-pce-action-id="action.actionId"
        :data-pce-action-source="'BusinessActionRegistry'"
        :data-required-permission="action.requiredPermission"
        :data-server-validator="action.serverValidator"
        :disabled="
          permissionState.loading
            || !action.enabled
            || executingActionId !== ''
        "
        :loading="executingActionId === action.actionId"
        :title="action.disabledReason"
        @click="execute(action)"
      >
        {{ action.actionName }}
      </el-button>
    </div>
  </section>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  listBusinessActionPermissions,
  validateBusinessActionPermission,
} from '@/api/businessActionPermission.js'
import {
  BusinessActionRegistry,
} from '../runtime/pceBusinessActionRegistry.js'

const props = defineProps({
  currentModule: { type: String, required: true },
  currentStatus: { type: String, default: '' },
  currentStatusLabel: { type: String, default: '' },
  selectedRows: { type: Array, default: () => [] },
  permissions: {
    type: Array,
    default: null,
  },
  eligibility: { type: Boolean, default: null },
  routeQuery: { type: Object, default: () => ({}) },
  showUnavailable: { type: Boolean, default: false },
  batchEnabled: { type: Boolean, default: true },
  includeActionIds: { type: Array, default: () => [] },
  beforeNavigate: { type: Function, default: null },
})
const emit = defineEmits(['execute', 'permission-denied'])
const router = useRouter()
const executingActionId = ref('')
const permissionState = reactive({
  loading: true,
  contractVersion: 'PCE-BUSINESS-ACTION-PERMISSION-V1.0',
  currentStateSource: 'server',
  grantedPermissionCodes: [],
  decisions: [],
  error: '',
})
let permissionRequestSequence = 0

const selectedObjectIds = computed(() => props.selectedRows
  .map(row => row?.id)
  .filter(value => value !== null && value !== undefined && value !== '')
  .map(String))
const selectedLegalEntityId = computed(() => String(
  props.selectedRows.find(row => (
    row?.legalEntityId || row?.legal_entity_id
  ))?.legalEntityId
    || props.selectedRows.find(row => row?.legal_entity_id)?.legal_entity_id
    || '',
))
const permissionRequestKey = computed(() => JSON.stringify({
  moduleCode: props.currentModule,
  currentStatus: props.currentStatus,
  objectIds: selectedObjectIds.value,
  selectionCount: props.selectedRows.length,
  legalEntityId: selectedLegalEntityId.value,
}))
const effectivePermissions = computed(() => {
  const granted = new Set(permissionState.grantedPermissionCodes)
  if (!Array.isArray(props.permissions)) return [...granted]
  return props.permissions.filter(item => granted.has(item))
})
const resolved = computed(() => BusinessActionRegistry.resolve({
  currentModule: props.currentModule,
  currentStatus: props.currentStatus,
  selectedRows: props.selectedRows,
  permissions: effectivePermissions.value,
  eligibility: props.eligibility,
  routeQuery: props.routeQuery,
}))

watch(permissionRequestKey, refreshPermissionDecisions, { immediate: true })

async function refreshPermissionDecisions() {
  const sequence = ++permissionRequestSequence
  permissionState.loading = true
  permissionState.error = ''
  try {
    const payload = await listBusinessActionPermissions({
      moduleCode: props.currentModule,
      objectIds: selectedObjectIds.value,
      selectionCount: props.selectedRows.length,
      legalEntityId: selectedLegalEntityId.value,
    })
    if (sequence !== permissionRequestSequence) return
    if (payload.result !== 'passed') {
      throw new Error(payload.error?.message || '服务端权限读取失败。')
    }
    permissionState.contractVersion = payload.contractVersion
    permissionState.currentStateSource =
      payload.currentStateSource || 'server'
    permissionState.grantedPermissionCodes =
      payload.data?.grantedPermissionCodes || []
    permissionState.decisions = payload.data?.decisions || []
  } catch (error) {
    if (sequence !== permissionRequestSequence) return
    permissionState.grantedPermissionCodes = []
    permissionState.decisions = []
    permissionState.error = error?.message || '服务端权限读取失败。'
  } finally {
    if (sequence === permissionRequestSequence) {
      permissionState.loading = false
    }
  }
}
const displayedActions = computed(() => {
  let actions = [
    ...resolved.value.availableActions,
    ...(props.batchEnabled ? resolved.value.batchActions : []),
  ]
  if (props.showUnavailable) {
    actions.push(...resolved.value.unavailableActions.filter(action => (
      props.batchEnabled || action.scope !== 'batch'
    )))
  }
  if (props.includeActionIds.length) {
    const included = new Set(props.includeActionIds)
    actions = actions.filter(action => included.has(action.actionId))
  }
  return actions
})

async function execute(action) {
  if (!action.enabled) return
  executingActionId.value = action.actionId
  try {
    const permissionPayload = await validateBusinessActionPermission({
      actionCode: action.actionCode,
      moduleCode: action.moduleCode,
      objectIds: selectedObjectIds.value,
      selectionCount: props.selectedRows.length,
      legalEntityId: selectedLegalEntityId.value,
    })
    const permissionDecision = permissionPayload.data || {}
    if (
      permissionPayload.result !== 'passed'
      || permissionDecision.granted !== true
    ) {
      const reason = permissionDecision.reason
        || permissionPayload.error?.message
        || '服务端拒绝当前业务动作。'
      ElMessage({ type: 'error', showClose: true, message: reason })
      emit('permission-denied', {
        action,
        decision: permissionDecision,
      })
      await refreshPermissionDecisions()
      return
    }
    if (action.handlerType === 'route' && action.targetRoute) {
      const allowed = props.beforeNavigate
        ? await props.beforeNavigate(action)
        : true
      if (allowed === false) return
      await router.push(action.targetRoute)
      return
    }
    emit('execute', {
      ...action,
      permissionDecision,
    })
  } finally {
    executingActionId.value = ''
  }
}
</script>

<style scoped>
.pce-business-action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
  padding: 14px 16px;
  border: 1px solid #93c5fd;
  border-radius: 10px;
  background: linear-gradient(135deg, #eff6ff, #ffffff);
}

.action-summary,
.action-buttons {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.action-summary span {
  color: #475569;
  font-size: 13px;
}
</style>

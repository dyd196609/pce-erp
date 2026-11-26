import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { findPdePageDefinition } from '../../src/meta/pages/pdePageDefinitions.js'
import {
  getFoundationCanonicalModuleByEntity,
} from '../../src/meta/master-data/foundationEntryUnificationRegistry.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const projectRoot = path.resolve(frontendRoot, '..')
const readFrontend = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const readProject = relative => fs.readFileSync(path.join(projectRoot, relative), 'utf8')

test('工艺路线页显示服务端生产计划就绪度且不创建计划', () => {
  const routing = findPdePageDefinition('routings')
  const fields = routing.columns.map(([field]) => field)
  const page = readFrontend('src/meta/pages/PdeFoundationPage.vue')
  const component = readFrontend('src/meta/pages/components/RoutingPlanningReadiness.vue')

  assert.ok(fields.includes('planningReadinessStatusLabel'))
  assert.ok(fields.includes('planningBlockingSummary'))
  assert.match(page, /<RoutingPlanningReadiness/)
  assert.match(page, /strictFacts\.routingFoundationAssessment/)
  assert.match(component, /data-acceptance-id="routing-production-planning-readiness"/)
  assert.match(component, /本页不会创建生产计划或排程/)
  assert.match(component, /工序核算口径/)
  assert.match(component, /row\.dailyCapacity/)
  assert.match(component, /row\.preparationDays/)
  assert.match(component, /row\.transferDays/)
  assert.doesNotMatch(component, /standardHours|setupHours|transferHours/)
  assert.match(component, /工序候选工作中心/)
  assert.match(component, /标准产能/)
  assert.match(component, /row\.blockerLabels/)
  assert.doesNotMatch(component, /row\.blockerCodes/)
  assert.doesNotMatch(component, /<el-button[^>]*>创建生产计划|提交排程|自动补齐/)
})

test('候选工作中心与工作中心班组关系复用企业基础资料正式入口', () => {
  const candidate = getFoundationCanonicalModuleByEntity('work-center-operation-capabilities')
  const team = getFoundationCanonicalModuleByEntity('work-center-team-assignments')
  const maintenance = readFrontend('src/meta/components/ProductionFoundationMaintenance.vue')
  const service = readProject('backend/pde/production_foundation_service.py')

  assert.equal(candidate.dataSource, 'pde.WorkCenterOperationCapability')
  assert.equal(team.dataSource, 'pde.WorkCenterTeamAssignment')
  assert.match(maintenance, /'work-center-operation-capabilities'/)
  assert.match(maintenance, /'work-center-team-assignments'/)
  assert.match(maintenance, /PCE-MFG-CALENDAR-V1\.0/)
  assert.match(service, /"work-center-operation-capabilities"/)
  assert.match(service, /"work-center-team-assignments"/)
})

test('服务端就绪度只读正式事实并显式保持零计划写入', () => {
  const service = readProject('backend/pde/routing_planning_readiness_service.py')
  const dailyService = readProject('backend/pde/daily_capacity_service.py')
  const views = readProject('backend/pde/views.py')
  const block = views.slice(
    views.indexOf('class RoutingListView'),
    views.indexOf('class EngineeringDocumentListView'),
  )

  for (const token of [
    'RoutingVersion', 'RoutingStep', 'Process', 'WorkCenter',
    'WorkCenterOperationCapability', 'StandardCapacity', 'PCE-MFG-CALENDAR-V1.0',
    'BLOCKED_MISSING_FORMAL_PLANNING_DATA', 'productionPlanCreatedCount',
    'productionScheduleCreatedCount', 'businessWriteCount',
  ]) assert.match(service + dailyService, new RegExp(token.replaceAll('.', '\\.')))
  assert.match(block, /RoutingPlanningReadinessService\.assess/)
  assert.match(block, /RoutingPlanningReadinessService\.foundation_assessment/)
  assert.match(service, /return DailyCapacityReadinessService\.assess/)
  assert.match(dailyService, /PCE-APS-DAILY-CAPACITY-V1/)
  assert.doesNotMatch(dailyService, /standard_hours|setup_hours|transfer_hours/)
  assert.doesNotMatch(service, /\.objects\.create\(|\.objects\.update\(|\.save\(/)
  assert.doesNotMatch(dailyService, /\.objects\.create\(|\.objects\.update\(|\.save\(/)
})

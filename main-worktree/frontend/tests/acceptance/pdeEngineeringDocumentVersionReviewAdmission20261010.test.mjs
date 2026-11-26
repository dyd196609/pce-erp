import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const projectRoot = path.resolve(frontendRoot, '..')
const readFrontend = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const readProject = relative => fs.readFileSync(path.join(projectRoot, relative), 'utf8')

test('工程资料发布原页面显示正式评审准入且不混同发布', () => {
  const page = readFrontend('src/meta/pages/PdeFoundationPage.vue')
  const component = readFrontend('src/meta/pages/components/EngineeringDocumentReleaseReadback.vue')
  const api = readFrontend('src/api/pde.js')

  assert.match(component, /engineering-document-version-review-admission/)
  assert.match(component, /工程资料版本正式评审/)
  assert.match(component, /READY_FOR_HUMAN_REVIEW/)
  assert.match(component, /正式评审通过/)
  assert.match(component, /评审与发布是两个业务动作/)
  assert.match(page, /handleReviewEngineeringDocumentVersion/)
  assert.match(page, /pde\.engineering_document_version\.review/)
  assert.match(page, /不会发布工程资料，也不会形成制造发布记录/)
  assert.match(api, /engineering-document-versions\/\$\{versionId\}\/review\//)
})

test('服务端专用入口复用共享Workflow并封堵通用发布权限评审', () => {
  const service = readProject('backend/pde/engineering_document_version_review_service.py')
  const lifecycle = readProject('backend/pde/production_foundation_service.py')
  const views = readProject('backend/pde/views.py')

  assert.match(service, /pde\.engineering_document_version\.review/)
  assert.match(service, /PositionWorkflowResponsibility/)
  assert.match(service, /ApprovalDecision\.objects\.create/)
  assert.match(service, /transition_business_object/)
  assert.match(service, /ProductManufacturingOutput\.objects\.filter/)
  assert.match(lifecycle, /review_engineering_document_version/)
  assert.match(views, /EngineeringDocumentVersionReviewView/)
  assert.match(views, /project_engineering_document_version_review_preflight/)
})

test('系统目录只创建技术Permission与Workflow，不授予人员关系', () => {
  const permissionCatalog = readProject('backend/pde/engineering_document_version_permission_catalog.py')
  const workflowCatalog = readProject('backend/pde/engineering_document_version_workflow_catalog.py')

  assert.match(permissionCatalog, /rolePermissionWrites": 0/)
  assert.match(permissionCatalog, /workflowResponsibilityWrites": 0/)
  assert.match(permissionCatalog, /userAuthorityWrites": 0/)
  assert.match(workflowCatalog, /PDE_ENGINEERING_DOCUMENT_VERSION_FORMAL_REVIEW/)
  assert.match(workflowCatalog, /系统目录自动生成/)
  assert.doesNotMatch(permissionCatalog, /Role\.objects|UserRoleScopeAssignment\.objects/)
})

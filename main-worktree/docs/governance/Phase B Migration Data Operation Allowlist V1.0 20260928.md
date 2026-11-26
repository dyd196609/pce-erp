# Phase B Migration Data Operation Allowlist V1.0

> Source Commit：`969a86fe4a1b8557e8c837d19c58e9a9cc5d8fba`。本版本吸收《Migration Data Operation B-Class Evidence Record V1.0》；未执行Migration或数据库操作。

## 1. 最终决策类型

- **A — APPROVE FOR REPLAY**：可进入后续授权集合，但只允许在R4获授权隔离空库、固定commit、签署Fingerprint及本文件Hash一致时执行。
- **B — EXCLUDE FROM REPLAY**：不进入当前Target Schema Replay。
- **C — REDESIGN REQUIRED**：当前源码操作不得执行；须完成独立受控重设计后重新评审。

任何A类都不构成Replay执行授权；`RunPython.noop`仅接受临时隔离库销毁合同，不代表生产回滚能力。

## 2. 全量Migration决策矩阵

|App|Migration|Decision|RunPython|RunSQL|Seed|Permission Seed|Data Impact|Idempotency / Reverse|Risk|Evidence|
|---|---|---|---:|---:|---:|---:|---|---|---|---|
| `bank_send_execution_gate` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `bank_send_execution_simulation` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `bank_send_execution_simulation` | `0002_v65_simulation_audit_isolation_gate` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `bank_send_execution_simulation` | `0003_v66_chain_trace_final_approval` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `bank_send_execution_simulation` | `0004_v67_production_release_isolation` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `bank_send_execution_simulation` | `0005_v68_execution_framework_design` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `bank_send_preparation` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `bank_send_request` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `bank_send_task` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `bank_send_task` | `0002_banksendtask_batch_id` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `bank_send_task` | `0003_banksendtaskcanarypoolentry` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `formal_payment_order` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `formal_payment_order` | `0002_formalpaymentorder_source_scenario_code` | **A — APPROVE FOR REPLAY** | 是 | 否 | 否 | 否 | 数据回填/规范化 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | 初始全量静态评审 |
| `formal_payment_order` | `0003_formalpaymentorder_execution_gate` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `formal_payment_order` | `0004_state_consistency_contract` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `masterdata` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `masterdata` | `0002_alter_materialcategory_options` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `masterdata` | `0003_materialcategory_parent` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `masterdata` | `0004_enterprise_procurement_dimensions_r4` | **C — REDESIGN REQUIRED** | 是 | 否 | 是/候选 | 否 | 基础或业务数据Seed/更新 | noop或残留不可接受，需排除/重设计 | 高（禁止执行） | Evidence Record B01 |
| `masterdata` | `0005_project_selector_linkage_r5` | **A — APPROVE FOR REPLAY** | 是 | 否 | 否 | 否 | 数据回填/规范化 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | 初始全量静态评审 |
| `masterdata` | `0006_price_approval_result_supplier_material_price_v45_8` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `masterdata` | `0007_supplier_material_price_manual_source_r5` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `masterdata` | `0008_material_supply_governance_a0` | **A — APPROVE FOR REPLAY** | 是 | 否 | 否 | 否 | 数据回填/规范化 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | 初始全量静态评审 |
| `masterdata` | `0009_unit_and_code_governance_a1` | **A — APPROVE FOR REPLAY** | 是 | 是 | 是/候选 | 否 | 基础或业务数据Seed/更新 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | Evidence Record B02 |
| `masterdata` | `0010_material_unit_confirmation_a1_final` | **A — APPROVE FOR REPLAY** | 是 | 否 | 否 | 否 | 数据回填/规范化 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | 初始全量静态评审 |
| `masterdata` | `0011_foundation_identity_uom_and_encoders` | **C — REDESIGN REQUIRED** | 是 | 否 | 是/候选 | 否 | 基础或业务数据Seed/更新 | 显式reverse或函数级证据已记录 | 高（禁止执行） | Evidence Record B03 |
| `masterdata` | `0012_standard_uom_initialization_v12` | **C — REDESIGN REQUIRED** | 是 | 否 | 是/候选 | 否 | 基础或业务数据Seed/更新 | 显式reverse或函数级证据已记录 | 高（禁止执行） | Evidence Record B04 |
| `masterdata` | `0013_manufacturing_plant_phase_a` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `mes` | `0001_manufacturing_domain_foundation_phase_a` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `payable_confirmation_prepare` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `payment_instruction_prepare` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `payment_instruction_prepare` | `0002_state_machine_semantics` | **A — APPROVE FOR REPLAY** | 是 | 否 | 否 | 否 | 数据回填/规范化 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | 初始全量静态评审 |
| `payment_order_draft` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `payment_order_draft` | `0002_state_machine_semantics` | **A — APPROVE FOR REPLAY** | 是 | 否 | 否 | 否 | 数据回填/规范化 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | 初始全量静态评审 |
| `payment_order_prepare` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `payment_order_prepare` | `0002_state_machine_semantics` | **A — APPROVE FOR REPLAY** | 是 | 否 | 否 | 否 | 数据回填/规范化 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | 初始全量静态评审 |
| `payment_request` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `payment_request` | `0002_state_machine_semantics` | **A — APPROVE FOR REPLAY** | 是 | 否 | 否 | 否 | 数据回填/规范化 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | 初始全量静态评审 |
| `payment_request_prepare` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `payment_risk_review` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `payment_risk_review` | `0002_paymentriskreview_scenario_code` | **A — APPROVE FOR REPLAY** | 是 | 否 | 否 | 否 | 数据回填/规范化 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | 初始全量静态评审 |
| `pde` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `pde` | `0002_pde_emd_relationships` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `pde` | `0003_pde_version_governance` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `pde` | `0004_pde_manufacturing_output` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `pde` | `0005_product_engineering_readiness` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `pde` | `0006_production_master_data_a1` | **A — APPROVE FOR REPLAY** | 是 | 否 | 否 | 否 | 数据回填/规范化 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | 初始全量静态评审 |
| `pde` | `0007_production_master_permissions_and_codes_a1` | **C — REDESIGN REQUIRED** | 是 | 否 | 是/候选 | 是/候选 | 权限/角色/关系数据操作 | noop或残留不可接受，需排除/重设计 | 高（禁止执行） | Evidence Record B05 |
| `pde` | `0008_engineering_fact_source_a15` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `pde` | `0009_stable_business_references_a15` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `pde` | `0010_engineering_permissions_a15` | **A — APPROVE FOR REPLAY** | 是 | 否 | 是/候选 | 是/候选 | 权限/角色/关系数据操作 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | Evidence Record B06 |
| `pde` | `0011_plan_operator_engineering_authority_a15` | **C — REDESIGN REQUIRED** | 是 | 否 | 是/候选 | 是/候选 | 权限/角色/关系数据操作 | noop或残留不可接受，需排除/重设计 | 高（禁止执行） | Evidence Record B07 |
| `pde` | `0012_engineeringbreakdownitem_and_more` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `pde` | `0013_production_unified_model_permissions_a17` | **C — REDESIGN REQUIRED** | 是 | 否 | 是/候选 | 是/候选 | 权限/角色/关系数据操作 | noop或残留不可接受，需排除/重设计 | 高（禁止执行） | Evidence Record B08 |
| `pde` | `0014_alter_productcategory_industry_type` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `pde` | `0015_standard_capacity_measurement_status_a1_final` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `pde` | `0016_a1_final_industry_semantics` | **B — EXCLUDE FROM REPLAY** | 是 | 否 | 否 | 否 | 数据回填/规范化 | noop或残留不可接受，需排除/重设计 | 高（明确排除） | Manifest/强制排除复核 |
| `pde` | `0017_engineering_rule_foundation_do2` | **C — REDESIGN REQUIRED** | 是 | 否 | 是/候选 | 是/候选 | 权限/角色/关系数据操作 | noop或残留不可接受，需排除/重设计 | 高（禁止执行） | Evidence Record B09 |
| `pde` | `0018_engineering_calculation_closure_do3` | **C — REDESIGN REQUIRED** | 是 | 否 | 是/候选 | 是/候选 | 权限/角色/关系数据操作 | noop或残留不可接受，需排除/重设计 | 高（禁止执行） | Evidence Record B10 |
| `pde` | `0019_manufacturing_structure_wave2` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `pde` | `0020_group3_transition_mode_override` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `pde` | `0021_group3a_operation_executor_authority` | **A — APPROVE FOR REPLAY** | 是 | 否 | 是/候选 | 是/候选 | 权限/角色/关系数据操作 | 显式reverse或函数级证据已记录 | 中（隔离合同） | Evidence Record B11 |
| `pde` | `0022_manufacturing_definition_applicability` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `pde` | `0023_order_engineering_calculation_bom_closure` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `pde` | `0024_engineering_breakdown_option` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `pde` | `0025_order_cross_functional_review` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `pde` | `0026_order_review_itemized` | **A — APPROVE FOR REPLAY** | 是 | 否 | 是/候选 | 否 | 基础或业务数据Seed/更新 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | 初始全量静态评审 |
| `pde` | `0027_order_review_participant_grant` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `pde` | `0028_product_design_plan_content_completion` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `pde` | `0029_product_design_plan_group_scope` | **A — APPROVE FOR REPLAY** | 是 | 否 | 否 | 否 | 数据回填/规范化 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | 初始全量静态评审 |
| `pde` | `0030_order_engineering_baseline` | **A — APPROVE FOR REPLAY** | 是 | 否 | 是/候选 | 是/候选 | 权限/角色/关系数据操作 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | Evidence Record B12 |
| `pde` | `0031_operation_time_standard_phase_a_rebased` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `pfm` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `pfm` | `0002_employee_formal_organization_relations` | **C — REDESIGN REQUIRED** | 是 | 否 | 否 | 否 | 数据回填/规范化 | noop或残留不可接受，需排除/重设计 | 高（禁止执行） | Manifest签署：REDESIGN REQUIRED |
| `pfm` | `0003_enterprise_organization_model_v1` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `planning` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `planning` | `0002_planning_access_workflow_v1` | **C — REDESIGN REQUIRED** | 是 | 否 | 是/候选 | 是/候选 | 权限/角色/关系数据操作 | noop或残留不可接受，需排除/重设计 | 高（禁止执行） | Evidence Record B13 |
| `planning` | `0003_demand_sales_order_source` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `planning` | `0004_engineering_and_plan_compatibility_a15` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `planning` | `0005_order_planning_chain_v1` | **B — EXCLUDE FROM REPLAY** | 是 | 否 | 是/候选 | 是/候选 | 权限/角色/关系数据操作 | noop或残留不可接受，需排除/重设计 | 高（明确排除） | Manifest/强制排除复核 |
| `planning` | `0006_material_plant_profile_phase_a` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0002_purchaseorder_department` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0003_purchaseorder_require_department` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0004_purchaseorder_purchase_department` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0005_scm_business_object_recovery_v1142813` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0006_purchase_request_lifecycle_v1142142` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0007_purchase_request_smart_form_r3` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0008_purchase_request_enterprise_model_r4` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0009_purchase_request_business_flow_r7` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0010_supplier_quotation_v11428422` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0011_quote_comparison_fact_v11428423_r5` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0012_price_approval_preparation_v11428424` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0013_price_approval_legacy_projection_v11428424_r3` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0014_price_approval_projection_snapshot_v11428424_r3` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0015_price_approval_review_result_v11428424_r23` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0016_supplier_master_completeness_v11428427227` | **A — APPROVE FOR REPLAY** | 是 | 否 | 是/候选 | 否 | 基础或业务数据Seed/更新 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | 初始全量静态评审 |
| `procurement` | `0017_supplier_category_classification_v11428427227` | **A — APPROVE FOR REPLAY** | 是 | 否 | 否 | 否 | 数据回填/规范化 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | 初始全量静态评审 |
| `procurement` | `0018_supplier_delivery_address_v11428427228` | **A — APPROVE FOR REPLAY** | 是 | 否 | 否 | 否 | 数据回填/规范化 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | 初始全量静态评审 |
| `procurement` | `0019_supplier_master_reverse_enrichment_v1142842724511` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0020_standard_purchase_price_link_v46_batch2` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0021_purchase_mode_entry_v46_batch22_r1` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0022_direct_price_source_trace_v46_batch22_r2` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0023_purchase_order_buyer_employee_r5` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0024_purchase_fulfillment_inventory_v1` | **C — REDESIGN REQUIRED** | 是 | 否 | 是/候选 | 是/候选 | 权限/角色/关系数据操作 | noop或残留不可接受，需排除/重设计 | 高（禁止执行） | Evidence Record B14 |
| `procurement` | `0025_purchase_request_purchase_plan_source_v1` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0026_location_lot_identity_a1` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0027_inventory_dimensions_a15` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `procurement` | `0028_completed_module_read_permissions` | **A — APPROVE FOR REPLAY** | 是 | 否 | 是/候选 | 是/候选 | 权限/角色/关系数据操作 | 显式reverse或函数级证据已记录 | 中（隔离合同） | Evidence Record B15 |
| `purchase` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `purchase` | `0002_alter_purchaseorder_options_and_more` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `purchase_accounts_payable_draft` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `purchase_canary` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `purchase_canary` | `0002_purchasecanarylineage` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `purchase_invoice_prepare` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `purchase_invoice_prepare` | `0002_legalentityinvoiceauthorityrecord_and_more` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `reconciliation` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `reconciliation` | `0002_payablecheckauthorityrecord_and_more` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `reconciliation` | `0003_businessdocumentnumberreservation_reusable` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `sales` | `0001_initial` | **B — EXCLUDE FROM REPLAY** | 是 | 否 | 是/候选 | 是/候选 | 权限/角色/关系数据操作 | noop或残留不可接受，需排除/重设计 | 高（明确排除） | Manifest/强制排除复核 |
| `sales` | `0002_sales_order_engineering_refs_a15` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `sales` | `0003_industrial_order_engineering_input_do1` | **C — REDESIGN REQUIRED** | 是 | 否 | 是/候选 | 是/候选 | 权限/角色/关系数据操作 | noop或残留不可接受，需排除/重设计 | 高（禁止执行） | Evidence Record B16 |
| `sales` | `0004_order_operating_system_v1` | **C — REDESIGN REQUIRED** | 是 | 否 | 是/候选 | 是/候选 | 权限/角色/关系数据操作 | noop或残留不可接受，需排除/重设计 | 高（禁止执行） | Evidence Record B17 |
| `sales` | `0005_sales_order_item_tax_snapshot` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `supplier_performance` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `supplier_performance` | `0002_v82_difference_collaboration` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `supplier_performance` | `0003_v83_payable_payment_request` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `supplier_performance` | `0004_v831_workflow_actions` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `supplier_performance` | `0005_v84_payment_status_closed_loop` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `supplier_performance` | `0006_formal_supplier_settlement_14_22_v1` | **C — REDESIGN REQUIRED** | 是 | 否 | 是/候选 | 是/候选 | 权限/角色/关系数据操作 | noop或残留不可接受，需排除/重设计 | 高（禁止执行） | Evidence Record B18 |
| `system` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `system` | `0002_permission_role_rolepermission` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `system` | `0003_menu_rolemenu` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `system` | `0004_erp_access_foundation` | **A — APPROVE FOR REPLAY** | 是 | 否 | 是/候选 | 是/候选 | 权限/角色/关系数据操作 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | Evidence Record B19 |
| `system` | `0005_organization_access_core_v1` | **A — APPROVE FOR REPLAY** | 是 | 否 | 是/候选 | 是/候选 | 权限/角色/关系数据操作 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | Evidence Record B20 |
| `system` | `0006_enterprise_organization_model_v1` | **A — APPROVE FOR REPLAY** | 是 | 否 | 是/候选 | 否 | 基础或业务数据Seed/更新 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | Evidence Record B21 |
| `system` | `0007_remove_department_cost_center_and_more` | **A — APPROVE FOR REPLAY** | 是 | 否 | 是/候选 | 是/候选 | 权限/角色/关系数据操作 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | Evidence Record B22 |
| `system` | `0008_position_effective_period` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `system` | `0009_responsibility_lifecycle_v1` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `system` | `0010_positionworkflowresponsibility_workflow_node` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `system` | `0011_process_operation_governance_a1` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `system` | `0012_remove_process_system_process_standard_hours_nonnegative_and_more` | **A — APPROVE FOR REPLAY** | 是 | 否 | 否 | 否 | 数据回填/规范化 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | 初始全量静态评审 |
| `system` | `0013_process_workshop_a1_final` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `system` | `0014_workshop_encoder_and_operation_measurement` | **A — APPROVE FOR REPLAY** | 是 | 否 | 否 | 否 | 数据回填/规范化 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | 初始全量静态评审 |
| `system` | `0015_process_default_transition_mode` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `system` | `0016_process_display_order` | **A — APPROVE FOR REPLAY** | 是 | 否 | 否 | 否 | 数据回填/规范化 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | 初始全量静态评审 |
| `system` | `0017_team_operation_capability` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `workflow_runtime` | `0001_initial` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `workflow_runtime` | `0002_business_state_transition` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `workflow_runtime` | `0003_transition_fact_integrity` | **A — APPROVE FOR REPLAY** | 是 | 否 | 否 | 否 | 数据回填/规范化 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | 初始全量静态评审 |
| `workflow_runtime` | `0004_payment_chain_transition_backfill` | **A — APPROVE FOR REPLAY** | 是 | 否 | 是/候选 | 否 | 基础或业务数据Seed/更新 | 幂等按证据；noop以隔离库销毁收口 | 中（隔离合同） | 初始全量静态评审 |
| `workflow_runtime` | `0005_workflownodedefinition_and_more` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |
| `workflow_runtime` | `0006_merge_formal_definitions_and_payment_backfill` | **A — APPROVE FOR REPLAY** | 否 | 否 | 否 | 否 | 无显式数据操作 | Schema反向按Migration声明 | 低 | 初始全量静态评审 |

## 3. RunPython / RunSQL / Seed结论

- RunPython 46项：29项A、3项B、14项C。
- RunSQL 1项：`masterdata.0009_unit_and_code_governance_a1`，SQL为`CREATE TABLE IF NOT EXISTS code_rule`，reverse为`DROP TABLE IF EXISTS code_rule`；在全新隔离空库合同下列A。
- Permission Seed：仅函数级证据明确、稳定编码且符合当前领域边界者列A；跨域PLAN赋权、固定岗位/职责或关闭能力相关者列C。
- 基础数据Seed：固定项目、公司1、默认仓库或组织样本者列C；行业/验收样例列B。
- 原治理来源分类中的C类保护对象继续受保护；最终Allowlist执行决策按本表语义记录：Planning 0005、PDE行业语义操作和Sales验收样例Seed为B（EXCLUDE FROM REPLAY），PFM 0002为C（REDESIGN REQUIRED）。Planning 0006不在固定commit且依赖未重设计，继续按C边界处理。

## 4. Reverse/noop合同

- A类noop：只在可销毁隔离库中接受，F1/F2必须一致；不宣称生产rollback。
- B类：不执行，无reverse需求。
- C类：现有操作不执行，重设计必须提供明确reverse或残留合同。

## 5. B类22项收敛汇总

|原B类结论|数量|状态|
|---|---:|---|
|A — APPROVE FOR REPLAY|9|Evidence完整；进入后续签署候选|
|B — EXCLUDE FROM REPLAY|0|无|
|C — REDESIGN REQUIRED|13|现有操作禁止执行|

## 6. R5 Data Operation Allowlist Sign-off Section

|字段|内容|
|---|---|
|ALLOWLIST STATUS|`TECHNICAL BASELINE SIGNED`|
|A Count|`136`|
|B Count|`3`|
|C Count|`14`|
|Signer|`admin`|
|Role|`System Administrator / Technical Governance Owner`|
|Signature Type|`Technical Replay Boundary Approval`|
|Signature Decision|`APPROVED FOR REPLAY BOUNDARY`|
|Signature Date|`2026-09-28`|
|Scope|确认当前Target Schema范围内Migration Data Operation允许范围|
|Excluded|Migration执行；Replay执行；正式数据库写入；Phase B业务开放|
|Execution Authorization|`NOT GRANTED`|
|R5 Gate|`READY`|

签署仅确认Replay数据操作边界，不代表Migration或Replay执行授权。所有Data Operation只允许在后续单独授权的隔离Replay数据库、Allowlist范围和Schema Fingerprint比较约束下执行；任何超出Allowlist的权限Seed、组织Seed、基础资料Seed、RunPython或RunSQL均禁止执行。


# Phase B Replay Migration Execution Manifest V1.0

## 1. 基础信息

|字段|内容|
|---|---|
|Manifest ID|`PCE-PHASE-B-REPLAY-EXECUTION-MANIFEST-V1.0-20260928`|
|Source Branch|`codex/manufacturing-baseline-convergence-20260927`|
|Source Commit|`969a86fe4a1b8557e8c837d19c58e9a9cc5d8fba`|
|Target Schema Manifest ID|`PCE-PHASE-B-TARGET-SCHEMA-MANIFEST-V1.0-20260928`|
|R5 Allowlist Hash|`8FE570A22A78741E393F37E0EB0CE95E90D1D466177F2536698B56533D33B0D2`|
|R6 Fingerprint Version|`PCE-SCHEMA-FINGERPRINT-V1`|
|Status|`DRAFT`|
|Analysis Rule|任何A节点只要直接或间接依赖B/C节点，即不得标记INCLUDE；当前标记为REDESIGN REQUIRED并保留三种处理选项|
|Execution Authorization|`NOT GRANTED`|

## 2. 执行集合统计

|项目|数量|
|---|---:|
|固定commit Migration节点|153|
|签署R5原A/B/C|136 / 3 / 14|
|闭包治理后INCLUDE|74|
|闭包治理后EXCLUDE|3|
|闭包治理后REDESIGN REQUIRED|76|
|原A因依赖传播转为REDESIGN REQUIRED|62|
|Allowlist未映射节点|0|
|项目内缺失依赖节点|0|

## 3. Migration Execution Matrix

|App|Migration|Dependency|Operation Class|Decision|Reason|
|---|---|---|---|---|---|
|bank_send_execution_gate|0001_initial|`bank_send_task.0003_banksendtaskcanarypoolentry`<br>`reconciliation.0003_businessdocumentnumberreservation_reusable`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|bank_send_execution_simulation|0001_initial|`bank_send_request.0001_initial`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|bank_send_execution_simulation|0002_v65_simulation_audit_isolation_gate|`bank_send_execution_simulation.0001_initial`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|bank_send_execution_simulation|0003_v66_chain_trace_final_approval|`bank_send_execution_simulation.0002_v65_simulation_audit_isolation_gate`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|bank_send_execution_simulation|0004_v67_production_release_isolation|`bank_send_execution_simulation.0003_v66_chain_trace_final_approval`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|bank_send_execution_simulation|0005_v68_execution_framework_design|`bank_send_execution_simulation.0004_v67_production_release_isolation`<br>`bank_send_request.0001_initial`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|bank_send_preparation|0001_initial|`formal_payment_order.0004_state_consistency_contract`<br>`reconciliation.0003_businessdocumentnumberreservation_reusable`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|bank_send_request|0001_initial|`bank_send_execution_gate.0001_initial`<br>`reconciliation.0003_businessdocumentnumberreservation_reusable`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|bank_send_task|0001_initial|`bank_send_preparation.0001_initial`<br>`reconciliation.0003_businessdocumentnumberreservation_reusable`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|bank_send_task|0002_banksendtask_batch_id|`bank_send_task.0001_initial`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|bank_send_task|0003_banksendtaskcanarypoolentry|`bank_send_preparation.0001_initial`<br>`bank_send_task.0002_banksendtask_batch_id`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|formal_payment_order|0001_initial|`payment_risk_review.0001_initial`<br>`reconciliation.0003_businessdocumentnumberreservation_reusable`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|formal_payment_order|0002_formalpaymentorder_source_scenario_code|`payment_risk_review.0002_paymentriskreview_scenario_code`<br>`formal_payment_order.0001_initial`|RunPython|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|formal_payment_order|0003_formalpaymentorder_execution_gate|`formal_payment_order.0002_formalpaymentorder_source_scenario_code`<br>`workflow_runtime.0001_initial`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|formal_payment_order|0004_state_consistency_contract|`formal_payment_order.0003_formalpaymentorder_execution_gate`<br>`workflow_runtime.0002_business_state_transition`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|masterdata|0001_initial|—|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|masterdata|0002_alter_materialcategory_options|`masterdata.0001_initial`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|masterdata|0003_materialcategory_parent|`masterdata.0002_alter_materialcategory_options`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|masterdata|0004_enterprise_procurement_dimensions_r4|`system.0003_menu_rolemenu`<br>`masterdata.0003_materialcategory_parent`|RunPython+Seed|C — REDESIGN REQUIRED|签署R5为C；现有操作须重设计后重新评审|
|masterdata|0005_project_selector_linkage_r5|`masterdata.0004_enterprise_procurement_dimensions_r4`|RunPython|C — REDESIGN REQUIRED|原A被上游阻断：`masterdata.0004_enterprise_procurement_dimensions_r4`；OPTION 1/2/3待架构裁决|
|masterdata|0006_price_approval_result_supplier_material_price_v45_8|`masterdata.0005_project_selector_linkage_r5`<br>`procurement.0018_supplier_delivery_address_v11428427228`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`masterdata.0005_project_selector_linkage_r5`；OPTION 1/2/3待架构裁决|
|masterdata|0007_supplier_material_price_manual_source_r5|`masterdata.0006_price_approval_result_supplier_material_price_v45_8`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`masterdata.0006_price_approval_result_supplier_material_price_v45_8`；OPTION 1/2/3待架构裁决|
|masterdata|0008_material_supply_governance_a0|`masterdata.0007_supplier_material_price_manual_source_r5`|RunPython|C — REDESIGN REQUIRED|原A被上游阻断：`masterdata.0007_supplier_material_price_manual_source_r5`；OPTION 1/2/3待架构裁决|
|masterdata|0009_unit_and_code_governance_a1|`masterdata.0008_material_supply_governance_a0`|RunPython+RunSQL+Seed|C — REDESIGN REQUIRED|原A被上游阻断：`masterdata.0008_material_supply_governance_a0`；OPTION 1/2/3待架构裁决|
|masterdata|0010_material_unit_confirmation_a1_final|`masterdata.0009_unit_and_code_governance_a1`|RunPython|C — REDESIGN REQUIRED|原A被上游阻断：`masterdata.0009_unit_and_code_governance_a1`；OPTION 1/2/3待架构裁决|
|masterdata|0011_foundation_identity_uom_and_encoders|`masterdata.0010_material_unit_confirmation_a1_final`|RunPython+Seed|C — REDESIGN REQUIRED|签署R5为C；现有操作须重设计后重新评审|
|masterdata|0012_standard_uom_initialization_v12|`masterdata.0011_foundation_identity_uom_and_encoders`|RunPython+Seed|C — REDESIGN REQUIRED|签署R5为C；现有操作须重设计后重新评审|
|masterdata|0013_manufacturing_plant_phase_a|`masterdata.0012_standard_uom_initialization_v12`<br>`system.0014_workshop_encoder_and_operation_measurement`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`masterdata.0012_standard_uom_initialization_v12`、`system.0014_workshop_encoder_and_operation_measurement`；OPTION 1/2/3待架构裁决|
|mes|0001_manufacturing_domain_foundation_phase_a|`masterdata.0013_manufacturing_plant_phase_a`<br>`pde.0030_order_engineering_baseline`<br>`pfm.0003_enterprise_organization_model_v1`<br>`system.0014_workshop_encoder_and_operation_measurement`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`masterdata.0013_manufacturing_plant_phase_a`、`pfm.0003_enterprise_organization_model_v1`、`system.0014_workshop_encoder_and_operation_measurement`；OPTION 1/2/3待架构裁决|
|payable_confirmation_prepare|0001_initial|`purchase_accounts_payable_draft.0001_initial`<br>`reconciliation.0003_businessdocumentnumberreservation_reusable`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|payment_instruction_prepare|0001_initial|`payment_request.0001_initial`<br>`reconciliation.0003_businessdocumentnumberreservation_reusable`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|payment_instruction_prepare|0002_state_machine_semantics|`payment_instruction_prepare.0001_initial`|RunPython|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|payment_order_draft|0001_initial|`payment_order_prepare.0001_initial`<br>`reconciliation.0003_businessdocumentnumberreservation_reusable`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|payment_order_draft|0002_state_machine_semantics|`payment_order_draft.0001_initial`|RunPython|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|payment_order_prepare|0001_initial|`payment_instruction_prepare.0001_initial`<br>`reconciliation.0003_businessdocumentnumberreservation_reusable`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|payment_order_prepare|0002_state_machine_semantics|`payment_order_prepare.0001_initial`|RunPython|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|payment_request|0001_initial|`payment_request_prepare.0001_initial`<br>`reconciliation.0003_businessdocumentnumberreservation_reusable`<br>`workflow_runtime.0001_initial`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|payment_request|0002_state_machine_semantics|`payment_request.0001_initial`|RunPython|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|payment_request_prepare|0001_initial|`payable_confirmation_prepare.0001_initial`<br>`reconciliation.0003_businessdocumentnumberreservation_reusable`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|payment_risk_review|0001_initial|`payment_order_draft.0001_initial`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|payment_risk_review|0002_paymentriskreview_scenario_code|`payment_risk_review.0001_initial`|RunPython|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|pde|0001_initial|—|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|pde|0002_pde_emd_relationships|`pde.0001_initial`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|pde|0003_pde_version_governance|`pde.0002_pde_emd_relationships`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|pde|0004_pde_manufacturing_output|`pde.0003_pde_version_governance`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|pde|0005_product_engineering_readiness|`pde.0004_pde_manufacturing_output`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|pde|0006_production_master_data_a1|`masterdata.0009_unit_and_code_governance_a1`<br>`pde.0005_product_engineering_readiness`<br>`system.0010_positionworkflowresponsibility_workflow_node`|RunPython|C — REDESIGN REQUIRED|原A被上游阻断：`masterdata.0009_unit_and_code_governance_a1`；OPTION 1/2/3待架构裁决|
|pde|0007_production_master_permissions_and_codes_a1|`pde.0006_production_master_data_a1`<br>`system.0011_process_operation_governance_a1`|RunPython+Seed+PermissionSeed|C — REDESIGN REQUIRED|签署R5为C；现有操作须重设计后重新评审|
|pde|0008_engineering_fact_source_a15|`pde.0007_production_master_permissions_and_codes_a1`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`pde.0007_production_master_permissions_and_codes_a1`；OPTION 1/2/3待架构裁决|
|pde|0009_stable_business_references_a15|`pde.0008_engineering_fact_source_a15`<br>`planning.0004_engineering_and_plan_compatibility_a15`<br>`sales.0002_sales_order_engineering_refs_a15`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`pde.0008_engineering_fact_source_a15`、`planning.0004_engineering_and_plan_compatibility_a15`、`sales.0002_sales_order_engineering_refs_a15`；OPTION 1/2/3待架构裁决|
|pde|0010_engineering_permissions_a15|`pde.0009_stable_business_references_a15`|RunPython+Seed+PermissionSeed|C — REDESIGN REQUIRED|原A被上游阻断：`pde.0009_stable_business_references_a15`；OPTION 1/2/3待架构裁决|
|pde|0011_plan_operator_engineering_authority_a15|`pde.0010_engineering_permissions_a15`|RunPython+Seed+PermissionSeed|C — REDESIGN REQUIRED|签署R5为C；现有操作须重设计后重新评审|
|pde|0012_engineeringbreakdownitem_and_more|`masterdata.0009_unit_and_code_governance_a1`<br>`pde.0011_plan_operator_engineering_authority_a15`<br>`sales.0002_sales_order_engineering_refs_a15`<br>`system.0011_process_operation_governance_a1`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`pde.0011_plan_operator_engineering_authority_a15`、`sales.0002_sales_order_engineering_refs_a15`；OPTION 1/2/3待架构裁决|
|pde|0013_production_unified_model_permissions_a17|`pde.0012_engineeringbreakdownitem_and_more`<br>`system.0012_remove_process_system_process_standard_hours_nonnegative_and_more`|RunPython+Seed+PermissionSeed|C — REDESIGN REQUIRED|签署R5为C；现有操作须重设计后重新评审|
|pde|0014_alter_productcategory_industry_type|`pde.0013_production_unified_model_permissions_a17`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`pde.0013_production_unified_model_permissions_a17`；OPTION 1/2/3待架构裁决|
|pde|0015_standard_capacity_measurement_status_a1_final|`pde.0014_alter_productcategory_industry_type`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`pde.0014_alter_productcategory_industry_type`；OPTION 1/2/3待架构裁决|
|pde|0016_a1_final_industry_semantics|`masterdata.0010_material_unit_confirmation_a1_final`<br>`system.0013_process_workshop_a1_final`<br>`pde.0015_standard_capacity_measurement_status_a1_final`|RunPython|B — EXCLUDE FROM REPLAY|签署R5为B；当前Replay明确排除|
|pde|0017_engineering_rule_foundation_do2|`pde.0016_a1_final_industry_semantics`|RunPython+Seed+PermissionSeed|C — REDESIGN REQUIRED|签署R5为C；现有操作须重设计后重新评审|
|pde|0018_engineering_calculation_closure_do3|`masterdata.0010_material_unit_confirmation_a1_final`<br>`pde.0017_engineering_rule_foundation_do2`<br>`sales.0003_industrial_order_engineering_input_do1`<br>`system.0013_process_workshop_a1_final`|RunPython+Seed+PermissionSeed|C — REDESIGN REQUIRED|签署R5为C；现有操作须重设计后重新评审|
|pde|0019_manufacturing_structure_wave2|`masterdata.0012_standard_uom_initialization_v12`<br>`pde.0018_engineering_calculation_closure_do3`<br>`system.0014_workshop_encoder_and_operation_measurement`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`masterdata.0012_standard_uom_initialization_v12`、`pde.0018_engineering_calculation_closure_do3`、`system.0014_workshop_encoder_and_operation_measurement`；OPTION 1/2/3待架构裁决|
|pde|0020_group3_transition_mode_override|`pde.0019_manufacturing_structure_wave2`<br>`system.0015_process_default_transition_mode`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`pde.0019_manufacturing_structure_wave2`、`system.0015_process_default_transition_mode`；OPTION 1/2/3待架构裁决|
|pde|0021_group3a_operation_executor_authority|`pde.0020_group3_transition_mode_override`|RunPython+Seed+PermissionSeed|C — REDESIGN REQUIRED|原A被上游阻断：`pde.0020_group3_transition_mode_override`；OPTION 1/2/3待架构裁决|
|pde|0022_manufacturing_definition_applicability|`pde.0021_group3a_operation_executor_authority`<br>`sales.0004_order_operating_system_v1`<br>`system.0016_process_display_order`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`sales.0004_order_operating_system_v1`；OPTION 1/2/3待架构裁决|
|pde|0023_order_engineering_calculation_bom_closure|`masterdata.0012_standard_uom_initialization_v12`<br>`pde.0022_manufacturing_definition_applicability`<br>`system.0016_process_display_order`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`masterdata.0012_standard_uom_initialization_v12`；OPTION 1/2/3待架构裁决|
|pde|0024_engineering_breakdown_option|`pde.0023_order_engineering_calculation_bom_closure`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`pde.0023_order_engineering_calculation_bom_closure`；OPTION 1/2/3待架构裁决|
|pde|0025_order_cross_functional_review|`pde.0024_engineering_breakdown_option`<br>`system.0017_team_operation_capability`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`pde.0024_engineering_breakdown_option`、`system.0017_team_operation_capability`；OPTION 1/2/3待架构裁决|
|pde|0026_order_review_itemized|`pde.0025_order_cross_functional_review`<br>`pfm.0003_enterprise_organization_model_v1`|RunPython+Seed|C — REDESIGN REQUIRED|原A被上游阻断：`pfm.0003_enterprise_organization_model_v1`；OPTION 1/2/3待架构裁决|
|pde|0027_order_review_participant_grant|`pde.0026_order_review_itemized`<br>`system.0007_remove_department_cost_center_and_more`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`pde.0026_order_review_itemized`；OPTION 1/2/3待架构裁决|
|pde|0028_product_design_plan_content_completion|`masterdata.0012_standard_uom_initialization_v12`<br>`pde.0027_order_review_participant_grant`<br>`pfm.0003_enterprise_organization_model_v1`<br>`sales.0005_sales_order_item_tax_snapshot`<br>`system.0007_remove_department_cost_center_and_more`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`masterdata.0012_standard_uom_initialization_v12`、`sales.0005_sales_order_item_tax_snapshot`；OPTION 1/2/3待架构裁决|
|pde|0029_product_design_plan_group_scope|`pde.0028_product_design_plan_content_completion`<br>`sales.0005_sales_order_item_tax_snapshot`|RunPython|C — REDESIGN REQUIRED|原A被上游阻断：`pde.0028_product_design_plan_content_completion`、`sales.0005_sales_order_item_tax_snapshot`；OPTION 1/2/3待架构裁决|
|pde|0030_order_engineering_baseline|`pde.0029_product_design_plan_group_scope`<br>`sales.0005_sales_order_item_tax_snapshot`<br>`system.0017_team_operation_capability`|RunPython+Seed+PermissionSeed|C — REDESIGN REQUIRED|原A被上游阻断：`pde.0029_product_design_plan_group_scope`、`sales.0005_sales_order_item_tax_snapshot`；OPTION 1/2/3待架构裁决|
|pde|0031_operation_time_standard_phase_a_rebased|`masterdata.0013_manufacturing_plant_phase_a`<br>`pde.0030_order_engineering_baseline`<br>`system.0014_workshop_encoder_and_operation_measurement`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`masterdata.0013_manufacturing_plant_phase_a`、`system.0014_workshop_encoder_and_operation_measurement`；OPTION 1/2/3待架构裁决|
|pfm|0001_initial|`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|pfm|0002_employee_formal_organization_relations|`pfm.0001_initial`<br>`system.0003_menu_rolemenu`<br>`AUTH_USER`|RunPython|C — REDESIGN REQUIRED|签署R5为C；现有操作须重设计后重新评审|
|pfm|0003_enterprise_organization_model_v1|`pfm.0002_employee_formal_organization_relations`<br>`system.0006_enterprise_organization_model_v1`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`pfm.0002_employee_formal_organization_relations`；OPTION 1/2/3待架构裁决|
|planning|0001_initial|`masterdata.0007_supplier_material_price_manual_source_r5`<br>`system.0010_positionworkflowresponsibility_workflow_node`<br>`AUTH_USER`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`masterdata.0007_supplier_material_price_manual_source_r5`；OPTION 1/2/3待架构裁决|
|planning|0002_planning_access_workflow_v1|`planning.0001_initial`<br>`system.0010_positionworkflowresponsibility_workflow_node`<br>`workflow_runtime.0006_merge_formal_definitions_and_payment_backfill`|RunPython+Seed+PermissionSeed|C — REDESIGN REQUIRED|签署R5为C；现有操作须重设计后重新评审|
|planning|0003_demand_sales_order_source|`planning.0002_planning_access_workflow_v1`<br>`sales.0001_initial`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`planning.0002_planning_access_workflow_v1`、`sales.0001_initial`；OPTION 1/2/3待架构裁决|
|planning|0004_engineering_and_plan_compatibility_a15|`planning.0003_demand_sales_order_source`<br>`pde.0008_engineering_fact_source_a15`<br>`sales.0002_sales_order_engineering_refs_a15`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`planning.0003_demand_sales_order_source`、`pde.0008_engineering_fact_source_a15`；OPTION 1/2/3待架构裁决|
|planning|0005_order_planning_chain_v1|`planning.0004_engineering_and_plan_compatibility_a15`<br>`sales.0004_order_operating_system_v1`<br>`pde.0019_manufacturing_structure_wave2`<br>`system.0014_workshop_encoder_and_operation_measurement`<br>`AUTH_USER`|RunPython+Seed+PermissionSeed|B — EXCLUDE FROM REPLAY|签署R5为B；当前Replay明确排除|
|planning|0006_material_plant_profile_phase_a|`masterdata.0013_manufacturing_plant_phase_a`<br>`mes.0001_manufacturing_domain_foundation_phase_a`<br>`pde.0031_operation_time_standard_phase_a_rebased`<br>`planning.0005_order_planning_chain_v1`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`masterdata.0013_manufacturing_plant_phase_a`、`planning.0005_order_planning_chain_v1`；OPTION 1/2/3待架构裁决|
|procurement|0001_initial|`masterdata.0001_initial`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|procurement|0002_purchaseorder_department|`procurement.0001_initial`<br>`system.0001_initial`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|procurement|0003_purchaseorder_require_department|`procurement.0002_purchaseorder_department`<br>`system.0001_initial`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|procurement|0004_purchaseorder_purchase_department|`procurement.0003_purchaseorder_require_department`<br>`system.0001_initial`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|procurement|0005_scm_business_object_recovery_v1142813|`procurement.0004_purchaseorder_purchase_department`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|procurement|0006_purchase_request_lifecycle_v1142142|`procurement.0005_scm_business_object_recovery_v1142813`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|procurement|0007_purchase_request_smart_form_r3|`masterdata.0003_materialcategory_parent`<br>`system.0003_menu_rolemenu`<br>`procurement.0006_purchase_request_lifecycle_v1142142`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|procurement|0008_purchase_request_enterprise_model_r4|`masterdata.0004_enterprise_procurement_dimensions_r4`<br>`system.0003_menu_rolemenu`<br>`procurement.0007_purchase_request_smart_form_r3`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`masterdata.0004_enterprise_procurement_dimensions_r4`；OPTION 1/2/3待架构裁决|
|procurement|0009_purchase_request_business_flow_r7|`procurement.0008_purchase_request_enterprise_model_r4`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`procurement.0008_purchase_request_enterprise_model_r4`；OPTION 1/2/3待架构裁决|
|procurement|0010_supplier_quotation_v11428422|`procurement.0009_purchase_request_business_flow_r7`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`procurement.0009_purchase_request_business_flow_r7`；OPTION 1/2/3待架构裁决|
|procurement|0011_quote_comparison_fact_v11428423_r5|`procurement.0010_supplier_quotation_v11428422`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`procurement.0010_supplier_quotation_v11428422`；OPTION 1/2/3待架构裁决|
|procurement|0012_price_approval_preparation_v11428424|`procurement.0011_quote_comparison_fact_v11428423_r5`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`procurement.0011_quote_comparison_fact_v11428423_r5`；OPTION 1/2/3待架构裁决|
|procurement|0013_price_approval_legacy_projection_v11428424_r3|`procurement.0012_price_approval_preparation_v11428424`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`procurement.0012_price_approval_preparation_v11428424`；OPTION 1/2/3待架构裁决|
|procurement|0014_price_approval_projection_snapshot_v11428424_r3|`procurement.0013_price_approval_legacy_projection_v11428424_r3`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`procurement.0013_price_approval_legacy_projection_v11428424_r3`；OPTION 1/2/3待架构裁决|
|procurement|0015_price_approval_review_result_v11428424_r23|`procurement.0014_price_approval_projection_snapshot_v11428424_r3`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`procurement.0014_price_approval_projection_snapshot_v11428424_r3`；OPTION 1/2/3待架构裁决|
|procurement|0016_supplier_master_completeness_v11428427227|`procurement.0015_price_approval_review_result_v11428424_r23`|RunPython+Seed|C — REDESIGN REQUIRED|原A被上游阻断：`procurement.0015_price_approval_review_result_v11428424_r23`；OPTION 1/2/3待架构裁决|
|procurement|0017_supplier_category_classification_v11428427227|`procurement.0016_supplier_master_completeness_v11428427227`|RunPython|C — REDESIGN REQUIRED|原A被上游阻断：`procurement.0016_supplier_master_completeness_v11428427227`；OPTION 1/2/3待架构裁决|
|procurement|0018_supplier_delivery_address_v11428427228|`procurement.0017_supplier_category_classification_v11428427227`|RunPython|C — REDESIGN REQUIRED|原A被上游阻断：`procurement.0017_supplier_category_classification_v11428427227`；OPTION 1/2/3待架构裁决|
|procurement|0019_supplier_master_reverse_enrichment_v1142842724511|`procurement.0018_supplier_delivery_address_v11428427228`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`procurement.0018_supplier_delivery_address_v11428427228`；OPTION 1/2/3待架构裁决|
|procurement|0020_standard_purchase_price_link_v46_batch2|`masterdata.0006_price_approval_result_supplier_material_price_v45_8`<br>`procurement.0019_supplier_master_reverse_enrichment_v1142842724511`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`masterdata.0006_price_approval_result_supplier_material_price_v45_8`；OPTION 1/2/3待架构裁决|
|procurement|0021_purchase_mode_entry_v46_batch22_r1|`procurement.0020_standard_purchase_price_link_v46_batch2`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`procurement.0020_standard_purchase_price_link_v46_batch2`；OPTION 1/2/3待架构裁决|
|procurement|0022_direct_price_source_trace_v46_batch22_r2|`masterdata.0006_price_approval_result_supplier_material_price_v45_8`<br>`procurement.0021_purchase_mode_entry_v46_batch22_r1`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`masterdata.0006_price_approval_result_supplier_material_price_v45_8`；OPTION 1/2/3待架构裁决|
|procurement|0023_purchase_order_buyer_employee_r5|`pfm.0001_initial`<br>`procurement.0022_direct_price_source_trace_v46_batch22_r2`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`procurement.0022_direct_price_source_trace_v46_batch22_r2`；OPTION 1/2/3待架构裁决|
|procurement|0024_purchase_fulfillment_inventory_v1|`masterdata.0007_supplier_material_price_manual_source_r5`<br>`pfm.0003_enterprise_organization_model_v1`<br>`system.0010_positionworkflowresponsibility_workflow_node`<br>`workflow_runtime.0006_merge_formal_definitions_and_payment_backfill`<br>`procurement.0023_purchase_order_buyer_employee_r5`|RunPython+Seed+PermissionSeed|C — REDESIGN REQUIRED|签署R5为C；现有操作须重设计后重新评审|
|procurement|0025_purchase_request_purchase_plan_source_v1|`planning.0002_planning_access_workflow_v1`<br>`procurement.0024_purchase_fulfillment_inventory_v1`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`planning.0002_planning_access_workflow_v1`、`procurement.0024_purchase_fulfillment_inventory_v1`；OPTION 1/2/3待架构裁决|
|procurement|0026_location_lot_identity_a1|`masterdata.0009_unit_and_code_governance_a1`<br>`procurement.0025_purchase_request_purchase_plan_source_v1`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`procurement.0025_purchase_request_purchase_plan_source_v1`；OPTION 1/2/3待架构裁决|
|procurement|0027_inventory_dimensions_a15|`procurement.0026_location_lot_identity_a1`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`procurement.0026_location_lot_identity_a1`；OPTION 1/2/3待架构裁决|
|procurement|0028_completed_module_read_permissions|`procurement.0027_inventory_dimensions_a15`|RunPython+Seed+PermissionSeed|C — REDESIGN REQUIRED|原A被上游阻断：`procurement.0027_inventory_dimensions_a15`；OPTION 1/2/3待架构裁决|
|purchase|0001_initial|—|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|purchase|0002_alter_purchaseorder_options_and_more|`purchase.0001_initial`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|purchase_accounts_payable_draft|0001_initial|`purchase_invoice_prepare.0002_legalentityinvoiceauthorityrecord_and_more`<br>`reconciliation.0003_businessdocumentnumberreservation_reusable`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|purchase_canary|0001_initial|—|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|purchase_canary|0002_purchasecanarylineage|`purchase_canary.0001_initial`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|purchase_invoice_prepare|0001_initial|`reconciliation.0002_payablecheckauthorityrecord_and_more`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|purchase_invoice_prepare|0002_legalentityinvoiceauthorityrecord_and_more|`purchase_invoice_prepare.0001_initial`<br>`reconciliation.0002_payablecheckauthorityrecord_and_more`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|reconciliation|0001_initial|`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|reconciliation|0002_payablecheckauthorityrecord_and_more|`reconciliation.0001_initial`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|reconciliation|0003_businessdocumentnumberreservation_reusable|`reconciliation.0002_payablecheckauthorityrecord_and_more`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|sales|0001_initial|`masterdata.0007_supplier_material_price_manual_source_r5`<br>`system.0010_positionworkflowresponsibility_workflow_node`<br>`workflow_runtime.0006_merge_formal_definitions_and_payment_backfill`<br>`AUTH_USER`|RunPython+Seed+PermissionSeed|B — EXCLUDE FROM REPLAY|签署R5为B；当前Replay明确排除|
|sales|0002_sales_order_engineering_refs_a15|`pde.0008_engineering_fact_source_a15`<br>`sales.0001_initial`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`pde.0008_engineering_fact_source_a15`、`sales.0001_initial`；OPTION 1/2/3待架构裁决|
|sales|0003_industrial_order_engineering_input_do1|`masterdata.0010_material_unit_confirmation_a1_final`<br>`pde.0016_a1_final_industry_semantics`<br>`pfm.0003_enterprise_organization_model_v1`<br>`sales.0002_sales_order_engineering_refs_a15`<br>`system.0013_process_workshop_a1_final`<br>`workflow_runtime.0006_merge_formal_definitions_and_payment_backfill`<br>`AUTH_USER`|RunPython+Seed+PermissionSeed|C — REDESIGN REQUIRED|签署R5为C；现有操作须重设计后重新评审|
|sales|0004_order_operating_system_v1|`pde.0019_manufacturing_structure_wave2`<br>`sales.0003_industrial_order_engineering_input_do1`<br>`system.0014_workshop_encoder_and_operation_measurement`<br>`workflow_runtime.0006_merge_formal_definitions_and_payment_backfill`<br>`AUTH_USER`|RunPython+Seed+PermissionSeed|C — REDESIGN REQUIRED|签署R5为C；现有操作须重设计后重新评审|
|sales|0005_sales_order_item_tax_snapshot|`sales.0004_order_operating_system_v1`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`sales.0004_order_operating_system_v1`；OPTION 1/2/3待架构裁决|
|supplier_performance|0001_initial|—|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|supplier_performance|0002_v82_difference_collaboration|`supplier_performance.0001_initial`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|supplier_performance|0003_v83_payable_payment_request|`supplier_performance.0002_v82_difference_collaboration`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|supplier_performance|0004_v831_workflow_actions|`supplier_performance.0003_v83_payable_payment_request`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|supplier_performance|0005_v84_payment_status_closed_loop|`supplier_performance.0004_v831_workflow_actions`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|supplier_performance|0006_formal_supplier_settlement_14_22_v1|`supplier_performance.0005_v84_payment_status_closed_loop`<br>`system.0010_positionworkflowresponsibility_workflow_node`<br>`workflow_runtime.0006_merge_formal_definitions_and_payment_backfill`<br>`procurement.0024_purchase_fulfillment_inventory_v1`|RunPython+Seed+PermissionSeed|C — REDESIGN REQUIRED|签署R5为C；现有操作须重设计后重新评审|
|system|0001_initial|`auth.0012_alter_user_first_name_max_length`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|system|0002_permission_role_rolepermission|`system.0001_initial`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|system|0003_menu_rolemenu|`system.0002_permission_role_rolepermission`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|system|0004_erp_access_foundation|`system.0003_menu_rolemenu`|RunPython+Seed+PermissionSeed|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|system|0005_organization_access_core_v1|`system.0004_erp_access_foundation`<br>`workflow_runtime.0001_initial`|RunPython+Seed+PermissionSeed|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|system|0006_enterprise_organization_model_v1|`system.0005_organization_access_core_v1`|RunPython+Seed|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|system|0007_remove_department_cost_center_and_more|`system.0006_enterprise_organization_model_v1`|RunPython+Seed+PermissionSeed|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|system|0008_position_effective_period|`system.0007_remove_department_cost_center_and_more`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|system|0009_responsibility_lifecycle_v1|`system.0008_position_effective_period`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|system|0010_positionworkflowresponsibility_workflow_node|`system.0009_responsibility_lifecycle_v1`<br>`workflow_runtime.0005_workflownodedefinition_and_more`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|system|0011_process_operation_governance_a1|`pde.0006_production_master_data_a1`<br>`system.0010_positionworkflowresponsibility_workflow_node`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`pde.0006_production_master_data_a1`；OPTION 1/2/3待架构裁决|
|system|0012_remove_process_system_process_standard_hours_nonnegative_and_more|`pde.0012_engineeringbreakdownitem_and_more`<br>`system.0011_process_operation_governance_a1`|RunPython|C — REDESIGN REQUIRED|原A被上游阻断：`pde.0012_engineeringbreakdownitem_and_more`；OPTION 1/2/3待架构裁决|
|system|0013_process_workshop_a1_final|`system.0012_remove_process_system_process_standard_hours_nonnegative_and_more`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`system.0012_remove_process_system_process_standard_hours_nonnegative_and_more`；OPTION 1/2/3待架构裁决|
|system|0014_workshop_encoder_and_operation_measurement|`masterdata.0011_foundation_identity_uom_and_encoders`<br>`system.0013_process_workshop_a1_final`|RunPython|C — REDESIGN REQUIRED|原A被上游阻断：`masterdata.0011_foundation_identity_uom_and_encoders`；OPTION 1/2/3待架构裁决|
|system|0015_process_default_transition_mode|`system.0014_workshop_encoder_and_operation_measurement`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`system.0014_workshop_encoder_and_operation_measurement`；OPTION 1/2/3待架构裁决|
|system|0016_process_display_order|`system.0015_process_default_transition_mode`|RunPython|C — REDESIGN REQUIRED|原A被上游阻断：`system.0015_process_default_transition_mode`；OPTION 1/2/3待架构裁决|
|system|0017_team_operation_capability|`pfm.0003_enterprise_organization_model_v1`<br>`system.0016_process_display_order`|SchemaOnly|C — REDESIGN REQUIRED|原A被上游阻断：`pfm.0003_enterprise_organization_model_v1`、`system.0016_process_display_order`；OPTION 1/2/3待架构裁决|
|workflow_runtime|0001_initial|`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|workflow_runtime|0002_business_state_transition|`workflow_runtime.0001_initial`<br>`AUTH_USER`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|workflow_runtime|0003_transition_fact_integrity|`reconciliation.0003_businessdocumentnumberreservation_reusable`<br>`workflow_runtime.0002_business_state_transition`|RunPython|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|workflow_runtime|0004_payment_chain_transition_backfill|`workflow_runtime.0003_transition_fact_integrity`<br>`payment_request_prepare.0001_initial`<br>`payment_request.0002_state_machine_semantics`<br>`payment_instruction_prepare.0002_state_machine_semantics`<br>`payment_order_prepare.0002_state_machine_semantics`<br>`payment_order_draft.0002_state_machine_semantics`|RunPython+Seed|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|workflow_runtime|0005_workflownodedefinition_and_more|`workflow_runtime.0002_business_state_transition`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|
|workflow_runtime|0006_merge_formal_definitions_and_payment_backfill|`workflow_runtime.0004_payment_chain_transition_backfill`<br>`workflow_runtime.0005_workflownodedefinition_and_more`|SchemaOnly|A — INCLUDE FOR REPLAY|签署R5为A，且全部内部依赖闭包均为A|

## 4. Execution Leaf定义

以下叶节点仅表示当前DRAFT中依赖闭包全部为A的最高可达节点。它们不构成执行授权，也不得使用无目标的标准`migrate`自动扩展到B/C节点。

|App|Migration|Dependency Closure Entry|
|---|---|---|
|bank_send_execution_simulation|0005_v68_execution_framework_design|`bank_send_execution_simulation.0004_v67_production_release_isolation`<br>`bank_send_request.0001_initial`<br>`AUTH_USER`|
|pde|0005_product_engineering_readiness|`pde.0004_pde_manufacturing_output`|
|pfm|0001_initial|`AUTH_USER`|
|procurement|0007_purchase_request_smart_form_r3|`masterdata.0003_materialcategory_parent`<br>`system.0003_menu_rolemenu`<br>`procurement.0006_purchase_request_lifecycle_v1142142`|
|purchase|0002_alter_purchaseorder_options_and_more|`purchase.0001_initial`|
|purchase_canary|0002_purchasecanarylineage|`purchase_canary.0001_initial`|
|supplier_performance|0005_v84_payment_status_closed_loop|`supplier_performance.0004_v831_workflow_actions`|
|system|0010_positionworkflowresponsibility_workflow_node|`system.0009_responsibility_lifecycle_v1`<br>`workflow_runtime.0005_workflownodedefinition_and_more`|
|workflow_runtime|0006_merge_formal_definitions_and_payment_backfill|`workflow_runtime.0004_payment_chain_transition_backfill`<br>`workflow_runtime.0005_workflownodedefinition_and_more`|

Execution Leaf数量：9。

## 5. 强制边界

- Planning 0005与0006不进入本Manifest的INCLUDE集合；
- PFM 0002及依赖它的0003不进入INCLUDE集合；
- PDE 0020–0022虽然已签署“APPROVED WITH TRACEABILITY PRESERVED”，但其当前活动链存在上游B/C阻断，故本DRAFT不能将其标记INCLUDE；
- B/C节点不得通过fake、跳过operation或忽略错误进入已执行状态；
- 只有后续完成重设计、重新固定commit、重算闭包并签署本Manifest后，状态才可从DRAFT推进。


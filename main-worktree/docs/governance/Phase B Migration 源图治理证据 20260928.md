# Phase B Migration 源图治理证据 20260928

- 基线：`codex/manufacturing-baseline-convergence-20260927@969a86fe4a1b8557e8c837d19c58e9a9cc5d8fba`
- 时间字段：当前基线中该文件最后一次 Git 提交时间（不是数据库应用时间）。
- 依赖：Django Migration 声明的 `dependencies`；`__first__` 保持原义。
- 图加载：`MigrationLoader(None)` 成功；冲突：无；`replaces`：无。

|App|Migration|Git timestamp|Dependencies|Ops|
|-|-|-|-|-:|
|bank_send_execution_gate|0001_initial|2026-09-27T20:15:03+08:00|bank_send_task.0003_banksendtaskcanarypoolentry<br>reconciliation.0003_businessdocumentnumberreservation_reusable<br>system.__first__|2|
|bank_send_execution_simulation|0001_initial|2026-09-27T20:15:03+08:00|bank_send_request.0001_initial<br>system.__first__|5|
|bank_send_execution_simulation|0002_v65_simulation_audit_isolation_gate|2026-09-27T20:15:03+08:00|bank_send_execution_simulation.0001_initial<br>system.__first__|9|
|bank_send_execution_simulation|0003_v66_chain_trace_final_approval|2026-09-27T20:15:03+08:00|bank_send_execution_simulation.0002_v65_simulation_audit_isolation_gate<br>system.__first__|7|
|bank_send_execution_simulation|0004_v67_production_release_isolation|2026-09-27T20:15:03+08:00|bank_send_execution_simulation.0003_v66_chain_trace_final_approval<br>system.__first__|8|
|bank_send_execution_simulation|0005_v68_execution_framework_design|2026-09-27T20:15:03+08:00|bank_send_execution_simulation.0004_v67_production_release_isolation<br>bank_send_request.0001_initial<br>system.__first__|19|
|bank_send_preparation|0001_initial|2026-09-27T20:15:03+08:00|system.__first__<br>formal_payment_order.0004_state_consistency_contract<br>reconciliation.0003_businessdocumentnumberreservation_reusable|9|
|bank_send_request|0001_initial|2026-09-27T20:15:03+08:00|bank_send_execution_gate.0001_initial<br>reconciliation.0003_businessdocumentnumberreservation_reusable<br>system.__first__|7|
|bank_send_task|0001_initial|2026-09-27T20:15:03+08:00|system.__first__<br>bank_send_preparation.0001_initial<br>reconciliation.0003_businessdocumentnumberreservation_reusable|6|
|bank_send_task|0002_banksendtask_batch_id|2026-09-27T20:15:03+08:00|bank_send_task.0001_initial|1|
|bank_send_task|0003_banksendtaskcanarypoolentry|2026-09-27T20:15:03+08:00|bank_send_preparation.0001_initial<br>bank_send_task.0002_banksendtask_batch_id|3|
|formal_payment_order|0001_initial|2026-09-27T20:15:03+08:00|payment_risk_review.0001_initial<br>reconciliation.0003_businessdocumentnumberreservation_reusable<br>system.__first__|9|
|formal_payment_order|0002_formalpaymentorder_source_scenario_code|2026-09-27T20:15:03+08:00|payment_risk_review.0002_paymentriskreview_scenario_code<br>formal_payment_order.0001_initial|4|
|formal_payment_order|0003_formalpaymentorder_execution_gate|2026-09-27T20:15:03+08:00|formal_payment_order.0002_formalpaymentorder_source_scenario_code<br>workflow_runtime.0001_initial<br>system.__first__|8|
|formal_payment_order|0004_state_consistency_contract|2026-09-27T20:15:03+08:00|formal_payment_order.0003_formalpaymentorder_execution_gate<br>workflow_runtime.0002_business_state_transition|1|
|masterdata|0001_initial|2026-09-01T14:05:17+08:00|ROOT|3|
|masterdata|0002_alter_materialcategory_options|2026-05-31T23:36:53+08:00|masterdata.0001_initial|1|
|masterdata|0003_materialcategory_parent|2026-06-12T22:36:24+08:00|masterdata.0002_alter_materialcategory_options|1|
|masterdata|0004_enterprise_procurement_dimensions_r4|2026-09-01T14:05:17+08:00|system.0003_menu_rolemenu<br>masterdata.0003_materialcategory_parent|5|
|masterdata|0005_project_selector_linkage_r5|2026-09-01T14:05:17+08:00|masterdata.0004_enterprise_procurement_dimensions_r4|3|
|masterdata|0006_price_approval_result_supplier_material_price_v45_8|2026-09-01T14:05:17+08:00|masterdata.0005_project_selector_linkage_r5<br>procurement.0018_supplier_delivery_address_v11428427228|3|
|masterdata|0007_supplier_material_price_manual_source_r5|2026-09-01T14:05:17+08:00|masterdata.0006_price_approval_result_supplier_material_price_v45_8|1|
|masterdata|0008_material_supply_governance_a0|2026-09-01T14:05:17+08:00|masterdata.0007_supplier_material_price_manual_source_r5|4|
|masterdata|0009_unit_and_code_governance_a1|2026-09-01T14:05:17+08:00|masterdata.0008_material_supply_governance_a0|7|
|masterdata|0010_material_unit_confirmation_a1_final|2026-09-01T14:05:17+08:00|masterdata.0009_unit_and_code_governance_a1|3|
|masterdata|0011_foundation_identity_uom_and_encoders|2026-08-31T16:51:05+08:00|masterdata.0010_material_unit_confirmation_a1_final|10|
|masterdata|0012_standard_uom_initialization_v12|2026-08-31T16:51:05+08:00|masterdata.0011_foundation_identity_uom_and_encoders|1|
|masterdata|0013_manufacturing_plant_phase_a|2026-09-27T20:10:49+08:00|masterdata.0012_standard_uom_initialization_v12<br>system.0014_workshop_encoder_and_operation_measurement|10|
|mes|0001_manufacturing_domain_foundation_phase_a|2026-09-27T20:50:51+08:00|masterdata.0013_manufacturing_plant_phase_a<br>pde.0030_order_engineering_baseline<br>pfm.0003_enterprise_organization_model_v1<br>system.0014_workshop_encoder_and_operation_measurement|3|
|payable_confirmation_prepare|0001_initial|2026-09-01T14:05:17+08:00|purchase_accounts_payable_draft.0001_initial<br>reconciliation.0003_businessdocumentnumberreservation_reusable<br>system.__first__|16|
|payment_instruction_prepare|0001_initial|2026-09-01T14:05:17+08:00|payment_request.0001_initial<br>reconciliation.0003_businessdocumentnumberreservation_reusable<br>system.__first__|22|
|payment_instruction_prepare|0002_state_machine_semantics|2026-09-01T14:05:17+08:00|payment_instruction_prepare.0001_initial|4|
|payment_order_draft|0001_initial|2026-09-01T14:05:17+08:00|payment_order_prepare.0001_initial<br>reconciliation.0003_businessdocumentnumberreservation_reusable<br>system.__first__|20|
|payment_order_draft|0002_state_machine_semantics|2026-09-01T14:05:17+08:00|payment_order_draft.0001_initial|4|
|payment_order_prepare|0001_initial|2026-09-01T14:05:17+08:00|payment_instruction_prepare.0001_initial<br>reconciliation.0003_businessdocumentnumberreservation_reusable<br>system.__first__|25|
|payment_order_prepare|0002_state_machine_semantics|2026-09-01T14:05:17+08:00|payment_order_prepare.0001_initial|4|
|payment_request|0001_initial|2026-09-01T14:05:17+08:00|payment_request_prepare.0001_initial<br>reconciliation.0003_businessdocumentnumberreservation_reusable<br>workflow_runtime.0001_initial<br>system.__first__|13|
|payment_request|0002_state_machine_semantics|2026-09-01T14:05:17+08:00|payment_request.0001_initial|4|
|payment_request_prepare|0001_initial|2026-09-01T14:05:17+08:00|payable_confirmation_prepare.0001_initial<br>reconciliation.0003_businessdocumentnumberreservation_reusable<br>system.__first__|22|
|payment_risk_review|0001_initial|2026-09-27T20:15:03+08:00|payment_order_draft.0001_initial<br>system.__first__|10|
|payment_risk_review|0002_paymentriskreview_scenario_code|2026-09-27T20:15:03+08:00|payment_risk_review.0001_initial|4|
|pde|0001_initial|2026-09-01T14:05:17+08:00|ROOT|6|
|pde|0002_pde_emd_relationships|2026-09-01T14:05:17+08:00|pde.0001_initial|2|
|pde|0003_pde_version_governance|2026-09-01T14:05:17+08:00|pde.0002_pde_emd_relationships|10|
|pde|0004_pde_manufacturing_output|2026-09-01T14:05:17+08:00|pde.0003_pde_version_governance|4|
|pde|0005_product_engineering_readiness|2026-09-01T14:05:17+08:00|pde.0004_pde_manufacturing_output|1|
|pde|0006_production_master_data_a1|2026-09-01T14:05:17+08:00|masterdata.0009_unit_and_code_governance_a1<br>pde.0005_product_engineering_readiness<br>system.0010_positionworkflowresponsibility_workflow_node|61|
|pde|0007_production_master_permissions_and_codes_a1|2026-09-01T14:05:17+08:00|pde.0006_production_master_data_a1<br>system.0011_process_operation_governance_a1|1|
|pde|0008_engineering_fact_source_a15|2026-09-01T14:05:17+08:00|pde.0007_production_master_permissions_and_codes_a1|15|
|pde|0009_stable_business_references_a15|2026-09-01T14:05:17+08:00|pde.0008_engineering_fact_source_a15<br>planning.0004_engineering_and_plan_compatibility_a15<br>sales.0002_sales_order_engineering_refs_a15|4|
|pde|0010_engineering_permissions_a15|2026-09-01T14:05:17+08:00|pde.0009_stable_business_references_a15|1|
|pde|0011_plan_operator_engineering_authority_a15|2026-09-01T14:05:17+08:00|pde.0010_engineering_permissions_a15|1|
|pde|0012_engineeringbreakdownitem_and_more|2026-09-01T14:05:17+08:00|masterdata.0009_unit_and_code_governance_a1<br>pde.0011_plan_operator_engineering_authority_a15<br>sales.0002_sales_order_engineering_refs_a15<br>system.0011_process_operation_governance_a1|44|
|pde|0013_production_unified_model_permissions_a17|2026-09-01T14:05:17+08:00|pde.0012_engineeringbreakdownitem_and_more<br>system.0012_remove_process_system_process_standard_hours_nonnegative_and_more|1|
|pde|0014_alter_productcategory_industry_type|2026-09-01T14:05:17+08:00|pde.0013_production_unified_model_permissions_a17|1|
|pde|0015_standard_capacity_measurement_status_a1_final|2026-09-01T14:05:17+08:00|pde.0014_alter_productcategory_industry_type|4|
|pde|0016_a1_final_industry_semantics|2026-09-01T14:05:17+08:00|masterdata.0010_material_unit_confirmation_a1_final<br>system.0013_process_workshop_a1_final<br>pde.0015_standard_capacity_measurement_status_a1_final|8|
|pde|0017_engineering_rule_foundation_do2|2026-09-01T14:05:17+08:00|pde.0016_a1_final_industry_semantics|1|
|pde|0018_engineering_calculation_closure_do3|2026-09-01T14:05:17+08:00|masterdata.0010_material_unit_confirmation_a1_final<br>pde.0017_engineering_rule_foundation_do2<br>sales.0003_industrial_order_engineering_input_do1<br>system.0013_process_workshop_a1_final|30|
|pde|0019_manufacturing_structure_wave2|2026-08-31T22:08:39+08:00|masterdata.0012_standard_uom_initialization_v12<br>pde.0018_engineering_calculation_closure_do3<br>system.0014_workshop_encoder_and_operation_measurement|47|
|pde|0020_group3_transition_mode_override|2026-09-27T20:15:03+08:00|pde.0019_manufacturing_structure_wave2<br>system.0015_process_default_transition_mode|1|
|pde|0021_group3a_operation_executor_authority|2026-09-27T20:15:03+08:00|pde.0020_group3_transition_mode_override|1|
|pde|0022_manufacturing_definition_applicability|2026-09-27T20:15:03+08:00|pde.0021_group3a_operation_executor_authority<br>sales.0004_order_operating_system_v1<br>system.0016_process_display_order|37|
|pde|0023_order_engineering_calculation_bom_closure|2026-09-27T20:15:03+08:00|masterdata.0012_standard_uom_initialization_v12<br>pde.0022_manufacturing_definition_applicability<br>system.0016_process_display_order|25|
|pde|0024_engineering_breakdown_option|2026-09-27T20:15:03+08:00|pde.0023_order_engineering_calculation_bom_closure|3|
|pde|0025_order_cross_functional_review|2026-09-27T20:15:03+08:00|pde.0024_engineering_breakdown_option<br>system.0017_team_operation_capability|3|
|pde|0026_order_review_itemized|2026-09-27T20:15:03+08:00|pde.0025_order_cross_functional_review<br>pfm.0003_enterprise_organization_model_v1|15|
|pde|0027_order_review_participant_grant|2026-09-27T20:15:03+08:00|pde.0026_order_review_itemized<br>system.0007_remove_department_cost_center_and_more|2|
|pde|0028_product_design_plan_content_completion|2026-09-27T20:15:03+08:00|masterdata.0012_standard_uom_initialization_v12<br>pde.0027_order_review_participant_grant<br>pfm.0003_enterprise_organization_model_v1<br>sales.0005_sales_order_item_tax_snapshot<br>system.0007_remove_department_cost_center_and_more|8|
|pde|0029_product_design_plan_group_scope|2026-09-27T20:15:03+08:00|pde.0028_product_design_plan_content_completion<br>sales.0005_sales_order_item_tax_snapshot|12|
|pde|0030_order_engineering_baseline|2026-09-27T20:15:03+08:00|pde.0029_product_design_plan_group_scope<br>sales.0005_sales_order_item_tax_snapshot<br>system.0017_team_operation_capability|10|
|pde|0031_operation_time_standard_phase_a_rebased|2026-09-27T20:50:51+08:00|masterdata.0013_manufacturing_plant_phase_a<br>pde.0030_order_engineering_baseline<br>system.0014_workshop_encoder_and_operation_measurement|1|
|pfm|0001_initial|2026-09-01T14:05:17+08:00|system.__first__|3|
|pfm|0002_employee_formal_organization_relations|2026-09-01T14:05:17+08:00|pfm.0001_initial<br>system.0003_menu_rolemenu<br>system.__first__|4|
|pfm|0003_enterprise_organization_model_v1|2026-09-01T14:05:17+08:00|pfm.0002_employee_formal_organization_relations<br>system.0006_enterprise_organization_model_v1|2|
|planning|0001_initial|2026-09-01T14:05:17+08:00|masterdata.0007_supplier_material_price_manual_source_r5<br>system.0010_positionworkflowresponsibility_workflow_node<br>system.__first__|10|
|planning|0002_planning_access_workflow_v1|2026-09-01T14:05:17+08:00|planning.0001_initial<br>system.0010_positionworkflowresponsibility_workflow_node<br>workflow_runtime.0006_merge_formal_definitions_and_payment_backfill|1|
|planning|0003_demand_sales_order_source|2026-09-01T14:05:17+08:00|planning.0002_planning_access_workflow_v1<br>sales.0001_initial|2|
|planning|0004_engineering_and_plan_compatibility_a15|2026-09-01T14:05:17+08:00|planning.0003_demand_sales_order_source<br>pde.0008_engineering_fact_source_a15<br>sales.0002_sales_order_engineering_refs_a15|13|
|planning|0005_order_planning_chain_v1|2026-09-27T20:15:03+08:00|planning.0004_engineering_and_plan_compatibility_a15<br>sales.0004_order_operating_system_v1<br>pde.0019_manufacturing_structure_wave2<br>system.0014_workshop_encoder_and_operation_measurement<br>system.__first__|16|
|planning|0006_material_plant_profile_phase_a|2026-09-27T20:50:51+08:00|masterdata.0013_manufacturing_plant_phase_a<br>mes.0001_manufacturing_domain_foundation_phase_a<br>pde.0031_operation_time_standard_phase_a_rebased<br>planning.0005_order_planning_chain_v1|1|
|procurement|0001_initial|2026-05-31T23:36:53+08:00|masterdata.0001_initial|4|
|procurement|0002_purchaseorder_department|2026-05-31T23:36:53+08:00|procurement.0001_initial<br>system.0001_initial|1|
|procurement|0003_purchaseorder_require_department|2026-06-12T22:36:24+08:00|procurement.0002_purchaseorder_department<br>system.0001_initial|1|
|procurement|0004_purchaseorder_purchase_department|2026-06-12T22:36:24+08:00|procurement.0003_purchaseorder_require_department<br>system.0001_initial|1|
|procurement|0005_scm_business_object_recovery_v1142813|2026-09-01T14:05:17+08:00|procurement.0004_purchaseorder_purchase_department|11|
|procurement|0006_purchase_request_lifecycle_v1142142|2026-09-01T14:05:17+08:00|procurement.0005_scm_business_object_recovery_v1142813|2|
|procurement|0007_purchase_request_smart_form_r3|2026-09-01T14:05:17+08:00|masterdata.0003_materialcategory_parent<br>system.0003_menu_rolemenu<br>procurement.0006_purchase_request_lifecycle_v1142142|9|
|procurement|0008_purchase_request_enterprise_model_r4|2026-09-01T14:05:17+08:00|masterdata.0004_enterprise_procurement_dimensions_r4<br>system.0003_menu_rolemenu<br>procurement.0007_purchase_request_smart_form_r3|24|
|procurement|0009_purchase_request_business_flow_r7|2026-09-01T14:05:17+08:00|procurement.0008_purchase_request_enterprise_model_r4|12|
|procurement|0010_supplier_quotation_v11428422|2026-09-01T14:05:17+08:00|procurement.0009_purchase_request_business_flow_r7|3|
|procurement|0011_quote_comparison_fact_v11428423_r5|2026-09-01T14:05:17+08:00|procurement.0010_supplier_quotation_v11428422|5|
|procurement|0012_price_approval_preparation_v11428424|2026-09-01T14:05:17+08:00|procurement.0011_quote_comparison_fact_v11428423_r5|2|
|procurement|0013_price_approval_legacy_projection_v11428424_r3|2026-09-01T14:05:17+08:00|procurement.0012_price_approval_preparation_v11428424|7|
|procurement|0014_price_approval_projection_snapshot_v11428424_r3|2026-09-01T14:05:17+08:00|procurement.0013_price_approval_legacy_projection_v11428424_r3|1|
|procurement|0015_price_approval_review_result_v11428424_r23|2026-09-01T14:05:17+08:00|procurement.0014_price_approval_projection_snapshot_v11428424_r3|2|
|procurement|0016_supplier_master_completeness_v11428427227|2026-09-01T14:05:17+08:00|procurement.0015_price_approval_review_result_v11428424_r23|4|
|procurement|0017_supplier_category_classification_v11428427227|2026-09-01T14:05:17+08:00|procurement.0016_supplier_master_completeness_v11428427227|1|
|procurement|0018_supplier_delivery_address_v11428427228|2026-09-01T14:05:17+08:00|procurement.0017_supplier_category_classification_v11428427227|2|
|procurement|0019_supplier_master_reverse_enrichment_v1142842724511|2026-09-01T14:05:17+08:00|procurement.0018_supplier_delivery_address_v11428427228|4|
|procurement|0020_standard_purchase_price_link_v46_batch2|2026-09-01T14:05:17+08:00|masterdata.0006_price_approval_result_supplier_material_price_v45_8<br>procurement.0019_supplier_master_reverse_enrichment_v1142842724511|21|
|procurement|0021_purchase_mode_entry_v46_batch22_r1|2026-09-01T14:05:17+08:00|procurement.0020_standard_purchase_price_link_v46_batch2|2|
|procurement|0022_direct_price_source_trace_v46_batch22_r2|2026-09-01T14:05:17+08:00|masterdata.0006_price_approval_result_supplier_material_price_v45_8<br>procurement.0021_purchase_mode_entry_v46_batch22_r1|8|
|procurement|0023_purchase_order_buyer_employee_r5|2026-09-01T14:05:17+08:00|pfm.0001_initial<br>procurement.0022_direct_price_source_trace_v46_batch22_r2|1|
|procurement|0024_purchase_fulfillment_inventory_v1|2026-09-01T14:05:17+08:00|masterdata.0007_supplier_material_price_manual_source_r5<br>pfm.0003_enterprise_organization_model_v1<br>system.0010_positionworkflowresponsibility_workflow_node<br>workflow_runtime.0006_merge_formal_definitions_and_payment_backfill<br>procurement.0023_purchase_order_buyer_employee_r5|20|
|procurement|0025_purchase_request_purchase_plan_source_v1|2026-09-01T14:05:17+08:00|planning.0002_planning_access_workflow_v1<br>procurement.0024_purchase_fulfillment_inventory_v1|2|
|procurement|0026_location_lot_identity_a1|2026-09-01T14:05:17+08:00|masterdata.0009_unit_and_code_governance_a1<br>procurement.0025_purchase_request_purchase_plan_source_v1|4|
|procurement|0027_inventory_dimensions_a15|2026-09-01T14:05:17+08:00|procurement.0026_location_lot_identity_a1|13|
|procurement|0028_completed_module_read_permissions|2026-09-27T20:15:03+08:00|procurement.0027_inventory_dimensions_a15|1|
|purchase|0001_initial|2026-05-31T23:36:53+08:00|ROOT|1|
|purchase|0002_alter_purchaseorder_options_and_more|2026-06-12T22:36:24+08:00|purchase.0001_initial|29|
|purchase_accounts_payable_draft|0001_initial|2026-09-01T14:05:17+08:00|purchase_invoice_prepare.0002_legalentityinvoiceauthorityrecord_and_more<br>reconciliation.0003_businessdocumentnumberreservation_reusable<br>system.__first__|11|
|purchase_canary|0001_initial|2026-09-27T20:15:03+08:00|ROOT|8|
|purchase_canary|0002_purchasecanarylineage|2026-09-27T20:15:03+08:00|purchase_canary.0001_initial|3|
|purchase_invoice_prepare|0001_initial|2026-09-01T14:05:17+08:00|reconciliation.0002_payablecheckauthorityrecord_and_more<br>system.__first__|8|
|purchase_invoice_prepare|0002_legalentityinvoiceauthorityrecord_and_more|2026-09-01T14:05:17+08:00|purchase_invoice_prepare.0001_initial<br>reconciliation.0002_payablecheckauthorityrecord_and_more<br>system.__first__|34|
|reconciliation|0001_initial|2026-09-01T14:05:17+08:00|system.__first__|10|
|reconciliation|0002_payablecheckauthorityrecord_and_more|2026-09-01T14:05:17+08:00|reconciliation.0001_initial<br>system.__first__|11|
|reconciliation|0003_businessdocumentnumberreservation_reusable|2026-09-01T14:05:17+08:00|reconciliation.0002_payablecheckauthorityrecord_and_more|1|
|sales|0001_initial|2026-09-01T14:05:17+08:00|masterdata.0007_supplier_material_price_manual_source_r5<br>system.0010_positionworkflowresponsibility_workflow_node<br>workflow_runtime.0006_merge_formal_definitions_and_payment_backfill<br>system.__first__|7|
|sales|0002_sales_order_engineering_refs_a15|2026-09-01T14:05:17+08:00|pde.0008_engineering_fact_source_a15<br>sales.0001_initial|3|
|sales|0003_industrial_order_engineering_input_do1|2026-09-01T14:05:17+08:00|masterdata.0010_material_unit_confirmation_a1_final<br>pde.0016_a1_final_industry_semantics<br>pfm.0003_enterprise_organization_model_v1<br>sales.0002_sales_order_engineering_refs_a15<br>system.0013_process_workshop_a1_final<br>workflow_runtime.0006_merge_formal_definitions_and_payment_backfill<br>system.__first__|19|
|sales|0004_order_operating_system_v1|2026-09-27T20:15:03+08:00|pde.0019_manufacturing_structure_wave2<br>sales.0003_industrial_order_engineering_input_do1<br>system.0014_workshop_encoder_and_operation_measurement<br>workflow_runtime.0006_merge_formal_definitions_and_payment_backfill<br>system.__first__|14|
|sales|0005_sales_order_item_tax_snapshot|2026-09-27T20:15:03+08:00|sales.0004_order_operating_system_v1|3|
|supplier_performance|0001_initial|2026-09-27T20:15:03+08:00|ROOT|3|
|supplier_performance|0002_v82_difference_collaboration|2026-09-27T20:15:03+08:00|supplier_performance.0001_initial|9|
|supplier_performance|0003_v83_payable_payment_request|2026-09-27T20:15:03+08:00|supplier_performance.0002_v82_difference_collaboration|6|
|supplier_performance|0004_v831_workflow_actions|2026-09-27T20:15:03+08:00|supplier_performance.0003_v83_payable_payment_request<br>system.__first__|4|
|supplier_performance|0005_v84_payment_status_closed_loop|2026-09-27T20:15:03+08:00|supplier_performance.0004_v831_workflow_actions|11|
|supplier_performance|0006_formal_supplier_settlement_14_22_v1|2026-09-27T20:15:03+08:00|supplier_performance.0005_v84_payment_status_closed_loop<br>system.0010_positionworkflowresponsibility_workflow_node<br>workflow_runtime.0006_merge_formal_definitions_and_payment_backfill<br>procurement.0024_purchase_fulfillment_inventory_v1|8|
|system|0001_initial|2026-05-31T23:36:53+08:00|auth.0012_alter_user_first_name_max_length|8|
|system|0002_permission_role_rolepermission|2026-06-12T22:36:24+08:00|system.0001_initial|3|
|system|0003_menu_rolemenu|2026-06-12T22:36:24+08:00|system.0002_permission_role_rolepermission|2|
|system|0004_erp_access_foundation|2026-09-01T14:05:17+08:00|system.0003_menu_rolemenu|2|
|system|0005_organization_access_core_v1|2026-09-01T14:05:17+08:00|system.0004_erp_access_foundation<br>workflow_runtime.0001_initial|4|
|system|0006_enterprise_organization_model_v1|2026-09-01T14:05:17+08:00|system.0005_organization_access_core_v1|25|
|system|0007_remove_department_cost_center_and_more|2026-09-01T14:05:17+08:00|system.0006_enterprise_organization_model_v1|10|
|system|0008_position_effective_period|2026-09-01T14:05:17+08:00|system.0007_remove_department_cost_center_and_more|2|
|system|0009_responsibility_lifecycle_v1|2026-09-01T14:05:17+08:00|system.0008_position_effective_period|3|
|system|0010_positionworkflowresponsibility_workflow_node|2026-09-01T14:05:17+08:00|system.0009_responsibility_lifecycle_v1<br>workflow_runtime.0005_workflownodedefinition_and_more|1|
|system|0011_process_operation_governance_a1|2026-09-01T14:05:17+08:00|pde.0006_production_master_data_a1<br>system.0010_positionworkflowresponsibility_workflow_node|10|
|system|0012_remove_process_system_process_standard_hours_nonnegative_and_more|2026-09-01T14:05:17+08:00|pde.0012_engineeringbreakdownitem_and_more<br>system.0011_process_operation_governance_a1|4|
|system|0013_process_workshop_a1_final|2026-09-01T14:05:17+08:00|system.0012_remove_process_system_process_standard_hours_nonnegative_and_more|1|
|system|0014_workshop_encoder_and_operation_measurement|2026-08-31T16:51:05+08:00|masterdata.0011_foundation_identity_uom_and_encoders<br>system.0013_process_workshop_a1_final|7|
|system|0015_process_default_transition_mode|2026-09-27T20:15:03+08:00|system.0014_workshop_encoder_and_operation_measurement|1|
|system|0016_process_display_order|2026-09-27T20:15:03+08:00|system.0015_process_default_transition_mode|4|
|system|0017_team_operation_capability|2026-09-27T20:15:03+08:00|pfm.0003_enterprise_organization_model_v1<br>system.0016_process_display_order|7|
|workflow_runtime|0001_initial|2026-09-01T14:05:17+08:00|system.__first__|10|
|workflow_runtime|0002_business_state_transition|2026-09-01T14:05:17+08:00|workflow_runtime.0001_initial<br>system.__first__|1|
|workflow_runtime|0003_transition_fact_integrity|2026-09-01T14:05:17+08:00|reconciliation.0003_businessdocumentnumberreservation_reusable<br>workflow_runtime.0002_business_state_transition|16|
|workflow_runtime|0004_payment_chain_transition_backfill|2026-09-01T14:05:17+08:00|workflow_runtime.0003_transition_fact_integrity<br>payment_request_prepare.0001_initial<br>payment_request.0002_state_machine_semantics<br>payment_instruction_prepare.0002_state_machine_semantics<br>payment_order_prepare.0002_state_machine_semantics<br>payment_order_draft.0002_state_machine_semantics|1|
|workflow_runtime|0005_workflownodedefinition_and_more|2026-09-01T14:05:17+08:00|workflow_runtime.0002_business_state_transition|9|
|workflow_runtime|0006_merge_formal_definitions_and_payment_backfill|2026-09-01T14:05:17+08:00|workflow_runtime.0004_payment_chain_transition_backfill<br>workflow_runtime.0005_workflownodedefinition_and_more|0|

## 叶节点

- `bank_send_execution_gate.0001_initial`
- `bank_send_execution_simulation.0005_v68_execution_framework_design`
- `bank_send_preparation.0001_initial`
- `bank_send_request.0001_initial`
- `bank_send_task.0003_banksendtaskcanarypoolentry`
- `formal_payment_order.0004_state_consistency_contract`
- `masterdata.0013_manufacturing_plant_phase_a`
- `mes.0001_manufacturing_domain_foundation_phase_a`
- `payable_confirmation_prepare.0001_initial`
- `payment_instruction_prepare.0002_state_machine_semantics`
- `payment_order_draft.0002_state_machine_semantics`
- `payment_order_prepare.0002_state_machine_semantics`
- `payment_request.0002_state_machine_semantics`
- `payment_request_prepare.0001_initial`
- `payment_risk_review.0002_paymentriskreview_scenario_code`
- `pde.0031_operation_time_standard_phase_a_rebased`
- `pfm.0003_enterprise_organization_model_v1`
- `planning.0006_material_plant_profile_phase_a`
- `procurement.0028_completed_module_read_permissions`
- `purchase.0002_alter_purchaseorder_options_and_more`
- `purchase_accounts_payable_draft.0001_initial`
- `purchase_canary.0002_purchasecanarylineage`
- `purchase_invoice_prepare.0002_legalentityinvoiceauthorityrecord_and_more`
- `reconciliation.0003_businessdocumentnumberreservation_reusable`
- `sales.0005_sales_order_item_tax_snapshot`
- `supplier_performance.0006_formal_supplier_settlement_14_22_v1`
- `system.0017_team_operation_capability`
- `workflow_runtime.0006_merge_formal_definitions_and_payment_backfill`

## 特殊关系

- `workflow_runtime.0006_merge_formal_definitions_and_payment_backfill`：0 operations，显式双父合并节点，不是伪造迁移。
- `replaces`：无。
- Loader conflicts：无。


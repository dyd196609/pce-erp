# Phase B Replay Dependency Closure Report

## 1. 分析范围与规则

- Source Commit：`969a86fe4a1b8557e8c837d19c58e9a9cc5d8fba`
- 节点数：153
- Allowlist映射：153/153
- 项目内缺失依赖：0
- 规则：A节点依赖任何B/C节点时，不得INCLUDE；传播结果标记为`REDESIGN REQUIRED`，但不自动选择重设计、整体排除或纳入上游重新授权。

## 2. 按App统计

|App|Total|INCLUDE|EXCLUDE|REDESIGN REQUIRED|
|---|---:|---:|---:|---:|
|bank_send_execution_gate|1|1|0|0|
|bank_send_execution_simulation|5|5|0|0|
|bank_send_preparation|1|1|0|0|
|bank_send_request|1|1|0|0|
|bank_send_task|3|3|0|0|
|formal_payment_order|4|4|0|0|
|masterdata|13|3|0|10|
|mes|1|0|0|1|
|payable_confirmation_prepare|1|1|0|0|
|payment_instruction_prepare|2|2|0|0|
|payment_order_draft|2|2|0|0|
|payment_order_prepare|2|2|0|0|
|payment_request|2|2|0|0|
|payment_request_prepare|1|1|0|0|
|payment_risk_review|2|2|0|0|
|pde|31|5|1|25|
|pfm|3|1|0|2|
|planning|6|0|1|5|
|procurement|28|7|0|21|
|purchase|2|2|0|0|
|purchase_accounts_payable_draft|1|1|0|0|
|purchase_canary|2|2|0|0|
|purchase_invoice_prepare|2|2|0|0|
|reconciliation|3|3|0|0|
|sales|5|0|1|4|
|supplier_performance|6|5|0|1|
|system|17|10|0|7|
|workflow_runtime|6|6|0|0|

## 3. B/C排除传播

原A节点因直接或间接依赖B/C被阻断：62项。

|App|Migration|直接阻断依赖|待决处理选项|
|---|---|---|---|
|masterdata|0005_project_selector_linkage_r5|`masterdata.0004_enterprise_procurement_dimensions_r4`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|masterdata|0006_price_approval_result_supplier_material_price_v45_8|`masterdata.0005_project_selector_linkage_r5`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|masterdata|0007_supplier_material_price_manual_source_r5|`masterdata.0006_price_approval_result_supplier_material_price_v45_8`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|masterdata|0008_material_supply_governance_a0|`masterdata.0007_supplier_material_price_manual_source_r5`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|masterdata|0009_unit_and_code_governance_a1|`masterdata.0008_material_supply_governance_a0`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|masterdata|0010_material_unit_confirmation_a1_final|`masterdata.0009_unit_and_code_governance_a1`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|masterdata|0013_manufacturing_plant_phase_a|`masterdata.0012_standard_uom_initialization_v12`<br>`system.0014_workshop_encoder_and_operation_measurement`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|mes|0001_manufacturing_domain_foundation_phase_a|`masterdata.0013_manufacturing_plant_phase_a`<br>`pfm.0003_enterprise_organization_model_v1`<br>`system.0014_workshop_encoder_and_operation_measurement`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|pde|0006_production_master_data_a1|`masterdata.0009_unit_and_code_governance_a1`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|pde|0008_engineering_fact_source_a15|`pde.0007_production_master_permissions_and_codes_a1`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|pde|0009_stable_business_references_a15|`pde.0008_engineering_fact_source_a15`<br>`planning.0004_engineering_and_plan_compatibility_a15`<br>`sales.0002_sales_order_engineering_refs_a15`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|pde|0010_engineering_permissions_a15|`pde.0009_stable_business_references_a15`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|pde|0012_engineeringbreakdownitem_and_more|`pde.0011_plan_operator_engineering_authority_a15`<br>`sales.0002_sales_order_engineering_refs_a15`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|pde|0014_alter_productcategory_industry_type|`pde.0013_production_unified_model_permissions_a17`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|pde|0015_standard_capacity_measurement_status_a1_final|`pde.0014_alter_productcategory_industry_type`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|pde|0019_manufacturing_structure_wave2|`masterdata.0012_standard_uom_initialization_v12`<br>`pde.0018_engineering_calculation_closure_do3`<br>`system.0014_workshop_encoder_and_operation_measurement`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|pde|0020_group3_transition_mode_override|`pde.0019_manufacturing_structure_wave2`<br>`system.0015_process_default_transition_mode`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|pde|0021_group3a_operation_executor_authority|`pde.0020_group3_transition_mode_override`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|pde|0022_manufacturing_definition_applicability|`sales.0004_order_operating_system_v1`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|pde|0023_order_engineering_calculation_bom_closure|`masterdata.0012_standard_uom_initialization_v12`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|pde|0024_engineering_breakdown_option|`pde.0023_order_engineering_calculation_bom_closure`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|pde|0025_order_cross_functional_review|`pde.0024_engineering_breakdown_option`<br>`system.0017_team_operation_capability`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|pde|0026_order_review_itemized|`pfm.0003_enterprise_organization_model_v1`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|pde|0027_order_review_participant_grant|`pde.0026_order_review_itemized`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|pde|0028_product_design_plan_content_completion|`masterdata.0012_standard_uom_initialization_v12`<br>`sales.0005_sales_order_item_tax_snapshot`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|pde|0029_product_design_plan_group_scope|`pde.0028_product_design_plan_content_completion`<br>`sales.0005_sales_order_item_tax_snapshot`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|pde|0030_order_engineering_baseline|`pde.0029_product_design_plan_group_scope`<br>`sales.0005_sales_order_item_tax_snapshot`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|pde|0031_operation_time_standard_phase_a_rebased|`masterdata.0013_manufacturing_plant_phase_a`<br>`system.0014_workshop_encoder_and_operation_measurement`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|pfm|0003_enterprise_organization_model_v1|`pfm.0002_employee_formal_organization_relations`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|planning|0001_initial|`masterdata.0007_supplier_material_price_manual_source_r5`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|planning|0003_demand_sales_order_source|`planning.0002_planning_access_workflow_v1`<br>`sales.0001_initial`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|planning|0004_engineering_and_plan_compatibility_a15|`planning.0003_demand_sales_order_source`<br>`pde.0008_engineering_fact_source_a15`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|planning|0006_material_plant_profile_phase_a|`masterdata.0013_manufacturing_plant_phase_a`<br>`planning.0005_order_planning_chain_v1`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|procurement|0008_purchase_request_enterprise_model_r4|`masterdata.0004_enterprise_procurement_dimensions_r4`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|procurement|0009_purchase_request_business_flow_r7|`procurement.0008_purchase_request_enterprise_model_r4`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|procurement|0010_supplier_quotation_v11428422|`procurement.0009_purchase_request_business_flow_r7`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|procurement|0011_quote_comparison_fact_v11428423_r5|`procurement.0010_supplier_quotation_v11428422`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|procurement|0012_price_approval_preparation_v11428424|`procurement.0011_quote_comparison_fact_v11428423_r5`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|procurement|0013_price_approval_legacy_projection_v11428424_r3|`procurement.0012_price_approval_preparation_v11428424`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|procurement|0014_price_approval_projection_snapshot_v11428424_r3|`procurement.0013_price_approval_legacy_projection_v11428424_r3`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|procurement|0015_price_approval_review_result_v11428424_r23|`procurement.0014_price_approval_projection_snapshot_v11428424_r3`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|procurement|0016_supplier_master_completeness_v11428427227|`procurement.0015_price_approval_review_result_v11428424_r23`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|procurement|0017_supplier_category_classification_v11428427227|`procurement.0016_supplier_master_completeness_v11428427227`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|procurement|0018_supplier_delivery_address_v11428427228|`procurement.0017_supplier_category_classification_v11428427227`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|procurement|0019_supplier_master_reverse_enrichment_v1142842724511|`procurement.0018_supplier_delivery_address_v11428427228`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|procurement|0020_standard_purchase_price_link_v46_batch2|`masterdata.0006_price_approval_result_supplier_material_price_v45_8`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|procurement|0021_purchase_mode_entry_v46_batch22_r1|`procurement.0020_standard_purchase_price_link_v46_batch2`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|procurement|0022_direct_price_source_trace_v46_batch22_r2|`masterdata.0006_price_approval_result_supplier_material_price_v45_8`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|procurement|0023_purchase_order_buyer_employee_r5|`procurement.0022_direct_price_source_trace_v46_batch22_r2`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|procurement|0025_purchase_request_purchase_plan_source_v1|`planning.0002_planning_access_workflow_v1`<br>`procurement.0024_purchase_fulfillment_inventory_v1`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|procurement|0026_location_lot_identity_a1|`procurement.0025_purchase_request_purchase_plan_source_v1`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|procurement|0027_inventory_dimensions_a15|`procurement.0026_location_lot_identity_a1`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|procurement|0028_completed_module_read_permissions|`procurement.0027_inventory_dimensions_a15`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|sales|0002_sales_order_engineering_refs_a15|`pde.0008_engineering_fact_source_a15`<br>`sales.0001_initial`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|sales|0005_sales_order_item_tax_snapshot|`sales.0004_order_operating_system_v1`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|system|0011_process_operation_governance_a1|`pde.0006_production_master_data_a1`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|system|0012_remove_process_system_process_standard_hours_nonnegative_and_more|`pde.0012_engineeringbreakdownitem_and_more`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|system|0013_process_workshop_a1_final|`system.0012_remove_process_system_process_standard_hours_nonnegative_and_more`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|system|0014_workshop_encoder_and_operation_measurement|`masterdata.0011_foundation_identity_uom_and_encoders`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|system|0015_process_default_transition_mode|`system.0014_workshop_encoder_and_operation_measurement`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|system|0016_process_display_order|`system.0015_process_default_transition_mode`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|
|system|0017_team_operation_capability|`pfm.0003_enterprise_organization_model_v1`<br>`system.0016_process_display_order`|OPTION 1 重新设计依赖 / OPTION 2 整体排除 / OPTION 3 纳入上游并重新授权；未自动选择|

## 4. Planning专项

- `planning.0005_order_planning_chain_v1`：B — EXCLUDE FROM REPLAY；
- `planning.0006_material_plant_profile_phase_a`：直接依赖0005；当前为BLOCKED，不得进入Manifest INCLUDE；
- 更早的`planning.0002`为C，导致0003、0004及其后续链无法形成纯A闭包；
- 需要独立裁决：OPTION 1重新设计依赖；OPTION 2整体排除；OPTION 3纳入上游并重新授权。本任务不自动选择。

## 5. PFM专项

- `pfm.0002_employee_formal_organization_relations`：C — REDESIGN REQUIRED；
- `pfm.0003_enterprise_organization_model_v1`直接依赖0002，因此同步BLOCKED；
- 当前仅`pfm.0001_initial`保持依赖闭包可包含；
- PFM未收敛链不得进入Replay执行集合。

## 6. PDE专项

- PDE 0020–0022的活动候选身份已签署并保留历史追溯；
- 当前活动0020依赖已被上游阻断的PDE 0019；0021依赖0020；0022还依赖被阻断的Sales链；
- 因此0020–0022在本Execution Manifest中均为REDESIGN REQUIRED，不引入任何历史未选同号链；
- 历史0020–0022仅作为Evidence，不是当前DAG节点。

## 7. Permission Seed专项

所有带Permission Seed、Role Seed或组织关系写入的Migration均按R5签署结果参与闭包。A类只在整个依赖闭包为A时可进入INCLUDE；B/C类及其被传播阻断的下游节点不得执行。不得将Schema operation与同一Migration内未授权Data Operation拆开执行或fake为已应用。

## 8. 结论

```text
DEPENDENCY CLOSURE = BLOCKED
INCLUDE = 74
EXCLUDE = 3
REDESIGN REQUIRED = 76
```


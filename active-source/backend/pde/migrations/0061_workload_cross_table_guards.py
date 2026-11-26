from django.db import migrations

def install(apps,editor):
    if editor.connection.vendor!='sqlite':raise RuntimeError('Backend-specific workload guards require review')
    tests={
      'input_scope':("pde_engineering_fact_input", "NEW.source_kind='FROZEN_TEST_DETAIL' AND NOT EXISTS(SELECT 1 FROM pde_engineering_derived_fact f JOIN pde_engineering_calculation_record t ON t.id=f.calculation_id JOIN pde_engineering_calculation_detail d ON d.id=NEW.source_detail_id JOIN pde_engineering_calculation_record r ON r.id=d.calculation_id JOIN pde_order_engineering_baseline_item b ON b.id=NEW.source_baseline_item_id WHERE f.id=NEW.fact_id AND t.usage_purpose='TEST_BUSINESS' AND r.usage_purpose='TEST_BUSINESS' AND r.scope='test_business' AND r.status='completed' AND t.scope='fact_extension' AND t.origin_calculation_id=r.id AND t.company_id=r.company_id AND t.source_record_id=r.source_record_id AND t.sales_order_item_id=r.sales_order_item_id AND t.engineering_instance_id=r.engineering_instance_id AND b.baseline_id=r.baseline_id AND d.status='succeeded' AND JSON_EXTRACT(d.input_snapshot,'$.componentKey')=NEW.component_key)"),
      'requirement_scope':("pde_engineering_operation_requirement", "NEW.usage_purpose='TEST_BUSINESS' AND NOT EXISTS(SELECT 1 FROM pde_order_routing_execution_arrangement a JOIN pde_routing_step s ON s.id=NEW.routing_step_id JOIN pde_engineering_calculation_record c ON c.id=NEW.calculation_id JOIN pde_engineering_calculation_record t ON t.id=NEW.source_calculation_id JOIN pde_engineering_calculation_record r ON r.id=t.origin_calculation_id JOIN pde_order_engineering_baseline_item b ON b.id=NEW.baseline_item_id WHERE a.id=NEW.execution_arrangement_id AND a.usage_purpose='TEST_BUSINESS' AND c.usage_purpose='TEST_BUSINESS' AND t.usage_purpose='TEST_BUSINESS' AND r.usage_purpose='TEST_BUSINESS' AND a.source_calculation_id=r.id AND a.company_id=c.company_id AND c.company_id=t.company_id AND t.company_id=r.company_id AND c.source_record_id=r.source_record_id AND c.sales_order_item_id=r.sales_order_item_id AND c.engineering_instance_id=r.engineering_instance_id AND a.arrangement_revision=NEW.arrangement_revision AND a.edit_version=NEW.arrangement_edit_version AND s.routing_version_id=a.routing_version_id AND s.operation_id=NEW.operation_id AND b.baseline_id=r.baseline_id AND length(NEW.arrangement_snapshot_hash)=64 AND NEW.component_key!='')"),
      'requirement_purpose':("pde_engineering_operation_requirement", "NEW.usage_purpose NOT IN ('TEST_BUSINESS','PRODUCTION_USE','UNCLASSIFIED') OR (NEW.usage_purpose='PRODUCTION_USE' AND NOT EXISTS(SELECT 1 FROM pde_engineering_calculation_record c JOIN pde_engineering_calculation_record s ON s.id=NEW.source_calculation_id WHERE c.id=NEW.calculation_id AND c.usage_purpose='PRODUCTION_USE' AND s.usage_purpose='PRODUCTION_USE'))"),
    }
    for name,(table,predicate) in tests.items():
        editor.execute('CREATE TRIGGER pde_workload_cross_'+name+' BEFORE INSERT ON '+table+' WHEN '+predicate+" BEGIN SELECT RAISE(ABORT,'WORKLOAD_CROSS_TABLE_REJECTED'); END")
    editor.execute("CREATE TRIGGER pde_workload_input_no_update BEFORE UPDATE ON pde_engineering_fact_input BEGIN SELECT RAISE(ABORT,'WORKLOAD_INPUT_IMMUTABLE'); END")
    editor.execute("CREATE TRIGGER pde_workload_test_req_no_update BEFORE UPDATE ON pde_engineering_operation_requirement WHEN OLD.usage_purpose='TEST_BUSINESS' BEGIN SELECT RAISE(ABORT,'WORKLOAD_REQUIREMENT_IMMUTABLE'); END")

def remove(apps,editor):
    for name in ('cross_input_scope','cross_requirement_scope','cross_requirement_purpose','input_no_update','test_req_no_update'):editor.execute('DROP TRIGGER IF EXISTS pde_workload_'+name)

class Migration(migrations.Migration):
    dependencies=[('pde','0060_workload_usage_consumer_guards')]
    operations=[migrations.RunPython(install,remove)]

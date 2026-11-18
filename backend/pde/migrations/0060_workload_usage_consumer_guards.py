from django.db import migrations

def guards(apps, editor):
    if editor.connection.vendor!='sqlite': raise RuntimeError('Usage guards require reviewed backend-specific DDL')
    statements={}
    for event in ('INSERT','UPDATE'):
        statements['allocation_'+event]=f"BEFORE {event} ON pde_production_plan_operation_requirement_allocation WHEN NOT EXISTS(SELECT 1 FROM pde_engineering_operation_requirement r JOIN pde_engineering_calculation_record c ON c.id=r.calculation_id JOIN pde_engineering_calculation_record s ON s.id=r.source_calculation_id WHERE r.id=NEW.operation_requirement_id AND r.usage_purpose='PRODUCTION_USE' AND c.usage_purpose='PRODUCTION_USE' AND s.usage_purpose='PRODUCTION_USE') BEGIN SELECT RAISE(ABORT,'SOURCE_PURPOSE_REJECTED'); END"
        statements['input_'+event]=f"BEFORE {event} ON pde_engineering_fact_input WHEN NOT ((NEW.source_kind='DERIVED_FACT' AND NEW.source_fact_id IS NOT NULL AND NEW.source_detail_id IS NULL AND NEW.source_baseline_item_id IS NULL AND NEW.component_key='') OR (NEW.source_kind='FROZEN_TEST_DETAIL' AND NEW.source_fact_id IS NULL AND NEW.source_detail_id IS NOT NULL AND NEW.source_baseline_item_id IS NOT NULL AND NEW.component_key!='')) BEGIN SELECT RAISE(ABORT,'INPUT_SOURCE_BRANCH_INVALID'); END"
    statements['calculation_immutable']="BEFORE UPDATE ON pde_engineering_calculation_record WHEN OLD.usage_purpose!=NEW.usage_purpose BEGIN SELECT RAISE(ABORT,'USAGE_PURPOSE_IMMUTABLE'); END"
    statements['requirement_immutable']="BEFORE UPDATE ON pde_engineering_operation_requirement WHEN OLD.usage_purpose!=NEW.usage_purpose BEGIN SELECT RAISE(ABORT,'USAGE_PURPOSE_IMMUTABLE'); END"
    for name,sql in statements.items():editor.execute('CREATE TRIGGER pde_workload_usage_'+name+' '+sql)

def reverse(apps, editor):
    for name in ('allocation_INSERT','allocation_UPDATE','input_INSERT','input_UPDATE','calculation_immutable','requirement_immutable'):editor.execute('DROP TRIGGER IF EXISTS pde_workload_usage_'+name)

class Migration(migrations.Migration):
    dependencies=[('pde','0059_order_execution_workload_contract')]
    operations=[migrations.RunPython(guards,reverse)]
